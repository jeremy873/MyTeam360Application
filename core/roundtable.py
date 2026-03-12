# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Roundtable — User-Initiated Multi-Agent Collaborative Discussion

The user EXPLICITLY creates a Roundtable:
  1. Pick a topic / problem
  2. Select 2-6 Spaces to participate
  3. Choose a discussion mode
  4. Kick off the discussion
  5. Interject, steer, or let them run
  6. End when satisfied — get a summary

This is NOT automatic. The user is the moderator.
Think: virtual boardroom where your AI team debates a problem with you.
"""

import json
import uuid
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.roundtable")


DISCUSSION_MODES = {
    "brainstorm": {
        "label": "Brainstorm",
        "description": "All ideas welcome. Spaces build on each other.",
        "agent_instruction": (
            "You are in a team brainstorming session. Build on others' ideas creatively. "
            "Don't shoot down suggestions — expand and improve them. Be bold."
        ),
    },
    "debate": {
        "label": "Debate",
        "description": "Each Space argues its position. User decides the winner.",
        "agent_instruction": (
            "You are in a team debate. Defend your perspective with evidence and reasoning. "
            "Respectfully challenge others when you disagree. Be specific and direct."
        ),
    },
    "red_team": {
        "label": "Red Team",
        "description": "One Space plays devil's advocate and stress-tests everything.",
        "agent_instruction": (
            "You are in a red team exercise. Present and defend your ideas. "
            "Expect rigorous scrutiny from the designated challenger."
        ),
        "challenger_instruction": (
            "You are the RED TEAM. Your job is to find flaws, risks, blind spots, and weaknesses "
            "in every idea presented. Ask hard questions. Don't accept surface-level reasoning. "
            "Be constructive but relentless."
        ),
    },
    "consensus": {
        "label": "Build Consensus",
        "description": "Spaces discuss until they converge on a unified recommendation.",
        "agent_instruction": (
            "You are working toward team consensus. Listen to others carefully. "
            "If you disagree, propose a compromise. Goal: one unified recommendation the whole team supports."
        ),
    },
    "round_robin": {
        "label": "Round Robin",
        "description": "Structured turns. Each Space speaks once, then waits.",
        "agent_instruction": (
            "You are in a structured round-robin discussion. When it's your turn, "
            "give your perspective clearly and concisely (2-3 sentences), then yield the floor."
        ),
    },
}


class RoundtableManager:
    """User-initiated multi-agent discussion orchestrator."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    # ── CREATE ──────────────────────────────────────────────

    def create(self, owner_id: str, topic: str, agent_ids: list,
               mode: str = "debate", red_team_agent_id: str = None,
               max_rounds: int = 5, context: str = "") -> dict:
        """User creates a new Roundtable. Nothing runs until they start it."""
        if mode not in DISCUSSION_MODES:
            raise ValueError(f"Invalid mode. Options: {list(DISCUSSION_MODES.keys())}")
        if len(agent_ids) < 2:
            raise ValueError("Select at least 2 Spaces")
        if len(agent_ids) > 6:
            raise ValueError("Maximum 6 Spaces per Roundtable")

        participants = []
        for aid in agent_ids:
            agent = self.agents.get_agent(aid) if self.agents else None
            if not agent:
                raise ValueError(f"Space '{aid}' not found")
            role = "challenger" if (mode == "red_team" and aid == red_team_agent_id) else "participant"
            participants.append({
                "agent_id": aid,
                "name": agent.get("name", "Unknown"),
                "icon": agent.get("icon", "🤖"),
                "role": role,
            })

        rid = f"rt_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO roundtables
                    (id, owner_id, topic, mode, participants, max_rounds,
                     initial_context, status)
                VALUES (?,?,?,?,?,?,?,?)
            """, (rid, owner_id, topic, mode, json.dumps(participants),
                  max_rounds, context, "created"))

        return self.get(rid)

    # ── READ ────────────────────────────────────────────────

    def get(self, rid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM roundtables WHERE id=?", (rid,)).fetchone()
        if not row: return None
        d = dict(row)
        for k in ("participants", "transcript"):
            d[k] = json.loads(d.get(k, "[]") or "[]")
        return d

    def list(self, owner_id: str, status: str = None) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM roundtables WHERE owner_id=? AND status=? ORDER BY created_at DESC",
                    (owner_id, status)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM roundtables WHERE owner_id=? ORDER BY created_at DESC",
                    (owner_id,)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["participants"] = json.loads(d.get("participants", "[]") or "[]")
            d["message_count"] = len(json.loads(d.get("transcript", "[]") or "[]"))
            d.pop("transcript", None)  # don't send full transcript in list view
            results.append(d)
        return results

    # ── USER ACTIONS ────────────────────────────────────────

    def user_message(self, rid: str, message: str) -> dict:
        """User interjects in the discussion. The moderator speaks."""
        rt = self.get(rid)
        if not rt: raise ValueError("Roundtable not found")
        if rt["status"] not in ("created", "active"):
            raise ValueError("Roundtable is not active")

        # Activate if first message
        if rt["status"] == "created":
            self._set_status(rid, "active")

        entry = {
            "type": "user",
            "speaker": "user",
            "name": "You (Moderator)",
            "icon": "👤",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
        self._append_transcript(rid, entry)
        return entry

    def run_round(self, rid: str, user_prompt: str = None) -> list:
        """User triggers one round — agents speak in dynamic order with natural flow.
        The ConversationOrchestrator ensures no one talks over each other,
        everyone builds on what was said, and yielding is handled gracefully."""
        from .launch_essentials import ConversationOrchestrator
        orchestrator = ConversationOrchestrator()

        rt = self.get(rid)
        if not rt: raise ValueError("Roundtable not found")
        if rt["status"] not in ("created", "active"):
            raise ValueError("Roundtable is not active")

        if rt["status"] == "created":
            self._set_status(rid, "active")

        transcript = rt.get("transcript", [])
        participants = rt.get("participants", [])
        mode = rt["mode"]
        mode_cfg = DISCUSSION_MODES.get(mode, {})

        # Count completed rounds
        completed_rounds = sum(1 for t in transcript if t.get("type") == "round_marker")
        if completed_rounds >= rt["max_rounds"]:
            self._set_status(rid, "completed")
            return [{"type": "system", "content": "Maximum rounds reached. Roundtable Meetings complete."}]

        # If user provided a steering prompt, add it first
        new_entries = []
        if user_prompt:
            user_entry = {
                "type": "user", "speaker": "user", "name": "You (Moderator)",
                "icon": "👤", "content": user_prompt,
                "timestamp": datetime.now().isoformat(),
            }
            new_entries.append(user_entry)

        # DYNAMIC SPEAKING ORDER — not fixed round-robin
        ordered = orchestrator.determine_speaking_order(
            participants, rt["topic"], transcript + new_entries, mode)

        # Each agent speaks in relevance order
        for i, p in enumerate(ordered):
            is_first = (i == 0)
            instruction = mode_cfg.get("agent_instruction", "")
            if p["role"] == "challenger" and mode == "red_team":
                instruction = mode_cfg.get("challenger_instruction", instruction)

            # Build NATURAL conversation prompt (not generic)
            prompt = orchestrator.build_turn_prompt(
                agent=p, topic=rt["topic"], mode=mode,
                mode_instruction=instruction,
                transcript=transcript + new_entries,
                all_participants=participants,
                round_number=completed_rounds + 1,
                is_first_speaker=is_first)

            if rt.get("initial_context") and completed_rounds == 0:
                prompt = f"Background context: {rt['initial_context']}\n\n" + prompt

            response_text = ""
            if self.agents:
                result = self.agents.run_agent(
                    p["agent_id"], prompt, user_id=rt["owner_id"])
                response_text = result.get("text", "")

            # Check if agent yielded (just agreed, nothing new)
            if orchestrator.should_yield(response_text):
                response_text = orchestrator.compress_yield(response_text, p["name"])

            entry = {
                "type": "agent",
                "speaker": p["agent_id"],
                "name": p["name"],
                "icon": p["icon"],
                "role": p["role"],
                "content": response_text,
                "yielded": orchestrator.should_yield(response_text),
                "timestamp": datetime.now().isoformat(),
            }
            new_entries.append(entry)

        # Add round marker
        new_entries.append({
            "type": "round_marker",
            "round": completed_rounds + 1,
            "timestamp": datetime.now().isoformat(),
        })

        # Save all new entries
        self._append_transcript_batch(rid, new_entries)

        return new_entries

    def request_summary(self, rid: str) -> dict:
        """User asks for a summary of the discussion so far.
        Uses the first participant agent to generate it."""
        rt = self.get(rid)
        if not rt: raise ValueError("Not found")

        transcript = rt.get("transcript", [])
        if not transcript:
            return {"summary": "No discussion yet."}

        context = self._build_readable_transcript(transcript)
        participants = rt.get("participants", [])

        prompt = (
            f"Summarize this team discussion. Include:\n"
            f"1. Key points raised by each participant\n"
            f"2. Areas of agreement\n"
            f"3. Areas of disagreement\n"
            f"4. Action items or recommendations\n\n"
            f"Topic: {rt['topic']}\n"
            f"Participants: {', '.join(p['name'] for p in participants)}\n\n"
            f"Discussion:\n{context}"
        )

        summary_text = ""
        if self.agents and participants:
            result = self.agents.run_agent(
                participants[0]["agent_id"], prompt, user_id=rt["owner_id"])
            summary_text = result.get("text", "")

        # Save summary
        with get_db() as db:
            db.execute("UPDATE roundtables SET summary=?, updated_at=? WHERE id=?",
                      (summary_text, datetime.now().isoformat(), rid))

        return {
            "roundtable_id": rid,
            "topic": rt["topic"],
            "rounds_completed": sum(1 for t in transcript if t.get("type") == "round_marker"),
            "participants": [p["name"] for p in participants],
            "summary": summary_text,
        }

    def end(self, rid: str) -> dict:
        """User ends the Roundtable."""
        rt = self.get(rid)
        if not rt: raise ValueError("Not found")
        self._set_status(rid, "completed")

        transcript = rt.get("transcript", [])
        return {
            "roundtable_id": rid,
            "status": "completed",
            "total_messages": len([t for t in transcript if t.get("type") in ("user", "agent")]),
            "rounds_completed": sum(1 for t in transcript if t.get("type") == "round_marker"),
        }

    def delete(self, rid: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM roundtables WHERE id=?", (rid,)).rowcount > 0

    # ── INTERNAL ────────────────────────────────────────────

    def _set_status(self, rid: str, status: str):
        with get_db() as db:
            db.execute("UPDATE roundtables SET status=?, updated_at=? WHERE id=?",
                      (status, datetime.now().isoformat(), rid))

    def _append_transcript(self, rid: str, entry: dict):
        self._append_transcript_batch(rid, [entry])

    def _append_transcript_batch(self, rid: str, entries: list):
        with get_db() as db:
            row = db.execute("SELECT transcript FROM roundtables WHERE id=?", (rid,)).fetchone()
            transcript = json.loads(row["transcript"] or "[]") if row else []
            transcript.extend(entries)
            db.execute("UPDATE roundtables SET transcript=?, updated_at=? WHERE id=?",
                      (json.dumps(transcript), datetime.now().isoformat(), rid))

    def _build_readable_transcript(self, transcript: list) -> str:
        """Build a human-readable version of the discussion for agent context."""
        if not transcript:
            return "(No discussion yet — you're starting fresh.)"
        lines = []
        for entry in transcript:
            if entry.get("type") == "round_marker":
                lines.append(f"\n--- Round {entry.get('round', '?')} complete ---\n")
            elif entry.get("type") in ("user", "agent"):
                name = entry.get("name", "Unknown")
                role_tag = f" [{entry['role'].upper()}]" if entry.get("role") == "challenger" else ""
                lines.append(f"{name}{role_tag}: {entry.get('content', '')}")
        return "\n".join(lines)
