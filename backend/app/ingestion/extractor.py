import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF

from app.ingestion.cleaner import TextCleaner
from app.config import settings
from app.core.logging_config import logger


# Common regex patterns for Indian statutory sections and chapters
SECTION_PATTERN = re.compile(
    r"(?:\n|^)\s*(?:Section|Sec\.)?\s*([0-9]+[A-Za-z]?(?:\s*\([0-9a-z]+\))*)\s*[\.\-—–:]\s*([^\n\r]+)",
    re.IGNORECASE
)

STANDALONE_SECTION_PATTERN = re.compile(
    r"(?:\n|^)\s*(?:Section|Sec\.)\s+([0-9]+[A-Za-z]?)(?!\s*\])[\.\-—–:\s]",
    re.IGNORECASE
)

DEFINITION_CLAUSE_PATTERN = re.compile(
    r'(?:\n|^)\s*\(([0-9]+)\)\s*["“\']([^"”\']+)["”\']',
    re.IGNORECASE
)

CHAPTER_PATTERN = re.compile(
    r"(?:\n|^)\s*(CHAPTER\s+[IVXLCDM0-9]+)\s*[\.\-—–:]?\s*([^\n\r]+)?",
    re.IGNORECASE
)


class ExtractedPage:
    """Represents text and metadata extracted from a single PDF page."""
    def __init__(
        self,
        page_number: int,
        raw_text: str,
        cleaned_text: str,
        sections: List[Dict[str, Any]]
    ):
        self.page_number = page_number
        self.raw_text = raw_text
        self.cleaned_text = cleaned_text
        self.sections = sections

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "raw_text": self.raw_text,
            "cleaned_text": self.cleaned_text,
            "sections": self.sections,
        }


class ExtractedDocument:
    """Represents a fully extracted and parsed legal document."""
    def __init__(
        self,
        document_id: str,
        filename: str,
        act_name: str,
        total_pages: int,
        pages: List[ExtractedPage],
        metadata: Dict[str, Any]
    ):
        self.document_id = document_id
        self.filename = filename
        self.act_name = act_name
        self.total_pages = total_pages
        self.pages = pages
        self.metadata = metadata

    def get_full_cleaned_text(self) -> str:
        return "\n\n".join(p.cleaned_text for p in self.pages if p.cleaned_text)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "act_name": self.act_name,
            "total_pages": self.total_pages,
            "metadata": self.metadata,
            "pages": [p.to_dict() for p in self.pages],
        }


class PDFExtractor:
    """Extracts text, metadata, page numbers, and statutory sections from PDFs."""

    @staticmethod
    def detect_act_name(doc: fitz.Document, default_name: Optional[str] = None) -> str:
        """
        Infer the Act or Policy name from PDF metadata or prominent text on the first page.
        """
        if default_name and default_name.strip() and default_name.strip().lower() != "unknown act":
            return default_name.strip()

        # Check PDF metadata title
        meta_title = doc.metadata.get("title", "")
        if meta_title and len(meta_title.strip()) > 4:
            return meta_title.strip()

        # Heuristic: inspect top text lines of the first page
        if doc.page_count > 0:
            first_page = doc[0]
            lines = [l.strip() for l in first_page.get_text("text").split("\n") if l.strip()]
            for line in lines[:8]:
                # Look for 'THE ... ACT, ...' or '... POLICY ...'
                if re.search(r"\b(ACT|CODE|RULES|REGULATIONS|POLICY|BILL)\b", line, re.IGNORECASE):
                    if len(line) < 120:
                        return line.title()

        return "Indian Legal Act / Document"

    @classmethod
    def identify_sections_on_page(cls, text: str, active_section: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Identify statutory sections and definition clauses on a page without inventing section numbers.
        Returns:
            List[Dict[str, Any]] containing identified sections
        """
        sections = []
        current_active = active_section

        # Pattern 1: e.g. "Section 4. Obligations of public authorities" or "2. In this Act..."
        for match in SECTION_PATTERN.finditer(text):
            sec_num = match.group(1).strip()
            heading = match.group(2).strip()
            # Guard against gazette bracket artifacts
            if heading.startswith("]") or "[" in sec_num or "]" in sec_num:
                continue
            sections.append({
                "section_number": sec_num,
                "heading": heading,
                "match_start": match.start(),
            })
            current_active = sec_num

        # Pattern 2: Standalone "Section 4" if not already captured
        if not sections:
            for match in STANDALONE_SECTION_PATTERN.finditer(text):
                sec_num = match.group(1).strip()
                if "[" in sec_num or "]" in sec_num:
                    continue
                sections.append({
                    "section_number": sec_num,
                    "heading": None,
                    "match_start": match.start(),
                })
                current_active = sec_num

        # If inside Section 2 (Definitions) or definition clauses are present
        if current_active == "2" or any(s.get("section_number") == "2" for s in sections):
            for match in DEFINITION_CLAUSE_PATTERN.finditer(text):
                clause_num = match.group(1).strip()
                term = match.group(2).strip()
                sub_sec = f"2({clause_num})"
                sections.append({
                    "section_number": sub_sec,
                    "heading": f'"{term}" definition',
                    "match_start": match.start(),
                })

        # Sort all sections by position on page
        sections.sort(key=lambda s: s["match_start"])
        return sections

    @classmethod
    def extract_document(
        cls,
        file_path: Path,
        document_id: str,
        act_name_override: Optional[str] = None
    ) -> ExtractedDocument:
        """
        Extract full content from a PDF file.
        Saves both raw and cleaned text in `data/processed/{document_id}/` for debugging.
        """
        logger.info(f"Extracting text from PDF: {file_path.name}")
        doc = fitz.open(str(file_path))

        try:
            total_pages = doc.page_count
            act_name = cls.detect_act_name(doc, act_name_override)
            metadata = {
                "format": doc.metadata.get("format", "PDF"),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
            }

            # Step 1: Extract raw text from all pages
            raw_page_texts = []
            for i in range(total_pages):
                page = doc[i]
                raw_text = page.get_text("text")
                raw_page_texts.append(raw_text)

            # Step 2: Detect repetitive running headers and footers across pages
            repetitive_patterns = TextCleaner.detect_repetitive_headers_footers(raw_page_texts)

            # Step 3: Clean and analyze each page
            pages: List[ExtractedPage] = []
            active_section: Optional[str] = None
            for i, raw_text in enumerate(raw_page_texts):
                page_num = i + 1
                cleaned = TextCleaner.clean_page_text(raw_text, repetitive_patterns)
                sections = cls.identify_sections_on_page(cleaned, active_section=active_section)

                # Update active_section to the last top-level section found
                for s in sections:
                    sec_num = s["section_number"]
                    if "(" not in sec_num:
                        active_section = sec_num

                pages.append(ExtractedPage(
                    page_number=page_num,
                    raw_text=raw_text,
                    cleaned_text=cleaned,
                    sections=sections,
                ))

            extracted_doc = ExtractedDocument(
                document_id=document_id,
                filename=file_path.name,
                act_name=act_name,
                total_pages=total_pages,
                pages=pages,
                metadata=metadata,
            )

            # Step 4: Persist raw and cleaned extracted data for debugging
            doc_processed_dir = settings.PROCESSED_DIR / document_id
            doc_processed_dir.mkdir(parents=True, exist_ok=True)

            with open(doc_processed_dir / "raw_extracted.json", "w", encoding="utf-8") as f:
                json.dump({
                    "document_id": document_id,
                    "pages": [{"page": p.page_number, "raw_text": p.raw_text} for p in pages]
                }, f, indent=2, ensure_ascii=False)

            with open(doc_processed_dir / "cleaned_extracted.json", "w", encoding="utf-8") as f:
                json.dump(extracted_doc.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Extracted {total_pages} pages for Act '{act_name}' (Document ID: {document_id})")
            return extracted_doc

        finally:
            doc.close()
