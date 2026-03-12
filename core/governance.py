# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Governance — Record Keeping, Meeting Minutes, and Compliance

Enterprise-grade governance layer:
  1. Meeting Minutes — Auto-generated from Roundtables or any conversation
  2. Record Keeper — Formal corporate records with retention policies
  3. Compliance Log — Track regulatory obligations and deadlines
  4. Summarization Engine — Generate executive summaries, briefs, action items
  5. Resolution Tracker — Track formal votes and approvals

Every decision, every meeting, every approval — documented, timestamped,
searchable, and exportable for auditors.
"""

import json
import uuid
import re
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.governance")


# ══════════════════════════════════════════════════════════════
# 1. MEETING MINUTES — Auto-generate from any discussion
# ══════════════════════════════════════════════════════════════

class MeetingMinutesGenerator:
    """Auto-generates formal meeting minutes from Roundtables,
    conversations, or manual input. Output is audit-ready."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    def generate_from_roundtable(self, roundtable_data: dict,
                                  owner_id: str) -> dict:
        """Generate formal minutes from a completed Roundtable."""
        transcript = roundtable_data.get("transcript", [])
        participants = roundtable_data.get("participants", [])
        topic = roundtable_data.get("topic", "")
        mode = roundtable_data.get("mode", "")

        # Build readable discussion
        discussion_text = ""
        for entry in transcript:
            if entry.get("type") in ("user", "agent"):
                name = entry.get("name", "Unknown")
                discussion_text += f"{name}: {entry.get('content', '')}\n\n"

        # Use an agent to generate formal minutes
        prompt = (
            "Generate formal meeting minutes from this team discussion. Use this exact format:\n\n"
            "MEETING MINUTES\n"
            "Date: [today's date]\n"
            "Subject: [topic]\n"
            "Attendees: [list]\n"
            "Meeting Type: [mode]\n\n"
            "1. CALL TO ORDER\n"
            "Brief description of how the meeting started.\n\n"
            "2. DISCUSSION SUMMARY\n"
            "Organized summary of key points raised, grouped by theme.\n\n"
            "3. KEY POSITIONS\n"
            "Each participant's main position or contribution.\n\n"
            "4. AREAS OF AGREEMENT\n"
            "What the group agreed on.\n\n"
            "5. AREAS OF DISAGREEMENT\n"
            "Where opinions differed and why.\n\n"
            "6. DECISIONS MADE\n"
            "Any explicit decisions or conclusions reached.\n\n"
            "7. ACTION ITEMS\n"
            "Specific next steps with responsible parties.\n\n"
            "8. ADJOURNMENT\n\n"
            f"Topic: {topic}\n"
            f"Mode: {mode}\n"
            f"Attendees: {', '.join(p['name'] for p in participants)}\n\n"
            f"Full Discussion:\n{discussion_text}"
        )

        minutes_text = ""
        if self.agents and participants:
            result = self.agents.run_agent(
                participants[0]["agent_id"], prompt, user_id=owner_id)
            minutes_text = result.get("text", "")

        # Save to database
        mid = f"min_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO meeting_minutes
                    (id, owner_id, source_type, source_id, topic, participants,
                     minutes_text, status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (mid, owner_id, "roundtable", roundtable_data.get("id", ""),
                  topic, json.dumps([p["name"] for p in participants]),
                  minutes_text, "draft"))

        return {
            "id": mid,
            "topic": topic,
            "participants": [p["name"] for p in participants],
            "minutes": minutes_text,
            "status": "draft",
        }

    def generate_from_conversation(self, conversation_id: str,
                                    owner_id: str) -> dict:
        """Generate meeting minutes from a regular conversation."""
        with get_db() as db:
            msgs = db.execute(
                "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at",
                (conversation_id,)).fetchall()
            conv = db.execute(
                "SELECT * FROM conversations WHERE id=?",
                (conversation_id,)).fetchone()

        if not msgs:
            return {"error": "No messages found"}

        discussion = "\n".join(
            f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in msgs)

        agent_id = dict(conv).get("agent_id") if conv else None
        agent_name = "AI Assistant"
        if agent_id and self.agents:
            agent = self.agents.get_agent(agent_id)
            if agent: agent_name = agent.get("name", "AI")

        prompt = (
            "Generate concise meeting notes from this conversation. Include:\n"
            "1. SUMMARY (2-3 sentences)\n"
            "2. KEY POINTS DISCUSSED\n"
            "3. DECISIONS MADE\n"
            "4. ACTION ITEMS\n"
            "5. OPEN QUESTIONS\n\n"
            f"Participants: User, {agent_name}\n\n"
            f"Conversation:\n{discussion[:8000]}"
        )

        minutes_text = ""
        if self.agents and agent_id:
            result = self.agents.run_agent(agent_id, prompt, user_id=owner_id)
            minutes_text = result.get("text", "")

        mid = f"min_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO meeting_minutes
                    (id, owner_id, source_type, source_id, topic, participants,
                     minutes_text, status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (mid, owner_id, "conversation", conversation_id,
                  dict(conv).get("title", "Conversation") if conv else "Conversation",
                  json.dumps(["User", agent_name]),
                  minutes_text, "draft"))

        return {"id": mid, "minutes": minutes_text, "status": "draft"}

    def approve_minutes(self, mid: str) -> dict:
        """Mark minutes as approved — locks them from editing."""
        with get_db() as db:
            db.execute(
                "UPDATE meeting_minutes SET status='approved', approved_at=? WHERE id=?",
                (datetime.now().isoformat(), mid))
            row = db.execute("SELECT * FROM meeting_minutes WHERE id=?", (mid,)).fetchone()
        return dict(row) if row else {}

    def get_minutes(self, mid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM meeting_minutes WHERE id=?", (mid,)).fetchone()
        if not row: return None
        d = dict(row)
        d["participants"] = json.loads(d.get("participants", "[]") or "[]")
        return d

    def list_minutes(self, owner_id: str, status: str = None,
                     limit: int = 50) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM meeting_minutes WHERE owner_id=? AND status=? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, status, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM meeting_minutes WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, limit)).fetchall()
        return [dict(r, participants=json.loads(r.get("participants", "[]") or "[]")) for r in rows]

    def delete_minutes(self, mid: str) -> bool:
        with get_db() as db:
            row = db.execute("SELECT status FROM meeting_minutes WHERE id=?", (mid,)).fetchone()
            if row and dict(row).get("status") == "approved":
                return False  # cannot delete approved minutes
            return db.execute("DELETE FROM meeting_minutes WHERE id=?", (mid,)).rowcount > 0


# ══════════════════════════════════════════════════════════════
# 2. CORPORATE RECORD KEEPER
# ══════════════════════════════════════════════════════════════

class RecordKeeper:
    """Formal corporate records with retention policies.
    Every important document, decision, and event — logged and searchable."""

    RECORD_TYPES = [
        "decision", "resolution", "meeting_minutes", "policy_change",
        "contract", "financial", "compliance", "incident", "personnel",
        "ip_filing", "legal", "customer", "general",
    ]

    def create_record(self, owner_id: str, record_type: str, title: str,
                      content: str, tags: list = None, retention_days: int = 0,
                      attachments: list = None, related_ids: list = None) -> dict:
        """Create a formal corporate record."""
        if record_type not in self.RECORD_TYPES:
            record_type = "general"

        rid = f"rec_{uuid.uuid4().hex[:12]}"
        expires_at = None
        if retention_days > 0:
            expires_at = (datetime.now() + timedelta(days=retention_days)).isoformat()

        with get_db() as db:
            db.execute("""
                INSERT INTO corporate_records
                    (id, owner_id, record_type, title, content, tags,
                     retention_days, expires_at, attachments, related_ids)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (rid, owner_id, record_type, title, content,
                  json.dumps(tags or []), retention_days, expires_at,
                  json.dumps(attachments or []), json.dumps(related_ids or [])))

        return {"id": rid, "type": record_type, "title": title}

    def get_record(self, rid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM corporate_records WHERE id=?", (rid,)).fetchone()
        if not row: return None
        d = dict(row)
        for k in ("tags", "attachments", "related_ids"):
            d[k] = json.loads(d.get(k, "[]") or "[]")
        return d

    def search_records(self, owner_id: str, query: str = None,
                       record_type: str = None, tag: str = None,
                       limit: int = 50) -> list:
        with get_db() as db:
            sql = "SELECT * FROM corporate_records WHERE owner_id=?"
            params = [owner_id]
            if record_type:
                sql += " AND record_type=?"
                params.append(record_type)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = db.execute(sql, params).fetchall()

        results = [dict(r, tags=json.loads(r.get("tags", "[]") or "[]")) for r in rows]

        if query:
            query_words = set(query.lower().split())
            results = [r for r in results if query_words &
                       set(f"{r['title']} {r['content']} {' '.join(r.get('tags',[]))}".lower().split())]

        if tag:
            results = [r for r in results if tag in r.get("tags", [])]

        return results[:limit]

    def update_record(self, rid: str, updates: dict) -> dict:
        safe_keys = {"title", "content", "tags", "record_type", "retention_days"}
        filtered = {k: v for k, v in updates.items() if k in safe_keys}
        if "tags" in filtered:
            filtered["tags"] = json.dumps(filtered["tags"])
        filtered["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in filtered)
        vals = list(filtered.values()) + [rid]
        with get_db() as db:
            db.execute(f"UPDATE corporate_records SET {sets} WHERE id=?", vals)
        return self.get_record(rid)

    def delete_record(self, rid: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM corporate_records WHERE id=?", (rid,)).rowcount > 0

    def get_record_types(self) -> list:
        return self.RECORD_TYPES

    def get_expiring_records(self, owner_id: str, days_ahead: int = 30) -> list:
        """Get records expiring within N days."""
        cutoff = (datetime.now() + timedelta(days=days_ahead)).isoformat()
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM corporate_records
                WHERE owner_id=? AND expires_at IS NOT NULL AND expires_at <= ? AND expires_at > ?
                ORDER BY expires_at
            """, (owner_id, cutoff, datetime.now().isoformat())).fetchall()
        return [dict(r, tags=json.loads(r.get("tags", "[]") or "[]")) for r in rows]


# ══════════════════════════════════════════════════════════════
# 3. RESOLUTION TRACKER — Formal Votes and Approvals
# ══════════════════════════════════════════════════════════════

class ResolutionTracker:
    """Track formal votes, approvals, and resolutions.
    Who voted, when, what the outcome was — audit-ready."""

    def create_resolution(self, owner_id: str, title: str, description: str,
                          required_approvers: list = None,
                          threshold: str = "majority") -> dict:
        """Create a resolution requiring approval."""
        rid = f"res_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO resolutions
                    (id, owner_id, title, description, required_approvers,
                     threshold, status)
                VALUES (?,?,?,?,?,?,?)
            """, (rid, owner_id, title, description,
                  json.dumps(required_approvers or []),
                  threshold, "pending"))
        return {"id": rid, "title": title, "status": "pending"}

    def cast_vote(self, resolution_id: str, voter_name: str,
                  vote: str, comment: str = "") -> dict:
        """Cast a vote on a resolution. vote = approve|reject|abstain"""
        if vote not in ("approve", "reject", "abstain"):
            raise ValueError("Vote must be: approve, reject, or abstain")

        vid = f"vote_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO resolution_votes
                    (id, resolution_id, voter_name, vote, comment)
                VALUES (?,?,?,?,?)
            """, (vid, resolution_id, voter_name, vote, comment))

            # Check if resolution is decided
            res = db.execute("SELECT * FROM resolutions WHERE id=?",
                            (resolution_id,)).fetchone()
            if res:
                res_dict = dict(res)
                required = json.loads(res_dict.get("required_approvers", "[]") or "[]")
                votes = db.execute(
                    "SELECT * FROM resolution_votes WHERE resolution_id=?",
                    (resolution_id,)).fetchall()

                approve_count = sum(1 for v in votes if dict(v)["vote"] == "approve")
                reject_count = sum(1 for v in votes if dict(v)["vote"] == "reject")
                total_votes = len(votes)

                threshold = res_dict.get("threshold", "majority")
                total_required = len(required) if required else total_votes

                decided = False
                outcome = ""
                if threshold == "majority" and approve_count > total_required / 2:
                    decided, outcome = True, "approved"
                elif threshold == "majority" and reject_count > total_required / 2:
                    decided, outcome = True, "rejected"
                elif threshold == "unanimous" and approve_count == total_required:
                    decided, outcome = True, "approved"
                elif threshold == "unanimous" and reject_count > 0:
                    decided, outcome = True, "rejected"
                elif threshold == "supermajority" and approve_count >= total_required * 0.75:
                    decided, outcome = True, "approved"

                if decided:
                    db.execute(
                        "UPDATE resolutions SET status=?, decided_at=? WHERE id=?",
                        (outcome, datetime.now().isoformat(), resolution_id))

        return {"vote_id": vid, "vote": vote, "voter": voter_name}

    def get_resolution(self, rid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM resolutions WHERE id=?", (rid,)).fetchone()
            if not row: return None
            d = dict(row)
            d["required_approvers"] = json.loads(d.get("required_approvers", "[]") or "[]")
            votes = db.execute(
                "SELECT * FROM resolution_votes WHERE resolution_id=? ORDER BY created_at",
                (rid,)).fetchall()
            d["votes"] = [dict(v) for v in votes]
            return d

    def list_resolutions(self, owner_id: str, status: str = None) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM resolutions WHERE owner_id=? AND status=? ORDER BY created_at DESC",
                    (owner_id, status)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM resolutions WHERE owner_id=? ORDER BY created_at DESC",
                    (owner_id,)).fetchall()
        return [dict(r, required_approvers=json.loads(r.get("required_approvers", "[]") or "[]"))
                for r in rows]


# ══════════════════════════════════════════════════════════════
# 4. SUMMARIZATION ENGINE
# ══════════════════════════════════════════════════════════════

class SummarizationEngine:
    """Generate executive summaries, briefs, and digests from any content."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    def summarize_conversations(self, owner_id: str, agent_id: str = None,
                                 days: int = 7, style: str = "executive") -> dict:
        """Summarize all conversations from the past N days."""
        with get_db() as db:
            sql = """SELECT c.title, c.agent_id, m.role, m.content, m.created_at
                     FROM messages m JOIN conversations c ON c.id = m.conversation_id
                     WHERE c.user_id=?"""
            params = [owner_id]
            if agent_id:
                sql += " AND c.agent_id=?"
                params.append(agent_id)
            sql += " ORDER BY m.created_at DESC LIMIT 200"
            rows = db.execute(sql, params).fetchall()

        if not rows:
            return {"summary": "No conversations found for this period."}

        content = "\n".join(f"[{r['title']}] {r['role']}: {r['content'][:200]}" for r in rows)

        style_instructions = {
            "executive": "Write a concise executive summary (3-5 bullet points). Focus on decisions, outcomes, and action items.",
            "detailed": "Write a comprehensive summary organized by topic. Include key discussions, decisions, and open items.",
            "action_items": "Extract ONLY action items and tasks. Format as a checklist with responsible parties and deadlines.",
            "brief": "Write a 2-sentence brief suitable for a daily standup.",
        }

        prompt = (
            f"{style_instructions.get(style, style_instructions['executive'])}\n\n"
            f"Conversations from the past {days} days:\n{content[:6000]}"
        )

        summary = ""
        target_agent = agent_id
        if not target_agent and self.agents:
            # Use first available agent
            with get_db() as db:
                first = db.execute(
                    "SELECT id FROM agents WHERE owner_id=? LIMIT 1",
                    (owner_id,)).fetchone()
                if first: target_agent = dict(first)["id"]

        if self.agents and target_agent:
            result = self.agents.run_agent(target_agent, prompt, user_id=owner_id)
            summary = result.get("text", "")

        return {
            "period_days": days,
            "style": style,
            "conversation_count": len(set(r["title"] for r in rows)),
            "message_count": len(rows),
            "summary": summary,
        }

    def generate_digest(self, owner_id: str) -> dict:
        """Generate a comprehensive daily/weekly digest."""
        with get_db() as db:
            # Recent decisions
            decisions = db.execute(
                "SELECT * FROM decisions WHERE owner_id=? ORDER BY created_at DESC LIMIT 10",
                (owner_id,)).fetchall()
            # Recent roundtables
            roundtables = db.execute(
                "SELECT id, topic, status, mode FROM roundtables WHERE owner_id=? ORDER BY created_at DESC LIMIT 5",
                (owner_id,)).fetchall()
            # Pending resolutions
            pending = db.execute(
                "SELECT id, title, status FROM resolutions WHERE owner_id=? AND status='pending'",
                (owner_id,)).fetchall()

        return {
            "generated_at": datetime.now().isoformat(),
            "recent_decisions": [dict(d) for d in decisions[:5]],
            "recent_roundtables": [dict(r) for r in roundtables],
            "pending_resolutions": [dict(p) for p in pending],
            "action_needed": len(pending),
        }
