import re
from typing import List, Dict, Any, Optional
from collections import Counter


class TextCleaner:
    """Preprocesses and cleans extracted legal text while preserving statutory structure."""

    # Patterns matching official Indian Gazette press headers/footers (not statutory sections)
    GAZETTE_HEADER_PATTERNS = [
        re.compile(r"\[?\s*PART\s+II\s*[\-\—–]\s*SEC(?:TION)?\.?\s*[0-9A-Za-z]+\s*\]?", re.IGNORECASE),
        re.compile(r"\[?\s*भाग\s+II\s*[\-\—–]\s*खण्ड\s*[0-9A-Za-z]+\s*\]?", re.IGNORECASE),
        re.compile(r"\bSEC(?:TION)?\.?\s*[0-9A-Za-z]+\s*\]", re.IGNORECASE),
        re.compile(r"THE\s+GAZETTE\s+OF\s+INDIA\s+(?:EXTRAORDINARY)?", re.IGNORECASE),
        re.compile(r"भारत\s+का\s+राजपत्र", re.IGNORECASE),
        re.compile(r"PUBLISHED\s+BY\s+AUTHORITY", re.IGNORECASE),
    ]

    @staticmethod
    def fix_hyphenated_linebreaks(text: str) -> str:
        """
        Merge words split across line breaks by hyphens.
        e.g. 'infor-\nmation' -> 'information'
        """
        return re.sub(r"(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)", r"\1\2", text)

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """
        Normalize excessive spaces, tabs, and multiple blank lines.
        Preserves paragraph and legal clause breaks.
        """
        # Replace non-breaking spaces and special unicode spaces
        text = text.replace("\xa0", " ").replace("\u200b", "")
        # Normalize double carriage returns / newlines
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\r", "\n", text)
        # Collapse multiple horizontal whitespace into single space
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse 3 or more newlines into double newline (paragraph boundary)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def detect_repetitive_headers_footers(cls, page_texts: List[str], threshold: float = 0.6) -> List[str]:
        """
        Identify recurring lines at the top or bottom of pages across a document
        (e.g. page numbers, gazette headers, recurring watermarks).
        """
        if len(page_texts) < 3:
            return []

        header_candidates = []
        footer_candidates = []

        for p_text in page_texts:
            lines = [line.strip() for line in p_text.split("\n") if line.strip()]
            if lines:
                # First 2 non-empty lines are candidate headers
                header_candidates.extend(lines[:2])
                # Last 2 non-empty lines are candidate footers
                footer_candidates.extend(lines[-2:])

        total_pages = len(page_texts)
        recurrent = []

        for candidate, count in Counter(header_candidates + footer_candidates).items():
            # If line appears on more than threshold % of pages and is relatively short
            if (count / total_pages) >= threshold and len(candidate) < 120:
                is_gazette = any(p.search(candidate) for p in cls.GAZETTE_HEADER_PATTERNS)
                # Do not strip lines that look like statutory sections, unless they are gazette press headers
                if is_gazette or not re.match(r"^(Section|Sec\.|Chapter|Part|Article)\b", candidate, re.IGNORECASE):
                    recurrent.append(candidate)

        return recurrent

    @classmethod
    def clean_page_text(cls, text: str, repetitive_patterns: Optional[List[str]] = None) -> str:
        """
        Clean text for a single page.
        """
        if not text:
            return ""

        # Remove known repetitive headers/footers
        if repetitive_patterns:
            for pattern in repetitive_patterns:
                text = text.replace(pattern, "")

        # Strip explicit Gazette press headers/footers (e.g. SEC. 1], THE GAZETTE OF INDIA)
        for g_pat in cls.GAZETTE_HEADER_PATTERNS:
            text = g_pat.sub("", text)

        # Fix hyphenated words broken across lines
        text = cls.fix_hyphenated_linebreaks(text)

        # Normalize unicode quotes and dashes
        text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        text = text.replace("—", "-").replace("–", "-")

        # Normalize whitespace while preserving legal paragraph structure
        text = cls.normalize_whitespace(text)

        return text
