# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Roundtable Whiteboard — Visual note-taking during AI team meetings.

Like a real office whiteboard:
  - Sticky notes (color-coded per participant or topic)
  - Action items (assigned to agents or user, with due dates)
  - Sections/columns (brainstorm ideas, decisions, parking lot)
  - Auto-capture (AI extracts key points from discussion into notes)
  - Freeform text notes
  - Full export (Markdown, JSON, and feeds into document export)

The whiteboard persists across rounds — it's the living document
that grows as the Roundtable Meeting progresses.
"""

import json
import uuid
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.whiteboard")


class RoundtableWhiteboard:
    """Visual whiteboard for Roundtable Meetings."""

    DEFAULT_SECTIONS = [
        {"id": "ideas", "title": "Ideas", "color": "#a459f2", "icon": "💡"},
        {"id": "decisions", "title": "Decisions", "color": "#22c55e", "icon": "✅"},
        {"id": "action_items", "title": "Action Items", "color": "#3b82f6", "icon": "📋"},
        {"id": "parking_lot", "title": "Parking Lot", "color": "#f59e0b", "icon": "🅿️"},
    ]

    STICKY_COLORS = [
        "#fef3c7",  # Yellow
        "#dbeafe",  # Blue
        "#dcfce7",  # Green
        "#fce7f3",  # Pink
        "#f3e8ff",  # Purple
        "#ffedd5",  # Orange
    ]

    def create(self, roundtable_id: str, owner_id: str) -> dict:
        """Create a whiteboard for a Roundtable Meeting."""
        wid = f"wb_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO roundtable_whiteboards
                    (id, roundtable_id, owner_id, sections, notes)
                VALUES (?,?,?,?,?)
            """, (wid, roundtable_id, owner_id,
                  json.dumps(self.DEFAULT_SECTIONS), "[]"))
        return {"id": wid, "roundtable_id": roundtable_id,
                "sections": self.DEFAULT_SECTIONS, "notes": []}

    def get(self, roundtable_id: str) -> dict:
        """Get the whiteboard for a Roundtable Meeting."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM roundtable_whiteboards WHERE roundtable_id=?",
                (roundtable_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["sections"] = json.loads(d.get("sections", "[]"))
        d["notes"] = json.loads(d.get("notes", "[]"))
        return d

    def get_or_create(self, roundtable_id: str, owner_id: str) -> dict:
        wb = self.get(roundtable_id)
        if wb:
            return wb
        return self.create(roundtable_id, owner_id)

    # ── Notes (Sticky Notes) ──

    def add_note(self, roundtable_id: str, section_id: str, content: str,
                 author: str = "", color: str = "", tags: list = None) -> dict:
        """Add a sticky note to a whiteboard section."""
        wb = self.get(roundtable_id)
        if not wb:
            return {"error": "Whiteboard not found"}

        note = {
            "id": f"note_{uuid.uuid4().hex[:8]}",
            "section_id": section_id,
            "content": content,
            "author": author,
            "color": color or self.STICKY_COLORS[len(wb["notes"]) % len(self.STICKY_COLORS)],
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "pinned": False,
            "completed": False,
        }

        notes = wb["notes"]
        notes.append(note)
        self._save_notes(roundtable_id, notes)
        return note

    def update_note(self, roundtable_id: str, note_id: str,
                    content: str = None, section_id: str = None,
                    pinned: bool = None, completed: bool = None,
                    color: str = None) -> dict:
        """Update a sticky note."""
        wb = self.get(roundtable_id)
        if not wb:
            return {"error": "Whiteboard not found"}

        for note in wb["notes"]:
            if note["id"] == note_id:
                if content is not None:
                    note["content"] = content
                if section_id is not None:
                    note["section_id"] = section_id
                if pinned is not None:
                    note["pinned"] = pinned
                if completed is not None:
                    note["completed"] = completed
                if color is not None:
                    note["color"] = color
                note["updated_at"] = datetime.now().isoformat()
                self._save_notes(roundtable_id, wb["notes"])
                return note
        return {"error": "Note not found"}

    def delete_note(self, roundtable_id: str, note_id: str) -> dict:
        wb = self.get(roundtable_id)
        if not wb:
            return {"error": "Whiteboard not found"}
        wb["notes"] = [n for n in wb["notes"] if n["id"] != note_id]
        self._save_notes(roundtable_id, wb["notes"])
        return {"deleted": True}

    # ── Action Items ──

    def add_action_item(self, roundtable_id: str, title: str,
                        assigned_to: str = "", due_date: str = "",
                        priority: str = "medium", details: str = "") -> dict:
        """Add an action item (automatically goes to Action Items section)."""
        return self.add_note(
            roundtable_id, "action_items",
            content=title,
            author=assigned_to,
            tags=[f"priority:{priority}"] + ([f"due:{due_date}"] if due_date else []),
            color="#dbeafe",
        )

    def get_action_items(self, roundtable_id: str) -> list:
        """Get all action items from the whiteboard."""
        wb = self.get(roundtable_id)
        if not wb:
            return []
        return [n for n in wb["notes"] if n["section_id"] == "action_items"]

    # ── Sections ──

    def add_section(self, roundtable_id: str, title: str,
                    color: str = "#94a3b8", icon: str = "📝") -> dict:
        """Add a custom section to the whiteboard."""
        wb = self.get(roundtable_id)
        if not wb:
            return {"error": "Whiteboard not found"}

        section = {
            "id": f"sec_{uuid.uuid4().hex[:6]}",
            "title": title,
            "color": color,
            "icon": icon,
        }
        sections = wb["sections"]
        sections.append(section)
        with get_db() as db:
            db.execute(
                "UPDATE roundtable_whiteboards SET sections=? WHERE roundtable_id=?",
                (json.dumps(sections), roundtable_id))
        return section

    def remove_section(self, roundtable_id: str, section_id: str) -> dict:
        wb = self.get(roundtable_id)
        if not wb:
            return {"error": "Whiteboard not found"}
        # Don't allow removing default sections
        if section_id in ("ideas", "decisions", "action_items", "parking_lot"):
            return {"error": "Cannot remove default sections"}
        sections = [s for s in wb["sections"] if s["id"] != section_id]
        with get_db() as db:
            db.execute(
                "UPDATE roundtable_whiteboards SET sections=? WHERE roundtable_id=?",
                (json.dumps(sections), roundtable_id))
        return {"removed": True}

    # ── AI Auto-Capture ──

    def auto_capture_from_round(self, roundtable_id: str,
                                 round_entries: list) -> list:
        """After each round, AI extracts key points into sticky notes.

        Looks for:
        - Decisions: "we should", "let's go with", "agreed", "decided"
        - Action items: "next step", "will do", "need to", "assigned to"
        - Key ideas: substantive points (>1 sentence, not just agreement)
        - Parking lot: "later", "table this", "come back to", "not now"
        """
        captured = []
        import re

        for entry in round_entries:
            if entry.get("type") != "agent":
                continue
            content = entry.get("content", "")
            name = entry.get("name", "Agent")

            # Decisions
            if re.search(r"(?:we should|let['\u2019]s go with|agreed|decided|consensus is|the answer is)", content, re.I):
                note = self.add_note(roundtable_id, "decisions", content[:200],
                                     author=name, color="#dcfce7")
                captured.append(note)

            # Action items
            elif re.search(r"(?:next step|will do|need to|should follow.up|action item|assigned to|deadline)", content, re.I):
                note = self.add_note(roundtable_id, "action_items", content[:200],
                                     author=name, color="#dbeafe")
                captured.append(note)

            # Parking lot
            elif re.search(r"(?:table this|come back to|later|not now|separate discussion|out of scope|park this)", content, re.I):
                note = self.add_note(roundtable_id, "parking_lot", content[:200],
                                     author=name, color="#fef3c7")
                captured.append(note)

            # Key ideas (substantive, not yielded)
            elif not entry.get("yielded") and len(content) > 80:
                note = self.add_note(roundtable_id, "ideas", content[:200],
                                     author=name, color="#f3e8ff")
                captured.append(note)

        return captured

    # ── Export ──

    def export_markdown(self, roundtable_id: str) -> str:
        """Export whiteboard as Markdown."""
        wb = self.get(roundtable_id)
        if not wb:
            return ""

        lines = ["# Roundtable Whiteboard\n"]
        for section in wb["sections"]:
            section_notes = [n for n in wb["notes"] if n["section_id"] == section["id"]]
            if not section_notes:
                continue
            lines.append(f"\n## {section['icon']} {section['title']}\n")
            for note in section_notes:
                status = "✅" if note.get("completed") else "📌" if note.get("pinned") else "•"
                author = f" — *{note['author']}*" if note.get("author") else ""
                lines.append(f"  {status} {note['content']}{author}")
        return "\n".join(lines)

    def export_json(self, roundtable_id: str) -> dict:
        return self.get(roundtable_id)

    # ── Internal ──

    def _save_notes(self, roundtable_id: str, notes: list):
        with get_db() as db:
            db.execute(
                "UPDATE roundtable_whiteboards SET notes=?, updated_at=CURRENT_TIMESTAMP WHERE roundtable_id=?",
                (json.dumps(notes), roundtable_id))
