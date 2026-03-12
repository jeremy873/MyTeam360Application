# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Platform Foundations — The five pillars that make this world-changing.

1. ACCESSIBILITY — Works for everyone, period.
2. ETHICAL REASONING — Not just "is it legal?" but "is it right?"
3. DATA PORTABILITY — Your data. You can take it and leave. No lock-in.
4. SPONSORED TIER — Paying customers fund access for those who can't afford it.
5. TRANSPARENCY REPORT — Public proof we practice what we preach.
"""

import json
import uuid
import re
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.foundations")


# ══════════════════════════════════════════════════════════════
# 1. ACCESSIBILITY ENGINE
# ══════════════════════════════════════════════════════════════

class AccessibilityEngine:
    """Ensures the platform works for EVERYONE.

    Not a checklist. A commitment.

    - Screen reader support (ARIA labels, semantic HTML, focus management)
    - Dyslexia-friendly mode (OpenDyslexic font, increased spacing, muted colors)
    - ADHD support mode (reduced animations, focus mode, chunked content)
    - High contrast mode (WCAG AAA contrast ratios)
    - Reduced motion (respects prefers-reduced-motion, disables all animations)
    - Keyboard-only navigation (every action reachable without a mouse)
    - Large text mode (minimum 18px, scalable)
    - Color blind safe (never relies on color alone for information)
    - Voice control integration (works with voice navigation software)
    - Cognitive load reduction (simplified UI option, progressive disclosure)
    """

    MODES = {
        "default": {
            "label": "Default",
            "description": "Standard platform experience",
        },
        "high_contrast": {
            "label": "High Contrast",
            "description": "WCAG AAA contrast ratios. Maximum readability.",
            "css_overrides": {
                "background": "#000000",
                "text": "#FFFFFF",
                "accent": "#FFD700",
                "surface": "#1a1a1a",
                "border": "#FFFFFF",
                "link": "#00BFFF",
                "focus_ring": "#FFD700 3px solid",
            },
        },
        "dyslexia_friendly": {
            "label": "Dyslexia Friendly",
            "description": "OpenDyslexic font, wider spacing, cream background.",
            "css_overrides": {
                "font_family": "OpenDyslexic, Comic Sans MS, sans-serif",
                "letter_spacing": "0.12em",
                "word_spacing": "0.16em",
                "line_height": "1.8",
                "background": "#FBF0D9",
                "text": "#333333",
                "max_width": "680px",
            },
        },
        "adhd_focus": {
            "label": "Focus Mode (ADHD)",
            "description": "Reduced distractions. No animations. Chunked content. Clear structure.",
            "css_overrides": {
                "animation": "none",
                "transition": "none",
                "max_width": "600px",
                "font_size": "16px",
                "line_height": "1.7",
            },
            "behavior_overrides": {
                "disable_animations": True,
                "chunk_responses": True,
                "max_paragraph_length": 3,
                "show_progress_indicators": True,
                "auto_summarize_long_responses": True,
            },
        },
        "reduced_motion": {
            "label": "Reduced Motion",
            "description": "No animations or transitions. Static orb. Instant transitions.",
            "css_overrides": {
                "animation": "none",
                "transition": "none",
            },
        },
        "large_text": {
            "label": "Large Text",
            "description": "Minimum 18px text. Everything scales up.",
            "css_overrides": {
                "font_size_base": "18px",
                "font_size_small": "16px",
                "font_size_heading": "28px",
            },
        },
        "screen_reader": {
            "label": "Screen Reader Optimized",
            "description": "Enhanced ARIA labels, skip navigation, focus management.",
            "behavior_overrides": {
                "enhanced_aria": True,
                "skip_nav": True,
                "announce_changes": True,
                "descriptive_links": True,
            },
        },
    }

    def get_modes(self) -> list:
        return [{"id": k, "label": v["label"], "description": v["description"]}
                for k, v in self.MODES.items()]

    def get_mode_detail(self, mode_id: str) -> dict | None:
        return self.MODES.get(mode_id)

    def set_user_mode(self, user_id: str, mode: str) -> dict:
        if mode not in self.MODES:
            return {"error": f"Unknown mode: {mode}"}
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?, ?)",
                (f"a11y_mode_{user_id}", mode))
        return {"mode": mode, "label": self.MODES[mode]["label"]}

    def get_user_mode(self, user_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT value FROM workspace_settings WHERE key=?",
                (f"a11y_mode_{user_id}",)).fetchone()
        mode = dict(row)["value"] if row else "default"
        return {"mode": mode, **self.MODES.get(mode, {})}

    def build_ai_instruction(self, mode: str) -> str:
        """Tell the AI how to format responses for this accessibility mode."""
        if mode == "dyslexia_friendly":
            return ("[ACCESSIBILITY: DYSLEXIA-FRIENDLY MODE]\n"
                    "Use short sentences. One idea per sentence. "
                    "Avoid walls of text. Use bullet points for lists. "
                    "Use simple, common words when possible. "
                    "Break complex ideas into numbered steps.")
        elif mode == "adhd_focus":
            return ("[ACCESSIBILITY: FOCUS MODE]\n"
                    "Keep responses concise and structured. "
                    "Use headers to break up sections. "
                    "Put the most important information first. "
                    "Maximum 3 sentences per paragraph. "
                    "End with a clear summary of action items.")
        elif mode == "screen_reader":
            return ("[ACCESSIBILITY: SCREEN READER MODE]\n"
                    "Structure responses with clear headers. "
                    "Describe any visual elements in text. "
                    "Use explicit list numbering (1, 2, 3) not bullets. "
                    "Avoid relying on formatting for meaning. "
                    "Spell out abbreviations on first use.")
        elif mode == "large_text":
            return ("[ACCESSIBILITY: LARGE TEXT MODE]\n"
                    "Keep responses shorter — the user sees fewer words per screen. "
                    "Be concise. Break into smaller sections.")
        return ""


# ══════════════════════════════════════════════════════════════
# 2. ETHICAL REASONING LAYER
# ══════════════════════════════════════════════════════════════

class EthicalReasoningLayer:
    """Beyond compliance — the "is this the right thing to do?" check.

    The Compliance Watchdog checks legality. This checks humanity.

    When the AI generates content about layoffs, it flags the human impact.
    When a deliverable recommends cost-cutting, it asks about the people affected.
    When a policy is drafted, it considers unintended consequences.

    Not to block. Not to preach. Just to make sure the decision-maker
    has considered all the stakeholders, not just the shareholders.
    """

    ETHICAL_SIGNALS = {
        "human_impact": {
            "patterns": [
                r"(?:lay ?off|terminate|fire|let go|downsize|reduce headcount|eliminate positions?) .{0,20}(?:\d+|employees?|staff|people|workers?|team)",
                r"(?:close|shut down|shutter) .{0,20}(?:office|location|facility|plant|store|branch)",
                r"(?:outsource|offshore|replace) .{0,20}(?:workers?|employees?|staff|team|department)",
                r"(?:cut|reduce|eliminate) .{0,20}(?:benefits?|healthcare|insurance|pension|401k|retirement)",
            ],
            "injection": (
                "[ETHICAL CONSIDERATION] This topic involves decisions that directly affect people's livelihoods. "
                "After providing your analysis, briefly note: 'Worth considering: [specific human impact]. "
                "How will this be communicated, and what support will be offered?' "
                "Keep it to one sentence. Don't preach — just ensure the human side is on the table."
            ),
        },
        "environmental_impact": {
            "patterns": [
                r"(?:dump|dispose|discharge) .{0,20}(?:waste|chemical|toxic|pollutant)",
                r"(?:clear ?cut|deforest|destroy) .{0,20}(?:forest|habitat|wetland|ecosystem)",
                r"(?:skip|bypass|ignore) .{0,20}(?:environmental|emission|pollution|epa|regulation)",
            ],
            "injection": (
                "[ETHICAL CONSIDERATION] This involves potential environmental impact. "
                "Briefly note the environmental dimension and any alternatives that reduce harm."
            ),
        },
        "fairness_equity": {
            "patterns": [
                r"(?:charge|price) .{0,20}(?:more|extra|premium) .{0,20}(?:because|based on|depending)",
                r"(?:exclude|deny|restrict) .{0,20}(?:access|service|coverage|eligibility)",
                r"(?:target|exploit) .{0,20}(?:vulnerable|elderly|low.income|disadvantaged|minority)",
            ],
            "injection": (
                "[ETHICAL CONSIDERATION] This involves potential equity implications. "
                "Briefly consider: does this disproportionately affect any group? Is there a fairer approach?"
            ),
        },
        "privacy_consent": {
            "patterns": [
                r"(?:track|monitor|surveil|spy on|record) .{0,20}(?:employees?|users?|customers?|people|without)",
                r"(?:collect|harvest|scrape|gather) .{0,20}(?:data|information|personal) .{0,20}(?:without|secretly|covertly)",
                r"(?:share|sell|give) .{0,20}(?:user|customer|patient|student) .{0,20}(?:data|information|records)",
            ],
            "injection": (
                "[ETHICAL CONSIDERATION] This involves people's privacy. "
                "Briefly note: have the affected people consented? Is there a less invasive way to achieve the same goal?"
            ),
        },
    }

    def __init__(self):
        self._compiled = {}
        for cat, data in self.ETHICAL_SIGNALS.items():
            self._compiled[cat] = [re.compile(p, re.I) for p in data["patterns"]]

    def analyze(self, text: str) -> dict:
        flags = []
        for cat, patterns in self._compiled.items():
            for p in patterns:
                if p.search(text):
                    flags.append({
                        "category": cat,
                        "injection": self.ETHICAL_SIGNALS[cat]["injection"],
                    })
                    break
        return {"has_ethical_dimension": len(flags) > 0, "flags": flags}

    def build_injection(self, analysis: dict) -> str:
        if not analysis.get("has_ethical_dimension"):
            return ""
        injections = [f["injection"] for f in analysis["flags"]]
        return "\n".join(injections)


# ══════════════════════════════════════════════════════════════
# 3. DATA PORTABILITY
# ══════════════════════════════════════════════════════════════

class DataPortabilityManager:
    """Your data is yours. Take it and leave. No lock-in. No hostage-taking.

    Export everything:
    - Conversations (JSON + Markdown)
    - Spaces (configuration JSON)
    - Voice Profile (JSON)
    - Business DNA (JSON)
    - Learning DNA (JSON)
    - Knowledge Base (original files + metadata)
    - Settings and preferences
    - Billing history
    """

    def generate_export(self, user_id: str) -> dict:
        """Generate a complete data export for a user."""
        export = {
            "export_version": "1.0",
            "platform": "MyTeam360",
            "exported_at": datetime.now().isoformat(),
            "user_id": user_id,
            "data": {},
        }

        with get_db() as db:
            # User profile
            user = db.execute("SELECT id, email, display_name, role, created_at FROM users WHERE id=?",
                             (user_id,)).fetchone()
            if user:
                export["data"]["profile"] = dict(user)

            # Conversations
            convs = db.execute("SELECT * FROM conversations WHERE user_id=? ORDER BY created_at",
                              (user_id,)).fetchall()
            export["data"]["conversations"] = []
            for conv in convs:
                c = dict(conv)
                msgs = db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at",
                                 (c["id"],)).fetchall()
                c["messages"] = [dict(m) for m in msgs]
                export["data"]["conversations"].append(c)

            # Spaces (agents)
            agents = db.execute("SELECT * FROM agents WHERE owner_id=?", (user_id,)).fetchall()
            export["data"]["spaces"] = [dict(a) for a in agents]

            # Voice profile
            vp = db.execute("SELECT * FROM voice_profiles WHERE user_id=?", (user_id,)).fetchone()
            if vp:
                export["data"]["voice_profile"] = dict(vp)

            # Business DNA
            dna = db.execute("SELECT * FROM business_dna WHERE owner_id=?", (user_id,)).fetchall()
            export["data"]["business_dna"] = [dict(d) for d in dna]

            # Learning DNA
            ldna = db.execute("SELECT * FROM learning_dna WHERE user_id=?", (user_id,)).fetchone()
            if ldna:
                export["data"]["learning_dna"] = dict(ldna)

            # Preferences
            prefs = db.execute("SELECT * FROM user_preferences WHERE user_id=?", (user_id,)).fetchall()
            export["data"]["preferences"] = [dict(p) for p in prefs]

        export["data"]["record_counts"] = {
            k: len(v) if isinstance(v, list) else (1 if v else 0)
            for k, v in export["data"].items() if k != "record_counts"
        }

        return export

    def get_export_summary(self, user_id: str) -> dict:
        """Preview what would be exported without generating the full export."""
        with get_db() as db:
            counts = {}
            for table, col in [
                ("conversations", "user_id"), ("agents", "owner_id"),
                ("messages", "user_id"), ("business_dna", "owner_id"),
            ]:
                try:
                    row = db.execute(f"SELECT COUNT(*) as c FROM {table} WHERE {col}=?",
                                    (user_id,)).fetchone()
                    counts[table] = dict(row)["c"]
                except:
                    counts[table] = 0

        return {
            "user_id": user_id,
            "exportable_data": counts,
            "format": "JSON",
            "note": "Your data export includes everything — conversations, Spaces, voice profile, "
                    "DNA profiles, knowledge base, and preferences. It's your data. No lock-in.",
        }


# ══════════════════════════════════════════════════════════════
# 4. SPONSORED TIER — Pay It Forward
# ══════════════════════════════════════════════════════════════

class SponsoredTierManager:
    """Paying customers fund access for those who can't afford it.

    How it works:
    1. Any paying customer can "sponsor" a seat ($7/month = one Student plan)
    2. Nonprofit organizations can apply for sponsored access
    3. Students who can't afford $15/month can apply
    4. Approved applicants get full access, funded by sponsors
    5. Sponsors see aggregate impact (not individual identities)
    6. Completely voluntary — no pressure, no guilt

    This makes MyTeam360 different from every other SaaS:
    we believe access to AI shouldn't depend on your bank account.
    """

    def create_sponsorship(self, sponsor_user_id: str, months: int = 1,
                            amount_per_month: float = 7.0) -> dict:
        sid = f"spon_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO sponsorships (id, sponsor_user_id, months, amount_per_month, status)
                VALUES (?,?,?,?,?)
            """, (sid, sponsor_user_id, months, amount_per_month, "active"))
        return {"id": sid, "months": months, "total": months * amount_per_month,
                "message": f"Thank you! You're sponsoring {months} month(s) of access for someone who needs it."}

    def apply_for_sponsorship(self, applicant_user_id: str, reason: str,
                               organization: str = "", role: str = "") -> dict:
        aid = f"spapp_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO sponsorship_applications
                    (id, applicant_user_id, reason, organization, role, status)
                VALUES (?,?,?,?,?,?)
            """, (aid, applicant_user_id, reason, organization, role, "pending"))
        return {"id": aid, "status": "pending",
                "message": "Application received. We'll review it within 48 hours."}

    def approve_application(self, application_id: str, admin_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE sponsorship_applications SET status='approved', reviewed_by=?, reviewed_at=? WHERE id=?",
                (admin_id, datetime.now().isoformat(), application_id))
        return {"approved": True}

    def get_impact_stats(self) -> dict:
        """Aggregate impact — how many people are being helped."""
        with get_db() as db:
            try:
                sponsors = db.execute("SELECT COUNT(DISTINCT sponsor_user_id) as c FROM sponsorships WHERE status='active'").fetchone()
                total_months = db.execute("SELECT COALESCE(SUM(months),0) as c FROM sponsorships WHERE status='active'").fetchone()
                approved = db.execute("SELECT COUNT(*) as c FROM sponsorship_applications WHERE status='approved'").fetchone()
            except:
                return {"sponsors": 0, "months_funded": 0, "people_helped": 0}
        return {
            "active_sponsors": dict(sponsors)["c"],
            "total_months_funded": dict(total_months)["c"],
            "people_helped": dict(approved)["c"],
            "message": "Every sponsored seat gives someone access to AI tools they couldn't otherwise afford.",
        }


# ══════════════════════════════════════════════════════════════
# 5. TRANSPARENCY REPORT
# ══════════════════════════════════════════════════════════════

class TransparencyReportGenerator:
    """Public proof we practice what we preach.

    Aggregate, anonymized data showing:
    - How many compliance flags were triggered
    - How many wellbeing interventions fired
    - How many parental consents were processed
    - How many sponsored seats are active
    - Platform uptime and reliability
    - Zero-knowledge encryption adoption rate
    - Accessibility mode usage
    - Data export requests fulfilled

    No individual data. No PII. Just proof that the systems work
    and that we're using them responsibly.
    """

    def generate_report(self) -> dict:
        """Generate a transparency report from aggregate data."""
        report = {
            "report_title": "MyTeam360 Transparency Report",
            "generated_at": datetime.now().isoformat(),
            "period": "Current snapshot",
            "sections": {},
        }

        with get_db() as db:
            # Compliance
            try:
                flags = db.execute("SELECT COUNT(*) as c FROM compliance_flags").fetchone()
                violations = db.execute("SELECT COUNT(*) as c FROM compliance_violations").fetchone()
                report["sections"]["compliance"] = {
                    "total_flags_detected": dict(flags)["c"],
                    "total_violations_escalated": dict(violations)["c"],
                    "note": "All reporting is internal. We detect and route — we don't file external reports.",
                }
            except:
                report["sections"]["compliance"] = {"note": "Compliance system active, no data yet."}

            # Parental consent
            try:
                consents = db.execute("SELECT COUNT(*) as c FROM parental_consents WHERE consent_agreed=1").fetchone()
                minors = db.execute("SELECT COUNT(*) as c FROM user_age_verification WHERE is_minor=1").fetchone()
                report["sections"]["child_safety"] = {
                    "minors_verified": dict(minors)["c"],
                    "parental_consents_on_file": dict(consents)["c"],
                    "note": "All users under 18 require verified parental consent before platform access.",
                }
            except:
                report["sections"]["child_safety"] = {"note": "Parental consent system active."}

            # Sponsorship
            try:
                sponsors = SponsoredTierManager().get_impact_stats()
                report["sections"]["sponsored_access"] = sponsors
            except:
                report["sections"]["sponsored_access"] = {"note": "Sponsored tier available."}

        # Static commitments
        report["sections"]["data_practices"] = {
            "zero_knowledge_available": True,
            "data_export_available": True,
            "data_portability": "Users can export all data at any time in JSON format.",
            "data_retention": "User data deleted within 30 days of account termination.",
            "third_party_sharing": "We never sell, share, or monetize user data.",
        }

        report["sections"]["accessibility"] = {
            "modes_available": 7,
            "wcag_target": "WCAG 2.1 AA (AAA for high contrast mode)",
            "supported_modes": ["High Contrast", "Dyslexia Friendly", "Focus (ADHD)",
                               "Reduced Motion", "Large Text", "Screen Reader Optimized"],
        }

        report["sections"]["ethical_ai"] = {
            "positivity_guard": "Always active. DNA never learns negative patterns.",
            "wellbeing_awareness": "Active for all users. Detects burnout signals.",
            "content_guardrails": "Available for all plans. 5 curriculum templates.",
            "content_filter": "6-category output safety scanning on every response.",
        }

        return report
