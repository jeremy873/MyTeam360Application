# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Business Intelligence + Remaining UX Gaps

BUSINESS INTELLIGENCE:
  1. Win/Loss Analysis — why deals close or don't
  2. Client Health Score — green/yellow/red per contact
  3. Revenue Forecasting — pipeline-weighted projections
  4. Time-to-Close Tracking — average deal velocity
  5. Activity Scoring — engagement-based deal prediction

UX GAPS:
  6. Undo System — 30-second undo window for destructive actions
  7. SMS/Text Log — manual capture of texts (we never touch their phone)
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from .database import get_db

logger = logging.getLogger("MyTeam360.business_intel")


# ══════════════════════════════════════════════════════════════
# 1. WIN / LOSS ANALYSIS
# ══════════════════════════════════════════════════════════════

class WinLossAnalyzer:
    """Analyze why deals close or don't."""

    LOSS_REASONS = [
        "price_too_high", "went_with_competitor", "no_budget", "timing_wrong",
        "no_decision_made", "lost_contact", "requirements_changed",
        "poor_fit", "internal_politics", "other",
    ]

    def log_outcome(self, deal_id: str, outcome: str, reason: str = "",
                     competitor: str = "", notes: str = "",
                     feedback: str = "") -> dict:
        """Log why a deal was won or lost."""
        oid = f"wl_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO win_loss_log
                    (id, deal_id, outcome, reason, competitor, notes, feedback)
                VALUES (?,?,?,?,?,?,?)
            """, (oid, deal_id, outcome, reason, competitor, notes, feedback))
        return {"logged": True, "id": oid}

    def get_analysis(self, owner_id: str, period_days: int = 90) -> dict:
        """Full win/loss analysis for a time period."""
        cutoff = (datetime.now() - timedelta(days=period_days)).isoformat()
        with get_db() as db:
            # Win rate
            total = db.execute(
                "SELECT COUNT(*) as c FROM crm_deals WHERE owner_id=? AND status!='open' AND updated_at>=?",
                (owner_id, cutoff)).fetchone()
            won = db.execute(
                "SELECT COUNT(*) as c, COALESCE(SUM(value),0) as v FROM crm_deals "
                "WHERE owner_id=? AND stage='closed_won' AND updated_at>=?",
                (owner_id, cutoff)).fetchone()
            lost = db.execute(
                "SELECT COUNT(*) as c, COALESCE(SUM(value),0) as v FROM crm_deals "
                "WHERE owner_id=? AND stage='closed_lost' AND updated_at>=?",
                (owner_id, cutoff)).fetchone()

            total_ct = dict(total)["c"]
            won_d = dict(won)
            lost_d = dict(lost)

            # Loss reasons breakdown
            reasons = db.execute("""
                SELECT wl.reason, COUNT(*) as count, COALESCE(SUM(d.value),0) as value_lost
                FROM win_loss_log wl
                JOIN crm_deals d ON wl.deal_id = d.id
                WHERE d.owner_id=? AND wl.outcome='lost' AND wl.reason!=''
                AND d.updated_at>=?
                GROUP BY wl.reason ORDER BY count DESC
            """, (owner_id, cutoff)).fetchall()

            # Competitor wins
            competitors = db.execute("""
                SELECT wl.competitor, COUNT(*) as count
                FROM win_loss_log wl
                JOIN crm_deals d ON wl.deal_id = d.id
                WHERE d.owner_id=? AND wl.outcome='lost' AND wl.competitor!=''
                AND d.updated_at>=?
                GROUP BY wl.competitor ORDER BY count DESC LIMIT 5
            """, (owner_id, cutoff)).fetchall()

            # Win rate by deal size
            size_brackets = [
                ("small", 0, 5000),
                ("medium", 5000, 25000),
                ("large", 25000, 100000),
                ("enterprise", 100000, 99999999),
            ]
            by_size = []
            for label, low, high in size_brackets:
                bracket_won = db.execute(
                    "SELECT COUNT(*) as c FROM crm_deals WHERE owner_id=? AND stage='closed_won' "
                    "AND value>=? AND value<? AND updated_at>=?",
                    (owner_id, low, high, cutoff)).fetchone()
                bracket_total = db.execute(
                    "SELECT COUNT(*) as c FROM crm_deals WHERE owner_id=? AND status!='open' "
                    "AND value>=? AND value<? AND updated_at>=?",
                    (owner_id, low, high, cutoff)).fetchone()
                bt = dict(bracket_total)["c"]
                bw = dict(bracket_won)["c"]
                by_size.append({
                    "bracket": label,
                    "range": f"${low:,}-${high:,}",
                    "total": bt,
                    "won": bw,
                    "win_rate": round(bw / bt * 100, 1) if bt > 0 else 0,
                })

        win_rate = round(won_d["c"] / total_ct * 100, 1) if total_ct > 0 else 0

        return {
            "period_days": period_days,
            "total_closed": total_ct,
            "won": {"count": won_d["c"], "value": round(won_d["v"], 2)},
            "lost": {"count": lost_d["c"], "value": round(lost_d["v"], 2)},
            "win_rate": win_rate,
            "loss_reasons": [dict(r) for r in reasons],
            "lost_to_competitors": [dict(c) for c in competitors],
            "by_deal_size": by_size,
            "ai_prompt": self._build_analysis_prompt(win_rate, [dict(r) for r in reasons]),
        }

    def _build_analysis_prompt(self, win_rate: float, reasons: list) -> str:
        top_reasons = ", ".join(r["reason"] for r in reasons[:3]) if reasons else "none recorded"
        return (
            f"Analyze this sales performance: win rate is {win_rate}%. "
            f"Top loss reasons: {top_reasons}. "
            f"Provide 3 specific, actionable recommendations to improve close rate. "
            f"Be direct and specific, not generic."
        )


# ══════════════════════════════════════════════════════════════
# 2. CLIENT HEALTH SCORE
# ══════════════════════════════════════════════════════════════

class ClientHealthScorer:
    """Score contacts green/yellow/red based on engagement."""

    def score_contact(self, contact_id: str) -> dict:
        """Calculate health score for a single contact."""
        with get_db() as db:
            # Last activity
            last_activity = db.execute(
                "SELECT MAX(created_at) as last FROM crm_activities WHERE contact_id=?",
                (contact_id,)).fetchone()
            activity_count = db.execute(
                "SELECT COUNT(*) as c FROM crm_activities WHERE contact_id=?",
                (contact_id,)).fetchone()

            # Open deals
            deals = db.execute(
                "SELECT COUNT(*) as c, COALESCE(SUM(value),0) as v FROM crm_deals "
                "WHERE contact_id=? AND status='open'",
                (contact_id,)).fetchone()

            # Emails sent
            emails = db.execute(
                "SELECT COUNT(*) as c FROM email_outbox WHERE contact_id=?",
                (contact_id,)).fetchone()

            # Overdue follow-ups
            overdue = db.execute(
                "SELECT COUNT(*) as c FROM crm_activities "
                "WHERE contact_id=? AND completed=0 AND due_date!='' AND due_date<?",
                (contact_id, datetime.now().strftime("%Y-%m-%d"))).fetchone()

        last = dict(last_activity).get("last", "")
        acts = dict(activity_count)["c"]
        deal_data = dict(deals)
        overdue_ct = dict(overdue)["c"]

        # Calculate score (0-100)
        score = 50  # Base

        # Recency bonus/penalty
        if last:
            days_since = (datetime.now() - datetime.fromisoformat(last)).days
            if days_since <= 3:
                score += 25
            elif days_since <= 7:
                score += 15
            elif days_since <= 14:
                score += 5
            elif days_since <= 30:
                score -= 10
            else:
                score -= 25
        else:
            score -= 20

        # Activity volume
        if acts >= 10:
            score += 15
        elif acts >= 5:
            score += 10
        elif acts >= 2:
            score += 5

        # Open deals
        if deal_data["c"] > 0:
            score += 10

        # Overdue penalty
        score -= overdue_ct * 10

        score = max(0, min(100, score))

        # Determine status
        if score >= 70:
            status = "healthy"
            color = "green"
            icon = "🟢"
        elif score >= 40:
            status = "at_risk"
            color = "yellow"
            icon = "🟡"
        else:
            status = "cold"
            color = "red"
            icon = "🔴"

        return {
            "contact_id": contact_id,
            "score": score,
            "status": status,
            "color": color,
            "icon": icon,
            "factors": {
                "days_since_contact": (datetime.now() - datetime.fromisoformat(last)).days if last else 999,
                "total_activities": acts,
                "open_deals": deal_data["c"],
                "pipeline_value": round(deal_data["v"], 2),
                "overdue_followups": overdue_ct,
                "emails_sent": dict(emails)["c"],
            },
        }

    def score_all_contacts(self, owner_id: str) -> dict:
        """Score every contact — return summary + sorted list."""
        with get_db() as db:
            contacts = db.execute(
                "SELECT id, name FROM crm_contacts WHERE owner_id=?",
                (owner_id,)).fetchall()

        scored = []
        summary = {"healthy": 0, "at_risk": 0, "cold": 0}
        for c in contacts:
            d = dict(c)
            health = self.score_contact(d["id"])
            health["name"] = d["name"]
            scored.append(health)
            summary[health["status"]] = summary.get(health["status"], 0) + 1

        # Sort: cold first (needs attention), then at_risk, then healthy
        scored.sort(key=lambda x: x["score"])

        return {
            "total_contacts": len(scored),
            "summary": summary,
            "contacts": scored,
        }


# ══════════════════════════════════════════════════════════════
# 3. REVENUE FORECASTING
# ══════════════════════════════════════════════════════════════

class RevenueForecast:
    """Pipeline-weighted revenue projections."""

    # Default stage probabilities
    STAGE_PROBABILITIES = {
        "lead": 0.10,
        "qualified": 0.20,
        "discovery": 0.20,
        "demo": 0.30,
        "trial": 0.40,
        "proposal": 0.50,
        "proposal_sent": 0.50,
        "negotiation": 0.70,
        "verbal_yes": 0.85,
        "contract_sent": 0.90,
        "closed_won": 1.0,
        "closed_lost": 0.0,
    }

    def forecast(self, owner_id: str, months: int = 3) -> dict:
        """Generate revenue forecast from current pipeline."""
        with get_db() as db:
            # All open deals
            deals = db.execute(
                "SELECT id, title, value, stage, expected_close, created_at FROM crm_deals "
                "WHERE owner_id=? AND status='open' ORDER BY value DESC",
                (owner_id,)).fetchall()

            # Historical close rate for calibration
            won = db.execute(
                "SELECT COUNT(*) as c FROM crm_deals WHERE owner_id=? AND stage='closed_won'",
                (owner_id,)).fetchone()
            total_closed = db.execute(
                "SELECT COUNT(*) as c FROM crm_deals WHERE owner_id=? AND status!='open'",
                (owner_id,)).fetchone()

            # Monthly revenue history
            history = []
            for i in range(6):
                month_start = (datetime.now() - timedelta(days=30 * (i + 1))).strftime("%Y-%m-%d")
                month_end = (datetime.now() - timedelta(days=30 * i)).strftime("%Y-%m-%d")
                rev = db.execute(
                    "SELECT COALESCE(SUM(total),0) as t FROM invoices "
                    "WHERE owner_id=? AND status='paid' AND paid_at>=? AND paid_at<?",
                    (owner_id, month_start, month_end)).fetchone()
                history.append({
                    "month": month_start[:7],
                    "revenue": round(dict(rev)["t"], 2),
                })

        historical_rate = dict(won)["c"] / max(dict(total_closed)["c"], 1)

        # Calculate weighted pipeline
        weighted_total = 0
        best_case = 0
        worst_case = 0
        deal_forecasts = []
        for deal in deals:
            d = dict(deal)
            stage = d.get("stage", "lead").lower().replace(" ", "_")
            prob = self.STAGE_PROBABILITIES.get(stage, 0.20)
            value = d.get("value", 0)
            weighted = round(value * prob, 2)
            weighted_total += weighted
            best_case += value
            worst_case += round(value * max(prob - 0.15, 0), 2)
            deal_forecasts.append({
                "deal": d["title"],
                "value": value,
                "stage": d["stage"],
                "probability": round(prob * 100),
                "weighted_value": weighted,
            })

        # Monthly projection
        monthly_avg = sum(h["revenue"] for h in history) / max(len(history), 1)
        monthly_projections = []
        for m in range(months):
            month = (datetime.now() + timedelta(days=30 * (m + 1))).strftime("%Y-%m")
            # Blend pipeline weighted + historical average
            projected = round((weighted_total / max(months, 1)) + (monthly_avg * 0.3), 2)
            monthly_projections.append({
                "month": month,
                "projected": projected,
            })

        return {
            "pipeline_value": best_case,
            "weighted_pipeline": round(weighted_total, 2),
            "best_case": best_case,
            "worst_case": round(worst_case, 2),
            "expected": round(weighted_total, 2),
            "historical_close_rate": round(historical_rate * 100, 1),
            "monthly_avg_revenue": round(monthly_avg, 2),
            "monthly_projections": monthly_projections,
            "deal_forecasts": deal_forecasts,
            "revenue_history": list(reversed(history)),
        }


# ══════════════════════════════════════════════════════════════
# 4. TIME-TO-CLOSE TRACKING
# ══════════════════════════════════════════════════════════════

class TimeToCloseTracker:
    """Track how long deals take from creation to close."""

    def get_metrics(self, owner_id: str) -> dict:
        """Calculate average time-to-close and velocity metrics."""
        with get_db() as db:
            # Won deals with both created_at and updated_at (close date)
            won = db.execute(
                "SELECT id, title, value, stage, created_at, updated_at FROM crm_deals "
                "WHERE owner_id=? AND stage='closed_won'",
                (owner_id,)).fetchall()

            # Stage transition times (from activity log)
            stage_times = db.execute("""
                SELECT d.id, d.title, a.subject, a.created_at
                FROM crm_deals d
                JOIN crm_activities a ON a.contact_id = d.contact_id
                WHERE d.owner_id=? AND d.stage='closed_won'
                ORDER BY d.id, a.created_at
            """, (owner_id,)).fetchall()

        close_times = []
        by_size = defaultdict(list)
        for deal in won:
            d = dict(deal)
            try:
                created = datetime.fromisoformat(d["created_at"])
                closed = datetime.fromisoformat(d["updated_at"])
                days = (closed - created).days
                close_times.append(days)
                value = d.get("value", 0)
                if value < 5000:
                    by_size["small"].append(days)
                elif value < 25000:
                    by_size["medium"].append(days)
                elif value < 100000:
                    by_size["large"].append(days)
                else:
                    by_size["enterprise"].append(days)
            except:
                pass

        avg_days = round(sum(close_times) / max(len(close_times), 1), 1)
        median_days = sorted(close_times)[len(close_times) // 2] if close_times else 0

        # Velocity by size
        velocity_by_size = {}
        for bracket, times in by_size.items():
            velocity_by_size[bracket] = {
                "avg_days": round(sum(times) / len(times), 1),
                "deal_count": len(times),
            }

        # Current pipeline velocity (how fast open deals are moving)
        with get_db() as db:
            open_deals = db.execute(
                "SELECT id, value, created_at FROM crm_deals WHERE owner_id=? AND status='open'",
                (owner_id,)).fetchall()
        aging = []
        for d in open_deals:
            dd = dict(d)
            try:
                age = (datetime.now() - datetime.fromisoformat(dd["created_at"])).days
                aging.append({"age_days": age, "value": dd.get("value", 0)})
            except:
                pass

        stalled = [a for a in aging if a["age_days"] > avg_days * 1.5] if avg_days > 0 else []

        return {
            "avg_days_to_close": avg_days,
            "median_days_to_close": median_days,
            "total_won_analyzed": len(close_times),
            "by_deal_size": velocity_by_size,
            "current_pipeline_aging": aging,
            "stalled_deals": len(stalled),
            "stalled_value": round(sum(d["value"] for d in stalled), 2),
        }


# ══════════════════════════════════════════════════════════════
# 5. ACTIVITY SCORING
# ══════════════════════════════════════════════════════════════

class ActivityScorer:
    """Score deals based on engagement patterns that predict wins."""

    ACTIVITY_WEIGHTS = {
        "call": 10,
        "meeting": 15,
        "email": 5,
        "demo": 20,
        "proposal": 15,
        "follow_up": 8,
        "note": 3,
        "site_visit": 20,
    }

    def score_deal(self, deal_id: str) -> dict:
        """Score a deal based on activity patterns."""
        with get_db() as db:
            deal = db.execute("SELECT * FROM crm_deals WHERE id=?", (deal_id,)).fetchone()
            if not deal:
                return {"error": "Deal not found"}
            deal = dict(deal)

            activities = db.execute(
                "SELECT activity_type, created_at FROM crm_activities WHERE contact_id=? ORDER BY created_at",
                (deal.get("contact_id", ""),)).fetchall()

        score = 0
        activity_breakdown = defaultdict(int)
        for a in activities:
            d = dict(a)
            atype = d.get("activity_type", "note")
            weight = self.ACTIVITY_WEIGHTS.get(atype, 3)
            score += weight
            activity_breakdown[atype] += 1

        # Recency bonus
        if activities:
            last = dict(activities[-1])
            try:
                days_since = (datetime.now() - datetime.fromisoformat(last["created_at"])).days
                if days_since <= 3:
                    score += 20
                elif days_since <= 7:
                    score += 10
                elif days_since > 14:
                    score -= 15
            except:
                pass

        # Velocity bonus — more activities in first week = higher close rate
        first_week_count = 0
        if activities:
            try:
                first_date = datetime.fromisoformat(dict(activities[0])["created_at"])
                for a in activities:
                    adate = datetime.fromisoformat(dict(a)["created_at"])
                    if (adate - first_date).days <= 7:
                        first_week_count += 1
                if first_week_count >= 3:
                    score += 15
            except:
                pass

        # Normalize to 0-100
        score = min(100, max(0, score))

        if score >= 70:
            prediction = "likely_to_close"
            color = "green"
        elif score >= 40:
            prediction = "needs_attention"
            color = "yellow"
        else:
            prediction = "at_risk"
            color = "red"

        return {
            "deal_id": deal_id,
            "deal_title": deal.get("title", ""),
            "score": score,
            "prediction": prediction,
            "color": color,
            "total_activities": len(activities),
            "first_week_activities": first_week_count,
            "activity_breakdown": dict(activity_breakdown),
        }

    def score_pipeline(self, owner_id: str) -> dict:
        """Score all open deals."""
        with get_db() as db:
            deals = db.execute(
                "SELECT id, title, value FROM crm_deals WHERE owner_id=? AND status='open'",
                (owner_id,)).fetchall()

        scored = []
        for d in deals:
            dd = dict(d)
            s = self.score_deal(dd["id"])
            s["value"] = dd.get("value", 0)
            scored.append(s)

        scored.sort(key=lambda x: x["score"], reverse=True)

        summary = {
            "likely_to_close": len([s for s in scored if s["prediction"] == "likely_to_close"]),
            "needs_attention": len([s for s in scored if s["prediction"] == "needs_attention"]),
            "at_risk": len([s for s in scored if s["prediction"] == "at_risk"]),
        }

        return {"deals": scored, "summary": summary}


# ══════════════════════════════════════════════════════════════
# 6. UNDO SYSTEM
# ══════════════════════════════════════════════════════════════

class UndoManager:
    """30-second undo window for destructive actions.
    Stores action + reverse data. Frontend polls for pending undos."""

    def log_action(self, owner_id: str, action_type: str,
                    entity_type: str, entity_id: str,
                    reverse_data: dict) -> dict:
        """Log an undoable action."""
        uid = f"undo_{uuid.uuid4().hex[:8]}"
        expires = (datetime.now() + timedelta(seconds=30)).isoformat()
        with get_db() as db:
            db.execute("""
                INSERT INTO undo_log
                    (id, owner_id, action_type, entity_type, entity_id, reverse_data, expires_at)
                VALUES (?,?,?,?,?,?,?)
            """, (uid, owner_id, action_type, entity_type, entity_id,
                  json.dumps(reverse_data), expires))
        return {"undo_id": uid, "expires_at": expires, "seconds": 30}

    def execute_undo(self, undo_id: str, owner_id: str) -> dict:
        """Execute an undo if still within window."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM undo_log WHERE id=? AND owner_id=? AND status='pending'",
                (undo_id, owner_id)).fetchone()
            if not row:
                return {"error": "Undo not found or already used"}
            undo = dict(row)

            if datetime.fromisoformat(undo["expires_at"]) < datetime.now():
                db.execute("UPDATE undo_log SET status='expired' WHERE id=?", (undo_id,))
                return {"error": "Undo window expired (30 seconds)"}

            # Execute the reverse
            reverse = json.loads(undo.get("reverse_data", "{}"))
            action = undo["action_type"]
            entity = undo["entity_type"]

            try:
                if action == "delete" and reverse.get("restore_sql"):
                    # Re-insert the deleted row
                    db.execute(reverse["restore_sql"], reverse.get("restore_params", []))
                elif action == "update" and reverse.get("original_values"):
                    table = reverse.get("table", entity)
                    orig = reverse["original_values"]
                    sets = ", ".join(f"{k}=?" for k in orig)
                    vals = list(orig.values()) + [undo["entity_id"]]
                    db.execute(f"UPDATE {table} SET {sets} WHERE id=?", vals)

                db.execute("UPDATE undo_log SET status='undone' WHERE id=?", (undo_id,))
                return {"undone": True, "action": action, "entity": entity}
            except Exception as e:
                logger.error(f"Undo failed: {e}")
                return {"error": "Undo failed", "detail": str(e)}

    def get_pending(self, owner_id: str) -> list:
        """Get any actions that can still be undone."""
        now = datetime.now().isoformat()
        with get_db() as db:
            rows = db.execute(
                "SELECT id, action_type, entity_type, entity_id, expires_at FROM undo_log "
                "WHERE owner_id=? AND status='pending' AND expires_at>? ORDER BY expires_at",
                (owner_id, now)).fetchall()
        return [dict(r) for r in rows]

    def cleanup_expired(self) -> int:
        """Clean up expired undos."""
        now = datetime.now().isoformat()
        with get_db() as db:
            db.execute("UPDATE undo_log SET status='expired' WHERE status='pending' AND expires_at<?",
                      (now,))
            result = db.execute("SELECT changes()").fetchone()
        return dict(result).get("changes()", 0)


# ══════════════════════════════════════════════════════════════
# 7. SMS / TEXT LOG (Manual capture — we never touch their phone)
# ══════════════════════════════════════════════════════════════

class TextMessageLog:
    """Manual log of text/SMS conversations.
    We NEVER integrate with their phone or messaging apps.
    Users tell us what happened, we log it to the CRM timeline."""

    def log_text(self, owner_id: str, contact_id: str = "",
                  contact_name: str = "", phone_number: str = "",
                  direction: str = "outbound", content: str = "",
                  notes: str = "") -> dict:
        """Log a text message interaction."""
        tid = f"txt_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO text_message_log
                    (id, owner_id, contact_id, contact_name, phone_number,
                     direction, content, notes)
                VALUES (?,?,?,?,?,?,?,?)
            """, (tid, owner_id, contact_id, contact_name, phone_number,
                  direction, content[:1000], notes))

            # Also log as CRM activity if contact_id provided
            if contact_id:
                db.execute("""
                    INSERT INTO crm_activities
                        (id, owner_id, contact_id, activity_type, subject, notes, completed)
                    VALUES (?,?,?,?,?,?,1)
                """, (f"act_{uuid.uuid4().hex[:8]}", owner_id, contact_id,
                      "text", f"{'Sent' if direction == 'outbound' else 'Received'} text: {content[:50]}",
                      content))

        return {"id": tid, "logged": True, "crm_synced": bool(contact_id)}

    def get_log(self, owner_id: str, contact_id: str = "",
                 limit: int = 50) -> list:
        """Get text message log."""
        with get_db() as db:
            if contact_id:
                rows = db.execute(
                    "SELECT * FROM text_message_log WHERE owner_id=? AND contact_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (owner_id, contact_id, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM text_message_log WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, limit)).fetchall()
        return [dict(r) for r in rows]
