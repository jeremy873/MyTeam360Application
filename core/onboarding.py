# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# See LICENSE and NOTICE files for full legal terms.
# ═══════════════════════════════════════════════════════════════════

"""
Onboarding Assistant + Pricing Tiers

1. Onboarding Assistant — A conversational guide that:
   - Asks about the user's business, team size, and use case
   - Recommends the right features for their needs
   - Activates features with one confirmation
   - Walks through initial Space setup
   - Creates their first Spaces based on their answers

2. Pricing Tiers — Features gated by plan level:
   - Starter (Free / $0)     → Core platform, 1 user, 3 Spaces
   - Pro ($15/mo)             → Full platform, 5 users, unlimited Spaces
   - Business ($49/mo)        → Teams, Roundtable, Governance, Deliverables
   - Enterprise ($149/mo)     → Compliance, Risk, Policy, Delegation, Full suite
"""

import json
import uuid
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.onboarding")


# ══════════════════════════════════════════════════════════════
# PRICING TIERS
# ══════════════════════════════════════════════════════════════

PRICING_TIERS = {
    "student": {
        "label": "Student",
        "price_monthly": 5,
        "price_yearly": 48,  # $4/mo billed yearly
        "description": "AI tutoring for K-12 students. Homework help, study guides, practice quizzes, and progress tracking.",
        "limits": {
            "users": 1,
            "spaces": 3,
            "conversations_per_month": 200,
            "messages_per_conversation": 100,
            "knowledge_base_mb": 50,
        },
        "features_included": [
            "education_tutor",
        ],
        "features_available": [],
    },
    "starter": {
        "label": "Starter",
        "price_monthly": 7,
        "price_yearly": 60,  # $5/mo billed yearly
        "description": "Get started with AI Spaces. Perfect for individuals and side projects.",
        "limits": {
            "users": 1,
            "spaces": 3,
            "conversations_per_month": 100,
            "messages_per_conversation": 50,
            "knowledge_base_mb": 10,
        },
        "features_included": [],
        "features_available": [],
    },
    "student": {
        "label": "Student",
        "price_monthly": 15,
        "price_yearly": 120,  # $10/mo billed yearly
        "description": "Full academic AI support — Bachelor's through PhD. Learning DNA adapts to how you learn.",
        "education_only": True,
        "limits": {
            "users": 1,
            "spaces": 5,
            "conversations_per_month": -1,
            "messages_per_conversation": -1,
            "knowledge_base_mb": 500,
        },
        "features_included": [
            "education_tutor", "content_guardrails",
        ],
        "features_available": [],
    },
    "pro": {
        "label": "Pro",
        "price_monthly": 29,
        "price_yearly": 288,  # $24/mo billed yearly
        "most_popular": True,
        "description": "AI + Business Essentials. CRM, invoicing, tasks, and social media for freelancers and small teams.",
        "replaces": "HubSpot Starter ($15/mo) + FreshBooks ($19/mo) + Trello ($10/mo) + Buffer ($18/mo) = $62/mo",
        "limits": {
            "users": 5,
            "spaces": -1,  # unlimited
            "conversations_per_month": -1,
            "messages_per_conversation": -1,
            "knowledge_base_mb": 500,
            "crm_contacts": 500,
            "crm_deals": 50,
            "invoices_per_month": 20,
            "projects": 5,
            "social_platforms": 3,
            "goals": 10,
        },
        "features_included": [
            "business_dna", "confidence_scoring", "decision_tracker",
            "cost_ticker", "space_cloning", "summarization",
            "client_deliverables", "doc_export",
            "crm_basic", "invoicing_basic", "task_board", "social_media_basic",
            "goals_basic", "expense_tracking", "email_composer",
            "document_export_word_pdf_excel",
        ],
        "features_available": [
            "roundtable", "meeting_minutes", "action_items",
        ],
    },
    "business": {
        "label": "Business",
        "price_monthly": 79,
        "price_yearly": 828,  # $69/mo billed yearly
        "description": "Full Business OS. Unlimited CRM, invoicing, projects, social, plus team collaboration and compliance.",
        "replaces": "HubSpot Pro ($90/mo) + FreshBooks Plus ($30/mo) + Asana ($25/mo) + Hootsuite ($99/mo) + PandaDoc ($35/mo) = $279/mo",
        "additional_user_cost": 9,
        "limits": {
            "users": 10,
            "additional_users_available": True,
            "additional_user_price": 9,
            "spaces": -1,
            "conversations_per_month": -1,
            "messages_per_conversation": -1,
            "knowledge_base_mb": 5000,
            "crm_contacts": -1,
            "crm_deals": -1,
            "invoices_per_month": -1,
            "projects": -1,
            "social_platforms": -1,
            "goals": -1,
        },
        "features_included": [
            "business_dna", "confidence_scoring", "decision_tracker",
            "cost_ticker", "space_cloning", "summarization",
            "client_deliverables", "doc_export",
            "roundtable", "roundtable_multiuser", "roundtable_whiteboard",
            "meeting_minutes", "action_items",
            "teams", "presence", "activity_feed",
            "crm_full", "invoicing_full", "proposals",
            "task_board_full", "social_media_full",
            "goals_full", "expense_tracking", "email_composer",
            "meeting_prep", "competitive_intel", "client_portal",
            "financial_dashboard", "hr_assistant", "contract_templates",
            "document_export_word_pdf_excel",
            "corporate_records", "resolutions", "ai_negotiation",
        ],
        "features_available": [
            "compliance_watchdog", "risk_register", "policy_engine", "sales_coach",
            "digital_marketing",
        ],
    },
    "enterprise": {
        "label": "Enterprise",
        "price_monthly": -1,  # contact sales
        "price_yearly": -1,
        "description": "Dedicated instance, full compliance suite, unlimited everything. Contact sales.",
        "contact_sales": True,
        "contact_email": "sales@myteam360.ai",
        "includes": [
            "Dedicated server instance",
            "Custom domain and branding",
            "SSO / SAML integration",
            "Dedicated account manager",
            "SLA with uptime guarantee",
            "Custom compliance rules",
            "On-premise deployment option",
            "Priority support",
            "Data residency options",
            "Custom integrations",
        ],
        "limits": {
            "users": -1,
            "spaces": -1,
            "conversations_per_month": -1,
            "messages_per_conversation": -1,
            "knowledge_base_mb": -1,
        },
        "features_included": [
            "business_dna", "confidence_scoring", "decision_tracker",
            "cost_ticker", "space_cloning", "summarization",
            "client_deliverables", "doc_export",
            "roundtable", "roundtable_multiuser", "meeting_minutes",
            "action_items", "teams", "presence", "activity_feed",
            "corporate_records", "resolutions", "ai_negotiation",
            "compliance_watchdog", "compliance_escalation",
            "risk_register", "policy_engine", "delegation_authority",
            "knowledge_handoff", "sales_coach",
            "digital_marketing",
        ],
        "features_available": [],
    },
}


class PricingManager:
    """Manage subscription tiers and plan-based feature access."""

    def get_tiers(self) -> dict:
        """Return all pricing tiers for display."""
        result = {}
        for key, tier in PRICING_TIERS.items():
            t = {
                "label": tier["label"],
                "price_monthly": tier["price_monthly"],
                "price_yearly": tier["price_yearly"],
                "description": tier["description"],
                "limits": tier["limits"],
                "feature_count": len(tier["features_included"]),
            }
            if tier.get("contact_sales"):
                t["contact_sales"] = True
                t["contact_email"] = tier.get("contact_email", "sales@myteam360.ai")
                t["includes"] = tier.get("includes", [])
            if tier.get("additional_user_cost"):
                t["additional_user_cost"] = tier["additional_user_cost"]
            result[key] = t
        return result

    def get_tier_detail(self, tier_name: str) -> dict | None:
        return PRICING_TIERS.get(tier_name)

    def get_current_plan(self, owner_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT value FROM workspace_settings WHERE key='plan'").fetchone()
        plan = dict(row)["value"] if row else "starter"
        tier = PRICING_TIERS.get(plan, PRICING_TIERS["starter"])
        return {"plan": plan, "label": tier["label"],
                "price_monthly": tier["price_monthly"], "limits": tier["limits"]}

    def set_plan(self, owner_id: str, plan: str) -> dict:
        if plan not in PRICING_TIERS:
            raise ValueError(f"Invalid plan: {plan}")
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('plan', ?)",
                (plan,))
        return {"plan": plan, "label": PRICING_TIERS[plan]["label"]}

    def is_feature_in_plan(self, feature: str, plan: str = None) -> bool:
        """Check if a feature is included or available in the current plan."""
        if plan is None:
            plan = "starter"
        tier = PRICING_TIERS.get(plan, PRICING_TIERS["starter"])
        return (feature in tier["features_included"] or
                feature in tier.get("features_available", []))

    def get_upgrade_needed(self, feature: str) -> str | None:
        """Return the minimum plan needed for a feature."""
        for plan_key in ["starter", "pro", "business", "enterprise"]:
            tier = PRICING_TIERS[plan_key]
            if feature in tier["features_included"] or feature in tier.get("features_available", []):
                return plan_key
        return None


# ══════════════════════════════════════════════════════════════
# ONBOARDING ASSISTANT
# ══════════════════════════════════════════════════════════════

# Predefined use case templates
USE_CASE_TEMPLATES = {
    "freelancer": {
        "label": "Freelancer / Solopreneur",
        "description": "Content creation, client work, personal productivity",
        "recommended_plan": "pro",
        "recommended_features": [
            "business_dna", "confidence_scoring", "cost_ticker",
            "client_deliverables", "doc_export", "space_cloning",
        ],
        "starter_spaces": [
            {"name": "Content Writer", "icon": "✍️", "description": "Blog posts, social media, and marketing copy",
             "instructions": "You are a professional content writer. Match the user's writing style and brand voice. Focus on engaging, clear prose."},
            {"name": "Strategy Advisor", "icon": "🎯", "description": "Business strategy and planning",
             "instructions": "You are a business strategy advisor. Ask clarifying questions before giving advice. Focus on actionable, practical recommendations."},
            {"name": "Client Communications", "icon": "💼", "description": "Emails, proposals, and client messaging",
             "instructions": "You are a professional communications specialist. Draft emails, proposals, and messages that are polished and client-ready."},
        ],
    },
    "small_team": {
        "label": "Small Team (2-10 people)",
        "description": "Team collaboration, project management, shared AI",
        "recommended_plan": "business",
        "recommended_features": [
            "business_dna", "confidence_scoring", "cost_ticker",
            "teams", "roundtable", "meeting_minutes", "action_items",
            "doc_export", "summarization", "decision_tracker",
        ],
        "starter_spaces": [
            {"name": "Team Researcher", "icon": "🔍", "description": "Research and analysis for the team",
             "instructions": "You are a research analyst. Provide thorough, well-sourced analysis. Present findings clearly with key takeaways."},
            {"name": "Project Manager", "icon": "📋", "description": "Task tracking, planning, and coordination",
             "instructions": "You are a project manager. Help plan projects, track progress, identify risks, and keep the team organized."},
            {"name": "Meeting Assistant", "icon": "📝", "description": "Meeting prep, notes, and follow-ups",
             "instructions": "You help prepare for meetings, take notes, and track action items. Be organized and thorough."},
        ],
    },
    "agency": {
        "label": "Agency / Consultancy",
        "description": "Client portals, deliverables, multi-client management",
        "recommended_plan": "business",
        "recommended_features": [
            "business_dna", "confidence_scoring", "cost_ticker",
            "client_deliverables", "space_cloning", "doc_export",
            "teams", "roundtable", "meeting_minutes", "action_items",
            "corporate_records", "summarization",
        ],
        "starter_spaces": [
            {"name": "Strategy Consultant", "icon": "🧠", "description": "Client strategy and recommendations",
             "instructions": "You are a management consultant. Analyze problems systematically. Provide data-driven recommendations with clear rationale."},
            {"name": "Report Writer", "icon": "📊", "description": "Client deliverables and reports",
             "instructions": "You create polished client deliverables. Write in professional consulting language. Structure with executive summary, analysis, and recommendations."},
            {"name": "Proposal Builder", "icon": "📑", "description": "Scope, pricing, and proposals",
             "instructions": "You draft business proposals. Include scope, timeline, deliverables, pricing, and terms. Be specific and professional."},
        ],
    },
    "enterprise": {
        "label": "Enterprise / Regulated Industry",
        "description": "Compliance, governance, risk management, full team — contact sales for dedicated instance",
        "recommended_plan": "enterprise",
        "contact_sales": True,
        "recommended_features": [
            "business_dna", "confidence_scoring", "cost_ticker",
            "teams", "roundtable", "roundtable_multiuser",
            "meeting_minutes", "action_items", "corporate_records",
            "resolutions", "compliance_watchdog", "compliance_escalation",
            "risk_register", "policy_engine", "delegation_authority",
            "knowledge_handoff", "sales_coach", "doc_export", "summarization",
            "client_deliverables", "decision_tracker",
        ],
        "starter_spaces": [
            {"name": "Compliance Advisor", "icon": "⚖️", "description": "Regulatory guidance and policy review",
             "instructions": "You are a compliance advisor. Help review processes for regulatory compliance. Flag potential issues. Always recommend consulting legal counsel for final determinations."},
            {"name": "Risk Analyst", "icon": "🛡️", "description": "Risk assessment and mitigation",
             "instructions": "You analyze business risks. Categorize by likelihood and severity. Recommend specific mitigation strategies."},
            {"name": "Executive Assistant", "icon": "👔", "description": "Briefs, summaries, and communications",
             "instructions": "You are an executive assistant AI. Draft executive communications, summarize meetings, and prepare briefing documents. Be concise and polished."},
        ],
    },
    "creator": {
        "label": "Content Creator / Marketing",
        "description": "Content at scale, brand voice, multi-platform",
        "recommended_plan": "pro",
        "recommended_features": [
            "business_dna", "cost_ticker", "space_cloning",
            "client_deliverables", "doc_export", "confidence_scoring",
        ],
        "starter_spaces": [
            {"name": "Blog Writer", "icon": "📝", "description": "Long-form blog posts and articles",
             "instructions": "You write engaging blog posts. Match the user's voice exactly. Use storytelling, data, and practical takeaways."},
            {"name": "Social Media", "icon": "📱", "description": "Twitter, LinkedIn, Instagram content",
             "instructions": "You create social media content. Platform-aware: LinkedIn is professional, Twitter is punchy, Instagram is visual. Adapt to each."},
            {"name": "SEO Specialist", "icon": "🔎", "description": "Keyword strategy and optimization",
             "instructions": "You are an SEO specialist. Analyze content for keyword opportunities, suggest optimizations, and help with meta descriptions and titles."},
        ],
    },
    "developer": {
        "label": "Developer / Technical Team",
        "description": "Code review, documentation, architecture",
        "recommended_plan": "pro",
        "recommended_features": [
            "business_dna", "confidence_scoring", "cost_ticker",
            "decision_tracker", "action_items", "doc_export",
        ],
        "starter_spaces": [
            {"name": "Code Reviewer", "icon": "🔧", "description": "Code review, debugging, and best practices",
             "instructions": "You are a senior code reviewer. Review code for bugs, security issues, performance, and best practices. Be specific with line-level feedback."},
            {"name": "Architect", "icon": "🏗️", "description": "System design and architecture",
             "instructions": "You are a software architect. Help design systems, evaluate trade-offs, and create scalable architectures. Think about maintainability and cost."},
            {"name": "Doc Writer", "icon": "📖", "description": "API docs, READMEs, and technical writing",
             "instructions": "You write clear technical documentation. Match the codebase style. Include examples, edge cases, and common pitfalls."},
        ],
    },
    "student_k5": {
        "label": "Elementary Student (K-5)",
        "description": "Patient, encouraging tutoring for younger students",
        "recommended_plan": "student",
        "recommended_features": ["education_tutor"],
        "starter_spaces": [
            {"name": "Math Buddy", "icon": "🔢", "description": "Math help with fun explanations",
             "instructions": "You are a patient, encouraging math tutor for elementary students. Use simple language, fun examples (pizza slices for fractions, blocks for counting), and lots of encouragement. NEVER give the answer — guide them step by step. Celebrate every correct answer. Keep explanations short and visual."},
            {"name": "Reading Helper", "icon": "📚", "description": "Reading and writing support",
             "instructions": "You are a friendly reading and writing tutor for young students. Help with spelling, grammar, and reading comprehension using age-appropriate language. Ask questions about what they read. Encourage them to use their own words. Be warm and patient."},
            {"name": "Science Explorer", "icon": "🔬", "description": "Science with wonder and curiosity",
             "instructions": "You are an enthusiastic science tutor who makes learning fun. Explain concepts with everyday examples kids can relate to. Ask 'what do you think would happen if...' questions. Encourage curiosity. Use simple, vivid language."},
        ],
    },
    "student_middle": {
        "label": "Middle School Student (6-8)",
        "description": "Building skills for independent learning",
        "recommended_plan": "student",
        "recommended_features": ["education_tutor"],
        "starter_spaces": [
            {"name": "Math Tutor", "icon": "📐", "description": "Pre-algebra, algebra, and geometry",
             "instructions": "You are a math tutor for middle school students. Explain concepts clearly with step-by-step examples. Use the Socratic method — ask guiding questions instead of giving answers. Cover pre-algebra, algebra basics, geometry, and word problems. Be patient but push them to think critically."},
            {"name": "Writing Coach", "icon": "✍️", "description": "Essays, reports, and creative writing",
             "instructions": "You are a writing coach for middle school students. Help with essay structure (intro, body, conclusion), thesis statements, evidence, and grammar. Never write their essays — help them outline and revise. Teach the difference between summary and analysis. Encourage their voice."},
            {"name": "Study Planner", "icon": "📋", "description": "Organization and test prep",
             "instructions": "You help middle school students organize their studying. Create study schedules, break down large assignments into steps, generate practice questions, and teach study techniques (flashcards, spaced repetition, active recall). Build their confidence for tests."},
        ],
    },
    "student_high": {
        "label": "High School Student (9-12)",
        "description": "Advanced academics, test prep, and college readiness",
        "recommended_plan": "student",
        "recommended_features": ["education_tutor"],
        "starter_spaces": [
            {"name": "Academic Tutor", "icon": "🎓", "description": "All subjects — AP, honors, and standard",
             "instructions": "You are an academic tutor for high school students. Cover all subjects at standard, honors, and AP level. Use the Socratic method. Push for deeper understanding, not memorization. Help with critical thinking, analysis, and connecting concepts across subjects. Adapt to the student's level and pace."},
            {"name": "SAT/ACT Prep", "icon": "📝", "description": "Test strategies and practice",
             "instructions": "You are a test prep coach for SAT and ACT. Teach test-taking strategies (process of elimination, time management, reading passage techniques). Generate practice questions by section. Explain why wrong answers are wrong. Track which question types need more work. Be encouraging but realistic about score goals."},
            {"name": "Essay & Research", "icon": "📄", "description": "Research papers, college essays, literary analysis",
             "instructions": "You help high school students with advanced writing: research papers with proper citations, literary analysis essays, rhetorical analysis, argumentative essays, and college application essays. Teach MLA/APA format. Help develop a thesis, find evidence, and revise. Never write for them — coach them through the process."},
        ],
    },
}


class OnboardingAssistant:
    """Conversational setup guide that configures the platform
    based on the user's needs."""

    def __init__(self, feature_gate=None, agent_manager=None):
        self.feature_gate = feature_gate
        self.agents = agent_manager

    def get_use_cases(self) -> list:
        """Return available use case templates."""
        return [{"id": k, "label": v["label"], "description": v["description"]}
                for k, v in USE_CASE_TEMPLATES.items()]

    def get_recommendation(self, use_case: str) -> dict:
        """Get full recommendation for a use case."""
        template = USE_CASE_TEMPLATES.get(use_case)
        if not template:
            return {"error": f"Unknown use case: {use_case}"}

        plan = PRICING_TIERS.get(template["recommended_plan"], {})
        rec = {
            "use_case": use_case,
            "label": template["label"],
            "recommended_plan": {
                "name": template["recommended_plan"],
                "label": plan.get("label", ""),
                "price_monthly": plan.get("price_monthly", 0),
                "price_yearly": plan.get("price_yearly", 0),
            },
            "recommended_features": template["recommended_features"],
            "starter_spaces": template["starter_spaces"],
            "feature_count": len(template["recommended_features"]),
            "space_count": len(template["starter_spaces"]),
        }

        if template.get("contact_sales") or plan.get("contact_sales"):
            rec["contact_sales"] = True
            rec["contact_email"] = plan.get("contact_email", "sales@myteam360.ai")
            rec["message"] = ("Enterprise plans include dedicated instances, custom compliance, "
                             "SSO, SLA, and priority support. Contact our sales team for pricing "
                             "tailored to your organization's needs.")

        if plan.get("additional_user_cost"):
            rec["recommended_plan"]["additional_user_cost"] = plan["additional_user_cost"]

        return rec

    def apply_recommendation(self, owner_id: str, use_case: str,
                              admin_id: str, admin_name: str = "") -> dict:
        """Apply a use case recommendation — activate features and create Spaces."""
        template = USE_CASE_TEMPLATES.get(use_case)
        if not template:
            raise ValueError(f"Unknown use case: {use_case}")

        # Enterprise requires sales contact — cannot self-provision
        if template.get("contact_sales"):
            return {
                "contact_sales": True,
                "contact_email": "sales@myteam360.ai",
                "message": ("Enterprise plans require a dedicated instance and custom configuration. "
                           "Please contact sales@myteam360.ai and we'll build a plan tailored to "
                           "your organization's compliance, security, and scalability requirements."),
            }

        results = {"features_enabled": [], "spaces_created": [], "plan": ""}

        # Set plan
        pricing = PricingManager()
        pricing.set_plan(owner_id, template["recommended_plan"])
        results["plan"] = template["recommended_plan"]

        # Enable recommended features
        if self.feature_gate:
            for feature in template["recommended_features"]:
                try:
                    self.feature_gate.enable(feature, admin_id, admin_name)
                    results["features_enabled"].append(feature)
                except Exception:
                    pass

        # Create starter Spaces
        if self.agents:
            for space in template.get("starter_spaces", []):
                try:
                    agent = self.agents.create_agent({
                        "name": space["name"],
                        "icon": space.get("icon", "🤖"),
                        "color": "#a459f2",
                        "description": space.get("description", ""),
                        "instructions": space.get("instructions", ""),
                    }, owner_id=owner_id)
                    results["spaces_created"].append({
                        "name": space["name"],
                        "id": agent.get("id") or agent.get("agent", {}).get("id", ""),
                    })
                except Exception:
                    pass

        # Mark onboarding complete
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('onboarding_complete', ?)",
                (datetime.now().isoformat(),))
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('onboarding_use_case', ?)",
                (use_case,))

        return results

    def get_onboarding_status(self) -> dict:
        """Check if onboarding has been completed."""
        with get_db() as db:
            complete = db.execute(
                "SELECT value FROM workspace_settings WHERE key='onboarding_complete'"
            ).fetchone()
            use_case = db.execute(
                "SELECT value FROM workspace_settings WHERE key='onboarding_use_case'"
            ).fetchone()
        return {
            "completed": complete is not None,
            "completed_at": dict(complete)["value"] if complete else None,
            "use_case": dict(use_case)["value"] if use_case else None,
        }

    def reset_onboarding(self) -> dict:
        """Reset onboarding status (for re-running the guide)."""
        with get_db() as db:
            db.execute("DELETE FROM workspace_settings WHERE key='onboarding_complete'")
            db.execute("DELETE FROM workspace_settings WHERE key='onboarding_use_case'")
        return {"reset": True}
