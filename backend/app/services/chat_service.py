import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.core.logging_config import logger
from app.models.schemas import ChatRequest, ChatResponse, Citation
from app.retrieval.retriever import LegalRetriever, RetrievalResult
from app.llm.factory import LLMProviderFactory
from app.llm.prompts import LEGAL_SYSTEM_PROMPT, build_grounded_legal_prompt
from app.services.citation_verifier import CitationVerifier
from app.database.conversation_store import get_conversation_store, ConversationStore


LEGAL_DISCLAIMER = (
    "This chatbot provides Indian legal and policy information for educational and research purposes only. "
    "It is strictly grounded in uploaded official statutory documents and does not constitute formal legal advice."
)


class ChatService:
    """Orchestrates end-to-end RAG chat: retrieval -> grounding -> LLM -> citation verification -> persistence."""

    def __init__(
        self,
        retriever: Optional[LegalRetriever] = None,
        conversation_store: Optional[ConversationStore] = None
    ):
        self.retriever = retriever or LegalRetriever()
        self.conversation_store = conversation_store or get_conversation_store()

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        start_time = time.time()
        question = request.question.strip()
        conv_id = request.conversation_id or self.conversation_store.create_conversation(title=question[:50])

        # Step 1: Retrieve conversation context for follow-up questions
        prior_context = self.conversation_store.get_conversation_context(conv_id, max_turns=2)

        # Step 2: Retrieve relevant statutory evidence from ChromaDB
        retrieval: RetrievalResult = self.retriever.retrieve(
            query=question,
            top_k=5,
            relevance_threshold=0.30,
            conversation_context=prior_context
        )

        # Step 3: Handle Unsupported Act Request
        if retrieval.is_unsupported_act:
            unsupported_act = retrieval.unsupported_act_name or "the requested Act"
            indexed_acts = self.retriever.get_indexed_act_names()
            indexed_str = ", ".join(f"'{a}'" for a in indexed_acts) if indexed_acts else "None"

            direct_ans = f"The requested statute ({unsupported_act}) is not currently indexed in this system."
            explanation = (
                f"You asked about '{unsupported_act}', but this document has not been uploaded or indexed into "
                f"NyayaSathi's database. Currently indexed legal documents include: {indexed_str}.\n\n"
                f"To query this statute, please upload the authentic gazette PDF in the Document Ingestion section."
            )
            full_ans = f"{direct_ans}\n\n{explanation}"

            # Save to conversation history
            self.conversation_store.add_message(conv_id, "user", question)
            self.conversation_store.add_message(
                conv_id, "assistant", full_ans,
                direct_answer=direct_ans,
                legal_explanation=explanation,
                citations=[]
            )

            return ChatResponse(
                conversation_id=conv_id,
                question=question,
                answer=full_ans,
                direct_answer=direct_ans,
                legal_explanation=explanation,
                citations=[],
                disclaimer=LEGAL_DISCLAIMER,
                provider_used="unsupported_act_refusal",
                tokens_used=0,
                processing_time_seconds=round(time.time() - start_time, 2)
            )

        # Step 4: Handle Insufficient Evidence
        if not retrieval.has_sufficient_evidence or len(retrieval.chunks) == 0:
            direct_ans = "The requested legal information is not available in the indexed statutory documents."
            explanation = (
                "NyayaSathi adheres to strict grounding principles and will not invent legal sections or speculate. "
                "No statutory provisions in the indexed collection sufficiently address this specific inquiry."
            )
            full_ans = f"{direct_ans}\n\n{explanation}"

            self.conversation_store.add_message(conv_id, "user", question)
            self.conversation_store.add_message(
                conv_id, "assistant", full_ans,
                direct_answer=direct_ans,
                legal_explanation=explanation,
                citations=[]
            )

            return ChatResponse(
                conversation_id=conv_id,
                question=question,
                answer=full_ans,
                direct_answer=direct_ans,
                legal_explanation=explanation,
                citations=[],
                disclaimer=LEGAL_DISCLAIMER,
                provider_used="insufficient_evidence_refusal",
                tokens_used=0,
                processing_time_seconds=round(time.time() - start_time, 2)
            )

        # Step 5: Format grounded legal prompt
        prompt = build_grounded_legal_prompt(
            question=question,
            evidence_chunks=retrieval.chunks,
            conversation_history=prior_context,
            target_section=retrieval.processed_query.target_section
        )

        # Step 6: Select provider and generate response
        provider = LLMProviderFactory.get_provider(request.provider)
        logger.info(f"Generating legal answer with LLM provider: {provider.provider_name} ({provider.model_name})")

        llm_result = await provider.generate_response(
            prompt=prompt,
            system_instruction=LEGAL_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=1024
        )

        raw_answer = llm_result.raw_response.strip()

        # Step 7: Verify citations against retrieved chunks
        citations, is_grounded, ungrounded = CitationVerifier.verify_and_build_citations(
            answer_text=raw_answer,
            evidence_chunks=retrieval.chunks
        )

        # Parse direct answer and legal explanation from response
        direct_answer = llm_result.direct_answer
        legal_explanation = llm_result.legal_explanation

        if not direct_answer or not legal_explanation:
            # Fallback parse if provider returned unformatted string
            parts = raw_answer.split("Legal Explanation:")
            if len(parts) == 2:
                direct_answer = parts[0].replace("Direct Answer:", "").strip()
                legal_explanation = parts[1].strip()
            else:
                paragraphs = [p.strip() for p in raw_answer.split("\n\n") if p.strip()]
                direct_answer = paragraphs[0] if paragraphs else raw_answer
                legal_explanation = "\n\n".join(paragraphs[1:]) if len(paragraphs) > 1 else raw_answer

        # Save turn to conversation history
        self.conversation_store.add_message(conv_id, "user", question)
        self.conversation_store.add_message(
            conv_id, "assistant", raw_answer,
            direct_answer=direct_answer,
            legal_explanation=legal_explanation,
            citations=citations
        )

        elapsed = round(time.time() - start_time, 2)

        return ChatResponse(
            conversation_id=conv_id,
            question=question,
            answer=raw_answer,
            direct_answer=direct_answer,
            legal_explanation=legal_explanation,
            citations=citations,
            disclaimer=LEGAL_DISCLAIMER,
            provider_used=f"{provider.provider_name} ({provider.model_name})",
            tokens_used=llm_result.tokens_used,
            processing_time_seconds=elapsed
        )
