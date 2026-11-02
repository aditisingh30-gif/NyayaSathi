import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from app.config import settings
from app.core.logging_config import logger
from app.models.schemas import ConversationSummary, ConversationDetail, MessageItem, Citation


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationStore:
    """Persistent storage for chatbot conversations and follow-up contexts."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (settings.DATA_DIR / "conversations.json")
        self._ensure_storage_file()

    def _ensure_storage_file(self):
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_conversations({})

    def _read_conversations(self) -> Dict[str, Any]:
        try:
            if not self.storage_path.exists():
                return {}
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"Failed to read conversations from {self.storage_path}: {e}")
            return {}

    def _write_conversations(self, data: Dict[str, Any]):
        try:
            self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to write conversations to {self.storage_path}: {e}")

    def create_conversation(self, title: Optional[str] = None) -> str:
        """Create a new conversation session and return its ID."""
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        conversations = self._read_conversations()
        now = utc_now_iso()

        conversations[conv_id] = {
            "conversation_id": conv_id,
            "title": title or "New Legal Inquiry",
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        self._write_conversations(conversations)
        return conv_id

    def get_conversation(self, conversation_id: str) -> Optional[ConversationDetail]:
        """Retrieve full conversation details by ID."""
        conversations = self._read_conversations()
        data = conversations.get(conversation_id)
        if not data:
            return None

        messages = []
        for m in data.get("messages", []):
            citations = [
                Citation(
                    act_name=c.get("act_name"),
                    section=c.get("section"),
                    document_name=c.get("document_name", ""),
                    page_number=c.get("page_number"),
                    snippet=c.get("snippet", ""),
                    relevance_score=c.get("relevance_score")
                )
                for c in m.get("citations", [])
            ]
            messages.append(MessageItem(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                direct_answer=m.get("direct_answer"),
                legal_explanation=m.get("legal_explanation"),
                citations=citations,
                created_at=datetime.fromisoformat(m["created_at"]) if "created_at" in m else datetime.now(timezone.utc)
            ))

        return ConversationDetail(
            conversation_id=data["conversation_id"],
            title=data.get("title", "Legal Inquiry"),
            messages=messages,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(timezone.utc),
        )

    def list_conversations(self) -> List[ConversationSummary]:
        """List summary of all conversation sessions."""
        conversations = self._read_conversations()
        summaries = []

        for conv_id, data in conversations.items():
            summaries.append(ConversationSummary(
                conversation_id=conv_id,
                title=data.get("title", "Legal Inquiry"),
                message_count=len(data.get("messages", [])),
                created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc),
                updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(timezone.utc),
            ))

        # Sort by updated_at descending
        summaries.sort(key=lambda s: s.updated_at, reverse=True)
        return summaries

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        direct_answer: Optional[str] = None,
        legal_explanation: Optional[str] = None,
        citations: Optional[List[Citation]] = None
    ) -> str:
        """Append a message to an existing conversation, creating it if absent."""
        conversations = self._read_conversations()
        now = utc_now_iso()

        if conversation_id not in conversations:
            title = content[:50] + ("..." if len(content) > 50 else "")
            conversations[conversation_id] = {
                "conversation_id": conversation_id,
                "title": title,
                "messages": [],
                "created_at": now,
                "updated_at": now,
            }

        conv = conversations[conversation_id]
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"

        # If this is the first user message and title is default, update title
        if role == "user" and len(conv["messages"]) == 0:
            conv["title"] = content[:55] + ("..." if len(content) > 55 else "")

        serialized_citations = []
        if citations:
            serialized_citations = [
                {
                    "act_name": c.act_name,
                    "section": c.section,
                    "document_name": c.document_name,
                    "page_number": c.page_number,
                    "snippet": c.snippet,
                    "relevance_score": c.relevance_score
                }
                for c in citations
            ]

        msg_obj = {
            "id": msg_id,
            "role": role,
            "content": content,
            "direct_answer": direct_answer,
            "legal_explanation": legal_explanation,
            "citations": serialized_citations,
            "created_at": now,
        }

        conv["messages"].append(msg_obj)
        conv["updated_at"] = now
        self._write_conversations(conversations)
        return msg_id

    def get_conversation_context(self, conversation_id: str, max_turns: int = 3) -> str:
        """Fetch recent conversation turns for query disambiguation."""
        conversations = self._read_conversations()
        conv = conversations.get(conversation_id)
        if not conv or not conv.get("messages"):
            return ""

        recent = conv["messages"][-(max_turns * 2):]
        context_parts = []
        for m in recent:
            role = "User" if m["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {m['content']}")

        return "\n".join(context_parts)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation session."""
        conversations = self._read_conversations()
        if conversation_id in conversations:
            del conversations[conversation_id]
            self._write_conversations(conversations)
            return True
        return False


_global_conversation_store: Optional[ConversationStore] = None

def get_conversation_store() -> ConversationStore:
    global _global_conversation_store
    if _global_conversation_store is None:
        _global_conversation_store = ConversationStore()
    return _global_conversation_store
