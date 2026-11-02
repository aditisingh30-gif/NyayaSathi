import re
from typing import List, Dict, Any, Optional, Set
from app.core.logging_config import logger
from app.services.embedding_service import EmbeddingService
from app.database.vector_store import VectorStoreService
from app.retrieval.query_processor import QueryProcessor, ProcessedQuery


class EvidenceChunk:
    """Represents a validated, ranked evidence chunk retrieved from ChromaDB."""
    def __init__(
        self,
        chunk_id: str,
        text: str,
        act_name: str,
        section_number: Optional[str],
        page_number: int,
        source_file: str,
        document_id: str,
        similarity_score: float,
        semantic_distance: float,
        is_exact_section_match: bool = False,
    ):
        self.chunk_id = chunk_id
        self.text = text
        self.act_name = act_name
        self.section_number = section_number
        self.page_number = page_number
        self.source_file = source_file
        self.document_id = document_id
        self.similarity_score = round(similarity_score, 4)
        self.semantic_distance = round(semantic_distance, 4)
        self.is_exact_section_match = is_exact_section_match

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "act_name": self.act_name,
            "section_number": self.section_number,
            "page_number": self.page_number,
            "source_file": self.source_file,
            "document_id": self.document_id,
            "similarity_score": self.similarity_score,
            "semantic_distance": self.semantic_distance,
            "is_exact_section_match": self.is_exact_section_match,
        }


class RetrievalResult:
    """Encapsulates the full result of a statutory retrieval operation."""
    def __init__(
        self,
        processed_query: ProcessedQuery,
        chunks: List[EvidenceChunk],
        is_unsupported_act: bool = False,
        unsupported_act_name: Optional[str] = None,
        has_sufficient_evidence: bool = False,
        total_candidates_examined: int = 0,
    ):
        self.processed_query = processed_query
        self.chunks = chunks
        self.is_unsupported_act = is_unsupported_act
        self.unsupported_act_name = unsupported_act_name
        self.has_sufficient_evidence = has_sufficient_evidence
        self.total_candidates_examined = total_candidates_examined

    def to_dict(self) -> Dict[str, Any]:
        return {
            "processed_query": self.processed_query.to_dict(),
            "evidence_chunks": [c.to_dict() for c in self.chunks],
            "is_unsupported_act": self.is_unsupported_act,
            "unsupported_act_name": self.unsupported_act_name,
            "has_sufficient_evidence": self.has_sufficient_evidence,
            "total_candidates_examined": self.total_candidates_examined,
        }


class LegalRetriever:
    """
    RAG Semantic Retrieval Engine for Indian Legal & Policy documents.
    Combines dense semantic vector retrieval with keyword overlap and exact section boosting.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStoreService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        default_relevance_threshold: float = 0.35,
    ):
        self.vector_store = vector_store or VectorStoreService.get_instance()
        self.embedding_service = embedding_service or EmbeddingService.get_instance()
        self.default_relevance_threshold = default_relevance_threshold

    def get_indexed_act_names(self) -> List[str]:
        """Fetch all unique Act names currently indexed in ChromaDB."""
        docs = self.vector_store.list_documents()
        return list({d.get("act_name", "").strip() for d in docs if d.get("act_name")})

    def _calculate_keyword_score(self, query_tokens: Set[str], text: str) -> float:
        """Calculate lexical overlap between query keywords and candidate chunk."""
        if not query_tokens:
            return 0.0
        text_lower = text.lower()
        matched = sum(1 for token in query_tokens if token in text_lower)
        return min(1.0, matched / max(1, len(query_tokens)))

    def _deduplicate_chunks(self, chunks: List[EvidenceChunk], overlap_threshold: float = 0.75) -> List[EvidenceChunk]:
        """Remove highly overlapping chunks to ensure context diversity."""
        unique_chunks: List[EvidenceChunk] = []
        for candidate in chunks:
            cand_tokens = set(re.findall(r"\w+", candidate.text.lower()))
            is_dup = False
            for accepted in unique_chunks:
                acc_tokens = set(re.findall(r"\w+", accepted.text.lower()))
                intersection = len(cand_tokens.intersection(acc_tokens))
                shorter_len = min(len(cand_tokens), len(acc_tokens))
                if shorter_len > 0 and (intersection / shorter_len) >= overlap_threshold:
                    is_dup = True
                    break
            if not is_dup:
                unique_chunks.append(candidate)
        return unique_chunks

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        relevance_threshold: Optional[float] = None,
        act_name_filter: Optional[str] = None,
        conversation_context: Optional[str] = None,
    ) -> RetrievalResult:
        """
        Execute full statutory retrieval workflow:
        1. Query processing (cleaning, section extraction, multilingual mapping, unsupported Act check)
        2. Dense vector embedding generation
        3. ChromaDB similarity query with optional metadata filtering
        4. Hybrid scoring (semantic similarity + keyword overlap + section match boost)
        5. Relevance threshold filtering & deduplication
        """
        threshold = relevance_threshold if relevance_threshold is not None else self.default_relevance_threshold
        indexed_acts = self.get_indexed_act_names()

        # Step 1: Analyze and process query
        processed = QueryProcessor.process_query(
            raw_query=query,
            indexed_act_names=indexed_acts,
            conversation_context=conversation_context
        )

        # Step 2: Handle unsupported Act check
        if processed.unsupported_act_detected:
            logger.info(
                f"Query explicitly requested unsupported Act: '{processed.unsupported_act_detected}'."
            )
            return RetrievalResult(
                processed_query=processed,
                chunks=[],
                is_unsupported_act=True,
                unsupported_act_name=processed.unsupported_act_detected,
                has_sufficient_evidence=False,
                total_candidates_examined=0
            )

        # Step 3: Embed search query
        query_embedding = self.embedding_service.embed_query(processed.search_query)

        # Step 4: Build ChromaDB query filters
        where_filter: Optional[Dict[str, Any]] = None
        target_act = act_name_filter or processed.target_act
        if target_act:
            where_filter = {"act_name": target_act}

        # Step 5: Query ChromaDB collection (retrieve 3x top_k for hybrid reranking)
        fetch_k = max(15, top_k * 3)
        try:
            raw_results = self.vector_store.collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            logger.error(f"ChromaDB retrieval error: {e}")
            return RetrievalResult(
                processed_query=processed,
                chunks=[],
                is_unsupported_act=False,
                has_sufficient_evidence=False,
                total_candidates_examined=0
            )

        docs = raw_results.get("documents", [[]])[0]
        metas = raw_results.get("metadatas", [[]])[0]
        dists = raw_results.get("distances", [[]])[0]
        ids = raw_results.get("ids", [[]])[0]

        total_candidates = len(docs)
        if total_candidates == 0:
            return RetrievalResult(
                processed_query=processed,
                chunks=[],
                is_unsupported_act=False,
                has_sufficient_evidence=False,
                total_candidates_examined=0
            )

        # Step 6: Hybrid scoring and ranking
        # Tokenize query for keyword scoring (strip small stopwords)
        stop_words = {"the", "is", "at", "which", "on", "a", "an", "in", "what", "how", "to", "for", "of", "and"}
        q_tokens = {
            t.lower() for t in re.findall(r"\w+", processed.clean_query)
            if len(t) > 2 and t.lower() not in stop_words
        }
        for kw in processed.detected_keywords:
            q_tokens.update(kw.lower().split())

        ranked_candidates: List[EvidenceChunk] = []

        for chunk_id, text, meta, dist in zip(ids, docs, metas, dists):
            # Distance to cosine similarity mapping (Chroma uses cosine distance in [0, 2])
            semantic_sim = max(0.0, 1.0 - (dist / 2.0))
            keyword_score = self._calculate_keyword_score(q_tokens, text)

            # Exact section and clause matching
            chunk_section = str(meta.get("section_number") or "").strip()
            is_section_match = False
            section_boost = 0.0

            if processed.target_section and chunk_section:
                norm_target = processed.target_section.lower().replace(" ", "")
                norm_chunk = chunk_section.lower().replace(" ", "")

                # Parse base section and subclause: e.g. "2(7)" -> ("2", "7"), "35" -> ("35", None)
                target_m = re.match(r"^(\d+[a-z]?)(?:\(([0-9a-z]+)\))?$", norm_target)
                chunk_m = re.match(r"^(\d+[a-z]?)(?:\(([0-9a-z]+)\))?$", norm_chunk)

                if target_m and chunk_m:
                    t_base, t_sub = target_m.group(1), target_m.group(2)
                    c_base, c_sub = chunk_m.group(1), chunk_m.group(2)

                    # Only evaluate if the base statutory section matches
                    if t_base == c_base:
                        if t_sub and c_sub:
                            # Both specify subclauses: e.g. "2(7)" vs "2(7)"
                            if t_sub == c_sub:
                                is_section_match = True
                                section_boost = 0.30
                        elif t_sub and not c_sub:
                            # Target requested subclause (e.g. 2(7)), chunk is base section 2
                            # Check if the specific subclause text is inside chunk text
                            if f"({t_sub})" in text:
                                is_section_match = True
                                section_boost = 0.25
                        elif not t_sub and not c_sub:
                            # Both are base section: e.g. "35" == "35"
                            is_section_match = True
                            section_boost = 0.30
                        elif not t_sub and c_sub:
                            # Target is base section "2", chunk is subclause "2(7)"
                            is_section_match = True
                            section_boost = 0.15
                elif norm_target == norm_chunk:
                    is_section_match = True
                    section_boost = 0.30

            # Definition query boost: if query asks for "definition" of a term (e.g. "consumer")
            # boost chunks that contain the authentic statutory definition clause
            if "definition" in processed.clean_query.lower() or "defined" in processed.clean_query.lower() or "means" in processed.clean_query.lower():
                for token in q_tokens:
                    if len(token) > 3:
                        token_pat = rf'["“\'{re.escape(token)}["”\']\s*(?:means|includes)'
                        if re.search(token_pat, text, re.IGNORECASE) or f'"{token}" means' in text.lower():
                            section_boost = max(section_boost, 0.20)
                            is_section_match = True
                            break

            # Hybrid score: 60% semantic + 20% keyword + 20% section boost
            hybrid_score = min(1.0, (0.60 * semantic_sim) + (0.20 * keyword_score) + section_boost)

            # Filter by relevance threshold
            if hybrid_score >= threshold:
                chunk = EvidenceChunk(
                    chunk_id=chunk_id,
                    text=text,
                    act_name=meta.get("act_name", "Indian Legal Act"),
                    section_number=meta.get("section_number"),
                    page_number=meta.get("page_number", 1),
                    source_file=meta.get("source_file", ""),
                    document_id=meta.get("document_id", ""),
                    similarity_score=hybrid_score,
                    semantic_distance=dist,
                    is_exact_section_match=is_section_match,
                )
                ranked_candidates.append(chunk)

        # Sort by hybrid score descending (exact section matches prioritized)
        ranked_candidates.sort(
            key=lambda c: (1 if c.is_exact_section_match else 0, c.similarity_score),
            reverse=True
        )

        # Step 7: Deduplicate and select top_k
        diverse_chunks = self._deduplicate_chunks(ranked_candidates)
        final_chunks = diverse_chunks[:top_k]

        return RetrievalResult(
            processed_query=processed,
            chunks=final_chunks,
            is_unsupported_act=False,
            unsupported_act_name=None,
            has_sufficient_evidence=len(final_chunks) > 0,
            total_candidates_examined=total_candidates
        )
