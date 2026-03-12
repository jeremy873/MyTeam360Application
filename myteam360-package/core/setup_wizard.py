"""
Setup Wizard — First-time guided setup for MyTeam360.
Walks admins through: org profile, AI providers, departments, agents, policies.
Seeds default business departments and role-specific AI agents.
"""

import uuid
import json
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.setup_wizard")


# ══════════════════════════════════════════════════════════════
# WIZARD STEPS
# ══════════════════════════════════════════════════════════════

WIZARD_STEPS = [
    {
        "step": 0,
        "id": "welcome",
        "title": "Welcome to My Team 360",
        "description": "Let's get your AI workspace set up in a few minutes.",
        "required": False,
    },
    {
        "step": 1,
        "id": "organization",
        "title": "Your Organization",
        "description": "Tell us about your company so we can tailor the experience.",
        "fields": ["org_name", "org_industry", "org_size"],
        "required": True,
    },
    {
        "step": 2,
        "id": "ai_providers",
        "title": "Connect AI Providers",
        "description": "Add at least one AI provider. We'll walk you through each one.",
        "required": True,
    },
    {
        "step": 3,
        "id": "departments",
        "title": "Set Up Departments",
        "description": "We've pre-built departments for common business functions. Select the ones your organization needs.",
        "required": True,
    },
    {
        "step": 4,
        "id": "policies",
        "title": "Acceptable Use Policy",
        "description": "Review and customize the AI usage policy your team will agree to.",
        "required": True,
    },
    {
        "step": 5,
        "id": "review",
        "title": "Review & Launch",
        "description": "Everything's set. Review your configuration and go live.",
        "required": False,
    },
]


# ══════════════════════════════════════════════════════════════
# DEFAULT DEPARTMENTS & AGENTS
# ══════════════════════════════════════════════════════════════

DEFAULT_DEPARTMENTS = [
    {
        "id": "dept_csuite",
        "name": "C-Suite / Executive",
        "description": "Strategic planning, board prep, executive communications",
        "icon": "👔",
        "agents": [
            {
                "name": "Executive Strategist",
                "description": "Strategic analysis, market intelligence, board presentation prep",
                "system_prompt": "You are an executive strategy advisor for a corporate leadership team. Provide concise, data-driven strategic analysis. Focus on market trends, competitive positioning, risk assessment, and actionable recommendations. Use executive-level language. Structure responses with clear headers and bullet points. Always consider financial impact, stakeholder implications, and timeline feasibility.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.5,
                "voice": {"provider": "openai", "id": "onyx", "speed": 0.95},
            },
            {
                "name": "Board Prep Assistant",
                "description": "Board meeting prep, talking points, shareholder communications",
                "system_prompt": "You help executives prepare for board meetings and shareholder communications. Create compelling talking points, anticipate tough questions, draft executive summaries, and prepare presentation narratives. Maintain a professional, authoritative tone. Focus on KPIs, strategic milestones, and forward-looking statements.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.4,
                "voice": {"provider": "openai", "id": "echo", "speed": 0.9},
            },
        ],
    },
    {
        "id": "dept_sales",
        "name": "Sales",
        "description": "Lead generation, proposals, competitive analysis, objection handling",
        "icon": "💰",
        "agents": [
            {
                "name": "Sales Assistant",
                "description": "Prospect research, email drafts, call prep, follow-ups",
                "system_prompt": "You are a sales enablement assistant. Help with prospect research, personalized outreach emails, call preparation, and follow-up strategies. Always be persuasive but professional. Focus on value propositions and pain points. Suggest specific talking points based on the prospect's industry and role. Include clear CTAs in all communications.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.7,
                "voice": {"provider": "openai", "id": "alloy", "speed": 1.05},
            },
            {
                "name": "Proposal Writer",
                "description": "RFP responses, proposals, SOWs, pricing justifications",
                "system_prompt": "You are an expert proposal writer. Create compelling RFP responses, proposals, and statements of work. Structure content with clear sections: executive summary, understanding of needs, proposed solution, timeline, team qualifications, pricing rationale, and next steps. Use confident, professional language. Emphasize differentiators and ROI.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.5,
                "voice": {"provider": "openai", "id": "fable", "speed": 0.95},
            },
            {
                "name": "Competitive Intel",
                "description": "Competitor analysis, battle cards, market positioning",
                "system_prompt": "You are a competitive intelligence analyst. Provide detailed competitor analysis, create battle cards, identify strengths/weaknesses, and suggest positioning strategies. Be objective and factual. Structure analyses with: company overview, product comparison, pricing intelligence, market share insights, and recommended counter-positioning.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.4,
                "voice": {"provider": "openai", "id": "echo", "speed": 1.0},
            },
        ],
    },
    {
        "id": "dept_marketing",
        "name": "Marketing",
        "description": "Content creation, campaigns, brand voice, social media, analytics",
        "icon": "📣",
        "agents": [
            {
                "name": "Content Creator",
                "description": "Blog posts, case studies, white papers, website copy",
                "system_prompt": "You are a professional content marketing writer. Create engaging, SEO-aware content including blog posts, case studies, white papers, and website copy. Match the brand voice provided. Use compelling headlines, clear structure, and strong CTAs. Optimize for readability and search. Always ask about target audience and key messages if not provided.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.8,
                "voice": {"provider": "openai", "id": "shimmer", "speed": 1.0},
            },
            {
                "name": "Social Media Manager",
                "description": "Social posts, campaign ideas, hashtag strategies, engagement",
                "system_prompt": "You are a social media strategist. Create platform-specific content for LinkedIn, X/Twitter, Instagram, and Facebook. Tailor tone and format to each platform. Suggest hashtag strategies, posting schedules, and engagement tactics. Create campaign concepts with multi-post sequences. Keep posts authentic and engaging — avoid corporate jargon.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.8,
                "voice": {"provider": "openai", "id": "nova", "speed": 1.1},
            },
            {
                "name": "Campaign Strategist",
                "description": "Campaign planning, A/B test ideas, audience targeting, metrics",
                "system_prompt": "You are a marketing campaign strategist. Help plan multi-channel campaigns with clear objectives, target audiences, messaging frameworks, channel strategies, timelines, and KPIs. Suggest A/B test variations, audience segmentation approaches, and budget allocation. Always tie recommendations back to measurable business outcomes.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.6,
                "voice": {"provider": "openai", "id": "alloy", "speed": 1.0},
            },
        ],
    },
    {
        "id": "dept_finance",
        "name": "Finance",
        "description": "Financial analysis, forecasting, reporting, budget planning",
        "icon": "📊",
        "agents": [
            {
                "name": "Financial Analyst",
                "description": "Financial modeling, variance analysis, KPI tracking, reports",
                "system_prompt": "You are a corporate financial analyst assistant. Help with financial modeling, variance analysis, KPI interpretation, and reporting. Be precise with numbers. Use standard financial terminology. Structure analyses with clear assumptions, methodology, findings, and recommendations. Always note limitations and suggest areas for deeper analysis. Never provide investment advice.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.3,
                "voice": {"provider": "openai", "id": "onyx", "speed": 0.9},
            },
            {
                "name": "Budget Planner",
                "description": "Budget forecasting, cost allocation, scenario planning",
                "system_prompt": "You are a budget planning assistant. Help create departmental budgets, forecast expenses, model scenarios (best/base/worst case), and identify cost optimization opportunities. Use clear tables and breakdowns. Compare against historical data when available. Flag risks and assumptions. Structure output for executive review.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.3,
                "voice": {"provider": "openai", "id": "echo", "speed": 0.95},
            },
        ],
    },
    {
        "id": "dept_legal",
        "name": "Legal",
        "description": "Contract review, compliance, policy drafting, risk assessment",
        "icon": "⚖️",
        "agents": [
            {
                "name": "Contract Reviewer",
                "description": "Contract analysis, clause identification, risk flagging",
                "system_prompt": "You are a legal contract analysis assistant. Review contracts to identify key terms, obligations, risks, and unusual clauses. Flag potential issues in: liability, indemnification, termination, IP rights, non-compete, confidentiality, and payment terms. Provide clear risk ratings (high/medium/low). Always note that this is AI analysis and should be reviewed by qualified legal counsel before action.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.2,
                "voice": {"provider": "openai", "id": "fable", "speed": 0.85},
            },
            {
                "name": "Compliance Advisor",
                "description": "Regulatory guidance, policy drafting, compliance checklists",
                "system_prompt": "You are a compliance and regulatory assistant. Help draft internal policies, create compliance checklists, summarize regulatory requirements, and identify potential compliance gaps. Cover areas like data privacy (GDPR, CCPA), employment law, industry regulations, and internal governance. Always include a disclaimer that outputs should be verified by qualified legal professionals.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.3,
                "voice": {"provider": "openai", "id": "onyx", "speed": 0.9},
            },
        ],
    },
    {
        "id": "dept_hr",
        "name": "Human Resources",
        "description": "Recruiting, onboarding, policy, employee communications",
        "icon": "👥",
        "agents": [
            {
                "name": "HR Assistant",
                "description": "Job descriptions, interview questions, employee comms, policies",
                "system_prompt": "You are an HR professional assistant. Help write job descriptions, create interview question sets, draft employee communications, and develop HR policies. Use inclusive language. Ensure compliance with employment law best practices. For sensitive topics (termination, complaints, accommodations), always recommend involvement of qualified HR professionals.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.5,
                "voice": {"provider": "openai", "id": "nova", "speed": 1.0},
            },
            {
                "name": "Onboarding Coordinator",
                "description": "New hire checklists, welcome materials, training plans",
                "system_prompt": "You are an employee onboarding specialist. Create comprehensive onboarding plans, welcome packets, 30-60-90 day plans, training schedules, and orientation materials. Tailor content to the role and department. Include both administrative tasks and cultural integration activities. Make new hires feel welcomed and set up for success.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.6,
                "voice": {"provider": "openai", "id": "shimmer", "speed": 1.05},
            },
        ],
    },
    {
        "id": "dept_it",
        "name": "Information Technology",
        "description": "Technical support, documentation, architecture, security",
        "icon": "🖥️",
        "agents": [
            {
                "name": "IT Support",
                "description": "Troubleshooting, how-to guides, system documentation",
                "system_prompt": "You are an IT support specialist. Help troubleshoot technical issues, write how-to documentation, create system guides, and draft IT policies. Provide clear step-by-step instructions. Consider multiple OS platforms. Prioritize security best practices. For critical systems or data recovery, always recommend consulting the IT team directly.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.4,
                "voice": {"provider": "openai", "id": "alloy", "speed": 1.0},
            },
            {
                "name": "Tech Writer",
                "description": "Technical documentation, API docs, architecture diagrams",
                "system_prompt": "You are a technical writer. Create clear, accurate technical documentation including API references, architecture guides, runbooks, and user manuals. Use consistent formatting, code examples, and diagrams where helpful. Structure docs with table of contents, prerequisites, step-by-step procedures, and troubleshooting sections.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.4,
                "voice": {"provider": "openai", "id": "echo", "speed": 0.95},
            },
        ],
    },
    {
        "id": "dept_ops",
        "name": "Operations",
        "description": "Process optimization, project management, vendor management",
        "icon": "⚙️",
        "agents": [
            {
                "name": "Operations Analyst",
                "description": "Process mapping, efficiency analysis, SOP creation",
                "system_prompt": "You are an operations analyst. Help map business processes, identify inefficiencies, create SOPs (Standard Operating Procedures), and design workflows. Use structured frameworks like SIPOC, process flow diagrams, and RACI matrices. Focus on measurable improvements and practical implementation steps.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.4,
                "voice": {"provider": "openai", "id": "fable", "speed": 1.0},
            },
            {
                "name": "Project Manager",
                "description": "Project plans, status reports, risk registers, stakeholder comms",
                "system_prompt": "You are a project management assistant. Help create project plans, WBS (Work Breakdown Structures), status reports, risk registers, and stakeholder communications. Use standard PM methodology. Include milestones, dependencies, resource allocation, and timeline estimates. Flag risks proactively and suggest mitigation strategies.",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.4,
                "voice": {"provider": "openai", "id": "nova", "speed": 1.0},
            },
        ],
    },
]


# ══════════════════════════════════════════════════════════════
# PROVIDER SETUP GUIDES
# ══════════════════════════════════════════════════════════════

PROVIDER_SETUP_GUIDES = {
    "anthropic": {
        "steps": [
            {"title": "Create an Anthropic Account", "detail": "Go to console.anthropic.com and sign up or log in."},
            {"title": "Navigate to API Keys", "detail": "Click your profile icon → API Keys, or go to console.anthropic.com/settings/keys"},
            {"title": "Create a New Key", "detail": "Click 'Create Key', give it a name like 'MyTeam360', and copy the key immediately — you won't see it again."},
            {"title": "Paste Your Key Below", "detail": "Your key starts with 'sk-ant-'. Paste it in the field and click Test Connection."},
        ],
        "pricing_note": "Claude models are pay-per-token. Haiku is cheapest (~$0.25/M input tokens), Sonnet is mid-range (~$3/M), Opus is premium (~$15/M). Most business use works great with Sonnet.",
        "recommended_for": "Best overall quality. Recommended as your primary provider.",
    },
    "openai": {
        "steps": [
            {"title": "Create an OpenAI Account", "detail": "Go to platform.openai.com and sign up or log in."},
            {"title": "Navigate to API Keys", "detail": "Go to platform.openai.com/api-keys"},
            {"title": "Create a New Key", "detail": "Click 'Create new secret key', name it 'MyTeam360', and copy immediately."},
            {"title": "Paste Your Key Below", "detail": "Your key starts with 'sk-'. Paste it in the field and click Test Connection."},
        ],
        "pricing_note": "GPT-4o is their best model (~$2.50/M input). GPT-4o-mini is budget-friendly (~$0.15/M). Good for variety.",
        "recommended_for": "Good alternative provider for cost optimization and model diversity.",
    },
    "xai": {
        "steps": [
            {"title": "Create an xAI Account", "detail": "Go to console.x.ai and sign up."},
            {"title": "Generate API Key", "detail": "Navigate to API Keys section in your xAI dashboard."},
            {"title": "Create a Key", "detail": "Click create, name it 'MyTeam360', and copy the key."},
            {"title": "Paste Your Key Below", "detail": "Your key starts with 'xai-'. Paste it and click Test Connection."},
        ],
        "pricing_note": "Grok models are competitively priced. Good for creative and analytical tasks.",
        "recommended_for": "Additional provider for creative tasks and diverse perspectives.",
    },
    "google": {
        "steps": [
            {"title": "Go to Google AI Studio", "detail": "Visit aistudio.google.com/apikey and sign in with Google."},
            {"title": "Create an API Key", "detail": "Click 'Create API key' and select or create a Google Cloud project."},
            {"title": "Copy the Key", "detail": "Copy the generated key immediately."},
            {"title": "Paste Your Key Below", "detail": "Paste the key and click Test Connection."},
        ],
        "pricing_note": "Gemini Flash is very cost-effective. Flash Lite even cheaper for simple tasks.",
        "recommended_for": "Budget-friendly option with strong multilingual support.",
    },
    "ollama": {
        "steps": [
            {"title": "Install Ollama", "detail": "Go to ollama.ai and download for your OS. Run the installer."},
            {"title": "Pull a Model", "detail": "Open terminal and run: ollama pull llama3.1 (or any model you prefer)"},
            {"title": "Verify It's Running", "detail": "Ollama runs on localhost:11434 by default. Test with: curl http://localhost:11434/api/tags"},
            {"title": "Enter the URL Below", "detail": "Default is http://localhost:11434. Change only if running on a different host/port."},
        ],
        "pricing_note": "Completely free — runs on your hardware. Requires a machine with 8GB+ RAM (16GB+ recommended for larger models).",
        "recommended_for": "Full data privacy. No data leaves your network. Great for sensitive industries.",
    },
}


# ══════════════════════════════════════════════════════════════
# SETUP WIZARD MANAGER
# ══════════════════════════════════════════════════════════════

class SetupWizard:
    """Manages the first-time setup experience."""

    def get_state(self):
        """Get current wizard state."""
        with get_db() as db:
            row = db.execute("SELECT * FROM setup_wizard_state WHERE id='wizard'").fetchone()
            if not row:
                db.execute(
                    "INSERT INTO setup_wizard_state (id) VALUES ('wizard')")
                row = db.execute("SELECT * FROM setup_wizard_state WHERE id='wizard'").fetchone()
        state = dict(row)
        state["completed_steps"] = json.loads(state.get("completed_steps") or "[]")
        state["selected_providers"] = json.loads(state.get("selected_providers") or "[]")
        state["selected_departments"] = json.loads(state.get("selected_departments") or "[]")
        state["steps"] = WIZARD_STEPS
        state["total_steps"] = len(WIZARD_STEPS)
        return state

    def is_complete(self):
        state = self.get_state()
        return bool(state.get("is_complete"))

    def update_step(self, step_id, data):
        """Update wizard data for a specific step."""
        state = self.get_state()
        completed = state.get("completed_steps", [])

        with get_db() as db:
            updates = ["updated_at=CURRENT_TIMESTAMP"]
            vals = []

            if step_id == "organization":
                for field in ["org_name", "org_industry", "org_size"]:
                    if field in data:
                        updates.append(f"{field}=?")
                        vals.append(data[field])

            elif step_id == "ai_providers":
                if "selected_providers" in data:
                    updates.append("selected_providers=?")
                    vals.append(json.dumps(data["selected_providers"]))

            elif step_id == "departments":
                if "selected_departments" in data:
                    updates.append("selected_departments=?")
                    vals.append(json.dumps(data["selected_departments"]))

            if step_id not in completed:
                completed.append(step_id)
            updates.append("completed_steps=?")
            vals.append(json.dumps(completed))

            # Find step number
            step_num = next((s["step"] for s in WIZARD_STEPS if s["id"] == step_id), 0)
            updates.append("current_step=?")
            vals.append(step_num + 1)

            db.execute(
                f"UPDATE setup_wizard_state SET {','.join(updates)} WHERE id='wizard'",
                vals)

        return {"step": step_id, "updated": True, "next_step": step_num + 1}

    def complete_wizard(self, admin_user_id=None):
        """Mark wizard as complete and seed selected departments/agents."""
        state = self.get_state()

        # Seed selected departments and their agents
        selected = state.get("selected_departments", [])
        if not selected:
            selected = [d["id"] for d in DEFAULT_DEPARTMENTS]

        created_depts = []
        created_agents = []

        for dept_template in DEFAULT_DEPARTMENTS:
            if dept_template["id"] in selected:
                dept_result = self._create_department(dept_template, admin_user_id)
                if dept_result:
                    created_depts.append(dept_result["name"])
                    for agent_tmpl in dept_template.get("agents", []):
                        agent_result = self._create_agent(agent_tmpl, dept_result["id"], owner_id=admin_user_id)
                        if agent_result:
                            created_agents.append(agent_result["name"])
                            # Grant agent access to the department
                            try:
                                with get_db() as db:
                                    db.execute(
                                        "INSERT OR IGNORE INTO department_agent_access"
                                        " (department_id, agent_id) VALUES (?,?)",
                                        (dept_result["id"], agent_result["id"]))
                            except Exception:
                                pass

        # Mark complete
        with get_db() as db:
            db.execute(
                "UPDATE setup_wizard_state SET is_complete=1, admin_configured=1,"
                " updated_at=CURRENT_TIMESTAMP WHERE id='wizard'")

        logger.info(f"Setup complete: {len(created_depts)} departments, {len(created_agents)} agents")
        return {
            "complete": True,
            "departments_created": created_depts,
            "agents_created": created_agents,
        }

    def _create_department(self, template, admin_id=None):
        """Create a department from template."""
        try:
            from .departments import DepartmentManager
            dm = DepartmentManager()
            dept_id = f"dept_{uuid.uuid4().hex[:8]}"
            with get_db() as db:
                existing = db.execute(
                    "SELECT id FROM departments WHERE name=?", (template["name"],)).fetchone()
                if existing:
                    return {"id": existing["id"], "name": template["name"]}
                db.execute(
                    "INSERT INTO departments (id, name, description, created_by)"
                    " VALUES (?,?,?,?)",
                    (dept_id, template["name"], template["description"], admin_id))
            return {"id": dept_id, "name": template["name"]}
        except Exception as e:
            logger.warning(f"Failed to create dept {template['name']}: {e}")
            return None

    def _create_agent(self, template, dept_id=None, owner_id=None):
        """Create an agent from template."""
        try:
            agent_id = f"agent_{uuid.uuid4().hex[:8]}"
            voice = template.get("voice", {})
            with get_db() as db:
                existing = db.execute(
                    "SELECT id FROM agents WHERE name=?", (template["name"],)).fetchone()
                if existing:
                    return {"id": existing["id"], "name": template["name"]}
                db.execute(
                    "INSERT INTO agents (id, owner_id, name, description, instructions, model,"
                    " temperature, company_wide, shared, voice_provider, voice_id, voice_model, voice_speed)"
                    " VALUES (?,?,?,?,?,?,?,1,1,?,?,?,?)",
                    (agent_id, owner_id or "system",
                     template["name"], template["description"],
                     template.get("system_prompt", ""),
                     template.get("model", "claude-sonnet-4-5-20250929"),
                     template.get("temperature", 0.7),
                     voice.get("provider", ""),
                     voice.get("id", ""),
                     voice.get("model", ""),
                     voice.get("speed", 1.0)))
            return {"id": agent_id, "name": template["name"]}
        except Exception as e:
            logger.warning(f"Failed to create agent {template['name']}: {e}")
            return None

    def get_department_templates(self):
        """Return available department templates for selection."""
        return [{
            "id": d["id"],
            "name": d["name"],
            "description": d["description"],
            "icon": d["icon"],
            "agent_count": len(d["agents"]),
            "agents": [{"name": a["name"], "description": a["description"]} for a in d["agents"]],
        } for d in DEFAULT_DEPARTMENTS]

    def get_provider_guide(self, provider):
        """Get step-by-step setup guide for a specific provider."""
        guide = PROVIDER_SETUP_GUIDES.get(provider)
        if not guide:
            return None
        return guide

    def get_all_provider_guides(self):
        """Get all provider setup guides."""
        return PROVIDER_SETUP_GUIDES

    def reset_wizard(self):
        """Reset wizard state (for testing or re-setup)."""
        with get_db() as db:
            db.execute("DELETE FROM setup_wizard_state")
            db.execute("INSERT INTO setup_wizard_state (id) VALUES ('wizard')")
        return {"reset": True}
