"""
MyTeam360 - Spend Management and Analytics
Per-model pricing, trend analytics, budget enforcement, cost reports.
"""

import csv
import io
import uuid
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.spend")

MODEL_PRICING = {
    "claude-opus-4-5-20250219":     {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5-20250929":   {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001":    {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-5-20250514":   {"input": 3.00,  "output": 15.00},
    "claude-3-5-sonnet-20241022":   {"input": 3.00,  "output": 15.00},
    "claude-3-5-haiku-20241022":    {"input": 0.80,  "output": 4.00},
    "claude-3-opus-20240229":       {"input": 15.00, "output": 75.00},
    "gpt-4o":                       {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":                  {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":                  {"input": 10.00, "output": 30.00},
    "gpt-4":                        {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo":                {"input": 0.50,  "output": 1.50},
    "o1":                           {"input": 15.00, "output": 60.00},
    "o1-mini":                      {"input": 3.00,  "output": 12.00},
    "grok-2":                       {"input": 2.00,  "output": 10.00},
    "grok-2-mini":                  {"input": 0.20,  "output": 1.00},
    "llama3":                       {"input": 0.00,  "output": 0.00},
    "mistral":                      {"input": 0.00,  "output": 0.00},
    "codellama":                    {"input": 0.00,  "output": 0.00},
}

DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


def calculate_cost(model, tokens_in, tokens_out):
    pricing = MODEL_PRICING.get(model or "", DEFAULT_PRICING)
    if model and any(model.startswith(p) for p in ["llama", "mistral", "codellama", "phi", "qwen"]):
        return 0.0
    cost = (tokens_in * pricing["input"] / 1_000_000) + (tokens_out * pricing["output"] / 1_000_000)
    return round(cost, 6)


class SpendManager:

    def get_daily_spend(self, days=30, user_id=None, dept_id=None):
        with get_db() as db:
            wc = "WHERE created_at >= date('now', ?)"
            params = ["-{} days".format(days)]
            if user_id:
                wc += " AND user_id=?"
                params.append(user_id)
            if dept_id:
                wc += " AND department_id=?"
                params.append(dept_id)
            rows = db.execute(
                "SELECT date(created_at) as day, COUNT(*) as requests,"
                " COALESCE(SUM(tokens_in),0) as tokens_in,"
                " COALESCE(SUM(tokens_out),0) as tokens_out,"
                " COALESCE(SUM(cost_estimate),0) as cost"
                " FROM usage_log " + wc +
                " GROUP BY date(created_at) ORDER BY day", params).fetchall()
            return [dict(r) for r in rows]

    def get_hourly_spend(self, hours=24):
        with get_db() as db:
            rows = db.execute(
                "SELECT strftime('%Y-%m-%d %H:00', created_at) as hour,"
                " COUNT(*) as requests, COALESCE(SUM(cost_estimate),0) as cost"
                " FROM usage_log WHERE created_at >= datetime('now', ?)"
                " GROUP BY hour ORDER BY hour",
                ("-{} hours".format(hours),)).fetchall()
            return [dict(r) for r in rows]

    def get_model_breakdown(self, days=30):
        with get_db() as db:
            rows = db.execute(
                "SELECT provider, model, COUNT(*) as requests,"
                " COALESCE(SUM(tokens_in),0) as tokens_in,"
                " COALESCE(SUM(tokens_out),0) as tokens_out,"
                " COALESCE(SUM(cost_estimate),0) as cost"
                " FROM usage_log WHERE created_at >= date('now', ?)"
                " GROUP BY provider, model ORDER BY cost DESC",
                ("-{} days".format(days),)).fetchall()
            return [dict(r) for r in rows]

    def get_agent_costs(self, days=30):
        with get_db() as db:
            rows = db.execute(
                "SELECT u.agent_id, a.name as agent_name, a.icon,"
                " COUNT(*) as requests,"
                " COALESCE(SUM(u.cost_estimate),0) as cost,"
                " COUNT(DISTINCT u.user_id) as unique_users,"
                " COALESCE(SUM(u.tokens_in + u.tokens_out),0) as total_tokens"
                " FROM usage_log u LEFT JOIN agents a ON u.agent_id = a.id"
                " WHERE u.created_at >= date('now', ?)"
                " GROUP BY u.agent_id ORDER BY cost DESC",
                ("-{} days".format(days),)).fetchall()
            return [dict(r) for r in rows]

    def get_user_leaderboard(self, days=30):
        with get_db() as db:
            rows = db.execute(
                "SELECT u.user_id, usr.display_name, usr.email, usr.avatar_color,"
                " COUNT(*) as requests,"
                " COALESCE(SUM(u.cost_estimate),0) as cost,"
                " COALESCE(SUM(u.tokens_in + u.tokens_out),0) as total_tokens,"
                " COUNT(DISTINCT u.agent_id) as agents_used"
                " FROM usage_log u LEFT JOIN users usr ON u.user_id = usr.id"
                " WHERE u.created_at >= date('now', ?)"
                " GROUP BY u.user_id ORDER BY cost DESC",
                ("-{} days".format(days),)).fetchall()
            return [dict(r) for r in rows]

    def check_budget_enforcement(self, user_id, dept_id=None):
        warnings = []
        with get_db() as db:
            user_spend = db.execute(
                "SELECT COALESCE(SUM(cost_estimate),0) as cost FROM usage_log"
                " WHERE user_id=? AND created_at >= date('now','start of month')",
                (user_id,)).fetchone()["cost"]
            user_limit_row = db.execute(
                "SELECT monthly_limit, warning_pct, hard_stop FROM budget_limits"
                " WHERE scope='user' AND scope_id=?", (user_id,)).fetchone()

            dept_spend = 0
            dept_limit_row = None
            if dept_id:
                dept_spend = db.execute(
                    "SELECT COALESCE(SUM(cost_estimate),0) as cost FROM usage_log"
                    " WHERE department_id=? AND created_at >= date('now','start of month')",
                    (dept_id,)).fetchone()["cost"]
                dept_limit_row = db.execute(
                    "SELECT monthly_limit, warning_pct, hard_stop FROM budget_limits"
                    " WHERE scope='department' AND scope_id=?", (dept_id,)).fetchone()

            ws_limit_row = db.execute(
                "SELECT monthly_limit, warning_pct, hard_stop FROM budget_limits WHERE scope='workspace'"
            ).fetchone()
            ws_spend = db.execute(
                "SELECT COALESCE(SUM(cost_estimate),0) as cost FROM usage_log"
                " WHERE created_at >= date('now','start of month')").fetchone()["cost"]

        allowed = True
        user_budget = self._check_limit(user_spend, user_limit_row)
        if user_budget.get("warning"):
            warnings.append("User budget: {:.0f}% used".format(user_budget["pct"]))
        if not user_budget["allowed"]:
            allowed = False

        dept_budget = self._check_limit(dept_spend, dept_limit_row) if dept_id else {"allowed": True, "pct": 0}
        if dept_budget.get("warning"):
            warnings.append("Dept budget: {:.0f}% used".format(dept_budget["pct"]))
        if not dept_budget["allowed"]:
            allowed = False

        ws_budget = self._check_limit(ws_spend, ws_limit_row)
        if ws_budget.get("warning"):
            warnings.append("Workspace budget: {:.0f}% used".format(ws_budget["pct"]))
        if not ws_budget["allowed"]:
            allowed = False

        return {
            "allowed": allowed, "warnings": warnings,
            "user": {**user_budget, "spent": user_spend},
            "department": {**dept_budget, "spent": dept_spend} if dept_id else None,
            "workspace": {**ws_budget, "spent": ws_spend},
        }

    def _check_limit(self, spent, limit_row):
        if not limit_row or not limit_row["monthly_limit"]:
            return {"allowed": True, "pct": 0, "limit": 0, "warning": False}
        limit = limit_row["monthly_limit"]
        pct = (spent / limit * 100) if limit > 0 else 0
        warning_pct = limit_row["warning_pct"] or 80
        hard_stop = bool(limit_row["hard_stop"])
        return {"allowed": not (hard_stop and pct >= 100), "pct": round(pct, 1),
                "limit": limit, "warning": pct >= warning_pct, "hard_stop": hard_stop}

    def set_budget(self, scope, scope_id, monthly_limit, warning_pct=80, hard_stop=False):
        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM budget_limits WHERE scope=? AND scope_id=?",
                (scope, scope_id or "")).fetchone()
            if existing:
                db.execute(
                    "UPDATE budget_limits SET monthly_limit=?, warning_pct=?, hard_stop=? WHERE id=?",
                    (monthly_limit, warning_pct, 1 if hard_stop else 0, existing["id"]))
            else:
                bid = "bgt_" + uuid.uuid4().hex[:8]
                db.execute(
                    "INSERT INTO budget_limits (id, scope, scope_id, monthly_limit, warning_pct, hard_stop)"
                    " VALUES (?,?,?,?,?,?)",
                    (bid, scope, scope_id or "", monthly_limit, warning_pct, 1 if hard_stop else 0))
        return {"scope": scope, "scope_id": scope_id, "monthly_limit": monthly_limit,
                "warning_pct": warning_pct, "hard_stop": hard_stop}

    def get_budgets(self):
        with get_db() as db:
            rows = db.execute(
                "SELECT b.*,"
                " CASE WHEN b.scope='user' THEN u.display_name"
                "      WHEN b.scope='department' THEN d.name"
                "      ELSE 'Workspace' END as scope_name"
                " FROM budget_limits b"
                " LEFT JOIN users u ON b.scope='user' AND b.scope_id=u.id"
                " LEFT JOIN departments d ON b.scope='department' AND b.scope_id=d.id"
                " ORDER BY b.scope, b.scope_id").fetchall()
            return [dict(r) for r in rows]

    def get_forecast(self):
        with get_db() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(cost_estimate),0) as mtd_cost,"
                " COUNT(DISTINCT date(created_at)) as active_days"
                " FROM usage_log WHERE created_at >= date('now','start of month')"
            ).fetchone()
        mtd = row["mtd_cost"]
        active_days = max(row["active_days"], 1)
        daily_rate = mtd / active_days
        remaining = max(30 - datetime.now().day, 0)
        return {"mtd_cost": round(mtd, 2), "daily_rate": round(daily_rate, 2),
                "projected_eom": round(mtd + daily_rate * remaining, 2),
                "active_days": active_days, "remaining_days": remaining}

    def export_spend_csv(self, days=30):
        with get_db() as db:
            rows = db.execute(
                "SELECT u.created_at, u.user_id, usr.display_name, usr.email,"
                " u.agent_id, a.name as agent_name,"
                " u.provider, u.model, u.tokens_in, u.tokens_out,"
                " u.cost_estimate, u.department_id"
                " FROM usage_log u"
                " LEFT JOIN users usr ON u.user_id = usr.id"
                " LEFT JOIN agents a ON u.agent_id = a.id"
                " WHERE u.created_at >= date('now', ?)"
                " ORDER BY u.created_at DESC",
                ("-{} days".format(days),)).fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "User", "Email", "Agent", "Provider", "Model",
                         "Tokens In", "Tokens Out", "Cost ($)", "Department"])
        for r in rows:
            writer.writerow([
                r["created_at"], r["display_name"], r["email"],
                r["agent_name"] or r["agent_id"], r["provider"], r["model"],
                r["tokens_in"], r["tokens_out"], "{:.4f}".format(r["cost_estimate"]),
                r["department_id"] or ""])
        return output.getvalue()

    def recalculate_costs(self):
        updated = 0
        with get_db() as db:
            rows = db.execute("SELECT id, model, tokens_in, tokens_out FROM usage_log").fetchall()
            for r in rows:
                new_cost = calculate_cost(r["model"] or "", r["tokens_in"] or 0, r["tokens_out"] or 0)
                db.execute("UPDATE usage_log SET cost_estimate=? WHERE id=?", (new_cost, r["id"]))
                updated += 1
        logger.info("Recalculated costs for {} usage records".format(updated))
        return updated
