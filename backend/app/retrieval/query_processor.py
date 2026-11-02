import re
from typing import Dict, List, Optional, Set, Tuple


# Common Hindi / Hinglish to English legal domain keyword dictionary
HINDI_HINGLISH_LEGAL_MAP: Dict[str, List[str]] = {
    # Consumer & Rights
    "upbhokta": ["consumer", "consumer protection"],
    "upbhoktaa": ["consumer"],
    "grahak": ["consumer", "customer", "buyer"],
    "graahak": ["consumer", "customer"],
    "उपभोक्ता": ["consumer", "consumer protection"],
    "ग्राहक": ["consumer", "customer"],
    "adhikar": ["rights", "consumer rights"],
    "adhikaar": ["rights"],
    "अधिकार": ["rights", "consumer rights"],

    # Complaints & Disputes
    "shikayat": ["complaint", "dispute"],
    "shikaayat": ["complaint"],
    "शिकायत": ["complaint", "dispute"],
    "mamla": ["dispute", "case", "matter"],
    "विवाद": ["dispute", "complaint"],
    "vivad": ["dispute"],

    # Commission & Authorities
    "aayog": ["commission", "consumer disputes redressal commission"],
    "ayukt": ["commissioner"],
    "आयोग": ["commission", "district commission", "state commission", "national commission"],
    "jila": ["district", "district commission"],
    "zilla": ["district"],
    "rajya": ["state", "state commission"],
    "rashtriya": ["national", "national commission"],
    "pradhikaran": ["authority", "central authority"],
    "adhikari": ["officer", "authority"],

    # Compensation & Penalties
    "muavza": ["compensation", "product liability"],
    "muavja": ["compensation"],
    "मुआवज़ा": ["compensation"],
    "dand": ["penalty", "punishment", "fine"],
    "jhurmana": ["penalty", "fine"],
    "jurmana": ["penalty", "fine"],
    "दण्ड": ["penalty", "punishment"],
    "सजा": ["imprisonment", "punishment"],
    "saza": ["imprisonment", "punishment"],

    # Defective goods & Unfair trade
    "kharab": ["defect", "defective goods"],
    "milawat": ["adulterant", "adulterated"],
    "nakli": ["spurious goods", "counterfeit"],
    "bhramak": ["misleading advertisement"],
    "vigyapan": ["advertisement", "misleading advertisement"],
    "विज्ञापन": ["advertisement", "misleading advertisement"],
    "bhrastachar": ["unfair trade practice"],
    "anuchit": ["unfair contract", "unfair trade practice"],

    # Procedures & Jurisdiction
    "darj": ["file complaint", "institution of complaint"],
    "dakhil": ["file complaint", "manner of filing"],
    "prakriya": ["procedure", "jurisdiction"],
    "seema": ["limitation", "jurisdiction", "pecuniary jurisdiction"],
    "samay": ["limitation period", "time limit", "thirty days"],
    "adhikarita": ["jurisdiction", "pecuniary jurisdiction"],
    "apeel": ["appeal"],
    "अपील": ["appeal"],
    "samjhauta": ["mediation", "settlement"],
    "madhyasthata": ["mediation"],
    "मध्यस्थता": ["mediation"],
}

# Known major Indian Acts for unsupported Act detection
WELL_KNOWN_INDIAN_ACTS: Dict[str, str] = {
    "consumer protection": "The Consumer Protection Act, 2019",
    "copra": "The Consumer Protection Act, 2019",
    "cpa": "The Consumer Protection Act, 2019",
    "right to information": "The Right to Information Act, 2005",
    "rti": "The Right to Information Act, 2005",
    "indian penal code": "The Indian Penal Code, 1860",
    "ipc": "The Indian Penal Code, 1860",
    "bharatiya nyaya sanhita": "The Bharatiya Nyaya Sanhita, 2023",
    "bns": "The Bharatiya Nyaya Sanhita, 2023",
    "code of criminal procedure": "The Code of Criminal Procedure, 1973",
    "crpc": "The Code of Criminal Procedure, 1973",
    "bharatiya nagarik suraksha sanhita": "The Bharatiya Nagarik Suraksha Sanhita, 2023",
    "bnss": "The Bharatiya Nagarik Suraksha Sanhita, 2023",
    "motor vehicles": "The Motor Vehicles Act, 1988",
    "mva": "The Motor Vehicles Act, 1988",
    "companies act": "The Companies Act, 2013",
    "income tax": "The Income Tax Act, 1961",
    "goods and services tax": "The Central Goods and Services Tax Act, 2017",
    "gst": "The Central Goods and Services Tax Act, 2017",
    "information technology": "The Information Technology Act, 2000",
    "it act": "The Information Technology Act, 2000",
    "arbitration": "The Arbitration and Conciliation Act, 1996",
    "contract act": "The Indian Contract Act, 1872",
    "negotiable instruments": "The Negotiable Instruments Act, 1881",
    "ni act": "The Negotiable Instruments Act, 1881",
}


class ProcessedQuery:
    """Represents an analyzed, normalized, and enriched user query."""
    def __init__(
        self,
        raw_query: str,
        clean_query: str,
        search_query: str,
        target_section: Optional[str] = None,
        target_act: Optional[str] = None,
        detected_keywords: Optional[List[str]] = None,
        is_hindi_hinglish: bool = False,
        unsupported_act_detected: Optional[str] = None,
    ):
        self.raw_query = raw_query
        self.clean_query = clean_query
        self.search_query = search_query
        self.target_section = target_section
        self.target_act = target_act
        self.detected_keywords = detected_keywords or []
        self.is_hindi_hinglish = is_hindi_hinglish
        self.unsupported_act_detected = unsupported_act_detected

    def to_dict(self) -> Dict:
        return {
            "raw_query": self.raw_query,
            "clean_query": self.clean_query,
            "search_query": self.search_query,
            "target_section": self.target_section,
            "target_act": self.target_act,
            "detected_keywords": self.detected_keywords,
            "is_hindi_hinglish": self.is_hindi_hinglish,
            "unsupported_act_detected": self.unsupported_act_detected,
        }


class QueryProcessor:
    """Analyzes and enriches legal queries with multilingual mapping & section detection."""

    @classmethod
    def extract_section_number(cls, query: str) -> Optional[str]:
        """
        Extract statutory section number mentioned in query.
        Examples: 'Section 35', 'Section 2(7)', 'sec 84', 'dhara 35', 'धारा 2'.
        """
        # Pattern 1: 'Section 35', 'Sec. 2', 'धारा 35', 'dhara 2(7)'
        m = re.search(
            r"\b(?:section|sec\.?|dhara|dhaara|धारा)\s+([0-9]+[A-Za-z]?(?:\s*\([0-9a-z]+\))*)",
            query,
            re.IGNORECASE
        )
        if m:
            sec_num = m.group(1).strip()
            # Normalize whitespace e.g. '2 (7)' -> '2(7)'
            sec_num = re.sub(r"\s+", "", sec_num)
            return sec_num

        # Pattern 2: 'u/s 35' or 'u/s. 35' (common Indian legal abbreviation for under section)
        m2 = re.search(r"\bu/s\.?\s*([0-9]+[A-Za-z]?(?:\s*\([0-9a-z]+\))*)", query, re.IGNORECASE)
        if m2:
            return re.sub(r"\s+", "", m2.group(1).strip())

        return None

    @classmethod
    def detect_multilingual_terms(cls, query: str) -> Tuple[List[str], bool]:
        """
        Detect Hindi or Hinglish legal words and return matching English legal concepts.
        """
        q_lower = query.lower()
        enriched_keywords: List[str] = []
        is_hindi_hinglish = False

        # Match legal terms from map (Devanagari substring or Latin word boundary)
        for term, concepts in HINDI_HINGLISH_LEGAL_MAP.items():
            if re.search(r"[\u0900-\u097F]", term):
                if term in q_lower:
                    is_hindi_hinglish = True
                    for concept in concepts:
                        if concept not in enriched_keywords:
                            enriched_keywords.append(concept)
            else:
                if re.search(r"\b" + re.escape(term) + r"\b", q_lower):
                    is_hindi_hinglish = True
                    for concept in concepts:
                        if concept not in enriched_keywords:
                            enriched_keywords.append(concept)

        # Check for Devanagari script presence
        if re.search(r"[\u0900-\u097F]", query):
            is_hindi_hinglish = True

        return enriched_keywords, is_hindi_hinglish

    @classmethod
    def detect_requested_act(
        cls,
        query: str,
        indexed_act_names: List[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect whether the query mentions a specific Act.
        Returns:
            (target_act, unsupported_act_name)
            If the requested Act is indexed: (act_name, None)
            If the requested Act is known but NOT indexed: (None, act_name)
            If no specific Act is named: (None, None)
        """
        q_lower = query.lower()

        # Check indexed acts first
        for indexed_act in indexed_act_names:
            act_clean = indexed_act.lower().replace("the", "").replace("act", "").replace(",", "").strip()
            parts = [p.strip() for p in act_clean.split() if len(p.strip()) > 3 and not p.isdigit()]
            # If prominent keywords of the indexed act appear in query
            if all(part in q_lower for part in parts[:2]):
                return indexed_act, None

        # Check against well-known Indian Acts dictionary
        for alias, formal_name in WELL_KNOWN_INDIAN_ACTS.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, q_lower):
                # Check if this formal name is among the indexed acts
                is_indexed = any(
                    formal_name.lower() in a.lower() or a.lower() in formal_name.lower()
                    for a in indexed_act_names
                )
                if is_indexed:
                    # Match to the exact indexed name
                    for a in indexed_act_names:
                        if formal_name.lower() in a.lower() or a.lower() in formal_name.lower():
                            return a, None
                else:
                    # Explicitly requested an unsupported Act!
                    return None, formal_name

        return None, None

    @classmethod
    def process_query(
        cls,
        raw_query: str,
        indexed_act_names: Optional[List[str]] = None,
        conversation_context: Optional[str] = None
    ) -> ProcessedQuery:
        """
        Full query normalization, section extraction, Hindi/Hinglish enrichment,
        and Act availability check.
        """
        indexed_acts = indexed_act_names or []
        clean_q = raw_query.strip()

        # 1. Extract target statutory section
        target_section = cls.extract_section_number(clean_q)

        # 2. Check for Hindi / Hinglish keywords
        enriched_keywords, is_hindi_hinglish = cls.detect_multilingual_terms(clean_q)

        # 3. Detect requested Act and check if indexed vs unsupported
        target_act, unsupported_act = cls.detect_requested_act(clean_q, indexed_acts)

        # 4. Synthesize optimal search query for dense embedding retrieval
        search_terms = [clean_q]
        if enriched_keywords:
            search_terms.append(" ".join(enriched_keywords))
        if target_section:
            search_terms.append(f"Section {target_section}")
        if conversation_context and len(conversation_context.strip()) > 0:
            # Append relevant context keywords from prior turn
            search_terms.append(conversation_context.strip()[:200])

        search_query = " ".join(search_terms)

        return ProcessedQuery(
            raw_query=raw_query,
            clean_query=clean_q,
            search_query=search_query,
            target_section=target_section,
            target_act=target_act,
            detected_keywords=enriched_keywords,
            is_hindi_hinglish=is_hindi_hinglish,
            unsupported_act_detected=unsupported_act,
        )
