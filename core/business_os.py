# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Complete Business OS — Final features to make MyTeam360 a full business platform.

10. GOAL / KPI TRACKER — OKRs, goals, milestones, team alignment
11. EMAIL COMPOSER + OUTBOX — Draft with AI, review, send
12. EXPENSE TRACKER — Track costs, categorize, receipts, profit/loss
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.business_os")


# ══════════════════════════════════════════════════════════════
# 10. GOAL / KPI TRACKER
# ══════════════════════════════════════════════════════════════

class GoalTracker:
    """OKR-style goal tracking for individuals and teams.

    Structure:
      Objective → Key Results → Progress updates
      "Grow revenue to $100K/mo" → "Close 20 new deals" (progress: 12/20 = 60%)
    """

    def create_goal(self, owner_id: str, title: str, description: str = "",
                     goal_type: str = "objective", target_value: float = 0,
                     target_unit: str = "", due_date: str = "",
                     parent_id: str = "", assigned_to: str = "",
                     category: str = "business") -> dict:
        gid = f"goal_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO goals
                    (id, owner_id, title, description, goal_type, target_value,
                     target_unit, current_value, due_date, parent_id,
                     assigned_to, category, status)
                VALUES (?,?,?,?,?,?,?,0,?,?,?,?,?)
            """, (gid, owner_id, title, description, goal_type, target_value,
                  target_unit, due_date, parent_id, assigned_to, category, "active"))
        return {"id": gid, "title": title, "goal_type": goal_type,
                "target": target_value, "unit": target_unit}

    def update_progress(self, goal_id: str, current_value: float,
                         note: str = "") -> dict:
        with get_db() as db:
            goal = db.execute("SELECT target_value FROM goals WHERE id=?",
                             (goal_id,)).fetchone()
            if not goal:
                return {"error": "Goal not found"}
            target = dict(goal)["target_value"]
            pct = round(current_value / target * 100, 1) if target else 0
            db.execute(
                "UPDATE goals SET current_value=?, progress_pct=?, updated_at=? WHERE id=?",
                (current_value, min(pct, 100), datetime.now().isoformat(), goal_id))
            # Log update
            db.execute("""
                INSERT INTO goal_updates (id, goal_id, value, note)
                VALUES (?,?,?,?)
            """, (f"gu_{uuid.uuid4().hex[:8]}", goal_id, current_value, note))
        status = "completed" if pct >= 100 else "on_track" if pct >= 50 else "at_risk" if pct >= 25 else "behind"
        return {"updated": True, "current": current_value, "target": target,
                "progress_pct": min(pct, 100), "status": status}

    def list_goals(self, owner_id: str, category: str = None,
                    status: str = "active") -> list:
        where, params = ["owner_id=?"], [owner_id]
        if category:
            where.append("category=?")
            params.append(category)
        if status:
            where.append("status=?")
            params.append(status)
        with get_db() as db:
            rows = db.execute(
                f"SELECT * FROM goals WHERE {' AND '.join(where)} ORDER BY due_date, created_at",
                params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Get key results (child goals)
            children = db.execute(
                "SELECT * FROM goals WHERE parent_id=? ORDER BY created_at",
                (d["id"],)).fetchall()
            d["key_results"] = [dict(c) for c in children]
            d["key_result_count"] = len(children)
            result.append(d)
        return result

    def get_goal(self, goal_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            children = db.execute(
                "SELECT * FROM goals WHERE parent_id=? ORDER BY created_at",
                (goal_id,)).fetchall()
            d["key_results"] = [dict(c) for c in children]
            updates = db.execute(
                "SELECT * FROM goal_updates WHERE goal_id=? ORDER BY created_at DESC LIMIT 10",
                (goal_id,)).fetchall()
            d["recent_updates"] = [dict(u) for u in updates]
        return d

    def complete_goal(self, goal_id: str) -> dict:
        with get_db() as db:
            db.execute("UPDATE goals SET status='completed', completed_at=? WHERE id=?",
                      (datetime.now().isoformat(), goal_id))
        return {"completed": True}

    def get_dashboard(self, owner_id: str) -> dict:
        with get_db() as db:
            total = db.execute(
                "SELECT COUNT(*) as c FROM goals WHERE owner_id=? AND status='active' AND parent_id=''",
                (owner_id,)).fetchone()
            completed = db.execute(
                "SELECT COUNT(*) as c FROM goals WHERE owner_id=? AND status='completed'",
                (owner_id,)).fetchone()
            avg_progress = db.execute(
                "SELECT AVG(progress_pct) as avg FROM goals WHERE owner_id=? AND status='active' AND parent_id=''",
                (owner_id,)).fetchone()
            overdue = db.execute(
                "SELECT COUNT(*) as c FROM goals WHERE owner_id=? AND status='active' AND due_date!='' AND due_date<?",
                (owner_id, datetime.now().strftime("%Y-%m-%d"))).fetchone()
            by_category = db.execute(
                "SELECT category, COUNT(*) as c, AVG(progress_pct) as avg_pct "
                "FROM goals WHERE owner_id=? AND status='active' AND parent_id='' GROUP BY category",
                (owner_id,)).fetchall()
        return {
            "active_objectives": dict(total)["c"],
            "completed": dict(completed)["c"],
            "average_progress": round(dict(avg_progress)["avg"] or 0, 1),
            "overdue": dict(overdue)["c"],
            "by_category": [{"category": dict(r)["category"],
                            "count": dict(r)["c"],
                            "avg_progress": round(dict(r)["avg_pct"] or 0, 1)} for r in by_category],
        }


# ══════════════════════════════════════════════════════════════
# 11. EMAIL COMPOSER + OUTBOX
# ══════════════════════════════════════════════════════════════

class EmailComposer:
    """Draft emails with AI, review, edit, and send from the platform.

    Flow: AI drafts → user reviews → edits if needed → sends → tracked in outbox
    """

    def create_draft(self, owner_id: str, to: str, subject: str,
                      body: str, cc: str = "", bcc: str = "",
                      reply_to: str = "", contact_id: str = "",
                      deal_id: str = "") -> dict:
        eid = f"email_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO email_outbox
                    (id, owner_id, to_addr, cc, bcc, reply_to, subject,
                     body, contact_id, deal_id, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (eid, owner_id, to, cc, bcc, reply_to, subject,
                  body, contact_id, deal_id, "draft"))
        return {"id": eid, "status": "draft", "to": to, "subject": subject}

    def update_draft(self, email_id: str, **updates) -> dict:
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [email_id]
        with get_db() as db:
            db.execute(f"UPDATE email_outbox SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def send_email(self, email_id: str, email_service=None) -> dict:
        """Send a drafted email."""
        with get_db() as db:
            row = db.execute("SELECT * FROM email_outbox WHERE id=?",
                            (email_id,)).fetchone()
        if not row:
            return {"error": "Email not found"}
        d = dict(row)
        if d["status"] != "draft":
            return {"error": f"Email already {d['status']}"}

        # Send via email service
        result = {"sent": False, "provider": "none"}
        if email_service:
            result = email_service.send(d["to_addr"], d["subject"], d["body"])

        if result.get("sent"):
            with get_db() as db:
                db.execute(
                    "UPDATE email_outbox SET status='sent', sent_at=? WHERE id=?",
                    (datetime.now().isoformat(), email_id))
            # Log in CRM if contact linked
            if d.get("contact_id"):
                try:
                    from .crm import CRMManager
                    CRMManager().log_activity(
                        d["owner_id"], "email", d["subject"],
                        contact_id=d["contact_id"], deal_id=d.get("deal_id", ""))
                except:
                    pass

        return {"sent": result.get("sent", False), "email_id": email_id,
                "provider": result.get("provider", "")}

    def list_outbox(self, owner_id: str, status: str = None) -> list:
        with get_db() as db:
            if status:
                rows = db.execute(
                    "SELECT id, to_addr, subject, status, sent_at, created_at "
                    "FROM email_outbox WHERE owner_id=? AND status=? ORDER BY created_at DESC",
                    (owner_id, status)).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, to_addr, subject, status, sent_at, created_at "
                    "FROM email_outbox WHERE owner_id=? ORDER BY created_at DESC LIMIT 50",
                    (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_email(self, email_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM email_outbox WHERE id=?",
                            (email_id,)).fetchone()
        return dict(row) if row else None

    def delete_draft(self, email_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM email_outbox WHERE id=? AND status='draft'",
                      (email_id,))
        return {"deleted": True}


# ══════════════════════════════════════════════════════════════
# 12. EXPENSE TRACKER
# ══════════════════════════════════════════════════════════════

class ExpenseTracker:
    """Track business expenses, categorize, and calculate profit/loss."""

    CATEGORIES = [
        "software", "hosting", "marketing", "travel", "meals",
        "office_supplies", "equipment", "professional_services",
        "insurance", "utilities", "rent", "payroll", "taxes",
        "shipping", "training", "subscriptions", "other",
    ]

    def add_expense(self, owner_id: str, description: str, amount: float,
                     category: str = "other", vendor: str = "",
                     date: str = "", receipt_url: str = "",
                     recurring: bool = False, notes: str = "") -> dict:
        eid = f"exp_{uuid.uuid4().hex[:10]}"
        expense_date = date or datetime.now().strftime("%Y-%m-%d")
        with get_db() as db:
            db.execute("""
                INSERT INTO expenses
                    (id, owner_id, description, amount, category, vendor,
                     expense_date, receipt_url, recurring, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (eid, owner_id, description, amount, category, vendor,
                  expense_date, receipt_url, 1 if recurring else 0, notes))
        return {"id": eid, "description": description, "amount": amount,
                "category": category, "date": expense_date}

    def list_expenses(self, owner_id: str, start_date: str = "",
                       end_date: str = "", category: str = "",
                       limit: int = 50) -> list:
        where, params = ["owner_id=?"], [owner_id]
        if start_date:
            where.append("expense_date>=?")
            params.append(start_date)
        if end_date:
            where.append("expense_date<=?")
            params.append(end_date)
        if category:
            where.append("category=?")
            params.append(category)
        params.append(limit)
        with get_db() as db:
            rows = db.execute(
                f"SELECT * FROM expenses WHERE {' AND '.join(where)} "
                "ORDER BY expense_date DESC LIMIT ?", params).fetchall()
        return [dict(r) for r in rows]

    def update_expense(self, expense_id: str, **updates) -> dict:
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [expense_id]
        with get_db() as db:
            db.execute(f"UPDATE expenses SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def delete_expense(self, expense_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        return {"deleted": True}

    def get_summary(self, owner_id: str, start_date: str = "",
                     end_date: str = "") -> dict:
        """Expense summary with profit/loss calculation."""
        if not start_date:
            start_date = datetime.now().replace(month=1, day=1).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        with get_db() as db:
            total_expenses = db.execute(
                "SELECT COALESCE(SUM(amount),0) as t FROM expenses WHERE owner_id=? AND expense_date>=? AND expense_date<=?",
                (owner_id, start_date, end_date)).fetchone()
            by_category = db.execute(
                "SELECT category, COALESCE(SUM(amount),0) as t, COUNT(*) as c "
                "FROM expenses WHERE owner_id=? AND expense_date>=? AND expense_date<=? "
                "GROUP BY category ORDER BY t DESC",
                (owner_id, start_date, end_date)).fetchall()
            # Revenue from paid invoices
            revenue = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=? AND status='paid' AND paid_at>=? AND paid_at<=?",
                (owner_id, start_date, end_date)).fetchone()
            # Monthly breakdown
            monthly = db.execute(
                "SELECT strftime('%%Y-%%m', expense_date) as month, COALESCE(SUM(amount),0) as t "
                "FROM expenses WHERE owner_id=? AND expense_date>=? AND expense_date<=? "
                "GROUP BY month ORDER BY month",
                (owner_id, start_date, end_date)).fetchall()

        total_exp = round(dict(total_expenses)["t"], 2)
        total_rev = round(dict(revenue)["t"], 2)
        return {
            "period": {"start": start_date, "end": end_date},
            "total_expenses": total_exp,
            "total_revenue": total_rev,
            "net_profit": round(total_rev - total_exp, 2),
            "profit_margin": round((total_rev - total_exp) / total_rev * 100, 1) if total_rev else 0,
            "by_category": [{"category": dict(r)["category"],
                            "total": round(dict(r)["t"], 2),
                            "count": dict(r)["c"]} for r in by_category],
            "monthly": [{"month": dict(r)["month"], "total": round(dict(r)["t"], 2)} for r in monthly],
            "categories_available": self.CATEGORIES,
        }
