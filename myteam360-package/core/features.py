"""
Platform Features — Conversation Export, Prompt Templates, Usage Quotas, Custom Branding.
"""

import os
import io
import csv
import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.features")


# ══════════════════════════════════════════════════════════════
# 1. CONVERSATION EXPORT — PDF & CSV
# ══════════════════════════════════════════════════════════════

class ConversationExporter:
    """Export conversations to CSV or structured JSON (PDF generation is client-side)."""

    def export_csv(self, conversation_id, user_id=None):
        """Export a conversation as CSV string."""
        msgs = self._get_messages(conversation_id, user_id)
        if msgs is None:
            return {"error": "Conversation not found or access denied"}

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "role", "content", "agent_name", "model"])
        for m in msgs:
            writer.writerow([
                m.get("created_at", ""),
                m.get("role", ""),
                m.get("content", ""),
                m.get("agent_name", ""),
                m.get("model", ""),
            ])
        return {"csv": output.getvalue(), "message_count": len(msgs)}

    def export_json(self, conversation_id, user_id=None):
        """Export a conversation as structured JSON."""
        msgs = self._get_messages(conversation_id, user_id)
        if msgs is None:
            return {"error": "Conversation not found or access denied"}

        conv = self._get_conversation_meta(conversation_id)
        return {
            "export_format": "json",
            "exported_at": datetime.utcnow().isoformat(),
            "conversation": conv,
            "messages": msgs,
            "message_count": len(msgs),
        }

    def export_markdown(self, conversation_id, user_id=None):
        """Export a conversation as Markdown for PDF rendering."""
        msgs = self._get_messages(conversation_id, user_id)
        if msgs is None:
            return {"error": "Conversation not found or access denied"}

        conv = self._get_conversation_meta(conversation_id)
        lines = [
            f"# {conv.get('title', 'Conversation')}",
            f"**Date:** {conv.get('created_at', '')}",
            f"**Agent:** {conv.get('agent_name', 'General')}",
            f"**Messages:** {len(msgs)}",
            "",
            "---",
            "",
        ]
        for m in msgs:
            role = m["role"].capitalize()
            ts = m.get("created_at", "")[:19]
            name = m.get("agent_name", role)
            lines.append(f"**{name}** ({ts}):")
            lines.append("")
            lines.append(m.get("content", ""))
            lines.append("")
            lines.append("---")
            lines.append("")

        return {"markdown": "\n".join(lines), "message_count": len(msgs)}

    def bulk_export(self, user_id, format="csv", limit=100):
        """Export all conversations for a user (GDPR data export)."""
        with get_db() as db:
            convs = db.execute(
                "SELECT id FROM conversations WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit)).fetchall()

        results = []
        for c in convs:
            if format == "csv":
                r = self.export_csv(c["id"], user_id)
            elif format == "markdown":
                r = self.export_markdown(c["id"], user_id)
            else:
                r = self.export_json(c["id"], user_id)
            r["conversation_id"] = c["id"]
            results.append(r)

        return {"exports": results, "count": len(results), "format": format}

    def _get_messages(self, conversation_id, user_id=None):
        with get_db() as db:
            conv = db.execute(
                "SELECT user_id FROM conversations WHERE id=?",
                (conversation_id,)).fetchone()
            if not conv:
                return None
            if user_id and conv["user_id"] != user_id:
                return None

            rows = db.execute(
                "SELECT m.role, m.content, m.model, m.created_at, a.name as agent_name"
                " FROM messages m LEFT JOIN agents a ON m.agent_id = a.id"
                " WHERE m.conversation_id=? ORDER BY m.created_at",
                (conversation_id,)).fetchall()
        return [dict(r) for r in rows]

    def _get_conversation_meta(self, conversation_id):
        with get_db() as db:
            row = db.execute(
                "SELECT c.id, c.title, c.created_at, c.updated_at, a.name as agent_name"
                " FROM conversations c LEFT JOIN agents a ON c.agent_id = a.id"
                " WHERE c.id=?",
                (conversation_id,)).fetchone()
        return dict(row) if row else {}


# ══════════════════════════════════════════════════════════════
# 2. PROMPT TEMPLATE LIBRARY — Shareable reusable prompts
# ══════════════════════════════════════════════════════════════

class PromptTemplateLibrary:
    """Manage reusable prompt templates that users can share across the org."""

    def create_template(self, owner_id, data):
        """Create a new prompt template."""
        tid = f"pt_{uuid.uuid4().hex[:8]}"
        name = data.get("name", "Untitled Template")
        content = data.get("content", "")
        description = data.get("description", "")
        category = data.get("category", "general")
        variables = json.dumps(data.get("variables", []))  # e.g. ["topic", "tone", "audience"]
        is_shared = 1 if data.get("is_shared", False) else 0
        department_id = data.get("department_id")

        with get_db() as db:
            db.execute(
                "INSERT INTO prompt_templates (id, owner_id, name, description, content,"
                " category, variables, is_shared, department_id)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (tid, owner_id, name, description, content, category,
                 variables, is_shared, department_id))

        return {"id": tid, "name": name, "created": True}

    def get_template(self, template_id):
        with get_db() as db:
            row = db.execute(
                "SELECT t.*, u.display_name as owner_name FROM prompt_templates t"
                " LEFT JOIN users u ON t.owner_id = u.id WHERE t.id=?",
                (template_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["variables"] = json.loads(d.get("variables", "[]"))
        return d

    def list_templates(self, user_id, category=None, search=None):
        """List templates visible to a user (own + shared + department)."""
        with get_db() as db:
            # Get user's department
            dm = db.execute(
                "SELECT department_id FROM department_members WHERE user_id=? LIMIT 1",
                (user_id,)).fetchone()
            dept_id = dm["department_id"] if dm else None

            query = """
                SELECT t.*, u.display_name as owner_name
                FROM prompt_templates t
                LEFT JOIN users u ON t.owner_id = u.id
                WHERE (t.owner_id=? OR t.is_shared=1
                    OR (t.department_id IS NOT NULL AND t.department_id=?))
            """
            params = [user_id, dept_id or ""]

            if category:
                query += " AND t.category=?"
                params.append(category)
            if search:
                query += " AND (t.name LIKE ? OR t.description LIKE ? OR t.content LIKE ?)"
                params.extend([f"%{search}%"] * 3)

            query += " ORDER BY t.updated_at DESC"
            rows = db.execute(query, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["variables"] = json.loads(d.get("variables", "[]"))
            results.append(d)
        return results

    def update_template(self, template_id, owner_id, updates):
        """Update a template (owner only)."""
        with get_db() as db:
            existing = db.execute(
                "SELECT owner_id FROM prompt_templates WHERE id=?",
                (template_id,)).fetchone()
            if not existing:
                return {"error": "Template not found"}
            if existing["owner_id"] != owner_id:
                return {"error": "Only the owner can edit this template"}

            fields, vals = [], []
            for k in ["name", "description", "content", "category", "is_shared", "department_id"]:
                if k in updates:
                    fields.append(f"{k}=?")
                    vals.append(updates[k])
            if "variables" in updates:
                fields.append("variables=?")
                vals.append(json.dumps(updates["variables"]))

            if fields:
                fields.append("updated_at=CURRENT_TIMESTAMP")
                vals.append(template_id)
                db.execute(
                    f"UPDATE prompt_templates SET {','.join(fields)} WHERE id=?", vals)

        return {"updated": True, "id": template_id}

    def delete_template(self, template_id, user_id):
        with get_db() as db:
            existing = db.execute(
                "SELECT owner_id FROM prompt_templates WHERE id=?",
                (template_id,)).fetchone()
            if not existing:
                return {"error": "Not found"}
            if existing["owner_id"] != user_id:
                return {"error": "Only the owner can delete this template"}
            db.execute("DELETE FROM prompt_templates WHERE id=?", (template_id,))
        return {"deleted": True}

    def use_template(self, template_id, user_id, variable_values=None):
        """Render a template with provided variable values and track usage."""
        template = self.get_template(template_id)
        if not template:
            return {"error": "Template not found"}

        content = template["content"]
        # Substitute variables: {{variable_name}} -> value
        variable_values = variable_values or {}
        for var in template.get("variables", []):
            placeholder = "{{" + var + "}}"
            value = variable_values.get(var, "")
            content = content.replace(placeholder, value)

        # Track usage
        with get_db() as db:
            db.execute(
                "INSERT INTO template_usage (id, template_id, user_id) VALUES (?,?,?)",
                (f"tu_{uuid.uuid4().hex[:8]}", template_id, user_id))

        return {"rendered": content, "template_id": template_id, "template_name": template["name"]}

    def get_categories(self):
        """Get all unique categories."""
        with get_db() as db:
            rows = db.execute(
                "SELECT DISTINCT category FROM prompt_templates ORDER BY category").fetchall()
        return [r["category"] for r in rows]

    def get_popular(self, limit=10):
        """Get most-used templates."""
        with get_db() as db:
            rows = db.execute("""
                SELECT t.*, u.display_name as owner_name,
                    COUNT(tu.id) as use_count
                FROM prompt_templates t
                LEFT JOIN users u ON t.owner_id = u.id
                LEFT JOIN template_usage tu ON tu.template_id = t.id
                WHERE t.is_shared = 1
                GROUP BY t.id
                ORDER BY use_count DESC
                LIMIT ?
            """, (limit,)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["variables"] = json.loads(d.get("variables", "[]"))
            results.append(d)
        return results


# ══════════════════════════════════════════════════════════════
# 3. USAGE QUOTAS — Per-user/department/month token limits
# ══════════════════════════════════════════════════════════════

class UsageQuotaManager:
    """Enforce token/cost quotas per user, department, and org-wide per month."""

    DEFAULT_QUOTAS = {
        "user_monthly_tokens": 0,        # 0 = unlimited
        "user_monthly_cost": 0.0,
        "department_monthly_tokens": 0,
        "department_monthly_cost": 0.0,
        "org_monthly_tokens": 0,
        "org_monthly_cost": 0.0,
        "warn_at_percent": 80,           # Warn when usage hits this %
        "block_at_percent": 100,         # Hard block at this %
    }

    def __init__(self):
        self.quotas = dict(self.DEFAULT_QUOTAS)

    def get_quotas(self):
        return dict(self.quotas)

    def update_quotas(self, updates):
        for k, v in updates.items():
            if k in self.quotas:
                self.quotas[k] = v
        return self.quotas

    def set_user_quota(self, user_id, monthly_tokens=None, monthly_cost=None):
        """Set per-user quota override."""
        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM user_quotas WHERE user_id=?", (user_id,)).fetchone()
            if existing:
                updates, vals = [], []
                if monthly_tokens is not None:
                    updates.append("monthly_tokens=?"); vals.append(monthly_tokens)
                if monthly_cost is not None:
                    updates.append("monthly_cost=?"); vals.append(monthly_cost)
                updates.append("updated_at=CURRENT_TIMESTAMP")
                vals.append(user_id)
                db.execute(
                    f"UPDATE user_quotas SET {','.join(updates)} WHERE user_id=?", vals)
            else:
                db.execute(
                    "INSERT INTO user_quotas (id, user_id, monthly_tokens, monthly_cost)"
                    " VALUES (?,?,?,?)",
                    (f"uq_{uuid.uuid4().hex[:8]}", user_id,
                     monthly_tokens or 0, monthly_cost or 0.0))
        return {"set": True, "user_id": user_id}

    def set_department_quota(self, department_id, monthly_tokens=None, monthly_cost=None):
        """Set per-department quota."""
        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM department_quotas WHERE department_id=?",
                (department_id,)).fetchone()
            if existing:
                updates, vals = [], []
                if monthly_tokens is not None:
                    updates.append("monthly_tokens=?"); vals.append(monthly_tokens)
                if monthly_cost is not None:
                    updates.append("monthly_cost=?"); vals.append(monthly_cost)
                updates.append("updated_at=CURRENT_TIMESTAMP")
                vals.append(department_id)
                db.execute(
                    f"UPDATE department_quotas SET {','.join(updates)} WHERE department_id=?", vals)
            else:
                db.execute(
                    "INSERT INTO department_quotas (id, department_id, monthly_tokens, monthly_cost)"
                    " VALUES (?,?,?,?)",
                    (f"dq_{uuid.uuid4().hex[:8]}", department_id,
                     monthly_tokens or 0, monthly_cost or 0.0))
        return {"set": True, "department_id": department_id}

    def check_quota(self, user_id):
        """Check if user is within their quota. Returns {allowed, warnings[], usage}."""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0).isoformat()

        usage = self._get_month_usage(user_id, month_start)
        warnings = []
        allowed = True

        # User-level quota
        user_quota = self._get_user_quota(user_id)
        if user_quota:
            if user_quota["monthly_tokens"] > 0:
                pct = (usage["tokens"] / user_quota["monthly_tokens"]) * 100
                if pct >= self.quotas["block_at_percent"]:
                    allowed = False
                    warnings.append(f"User token quota exceeded ({int(pct)}%)")
                elif pct >= self.quotas["warn_at_percent"]:
                    warnings.append(f"User token usage at {int(pct)}% of monthly limit")
            if user_quota["monthly_cost"] > 0:
                pct = (usage["cost"] / user_quota["monthly_cost"]) * 100
                if pct >= self.quotas["block_at_percent"]:
                    allowed = False
                    warnings.append(f"User cost quota exceeded ({int(pct)}%)")
                elif pct >= self.quotas["warn_at_percent"]:
                    warnings.append(f"User cost at {int(pct)}% of monthly limit")

        # Department-level quota
        dept_id = self._get_user_department(user_id)
        if dept_id:
            dept_usage = self._get_department_month_usage(dept_id, month_start)
            dept_quota = self._get_department_quota(dept_id)
            if dept_quota and dept_quota["monthly_tokens"] > 0:
                pct = (dept_usage["tokens"] / dept_quota["monthly_tokens"]) * 100
                if pct >= self.quotas["block_at_percent"]:
                    allowed = False
                    warnings.append(f"Department token quota exceeded ({int(pct)}%)")
                elif pct >= self.quotas["warn_at_percent"]:
                    warnings.append(f"Department at {int(pct)}% of monthly token limit")

        # Org-level
        if self.quotas["org_monthly_tokens"] > 0:
            org_usage = self._get_org_month_usage(month_start)
            pct = (org_usage["tokens"] / self.quotas["org_monthly_tokens"]) * 100
            if pct >= self.quotas["block_at_percent"]:
                allowed = False
                warnings.append(f"Organization token quota exceeded ({int(pct)}%)")
            elif pct >= self.quotas["warn_at_percent"]:
                warnings.append(f"Organization at {int(pct)}% of monthly token limit")

        return {
            "allowed": allowed,
            "warnings": warnings,
            "usage": usage,
            "period": {"start": month_start, "end": now.isoformat()},
        }

    def get_usage_report(self, scope="org", scope_id=None):
        """Get usage breakdown for user, department, or org."""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0).isoformat()

        if scope == "user" and scope_id:
            usage = self._get_month_usage(scope_id, month_start)
            quota = self._get_user_quota(scope_id)
        elif scope == "department" and scope_id:
            usage = self._get_department_month_usage(scope_id, month_start)
            quota = self._get_department_quota(scope_id)
        else:
            usage = self._get_org_month_usage(month_start)
            quota = {"monthly_tokens": self.quotas["org_monthly_tokens"],
                     "monthly_cost": self.quotas["org_monthly_cost"]}

        return {
            "scope": scope,
            "scope_id": scope_id,
            "period": month_start,
            "usage": usage,
            "quota": quota,
        }

    def _get_month_usage(self, user_id, month_start):
        with get_db() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(tokens_in + tokens_out), 0) as tokens,"
                " COALESCE(SUM(cost_estimate), 0) as cost,"
                " COUNT(*) as requests"
                " FROM usage_log WHERE user_id=? AND created_at >= ?",
                (user_id, month_start)).fetchone()
        return {"tokens": row["tokens"], "cost": round(row["cost"], 4),
                "requests": row["requests"]}

    def _get_department_month_usage(self, dept_id, month_start):
        with get_db() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(ul.tokens_in + ul.tokens_out), 0) as tokens,"
                " COALESCE(SUM(ul.cost_estimate), 0) as cost,"
                " COUNT(*) as requests"
                " FROM usage_log ul JOIN users u ON ul.user_id = u.id"
                " WHERE u.department_id=? AND ul.created_at >= ?",
                (dept_id, month_start)).fetchone()
        return {"tokens": row["tokens"], "cost": round(row["cost"], 4),
                "requests": row["requests"]}

    def _get_org_month_usage(self, month_start):
        with get_db() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(tokens_in + tokens_out), 0) as tokens,"
                " COALESCE(SUM(cost_estimate), 0) as cost,"
                " COUNT(*) as requests"
                " FROM usage_log WHERE created_at >= ?",
                (month_start,)).fetchone()
        return {"tokens": row["tokens"], "cost": round(row["cost"], 4),
                "requests": row["requests"]}

    def _get_user_quota(self, user_id):
        with get_db() as db:
            row = db.execute(
                "SELECT monthly_tokens, monthly_cost FROM user_quotas WHERE user_id=?",
                (user_id,)).fetchone()
        return dict(row) if row else None

    def _get_department_quota(self, dept_id):
        with get_db() as db:
            row = db.execute(
                "SELECT monthly_tokens, monthly_cost FROM department_quotas WHERE department_id=?",
                (dept_id,)).fetchone()
        return dict(row) if row else None

    def _get_user_department(self, user_id):
        with get_db() as db:
            row = db.execute(
                "SELECT department_id FROM department_members WHERE user_id=? LIMIT 1",
                (user_id,)).fetchone()
        return row["department_id"] if row else None


# ══════════════════════════════════════════════════════════════
# 4. CUSTOM BRANDING — Org name, colors, logo, white-label
# ══════════════════════════════════════════════════════════════

class BrandingManager:
    """Manage platform branding: org name, colors, logo, custom text."""

    DEFAULT_BRANDING = {
        "org_name": "MyTeam360",
        "tagline": "AI-Powered Workplace Platform",
        "primary_color": "#7c5cfc",
        "secondary_color": "#4d8eff",
        "accent_color": "#4ade80",
        "bg_color": "#0a0a0f",
        "surface_color": "#12121a",
        "text_color": "#e8e8f0",
        "logo_url": "/api/branding/logo-asset",
        "favicon_url": "",
        "login_title": "Welcome Back",
        "login_subtitle": "Sign in to your workspace",
        "footer_text": "",
        "support_email": "",
        "support_url": "",
        "custom_css": "",
    }

    def get_branding(self):
        """Get current branding settings."""
        with get_db() as db:
            rows = db.execute(
                "SELECT key, value FROM workspace_settings WHERE key LIKE 'branding_%'").fetchall()

        branding = dict(self.DEFAULT_BRANDING)
        for r in rows:
            key = r["key"].replace("branding_", "", 1)
            if key in branding:
                branding[key] = r["value"]
        return branding

    def update_branding(self, updates):
        """Update branding settings (admin only)."""
        with get_db() as db:
            for key, value in updates.items():
                if key not in self.DEFAULT_BRANDING:
                    continue
                db_key = f"branding_{key}"
                existing = db.execute(
                    "SELECT key FROM workspace_settings WHERE key=?",
                    (db_key,)).fetchone()
                if existing:
                    db.execute(
                        "UPDATE workspace_settings SET value=? WHERE key=?",
                        (str(value), db_key))
                else:
                    db.execute(
                        "INSERT INTO workspace_settings (key, value) VALUES (?,?)",
                        (db_key, str(value)))
        return self.get_branding()

    def save_logo(self, file_data, filename="logo.png"):
        """Save uploaded logo file."""
        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
        os.makedirs(static_dir, exist_ok=True)
        logo_path = os.path.join(static_dir, filename)

        if isinstance(file_data, str):
            # Base64 encoded
            import base64
            with open(logo_path, "wb") as f:
                f.write(base64.b64decode(file_data))
        elif isinstance(file_data, bytes):
            with open(logo_path, "wb") as f:
                f.write(file_data)
        else:
            # File-like object
            with open(logo_path, "wb") as f:
                f.write(file_data.read())

        return {"saved": True, "path": logo_path, "url": "/api/branding/logo-asset"}

    def generate_css_variables(self):
        """Generate CSS custom properties from branding."""
        b = self.get_branding()
        return f""":root {{
  --brand-primary: {b['primary_color']};
  --brand-secondary: {b['secondary_color']};
  --brand-accent: {b['accent_color']};
  --brand-bg: {b['bg_color']};
  --brand-surface: {b['surface_color']};
  --brand-text: {b['text_color']};
}}"""

    def reset_branding(self):
        """Reset all branding to defaults."""
        with get_db() as db:
            db.execute("DELETE FROM workspace_settings WHERE key LIKE 'branding_%'")
        return self.get_branding()
