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
Workflows — Multi-step agent pipelines with scheduling, approvals, and webhook triggers.
"""

import os
import uuid
import json
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.workflows")


class WorkflowEngine:
    """Runs multi-agent workflows with approval gates and scheduling."""

    def __init__(self, agent_manager):
        self.agents = agent_manager

    def create_workflow(self, data: dict, owner_id: str) -> dict:
        wf_id = f"wf_{uuid.uuid4().hex[:10]}"
        webhook_token = f"whk_{uuid.uuid4().hex[:16]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO workflows (id, owner_id, name, description, icon, steps, shared, schedule, webhook_token)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (wf_id, owner_id, data.get("name","New Workflow"), data.get("description",""),
                  data.get("icon","⚡"), json.dumps(data.get("steps",[])),
                  int(data.get("shared",False)), data.get("schedule"), webhook_token))
        return self.get_workflow(wf_id)

    def get_workflow(self, wf_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM workflows WHERE id=?", (wf_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["steps"] = json.loads(d.get("steps", "[]"))
            except Exception:
                d["steps"] = []
            return d

    def list_workflows(self, user_id: str = None) -> list:
        with get_db() as db:
            if user_id:
                rows = db.execute("SELECT * FROM workflows WHERE owner_id=? OR shared=1 ORDER BY name",
                                  (user_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM workflows ORDER BY name").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["steps"] = json.loads(d.get("steps","[]"))
                except Exception:
                    d["steps"] = []
                result.append(d)
            return result

    def update_workflow(self, wf_id: str, data: dict) -> dict | None:
        allowed = {"name","description","icon","steps","shared","schedule"}
        updates = {}
        for k, v in data.items():
            if k in allowed:
                updates[k] = json.dumps(v) if k == "steps" else (int(v) if k == "shared" else v)
        if not updates:
            return self.get_workflow(wf_id)
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [wf_id]
        with get_db() as db:
            db.execute(f"UPDATE workflows SET {sets} WHERE id=?", vals)
        return self.get_workflow(wf_id)

    def delete_workflow(self, wf_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM workflows WHERE id=?", (wf_id,)).rowcount > 0

    # ── Execution ──

    def run_workflow(self, wf_id: str, user_id: str, input_text: str) -> dict:
        wf = self.get_workflow(wf_id)
        if not wf:
            return {"error": "Workflow not found"}

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO workflow_runs (id, workflow_id, user_id, status, input_text, current_step)
                VALUES (?,?,?,?,?,0)
            """, (run_id, wf_id, user_id, "running", input_text))
            db.execute("UPDATE workflows SET run_count=run_count+1 WHERE id=?", (wf_id,))

        step_results = []
        current_text = input_text
        steps = wf["steps"]
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except (json.JSONDecodeError, TypeError):
                steps = []
        if not isinstance(steps, list):
            steps = []

        for i, step in enumerate(steps):
            step_type = step.get("type", "agent")

            if step_type == "agent":
                agent_id = step.get("agent_id")
                if not agent_id:
                    step_results.append({"step": i, "type": "agent", "error": "No agent specified"})
                    continue
                result = self.agents.run_agent(agent_id, current_text, user_id=user_id)
                current_text = result.get("text", "")
                step_results.append({
                    "step": i, "type": "agent", "agent_id": agent_id,
                    "agent_name": result.get("agent_name", ""),
                    "text": current_text, "provider": result.get("provider", ""),
                })

            elif step_type == "approval":
                approval_id = f"apr_{uuid.uuid4().hex[:8]}"
                with get_db() as db:
                    db.execute("""
                        INSERT INTO approvals (id, workflow_run_id, submitted_by, assigned_to, title, content, status)
                        VALUES (?,?,?,?,?,?,'pending')
                    """, (approval_id, run_id, user_id, step.get("assigned_to", user_id),
                          step.get("title", f"Approval for step {i}"), current_text))
                    db.execute("UPDATE workflow_runs SET status='paused', current_step=? WHERE id=?", (i, run_id))
                step_results.append({"step": i, "type": "approval", "approval_id": approval_id, "status": "pending"})
                self._save_run_results(run_id, step_results)
                return {"run_id": run_id, "status": "paused", "paused_at_step": i,
                        "approval_id": approval_id, "step_results": step_results}

            elif step_type == "parallel":
                agent_ids = step.get("agent_ids", [])
                parallel_results = []
                for aid in agent_ids:
                    r = self.agents.run_agent(aid, current_text, user_id=user_id)
                    parallel_results.append({"agent_id": aid, "text": r.get("text","")})
                current_text = "\n\n---\n\n".join(r["text"] for r in parallel_results)
                step_results.append({"step": i, "type": "parallel", "results": parallel_results})

            # Update progress
            with get_db() as db:
                db.execute("UPDATE workflow_runs SET current_step=? WHERE id=?", (i, run_id))

        # Complete
        self._save_run_results(run_id, step_results, status="completed")
        return {"run_id": run_id, "status": "completed", "step_results": step_results, "final_output": current_text}

    def resume_workflow(self, run_id: str, approved: bool, feedback: str = "") -> dict:
        with get_db() as db:
            run = db.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
            if not run or run["status"] != "paused":
                return {"error": "Run not found or not paused"}

            approval = db.execute(
                "SELECT id FROM approvals WHERE workflow_run_id=? AND status='pending'",
                (run_id,)).fetchone()
            if approval:
                status = "approved" if approved else "rejected"
                db.execute("UPDATE approvals SET status=?, feedback=?, resolved_at=CURRENT_TIMESTAMP WHERE id=?",
                           (status, feedback, approval["id"]))

            if not approved:
                db.execute("UPDATE workflow_runs SET status='cancelled' WHERE id=?", (run_id,))
                return {"run_id": run_id, "status": "cancelled", "feedback": feedback}

            # Continue from next step
            wf = self.get_workflow(run["workflow_id"])
            step_results = json.loads(run["step_results"]) if run["step_results"] else []
            current_step = run["current_step"] + 1
            current_text = step_results[-1].get("text", run["input_text"]) if step_results else run["input_text"]

            db.execute("UPDATE workflow_runs SET status='running' WHERE id=?", (run_id,))

        for i in range(current_step, len(wf["steps"])):
            step = wf["steps"][i]
            if step.get("type") == "agent":
                result = self.agents.run_agent(step["agent_id"], current_text, user_id=run["user_id"])
                current_text = result.get("text", "")
                step_results.append({"step": i, "type": "agent", "text": current_text})
            elif step.get("type") == "approval":
                return self._pause_at_approval(run_id, run["user_id"], i, current_text, step, step_results)

        self._save_run_results(run_id, step_results, status="completed")
        return {"run_id": run_id, "status": "completed", "step_results": step_results, "final_output": current_text}

    def _pause_at_approval(self, run_id, user_id, step_idx, text, step, results):
        approval_id = f"apr_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO approvals (id, workflow_run_id, submitted_by, assigned_to, title, content, status)
                VALUES (?,?,?,?,?,?,'pending')
            """, (approval_id, run_id, user_id, step.get("assigned_to", user_id),
                  step.get("title", f"Review step {step_idx}"), text))
            db.execute("UPDATE workflow_runs SET status='paused', current_step=? WHERE id=?", (step_idx, run_id))
        results.append({"step": step_idx, "type": "approval", "approval_id": approval_id, "status": "pending"})
        self._save_run_results(run_id, results)
        return {"run_id": run_id, "status": "paused", "paused_at_step": step_idx, "approval_id": approval_id}

    def _save_run_results(self, run_id: str, results: list, status: str = None):
        with get_db() as db:
            if status:
                db.execute("UPDATE workflow_runs SET step_results=?, status=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
                           (json.dumps(results), status, run_id))
            else:
                db.execute("UPDATE workflow_runs SET step_results=? WHERE id=?",
                           (json.dumps(results), run_id))

    def get_run(self, run_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["step_results"] = json.loads(d.get("step_results","[]"))
            except Exception:
                d["step_results"] = []
            return d

    def list_runs(self, user_id: str = None, workflow_id: str = None, limit: int = 20) -> list:
        with get_db() as db:
            if workflow_id:
                rows = db.execute("SELECT * FROM workflow_runs WHERE workflow_id=? ORDER BY started_at DESC LIMIT ?",
                                  (workflow_id, limit)).fetchall()
            elif user_id:
                rows = db.execute("SELECT * FROM workflow_runs WHERE user_id=? ORDER BY started_at DESC LIMIT ?",
                                  (user_id, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_pending_approvals(self, user_id: str) -> list:
        with get_db() as db:
            rows = db.execute("""
                SELECT a.*, w.name as workflow_name, w.icon as workflow_icon
                FROM approvals a
                JOIN workflow_runs r ON a.workflow_run_id = r.id
                JOIN workflows w ON r.workflow_id = w.id
                WHERE (a.assigned_to=? OR a.assigned_to IS NULL) AND a.status='pending'
                ORDER BY a.created_at DESC
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]
