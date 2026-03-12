"""
MyTeam360 — Agent Analytics, Templates & Recommendations Engine
© 2026 MyTeam360. All Rights Reserved.
"""
import uuid
import json
from datetime import datetime, timedelta
from .database import get_db


class AgentAnalytics:
    """Track agent performance, usage patterns, and generate recommendations."""

    # ── Agent Performance ──

    def get_agent_performance(self, agent_id):
        """Get comprehensive performance metrics for an agent."""
        with get_db() as db:
            agent = db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            if not agent:
                return None

            # Usage stats from usage_log
            usage = db.execute("""
                SELECT COUNT(*) as total_calls,
                       SUM(tokens_in) as total_tokens_in,
                       SUM(tokens_out) as total_tokens_out,
                       SUM(cost_estimate) as total_cost,
                       AVG(tokens_out) as avg_tokens_out
                FROM usage_log WHERE agent_id=?
            """, (agent_id,)).fetchone()

            # Last 30 days usage
            thirty_days = (datetime.utcnow() - timedelta(days=30)).isoformat()
            recent = db.execute("""
                SELECT COUNT(*) as calls_30d,
                       SUM(cost_estimate) as cost_30d,
                       COUNT(DISTINCT user_id) as unique_users_30d
                FROM usage_log WHERE agent_id=? AND created_at>=?
            """, (agent_id, thirty_days)).fetchone()

            # Feedback stats
            feedback = db.execute("""
                SELECT COUNT(*) as total_feedback,
                       SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) as thumbs_up,
                       SUM(CASE WHEN rating=-1 THEN 1 ELSE 0 END) as thumbs_down
                FROM message_feedback WHERE agent_id=?
            """, (agent_id,)).fetchone()

            # Conversation count
            conv_count = db.execute(
                "SELECT COUNT(*) as c FROM conversations WHERE agent_id=?", (agent_id,)
            ).fetchone()["c"]

            # Daily usage trend (last 14 days)
            fourteen_days = (datetime.utcnow() - timedelta(days=14)).isoformat()
            daily = db.execute("""
                SELECT DATE(created_at) as day, COUNT(*) as calls, SUM(cost_estimate) as cost
                FROM usage_log WHERE agent_id=? AND created_at>=?
                GROUP BY DATE(created_at) ORDER BY day
            """, (agent_id, fourteen_days)).fetchall()

            total_fb = (feedback["total_feedback"] or 0)
            thumbs_up = (feedback["thumbs_up"] or 0)

            return {
                "agent_id": agent_id,
                "agent_name": agent["name"],
                "total_calls": usage["total_calls"] or 0,
                "total_tokens_in": usage["total_tokens_in"] or 0,
                "total_tokens_out": usage["total_tokens_out"] or 0,
                "total_cost": round(usage["total_cost"] or 0, 4),
                "avg_tokens_per_response": round(usage["avg_tokens_out"] or 0),
                "conversations": conv_count,
                "calls_30d": recent["calls_30d"] or 0,
                "cost_30d": round(recent["cost_30d"] or 0, 4),
                "unique_users_30d": recent["unique_users_30d"] or 0,
                "feedback_total": total_fb,
                "thumbs_up": thumbs_up,
                "thumbs_down": (feedback["thumbs_down"] or 0),
                "satisfaction_rate": round(thumbs_up / total_fb * 100, 1) if total_fb > 0 else None,
                "avg_rating": agent["avg_rating"] or 0,
                "daily_trend": [dict(r) for r in daily],
            }

    def get_all_agent_performance(self):
        """Get performance summary for all agents."""
        with get_db() as db:
            agents = db.execute("SELECT id, name, icon, color, provider, model, run_count, avg_rating, rating_count FROM agents ORDER BY run_count DESC").fetchall()
            results = []
            for a in agents:
                usage = db.execute("""
                    SELECT COUNT(*) as calls, SUM(cost_estimate) as cost,
                           COUNT(DISTINCT user_id) as users
                    FROM usage_log WHERE agent_id=?
                """, (a["id"],)).fetchone()
                fb = db.execute("""
                    SELECT SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) as up,
                           SUM(CASE WHEN rating=-1 THEN 1 ELSE 0 END) as down
                    FROM message_feedback WHERE agent_id=?
                """, (a["id"],)).fetchone()
                total_fb = (fb["up"] or 0) + (fb["down"] or 0)
                results.append({
                    "id": a["id"], "name": a["name"], "icon": a["icon"],
                    "color": a["color"], "provider": a["provider"], "model": a["model"],
                    "total_calls": usage["calls"] or 0,
                    "total_cost": round(usage["cost"] or 0, 4),
                    "unique_users": usage["users"] or 0,
                    "thumbs_up": fb["up"] or 0,
                    "thumbs_down": fb["down"] or 0,
                    "satisfaction_rate": round((fb["up"] or 0) / total_fb * 100, 1) if total_fb > 0 else None,
                })
            return results

    # ── Message Feedback ──

    def add_feedback(self, message_id, user_id, rating, comment=""):
        """Add or update feedback on a message. rating: 1 (up) or -1 (down)."""
        with get_db() as db:
            # Get agent_id from message
            msg = db.execute("""
                SELECT m.agent_id FROM messages m
                JOIN conversations c ON m.conversation_id=c.id
                WHERE m.id=?
            """, (message_id,)).fetchone()
            agent_id = msg["agent_id"] if msg else None

            fid = f"fb_{uuid.uuid4().hex[:12]}"
            db.execute("""
                INSERT INTO message_feedback (id, message_id, user_id, agent_id, rating, comment)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, user_id) DO UPDATE SET rating=?, comment=?, created_at=CURRENT_TIMESTAMP
            """, (fid, message_id, user_id, agent_id, rating, comment, rating, comment))

            # Update agent aggregate rating
            if agent_id:
                stats = db.execute("""
                    SELECT COUNT(*) as c, AVG(rating) as avg FROM message_feedback WHERE agent_id=?
                """, (agent_id,)).fetchone()
                db.execute("UPDATE agents SET avg_rating=?, rating_count=? WHERE id=?",
                           (round(stats["avg"] or 0, 2), stats["c"] or 0, agent_id))
            db.commit()
            return {"id": fid, "message_id": message_id, "rating": rating}

    def get_feedback_for_agent(self, agent_id, limit=50):
        """Get recent feedback for an agent."""
        with get_db() as db:
            rows = db.execute("""
                SELECT mf.*, m.content as message_content, u.display_name as user_name
                FROM message_feedback mf
                JOIN messages m ON mf.message_id=m.id
                JOIN users u ON mf.user_id=u.id
                WHERE mf.agent_id=?
                ORDER BY mf.created_at DESC LIMIT ?
            """, (agent_id, limit)).fetchall()
            return [dict(r) for r in rows]


class AgentTemplateManager:
    """Manage pre-built agent templates."""

    SEED_TEMPLATES = [
        {
            "name": "Legal Researcher", "role": "Legal research and case analysis",
            "icon": "⚖️", "color": "#6366f1", "category": "legal",
            "description": "Researches case law, statutes, and legal precedents. Analyzes legal documents and summarizes findings for attorneys.",
            "instructions": "You are a legal research assistant. When given a legal question or topic, research relevant case law, statutes, and legal principles. Provide thorough analysis with citations. Always note that your analysis is for informational purposes and not legal advice.",
            "tags": '["legal","research","compliance"]'
        },
        {
            "name": "Contract Reviewer", "role": "Contract analysis and risk identification",
            "icon": "📋", "color": "#8b5cf6", "category": "legal",
            "description": "Reviews contracts for risks, missing clauses, and unfavorable terms. Flags issues and suggests improvements.",
            "instructions": "You are a contract review specialist. Analyze contracts clause by clause. Identify risks, ambiguities, missing protections, and unfavorable terms. Suggest specific improvements with alternative language. Always flag liability, indemnification, termination, and IP clauses.",
            "tags": '["legal","contracts","risk"]'
        },
        {
            "name": "Sales Email Writer", "role": "Craft persuasive sales communications",
            "icon": "📧", "color": "#10b981", "category": "sales",
            "description": "Writes compelling sales emails, follow-ups, proposals, and outreach sequences tailored to prospects.",
            "instructions": "You are a sales communications expert. Write emails that are concise, personalized, and action-oriented. Focus on value propositions, not features. Use a professional but warm tone. Include clear CTAs. Adapt style to cold outreach, warm follow-up, or proposal contexts.",
            "tags": '["sales","email","copywriting"]'
        },
        {
            "name": "Financial Analyst", "role": "Financial analysis and reporting",
            "icon": "📊", "color": "#f59e0b", "category": "finance",
            "description": "Analyzes financial data, creates reports, interprets metrics, and provides budget analysis.",
            "instructions": "You are a financial analyst. When given financial data, provide clear analysis including trends, anomalies, and actionable insights. Use precise numbers. Create structured reports with executive summaries. Flag any concerning metrics. Note that your analysis is informational, not financial advice.",
            "tags": '["finance","analytics","reporting"]'
        },
        {
            "name": "HR Policy Advisor", "role": "HR policy guidance and documentation",
            "icon": "👥", "color": "#ec4899", "category": "hr",
            "description": "Drafts HR policies, answers workplace questions, helps with employee communications, and reviews compliance.",
            "instructions": "You are an HR policy specialist. Provide guidance on workplace policies, employee relations, and HR best practices. When drafting policies, ensure they are clear, fair, and legally defensible. Always note that specific legal requirements vary by jurisdiction and recommend consulting local counsel for compliance.",
            "tags": '["hr","policy","compliance"]'
        },
        {
            "name": "Code Reviewer", "role": "Code review and engineering best practices",
            "icon": "🔍", "color": "#3b82f6", "category": "engineering",
            "description": "Reviews code for bugs, security issues, performance problems, and adherence to best practices.",
            "instructions": "You are a senior software engineer conducting code reviews. Analyze code for bugs, security vulnerabilities, performance issues, and style. Provide specific, actionable feedback with corrected examples. Prioritize issues by severity. Be constructive and educational in tone.",
            "tags": '["engineering","code","security"]'
        },
        {
            "name": "Marketing Strategist", "role": "Marketing strategy and content planning",
            "icon": "📣", "color": "#ef4444", "category": "marketing",
            "description": "Develops marketing strategies, content calendars, campaign ideas, and competitive analysis.",
            "instructions": "You are a marketing strategist. Create data-informed marketing strategies. Consider target audience, competitive landscape, and available channels. Provide specific, actionable recommendations with KPIs to track. Balance creativity with measurable outcomes.",
            "tags": '["marketing","strategy","content"]'
        },
        {
            "name": "Meeting Summarizer", "role": "Summarize meetings and extract action items",
            "icon": "📝", "color": "#22c55e", "category": "general",
            "description": "Takes meeting notes or transcripts and produces structured summaries with decisions, action items, and follow-ups.",
            "instructions": "You are a meeting summarizer. From notes or transcripts, extract: 1) Key decisions made, 2) Action items with owners and deadlines, 3) Open questions, 4) Brief summary of discussion topics. Format clearly with headers. Be concise but don't miss important details.",
            "tags": '["productivity","meetings","documentation"]'
        },
        {
            "name": "Data Analyst", "role": "Analyze data and create insights",
            "icon": "🔬", "color": "#06b6d4", "category": "engineering",
            "description": "Processes CSV/data inputs, generates statistical analysis, identifies trends, and creates data-driven recommendations.",
            "instructions": "You are a data analyst. When given data, perform thorough analysis: descriptive statistics, trend identification, anomaly detection, and correlation analysis. Present findings clearly with specific numbers. Suggest visualizations that would best represent the data. Note confidence levels and data limitations.",
            "tags": '["data","analytics","statistics"]'
        },
        {
            "name": "Customer Support Agent", "role": "Handle customer inquiries professionally",
            "icon": "🎧", "color": "#a855f7", "category": "support",
            "description": "Responds to customer questions with empathy and accuracy. Troubleshoots issues and escalates when needed.",
            "instructions": "You are a customer support specialist. Respond with empathy and professionalism. Acknowledge the customer's concern, provide clear solutions, and offer alternatives when the ideal solution isn't available. Use a friendly but professional tone. If you can't resolve an issue, explain the escalation process.",
            "tags": '["support","customer-service","troubleshooting"]'
        },
    ]

    def seed_templates(self):
        """Insert default templates if none exist."""
        with get_db() as db:
            count = db.execute("SELECT COUNT(*) as c FROM agent_templates").fetchone()["c"]
            if count > 0:
                return count
            for t in self.SEED_TEMPLATES:
                tid = f"tmpl_{uuid.uuid4().hex[:12]}"
                db.execute("""
                    INSERT INTO agent_templates (id, name, role, icon, color, description, instructions, category, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (tid, t["name"], t["role"], t["icon"], t["color"],
                      t["description"], t["instructions"], t["category"], t.get("tags", "[]")))
            db.commit()
            return len(self.SEED_TEMPLATES)

    def list_templates(self, category=None):
        """List all active templates, optionally filtered by category."""
        with get_db() as db:
            if category:
                rows = db.execute(
                    "SELECT * FROM agent_templates WHERE is_active=1 AND category=? ORDER BY deploy_count DESC, name",
                    (category,)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM agent_templates WHERE is_active=1 ORDER BY category, deploy_count DESC, name"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_template(self, template_id):
        with get_db() as db:
            r = db.execute("SELECT * FROM agent_templates WHERE id=?", (template_id,)).fetchone()
            return dict(r) if r else None

    def deploy_template(self, template_id, user_id, department_id=None):
        """Create an agent from a template."""
        tmpl = self.get_template(template_id)
        if not tmpl:
            return None
        agent_id = f"agt_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO agents (id, owner_id, name, role, icon, color, description, instructions,
                                    provider, model, temperature, max_tokens, company_wide, shared)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
            """, (agent_id, user_id, tmpl["name"], tmpl["role"], tmpl["icon"], tmpl["color"],
                  tmpl["description"], tmpl["instructions"], tmpl.get("provider", ""),
                  tmpl.get("model", ""), tmpl.get("temperature", 0.7), tmpl.get("max_tokens", 4096)))
            # Increment deploy count
            db.execute("UPDATE agent_templates SET deploy_count=deploy_count+1 WHERE id=?", (template_id,))
            # If department specified, assign agent access
            if department_id:
                db.execute("INSERT OR IGNORE INTO department_agent_access (department_id, agent_id) VALUES (?,?)",
                           (department_id, agent_id))
            db.commit()
        return {"agent_id": agent_id, "template_id": template_id, "name": tmpl["name"]}

    def create_template(self, data):
        """Create a custom template."""
        tid = f"tmpl_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO agent_templates (id, name, role, icon, color, description, instructions, category, provider, model, temperature, max_tokens, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tid, data.get("name", ""), data.get("role", ""), data.get("icon", "🤖"),
                  data.get("color", "#4f46e5"), data.get("description", ""), data.get("instructions", ""),
                  data.get("category", "general"), data.get("provider", ""), data.get("model", ""),
                  data.get("temperature", 0.7), data.get("max_tokens", 4096), data.get("tags", "[]")))
            db.commit()
        return {"id": tid}


class RecommendationEngine:
    """Analyze usage patterns and recommend agent additions, optimizations, and changes."""

    TOPIC_KEYWORDS = {
        "code": ["code", "python", "javascript", "function", "bug", "debug", "api", "database", "sql", "git",
                 "deploy", "server", "error", "stack", "compile", "syntax", "class", "variable", "algorithm"],
        "writing": ["write", "draft", "email", "blog", "article", "copy", "edit", "proofread", "tone",
                     "headline", "paragraph", "essay", "letter", "memo", "report", "summary"],
        "analysis": ["analyze", "data", "chart", "graph", "trend", "metrics", "kpi", "compare", "benchmark",
                      "forecast", "predict", "statistical", "correlation", "insight", "performance"],
        "legal": ["contract", "clause", "liability", "compliance", "regulation", "gdpr", "terms",
                  "legal", "law", "patent", "trademark", "indemnify", "nda", "agreement"],
        "finance": ["budget", "revenue", "cost", "profit", "expense", "invoice", "roi", "margin",
                     "financial", "pricing", "forecast", "quarterly", "earnings", "p&l", "cash flow"],
        "hr": ["hiring", "interview", "onboarding", "employee", "performance review", "pto",
               "benefits", "compensation", "job description", "talent", "recruit", "offer letter"],
        "marketing": ["campaign", "seo", "social media", "brand", "audience", "conversion", "funnel",
                       "ad copy", "engagement", "content calendar", "hashtag", "influencer", "ctr"],
        "sales": ["prospect", "lead", "pipeline", "deal", "quota", "objection", "proposal",
                  "rfp", "close", "demo", "competitor", "pricing", "discount", "commission"],
        "strategy": ["strategy", "roadmap", "competitive", "market", "growth", "acquisition",
                      "partnership", "vision", "mission", "stakeholder", "board", "initiative"],
        "support": ["troubleshoot", "ticket", "issue", "fix", "broken", "help", "how to",
                     "install", "configure", "setup", "reset", "password", "access", "permission"],
    }

    def analyze_and_recommend(self):
        """Scan usage patterns and generate all recommendation types."""
        recommendations = []
        with get_db() as db:
            thirty_days = (datetime.utcnow() - timedelta(days=30)).isoformat()
            ninety_days = (datetime.utcnow() - timedelta(days=90)).isoformat()

            msg_count = db.execute(
                "SELECT COUNT(*) as c FROM messages WHERE created_at>=? AND role='user'",
                (thirty_days,)).fetchone()["c"]

            # ── Pattern 1: Departments without agents ──
            recs = self._pattern_dept_no_agents(db)
            recommendations.extend(recs)

            # ── Pattern 2: Heavy users without dedicated agents ──
            if msg_count >= 10:
                recs = self._pattern_heavy_users(db, thirty_days)
                recommendations.extend(recs)

            # ── Pattern 3: Underperforming agents ──
            recs = self._pattern_underperforming(db, thirty_days)
            recommendations.extend(recs)

            # ── Pattern 4: Cost optimization ──
            recs = self._pattern_cost_optimization(db, thirty_days)
            recommendations.extend(recs)

            # ── Pattern 5: Topic gap detection ──
            if msg_count >= 20:
                recs = self._pattern_topic_gaps(db, thirty_days)
                recommendations.extend(recs)

            # ── Pattern 6: Cross-department agent sharing ──
            recs = self._pattern_cross_department(db, thirty_days)
            recommendations.extend(recs)

            db.commit()
        return recommendations

    def _insert_rec(self, db, name, role, icon, description, reason, confidence,
                    category, department_id=None, source_data="{}",
                    suggested_action=None, instructions=None):
        """Insert a recommendation if no similar pending one exists."""
        # Deduplicate: skip if a pending rec with same name exists
        existing = db.execute(
            "SELECT id FROM agent_recommendations WHERE name=? AND status='pending'",
            (name,)).fetchone()
        if existing:
            return None
        rec_id = f"rec_{uuid.uuid4().hex[:12]}"
        db.execute("""
            INSERT INTO agent_recommendations
            (id, name, role, icon, description, reason, confidence, category,
             department_id, source_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rec_id, name, role, icon, description, reason,
              confidence, category, department_id, source_data))
        return {"id": rec_id, "name": name, "category": category,
                "reason": reason, "confidence": confidence,
                "suggested_action": suggested_action}

    # ────────────────────────────────────────────
    # Pattern 1: Departments without agents
    # ────────────────────────────────────────────
    def _pattern_dept_no_agents(self, db):
        results = []
        depts = db.execute("""
            SELECT d.id, d.name, d.icon, COUNT(dm.user_id) as member_count
            FROM departments d
            LEFT JOIN department_agent_access daa ON d.id=daa.department_id
            JOIN department_members dm ON d.id=dm.department_id
            WHERE daa.agent_id IS NULL AND d.is_active=1
            GROUP BY d.id HAVING member_count > 0
        """).fetchall()
        for dept in depts:
            r = self._insert_rec(db,
                f"{dept['name']} Assistant",
                f"General assistant for {dept['name']} team",
                dept['icon'] or '🤖',
                f"A tailored AI assistant for the {dept['name']} department with {dept['member_count']} members.",
                f"{dept['name']} has {dept['member_count']} members but no assigned agents.",
                0.85, "new_agent", dept['id'],
                f'{{"pattern":"dept_no_agents","member_count":{dept["member_count"]}}}',
                "Create a new agent for this department")
            if r: results.append(r)
        return results

    # ────────────────────────────────────────────
    # Pattern 2: Heavy users without custom agents
    # ────────────────────────────────────────────
    def _pattern_heavy_users(self, db, since):
        results = []
        heavy = db.execute("""
            SELECT u.id, u.display_name, COUNT(*) as msg_count
            FROM messages m
            JOIN conversations c ON m.conversation_id=c.id
            JOIN users u ON c.user_id=u.id
            WHERE m.created_at>=? AND m.role='user'
            GROUP BY u.id HAVING msg_count > 50
        """, (since,)).fetchall()
        for user in heavy:
            own = db.execute(
                "SELECT COUNT(*) as c FROM agents WHERE owner_id=?",
                (user["id"],)).fetchone()["c"]
            if own < 2:
                r = self._insert_rec(db,
                    f"{user['display_name']}'s Personal Assistant",
                    f"Personal assistant for {user['display_name']}",
                    "🧑‍💼",
                    f"A custom agent tailored to {user['display_name']}'s frequent usage patterns ({user['msg_count']} messages/month).",
                    f"{user['display_name']} sent {user['msg_count']} messages in 30 days but has only {own} custom agents.",
                    0.65, "productivity",
                    source_data=f'{{"pattern":"heavy_user","msg_count":{user["msg_count"]},"own_agents":{own}}}',
                    suggested_action="Create a personal agent tuned to this user's common tasks")
                if r: results.append(r)
        return results

    # ────────────────────────────────────────────
    # Pattern 3: Underperforming agents
    # ────────────────────────────────────────────
    def _pattern_underperforming(self, db, since):
        results = []
        # Agents with enough feedback and high negative ratio (rating is -1 or 1)
        agents = db.execute("""
            SELECT a.id, a.name, a.model, a.instructions, a.run_count,
                   COUNT(CASE WHEN mf.rating = -1 THEN 1 END) as neg_feedback,
                   COUNT(CASE WHEN mf.rating = 1 THEN 1 END) as pos_feedback,
                   COUNT(mf.id) as total_feedback
            FROM agents a
            LEFT JOIN message_feedback mf ON mf.agent_id=a.id AND mf.created_at>=?
            WHERE a.run_count >= 10
            GROUP BY a.id
            HAVING total_feedback >= 5 AND neg_feedback > pos_feedback
        """, (since,)).fetchall()

        for agent in agents:
            neg_pct = round((agent["neg_feedback"] / max(agent["total_feedback"], 1)) * 100)
            prompt_len = len(agent["instructions"] or "")
            approval_rate = round((agent["pos_feedback"] / max(agent["total_feedback"], 1)) * 100)

            suggestion = "Consider rewriting the system prompt with clearer instructions"
            if prompt_len < 100:
                suggestion = "The system prompt is very short ({} chars). Add detailed instructions, role definition, and output format guidelines".format(prompt_len)
            elif neg_pct > 70:
                suggestion = "Very high dissatisfaction. Consider replacing this agent entirely or switching to a more capable model"

            r = self._insert_rec(db,
                f"Improve: {agent['name']}",
                f"Prompt tuning recommendation for {agent['name']}",
                "🔧",
                f"Agent '{agent['name']}' has {neg_pct}% negative feedback ({agent['neg_feedback']} 👎 vs {agent['pos_feedback']} 👍 across {agent['total_feedback']} ratings). {suggestion}.",
                f"Low satisfaction: {approval_rate}% approval rate. {agent['neg_feedback']}/{agent['total_feedback']} thumbs down. Used {agent['run_count']} times total.",
                0.80, "optimization",
                source_data=json.dumps({"pattern": "underperforming", "agent_id": agent["id"],
                    "neg_pct": neg_pct, "approval_rate": approval_rate,
                    "run_count": agent["run_count"], "prompt_length": prompt_len}),
                suggested_action=suggestion)
            if r: results.append(r)
        return results

    # ────────────────────────────────────────────
    # Pattern 4: Cost optimization
    # ────────────────────────────────────────────
    def _pattern_cost_optimization(self, db, since):
        results = []
        # Find agents using expensive models for simple conversations
        expensive_models = ["claude-opus-4-5-20250929", "gpt-4-turbo", "gpt-4", "o1-preview"]
        cheap_alternatives = {
            "claude-opus-4-5-20250929": "claude-sonnet-4-5-20250929",
            "gpt-4-turbo": "gpt-4o-mini",
            "gpt-4": "gpt-4o-mini",
            "o1-preview": "o1-mini",
        }

        agents_on_expensive = db.execute("""
            SELECT a.id, a.name, a.model, a.run_count,
                   SUM(u.cost_estimate) as total_cost,
                   AVG(u.tokens_in + u.tokens_out) as avg_tokens,
                   COUNT(u.id) as usage_count
            FROM agents a
            JOIN usage_log u ON u.agent_id=a.id AND u.created_at>=?
            WHERE a.model IN ({})
            GROUP BY a.id
            HAVING usage_count >= 20
        """.format(",".join("?" * len(expensive_models))),
            (since, *expensive_models)).fetchall()

        for agent in agents_on_expensive:
            avg_tokens = int(agent["avg_tokens"] or 0)
            # If average tokens per conversation is low, cheaper model would work
            if avg_tokens < 2000:
                complexity = "simple"
                confidence = 0.85
            elif avg_tokens < 4000:
                complexity = "moderate"
                confidence = 0.70
            else:
                continue  # Complex usage, keep the expensive model

            alt_model = cheap_alternatives.get(agent["model"], "claude-sonnet-4-5-20250929")
            estimated_savings = round((agent["total_cost"] or 0) * 0.6, 2)  # ~60% savings estimate

            r = self._insert_rec(db,
                f"Cost savings: {agent['name']}",
                f"Switch {agent['name']} from {agent['model']} to {alt_model}",
                "💸",
                f"Agent '{agent['name']}' uses {agent['model']} but has {complexity} average complexity ({avg_tokens} avg tokens/request). Switching to {alt_model} could save ~${estimated_savings:.2f}/month with minimal quality impact.",
                f"${agent['total_cost']:.2f} spent in 30 days on {agent['usage_count']} requests averaging {avg_tokens} tokens. {complexity.title()} complexity doesn't require a premium model.",
                confidence, "cost_optimization",
                source_data=json.dumps({"pattern": "cost_optimization", "agent_id": agent["id"],
                    "current_model": agent["model"], "suggested_model": alt_model,
                    "avg_tokens": avg_tokens, "total_cost": float(agent["total_cost"] or 0),
                    "estimated_savings": estimated_savings}),
                suggested_action=f"Switch model from {agent['model']} to {alt_model}")
            if r: results.append(r)
        return results

    # ────────────────────────────────────────────
    # Pattern 5: Topic gap detection
    # ────────────────────────────────────────────
    def _pattern_topic_gaps(self, db, since):
        results = []
        # Analyze recent user messages to detect topic clusters
        messages = db.execute("""
            SELECT m.content, c.agent_id
            FROM messages m
            JOIN conversations c ON m.conversation_id=c.id
            WHERE m.role='user' AND m.created_at>=?
            ORDER BY m.created_at DESC LIMIT 500
        """, (since,)).fetchall()

        if len(messages) < 20:
            return results

        # Count topic hits
        topic_counts = {}
        topic_without_agent = {}  # topics where messages go to generic/default agents

        # Get specialized agent topics (from their instructions)
        agent_topics = {}
        agents_data = db.execute("SELECT id, name, instructions FROM agents").fetchall()
        for a in agents_data:
            instr = (a["instructions"] or "").lower()
            for topic, keywords in self.TOPIC_KEYWORDS.items():
                matches = sum(1 for kw in keywords if kw in instr)
                if matches >= 3:
                    agent_topics.setdefault(topic, []).append(a["id"])

        for msg in messages:
            content = (msg["content"] or "").lower()
            for topic, keywords in self.TOPIC_KEYWORDS.items():
                hits = sum(1 for kw in keywords if kw in content)
                if hits >= 2:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
                    if topic not in agent_topics:
                        topic_without_agent[topic] = topic_without_agent.get(topic, 0) + 1

        # Recommend agents for topics with significant volume but no specialized agent
        topic_labels = {
            "code": ("Code Assistant", "🖥️", "Help with programming, debugging, and code review"),
            "writing": ("Writing Editor", "✍️", "Professional writing, editing, and content polishing"),
            "analysis": ("Data Analyst", "📊", "Data analysis, visualization suggestions, and insights"),
            "legal": ("Legal Assistant", "⚖️", "Contract review, compliance questions, and legal research"),
            "finance": ("Finance Advisor", "💹", "Financial analysis, budgeting, and forecasting"),
            "hr": ("HR Assistant", "👥", "Recruiting, onboarding, and employee relations"),
            "marketing": ("Marketing Strategist", "📣", "Campaign planning, content strategy, and SEO"),
            "sales": ("Sales Enablement", "💰", "Prospecting, proposals, and competitive intelligence"),
            "strategy": ("Strategy Advisor", "🎯", "Strategic planning, market analysis, and roadmapping"),
            "support": ("Tech Support", "🛠️", "Troubleshooting, how-to guides, and system support"),
        }

        for topic, count in sorted(topic_without_agent.items(), key=lambda x: -x[1]):
            if count < 5:
                continue
            total_topic = topic_counts.get(topic, count)
            pct = round(count / len(messages) * 100, 1)
            label = topic_labels.get(topic, (f"{topic.title()} Specialist", "🤖", f"Specialized {topic} assistant"))

            r = self._insert_rec(db,
                label[0],
                f"Specialist for {topic} questions",
                label[1],
                f"{label[2]}. Your team asked {count} {topic}-related questions in the last 30 days ({pct}% of all messages) but no agent specializes in {topic}.",
                f"Detected {count} messages about {topic} (out of {total_topic} topic matches) with no specialized agent. Creating a dedicated agent could improve response quality significantly.",
                min(0.90, 0.60 + (count / 100)),  # Higher confidence with more messages
                "topic_gap",
                source_data=json.dumps({"pattern": "topic_gap", "topic": topic,
                    "message_count": count, "total_messages": len(messages), "pct": pct}),
                suggested_action=f"Create a specialized {topic} agent with domain-specific instructions")
            if r: results.append(r)
        return results

    # ────────────────────────────────────────────
    # Pattern 6: Cross-department agent sharing
    # ────────────────────────────────────────────
    def _pattern_cross_department(self, db, since):
        results = []
        # Find agents that are popular in one department — could benefit another
        agent_dept_usage = db.execute("""
            SELECT a.id as agent_id, a.name as agent_name,
                   a.avg_rating, a.run_count,
                   d_owner.id as owner_dept_id, d_owner.name as owner_dept,
                   d_user.id as user_dept_id, d_user.name as user_dept,
                   COUNT(*) as cross_usage
            FROM messages m
            JOIN conversations c ON m.conversation_id=c.id
            JOIN agents a ON c.agent_id=a.id
            JOIN department_members dm ON c.user_id=dm.user_id
            JOIN departments d_user ON dm.department_id=d_user.id
            LEFT JOIN department_agent_access daa ON a.id=daa.agent_id
            LEFT JOIN departments d_owner ON daa.department_id=d_owner.id
            WHERE m.created_at>=? AND m.role='user'
                AND a.avg_rating >= 3.5
                AND d_user.id != COALESCE(d_owner.id, '')
            GROUP BY a.id, d_user.id
            HAVING cross_usage >= 5
            ORDER BY cross_usage DESC
        """, (since,)).fetchall()

        for row in agent_dept_usage:
            # Check if agent is already accessible to the other department
            already = db.execute(
                "SELECT id FROM department_agent_access WHERE department_id=? AND agent_id=?",
                (row["user_dept_id"], row["agent_id"])).fetchone()
            if already:
                continue

            r = self._insert_rec(db,
                f"Share '{row['agent_name']}' with {row['user_dept']}",
                f"Cross-department agent recommendation",
                "🔄",
                f"Agent '{row['agent_name']}' ({row['avg_rating']:.1f}★, {row['run_count']} runs) is assigned to {row['owner_dept'] or 'no department'} but {row['user_dept']} members have used it {row['cross_usage']} times in 30 days. Consider formally granting access.",
                f"Popular cross-department usage detected: {row['cross_usage']} uses by {row['user_dept']} team. Agent has {row['avg_rating']:.1f}/5 rating across {row['run_count']} total runs.",
                min(0.85, 0.55 + (row["cross_usage"] / 50)),
                "cross_department", row["user_dept_id"],
                source_data=json.dumps({"pattern": "cross_department",
                    "agent_id": row["agent_id"], "agent_name": row["agent_name"],
                    "from_dept": row["owner_dept"], "to_dept": row["user_dept"],
                    "cross_usage": row["cross_usage"], "rating": row["avg_rating"]}),
                suggested_action=f"Grant {row['user_dept']} access to '{row['agent_name']}'")
            if r: results.append(r)
        return results

    def list_recommendations(self, status=None):
        """List all recommendations, optionally filtered by status."""
        with get_db() as db:
            if status:
                rows = db.execute("""
                    SELECT ar.*, d.name as department_name
                    FROM agent_recommendations ar
                    LEFT JOIN departments d ON ar.department_id=d.id
                    WHERE ar.status=? ORDER BY ar.confidence DESC, ar.created_at DESC
                """, (status,)).fetchall()
            else:
                rows = db.execute("""
                    SELECT ar.*, d.name as department_name
                    FROM agent_recommendations ar
                    LEFT JOIN departments d ON ar.department_id=d.id
                    ORDER BY ar.created_at DESC
                """).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try:
                    d["source_data"] = json.loads(d.get("source_data") or "{}")
                except Exception:
                    pass
                results.append(d)
            return results

    def get_recommendation_summary(self):
        """Get a summary of recommendations by category and status."""
        with get_db() as db:
            rows = db.execute("""
                SELECT category, status, COUNT(*) as count,
                       AVG(confidence) as avg_confidence
                FROM agent_recommendations
                GROUP BY category, status
            """).fetchall()
        summary = {}
        for r in rows:
            cat = r["category"]
            if cat not in summary:
                summary[cat] = {"total": 0, "by_status": {}}
            summary[cat]["total"] += r["count"]
            summary[cat]["by_status"][r["status"]] = {
                "count": r["count"],
                "avg_confidence": round(r["avg_confidence"], 2),
            }
        return summary

    def review_recommendation(self, rec_id, action, reviewer_id):
        """Approve or reject a recommendation. If approved, deploy the agent."""
        with get_db() as db:
            rec = db.execute("SELECT * FROM agent_recommendations WHERE id=?", (rec_id,)).fetchone()
            if not rec:
                return None

            source = {}
            try:
                source = json.loads(rec["source_data"] or "{}")
            except Exception:
                pass

            new_status = "approved" if action == "approve" else "rejected"
            db.execute("""
                UPDATE agent_recommendations SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (new_status, reviewer_id, rec_id))

            agent_id = None
            result_action = None

            if action == "approve":
                pattern = source.get("pattern", "")

                if pattern == "cost_optimization":
                    # Switch the agent's model
                    target_agent = source.get("agent_id")
                    new_model = source.get("suggested_model")
                    if target_agent and new_model:
                        db.execute("UPDATE agents SET model=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                   (new_model, target_agent))
                        result_action = f"Switched agent to {new_model}"
                    db.execute("UPDATE agent_recommendations SET status='deployed' WHERE id=?", (rec_id,))

                elif pattern == "cross_department":
                    # Grant department access to the agent
                    target_agent = source.get("agent_id")
                    target_dept = rec["department_id"]
                    if target_agent and target_dept:
                        db.execute(
                            "INSERT OR IGNORE INTO department_agent_access (department_id, agent_id) VALUES (?,?)",
                            (target_dept, target_agent))
                        result_action = f"Granted department access to agent"
                    db.execute("UPDATE agent_recommendations SET status='deployed' WHERE id=?", (rec_id,))

                elif pattern == "underperforming":
                    # Flag for prompt tuning (admin still needs to manually edit)
                    result_action = "Agent flagged for prompt improvement"
                    db.execute("UPDATE agent_recommendations SET status='in_progress' WHERE id=?", (rec_id,))

                else:
                    # Default: create a new agent
                    agent_id = f"agt_{uuid.uuid4().hex[:12]}"
                    db.execute("""
                        INSERT INTO agents (id, owner_id, name, role, icon, description,
                                            instructions, company_wide, shared)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (agent_id, reviewer_id, rec["name"], rec["role"],
                          rec["icon"], rec["description"], rec["instructions"] or ""))
                    if rec["department_id"]:
                        db.execute(
                            "INSERT OR IGNORE INTO department_agent_access (department_id, agent_id) VALUES (?,?)",
                            (rec["department_id"], agent_id))
                    result_action = "Agent created and deployed"
                    db.execute("UPDATE agent_recommendations SET status='deployed' WHERE id=?", (rec_id,))

            db.commit()
            return {"id": rec_id, "status": new_status, "agent_id": agent_id,
                    "action_taken": result_action}
