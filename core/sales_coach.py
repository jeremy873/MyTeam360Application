# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Sales Coach — AI-Powered Sales Prep, Interview Coaching, and Deal Intelligence

Nobody else has this. An AI that:
  1. Reads the RFP/RFI and extracts what the client actually wants
  2. Reads your proposal and identifies gaps vs. the RFP
  3. Simulates the client interview — asks the hard questions
  4. Coaches you on objection handling for YOUR specific deal
  5. Scores your pitch and gives specific improvement feedback
  6. Builds a deal brief — everything you need on one page
  7. Tracks deal pipeline with win/loss analysis

The user uploads the RFP, uploads their proposal, and the AI becomes
a sales coach that knows every detail of both documents.
"""

import json
import uuid
import re
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.sales_coach")


class SalesCoach:
    """AI-powered sales preparation and interview coaching."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    # ── DEAL MANAGEMENT ─────────────────────────────────────

    def create_deal(self, owner_id: str, title: str, client_name: str,
                    deal_value: float = 0, close_date: str = None,
                    stage: str = "prospect", notes: str = "",
                    rfp_text: str = "", proposal_text: str = "",
                    client_requirements: str = "") -> dict:
        """Create a new deal with optional RFP and proposal text."""
        did = f"deal_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO sales_deals
                    (id, owner_id, title, client_name, deal_value, close_date,
                     stage, notes, rfp_text, proposal_text, client_requirements)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (did, owner_id, title, client_name, deal_value, close_date,
                  stage, notes, rfp_text, proposal_text, client_requirements))
        return {"id": did, "title": title, "client": client_name, "stage": stage}

    def get_deal(self, did: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM sales_deals WHERE id=?", (did,)).fetchone()
        if not row: return None
        d = dict(row)
        d["coaching_sessions"] = self._get_sessions(did)
        return d

    def list_deals(self, owner_id: str, stage: str = None) -> list:
        with get_db() as db:
            if stage:
                rows = db.execute(
                    "SELECT id, title, client_name, deal_value, stage, close_date, created_at FROM sales_deals WHERE owner_id=? AND stage=? ORDER BY created_at DESC",
                    (owner_id, stage)).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, title, client_name, deal_value, stage, close_date, created_at FROM sales_deals WHERE owner_id=? ORDER BY created_at DESC",
                    (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def update_deal(self, did: str, updates: dict) -> dict:
        safe = {"title", "client_name", "deal_value", "close_date", "stage",
                "notes", "rfp_text", "proposal_text", "client_requirements", "outcome", "loss_reason"}
        filtered = {k: v for k, v in updates.items() if k in safe}
        filtered["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in filtered)
        vals = list(filtered.values()) + [did]
        with get_db() as db:
            db.execute(f"UPDATE sales_deals SET {sets} WHERE id=?", vals)
        return self.get_deal(did)

    # ── RFP ANALYSIS ────────────────────────────────────────

    def analyze_rfp(self, did: str, owner_id: str) -> dict:
        """AI analyzes the RFP and extracts key requirements, evaluation criteria,
        red flags, and what the client really wants."""
        deal = self.get_deal(did)
        if not deal or not deal.get("rfp_text"):
            return {"error": "No RFP text found. Upload the RFP first."}

        prompt = (
            "You are a senior sales strategist analyzing a Request for Proposal. "
            "Analyze this RFP thoroughly and provide:\n\n"
            "1. EXECUTIVE SUMMARY — What is the client looking for in 2-3 sentences?\n"
            "2. KEY REQUIREMENTS — Numbered list of must-have requirements\n"
            "3. EVALUATION CRITERIA — How will they score proposals? What weights?\n"
            "4. HIDDEN PRIORITIES — Read between the lines. What do they REALLY care about?\n"
            "5. RED FLAGS — Anything that suggests this deal is risky or pre-wired for a competitor\n"
            "6. TIMELINE & DEADLINES — Key dates\n"
            "7. BUDGET SIGNALS — Any clues about their budget range?\n"
            "8. WIN THEMES — The top 3 themes your proposal should hit\n\n"
            f"RFP Text:\n{deal['rfp_text'][:12000]}"
        )

        analysis = self._run_agent(deal, prompt, owner_id)
        self._save_session(did, "rfp_analysis", prompt, analysis)
        return {"deal_id": did, "analysis": analysis}

    # ── GAP ANALYSIS ────────────────────────────────────────

    def gap_analysis(self, did: str, owner_id: str) -> dict:
        """Compare your proposal against the RFP — find gaps and strengths."""
        deal = self.get_deal(did)
        if not deal.get("rfp_text") or not deal.get("proposal_text"):
            return {"error": "Both RFP and proposal text required."}

        prompt = (
            "You are a proposal review specialist. Compare this proposal against the RFP "
            "and provide a detailed gap analysis:\n\n"
            "1. REQUIREMENTS MET — Which RFP requirements does the proposal address well?\n"
            "2. GAPS — Which requirements are missing or weakly addressed?\n"
            "3. STRENGTHS — Where does the proposal exceed what the RFP asks for?\n"
            "4. COMPETITIVE VULNERABILITIES — Where could a competitor beat this proposal?\n"
            "5. PRICING ASSESSMENT — Is the pricing aligned with what the RFP suggests?\n"
            "6. COMPLIANCE CHECK — Does the proposal meet all mandatory format/content requirements?\n"
            "7. RECOMMENDED IMPROVEMENTS — Specific, actionable changes ranked by impact\n\n"
            f"RFP:\n{deal['rfp_text'][:6000]}\n\n"
            f"PROPOSAL:\n{deal['proposal_text'][:6000]}"
        )

        analysis = self._run_agent(deal, prompt, owner_id)
        self._save_session(did, "gap_analysis", prompt, analysis)
        return {"deal_id": did, "analysis": analysis}

    # ── INTERVIEW SIMULATION ────────────────────────────────

    def simulate_interview(self, did: str, owner_id: str,
                           difficulty: str = "tough",
                           focus: str = "") -> dict:
        """Simulate the client interview. AI plays the client and asks hard questions."""
        deal = self.get_deal(did)
        if not deal:
            return {"error": "Deal not found."}

        difficulty_map = {
            "friendly": "Ask straightforward questions. Be warm and encouraging.",
            "moderate": "Ask probing questions. Push for specifics but remain fair.",
            "tough": "Be a tough evaluator. Ask hard questions, push back on vague answers, test their knowledge deeply.",
            "hostile": "Be skeptical and adversarial. Challenge everything. Play devil's advocate. You're looking for reasons to say no.",
        }

        focus_instruction = ""
        if focus:
            focus_instruction = f"Focus your questions specifically on: {focus}. "

        context_parts = []
        if deal.get("rfp_text"):
            context_parts.append(f"RFP: {deal['rfp_text'][:4000]}")
        if deal.get("proposal_text"):
            context_parts.append(f"Their proposal: {deal['proposal_text'][:4000]}")
        if deal.get("client_requirements"):
            context_parts.append(f"Client priorities: {deal['client_requirements']}")

        prompt = (
            f"You are the client evaluator for {deal.get('client_name', 'the client')}. "
            f"You are interviewing a vendor who submitted a proposal for: {deal['title']}.\n\n"
            f"{difficulty_map.get(difficulty, difficulty_map['tough'])}\n"
            f"{focus_instruction}\n\n"
            "Generate 8-10 interview questions the client would ask, ordered from "
            "opening questions to the hardest closing questions. For each question, include:\n"
            "- The question itself\n"
            "- WHY the client is asking this (what they're really trying to learn)\n"
            "- What a GREAT answer looks like (brief)\n"
            "- What a BAD answer looks like (brief)\n\n"
            + "\n\n".join(context_parts)
        )

        questions = self._run_agent(deal, prompt, owner_id)
        self._save_session(did, "interview_simulation", prompt, questions)
        return {"deal_id": did, "difficulty": difficulty, "questions": questions}

    # ── OBJECTION HANDLING ──────────────────────────────────

    def prepare_objections(self, did: str, owner_id: str) -> dict:
        """Generate likely objections and prepare responses."""
        deal = self.get_deal(did)
        if not deal:
            return {"error": "Deal not found."}

        context_parts = []
        if deal.get("rfp_text"):
            context_parts.append(f"RFP: {deal['rfp_text'][:4000]}")
        if deal.get("proposal_text"):
            context_parts.append(f"Proposal: {deal['proposal_text'][:4000]}")

        prompt = (
            "You are a senior sales coach. Based on this deal, generate the 10 most likely "
            "objections the client will raise, and for each one provide:\n\n"
            "1. THE OBJECTION — Exactly what the client will say\n"
            "2. WHY THEY'RE SAYING IT — The underlying concern\n"
            "3. THE WRONG RESPONSE — What most people say (and why it fails)\n"
            "4. THE RIGHT RESPONSE — A specific, confident answer with evidence\n"
            "5. BRIDGE STATEMENT — How to transition back to your strengths\n\n"
            f"Deal: {deal['title']} for {deal.get('client_name', 'client')}\n"
            f"Value: ${deal.get('deal_value', 0):,.0f}\n\n"
            + "\n\n".join(context_parts)
        )

        objections = self._run_agent(deal, prompt, owner_id)
        self._save_session(did, "objection_handling", prompt, objections)
        return {"deal_id": did, "objections": objections}

    # ── PITCH SCORING ───────────────────────────────────────

    def score_pitch(self, did: str, owner_id: str, pitch_text: str) -> dict:
        """User submits their pitch/presentation and gets scored with feedback."""
        deal = self.get_deal(did)
        if not deal:
            return {"error": "Deal not found."}

        context_parts = []
        if deal.get("rfp_text"):
            context_parts.append(f"RFP requirements: {deal['rfp_text'][:3000]}")
        if deal.get("client_requirements"):
            context_parts.append(f"Client priorities: {deal['client_requirements']}")

        prompt = (
            "You are a sales presentation coach. Score this pitch on a scale of 1-10 "
            "across these dimensions, then provide specific feedback:\n\n"
            "SCORING DIMENSIONS:\n"
            "1. CLARITY (1-10) — Is the message clear and easy to follow?\n"
            "2. RELEVANCE (1-10) — Does it address what the client actually asked for?\n"
            "3. DIFFERENTIATION (1-10) — Does it explain why YOU vs. competitors?\n"
            "4. EVIDENCE (1-10) — Are claims backed by data, examples, or case studies?\n"
            "5. CONFIDENCE (1-10) — Does it sound authoritative without being arrogant?\n"
            "6. CALL TO ACTION (1-10) — Is there a clear next step?\n\n"
            "Then provide:\n"
            "- OVERALL SCORE (average)\n"
            "- TOP 3 STRENGTHS\n"
            "- TOP 3 WEAKNESSES\n"
            "- SPECIFIC REWRITES — Take the weakest 2-3 sentences and rewrite them\n"
            "- MISSING ELEMENTS — What should be added\n\n"
            f"Context:\n{chr(10).join(context_parts)}\n\n"
            f"PITCH TO SCORE:\n{pitch_text[:6000]}"
        )

        feedback = self._run_agent(deal, prompt, owner_id)
        self._save_session(did, "pitch_scoring", prompt, feedback)
        return {"deal_id": did, "feedback": feedback}

    # ── DEAL BRIEF ──────────────────────────────────────────

    def generate_brief(self, did: str, owner_id: str) -> dict:
        """One-page deal brief — everything you need before walking in."""
        deal = self.get_deal(did)
        if not deal:
            return {"error": "Deal not found."}

        sessions = deal.get("coaching_sessions", [])
        session_context = ""
        for s in sessions[-5:]:  # last 5 sessions
            session_context += f"\n[{s.get('session_type','')}]: {s.get('response','')[:500]}\n"

        context_parts = [f"Deal: {deal['title']}", f"Client: {deal.get('client_name','')}",
                        f"Value: ${deal.get('deal_value',0):,.0f}"]
        if deal.get("rfp_text"):
            context_parts.append(f"RFP summary: {deal['rfp_text'][:2000]}")
        if deal.get("proposal_text"):
            context_parts.append(f"Proposal summary: {deal['proposal_text'][:2000]}")

        prompt = (
            "Create a concise ONE-PAGE deal brief for a sales meeting. Format:\n\n"
            "DEAL BRIEF — [Client Name]\n"
            "Date: [today]\n\n"
            "THE OPPORTUNITY: 2 sentences on what they need\n"
            "YOUR SOLUTION: 2 sentences on what you're proposing\n"
            "DEAL VALUE: $X | CLOSE DATE: X\n"
            "KEY DECISION MAKER: (if known from RFP)\n\n"
            "TOP 3 THINGS THE CLIENT CARES ABOUT:\n"
            "1. ...\n2. ...\n3. ...\n\n"
            "YOUR 3 STRONGEST POINTS:\n"
            "1. ...\n2. ...\n3. ...\n\n"
            "LIKELY OBJECTIONS + YOUR RESPONSES:\n"
            "1. They'll say: ... → You say: ...\n"
            "2. They'll say: ... → You say: ...\n\n"
            "DO NOT SAY: (things to avoid)\n"
            "CLOSING MOVE: (how to end the meeting)\n\n"
            + "\n".join(context_parts)
            + "\n\nPrevious coaching insights:" + session_context
        )

        brief = self._run_agent(deal, prompt, owner_id)
        self._save_session(did, "deal_brief", prompt, brief)
        return {"deal_id": did, "brief": brief}

    # ── LIVE COACHING ───────────────────────────────────────

    def coach_response(self, did: str, owner_id: str,
                       client_question: str) -> dict:
        """Real-time coaching: 'The client just asked X, how should I respond?'"""
        deal = self.get_deal(did)
        if not deal:
            return {"error": "Deal not found."}

        context_parts = []
        if deal.get("rfp_text"):
            context_parts.append(f"RFP context: {deal['rfp_text'][:2000]}")
        if deal.get("proposal_text"):
            context_parts.append(f"Your proposal: {deal['proposal_text'][:2000]}")

        prompt = (
            "You are a sales coach sitting next to your client in an earpiece. "
            "They need an immediate, specific response to this question from the buyer. "
            "Give them:\n\n"
            "1. QUICK ANSWER (2-3 sentences they can say right now)\n"
            "2. KEY POINT TO EMPHASIZE\n"
            "3. WHAT NOT TO SAY\n"
            "4. BRIDGE TO YOUR STRENGTH (one sentence to pivot to your advantage)\n\n"
            f"Deal: {deal['title']} | Client: {deal.get('client_name','')}\n"
            + "\n".join(context_parts)
            + f"\n\nCLIENT JUST ASKED: \"{client_question}\""
        )

        coaching = self._run_agent(deal, prompt, owner_id)
        self._save_session(did, "live_coaching", client_question, coaching)
        return {"deal_id": did, "question": client_question, "coaching": coaching}

    # ── WIN/LOSS ANALYSIS ───────────────────────────────────

    def record_outcome(self, did: str, outcome: str,
                       loss_reason: str = "", notes: str = "") -> dict:
        """Record deal outcome for pipeline analytics."""
        if outcome not in ("won", "lost", "no_decision", "cancelled"):
            raise ValueError("outcome must be: won, lost, no_decision, or cancelled")
        with get_db() as db:
            db.execute("""
                UPDATE sales_deals SET outcome=?, loss_reason=?, stage=?, updated_at=?
                WHERE id=?
            """, (outcome, loss_reason, "closed", datetime.now().isoformat(), did))
        return {"deal_id": did, "outcome": outcome}

    def get_pipeline(self, owner_id: str) -> dict:
        """Pipeline dashboard with win/loss analytics."""
        with get_db() as db:
            deals = db.execute(
                "SELECT * FROM sales_deals WHERE owner_id=? ORDER BY created_at DESC",
                (owner_id,)).fetchall()

        total_value = sum(d["deal_value"] or 0 for d in deals)
        won = [d for d in deals if d.get("outcome") == "won"]
        lost = [d for d in deals if d.get("outcome") == "lost"]
        active = [d for d in deals if d.get("outcome") is None or d["outcome"] == ""]

        won_value = sum(d["deal_value"] or 0 for d in won)
        win_rate = len(won) / max(len(won) + len(lost), 1) * 100

        # Loss reasons
        loss_reasons = {}
        for d in lost:
            reason = d.get("loss_reason", "unspecified") or "unspecified"
            loss_reasons[reason] = loss_reasons.get(reason, 0) + 1

        # Stage breakdown
        stages = {}
        for d in active:
            s = d.get("stage", "prospect")
            stages.setdefault(s, {"count": 0, "value": 0})
            stages[s]["count"] += 1
            stages[s]["value"] += d.get("deal_value", 0) or 0

        return {
            "total_deals": len(deals),
            "active_deals": len(active),
            "total_pipeline_value": total_value,
            "won_count": len(won),
            "won_value": won_value,
            "lost_count": len(lost),
            "win_rate_pct": round(win_rate, 1),
            "loss_reasons": loss_reasons,
            "stages": stages,
        }

    # ── INTERNAL ────────────────────────────────────────────

    def _run_agent(self, deal: dict, prompt: str, owner_id: str) -> str:
        """Run an agent for coaching. Uses the first available agent."""
        if not self.agents:
            return "(Agent manager not connected — coaching requires an AI provider)"
        with get_db() as db:
            agent = db.execute(
                "SELECT id FROM agents WHERE owner_id=? LIMIT 1",
                (owner_id,)).fetchone()
        if not agent:
            return "(No Spaces configured — create at least one Space first)"
        result = self.agents.run_agent(dict(agent)["id"], prompt, user_id=owner_id)
        return result.get("text", "")

    def _save_session(self, deal_id: str, session_type: str,
                      prompt: str, response: str):
        sid = f"sc_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO sales_coaching_sessions
                    (id, deal_id, session_type, prompt, response)
                VALUES (?,?,?,?,?)
            """, (sid, deal_id, session_type, prompt[:2000], response[:5000]))

    def _get_sessions(self, deal_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT id, session_type, response, created_at FROM sales_coaching_sessions WHERE deal_id=? ORDER BY created_at DESC LIMIT 20",
                (deal_id,)).fetchall()
        return [dict(r) for r in rows]
