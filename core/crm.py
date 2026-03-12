# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
CRM / Deal Tracker — Lightweight AI-powered customer relationship management.

Replaces: HubSpot Free, Salesforce Essentials, Pipedrive
Cost to user if using those: $50-$300/month

Features:
  - Contacts with custom fields, tags, notes
  - Companies with contact associations
  - Deal pipeline with customizable stages
  - Activity log (calls, emails, meetings, notes)
  - Follow-up reminders (never forget to call back)
  - AI lead scoring (based on engagement signals)
  - AI email drafting ("draft follow-up for this contact")
  - Search across all contacts, companies, deals
  - Import/export CSV
  - Dashboard: pipeline value, conversion rate, stale deals
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.crm")


# ── Default Pipeline ──

DEFAULT_STAGES = [
    {"id": "lead", "label": "Lead", "color": "#94a3b8", "order": 0},
    {"id": "qualified", "label": "Qualified", "color": "#3b82f6", "order": 1},
    {"id": "proposal", "label": "Proposal Sent", "color": "#a459f2", "order": 2},
    {"id": "negotiation", "label": "Negotiation", "color": "#f59e0b", "order": 3},
    {"id": "closed_won", "label": "Closed Won", "color": "#22c55e", "order": 4},
    {"id": "closed_lost", "label": "Closed Lost", "color": "#ef4444", "order": 5},
]


class CRMManager:
    """Lightweight CRM with AI integration."""

    # ── Contacts ──

    def create_contact(self, owner_id: str, name: str, email: str = "",
                        phone: str = "", company: str = "", title: str = "",
                        source: str = "", tags: list = None,
                        custom_fields: dict = None, notes: str = "") -> dict:
        cid = f"contact_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO crm_contacts
                    (id, owner_id, name, email, phone, company, title,
                     source, tags, custom_fields, notes, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, owner_id, name, email, phone, company, title,
                  source, json.dumps(tags or []),
                  json.dumps(custom_fields or {}), notes, "active"))
        return {"id": cid, "name": name, "email": email}

    def get_contact(self, contact_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM crm_contacts WHERE id=?",
                            (contact_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d.get("tags", "[]"))
        d["custom_fields"] = json.loads(d.get("custom_fields", "{}"))
        return d

    def list_contacts(self, owner_id: str, search: str = "",
                       tag: str = "", limit: int = 50) -> list:
        with get_db() as db:
            if search:
                rows = db.execute("""
                    SELECT * FROM crm_contacts WHERE owner_id=?
                    AND (name LIKE ? OR email LIKE ? OR company LIKE ?)
                    ORDER BY updated_at DESC LIMIT ?
                """, (owner_id, f"%{search}%", f"%{search}%",
                      f"%{search}%", limit)).fetchall()
            elif tag:
                rows = db.execute("""
                    SELECT * FROM crm_contacts WHERE owner_id=?
                    AND tags LIKE ? ORDER BY updated_at DESC LIMIT ?
                """, (owner_id, f"%{tag}%", limit)).fetchall()
            else:
                rows = db.execute("""
                    SELECT * FROM crm_contacts WHERE owner_id=?
                    ORDER BY updated_at DESC LIMIT ?
                """, (owner_id, limit)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.get("tags", "[]"))
            d["custom_fields"] = json.loads(d.get("custom_fields", "{}"))
            result.append(d)
        return result

    def update_contact(self, contact_id: str, **updates) -> dict:
        if "tags" in updates:
            updates["tags"] = json.dumps(updates["tags"])
        if "custom_fields" in updates:
            updates["custom_fields"] = json.dumps(updates["custom_fields"])
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [contact_id]
        with get_db() as db:
            db.execute(f"UPDATE crm_contacts SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def delete_contact(self, contact_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM crm_contacts WHERE id=?", (contact_id,))
        return {"deleted": True}

    # ── Companies ──

    def create_company(self, owner_id: str, name: str, domain: str = "",
                        industry: str = "", size: str = "",
                        notes: str = "") -> dict:
        cid = f"company_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO crm_companies
                    (id, owner_id, name, domain, industry, size, notes)
                VALUES (?,?,?,?,?,?,?)
            """, (cid, owner_id, name, domain, industry, size, notes))
        return {"id": cid, "name": name}

    def list_companies(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM crm_companies WHERE owner_id=? ORDER BY name",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_company(self, company_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM crm_companies WHERE id=?",
                            (company_id,)).fetchone()
        return dict(row) if row else None

    # ── Deals ──

    def create_deal(self, owner_id: str, title: str, value: float = 0,
                     contact_id: str = "", company_id: str = "",
                     stage: str = "lead", expected_close: str = "",
                     notes: str = "") -> dict:
        did = f"deal_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO crm_deals
                    (id, owner_id, title, value, contact_id, company_id,
                     stage, expected_close, notes, status)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (did, owner_id, title, value, contact_id, company_id,
                  stage, expected_close, notes, "open"))
        return {"id": did, "title": title, "value": value, "stage": stage}

    def list_deals(self, owner_id: str, stage: str = None,
                    status: str = "open") -> list:
        where = ["owner_id=?"]
        params = [owner_id]
        if stage:
            where.append("stage=?")
            params.append(stage)
        if status:
            where.append("status=?")
            params.append(status)
        with get_db() as db:
            rows = db.execute(
                f"SELECT * FROM crm_deals WHERE {' AND '.join(where)} "
                "ORDER BY updated_at DESC", params).fetchall()
        return [dict(r) for r in rows]

    def update_deal(self, deal_id: str, **updates) -> dict:
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [deal_id]
        with get_db() as db:
            db.execute(f"UPDATE crm_deals SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def move_deal(self, deal_id: str, new_stage: str) -> dict:
        """Move a deal to a new pipeline stage."""
        return self.update_deal(deal_id, stage=new_stage)

    def delete_deal(self, deal_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM crm_deals WHERE id=?", (deal_id,))
        return {"deleted": True}

    # ── Activities ──

    def log_activity(self, owner_id: str, activity_type: str, subject: str,
                      contact_id: str = "", deal_id: str = "",
                      notes: str = "", due_date: str = "") -> dict:
        """Log an activity: call, email, meeting, note, task."""
        aid = f"act_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO crm_activities
                    (id, owner_id, activity_type, subject, contact_id,
                     deal_id, notes, due_date, completed)
                VALUES (?,?,?,?,?,?,?,?,0)
            """, (aid, owner_id, activity_type, subject, contact_id,
                  deal_id, notes, due_date))
        return {"id": aid, "type": activity_type, "subject": subject}

    def list_activities(self, owner_id: str, contact_id: str = "",
                         deal_id: str = "", limit: int = 50) -> list:
        where = ["owner_id=?"]
        params = [owner_id]
        if contact_id:
            where.append("contact_id=?")
            params.append(contact_id)
        if deal_id:
            where.append("deal_id=?")
            params.append(deal_id)
        params.append(limit)
        with get_db() as db:
            rows = db.execute(
                f"SELECT * FROM crm_activities WHERE {' AND '.join(where)} "
                "ORDER BY created_at DESC LIMIT ?", params).fetchall()
        return [dict(r) for r in rows]

    def complete_activity(self, activity_id: str) -> dict:
        with get_db() as db:
            db.execute("UPDATE crm_activities SET completed=1 WHERE id=?",
                      (activity_id,))
        return {"completed": True}

    # ── Follow-up Reminders ──

    def get_follow_ups(self, owner_id: str) -> list:
        """Get all overdue and upcoming follow-ups."""
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db() as db:
            rows = db.execute("""
                SELECT a.*, c.name as contact_name, c.email as contact_email,
                       d.title as deal_title
                FROM crm_activities a
                LEFT JOIN crm_contacts c ON a.contact_id = c.id
                LEFT JOIN crm_deals d ON a.deal_id = d.id
                WHERE a.owner_id=? AND a.completed=0
                    AND a.due_date != '' AND a.due_date <= ?
                ORDER BY a.due_date
            """, (owner_id, today)).fetchall()
        return [dict(r) for r in rows]

    def get_stale_deals(self, owner_id: str, days: int = 14) -> list:
        """Deals with no activity in N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM crm_deals
                WHERE owner_id=? AND status='open' AND updated_at < ?
                ORDER BY updated_at
            """, (owner_id, cutoff)).fetchall()
        return [dict(r) for r in rows]

    # ── Pipeline Dashboard ──

    def get_pipeline(self, owner_id: str) -> dict:
        """Pipeline summary: deals by stage with total values."""
        with get_db() as db:
            by_stage = db.execute("""
                SELECT stage, COUNT(*) as count, COALESCE(SUM(value),0) as total_value
                FROM crm_deals WHERE owner_id=? AND status='open'
                GROUP BY stage
            """, (owner_id,)).fetchall()

            won = db.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(value),0) as total_value
                FROM crm_deals WHERE owner_id=? AND stage='closed_won'
            """, (owner_id,)).fetchone()

            lost = db.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(value),0) as total_value
                FROM crm_deals WHERE owner_id=? AND stage='closed_lost'
            """, (owner_id,)).fetchone()

            total_contacts = db.execute(
                "SELECT COUNT(*) as c FROM crm_contacts WHERE owner_id=?",
                (owner_id,)).fetchone()

            total_companies = db.execute(
                "SELECT COUNT(*) as c FROM crm_companies WHERE owner_id=?",
                (owner_id,)).fetchone()

        stages = {dict(r)["stage"]: {"count": dict(r)["count"],
                  "value": round(dict(r)["total_value"], 2)} for r in by_stage}
        pipeline_value = sum(s["value"] for s in stages.values())
        won_d = dict(won)
        lost_d = dict(lost)
        total_closed = won_d["count"] + lost_d["count"]
        win_rate = round(won_d["count"] / total_closed * 100, 1) if total_closed else 0

        return {
            "stages": DEFAULT_STAGES,
            "pipeline": stages,
            "pipeline_value": round(pipeline_value, 2),
            "won": {"count": won_d["count"], "value": round(won_d["total_value"], 2)},
            "lost": {"count": lost_d["count"], "value": round(lost_d["total_value"], 2)},
            "win_rate": win_rate,
            "total_contacts": dict(total_contacts)["c"],
            "total_companies": dict(total_companies)["c"],
            "stale_deals": len(self.get_stale_deals(owner_id)),
            "follow_ups_due": len(self.get_follow_ups(owner_id)),
        }

    # ── AI Integration ──

    def build_contact_context(self, contact_id: str) -> str:
        """Build AI context for a contact — everything we know about them."""
        contact = self.get_contact(contact_id)
        if not contact:
            return ""

        activities = self.list_activities(contact.get("owner_id", ""),
                                          contact_id=contact_id, limit=10)

        parts = [
            f"Contact: {contact['name']}",
            f"Email: {contact.get('email', 'N/A')}",
            f"Company: {contact.get('company', 'N/A')}",
            f"Title: {contact.get('title', 'N/A')}",
            f"Tags: {', '.join(contact.get('tags', []))}",
        ]
        if contact.get("notes"):
            parts.append(f"Notes: {contact['notes'][:300]}")

        if activities:
            parts.append("\nRecent activity:")
            for a in activities[:5]:
                parts.append(f"  - [{a['activity_type']}] {a['subject']} "
                            f"({a.get('created_at', '')[:10]})")

        return "\n".join(parts)

    def build_deal_context(self, deal_id: str) -> str:
        """Build AI context for a deal."""
        with get_db() as db:
            deal = db.execute("SELECT * FROM crm_deals WHERE id=?",
                             (deal_id,)).fetchone()
        if not deal:
            return ""
        d = dict(deal)
        return (
            f"Deal: {d['title']}\n"
            f"Value: ${d.get('value', 0):,.2f}\n"
            f"Stage: {d.get('stage', 'lead')}\n"
            f"Expected close: {d.get('expected_close', 'TBD')}\n"
            f"Notes: {d.get('notes', '')[:300]}"
        )
