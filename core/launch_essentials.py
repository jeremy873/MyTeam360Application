# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Natural Conversation Orchestrator + Pre-Launch Essentials

1. CONVERSATION ORCHESTRATOR
   Makes Roundtable Meetings feel like actual human conversations:
   - Dynamic turn order (not rigid round-robin)
   - Agents reference each other by name and build on points
   - Agents can "yield" when they have nothing new to add
   - Agents with relevant expertise speak first
   - Natural pauses between speakers
   - No repeating what someone else already said
   - Moderator can redirect, call on specific agents, or end

2. PRE-LAUNCH ESSENTIALS
   - TOS acceptance tracking
   - Cookie consent (GDPR)
   - Rate limiting per plan
"""

import re
import json
import uuid
import hashlib
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.orchestrator")


# ══════════════════════════════════════════════════════════════
# 1. NATURAL CONVERSATION ORCHESTRATOR
# ══════════════════════════════════════════════════════════════

class ConversationOrchestrator:
    """Makes multi-agent discussions feel natural.

    Key techniques:
    1. RELEVANCE-BASED ORDERING — agents with relevant expertise speak first
    2. CONTEXT INJECTION — each agent sees what was said AND is told to build on it
    3. YIELD DETECTION — if an agent says "I agree" or repeats others, it's shortened
    4. ANTI-REPETITION — agents are told exactly what NOT to repeat
    5. REFERENCE INJECTION — agents must reference the previous speaker by name
    6. DYNAMIC PROMPTING — different agents get different meta-instructions
    """

    # Phrases that indicate an agent is just agreeing / has nothing to add
    YIELD_SIGNALS = [
        r"^i (?:completely |fully |totally )?agree",
        r"^(?:exactly|precisely|that['\u2019]s (?:right|correct|exactly))",
        r"^(?:i have )?nothing (?:more )?to add",
        r"^(?:i['\u2019]d |i would )(?:just )?echo",
        r"^(?:same|ditto|seconded)",
    ]

    def __init__(self):
        self._yield_patterns = [re.compile(p, re.I) for p in self.YIELD_SIGNALS]

    def build_turn_prompt(self, agent: dict, topic: str, mode: str,
                           mode_instruction: str, transcript: list,
                           all_participants: list, round_number: int,
                           is_first_speaker: bool = False) -> str:
        """Build a natural conversation prompt for this agent's turn.

        This is the key innovation — each agent gets a personalized prompt
        that references who spoke before them and what was said.
        """
        agent_name = agent.get("name", "Agent")
        other_names = [p["name"] for p in all_participants
                       if p.get("agent_id") != agent.get("agent_id")]

        # Build readable transcript
        recent = self._get_recent_entries(transcript, limit=10)
        transcript_text = self._format_transcript(recent)

        # Who spoke last?
        last_speaker = None
        last_content = ""
        for entry in reversed(recent):
            if entry.get("type") == "agent" and entry.get("speaker") != agent.get("agent_id"):
                last_speaker = entry.get("name", "")
                last_content = entry.get("content", "")[:150]
                break
            elif entry.get("type") == "user":
                last_speaker = "the moderator"
                last_content = entry.get("content", "")[:150]
                break

        # What key points have already been made? (for anti-repetition)
        made_points = self._extract_key_points(recent)

        # Build the prompt
        parts = [
            f"[ROUNDTABLE MEETING — {mode.replace('_', ' ').title()}]",
            f"Topic: {topic}",
            f"You are: {agent_name}",
            f"Round: {round_number}",
            f"Your role: {mode_instruction}",
            f"Other participants: {', '.join(other_names)}",
        ]

        # Natural conversation instructions
        parts.append("\n[CONVERSATION RULES — Follow these exactly]")

        if is_first_speaker:
            parts.append(
                f"You're opening this {'round' if round_number > 1 else 'discussion'}. "
                f"{'Build on what was discussed in the previous round.' if round_number > 1 else 'Set the tone and lay out your initial thinking.'}"
            )
        elif last_speaker:
            parts.append(
                f"{last_speaker} just spoke. Start by briefly acknowledging or responding to "
                f"their point before making your own. Use their name naturally. "
                f"Example: '{last_speaker} raises a good point about X — I'd add that...' or "
                f"'I see it differently than {last_speaker} on this because...'"
            )

        parts.append(
            "IMPORTANT RULES:\n"
            "- Do NOT repeat points already made. Add NEW perspective or build on existing ones.\n"
            "- Keep it to 2-4 sentences. This is a conversation, not a presentation.\n"
            "- If you genuinely have nothing new to add, say so briefly: "
            "'I think [name] covered this well — my main addition would be [one sentence].'\n"
            "- Use other participants' names when referencing their ideas.\n"
            "- Be specific. No generic 'I agree with the team' — say WHAT you agree with and WHY."
        )

        if made_points:
            parts.append(
                f"\n[POINTS ALREADY MADE — Do NOT repeat these]\n" +
                "\n".join(f"- {p}" for p in made_points[:8])
            )

        parts.append(f"\n--- Discussion so far ---\n{transcript_text}\n---")
        parts.append(f"\nIt's your turn, {agent_name}.")

        return "\n".join(parts)

    def determine_speaking_order(self, participants: list, topic: str,
                                  transcript: list, mode: str) -> list:
        """Determine who speaks next based on relevance, not fixed order.

        Rules:
        1. First round: agents with most relevant expertise go first
        2. Subsequent rounds: agents who were referenced by name go first
        3. Red team: challenger always goes last (reacts to all points)
        4. Agents who yielded in the last round go last (or skip)
        """
        scored = []

        for p in participants:
            score = 50  # Base score

            # Red team challenger always goes last
            if p.get("role") == "challenger" and mode == "red_team":
                score = 0

            # Check if this agent was mentioned by name in recent entries
            name_lower = p.get("name", "").lower()
            for entry in transcript[-6:]:
                content = entry.get("content", "").lower()
                if name_lower in content:
                    score += 20  # Someone referenced them — they should respond

            # Check if agent's expertise matches the topic
            instructions = p.get("instructions", "").lower()
            topic_words = set(topic.lower().split())
            overlap = sum(1 for w in topic_words if w in instructions and len(w) > 3)
            score += overlap * 10

            # Check if agent yielded in last round (deprioritize)
            for entry in reversed(transcript[-len(participants):]):
                if entry.get("speaker") == p.get("agent_id"):
                    if self._is_yield(entry.get("content", "")):
                        score -= 30
                    break

            scored.append((p, score))

        scored.sort(key=lambda x: -x[1])
        return [p for p, _ in scored]

    def should_yield(self, response: str) -> bool:
        """Check if an agent's response is essentially just agreement with nothing new."""
        return self._is_yield(response)

    def compress_yield(self, response: str, agent_name: str) -> str:
        """If an agent yielded, shorten their response to one sentence."""
        sentences = re.split(r'[.!?]+', response)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return f"{agent_name} agrees with the discussion."
        return sentences[0] + "."

    def build_summary_prompt(self, topic: str, transcript: list,
                              participants: list) -> str:
        """Build a prompt for generating the discussion summary."""
        transcript_text = self._format_transcript(transcript)
        names = [p["name"] for p in participants]

        return (
            f"You are summarizing a Roundtable Meeting.\n\n"
            f"Topic: {topic}\n"
            f"Participants: {', '.join(names)}\n\n"
            f"--- Full Discussion ---\n{transcript_text}\n---\n\n"
            f"Create a concise summary with:\n"
            f"1. KEY AGREEMENTS — what everyone aligned on\n"
            f"2. KEY DISAGREEMENTS — where perspectives diverged\n"
            f"3. OPEN QUESTIONS — unresolved items\n"
            f"4. RECOMMENDED NEXT STEPS — actionable items\n\n"
            f"Reference participants by name when attributing ideas."
        )

    def _is_yield(self, text: str) -> bool:
        text = text.strip()
        return any(p.match(text) for p in self._yield_patterns)

    def _get_recent_entries(self, transcript: list, limit: int = 10) -> list:
        return [e for e in transcript if e.get("type") in ("agent", "user")][-limit:]

    def _format_transcript(self, entries: list) -> str:
        lines = []
        for e in entries:
            name = e.get("name", "Unknown")
            content = e.get("content", "")
            if e.get("type") == "user":
                lines.append(f"[Moderator]: {content}")
            else:
                lines.append(f"[{name}]: {content}")
        return "\n\n".join(lines) if lines else "(No discussion yet)"

    def _extract_key_points(self, entries: list) -> list:
        """Extract the main points made so far (for anti-repetition)."""
        points = []
        for e in entries:
            if e.get("type") not in ("agent", "user"):
                continue
            content = e.get("content", "")
            # Take the first sentence of each contribution as the "key point"
            sentences = re.split(r'[.!?]+', content)
            if sentences and sentences[0].strip():
                first = sentences[0].strip()
                if len(first) > 20:  # Skip very short fragments
                    points.append(f"{e.get('name', 'Someone')}: {first[:120]}")
        return points


# ══════════════════════════════════════════════════════════════
# 2. TOS ACCEPTANCE TRACKING
# ══════════════════════════════════════════════════════════════

class TOSTracker:
    """Track TOS acceptance. When terms change, require re-acceptance.

    Stores: user_id, version accepted, timestamp, IP address
    Checks: on every authenticated request, is the user on the latest version?
    """

    CURRENT_VERSION = "2.0"

    def accept(self, user_id: str, version: str = None,
               ip: str = "", user_agent: str = "") -> dict:
        version = version or self.CURRENT_VERSION
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO tos_acceptance
                    (user_id, version, ip_address, user_agent, accepted_at)
                VALUES (?,?,?,?,?)
            """, (user_id, version, ip, user_agent[:200], datetime.now().isoformat()))
        return {"accepted": True, "version": version}

    def check(self, user_id: str) -> dict:
        """Check if user has accepted the current TOS version."""
        with get_db() as db:
            row = db.execute(
                "SELECT version, accepted_at FROM tos_acceptance WHERE user_id=? ORDER BY accepted_at DESC LIMIT 1",
                (user_id,)).fetchone()
        if not row:
            return {"accepted": False, "needs_acceptance": True, "current_version": self.CURRENT_VERSION}
        d = dict(row)
        if d["version"] != self.CURRENT_VERSION:
            return {"accepted": False, "needs_acceptance": True,
                    "accepted_version": d["version"],
                    "current_version": self.CURRENT_VERSION,
                    "message": "Our terms have been updated. Please review and accept."}
        return {"accepted": True, "version": d["version"], "accepted_at": d["accepted_at"]}

    def get_acceptance_log(self, user_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM tos_acceptance WHERE user_id=? ORDER BY accepted_at DESC",
                (user_id,)).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# 3. RATE LIMITING PER PLAN
# ══════════════════════════════════════════════════════════════

class PlanRateLimiter:
    """Rate limits tied to pricing tiers.

    Starter:  30 messages/hour, 300/day
    Student:  50 messages/hour, 500/day
    Pro:      100 messages/hour, 2000/day
    Business: 500 messages/hour, 10000/day
    Enterprise: Unlimited
    """

    PLAN_LIMITS = {
        "starter":    {"per_hour": 30,  "per_day": 300},
        "k12_student": {"per_hour": 30,  "per_day": 300},
        "student":    {"per_hour": 50,  "per_day": 500},
        "pro":        {"per_hour": 100, "per_day": 2000},
        "business":   {"per_hour": 500, "per_day": 10000},
        "enterprise": {"per_hour": 99999, "per_day": 999999},
    }

    def check(self, user_id: str, plan: str = "starter") -> dict:
        """Check if user is within rate limits."""
        limits = self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS["starter"])

        with get_db() as db:
            # Count messages in last hour
            hour_ago = (datetime.now().replace(second=0, microsecond=0)).isoformat()
            hour_count = db.execute(
                "SELECT COUNT(*) as c FROM messages WHERE user_id=? AND role='user' AND created_at>?",
                (user_id, hour_ago)).fetchone()

            # Count messages today
            today = datetime.now().strftime("%Y-%m-%d")
            day_count = db.execute(
                "SELECT COUNT(*) as c FROM messages WHERE user_id=? AND role='user' AND created_at>?",
                (user_id, today)).fetchone()

        h = dict(hour_count)["c"]
        d = dict(day_count)["c"]

        if h >= limits["per_hour"]:
            return {
                "allowed": False,
                "reason": "hourly_limit",
                "limit": limits["per_hour"],
                "used": h,
                "message": f"You've reached your hourly message limit ({limits['per_hour']}). "
                           f"Upgrade your plan for higher limits.",
            }
        if d >= limits["per_day"]:
            return {
                "allowed": False,
                "reason": "daily_limit",
                "limit": limits["per_day"],
                "used": d,
                "message": f"You've reached your daily message limit ({limits['per_day']}). "
                           f"Limits reset at midnight.",
            }

        return {
            "allowed": True,
            "hourly": {"used": h, "limit": limits["per_hour"], "remaining": limits["per_hour"] - h},
            "daily": {"used": d, "limit": limits["per_day"], "remaining": limits["per_day"] - d},
        }

    def get_limits(self, plan: str = "starter") -> dict:
        return self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS["starter"])
