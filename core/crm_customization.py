# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
CRM Customization Engine — Make the CRM yours.

Every business tracks different things:
  - Real estate agent: Property Address, Listing Price, Square Footage
  - SaaS company: MRR, Churn Risk Score, Plan Type
  - Law firm: Case Number, Court Date, Opposing Counsel
  - Freelancer: Project Type, Hourly Rate, Retainer Amount

This module lets users define:
  1. CUSTOM FIELDS — on contacts, companies, AND deals
     Types: text, number, currency, date, select, multi_select, url, email, phone, boolean
  2. CUSTOM PIPELINES — rename stages, add stages, reorder, multiple pipelines
  3. CUSTOM ACTIVITY TYPES — beyond call/email/meeting/note
  4. SAVED VIEWS — filtered, sorted views they can name and reuse
  5. CUSTOM TAGS — color-coded tag groups
"""

import json
import uuid
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.crm_custom")


# ══════════════════════════════════════════════════════════════
# 1. CUSTOM FIELD DEFINITIONS
# ══════════════════════════════════════════════════════════════

class CustomFieldManager:
    """Define and manage custom fields for contacts, companies, and deals.

    Field types:
      text       — free text (max 500 chars)
      textarea   — long text (max 5000 chars)
      number     — numeric value
      currency   — money value (stores as float, displays with currency symbol)
      date       — date picker
      select     — single choice from predefined options
      multi_select — multiple choices from predefined options
      url        — validated URL
      email      — validated email
      phone      — phone number
      boolean    — yes/no toggle
      rating     — 1-5 stars
    """

    FIELD_TYPES = [
        "text", "textarea", "number", "currency", "date",
        "select", "multi_select", "url", "email", "phone",
        "boolean", "rating",
    ]

    ENTITY_TYPES = ["contact", "company", "deal"]

    def create_field(self, owner_id: str, entity_type: str, label: str,
                      field_type: str = "text", options: list = None,
                      required: bool = False, default_value: str = "",
                      placeholder: str = "", group: str = "",
                      position: int = 0) -> dict:
        """Create a custom field definition."""
        if entity_type not in self.ENTITY_TYPES:
            return {"error": f"entity_type must be one of: {self.ENTITY_TYPES}"}
        if field_type not in self.FIELD_TYPES:
            return {"error": f"field_type must be one of: {self.FIELD_TYPES}"}

        fid = f"cf_{uuid.uuid4().hex[:10]}"
        field_key = label.lower().replace(" ", "_").replace("-", "_")[:30]

        with get_db() as db:
            db.execute("""
                INSERT INTO crm_custom_fields
                    (id, owner_id, entity_type, field_key, label, field_type,
                     options, required, default_value, placeholder, field_group,
                     position, active)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)
            """, (fid, owner_id, entity_type, field_key, label, field_type,
                  json.dumps(options or []), 1 if required else 0,
                  default_value, placeholder, group, position))

        return {
            "id": fid, "field_key": field_key, "label": label,
            "entity_type": entity_type, "field_type": field_type,
            "options": options or [],
        }

    def list_fields(self, owner_id: str, entity_type: str = None) -> list:
        """List all custom field definitions."""
        with get_db() as db:
            if entity_type:
                rows = db.execute(
                    "SELECT * FROM crm_custom_fields WHERE owner_id=? AND entity_type=? AND active=1 ORDER BY position, label",
                    (owner_id, entity_type)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM crm_custom_fields WHERE owner_id=? AND active=1 ORDER BY entity_type, position, label",
                    (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["options"] = json.loads(d.get("options", "[]"))
            d["required"] = bool(d.get("required"))
            result.append(d)
        return result

    def update_field(self, field_id: str, **updates) -> dict:
        if "options" in updates:
            updates["options"] = json.dumps(updates["options"])
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [field_id]
        with get_db() as db:
            db.execute(f"UPDATE crm_custom_fields SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def delete_field(self, field_id: str) -> dict:
        """Soft delete — mark inactive so existing data isn't lost."""
        with get_db() as db:
            db.execute("UPDATE crm_custom_fields SET active=0 WHERE id=?", (field_id,))
        return {"deleted": True}

    def validate_value(self, field_type: str, value, options: list = None) -> dict:
        """Validate a field value against its type."""
        if field_type == "number" or field_type == "currency" or field_type == "rating":
            try:
                float(value)
                if field_type == "rating" and (float(value) < 1 or float(value) > 5):
                    return {"valid": False, "error": "Rating must be between 1 and 5"}
                return {"valid": True}
            except (ValueError, TypeError):
                return {"valid": False, "error": f"Expected a number, got: {type(value).__name__}"}
        if field_type == "boolean":
            return {"valid": True}
        if field_type == "select" and options:
            if value not in options:
                return {"valid": False, "error": f"Must be one of: {options}"}
        if field_type == "multi_select" and options:
            if isinstance(value, list):
                invalid = [v for v in value if v not in options]
                if invalid:
                    return {"valid": False, "error": f"Invalid options: {invalid}"}
        if field_type == "email" and value:
            if "@" not in str(value) or "." not in str(value):
                return {"valid": False, "error": "Invalid email format"}
        if field_type == "url" and value:
            if not str(value).startswith(("http://", "https://")):
                return {"valid": False, "error": "URL must start with http:// or https://"}
        return {"valid": True}


# ══════════════════════════════════════════════════════════════
# 2. CUSTOM PIPELINES
# ══════════════════════════════════════════════════════════════

class PipelineManager:
    """Custom deal pipelines — multiple pipelines with custom stages.

    A business might have:
      - "Sales Pipeline" (Lead → Demo → Proposal → Negotiation → Won/Lost)
      - "Partnership Pipeline" (Intro → Evaluation → Terms → Signed)
      - "Hiring Pipeline" (Applied → Phone Screen → Interview → Offer → Hired)
    """

    DEFAULT_PIPELINE = {
        "name": "Sales Pipeline",
        "stages": [
            {"id": "lead", "label": "Lead", "color": "#94a3b8", "order": 0, "type": "open"},
            {"id": "qualified", "label": "Qualified", "color": "#3b82f6", "order": 1, "type": "open"},
            {"id": "proposal", "label": "Proposal Sent", "color": "#a459f2", "order": 2, "type": "open"},
            {"id": "negotiation", "label": "Negotiation", "color": "#f59e0b", "order": 3, "type": "open"},
            {"id": "closed_won", "label": "Closed Won", "color": "#22c55e", "order": 4, "type": "won"},
            {"id": "closed_lost", "label": "Closed Lost", "color": "#ef4444", "order": 5, "type": "lost"},
        ],
    }

    def create_pipeline(self, owner_id: str, name: str,
                         stages: list = None) -> dict:
        pid = f"pipe_{uuid.uuid4().hex[:10]}"
        stgs = stages or self.DEFAULT_PIPELINE["stages"]
        # Ensure IDs on stages
        for i, s in enumerate(stgs):
            if not s.get("id"):
                s["id"] = f"stg_{uuid.uuid4().hex[:6]}"
            s["order"] = i

        with get_db() as db:
            db.execute("""
                INSERT INTO crm_pipelines (id, owner_id, name, stages)
                VALUES (?,?,?,?)
            """, (pid, owner_id, name, json.dumps(stgs)))
        return {"id": pid, "name": name, "stages": stgs}

    def list_pipelines(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM crm_pipelines WHERE owner_id=? ORDER BY created_at",
                (owner_id,)).fetchall()
        if not rows:
            # Create default pipeline
            default = self.create_pipeline(owner_id, "Sales Pipeline")
            return [default]
        result = []
        for r in rows:
            d = dict(r)
            d["stages"] = json.loads(d.get("stages", "[]"))
            result.append(d)
        return result

    def get_pipeline(self, pipeline_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM crm_pipelines WHERE id=?",
                            (pipeline_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["stages"] = json.loads(d.get("stages", "[]"))
        return d

    def update_pipeline(self, pipeline_id: str, name: str = None,
                         stages: list = None) -> dict:
        updates = {}
        if name:
            updates["name"] = name
        if stages is not None:
            for i, s in enumerate(stages):
                if not s.get("id"):
                    s["id"] = f"stg_{uuid.uuid4().hex[:6]}"
                s["order"] = i
            updates["stages"] = json.dumps(stages)
        if not updates:
            return {"error": "Nothing to update"}
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [pipeline_id]
        with get_db() as db:
            db.execute(f"UPDATE crm_pipelines SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def delete_pipeline(self, pipeline_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM crm_pipelines WHERE id=?", (pipeline_id,))
        return {"deleted": True}


# ══════════════════════════════════════════════════════════════
# 3. CUSTOM ACTIVITY TYPES
# ══════════════════════════════════════════════════════════════

class ActivityTypeManager:
    """Custom activity types beyond the defaults.

    Defaults: call, email, meeting, note, task
    Custom examples: site_visit, demo, contract_review, follow_up, referral
    """

    DEFAULTS = [
        {"id": "call", "label": "Call", "icon": "📞", "color": "#3b82f6"},
        {"id": "email", "label": "Email", "icon": "📧", "color": "#a459f2"},
        {"id": "meeting", "label": "Meeting", "icon": "🤝", "color": "#22c55e"},
        {"id": "note", "label": "Note", "icon": "📝", "color": "#f59e0b"},
        {"id": "task", "label": "Task", "icon": "✅", "color": "#6366f1"},
    ]

    def get_types(self, owner_id: str) -> list:
        """Get all activity types (defaults + custom)."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM crm_activity_types WHERE owner_id=? ORDER BY position",
                (owner_id,)).fetchall()
        custom = [dict(r) for r in rows]
        return self.DEFAULTS + custom

    def create_type(self, owner_id: str, label: str, icon: str = "📌",
                     color: str = "#94a3b8") -> dict:
        tid = label.lower().replace(" ", "_")[:20]
        with get_db() as db:
            db.execute("""
                INSERT INTO crm_activity_types (id, owner_id, label, icon, color, position)
                VALUES (?,?,?,?,?,?)
            """, (tid, owner_id, label, icon, color, 100))
        return {"id": tid, "label": label, "icon": icon, "color": color}

    def delete_type(self, owner_id: str, type_id: str) -> dict:
        if type_id in [d["id"] for d in self.DEFAULTS]:
            return {"error": "Cannot delete default activity types"}
        with get_db() as db:
            db.execute("DELETE FROM crm_activity_types WHERE id=? AND owner_id=?",
                      (type_id, owner_id))
        return {"deleted": True}


# ══════════════════════════════════════════════════════════════
# 4. SAVED VIEWS
# ══════════════════════════════════════════════════════════════

class SavedViewManager:
    """Save filtered, sorted CRM views for quick access.

    Examples:
      "Hot Leads" — contacts tagged "hot" where source = "linkedin"
      "Closing This Month" — deals in negotiation with expected_close this month
      "Enterprise Prospects" — companies where size = "500+"
    """

    def create_view(self, owner_id: str, name: str, entity_type: str,
                     filters: dict = None, sort_by: str = "",
                     sort_order: str = "desc", columns: list = None) -> dict:
        vid = f"view_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO crm_saved_views
                    (id, owner_id, name, entity_type, filters, sort_by,
                     sort_order, columns)
                VALUES (?,?,?,?,?,?,?,?)
            """, (vid, owner_id, name, entity_type,
                  json.dumps(filters or {}), sort_by, sort_order,
                  json.dumps(columns or [])))
        return {"id": vid, "name": name, "entity_type": entity_type}

    def list_views(self, owner_id: str, entity_type: str = None) -> list:
        with get_db() as db:
            if entity_type:
                rows = db.execute(
                    "SELECT * FROM crm_saved_views WHERE owner_id=? AND entity_type=? ORDER BY name",
                    (owner_id, entity_type)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM crm_saved_views WHERE owner_id=? ORDER BY entity_type, name",
                    (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["filters"] = json.loads(d.get("filters", "{}"))
            d["columns"] = json.loads(d.get("columns", "[]"))
            result.append(d)
        return result

    def get_view(self, view_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM crm_saved_views WHERE id=?",
                            (view_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["filters"] = json.loads(d.get("filters", "{}"))
        d["columns"] = json.loads(d.get("columns", "[]"))
        return d

    def update_view(self, view_id: str, **updates) -> dict:
        if "filters" in updates:
            updates["filters"] = json.dumps(updates["filters"])
        if "columns" in updates:
            updates["columns"] = json.dumps(updates["columns"])
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [view_id]
        with get_db() as db:
            db.execute(f"UPDATE crm_saved_views SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def delete_view(self, view_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM crm_saved_views WHERE id=?", (view_id,))
        return {"deleted": True}

    def apply_view(self, view_id: str, owner_id: str) -> dict:
        """Apply a saved view — returns the filter criteria for the frontend to execute."""
        view = self.get_view(view_id)
        if not view:
            return {"error": "View not found"}
        return {
            "view": view,
            "query_params": {
                "entity_type": view["entity_type"],
                "filters": view["filters"],
                "sort_by": view.get("sort_by", ""),
                "sort_order": view.get("sort_order", "desc"),
                "columns": view["columns"],
            },
        }
