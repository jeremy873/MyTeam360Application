# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Smart Team Builder — "I'm a [profession]" → Complete AI Team

150+ profession profiles across 25 industries. User says what they do,
we build their entire AI team with the right Spaces, the right
instructions, and the right features activated.

If their profession isn't listed, we use AI to dynamically generate
a team recommendation based on what they describe.

Architecture:
  INDUSTRIES → contain ROLES → each role has TEAM_TEMPLATE
  TEAM_TEMPLATE → list of Spaces with instructions + features to activate
"""

import json
import uuid
import re
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.team_builder")


# ══════════════════════════════════════════════════════════════
# INDUSTRY TAXONOMY — 25 industries, 150+ roles
# ══════════════════════════════════════════════════════════════

INDUSTRIES = {
    "marketing_advertising": {
        "label": "Marketing & Advertising",
        "icon": "📣",
        "roles": [
            "digital_marketer", "social_media_manager", "copywriter", "content_strategist",
            "seo_specialist", "ppc_manager", "email_marketer", "brand_manager",
            "marketing_director", "growth_hacker", "influencer_marketer", "media_buyer",
            "public_relations", "event_marketer", "affiliate_marketer",
        ],
    },
    "sales_business_dev": {
        "label": "Sales & Business Development",
        "icon": "🤝",
        "roles": [
            "sales_rep", "account_executive", "sales_manager", "business_development_rep",
            "sales_engineer", "inside_sales", "enterprise_sales", "channel_partner_manager",
            "sales_operations", "customer_success_manager", "key_account_manager",
            "proposal_writer", "solutions_consultant",
        ],
    },
    "technology_engineering": {
        "label": "Technology & Engineering",
        "icon": "💻",
        "roles": [
            "software_developer", "frontend_developer", "backend_developer", "fullstack_developer",
            "mobile_developer", "devops_engineer", "data_engineer", "ml_engineer",
            "qa_engineer", "security_engineer", "systems_architect", "cto",
            "tech_lead", "product_engineer", "embedded_engineer", "game_developer",
            "blockchain_developer", "cloud_architect",
        ],
    },
    "data_analytics": {
        "label": "Data & Analytics",
        "icon": "📊",
        "roles": [
            "data_analyst", "data_scientist", "business_analyst", "bi_analyst",
            "quantitative_analyst", "research_analyst", "market_researcher",
            "data_visualization_specialist", "analytics_manager",
        ],
    },
    "design_creative": {
        "label": "Design & Creative",
        "icon": "🎨",
        "roles": [
            "graphic_designer", "ui_ux_designer", "product_designer", "web_designer",
            "brand_designer", "motion_designer", "creative_director", "illustrator",
            "video_editor", "photographer", "art_director", "interior_designer",
            "fashion_designer", "industrial_designer",
        ],
    },
    "finance_accounting": {
        "label": "Finance & Accounting",
        "icon": "💰",
        "roles": [
            "accountant", "bookkeeper", "financial_analyst", "cfo", "controller",
            "tax_preparer", "auditor", "investment_analyst", "portfolio_manager",
            "stock_trader", "day_trader", "financial_planner", "wealth_manager",
            "credit_analyst", "treasury_analyst", "risk_analyst_finance",
            "accounts_payable_specialist", "payroll_specialist",
        ],
    },
    "legal": {
        "label": "Legal",
        "icon": "⚖️",
        "roles": [
            "attorney", "paralegal", "legal_assistant", "corporate_counsel",
            "ip_attorney", "litigation_attorney", "contract_specialist",
            "compliance_officer", "legal_ops_manager", "immigration_attorney",
            "family_law_attorney", "criminal_defense_attorney", "patent_agent",
        ],
    },
    "healthcare_medical": {
        "label": "Healthcare & Medical",
        "icon": "🏥",
        "roles": [
            "physician", "nurse_practitioner", "registered_nurse", "physician_assistant",
            "pharmacist", "dentist", "therapist_mental_health", "psychologist",
            "physical_therapist", "occupational_therapist", "medical_coder",
            "health_administrator", "clinical_researcher", "veterinarian",
            "optometrist", "chiropractor", "nutritionist", "speech_pathologist",
            "medical_device_rep", "hospital_administrator",
        ],
    },
    "education_training": {
        "label": "Education & Training",
        "icon": "🎓",
        "roles": [
            "teacher_k12", "professor", "academic_advisor", "school_administrator",
            "curriculum_developer", "instructional_designer", "corporate_trainer",
            "tutor", "special_education_teacher", "school_counselor",
            "education_consultant", "librarian", "research_assistant",
        ],
    },
    "real_estate": {
        "label": "Real Estate",
        "icon": "🏠",
        "roles": [
            "real_estate_agent", "real_estate_broker", "property_manager",
            "real_estate_investor", "appraiser", "mortgage_broker",
            "commercial_real_estate", "real_estate_developer", "leasing_agent",
        ],
    },
    "construction_trades": {
        "label": "Construction & Trades",
        "icon": "🔨",
        "roles": [
            "general_contractor", "project_manager_construction", "electrician",
            "plumber", "hvac_technician", "carpenter", "welder",
            "estimator", "site_superintendent", "safety_manager_construction",
            "architect", "civil_engineer", "surveyor",
        ],
    },
    "hospitality_food": {
        "label": "Hospitality & Food Service",
        "icon": "🍽️",
        "roles": [
            "restaurant_owner", "chef", "food_truck_owner", "hotel_manager",
            "event_planner", "catering_manager", "bartender_manager",
            "sommelier", "bakery_owner", "food_blogger",
        ],
    },
    "retail_ecommerce": {
        "label": "Retail & E-Commerce",
        "icon": "🛍️",
        "roles": [
            "retail_store_manager", "ecommerce_manager", "merchandiser",
            "buyer", "visual_merchandiser", "store_owner",
            "dropshipping_entrepreneur", "amazon_seller", "shopify_store_owner",
            "retail_operations_manager",
        ],
    },
    "consulting_professional_services": {
        "label": "Consulting & Professional Services",
        "icon": "💼",
        "roles": [
            "management_consultant", "strategy_consultant", "it_consultant",
            "hr_consultant", "tax_consultant", "operations_consultant",
            "executive_coach", "business_coach", "life_coach",
            "organizational_development", "change_management",
        ],
    },
    "human_resources": {
        "label": "Human Resources",
        "icon": "👥",
        "roles": [
            "hr_manager", "recruiter", "talent_acquisition", "hr_business_partner",
            "compensation_analyst", "benefits_administrator", "hr_director",
            "dei_specialist", "employee_relations", "training_development_manager",
            "people_operations",
        ],
    },
    "operations_logistics": {
        "label": "Operations & Logistics",
        "icon": "📦",
        "roles": [
            "operations_manager", "supply_chain_manager", "logistics_coordinator",
            "warehouse_manager", "fleet_manager", "procurement_specialist",
            "inventory_manager", "quality_assurance_manager", "production_manager",
            "lean_six_sigma", "facilities_manager",
        ],
    },
    "media_entertainment": {
        "label": "Media & Entertainment",
        "icon": "🎬",
        "roles": [
            "journalist", "editor", "podcast_host", "youtuber", "streamer",
            "producer", "screenwriter", "film_director", "music_producer",
            "author", "ghostwriter", "technical_writer", "grant_writer",
        ],
    },
    "government_public_sector": {
        "label": "Government & Public Sector",
        "icon": "🏛️",
        "roles": [
            "government_analyst", "policy_advisor", "city_planner",
            "grant_administrator", "public_affairs", "legislative_aide",
            "program_manager_gov", "contracting_officer", "intelligence_analyst",
            "law_enforcement_admin", "social_worker", "parole_officer",
        ],
    },
    "nonprofit_ngo": {
        "label": "Nonprofit & NGO",
        "icon": "🌍",
        "roles": [
            "nonprofit_director", "fundraiser", "grant_writer_nonprofit",
            "program_coordinator", "volunteer_coordinator", "advocacy_specialist",
            "community_organizer", "development_director",
        ],
    },
    "insurance": {
        "label": "Insurance",
        "icon": "🛡️",
        "roles": [
            "insurance_agent", "claims_adjuster", "underwriter",
            "actuarial_analyst", "insurance_broker", "risk_manager",
        ],
    },
    "transportation_automotive": {
        "label": "Transportation & Automotive",
        "icon": "🚗",
        "roles": [
            "fleet_operator", "auto_dealer", "auto_mechanic_owner",
            "trucking_company_owner", "logistics_broker", "dispatcher",
            "shuttle_operations_manager", "pilot",
        ],
    },
    "agriculture_environment": {
        "label": "Agriculture & Environment",
        "icon": "🌱",
        "roles": [
            "farmer", "rancher", "agronomist", "environmental_consultant",
            "sustainability_manager", "landscape_architect", "arborist",
            "wildlife_biologist", "forestry_manager",
        ],
    },
    "fitness_wellness": {
        "label": "Fitness & Wellness",
        "icon": "💪",
        "roles": [
            "personal_trainer", "gym_owner", "yoga_instructor",
            "wellness_coach", "sports_coach", "physical_therapy_clinic_owner",
            "spa_owner", "massage_therapist",
        ],
    },
    "beauty_personal_care": {
        "label": "Beauty & Personal Care",
        "icon": "💇",
        "roles": [
            "salon_owner", "barber_shop_owner", "esthetician",
            "makeup_artist", "nail_technician", "cosmetology_instructor",
        ],
    },
    "freelance_solopreneur": {
        "label": "Freelance & Solopreneur",
        "icon": "🚀",
        "roles": [
            "freelance_writer", "freelance_developer", "freelance_designer",
            "virtual_assistant", "consultant_independent", "photographer_freelance",
            "translator", "bookkeeper_freelance", "notary_public",
            "wedding_planner", "dj", "handyman",
        ],
    },
}


# ══════════════════════════════════════════════════════════════
# TEAM TEMPLATES — What Spaces to create for each role
# ══════════════════════════════════════════════════════════════

# Rather than 150+ individual templates (which would be 5000+ lines),
# we use a ROLE → ARCHETYPE mapping. Each archetype defines the team.
# Specific roles can override with custom Spaces.

TEAM_ARCHETYPES = {
    "creative_producer": {
        "spaces": [
            {"name": "Content Creator", "icon": "✍️", "instr": "You create compelling content. Match brand voice, optimize for engagement, and think in hooks and CTAs. Always suggest A/B variations."},
            {"name": "Editor & Proofreader", "icon": "📝", "instr": "You review and improve written content. Check grammar, clarity, flow, and impact. Suggest stronger words. Cut unnecessary words. Make every sentence earn its place."},
            {"name": "Research Assistant", "icon": "🔍", "instr": "You research topics thoroughly. Find data, statistics, trends, and examples to support content. Always cite where you found information."},
            {"name": "Strategy Advisor", "icon": "🎯", "instr": "You develop strategy. Analyze the market, identify opportunities, and create actionable plans with measurable goals and timelines."},
        ],
        "features": ["business_dna", "cost_ticker", "client_deliverables", "doc_export"],
    },
    "analyst_researcher": {
        "spaces": [
            {"name": "Data Analyst", "icon": "📊", "instr": "You analyze data and extract insights. Present findings clearly with key takeaways and recommended actions. Use precise numbers."},
            {"name": "Report Writer", "icon": "📄", "instr": "You write professional reports and presentations. Structure with executive summary, methodology, findings, and recommendations. Be thorough but concise."},
            {"name": "Research Partner", "icon": "🔬", "instr": "You help conduct research. Review literature, identify patterns, formulate hypotheses, and evaluate evidence. Be rigorous and objective."},
            {"name": "Devil's Advocate", "icon": "🤔", "instr": "You challenge assumptions and find weaknesses in arguments. Ask tough questions. Identify what could go wrong. Help stress-test conclusions."},
        ],
        "features": ["business_dna", "confidence_scoring", "decision_tracker", "doc_export"],
    },
    "client_facing": {
        "spaces": [
            {"name": "Client Communications", "icon": "💼", "instr": "You draft professional client communications — emails, proposals, presentations, and reports. Polished, clear, and tailored to each client's expectations."},
            {"name": "Proposal Builder", "icon": "📑", "instr": "You create winning proposals. Include scope, timeline, deliverables, pricing, and terms. Address the client's specific pain points. Differentiate from competitors."},
            {"name": "Sales Coach", "icon": "🏆", "instr": "You prepare for client meetings. Anticipate questions, prepare talking points, and rehearse objection handling. Focus on building trust and demonstrating value."},
            {"name": "Project Tracker", "icon": "📋", "instr": "You help manage client projects. Track deliverables, deadlines, and dependencies. Flag risks early. Keep status reports concise and actionable."},
        ],
        "features": ["business_dna", "sales_coach", "client_deliverables", "action_items", "doc_export"],
    },
    "technical_builder": {
        "spaces": [
            {"name": "Code Partner", "icon": "💻", "instr": "You are a senior developer. Write clean, well-documented code. Review for bugs, security, and performance. Explain your reasoning. Suggest better approaches when you see them."},
            {"name": "Architecture Advisor", "icon": "🏗️", "instr": "You design systems. Evaluate trade-offs between approaches. Think about scalability, maintainability, and cost. Draw from real-world patterns."},
            {"name": "Documentation Writer", "icon": "📖", "instr": "You write clear technical documentation. READMEs, API docs, architecture decisions, runbooks. Write for the person who'll read this at 2 AM during an outage."},
            {"name": "Debug Partner", "icon": "🔧", "instr": "You help debug problems. Ask clarifying questions, form hypotheses, suggest diagnostic steps. Think systematically — what changed? what's different? what's the simplest explanation?"},
        ],
        "features": ["business_dna", "confidence_scoring", "cost_ticker", "decision_tracker"],
    },
    "people_manager": {
        "spaces": [
            {"name": "HR Advisor", "icon": "👥", "instr": "You advise on people management — hiring, reviews, difficult conversations, policies, and compliance. Be practical and empathetic. Consider both the person and the organization."},
            {"name": "Communication Drafter", "icon": "✉️", "instr": "You draft internal communications — announcements, policy updates, feedback, performance reviews, and 1-on-1 agendas. Professional but human."},
            {"name": "Process Optimizer", "icon": "⚙️", "instr": "You improve business processes. Identify bottlenecks, suggest automation, create SOPs, and design workflows that reduce friction."},
            {"name": "Training Designer", "icon": "🎓", "instr": "You design training materials and programs. Create curriculum, assessments, and hands-on exercises. Make learning engaging and practical."},
        ],
        "features": ["business_dna", "action_items", "meeting_minutes", "doc_export", "summarization"],
    },
    "operations_logistics": {
        "spaces": [
            {"name": "Operations Analyst", "icon": "📦", "instr": "You analyze operations — supply chain, logistics, inventory, scheduling, and resource allocation. Find inefficiencies. Recommend improvements with data."},
            {"name": "Process Designer", "icon": "🔄", "instr": "You design and document processes. Create flowcharts, SOPs, checklists, and decision trees. Make complex processes simple and repeatable."},
            {"name": "Compliance Checker", "icon": "✅", "instr": "You verify operations compliance — safety regulations, quality standards, reporting requirements. Flag gaps before they become problems."},
            {"name": "Report Generator", "icon": "📊", "instr": "You create operational reports — KPI dashboards, status updates, variance analysis, and trend reports. Clear, accurate, actionable."},
        ],
        "features": ["business_dna", "action_items", "risk_register", "doc_export"],
    },
    "financial_professional": {
        "spaces": [
            {"name": "Financial Analyst", "icon": "📈", "instr": "You analyze financial data — statements, ratios, trends, and projections. Identify risks and opportunities. Present findings clearly for decision-makers."},
            {"name": "Tax & Compliance", "icon": "🧾", "instr": "You assist with tax preparation, compliance, and financial regulations. Identify deductions, flag issues, and ensure accuracy. Always recommend consulting a CPA for final decisions."},
            {"name": "Client Advisor", "icon": "💼", "instr": "You help prepare client-facing financial materials — reports, projections, and recommendations. Professional, clear, and tailored to the audience."},
            {"name": "Market Watcher", "icon": "👁️", "instr": "You monitor market conditions, economic indicators, and industry trends. Summarize what matters and what it means for the business or portfolio."},
        ],
        "features": ["business_dna", "confidence_scoring", "risk_register", "doc_export", "decision_tracker"],
    },
    "healthcare_provider": {
        "spaces": [
            {"name": "Clinical Notes", "icon": "📋", "instr": "You help draft clinical documentation — SOAP notes, treatment plans, referral letters, and discharge summaries. Use proper medical terminology. Always note: final documentation must be reviewed by the clinician."},
            {"name": "Research Assistant", "icon": "🔬", "instr": "You research medical topics — conditions, treatments, drug interactions, clinical guidelines. Cite peer-reviewed sources. Note evidence levels."},
            {"name": "Patient Communication", "icon": "💬", "instr": "You help draft patient-facing materials — education handouts, follow-up instructions, and consent explanations. Clear, empathetic, appropriate reading level."},
            {"name": "Admin & Billing", "icon": "🏥", "instr": "You assist with healthcare administration — scheduling optimization, coding questions, prior authorizations, and compliance documentation."},
        ],
        "features": ["business_dna", "doc_export", "summarization", "content_guardrails"],
    },
    "legal_professional": {
        "spaces": [
            {"name": "Legal Research", "icon": "📚", "instr": "You research legal questions — statutes, case law, regulations, and precedent. Organize findings clearly. Always note: this is research assistance, not legal advice."},
            {"name": "Document Drafter", "icon": "📝", "instr": "You draft legal documents — contracts, agreements, memoranda, briefs, and correspondence. Precise language. Follow formatting conventions for the jurisdiction."},
            {"name": "Case Analyst", "icon": "🔍", "instr": "You analyze cases — identify strengths, weaknesses, risks, and strategies. Consider both sides. Help prepare for opposing arguments."},
            {"name": "Client Manager", "icon": "👔", "instr": "You help manage client relationships — draft status updates, prepare meeting agendas, track deadlines and filing dates, and organize case materials."},
        ],
        "features": ["business_dna", "compliance_watchdog", "action_items", "doc_export", "decision_tracker"],
    },
    "educator": {
        "spaces": [
            {"name": "Lesson Planner", "icon": "📅", "instr": "You create lesson plans and curricula. Align to standards. Include objectives, activities, assessments, and differentiation strategies. Make learning engaging."},
            {"name": "Assignment Creator", "icon": "📝", "instr": "You create assignments, quizzes, rubrics, and assessments. Align to learning objectives. Include clear instructions and grading criteria."},
            {"name": "Student Support", "icon": "🤝", "instr": "You help address student needs — accommodations, behavioral strategies, parent communication, and intervention plans. Empathetic and practical."},
            {"name": "Research & Resources", "icon": "📚", "instr": "You find educational resources — articles, activities, tools, and best practices. Stay current with pedagogy trends. Help with professional development."},
        ],
        "features": ["business_dna", "doc_export", "content_guardrails"],
    },
    "small_business_owner": {
        "spaces": [
            {"name": "Business Advisor", "icon": "🧠", "instr": "You are a practical business advisor. Help with strategy, pricing, hiring, operations, and growth. Give advice a small business owner can act on TODAY, not just theory."},
            {"name": "Marketing Helper", "icon": "📣", "instr": "You help with marketing on a small budget. Social media, local SEO, email campaigns, referral programs, and community engagement. Practical and cost-effective."},
            {"name": "Financial Helper", "icon": "💰", "instr": "You help with small business finances — bookkeeping questions, pricing strategy, cash flow management, tax preparation, and budgeting. Keep it simple."},
            {"name": "Customer Service", "icon": "😊", "instr": "You help draft customer communications — responses to reviews, complaint handling, follow-up emails, and loyalty programs. Professional and warm."},
        ],
        "features": ["business_dna", "cost_ticker", "client_deliverables", "doc_export"],
    },
    "trades_professional": {
        "spaces": [
            {"name": "Estimate Builder", "icon": "🧮", "instr": "You help create job estimates and quotes. Materials, labor, timeline, and markup. Professional formatting. Account for contingencies."},
            {"name": "Client Manager", "icon": "📱", "instr": "You help manage client communications — appointment reminders, job updates, invoice follow-ups, and review requests. Professional but friendly."},
            {"name": "Safety & Compliance", "icon": "⚠️", "instr": "You help with safety documentation, OSHA compliance, permits, and inspection preparation. Keep workers safe and businesses compliant."},
            {"name": "Business Growth", "icon": "📈", "instr": "You help trades businesses grow — marketing, hiring, pricing, scheduling optimization, and reputation management. Practical advice for hands-on professionals."},
        ],
        "features": ["business_dna", "cost_ticker", "action_items"],
    },
    "investor_trader": {
        "spaces": [
            {"name": "Market Analyst", "icon": "📈", "instr": "You analyze markets — technical analysis, fundamental analysis, sector trends, and macroeconomic factors. Present data-driven insights, never predictions. Always note: not financial advice."},
            {"name": "Portfolio Reviewer", "icon": "💼", "instr": "You help review portfolio allocation, diversification, risk exposure, and rebalancing opportunities. Analytical and objective. Always note: not financial advice."},
            {"name": "News Synthesizer", "icon": "📰", "instr": "You synthesize market news and earnings reports into actionable summaries. What happened, why it matters, what to watch. Cut through noise."},
            {"name": "Risk Assessor", "icon": "⚖️", "instr": "You evaluate risk — position sizing, correlation, volatility, and downside scenarios. Help think about what could go wrong and how to protect against it."},
        ],
        "features": ["business_dna", "confidence_scoring", "decision_tracker", "risk_register"],
    },
    "nonprofit_worker": {
        "spaces": [
            {"name": "Grant Writer", "icon": "📝", "instr": "You write grant proposals. Match funder priorities. Include needs assessment, program design, evaluation plan, and budget. Compelling but honest."},
            {"name": "Fundraising Advisor", "icon": "🎯", "instr": "You plan fundraising campaigns — donor outreach, events, annual appeals, major gifts, and planned giving. Practical strategies for limited budgets."},
            {"name": "Impact Reporter", "icon": "📊", "instr": "You create impact reports and program evaluations. Tell the story with data. Show outcomes, not just outputs. For boards, donors, and the community."},
            {"name": "Volunteer Coordinator", "icon": "🤝", "instr": "You help manage volunteers — recruitment, scheduling, training, recognition, and retention. Make people feel valued and productive."},
        ],
        "features": ["business_dna", "doc_export", "action_items"],
    },
    "government_worker": {
        "spaces": [
            {"name": "Policy Analyst", "icon": "📋", "instr": "You analyze policy — research evidence, compare approaches, assess impact, and draft recommendations. Balanced, evidence-based, nonpartisan."},
            {"name": "Constituent Communications", "icon": "📬", "instr": "You draft public-facing communications — press releases, public notices, reports, and constituent responses. Clear, accessible, professional."},
            {"name": "Procurement Assistant", "icon": "📦", "instr": "You help with government procurement — RFP drafting, vendor evaluation, compliance with procurement regulations, and contract administration."},
            {"name": "Compliance Tracker", "icon": "✅", "instr": "You track regulatory compliance — deadlines, reporting requirements, audits, and corrective actions. Keep everything documented and on schedule."},
        ],
        "features": ["business_dna", "compliance_watchdog", "action_items", "doc_export"],
    },
}

# ══════════════════════════════════════════════════════════════
# ROLE → ARCHETYPE MAPPING
# ══════════════════════════════════════════════════════════════

ROLE_ARCHETYPE = {
    # Marketing & Advertising
    "digital_marketer": "creative_producer", "social_media_manager": "creative_producer",
    "copywriter": "creative_producer", "content_strategist": "creative_producer",
    "seo_specialist": "analyst_researcher", "ppc_manager": "analyst_researcher",
    "email_marketer": "creative_producer", "brand_manager": "creative_producer",
    "marketing_director": "people_manager", "growth_hacker": "analyst_researcher",
    "influencer_marketer": "creative_producer", "media_buyer": "analyst_researcher",
    "public_relations": "client_facing", "event_marketer": "client_facing",
    "affiliate_marketer": "analyst_researcher",

    # Sales
    "sales_rep": "client_facing", "account_executive": "client_facing",
    "sales_manager": "people_manager", "business_development_rep": "client_facing",
    "sales_engineer": "technical_builder", "inside_sales": "client_facing",
    "enterprise_sales": "client_facing", "channel_partner_manager": "client_facing",
    "sales_operations": "operations_logistics", "customer_success_manager": "client_facing",
    "key_account_manager": "client_facing", "proposal_writer": "creative_producer",
    "solutions_consultant": "client_facing",

    # Technology
    "software_developer": "technical_builder", "frontend_developer": "technical_builder",
    "backend_developer": "technical_builder", "fullstack_developer": "technical_builder",
    "mobile_developer": "technical_builder", "devops_engineer": "technical_builder",
    "data_engineer": "technical_builder", "ml_engineer": "technical_builder",
    "qa_engineer": "technical_builder", "security_engineer": "technical_builder",
    "systems_architect": "technical_builder", "cto": "technical_builder",
    "tech_lead": "technical_builder", "product_engineer": "technical_builder",
    "embedded_engineer": "technical_builder", "game_developer": "technical_builder",
    "blockchain_developer": "technical_builder", "cloud_architect": "technical_builder",

    # Data
    "data_analyst": "analyst_researcher", "data_scientist": "analyst_researcher",
    "business_analyst": "analyst_researcher", "bi_analyst": "analyst_researcher",
    "quantitative_analyst": "analyst_researcher", "research_analyst": "analyst_researcher",
    "market_researcher": "analyst_researcher",
    "data_visualization_specialist": "analyst_researcher",
    "analytics_manager": "analyst_researcher",

    # Design
    "graphic_designer": "creative_producer", "ui_ux_designer": "creative_producer",
    "product_designer": "creative_producer", "web_designer": "creative_producer",
    "brand_designer": "creative_producer", "motion_designer": "creative_producer",
    "creative_director": "creative_producer", "illustrator": "creative_producer",
    "video_editor": "creative_producer", "photographer": "creative_producer",
    "art_director": "creative_producer", "interior_designer": "creative_producer",
    "fashion_designer": "creative_producer", "industrial_designer": "creative_producer",

    # Finance
    "accountant": "financial_professional", "bookkeeper": "financial_professional",
    "financial_analyst": "financial_professional", "cfo": "financial_professional",
    "controller": "financial_professional", "tax_preparer": "financial_professional",
    "auditor": "financial_professional", "investment_analyst": "investor_trader",
    "portfolio_manager": "investor_trader", "stock_trader": "investor_trader",
    "day_trader": "investor_trader", "financial_planner": "financial_professional",
    "wealth_manager": "financial_professional", "credit_analyst": "financial_professional",
    "treasury_analyst": "financial_professional", "risk_analyst_finance": "investor_trader",
    "accounts_payable_specialist": "financial_professional",
    "payroll_specialist": "financial_professional",

    # Legal
    "attorney": "legal_professional", "paralegal": "legal_professional",
    "legal_assistant": "legal_professional", "corporate_counsel": "legal_professional",
    "ip_attorney": "legal_professional", "litigation_attorney": "legal_professional",
    "contract_specialist": "legal_professional", "compliance_officer": "legal_professional",
    "legal_ops_manager": "legal_professional", "immigration_attorney": "legal_professional",
    "family_law_attorney": "legal_professional",
    "criminal_defense_attorney": "legal_professional", "patent_agent": "legal_professional",

    # Healthcare
    "physician": "healthcare_provider", "nurse_practitioner": "healthcare_provider",
    "registered_nurse": "healthcare_provider", "physician_assistant": "healthcare_provider",
    "pharmacist": "healthcare_provider", "dentist": "healthcare_provider",
    "therapist_mental_health": "healthcare_provider", "psychologist": "healthcare_provider",
    "physical_therapist": "healthcare_provider",
    "occupational_therapist": "healthcare_provider",
    "medical_coder": "healthcare_provider", "health_administrator": "people_manager",
    "clinical_researcher": "analyst_researcher", "veterinarian": "healthcare_provider",
    "optometrist": "healthcare_provider", "chiropractor": "healthcare_provider",
    "nutritionist": "healthcare_provider", "speech_pathologist": "healthcare_provider",
    "medical_device_rep": "client_facing", "hospital_administrator": "people_manager",

    # Education
    "teacher_k12": "educator", "professor": "educator",
    "academic_advisor": "educator", "school_administrator": "people_manager",
    "curriculum_developer": "educator", "instructional_designer": "educator",
    "corporate_trainer": "educator", "tutor": "educator",
    "special_education_teacher": "educator", "school_counselor": "educator",
    "education_consultant": "client_facing", "librarian": "analyst_researcher",
    "research_assistant": "analyst_researcher",

    # Real Estate
    "real_estate_agent": "client_facing", "real_estate_broker": "client_facing",
    "property_manager": "operations_logistics", "real_estate_investor": "investor_trader",
    "appraiser": "analyst_researcher", "mortgage_broker": "financial_professional",
    "commercial_real_estate": "client_facing", "real_estate_developer": "small_business_owner",
    "leasing_agent": "client_facing",

    # Construction
    "general_contractor": "trades_professional",
    "project_manager_construction": "operations_logistics",
    "electrician": "trades_professional", "plumber": "trades_professional",
    "hvac_technician": "trades_professional", "carpenter": "trades_professional",
    "welder": "trades_professional", "estimator": "trades_professional",
    "site_superintendent": "operations_logistics",
    "safety_manager_construction": "operations_logistics",
    "architect": "creative_producer", "civil_engineer": "technical_builder",
    "surveyor": "analyst_researcher",

    # Hospitality
    "restaurant_owner": "small_business_owner", "chef": "creative_producer",
    "food_truck_owner": "small_business_owner", "hotel_manager": "people_manager",
    "event_planner": "client_facing", "catering_manager": "client_facing",
    "bartender_manager": "small_business_owner", "sommelier": "analyst_researcher",
    "bakery_owner": "small_business_owner", "food_blogger": "creative_producer",

    # Retail
    "retail_store_manager": "people_manager", "ecommerce_manager": "analyst_researcher",
    "merchandiser": "analyst_researcher", "buyer": "analyst_researcher",
    "visual_merchandiser": "creative_producer", "store_owner": "small_business_owner",
    "dropshipping_entrepreneur": "small_business_owner",
    "amazon_seller": "small_business_owner",
    "shopify_store_owner": "small_business_owner",
    "retail_operations_manager": "operations_logistics",

    # Consulting
    "management_consultant": "client_facing", "strategy_consultant": "client_facing",
    "it_consultant": "technical_builder", "hr_consultant": "people_manager",
    "tax_consultant": "financial_professional",
    "operations_consultant": "operations_logistics",
    "executive_coach": "client_facing", "business_coach": "client_facing",
    "life_coach": "client_facing", "organizational_development": "people_manager",
    "change_management": "people_manager",

    # HR
    "hr_manager": "people_manager", "recruiter": "people_manager",
    "talent_acquisition": "people_manager", "hr_business_partner": "people_manager",
    "compensation_analyst": "analyst_researcher",
    "benefits_administrator": "people_manager", "hr_director": "people_manager",
    "dei_specialist": "people_manager", "employee_relations": "people_manager",
    "training_development_manager": "educator", "people_operations": "people_manager",

    # Operations
    "operations_manager": "operations_logistics",
    "supply_chain_manager": "operations_logistics",
    "logistics_coordinator": "operations_logistics",
    "warehouse_manager": "operations_logistics",
    "fleet_manager": "operations_logistics",
    "procurement_specialist": "operations_logistics",
    "inventory_manager": "operations_logistics",
    "quality_assurance_manager": "operations_logistics",
    "production_manager": "operations_logistics",
    "lean_six_sigma": "operations_logistics",
    "facilities_manager": "operations_logistics",

    # Media
    "journalist": "creative_producer", "editor": "creative_producer",
    "podcast_host": "creative_producer", "youtuber": "creative_producer",
    "streamer": "creative_producer", "producer": "creative_producer",
    "screenwriter": "creative_producer", "film_director": "creative_producer",
    "music_producer": "creative_producer", "author": "creative_producer",
    "ghostwriter": "creative_producer", "technical_writer": "creative_producer",
    "grant_writer": "creative_producer",

    # Government
    "government_analyst": "government_worker", "policy_advisor": "government_worker",
    "city_planner": "government_worker", "grant_administrator": "government_worker",
    "public_affairs": "government_worker", "legislative_aide": "government_worker",
    "program_manager_gov": "government_worker",
    "contracting_officer": "government_worker",
    "intelligence_analyst": "analyst_researcher",
    "law_enforcement_admin": "government_worker",
    "social_worker": "healthcare_provider", "parole_officer": "government_worker",

    # Nonprofit
    "nonprofit_director": "nonprofit_worker", "fundraiser": "nonprofit_worker",
    "grant_writer_nonprofit": "nonprofit_worker",
    "program_coordinator": "nonprofit_worker",
    "volunteer_coordinator": "nonprofit_worker",
    "advocacy_specialist": "nonprofit_worker",
    "community_organizer": "nonprofit_worker",
    "development_director": "nonprofit_worker",

    # Insurance
    "insurance_agent": "client_facing", "claims_adjuster": "analyst_researcher",
    "underwriter": "analyst_researcher", "actuarial_analyst": "analyst_researcher",
    "insurance_broker": "client_facing", "risk_manager": "analyst_researcher",

    # Transportation
    "fleet_operator": "operations_logistics", "auto_dealer": "client_facing",
    "auto_mechanic_owner": "trades_professional",
    "trucking_company_owner": "small_business_owner",
    "logistics_broker": "operations_logistics", "dispatcher": "operations_logistics",
    "shuttle_operations_manager": "operations_logistics", "pilot": "operations_logistics",

    # Agriculture
    "farmer": "small_business_owner", "rancher": "small_business_owner",
    "agronomist": "analyst_researcher",
    "environmental_consultant": "client_facing",
    "sustainability_manager": "analyst_researcher",
    "landscape_architect": "creative_producer", "arborist": "trades_professional",
    "wildlife_biologist": "analyst_researcher", "forestry_manager": "operations_logistics",

    # Fitness
    "personal_trainer": "small_business_owner", "gym_owner": "small_business_owner",
    "yoga_instructor": "small_business_owner", "wellness_coach": "client_facing",
    "sports_coach": "educator",
    "physical_therapy_clinic_owner": "small_business_owner",
    "spa_owner": "small_business_owner", "massage_therapist": "small_business_owner",

    # Beauty
    "salon_owner": "small_business_owner", "barber_shop_owner": "small_business_owner",
    "esthetician": "small_business_owner", "makeup_artist": "creative_producer",
    "nail_technician": "small_business_owner",
    "cosmetology_instructor": "educator",

    # Freelance
    "freelance_writer": "creative_producer", "freelance_developer": "technical_builder",
    "freelance_designer": "creative_producer", "virtual_assistant": "operations_logistics",
    "consultant_independent": "client_facing",
    "photographer_freelance": "creative_producer",
    "translator": "creative_producer", "bookkeeper_freelance": "financial_professional",
    "notary_public": "small_business_owner", "wedding_planner": "client_facing",
    "dj": "small_business_owner", "handyman": "trades_professional",
}


# ══════════════════════════════════════════════════════════════
# SMART TEAM BUILDER ENGINE
# ══════════════════════════════════════════════════════════════

class SmartTeamBuilder:
    """Builds a complete AI team based on what the user does."""

    def __init__(self, agent_manager=None, feature_gate=None):
        self.agents = agent_manager
        self.feature_gate = feature_gate

    def get_industries(self) -> list:
        """List all industries."""
        return [{"id": k, "label": v["label"], "icon": v["icon"],
                 "role_count": len(v["roles"])}
                for k, v in INDUSTRIES.items()]

    def get_industry_roles(self, industry_id: str) -> list:
        """Get all roles in an industry."""
        industry = INDUSTRIES.get(industry_id)
        if not industry:
            return []
        return [{"id": r, "label": r.replace("_", " ").title(),
                 "archetype": ROLE_ARCHETYPE.get(r, "small_business_owner")}
                for r in industry["roles"]]

    def search_roles(self, query: str) -> list:
        """Fuzzy search across all roles."""
        query_lower = query.lower().replace(" ", "_")
        query_words = set(query.lower().split())
        results = []

        for industry_id, industry in INDUSTRIES.items():
            for role in industry["roles"]:
                role_words = set(role.split("_"))
                label = role.replace("_", " ").title()

                # Exact match
                if query_lower == role:
                    results.append({"id": role, "label": label,
                        "industry": industry["label"], "score": 100})
                    continue

                # Partial match
                overlap = len(query_words & role_words)
                if overlap > 0:
                    score = int(overlap / max(len(query_words), 1) * 80)
                    results.append({"id": role, "label": label,
                        "industry": industry["label"], "score": score})
                elif query_lower in role:
                    results.append({"id": role, "label": label,
                        "industry": industry["label"], "score": 50})

        results.sort(key=lambda x: -x["score"])
        return results[:10]

    def apply_recommendation(self, owner_id: str, role_id: str,
                              admin_name: str = "") -> dict:
        """Apply the recommendation — create Spaces and activate features."""
        rec = self.get_recommendation(role_id)
        if "error" in rec:
            return rec

        results = {"spaces_created": [], "features_enabled": [], "role": role_id}

        # Create Spaces
        if self.agents:
            for space in rec.get("spaces", []):
                try:
                    agent = self.agents.create_agent({
                        "name": space["name"],
                        "icon": space.get("icon", "🤖"),
                        "color": "#a459f2",
                        "instructions": space.get("instr", ""),
                    }, owner_id=owner_id)
                    results["spaces_created"].append(space["name"])
                except Exception:
                    pass

        # Activate features
        if self.feature_gate:
            for feature in rec.get("features", []):
                try:
                    self.feature_gate.enable(feature, owner_id, admin_name)
                    results["features_enabled"].append(feature)
                except Exception:
                    pass

        # Save role choice
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO workspace_settings (key, value) VALUES ('user_role', ?)",
                (role_id,))

        return results

    def get_stats(self) -> dict:
        """Platform coverage stats."""
        total_roles = sum(len(v["roles"]) for v in INDUSTRIES.values())
        learned = self._get_learned_count()
        return {
            "industries": len(INDUSTRIES),
            "built_in_roles": total_roles,
            "learned_roles": learned,
            "total_roles": total_roles + learned,
            "archetypes": len(TEAM_ARCHETYPES),
            "all_built_in_mapped": all(r in ROLE_ARCHETYPE
                for ind in INDUSTRIES.values() for r in ind["roles"]),
        }

    # ══════════════════════════════════════════════════════════
    # DYNAMIC PROFESSION LEARNING
    # ══════════════════════════════════════════════════════════

    def get_recommendation(self, role_id: str) -> dict:
        """Get team recommendation — built-in first, then learned, then generate."""
        # 1. Check built-in archetypes
        archetype_id = ROLE_ARCHETYPE.get(role_id)
        if archetype_id:
            archetype = TEAM_ARCHETYPES.get(archetype_id, {})
            label = role_id.replace("_", " ").title()
            return {
                "role": role_id,
                "role_label": label,
                "archetype": archetype_id,
                "source": "built_in",
                "spaces": archetype.get("spaces", []),
                "features": archetype.get("features", []),
                "space_count": len(archetype.get("spaces", [])),
                "feature_count": len(archetype.get("features", [])),
            }

        # 2. Check learned professions (previously generated by AI)
        learned = self._get_learned_profession(role_id)
        if learned:
            self._increment_learned_usage(role_id)
            return learned

        # 3. Not found anywhere — tell the caller to use generate endpoint
        return {
            "error": "not_found",
            "role": role_id,
            "message": f"'{role_id.replace('_', ' ').title()}' isn't in our database yet. "
                       f"We can build a custom team for this role using AI.",
            "action": "generate",
            "generate_url": f"/api/team-builder/generate",
        }

    def generate_for_unknown(self, role_title: str, owner_id: str,
                              description: str = "") -> dict:
        """Use AI to generate a team recommendation for an unknown profession,
        then LEARN it so the next person gets it instantly."""
        role_id = re.sub(r'[^a-z0-9]+', '_', role_title.lower()).strip('_')

        # Check if we already know this one
        if role_id in ROLE_ARCHETYPE:
            return self.get_recommendation(role_id)
        learned = self._get_learned_profession(role_id)
        if learned:
            self._increment_learned_usage(role_id)
            return learned

        # Generate using AI
        prompt = (
            "You are a workforce consultant. A professional just told you their job title.\n\n"
            f"Job Title: {role_title}\n"
            f"Description: {description or 'Not provided'}\n\n"
            "Create an AI team of exactly 4 specialists that would help this professional "
            "do their job better. For each specialist, provide:\n\n"
            "Respond ONLY in this exact JSON format, nothing else:\n"
            "{\n"
            '  "industry": "the broad industry category",\n'
            '  "spaces": [\n'
            '    {"name": "Specialist Name", "icon": "single emoji", "instr": "System instructions for this AI specialist. 2-3 sentences explaining their role and approach."},\n'
            '    {"name": "Specialist Name", "icon": "single emoji", "instr": "..."},\n'
            '    {"name": "Specialist Name", "icon": "single emoji", "instr": "..."},\n'
            '    {"name": "Specialist Name", "icon": "single emoji", "instr": "..."}\n'
            '  ],\n'
            '  "features": ["business_dna", "cost_ticker"]\n'
            "}\n\n"
            "For features, choose from: business_dna, cost_ticker, confidence_scoring, "
            "decision_tracker, client_deliverables, doc_export, action_items, sales_coach, "
            "digital_marketing, risk_register, summarization, space_cloning.\n"
            "Pick 3-5 that are most relevant to this profession.\n\n"
            "Respond with ONLY the JSON. No explanation. No markdown."
        )

        # Call AI
        ai_response = ""
        if self.agents:
            with get_db() as db:
                agent = db.execute(
                    "SELECT id FROM agents WHERE owner_id=? LIMIT 1",
                    (owner_id,)).fetchone()
            if agent:
                result = self.agents.run_agent(dict(agent)["id"], prompt, user_id=owner_id)
                ai_response = result.get("text", "")

        if not ai_response:
            # Fallback — assign to closest archetype by keyword
            return self._fallback_recommendation(role_id, role_title)

        # Parse AI response
        try:
            # Clean markdown fences if present
            clean = ai_response.strip()
            if clean.startswith("```"):
                clean = re.sub(r'^```(?:json)?\s*', '', clean)
                clean = re.sub(r'\s*```$', '', clean)
            parsed = json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            return self._fallback_recommendation(role_id, role_title)

        spaces = parsed.get("spaces", [])
        features = parsed.get("features", ["business_dna", "cost_ticker"])
        industry = parsed.get("industry", "Other")

        if not spaces or len(spaces) < 2:
            return self._fallback_recommendation(role_id, role_title)

        # Validate and clean spaces
        clean_spaces = []
        for s in spaces[:5]:
            if s.get("name") and s.get("instr"):
                clean_spaces.append({
                    "name": str(s["name"])[:50],
                    "icon": str(s.get("icon", "🤖"))[:4],
                    "instr": str(s["instr"])[:500],
                })

        # Validate features
        valid_features = {
            "business_dna", "cost_ticker", "confidence_scoring", "decision_tracker",
            "client_deliverables", "doc_export", "action_items", "sales_coach",
            "digital_marketing", "risk_register", "summarization", "space_cloning",
        }
        clean_features = [f for f in features if f in valid_features][:6]

        # LEARN IT — store in database for next time
        recommendation = {
            "role": role_id,
            "role_label": role_title.strip().title(),
            "industry": industry,
            "source": "ai_generated",
            "spaces": clean_spaces,
            "features": clean_features,
            "space_count": len(clean_spaces),
            "feature_count": len(clean_features),
        }

        self._store_learned_profession(role_id, recommendation)

        return recommendation

    def _get_learned_profession(self, role_id: str) -> dict | None:
        """Retrieve a previously learned profession from the database."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM learned_professions WHERE role_id=?",
                (role_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            rec = json.loads(d.get("recommendation", "{}"))
            rec["source"] = "learned"
            rec["times_used"] = d.get("times_used", 0)
            return rec
        except:
            return None

    def _store_learned_profession(self, role_id: str, recommendation: dict):
        """Store a new profession in the database."""
        pid = f"lp_{uuid.uuid4().hex[:12]}"
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO learned_professions
                    (id, role_id, role_label, industry, recommendation, times_used)
                VALUES (?,?,?,?,?,?)
            """, (pid, role_id,
                  recommendation.get("role_label", role_id.replace("_", " ").title()),
                  recommendation.get("industry", "Other"),
                  json.dumps(recommendation), 1))
        logger.info(f"Learned new profession: {role_id} ({recommendation.get('role_label')})")

    def _increment_learned_usage(self, role_id: str):
        """Track popularity of learned professions."""
        with get_db() as db:
            db.execute(
                "UPDATE learned_professions SET times_used=times_used+1 WHERE role_id=?",
                (role_id,))

    def _get_learned_count(self) -> int:
        try:
            with get_db() as db:
                row = db.execute("SELECT COUNT(*) as c FROM learned_professions").fetchone()
            return dict(row)["c"]
        except:
            return 0

    def get_learned_professions(self, min_uses: int = 0) -> list:
        """List all learned professions, optionally filtered by popularity."""
        with get_db() as db:
            rows = db.execute(
                "SELECT role_id, role_label, industry, times_used, created_at "
                "FROM learned_professions WHERE times_used>=? ORDER BY times_used DESC",
                (min_uses,)).fetchall()
        return [dict(r) for r in rows]

    def get_popular_learned(self, limit: int = 20) -> list:
        """Get the most popular AI-generated professions — candidates for promotion to built-in."""
        with get_db() as db:
            rows = db.execute(
                "SELECT role_id, role_label, industry, times_used FROM learned_professions "
                "ORDER BY times_used DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def _fallback_recommendation(self, role_id: str, role_title: str) -> dict:
        """When AI generation fails, assign the closest archetype by keywords."""
        title_lower = role_title.lower()
        keyword_map = {
            "technical_builder": ["developer", "engineer", "programmer", "coder", "tech", "it ", "devops", "architect"],
            "creative_producer": ["writer", "designer", "artist", "creative", "content", "editor", "photographer", "video"],
            "client_facing": ["sales", "account", "consultant", "advisor", "agent", "broker", "representative"],
            "analyst_researcher": ["analyst", "researcher", "data", "scientist", "statistician"],
            "people_manager": ["manager", "director", "supervisor", "coordinator", "lead", "chief", "head of"],
            "healthcare_provider": ["doctor", "nurse", "therapist", "clinician", "medical", "health", "dental", "pharmacy"],
            "legal_professional": ["lawyer", "attorney", "legal", "paralegal", "judge", "law"],
            "financial_professional": ["accountant", "financial", "bookkeeper", "tax", "audit", "banking", "mortgage"],
            "educator": ["teacher", "professor", "instructor", "tutor", "coach", "trainer", "education"],
            "trades_professional": ["electrician", "plumber", "carpenter", "mechanic", "technician", "installer", "repair"],
            "operations_logistics": ["operations", "logistics", "warehouse", "supply", "fleet", "dispatch", "shipping"],
            "small_business_owner": ["owner", "entrepreneur", "founder", "operator", "shop", "store", "business"],
            "government_worker": ["government", "federal", "state", "city", "public", "municipal", "officer", "inspector"],
            "nonprofit_worker": ["nonprofit", "charity", "ngo", "volunteer", "community", "advocacy", "foundation"],
            "investor_trader": ["trader", "investor", "portfolio", "stock", "crypto", "hedge", "fund"],
        }

        best_match = "small_business_owner"
        best_score = 0
        for archetype, keywords in keyword_map.items():
            score = sum(1 for kw in keywords if kw in title_lower)
            if score > best_score:
                best_score = score
                best_match = archetype

        archetype = TEAM_ARCHETYPES.get(best_match, TEAM_ARCHETYPES["small_business_owner"])
        recommendation = {
            "role": role_id,
            "role_label": role_title.strip().title(),
            "archetype": best_match,
            "source": "keyword_fallback",
            "spaces": archetype.get("spaces", []),
            "features": archetype.get("features", []),
            "space_count": len(archetype.get("spaces", [])),
            "feature_count": len(archetype.get("features", [])),
        }

        # Store it so next lookup is instant
        self._store_learned_profession(role_id, recommendation)
        return recommendation
