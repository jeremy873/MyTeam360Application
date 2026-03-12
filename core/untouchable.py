# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Untouchable Features — The six capabilities nobody else has.

1. Conversation DNA — Digital twin of how your business operates
2. AI-to-AI Negotiation — Two Spaces negotiate on behalf of users
3. Confidence Scoring — Every response rated with source attribution
4. Time-Travel Context — "What did we decide about X last month?"
5. Space Cloning — Clone + auto-adapt to client's voice
6. Real-Time Cost Ticker — Live per-conversation cost tracking
"""

import json
import uuid
import re
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.untouchable")


# ══════════════════════════════════════════════════════════════
# 1. CONVERSATION DNA — Digital Twin of Your Business
# ══════════════════════════════════════════════════════════════

class ConversationDNA:
    """Builds a searchable knowledge base from conversation patterns.
    Over time, creates a digital twin of how your business operates.

    "How do we handle refund requests?" → returns YOUR actual answer
    based on patterns extracted from past conversations.
    """

    def record_knowledge(self, owner_id: str, question: str, answer: str,
                         category: str = "general", conversation_id: str = None,
                         confidence: float = 0.8) -> dict:
        """Record a piece of business knowledge from a conversation."""
        kid = f"dna_{uuid.uuid4().hex[:10]}"
        sources = json.dumps([conversation_id] if conversation_id else [])
        with get_db() as db:
            db.execute("""
                INSERT INTO business_dna
                    (id, owner_id, category, question, answer, confidence, source_conversations)
                VALUES (?,?,?,?,?,?,?)
            """, (kid, owner_id, category, question, answer, confidence, sources))
        return {"id": kid, "question": question, "category": category}

    def query_dna(self, owner_id: str, question: str, category: str = None,
                  limit: int = 5) -> list:
        """Search the business DNA for relevant knowledge."""
        with get_db() as db:
            sql = "SELECT * FROM business_dna WHERE owner_id=?"
            params = [owner_id]
            if category:
                sql += " AND category=?"
                params.append(category)
            rows = db.execute(sql + " ORDER BY times_referenced DESC, confidence DESC",
                             params).fetchall()

        # Keyword matching (upgradable to semantic search)
        query_words = set(question.lower().split())
        scored = []
        for row in rows:
            d = dict(row)
            text = f"{d['question']} {d['answer']}".lower()
            text_words = set(text.split())
            overlap = len(query_words & text_words)
            if overlap > 0:
                d["match_score"] = overlap / max(len(query_words), 1)
                scored.append(d)

        scored.sort(key=lambda x: x["match_score"], reverse=True)

        # Increment reference count for returned results
        for item in scored[:limit]:
            with get_db() as db:
                db.execute("UPDATE business_dna SET times_referenced=times_referenced+1 WHERE id=?",
                          (item["id"],))

        return scored[:limit]

    def get_categories(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT DISTINCT category, COUNT(*) as count FROM business_dna WHERE owner_id=? GROUP BY category",
                (owner_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def list_dna(self, owner_id: str, category: str = None, limit: int = 50) -> list:
        with get_db() as db:
            if category:
                rows = db.execute(
                    "SELECT * FROM business_dna WHERE owner_id=? AND category=? ORDER BY times_referenced DESC LIMIT ?",
                    (owner_id, category, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM business_dna WHERE owner_id=? ORDER BY times_referenced DESC LIMIT ?",
                    (owner_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def update_knowledge(self, kid: str, answer: str = None,
                         confidence: float = None, category: str = None) -> dict:
        updates = {"updated_at": datetime.now().isoformat()}
        if answer is not None: updates["answer"] = answer
        if confidence is not None: updates["confidence"] = confidence
        if category is not None: updates["category"] = category
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [kid]
        with get_db() as db:
            db.execute(f"UPDATE business_dna SET {sets} WHERE id=?", vals)
            row = db.execute("SELECT * FROM business_dna WHERE id=?", (kid,)).fetchone()
        return dict(row) if row else {}

    def delete_knowledge(self, kid: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM business_dna WHERE id=?", (kid,)).rowcount > 0

    def build_dna_injection(self, owner_id: str, query: str, max_items: int = 5) -> str:
        """Build a context string from DNA for system prompt injection."""
        items = self.query_dna(owner_id, query, limit=max_items)
        if not items:
            return ""
        parts = ["[BUSINESS DNA — How this organization operates]"]
        for item in items:
            parts.append(f"Q: {item['question']}")
            parts.append(f"A: {item['answer']} (confidence: {item['confidence']})")
        return "\n".join(parts)


# ══════════════════════════════════════════════════════════════
# 2. AI-TO-AI NEGOTIATION
# ══════════════════════════════════════════════════════════════

class NegotiationManager:
    """Two Spaces negotiate on behalf of their users.

    Party A sets: "Don't go below $50K, prefer 3-year term"
    Party B sets: "Don't exceed $40K, want monthly"
    AIs exchange proposals until they find middle ground or exhaust rounds.
    """

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    def create_negotiation(self, party_a_user: str, party_a_agent: str,
                           party_b_user: str, party_b_agent: str,
                           party_a_params: dict, party_b_params: dict,
                           max_rounds: int = 10) -> dict:
        nid = f"neg_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO negotiations
                    (id, party_a_user, party_a_agent, party_b_user, party_b_agent,
                     party_a_params, party_b_params, max_rounds, status)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (nid, party_a_user, party_a_agent, party_b_user, party_b_agent,
                  json.dumps(party_a_params), json.dumps(party_b_params),
                  max_rounds, "active"))
        return self.get_negotiation(nid)

    def get_negotiation(self, nid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM negotiations WHERE id=?", (nid,)).fetchone()
            if not row: return None
            d = dict(row)
            for k in ("party_a_params", "party_b_params", "rounds"):
                d[k] = json.loads(d.get(k, "{}") or "{}")
            return d

    def run_round(self, nid: str) -> dict:
        """Execute one negotiation round — both AIs make proposals."""
        neg = self.get_negotiation(nid)
        if not neg or neg["status"] != "active":
            raise ValueError("Negotiation not active")

        rounds = neg.get("rounds", [])
        round_num = len(rounds) + 1

        if round_num > neg["max_rounds"]:
            self._update_status(nid, "failed")
            return {"status": "failed", "reason": "Max rounds exceeded"}

        # Build context for Party A
        history = self._build_history(rounds, "A")
        a_prompt = (f"You are negotiating on behalf of your user. "
                    f"Your parameters: {json.dumps(neg['party_a_params'])}. "
                    f"Round {round_num} of {neg['max_rounds']}. "
                    f"{history}"
                    f"Make your proposal. Be specific with numbers and terms. "
                    f"If you believe the other party's last proposal is acceptable, say 'ACCEPT: [terms]'.")

        # Build context for Party B
        history_b = self._build_history(rounds, "B")
        b_prompt = (f"You are negotiating on behalf of your user. "
                    f"Your parameters: {json.dumps(neg['party_b_params'])}. "
                    f"Round {round_num} of {neg['max_rounds']}. "
                    f"{history_b}"
                    f"Make your counter-proposal. Be specific. "
                    f"If you believe the other party's last proposal is acceptable, say 'ACCEPT: [terms]'.")

        # Run both agents
        a_response = ""
        b_response = ""
        if self.agents:
            a_result = self.agents.run_agent(neg["party_a_agent"], a_prompt,
                                             user_id=neg["party_a_user"])
            a_response = a_result.get("text", "")

            b_result = self.agents.run_agent(neg["party_b_agent"], b_prompt,
                                             user_id=neg["party_b_user"])
            b_response = b_result.get("text", "")

        round_data = {
            "round": round_num,
            "party_a_proposal": a_response,
            "party_b_proposal": b_response,
            "timestamp": datetime.now().isoformat(),
        }
        rounds.append(round_data)

        # Check for acceptance
        agreed = False
        final_terms = ""
        if "ACCEPT:" in a_response.upper():
            agreed = True
            final_terms = a_response.split("ACCEPT:")[-1].strip() if "ACCEPT:" in a_response else a_response
        elif "ACCEPT:" in b_response.upper():
            agreed = True
            final_terms = b_response.split("ACCEPT:")[-1].strip() if "ACCEPT:" in b_response else b_response

        with get_db() as db:
            if agreed:
                db.execute("""UPDATE negotiations SET rounds=?, status='agreed',
                    final_terms=?, updated_at=? WHERE id=?""",
                    (json.dumps(rounds), final_terms, datetime.now().isoformat(), nid))
            else:
                db.execute("UPDATE negotiations SET rounds=?, updated_at=? WHERE id=?",
                    (json.dumps(rounds), datetime.now().isoformat(), nid))

        return {
            "round": round_num,
            "party_a": a_response,
            "party_b": b_response,
            "agreed": agreed,
            "final_terms": final_terms if agreed else None,
            "status": "agreed" if agreed else "active",
        }

    def run_full(self, nid: str) -> dict:
        """Run all rounds until agreement or exhaustion."""
        neg = self.get_negotiation(nid)
        if not neg: raise ValueError("Not found")
        results = []
        for _ in range(neg["max_rounds"]):
            result = self.run_round(nid)
            results.append(result)
            if result["agreed"] or result["status"] != "active":
                break
        return {"negotiation_id": nid, "rounds": results,
                "final_status": results[-1]["status"] if results else "no_rounds"}

    def _build_history(self, rounds: list, party: str) -> str:
        if not rounds:
            return "This is the opening round. Make your initial proposal. "
        lines = ["Previous rounds: "]
        other = "b" if party == "A" else "a"
        my_key = f"party_{party.lower()}_proposal"
        their_key = f"party_{other}_proposal"
        for r in rounds:
            my_prop = r.get(my_key, "")
            their_prop = r.get(their_key, "")
            lines.append(f"Round {r['round']}: Your proposal: {my_prop} | Their proposal: {their_prop}")
        return " ".join(lines) + " "

    def _update_status(self, nid: str, status: str):
        with get_db() as db:
            db.execute("UPDATE negotiations SET status=?, updated_at=? WHERE id=?",
                      (status, datetime.now().isoformat(), nid))

    def list_negotiations(self, user_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM negotiations WHERE party_a_user=? OR party_b_user=? ORDER BY created_at DESC",
                (user_id, user_id)).fetchall()
        return [dict(r, rounds=json.loads(r.get("rounds", "[]") or "[]"),
                     party_a_params=json.loads(r.get("party_a_params", "{}") or "{}"),
                     party_b_params=json.loads(r.get("party_b_params", "{}") or "{}"))
                for r in rows]


# ══════════════════════════════════════════════════════════════
# 3. CONFIDENCE SCORING WITH SOURCE ATTRIBUTION
# ══════════════════════════════════════════════════════════════

class ConfidenceScorer:
    """Rates every AI response with a confidence level and shows
    exactly where the information came from.

    High = from user's knowledge base or business DNA
    Medium = from AI's training data on a well-known topic
    Low = AI's best guess or speculation
    """

    # Phrases that indicate uncertainty
    UNCERTAIN_PHRASES = [
        "i'm not sure", "i think", "it might", "possibly", "perhaps",
        "it's unclear", "i don't have", "i cannot confirm", "approximately",
        "it could be", "my understanding is", "generally speaking",
        "it depends", "there may be", "i believe", "arguably",
    ]

    # Phrases that indicate confidence
    CONFIDENT_PHRASES = [
        "based on your", "according to your", "in your knowledge base",
        "from your records", "you previously stated", "per your",
        "your business dna shows", "as documented in",
    ]

    def score_response(self, response_text: str, had_kb_context: bool = False,
                       had_dna_context: bool = False, had_shared_context: bool = False,
                       model_used: str = "") -> dict:
        """Score a response's confidence level."""
        text_lower = response_text.lower()

        # Count uncertainty and confidence markers
        uncertain_count = sum(1 for p in self.UNCERTAIN_PHRASES if p in text_lower)
        confident_count = sum(1 for p in self.CONFIDENT_PHRASES if p in text_lower)

        # Base score
        score = 0.7  # default medium

        # Source-based adjustments
        sources = []
        if had_kb_context:
            score += 0.15
            sources.append({"type": "knowledge_base", "label": "Your uploaded documents"})
        if had_dna_context:
            score += 0.1
            sources.append({"type": "business_dna", "label": "Your business patterns"})
        if had_shared_context:
            score += 0.05
            sources.append({"type": "shared_context", "label": "Cross-Space knowledge"})

        if not sources:
            sources.append({"type": "ai_training", "label": "AI general knowledge"})

        # Language-based adjustments
        score += confident_count * 0.05
        score -= uncertain_count * 0.08

        # Clamp
        score = max(0.1, min(1.0, score))

        # Tier
        if score >= 0.85:
            tier = "high"
            label = "High confidence — grounded in your data"
        elif score >= 0.6:
            tier = "medium"
            label = "Medium confidence — based on AI knowledge"
        elif score >= 0.35:
            tier = "low"
            label = "Low confidence — best estimate"
        else:
            tier = "uncertain"
            label = "Uncertain — consider verifying independently"

        # Detect what the AI doesn't know
        gaps = []
        gap_patterns = [
            r"I (?:don't|do not) have (?:access to|information about) (.+?)[\.\,]",
            r"I (?:cannot|can't) (?:confirm|verify) (.+?)[\.\,]",
            r"(?:more information|additional context) (?:about|on|regarding) (.+?) would (?:help|be useful)",
        ]
        for pat in gap_patterns:
            matches = re.findall(pat, text_lower)
            gaps.extend(matches)

        return {
            "score": round(score, 2),
            "tier": tier,
            "label": label,
            "sources": sources,
            "gaps": gaps[:5],
            "model": model_used,
        }


# ══════════════════════════════════════════════════════════════
# 4. TIME-TRAVEL CONTEXT — Decision Archaeology
# ══════════════════════════════════════════════════════════════

class DecisionTracker:
    """Records decisions from conversations and lets users
    search across all history: "What did we decide about pricing?"
    """

    def record_decision(self, owner_id: str, decision: str,
                        reasoning: str = "", conversation_id: str = None,
                        agent_id: str = None, tags: list = None,
                        context: str = "") -> dict:
        did = f"dec_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO decisions
                    (id, owner_id, conversation_id, agent_id, decision,
                     reasoning, context, tags)
                VALUES (?,?,?,?,?,?,?,?)
            """, (did, owner_id, conversation_id, agent_id, decision,
                  reasoning, context, json.dumps(tags or [])))
        return {"id": did, "decision": decision}

    def search_decisions(self, owner_id: str, query: str,
                         limit: int = 10) -> list:
        """Search decisions by keyword — 'What did we decide about pricing?'"""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM decisions WHERE owner_id=? ORDER BY created_at DESC",
                (owner_id,)
            ).fetchall()

        query_words = set(query.lower().split())
        scored = []
        for row in rows:
            d = dict(row)
            d["tags"] = json.loads(d.get("tags", "[]") or "[]")
            text = f"{d['decision']} {d['reasoning']} {d['context']} {' '.join(d['tags'])}".lower()
            text_words = set(text.split())
            overlap = len(query_words & text_words)
            if overlap > 0:
                d["relevance"] = overlap / max(len(query_words), 1)
                scored.append(d)

        scored.sort(key=lambda x: x["relevance"], reverse=True)
        return scored[:limit]

    def list_decisions(self, owner_id: str, agent_id: str = None,
                       limit: int = 50) -> list:
        with get_db() as db:
            if agent_id:
                rows = db.execute(
                    "SELECT * FROM decisions WHERE owner_id=? AND agent_id=? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, agent_id, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM decisions WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, limit)).fetchall()
        return [dict(r, tags=json.loads(r.get("tags", "[]") or "[]")) for r in rows]

    def get_decision(self, did: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM decisions WHERE id=?", (did,)).fetchone()
            if not row: return None
            d = dict(row)
            d["tags"] = json.loads(d.get("tags", "[]") or "[]")
            return d

    def supersede_decision(self, old_id: str, new_decision: str,
                           new_reasoning: str = "", owner_id: str = None,
                           **kwargs) -> dict:
        """Replace an old decision with a new one, keeping history."""
        new = self.record_decision(owner_id or "", new_decision, new_reasoning, **kwargs)
        with get_db() as db:
            db.execute("UPDATE decisions SET superseded_by=? WHERE id=?",
                      (new["id"], old_id))
        return new

    def get_timeline(self, owner_id: str, tag: str = None,
                     limit: int = 30) -> list:
        """Get a chronological timeline of all decisions."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM decisions WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                (owner_id, limit)).fetchall()
        results = [dict(r, tags=json.loads(r.get("tags", "[]") or "[]")) for r in rows]
        if tag:
            results = [r for r in results if tag in r.get("tags", [])]
        return results


# ══════════════════════════════════════════════════════════════
# 5. SPACE CLONING WITH AUDIENCE ADAPTATION
# ══════════════════════════════════════════════════════════════

class SpaceCloner:
    """Clone a Space and auto-adapt it to a client's audience/voice."""

    def __init__(self, agent_manager=None, voice_profile_manager=None):
        self.agents = agent_manager
        self.voice_mgr = voice_profile_manager

    def clone_space(self, source_agent_id: str, owner_id: str,
                    client_name: str = "", adaptations: dict = None) -> dict:
        """Clone a Space with optional audience adaptations.

        adaptations: {
            "audience": "tech founders",
            "tone": "more casual",
            "format": "shorter paragraphs",
            "voice_user_id": "client_user_id"  # use client's voice profile
        }
        """
        if not self.agents:
            raise ValueError("Agent manager not connected")

        source = self.agents.get_agent(source_agent_id)
        if not source:
            raise ValueError("Source Space not found")

        # Build adapted instructions
        instructions = source.get("instructions", "")
        adaptations = adaptations or {}

        adaptation_notes = []
        if adaptations.get("audience"):
            adaptation_notes.append(f"Target audience: {adaptations['audience']}. "
                                   f"Adjust vocabulary, examples, and complexity accordingly.")
        if adaptations.get("tone"):
            adaptation_notes.append(f"Tone adjustment: {adaptations['tone']}.")
        if adaptations.get("format"):
            adaptation_notes.append(f"Format preference: {adaptations['format']}.")

        # If a client voice profile is provided, inject it
        voice_injection = ""
        if adaptations.get("voice_user_id") and self.voice_mgr:
            voice_injection = self.voice_mgr.build_voice_injection(adaptations["voice_user_id"])

        if adaptation_notes:
            instructions += "\n\n[CLIENT ADAPTATION]\n" + "\n".join(adaptation_notes)
        if voice_injection:
            instructions += "\n\n" + voice_injection

        # Create the cloned agent
        clone_name = f"{source['name']}"
        if client_name:
            clone_name += f" ({client_name})"

        clone_data = {
            "name": clone_name,
            "icon": source.get("icon", "🤖"),
            "color": source.get("color", "#a459f2"),
            "description": source.get("description", ""),
            "instructions": instructions,
            "provider": source.get("provider", ""),
            "model": source.get("model", ""),
            "temperature": source.get("temperature", 0.7),
            "max_tokens": source.get("max_tokens", 4096),
        }
        cloned = self.agents.create_agent(clone_data, owner_id=owner_id)
        clone_id = cloned.get("id") or cloned.get("agent", {}).get("id", "")

        # Record the clone relationship
        sc_id = f"sc_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO space_clones
                    (id, source_agent_id, cloned_agent_id, owner_id, client_name, adaptation_profile)
                VALUES (?,?,?,?,?,?)
            """, (sc_id, source_agent_id, clone_id, owner_id,
                  client_name, json.dumps(adaptations)))

        return {
            "clone_id": clone_id,
            "source_id": source_agent_id,
            "client_name": client_name,
            "adaptations_applied": adaptation_notes,
            "has_voice_profile": bool(voice_injection),
        }

    def list_clones(self, owner_id: str = None, source_id: str = None) -> list:
        with get_db() as db:
            if source_id:
                rows = db.execute(
                    "SELECT * FROM space_clones WHERE source_agent_id=? ORDER BY created_at DESC",
                    (source_id,)).fetchall()
            elif owner_id:
                rows = db.execute(
                    "SELECT * FROM space_clones WHERE owner_id=? ORDER BY created_at DESC",
                    (owner_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM space_clones ORDER BY created_at DESC").fetchall()
        return [dict(r, adaptation_profile=json.loads(r.get("adaptation_profile", "{}") or "{}"))
                for r in rows]


# ══════════════════════════════════════════════════════════════
# 6. REAL-TIME COST TICKER
# ══════════════════════════════════════════════════════════════

class CostTicker:
    """Live per-conversation cost tracking.
    "This conversation has cost $0.03 so far."
    "Stop me if this conversation exceeds $0.50."
    """

    # Approximate costs per 1K tokens (input/output)
    MODEL_COSTS = {
        "claude-haiku-4-5-20251001": (0.001, 0.005),
        "claude-sonnet-4-5-20250929": (0.003, 0.015),
        "claude-opus-4-5-20250929": (0.015, 0.075),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4o": (0.0025, 0.01),
        "o1-preview": (0.015, 0.06),
        "o3-mini": (0.0011, 0.0044),
        "grok-2-latest": (0.002, 0.01),
        "grok-3": (0.003, 0.015),
        "grok-3-mini": (0.0003, 0.0005),
        "gemini-2.0-flash": (0.0001, 0.0004),
        "gemini-1.5-pro": (0.00125, 0.005),
        "mistral-large-latest": (0.002, 0.006),
        "mistral-small-latest": (0.0002, 0.0006),
        "deepseek-chat": (0.00014, 0.00028),
        "deepseek-reasoner": (0.00055, 0.00219),
        "command-r-plus": (0.003, 0.015),
        "sonar-pro": (0.003, 0.015),
        "llama-3.1-70b-versatile": (0.00059, 0.00079),
    }

    def record_message_cost(self, conversation_id: str, model: str,
                            input_tokens: int, output_tokens: int) -> dict:
        """Record tokens and cost for a single message."""
        costs = self.MODEL_COSTS.get(model, (0.003, 0.015))  # default to mid-tier
        msg_cost = (input_tokens / 1000 * costs[0]) + (output_tokens / 1000 * costs[1])

        with get_db() as db:
            # Upsert conversation cost tracker
            existing = db.execute(
                "SELECT * FROM conversation_costs WHERE conversation_id=?",
                (conversation_id,)
            ).fetchone()

            if existing:
                db.execute("""
                    UPDATE conversation_costs SET
                        total_input_tokens=total_input_tokens+?,
                        total_output_tokens=total_output_tokens+?,
                        total_cost=total_cost+?,
                        message_count=message_count+1,
                        updated_at=?
                    WHERE conversation_id=?
                """, (input_tokens, output_tokens, msg_cost,
                      datetime.now().isoformat(), conversation_id))
            else:
                db.execute("""
                    INSERT INTO conversation_costs
                        (conversation_id, total_input_tokens, total_output_tokens,
                         total_cost, message_count)
                    VALUES (?,?,?,?,1)
                """, (conversation_id, input_tokens, output_tokens, msg_cost))

            # Check budget cap
            row = db.execute(
                "SELECT * FROM conversation_costs WHERE conversation_id=?",
                (conversation_id,)
            ).fetchone()

        result = dict(row) if row else {}
        result["this_message_cost"] = round(msg_cost, 6)
        result["total_cost"] = round(result.get("total_cost", 0), 6)

        # Budget check
        budget = result.get("budget_cap", 0)
        if budget > 0 and result["total_cost"] >= budget:
            result["budget_exceeded"] = True
            result["budget_message"] = f"Budget cap of ${budget:.2f} reached. This conversation has cost ${result['total_cost']:.4f}."
        else:
            result["budget_exceeded"] = False

        return result

    def get_conversation_cost(self, conversation_id: str) -> dict:
        """Get current cost for a conversation."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM conversation_costs WHERE conversation_id=?",
                (conversation_id,)
            ).fetchone()
        if not row:
            return {"conversation_id": conversation_id, "total_cost": 0,
                    "message_count": 0, "total_input_tokens": 0, "total_output_tokens": 0}
        return dict(row)

    def set_budget_cap(self, conversation_id: str, cap: float) -> dict:
        """Set a budget cap for a conversation."""
        with get_db() as db:
            db.execute(
                "UPDATE conversation_costs SET budget_cap=? WHERE conversation_id=?",
                (cap, conversation_id))
        return {"conversation_id": conversation_id, "budget_cap": cap}

    def get_user_total_cost(self, user_id: str, days: int = 30) -> dict:
        """Get total cost across all conversations for a user."""
        with get_db() as db:
            row = db.execute("""
                SELECT SUM(cc.total_cost) as total_cost,
                       SUM(cc.total_input_tokens) as input_tokens,
                       SUM(cc.total_output_tokens) as output_tokens,
                       SUM(cc.message_count) as messages,
                       COUNT(cc.conversation_id) as conversations
                FROM conversation_costs cc
                JOIN conversations c ON c.id = cc.conversation_id
                WHERE c.user_id=?
            """, (user_id,)).fetchone()
        return dict(row) if row else {"total_cost": 0}

    def estimate_cost(self, model: str, input_text: str) -> dict:
        """Estimate cost before sending a message."""
        # Rough token estimate: ~4 chars per token
        est_input_tokens = len(input_text) / 4
        est_output_tokens = est_input_tokens * 1.5  # assume response is ~1.5x input
        costs = self.MODEL_COSTS.get(model, (0.003, 0.015))
        est_cost = (est_input_tokens / 1000 * costs[0]) + (est_output_tokens / 1000 * costs[1])
        return {
            "model": model,
            "estimated_input_tokens": int(est_input_tokens),
            "estimated_output_tokens": int(est_output_tokens),
            "estimated_cost": round(est_cost, 6),
        }
