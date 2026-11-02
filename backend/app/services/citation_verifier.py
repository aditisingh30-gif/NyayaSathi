import re
from typing import List, Tuple, Set, Optional
from app.models.schemas import Citation
from app.retrieval.retriever import EvidenceChunk
from app.core.logging_config import logger


class CitationVerifier:
    """Verifies that legal citations in LLM responses are grounded in retrieved evidence."""

    SECTION_REGEX = re.compile(
        r"\b(?:section|sec\.?|dhara|dhaara|धारा)\s+([0-9]+[A-Za-z]?(?:\s*\([0-9a-z]+\))*)",
        re.IGNORECASE
    )

    @classmethod
    def extract_cited_sections(cls, text: str) -> Set[str]:
        """Extract all statutory section numbers mentioned in generated text."""
        sections = set()
        for match in cls.SECTION_REGEX.finditer(text):
            sec_clean = re.sub(r"\s+", "", match.group(1).strip())
            sections.add(sec_clean)
        return sections

    @classmethod
    def verify_and_build_citations(
        cls,
        answer_text: str,
        evidence_chunks: List[EvidenceChunk]
    ) -> Tuple[List[Citation], bool, List[str]]:
        """
        Cross-check citations in answer against retrieved evidence chunks.
        Returns:
            (verified_citations, is_fully_grounded, hallucinated_sections)
        """
        if not evidence_chunks:
            return [], True, []

        cited_in_text = cls.extract_cited_sections(answer_text)

        # Build map of available sections from evidence
        evidence_sections: Set[str] = set()
        for c in evidence_chunks:
            if c.section_number:
                norm_sec = re.sub(r"\s+", "", str(c.section_number).strip())
                evidence_sections.add(norm_sec)
                # Also include base section if subsection (e.g. '2' from '2(7)')
                base = re.match(r"^(\d+)", norm_sec)
                if base:
                    evidence_sections.add(base.group(1))

        verified_citations: List[Citation] = []
        hallucinated_sections: List[str] = []

        # Check each section mentioned in the LLM answer
        for cited_sec in cited_in_text:
            base_match = re.match(r"^(\d+)", cited_sec)
            base_num = base_match.group(1) if base_match else cited_sec

            # Check if this cited section is corroborated by evidence
            matched_chunk: Optional[EvidenceChunk] = None

            # Priority 1: Exact section & clause match
            for c in evidence_chunks:
                chunk_sec = re.sub(r"\s+", "", str(c.section_number or "")).strip()
                if cited_sec.lower() == chunk_sec.lower():
                    matched_chunk = c
                    break

            # Priority 2: Base section matches and subclause is present in chunk text
            if not matched_chunk:
                for c in evidence_chunks:
                    chunk_sec = re.sub(r"\s+", "", str(c.section_number or "")).strip()
                    c_base = re.match(r"^(\d+)", chunk_sec)
                    c_base_num = c_base.group(1) if c_base else chunk_sec
                    if base_num == c_base_num:
                        # If cited_sec has subclause e.g. 2(7), check if (7) is in chunk text
                        sub_m = re.search(r"\((\d+)\)", cited_sec)
                        if sub_m:
                            if f"({sub_m.group(1)})" in c.text:
                                matched_chunk = c
                                break
                        else:
                            matched_chunk = c
                            break

            if matched_chunk:
                snippet = matched_chunk.text.strip().replace("\n", " ")
                if len(snippet) > 280:
                    snippet = snippet[:280] + "..."
                verified_citations.append(Citation(
                    act_name=matched_chunk.act_name,
                    section=f"Section {cited_sec}",
                    document_name=matched_chunk.source_file,
                    page_number=matched_chunk.page_number,
                    snippet=snippet,
                    relevance_score=matched_chunk.similarity_score
                ))
            else:
                hallucinated_sections.append(cited_sec)

        # If LLM didn't cite specific sections in text, include the top evidence chunks as primary citations
        if not verified_citations and evidence_chunks:
            for c in evidence_chunks[:2]:
                snippet = c.text.strip().replace("\n", " ")
                if len(snippet) > 280:
                    snippet = snippet[:280] + "..."
                sec_label = f"Section {c.section_number}" if c.section_number else None
                verified_citations.append(Citation(
                    act_name=c.act_name,
                    section=sec_label,
                    document_name=c.source_file,
                    page_number=c.page_number,
                    snippet=snippet,
                    relevance_score=c.similarity_score
                ))

        is_fully_grounded = len(hallucinated_sections) == 0

        if hallucinated_sections:
            logger.warning(
                f"Uncorroborated sections detected in LLM response: {hallucinated_sections}. "
                f"Available in evidence: {evidence_sections}"
            )

        return verified_citations, is_fully_grounded, hallucinated_sections
