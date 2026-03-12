"""
Conversations — Persistent chat history with messages, search, and cross-platform context.
"""

import uuid
import json
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.conversations")


class ConversationManager:
    """Manages conversations and messages across all platforms."""

    def create_conversation(self, user_id: str, agent_id: str = None,
                            title: str = "New Conversation", platform: str = "web") -> dict:
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO conversations (id, user_id, agent_id, title, platform)
                VALUES (?, ?, ?, ?, ?)
            """, (conv_id, user_id, agent_id, title, platform))
        return self.get_conversation(conv_id)

    def get_conversation(self, conv_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("""
                SELECT c.*, a.name as agent_name, a.icon as agent_icon, a.provider as agent_provider
                FROM conversations c
                LEFT JOIN agents a ON c.agent_id = a.id
                WHERE c.id=?
            """, (conv_id,)).fetchone()
            return dict(row) if row else None

    def list_conversations(self, user_id: str, limit: int = 50, offset: int = 0,
                           archived: bool = False) -> list:
        with get_db() as db:
            rows = db.execute("""
                SELECT c.*, a.name as agent_name, a.icon as agent_icon, a.provider as agent_provider,
                    (SELECT content FROM messages WHERE conversation_id=c.id ORDER BY created_at DESC LIMIT 1) as last_message,
                    (SELECT COUNT(*) FROM messages WHERE conversation_id=c.id) as message_count
                FROM conversations c
                LEFT JOIN agents a ON c.agent_id = a.id
                WHERE c.user_id=? AND c.archived=?
                ORDER BY c.pinned DESC, c.updated_at DESC
                LIMIT ? OFFSET ?
            """, (user_id, int(archived), limit, offset)).fetchall()
            return [dict(r) for r in rows]

    def update_conversation(self, conv_id: str, data: dict) -> dict | None:
        allowed = {"title", "agent_id", "pinned", "archived"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return self.get_conversation(conv_id)
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [conv_id]
        with get_db() as db:
            db.execute(f"UPDATE conversations SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
        return self.get_conversation(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM conversations WHERE id=?", (conv_id,)).rowcount > 0

    # ── Messages ──

    def add_message(self, conversation_id: str, role: str, content: str,
                    agent_id: str = None, provider: str = None, model: str = None,
                    tokens_used: int = 0, cost_estimate: float = 0,
                    sources: list = None) -> dict:
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        sources_json = json.dumps(sources or [])
        with get_db() as db:
            db.execute("""
                INSERT INTO messages (id, conversation_id, role, content, agent_id, provider, model,
                                      tokens_used, cost_estimate, sources)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, conversation_id, role, content, agent_id, provider, model,
                  tokens_used, cost_estimate, sources_json))
            # Update conversation timestamp and auto-title
            db.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (conversation_id,))
            # Auto-title from first user message
            if role == "user":
                conv = db.execute("SELECT title FROM conversations WHERE id=?", (conversation_id,)).fetchone()
                msg_count = db.execute("SELECT COUNT(*) as c FROM messages WHERE conversation_id=? AND role='user'",
                                       (conversation_id,)).fetchone()["c"]
                if msg_count == 1 and conv and conv["title"] == "New Conversation":
                    title = content[:80].strip()
                    if len(content) > 80:
                        title += "..."
                    db.execute("UPDATE conversations SET title=? WHERE id=?", (title, conversation_id))

        return {"id": msg_id, "conversation_id": conversation_id, "role": role,
                "content": content, "sources": sources or []}

    def get_messages(self, conversation_id: str, limit: int = 100, before: str = None) -> list:
        with get_db() as db:
            if before:
                rows = db.execute("""
                    SELECT * FROM messages WHERE conversation_id=? AND created_at < ?
                    ORDER BY created_at DESC LIMIT ?
                """, (conversation_id, before, limit)).fetchall()
            else:
                rows = db.execute("""
                    SELECT * FROM messages WHERE conversation_id=?
                    ORDER BY created_at ASC LIMIT ?
                """, (conversation_id, limit)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["sources"] = json.loads(d.get("sources", "[]"))
                except Exception:
                    d["sources"] = []
                result.append(d)
            return result

    def get_context_messages(self, conversation_id: str, max_messages: int = 20) -> list:
        """Get recent messages formatted for AI context."""
        with get_db() as db:
            rows = db.execute("""
                SELECT role, content FROM messages WHERE conversation_id=?
                ORDER BY created_at DESC LIMIT ?
            """, (conversation_id, max_messages)).fetchall()
            messages = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
            return messages

    # ── Search ──

    def search(self, user_id: str, query: str, limit: int = 20) -> list:
        with get_db() as db:
            rows = db.execute("""
                SELECT m.id, m.content, m.role, m.created_at,
                       c.id as conversation_id, c.title as conversation_title,
                       a.name as agent_name, a.icon as agent_icon
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                LEFT JOIN agents a ON c.agent_id = a.id
                WHERE c.user_id=? AND m.content LIKE ?
                ORDER BY m.created_at DESC LIMIT ?
            """, (user_id, f"%{query}%", limit)).fetchall()
            return [dict(r) for r in rows]

    # ── Stats ──

    def get_stats(self, user_id: str) -> dict:
        with get_db() as db:
            conv_count = db.execute("SELECT COUNT(*) as c FROM conversations WHERE user_id=?",
                                    (user_id,)).fetchone()["c"]
            msg_count = db.execute("""
                SELECT COUNT(*) as c FROM messages m
                JOIN conversations c ON m.conversation_id=c.id WHERE c.user_id=?
            """, (user_id,)).fetchone()["c"]
            return {"conversations": conv_count, "messages": msg_count}

    # ── Platform-specific helpers ──

    def get_or_create_platform_conversation(self, user_id: str, platform: str,
                                             agent_id: str = None) -> dict:
        """Get the active conversation for a platform, or create one."""
        with get_db() as db:
            row = db.execute("""
                SELECT id FROM conversations
                WHERE user_id=? AND platform=? AND archived=0
                ORDER BY updated_at DESC LIMIT 1
            """, (user_id, platform)).fetchone()
            if row:
                return self.get_conversation(row["id"])
        return self.create_conversation(user_id, agent_id=agent_id, platform=platform)
