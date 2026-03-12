# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Email Service — Every notification the platform needs.

Providers (auto-detected from env vars):
  1. SendGrid (SENDGRID_API_KEY)
  2. Mailgun (MAILGUN_API_KEY + MAILGUN_DOMAIN)
  3. SMTP (SMTP_HOST + SMTP_PORT + SMTP_USER + SMTP_PASS)
  4. Console (fallback — logs to stdout for dev)

Templates:
  - Welcome / Signup confirmation
  - Password reset
  - MFA recovery
  - MFA enabled/disabled notification
  - Parental consent request
  - Compliance escalation alert
  - Sponsored tier approval/denial
  - Subscription confirmation
  - Subscription change/cancellation
  - Weekly usage digest
  - Platform announcement
"""

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

logger = logging.getLogger("MyTeam360.email")

# ── Brand colors for templates ──
BRAND = "#a459f2"
BRAND_DARK = "#7c3aed"
TEXT_DARK = "#1e293b"
TEXT_LIGHT = "#64748b"
BG = "#f8f9fb"


class EmailService:
    """Multi-provider email service with template system."""

    def __init__(self):
        self.provider = self._detect_provider()
        self.from_email = os.getenv("EMAIL_FROM", "noreply@myteam360.ai")
        self.from_name = os.getenv("EMAIL_FROM_NAME", "MyTeam360")

    def _detect_provider(self) -> str:
        if os.getenv("SENDGRID_API_KEY"):
            return "sendgrid"
        if os.getenv("MAILGUN_API_KEY"):
            return "mailgun"
        if os.getenv("SMTP_HOST"):
            return "smtp"
        return "console"

    def send(self, to: str, subject: str, html: str, text: str = "") -> dict:
        """Send an email. Routes to the configured provider."""
        if not to or not subject:
            return {"sent": False, "error": "Missing to or subject"}

        try:
            if self.provider == "sendgrid":
                return self._send_sendgrid(to, subject, html, text)
            elif self.provider == "mailgun":
                return self._send_mailgun(to, subject, html, text)
            elif self.provider == "smtp":
                return self._send_smtp(to, subject, html, text)
            else:
                return self._send_console(to, subject, html, text)
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return {"sent": False, "error": str(e)}

    def _send_sendgrid(self, to, subject, html, text) -> dict:
        import urllib.request
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self.from_email, "name": self.from_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text or "Please view this email in an HTML-capable client."},
                {"type": "text/html", "value": html},
            ],
        }
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {os.getenv('SENDGRID_API_KEY')}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:
            logger.info(f"SendGrid: sent to {to} — {resp.status}")
        return {"sent": True, "provider": "sendgrid"}

    def _send_mailgun(self, to, subject, html, text) -> dict:
        import urllib.request, urllib.parse, base64
        domain = os.getenv("MAILGUN_DOMAIN")
        api_key = os.getenv("MAILGUN_API_KEY")
        data = urllib.parse.urlencode({
            "from": f"{self.from_name} <{self.from_email}>",
            "to": to, "subject": subject, "html": html,
            "text": text or "Please view in HTML.",
        }).encode()
        auth = base64.b64encode(f"api:{api_key}".encode()).decode()
        req = urllib.request.Request(
            f"https://api.mailgun.net/v3/{domain}/messages",
            data=data,
            headers={"Authorization": f"Basic {auth}"},
        )
        with urllib.request.urlopen(req) as resp:
            logger.info(f"Mailgun: sent to {to} — {resp.status}")
        return {"sent": True, "provider": "mailgun"}

    def _send_smtp(self, to, subject, html, text) -> dict:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to
        msg["Subject"] = subject
        if text:
            msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER", "")
        passwd = os.getenv("SMTP_PASS", "")

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            if user:
                server.login(user, passwd)
            server.send_message(msg)
        logger.info(f"SMTP: sent to {to}")
        return {"sent": True, "provider": "smtp"}

    def _send_console(self, to, subject, html, text) -> dict:
        """Development fallback — log to console."""
        logger.info(f"\n{'='*50}\n📧 EMAIL (console mode)\nTo: {to}\nSubject: {subject}\n{'='*50}\n{text or '(HTML only)'}\n{'='*50}")
        return {"sent": True, "provider": "console", "dev_mode": True}


# ══════════════════════════════════════════════════════════════
# EMAIL TEMPLATES
# ══════════════════════════════════════════════════════════════

def _base_template(title: str, body_html: str) -> str:
    """Wrap content in the branded email template."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{BG}"><tr><td align="center" style="padding:40px 20px">
<table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden">
<tr><td style="padding:28px 32px 20px;border-bottom:1px solid #f1f5f9">
<div style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{BRAND};margin-right:8px;vertical-align:middle"></div>
<span style="font-size:16px;font-weight:700;color:{TEXT_DARK};vertical-align:middle">MyTeam360</span>
</td></tr>
<tr><td style="padding:32px">
<h1 style="margin:0 0 16px;font-size:22px;font-weight:700;color:{TEXT_DARK}">{title}</h1>
{body_html}
</td></tr>
<tr><td style="padding:20px 32px;background:#f8f9fb;border-top:1px solid #f1f5f9">
<p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.6">
This email was sent by MyTeam360, operated by MyTeam360 LLC.<br>
© 2026 Praxis Holdings LLC. All rights reserved.<br>
<a href="mailto:support@myteam360.ai" style="color:{BRAND};text-decoration:none">support@myteam360.ai</a>
</p></td></tr>
</table></td></tr></table></body></html>"""


def _button(text: str, url: str) -> str:
    return f"""<a href="{url}" style="display:inline-block;padding:12px 28px;background:{BRAND};color:#fff;
    font-size:14px;font-weight:600;text-decoration:none;border-radius:8px;margin:16px 0">{text}</a>"""


class EmailTemplates:
    """Pre-built email templates for every platform flow."""

    def __init__(self, email_service: EmailService, base_url: str = ""):
        self.email = email_service
        self.base_url = base_url or os.getenv("BASE_URL", "https://myteam360.ai")

    def send_welcome(self, to: str, name: str = "") -> dict:
        greeting = f"Hi {name}," if name else "Welcome,"
        html = _base_template("Welcome to MyTeam360", f"""
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">{greeting}</p>
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">Your AI team is ready. Here's how to get started:</p>
        <ol style="color:{TEXT_LIGHT};line-height:2;padding-left:20px;margin:0 0 16px">
            <li><strong style="color:{TEXT_DARK}">Tell us your role</strong> — the Smart Team Builder creates your ideal AI team</li>
            <li><strong style="color:{TEXT_DARK}">Add your API key</strong> — connect any of our 14 supported AI providers</li>
            <li><strong style="color:{TEXT_DARK}">Start a conversation</strong> — your Spaces are ready to work</li>
        </ol>
        {_button("Open MyTeam360", self.base_url + "/app")}
        """)
        return self.email.send(to, "Welcome to MyTeam360 — Your AI Team is Ready", html)

    def send_password_reset(self, to: str, reset_token: str, name: str = "") -> dict:
        url = f"{self.base_url}/auth/reset-password?token={reset_token}"
        html = _base_template("Reset Your Password", f"""
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            {"Hi " + name + "," if name else "Hi,"} we received a request to reset your password.
        </p>
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">Click the button below to create a new password. This link expires in 1 hour.</p>
        {_button("Reset Password", url)}
        <p style="color:#94a3b8;font-size:12px;margin:16px 0 0">If you didn't request this, you can safely ignore this email. Your password won't change.</p>
        """)
        return self.email.send(to, "Reset Your MyTeam360 Password", html)

    def send_mfa_recovery(self, to: str, recovery_token: str) -> dict:
        url = f"{self.base_url}/auth/mfa-recover?token={recovery_token}"
        html = _base_template("MFA Recovery", f"""
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            You requested to recover access to your account after losing your authenticator device.
        </p>
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            Click below to temporarily disable MFA and regain access. This link expires in 1 hour.
            <strong style="color:{TEXT_DARK}">You must re-enable MFA after logging in.</strong>
        </p>
        {_button("Recover Account", url)}
        <p style="color:#f87171;font-size:12px;margin:16px 0 0">⚠ If you did not request this, someone may be trying to access your account. Change your password immediately.</p>
        """)
        return self.email.send(to, "MyTeam360 MFA Recovery", html)

    def send_mfa_enabled(self, to: str, name: str = "") -> dict:
        html = _base_template("MFA Enabled", f"""
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            {"Hi " + name + "," if name else "Hi,"} multi-factor authentication has been enabled on your account.
        </p>
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            You'll now need your authenticator app when logging in. Keep your backup codes in a safe place.
        </p>
        <p style="color:#94a3b8;font-size:12px;margin:16px 0 0">If you didn't do this, your account may be compromised. Contact support@myteam360.ai immediately.</p>
        """)
        return self.email.send(to, "MFA Enabled on Your MyTeam360 Account", html)

    def send_compliance_escalation(self, to: str, category: str, severity: str,
                                    detail: str = "") -> dict:
        html = _base_template("Compliance Alert", f"""
        <div style="padding:12px 16px;background:{'#fef2f2' if severity == 'critical' else '#fffbeb'};
            border-left:4px solid {'#f87171' if severity == 'critical' else '#fbbf24'};
            border-radius:0 8px 8px 0;margin:0 0 16px">
            <p style="margin:0;font-size:12px;font-weight:700;color:{'#f87171' if severity == 'critical' else '#f59e0b'};
                text-transform:uppercase;letter-spacing:1px">{severity} — {category.replace('_',' ').title()}</p>
        </div>
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">{detail or 'A compliance flag has been triggered that requires your review.'}</p>
        {_button("Review in Dashboard", self.base_url + "/app#compliance")}
        """)
        return self.email.send(to, f"[{severity.upper()}] Compliance Alert — {category.replace('_',' ').title()}", html)

    def send_parental_consent_request(self, parent_email: str, child_name: str,
                                       consent_url: str) -> dict:
        html = _base_template("Parental Consent Request", f"""
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            <strong style="color:{TEXT_DARK}">{child_name}</strong> has requested to use MyTeam360,
            an AI-powered learning platform. Because they are under 18, we need your consent.
        </p>
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">MyTeam360 includes content guardrails,
            curriculum restrictions, and output filtering to ensure age-appropriate interactions.</p>
        {_button("Review & Consent", consent_url)}
        <p style="color:#94a3b8;font-size:12px;margin:16px 0 0">
            You can revoke consent at any time. Questions? Contact support@myteam360.ai.
        </p>
        """)
        return self.email.send(parent_email,
            f"Parental Consent Required — {child_name} wants to use MyTeam360", html)

    def send_subscription_confirmation(self, to: str, plan: str, amount: str,
                                        name: str = "") -> dict:
        html = _base_template("Subscription Confirmed", f"""
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            {"Hi " + name + "," if name else "Hi,"} your <strong style="color:{TEXT_DARK}">{plan}</strong> plan is active.
        </p>
        <div style="padding:16px;background:#f8f9fb;border-radius:8px;margin:0 0 16px">
            <p style="margin:0;font-size:13px;color:{TEXT_LIGHT}">Plan: <strong style="color:{TEXT_DARK}">{plan}</strong></p>
            <p style="margin:4px 0 0;font-size:13px;color:{TEXT_LIGHT}">Amount: <strong style="color:{TEXT_DARK}">{amount}</strong></p>
        </div>
        {_button("Go to Dashboard", self.base_url + "/app")}
        """)
        return self.email.send(to, f"MyTeam360 {plan} Plan — Subscription Confirmed", html)

    def send_sponsored_approval(self, to: str, name: str = "") -> dict:
        html = _base_template("Sponsored Access Approved", f"""
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            {"Hi " + name + "," if name else "Great news!"} Your application for sponsored access has been approved.
        </p>
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            You now have full access to MyTeam360, funded by a member of our community who
            believes AI should be accessible to everyone.
        </p>
        {_button("Start Using MyTeam360", self.base_url + "/app")}
        <p style="color:{BRAND};font-size:12px;margin:16px 0 0">💛 Someday, when you're able, consider paying it forward.</p>
        """)
        return self.email.send(to, "You've Been Approved — Welcome to MyTeam360", html)

    def send_weekly_digest(self, to: str, name: str = "", stats: dict = None) -> dict:
        s = stats or {}
        html = _base_template("Your Weekly Digest", f"""
        <p style="color:{TEXT_LIGHT};line-height:1.7;margin:0 0 16px">
            {"Hi " + name + "," if name else "Hi,"} here's your week in MyTeam360:
        </p>
        <div style="display:flex;gap:12px;margin:0 0 16px">
            <div style="flex:1;text-align:center;padding:16px;background:#f8f9fb;border-radius:8px">
                <div style="font-size:24px;font-weight:700;color:{BRAND}">{s.get('conversations',0)}</div>
                <div style="font-size:11px;color:{TEXT_LIGHT}">Conversations</div>
            </div>
            <div style="flex:1;text-align:center;padding:16px;background:#f8f9fb;border-radius:8px">
                <div style="font-size:24px;font-weight:700;color:{BRAND}">{s.get('messages',0)}</div>
                <div style="font-size:11px;color:{TEXT_LIGHT}">Messages</div>
            </div>
            <div style="flex:1;text-align:center;padding:16px;background:#f8f9fb;border-radius:8px">
                <div style="font-size:24px;font-weight:700;color:{BRAND}">${s.get('cost','0.00')}</div>
                <div style="font-size:11px;color:{TEXT_LIGHT}">AI Cost</div>
            </div>
        </div>
        {_button("Open Dashboard", self.base_url + "/app")}
        """)
        return self.email.send(to, "Your MyTeam360 Weekly Digest", html)
