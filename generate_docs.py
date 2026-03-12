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

#!/usr/bin/env python3
"""Generate branded Setup Guide + User Guide PDFs for MyTeam360."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, Frame
from reportlab.lib.units import cm

# Brand colors
PURPLE = HexColor("#a459f2")
DARK_BG = HexColor("#0a0a0f")
SURFACE = HexColor("#12121a")
BLUE = HexColor("#4d8eff")
GREEN = HexColor("#4ade80")
TEXT = HexColor("#333344")
TEXT_DIM = HexColor("#666688")
LIGHT_BG = HexColor("#f5f5fa")
BORDER = HexColor("#e0e0e8")

LOGO = os.path.join(os.path.dirname(__file__), "static", "logo.png")
W, H = letter

styles = getSampleStyleSheet()

# Custom styles
title_style = ParagraphStyle("DocTitle", parent=styles["Title"],
    fontSize=28, leading=34, textColor=PURPLE, spaceAfter=6, fontName="Helvetica-Bold")
subtitle_style = ParagraphStyle("DocSubtitle", parent=styles["Normal"],
    fontSize=14, leading=18, textColor=TEXT_DIM, spaceAfter=30)
h1 = ParagraphStyle("H1", parent=styles["Heading1"],
    fontSize=20, leading=24, textColor=PURPLE, spaceBefore=24, spaceAfter=12, fontName="Helvetica-Bold")
h2 = ParagraphStyle("H2", parent=styles["Heading2"],
    fontSize=15, leading=19, textColor=HexColor("#444466"), spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold")
h3 = ParagraphStyle("H3", parent=styles["Heading3"],
    fontSize=12, leading=16, textColor=PURPLE, spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold")
body = ParagraphStyle("Body", parent=styles["Normal"],
    fontSize=10.5, leading=15, textColor=TEXT, spaceAfter=8)
code_style = ParagraphStyle("Code", parent=styles["Code"],
    fontSize=9, leading=13, textColor=HexColor("#2d2d44"),
    backColor=LIGHT_BG, borderPadding=8, spaceBefore=6, spaceAfter=10, fontName="Courier")
note_style = ParagraphStyle("Note", parent=body,
    fontSize=10, leading=14, textColor=HexColor("#555577"),
    backColor=HexColor("#f0f0ff"), borderPadding=10, borderColor=PURPLE,
    borderWidth=1, borderRadius=4, spaceBefore=8, spaceAfter=12)
bullet_style = ParagraphStyle("Bullet", parent=body,
    fontSize=10.5, leading=15, leftIndent=20, bulletIndent=8, spaceBefore=2, spaceAfter=2)
table_header_style = ParagraphStyle("TableHeader", parent=body,
    fontSize=10, fontName="Helvetica-Bold", textColor=white)
table_cell_style = ParagraphStyle("TableCell", parent=body,
    fontSize=9.5, leading=13, textColor=TEXT)

def header_footer(canvas, doc):
    canvas.saveState()
    # Header line
    canvas.setStrokeColor(PURPLE)
    canvas.setLineWidth(1.5)
    canvas.line(0.75*inch, H - 0.55*inch, W - 0.75*inch, H - 0.55*inch)
    # Header logo
    try:
        canvas.drawImage(LOGO, 0.75*inch, H - 0.5*inch, width=20, height=20, preserveAspectRatio=True, mask='auto')
    except:
        pass
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_DIM)
    canvas.drawString(1.1*inch, H - 0.47*inch, "MyTeam360")
    canvas.drawRightString(W - 0.75*inch, H - 0.47*inch, doc.title if hasattr(doc, 'title') else "")
    # Footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(0.75*inch, 0.6*inch, W - 0.75*inch, 0.6*inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_DIM)
    canvas.drawString(0.75*inch, 0.42*inch, "MyTeam360 — AI-Powered Workplace Platform")
    canvas.drawRightString(W - 0.75*inch, 0.42*inch, f"Page {doc.page}")
    canvas.restoreState()

def make_cover(title, subtitle, version):
    """Generate a cover page."""
    elements = []
    elements.append(Spacer(1, 1.5*inch))
    try:
        elements.append(Image(LOGO, width=80, height=80))
    except:
        pass
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(title, ParagraphStyle("CoverTitle", parent=title_style,
        fontSize=36, leading=42, alignment=TA_CENTER)))
    elements.append(Spacer(1, 0.15*inch))
    elements.append(HRFlowable(width="40%", thickness=2, color=PURPLE, spaceAfter=12, spaceBefore=6))
    elements.append(Paragraph(subtitle, ParagraphStyle("CoverSub", parent=subtitle_style,
        alignment=TA_CENTER, fontSize=16)))
    elements.append(Spacer(1, 0.5*inch))
    cover_body = ParagraphStyle("CoverBody", parent=body, alignment=TA_CENTER, textColor=TEXT_DIM, fontSize=11)
    elements.append(Paragraph(f"Version {version}", cover_body))
    elements.append(Paragraph("March 2026", cover_body))
    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph("CONFIDENTIAL", ParagraphStyle("Conf", parent=body,
        alignment=TA_CENTER, fontSize=9, textColor=HexColor("#aa4444"))))
    elements.append(PageBreak())
    return elements

def make_table(headers, rows, col_widths=None):
    """Create a styled table."""
    header_row = [Paragraph(h, table_header_style) for h in headers]
    data = [header_row]
    for row in rows:
        data.append([Paragraph(str(c), table_cell_style) for c in row])
    if not col_widths:
        col_widths = [6.5*inch / len(headers)] * len(headers)
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PURPLE),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), white),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return t

def b(text):
    """Bullet point."""
    return Paragraph(f"• {text}", bullet_style)

# ══════════════════════════════════════════════════════════
# SETUP GUIDE
# ══════════════════════════════════════════════════════════

def build_setup_guide(path):
    doc = SimpleDocTemplate(path, pagesize=letter,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        title="Setup Guide")
    elements = []

    # Cover
    elements += make_cover("Setup Guide", "Installation, Configuration & First Run", "1.0")

    # TOC
    elements.append(Paragraph("Table of Contents", h1))
    toc_items = [
        "1. System Requirements",
        "2. Installation",
        "3. First Run & Initial Setup",
        "4. Setup Wizard Walkthrough",
        "5. Configuring AI Providers",
        "6. Security Configuration",
        "7. Branding & White-Label",
        "8. Network & Deployment Notes",
        "9. Troubleshooting",
    ]
    for item in toc_items:
        elements.append(Paragraph(item, ParagraphStyle("TOC", parent=body, leftIndent=20, fontSize=11, spaceBefore=4)))
    elements.append(PageBreak())

    # 1. SYSTEM REQUIREMENTS
    elements.append(Paragraph("1. System Requirements", h1))
    elements.append(Paragraph("MyTeam360 runs on any system with Python 3.10+. The platform is designed for local testing and small-team deployment.", body))
    elements.append(Spacer(1, 8))
    elements.append(make_table(
        ["Component", "Requirement", "Notes"],
        [
            ["Operating System", "macOS 12+, Linux, Windows 10+", "macOS recommended for native app"],
            ["Python", "3.10 or higher", "Check: python3 --version"],
            ["Node.js", "18+ (optional)", "Only for native Tauri app build"],
            ["Rust", "1.70+ (optional)", "Only for native Tauri app build"],
            ["RAM", "512 MB minimum", "1 GB recommended"],
            ["Disk Space", "50 MB + database", "Database grows with usage"],
            ["Browser", "Chrome, Safari, Firefox", "Chrome recommended for voice chat"],
        ],
        col_widths=[1.4*inch, 2*inch, 3.1*inch]
    ))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Python packages (installed automatically):", body))
    elements.append(b("flask — Web framework"))
    elements.append(b("cryptography — AES-256-GCM encryption for API keys at rest"))
    elements.append(b("qrcode — MFA QR code generation"))
    elements.append(b("requests — HTTP client for AI provider APIs"))

    # 2. INSTALLATION
    elements.append(PageBreak())
    elements.append(Paragraph("2. Installation", h1))

    elements.append(Paragraph("Step 1: Extract the Package", h2))
    elements.append(Paragraph("Unzip the MyTeam360 package to your preferred location:", body))
    elements.append(Paragraph("unzip myteam360-package.zip<br/>cd myteam360", code_style))

    elements.append(Paragraph("Step 2: Install Dependencies", h2))
    elements.append(Paragraph("pip3 install flask cryptography qrcode requests pillow --break-system-packages", code_style))
    elements.append(Paragraph("If you prefer a virtual environment (recommended for production):", body))
    elements.append(Paragraph("python3 -m venv venv<br/>source venv/bin/activate<br/>pip install flask cryptography qrcode requests pillow", code_style))

    elements.append(Paragraph("Step 3: Set Environment Variable", h2))
    elements.append(Paragraph("The server requires at least one AI provider key to be set. For testing without real API calls, use a dummy value:", body))
    elements.append(Paragraph("export ANTHROPIC_API_KEY=test", code_style))
    elements.append(Paragraph('<b>Important:</b> With a dummy key, the platform boots fully and all features work except actual AI chat responses. This is the recommended way to explore the platform without incurring API costs.', note_style))

    elements.append(Paragraph("Step 4: Start the Server", h2))
    elements.append(Paragraph("python3 app.py", code_style))
    elements.append(Paragraph("You should see:", body))
    elements.append(Paragraph("============================================================<br/>"
        "&nbsp;&nbsp;DEFAULT OWNER ACCOUNT CREATED<br/>"
        "&nbsp;&nbsp;Email:&nbsp;&nbsp;&nbsp;&nbsp;admin@localhost<br/>"
        "&nbsp;&nbsp;Password: admin123<br/>"
        "============================================================<br/>"
        "* Running on http://127.0.0.1:5000", code_style))

    elements.append(Paragraph("Step 5: Open in Browser", h2))
    elements.append(Paragraph("Navigate to <b>http://127.0.0.1:5000</b> in Chrome (recommended) or any modern browser.", body))

    # 3. FIRST RUN
    elements.append(PageBreak())
    elements.append(Paragraph("3. First Run &amp; Initial Setup", h1))

    elements.append(Paragraph("When you first open the platform, you'll go through three steps:", body))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("3.1 Login", h2))
    elements.append(Paragraph("Use the default credentials created during startup:", body))
    elements.append(b("Email: <b>admin@localhost</b>"))
    elements.append(b("Password: <b>admin123</b>"))
    elements.append(Paragraph('<b>Security Note:</b> Change this password immediately after first login via the API: PUT /api/me/password with your new password. The password policy requires 10+ characters, uppercase, lowercase, digit, and special character.', note_style))

    elements.append(Paragraph("3.2 Acceptable Use Policy", h2))
    elements.append(Paragraph("The platform presents an Acceptable Use Policy that must be accepted before access is granted. This is version-tracked — when policies are updated, users must re-accept.", body))

    elements.append(Paragraph("3.3 Setup Wizard", h2))
    elements.append(Paragraph("The setup wizard creates your organizational structure in one step. Run it via:", body))
    elements.append(Paragraph("POST /api/setup/complete", code_style))
    elements.append(Paragraph("This creates 8 departments and 18 specialized AI agents, each pre-configured with role-appropriate system prompts, AI models, and voice personalities.", body))

    # 4. SETUP WIZARD
    elements.append(PageBreak())
    elements.append(Paragraph("4. Setup Wizard Walkthrough", h1))
    elements.append(Paragraph("The wizard provisions these departments and agents:", body))
    elements.append(Spacer(1, 8))
    elements.append(make_table(
        ["Department", "Agents", "Voice Profiles"],
        [
            ["C-Suite / Executive", "Executive Strategist, Board Prep Assistant", "Onyx (deep), Echo (warm)"],
            ["Sales", "Sales Assistant, Proposal Writer, Competitive Intel", "Alloy, Fable, Echo"],
            ["Marketing", "Content Creator, Social Media Mgr, Campaign Strategist", "Shimmer, Nova, Alloy"],
            ["Finance", "Financial Analyst, Budget Planner", "Onyx (slow), Echo"],
            ["Legal", "Contract Reviewer, Compliance Advisor", "Fable (0.85x), Onyx"],
            ["HR", "HR Assistant, Onboarding Coordinator", "Nova, Shimmer"],
            ["IT / Engineering", "IT Support, Tech Writer", "Alloy, Echo"],
            ["Operations", "Operations Analyst, Project Manager", "Fable, Nova"],
        ],
        col_widths=[1.5*inch, 2.5*inch, 2.5*inch]
    ))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Each agent is configured with a specific AI model (Claude Sonnet 4.5 for most roles), temperature setting, and OpenAI TTS voice with speed tuned to the role personality.", body))

    # 5. AI PROVIDERS
    elements.append(PageBreak())
    elements.append(Paragraph("5. Configuring AI Providers", h1))
    elements.append(Paragraph("MyTeam360 supports multiple AI providers. Configure them via the API:", body))
    elements.append(Spacer(1, 8))
    elements.append(make_table(
        ["Provider", "Env Variable", "Get Key At"],
        [
            ["Anthropic (Claude)", "ANTHROPIC_API_KEY", "console.anthropic.com/settings/keys"],
            ["OpenAI (GPT)", "OPENAI_API_KEY", "platform.openai.com/api-keys"],
            ["xAI (Grok)", "XAI_API_KEY", "console.x.ai"],
            ["Azure OpenAI", "AZURE_OPENAI_KEY", "portal.azure.com"],
            ["Google AI", "GOOGLE_API_KEY", "aistudio.google.com"],
            ["Mistral", "MISTRAL_API_KEY", "console.mistral.ai"],
        ],
        col_widths=[1.8*inch, 2*inch, 2.7*inch]
    ))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("You can also configure keys through the API at runtime:", body))
    elements.append(Paragraph("POST /api/providers/auth<br/>"
        '{"provider": "anthropic", "auth_method": "api_key", "api_key": "sk-ant-..."}', code_style))
    elements.append(Paragraph('<b>Encryption:</b> All API keys are encrypted at rest using AES-256-GCM. The encryption key is auto-generated on first run and stored at data/.encryption_key with 600 permissions (owner-only read/write).', note_style))

    # 6. SECURITY
    elements.append(PageBreak())
    elements.append(Paragraph("6. Security Configuration", h1))

    elements.append(Paragraph("6.1 Password Policy", h2))
    elements.append(Paragraph("Default policy enforces:", body))
    elements.append(b("Minimum 10 characters with uppercase, lowercase, digit, and special character"))
    elements.append(b("Password history — prevents reuse of last 5 passwords"))
    elements.append(b("90-day expiration with configurable max age"))
    elements.append(b("Account lockout after 5 failed attempts (15-minute cooldown)"))
    elements.append(b("HaveIBeenPwned breach detection via k-anonymity"))

    elements.append(Paragraph("6.2 MFA / Two-Factor Authentication", h2))
    elements.append(Paragraph("TOTP-based MFA using any authenticator app (Google Authenticator, Authy, 1Password):", body))
    elements.append(Paragraph("POST /api/security/mfa/setup&nbsp;&nbsp;&nbsp;# Returns secret + QR code<br/>"
        "POST /api/security/mfa/verify-setup&nbsp;&nbsp;# Verify with 6-digit code", code_style))

    elements.append(Paragraph("6.3 DLP (Data Loss Prevention)", h2))
    elements.append(Paragraph("Automatically scans every chat message before it reaches the AI. Detects and blocks:", body))
    elements.append(b("Social Security Numbers — blocked"))
    elements.append(b("Credit card numbers — blocked"))
    elements.append(b("AWS access keys, private keys — blocked"))
    elements.append(b("API keys, passwords in text — warned"))
    elements.append(b("Phone numbers, email addresses — flagged"))

    elements.append(Paragraph("6.4 Encryption Key Rotation", h2))
    elements.append(Paragraph("Rotate the master encryption key (re-encrypts all sensitive fields):", body))
    elements.append(Paragraph("POST /api/security/encryption/rotate", code_style))

    # 7. BRANDING
    elements.append(PageBreak())
    elements.append(Paragraph("7. Branding &amp; White-Label", h1))
    elements.append(Paragraph("Customize the platform appearance for your organization:", body))
    elements.append(Paragraph('PUT /api/branding<br/>'
        '{"org_name": "Your Company",<br/>'
        '&nbsp;"primary_color": "#0066CC",<br/>'
        '&nbsp;"tagline": "Your Tagline",<br/>'
        '&nbsp;"login_title": "Welcome to Your Platform"}', code_style))
    elements.append(Paragraph("Available fields: org_name, tagline, primary_color, secondary_color, accent_color, bg_color, surface_color, text_color, logo_url, login_title, login_subtitle, footer_text, support_email, custom_css.", body))

    # 8. NETWORK
    elements.append(Paragraph("8. Network &amp; Deployment Notes", h1))
    elements.append(Paragraph('<b>Local testing (default):</b> Flask binds to 127.0.0.1:5000. Only your machine can access it. This is the safest option.', body))
    elements.append(Paragraph('<b>Do NOT</b> change the bind address to 0.0.0.0 unless you understand the implications — this exposes the server to your entire network with default credentials.', note_style))
    elements.append(Paragraph("For production deployment, you would need: a WSGI server (Gunicorn), HTTPS via reverse proxy (Nginx), a production database (PostgreSQL), and proper secrets management.", body))

    # 9. TROUBLESHOOTING
    elements.append(PageBreak())
    elements.append(Paragraph("9. Troubleshooting", h1))
    elements.append(make_table(
        ["Problem", "Solution"],
        [
            ["Server won't start", "Check Python version (3.10+). Install missing packages. Ensure ANTHROPIC_API_KEY is set (even 'test')."],
            ["Login fails immediately", "Delete data/myteam360.db and restart — a fresh database recreates the default admin account."],
            ["'Module not found' error", "Run: pip3 install flask cryptography qrcode requests --break-system-packages"],
            ["Voice chat mic not working", "Use Chrome. Grant mic permission when prompted. Check that no other app is using the mic."],
            ["MFA lockout", "Admin can disable MFA: POST /api/security/mfa/disable"],
            ["API keys not working", "Verify the key is valid at the provider's console. Check: GET /api/providers"],
            ["Database corruption", "Delete data/myteam360.db and restart. All data will be reset."],
            ["Port 5000 in use", "Another app is using port 5000. Kill it or set: export FLASK_RUN_PORT=5001"],
        ],
        col_widths=[2*inch, 4.5*inch]
    ))

    doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"  Setup Guide: {path}")


# ══════════════════════════════════════════════════════════
# USER GUIDE
# ══════════════════════════════════════════════════════════

def build_user_guide(path):
    doc = SimpleDocTemplate(path, pagesize=letter,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        title="User Guide")
    elements = []

    # Cover
    elements += make_cover("User Guide", "Complete Feature Reference & Workflows", "1.0")

    # TOC
    elements.append(Paragraph("Table of Contents", h1))
    toc = [
        "1. Platform Overview",
        "2. Getting Started",
        "3. Working with AI Agents",
        "4. Voice Chat",
        "5. Prompt Templates",
        "6. Conversations & Export",
        "7. Analytics & Recommendations",
        "8. Usage Quotas & Spend Tracking",
        "9. Security Features",
        "10. Administration",
        "11. API Reference (Key Endpoints)",
    ]
    for item in toc:
        elements.append(Paragraph(item, ParagraphStyle("TOC", parent=body, leftIndent=20, fontSize=11, spaceBefore=4)))
    elements.append(PageBreak())

    # 1. OVERVIEW
    elements.append(Paragraph("1. Platform Overview", h1))
    elements.append(Paragraph("MyTeam360 is an AI-powered workplace platform that gives every department its own specialized AI agents. Instead of one generic chatbot, your organization gets purpose-built assistants for Sales, Legal, Finance, Marketing, HR, IT, Operations, and Executive teams.", body))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Key capabilities:", h3))
    elements.append(b("<b>18 pre-built AI agents</b> across 8 departments, each with role-specific prompts and models"))
    elements.append(b("<b>Voice chat</b> with unique voice personalities per agent (OpenAI-style pulsing orb interface)"))
    elements.append(b("<b>6 AI providers</b> supported — Anthropic, OpenAI, xAI, Azure, Google, Mistral"))
    elements.append(b("<b>Enterprise security</b> — encryption at rest, MFA, DLP scanning, password policies, audit logging"))
    elements.append(b("<b>Smart recommendations</b> — the platform analyzes usage and suggests optimizations"))
    elements.append(b("<b>Usage quotas</b> — per-user, per-department, and org-wide token and cost limits"))
    elements.append(b("<b>White-label branding</b> — customize name, colors, logo for your organization"))
    elements.append(b("<b>Conversation export</b> — CSV, JSON, Markdown for compliance and record-keeping"))
    elements.append(b("<b>Prompt template library</b> — reusable templates with variable substitution"))
    elements.append(Spacer(1, 8))
    elements.append(make_table(
        ["Metric", "Count"],
        [
            ["Total code lines", "14,179"],
            ["API endpoints", "213"],
            ["Database tables", "58"],
            ["Core modules", "22"],
            ["AI providers", "6"],
            ["Recommendation patterns", "6"],
        ],
        col_widths=[3.25*inch, 3.25*inch]
    ))

    # 2. GETTING STARTED
    elements.append(PageBreak())
    elements.append(Paragraph("2. Getting Started", h1))

    elements.append(Paragraph("2.1 Logging In", h2))
    elements.append(Paragraph("Open <b>http://127.0.0.1:5000</b> in your browser. Enter your email and password. First-time users will be prompted to accept the Acceptable Use Policy before accessing any features.", body))

    elements.append(Paragraph("2.2 Understanding Roles", h2))
    elements.append(make_table(
        ["Role", "Can Do"],
        [
            ["Owner", "Everything — full admin plus billing, branding, provider keys, user management"],
            ["Admin", "Manage agents, departments, quotas, view analytics, security settings"],
            ["Manager", "Use agents, view department analytics, manage team templates"],
            ["Member", "Use assigned agents, create personal templates, view own usage"],
        ],
        col_widths=[1.3*inch, 5.2*inch]
    ))

    elements.append(Paragraph("2.3 Navigation", h2))
    elements.append(Paragraph("The platform is API-first with a web dashboard. Key pages:", body))
    elements.append(b("<b>/</b> — Main dashboard and chat interface"))
    elements.append(b("<b>/voice-chat</b> — Voice conversation interface with agent selection"))

    # 3. AGENTS
    elements.append(PageBreak())
    elements.append(Paragraph("3. Working with AI Agents", h1))
    elements.append(Paragraph("Agents are specialized AI assistants. Each one has a unique personality, model, temperature, system prompt, and voice.", body))

    elements.append(Paragraph("3.1 Chatting with an Agent", h2))
    elements.append(Paragraph("Select an agent and send a message. The platform routes your message to the agent's configured AI provider and returns the response.", body))
    elements.append(Paragraph("POST /api/chat<br/>"
        '{"message": "Draft a follow-up email for the TechCorp meeting",<br/>'
        '&nbsp;"agent_id": "agent_abc123"}', code_style))

    elements.append(Paragraph("3.2 Agent Intelligence", h2))
    elements.append(Paragraph("Agents can be configured with:", body))
    elements.append(b("<b>System instructions</b> — defines the agent's role and behavior"))
    elements.append(b("<b>Additional context</b> — company-specific information the agent should know"))
    elements.append(b("<b>Knowledge base</b> — uploaded documents the agent can reference"))
    elements.append(b("<b>Temperature</b> — controls creativity (0.0 = precise, 1.0 = creative)"))
    elements.append(b("<b>Delegation</b> — agents can route to other specialized agents"))

    elements.append(Paragraph("3.3 Intelligent Routing", h2))
    elements.append(Paragraph("Send a message without specifying an agent, and the platform automatically classifies the intent and routes to the best-fit agent:", body))
    elements.append(Paragraph("POST /api/routing/classify<br/>"
        '{"message": "Review this NDA for red flags"}', code_style))
    elements.append(Paragraph("The router would classify this as a Legal task and suggest the Contract Reviewer agent.", body))

    # 4. VOICE CHAT
    elements.append(PageBreak())
    elements.append(Paragraph("4. Voice Chat", h1))
    elements.append(Paragraph("The voice chat interface provides a hands-free conversation experience with any agent, featuring a visual design inspired by premium voice AI products.", body))

    elements.append(Paragraph("4.1 The Interface", h2))
    elements.append(b("<b>Central orb</b> — tap to start/stop. Color changes by state: purple (listening), blue (speaking), orange (thinking), red (error)"))
    elements.append(b("<b>Agent selector</b> — dropdown at top to switch agents mid-conversation"))
    elements.append(b("<b>Transcript</b> — scrolling chat log at bottom shows what was said"))
    elements.append(b("<b>Settings panel</b> — gear icon opens TTS provider, voice, speed, and language controls"))

    elements.append(Paragraph("4.2 Voice Flow", h2))
    elements.append(Paragraph("1. Tap the orb — mic activates, orb pulses purple with expanding rings<br/>"
        "2. Speak your question — real-time transcription appears as you talk<br/>"
        "3. Pause speaking — after silence threshold (default 1.5s), message auto-sends<br/>"
        "4. Orb turns orange — AI is thinking<br/>"
        "5. Orb turns blue — response plays through TTS with audio visualization<br/>"
        "6. Returns to listening — continuous conversation loop<br/>"
        "7. Tap again to stop", body))

    elements.append(Paragraph("4.3 Per-Agent Voices", h2))
    elements.append(Paragraph("Each agent has a distinct voice personality. When you switch agents, the voice changes automatically. Admins can customize any agent's voice:", body))
    elements.append(Paragraph("PUT /api/agents/{agent_id}/voice<br/>"
        '{"voice_provider": "openai", "voice_id": "shimmer",<br/>'
        '&nbsp;"voice_model": "tts-1", "voice_speed": 1.1}', code_style))

    elements.append(Paragraph("4.4 Supported TTS Providers", h2))
    elements.append(make_table(
        ["Provider", "Voices", "Notes"],
        [
            ["Browser Native", "System voices", "Free, no API key needed, basic quality"],
            ["OpenAI TTS", "Alloy, Echo, Fable, Onyx, Nova, Shimmer", "Best quality, ~$15/M chars"],
            ["ElevenLabs", "Rachel, Domi, Bella, Antoni +5 more", "Most natural, ~$30/M chars"],
            ["Google Cloud", "US/UK Neural2 voices", "Good quality, ~$16/M chars"],
        ],
        col_widths=[1.5*inch, 2.5*inch, 2.5*inch]
    ))

    # 5. TEMPLATES
    elements.append(PageBreak())
    elements.append(Paragraph("5. Prompt Templates", h1))
    elements.append(Paragraph("Templates are reusable prompt patterns with variable placeholders. Create them once, use them across the team.", body))

    elements.append(Paragraph("5.1 Creating a Template", h2))
    elements.append(Paragraph("POST /api/templates<br/>"
        '{"name": "Client Follow-Up",<br/>'
        '&nbsp;"category": "sales",<br/>'
        '&nbsp;"content": "Write a follow-up email to {{client}} at {{company}} about {{topic}}",<br/>'
        '&nbsp;"variables": ["client", "company", "topic"],<br/>'
        '&nbsp;"is_shared": true}', code_style))

    elements.append(Paragraph("5.2 Using a Template", h2))
    elements.append(Paragraph("POST /api/templates/{id}/use<br/>"
        '{"variables": {"client": "Sarah", "company": "TechCorp", "topic": "fleet automation"}}', code_style))
    elements.append(Paragraph("Returns the rendered prompt with all variables replaced, ready to send to an agent.", body))

    # 6. CONVERSATIONS
    elements.append(Paragraph("6. Conversations &amp; Export", h1))
    elements.append(Paragraph("All conversations are stored and can be exported for compliance, handoff, or analysis.", body))

    elements.append(Paragraph("6.1 Export Formats", h2))
    elements.append(b("<b>CSV</b> — spreadsheet-ready with timestamp, role, content, agent, model columns"))
    elements.append(b("<b>JSON</b> — full structured data including metadata"))
    elements.append(b("<b>Markdown</b> — human-readable formatted transcript"))
    elements.append(Paragraph("GET /api/conversations/{id}/export/csv<br/>"
        "GET /api/conversations/{id}/export/json<br/>"
        "GET /api/conversations/{id}/export/markdown", code_style))

    elements.append(Paragraph("6.2 Bulk Export (GDPR)", h2))
    elements.append(Paragraph("Export all your conversations at once for data portability:", body))
    elements.append(Paragraph("GET /api/conversations/export-all?format=json", code_style))

    # 7. ANALYTICS
    elements.append(PageBreak())
    elements.append(Paragraph("7. Analytics &amp; Recommendations", h1))

    elements.append(Paragraph("7.1 Smart Recommendations", h2))
    elements.append(Paragraph("The platform continuously analyzes usage patterns and generates actionable recommendations across 6 patterns:", body))
    elements.append(Spacer(1, 6))
    elements.append(make_table(
        ["Pattern", "What It Detects", "Example Action"],
        [
            ["Heavy User", "Users with 50+ messages, no dedicated agent", "Create a personalized agent"],
            ["Department Gap", "Departments with no agents assigned", "Deploy a department agent"],
            ["Underperforming Agent", ">50% negative ratings", "Improve prompt or switch model"],
            ["Cost Optimization", "Expensive model for simple tasks", "Switch to cheaper model (60% savings)"],
            ["Topic Gap", "Recurring topics with no specialist", "Create a specialist agent"],
            ["Cross-Department", "Agent popular outside its department", "Grant formal department access"],
        ],
        col_widths=[1.3*inch, 2.2*inch, 3*inch]
    ))

    elements.append(Paragraph("7.2 Reviewing Recommendations", h2))
    elements.append(Paragraph("POST /api/recommendations/generate&nbsp;&nbsp;# Scan for new recommendations<br/>"
        "GET /api/recommendations&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# List all<br/>"
        "POST /api/recommendations/{id}/review&nbsp;&nbsp;# Approve or dismiss", code_style))

    # 8. QUOTAS
    elements.append(Paragraph("8. Usage Quotas &amp; Spend Tracking", h1))
    elements.append(Paragraph("Control AI spending at three levels:", body))
    elements.append(b("<b>Organization</b> — total monthly token and cost cap"))
    elements.append(b("<b>Department</b> — per-department limits"))
    elements.append(b("<b>User</b> — per-user limits"))
    elements.append(Paragraph("When a user hits their quota, chat messages are blocked with a clear error. Warnings are issued at 80% usage.", body))
    elements.append(Paragraph("PUT /api/quotas<br/>"
        '{"org_monthly_tokens": 10000000, "org_monthly_cost": 500.00}<br/><br/>'
        "PUT /api/quotas/user/{user_id}<br/>"
        '{"monthly_tokens": 1000000, "monthly_cost": 50.00}<br/><br/>'
        "GET /api/quotas/check&nbsp;&nbsp;# Check your current status", code_style))

    # 9. SECURITY
    elements.append(PageBreak())
    elements.append(Paragraph("9. Security Features", h1))

    elements.append(Paragraph("9.1 Overview", h2))
    elements.append(Paragraph("MyTeam360 includes enterprise-grade security out of the box:", body))
    elements.append(make_table(
        ["Feature", "Description"],
        [
            ["Encryption at Rest", "All API keys and secrets encrypted with AES-256-GCM"],
            ["MFA/TOTP", "Authenticator app support with QR provisioning"],
            ["Password Policies", "Complexity, expiry, history, breach detection, lockout"],
            ["DLP Scanning", "Real-time PII detection on every chat message"],
            ["Audit Logging", "Complete trail of all security events"],
            ["Rate Limiting", "Configurable per-endpoint request limits"],
            ["Session Management", "Idle timeout, max sessions, device tracking"],
            ["IP Allowlisting", "Restrict access to approved IP ranges"],
            ["AUP Enforcement", "Version-tracked acceptable use policy"],
        ],
        col_widths=[1.8*inch, 4.7*inch]
    ))

    elements.append(Paragraph("9.2 Security Dashboard", h2))
    elements.append(Paragraph("A single endpoint provides a full security status overview:", body))
    elements.append(Paragraph("GET /api/security/dashboard", code_style))
    elements.append(Paragraph("Returns: password policy settings, session policy, MFA coverage percentage, DLP detections in last 24 hours, encryption status, active sessions count.", body))

    # 10. ADMIN
    elements.append(PageBreak())
    elements.append(Paragraph("10. Administration", h1))

    elements.append(Paragraph("10.1 User Management", h2))
    elements.append(Paragraph("POST /api/auth/invite&nbsp;&nbsp;&nbsp;# Invite a new user<br/>"
        "GET /api/users&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# List all users<br/>"
        "PUT /api/users/{id}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Update role, deactivate", code_style))

    elements.append(Paragraph("10.2 Department Management", h2))
    elements.append(Paragraph("POST /api/departments&nbsp;&nbsp;&nbsp;# Create department<br/>"
        "PUT /api/departments/{id}&nbsp;# Update<br/>"
        "POST /api/departments/{id}/members&nbsp;# Add members", code_style))

    elements.append(Paragraph("10.3 Data Retention", h2))
    elements.append(Paragraph("Configure automatic data cleanup policies:", body))
    elements.append(Paragraph("GET /api/retention&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# View current policies<br/>"
        "PUT /api/retention&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;# Update retention periods", code_style))

    elements.append(Paragraph("10.4 Audit Log", h2))
    elements.append(Paragraph("Every significant action is logged:", body))
    elements.append(Paragraph("GET /api/admin/audit?limit=50&nbsp;&nbsp;# Recent audit events<br/>"
        "GET /api/admin/audit/export&nbsp;&nbsp;&nbsp;&nbsp;# Export full audit trail", code_style))

    # 11. API REFERENCE
    elements.append(PageBreak())
    elements.append(Paragraph("11. API Reference (Key Endpoints)", h1))
    elements.append(Paragraph("All endpoints require <b>Authorization: Bearer {token}</b> header unless noted.", body))
    elements.append(Spacer(1, 8))

    api_sections = [
        ("Auth", [
            ("POST /api/auth/login", "Login, returns JWT token"),
            ("POST /api/auth/invite", "Invite user (admin)"),
            ("PUT /api/me/password", "Change own password"),
        ]),
        ("Chat", [
            ("POST /api/chat", "Send message to agent"),
            ("POST /api/routing/classify", "Auto-route to best agent"),
            ("GET /api/conversations", "List conversations"),
        ]),
        ("Agents", [
            ("GET /api/agents", "List all agents"),
            ("POST /api/agents", "Create agent (admin)"),
            ("GET /api/agents/{id}/voice", "Get agent voice config"),
            ("PUT /api/agents/{id}/voice", "Set agent voice (admin)"),
        ]),
        ("Voice", [
            ("GET /api/voice/providers", "List TTS providers"),
            ("GET /api/voice/settings", "Get voice preferences"),
            ("PUT /api/voice/settings", "Update voice preferences"),
            ("POST /api/voice/synthesize", "Text-to-speech"),
        ]),
        ("Security", [
            ("GET /api/security/dashboard", "Full security overview"),
            ("POST /api/security/mfa/setup", "Start MFA enrollment"),
            ("POST /api/security/dlp/scan", "Scan text for PII"),
            ("POST /api/security/encryption/rotate", "Rotate encryption key"),
        ]),
        ("Analytics", [
            ("POST /api/recommendations/generate", "Generate recommendations"),
            ("GET /api/spend/dashboard", "Spending overview"),
            ("GET /api/quotas/check", "Check quota status"),
        ]),
    ]

    for section_name, endpoints in api_sections:
        elements.append(Paragraph(section_name, h3))
        elements.append(make_table(
            ["Endpoint", "Description"],
            [[e[0], e[1]] for e in endpoints],
            col_widths=[3.2*inch, 3.3*inch]
        ))
        elements.append(Spacer(1, 6))

    doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"  User Guide: {path}")


# ══════════════════════════════════════════════════════════
# BUILD ALL
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)
    print("Generating branded PDFs...")
    build_setup_guide("docs/MyTeam360_Setup_Guide.pdf")
    build_user_guide("docs/MyTeam360_User_Guide.pdf")
    print("Done!")
