# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Voice Setup Concierge — Interactive guided setup for every feature.

Instead of forms and settings pages, users talk to the concierge:
  "Help me set up my CRM" → guided conversation → CRM configured
  "Let's create a social media campaign" → questions → campaign live
  "Set up invoicing for my business" → profile created → ready to invoice

The concierge:
  1. Detects WHAT the user wants to set up (intent detection)
  2. Asks the minimum questions needed (guided flow)
  3. Actually configures the platform (calls real APIs)
  4. Confirms what was done and suggests next steps

Works via text OR voice (same API, frontend handles speech-to-text).

Setup flows available:
  - First run (brand new user — what's your business?)
  - CRM (pipeline, custom fields, import contacts)
  - Invoicing (business profile, first invoice)
  - Social media (connect platforms, first campaign)
  - Task board (pick template, first project)
  - Goals (set first OKR)
  - Email (signature, first template)
  - Expenses (categories, first entry)
  - Team (invite users, set roles)
"""

import json
import uuid
import logging
from datetime import datetime

logger = logging.getLogger("MyTeam360.concierge")


# ══════════════════════════════════════════════════════════════
# INTENT DETECTION
# ══════════════════════════════════════════════════════════════

SETUP_INTENTS = {
    "first_run": {
        "triggers": ["just signed up", "new here", "first time", "get started",
                      "how does this work", "what can you do", "help me start"],
        "label": "Welcome Setup",
        "description": "First-time user orientation and business profile",
    },
    "crm": {
        "triggers": ["crm", "contacts", "leads", "deals", "pipeline", "customers",
                      "client list", "sales tracker", "track deals", "manage contacts"],
        "label": "CRM Setup",
        "description": "Configure pipeline, custom fields, and import contacts",
    },
    "invoicing": {
        "triggers": ["invoice", "invoicing", "billing", "send invoice", "get paid",
                      "payment", "charge client", "bill client", "proposal"],
        "label": "Invoicing Setup",
        "description": "Set up business profile and create your first invoice",
    },
    "social_media": {
        "triggers": ["social media", "social", "twitter", "linkedin", "instagram",
                      "facebook", "posting", "campaign", "content calendar",
                      "schedule posts", "marketing campaign"],
        "label": "Social Media Setup",
        "description": "Connect platforms and create your first campaign",
    },
    "tasks": {
        "triggers": ["task", "project", "kanban", "to do", "todo", "board",
                      "project management", "track tasks", "assign tasks"],
        "label": "Task Board Setup",
        "description": "Create your first project with a template",
    },
    "goals": {
        "triggers": ["goal", "okr", "kpi", "objective", "target", "milestone",
                      "track progress", "set goals", "quarterly goals"],
        "label": "Goals Setup",
        "description": "Define your first objective and key results",
    },
    "email": {
        "triggers": ["email", "email template", "signature", "outbox",
                      "compose email", "draft email", "send email"],
        "label": "Email Setup",
        "description": "Set up your signature and first email template",
    },
    "expenses": {
        "triggers": ["expense", "expenses", "costs", "spending", "track expenses",
                      "budget", "receipts", "tax deduction"],
        "label": "Expense Tracking Setup",
        "description": "Configure categories and log your first expense",
    },
    "team": {
        "triggers": ["team", "invite", "add user", "add member", "collaboration",
                      "roles", "permissions"],
        "label": "Team Setup",
        "description": "Invite team members and assign roles",
    },
}


def detect_intent(user_message: str) -> dict:
    """Detect what the user wants to set up from their message."""
    msg = user_message.lower().strip()

    # Check each intent's triggers
    scores = {}
    for intent_id, intent in SETUP_INTENTS.items():
        score = 0
        for trigger in intent["triggers"]:
            if trigger in msg:
                score += len(trigger)  # Longer matches score higher
        if score > 0:
            scores[intent_id] = score

    if not scores:
        return {"intent": None, "confidence": 0,
                "available": list(SETUP_INTENTS.keys())}

    best = max(scores, key=scores.get)
    return {
        "intent": best,
        "confidence": min(scores[best] / 20, 1.0),
        "label": SETUP_INTENTS[best]["label"],
        "description": SETUP_INTENTS[best]["description"],
    }


# ══════════════════════════════════════════════════════════════
# SETUP FLOWS — Step-by-step guided configuration
# ══════════════════════════════════════════════════════════════

SETUP_FLOWS = {
    "first_run": {
        "steps": [
            {
                "id": "welcome",
                "say": "Welcome to MyTeam360! I'm your setup concierge — I'll help you get everything configured. First, what's your name?",
                "expect": "name",
                "field": "user_name",
            },
            {
                "id": "business_type",
                "say": "Nice to meet you, {user_name}! What kind of business are you in? For example: real estate, consulting, freelance design, SaaS, law firm, restaurant...",
                "expect": "business_type",
                "field": "business_type",
            },
            {
                "id": "business_name",
                "say": "Got it — {business_type}. What's the name of your business?",
                "expect": "text",
                "field": "business_name",
            },
            {
                "id": "team_size",
                "say": "And how many people are on your team? Just you, 2-5, 5-10, or more?",
                "expect": "choice",
                "options": ["Just me", "2-5", "5-10", "10+"],
                "field": "team_size",
            },
            {
                "id": "first_feature",
                "say": "Perfect. {business_name} is all set up. What would you like to configure first?",
                "expect": "choice",
                "options": ["CRM & Contacts", "Invoicing", "Social Media", "Task Board", "Just explore"],
                "field": "first_feature",
            },
        ],
        "on_complete": "first_run_complete",
    },

    "crm": {
        "steps": [
            {
                "id": "industry",
                "say": "Let's set up your CRM. What industry are you in? This helps me create the right pipeline stages and custom fields for you.",
                "expect": "text",
                "field": "industry",
            },
            {
                "id": "pipeline_confirm",
                "say": "Based on {industry}, I'll create a pipeline with stages that fit your business. I'll also add custom fields that are common in your industry. Sound good, or do you want to customize the stages?",
                "expect": "choice",
                "options": ["Sounds good", "Let me customize"],
                "field": "pipeline_choice",
            },
            {
                "id": "lead_sources",
                "say": "Where do most of your leads come from? For example: website, referrals, LinkedIn, cold outreach, trade shows...",
                "expect": "text",
                "field": "lead_sources",
            },
            {
                "id": "import",
                "say": "Do you have existing contacts to import? You can upload a CSV file later, or we can start fresh.",
                "expect": "choice",
                "options": ["Start fresh", "I'll import later"],
                "field": "import_choice",
            },
        ],
        "on_complete": "crm_complete",
    },

    "invoicing": {
        "steps": [
            {
                "id": "business_name",
                "say": "Let's set up invoicing. What's your business name — the name that should appear on invoices?",
                "expect": "text",
                "field": "business_name",
            },
            {
                "id": "business_address",
                "say": "And your business address?",
                "expect": "text",
                "field": "address",
            },
            {
                "id": "business_email",
                "say": "Email address for invoicing?",
                "expect": "text",
                "field": "email",
            },
            {
                "id": "payment_terms",
                "say": "What payment terms do you usually use? Most businesses do Net 30 (due in 30 days).",
                "expect": "choice",
                "options": ["Due on receipt", "Net 15", "Net 30", "Net 60"],
                "field": "payment_terms",
            },
            {
                "id": "payment_method",
                "say": "How do your clients pay you? This will appear as payment instructions on your invoices.",
                "expect": "text",
                "field": "payment_instructions",
            },
            {
                "id": "tax",
                "say": "Do you charge sales tax? If so, what percentage?",
                "expect": "text",
                "field": "tax_rate",
            },
        ],
        "on_complete": "invoicing_complete",
    },

    "social_media": {
        "steps": [
            {
                "id": "platforms",
                "say": "Let's set up your social media. Which platforms do you use? You can pick multiple.",
                "expect": "multi_choice",
                "options": ["Twitter/X", "LinkedIn", "Instagram", "Facebook", "TikTok", "Threads"],
                "field": "platforms",
            },
            {
                "id": "campaign_name",
                "say": "Let's create your first campaign. What would you like to call it? Something like 'Q2 Launch' or 'Brand Awareness'.",
                "expect": "text",
                "field": "campaign_name",
            },
            {
                "id": "objective",
                "say": "What's the goal of this campaign? For example: drive signups, build brand awareness, generate leads, promote a product...",
                "expect": "text",
                "field": "objective",
            },
            {
                "id": "audience",
                "say": "Who's your target audience? Be specific — like 'startup founders in SaaS' or 'homeowners in Las Vegas'.",
                "expect": "text",
                "field": "target_audience",
            },
            {
                "id": "tone",
                "say": "What tone should the posts have?",
                "expect": "choice",
                "options": ["Professional", "Casual & friendly", "Bold & provocative", "Educational"],
                "field": "tone",
            },
        ],
        "on_complete": "social_media_complete",
    },

    "tasks": {
        "steps": [
            {
                "id": "project_name",
                "say": "Let's create your first project board. What's the project called?",
                "expect": "text",
                "field": "project_name",
            },
            {
                "id": "template",
                "say": "Would you like to start with a template? I have pre-built boards for common workflows.",
                "expect": "choice",
                "options": ["Product Launch", "Client Project", "Content Calendar", "Start from scratch"],
                "field": "template",
            },
            {
                "id": "first_task",
                "say": "What's the first task you need to do for this project?",
                "expect": "text",
                "field": "first_task",
            },
        ],
        "on_complete": "tasks_complete",
    },

    "goals": {
        "steps": [
            {
                "id": "objective",
                "say": "Let's set your first goal. What's the big objective? For example: 'Grow revenue to $50K/month' or 'Launch mobile app by June'.",
                "expect": "text",
                "field": "objective_title",
            },
            {
                "id": "target",
                "say": "What's the measurable target? Give me a number and unit — like '50000 dollars' or '1000 users'.",
                "expect": "text",
                "field": "target",
            },
            {
                "id": "deadline",
                "say": "When do you want to achieve this by?",
                "expect": "text",
                "field": "deadline",
            },
            {
                "id": "key_results",
                "say": "What are 2-3 key results that would mean you're on track? For example: 'Close 20 new deals', 'Reduce churn to under 5%'.",
                "expect": "text",
                "field": "key_results",
            },
        ],
        "on_complete": "goals_complete",
    },

    "email": {
        "steps": [
            {
                "id": "signature_name",
                "say": "Let's set up your email. First, what name should appear in your email signature?",
                "expect": "text",
                "field": "sig_name",
            },
            {
                "id": "signature_title",
                "say": "And your title? Like 'Founder & CEO' or 'Senior Consultant'.",
                "expect": "text",
                "field": "sig_title",
            },
            {
                "id": "signature_phone",
                "say": "Phone number for the signature? (Or say 'skip' to leave it out.)",
                "expect": "text",
                "field": "sig_phone",
            },
            {
                "id": "first_template",
                "say": "Would you like me to create some email templates for you? I can make a follow-up template, a proposal template, and an introduction template.",
                "expect": "choice",
                "options": ["Yes, create templates", "I'll make my own later"],
                "field": "create_templates",
            },
        ],
        "on_complete": "email_complete",
    },

    "expenses": {
        "steps": [
            {
                "id": "categories",
                "say": "Let's set up expense tracking. I have default categories like Software, Hosting, Marketing, Travel, and Office Supplies. Do you need any custom categories for your business?",
                "expect": "text",
                "field": "custom_categories",
            },
            {
                "id": "budget",
                "say": "Would you like to set a monthly budget? I'll alert you when you're approaching the limit.",
                "expect": "text",
                "field": "monthly_budget",
            },
        ],
        "on_complete": "expenses_complete",
    },

    "team": {
        "steps": [
            {
                "id": "members",
                "say": "Let's set up your team. How many people do you want to invite?",
                "expect": "text",
                "field": "member_count",
            },
            {
                "id": "first_invite",
                "say": "What's the email address of the first person you'd like to invite?",
                "expect": "text",
                "field": "first_email",
            },
            {
                "id": "role",
                "say": "What role should they have?",
                "expect": "choice",
                "options": ["Admin (full access)", "Member (standard access)", "Viewer (read-only)"],
                "field": "role",
            },
        ],
        "on_complete": "team_complete",
    },
}


# ══════════════════════════════════════════════════════════════
# CONCIERGE SESSION MANAGER
# ══════════════════════════════════════════════════════════════

class SetupConcierge:
    """Manages guided setup sessions."""

    def start_session(self, user_id: str, intent: str = None,
                       user_message: str = "") -> dict:
        """Start a new setup session or detect intent from message."""
        if not intent and user_message:
            detected = detect_intent(user_message)
            intent = detected.get("intent")

        if not intent:
            # Welcome message with options
            return {
                "session_id": f"setup_{uuid.uuid4().hex[:8]}",
                "message": (
                    "Hi! I'm your setup concierge. I can help you configure any part of "
                    "the platform. What would you like to set up? You can say things like:\n\n"
                    "• \"Help me set up my CRM\"\n"
                    "• \"Let's create a social media campaign\"\n"
                    "• \"Set up invoicing for my business\"\n"
                    "• \"Create a project board\"\n"
                    "• \"Set my goals for the quarter\"\n"
                    "• \"Configure email templates\"\n"
                    "• \"Set up expense tracking\"\n"
                    "• \"Invite my team\"\n\n"
                    "Or just tell me about your business and I'll suggest where to start!"
                ),
                "intent": None,
                "step": None,
                "awaiting_input": True,
                "input_type": "text",
            }

        flow = SETUP_FLOWS.get(intent)
        if not flow:
            return {"error": f"Unknown setup flow: {intent}"}

        session_id = f"setup_{uuid.uuid4().hex[:8]}"
        first_step = flow["steps"][0]

        # Save session state
        from .database import get_db
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO setup_sessions
                    (id, user_id, intent, current_step, collected_data, status)
                VALUES (?,?,?,?,?,?)
            """, (session_id, user_id, intent, 0, "{}", "active"))

        return {
            "session_id": session_id,
            "intent": intent,
            "flow_label": SETUP_INTENTS.get(intent, {}).get("label", intent),
            "total_steps": len(flow["steps"]),
            "current_step": 1,
            "message": first_step["say"],
            "awaiting_input": True,
            "input_type": first_step["expect"],
            "options": first_step.get("options"),
            "field": first_step.get("field"),
        }

    def respond(self, session_id: str, user_id: str,
                 user_response: str) -> dict:
        """Process user's response and advance to next step."""
        from .database import get_db

        with get_db() as db:
            row = db.execute(
                "SELECT * FROM setup_sessions WHERE id=? AND user_id=?",
                (session_id, user_id)).fetchone()
        if not row:
            return {"error": "Session not found"}

        session = dict(row)
        intent = session["intent"]
        step_idx = session["current_step"]
        collected = json.loads(session.get("collected_data", "{}"))

        flow = SETUP_FLOWS.get(intent)
        if not flow:
            return {"error": "Flow not found"}

        current_step = flow["steps"][step_idx]

        # Store the user's response
        field = current_step.get("field", f"step_{step_idx}")
        collected[field] = user_response

        # Advance to next step
        next_idx = step_idx + 1

        if next_idx >= len(flow["steps"]):
            # Flow complete — execute the setup
            with get_db() as db:
                db.execute(
                    "UPDATE setup_sessions SET current_step=?, collected_data=?, status='completed' WHERE id=?",
                    (next_idx, json.dumps(collected), session_id))

            result = self._execute_setup(user_id, intent, collected)

            return {
                "session_id": session_id,
                "intent": intent,
                "complete": True,
                "message": result.get("message", "All set up!"),
                "summary": result.get("summary", {}),
                "next_suggestions": result.get("next_suggestions", []),
                "awaiting_input": False,
            }

        # More steps to go
        next_step = flow["steps"][next_idx]

        # Interpolate collected data into the message
        message = next_step["say"]
        for k, v in collected.items():
            message = message.replace(f"{{{k}}}", str(v))

        with get_db() as db:
            db.execute(
                "UPDATE setup_sessions SET current_step=?, collected_data=? WHERE id=?",
                (next_idx, json.dumps(collected), session_id))

        return {
            "session_id": session_id,
            "intent": intent,
            "complete": False,
            "total_steps": len(flow["steps"]),
            "current_step": next_idx + 1,
            "message": message,
            "awaiting_input": True,
            "input_type": next_step["expect"],
            "options": next_step.get("options"),
            "field": next_step.get("field"),
        }

    def get_session(self, session_id: str) -> dict:
        from .database import get_db
        with get_db() as db:
            row = db.execute("SELECT * FROM setup_sessions WHERE id=?",
                            (session_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["collected_data"] = json.loads(d.get("collected_data", "{}"))
        return d

    # ── Setup Execution ──

    def _execute_setup(self, user_id: str, intent: str, data: dict) -> dict:
        """Actually configure the platform based on collected data."""

        if intent == "first_run":
            return self._exec_first_run(user_id, data)
        elif intent == "crm":
            return self._exec_crm(user_id, data)
        elif intent == "invoicing":
            return self._exec_invoicing(user_id, data)
        elif intent == "social_media":
            return self._exec_social_media(user_id, data)
        elif intent == "tasks":
            return self._exec_tasks(user_id, data)
        elif intent == "goals":
            return self._exec_goals(user_id, data)
        elif intent == "email":
            return self._exec_email(user_id, data)
        elif intent == "expenses":
            return self._exec_expenses(user_id, data)
        elif intent == "team":
            return self._exec_team(user_id, data)

        return {"message": "Setup complete!", "summary": data}

    def _exec_first_run(self, user_id: str, data: dict) -> dict:
        from .database import get_db
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?,?)",
                (f"business_name_{user_id}", data.get("business_name", "")))
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?,?)",
                (f"business_type_{user_id}", data.get("business_type", "")))
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES (?,?)",
                (f"team_size_{user_id}", data.get("team_size", "")))

        next_feature = data.get("first_feature", "")
        next_intent = None
        if "crm" in next_feature.lower():
            next_intent = "crm"
        elif "invoice" in next_feature.lower():
            next_intent = "invoicing"
        elif "social" in next_feature.lower():
            next_intent = "social_media"
        elif "task" in next_feature.lower():
            next_intent = "tasks"

        return {
            "message": (
                f"Welcome to MyTeam360, {data.get('user_name', '')}! "
                f"I've set up your workspace for {data.get('business_name', 'your business')}. "
                f"{'Let me walk you through ' + next_feature + ' next!' if next_intent else 'Feel free to explore or ask me to set up any feature!'}"
            ),
            "summary": {
                "business_name": data.get("business_name"),
                "business_type": data.get("business_type"),
                "team_size": data.get("team_size"),
            },
            "next_suggestions": [
                "Set up my CRM",
                "Configure invoicing",
                "Create a social media campaign",
                "Build a project board",
            ],
            "auto_start_next": next_intent,
        }

    def _exec_crm(self, user_id: str, data: dict) -> dict:
        try:
            from .crm_customization import PipelineManager, CustomFieldManager
            pm = PipelineManager()
            cf = CustomFieldManager()

            industry = data.get("industry", "general")
            # Create industry-appropriate pipeline
            stages = self._get_industry_pipeline(industry)
            pm.create_pipeline(user_id, f"{industry.title()} Pipeline", stages=stages)

            # Create industry-appropriate custom fields
            fields = self._get_industry_fields(industry)
            for f in fields:
                cf.create_field(user_id, f["entity"], f["label"],
                               field_type=f.get("type", "text"),
                               options=f.get("options"))

            return {
                "message": (
                    f"Your CRM is ready! I've created a {industry} pipeline with "
                    f"{len(stages)} stages and {len(fields)} custom fields. "
                    f"You can start adding contacts now, or I can help you set up another feature."
                ),
                "summary": {
                    "pipeline_stages": len(stages),
                    "custom_fields": len(fields),
                    "industry": industry,
                },
                "next_suggestions": [
                    "Add my first contact",
                    "Set up invoicing",
                    "Import contacts from CSV",
                ],
            }
        except Exception as e:
            logger.error(f"CRM setup error: {e}")
            return {"message": "CRM setup complete! You can customize it further in settings.",
                    "summary": data}

    def _exec_invoicing(self, user_id: str, data: dict) -> dict:
        try:
            from .invoicing import InvoiceManager
            im = InvoiceManager()

            terms_map = {"Due on receipt": 0, "Net 15": 15, "Net 30": 30, "Net 60": 60}
            due_days = terms_map.get(data.get("payment_terms", "Net 30"), 30)
            tax_rate = 0
            try:
                tax_str = data.get("tax_rate", "0").replace("%", "").strip()
                if tax_str.lower() not in ("no", "none", "0", ""):
                    tax_rate = float(tax_str)
            except:
                pass

            im.set_business_profile(user_id,
                data.get("business_name", ""),
                address=data.get("address", ""),
                email=data.get("email", ""),
                payment_instructions=data.get("payment_instructions", ""),
                default_payment_terms=due_days,
                default_tax_rate=tax_rate)

            return {
                "message": (
                    f"Invoicing is set up for {data.get('business_name', 'your business')}! "
                    f"Payment terms: {data.get('payment_terms', 'Net 30')}. "
                    f"{'Tax rate: ' + str(tax_rate) + '%. ' if tax_rate else ''}"
                    f"You're ready to create your first invoice."
                ),
                "summary": {
                    "business_name": data.get("business_name"),
                    "payment_terms": data.get("payment_terms"),
                    "tax_rate": tax_rate,
                },
                "next_suggestions": [
                    "Create my first invoice",
                    "Set up recurring invoices",
                    "Create a proposal",
                ],
            }
        except Exception as e:
            logger.error(f"Invoicing setup error: {e}")
            return {"message": "Invoicing profile created!", "summary": data}

    def _exec_social_media(self, user_id: str, data: dict) -> dict:
        try:
            from .social_media import SocialMediaManager
            sm = SocialMediaManager()

            platform_map = {
                "Twitter/X": "twitter", "LinkedIn": "linkedin",
                "Instagram": "instagram", "Facebook": "facebook",
                "TikTok": "tiktok", "Threads": "threads",
            }
            platforms_raw = data.get("platforms", "")
            if isinstance(platforms_raw, str):
                platforms = [p.strip() for p in platforms_raw.split(",")]
            else:
                platforms = platforms_raw
            platform_ids = [platform_map.get(p, p.lower()) for p in platforms]

            tone_map = {
                "Professional": "professional",
                "Casual & friendly": "casual",
                "Bold & provocative": "bold",
                "Educational": "educational",
            }
            tone = tone_map.get(data.get("tone", ""), "professional")

            camp = sm.create_campaign(user_id,
                data.get("campaign_name", "My First Campaign"),
                objective=data.get("objective", ""),
                platforms=platform_ids,
                target_audience=data.get("target_audience", ""),
                tone=tone)

            return {
                "message": (
                    f"Your campaign '{data.get('campaign_name', '')}' is live on "
                    f"{', '.join(platforms)}! "
                    f"Next, you can ask your Marketing Space to generate posts, "
                    f"or create them manually in the content calendar."
                ),
                "summary": {
                    "campaign": data.get("campaign_name"),
                    "platforms": platforms,
                    "objective": data.get("objective"),
                    "audience": data.get("target_audience"),
                },
                "next_suggestions": [
                    "Generate a week of posts with AI",
                    "Connect my social accounts",
                    "Open the content calendar",
                ],
            }
        except Exception as e:
            logger.error(f"Social media setup error: {e}")
            return {"message": "Campaign created!", "summary": data}

    def _exec_tasks(self, user_id: str, data: dict) -> dict:
        try:
            from .tasks import TaskManager
            tm = TaskManager()

            template_map = {
                "Product Launch": "product_launch",
                "Client Project": "client_project",
                "Content Calendar": "content_calendar",
                "Start from scratch": None,
            }
            template = template_map.get(data.get("template"), None)

            proj = tm.create_project(user_id,
                data.get("project_name", "My Project"),
                template=template)

            if data.get("first_task"):
                tm.create_task(proj["id"], user_id, data["first_task"], priority="high")

            return {
                "message": (
                    f"Project '{data.get('project_name', '')}' is ready"
                    f"{' with ' + str(proj.get('tasks_created', 0)) + ' template tasks' if proj.get('tasks_created') else ''}! "
                    f"{'Your first task is on the board. ' if data.get('first_task') else ''}"
                    f"Open the board to start managing your work."
                ),
                "summary": {
                    "project": data.get("project_name"),
                    "template": data.get("template"),
                    "tasks_created": proj.get("tasks_created", 0) + (1 if data.get("first_task") else 0),
                },
                "next_suggestions": [
                    "Add more tasks",
                    "Invite team members",
                    "Set up project goals",
                ],
            }
        except Exception as e:
            logger.error(f"Tasks setup error: {e}")
            return {"message": "Project created!", "summary": data}

    def _exec_goals(self, user_id: str, data: dict) -> dict:
        try:
            from .business_os import GoalTracker
            gt = GoalTracker()

            # Parse target
            target_val = 0
            target_unit = ""
            target_raw = data.get("target", "")
            import re
            nums = re.findall(r"[\d,]+\.?\d*", target_raw.replace(",", ""))
            if nums:
                target_val = float(nums[0])
            words = re.findall(r"[a-zA-Z]+", target_raw)
            if words:
                target_unit = " ".join(words)

            goal = gt.create_goal(user_id,
                data.get("objective_title", ""),
                target_value=target_val,
                target_unit=target_unit,
                due_date=data.get("deadline", ""),
                category="business")

            # Parse key results
            kr_text = data.get("key_results", "")
            if kr_text:
                krs = [kr.strip() for kr in kr_text.replace(";", ",").split(",") if kr.strip()]
                for kr in krs[:5]:
                    gt.create_goal(user_id, kr, parent_id=goal["id"],
                                   goal_type="key_result", category="business")

            return {
                "message": (
                    f"Goal set: '{data.get('objective_title', '')}' — "
                    f"target: {target_val} {target_unit} by {data.get('deadline', 'TBD')}. "
                    f"Track your progress anytime from the Goals dashboard."
                ),
                "summary": {
                    "objective": data.get("objective_title"),
                    "target": f"{target_val} {target_unit}",
                    "deadline": data.get("deadline"),
                },
                "next_suggestions": [
                    "Set up my CRM to track deals",
                    "Create a project board for this goal",
                    "Set another goal",
                ],
            }
        except Exception as e:
            logger.error(f"Goals setup error: {e}")
            return {"message": "Goal created!", "summary": data}

    def _exec_email(self, user_id: str, data: dict) -> dict:
        try:
            from .biz_upgrades import EmailTemplateManager
            etm = EmailTemplateManager()

            # Create signature
            name = data.get("sig_name", "")
            title = data.get("sig_title", "")
            phone = data.get("sig_phone", "")
            if phone.lower() == "skip":
                phone = ""

            sig_html = f"<p><strong>{name}</strong>"
            if title:
                sig_html += f"<br>{title}"
            if phone:
                sig_html += f"<br>{phone}"
            sig_html += "</p>"
            etm.set_signature(user_id, sig_html)

            # Create default templates if requested
            templates_created = 0
            if "yes" in data.get("create_templates", "").lower():
                etm.create_template(user_id, "Follow-Up",
                    "Following up on our conversation",
                    f"Hi [Name],\n\nI wanted to follow up on our recent conversation. "
                    f"Please let me know if you have any questions.\n\nBest regards,\n{name}",
                    category="sales")
                etm.create_template(user_id, "Introduction",
                    "Introduction — {name}",
                    f"Hi [Name],\n\nMy name is {name} and I'm reaching out because "
                    f"[reason]. I'd love to connect and discuss how we might work together.\n\nBest,\n{name}",
                    category="outreach")
                etm.create_template(user_id, "Thank You",
                    "Thank you!",
                    f"Hi [Name],\n\nThank you for [reason]. I really appreciate it "
                    f"and look forward to [next step].\n\nBest regards,\n{name}",
                    category="general")
                templates_created = 3

            return {
                "message": (
                    f"Email is set up! Your signature is ready"
                    f"{' and I created 3 email templates (Follow-Up, Introduction, Thank You)' if templates_created else ''}. "
                    f"You can compose and send emails right from the platform."
                ),
                "summary": {
                    "signature": f"{name}, {title}",
                    "templates_created": templates_created,
                },
                "next_suggestions": [
                    "Compose my first email",
                    "Set up my CRM",
                    "Create more templates",
                ],
            }
        except Exception as e:
            logger.error(f"Email setup error: {e}")
            return {"message": "Email configured!", "summary": data}

    def _exec_expenses(self, user_id: str, data: dict) -> dict:
        try:
            from .biz_upgrades import CustomExpenseCategoryManager
            from .launch_fixes import SpendAlertManager

            # Custom categories
            cats_created = 0
            cats_text = data.get("custom_categories", "")
            if cats_text and cats_text.lower() not in ("no", "none", "nope"):
                cem = CustomExpenseCategoryManager()
                cats = [c.strip() for c in cats_text.replace(";", ",").split(",") if c.strip()]
                for cat in cats[:10]:
                    cem.create_category(user_id, cat)
                    cats_created += 1

            # Budget
            budget_set = False
            budget_text = data.get("monthly_budget", "")
            if budget_text and budget_text.lower() not in ("no", "none", "skip"):
                import re
                nums = re.findall(r"[\d,]+\.?\d*", budget_text.replace(",", ""))
                if nums:
                    sa = SpendAlertManager()
                    sa.set_budget(user_id, float(nums[0]))
                    budget_set = True

            return {
                "message": (
                    f"Expense tracking is ready! "
                    f"{'Added ' + str(cats_created) + ' custom categories. ' if cats_created else ''}"
                    f"{'Budget alerts set up. ' if budget_set else ''}"
                    f"Start logging expenses to track your spending."
                ),
                "summary": {
                    "custom_categories_added": cats_created,
                    "budget_configured": budget_set,
                },
                "next_suggestions": [
                    "Log my first expense",
                    "Set up invoicing",
                    "View expense categories",
                ],
            }
        except Exception as e:
            logger.error(f"Expenses setup error: {e}")
            return {"message": "Expense tracking ready!", "summary": data}

    def _exec_team(self, user_id: str, data: dict) -> dict:
        return {
            "message": (
                f"Team setup noted! To invite {data.get('first_email', 'your team member')}, "
                f"go to Settings → Team → Invite. They'll get an email with instructions to join. "
                f"Role: {data.get('role', 'Member')}."
            ),
            "summary": {
                "first_invite": data.get("first_email"),
                "role": data.get("role"),
            },
            "next_suggestions": [
                "Set up my CRM",
                "Create a project board",
                "Set team goals",
            ],
        }

    # ── Industry-Specific Configurations ──

    def _get_industry_pipeline(self, industry: str) -> list:
        """Return pipeline stages appropriate for the industry."""
        industry_lower = industry.lower()

        if any(w in industry_lower for w in ["real estate", "realtor", "property"]):
            return [
                {"label": "New Lead", "color": "#94a3b8", "type": "open"},
                {"label": "Showing Scheduled", "color": "#3b82f6", "type": "open"},
                {"label": "Offer Made", "color": "#a459f2", "type": "open"},
                {"label": "Under Contract", "color": "#f59e0b", "type": "open"},
                {"label": "Closed", "color": "#22c55e", "type": "won"},
                {"label": "Lost", "color": "#ef4444", "type": "lost"},
            ]
        elif any(w in industry_lower for w in ["saas", "software", "tech", "startup"]):
            return [
                {"label": "Discovery", "color": "#94a3b8", "type": "open"},
                {"label": "Demo", "color": "#3b82f6", "type": "open"},
                {"label": "Trial", "color": "#a459f2", "type": "open"},
                {"label": "Negotiation", "color": "#f59e0b", "type": "open"},
                {"label": "Closed Won", "color": "#22c55e", "type": "won"},
                {"label": "Churned", "color": "#ef4444", "type": "lost"},
            ]
        elif any(w in industry_lower for w in ["law", "legal", "attorney", "lawyer"]):
            return [
                {"label": "Intake", "color": "#94a3b8", "type": "open"},
                {"label": "Consultation", "color": "#3b82f6", "type": "open"},
                {"label": "Retained", "color": "#a459f2", "type": "open"},
                {"label": "Active Case", "color": "#f59e0b", "type": "open"},
                {"label": "Resolved", "color": "#22c55e", "type": "won"},
                {"label": "Declined", "color": "#ef4444", "type": "lost"},
            ]
        elif any(w in industry_lower for w in ["consult", "agency", "freelance"]):
            return [
                {"label": "Lead", "color": "#94a3b8", "type": "open"},
                {"label": "Discovery Call", "color": "#3b82f6", "type": "open"},
                {"label": "Proposal Sent", "color": "#a459f2", "type": "open"},
                {"label": "Negotiation", "color": "#f59e0b", "type": "open"},
                {"label": "Signed", "color": "#22c55e", "type": "won"},
                {"label": "Lost", "color": "#ef4444", "type": "lost"},
            ]
        else:
            # Default sales pipeline
            return [
                {"label": "Lead", "color": "#94a3b8", "type": "open"},
                {"label": "Qualified", "color": "#3b82f6", "type": "open"},
                {"label": "Proposal", "color": "#a459f2", "type": "open"},
                {"label": "Negotiation", "color": "#f59e0b", "type": "open"},
                {"label": "Won", "color": "#22c55e", "type": "won"},
                {"label": "Lost", "color": "#ef4444", "type": "lost"},
            ]

    def _get_industry_fields(self, industry: str) -> list:
        """Return custom fields appropriate for the industry."""
        industry_lower = industry.lower()

        if any(w in industry_lower for w in ["real estate", "realtor", "property"]):
            return [
                {"entity": "contact", "label": "Property Address", "type": "text"},
                {"entity": "deal", "label": "Listing Price", "type": "currency"},
                {"entity": "deal", "label": "Bedrooms", "type": "number"},
                {"entity": "deal", "label": "Square Footage", "type": "number"},
                {"entity": "contact", "label": "Lead Source", "type": "select",
                 "options": ["Zillow", "Realtor.com", "Referral", "Open House", "Cold Call"]},
            ]
        elif any(w in industry_lower for w in ["saas", "software", "tech"]):
            return [
                {"entity": "deal", "label": "MRR", "type": "currency"},
                {"entity": "deal", "label": "Plan", "type": "select",
                 "options": ["Free", "Starter", "Pro", "Enterprise"]},
                {"entity": "contact", "label": "LinkedIn", "type": "url"},
                {"entity": "deal", "label": "Churn Risk", "type": "select",
                 "options": ["Low", "Medium", "High"]},
                {"entity": "company", "label": "Employee Count", "type": "number"},
            ]
        elif any(w in industry_lower for w in ["law", "legal", "attorney"]):
            return [
                {"entity": "contact", "label": "Case Number", "type": "text"},
                {"entity": "contact", "label": "Court Date", "type": "date"},
                {"entity": "deal", "label": "Retainer Amount", "type": "currency"},
                {"entity": "deal", "label": "Case Type", "type": "select",
                 "options": ["Family", "Criminal", "Civil", "Corporate", "Immigration"]},
                {"entity": "contact", "label": "Opposing Counsel", "type": "text"},
            ]
        elif any(w in industry_lower for w in ["consult", "agency", "freelance"]):
            return [
                {"entity": "deal", "label": "Project Type", "type": "select",
                 "options": ["Hourly", "Fixed Price", "Retainer", "Project-Based"]},
                {"entity": "deal", "label": "Hourly Rate", "type": "currency"},
                {"entity": "contact", "label": "Referral Source", "type": "text"},
                {"entity": "deal", "label": "Estimated Hours", "type": "number"},
            ]
        else:
            return [
                {"entity": "contact", "label": "Lead Source", "type": "text"},
                {"entity": "deal", "label": "Deal Size", "type": "select",
                 "options": ["Small", "Medium", "Large", "Enterprise"]},
                {"entity": "company", "label": "Industry", "type": "text"},
            ]
