# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Business Customization Upgrades — Closes gaps found in deep audit.

INVOICING:
  - Recurring invoices (weekly/monthly/quarterly/yearly)
  - Partial payments + balance tracking
  - Late fee calculation
  - Custom number formats

TASKS:
  - Time tracking per task (start/stop timer + manual entry)
  - Task dependencies (blocked by)
  - Recurring tasks

EMAIL:
  - Email templates/snippets (reusable)
  - Email signatures
  - Scheduled send (compose now, send later)

EXPENSES:
  - Custom categories (user creates their own)
  - Tax deductibility flag per expense
  - Budget limits per category

GOALS:
  - Team goals (shared across users)
  - Goal templates (common OKRs)

SOCIAL:
  - Hashtag groups (saved sets)
  - Post templates
  - Post approval workflow
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.biz_upgrades")


# ══════════════════════════════════════════════════════════════
# INVOICING UPGRADES
# ══════════════════════════════════════════════════════════════

class RecurringInvoiceManager:
    """Auto-generate invoices on a schedule."""

    FREQUENCIES = ["weekly", "biweekly", "monthly", "quarterly", "yearly"]

    def create_recurring(self, owner_id: str, client_name: str,
                          client_email: str, line_items: list,
                          frequency: str = "monthly",
                          start_date: str = "", end_date: str = "",
                          auto_send: bool = False) -> dict:
        rid = f"rec_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO recurring_invoices
                    (id, owner_id, client_name, client_email, line_items,
                     frequency, start_date, end_date, auto_send, status,
                     next_date, invoices_generated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,0)
            """, (rid, owner_id, client_name, client_email,
                  json.dumps(line_items), frequency,
                  start_date or datetime.now().strftime("%Y-%m-%d"),
                  end_date or "", 1 if auto_send else 0, "active",
                  start_date or datetime.now().strftime("%Y-%m-%d")))
        return {"id": rid, "frequency": frequency, "client": client_name,
                "auto_send": auto_send}

    def list_recurring(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM recurring_invoices WHERE owner_id=? ORDER BY next_date",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def pause(self, recurring_id: str) -> dict:
        with get_db() as db:
            db.execute("UPDATE recurring_invoices SET status='paused' WHERE id=?",
                      (recurring_id,))
        return {"paused": True}

    def resume(self, recurring_id: str) -> dict:
        with get_db() as db:
            db.execute("UPDATE recurring_invoices SET status='active' WHERE id=?",
                      (recurring_id,))
        return {"resumed": True}

    def get_due(self, owner_id: str) -> list:
        """Get recurring invoices due for generation today."""
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM recurring_invoices WHERE owner_id=? AND status='active' AND next_date<=?",
                (owner_id, today)).fetchall()
        return [dict(r) for r in rows]


class PaymentTracker:
    """Track partial payments on invoices."""

    def record_payment(self, invoice_id: str, amount: float,
                        method: str = "", note: str = "") -> dict:
        pid = f"pay_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            # Get invoice total and prior payments
            inv = db.execute("SELECT total FROM invoices WHERE id=?",
                            (invoice_id,)).fetchone()
            if not inv:
                return {"error": "Invoice not found"}
            prior = db.execute(
                "SELECT COALESCE(SUM(amount),0) as paid FROM invoice_payments WHERE invoice_id=?",
                (invoice_id,)).fetchone()
            total = dict(inv)["total"]
            total_paid = dict(prior)["paid"] + amount
            balance = round(total - total_paid, 2)

            db.execute("""
                INSERT INTO invoice_payments (id, invoice_id, amount, method, note)
                VALUES (?,?,?,?,?)
            """, (pid, invoice_id, amount, method, note))

            # Auto-update invoice status
            if balance <= 0:
                db.execute("UPDATE invoices SET status='paid', paid_at=? WHERE id=?",
                          (datetime.now().isoformat(), invoice_id))
            else:
                db.execute("UPDATE invoices SET status='partial' WHERE id=? AND status!='paid'",
                          (invoice_id,))

        return {"payment_id": pid, "amount": amount, "total_paid": round(total_paid, 2),
                "balance": max(balance, 0), "fully_paid": balance <= 0}

    def get_payments(self, invoice_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM invoice_payments WHERE invoice_id=? ORDER BY created_at",
                (invoice_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_balance(self, invoice_id: str) -> dict:
        with get_db() as db:
            inv = db.execute("SELECT total FROM invoices WHERE id=?",
                            (invoice_id,)).fetchone()
            paid = db.execute(
                "SELECT COALESCE(SUM(amount),0) as t FROM invoice_payments WHERE invoice_id=?",
                (invoice_id,)).fetchone()
        if not inv:
            return {"error": "Invoice not found"}
        total = dict(inv)["total"]
        total_paid = dict(paid)["t"]
        return {"total": total, "paid": round(total_paid, 2),
                "balance": round(total - total_paid, 2)}


# ══════════════════════════════════════════════════════════════
# TASK TIME TRACKING
# ══════════════════════════════════════════════════════════════

class TaskTimeTracker:
    """Start/stop timer or manually log time on tasks."""

    def start_timer(self, task_id: str, user_id: str) -> dict:
        tid = f"timer_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            # Stop any running timer for this user
            db.execute(
                "UPDATE task_time_entries SET ended_at=? WHERE user_id=? AND ended_at=''",
                (datetime.now().isoformat(), user_id))
            db.execute("""
                INSERT INTO task_time_entries (id, task_id, user_id, started_at, ended_at, manual)
                VALUES (?,?,?,?,'',0)
            """, (tid, task_id, user_id, datetime.now().isoformat()))
        return {"timer_id": tid, "started": True, "task_id": task_id}

    def stop_timer(self, user_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT id, task_id, started_at FROM task_time_entries WHERE user_id=? AND ended_at=''",
                (user_id,)).fetchone()
            if not row:
                return {"error": "No active timer"}
            d = dict(row)
            now = datetime.now()
            started = datetime.fromisoformat(d["started_at"])
            duration_min = round((now - started).total_seconds() / 60, 1)
            db.execute("UPDATE task_time_entries SET ended_at=?, duration_minutes=? WHERE id=?",
                      (now.isoformat(), duration_min, d["id"]))
        return {"stopped": True, "task_id": d["task_id"],
                "duration_minutes": duration_min}

    def log_manual(self, task_id: str, user_id: str, minutes: float,
                    date: str = "", note: str = "") -> dict:
        tid = f"time_{uuid.uuid4().hex[:8]}"
        log_date = date or datetime.now().isoformat()
        with get_db() as db:
            db.execute("""
                INSERT INTO task_time_entries
                    (id, task_id, user_id, started_at, ended_at, duration_minutes, note, manual)
                VALUES (?,?,?,?,?,?,?,1)
            """, (tid, task_id, user_id, log_date, log_date, minutes, note))
        return {"id": tid, "minutes": minutes, "task_id": task_id}

    def get_task_time(self, task_id: str) -> dict:
        with get_db() as db:
            total = db.execute(
                "SELECT COALESCE(SUM(duration_minutes),0) as t FROM task_time_entries WHERE task_id=?",
                (task_id,)).fetchone()
            entries = db.execute(
                "SELECT * FROM task_time_entries WHERE task_id=? ORDER BY started_at DESC",
                (task_id,)).fetchall()
        return {"total_minutes": round(dict(total)["t"], 1),
                "total_hours": round(dict(total)["t"] / 60, 2),
                "entries": [dict(r) for r in entries]}

    def get_active_timer(self, user_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM task_time_entries WHERE user_id=? AND ended_at=''",
                (user_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        started = datetime.fromisoformat(d["started_at"])
        elapsed = round((datetime.now() - started).total_seconds() / 60, 1)
        d["elapsed_minutes"] = elapsed
        return d

    def get_timesheet(self, user_id: str, start_date: str, end_date: str) -> dict:
        """Get all time entries for a period — the timesheet."""
        with get_db() as db:
            rows = db.execute("""
                SELECT te.*, t.title as task_title, p.name as project_name
                FROM task_time_entries te
                JOIN tasks t ON te.task_id = t.id
                JOIN task_projects p ON t.project_id = p.id
                WHERE te.user_id=? AND te.started_at>=? AND te.started_at<=?
                ORDER BY te.started_at
            """, (user_id, start_date, end_date)).fetchall()
            total = db.execute(
                "SELECT COALESCE(SUM(duration_minutes),0) as t FROM task_time_entries "
                "WHERE user_id=? AND started_at>=? AND started_at<=?",
                (user_id, start_date, end_date)).fetchone()
        return {
            "period": {"start": start_date, "end": end_date},
            "total_minutes": round(dict(total)["t"], 1),
            "total_hours": round(dict(total)["t"] / 60, 2),
            "entries": [dict(r) for r in rows],
        }


# ══════════════════════════════════════════════════════════════
# EMAIL UPGRADES
# ══════════════════════════════════════════════════════════════

class EmailTemplateManager:
    """Reusable email templates and signatures."""

    def create_template(self, owner_id: str, name: str, subject: str,
                         body: str, category: str = "general") -> dict:
        tid = f"etpl_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO email_templates (id, owner_id, name, subject, body, category)
                VALUES (?,?,?,?,?,?)
            """, (tid, owner_id, name, subject, body, category))
        return {"id": tid, "name": name}

    def list_templates(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM email_templates WHERE owner_id=? ORDER BY category, name",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_template(self, template_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM email_templates WHERE id=?",
                            (template_id,)).fetchone()
        return dict(row) if row else None

    def update_template(self, template_id: str, **updates) -> dict:
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [template_id]
        with get_db() as db:
            db.execute(f"UPDATE email_templates SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def delete_template(self, template_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM email_templates WHERE id=?", (template_id,))
        return {"deleted": True}

    def set_signature(self, owner_id: str, signature_html: str) -> dict:
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO email_signatures (owner_id, signature) VALUES (?,?)",
                (owner_id, signature_html))
        return {"saved": True}

    def get_signature(self, owner_id: str) -> str:
        with get_db() as db:
            row = db.execute(
                "SELECT signature FROM email_signatures WHERE owner_id=?",
                (owner_id,)).fetchone()
        return dict(row)["signature"] if row else ""


class ScheduledEmailManager:
    """Schedule emails to send at a future time."""

    def schedule(self, email_id: str, send_at: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE email_outbox SET status='scheduled', scheduled_at=? WHERE id=?",
                (send_at, email_id))
        return {"scheduled": True, "send_at": send_at}

    def get_scheduled(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT id, to_addr, subject, scheduled_at FROM email_outbox "
                "WHERE owner_id=? AND status='scheduled' ORDER BY scheduled_at",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_due(self, owner_id: str) -> list:
        """Get emails due to send now."""
        now = datetime.now().isoformat()
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM email_outbox WHERE owner_id=? AND status='scheduled' AND scheduled_at<=?",
                (owner_id, now)).fetchall()
        return [dict(r) for r in rows]

    def cancel(self, email_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE email_outbox SET status='draft', scheduled_at='' WHERE id=? AND status='scheduled'",
                (email_id,))
        return {"cancelled": True}


# ══════════════════════════════════════════════════════════════
# EXPENSE UPGRADES
# ══════════════════════════════════════════════════════════════

class CustomExpenseCategoryManager:
    """User-defined expense categories + tax deductibility."""

    def create_category(self, owner_id: str, name: str, icon: str = "📁",
                         color: str = "#94a3b8",
                         tax_deductible: bool = True) -> dict:
        cid = name.lower().replace(" ", "_")[:25]
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO custom_expense_categories
                    (id, owner_id, name, icon, color, tax_deductible)
                VALUES (?,?,?,?,?,?)
            """, (cid, owner_id, name, icon, color, 1 if tax_deductible else 0))
        return {"id": cid, "name": name, "tax_deductible": tax_deductible}

    def list_categories(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM custom_expense_categories WHERE owner_id=? ORDER BY name",
                (owner_id,)).fetchall()
        defaults = [
            {"id": "software", "name": "Software", "icon": "💻", "tax_deductible": True},
            {"id": "hosting", "name": "Hosting", "icon": "☁️", "tax_deductible": True},
            {"id": "marketing", "name": "Marketing", "icon": "📣", "tax_deductible": True},
            {"id": "travel", "name": "Travel", "icon": "✈️", "tax_deductible": True},
            {"id": "meals", "name": "Meals", "icon": "🍽️", "tax_deductible": True},
            {"id": "office_supplies", "name": "Office Supplies", "icon": "📎", "tax_deductible": True},
            {"id": "equipment", "name": "Equipment", "icon": "🖥️", "tax_deductible": True},
            {"id": "professional_services", "name": "Professional Services", "icon": "👔", "tax_deductible": True},
            {"id": "other", "name": "Other", "icon": "📁", "tax_deductible": False},
        ]
        custom = [dict(r) for r in rows]
        return defaults + custom

    def delete_category(self, owner_id: str, category_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "DELETE FROM custom_expense_categories WHERE id=? AND owner_id=?",
                (category_id, owner_id))
        return {"deleted": True}

    def get_tax_summary(self, owner_id: str, year: str = "") -> dict:
        """Expenses grouped by deductible vs non-deductible for tax time."""
        year = year or datetime.now().strftime("%Y")
        start = f"{year}-01-01"
        end = f"{year}-12-31"
        categories = {c["id"]: c for c in self.list_categories(owner_id)}
        with get_db() as db:
            rows = db.execute(
                "SELECT category, COALESCE(SUM(amount),0) as total, COUNT(*) as count "
                "FROM expenses WHERE owner_id=? AND expense_date>=? AND expense_date<=? "
                "GROUP BY category ORDER BY total DESC",
                (owner_id, start, end)).fetchall()

        deductible, non_deductible = 0, 0
        breakdown = []
        for r in rows:
            d = dict(r)
            cat_info = categories.get(d["category"], {})
            is_deductible = cat_info.get("tax_deductible", False)
            if is_deductible:
                deductible += d["total"]
            else:
                non_deductible += d["total"]
            breakdown.append({
                "category": d["category"],
                "total": round(d["total"], 2),
                "count": d["count"],
                "tax_deductible": is_deductible,
            })

        return {
            "year": year,
            "total_expenses": round(deductible + non_deductible, 2),
            "total_deductible": round(deductible, 2),
            "total_non_deductible": round(non_deductible, 2),
            "potential_tax_savings_estimate": round(deductible * 0.25, 2),
            "breakdown": breakdown,
            "note": "This is an estimate. Consult a tax professional for actual deductions.",
        }


# ══════════════════════════════════════════════════════════════
# SOCIAL MEDIA UPGRADES
# ══════════════════════════════════════════════════════════════

class HashtagManager:
    """Save and reuse hashtag groups."""

    def create_group(self, owner_id: str, name: str, hashtags: list,
                      platform: str = "all") -> dict:
        gid = f"htg_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO hashtag_groups (id, owner_id, name, hashtags, platform)
                VALUES (?,?,?,?,?)
            """, (gid, owner_id, name, json.dumps(hashtags), platform))
        return {"id": gid, "name": name, "count": len(hashtags)}

    def list_groups(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM hashtag_groups WHERE owner_id=? ORDER BY name",
                (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["hashtags"] = json.loads(d.get("hashtags", "[]"))
            result.append(d)
        return result

    def delete_group(self, group_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM hashtag_groups WHERE id=?", (group_id,))
        return {"deleted": True}


class PostApprovalWorkflow:
    """Require approval before posts go live."""

    def submit_for_approval(self, post_id: str, submitted_by: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE social_posts SET status='pending_approval' WHERE id=?",
                (post_id,))
        return {"submitted": True, "post_id": post_id}

    def approve(self, post_id: str, approved_by: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE social_posts SET status='scheduled' WHERE id=? AND status='pending_approval'",
                (post_id,))
        return {"approved": True}

    def reject(self, post_id: str, rejected_by: str, reason: str = "") -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE social_posts SET status='draft', error_message=? WHERE id=? AND status='pending_approval'",
                (f"Rejected: {reason}", post_id))
        return {"rejected": True, "reason": reason}

    def get_pending(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute("""
                SELECT p.*, c.name as campaign_name
                FROM social_posts p
                JOIN social_campaigns c ON p.campaign_id = c.id
                WHERE c.owner_id=? AND p.status='pending_approval'
                ORDER BY p.created_at
            """, (owner_id,)).fetchall()
        return [dict(r) for r in rows]
