import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app
from app.services.citation_verifier import CitationVerifier
from app.retrieval.retriever import EvidenceChunk
from app.database.conversation_store import ConversationStore
from app.llm.factory import LLMProviderFactory
from app.llm.fallback_provider import GroundedSynthesizerProvider

client = TestClient(app)


# --- Unit Tests: Citation Verifier ---

def test_citation_verifier_grounded_and_hallucination():
    evidence = [
        EvidenceChunk(
            chunk_id="c1",
            text="Section 35 specifies the manner in which complaint shall be made to District Commission.",
            act_name="The Consumer Protection Act, 2019",
            section_number="35",
            page_number=18,
            source_file="cpa_2019.pdf",
            document_id="doc1",
            similarity_score=0.88,
            semantic_distance=0.12,
        ),
        EvidenceChunk(
            chunk_id="c2",
            text="Section 2(7) defines 'consumer' as any person who buys any goods or hires any service.",
            act_name="The Consumer Protection Act, 2019",
            section_number="2(7)",
            page_number=2,
            source_file="cpa_2019.pdf",
            document_id="doc1",
            similarity_score=0.92,
            semantic_distance=0.08,
        )
    ]

    # Grounded answer citing Section 35
    grounded_text = "Under Section 35 of the Act, a consumer may file a complaint with the District Commission."
    cites, is_grounded, hallucinated = CitationVerifier.verify_and_build_citations(grounded_text, evidence)
    assert is_grounded is True
    assert len(hallucinated) == 0
    assert len(cites) == 1
    assert "35" in cites[0].section

    # Hallucinated answer citing an unretrieved Section 999
    hallucinated_text = "According to Section 999, the penalties are doubling every month."
    cites2, is_grounded2, hallucinated2 = CitationVerifier.verify_and_build_citations(hallucinated_text, evidence)
    assert is_grounded2 is False
    assert "999" in hallucinated2


# --- Unit Tests: Conversation Store ---

def test_conversation_store_crud(tmp_path):
    test_file = tmp_path / "test_conversations.json"
    store = ConversationStore(storage_path=test_file)

    # 1. Create conversation
    conv_id = store.create_conversation(title="Test Consumer Inquiry")
    assert conv_id.startswith("conv_")

    # 2. Add User Message
    msg_id = store.add_message(conv_id, "user", "What is consumer protection?")
    assert msg_id.startswith("msg_")

    # 3. Add Assistant Message
    store.add_message(
        conv_id,
        "assistant",
        "Consumer protection safeguards buyers against unfair practices.",
        direct_answer="Direct summary",
        legal_explanation="Detailed statutory explanation",
        citations=[]
    )

    # 4. Retrieve conversation
    detail = store.get_conversation(conv_id)
    assert detail is not None
    assert len(detail.messages) == 2
    assert detail.messages[0].role == "user"
    assert detail.messages[1].role == "assistant"

    # 5. List conversations
    summaries = store.list_conversations()
    assert len(summaries) == 1
    assert summaries[0].conversation_id == conv_id
    assert summaries[0].message_count == 2

    # 6. Delete conversation
    assert store.delete_conversation(conv_id) is True
    assert store.get_conversation(conv_id) is None


# --- Unit Tests: LLM Provider Factory ---

def test_llm_factory_fallback_provider():
    provider = LLMProviderFactory.get_provider("fallback")
    assert isinstance(provider, GroundedSynthesizerProvider)
    assert provider.is_available() is True


# --- Integration Tests: End-to-End Chat API ---

def test_regression_chat_section_2_7_consumer_definition():
    """
    Regression test for reported legal citation accuracy bug:
    Question: 'What is the definition of a consumer under Section 2(7) of the Consumer Protection Act, 2019?'
    Must cite Section 2(7) on Page 3.
    Must define consumer accurately.
    Must NOT cite unrelated Section 7.
    """
    payload = {
        "question": "What is the definition of a consumer under Section 2(7) of the Consumer Protection Act, 2019?",
        "provider": "fallback"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Direct answer assertions
    assert "Section 2(7)" in data["direct_answer"]
    assert "Page 3" in data["direct_answer"]
    assert "consumer" in data["direct_answer"].lower()
    assert "Section 7" not in data["direct_answer"]  # Must NEVER cite Section 7

    # Citations assertions
    assert len(data["citations"]) >= 1
    primary_citation = data["citations"][0]
    assert primary_citation["section"] == "Section 2(7)"
    assert primary_citation["page_number"] == 3
    assert "The Consumer Protection Act, 2019" in primary_citation["act_name"]
    assert "consumer" in primary_citation["snippet"].lower()
    assert "buys any goods" in primary_citation["snippet"].lower()

    # Verify no citation references Section 7
    for cite in data["citations"]:
        assert cite["section"] != "Section 7"


def test_chat_endpoint_valid_consumer_act_query():
    payload = {
        "question": "What is the definition of consumer under the Consumer Protection Act, 2019?",
        "provider": "fallback"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["conversation_id"].startswith("conv_")
    assert "consumer" in data["answer"].lower()
    assert data["direct_answer"] is not None
    assert data["legal_explanation"] is not None
    assert len(data["citations"]) > 0
    assert "Consumer Protection" in data["citations"][0]["act_name"]
    assert "educational" in data["disclaimer"].lower() or "not formal legal advice" in data["disclaimer"].lower()


def test_chat_endpoint_unsupported_act_refusal():
    payload = {
        "question": "What is Section 302 of the Indian Penal Code regarding murder?",
        "provider": "fallback"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "not currently indexed" in data["answer"].lower()
    assert "Indian Penal Code" in data["answer"]
    assert len(data["citations"]) == 0  # Crucial: never fabricate citations for unindexed Acts


def test_chat_endpoint_insufficient_evidence_refusal():
    payload = {
        "question": "What are the planetary defense regulations for asteroids in Indian law?",
        "provider": "fallback"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "not available" in data["answer"].lower()
    assert len(data["citations"]) == 0


def test_chat_follow_up_conversation_context():
    # Turn 1: Ask about Section 35
    turn1_payload = {
        "question": "What does Section 35 of the Consumer Protection Act cover?",
        "provider": "fallback"
    }
    r1 = client.post("/api/chat", json=turn1_payload)
    assert r1.status_code == 200
    data1 = r1.json()
    conv_id = data1["conversation_id"]

    # Turn 2: Follow-up question using the same conversation_id
    turn2_payload = {
        "conversation_id": conv_id,
        "question": "What is the manner or procedure specified in this section?",
        "provider": "fallback"
    }
    r2 = client.post("/api/chat", json=turn2_payload)
    assert r2.status_code == 200
    data2 = r2.json()

    assert data2["conversation_id"] == conv_id
    assert len(data2["citations"]) > 0

    # Verify conversation history stored in backend
    conv_resp = client.get(f"/api/conversations/{conv_id}")
    assert conv_resp.status_code == 200
    conv_data = conv_resp.json()
    assert len(conv_data["messages"]) == 4  # 2 user messages, 2 assistant messages


def test_conversations_api_lifecycle():
    # 1. List conversations
    list_resp = client.get("/api/conversations")
    assert list_resp.status_code == 200
    convs = list_resp.json()
    assert isinstance(convs, list)

    if convs:
        test_id = convs[0]["conversation_id"]
        # 2. Get specific conversation
        get_resp = client.get(f"/api/conversations/{test_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["conversation_id"] == test_id

        # 3. Delete specific conversation
        del_resp = client.delete(f"/api/conversations/{test_id}")
        assert del_resp.status_code == 200

        # 4. Confirm deleted returns 404
        get_again = client.get(f"/api/conversations/{test_id}")
        assert get_again.status_code == 404
