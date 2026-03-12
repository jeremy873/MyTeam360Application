# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Feature Gate — Admin-Controlled Feature Activation

ALL advanced features are OFF by default. An admin must explicitly
activate each one. This ensures:
  - Companies only pay attention to features they need
  - No compliance scanning unless they want it
  - No overhead from unused features
  - Clean onboarding — start simple, add power as needed
  - Full audit trail of who activated what and when
"""

import json
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.feature_gate")


# Every gatable feature with its default state and description
FEATURE_REGISTRY = {
    # ── Untouchable Features ──
    "business_dna": {
        "label": "Business DNA / Digital Twin",
        "description": "Build a searchable knowledge base from conversation patterns. Auto-injected into every chat.",
        "category": "intelligence",
        "default": False,
    },
    "ai_negotiation": {
        "label": "AI-to-AI Negotiation",
        "description": "Two Spaces negotiate on behalf of users with structured proposals and counter-proposals.",
        "category": "intelligence",
        "default": False,
    },
    "confidence_scoring": {
        "label": "Confidence Scoring",
        "description": "Every AI response rated High/Medium/Low with source attribution and knowledge gap detection.",
        "category": "intelligence",
        "default": False,
    },
    "decision_tracker": {
        "label": "Time-Travel Decisions",
        "description": "Record and search decisions across all conversations. 'What did we decide about pricing?'",
        "category": "intelligence",
        "default": False,
    },
    "space_cloning": {
        "label": "Space Cloning with Adaptation",
        "description": "Clone Spaces for clients with auto-adapted tone, audience, and voice profile.",
        "category": "intelligence",
        "default": False,
    },
    "cost_ticker": {
        "label": "Real-Time Cost Ticker",
        "description": "Live per-message cost tracking with budget caps and pre-send estimates.",
        "category": "financial",
        "default": False,
    },

    # ── Roundtable ──
    "roundtable": {
        "label": "Roundtable Discussions",
        "description": "Multi-agent discussions where 2-6 Spaces debate a problem. User moderates.",
        "category": "collaboration",
        "default": False,
    },
    "roundtable_multiuser": {
        "label": "Multi-User Roundtable",
        "description": "Invite human team members to participate alongside AI Spaces in Roundtables.",
        "category": "collaboration",
        "default": False,
    },

    # ── Collaboration ──
    "teams": {
        "label": "Teams",
        "description": "Create teams, invite members, assign roles, and collaborate across the organization.",
        "category": "collaboration",
        "default": False,
    },
    "presence": {
        "label": "Presence Tracking",
        "description": "See who's online in the team and who's active in a Roundtable.",
        "category": "collaboration",
        "default": False,
    },
    "activity_feed": {
        "label": "Team Activity Feed",
        "description": "Team-wide log of who did what and when.",
        "category": "collaboration",
        "default": False,
    },

    # ── Governance ──
    "meeting_minutes": {
        "label": "Meeting Minutes",
        "description": "Auto-generate formal meeting minutes from Roundtables or any conversation.",
        "category": "governance",
        "default": False,
    },
    "corporate_records": {
        "label": "Corporate Records",
        "description": "Formal record keeping with 13 categories, retention policies, and expiration tracking.",
        "category": "governance",
        "default": False,
    },
    "resolutions": {
        "label": "Resolution Voting",
        "description": "Formal vote tracking with majority/supermajority/unanimous thresholds.",
        "category": "governance",
        "default": False,
    },
    "summarization": {
        "label": "Summarization Engine",
        "description": "Executive briefs, detailed summaries, action item extraction, and governance digests.",
        "category": "governance",
        "default": False,
    },
    "doc_export": {
        "label": "Document Export",
        "description": "Export minutes, records, resolutions, and transcripts to .docx with company letterhead.",
        "category": "governance",
        "default": False,
    },

    # ── Enterprise ──
    "action_items": {
        "label": "Action Item Tracker",
        "description": "Track commitments with assignees, due dates, priorities, and overdue alerts.",
        "category": "enterprise",
        "default": False,
    },
    "compliance_watchdog": {
        "label": "Compliance Watchdog",
        "description": "Real-time scanning of all messages for 18 regulatory categories including FCPA, UK Bribery Act, HIPAA, and more.",
        "category": "enterprise",
        "default": False,
    },
    "compliance_escalation": {
        "label": "Compliance Escalation Pipeline",
        "description": "3-tier internal escalation routing violations to Compliance Officer and admins.",
        "category": "enterprise",
        "default": False,
    },
    "client_deliverables": {
        "label": "Client Deliverables",
        "description": "Auto-generate polished client-ready reports, proposals, and briefs from conversations.",
        "category": "enterprise",
        "default": False,
    },
    "delegation_authority": {
        "label": "Delegation of Authority",
        "description": "Temporary authority transfer with scope, time limits, and audit trail.",
        "category": "enterprise",
        "default": False,
    },
    "risk_register": {
        "label": "Risk Register",
        "description": "Track organizational risks with severity, likelihood, mitigation status, and heat map.",
        "category": "enterprise",
        "default": False,
    },
    "policy_engine": {
        "label": "Policy Engine",
        "description": "Define company rules in plain English. Auto-injected into every Space and enforced on every message.",
        "category": "enterprise",
        "default": False,
    },
    "knowledge_handoff": {
        "label": "Knowledge Handoff",
        "description": "Generate structured knowledge transfer packages when team members leave.",
        "category": "enterprise",
        "default": False,
    },
    "sales_coach": {
        "label": "Sales Coach & Interview Prep",
        "description": "RFP analysis, proposal gap analysis, interview simulation, objection handling, pitch scoring, deal briefs, and live coaching.",
        "category": "enterprise",
        "default": False,
    },
    "digital_marketing": {
        "label": "Digital Marketing Engine",
        "description": "Country-aware campaign planning, content generation, platform strategy, ad compliance checking, and SEO briefs.",
        "category": "enterprise",
        "default": False,
    },
    "content_guardrails": {
        "label": "Content Guardrails & Parental Consent",
        "description": "Age verification, parental/guardian TOS consent, approved curriculum enforcement, and AI output content filtering.",
        "category": "enterprise",
        "default": False,
    },
    "education_tutor": {
        "label": "K-12 Tutoring",
        "description": "Socratic method tutoring, homework help, study guides, practice quizzes, progress tracking, and parent dashboard.",
        "category": "education",
        "default": False,
    },
}


class FeatureGate:
    """Controls which features are active. Admin must explicitly enable each one."""

    def is_enabled(self, feature: str, owner_id: str = None) -> bool:
        """Check if a feature is enabled."""
        if feature not in FEATURE_REGISTRY:
            return True  # unknown features are ungated (core features)

        with get_db() as db:
            row = db.execute(
                "SELECT enabled FROM feature_gates WHERE feature=?",
                (feature,)).fetchone()

        if row is None:
            return FEATURE_REGISTRY[feature].get("default", False)
        return bool(dict(row)["enabled"])

    def enable(self, feature: str, admin_id: str, admin_name: str = "") -> dict:
        """Admin enables a feature."""
        if feature not in FEATURE_REGISTRY:
            raise ValueError(f"Unknown feature: {feature}")

        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO feature_gates
                    (feature, enabled, changed_by, changed_by_name, changed_at)
                VALUES (?,1,?,?,?)
            """, (feature, admin_id, admin_name, datetime.now().isoformat()))

            # Audit log
            db.execute("""
                INSERT INTO feature_gate_log
                    (feature, action, admin_id, admin_name)
                VALUES (?,?,?,?)
            """, (feature, "enabled", admin_id, admin_name))

        info = FEATURE_REGISTRY[feature]
        return {"feature": feature, "label": info["label"], "enabled": True}

    def disable(self, feature: str, admin_id: str, admin_name: str = "") -> dict:
        """Admin disables a feature."""
        if feature not in FEATURE_REGISTRY:
            raise ValueError(f"Unknown feature: {feature}")

        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO feature_gates
                    (feature, enabled, changed_by, changed_by_name, changed_at)
                VALUES (?,0,?,?,?)
            """, (feature, admin_id, admin_name, datetime.now().isoformat()))

            db.execute("""
                INSERT INTO feature_gate_log
                    (feature, action, admin_id, admin_name)
                VALUES (?,?,?,?)
            """, (feature, "disabled", admin_id, admin_name))

        info = FEATURE_REGISTRY[feature]
        return {"feature": feature, "label": info["label"], "enabled": False}

    def get_all(self) -> list:
        """Get all features with their current state."""
        with get_db() as db:
            rows = db.execute("SELECT * FROM feature_gates").fetchall()
        states = {dict(r)["feature"]: dict(r) for r in rows}

        result = []
        for key, info in FEATURE_REGISTRY.items():
            state = states.get(key, {})
            result.append({
                "feature": key,
                "label": info["label"],
                "description": info["description"],
                "category": info["category"],
                "enabled": bool(state.get("enabled", info["default"])),
                "changed_by": state.get("changed_by_name", ""),
                "changed_at": state.get("changed_at", ""),
            })
        return result

    def get_by_category(self) -> dict:
        """Get features grouped by category."""
        all_features = self.get_all()
        categories = {}
        for f in all_features:
            cat = f["category"]
            categories.setdefault(cat, []).append(f)
        return categories

    def get_audit_log(self, limit: int = 50) -> list:
        """Who enabled/disabled what and when."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM feature_gate_log ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def bulk_enable(self, features: list, admin_id: str,
                    admin_name: str = "") -> list:
        """Enable multiple features at once."""
        results = []
        for f in features:
            try:
                results.append(self.enable(f, admin_id, admin_name))
            except ValueError:
                results.append({"feature": f, "error": "unknown feature"})
        return results

    def bulk_disable(self, features: list, admin_id: str,
                     admin_name: str = "") -> list:
        """Disable multiple features at once."""
        results = []
        for f in features:
            try:
                results.append(self.disable(f, admin_id, admin_name))
            except ValueError:
                results.append({"feature": f, "error": "unknown feature"})
        return results
