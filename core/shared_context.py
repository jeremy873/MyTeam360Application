# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# This software and all associated intellectual property are owned
# exclusively by Praxis Holdings LLC, a Nevada limited-liability company.
# Licensed to MyTeam360 LLC for operation.
#
# UNAUTHORIZED ACCESS, COPYING, MODIFICATION, DISTRIBUTION, OR USE
# OF THIS SOFTWARE IS STRICTLY PROHIBITED AND MAY RESULT IN CIVIL
# LIABILITY AND CRIMINAL PROSECUTION UNDER FEDERAL AND STATE LAW,
# INCLUDING THE DEFEND TRADE SECRETS ACT (18 U.S.C. § 1836),
# THE COMPUTER FRAUD AND ABUSE ACT (18 U.S.C. § 1030), AND THE
# NEVADA UNIFORM TRADE SECRETS ACT (NRS 600A).
#
# See LICENSE and NOTICE files for full legal terms.
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Shared Context Layer — The "Company Brain" that connects all Spaces.

Every Space can contribute facts/knowledge to a shared pool, and every Space
can query it for relevant context. This means your Blog Writer knows what
your Code Reviewer knows about your tech stack — without dumping everything
into one giant prompt.

Uses keyword matching and category filtering for retrieval (upgradable to
vector embeddings when a vector store is available).
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db, _USE_POSTGRES

logger = logging.getLogger("MyTeam360.shared_context")


class SharedContextManager:
    """Cross-Space knowledge retrieval system."""

    def add_context(self, owner_id: str, key: str, value: str,
                    category: str = "general", source_agent_id: str = None,
                    ttl_days: int = 0) -> dict:
        """Add a fact/knowledge item to the shared context."""
        ctx_id = f"ctx_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO shared_context
                    (id, owner_id, category, key, value, source_agent_id, ttl_days)
                VALUES (?,?,?,?,?,?,?)
            """, (ctx_id, owner_id, category, key, value, source_agent_id, ttl_days))
        return {"id": ctx_id, "key": key, "category": category}

    def query_context(self, owner_id: str, query: str, category: str = None,
                      limit: int = 10, exclude_agent_id: str = None) -> list:
        """Retrieve relevant context items matching a query."""
        with get_db() as db:
            # Build query with optional filters
            sql = "SELECT * FROM shared_context WHERE owner_id=?"
            params = [owner_id]

            if category:
                sql += " AND category=?"
                params.append(category)

            if exclude_agent_id:
                sql += " AND (source_agent_id IS NULL OR source_agent_id!=?)"
                params.append(exclude_agent_id)

            # Filter expired items — compatible with both Postgres and SQLite
            if _USE_POSTGRES:
                sql += " AND (ttl_days=0 OR created_at + (ttl_days || ' days')::interval > NOW())"
            else:
                sql += " AND (ttl_days=0 OR datetime(created_at, '+' || ttl_days || ' days') > datetime('now'))"

            rows = db.execute(sql + " ORDER BY updated_at DESC", params).fetchall()

        # Simple keyword matching (upgradable to vector similarity)
        query_words = set(query.lower().split())
        scored = []
        for row in rows:
            d = dict(row)
            text = f"{d['key']} {d['value']}".lower()
            text_words = set(text.split())
            overlap = len(query_words & text_words)
            if overlap > 0 or not query.strip():
                d["relevance_score"] = overlap / max(len(query_words), 1)
                scored.append(d)

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:limit]

    def build_context_injection(self, owner_id: str, query: str,
                                 agent_id: str = None, max_tokens: int = 1000) -> str:
        """Build a context string for injection into a Space's system prompt."""
        items = self.query_context(owner_id, query, exclude_agent_id=agent_id, limit=8)
        if not items:
            return ""

        parts = ["[SHARED KNOWLEDGE]"]
        char_count = 0
        approx_max_chars = max_tokens * 4  # rough token-to-char ratio

        for item in items:
            entry = f"- {item['key']}: {item['value']}"
            if char_count + len(entry) > approx_max_chars:
                break
            parts.append(entry)
            char_count += len(entry)

        return "\n".join(parts)

    def list_context(self, owner_id: str, category: str = None,
                     limit: int = 50) -> list:
        """List all shared context items."""
        with get_db() as db:
            if category:
                rows = db.execute(
                    "SELECT * FROM shared_context WHERE owner_id=? AND category=? ORDER BY updated_at DESC LIMIT ?",
                    (owner_id, category, limit)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM shared_context WHERE owner_id=? ORDER BY updated_at DESC LIMIT ?",
                    (owner_id, limit)
                ).fetchall()
        return [dict(r) for r in rows]

    def get_categories(self, owner_id: str) -> list:
        """Get all unique categories."""
        with get_db() as db:
            rows = db.execute(
                "SELECT DISTINCT category, COUNT(*) as count FROM shared_context WHERE owner_id=? GROUP BY category",
                (owner_id,)
            ).fetchall()
        return [{"category": r["category"], "count": r["count"]} for r in rows]

    def update_context(self, ctx_id: str, value: str = None,
                       category: str = None) -> dict:
        """Update an existing context item."""
        updates = {"updated_at": datetime.now().isoformat()}
        if value is not None:
            updates["value"] = value
        if category is not None:
            updates["category"] = category
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [ctx_id]
        with get_db() as db:
            db.execute(f"UPDATE shared_context SET {sets} WHERE id=?", vals)
            row = db.execute("SELECT * FROM shared_context WHERE id=?", (ctx_id,)).fetchone()
        return dict(row) if row else {}

    def delete_context(self, ctx_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM shared_context WHERE id=?", (ctx_id,)).rowcount > 0

    def auto_extract(self, agent_id: str, owner_id: str,
                     conversation_text: str, agent_name: str = "") -> list:
        """Stub for auto-extracting facts from conversations.
        In production, this would call an LLM to extract key facts.
        For now, returns empty — ready for the LLM integration."""
        # Future: send conversation_text to a lightweight model with prompt:
        # "Extract key facts, decisions, and preferences from this conversation.
        #  Return as JSON array of {key, value, category}."
        return []

    def link_agent(self, agent_id: str, context_id: str, relevance: float = 1.0):
        """Explicitly link a context item to a specific agent."""
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO context_links (agent_id, context_id, relevance) VALUES (?,?,?)",
                (agent_id, context_id, relevance)
            )

    def get_agent_context(self, agent_id: str, limit: int = 20) -> list:
        """Get context items explicitly linked to an agent."""
        with get_db() as db:
            rows = db.execute("""
                SELECT sc.*, cl.relevance FROM shared_context sc
                JOIN context_links cl ON sc.id = cl.context_id
                WHERE cl.agent_id=? ORDER BY cl.relevance DESC LIMIT ?
            """, (agent_id, limit)).fetchall()
        return [dict(r) for r in rows]
