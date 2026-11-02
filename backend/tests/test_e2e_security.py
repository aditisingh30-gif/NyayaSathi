import io
import fitz
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.ingestion.validator import PDFValidator, PDFValidationError
from app.database.vector_store import VectorStoreService
from app.services.ingestion_service import DocumentIngestionService
from app.services.chat_service import ChatService
from app.database.conversation_store import ConversationStore
from app.models.schemas import ChatRequest

client = TestClient(app)


def generate_sample_statute_pdf(title: str, sections: list) -> bytes:
    """Helper to generate an authentic statutory PDF in memory."""
    doc = fitz.open()
    doc.set_metadata({"title": title, "author": "Legislative Department"})
    for sec_num, sec_heading, sec_body in sections:
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 40), f"{title.upper()} (CENTRAL ACT)", fontsize=9)
        content = f"Section {sec_num}. {sec_heading}.-\n{sec_body}"
        rect = fitz.Rect(50, 80, 545, 780)
        page.insert_textbox(rect, content, fontsize=11)
        page.insert_text((280, 810), str(doc.page_count), fontsize=9)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# --- End-to-End Full Lifecycle Test in Isolated Environment ---

def test_full_e2e_lifecycle(tmp_path):
    # Isolated test vector store and conversation store
    test_db_dir = tmp_path / "e2e_vector_store"
    test_conv_file = tmp_path / "e2e_conversations.json"

    vs = VectorStoreService(persist_dir=test_db_dir)
    conv_store = ConversationStore(storage_path=test_conv_file)
    ingestion = DocumentIngestionService(vector_store=vs)

    # 1. Create a sample Act: The Digital Personal Data Protection Act, 2023
    statute_title = "The Digital Personal Data Protection Act, 2023"
    statute_sections = [
        ("4", "Grounds for processing digital personal data",
         "A person may process personal data of a Data Principal only in accordance with the provisions of this Act and for a lawful purpose for which the Data Principal has given her consent."),
        ("8", "General obligations of Data Fiduciary",
         "A Data Fiduciary shall, irrespective of any agreement to the contrary or refusal by Data Principal, make reasonable security safeguards to prevent personal data breach."),
        ("33", "Penalties for failure to take security safeguards",
         "If the Board on conclusion of an inquiry determines significant non-compliance, it may impose financial penalty up to two hundred and fifty crore rupees.")
    ]
    pdf_bytes = generate_sample_statute_pdf(statute_title, statute_sections)

    # 2. Ingest into isolated vector store
    ingest_res = ingestion.process_and_index_pdf(
        file_bytes=pdf_bytes,
        filename="dpdp_act_2023.pdf",
        act_name=statute_title
    )
    doc_id = ingest_res["document_id"]
    assert ingest_res["status"] == "indexed"
    assert ingest_res["total_pages"] == 3
    assert ingest_res["total_chunks"] >= 3
    assert vs.count_chunks(doc_id) == ingest_res["total_chunks"]

    # 3. Create chat service connected to this isolated vector store
    from app.retrieval.retriever import LegalRetriever
    test_retriever = LegalRetriever(vector_store=vs)
    chat_service = ChatService(retriever=test_retriever, conversation_store=conv_store)

    # 4. Turn 1: Ask specific question about Section 8
    q1 = ChatRequest(
        question="What are the obligations of Data Fiduciary under Section 8?",
        provider="fallback"
    )
    import asyncio
    res1 = asyncio.run(chat_service.process_chat(q1))
    assert res1.conversation_id is not None
    assert "Section 8" in res1.answer or "obligation" in res1.answer.lower()
    assert len(res1.citations) > 0
    assert any("Digital Personal Data" in c.act_name for c in res1.citations)
    assert any("8" in (c.section or "") for c in res1.citations)

    # 5. Turn 2: Follow-up question in the same conversation
    q2 = ChatRequest(
        conversation_id=res1.conversation_id,
        question="What is the maximum penalty under Section 33 for security breach failure?",
        provider="fallback"
    )
    res2 = asyncio.run(chat_service.process_chat(q2))
    assert res2.conversation_id == res1.conversation_id
    assert "33" in res2.answer or "two hundred and fifty crore" in res2.answer.lower()
    assert len(res2.citations) > 0

    # 6. Turn 3: Ask about an Unsupported Act (e.g. IPC)
    q3 = ChatRequest(
        conversation_id=res1.conversation_id,
        question="What is Section 302 of the Indian Penal Code?",
        provider="fallback"
    )
    res3 = asyncio.run(chat_service.process_chat(q3))
    assert "not currently indexed" in res3.answer.lower()
    assert len(res3.citations) == 0  # No fake citations

    # 7. Turn 4: Hindi/Hinglish query on penalty
    q4 = ChatRequest(
        conversation_id=res1.conversation_id,
        question="Suraksha niyam todne par kitna jurmana lag sakta hai?",
        provider="fallback"
    )
    res4 = asyncio.run(chat_service.process_chat(q4))
    assert len(res4.citations) > 0

    # 8. Clean up: Delete document from vector store
    del_res = vs.delete_document(doc_id, delete_raw_file=False)
    assert del_res["deleted"] is True
    assert vs.count_chunks(doc_id) == 0


# --- Security & Vulnerability Tests ---

def test_security_non_pdf_upload_rejection():
    # Attempt upload of shell script
    files = {"file": ("malicious.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "Only PDF documents are supported" in response.json()["detail"]


def test_security_fake_header_rejection():
    # File named .pdf but containing arbitrary text
    files = {"file": ("fake.pdf", b"PLAIN_TEXT_NOT_A_REAL_PDF", "application/pdf")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "magic bytes" in response.json()["detail"].lower()


def test_security_empty_pdf_rejection():
    files = {"file": ("zero_bytes.pdf", b"", "application/pdf")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_security_oversized_file_limit():
    validator = PDFValidator()
    # 51MB simulated bytes
    huge_bytes = b"%PDF-1.4 " + b"0" * (51 * 1024 * 1024)
    is_valid, err = validator.validate_file_bytes(huge_bytes, "huge.pdf")
    assert is_valid is False
    assert "exceeds maximum allowed size" in err.lower()


def test_security_sql_injection_in_query():
    # Test that SQL injection / malicious queries are safely treated as text without crashing
    sql_payload = "'; DROP TABLE documents; SELECT * FROM users WHERE '1'='1"
    response = client.post("/api/chat", json={"question": sql_payload, "provider": "fallback"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    # Database remains unaffected and healthy
    health = client.get("/health")
    assert health.status_code == 200


def test_security_xss_payload_in_query():
    # Test script injection in chat query
    xss_payload = "<script>alert('XSS Attack');</script>"
    response = client.post("/api/chat", json={"question": xss_payload, "provider": "fallback"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data


def test_security_empty_question_validation():
    # Empty query should fail Pydantic min_length validation
    response = client.post("/api/chat", json={"question": ""})
    assert response.status_code == 422  # Unprocessable Entity


def test_security_api_keys_not_exposed():
    # Verify health endpoint never exposes API keys or secrets
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    text = health_resp.text.lower()
    assert "api_key" not in text
    assert "secret" not in text
    assert "password" not in text
