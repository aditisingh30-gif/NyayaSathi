from typing import List
from app.retrieval.retriever import EvidenceChunk


LEGAL_SYSTEM_PROMPT = """You are NyayaSathi, a specialized AI Indian Legal & Policy Information Assistant.
Your core mission is to provide accurate, strictly evidence-grounded information on Indian statutes, acts, rules, and regulations.

CRITICAL RULES:
1. GROUNDED IN EVIDENCE ONLY: Answer the user's question using ONLY the provided statutory excerpts below. Do not assume, extrapolate, or invent legal provisions, section numbers, or punishments.
2. CITATION DISCLOSURE: For every legal fact or rule you state, you MUST explicitly cite:
   - The Act Name (e.g. The Consumer Protection Act, 2019)
   - The Section or Rule number (e.g. Section 2(7), Section 35)
   - The Page number where the provision appears.
3. ADMITTING ABSENCE / REFUSAL:
   - If the provided excerpts do not contain sufficient evidence to answer the question, clearly state: "The requested legal information is not available in the indexed statutory documents."
   - Never fabricate legal sections or speculate on legal outcomes.
4. MULTILINGUAL QUERIES: If the user asked in Hindi or Hinglish, provide a clear and easy-to-understand response in English or simple bilingual English-Hindi, explaining the statutory position clearly.
5. FORMATTING: Structure your response cleanly:
   - Direct Answer: A direct, 1-2 sentence concise answer.
   - Legal Explanation: A detailed, clear explanation citing relevant sections and clauses.
   - Statutory Basis: Specific Act and section references.
6. MANDATORY DISCLAIMER: Always remind the user that this chatbot provides legal and policy information for educational purposes only, and does not constitute formal legal advice."""


def build_grounded_legal_prompt(
    question: str,
    evidence_chunks: List[EvidenceChunk],
    conversation_history: str = "",
    target_section: str = None
) -> str:
    """Format prompt with retrieved statutory evidence chunks and context."""
    if not evidence_chunks:
        return f"""User Question: {question}

No relevant statutory excerpts were found in the indexed database for this question.
Please state clearly that the requested statutory document or legal information is not available in the indexed database."""

    evidence_text_blocks = []
    for idx, c in enumerate(evidence_chunks, start=1):
        sec_str = f"Section {c.section_number}" if c.section_number else "Section: Not specified"
        block = (
            f"--- EVIDENCE EXCERPT {idx} ---\n"
            f"Act: {c.act_name}\n"
            f"{sec_str} | Page: {c.page_number} | Source File: {c.source_file}\n"
            f"Text:\n{c.text.strip()}\n"
        )
        evidence_text_blocks.append(block)

    all_evidence = "\n".join(evidence_text_blocks)

    context_section = ""
    if conversation_history:
        context_section = f"\nRelevant Previous Conversation Context:\n{conversation_history}\n"

    section_note = ""
    if target_section:
        section_note = f"\nNote: The user specifically inquired about Section {target_section}. Focus on this section if supported by the evidence.\n"

    prompt = f"""{context_section}{section_note}
STATUTORY EVIDENCE EXCERPTS FROM INDEXED DOCUMENTS:
{all_evidence}

USER LEGAL QUESTION:
{question}

INSTRUCTIONS:
Using ONLY the evidence excerpts provided above, answer the question accurately.
Explicitly cite the Act name, section number, and page number for each point.
If the evidence does not answer the question, state that the information is unavailable in the indexed documents."""

    return prompt
