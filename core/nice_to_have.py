# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Nice-to-Have Features — Closing every remaining gap.

1. Zapier/Make outbound webhooks (fire events to external services)
2. Task dependencies (blocked by / blocks)
3. Recurring tasks (daily, weekly, monthly, custom)
4. Late fee auto-calculation on overdue invoices
5. Demo / sample data generator
6. Dark mode preference
7. Contextual tooltips / help system
8. WhatsApp message log (manual capture, same as SMS)
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.nice_to_have")


# ══════════════════════════════════════════════════════════════
# 1. ZAPIER / MAKE OUTBOUND WEBHOOKS
# ══════════════════════════════════════════════════════════════

class OutboundWebhooks:
    """Fire events to Zapier/Make/custom URLs when things happen."""

    EVENT_TYPES = [
        "deal.won", "deal.lost", "deal.stage_changed",
        "contact.created", "contact.updated",
        "task.completed", "task.created", "task.overdue",
        "invoice.sent", "invoice.paid", "invoice.overdue",
        "booking.requested", "booking.confirmed",
        "goal.completed", "goal.progress",
        "social.post_published",
    ]

    def register_webhook(self, owner_id: str, url: str, events: list,
                          name: str = "", secret: str = "") -> dict:
        """Register an outbound webhook endpoint."""
        wid = f"whk_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO outbound_webhooks
                    (id, owner_id, name, url, events, secret, enabled)
                VALUES (?,?,?,?,?,?,1)
            """, (wid, owner_id, name or "Webhook", url,
                  json.dumps(events), secret))
        return {"id": wid, "url": url, "events": events, "enabled": True}

    def list_webhooks(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM outbound_webhooks WHERE owner_id=?",
                (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["events"] = json.loads(d.get("events", "[]"))
            result.append(d)
        return result

    def fire_event(self, owner_id: str, event_type: str, payload: dict) -> dict:
        """Fire an event to all matching webhooks (async in production)."""
        import requests as req
        with get_db() as db:
            hooks = db.execute(
                "SELECT * FROM outbound_webhooks WHERE owner_id=? AND enabled=1",
                (owner_id,)).fetchall()

        fired = 0
        errors = 0
        for hook in hooks:
            h = dict(hook)
            events = json.loads(h.get("events", "[]"))
            if event_type in events or "*" in events:
                try:
                    headers = {"Content-Type": "application/json",
                               "X-MT360-Event": event_type}
                    if h.get("secret"):
                        import hmac, hashlib
                        sig = hmac.new(h["secret"].encode(), json.dumps(payload).encode(),
                                       hashlib.sha256).hexdigest()
                        headers["X-MT360-Signature"] = sig
                    # In production: use celery/background task
                    req.post(h["url"], json={"event": event_type, "data": payload},
                            headers=headers, timeout=5)
                    fired += 1
                except Exception as e:
                    logger.error(f"Webhook fire error: {e}")
                    errors += 1
        return {"fired": fired, "errors": errors}

    def delete_webhook(self, webhook_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM outbound_webhooks WHERE id=?", (webhook_id,))
        return {"deleted": True}

    def toggle_webhook(self, webhook_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE outbound_webhooks SET enabled=CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id=?",
                (webhook_id,))
            row = db.execute("SELECT enabled FROM outbound_webhooks WHERE id=?",
                            (webhook_id,)).fetchone()
        return {"toggled": True, "enabled": bool(dict(row)["enabled"])}

    def get_event_types(self) -> list:
        return self.EVENT_TYPES


# ══════════════════════════════════════════════════════════════
# 2. TASK DEPENDENCIES
# ══════════════════════════════════════════════════════════════

class TaskDependencyManager:
    """Task A blocks Task B — B can't start until A is done."""

    def add_dependency(self, task_id: str, blocked_by: str) -> dict:
        """Task (task_id) is blocked by another task (blocked_by)."""
        if task_id == blocked_by:
            return {"error": "A task cannot block itself"}
        # Check circular
        if self._would_create_cycle(task_id, blocked_by):
            return {"error": "This would create a circular dependency"}
        did = f"dep_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT OR IGNORE INTO task_dependencies (id, task_id, blocked_by)
                VALUES (?,?,?)
            """, (did, task_id, blocked_by))
        return {"id": did, "task_id": task_id, "blocked_by": blocked_by}

    def remove_dependency(self, task_id: str, blocked_by: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM task_dependencies WHERE task_id=? AND blocked_by=?",
                      (task_id, blocked_by))
        return {"removed": True}

    def get_blockers(self, task_id: str) -> list:
        """What's blocking this task?"""
        with get_db() as db:
            rows = db.execute("""
                SELECT td.blocked_by, t.title, t.status
                FROM task_dependencies td
                JOIN tasks t ON td.blocked_by = t.id
                WHERE td.task_id=?
            """, (task_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_blocking(self, task_id: str) -> list:
        """What does this task block?"""
        with get_db() as db:
            rows = db.execute("""
                SELECT td.task_id, t.title, t.status
                FROM task_dependencies td
                JOIN tasks t ON td.task_id = t.id
                WHERE td.blocked_by=?
            """, (task_id,)).fetchall()
        return [dict(r) for r in rows]

    def is_blocked(self, task_id: str) -> dict:
        """Check if a task is currently blocked."""
        blockers = self.get_blockers(task_id)
        incomplete = [b for b in blockers if b.get("status") != "completed"]
        return {
            "blocked": len(incomplete) > 0,
            "incomplete_blockers": len(incomplete),
            "blockers": incomplete,
        }

    def _would_create_cycle(self, task_id: str, blocked_by: str) -> bool:
        visited = set()
        queue = [blocked_by]
        while queue:
            current = queue.pop(0)
            if current == task_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            with get_db() as db:
                deps = db.execute(
                    "SELECT blocked_by FROM task_dependencies WHERE task_id=?",
                    (current,)).fetchall()
            queue.extend(dict(d)["blocked_by"] for d in deps)
        return False


# ══════════════════════════════════════════════════════════════
# 3. RECURRING TASKS
# ══════════════════════════════════════════════════════════════

class RecurringTaskManager:
    """Tasks that repeat on a schedule."""

    FREQUENCIES = ["daily", "weekly", "biweekly", "monthly", "quarterly", "custom"]

    def create_recurring(self, owner_id: str, project_id: str, title: str,
                          frequency: str = "weekly", day_of_week: int = None,
                          day_of_month: int = None, custom_days: int = None,
                          priority: str = "medium", assigned_to: str = "") -> dict:
        rid = f"rec_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO recurring_tasks
                    (id, owner_id, project_id, title, frequency,
                     day_of_week, day_of_month, custom_interval_days,
                     priority, assigned_to, enabled)
                VALUES (?,?,?,?,?,?,?,?,?,?,1)
            """, (rid, owner_id, project_id, title, frequency,
                  day_of_week, day_of_month, custom_days,
                  priority, assigned_to))
        return {"id": rid, "title": title, "frequency": frequency, "enabled": True}

    def list_recurring(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM recurring_tasks WHERE owner_id=? ORDER BY title",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def generate_due_tasks(self, owner_id: str) -> dict:
        """Check all recurring tasks and create instances that are due."""
        from .tasks import TaskManager
        tm = TaskManager()
        created = 0
        with get_db() as db:
            recurrings = db.execute(
                "SELECT * FROM recurring_tasks WHERE owner_id=? AND enabled=1",
                (owner_id,)).fetchall()
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        for rec in recurrings:
            r = dict(rec)
            last = r.get("last_generated", "")
            should_generate = False
            if not last:
                should_generate = True
            else:
                last_date = datetime.fromisoformat(last)
                freq = r["frequency"]
                if freq == "daily" and (now - last_date).days >= 1:
                    should_generate = True
                elif freq == "weekly" and (now - last_date).days >= 7:
                    should_generate = True
                elif freq == "biweekly" and (now - last_date).days >= 14:
                    should_generate = True
                elif freq == "monthly" and (now - last_date).days >= 28:
                    should_generate = True
                elif freq == "quarterly" and (now - last_date).days >= 90:
                    should_generate = True
                elif freq == "custom" and r.get("custom_interval_days"):
                    if (now - last_date).days >= r["custom_interval_days"]:
                        should_generate = True

            if should_generate:
                tm.create_task(r["project_id"], owner_id, r["title"],
                              priority=r.get("priority", "medium"),
                              due_date=today,
                              assigned_to=r.get("assigned_to", ""))
                with get_db() as db:
                    db.execute("UPDATE recurring_tasks SET last_generated=? WHERE id=?",
                              (now.isoformat(), r["id"]))
                created += 1

        return {"generated": created}

    def toggle_recurring(self, rec_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE recurring_tasks SET enabled=CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id=?",
                (rec_id,))
        return {"toggled": True}

    def delete_recurring(self, rec_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM recurring_tasks WHERE id=?", (rec_id,))
        return {"deleted": True}


# ══════════════════════════════════════════════════════════════
# 4. LATE FEE AUTO-CALCULATION
# ══════════════════════════════════════════════════════════════

class LateFeeCalculator:
    """Auto-calculate late fees on overdue invoices."""

    def set_policy(self, owner_id: str, fee_type: str = "percentage",
                    fee_value: float = 1.5, grace_period_days: int = 5,
                    max_fee_pct: float = 25.0) -> dict:
        """Set late fee policy. fee_type: 'percentage' (monthly) or 'flat'."""
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO late_fee_policies
                    (owner_id, fee_type, fee_value, grace_period_days, max_fee_pct)
                VALUES (?,?,?,?,?)
            """, (owner_id, fee_type, fee_value, grace_period_days, max_fee_pct))
        return {"saved": True, "fee_type": fee_type, "fee_value": fee_value}

    def get_policy(self, owner_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM late_fee_policies WHERE owner_id=?",
                            (owner_id,)).fetchone()
        return dict(row) if row else {"fee_type": "percentage", "fee_value": 1.5,
                                       "grace_period_days": 5, "max_fee_pct": 25.0}

    def calculate_fees(self, owner_id: str) -> list:
        """Calculate late fees for all overdue invoices."""
        policy = self.get_policy(owner_id)
        today = datetime.now().strftime("%Y-%m-%d")
        grace = timedelta(days=policy.get("grace_period_days", 5))

        with get_db() as db:
            overdue = db.execute(
                "SELECT id, invoice_number, client_name, total, due_date FROM invoices "
                "WHERE owner_id=? AND status='sent' AND due_date<? AND due_date!=''",
                (owner_id, today)).fetchall()

        results = []
        for inv in overdue:
            d = dict(inv)
            due = datetime.strptime(d["due_date"], "%Y-%m-%d")
            grace_end = due + grace
            if datetime.now() <= grace_end:
                continue  # Still in grace period
            days_late = (datetime.now() - grace_end).days
            total = d.get("total", 0)
            if policy["fee_type"] == "percentage":
                months_late = max(1, days_late // 30 + 1)
                fee = total * (policy["fee_value"] / 100) * months_late
                max_fee = total * (policy.get("max_fee_pct", 25) / 100)
                fee = min(fee, max_fee)
            else:
                fee = policy["fee_value"]

            results.append({
                "invoice_id": d["id"],
                "invoice_number": d["invoice_number"],
                "client_name": d["client_name"],
                "original_total": total,
                "days_late": days_late,
                "late_fee": round(fee, 2),
                "total_with_fee": round(total + fee, 2),
            })
        return results


# ══════════════════════════════════════════════════════════════
# 5. DEMO / SAMPLE DATA
# ══════════════════════════════════════════════════════════════

class DemoDataGenerator:
    """Generate realistic sample data so new users can explore features."""

    def generate(self, owner_id: str) -> dict:
        """Populate the platform with realistic demo data."""
        from .crm import CRMManager
        from .tasks import TaskManager
        from .invoicing import InvoiceManager
        from .business_os import GoalTracker, ExpenseTracker

        crm = CRMManager()
        tm = TaskManager()
        im = InvoiceManager()
        gt = GoalTracker()
        et = ExpenseTracker()

        created = {"contacts": 0, "deals": 0, "tasks": 0,
                   "invoices": 0, "goals": 0, "expenses": 0}

        # Contacts
        demo_contacts = [
            {"name": "Sarah Johnson", "email": "sarah@acmecorp.com",
             "company": "Acme Corporation", "title": "VP of Marketing", "phone": "555-123-4567"},
            {"name": "Michael Chen", "email": "mchen@techstart.io",
             "company": "TechStart Inc", "title": "CTO", "phone": "555-234-5678"},
            {"name": "Lisa Rodriguez", "email": "lisa@greenleaf.com",
             "company": "GreenLeaf Partners", "title": "Managing Director"},
            {"name": "James Wilson", "email": "jwilson@bluecrest.com",
             "company": "BlueCrest Capital", "title": "Investment Analyst"},
            {"name": "Emily Davis", "email": "emily@brightpath.co",
             "company": "BrightPath Consulting", "title": "Founder"},
        ]
        contact_ids = []
        for c in demo_contacts:
            result = crm.create_contact(owner_id, c["name"], email=c.get("email"),
                company=c.get("company"), title=c.get("title"), phone=c.get("phone"))
            contact_ids.append(result["id"])
            created["contacts"] += 1

        # Deals
        demo_deals = [
            {"title": "Acme Enterprise Contract", "value": 75000, "stage": "proposal",
             "contact": 0},
            {"title": "TechStart Platform License", "value": 25000, "stage": "qualified",
             "contact": 1},
            {"title": "GreenLeaf Annual Retainer", "value": 120000, "stage": "negotiation",
             "contact": 2},
            {"title": "BlueCrest Analytics Package", "value": 15000, "stage": "demo",
             "contact": 3},
            {"title": "BrightPath Consulting SOW", "value": 45000, "stage": "closed_won",
             "contact": 4},
        ]
        for d in demo_deals:
            crm.create_deal(owner_id, d["title"], value=d["value"], stage=d["stage"],
                           contact_id=contact_ids[d["contact"]])
            created["deals"] += 1

        # Activities
        for i, cid in enumerate(contact_ids[:3]):
            crm.log_activity(owner_id, "call", f"Intro call with {demo_contacts[i]['name']}",
                            contact_id=cid)
            crm.log_activity(owner_id, "email", "Sent proposal", contact_id=cid)

        # Tasks
        proj = tm.create_project(owner_id, "Q2 Launch Plan", template="product_launch")
        tm.create_task(proj["id"], owner_id, "Follow up with Sarah on contract",
                      priority="high", due_date=datetime.now().strftime("%Y-%m-%d"))
        tm.create_task(proj["id"], owner_id, "Prepare demo for TechStart",
                      priority="high", due_date=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"))
        tm.create_task(proj["id"], owner_id, "Send revised proposal to GreenLeaf",
                      priority="medium")
        created["tasks"] = 3 + proj.get("tasks_created", 0)

        # Invoices
        im.set_business_profile(owner_id, "Demo Business", email="demo@myteam360.ai",
                                default_payment_terms=30)
        im.create_invoice(owner_id, "BrightPath Consulting", line_items=[
            {"description": "Strategy Consulting — Phase 1", "quantity": 1, "unit_price": 25000},
            {"description": "Implementation Support", "quantity": 40, "unit_price": 250},
        ])
        im.create_invoice(owner_id, "Acme Corporation", line_items=[
            {"description": "Platform License — Annual", "quantity": 1, "unit_price": 75000},
        ])
        created["invoices"] = 2

        # Goals
        gt.create_goal(owner_id, "Hit $250K Revenue in Q2", target_value=250000,
                      target_unit="USD", category="revenue",
                      due_date=(datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d"))
        gt.create_goal(owner_id, "Close 15 New Deals", target_value=15,
                      category="sales",
                      due_date=(datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"))
        created["goals"] = 2

        # Expenses
        et.add_expense(owner_id, "AWS Hosting", 450, category="hosting", vendor="Amazon")
        et.add_expense(owner_id, "Zoom Pro", 15.99, category="software", vendor="Zoom")
        et.add_expense(owner_id, "Client Lunch — Sarah J", 85, category="meals", vendor="Carbone")
        created["expenses"] = 3

        # Mark as demo
        with get_db() as db:
            db.execute("INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?,?)",
                      (f"demo_data_{owner_id}", "true"))

        return {
            "generated": True,
            "created": created,
            "message": "Demo data loaded! Explore the CRM, tasks, invoices, and more.",
        }

    def clear_demo(self, owner_id: str) -> dict:
        """Remove all demo data (careful!)."""
        with get_db() as db:
            # Only clear if demo was generated
            check = db.execute(
                "SELECT value FROM workspace_settings WHERE key=?",
                (f"demo_data_{owner_id}",)).fetchone()
            if not check:
                return {"error": "No demo data found"}
            # Clear all user data
            for table in ["crm_contacts", "crm_deals", "crm_activities",
                         "tasks", "task_projects", "invoices",
                         "goals", "expenses"]:
                db.execute(f"DELETE FROM {table} WHERE owner_id=?", (owner_id,))
            db.execute("DELETE FROM workspace_settings WHERE key=?",
                      (f"demo_data_{owner_id}",))
        return {"cleared": True}


# ══════════════════════════════════════════════════════════════
# 6. DARK MODE PREFERENCE
# ══════════════════════════════════════════════════════════════

class ThemePreference:
    """Store and retrieve dark/light mode + accent color preferences."""

    THEMES = {
        "light": {"background": "#FFFFFF", "surface": "#F9FAFB", "text": "#111827",
                  "text_secondary": "#6B7280", "border": "#E5E7EB"},
        "dark": {"background": "#0F172A", "surface": "#1E293B", "text": "#F1F5F9",
                 "text_secondary": "#94A3B8", "border": "#334155"},
        "auto": {},  # Follows OS preference
    }

    def set_theme(self, owner_id: str, theme: str = "light",
                   accent_color: str = "#A459F2") -> dict:
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO workspace_settings (key, value)
                VALUES (?, ?)
            """, (f"theme_{owner_id}", json.dumps({
                "theme": theme, "accent_color": accent_color})))
        return {"theme": theme, "accent_color": accent_color}

    def get_theme(self, owner_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT value FROM workspace_settings WHERE key=?",
                (f"theme_{owner_id}",)).fetchone()
        if row:
            prefs = json.loads(dict(row)["value"])
            theme_name = prefs.get("theme", "light")
            base = self.THEMES.get(theme_name, self.THEMES["light"])
            return {**prefs, "colors": base}
        return {"theme": "light", "accent_color": "#A459F2",
                "colors": self.THEMES["light"]}


# ══════════════════════════════════════════════════════════════
# 7. CONTEXTUAL TOOLTIPS / HELP SYSTEM
# ══════════════════════════════════════════════════════════════

HELP_TOOLTIPS = {
    "dashboard": {
        "title": "Your Command Center",
        "description": "See everything at a glance — briefing, reminders, pipeline, tasks.",
        "tips": ["Your daily briefing adapts to the day of the week",
                 "Quick Capture lets you log anything by voice or text"],
    },
    "crm": {
        "title": "CRM — Customer Relationship Manager",
        "description": "Track contacts, deals, companies, and activities in one place.",
        "tips": ["Use the health score to spot contacts going cold",
                 "Pin your VIP contacts to favorites for quick access",
                 "The AI can build a full context brief before any call"],
    },
    "tasks": {
        "title": "Task & Project Board",
        "description": "Kanban boards, subtasks, time tracking, and templates.",
        "tips": ["Drag tasks between columns to update status",
                 "Use dependencies to mark tasks as 'blocked by'",
                 "Set up recurring tasks for weekly reviews"],
    },
    "invoicing": {
        "title": "Invoicing & Proposals",
        "description": "Create professional invoices, track payments, manage proposals.",
        "tips": ["Set up your business profile first for branded invoices",
                 "Late fees auto-calculate based on your policy",
                 "Export invoices as PDF to send to clients"],
    },
    "social_media": {
        "title": "Social Media Manager",
        "description": "Plan campaigns, schedule posts, track engagement across platforms.",
        "tips": ["Use Content Repurpose to turn one post into 5 platforms",
                 "Bulk schedule a week of posts in one go",
                 "Hashtag groups save time on repetitive tags"],
    },
    "goals": {
        "title": "Goals & OKRs",
        "description": "Set objectives, track key results, measure progress.",
        "tips": ["Link goals to deals for automatic progress tracking",
                 "Your briefing will warn you when goals are at risk"],
    },
    "booking": {
        "title": "Booking Links",
        "description": "Share a link so people can book time with you.",
        "tips": ["Connects to your calendar to show real availability",
                 "Add custom questions to qualify meetings before they happen"],
    },
    "quick_capture": {
        "title": "Quick Capture",
        "description": "Say or type anything — the AI routes it to the right place.",
        "tips": ["'Just talked to Sarah about the 450K deal' → CRM updated automatically",
                 "'Need to send proposal by Friday' → Task created",
                 "'Spent $45 on gas for showings' → Expense logged"],
    },
    "automations": {
        "title": "Workflow Automation",
        "description": "When X happens, automatically do Y.",
        "tips": ["Deal Won → auto-send thank you email + create invoice",
                 "New Lead → welcome email + follow-up task in 3 days",
                 "Use templates to set up common workflows instantly"],
    },
}


class HelpSystem:
    """Contextual help + tooltips for every feature."""

    def get_tooltip(self, feature: str) -> dict:
        return HELP_TOOLTIPS.get(feature, {
            "title": feature.replace("_", " ").title(),
            "description": "Help content for this feature.",
            "tips": [],
        })

    def get_all_tooltips(self) -> dict:
        return HELP_TOOLTIPS

    def search_help(self, query: str) -> list:
        q = query.lower()
        results = []
        for key, tip in HELP_TOOLTIPS.items():
            if (q in tip["title"].lower() or
                q in tip["description"].lower() or
                any(q in t.lower() for t in tip.get("tips", []))):
                results.append({"feature": key, **tip})
        return results


# ══════════════════════════════════════════════════════════════
# 8. WHATSAPP MESSAGE LOG
# ══════════════════════════════════════════════════════════════

class WhatsAppLog:
    """Manual log of WhatsApp conversations.
    Same pattern as TextMessageLog — we NEVER integrate with their phone."""

    def log_message(self, owner_id: str, contact_id: str = "",
                     contact_name: str = "", phone_number: str = "",
                     direction: str = "outbound", content: str = "",
                     has_media: bool = False, notes: str = "") -> dict:
        wid = f"wa_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO whatsapp_log
                    (id, owner_id, contact_id, contact_name, phone_number,
                     direction, content, has_media, notes)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (wid, owner_id, contact_id, contact_name, phone_number,
                  direction, content[:2000], 1 if has_media else 0, notes))
            if contact_id:
                db.execute("""
                    INSERT INTO crm_activities
                        (id, owner_id, contact_id, activity_type, subject, notes, completed)
                    VALUES (?,?,?,?,?,?,1)
                """, (f"act_{uuid.uuid4().hex[:8]}", owner_id, contact_id,
                      "whatsapp",
                      f"{'Sent' if direction == 'outbound' else 'Received'} WhatsApp: {content[:50]}",
                      content))
        return {"id": wid, "logged": True, "crm_synced": bool(contact_id)}

    def get_log(self, owner_id: str, contact_id: str = "",
                 limit: int = 50) -> list:
        with get_db() as db:
            if contact_id:
                rows = db.execute(
                    "SELECT * FROM whatsapp_log WHERE owner_id=? AND contact_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (owner_id, contact_id, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM whatsapp_log WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, limit)).fetchall()
        return [dict(r) for r in rows]
