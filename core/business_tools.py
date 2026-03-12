# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Business Tools Suite — The remaining six features that complete the business OS.

4. Meeting Prep & Summary — Before/after meeting intelligence
5. Competitive Intelligence — Monitor competitors automatically
6. Client Portal — Share deliverables via secure links
7. Financial Dashboard — Revenue, expenses, runway
8. HR Assistant — Job descriptions, interview questions, onboarding
9. Contract Templates — NDA, SOW, freelancer agreements
"""

import json
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from .database import get_db

logger = logging.getLogger("MyTeam360.business_tools")


# ══════════════════════════════════════════════════════════════
# 4. MEETING PREP & SUMMARY
# ══════════════════════════════════════════════════════════════

class MeetingAssistant:
    """AI-powered meeting preparation and post-meeting summaries.

    Before: Pull context from CRM, past conversations, knowledge base.
    After: Generate summary, action items, follow-up emails.
    """

    def prepare(self, owner_id: str, meeting_with: str,
                 topic: str = "", contact_id: str = "",
                 deal_id: str = "") -> dict:
        """Generate a meeting prep brief."""
        context_parts = [f"Meeting with: {meeting_with}", f"Topic: {topic}"]

        # Pull CRM context if available
        if contact_id:
            try:
                from .crm import CRMManager
                crm = CRMManager()
                ctx = crm.build_contact_context(contact_id)
                if ctx:
                    context_parts.append(f"\n--- CRM Context ---\n{ctx}")
            except:
                pass

        if deal_id:
            try:
                from .crm import CRMManager
                crm = CRMManager()
                ctx = crm.build_deal_context(deal_id)
                if ctx:
                    context_parts.append(f"\n--- Deal Context ---\n{ctx}")
            except:
                pass

        prompt = (
            "Prepare a meeting brief for the following:\n\n"
            + "\n".join(context_parts) +
            "\n\nGenerate:\n"
            "1. KEY TALKING POINTS — 3-5 items to discuss\n"
            "2. QUESTIONS TO ASK — 3-4 strategic questions\n"
            "3. POTENTIAL OBJECTIONS — what they might push back on\n"
            "4. BACKGROUND CONTEXT — relevant history and context\n"
            "5. DESIRED OUTCOMES — what success looks like for this meeting\n"
        )

        return {
            "meeting_with": meeting_with,
            "topic": topic,
            "prompt": prompt,
            "context_sources": ["crm_contact", "crm_deal"] if contact_id else [],
        }

    def summarize(self, owner_id: str, meeting_with: str,
                   notes: str, contact_id: str = "",
                   deal_id: str = "") -> dict:
        """Generate post-meeting summary and action items."""
        prompt = (
            f"Summarize this meeting and extract action items.\n\n"
            f"Meeting with: {meeting_with}\n"
            f"Notes/Transcript:\n{notes}\n\n"
            f"Generate:\n"
            f"1. SUMMARY — 2-3 sentence overview\n"
            f"2. KEY DECISIONS — what was agreed on\n"
            f"3. ACTION ITEMS — who does what, by when (format: [Person] — [Task] — [Due])\n"
            f"4. FOLLOW-UP EMAIL DRAFT — professional email summarizing next steps\n"
            f"5. OPEN QUESTIONS — unresolved items to address next time\n"
        )

        return {
            "meeting_with": meeting_with,
            "prompt": prompt,
            "contact_id": contact_id,
            "deal_id": deal_id,
        }


# ══════════════════════════════════════════════════════════════
# 5. COMPETITIVE INTELLIGENCE
# ══════════════════════════════════════════════════════════════

class CompetitiveIntel:
    """Monitor competitors and generate intelligence reports."""

    def add_competitor(self, owner_id: str, name: str, website: str = "",
                        description: str = "", tags: list = None) -> dict:
        cid = f"comp_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO competitors
                    (id, owner_id, name, website, description, tags)
                VALUES (?,?,?,?,?,?)
            """, (cid, owner_id, name, website, description,
                  json.dumps(tags or [])))
        return {"id": cid, "name": name}

    def list_competitors(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM competitors WHERE owner_id=? ORDER BY name",
                (owner_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.get("tags", "[]"))
            result.append(d)
        return result

    def get_competitor(self, competitor_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM competitors WHERE id=?",
                            (competitor_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d.get("tags", "[]"))
        return d

    def delete_competitor(self, competitor_id: str) -> dict:
        with get_db() as db:
            db.execute("DELETE FROM competitors WHERE id=?", (competitor_id,))
        return {"deleted": True}

    def log_intel(self, competitor_id: str, intel_type: str,
                   content: str, source: str = "") -> dict:
        """Log a competitive intelligence item."""
        iid = f"intel_{uuid.uuid4().hex[:8]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO competitor_intel
                    (id, competitor_id, intel_type, content, source)
                VALUES (?,?,?,?,?)
            """, (iid, competitor_id, intel_type, content[:2000], source))
        return {"id": iid, "type": intel_type}

    def get_intel(self, competitor_id: str, limit: int = 20) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM competitor_intel WHERE competitor_id=? ORDER BY created_at DESC LIMIT ?",
                (competitor_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def build_analysis_prompt(self, owner_id: str) -> str:
        """Build a prompt for AI to analyze competitive landscape."""
        competitors = self.list_competitors(owner_id)
        if not competitors:
            return "No competitors tracked yet. Add competitors first."

        parts = ["Analyze our competitive landscape:\n"]
        for c in competitors:
            intel = self.get_intel(c["id"], limit=5)
            parts.append(f"\n**{c['name']}** ({c.get('website', '')})")
            parts.append(f"  Description: {c.get('description', 'N/A')}")
            if intel:
                parts.append("  Recent intel:")
                for i in intel[:3]:
                    parts.append(f"    - [{i['intel_type']}] {i['content'][:150]}")

        parts.append(
            "\n\nGenerate:\n"
            "1. COMPETITIVE POSITIONING — where we stand vs each competitor\n"
            "2. THREATS — biggest risks from competitors\n"
            "3. OPPORTUNITIES — gaps we can exploit\n"
            "4. RECOMMENDATIONS — strategic actions to take\n"
        )
        return "\n".join(parts)


# ══════════════════════════════════════════════════════════════
# 6. CLIENT PORTAL
# ══════════════════════════════════════════════════════════════

class ClientPortal:
    """Share deliverables with clients via secure, branded links.
    No login required for clients — just a secure token URL.
    """

    def create_share(self, owner_id: str, title: str,
                      content_type: str, content_id: str,
                      client_name: str = "", client_email: str = "",
                      expires_days: int = 30, password: str = "") -> dict:
        """Create a shareable link for a deliverable."""
        sid = f"share_{uuid.uuid4().hex[:12]}"
        token = secrets.token_urlsafe(24)
        expires = (datetime.now() + timedelta(days=expires_days)).isoformat()
        password_hash = hashlib.sha256(password.encode()).hexdigest() if password else ""

        with get_db() as db:
            db.execute("""
                INSERT INTO client_shares
                    (id, owner_id, token, title, content_type, content_id,
                     client_name, client_email, expires_at, password_hash,
                     view_count, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,0,?)
            """, (sid, owner_id, token, title, content_type, content_id,
                  client_name, client_email, expires, password_hash, "active"))

        import os
        base_url = os.getenv("BASE_URL", "https://myteam360.ai")
        return {
            "id": sid,
            "share_url": f"{base_url}/portal/{token}",
            "token": token,
            "expires": expires,
            "password_protected": bool(password),
        }

    def get_share(self, token: str, password: str = "") -> dict:
        """Retrieve a shared item by token (client access)."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM client_shares WHERE token=? AND status='active'",
                (token,)).fetchone()
        if not row:
            return {"error": "Share not found or expired"}

        d = dict(row)
        # Check expiry
        if d.get("expires_at"):
            try:
                if datetime.now() > datetime.fromisoformat(d["expires_at"]):
                    return {"error": "This link has expired"}
            except:
                pass

        # Check password
        if d.get("password_hash"):
            if not password:
                return {"error": "password_required", "password_protected": True}
            if hashlib.sha256(password.encode()).hexdigest() != d["password_hash"]:
                return {"error": "Incorrect password"}

        # Increment view count
        with get_db() as db:
            db.execute(
                "UPDATE client_shares SET view_count=view_count+1, last_viewed=? WHERE id=?",
                (datetime.now().isoformat(), d["id"]))

        return {
            "title": d["title"],
            "content_type": d["content_type"],
            "content_id": d["content_id"],
            "client_name": d.get("client_name", ""),
            "view_count": d.get("view_count", 0) + 1,
        }

    def list_shares(self, owner_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM client_shares WHERE owner_id=? ORDER BY created_at DESC",
                (owner_id,)).fetchall()
        return [dict(r) for r in rows]

    def revoke_share(self, share_id: str) -> dict:
        with get_db() as db:
            db.execute("UPDATE client_shares SET status='revoked' WHERE id=?",
                      (share_id,))
        return {"revoked": True}


# ══════════════════════════════════════════════════════════════
# 7. FINANCIAL DASHBOARD
# ══════════════════════════════════════════════════════════════

class FinancialDashboard:
    """Revenue, expenses, and financial health overview."""

    def get_overview(self, owner_id: str) -> dict:
        """Pull financial data from invoices, subscriptions, and expenses."""
        with get_db() as db:
            # Revenue from invoices
            revenue_paid = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=? AND status='paid'",
                (owner_id,)).fetchone()
            revenue_outstanding = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=? AND status='sent'",
                (owner_id,)).fetchone()
            revenue_overdue = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=? AND status='sent' AND due_date<?",
                (owner_id, datetime.now().strftime("%Y-%m-%d"))).fetchone()

            # Monthly revenue (last 6 months)
            monthly = []
            for i in range(5, -1, -1):
                month_start = (datetime.now().replace(day=1) - timedelta(days=30*i)).strftime("%Y-%m-01")
                month_end = (datetime.now().replace(day=1) - timedelta(days=30*(i-1))).strftime("%Y-%m-01") if i > 0 else "9999-12-31"
                row = db.execute(
                    "SELECT COALESCE(SUM(total),0) as t FROM invoices WHERE owner_id=? AND status='paid' AND paid_at>=? AND paid_at<?",
                    (owner_id, month_start, month_end)).fetchone()
                monthly.append({"month": month_start[:7], "revenue": round(dict(row)["t"], 2)})

            # Deal pipeline value
            pipeline = db.execute(
                "SELECT COALESCE(SUM(value),0) as t FROM crm_deals WHERE owner_id=? AND status='open'",
                (owner_id,)).fetchone()

            # Proposals pending
            proposals_pending = db.execute(
                "SELECT COALESCE(SUM(total),0) as t FROM proposals WHERE owner_id=? AND status='sent'",
                (owner_id,)).fetchone()

            # Invoice counts
            invoice_counts = db.execute(
                "SELECT status, COUNT(*) as c FROM invoices WHERE owner_id=? GROUP BY status",
                (owner_id,)).fetchall()

        return {
            "revenue": {
                "total_paid": round(dict(revenue_paid)["t"], 2),
                "outstanding": round(dict(revenue_outstanding)["t"], 2),
                "overdue": round(dict(revenue_overdue)["t"], 2),
            },
            "pipeline_value": round(dict(pipeline)["t"], 2),
            "proposals_pending": round(dict(proposals_pending)["t"], 2),
            "monthly_revenue": monthly,
            "invoices_by_status": {dict(r)["status"]: dict(r)["c"] for r in invoice_counts},
        }


# ══════════════════════════════════════════════════════════════
# 8. HR ASSISTANT
# ══════════════════════════════════════════════════════════════

class HRAssistant:
    """AI-powered HR tools for small teams.

    - Job description generation
    - Interview question generation
    - Onboarding checklist templates
    - Policy document templates
    """

    JOB_DESCRIPTION_PROMPT = (
        "Write a professional job description for the following role:\n\n"
        "Title: {title}\n"
        "Department: {department}\n"
        "Type: {employment_type}\n"
        "Location: {location}\n"
        "Company: {company}\n"
        "Description: {description}\n\n"
        "Include: Job summary, Key responsibilities (5-8), Required qualifications, "
        "Preferred qualifications, Benefits, and Equal opportunity statement.\n"
        "Tone: Professional but welcoming. Avoid gendered language."
    )

    INTERVIEW_PROMPT = (
        "Generate interview questions for a {title} position.\n\n"
        "Role description: {description}\n"
        "Interview stage: {stage}\n\n"
        "Generate:\n"
        "1. BEHAVIORAL QUESTIONS (3) — past experience, STAR format\n"
        "2. TECHNICAL QUESTIONS (3) — role-specific skills\n"
        "3. SITUATIONAL QUESTIONS (2) — hypothetical scenarios\n"
        "4. CULTURE FIT QUESTIONS (2) — values and work style\n"
        "5. CANDIDATE QUESTIONS — 3 questions the candidate might ask (with suggested answers)\n"
    )

    ONBOARDING_TEMPLATES = {
        "general": {
            "name": "General Onboarding",
            "items": [
                {"task": "Send welcome email with start date and logistics", "due": "Day -3", "assigned": "HR"},
                {"task": "Set up email account and software access", "due": "Day -1", "assigned": "IT"},
                {"task": "Prepare workspace/equipment", "due": "Day -1", "assigned": "Office Manager"},
                {"task": "First day orientation — company overview", "due": "Day 1", "assigned": "HR"},
                {"task": "Introduce to team members", "due": "Day 1", "assigned": "Manager"},
                {"task": "Review company handbook and policies", "due": "Day 1", "assigned": "HR"},
                {"task": "Set up direct deposit and benefits enrollment", "due": "Day 1", "assigned": "HR"},
                {"task": "Assign onboarding buddy/mentor", "due": "Day 1", "assigned": "Manager"},
                {"task": "First week check-in", "due": "Day 5", "assigned": "Manager"},
                {"task": "30-day performance check-in", "due": "Day 30", "assigned": "Manager"},
                {"task": "60-day review and feedback", "due": "Day 60", "assigned": "Manager"},
                {"task": "90-day probation review", "due": "Day 90", "assigned": "Manager/HR"},
            ],
        },
        "remote": {
            "name": "Remote Employee Onboarding",
            "items": [
                {"task": "Ship laptop and equipment", "due": "Day -5", "assigned": "IT"},
                {"task": "Send welcome package (swag, handbook)", "due": "Day -3", "assigned": "HR"},
                {"task": "Set up all software accounts (email, Slack, tools)", "due": "Day -1", "assigned": "IT"},
                {"task": "Schedule video orientation call", "due": "Day 1", "assigned": "HR"},
                {"task": "Virtual team introductions", "due": "Day 1", "assigned": "Manager"},
                {"task": "Walk through communication norms and tools", "due": "Day 1", "assigned": "Manager"},
                {"task": "Assign onboarding buddy for daily check-ins (first 2 weeks)", "due": "Day 1", "assigned": "Manager"},
                {"task": "First virtual coffee/lunch with team", "due": "Day 3", "assigned": "Team"},
                {"task": "Weekly 1:1 with manager (first month)", "due": "Weekly", "assigned": "Manager"},
                {"task": "30/60/90-day virtual reviews", "due": "Day 30/60/90", "assigned": "Manager"},
            ],
        },
    }

    def build_job_description_prompt(self, title: str, department: str = "",
                                      employment_type: str = "Full-time",
                                      location: str = "",
                                      company: str = "",
                                      description: str = "") -> dict:
        prompt = self.JOB_DESCRIPTION_PROMPT.format(
            title=title, department=department or "Not specified",
            employment_type=employment_type, location=location or "Not specified",
            company=company or "Our company", description=description or title)
        return {"prompt": prompt, "title": title}

    def build_interview_prompt(self, title: str, description: str = "",
                                stage: str = "first_round") -> dict:
        prompt = self.INTERVIEW_PROMPT.format(
            title=title, description=description or title,
            stage=stage.replace("_", " "))
        return {"prompt": prompt, "title": title, "stage": stage}

    def get_onboarding_templates(self) -> dict:
        return self.ONBOARDING_TEMPLATES

    def get_onboarding_checklist(self, template: str = "general") -> dict:
        t = self.ONBOARDING_TEMPLATES.get(template, self.ONBOARDING_TEMPLATES["general"])
        return {"template": template, "name": t["name"], "items": t["items"],
                "total_items": len(t["items"])}


# ══════════════════════════════════════════════════════════════
# 9. CONTRACT TEMPLATES
# ══════════════════════════════════════════════════════════════

class ContractTemplateManager:
    """Pre-built contract templates with AI customization."""

    TEMPLATES = {
        "nda": {
            "name": "Non-Disclosure Agreement (NDA)",
            "description": "Mutual or one-way confidentiality agreement",
            "fields": ["party_1_name", "party_1_address", "party_2_name",
                       "party_2_address", "effective_date", "duration_months",
                       "governing_state"],
            "prompt": (
                "Generate a professional Non-Disclosure Agreement with these details:\n"
                "Party 1: {party_1_name} ({party_1_address})\n"
                "Party 2: {party_2_name} ({party_2_address})\n"
                "Type: {nda_type}\n"
                "Effective date: {effective_date}\n"
                "Duration: {duration_months} months\n"
                "Governing law: {governing_state}\n\n"
                "Include: Definition of confidential information, obligations, exclusions, "
                "term and termination, remedies, and signature blocks.\n"
                "End with: 'This document was generated by AI and is not legal advice. "
                "Have it reviewed by a qualified attorney before signing.'"
            ),
        },
        "freelancer_agreement": {
            "name": "Freelancer/Contractor Agreement",
            "description": "Independent contractor engagement terms",
            "fields": ["company_name", "contractor_name", "project_description",
                       "compensation", "start_date", "end_date", "governing_state"],
            "prompt": (
                "Generate a Freelancer/Independent Contractor Agreement:\n"
                "Company: {company_name}\n"
                "Contractor: {contractor_name}\n"
                "Project: {project_description}\n"
                "Compensation: {compensation}\n"
                "Period: {start_date} to {end_date}\n"
                "Governing law: {governing_state}\n\n"
                "Include: Scope of work, compensation and payment terms, "
                "independent contractor status (not employee), confidentiality, "
                "IP ownership (work-for-hire), termination, indemnification, "
                "and signature blocks.\n"
                "End with the legal advice disclaimer."
            ),
        },
        "sow": {
            "name": "Statement of Work (SOW)",
            "description": "Detailed project scope and deliverables",
            "fields": ["company_name", "client_name", "project_name",
                       "project_description", "deliverables", "timeline",
                       "budget"],
            "prompt": (
                "Generate a Statement of Work:\n"
                "Provider: {company_name}\n"
                "Client: {client_name}\n"
                "Project: {project_name}\n"
                "Description: {project_description}\n"
                "Deliverables: {deliverables}\n"
                "Timeline: {timeline}\n"
                "Budget: {budget}\n\n"
                "Include: Project overview, scope, deliverables table, "
                "timeline/milestones, budget breakdown, acceptance criteria, "
                "change request process, and signature blocks.\n"
                "End with the legal advice disclaimer."
            ),
        },
        "consulting_agreement": {
            "name": "Consulting Agreement",
            "description": "Professional consulting engagement terms",
            "fields": ["consultant_name", "client_name", "services_description",
                       "rate", "rate_type", "start_date", "governing_state"],
            "prompt": (
                "Generate a Consulting Agreement:\n"
                "Consultant: {consultant_name}\n"
                "Client: {client_name}\n"
                "Services: {services_description}\n"
                "Rate: {rate} ({rate_type})\n"
                "Start date: {start_date}\n"
                "Governing law: {governing_state}\n\n"
                "Include: Services description, compensation, expenses, "
                "term and termination, confidentiality, non-solicitation, "
                "limitation of liability, and signature blocks.\n"
                "End with the legal advice disclaimer."
            ),
        },
    }

    def get_templates(self) -> dict:
        return {k: {"name": v["name"], "description": v["description"],
                     "fields": v["fields"]}
                for k, v in self.TEMPLATES.items()}

    def get_template(self, template_id: str) -> dict:
        t = self.TEMPLATES.get(template_id)
        if not t:
            return {"error": f"Template not found. Options: {list(self.TEMPLATES.keys())}"}
        return {"id": template_id, **t}

    def build_prompt(self, template_id: str, field_values: dict) -> dict:
        """Fill in template fields and generate the AI prompt."""
        t = self.TEMPLATES.get(template_id)
        if not t:
            return {"error": "Template not found"}

        # Check required fields
        missing = [f for f in t["fields"] if not field_values.get(f)]
        if missing:
            return {"error": f"Missing required fields: {missing}", "fields": t["fields"]}

        try:
            prompt = t["prompt"].format(**field_values)
        except KeyError as e:
            prompt = t["prompt"]
            for k, v in field_values.items():
                prompt = prompt.replace(f"{{{k}}}", str(v))

        return {
            "template": template_id,
            "template_name": t["name"],
            "prompt": prompt,
            "fields_used": field_values,
            "disclaimer": "This document was generated by AI and is not legal advice. "
                         "Have it reviewed by a qualified attorney before signing.",
        }
