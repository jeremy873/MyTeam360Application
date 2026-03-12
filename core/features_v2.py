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
Advanced Features — Pipelines, Client Portals, Proof of Work,
Output Scoring, and Conversation Branching.

Pipelines: Chain agents into automated workflows (Research → Write → Edit → Publish)
Client Portals: Shareable branded agent interfaces for freelancers
Proof of Work: Auditable work reports for client billing
Output Scoring: Track feedback patterns and auto-suggest prompt improvements
Conversation Branching: Fork conversations to explore alternatives
"""

import json
import uuid
import time
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.features_v2")


# ══════════════════════════════════════════════════════════════
# PIPELINES (Agent-to-Agent Assembly Line)
# ══════════════════════════════════════════════════════════════

class PipelineManager:
    """Chain multiple agents into sequential processing pipelines."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    def create_pipeline(self, owner_id: str, name: str, description: str = "",
                        steps: list = None) -> dict:
        """Create a pipeline. Steps format: [{"agent_id": "...", "input_template": "...", "transform": ""}]"""
        pid = f"pipe_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO pipelines (id, owner_id, name, description, steps)
                VALUES (?,?,?,?,?)
            """, (pid, owner_id, name, description, json.dumps(steps or [])))
        return self.get_pipeline(pid)

    def get_pipeline(self, pipeline_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM pipelines WHERE id=?", (pipeline_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["steps"] = json.loads(d.get("steps", "[]"))
            return d

    def list_pipelines(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM pipelines WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)
            ).fetchall()
        return [dict(r, steps=json.loads(r["steps"] or "[]")) for r in rows]

    def update_pipeline(self, pipeline_id: str, data: dict) -> dict:
        updates = {}
        for k in ("name", "description", "is_active"):
            if k in data:
                updates[k] = data[k]
        if "steps" in data:
            updates["steps"] = json.dumps(data["steps"])
        if not updates:
            return self.get_pipeline(pipeline_id)
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [pipeline_id]
        with get_db() as db:
            db.execute(f"UPDATE pipelines SET {sets} WHERE id=?", vals)
        return self.get_pipeline(pipeline_id)

    def delete_pipeline(self, pipeline_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM pipelines WHERE id=?", (pipeline_id,)).rowcount > 0

    def run_pipeline(self, pipeline_id: str, initial_input: str,
                     owner_id: str = None) -> dict:
        """Execute a pipeline — run each agent in sequence, passing output to next."""
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            raise ValueError("Pipeline not found")

        run_id = f"prun_{uuid.uuid4().hex[:10]}"
        steps = pipeline.get("steps", [])
        start = time.time()

        step_results = []
        current_input = initial_input
        total_tokens = 0
        total_cost = 0.0

        with get_db() as db:
            db.execute("""
                INSERT INTO pipeline_runs (id, pipeline_id, status, input_data)
                VALUES (?,?,?,?)
            """, (run_id, pipeline_id, "running", initial_input[:5000]))

        try:
            for i, step in enumerate(steps):
                agent_id = step.get("agent_id")
                if not agent_id or not self.agents:
                    continue

                # Apply input template if provided
                template = step.get("input_template", "")
                if template:
                    step_input = template.replace("{{input}}", current_input)
                    step_input = step_input.replace("{{previous}}", current_input)
                    step_input = step_input.replace("{{original}}", initial_input)
                else:
                    step_input = current_input

                step_start = time.time()
                result = self.agents.run_agent(agent_id, step_input, user_id=owner_id)
                step_duration = int((time.time() - step_start) * 1000)

                tokens = result.get("usage", {}).get("total_tokens", 0)
                total_tokens += tokens

                step_results.append({
                    "step": i + 1,
                    "agent_id": agent_id,
                    "agent_name": result.get("agent_name", ""),
                    "input_preview": step_input[:200],
                    "output_preview": result.get("text", "")[:500],
                    "output_full": result.get("text", ""),
                    "tokens": tokens,
                    "duration_ms": step_duration,
                    "error": result.get("error", False),
                })

                if result.get("error"):
                    raise RuntimeError(f"Step {i+1} failed: {result.get('text')}")

                current_input = result.get("text", "")

            duration = int((time.time() - start) * 1000)

            with get_db() as db:
                db.execute("""
                    UPDATE pipeline_runs SET status='completed', step_results=?,
                    final_output=?, total_tokens=?, duration_ms=?, completed_at=?
                    WHERE id=?
                """, (json.dumps(step_results), current_input[:10000],
                      total_tokens, duration, datetime.now().isoformat(), run_id))
                db.execute("""
                    UPDATE pipelines SET run_count=run_count+1,
                    avg_duration_ms=((avg_duration_ms * (run_count-1)) + ?) / run_count
                    WHERE id=?
                """, (duration, pipeline_id))

            return {
                "run_id": run_id,
                "pipeline_id": pipeline_id,
                "status": "completed",
                "steps": step_results,
                "final_output": current_input,
                "total_tokens": total_tokens,
                "duration_ms": duration,
            }

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            with get_db() as db:
                db.execute("""
                    UPDATE pipeline_runs SET status='failed', step_results=?,
                    error_message=?, duration_ms=?, completed_at=? WHERE id=?
                """, (json.dumps(step_results), str(e), duration,
                      datetime.now().isoformat(), run_id))
            raise

    def get_run(self, run_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["step_results"] = json.loads(d.get("step_results", "[]"))
            return d

    def list_runs(self, pipeline_id: str, limit: int = 20) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM pipeline_runs WHERE pipeline_id=? ORDER BY started_at DESC LIMIT ?",
                (pipeline_id, limit)
            ).fetchall()
        return [dict(r, step_results=json.loads(r["step_results"] or "[]")) for r in rows]


# ══════════════════════════════════════════════════════════════
# CLIENT PORTALS
# ══════════════════════════════════════════════════════════════

class ClientPortalManager:
    """Shareable branded agent interfaces for freelancers."""

    def create_portal(self, owner_id: str, name: str, agent_id: str,
                      slug: str = None, branding: dict = None,
                      welcome_message: str = "",
                      require_email: bool = False) -> dict:
        portal_id = f"portal_{uuid.uuid4().hex[:10]}"
        slug = slug or f"p-{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO client_portals
                    (id, owner_id, name, slug, agent_id, branding, welcome_message, require_email)
                VALUES (?,?,?,?,?,?,?,?)
            """, (portal_id, owner_id, name, slug, agent_id,
                  json.dumps(branding or {}), welcome_message, int(require_email)))
        return self.get_portal(portal_id)

    def get_portal(self, portal_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM client_portals WHERE id=?", (portal_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["branding"] = json.loads(d.get("branding", "{}"))
            d["allowed_domains"] = json.loads(d.get("allowed_domains", "[]"))
            return d

    def get_portal_by_slug(self, slug: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM client_portals WHERE slug=?", (slug,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["branding"] = json.loads(d.get("branding", "{}"))
            return d

    def list_portals(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM client_portals WHERE owner_id=? ORDER BY created_at DESC",
                (owner_id,)
            ).fetchall()
        return [dict(r, branding=json.loads(r["branding"] or "{}")) for r in rows]

    def update_portal(self, portal_id: str, data: dict) -> dict:
        allowed = {"name", "branding", "welcome_message", "require_email", "is_active",
                    "max_messages_per_session", "allowed_domains"}
        updates = {}
        for k, v in data.items():
            if k in allowed:
                updates[k] = json.dumps(v) if k in ("branding", "allowed_domains") else v
        if not updates:
            return self.get_portal(portal_id)
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [portal_id]
        with get_db() as db:
            db.execute(f"UPDATE client_portals SET {sets} WHERE id=?", vals)
        return self.get_portal(portal_id)

    def delete_portal(self, portal_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM client_portals WHERE id=?", (portal_id,)).rowcount > 0

    def create_session(self, portal_id: str, client_name: str = "",
                       client_email: str = "", ip: str = "") -> dict:
        sid = f"psess_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO portal_sessions (id, portal_id, client_name, client_email, ip_address)
                VALUES (?,?,?,?,?)
            """, (sid, portal_id, client_name, client_email, ip))
            db.execute("UPDATE client_portals SET total_sessions=total_sessions+1 WHERE id=?", (portal_id,))
        return {"session_id": sid, "portal_id": portal_id}

    def log_message(self, portal_id: str, session_id: str, tokens: int = 0, cost: float = 0):
        with get_db() as db:
            db.execute("""
                UPDATE portal_sessions SET message_count=message_count+1,
                tokens_used=tokens_used+?, cost=cost+?, last_message_at=?
                WHERE id=?
            """, (tokens, cost, datetime.now().isoformat(), session_id))
            db.execute("UPDATE client_portals SET total_messages=total_messages+1 WHERE id=?", (portal_id,))

    def get_portal_analytics(self, portal_id: str) -> dict:
        with get_db() as db:
            portal = db.execute("SELECT * FROM client_portals WHERE id=?", (portal_id,)).fetchone()
            sessions = db.execute(
                "SELECT * FROM portal_sessions WHERE portal_id=? ORDER BY created_at DESC LIMIT 50",
                (portal_id,)
            ).fetchall()
            totals = db.execute("""
                SELECT SUM(message_count) as msgs, SUM(tokens_used) as tokens,
                       SUM(cost) as cost, COUNT(*) as sessions
                FROM portal_sessions WHERE portal_id=?
            """, (portal_id,)).fetchone()
        return {
            "portal": dict(portal) if portal else {},
            "sessions": [dict(s) for s in sessions],
            "totals": dict(totals) if totals else {},
        }


# ══════════════════════════════════════════════════════════════
# PROOF OF WORK / AUDIT REPORTS
# ══════════════════════════════════════════════════════════════

class WorkReportManager:
    """Generate auditable work reports for client billing."""

    def generate_report(self, owner_id: str, title: str,
                        period_start: str, period_end: str,
                        agent_ids: list = None) -> dict:
        report_id = f"rpt_{uuid.uuid4().hex[:10]}"

        with get_db() as db:
            # Gather conversation data
            agent_filter = ""
            params = [owner_id, period_start, period_end]
            if agent_ids:
                placeholders = ",".join("?" * len(agent_ids))
                agent_filter = f"AND c.agent_id IN ({placeholders})"
                params.extend(agent_ids)

            conversations = db.execute(f"""
                SELECT c.id, c.title, c.agent_id, c.created_at,
                    COUNT(m.id) as message_count,
                    SUM(m.tokens_used) as total_tokens,
                    SUM(m.cost_estimate) as total_cost
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.user_id=? AND c.created_at >= ? AND c.created_at <= ?
                    {agent_filter}
                GROUP BY c.id
                ORDER BY c.created_at
            """, params).fetchall()

            # Gather agent stats
            agent_stats = {}
            for c in conversations:
                aid = c["agent_id"] or "unknown"
                if aid not in agent_stats:
                    agent_stats[aid] = {"conversations": 0, "messages": 0, "tokens": 0, "cost": 0}
                agent_stats[aid]["conversations"] += 1
                agent_stats[aid]["messages"] += c["message_count"] or 0
                agent_stats[aid]["tokens"] += c["total_tokens"] or 0
                agent_stats[aid]["cost"] += c["total_cost"] or 0

            total_conversations = len(conversations)
            total_messages = sum(c["message_count"] or 0 for c in conversations)
            total_tokens = sum(c["total_tokens"] or 0 for c in conversations)
            total_cost = sum(c["total_cost"] or 0 for c in conversations)

            summary = {
                "period": f"{period_start} to {period_end}",
                "agent_breakdown": agent_stats,
            }

            detail_rows = [dict(c) for c in conversations]

            db.execute("""
                INSERT INTO work_reports
                    (id, owner_id, title, period_start, period_end, agent_ids,
                     summary, detail_rows, total_tokens, total_cost,
                     total_conversations, total_messages)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (report_id, owner_id, title, period_start, period_end,
                  json.dumps(agent_ids or []), json.dumps(summary),
                  json.dumps(detail_rows), total_tokens, total_cost,
                  total_conversations, total_messages))

        return self.get_report(report_id)

    def get_report(self, report_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM work_reports WHERE id=?", (report_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["summary"] = json.loads(d.get("summary", "{}"))
            d["detail_rows"] = json.loads(d.get("detail_rows", "[]"))
            d["agent_ids"] = json.loads(d.get("agent_ids", "[]"))
            return d

    def list_reports(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT id, title, period_start, period_end, total_tokens, total_cost, "
                "total_conversations, total_messages, generated_at "
                "FROM work_reports WHERE owner_id=? ORDER BY generated_at DESC",
                (owner_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_report(self, report_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM work_reports WHERE id=?", (report_id,)).rowcount > 0


# ══════════════════════════════════════════════════════════════
# OUTPUT SCORING + AUTO-IMPROVE
# ══════════════════════════════════════════════════════════════

class OutputScorer:
    """Track feedback patterns and suggest prompt improvements."""

    def record_feedback(self, message_id: str, agent_id: str, rating: int,
                        feedback: str = "", tags: list = None):
        """Record detailed feedback on a message. rating: 1 (bad) to 5 (great)."""
        with get_db() as db:
            db.execute("""
                UPDATE messages SET rating=?, feedback=?, feedback_tags=? WHERE id=?
            """, (rating, feedback, json.dumps(tags or []), message_id))
            # Update agent average
            if agent_id:
                stats = db.execute("""
                    SELECT AVG(rating) as avg, COUNT(*) as cnt FROM messages
                    WHERE agent_id=? AND rating > 0
                """, (agent_id,)).fetchone()
                if stats:
                    db.execute(
                        "UPDATE agents SET avg_rating=?, rating_count=? WHERE id=?",
                        (round(stats["avg"] or 0, 2), stats["cnt"] or 0, agent_id)
                    )

    def get_agent_feedback_analysis(self, agent_id: str) -> dict:
        """Analyze feedback patterns for an agent to suggest improvements."""
        with get_db() as db:
            # Get rated messages
            rated = db.execute("""
                SELECT rating, feedback, feedback_tags, content, role
                FROM messages WHERE agent_id=? AND rating > 0
                ORDER BY created_at DESC LIMIT 100
            """, (agent_id,)).fetchall()

            if not rated:
                return {"agent_id": agent_id, "sample_size": 0, "suggestions": []}

            total = len(rated)
            positive = len([r for r in rated if r["rating"] >= 4])
            negative = len([r for r in rated if r["rating"] <= 2])
            avg_rating = sum(r["rating"] for r in rated) / total

            # Collect tags
            all_tags = {}
            neg_tags = {}
            for r in rated:
                try:
                    tags = json.loads(r["feedback_tags"] or "[]")
                except Exception:
                    tags = []
                for tag in tags:
                    all_tags[tag] = all_tags.get(tag, 0) + 1
                    if r["rating"] <= 2:
                        neg_tags[tag] = neg_tags.get(tag, 0) + 1

            # Generate suggestions based on patterns
            suggestions = []
            if neg_tags.get("too_long", 0) > 2:
                suggestions.append({
                    "type": "instruction_edit",
                    "priority": "high",
                    "suggestion": "Add instruction: 'Keep responses concise and under 200 words unless asked for detail.'",
                    "reason": f"Users marked {neg_tags['too_long']} responses as too long",
                })
            if neg_tags.get("wrong_tone", 0) > 2:
                suggestions.append({
                    "type": "instruction_edit",
                    "priority": "high",
                    "suggestion": "Review and clarify the tone/voice instructions",
                    "reason": f"Users flagged {neg_tags['wrong_tone']} responses for wrong tone",
                })
            if neg_tags.get("inaccurate", 0) > 1:
                suggestions.append({
                    "type": "instruction_edit",
                    "priority": "critical",
                    "suggestion": "Add instruction: 'Always verify claims. If unsure, say so.'",
                    "reason": f"Users flagged {neg_tags['inaccurate']} responses as inaccurate",
                })
            if neg_tags.get("off_topic", 0) > 1:
                suggestions.append({
                    "type": "instruction_edit",
                    "priority": "medium",
                    "suggestion": "Add clearer scope boundaries to the system instructions",
                    "reason": f"Users flagged {neg_tags['off_topic']} responses as off-topic",
                })
            if neg_tags.get("too_formal", 0) > 2:
                suggestions.append({
                    "type": "instruction_edit",
                    "priority": "medium",
                    "suggestion": "Add: 'Use a conversational, approachable tone.'",
                    "reason": f"{neg_tags['too_formal']} responses flagged as too formal",
                })
            if neg_tags.get("too_casual", 0) > 2:
                suggestions.append({
                    "type": "instruction_edit",
                    "priority": "medium",
                    "suggestion": "Add: 'Maintain a professional tone.'",
                    "reason": f"{neg_tags['too_casual']} responses flagged as too casual",
                })
            if negative > total * 0.4 and not suggestions:
                suggestions.append({
                    "type": "general",
                    "priority": "high",
                    "suggestion": "This agent has a high rejection rate. Consider rewriting the system instructions or switching models.",
                    "reason": f"{negative}/{total} responses rated poorly ({round(negative/total*100)}%)",
                })

            return {
                "agent_id": agent_id,
                "sample_size": total,
                "avg_rating": round(avg_rating, 2),
                "positive_rate": round(positive / total * 100, 1),
                "negative_rate": round(negative / total * 100, 1),
                "tag_frequency": all_tags,
                "negative_tags": neg_tags,
                "suggestions": suggestions,
            }


# ══════════════════════════════════════════════════════════════
# CONVERSATION BRANCHING
# ══════════════════════════════════════════════════════════════

class ConversationBrancher:
    """Fork conversations to explore alternatives without losing the original."""

    def branch_conversation(self, conversation_id: str, branch_point_msg_id: str,
                            branch_name: str = "", user_id: str = None) -> dict:
        """Create a branch from a specific message in a conversation."""
        with get_db() as db:
            # Get original conversation
            original = db.execute(
                "SELECT * FROM conversations WHERE id=?", (conversation_id,)
            ).fetchone()
            if not original:
                raise ValueError("Conversation not found")

            # Get messages up to branch point
            messages = db.execute("""
                SELECT * FROM messages WHERE conversation_id=?
                AND created_at <= (SELECT created_at FROM messages WHERE id=?)
                ORDER BY created_at
            """, (conversation_id, branch_point_msg_id)).fetchall()

            if not messages:
                raise ValueError("No messages found at branch point")

            # Create new conversation
            branch_id = f"conv_{uuid.uuid4().hex[:12]}"
            branch_name = branch_name or f"Branch of {original['title']}"

            db.execute("""
                INSERT INTO conversations
                    (id, user_id, agent_id, department_id, title, parent_id,
                     branch_name, branch_point_msg)
                VALUES (?,?,?,?,?,?,?,?)
            """, (branch_id, user_id or original["user_id"],
                  original["agent_id"], original.get("department_id"),
                  branch_name, conversation_id, branch_name, branch_point_msg_id))

            # Copy messages to branch
            for msg in messages:
                new_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                db.execute("""
                    INSERT INTO messages
                        (id, conversation_id, role, content, agent_id, provider,
                         model, tokens_used, cost_estimate, sources, metadata, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (new_msg_id, branch_id, msg["role"], msg["content"],
                      msg["agent_id"], msg["provider"], msg["model"],
                      msg["tokens_used"], msg["cost_estimate"],
                      msg["sources"], msg["metadata"], msg["created_at"]))

        return {
            "branch_id": branch_id,
            "parent_id": conversation_id,
            "branch_name": branch_name,
            "messages_copied": len(messages),
            "branch_point": branch_point_msg_id,
        }

    def get_branches(self, conversation_id: str) -> list:
        """Get all branches of a conversation."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM conversations WHERE parent_id=? ORDER BY created_at",
                (conversation_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_branch_tree(self, conversation_id: str) -> dict:
        """Get the full branch tree for a conversation."""
        with get_db() as db:
            original = db.execute(
                "SELECT id, title, created_at FROM conversations WHERE id=?",
                (conversation_id,)
            ).fetchone()
            branches = db.execute(
                "SELECT id, title, branch_name, branch_point_msg, created_at "
                "FROM conversations WHERE parent_id=? ORDER BY created_at",
                (conversation_id,)
            ).fetchall()
        return {
            "root": dict(original) if original else {},
            "branches": [dict(b) for b in branches],
            "total_branches": len(branches),
        }
