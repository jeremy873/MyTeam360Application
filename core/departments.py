# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# This software and all associated intellectual property are owned
# exclusively by Praxis Holdings LLC, a Nevada limited-liability company.
# Licensed to MyTeam360 LLC for operation.
#
# UNAUTHORIZED ACCESS, COPYING, MODIFICATION, DISTRIBUTION, OR USE
# OF THIS SOFTWARE IS STRICTLY PROHIBITED AND MAY RESULT IN CIVIL
# LIABILITY AND CRIMINAL PROSECUTION UNDER FEDERAL AND STATE LAW,
# INCLUDING THE DEFEND TRADE SECRETS ACT (18 U.S.C. § 1836),
# THE COMPUTER FRAUD AND ABUSE ACT (18 U.S.C. § 1030), AND THE
# NEVADA UNIFORM TRADE SECRETS ACT (NRS 600A).
#
# See LICENSE and NOTICE files for full legal terms.
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
MyTeam360 — Department Management
Handles department CRUD, member management, and data isolation.
© 2026 Praxis Holdings LLC. All rights reserved.
"""

import uuid
import logging
from .database import get_db

logger = logging.getLogger("MyTeam360.departments")


class DepartmentManager:

    def create_department(self, name, description="", icon="🏢", color="#3b82f6", created_by=None):
        dept_id = f"dept_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO departments (id, name, description, icon, color, created_by)
                VALUES (?,?,?,?,?,?)
            """, (dept_id, name, description, icon, color, created_by))
        logger.info(f"Department created: {name} ({dept_id})")
        return self.get_department(dept_id)

    def get_department(self, dept_id):
        with get_db() as db:
            row = db.execute("SELECT * FROM departments WHERE id=?", (dept_id,)).fetchone()
            if row:
                d = dict(row)
                d["members"] = self._get_members(db, dept_id)
                d["member_count"] = len(d["members"])
                return d
        return None

    def list_departments(self, active_only=True):
        with get_db() as db:
            q = "SELECT * FROM departments"
            if active_only:
                q += " WHERE is_active=1"
            q += " ORDER BY name"
            rows = db.execute(q).fetchall()
            depts = []
            for r in rows:
                d = dict(r)
                d["member_count"] = db.execute(
                    "SELECT COUNT(*) as c FROM department_members WHERE department_id=?",
                    (d["id"],)
                ).fetchone()["c"]
                depts.append(d)
            return depts

    def update_department(self, dept_id, **kwargs):
        allowed = {"name", "description", "icon", "color", "budget_monthly",
                    "budget_warning_pct", "budget_hard_stop", "is_active"}
        fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not fields:
            return self.get_department(dept_id)
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [dept_id]
        with get_db() as db:
            db.execute(f"UPDATE departments SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
        return self.get_department(dept_id)

    def delete_department(self, dept_id):
        with get_db() as db:
            db.execute("DELETE FROM department_members WHERE department_id=?", (dept_id,))
            db.execute("DELETE FROM department_agent_access WHERE department_id=?", (dept_id,))
            db.execute("DELETE FROM department_kb_access WHERE department_id=?", (dept_id,))
            db.execute("DELETE FROM departments WHERE id=?", (dept_id,))
        logger.info(f"Department deleted: {dept_id}")

    # ── Members ──

    def add_member(self, dept_id, user_id, role="member"):
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO department_members (department_id, user_id, role)
                VALUES (?,?,?)
            """, (dept_id, user_id, role))
        logger.info(f"User {user_id} added to department {dept_id} as {role}")

    def remove_member(self, dept_id, user_id):
        with get_db() as db:
            db.execute(
                "DELETE FROM department_members WHERE department_id=? AND user_id=?",
                (dept_id, user_id)
            )

    def get_user_departments(self, user_id):
        with get_db() as db:
            rows = db.execute("""
                SELECT d.*, dm.role as member_role
                FROM departments d
                JOIN department_members dm ON d.id=dm.department_id
                WHERE dm.user_id=? AND d.is_active=1
                ORDER BY d.name
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def _get_members(self, db, dept_id):
        rows = db.execute("""
            SELECT u.id, u.email, u.display_name, u.role as user_role,
                   u.avatar_color, u.is_active, dm.role as dept_role, dm.joined_at
            FROM department_members dm
            JOIN users u ON dm.user_id=u.id
            WHERE dm.department_id=?
            ORDER BY dm.role DESC, u.display_name
        """, (dept_id,)).fetchall()
        return [dict(r) for r in rows]

    def is_member(self, dept_id, user_id):
        with get_db() as db:
            row = db.execute(
                "SELECT 1 FROM department_members WHERE department_id=? AND user_id=?",
                (dept_id, user_id)
            ).fetchone()
            return row is not None

    # ── Agent Access ──

    def assign_agent(self, dept_id, agent_id):
        with get_db() as db:
            db.execute("""
                INSERT OR IGNORE INTO department_agent_access (department_id, agent_id)
                VALUES (?,?)
            """, (dept_id, agent_id))

    def unassign_agent(self, dept_id, agent_id):
        with get_db() as db:
            db.execute(
                "DELETE FROM department_agent_access WHERE department_id=? AND agent_id=?",
                (dept_id, agent_id)
            )

    def get_accessible_agent_ids(self, user_id, user_role="member"):
        """Get agent IDs this user can access based on department membership."""
        if user_role in ("owner", "admin"):
            return None  # Admins see all
        with get_db() as db:
            # Company-wide agents
            company_ids = [r["id"] for r in db.execute(
                "SELECT id FROM agents WHERE company_wide=1"
            ).fetchall()]
            # Dept-scoped agents
            dept_ids = [r["agent_id"] for r in db.execute("""
                SELECT DISTINCT da.agent_id
                FROM department_agent_access da
                JOIN department_members dm ON da.department_id=dm.department_id
                WHERE dm.user_id=?
            """, (user_id,)).fetchall()]
            # Own agents
            own_ids = [r["id"] for r in db.execute(
                "SELECT id FROM agents WHERE owner_id=?", (user_id,)
            ).fetchall()]
            return list(set(company_ids + dept_ids + own_ids))

    # ── KB Access ──

    def assign_kb_folder(self, dept_id, folder_id):
        with get_db() as db:
            db.execute("""
                INSERT OR IGNORE INTO department_kb_access (department_id, folder_id)
                VALUES (?,?)
            """, (dept_id, folder_id))

    def unassign_kb_folder(self, dept_id, folder_id):
        with get_db() as db:
            db.execute(
                "DELETE FROM department_kb_access WHERE department_id=? AND folder_id=?",
                (dept_id, folder_id)
            )

    def get_accessible_folder_ids(self, user_id, user_role="member"):
        """Get KB folder IDs this user can access."""
        if user_role in ("owner", "admin"):
            return None  # Admins see all
        with get_db() as db:
            company_ids = [r["id"] for r in db.execute(
                "SELECT id FROM kb_folders WHERE company_wide=1"
            ).fetchall()]
            dept_ids = [r["folder_id"] for r in db.execute("""
                SELECT DISTINCT dk.folder_id
                FROM department_kb_access dk
                JOIN department_members dm ON dk.department_id=dm.department_id
                WHERE dm.user_id=?
            """, (user_id,)).fetchall()]
            own_ids = [r["id"] for r in db.execute(
                "SELECT id FROM kb_folders WHERE owner_id=?", (user_id,)
            ).fetchall()]
            return list(set(company_ids + dept_ids + own_ids))

    # ── Spend ──

    def get_department_spend(self, dept_id, period="month"):
        with get_db() as db:
            if period == "month":
                where = "AND created_at >= date('now', 'start of month')"
            elif period == "week":
                where = "AND created_at >= date('now', '-7 days')"
            else:
                where = ""
            row = db.execute(f"""
                SELECT COALESCE(SUM(cost_estimate), 0) as total_cost,
                       COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens,
                       COUNT(*) as request_count
                FROM usage_log WHERE department_id=? {where}
            """, (dept_id,)).fetchone()
            return dict(row)
