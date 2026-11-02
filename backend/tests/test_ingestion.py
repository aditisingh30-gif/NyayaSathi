import io
import fitz  # PyMuPDF
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.ingestion.validator import PDFValidator, PDFValidationError
from app.ingestion.cleaner import TextCleaner
from app.ingestion.extractor import PDFExtractor, SECTION_PATTERN
from app.ingestion.chunker import LegalChunker, ExtractedDocument, ExtractedPage
from app.services.embedding_service import EmbeddingService
from app.database.vector_store import VectorStoreService, VectorStoreError
from app.services.ingestion_service import DocumentIngestionService
from app.config import settings


def create_sample_legal_pdf_bytes(
    title: str = "THE RIGHT TO INFORMATION ACT, 2005",
    sections_text: list = None
) -> bytes:
    """Helper to generate an authentic in-memory legal PDF for automated tests."""
    doc = fitz.open()
    doc.set_metadata({"title": title, "author": "Legislative Department, Ministry of Law and Justice"})

    if sections_text is None:
        sections_text = [
            (
                "Section 3. Right to information.-\n"
                "Subject to the provisions of this Act, all citizens shall have the right to information.\n\n"
                "Section 4. Obligations of public authorities.-\n"
                "(1) Every public authority shall maintain all its records duly catalogued and indexed in a manner "
                "and the form which facilitates the right to information under this Act and ensure that all records "
                "that are appropriate to be computerised are, within a reasonable time and subject to availability of "
                "resources, computerised and connected through a network all over the country on different systems "
                "so that access to such records is facilitated."
            ),
            (
                "Section 7. Disposal of request.-\n"
                "(1) Subject to the proviso to sub-section (2) of section 5 or the proviso to sub-section (3) of "
                "section 6, the Central Public Information Officer or State Public Information Officer, as the case "
                "may be, on receipt of a request under section 6 shall, as expeditiously as possible, and in any case "
                "within thirty days of the receipt of the request, either provide the information on payment of such "
                "fee as may be prescribed or reject the request for any of the reasons specified in sections 8 and 9:\n"
                "Provided that where the information sought for concerns the life or liberty of a person, the same "
                "shall be provided within forty-eight hours of the receipt of the request."
            )
        ]

    for page_content in sections_text:
        page = doc.new_page(width=595, height=842)  # A4 size
        # Add running header
        page.insert_text((50, 40), "THE RIGHT TO INFORMATION ACT, 2005 (ACT NO. 22 OF 2005)", fontsize=9)
        # Add page body content
        rect = fitz.Rect(50, 70, 545, 780)
        page.insert_textbox(rect, page_content, fontsize=11)
        # Add footer
        page.insert_text((280, 810), str(doc.page_count), fontsize=9)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# --- Unit Tests: Validator ---

def test_pdf_validation_valid():
    pdf_bytes = create_sample_legal_pdf_bytes()
    is_valid, error = PDFValidator.validate_file_bytes(pdf_bytes, "rti_act_2005.pdf")
    assert is_valid is True
    assert error is None


def test_pdf_validation_invalid_extension():
    pdf_bytes = create_sample_legal_pdf_bytes()
    is_valid, error = PDFValidator.validate_file_bytes(pdf_bytes, "document.txt")
    assert is_valid is False
    assert "Invalid file extension" in error


def test_pdf_validation_empty_bytes():
    is_valid, error = PDFValidator.validate_file_bytes(b"", "empty.pdf")
    assert is_valid is False
    assert "empty" in error.lower()


def test_pdf_validation_corrupted_content():
    corrupted_bytes = b"%PDF-corrupted-data-not-a-real-pdf-body-invalid"
    is_valid, error = PDFValidator.validate_file_bytes(corrupted_bytes, "corrupt.pdf")
    assert is_valid is False
    assert "corrupted" in error.lower() or "unable to parse" in error.lower()


def test_pdf_validation_missing_magic_bytes():
    fake_bytes = b"NOT_A_PDF_CONTENT_HELLO_WORLD"
    is_valid, error = PDFValidator.validate_file_bytes(fake_bytes, "fake.pdf")
    assert is_valid is False
    assert "magic bytes" in error.lower()


# --- Unit Tests: Cleaner ---

def test_text_cleaner_hyphen_merging():
    raw = "The Central Public Infor-\nmation Officer shall provide access."
    cleaned = TextCleaner.fix_hyphenated_linebreaks(raw)
    assert "Information" in cleaned
    assert "Infor-\nmation" not in cleaned


def test_text_cleaner_whitespace():
    raw = "Section  4.\tObligations   of   public authorities.\n\n\n\n(1) Every public authority."
    cleaned = TextCleaner.normalize_whitespace(raw)
    assert "  " not in cleaned
    assert "\t" not in cleaned
    assert "\n\n\n" not in cleaned
    assert "(1) Every public authority." in cleaned


def test_text_cleaner_repetitive_headers():
    pages = [
        "GAZETTE OF INDIA RECURRENT HEADER\nSection 1. Short title.\nSome body text here.\nPage 1",
        "GAZETTE OF INDIA RECURRENT HEADER\nSection 2. Definitions.\nSome body text here.\nPage 2",
        "GAZETTE OF INDIA RECURRENT HEADER\nSection 3. Scope.\nSome body text here.\nPage 3",
    ]
    recurrent = TextCleaner.detect_repetitive_headers_footers(pages, threshold=0.6)
    assert any("GAZETTE OF INDIA" in r for r in recurrent)


# --- Unit Tests: Extractor & Sections ---

def test_pdf_extraction_metadata_and_sections(tmp_path):
    pdf_bytes = create_sample_legal_pdf_bytes()
    pdf_file = tmp_path / "test_rti.pdf"
    pdf_file.write_bytes(pdf_bytes)

    extracted = PDFExtractor.extract_document(
        file_path=pdf_file,
        document_id="doc_test_123",
        act_name_override="The Right to Information Act, 2005"
    )

    assert extracted.total_pages == 2
    assert "Right to Information" in extracted.act_name
    assert len(extracted.pages) == 2

    # Check page 1 has Section 3 and Section 4 identified
    page1 = extracted.pages[0]
    sec_nums = [s["section_number"] for s in page1.sections]
    assert "3" in sec_nums or "4" in sec_nums

    # Verify debug files were persisted
    proc_dir = settings.PROCESSED_DIR / "doc_test_123"
    assert (proc_dir / "raw_extracted.json").exists()
    assert (proc_dir / "cleaned_extracted.json").exists()


# --- Unit Tests: Chunker ---

def test_legal_chunker_section_preservation():
    pdf_bytes = create_sample_legal_pdf_bytes()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, p in enumerate(doc):
        text = p.get_text()
        cleaned = TextCleaner.clean_page_text(text)
        sections = PDFExtractor.identify_sections_on_page(cleaned)
        pages.append(ExtractedPage(page_number=i + 1, raw_text=text, cleaned_text=cleaned, sections=sections))
    doc.close()

    extracted = ExtractedDocument(
        document_id="doc_chunk_test",
        filename="rti.pdf",
        act_name="The Right to Information Act, 2005",
        total_pages=len(pages),
        pages=pages,
        metadata={}
    )

    chunker = LegalChunker(target_chunk_size=500, chunk_overlap=100)
    chunks = chunker.chunk_document(extracted)

    assert len(chunks) >= 2
    for c in chunks:
        assert c.document_id == "doc_chunk_test"
        assert c.act_name == "The Right to Information Act, 2005"
        assert c.page_number in (1, 2)
        assert len(c.text) > 0


# --- Unit Tests: Embedding Service ---

def test_embedding_service_dimensions_and_batch():
    service = EmbeddingService.get_instance()
    texts = [
        "Subject to the provisions of this Act, all citizens shall have the right to information.",
        "Section 4 obligates public authorities to maintain records."
    ]
    embeddings = service.embed_texts(texts)
    assert len(embeddings) == 2
    assert service.embedding_dimension == 384
    assert len(embeddings[0]) == 384
    assert len(embeddings[1]) == 384


# --- Unit Tests: Vector Store & Ingestion Service (Isolated Test DB) ---

def test_vector_store_operations_and_duplicate_prevention(tmp_path):
    test_db_dir = tmp_path / "test_vector_store"
    v_service = VectorStoreService(persist_dir=test_db_dir)

    pdf_bytes = create_sample_legal_pdf_bytes()
    ingestion = DocumentIngestionService(vector_store=v_service)

    # 1. Ingest document
    result = ingestion.process_and_index_pdf(
        file_bytes=pdf_bytes,
        filename="rti_sample.pdf",
        act_name="Right to Information Act, 2005"
    )
    doc_id = result["document_id"]
    assert result["status"] == "indexed"
    assert result["total_chunks"] > 0
    assert result["total_pages"] == 2

    # 2. Verify stored in ChromaDB
    chunks_count = v_service.count_chunks(doc_id)
    assert chunks_count == result["total_chunks"]

    # 3. Retrieve document by ID
    doc_info = v_service.get_document(doc_id)
    assert doc_info is not None
    assert doc_info["filename"] == "rti_sample.pdf"

    # 4. Duplicate upload prevention test
    with pytest.raises(PDFValidationError) as exc_info:
        ingestion.process_and_index_pdf(
            file_bytes=pdf_bytes,
            filename="rti_sample_copy.pdf"
        )
    assert "already indexed" in str(exc_info.value).lower()

    # 5. Delete document test (preserves raw file)
    del_res = v_service.delete_document(doc_id, delete_raw_file=False)
    assert del_res["deleted"] is True
    assert v_service.count_chunks(doc_id) == 0
    assert v_service.get_document(doc_id) is None


# --- Integration Tests: API Endpoints ---

client = TestClient(app)


def test_api_document_upload_and_lifecycle():
    pdf_bytes = create_sample_legal_pdf_bytes(title="THE MOTOR VEHICLES ACT, 1988")
    files = {"file": ("motor_vehicles_act.pdf", pdf_bytes, "application/pdf")}
    data = {"act_name": "The Motor Vehicles Act, 1988"}

    # 1. Upload valid PDF
    response = client.post("/api/documents/upload", files=files, data=data)
    assert response.status_code == 201
    upload_data = response.json()
    doc_meta = upload_data["document"]
    doc_id = doc_meta["document_id"]
    assert doc_meta["act_name"] == "The Motor Vehicles Act, 1988"
    assert doc_meta["total_chunks"] > 0

    # 2. Get document status
    status_resp = client.get(f"/api/documents/{doc_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "indexed"

    # 3. Get document details
    detail_resp = client.get(f"/api/documents/{doc_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["filename"] == "motor_vehicles_act.pdf"

    # 4. List documents includes this document
    list_resp = client.get("/api/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert any(d["document_id"] == doc_id for d in docs)

    # 5. Attempt duplicate upload returns 409 Conflict
    files_dup = {"file": ("motor_vehicles_act.pdf", pdf_bytes, "application/pdf")}
    dup_resp = client.post("/api/documents/upload", files=files_dup, data=data)
    assert dup_resp.status_code == 409
    assert "already indexed" in dup_resp.json()["detail"].lower()

    # 6. Delete document
    del_resp = client.delete(f"/api/documents/{doc_id}?delete_raw_file=true")
    assert del_resp.status_code == 200

    # 7. Confirm deleted
    confirm_resp = client.get(f"/api/documents/{doc_id}")
    assert confirm_resp.status_code == 404
