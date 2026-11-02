import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.retrieval.query_processor import QueryProcessor
from app.retrieval.retriever import LegalRetriever
from app.database.vector_store import VectorStoreService

client = TestClient(app)


# --- Unit Tests: Query Processor ---

def test_query_processor_section_extraction():
    # Standard Section
    p1 = QueryProcessor.process_query("What does Section 35 specify about filing complaints?")
    assert p1.target_section == "35"

    # Subsection
    p2 = QueryProcessor.process_query("Who is a consumer under Section 2(7)?")
    assert p2.target_section == "2(7)"

    # Hinglish 'dhara'
    p3 = QueryProcessor.process_query("Dhara 84 ke tehat product liability kya hai?")
    assert p3.target_section == "84"

    # Legal abbreviation 'u/s'
    p4 = QueryProcessor.process_query("Jurisdiction of commission u/s 47")
    assert p4.target_section == "47"

    # No section mentioned
    p5 = QueryProcessor.process_query("What are consumer rights in India?")
    assert p5.target_section is None


def test_query_processor_hindi_hinglish_detection():
    # Hinglish query
    q_hinglish = "Upbhokta ke kya adhikar hain aur shikayat kahan darj karein?"
    p1 = QueryProcessor.process_query(q_hinglish)
    assert p1.is_hindi_hinglish is True
    assert "consumer" in p1.detected_keywords
    assert "rights" in p1.detected_keywords
    assert any("complaint" in kw for kw in p1.detected_keywords)
    assert "consumer" in p1.search_query.lower()

    # Devanagari Hindi query
    q_hindi = "उपभोक्ता शिकायत दर्ज करने की प्रक्रिया क्या है?"
    p2 = QueryProcessor.process_query(q_hindi)
    assert p2.is_hindi_hinglish is True
    assert "consumer" in p2.detected_keywords
    assert any("complaint" in kw for kw in p2.detected_keywords)

    # Pure English query
    q_english = "What is the pecuniary jurisdiction of the State Commission?"
    p3 = QueryProcessor.process_query(q_english)
    assert p3.is_hindi_hinglish is False


def test_query_processor_unsupported_act_detection():
    indexed_acts = ["The Consumer Protection Act, 2019"]

    # Query for unindexed Indian Penal Code
    q_ipc = "What is the penalty for cheating under Section 420 of Indian Penal Code?"
    p_ipc = QueryProcessor.process_query(q_ipc, indexed_act_names=indexed_acts)
    assert p_ipc.unsupported_act_detected == "The Indian Penal Code, 1860"

    # Query for unindexed Companies Act
    q_comp = "What are director obligations under Companies Act 2013?"
    p_comp = QueryProcessor.process_query(q_comp, indexed_act_names=indexed_acts)
    assert p_comp.unsupported_act_detected == "The Companies Act, 2013"

    # Query for indexed Consumer Protection Act
    q_cpa = "What is product liability under Consumer Protection Act?"
    p_cpa = QueryProcessor.process_query(q_cpa, indexed_act_names=indexed_acts)
    assert p_cpa.unsupported_act_detected is None
    assert p_cpa.target_act == "The Consumer Protection Act, 2019"


# --- Integration Tests: Semantic & Hybrid Retrieval on Real Ingested Chunks ---

def test_retrieval_on_consumer_protection_act():
    retriever = LegalRetriever()
    result = retriever.retrieve(
        query="Who is defined as a consumer and what is the definition under the Act?",
        top_k=3,
        relevance_threshold=0.30
    )

    assert result.has_sufficient_evidence is True
    assert len(result.chunks) > 0
    top_chunk = result.chunks[0]
    assert "Consumer Protection" in top_chunk.act_name
    assert top_chunk.similarity_score > 0.40
    # The definition of consumer is in Section 2(7) / Section 2
    sections = [c.section_number for c in result.chunks if c.section_number]
    assert any("2" in str(s) for s in sections)


def test_regression_section_2_7_consumer_definition_retrieval():
    """
    Regression test for reported bug:
    'What is the definition of a consumer under Section 2(7) of the Consumer Protection Act, 2019?'
    Must retrieve Section 2(7) on Page 3 as top rank.
    Must NOT retrieve or boost unrelated Section 7.
    """
    retriever = LegalRetriever()
    result = retriever.retrieve(
        query="What is the definition of a consumer under Section 2(7) of the Consumer Protection Act, 2019?",
        top_k=5,
        relevance_threshold=0.30
    )

    assert result.has_sufficient_evidence is True
    assert len(result.chunks) > 0

    top_chunk = result.chunks[0]
    assert top_chunk.section_number == "2(7)"
    assert top_chunk.page_number == 3
    assert top_chunk.is_exact_section_match is True
    assert "consumer" in top_chunk.text.lower()
    assert "buys any goods" in top_chunk.text.lower()

    # Verify unrelated Section 7 is NOT returned or boosted as match
    for chunk in result.chunks:
        assert chunk.section_number != "7"


def test_retrieval_exact_section_match_priority():
    retriever = LegalRetriever()
    # Target Section 35 (Manner in which complaint shall be made to District Commission)
    result = retriever.retrieve(
        query="What is the procedure under Section 35 for making a complaint?",
        top_k=3,
        relevance_threshold=0.25
    )

    assert result.has_sufficient_evidence is True
    # Verify that Section 35 was detected and prioritized
    top_chunk = result.chunks[0]
    assert top_chunk.is_exact_section_match is True
    assert "35" in str(top_chunk.section_number)


def test_retrieval_hindi_hinglish_query():
    retriever = LegalRetriever()
    result = retriever.retrieve(
        query="Upbhokta vivad me shikayat kaise darj karein?",
        top_k=3,
        relevance_threshold=0.25
    )

    assert result.has_sufficient_evidence is True
    assert len(result.chunks) > 0
    # Chunks should be from Consumer Protection Act
    for c in result.chunks:
        assert "Consumer Protection" in c.act_name


def test_retrieval_unsupported_act_flag():
    retriever = LegalRetriever()
    result = retriever.retrieve(
        query="Explain Section 302 of the Indian Penal Code regarding murder punishment.",
        top_k=5
    )

    assert result.is_unsupported_act is True
    assert result.unsupported_act_name == "The Indian Penal Code, 1860"
    assert result.has_sufficient_evidence is False
    assert len(result.chunks) == 0


def test_retrieval_irrelevant_query_filtered():
    retriever = LegalRetriever()
    result = retriever.retrieve(
        query="What is the recipe for baking chocolate cookies with almond butter?",
        top_k=5,
        relevance_threshold=0.55
    )

    # Irrelevant non-legal query should return no evidence at standard threshold
    assert len(result.chunks) == 0
    assert result.has_sufficient_evidence is False


# --- API Endpoint Integration Tests ---

def test_api_retrieval_search_endpoint():
    payload = {
        "query": "What are unfair contracts and misleading advertisements?",
        "top_k": 3,
        "relevance_threshold": 0.30
    }
    response = client.post("/api/retrieval/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "evidence_chunks" in data
    assert data["has_sufficient_evidence"] is True
    assert len(data["evidence_chunks"]) > 0

    chunk = data["evidence_chunks"][0]
    assert "act_name" in chunk
    assert "text" in chunk
    assert "page_number" in chunk
    assert "similarity_score" in chunk
    assert chunk["similarity_score"] >= 0.30


def test_api_retrieval_search_unsupported_act():
    payload = {
        "query": "What are the provisions of Section 138 of Negotiable Instruments Act?",
        "top_k": 3
    }
    response = client.post("/api/retrieval/search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_unsupported_act"] is True
    assert "Negotiable Instruments" in data["unsupported_act_name"]
    assert len(data["evidence_chunks"]) == 0
