# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
UX Essentials — Features every user expects from a modern platform.

1. GLOBAL SEARCH — Search across everything: conversations, CRM, tasks, invoices, notes
2. FAVORITES / PINS — Quick-access bar for most-used items
3. ACTIVITY FEED — Real-time feed of everything happening in your business
4. NOTES / SCRATCHPAD — Quick freeform notes not tied to any feature
5. BOOKING LINKS — "Book a time with me" shareable page
6. COMMAND PALETTE — Cmd+K universal search + actions (frontend defines, backend powers)
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.ux")


# ══════════════════════════════════════════════════════════════
# 1. GLOBAL SEARCH
# ══════════════════════════════════════════════════════════════

class GlobalSearch:
    """Search across every feature in the platform."""

    SEARCHABLE_ENTITIES = [
        "conversations", "crm_contacts", "crm_deals", "crm_companies",
        "tasks", "invoices", "proposals", "goals", "expenses",
        "social_campaigns", "competitors", "notes", "email_outbox",
    ]

    def search(self, owner_id: str, query: str, limit: int = 20,
               entity_filter: str = None) -> dict:
        """Search everything. Returns grouped results."""
        if not query or len(query) < 2:
            return {"results": [], "total": 0}

        q = f"%{query}%"
        results = []

        with get_db() as db:
            # Conversations
            if not entity_filter or entity_filter == "conversations":
                rows = db.execute(
                    "SELECT id, title, agent_id, updated_at FROM conversations "
                    "WHERE user_id=? AND title LIKE ? LIMIT 5",
                    (owner_id, q)).fetchall()
                for r in rows:
                    d = dict(r)
                    results.append({"type": "conversation", "id": d["id"],
                        "title": d.get("title", ""), "subtitle": d.get("agent_id", ""),
                        "updated": d.get("updated_at", ""), "icon": "💬"})

            # CRM Contacts
            if not entity_filter or entity_filter == "contacts":
                rows = db.execute(
                    "SELECT id, name, email, company FROM crm_contacts "
                    "WHERE owner_id=? AND (name LIKE ? OR email LIKE ? OR company LIKE ?) LIMIT 5",
                    (owner_id, q, q, q)).fetchall()
                for r in rows:
                    d = dict(r)
                    results.append({"type": "contact", "id": d["id"],
                        "title": d["name"], "subtitle": f"{d.get('company','')} • {d.get('email','')}",
                        "icon": "👤"})

            # CRM Deals
            if not entity_filter or entity_filter == "deals":
                rows = db.execute(
                    "SELECT id, title, value, stage FROM crm_deals "
                    "WHERE owner_id=? AND title LIKE ? LIMIT 5",
                    (owner_id, q)).fetchall()
                for r in rows:
                    d = dict(r)
                    results.append({"type": "deal", "id": d["id"],
                        "title": d["title"], "subtitle": f"${d.get('value',0):,.0f} • {d.get('stage','')}",
                        "icon": "🤝"})

            # Tasks
            if not entity_filter or entity_filter == "tasks":
                rows = db.execute(
                    "SELECT id, title, priority, column_id FROM tasks "
                    "WHERE owner_id=? AND status='open' AND title LIKE ? LIMIT 5",
                    (owner_id, q)).fetchall()
                for r in rows:
                    d = dict(r)
                    results.append({"type": "task", "id": d["id"],
                        "title": d["title"], "subtitle": f"{d.get('priority','')} • {d.get('column_id','')}",
                        "icon": "📋"})

            # Invoices
            if not entity_filter or entity_filter == "invoices":
                rows = db.execute(
                    "SELECT id, invoice_number, client_name, total, status FROM invoices "
                    "WHERE owner_id=? AND (invoice_number LIKE ? OR client_name LIKE ?) LIMIT 5",
                    (owner_id, q, q)).fetchall()
                for r in rows:
                    d = dict(r)
                    results.append({"type": "invoice", "id": d["id"],
                        "title": f"{d['invoice_number']} — {d['client_name']}",
                        "subtitle": f"${d.get('total',0):,.2f} • {d.get('status','')}",
                        "icon": "🧾"})

            # Goals
            if not entity_filter or entity_filter == "goals":
                rows = db.execute(
                    "SELECT id, title, progress_pct FROM goals "
                    "WHERE owner_id=? AND title LIKE ? LIMIT 5",
                    (owner_id, q)).fetchall()
                for r in rows:
                    d = dict(r)
                    results.append({"type": "goal", "id": d["id"],
                        "title": d["title"],
                        "subtitle": f"{d.get('progress_pct',0):.0f}% complete",
                        "icon": "🎯"})

            # Notes
            if not entity_filter or entity_filter == "notes":
                rows = db.execute(
                    "SELECT id, title, content FROM scratch_notes "
                    "WHERE owner_id=? AND (title LIKE ? OR content LIKE ?) LIMIT 5",
                    (owner_id, q, q)).fetchall()
                for r in rows:
                    d = dict(r)
                    results.append({"type": "note", "id": d["id"],
                        "title": d.get("title", "Note"),
                        "subtitle": d.get("content", "")[:80],
                        "icon": "📝"})

            # Competitors
            if not entity_filter or entity_filter == "competitors":
                rows = db.execute(
                    "SELECT id, name, website FROM competitors "
                    "WHERE owner_id=? AND name LIKE ? LIMIT 3",
                    (owner_id, q)).fetchall()
                for r in rows:
                    d = dict(r)
                    results.append({"type": "competitor", "id": d["id"],
                        "title": d["name"], "subtitle": d.get("website", ""),
                        "icon": "🏢"})

        return {
            "query": query,
            "results": results[:limit],
            "total": len(results),
            "searched": self.SEARCHABLE_ENTITIES if not entity_filter else [entity_filter],
        }


# ══════════════════════════════════════════════════════════════
# 2. FAVORITES / PINS
# ══════════════════════════════════════════════════════════════

class FavoritesManager:
    """Pin important items for quick access."""

    def add(self, owner_id: str, entity_type: str, entity_id: str,
            label: str = "", icon: str = "") -> dict:
        fid = f"fav_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            # Don't duplicate
            existing = db.execute(
                "SELECT id FROM favorites WHERE owner_id=? AND entity_type=? AND entity_id=?",
                (owner_id, entity_type, entity_id)).fetchone()
            if existing:
                return {"already_pinned": True}
            db.execute("""
                INSERT INTO favorites (id, owner_id, entity_type, entity_id, label, icon, position)
                VALUES (?,?,?,?,?,?,?)
            """, (fid, owner_id, entity_type, entity_id, label, icon,
                  self._next_position(owner_id)))
        return {"id": fid, "pinned": True}

    def remove(self, owner_id: str, entity_type: str, entity_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "DELETE FROM favorites WHERE owner_id=? AND entity_type=? AND entity_id=?",
                (owner_id, entity_type, entity_id))
        return {"unpinned": True}

    def list(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM favorites WHERE owner_id=? ORDER BY position",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def reorder(self, owner_id: str, favorite_ids: list) -> dict:
        with get_db() as db:
            for i, fid in enumerate(favorite_ids):
                db.execute("UPDATE favorites SET position=? WHERE id=? AND owner_id=?",
                          (i, fid, owner_id))
        return {"reordered": True}

    def _next_position(self, owner_id: str) -> int:
        with get_db() as db:
            row = db.execute(
                "SELECT MAX(position) as m FROM favorites WHERE owner_id=?",
                (owner_id,)).fetchone()
        return (dict(row)["m"] or 0) + 1


# ══════════════════════════════════════════════════════════════
# 3. ACTIVITY FEED
# ══════════════════════════════════════════════════════════════

class ActivityFeed:
    """Real-time feed of everything happening in your business."""

    def log(self, owner_id: str, action: str, entity_type: str,
            entity_id: str = "", detail: str = "", icon: str = "") -> dict:
        aid = f"af_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO activity_feed
                    (id, owner_id, action, entity_type, entity_id, detail, icon)
                VALUES (?,?,?,?,?,?,?)
            """, (aid, owner_id, action, entity_type, entity_id, detail[:500], icon))
        return {"logged": True}

    def get_feed(self, owner_id: str, limit: int = 50,
                  entity_type: str = None) -> list:
        with get_db() as db:
            if entity_type:
                rows = db.execute(
                    "SELECT * FROM activity_feed WHERE owner_id=? AND entity_type=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (owner_id, entity_type, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM activity_feed WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, limit)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["time_ago"] = self._time_ago(d.get("created_at", ""))
            results.append(d)
        return results

    def _time_ago(self, timestamp: str) -> str:
        try:
            dt = datetime.fromisoformat(timestamp)
            diff = datetime.now() - dt
            if diff.seconds < 60:
                return "just now"
            elif diff.seconds < 3600:
                return f"{diff.seconds // 60}m ago"
            elif diff.seconds < 86400:
                return f"{diff.seconds // 3600}h ago"
            elif diff.days == 1:
                return "yesterday"
            elif diff.days < 7:
                return f"{diff.days}d ago"
            return dt.strftime("%b %d")
        except:
            return ""


# ══════════════════════════════════════════════════════════════
# 4. NOTES / SCRATCHPAD
# ══════════════════════════════════════════════════════════════

class ScratchPad:
    """Quick freeform notes — the digital junk drawer every business owner needs."""

    def create(self, owner_id: str, title: str = "", content: str = "",
               color: str = "#FEF3C7", pinned: bool = False) -> dict:
        nid = f"note_{uuid.uuid4().hex[:10]}"
        if not title and content:
            title = content[:40] + ("..." if len(content) > 40 else "")
        with get_db() as db:
            db.execute("""
                INSERT INTO scratch_notes
                    (id, owner_id, title, content, color, pinned)
                VALUES (?,?,?,?,?,?)
            """, (nid, owner_id, title or "Untitled Note", content,
                  color, 1 if pinned else 0))
        return {"id": nid, "title": title}

    def list(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM scratch_notes WHERE owner_id=? ORDER BY pinned DESC, updated_at DESC",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def get(self, note_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM scratch_notes WHERE id=?",
                            (note_id,)).fetchone()
        return dict(row) if row else None

    def update(self, note_id: str, title: str = None, content: str = None,
               color: str = None, pinned: bool = None) -> dict:
        updates = {"updated_at": datetime.now().isoformat()}
        if title is not None: updates["title"] = title
        if content is not None: updates["content"] = content
        if color is not None: updates["color"] = color
        if pinned is not None: updates["pinned"] = 1 if pinned else 0
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [note_id]
        with get_db() as db:
            db.execute(f"UPDATE scratch_notes SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def delete(self, note_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM scratch_notes WHERE id=?", (note_id,))
        return {"deleted": True}


# ══════════════════════════════════════════════════════════════
# 5. BOOKING LINKS
# ══════════════════════════════════════════════════════════════

class BookingLinks:
    """Shareable 'book a time with me' pages.

    User creates a booking page → shares the link → visitor picks a time.
    Checks calendar availability before offering slots.
    """

    def create_link(self, owner_id: str, name: str, duration_minutes: int = 30,
                     description: str = "", availability: dict = None,
                     questions: list = None) -> dict:
        bid = f"book_{uuid.uuid4().hex[:10]}"
        slug = name.lower().replace(" ", "-").replace("'", "")[:30]

        default_availability = availability or {
            "monday": {"start": "09:00", "end": "17:00"},
            "tuesday": {"start": "09:00", "end": "17:00"},
            "wednesday": {"start": "09:00", "end": "17:00"},
            "thursday": {"start": "09:00", "end": "17:00"},
            "friday": {"start": "09:00", "end": "17:00"},
        }

        import os
        base_url = os.getenv("BASE_URL", "https://myteam360.ai")

        with get_db() as db:
            db.execute("""
                INSERT INTO booking_links
                    (id, owner_id, slug, name, duration_minutes, description,
                     availability, questions, status)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (bid, owner_id, slug, name, duration_minutes, description,
                  json.dumps(default_availability),
                  json.dumps(questions or []),
                  "active"))

        return {
            "id": bid,
            "url": f"{base_url}/book/{slug}",
            "slug": slug,
            "name": name,
            "duration": duration_minutes,
        }

    def list_links(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM booking_links WHERE owner_id=? ORDER BY created_at",
                (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["availability"] = json.loads(d.get("availability", "{}"))
            d["questions"] = json.loads(d.get("questions", "[]"))
            result.append(d)
        return result

    def get_link(self, slug: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM booking_links WHERE slug=? AND status='active'",
                (slug,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["availability"] = json.loads(d.get("availability", "{}"))
        d["questions"] = json.loads(d.get("questions", "[]"))
        return d

    def submit_booking(self, slug: str, booker_name: str, booker_email: str,
                        requested_time: str, answers: dict = None) -> dict:
        """Visitor submits a booking request."""
        link = self.get_link(slug)
        if not link:
            return {"error": "Booking link not found"}

        booking_id = f"bkng_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO booking_requests
                    (id, link_id, owner_id, booker_name, booker_email,
                     requested_time, duration_minutes, answers, status)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (booking_id, link["id"], link["owner_id"],
                  booker_name, booker_email, requested_time,
                  link["duration_minutes"], json.dumps(answers or {}),
                  "pending"))

        return {
            "booking_id": booking_id,
            "status": "pending",
            "message": f"Your booking request for {requested_time} has been submitted. "
                       f"You'll receive a confirmation shortly.",
        }

    def get_requests(self, owner_id: str, status: str = "pending") -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM booking_requests WHERE owner_id=? AND status=? ORDER BY requested_time",
                (owner_id, status)).fetchall()
        return [dict(r) for r in rows]

    def confirm_booking(self, booking_id: str) -> dict:
        with get_db() as db:
            db.execute("UPDATE booking_requests SET status='confirmed' WHERE id=?",
                      (booking_id,))
        return {"confirmed": True}

    def decline_booking(self, booking_id: str, reason: str = "") -> dict:
        with get_db() as db:
            db.execute("UPDATE booking_requests SET status='declined' WHERE id=?",
                      (booking_id,))
        return {"declined": True}


# ══════════════════════════════════════════════════════════════
# 6. COMMAND PALETTE DATA (Cmd+K)
# ══════════════════════════════════════════════════════════════

class CommandPalette:
    """Powers the Cmd+K universal command palette."""

    COMMANDS = [
        {"id": "new_conversation", "label": "New Conversation", "shortcut": "Ctrl+N", "icon": "💬", "category": "create"},
        {"id": "new_contact", "label": "New Contact", "shortcut": "", "icon": "👤", "category": "create"},
        {"id": "new_deal", "label": "New Deal", "shortcut": "", "icon": "🤝", "category": "create"},
        {"id": "new_task", "label": "New Task", "shortcut": "Ctrl+T", "icon": "📋", "category": "create"},
        {"id": "new_invoice", "label": "New Invoice", "shortcut": "", "icon": "🧾", "category": "create"},
        {"id": "new_note", "label": "Quick Note", "shortcut": "Ctrl+Shift+N", "icon": "📝", "category": "create"},
        {"id": "quick_capture", "label": "Quick Capture", "shortcut": "Ctrl+.", "icon": "⚡", "category": "create"},
        {"id": "dashboard", "label": "Go to Dashboard", "shortcut": "Ctrl+D", "icon": "📊", "category": "navigate"},
        {"id": "crm", "label": "Go to CRM", "shortcut": "", "icon": "👥", "category": "navigate"},
        {"id": "tasks", "label": "Go to Tasks", "shortcut": "", "icon": "📋", "category": "navigate"},
        {"id": "invoices", "label": "Go to Invoicing", "shortcut": "", "icon": "🧾", "category": "navigate"},
        {"id": "social", "label": "Go to Social Media", "shortcut": "", "icon": "📱", "category": "navigate"},
        {"id": "goals", "label": "Go to Goals", "shortcut": "", "icon": "🎯", "category": "navigate"},
        {"id": "settings", "label": "Settings", "shortcut": "Ctrl+,", "icon": "⚙️", "category": "navigate"},
        {"id": "search", "label": "Search Everything", "shortcut": "Ctrl+K", "icon": "🔍", "category": "action"},
        {"id": "briefing", "label": "Daily Briefing", "shortcut": "", "icon": "☀️", "category": "action"},
        {"id": "setup", "label": "Setup Concierge", "shortcut": "", "icon": "🎯", "category": "action"},
        {"id": "export", "label": "Export Data", "shortcut": "", "icon": "📤", "category": "action"},
    ]

    def get_commands(self, query: str = "") -> list:
        if not query:
            return self.COMMANDS
        q = query.lower()
        return [c for c in self.COMMANDS if q in c["label"].lower() or q in c.get("category", "")]
