import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from app.ingestion.extractor import ExtractedDocument, ExtractedPage
from app.core.logging_config import logger


@dataclass
class DocumentChunk:
    """Represents an indexed chunk with statutory metadata."""
    chunk_id: str
    document_id: str
    document_name: str
    act_name: str
    section_number: Optional[str]
    page_number: int
    chunk_index: int
    source_file: str
    text: str

    def to_metadata(self) -> Dict[str, Any]:
        """Return metadata dictionary suitable for vector databases (flat types)."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "act_name": self.act_name,
            "section_number": self.section_number or "N/A",
            "page_number": int(self.page_number),
            "chunk_index": int(self.chunk_index),
            "source_file": self.source_file,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LegalChunker:
    """
    Section-aware, statutory chunking engine.
    Preserves legal provisions, sections, and clause boundaries.
    """

    def __init__(
        self,
        target_chunk_size: int = 1000,
        chunk_overlap: int = 150,
        min_chunk_size: int = 100
    ):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def _split_long_text(self, text: str, page_num: int, section_num: Optional[str]) -> List[str]:
        """
        Split a block of text that exceeds target_chunk_size while respecting
        paragraph and sentence boundaries.
        """
        if len(text) <= self.target_chunk_size:
            return [text]

        # First try splitting by double newline (paragraphs)
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if current_len + len(para) + 2 <= self.target_chunk_size:
                current_chunk.append(para)
                current_len += len(para) + 2
            else:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                # If paragraph itself is excessively large, split by sentence or clause
                if len(para) > self.target_chunk_size:
                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    s_chunk = []
                    s_len = 0
                    for s in sentences:
                        if s_len + len(s) + 1 <= self.target_chunk_size:
                            s_chunk.append(s)
                            s_len += len(s) + 1
                        else:
                            if s_chunk:
                                chunks.append(" ".join(s_chunk))
                            s_chunk = [s]
                            s_len = len(s)
                    if s_chunk:
                        current_chunk = s_chunk
                        current_len = s_len
                    else:
                        current_chunk = []
                        current_len = 0
                else:
                    current_chunk = [para]
                    current_len = len(para)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        # Add overlap if possible
        if len(chunks) > 1 and self.chunk_overlap > 0:
            overlapped_chunks = []
            for i, c in enumerate(chunks):
                if i > 0 and len(chunks[i - 1]) >= self.chunk_overlap:
                    overlap_prefix = chunks[i - 1][-self.chunk_overlap:]
                    # Ensure we don't duplicate full chunk
                    overlapped_chunks.append(f"...{overlap_prefix}\n\n{c}")
                else:
                    overlapped_chunks.append(c)
            return overlapped_chunks

        return chunks

    def chunk_document(self, document: ExtractedDocument) -> List[DocumentChunk]:
        """
        Chunk an ExtractedDocument with section-awareness and exact statutory metadata.
        """
        chunks: List[DocumentChunk] = []
        chunk_idx = 0
        last_seen_section: Optional[str] = None

        for page in document.pages:
            cleaned_text = page.cleaned_text
            if not cleaned_text or len(cleaned_text.strip()) < 20:
                continue

            # Identify if page has statutory section markers
            if page.sections:
                sections = sorted(page.sections, key=lambda s: s["match_start"])

                # If there is text before the first section marker on this page (continuation of prior section)
                first_start = sections[0]["match_start"]
                if first_start > 40:
                    pre_text = cleaned_text[:first_start].strip()
                    if len(pre_text) >= self.min_chunk_size:
                        pre_splits = self._split_long_text(pre_text, page.page_number, last_seen_section)
                        for text_seg in pre_splits:
                            if len(text_seg.strip()) >= self.min_chunk_size or len(pre_splits) == 1:
                                chunk_id = f"{document.document_id}_p{page.page_number}_c{chunk_idx}"
                                chunks.append(DocumentChunk(
                                    chunk_id=chunk_id,
                                    document_id=document.document_id,
                                    document_name=document.filename,
                                    act_name=document.act_name,
                                    section_number=last_seen_section,
                                    page_number=page.page_number,
                                    chunk_index=chunk_idx,
                                    source_file=document.filename,
                                    text=text_seg.strip(),
                                ))
                                chunk_idx += 1

                for i, sec_info in enumerate(sections):
                    sec_num = sec_info["section_number"]
                    last_seen_section = sec_num
                    start_pos = sec_info["match_start"]
                    end_pos = sections[i + 1]["match_start"] if (i + 1 < len(sections)) else len(cleaned_text)
                    sec_block = cleaned_text[start_pos:end_pos].strip()

                    if not sec_block:
                        continue

                    # Split block if too long
                    split_texts = self._split_long_text(sec_block, page.page_number, sec_num)
                    for text_segment in split_texts:
                        if len(text_segment.strip()) >= self.min_chunk_size or len(split_texts) == 1:
                            chunk_id = f"{document.document_id}_p{page.page_number}_c{chunk_idx}"
                            chunks.append(DocumentChunk(
                                chunk_id=chunk_id,
                                document_id=document.document_id,
                                document_name=document.filename,
                                act_name=document.act_name,
                                section_number=sec_num,
                                page_number=page.page_number,
                                chunk_index=chunk_idx,
                                source_file=document.filename,
                                text=text_segment.strip(),
                            ))
                            chunk_idx += 1
            else:
                # Page has no new section marker (continuation page or unsectioned)
                split_texts = self._split_long_text(cleaned_text, page.page_number, last_seen_section)
                for text_segment in split_texts:
                    if len(text_segment.strip()) >= self.min_chunk_size or len(split_texts) == 1:
                        chunk_id = f"{document.document_id}_p{page.page_number}_c{chunk_idx}"
                        chunks.append(DocumentChunk(
                            chunk_id=chunk_id,
                            document_id=document.document_id,
                            document_name=document.filename,
                            act_name=document.act_name,
                            section_number=last_seen_section,
                            page_number=page.page_number,
                            chunk_index=chunk_idx,
                            source_file=document.filename,
                            text=text_segment.strip(),
                        ))
                        chunk_idx += 1

        logger.info(
            f"Chunked document '{document.filename}' into {len(chunks)} chunks "
            f"(target size: {self.target_chunk_size}, overlap: {self.chunk_overlap})"
        )
        return chunks
