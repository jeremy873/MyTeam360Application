# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Task / Project Board — Kanban-style project management with AI integration.

Replaces: Trello ($10/mo), Asana ($25/mo), Monday.com ($36/mo)

Features:
  - Projects with customizable Kanban columns
  - Tasks with priority, due dates, assignments, labels
  - Subtasks (checklist items within a task)
  - Comments on tasks
  - AI task creation from conversations and Roundtable action items
  - Drag-and-drop column movement via API
  - Project templates for common workflows
  - Dashboard: overdue, due today, by priority, by assignee
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.tasks")


DEFAULT_COLUMNS = [
    {"id": "backlog", "label": "Backlog", "color": "#94a3b8", "order": 0},
    {"id": "todo", "label": "To Do", "color": "#3b82f6", "order": 1},
    {"id": "in_progress", "label": "In Progress", "color": "#f59e0b", "order": 2},
    {"id": "review", "label": "Review", "color": "#a459f2", "order": 3},
    {"id": "done", "label": "Done", "color": "#22c55e", "order": 4},
]

PROJECT_TEMPLATES = {
    "product_launch": {
        "name": "Product Launch",
        "columns": DEFAULT_COLUMNS,
        "tasks": [
            {"title": "Finalize product features", "column": "todo", "priority": "high"},
            {"title": "Create landing page", "column": "todo", "priority": "high"},
            {"title": "Write press release", "column": "todo", "priority": "medium"},
            {"title": "Set up analytics tracking", "column": "todo", "priority": "medium"},
            {"title": "Create social media campaign", "column": "todo", "priority": "medium"},
            {"title": "Prepare email announcement", "column": "todo", "priority": "medium"},
            {"title": "Beta testing", "column": "todo", "priority": "high"},
            {"title": "Fix critical bugs", "column": "todo", "priority": "high"},
            {"title": "Deploy to production", "column": "todo", "priority": "high"},
            {"title": "Post-launch monitoring", "column": "backlog", "priority": "medium"},
        ],
    },
    "client_project": {
        "name": "Client Project",
        "columns": [
            {"id": "scoping", "label": "Scoping", "color": "#94a3b8", "order": 0},
            {"id": "in_progress", "label": "In Progress", "color": "#f59e0b", "order": 1},
            {"id": "client_review", "label": "Client Review", "color": "#a459f2", "order": 2},
            {"id": "revisions", "label": "Revisions", "color": "#ef4444", "order": 3},
            {"id": "delivered", "label": "Delivered", "color": "#22c55e", "order": 4},
        ],
        "tasks": [
            {"title": "Kickoff meeting", "column": "scoping", "priority": "high"},
            {"title": "Gather requirements", "column": "scoping", "priority": "high"},
            {"title": "Create project timeline", "column": "scoping", "priority": "medium"},
            {"title": "Send proposal/contract", "column": "scoping", "priority": "high"},
            {"title": "Deliver first draft", "column": "scoping", "priority": "medium"},
            {"title": "Final delivery", "column": "scoping", "priority": "high"},
        ],
    },
    "content_calendar": {
        "name": "Content Calendar",
        "columns": [
            {"id": "ideas", "label": "Ideas", "color": "#94a3b8", "order": 0},
            {"id": "writing", "label": "Writing", "color": "#3b82f6", "order": 1},
            {"id": "editing", "label": "Editing", "color": "#f59e0b", "order": 2},
            {"id": "scheduled", "label": "Scheduled", "color": "#a459f2", "order": 3},
            {"id": "published", "label": "Published", "color": "#22c55e", "order": 4},
        ],
        "tasks": [],
    },
}


class TaskManager:
    """Kanban-style project and task management."""

    # ── Projects ──

    def create_project(self, owner_id: str, name: str,
                        description: str = "", template: str = None,
                        columns: list = None) -> dict:
        pid = f"proj_{uuid.uuid4().hex[:12]}"
        cols = columns or DEFAULT_COLUMNS

        if template and template in PROJECT_TEMPLATES:
            t = PROJECT_TEMPLATES[template]
            cols = t["columns"]

        with get_db() as db:
            db.execute("""
                INSERT INTO task_projects
                    (id, owner_id, name, description, columns, status)
                VALUES (?,?,?,?,?,?)
            """, (pid, owner_id, name, description, json.dumps(cols), "active"))

        # Seed tasks from template
        tasks_created = 0
        if template and template in PROJECT_TEMPLATES:
            for task in PROJECT_TEMPLATES[template].get("tasks", []):
                self.create_task(pid, owner_id, task["title"],
                               column=task.get("column", "todo"),
                               priority=task.get("priority", "medium"))
                tasks_created += 1

        return {"id": pid, "name": name, "columns": cols,
                "template": template, "tasks_created": tasks_created}

    def list_projects(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM task_projects WHERE owner_id=? AND status='active' ORDER BY created_at DESC",
                (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["columns"] = json.loads(d.get("columns", "[]"))
            # Count tasks
            tasks = db.execute(
                "SELECT column_id, COUNT(*) as c FROM tasks WHERE project_id=? GROUP BY column_id",
                (d["id"],)).fetchall()
            d["task_counts"] = {dict(t)["column_id"]: dict(t)["c"] for t in tasks}
            d["total_tasks"] = sum(d["task_counts"].values())
            result.append(d)
        return result

    def get_project(self, project_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM task_projects WHERE id=?",
                            (project_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["columns"] = json.loads(d.get("columns", "[]"))
        return d

    def update_project(self, project_id: str, **updates) -> dict:
        if "columns" in updates:
            updates["columns"] = json.dumps(updates["columns"])
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [project_id]
        with get_db() as db:
            db.execute(f"UPDATE task_projects SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def archive_project(self, project_id: str) -> dict:
        return self.update_project(project_id, status="archived")

    def get_templates(self) -> dict:
        return {k: {"name": v["name"], "columns": v["columns"],
                     "task_count": len(v.get("tasks", []))}
                for k, v in PROJECT_TEMPLATES.items()}

    # ── Tasks ──

    def create_task(self, project_id: str, owner_id: str, title: str,
                     description: str = "", column: str = "todo",
                     priority: str = "medium", assigned_to: str = "",
                     due_date: str = "", labels: list = None,
                     source: str = "", source_id: str = "") -> dict:
        """Create a task. Source can be 'conversation', 'roundtable', 'manual'."""
        tid = f"task_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO tasks
                    (id, project_id, owner_id, title, description, column_id,
                     priority, assigned_to, due_date, labels, source, source_id, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (tid, project_id, owner_id, title, description, column,
                  priority, assigned_to, due_date,
                  json.dumps(labels or []), source, source_id, "open"))
        return {"id": tid, "title": title, "column": column, "priority": priority}

    def get_board(self, project_id: str) -> dict:
        """Get the full Kanban board: columns with their tasks."""
        project = self.get_project(project_id)
        if not project:
            return {"error": "Project not found"}

        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM tasks WHERE project_id=? AND status='open' ORDER BY position, created_at",
                (project_id,)).fetchall()

        board = {}
        for col in project["columns"]:
            board[col["id"]] = {
                "column": col,
                "tasks": [],
            }

        for r in rows:
            d = dict(r)
            d["labels"] = json.loads(d.get("labels", "[]"))
            d["subtasks"] = self._get_subtasks(d["id"])
            col_id = d.get("column_id", "todo")
            if col_id in board:
                board[col_id]["tasks"].append(d)

        return {"project": project, "board": board}

    def get_task(self, task_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?",
                            (task_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["labels"] = json.loads(d.get("labels", "[]"))
        d["subtasks"] = self._get_subtasks(task_id)
        d["comments"] = self._get_comments(task_id)
        return d

    def update_task(self, task_id: str, **updates) -> dict:
        if "labels" in updates:
            updates["labels"] = json.dumps(updates["labels"])
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [task_id]
        with get_db() as db:
            db.execute(f"UPDATE tasks SET {sets} WHERE id=?", vals)
        return {"updated": True}

    def move_task(self, task_id: str, new_column: str,
                   position: int = None) -> dict:
        """Move a task to a different column (drag and drop)."""
        updates = {"column_id": new_column}
        if position is not None:
            updates["position"] = position
        return self.update_task(task_id, **updates)

    def complete_task(self, task_id: str) -> dict:
        return self.update_task(task_id, status="completed", column_id="done",
                               completed_at=datetime.now().isoformat())

    def delete_task(self, task_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            db.execute("DELETE FROM task_subtasks WHERE task_id=?", (task_id,))
            db.execute("DELETE FROM task_comments WHERE task_id=?", (task_id,))
        return {"deleted": True}

    # ── Subtasks ──

    def add_subtask(self, task_id: str, title: str) -> dict:
        sid = f"sub_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO task_subtasks (id, task_id, title, completed)
                VALUES (?,?,?,0)
            """, (sid, task_id, title))
        return {"id": sid, "title": title, "completed": False}

    def toggle_subtask(self, subtask_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "UPDATE task_subtasks SET completed = CASE WHEN completed=0 THEN 1 ELSE 0 END WHERE id=?",
                (subtask_id,))
        return {"toggled": True}

    def _get_subtasks(self, task_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM task_subtasks WHERE task_id=? ORDER BY created_at",
                (task_id,)).fetchall()
        return [dict(r) for r in rows]

    # ── Comments ──

    def add_comment(self, task_id: str, user_id: str, content: str) -> dict:
        cid = f"cmt_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO task_comments (id, task_id, user_id, content)
                VALUES (?,?,?,?)
            """, (cid, task_id, user_id, content))
        return {"id": cid, "content": content}

    def _get_comments(self, task_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM task_comments WHERE task_id=? ORDER BY created_at",
                (task_id,)).fetchall()
        return [dict(r) for r in rows]

    # ── AI Integration ──

    def create_tasks_from_action_items(self, project_id: str, owner_id: str,
                                        action_items: list) -> list:
        """Bulk create tasks from Roundtable whiteboard action items."""
        created = []
        for item in action_items:
            task = self.create_task(
                project_id, owner_id,
                title=item.get("content", item.get("title", "")),
                assigned_to=item.get("author", item.get("assigned_to", "")),
                priority=self._extract_priority(item.get("tags", [])),
                due_date=self._extract_due_date(item.get("tags", [])),
                source="roundtable",
                source_id=item.get("id", ""))
            created.append(task)
        return created

    def _extract_priority(self, tags: list) -> str:
        for t in tags:
            if t.startswith("priority:"):
                return t.split(":")[1]
        return "medium"

    def _extract_due_date(self, tags: list) -> str:
        for t in tags:
            if t.startswith("due:"):
                return t.split(":")[1]
        return ""

    # ── Dashboard ──

    def get_dashboard(self, owner_id: str) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db() as db:
            total = db.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE owner_id=? AND status='open'",
                (owner_id,)).fetchone()
            overdue = db.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE owner_id=? AND status='open' "
                "AND due_date!='' AND due_date<?",
                (owner_id, today)).fetchone()
            due_today = db.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE owner_id=? AND status='open' "
                "AND due_date=?",
                (owner_id, today)).fetchone()
            by_priority = db.execute(
                "SELECT priority, COUNT(*) as c FROM tasks WHERE owner_id=? AND status='open' "
                "GROUP BY priority",
                (owner_id,)).fetchall()
            completed_week = db.execute(
                "SELECT COUNT(*) as c FROM tasks WHERE owner_id=? AND status='completed' "
                "AND completed_at>?",
                (owner_id, (datetime.now() - timedelta(days=7)).isoformat())).fetchone()
            by_assignee = db.execute(
                "SELECT assigned_to, COUNT(*) as c FROM tasks WHERE owner_id=? "
                "AND status='open' AND assigned_to!='' GROUP BY assigned_to ORDER BY c DESC",
                (owner_id,)).fetchall()

        return {
            "total_open": dict(total)["c"],
            "overdue": dict(overdue)["c"],
            "due_today": dict(due_today)["c"],
            "completed_this_week": dict(completed_week)["c"],
            "by_priority": {dict(r)["priority"]: dict(r)["c"] for r in by_priority},
            "by_assignee": [dict(r) for r in by_assignee],
        }
