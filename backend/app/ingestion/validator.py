import hashlib
import uuid
from pathlib import Path
from typing import Tuple, Optional
import fitz  # PyMuPDF

from app.config import settings
from app.core.logging_config import logger

# Maximum file size allowed (Default: 50MB)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
PDF_MAGIC_BYTES = b"%PDF-"


class PDFValidationError(Exception):
    """Custom exception raised when PDF validation fails."""
    pass


class PDFValidator:
    """Validates PDF files for security, format, size, encryption, and corruption."""

    @staticmethod
    def calculate_file_hash(content: bytes) -> str:
        """Calculate the SHA-256 hash of the document content."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def validate_file_bytes(
        content: bytes,
        filename: str,
        max_size_bytes: int = MAX_FILE_SIZE_BYTES
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate raw file bytes before saving or processing.
        Returns: (is_valid, error_message)
        """
        if not filename.lower().endswith(".pdf"):
            return False, f"Invalid file extension. Expected '.pdf', received '{filename}'."

        if not content or len(content) == 0:
            return False, "Uploaded file is empty (0 bytes)."

        if len(content) > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            actual_mb = len(content) / (1024 * 1024)
            return False, f"File size ({actual_mb:.2f} MB) exceeds maximum allowed size ({max_mb:.0f} MB)."

        # Validate PDF magic bytes header
        if not content.startswith(PDF_MAGIC_BYTES):
            return False, "Invalid PDF format: Missing standard '%PDF-' magic bytes header."

        # Deep validation using PyMuPDF (fitz)
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            try:
                if doc.is_encrypted:
                    return False, "PDF is password-protected or encrypted. Please upload an unencrypted document."

                if doc.page_count == 0:
                    return False, "PDF contains zero pages or is corrupted."

            finally:
                doc.close()
        except fitz.FileDataError as e:
            return False, f"Corrupted PDF file: Unable to parse document structure ({str(e)})."
        except Exception as e:
            return False, f"Failed to validate PDF: {str(e)}"

        return True, None

    @classmethod
    def save_raw_document(
        cls,
        content: bytes,
        filename: str,
        document_id: Optional[str] = None
    ) -> Tuple[str, Path, str]:
        """
        Validate and save an uploaded PDF into the raw documents directory.
        Returns: (document_id, saved_path, file_hash)
        """
        is_valid, error = cls.validate_file_bytes(content, filename)
        if not is_valid:
            logger.warning(f"PDF validation failed for '{filename}': {error}")
            raise PDFValidationError(error)

        doc_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        file_hash = cls.calculate_file_hash(content)

        # Sanitize filename
        safe_name = "".join(c for c in filename if c.isalnum() or c in ("-", "_", "."))
        saved_filename = f"{doc_id}_{safe_name}"
        saved_path = settings.RAW_DOCS_DIR / saved_filename

        try:
            with open(saved_path, "wb") as f:
                f.write(content)
            logger.info(f"Saved raw PDF '{filename}' to '{saved_path}' (ID: {doc_id}, Hash: {file_hash[:8]}...)")
        except Exception as e:
            logger.error(f"Failed to save raw document: {str(e)}")
            raise PDFValidationError(f"Could not persist uploaded file to storage: {str(e)}")

        return doc_id, saved_path, file_hash
