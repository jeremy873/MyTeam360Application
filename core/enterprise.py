# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Enterprise Features — The complete operational intelligence layer.

1. Action Item Tracker — Assignments with AI follow-up and escalation
2. Compliance Watchdog — Real-time conversation scanning for regulatory flags
3. Client Deliverables — Auto-generate polished reports from conversations
4. Delegation of Authority — Temporary authority transfer with audit trail
5. Risk Register — Auto-detect and track risks across all conversations
6. Policy Engine — Company rules enforced across every Space
7. Knowledge Handoff — Structured transfer when team members leave
"""

import json
import uuid
import re
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.enterprise")


# ══════════════════════════════════════════════════════════════
# 1. ACTION ITEM TRACKER WITH AI FOLLOW-UP
# ══════════════════════════════════════════════════════════════

class ActionItemTracker:
    """Track commitments made in conversations and Roundtables.
    AI follows up before deadlines and escalates when overdue."""

    def create_item(self, owner_id: str, title: str, assignee: str,
                    due_date: str = None, source_type: str = "manual",
                    source_id: str = "", priority: str = "medium",
                    description: str = "", tags: list = None) -> dict:
        aid = f"ai_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO action_items
                    (id, owner_id, title, assignee, due_date, source_type,
                     source_id, priority, description, tags, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (aid, owner_id, title, assignee, due_date, source_type,
                  source_id, priority, description, json.dumps(tags or []), "open"))
        return {"id": aid, "title": title, "assignee": assignee, "status": "open"}

    def get_item(self, aid: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM action_items WHERE id=?", (aid,)).fetchone()
        if not row: return None
        d = dict(row)
        d["tags"] = json.loads(d.get("tags", "[]") or "[]")
        return d

    def list_items(self, owner_id: str, assignee: str = None,
                   status: str = None, priority: str = None) -> list:
        with get_db() as db:
            sql = "SELECT * FROM action_items WHERE owner_id=?"
            params = [owner_id]
            if assignee:
                sql += " AND assignee=?"
                params.append(assignee)
            if status:
                sql += " AND status=?"
                params.append(status)
            if priority:
                sql += " AND priority=?"
                params.append(priority)
            sql += " ORDER BY due_date IS NULL, due_date, priority DESC"
            rows = db.execute(sql, params).fetchall()
        return [dict(r, tags=json.loads(r.get("tags", "[]") or "[]")) for r in rows]

    def update_item(self, aid: str, updates: dict) -> dict:
        safe = {"title", "assignee", "due_date", "priority", "description", "status", "tags"}
        filtered = {k: v for k, v in updates.items() if k in safe}
        if "tags" in filtered:
            filtered["tags"] = json.dumps(filtered["tags"])
        if "status" in filtered and filtered["status"] == "completed":
            filtered["completed_at"] = datetime.now().isoformat()
        filtered["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in filtered)
        vals = list(filtered.values()) + [aid]
        with get_db() as db:
            db.execute(f"UPDATE action_items SET {sets} WHERE id=?", vals)
        return self.get_item(aid)

    def get_overdue(self, owner_id: str) -> list:
        """Get items past their due date."""
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM action_items
                WHERE owner_id=? AND status='open' AND due_date IS NOT NULL AND due_date < ?
                ORDER BY due_date
            """, (owner_id, datetime.now().isoformat()[:10])).fetchall()
        return [dict(r) for r in rows]

    def get_due_soon(self, owner_id: str, days: int = 2) -> list:
        """Get items due within N days."""
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()[:10]
        today = datetime.now().isoformat()[:10]
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM action_items
                WHERE owner_id=? AND status='open' AND due_date IS NOT NULL
                AND due_date >= ? AND due_date <= ?
                ORDER BY due_date
            """, (owner_id, today, cutoff)).fetchall()
        return [dict(r) for r in rows]

    def get_dashboard(self, owner_id: str) -> dict:
        """Full action item dashboard."""
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) as c FROM action_items WHERE owner_id=?",
                              (owner_id,)).fetchone()
            open_count = db.execute("SELECT COUNT(*) as c FROM action_items WHERE owner_id=? AND status='open'",
                                   (owner_id,)).fetchone()
        return {
            "total": dict(total)["c"],
            "open": dict(open_count)["c"],
            "overdue": len(self.get_overdue(owner_id)),
            "due_soon": len(self.get_due_soon(owner_id)),
            "overdue_items": self.get_overdue(owner_id),
            "due_soon_items": self.get_due_soon(owner_id),
        }


# ══════════════════════════════════════════════════════════════
# 2. COMPLIANCE WATCHDOG
# ══════════════════════════════════════════════════════════════

class ComplianceWatchdog:
    """Scans conversations for regulatory and policy red flags."""

    DEFAULT_RULES = {
        "deception": {
            "patterns": [
                r"don['\u2019]t tell (?:the )?client", r"hide (?:this|that|it) from",
                r"off the record", r"just between us", r"nobody needs to know",
                r"cover (?:this|that|it) up", r"delete (?:the|those) (?:emails?|messages?|records?)",
            ],
            "severity": "critical",
            "label": "Potential deception or concealment",
        },
        "price_fixing": {
            "patterns": [
                r"agree on (?:a )?price", r"fix(?:ed|ing)? (?:the )?prices?",
                r"competitor['\u2019]?s? (?:pricing|prices|rates)",
                r"collude", r"price coordination",
            ],
            "severity": "critical",
            "label": "Potential antitrust / price-fixing language",
        },
        "discrimination": {
            "patterns": [
                r"(?:don['\u2019]t|never) hire (?:a |any )?(?:woman|women|man|men|old|young)",
                r"too old", r"wrong (?:race|gender|religion)",
            ],
            "severity": "critical",
            "label": "Potential discriminatory language",
        },
        "phi_exposure": {
            "patterns": [
                r"patient['\u2019]?s? (?:name|record|diagnosis|ssn|social)",
                r"medical record", r"health (?:information|data|record)",
                r"\b(?:HIPAA|PHI)\b",
            ],
            "severity": "high",
            "label": "Potential PHI / HIPAA-sensitive content",
        },
        "financial_risk": {
            "patterns": [
                r"guarantee(?:d|s|ing)? (?:returns?|profit|income)",
                r"insider (?:information|trading|tip)",
                r"material non-public",
            ],
            "severity": "high",
            "label": "Potential financial compliance issue",
        },
        "data_breach": {
            "patterns": [
                r"(?:send|share|email) (?:the |all )?(?:customer|client|user) (?:data|list|info)",
                r"export (?:all |the )?(?:contacts|users|clients)",
                r"(?:password|credential)s? (?:in |via )(?:email|slack|text|chat)",
            ],
            "severity": "high",
            "label": "Potential data handling violation",
        },
        "sexual_harassment": {
            "patterns": [
                r"(?:nice|great|hot) (?:body|legs|ass|figure|rack)",
                r"(?:hook up|sleep with|slept with) (?:a |the )?(?:coworker|colleague|intern|employee|boss|manager|subordinate)",
                r"(?:send|sent|show) (?:me |him |her )?(?:nudes?|nude (?:photo|pic))",
                r"quid pro quo", r"sexual favor",
                r"(?:grab|touch|grope|fondle|rub) (?:her|his|their)",
                r"(?:what are you wearing|come to my (?:room|hotel|office))",
                r"(?:dating|date|sleep with) (?:the |a )?(?:intern|subordinate|employee)",
            ],
            "severity": "critical",
            "label": "Potential sexual harassment — Title VII / hostile work environment",
        },
        "sexual_content": {
            "patterns": [
                r"(?:write|generate|create|draft) .{0,10}(?:erotic|sexual|explicit|pornographic|nsfw)",
                r"(?:sex (?:scene|story)|erotica|porn(?:ography)?|adult content|xxx)",
                r"(?:naked|topless|nude) (?:photo|image|picture|video)",
                r"only ?fans", r"escort service",
                r"(?:age of consent|underage|minor) .{0,20}(?:sex|relation|attract|date)",
            ],
            "severity": "critical",
            "label": "Sexual or explicit content — inappropriate for business platform",
        },
        "illegal_drugs": {
            "patterns": [
                r"(?:buy|sell|get|find|source|smuggle|distribute|deal) (?:me )?(?:drugs?|cocaine|heroin|fentanyl|meth|mdma|ecstasy|lsd|shrooms|crack|oxy(?:contin)?)",
                r"drug (?:dealer|deal|trafficking|supplier|connect|plug)",
                r"(?:cook|make|manufacture|produce|synthesize) (?:meth|drugs?|fentanyl)",
                r"(?:dark ?web|silk ?road) .{0,20}(?:buy|order|purchase|drugs?)",
                r"(?:launder|laundering) (?:money|cash|funds)",
            ],
            "severity": "critical",
            "label": "Illegal substance activity — controlled substance violation",
        },
        "illegal_activity": {
            "patterns": [
                r"(?:how to|let['\u2019]?s|plan to|going to|want to) (?:rob|steal|burglar|break into|hack into)",
                r"(?:forge|forging|counterfeit|counterfeiting) (?:documents?|checks?|money|currency|ids?|passport)",
                r"(?:identity theft|steal (?:someone|their|his|her) identity)",
                r"(?:bribe|bribery|kickback|payoff|pay off) (?:the |a )?(?:official|judge|inspector|politician|cop|officer)",
                r"(?:hit ?man|assassin|contract kill|murder for hire)",
                r"(?:human trafficking|traffic(?:king)? (?:people|persons|humans|women|children|minors))",
                r"(?:child (?:exploitation|abuse|pornography|porn))",
                r"(?:bomb|explosive|weapon) .{0,20}(?:make|build|construct|assemble|detonate)",
                r"(?:arson|set fire|burn down)",
                r"(?:extort|blackmail|ransom) .{0,20}(?:money|payment|bitcoin|crypto)",
            ],
            "severity": "critical",
            "label": "Potential illegal activity — criminal conduct",
        },
        "threats_violence": {
            "patterns": [
                r"(?:i['\u2019]?ll|going to|gonna|want to|plan to) (?:kill|hurt|shoot|stab|beat|attack|assault|harm)",
                r"(?:bring|have) (?:a |my )?(?:gun|weapon|knife) to (?:work|office|school|meeting)",
                r"(?:death threat|bomb threat|shoot up|blow up)",
                r"(?:they|you|he|she) deserve(?:s)? to (?:die|be (?:hurt|killed|shot))",
                r"(?:school shooting|workplace violence|mass (?:shooting|casualty))",
                r"(?:i['\u2019]?ll|going to) (?:make (?:them|you|him|her) pay|get (?:revenge|even))",
            ],
            "severity": "critical",
            "label": "Threat of violence — potential safety emergency",
        },
        "fraud_embezzlement": {
            "patterns": [
                r"(?:skim|siphon|divert|redirect) (?:money|funds|payments|revenue)",
                r"(?:fake|falsif|fabricat)(?:e|ed|ing) (?:the |an? )?(?:invoice|receipt|report|expense|record|signature)",
                r"(?:phantom|ghost|fictitious) (?:employee|vendor|invoice|company)",
                r"(?:cook|manipulate|alter|doctor) (?:the )?(?:books|financials|numbers|records|accounting)",
                r"(?:ponzi|pyramid) (?:scheme|scam)",
                r"(?:embezzl|misappropriat)(?:e|ed|ing|ement)",
                r"(?:wire fraud|tax (?:evasion|fraud)|insurance fraud|securities fraud)",
            ],
            "severity": "critical",
            "label": "Potential fraud or embezzlement activity",
        },
        "workplace_safety": {
            "patterns": [
                r"(?:skip|ignore|bypass|disable) (?:the )?(?:safety|osha|inspection|compliance|alarm|fire (?:code|exit))",
                r"(?:don['\u2019]t|no need to) (?:report|document|log|file) (?:the )?(?:injury|accident|incident|spill)",
                r"(?:unsafe|dangerous|hazardous) (?:condition|environment|practice|chemical)",
                r"(?:expired|missing|broken) (?:safety (?:equipment|gear)|fire extinguisher|first aid)",
            ],
            "severity": "high",
            "label": "Workplace safety concern — potential OSHA violation",
        },
        "child_safety": {
            "patterns": [
                r"(?:child|minor|underage|kid|teen) .{0,30}(?:explicit|sexual|nude|naked|porn|abuse|exploit)",
                r"(?:explicit|sexual|nude|naked|porn|abuse) .{0,30}(?:child|children|minor|underage|kid|teen)",
                r"(?:groom(?:ing)?|lure|entice) .{0,20}(?:child|minor|underage|kid|teen)",
                r"(?:csam|cp|child porn)",
            ],
            "severity": "critical",
            "label": "Child safety violation — escalate to Compliance Officer immediately",
        },
        "fcpa": {
            "patterns": [
                r"(?:pay|paid|give|gave|offer|gift|donate) .{0,30}(?:foreign|government|public) (?:official|minister|officer|regulator|inspector|customs)",
                r"(?:facilitat(?:e|ion)|grease|speed|expedit(?:e|ing)) (?:payment|money|fee|bribe)",
                r"(?:agent|intermediary|consultant|fixer) .{0,30}(?:foreign|government|overseas|official)",
                r"(?:slush fund|off.?book|secret (?:payment|account|fund))",
                r"(?:kickback|commission|fee) .{0,20}(?:government|official|minister|customs|permit)",
                r"(?:entertain|hospitality|luxury|gift) .{0,20}(?:official|minister|regulator|inspector)",
                r"(?:third.?party|intermediary|shell company) .{0,20}(?:payment|transfer|route|funnel)",
            ],
            "severity": "critical",
            "label": "Potential FCPA violation — Foreign Corrupt Practices Act (15 U.S.C. § 78dd)",
        },
        "uk_bribery_act": {
            "patterns": [
                r"(?:bribe|bribery|corrupt payment|improper (?:payment|advantage|benefit))",
                r"(?:offer|promise|give) .{0,20}(?:advantage|benefit|inducement|reward) .{0,20}(?:to (?:influence|obtain|secure|win))",
                r"(?:fail(?:ure|ed|ing)? to prevent|adequate procedures|corporate hospitality) .{0,20}(?:brib)",
                r"(?:private sector|commercial) .{0,15}(?:brib|corrupt|kickback)",
                r"(?:foreign|public) (?:official|officer) .{0,20}(?:payment|gift|advantage|benefit|induce)",
            ],
            "severity": "critical",
            "label": "Potential UK Bribery Act 2010 violation — Sections 1, 2, 6, or 7",
        },
        "sanctions_export": {
            "patterns": [
                r"(?:sanction(?:ed|s)?|embargo(?:ed)?|restricted|denied) .{0,20}(?:country|entity|person|party|list)",
                r"(?:ofac|sdn list|bis|ear|itar)",
                r"(?:export|ship|send|transfer) .{0,20}(?:iran|north korea|cuba|syria|russia|crimea)",
                r"(?:dual.?use|controlled (?:goods|technology|item)|export (?:license|control))",
                r"(?:circumvent|evade|avoid) .{0,20}(?:sanction|embargo|restriction|export control)",
            ],
            "severity": "critical",
            "label": "Potential sanctions or export control violation — escalate to Compliance Officer",
        },
        "money_laundering": {
            "patterns": [
                r"(?:launder|laundering|wash|clean) .{0,15}(?:money|cash|funds|proceeds)",
                r"(?:structure|structuring|smurfing) .{0,15}(?:deposit|transaction|payment|transfer)",
                r"(?:shell (?:company|corporation|entity)|nominee (?:account|director))",
                r"(?:beneficial (?:owner|ownership)|hide (?:the )?(?:source|origin)) .{0,20}(?:funds|money|proceeds)",
                r"(?:suspicious (?:activity|transaction)|sar|ctr|currency transaction report)",
                r"(?:under|below) .{0,10}(?:\$10,?000|reporting (?:threshold|limit))",
            ],
            "severity": "critical",
            "label": "Potential money laundering — escalate to Compliance Officer",
        },
    }

    def __init__(self):
        self.rules = dict(self.DEFAULT_RULES)
        self._compiled = {}
        self._compile_rules()
        self._load_custom_rules()

    def _compile_rules(self):
        for name, rule in self.rules.items():
            self._compiled[name] = [re.compile(p, re.I) for p in rule["patterns"]]

    def _load_custom_rules(self):
        """Load company-defined custom rules from database."""
        try:
            with get_db() as db:
                rows = db.execute(
                    "SELECT * FROM compliance_custom_rules WHERE enabled=1"
                ).fetchall()
            for row in rows:
                r = dict(row)
                patterns = json.loads(r.get("patterns", "[]") or "[]")
                if patterns:
                    self.rules[r["rule_name"]] = {
                        "patterns": patterns,
                        "severity": r.get("severity", "medium"),
                        "label": r.get("label", r["rule_name"]),
                        "custom": True,
                        "created_by": r.get("owner_id", ""),
                    }
                    self._compiled[r["rule_name"]] = [re.compile(p, re.I) for p in patterns]
        except Exception:
            pass  # table may not exist yet on first run

    def add_rule(self, name: str, patterns: list, severity: str = "medium",
                 label: str = "", owner_id: str = "") -> dict:
        """Add a custom rule — persisted to database."""
        self.rules[name] = {"patterns": patterns, "severity": severity,
                            "label": label or name, "custom": True}
        self._compiled[name] = [re.compile(p, re.I) for p in patterns]
        # Persist
        rid = f"cr_{uuid.uuid4().hex[:12]}"
        try:
            with get_db() as db:
                db.execute("""
                    INSERT INTO compliance_custom_rules
                        (id, owner_id, rule_name, patterns, severity, label, enabled)
                    VALUES (?,?,?,?,?,?,1)
                """, (rid, owner_id, name, json.dumps(patterns), severity, label or name))
        except Exception:
            pass
        return {"id": rid, "rule": name, "patterns": len(patterns)}

    def remove_custom_rule(self, rule_name: str) -> bool:
        """Remove a custom rule."""
        if rule_name in self.rules and self.rules[rule_name].get("custom"):
            del self.rules[rule_name]
            del self._compiled[rule_name]
            with get_db() as db:
                db.execute("DELETE FROM compliance_custom_rules WHERE rule_name=?", (rule_name,))
            return True
        return False

    def list_custom_rules(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM compliance_custom_rules WHERE owner_id=? ORDER BY rule_name",
                (owner_id,)).fetchall()
        return [dict(r, patterns=json.loads(r.get("patterns", "[]") or "[]")) for r in rows]

    def scan_text(self, text: str, context: str = "") -> dict:
        """Scan text for compliance flags."""
        flags = []
        for name, compiled_patterns in self._compiled.items():
            rule = self.rules[name]
            for pattern in compiled_patterns:
                matches = pattern.findall(text)
                if matches:
                    flags.append({
                        "rule": name,
                        "severity": rule["severity"],
                        "label": rule["label"],
                        "matched": matches[0] if matches else "",
                        "context": context,
                    })
                    break  # one match per rule is enough

        return {
            "clean": len(flags) == 0,
            "flags": flags,
            "critical_count": sum(1 for f in flags if f["severity"] == "critical"),
            "high_count": sum(1 for f in flags if f["severity"] == "high"),
        }

    def log_flag(self, owner_id: str, flag_data: dict, source_type: str = "",
                 source_id: str = "") -> dict:
        """Log a compliance flag to the database."""
        fid = f"cf_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO compliance_flags
                    (id, owner_id, rule_name, severity, label, matched_text,
                     source_type, source_id, status)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (fid, owner_id, flag_data.get("rule", ""),
                  flag_data.get("severity", ""), flag_data.get("label", ""),
                  flag_data.get("matched", ""), source_type, source_id, "open"))
        return {"flag_id": fid, "severity": flag_data.get("severity")}

    def get_flags(self, owner_id: str, status: str = None,
                  severity: str = None) -> list:
        with get_db() as db:
            sql = "SELECT * FROM compliance_flags WHERE owner_id=?"
            params = [owner_id]
            if status:
                sql += " AND status=?"
                params.append(status)
            if severity:
                sql += " AND severity=?"
                params.append(severity)
            sql += " ORDER BY created_at DESC"
            rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def resolve_flag(self, fid: str, resolution: str = "") -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE compliance_flags SET status='resolved', resolution=?, resolved_at=? WHERE id=?",
                (resolution, datetime.now().isoformat(), fid))
        return {"flag_id": fid, "status": "resolved"}

    def get_rules(self) -> dict:
        return {k: {"severity": v["severity"], "label": v["label"],
                     "pattern_count": len(v["patterns"]),
                     "custom": v.get("custom", False)}
                for k, v in self.rules.items()}


# ══════════════════════════════════════════════════════════════
# 2b. COMPLIANCE ESCALATION PIPELINE
# ══════════════════════════════════════════════════════════════

class ComplianceEscalation:
    """Routes compliance violations to the right people INTERNALLY.

    Escalation tiers:
      Tier 1 (Medium)  → Logged silently. Visible on compliance dashboard.
      Tier 2 (High)    → Notify compliance officer + team admin.
      Tier 3 (Critical)→ Notify compliance officer + all admins + flag the message.

    ALL reporting is internal only. MyTeam360 does not file external reports,
    contact authorities, or make determinations about legal obligations.
    The designated Compliance Officer decides what external action, if any,
    is appropriate based on their organization's policies and legal counsel.

    Reports go to:
      1. Internal compliance dashboard (always)
      2. Designated Compliance Officer (configurable)
      3. Team admin notification queue
      4. Incident report (auto-generated, exportable to .docx for internal use)
    """

    def __init__(self, watchdog: ComplianceWatchdog = None):
        self.watchdog = watchdog

    def process_violation(self, owner_id: str, flag_data: dict,
                          source_type: str = "", source_id: str = "",
                          user_id: str = "", user_name: str = "") -> dict:
        """Process a compliance flag through the INTERNAL escalation pipeline.
        All reporting stays inside the organization."""
        severity = flag_data.get("severity", "medium")
        rule = flag_data.get("rule", "")
        label = flag_data.get("label", "")

        # Determine tier (internal only — 3 tiers)
        if severity == "critical":
            tier = 3
        elif severity == "high":
            tier = 2
        else:
            tier = 1

        # Log to database
        vid = f"cv_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO compliance_violations
                    (id, owner_id, rule_name, severity, tier, label,
                     matched_text, source_type, source_id, user_id, user_name,
                     status, requires_external_report)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (vid, owner_id, rule, severity, tier, label,
                  flag_data.get("matched", ""), source_type, source_id,
                  user_id, user_name, "open", 0))

        result = {
            "violation_id": vid,
            "tier": tier,
            "severity": severity,
            "rule": rule,
            "label": label,
            "actions_taken": [],
            "notifications": [],
        }

        # Tier 1: Dashboard only
        result["actions_taken"].append("Logged to internal compliance dashboard")

        # Tier 2: Notify compliance officer + admin
        if tier >= 2:
            officer = self._get_compliance_officer(owner_id)
            if officer:
                result["notifications"].append({
                    "recipient": officer.get("name", "Compliance Officer"),
                    "type": "compliance_alert",
                    "message": f"[{severity.upper()}] {label}",
                })
                result["actions_taken"].append("Compliance officer notified internally")

        # Tier 3: Notify all admins + flag for review
        if tier >= 3:
            admins = self._get_admins(owner_id)
            for admin in admins:
                result["notifications"].append({
                    "recipient": admin.get("display_name", "Admin"),
                    "type": "critical_compliance_alert",
                    "message": f"[CRITICAL] {label} — Requires immediate internal review",
                })
            result["actions_taken"].append("All administrators notified internally")
            result["actions_taken"].append("Message flagged for internal review")
            result["actions_taken"].append("Incident report available for export")

        return result

    def get_violations(self, owner_id: str, status: str = None,
                       tier: int = None, limit: int = 100) -> list:
        with get_db() as db:
            sql = "SELECT * FROM compliance_violations WHERE owner_id=?"
            params = [owner_id]
            if status:
                sql += " AND status=?"
                params.append(status)
            if tier:
                sql += " AND tier=?"
                params.append(tier)
            sql += " ORDER BY tier DESC, created_at DESC LIMIT ?"
            params.append(limit)
            rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def resolve_violation(self, vid: str, resolution: str,
                          resolved_by: str = "") -> dict:
        with get_db() as db:
            db.execute("""
                UPDATE compliance_violations
                SET status='resolved', resolution=?, resolved_by=?, resolved_at=?
                WHERE id=?
            """, (resolution, resolved_by, datetime.now().isoformat(), vid))
            row = db.execute("SELECT * FROM compliance_violations WHERE id=?", (vid,)).fetchone()
        return dict(row) if row else {}

    def get_compliance_dashboard(self, owner_id: str) -> dict:
        """Internal compliance overview for the Compliance Officer."""
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) as c FROM compliance_violations WHERE owner_id=?",
                              (owner_id,)).fetchone()
            open_count = db.execute("SELECT COUNT(*) as c FROM compliance_violations WHERE owner_id=? AND status='open'",
                                   (owner_id,)).fetchone()
            critical = db.execute("SELECT COUNT(*) as c FROM compliance_violations WHERE owner_id=? AND status='open' AND tier=3",
                                 (owner_id,)).fetchone()
            by_rule = db.execute("""
                SELECT rule_name, COUNT(*) as count FROM compliance_violations
                WHERE owner_id=? AND status='open' GROUP BY rule_name ORDER BY count DESC
            """, (owner_id,)).fetchall()
            recent = db.execute("""
                SELECT * FROM compliance_violations WHERE owner_id=? AND status='open'
                ORDER BY tier DESC, created_at DESC LIMIT 10
            """, (owner_id,)).fetchall()
        return {
            "total_violations": dict(total)["c"],
            "open_violations": dict(open_count)["c"],
            "critical_open": dict(critical)["c"],
            "by_rule": [dict(r) for r in by_rule],
            "recent_open": [dict(r) for r in recent],
            "note": "All reporting is internal. Consult legal counsel for any external reporting obligations.",
        }

    def set_compliance_officer(self, owner_id: str, officer_user_id: str,
                               officer_name: str, officer_email: str) -> dict:
        """Designate who receives compliance notifications."""
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO branding (key, value) VALUES ('compliance_officer_id', ?)",
                (officer_user_id,))
            db.execute(
                "INSERT OR REPLACE INTO branding (key, value) VALUES ('compliance_officer_name', ?)",
                (officer_name,))
            db.execute(
                "INSERT OR REPLACE INTO branding (key, value) VALUES ('compliance_officer_email', ?)",
                (officer_email,))
        return {"officer": officer_name, "email": officer_email}

    def get_compliance_officer(self, owner_id: str) -> dict:
        return self._get_compliance_officer(owner_id)

    def _get_compliance_officer(self, owner_id: str) -> dict:
        with get_db() as db:
            rows = db.execute(
                "SELECT key, value FROM branding WHERE key LIKE 'compliance_officer_%'"
            ).fetchall()
        d = {r["key"]: r["value"] for r in rows}
        if not d: return {}
        return {
            "id": d.get("compliance_officer_id", ""),
            "name": d.get("compliance_officer_name", ""),
            "email": d.get("compliance_officer_email", ""),
        }

    def _get_admins(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT id, display_name, email FROM users WHERE role IN ('owner','admin')"
            ).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# 3. CLIENT DELIVERABLES
# ══════════════════════════════════════════════════════════════

class DeliverableGenerator:
    """Turn a conversation into a polished client-ready document."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    STYLES = {
        "report": "formal business report with executive summary, findings, and recommendations",
        "proposal": "business proposal with scope, timeline, pricing, and terms",
        "brief": "concise strategic brief (1-2 pages) with key insights and next steps",
        "presentation_notes": "presentation talking points organized by slide/section",
        "memo": "internal memo format with subject, background, analysis, and recommendation",
        "sow": "statement of work with deliverables, timeline, acceptance criteria",
    }

    def generate(self, owner_id: str, conversation_id: str,
                 style: str = "report", client_name: str = "",
                 additional_instructions: str = "") -> dict:
        """Generate a client deliverable from a conversation."""
        with get_db() as db:
            msgs = db.execute(
                "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at",
                (conversation_id,)).fetchall()
            conv = db.execute("SELECT * FROM conversations WHERE id=?",
                             (conversation_id,)).fetchone()

        if not msgs:
            return {"error": "No messages found"}

        discussion = "\n".join(
            f"{'Client' if m['role']=='user' else 'Advisor'}: {m['content']}" for m in msgs)

        style_desc = self.STYLES.get(style, self.STYLES["report"])
        client_line = f"Client: {client_name}\n" if client_name else ""

        prompt = (
            f"Transform this conversation into a professional {style_desc}.\n\n"
            f"Requirements:\n"
            f"- Write as if this is a deliverable from a consulting firm to the client\n"
            f"- Use professional language, not conversational\n"
            f"- Include section headings\n"
            f"- Be specific with data points and recommendations\n"
            f"- Do NOT reference the conversation — write as original analysis\n"
            f"- Do NOT include 'Based on our discussion' or similar phrases\n"
            f"{client_line}"
            f"{additional_instructions}\n\n"
            f"Source conversation:\n{discussion[:8000]}"
        )

        agent_id = dict(conv).get("agent_id") if conv else None
        deliverable_text = ""
        if self.agents and agent_id:
            result = self.agents.run_agent(agent_id, prompt, user_id=owner_id)
            deliverable_text = result.get("text", "")

        did = f"del_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO deliverables
                    (id, owner_id, conversation_id, style, client_name, content, status)
                VALUES (?,?,?,?,?,?,?)
            """, (did, owner_id, conversation_id, style, client_name,
                  deliverable_text, "draft"))

        return {
            "id": did, "style": style, "client_name": client_name,
            "content": deliverable_text, "status": "draft",
        }

    def list_deliverables(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT id, conversation_id, style, client_name, status, created_at FROM deliverables WHERE owner_id=? ORDER BY created_at DESC",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_deliverable(self, did: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM deliverables WHERE id=?", (did,)).fetchone()
        return dict(row) if row else None

    def get_styles(self) -> dict:
        return dict(self.STYLES)


# ══════════════════════════════════════════════════════════════
# 4. DELEGATION OF AUTHORITY
# ══════════════════════════════════════════════════════════════

class DelegationOfAuthority:
    """Formal authority transfer with time limits and audit trail."""

    def create_delegation(self, delegator_id: str, delegate_id: str,
                          scope: str = "all", expires_at: str = None,
                          reason: str = "") -> dict:
        did = f"doa_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            # Get names
            delegator = db.execute("SELECT display_name FROM users WHERE id=?",
                                  (delegator_id,)).fetchone()
            delegate = db.execute("SELECT display_name FROM users WHERE id=?",
                                 (delegate_id,)).fetchone()
            db.execute("""
                INSERT INTO authority_delegations
                    (id, delegator_id, delegator_name, delegate_id, delegate_name,
                     scope, expires_at, reason, status)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (did, delegator_id,
                  dict(delegator)["display_name"] if delegator else "",
                  delegate_id,
                  dict(delegate)["display_name"] if delegate else "",
                  scope, expires_at, reason, "active"))
        return {"id": did, "status": "active", "scope": scope}

    def revoke_delegation(self, did: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE authority_delegations SET status='revoked', revoked_at=? WHERE id=?",
                (datetime.now().isoformat(), did))
        return {"id": did, "status": "revoked"}

    def get_active_delegations(self, user_id: str) -> dict:
        """What authority has been delegated TO and FROM this user."""
        now = datetime.now().isoformat()
        with get_db() as db:
            delegated_to = db.execute("""
                SELECT * FROM authority_delegations
                WHERE delegate_id=? AND status='active'
                AND (expires_at IS NULL OR expires_at > ?)
            """, (user_id, now)).fetchall()
            delegated_from = db.execute("""
                SELECT * FROM authority_delegations
                WHERE delegator_id=? AND status='active'
                AND (expires_at IS NULL OR expires_at > ?)
            """, (user_id, now)).fetchall()
        return {
            "delegated_to_me": [dict(r) for r in delegated_to],
            "delegated_from_me": [dict(r) for r in delegated_from],
        }

    def check_authority(self, user_id: str, scope: str = "all") -> bool:
        """Check if user has delegated authority for a scope."""
        now = datetime.now().isoformat()
        with get_db() as db:
            row = db.execute("""
                SELECT id FROM authority_delegations
                WHERE delegate_id=? AND status='active'
                AND (scope='all' OR scope=?)
                AND (expires_at IS NULL OR expires_at > ?)
                LIMIT 1
            """, (user_id, scope, now)).fetchone()
        return row is not None


# ══════════════════════════════════════════════════════════════
# 5. RISK REGISTER
# ══════════════════════════════════════════════════════════════

class RiskRegister:
    """Track and manage organizational risks detected across conversations."""

    RISK_PATTERNS = {
        "supply_chain": [r"supplier (?:delay|issue|problem|risk)", r"supply chain",
                         r"vendor (?:risk|issue|problem)", r"shipping delay"],
        "legal": [r"(?:get |be )?sued", r"lawsuit", r"legal (?:risk|action|liability)",
                  r"non-?compliance", r"regulatory"],
        "financial": [r"cash ?flow (?:issue|problem|risk)", r"budget (?:overrun|cut)",
                      r"revenue (?:decline|drop|risk)", r"cost overrun"],
        "operational": [r"single point of failure", r"bus factor", r"key person risk",
                        r"system (?:outage|failure|down)"],
        "reputational": [r"bad (?:press|review|publicity)", r"reputation (?:risk|damage)",
                         r"public backlash", r"social media (?:crisis|storm)"],
        "security": [r"(?:data )?breach", r"hack(?:ed|ing)?", r"vulnerability",
                     r"unauthorized access", r"phishing"],
    }

    def __init__(self):
        self._compiled = {}
        for cat, patterns in self.RISK_PATTERNS.items():
            self._compiled[cat] = [re.compile(p, re.I) for p in patterns]

    def scan_for_risks(self, text: str) -> list:
        """Scan text for risk mentions."""
        found = []
        for category, patterns in self._compiled.items():
            for pat in patterns:
                if pat.search(text):
                    found.append({"category": category, "matched": pat.pattern})
                    break
        return found

    def create_risk(self, owner_id: str, title: str, category: str,
                    description: str = "", severity: str = "medium",
                    likelihood: str = "medium", mitigation: str = "",
                    owner_name: str = "", source_id: str = "") -> dict:
        rid = f"risk_{uuid.uuid4().hex[:12]}"
        score = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        risk_score = score.get(severity, 2) * score.get(likelihood, 2)
        with get_db() as db:
            db.execute("""
                INSERT INTO risk_register
                    (id, owner_id, title, category, description, severity,
                     likelihood, risk_score, mitigation, risk_owner, source_id, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (rid, owner_id, title, category, description, severity,
                  likelihood, risk_score, mitigation, owner_name, source_id, "open"))
        return {"id": rid, "title": title, "risk_score": risk_score}

    def list_risks(self, owner_id: str, status: str = None,
                   category: str = None) -> list:
        with get_db() as db:
            sql = "SELECT * FROM risk_register WHERE owner_id=?"
            params = [owner_id]
            if status:
                sql += " AND status=?"
                params.append(status)
            if category:
                sql += " AND category=?"
                params.append(category)
            sql += " ORDER BY risk_score DESC, created_at DESC"
            rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def update_risk(self, rid: str, updates: dict) -> dict:
        safe = {"title", "description", "severity", "likelihood", "mitigation",
                "risk_owner", "status", "category"}
        filtered = {k: v for k, v in updates.items() if k in safe}
        if "severity" in filtered or "likelihood" in filtered:
            score = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            s = score.get(filtered.get("severity", "medium"), 2)
            l = score.get(filtered.get("likelihood", "medium"), 2)
            filtered["risk_score"] = s * l
        filtered["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in filtered)
        vals = list(filtered.values()) + [rid]
        with get_db() as db:
            db.execute(f"UPDATE risk_register SET {sets} WHERE id=?", vals)
            row = db.execute("SELECT * FROM risk_register WHERE id=?", (rid,)).fetchone()
        return dict(row) if row else {}

    def get_risk_matrix(self, owner_id: str) -> dict:
        """Risk heat map data."""
        risks = self.list_risks(owner_id, status="open")
        matrix = {}
        for r in risks:
            key = f"{r.get('likelihood','medium')}_{r.get('severity','medium')}"
            matrix.setdefault(key, []).append(r["title"])
        return {"matrix": matrix, "total_open": len(risks),
                "critical": sum(1 for r in risks if r.get("severity") == "critical")}


# ══════════════════════════════════════════════════════════════
# 6. POLICY ENGINE
# ══════════════════════════════════════════════════════════════

class PolicyEngine:
    """Company policies enforced across every Space."""

    def create_policy(self, owner_id: str, name: str, rule: str,
                      category: str = "general", enforcement: str = "warn",
                      applies_to: str = "all") -> dict:
        """Create a policy rule.
        enforcement: 'warn' (flag), 'block' (prevent), 'inject' (add to prompts)
        applies_to: 'all', 'agents', 'humans', or specific agent_id
        """
        pid = f"pol_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO policies_v2
                    (id, owner_id, name, rule, category, enforcement, applies_to, enabled)
                VALUES (?,?,?,?,?,?,?,?)
            """, (pid, owner_id, name, rule, category, enforcement, applies_to, 1))
        return {"id": pid, "name": name, "enforcement": enforcement}

    def list_policies(self, owner_id: str, category: str = None,
                      enabled_only: bool = True) -> list:
        with get_db() as db:
            sql = "SELECT * FROM policies_v2 WHERE owner_id=?"
            params = [owner_id]
            if enabled_only:
                sql += " AND enabled=1"
            if category:
                sql += " AND category=?"
                params.append(category)
            sql += " ORDER BY category, name"
            rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def update_policy(self, pid: str, updates: dict) -> dict:
        safe = {"name", "rule", "category", "enforcement", "applies_to", "enabled"}
        filtered = {k: v for k, v in updates.items() if k in safe}
        filtered["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in filtered)
        vals = list(filtered.values()) + [pid]
        with get_db() as db:
            db.execute(f"UPDATE policies_v2 SET {sets} WHERE id=?", vals)
            row = db.execute("SELECT * FROM policies_v2 WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else {}

    def delete_policy(self, pid: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM policies_v2 WHERE id=?", (pid,)).rowcount > 0

    def build_policy_injection(self, owner_id: str, agent_id: str = None) -> str:
        """Build policy instructions for system prompt injection."""
        policies = self.list_policies(owner_id)
        inject_policies = [p for p in policies if p.get("enforcement") == "inject"
                          and p.get("applies_to") in ("all", "agents", agent_id)]
        if not inject_policies:
            return ""
        parts = ["[COMPANY POLICIES — You MUST follow these rules]"]
        for p in inject_policies:
            parts.append(f"• {p['name']}: {p['rule']}")
        return "\n".join(parts)

    def check_compliance(self, owner_id: str, text: str,
                         agent_id: str = None) -> dict:
        """Check if text violates any policies."""
        policies = self.list_policies(owner_id)
        violations = []
        for p in policies:
            if p.get("applies_to") not in ("all", agent_id, "humans"):
                continue
            rule_lower = p["rule"].lower()
            text_lower = text.lower()
            # Extract key phrases from the rule for matching
            if "never" in rule_lower:
                forbidden = rule_lower.split("never")[-1].strip().split(".")[0]
                if forbidden and any(word in text_lower for word in forbidden.split() if len(word) > 3):
                    violations.append({"policy": p["name"], "rule": p["rule"],
                                      "enforcement": p["enforcement"]})
            elif "always" in rule_lower:
                required = rule_lower.split("always")[-1].strip().split(".")[0]
                if required and not any(word in text_lower for word in required.split() if len(word) > 3):
                    violations.append({"policy": p["name"], "rule": p["rule"],
                                      "enforcement": p["enforcement"]})
        blocked = any(v["enforcement"] == "block" for v in violations)
        return {"compliant": len(violations) == 0, "violations": violations, "blocked": blocked}


# ══════════════════════════════════════════════════════════════
# 7. KNOWLEDGE HANDOFF
# ══════════════════════════════════════════════════════════════

class KnowledgeHandoff:
    """Package a departing team member's knowledge for their replacement."""

    def generate_handoff(self, owner_id: str, departing_user_id: str,
                         departing_name: str) -> dict:
        """Generate a structured knowledge transfer package."""
        with get_db() as db:
            # Their conversations
            convs = db.execute("""
                SELECT c.id, c.title, c.agent_id, c.created_at,
                    (SELECT COUNT(*) FROM messages WHERE conversation_id=c.id) as msg_count
                FROM conversations c WHERE c.user_id=?
                ORDER BY c.updated_at DESC LIMIT 50
            """, (departing_user_id,)).fetchall()

            # Their decisions
            decisions = db.execute("""
                SELECT * FROM decisions WHERE owner_id=?
                ORDER BY created_at DESC LIMIT 30
            """, (departing_user_id,)).fetchall()

            # Their action items
            actions = db.execute("""
                SELECT * FROM action_items
                WHERE (owner_id=? OR assignee=?) AND status='open'
                ORDER BY due_date IS NULL, due_date
            """, (departing_user_id, departing_name)).fetchall()

            # Their business DNA contributions
            dna = db.execute("""
                SELECT * FROM business_dna WHERE owner_id=?
                ORDER BY times_referenced DESC LIMIT 20
            """, (departing_user_id,)).fetchall()

            # Spaces they created
            agents = db.execute("""
                SELECT id, name, description, instructions, run_count
                FROM agents WHERE owner_id=?
                ORDER BY run_count DESC
            """, (departing_user_id,)).fetchall()

        handoff = {
            "id": f"ho_{uuid.uuid4().hex[:12]}",
            "departing_user": departing_name,
            "departing_user_id": departing_user_id,
            "generated_at": datetime.now().isoformat(),
            "sections": {
                "recent_conversations": {
                    "count": len(convs),
                    "items": [dict(c) for c in convs[:20]],
                },
                "open_action_items": {
                    "count": len(actions),
                    "items": [dict(a) for a in actions],
                },
                "key_decisions": {
                    "count": len(decisions),
                    "items": [dict(d) for d in decisions[:15]],
                },
                "business_knowledge": {
                    "count": len(dna),
                    "items": [dict(d) for d in dna],
                },
                "spaces_created": {
                    "count": len(agents),
                    "items": [dict(a) for a in agents],
                },
            },
        }

        # Save to records
        with get_db() as db:
            db.execute("""
                INSERT INTO corporate_records
                    (id, owner_id, record_type, title, content, tags)
                VALUES (?,?,?,?,?,?)
            """, (handoff["id"], owner_id, "personnel",
                  f"Knowledge Handoff — {departing_name}",
                  json.dumps(handoff, default=str),
                  json.dumps(["handoff", "knowledge_transfer", departing_name])))

        return handoff
