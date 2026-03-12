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
MyTeam360 — Stripe Billing Integration
Handles subscriptions, trials, and payment gating.

Architecture:
  - We store: user_id, stripe_customer_id, subscription_status, period_end
  - We never store: card numbers, payment details, usage data
  - Stripe handles: checkout UI, card processing, receipts, cancellations

Setup:
  1. Create Stripe account: https://dashboard.stripe.com
  2. Get API keys from: https://dashboard.stripe.com/apikeys
  3. Create two Price objects in Stripe dashboard:
     - Monthly: $15/mo recurring
     - Annual: $129/yr recurring
  4. Set env vars: STRIPE_SECRET_KEY, STRIPE_PRICE_MONTHLY, STRIPE_PRICE_ANNUAL
  5. Set up webhook endpoint in Stripe dashboard:
     URL: https://myteam360.ai/api/billing/webhook
     Events: checkout.session.completed, customer.subscription.updated,
             customer.subscription.deleted, invoice.payment_failed
  6. Set STRIPE_WEBHOOK_SECRET env var
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from flask import request, jsonify, redirect, g, Response

logger = logging.getLogger("Billing")

# Lazy import — stripe may not be installed during dev
stripe = None

def _ensure_stripe():
    global stripe
    if stripe is None:
        try:
            import stripe as _stripe
            _stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            stripe = _stripe
        except ImportError:
            logger.warning("stripe package not installed. Run: pip install stripe")
            return False
    return bool(stripe.api_key)


# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════

BILLING_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT PRIMARY KEY,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    status TEXT DEFAULT 'none',
    plan TEXT DEFAULT 'none',
    trial_end TIMESTAMP,
    period_end TIMESTAMP,
    tos_accepted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS consent_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    consent_type TEXT NOT NULL,
    consent_version TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    consent_text TEXT NOT NULL,
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT NOT NULL,
    pref_key TEXT NOT NULL,
    pref_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, pref_key)
);
"""

BILLING_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT PRIMARY KEY,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    status TEXT DEFAULT 'none',
    plan TEXT DEFAULT 'none',
    trial_end TIMESTAMP,
    period_end TIMESTAMP,
    tos_accepted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS consent_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    consent_type TEXT NOT NULL,
    consent_version TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    consent_text TEXT NOT NULL,
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT NOT NULL,
    pref_key TEXT NOT NULL,
    pref_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, pref_key)
);
"""

def _init_billing_db(db):
    """Create billing tables if they don't exist."""
    from .database import _USE_POSTGRES
    db.executescript(BILLING_SCHEMA_PG if _USE_POSTGRES else BILLING_SCHEMA_SQLITE)


def _get_sub(db, user_id):
    """Get subscription record, creating one if needed."""
    _init_billing_db(db)
    row = db.execute("SELECT * FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
    if row:
        return dict(row)
    # Create default record
    db.execute("INSERT INTO subscriptions (user_id) VALUES (?)", (user_id,))
    return {"user_id": user_id, "status": "none", "plan": "none",
            "stripe_customer_id": None, "stripe_subscription_id": None,
            "trial_end": None, "period_end": None, "tos_accepted_at": None}


# ═══════════════════════════════════════════════════════════════
# SUBSCRIPTION LOGIC
# ═══════════════════════════════════════════════════════════════

TRIAL_DAYS = 3

def check_access(db, user_id):
    """
    Returns dict with:
      - has_access: bool
      - reason: 'active' | 'trialing' | 'expired' | 'no_subscription' | 'no_tos'
      - sub: full subscription record
      - days_remaining: int (for trial)
    """
    sub = _get_sub(db, user_id)

    # Must accept TOS first
    if not sub.get("tos_accepted_at"):
        return {"has_access": False, "reason": "no_tos", "sub": sub}

    status = sub.get("status", "none")

    # Active paid subscription
    if status == "active":
        return {"has_access": True, "reason": "active", "sub": sub}

    # Trial period
    if status == "trialing":
        trial_end = sub.get("trial_end")
        if trial_end:
            if isinstance(trial_end, str):
                trial_end = datetime.fromisoformat(trial_end)
            if datetime.utcnow() < trial_end:
                days_left = (trial_end - datetime.utcnow()).days + 1
                return {"has_access": True, "reason": "trialing", "sub": sub,
                        "days_remaining": max(1, days_left)}
        # Trial expired
        return {"has_access": False, "reason": "expired", "sub": sub}

    # Past due — give grace period
    if status == "past_due":
        return {"has_access": True, "reason": "past_due", "sub": sub}

    # No subscription or canceled
    return {"has_access": False, "reason": "no_subscription", "sub": sub}


def start_trial(db, user_id):
    """Start the 3-day free trial."""
    sub = _get_sub(db, user_id)
    if sub["status"] != "none":
        return sub  # Already has a subscription or trial

    trial_end = datetime.utcnow() + timedelta(days=TRIAL_DAYS)
    db.execute("""
        UPDATE subscriptions SET status='trialing', plan='trial',
        trial_end=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?
    """, (trial_end.isoformat(), user_id))

    logger.info(f"Trial started for {user_id}, ends {trial_end.isoformat()}")
    return {**sub, "status": "trialing", "plan": "trial", "trial_end": trial_end.isoformat()}


def accept_tos(db, user_id, ip_address=None, user_agent=None):
    """Record TOS acceptance with forensic proof."""
    _init_billing_db(db)
    sub = _get_sub(db, user_id)
    now = datetime.utcnow().isoformat()
    db.execute("""
        UPDATE subscriptions SET tos_accepted_at=?, updated_at=CURRENT_TIMESTAMP
        WHERE user_id=?
    """, (now, user_id))
    return {**sub, "tos_accepted_at": now}


# Current consent versions — bump these when terms change
TOS_VERSION = "2026.03.1"
COST_ACK_VERSION = "2026.03.1"

# The exact text they agree to — stored with consent record
TOS_CONSENT_TEXT = (
    "I have read and agree to the MyTeam360 Terms of Service (v{version}). "
    "I understand that MyTeam360 provides a platform interface and does not generate AI responses. "
    "MyTeam360 stores only my email, display name, user ID, subscription status, and Stripe customer ID."
)

COST_CONSENT_TEXT = (
    "I understand that AI provider costs (Anthropic, OpenAI, xAI, Google, etc.) are billed directly "
    "to me by the provider based on my usage. These costs are separate from my MyTeam360 subscription "
    "and are entirely my responsibility. Costs vary significantly by model and usage volume, and heavy "
    "usage can result in charges of $50-$500+ per month or more. The spend dashboard in MyTeam360 "
    "provides estimates only — actual charges are determined by my AI provider. MyTeam360 is not "
    "responsible for any API provider charges under any circumstances."
)


def log_consent(db, user_id, consent_type, consent_version, consent_text,
                ip_address=None, user_agent=None):
    """Record a consent event with full proof chain."""
    _init_billing_db(db)
    db.execute("""
        INSERT INTO consent_log (user_id, consent_type, consent_version,
                                 ip_address, user_agent, consent_text)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, consent_type, consent_version,
          ip_address or "unknown", user_agent or "unknown", consent_text))

    logger.info(f"Consent logged: {user_id} → {consent_type} v{consent_version} from {ip_address}")


def get_consent_records(db, user_id=None, consent_type=None):
    """Retrieve consent records for audit/export."""
    _init_billing_db(db)
    where, params = [], []
    if user_id:
        where.append("user_id=?"); params.append(user_id)
    if consent_type:
        where.append("consent_type=?"); params.append(consent_type)

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = db.execute(f"""
        SELECT * FROM consent_log {clause} ORDER BY accepted_at DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def check_consent(db, user_id, consent_type, required_version):
    """Check if user has accepted the required version of a consent."""
    _init_billing_db(db)
    row = db.execute("""
        SELECT * FROM consent_log
        WHERE user_id=? AND consent_type=? AND consent_version=?
        ORDER BY accepted_at DESC LIMIT 1
    """, (user_id, consent_type, required_version)).fetchone()
    return dict(row) if row else None


def set_user_pref(db, user_id, key, value):
    """Set a user preference."""
    _init_billing_db(db)
    db.execute("""
        INSERT OR REPLACE INTO user_preferences (user_id, pref_key, pref_value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    """, (user_id, key, value))


def get_user_pref(db, user_id, key, default=None):
    """Get a user preference."""
    _init_billing_db(db)
    row = db.execute(
        "SELECT pref_value FROM user_preferences WHERE user_id=? AND pref_key=?",
        (user_id, key)).fetchone()
    return row["pref_value"] if row else default


# ═══════════════════════════════════════════════════════════════
# STRIPE CHECKOUT
# ═══════════════════════════════════════════════════════════════

def create_checkout_session(db, user_id, user_email, plan="pro", billing="monthly"):
    """Create a Stripe Checkout session for a specific plan.

    Plans: starter, student, pro, business
    Billing: monthly, annual

    Env vars: STRIPE_PRICE_{PLAN}_{BILLING}
    Example: STRIPE_PRICE_PRO_MONTHLY=price_xxxxx
    """
    if not _ensure_stripe():
        return {"error": "Stripe not configured"}

    # Map plan + billing to Stripe price ID
    PRICE_MAP = {
        "starter_monthly": os.getenv("STRIPE_PRICE_STARTER_MONTHLY", ""),
        "starter_annual": os.getenv("STRIPE_PRICE_STARTER_ANNUAL", ""),
        "student_monthly": os.getenv("STRIPE_PRICE_STUDENT_MONTHLY", ""),
        "student_annual": os.getenv("STRIPE_PRICE_STUDENT_ANNUAL", ""),
        "pro_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY", ""),
        "pro_annual": os.getenv("STRIPE_PRICE_PRO_ANNUAL", ""),
        "business_monthly": os.getenv("STRIPE_PRICE_BUSINESS_MONTHLY", ""),
        "business_annual": os.getenv("STRIPE_PRICE_BUSINESS_ANNUAL", ""),
    }

    # Backward compat: old env vars
    if not PRICE_MAP.get(f"{plan}_{billing}"):
        if billing == "monthly" and os.getenv("STRIPE_PRICE_MONTHLY"):
            PRICE_MAP[f"{plan}_{billing}"] = os.getenv("STRIPE_PRICE_MONTHLY")
        elif billing == "annual" and os.getenv("STRIPE_PRICE_ANNUAL"):
            PRICE_MAP[f"{plan}_{billing}"] = os.getenv("STRIPE_PRICE_ANNUAL")

    price_id = PRICE_MAP.get(f"{plan}_{billing}")
    if not price_id:
        return {"error": f"Stripe price ID not configured for {plan}/{billing}. "
                         f"Set STRIPE_PRICE_{plan.upper()}_{billing.upper()} env var."}

    if plan == "enterprise":
        return {"error": "Enterprise plans require contacting sales.", "contact": "sales@myteam360.ai"}

    sub = _get_sub(db, user_id)
    app_url = os.getenv("BASE_URL", os.getenv("APP_URL", "https://myteam360.ai")).rstrip("/")

    try:
        # Find or create Stripe customer
        customer_id = sub.get("stripe_customer_id")
        if not customer_id:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={"user_id": user_id, "plan": plan}
            )
            customer_id = customer.id
            db.execute("UPDATE subscriptions SET stripe_customer_id=? WHERE user_id=?",
                       (customer_id, user_id))

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{app_url}/app?billing=success&plan={plan}",
            cancel_url=f"{app_url}/app?billing=cancel",
            metadata={"user_id": user_id, "plan": plan, "billing": billing},
            allow_promotion_codes=True,
        )

        return {"url": session.url, "session_id": session.id, "plan": plan, "billing": billing}

    except Exception as e:
        logger.error(f"Checkout error: {e}")
        return {"error": "Unable to create checkout session. Please try again."}


def create_portal_session(db, user_id):
    """Create a Stripe Customer Portal session for managing subscription."""
    if not _ensure_stripe():
        return {"error": "Stripe not configured"}

    sub = _get_sub(db, user_id)
    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        return {"error": "No billing account found"}

    app_url = os.getenv("APP_URL", "https://myteam360.ai").rstrip("/")

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{app_url}/app",
        )
        return {"url": session.url}
    except Exception as e:
        logger.error(f"Portal error: {e}")
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# STRIPE WEBHOOK
# ═══════════════════════════════════════════════════════════════

def handle_webhook(payload, sig_header, db):
    """Process Stripe webhook events."""
    if not _ensure_stripe():
        return {"error": "Stripe not configured"}, 500

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload)
    except Exception as e:
        logger.error(f"Webhook verification failed: {e}")
        return {"error": "Invalid signature"}, 400

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info(f"Webhook: {event_type}")

    if event_type == "checkout.session.completed":
        _handle_checkout_complete(data, db)

    elif event_type == "customer.subscription.updated":
        _handle_subscription_update(data, db)

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data, db)

    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data, db)

    return {"received": True}, 200


def _handle_checkout_complete(session, db):
    """Checkout completed — activate subscription."""
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    user_id = session.get("metadata", {}).get("user_id")

    if not user_id:
        # Look up by customer ID
        row = db.execute("SELECT user_id FROM subscriptions WHERE stripe_customer_id=?",
                         (customer_id,)).fetchone()
        if row:
            user_id = row["user_id"]

    if not user_id:
        logger.error(f"Checkout complete but no user_id found for customer {customer_id}")
        return

    db.execute("""
        UPDATE subscriptions SET
            status='active', plan='paid',
            stripe_customer_id=?, stripe_subscription_id=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE user_id=?
    """, (customer_id, subscription_id, user_id))

    logger.info(f"Subscription activated for {user_id}")


def _handle_subscription_update(subscription, db):
    """Subscription updated (renewal, plan change, etc.)."""
    sub_id = subscription.get("id")
    status = subscription.get("status", "")
    period_end = subscription.get("current_period_end")

    row = db.execute("SELECT user_id FROM subscriptions WHERE stripe_subscription_id=?",
                     (sub_id,)).fetchone()
    if not row:
        return

    period_end_dt = datetime.utcfromtimestamp(period_end).isoformat() if period_end else None

    db.execute("""
        UPDATE subscriptions SET status=?, period_end=?, updated_at=CURRENT_TIMESTAMP
        WHERE stripe_subscription_id=?
    """, (status, period_end_dt, sub_id))

    logger.info(f"Subscription updated: {row['user_id']} → {status}")


def _handle_subscription_deleted(subscription, db):
    """Subscription canceled."""
    sub_id = subscription.get("id")

    db.execute("""
        UPDATE subscriptions SET status='canceled', plan='none',
        updated_at=CURRENT_TIMESTAMP WHERE stripe_subscription_id=?
    """, (sub_id,))

    logger.info(f"Subscription canceled: {sub_id}")


def _handle_payment_failed(invoice, db):
    """Payment failed — mark as past_due."""
    customer_id = invoice.get("customer")

    db.execute("""
        UPDATE subscriptions SET status='past_due', updated_at=CURRENT_TIMESTAMP
        WHERE stripe_customer_id=?
    """, (customer_id,))

    logger.warning(f"Payment failed for customer {customer_id}")


# ═══════════════════════════════════════════════════════════════
# FLASK ROUTES
# ═══════════════════════════════════════════════════════════════

def register_billing_routes(app, get_db_func):
    """Register all billing API routes."""

    @app.route("/api/billing/status")
    def billing_status():
        """Get current user's subscription status + consent state."""
        with get_db_func() as db:
            _init_billing_db(db)
            access = check_access(db, g.user_id)
            sub = access["sub"]
            # Check which consents are on file
            has_tos = check_consent(db, g.user_id, "tos", TOS_VERSION)
            has_cost_ack = check_consent(db, g.user_id, "api_cost_ack", COST_ACK_VERSION)
            # Check spend dashboard preference
            spend_enabled = get_user_pref(db, g.user_id, "spend_dashboard", "off")
            return jsonify({
                "has_access": access["has_access"],
                "reason": access["reason"],
                "status": sub.get("status", "none"),
                "plan": sub.get("plan", "none"),
                "trial_end": sub.get("trial_end"),
                "period_end": sub.get("period_end"),
                "tos_accepted": bool(sub.get("tos_accepted_at")),
                "tos_version": TOS_VERSION,
                "cost_ack_accepted": bool(has_cost_ack),
                "cost_ack_version": COST_ACK_VERSION,
                "days_remaining": access.get("days_remaining"),
                "stripe_configured": bool(os.getenv("STRIPE_SECRET_KEY")),
                "spend_dashboard_enabled": spend_enabled == "on",
            })

    @app.route("/api/billing/accept-tos", methods=["POST"])
    def billing_accept_tos():
        """Accept TOS + cost acknowledgment and start trial. Logs forensic proof."""
        data = request.json or {}
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        ua = request.headers.get("User-Agent", "unknown")

        with get_db_func() as db:
            _init_billing_db(db)

            # Log TOS consent
            log_consent(db, g.user_id, "tos", TOS_VERSION,
                        TOS_CONSENT_TEXT.format(version=TOS_VERSION),
                        ip_address=ip, user_agent=ua)

            # Log API cost acknowledgment
            log_consent(db, g.user_id, "api_cost_ack", COST_ACK_VERSION,
                        COST_CONSENT_TEXT,
                        ip_address=ip, user_agent=ua)

            # Update subscription record
            accept_tos(db, g.user_id, ip_address=ip, user_agent=ua)
            sub = start_trial(db, g.user_id)

            return jsonify({
                "success": True,
                "status": sub.get("status"),
                "trial_end": sub.get("trial_end"),
                "consents_logged": ["tos", "api_cost_ack"],
            })

    @app.route("/api/billing/checkout", methods=["POST"])
    def billing_checkout():
        """Create Stripe checkout session for a specific plan."""
        data = request.json or {}
        plan = data.get("plan", "pro")
        billing = data.get("billing", "monthly")
        with get_db_func() as db:
            _init_billing_db(db)
            user = g.user
            result = create_checkout_session(db, g.user_id, user.get("email", ""),
                                             plan=plan, billing=billing)
            if "error" in result:
                return jsonify(result), 400
            return jsonify(result)

    @app.route("/api/billing/portal", methods=["POST"])
    def billing_portal():
        """Create Stripe customer portal session."""
        with get_db_func() as db:
            _init_billing_db(db)
            result = create_portal_session(db, g.user_id)
            if "error" in result:
                return jsonify(result), 400
            return jsonify(result)

    @app.route("/api/billing/webhook", methods=["POST"])
    def billing_webhook():
        """Stripe webhook endpoint."""
        payload = request.get_data(as_text=True)
        sig = request.headers.get("Stripe-Signature", "")
        with get_db_func() as db:
            _init_billing_db(db)
            result, status = handle_webhook(payload, sig, db)
            return jsonify(result), status

    # ── Consent Records (admin) ──

    @app.route("/api/billing/consents", methods=["GET"])
    def billing_consents():
        """Get consent records. Admin sees all; users see their own."""
        with get_db_func() as db:
            _init_billing_db(db)
            user = g.user
            if user.get("role") == "owner":
                uid = request.args.get("user_id")  # Admin can filter by user
            else:
                uid = g.user_id  # Regular users see only their own
            ctype = request.args.get("type")
            records = get_consent_records(db, user_id=uid, consent_type=ctype)
            return jsonify({"records": records, "count": len(records)})

    @app.route("/api/billing/consents/export", methods=["GET"])
    def billing_consents_export():
        """Export all consent records as CSV. Admin only."""
        user = g.user
        if user.get("role") != "owner":
            return jsonify({"error": "Admin only"}), 403
        with get_db_func() as db:
            _init_billing_db(db)
            records = get_consent_records(db)
            if not records:
                return jsonify({"error": "No consent records"}), 404
            # Build CSV
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                "id", "user_id", "consent_type", "consent_version",
                "ip_address", "user_agent", "consent_text", "accepted_at"
            ])
            writer.writeheader()
            for r in records:
                writer.writerow(r)
            csv_data = output.getvalue()
            return Response(csv_data, mimetype="text/csv",
                          headers={"Content-Disposition": "attachment; filename=consent_records.csv"})

    # ── Spend Dashboard Opt-In ──

    @app.route("/api/billing/spend-dashboard", methods=["GET"])
    def spend_dashboard_status():
        """Check if spend dashboard is enabled."""
        with get_db_func() as db:
            _init_billing_db(db)
            enabled = get_user_pref(db, g.user_id, "spend_dashboard", "off")
            return jsonify({"enabled": enabled == "on"})

    @app.route("/api/billing/spend-dashboard", methods=["POST"])
    def spend_dashboard_toggle():
        """Enable/disable spend dashboard. Enabling logs consent."""
        data = request.json or {}
        enable = data.get("enable", False)
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        ua = request.headers.get("User-Agent", "unknown")

        with get_db_func() as db:
            _init_billing_db(db)
            if enable:
                # Log consent for spend tracking
                log_consent(db, g.user_id, "spend_dashboard_optin", "2026.03.1",
                    "I opt in to the spend estimate dashboard. I understand all cost figures "
                    "shown are estimates based on token counts and published pricing. Actual "
                    "charges are determined by my AI provider and may differ. I will verify "
                    "charges with my provider directly.",
                    ip_address=ip, user_agent=ua)
                set_user_pref(db, g.user_id, "spend_dashboard", "on")
            else:
                set_user_pref(db, g.user_id, "spend_dashboard", "off")

            return jsonify({"enabled": enable, "consent_logged": enable})

    # Make webhook public (no auth required)
    # This is handled by adding to the public routes list in security.py

    logger.info("Billing routes registered")
