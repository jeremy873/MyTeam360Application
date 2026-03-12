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
Next-Gen Features:

1. Natural Language Configuration — Create/modify Spaces with plain English
2. Conversation Artifacts — Auto-extract decisions, tasks, facts
3. Proactive AI — Morning briefings and intelligent suggestions
4. Show Your Work — Transparency layer for every response
"""

import json
import uuid
import re
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.nextgen")


# ══════════════════════════════════════════════════════════════
# NATURAL LANGUAGE CONFIGURATION
# ══════════════════════════════════════════════════════════════

class NaturalLanguageConfig:
    """Create and modify Spaces using plain English descriptions.
    No forms, no settings, no technical knowledge required.

    User says: "I need a Space that writes LinkedIn posts, professional
    but not corporate, under 200 words, for tech founders"

    System creates the Space with appropriate name, icon, instructions,
    model, and temperature — all inferred from the description.
    """

    # Templates for different detected intents
    INTENT_MAP = {
        "writing": {
            "keywords": ["write", "draft", "compose", "blog", "article", "post", "copy",
                        "email", "content", "newsletter", "social media", "linkedin", "twitter"],
            "default_icon": "✍️",
            "default_temp": 0.7,
            "default_model_tier": "mid",
            "instruction_prefix": "You are a skilled writer.",
        },
        "coding": {
            "keywords": ["code", "program", "debug", "develop", "build", "script",
                        "software", "api", "function", "bug", "python", "javascript"],
            "default_icon": "💻",
            "default_temp": 0.3,
            "default_model_tier": "mid",
            "instruction_prefix": "You are an expert programmer.",
        },
        "analysis": {
            "keywords": ["analyze", "data", "research", "report", "numbers", "trends",
                        "statistics", "metrics", "insights", "dashboard", "spreadsheet"],
            "default_icon": "📊",
            "default_temp": 0.4,
            "default_model_tier": "mid",
            "instruction_prefix": "You are a data analyst.",
        },
        "strategy": {
            "keywords": ["strategy", "plan", "advise", "consult", "business", "decision",
                        "recommend", "evaluate", "assess", "compare", "trade-off"],
            "default_icon": "♟️",
            "default_temp": 0.6,
            "default_model_tier": "mid",
            "instruction_prefix": "You are a strategic advisor.",
        },
        "support": {
            "keywords": ["support", "customer", "help", "service", "complaint", "ticket",
                        "reply", "respond", "FAQ", "helpdesk"],
            "default_icon": "🎧",
            "default_temp": 0.5,
            "default_model_tier": "cheap",
            "instruction_prefix": "You are a customer support specialist.",
        },
        "creative": {
            "keywords": ["creative", "design", "brainstorm", "idea", "invent", "imagine",
                        "story", "narrative", "concept", "mood", "brand"],
            "default_icon": "🎨",
            "default_temp": 0.85,
            "default_model_tier": "mid",
            "instruction_prefix": "You are a creative professional.",
        },
        "education": {
            "keywords": ["teach", "explain", "tutor", "learn", "study", "lesson",
                        "homework", "course", "training", "quiz"],
            "default_icon": "📚",
            "default_temp": 0.5,
            "default_model_tier": "mid",
            "instruction_prefix": "You are a patient, expert teacher.",
        },
        "legal": {
            "keywords": ["legal", "contract", "law", "compliance", "regulation",
                        "policy", "agreement", "terms", "clause"],
            "default_icon": "⚖️",
            "default_temp": 0.2,
            "default_model_tier": "premium",
            "instruction_prefix": "You are a legal analyst. Always note you are not a lawyer.",
        },
        "finance": {
            "keywords": ["finance", "budget", "accounting", "tax", "invoice", "expense",
                        "revenue", "profit", "forecast", "cashflow"],
            "default_icon": "📊",
            "default_temp": 0.3,
            "default_model_tier": "mid",
            "instruction_prefix": "You are a financial analyst. Always note you are not a financial advisor.",
        },
    }

    # Tone modifiers detected from description
    TONE_MAP = {
        "casual": "Use a casual, conversational tone. Contractions are fine.",
        "formal": "Use a formal, professional tone. Avoid contractions.",
        "friendly": "Be warm, friendly, and approachable.",
        "professional": "Maintain a professional, polished tone.",
        "corporate": "Use corporate-appropriate language and structure.",
        "fun": "Be playful and energetic. Show personality.",
        "serious": "Be serious and authoritative. No fluff.",
        "empathetic": "Be empathetic and understanding. Show you care.",
        "direct": "Be direct and to the point. No unnecessary words.",
        "detailed": "Be thorough and detailed. Cover all angles.",
        "concise": "Keep responses concise. Under 200 words when possible.",
        "brief": "Be brief. Maximum 100 words unless asked for more.",
    }

    def parse_description(self, description: str) -> dict:
        """Parse a natural language description into Space configuration."""
        text = description.lower().strip()

        # Detect primary intent
        intent = self._detect_intent(text)
        intent_config = self.INTENT_MAP.get(intent, {})

        # Extract name (if mentioned)
        name = self._extract_name(description) or self._generate_name(intent, text)

        # Detect tone modifiers
        tones = self._detect_tones(text)

        # Detect audience
        audience = self._extract_audience(text)

        # Detect constraints (word limits, formatting preferences)
        constraints = self._extract_constraints(text)

        # Build system instructions
        instructions = self._build_instructions(
            intent_config, description, tones, audience, constraints
        )

        # Pick icon and temperature
        icon = intent_config.get("default_icon", "🤖")
        temperature = intent_config.get("default_temp", 0.7)

        # Adjust temp based on tone
        if any(t in tones for t in ["creative", "fun"]):
            temperature = min(temperature + 0.15, 0.95)
        if any(t in tones for t in ["serious", "formal", "precise"]):
            temperature = max(temperature - 0.15, 0.1)

        return {
            "name": name,
            "icon": icon,
            "description": description[:200],
            "instructions": instructions,
            "temperature": round(temperature, 2),
            "model_tier": intent_config.get("default_model_tier", "mid"),
            "detected_intent": intent,
            "detected_tones": tones,
            "detected_audience": audience,
            "color": "#a459f2",
        }

    def modify_from_instruction(self, current_instructions: str,
                                 modification: str) -> str:
        """Modify existing Space instructions using natural language.
        e.g. "make it more casual" or "add a rule about word count"
        """
        text = modification.lower().strip()

        # Detect modification type
        additions = []
        removals = []

        # Tone changes
        for tone, desc in self.TONE_MAP.items():
            if tone in text and ("more" in text or "be" in text or "make" in text):
                additions.append(desc)

        # Add rules
        if "add" in text or "also" in text or "include" in text:
            # Extract the rule after "add"/"also"/"include"
            rule = re.sub(r'^(add|also|include|make sure|ensure)\s+(that\s+)?', '', text, flags=re.I).strip()
            if rule:
                additions.append(f"Additional rule: {rule}")

        # Word/length limits
        limit_match = re.search(r'(\d+)\s*(word|char|sentence)', text)
        if limit_match:
            num, unit = limit_match.group(1), limit_match.group(2)
            additions.append(f"Keep responses under {num} {unit}s unless asked for more.")

        # Remove/stop
        if "stop" in text or "don't" in text or "remove" in text or "no more" in text:
            pattern = re.sub(r'^(stop|don\'t|remove|no more)\s+', '', text, flags=re.I).strip()
            if pattern:
                additions.append(f"NEVER: {pattern}")

        if additions:
            return current_instructions + "\n\n" + "\n".join(additions)
        return current_instructions

    def _detect_intent(self, text: str) -> str:
        scores = {}
        for intent, config in self.INTENT_MAP.items():
            score = sum(1 for kw in config["keywords"] if kw in text)
            if score > 0:
                scores[intent] = score
        if scores:
            return max(scores, key=scores.get)
        return "general"

    def _detect_tones(self, text: str) -> list:
        return [tone for tone in self.TONE_MAP if tone in text]

    def _extract_audience(self, text: str) -> str:
        patterns = [
            r'(?:for|targeting|audience[:\s]+|aimed at)\s+([^.,]+)',
            r'my (\w+(?:\s+\w+)?)\s+(?:audience|readers|clients|customers)',
        ]
        for pat in patterns:
            match = re.search(pat, text, re.I)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_constraints(self, text: str) -> list:
        constraints = []
        # Word limits
        match = re.search(r'(?:under|max|maximum|no more than|limit)\s*(\d+)\s*words?', text, re.I)
        if match:
            constraints.append(f"Keep responses under {match.group(1)} words unless explicitly asked for more.")
        # Format preferences
        if "bullet" in text or "list" in text:
            constraints.append("Use bullet points for structured information.")
        if "paragraph" in text or "prose" in text:
            constraints.append("Write in flowing paragraphs, not bullet points.")
        if "step by step" in text or "step-by-step" in text:
            constraints.append("Break down complex tasks into numbered steps.")
        return constraints

    def _extract_name(self, text: str) -> str:
        patterns = [
            r'(?:called?|named?)\s+"([^"]+)"',
            r'(?:called?|named?)\s+([A-Z][a-zA-Z\s]+)',
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                return match.group(1).strip()
        return ""

    def _generate_name(self, intent: str, text: str) -> str:
        names = {
            "writing": "Writer",
            "coding": "Code Assistant",
            "analysis": "Analyst",
            "strategy": "Strategist",
            "support": "Support Agent",
            "creative": "Creative",
            "education": "Tutor",
            "legal": "Legal Analyst",
            "finance": "Finance Helper",
        }
        base = names.get(intent, "Assistant")
        # Try to make it more specific
        if "linkedin" in text:
            return "LinkedIn Writer"
        if "email" in text:
            return "Email Drafter"
        if "blog" in text:
            return "Blog Writer"
        if "python" in text:
            return "Python Assistant"
        if "social media" in text:
            return "Social Media Writer"
        return base

    def _build_instructions(self, intent_config, description, tones, audience, constraints):
        parts = []

        # Core role
        prefix = intent_config.get("instruction_prefix", "You are a helpful AI assistant.")
        parts.append(prefix)

        # User's description as context
        parts.append(f"\nThe user described your purpose as: \"{description}\"")
        parts.append("Follow this description as your primary guide.")

        # Tone
        for tone in tones:
            if tone in self.TONE_MAP:
                parts.append(self.TONE_MAP[tone])

        # Audience
        if audience:
            parts.append(f"Target audience: {audience}. Adjust language and examples accordingly.")

        # Constraints
        for c in constraints:
            parts.append(c)

        # Default quality rules
        parts.append("\nAlways:")
        parts.append("- Match the user's intent precisely")
        parts.append("- Be helpful and practical, not generic")
        parts.append("- Ask clarifying questions when the request is ambiguous")

        return "\n".join(parts)


# ══════════════════════════════════════════════════════════════
# CONVERSATION ARTIFACTS
# ══════════════════════════════════════════════════════════════

class ArtifactExtractor:
    """Auto-extract decisions, tasks, facts, and documents from conversations.
    Conversations produce THINGS, not just words.

    For now uses pattern matching. In production, this calls a lightweight
    LLM to extract structured data from conversation text.
    """

    def extract_from_messages(self, messages: list, agent_name: str = "") -> dict:
        """Extract artifacts from a list of messages."""
        full_text = "\n".join(
            f"{'User' if m.get('role')=='user' else agent_name or 'AI'}: {m.get('content','')}"
            for m in messages
        )

        return {
            "decisions": self._extract_decisions(full_text),
            "action_items": self._extract_action_items(full_text),
            "facts": self._extract_facts(full_text),
            "key_numbers": self._extract_numbers(full_text),
            "links": self._extract_links(full_text),
        }

    def _extract_decisions(self, text: str) -> list:
        patterns = [
            r"(?:let's|we'll|I'll|we should|decided to|going to|the plan is to)\s+(.+?)(?:\.|$)",
            r"(?:decision|agreed|confirmed):\s*(.+?)(?:\.|$)",
            r"(?:go with|stick with|choose|choosing)\s+(.+?)(?:\.|$)",
        ]
        decisions = []
        for pat in patterns:
            matches = re.findall(pat, text, re.I | re.MULTILINE)
            for m in matches:
                cleaned = m.strip()
                if 10 < len(cleaned) < 200:
                    decisions.append(cleaned)
        return decisions[:10]

    def _extract_action_items(self, text: str) -> list:
        patterns = [
            r"(?:TODO|to-do|action item|task|need to|must|should|have to)[\s:]+(.+?)(?:\.|$)",
            r"(?:next step|follow up|reminder)[\s:]+(.+?)(?:\.|$)",
            r"(?:\d+\.|\-|\*)\s+(.+?)(?:\n|$)",  # Numbered or bulleted lists (potential tasks)
        ]
        items = []
        for pat in patterns:
            matches = re.findall(pat, text, re.I | re.MULTILINE)
            for m in matches:
                cleaned = m.strip()
                if 5 < len(cleaned) < 200:
                    items.append(cleaned)
        return items[:15]

    def _extract_facts(self, text: str) -> list:
        """Extract key facts that should be remembered."""
        patterns = [
            r"(?:remember that|note that|important|key point|FYI|for the record)[\s:]+(.+?)(?:\.|$)",
            r"(?:my|our|the)\s+(\w+)\s+is\s+(.+?)(?:\.|$)",
        ]
        facts = []
        for pat in patterns:
            matches = re.findall(pat, text, re.I | re.MULTILINE)
            for m in matches:
                if isinstance(m, tuple):
                    cleaned = " ".join(m).strip()
                else:
                    cleaned = m.strip()
                if 5 < len(cleaned) < 200:
                    facts.append(cleaned)
        return facts[:10]

    def _extract_numbers(self, text: str) -> list:
        """Extract significant numbers with context."""
        patterns = [
            r'(\$[\d,]+(?:\.\d{2})?)\s*(?:\w+)',
            r'(\d+(?:\.\d+)?%)',
            r'(\d{1,3}(?:,\d{3})+)',
        ]
        numbers = []
        for pat in patterns:
            matches = re.finditer(pat, text)
            for m in matches:
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                context = text[start:end].strip()
                numbers.append({"value": m.group(), "context": context})
        return numbers[:10]

    def _extract_links(self, text: str) -> list:
        return re.findall(r'https?://[^\s<>"\']+', text)[:10]


# ══════════════════════════════════════════════════════════════
# PROACTIVE AI (Morning Briefings)
# ══════════════════════════════════════════════════════════════

class ProactiveManager:
    """Your AI reaches out to you instead of waiting.

    Generates briefings based on:
    - Pending action items from recent conversations
    - Trigger results that came in overnight
    - Upcoming calendar events (if connected)
    - Unfinished conversations
    - Suggestions based on usage patterns
    """

    def generate_briefing(self, user_id: str) -> dict:
        """Generate a morning briefing for the user."""
        with get_db() as db:
            # Recent conversations (last 48h) with unfinished threads
            recent_convs = db.execute("""
                SELECT c.id, c.title, c.agent_id, c.updated_at,
                    (SELECT COUNT(*) FROM messages WHERE conversation_id=c.id) as msg_count
                FROM conversations c
                WHERE c.user_id=? AND c.updated_at > datetime('now', '-2 days')
                ORDER BY c.updated_at DESC LIMIT 10
            """, (user_id,)).fetchall()

            # Trigger results (last 24h)
            trigger_results = db.execute("""
                SELECT tl.*, t.name as trigger_name, t.agent_id
                FROM trigger_log tl
                JOIN agent_triggers t ON t.id = tl.trigger_id
                WHERE t.owner_id=? AND tl.created_at > datetime('now', '-1 day')
                ORDER BY tl.created_at DESC LIMIT 5
            """, (user_id,)).fetchall()

            # Usage stats
            stats = db.execute("""
                SELECT COUNT(DISTINCT c.id) as conversations,
                    SUM(m.tokens_used) as tokens,
                    COUNT(m.id) as messages
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id=? AND c.created_at > datetime('now', '-7 days')
            """, (user_id,)).fetchone()

            # Most-used spaces
            top_spaces = db.execute("""
                SELECT a.id, a.name, a.icon, a.run_count
                FROM agents a WHERE a.owner_id=?
                ORDER BY a.run_count DESC LIMIT 3
            """, (user_id,)).fetchall()

        briefing = {
            "generated_at": datetime.now().isoformat(),
            "sections": [],
        }

        # Unfinished conversations
        active = [dict(c) for c in recent_convs if c["msg_count"] > 2]
        if active:
            briefing["sections"].append({
                "title": "Continue where you left off",
                "type": "conversations",
                "items": [{"id": c["id"], "title": c["title"], "messages": c["msg_count"],
                          "last_active": c["updated_at"]} for c in active[:3]]
            })

        # Trigger results
        if trigger_results:
            briefing["sections"].append({
                "title": "While you were away",
                "type": "triggers",
                "items": [{"trigger": r["trigger_name"], "status": r["status"],
                          "preview": (r["output_data"] or "")[:150],
                          "time": r["created_at"]} for r in trigger_results]
            })

        # Weekly stats
        if stats and stats["conversations"]:
            briefing["sections"].append({
                "title": "Your week",
                "type": "stats",
                "data": {
                    "conversations": stats["conversations"] or 0,
                    "messages": stats["messages"] or 0,
                    "tokens": stats["tokens"] or 0,
                }
            })

        # Suggestions
        if top_spaces:
            briefing["sections"].append({
                "title": "Your top Spaces",
                "type": "spaces",
                "items": [{"id": s["id"], "name": s["name"], "icon": s["icon"],
                          "runs": s["run_count"]} for s in top_spaces]
            })

        return briefing

    def get_notifications(self, user_id: str) -> list:
        """Get pending notifications for a user."""
        notifications = []
        with get_db() as db:
            # Check for completed triggers
            pending = db.execute("""
                SELECT tl.id, t.name, tl.status, tl.output_data, tl.created_at
                FROM trigger_log tl
                JOIN agent_triggers t ON t.id = tl.trigger_id
                WHERE t.owner_id=? AND tl.created_at > datetime('now', '-1 day')
                AND tl.status = 'success'
                ORDER BY tl.created_at DESC LIMIT 5
            """, (user_id,)).fetchall()

            for p in pending:
                notifications.append({
                    "type": "trigger_complete",
                    "title": f"{p['name']} completed",
                    "preview": (p["output_data"] or "")[:100],
                    "time": p["created_at"],
                })

        return notifications


# ══════════════════════════════════════════════════════════════
# SHOW YOUR WORK (Transparency Layer)
# ══════════════════════════════════════════════════════════════

class TransparencyLayer:
    """Add a "how I got here" breakdown to every AI response.

    For business decisions and client work, full transparency:
    - Which sources/context were used
    - What model was chosen and why
    - Confidence level
    - Cost of this response
    """

    def build_transparency(self, response_meta: dict, agent: dict = None,
                           context_items: list = None,
                           routing_decision: dict = None) -> dict:
        """Build a transparency report for a response."""
        report = {
            "model": response_meta.get("model", "unknown"),
            "provider": response_meta.get("provider", "unknown"),
            "tokens_used": response_meta.get("usage", {}).get("total_tokens", 0),
        }

        # Cost estimate
        input_tokens = response_meta.get("usage", {}).get("input_tokens", 0)
        output_tokens = response_meta.get("usage", {}).get("output_tokens", 0)
        # Rough estimate
        report["estimated_cost"] = round(
            (input_tokens * 0.003 + output_tokens * 0.015) / 1000, 4
        )

        # Sources used
        if context_items:
            report["context_sources"] = [
                {"key": item.get("key", ""), "category": item.get("category", "")}
                for item in context_items[:5]
            ]

        # Routing decision
        if routing_decision:
            report["routing"] = {
                "tier": routing_decision.get("tier", ""),
                "reason": routing_decision.get("analysis", {}).get("signals", []),
                "savings": routing_decision.get("savings_vs_premium_pct", 0),
            }

        # Agent info
        if agent:
            report["space"] = {
                "name": agent.get("name", ""),
                "has_instructions": bool(agent.get("instructions")),
                "has_knowledge": bool(agent.get("use_knowledge_base")),
                "voice_active": bool(agent.get("voice_provider")),
            }

        return report
