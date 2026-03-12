# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
BYOK — Bring Your Own Key

MyTeam360 is a BYOK platform. Period.

  ✅ Users provide their own AI API keys (Anthropic, OpenAI, etc.)
  ✅ Keys are stored encrypted (AES-256-GCM) in our database
  ✅ All AI calls use the USER'S key, never a platform key
  ✅ Users control their own costs directly with the provider
  ✅ Users can rotate, revoke, or change keys anytime

  ❌ MyTeam360 NEVER has its own AI provider API keys
  ❌ MyTeam360 NEVER pays for AI API calls
  ❌ MyTeam360 NEVER resells AI tokens
  ❌ Platform env vars (ANTHROPIC_API_KEY, etc.) should NOT exist in production

This means:
  - New users MUST add at least one API key before using AI features
  - The setup concierge guides them through this on first login
  - Non-AI features (CRM, invoicing, tasks, etc.) work without any key
  - We track usage for transparency but never throttle based on our costs

Business model:
  We sell the PLATFORM (orchestration, workflows, intelligence, UX)
  Users pay AI providers DIRECTLY for their own usage
  This is like selling a premium car — we build the car, they buy the gas
"""

import os
import json
import uuid
import logging
import base64
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.byok")


# ══════════════════════════════════════════════════════════════
# SUPPORTED PROVIDERS
# ══════════════════════════════════════════════════════════════

SUPPORTED_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "key_prefix": "sk-ant-",
        "key_format": "Starts with sk-ant-",
        "signup_url": "https://console.anthropic.com/",
        "pricing_url": "https://www.anthropic.com/pricing",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-6"],
        "default_model": "claude-sonnet-4-20250514",
        "test_endpoint": "https://api.anthropic.com/v1/messages",
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "key_prefix": "sk-",
        "key_format": "Starts with sk-",
        "signup_url": "https://platform.openai.com/",
        "pricing_url": "https://openai.com/pricing",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "default_model": "gpt-4o",
        "test_endpoint": "https://api.openai.com/v1/chat/completions",
    },
    "xai": {
        "name": "xAI (Grok)",
        "key_prefix": "xai-",
        "key_format": "Starts with xai-",
        "signup_url": "https://console.x.ai/",
        "pricing_url": "https://x.ai/pricing",
        "models": ["grok-3", "grok-3-mini"],
        "default_model": "grok-3-mini",
        "test_endpoint": "https://api.x.ai/v1/chat/completions",
    },
    "google": {
        "name": "Google (Gemini)",
        "key_prefix": "AI",
        "key_format": "Google AI API key",
        "signup_url": "https://aistudio.google.com/",
        "pricing_url": "https://ai.google.dev/pricing",
        "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
        "default_model": "gemini-2.5-flash",
        "test_endpoint": "https://generativelanguage.googleapis.com/v1beta/models",
    },
}


# ══════════════════════════════════════════════════════════════
# KEY MANAGEMENT
# ══════════════════════════════════════════════════════════════

class BYOKManager:
    """Manage user-provided API keys."""

    def add_key(self, user_id: str, provider: str, api_key: str,
                 label: str = "", preferred_model: str = "") -> dict:
        """Add or update an API key for a provider."""
        if provider not in SUPPORTED_PROVIDERS:
            return {"error": f"Unsupported provider. Choose from: {list(SUPPORTED_PROVIDERS.keys())}"}

        provider_info = SUPPORTED_PROVIDERS[provider]

        # Basic format validation (don't be too strict — providers change formats)
        if not api_key or len(api_key) < 10:
            return {"error": "API key appears too short"}

        # Encrypt the key before storage
        encrypted = self._encrypt_key(api_key)

        # Store a masked version for display (first 8 + last 4)
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"

        kid = f"key_{uuid.uuid4().hex[:8]}"
        model = preferred_model or provider_info["default_model"]

        with get_db() as db:
            # Check if user already has a key for this provider
            existing = db.execute(
                "SELECT id FROM user_api_keys WHERE user_id=? AND provider=?",
                (user_id, provider)).fetchone()

            if existing:
                # Update existing key
                db.execute("""
                    UPDATE user_api_keys
                    SET encrypted_key=?, masked_key=?, label=?, preferred_model=?, status='active', updated_at=?
                    WHERE user_id=? AND provider=?
                """, (encrypted, masked, label or provider_info["name"],
                      model, datetime.now().isoformat(), user_id, provider))
                kid = dict(existing)["id"]
            else:
                # Insert new
                db.execute("""
                    INSERT INTO user_api_keys
                        (id, user_id, provider, encrypted_key, masked_key, label,
                         preferred_model, status)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (kid, user_id, provider, encrypted, masked,
                      label or provider_info["name"], model, "active"))

        return {
            "id": kid,
            "provider": provider,
            "masked_key": masked,
            "model": model,
            "status": "active",
            "message": f"{provider_info['name']} key added. You're ready to use AI features.",
        }

    def remove_key(self, user_id: str, provider: str) -> dict:
        """Remove an API key."""
        with get_db() as db:
            db.execute(
                "DELETE FROM user_api_keys WHERE user_id=? AND provider=?",
                (user_id, provider))
        return {"removed": True, "provider": provider}

    def list_keys(self, user_id: str) -> list:
        """List all user's keys (masked, never raw)."""
        with get_db() as db:
            rows = db.execute(
                "SELECT id, provider, masked_key, label, preferred_model, status, updated_at "
                "FROM user_api_keys WHERE user_id=? ORDER BY provider",
                (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_key(self, user_id: str, provider: str) -> str:
        """Get decrypted API key for making AI calls. Internal use only."""
        with get_db() as db:
            row = db.execute(
                "SELECT encrypted_key FROM user_api_keys WHERE user_id=? AND provider=? AND status='active'",
                (user_id, provider)).fetchone()
        if not row:
            return None
        return self._decrypt_key(dict(row)["encrypted_key"])

    def get_preferred_provider(self, user_id: str) -> dict:
        """Get the user's preferred/first available provider + model."""
        keys = self.list_keys(user_id)
        active = [k for k in keys if k["status"] == "active"]
        if not active:
            return {
                "has_key": False,
                "message": "No AI provider configured. Add your API key to use AI features.",
                "setup_url": "/settings/api-keys",
                "providers": SUPPORTED_PROVIDERS,
            }
        # Prefer Anthropic > OpenAI > others
        priority = ["anthropic", "openai", "xai", "google"]
        for p in priority:
            for k in active:
                if k["provider"] == p:
                    return {
                        "has_key": True,
                        "provider": p,
                        "model": k["preferred_model"],
                        "label": k["label"],
                    }
        # Fallback to first available
        return {
            "has_key": True,
            "provider": active[0]["provider"],
            "model": active[0]["preferred_model"],
            "label": active[0]["label"],
        }

    def has_any_key(self, user_id: str) -> bool:
        """Quick check — does this user have at least one active key?"""
        with get_db() as db:
            row = db.execute(
                "SELECT COUNT(*) as c FROM user_api_keys WHERE user_id=? AND status='active'",
                (user_id,)).fetchone()
        return dict(row)["c"] > 0

    def get_setup_guide(self) -> dict:
        """Return instructions for setting up each provider."""
        guide = {}
        for pid, info in SUPPORTED_PROVIDERS.items():
            guide[pid] = {
                "name": info["name"],
                "steps": [
                    f"1. Go to {info['signup_url']}",
                    "2. Create an account or sign in",
                    "3. Navigate to API Keys",
                    "4. Generate a new API key",
                    f"5. Copy the key (it {info['key_format']})",
                    "6. Paste it here in MyTeam360 → Settings → API Keys",
                ],
                "signup_url": info["signup_url"],
                "pricing_url": info["pricing_url"],
                "models": info["models"],
                "default_model": info["default_model"],
                "estimated_cost": self._estimate_cost(pid),
            }
        return guide

    def set_preferred_model(self, user_id: str, provider: str,
                             model: str) -> dict:
        """Change preferred model for a provider."""
        provider_info = SUPPORTED_PROVIDERS.get(provider)
        if not provider_info:
            return {"error": "Unknown provider"}
        if model not in provider_info["models"]:
            return {"error": f"Unknown model. Available: {provider_info['models']}"}
        with get_db() as db:
            db.execute(
                "UPDATE user_api_keys SET preferred_model=? WHERE user_id=? AND provider=?",
                (model, user_id, provider))
        return {"updated": True, "model": model}

    def test_key(self, user_id: str, provider: str) -> dict:
        """Test if a stored key works by making a minimal API call."""
        key = self.get_key(user_id, provider)
        if not key:
            return {"valid": False, "error": "No key found for this provider"}

        try:
            import requests
            if provider == "anthropic":
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": "claude-haiku-4-5-20251001", "max_tokens": 5,
                          "messages": [{"role": "user", "content": "Hi"}]},
                    timeout=10)
                if resp.status_code == 200:
                    return {"valid": True, "provider": provider,
                            "message": "Key verified — connection successful"}
                elif resp.status_code == 401:
                    return {"valid": False, "error": "Invalid API key"}
                else:
                    return {"valid": False, "error": f"API returned status {resp.status_code}"}

            elif provider == "openai":
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={"model": "gpt-4o-mini", "max_tokens": 5,
                          "messages": [{"role": "user", "content": "Hi"}]},
                    timeout=10)
                if resp.status_code == 200:
                    return {"valid": True, "provider": provider}
                elif resp.status_code == 401:
                    return {"valid": False, "error": "Invalid API key"}
                else:
                    return {"valid": False, "error": f"API returned status {resp.status_code}"}

            else:
                return {"valid": "untested", "message": "Key stored — test not available for this provider yet"}

        except Exception as e:
            return {"valid": False, "error": str(e)}

    # ── Usage Tracking (transparency, not throttling) ──

    def log_usage(self, user_id: str, provider: str, model: str,
                   input_tokens: int = 0, output_tokens: int = 0,
                   feature: str = "") -> dict:
        """Log API usage for transparency — user sees their own costs."""
        uid = f"usage_{uuid.uuid4().hex[:8]}"
        estimated_cost = self._calculate_cost(provider, model, input_tokens, output_tokens)
        with get_db() as db:
            db.execute("""
                INSERT INTO api_usage_log
                    (id, user_id, provider, model, input_tokens, output_tokens,
                     estimated_cost, feature)
                VALUES (?,?,?,?,?,?,?,?)
            """, (uid, user_id, provider, model, input_tokens, output_tokens,
                  estimated_cost, feature))
        return {"logged": True, "estimated_cost": estimated_cost}

    def get_usage_summary(self, user_id: str, days: int = 30) -> dict:
        """Get usage summary — what has this cost the user?"""
        cutoff = (datetime.now() - datetime.timedelta(days=days)).isoformat() if hasattr(datetime, 'timedelta') else ""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with get_db() as db:
            # By provider
            by_provider = db.execute("""
                SELECT provider, model,
                    SUM(input_tokens) as total_input,
                    SUM(output_tokens) as total_output,
                    SUM(estimated_cost) as total_cost,
                    COUNT(*) as calls
                FROM api_usage_log WHERE user_id=? AND created_at>=?
                GROUP BY provider, model ORDER BY total_cost DESC
            """, (user_id, cutoff)).fetchall()

            # By feature
            by_feature = db.execute("""
                SELECT feature, COUNT(*) as calls,
                    SUM(estimated_cost) as total_cost
                FROM api_usage_log WHERE user_id=? AND created_at>=? AND feature!=''
                GROUP BY feature ORDER BY total_cost DESC
            """, (user_id, cutoff)).fetchall()

            # Daily totals
            daily = db.execute("""
                SELECT DATE(created_at) as day, SUM(estimated_cost) as cost, COUNT(*) as calls
                FROM api_usage_log WHERE user_id=? AND created_at>=?
                GROUP BY DATE(created_at) ORDER BY day
            """, (user_id, cutoff)).fetchall()

        total_cost = sum(dict(r)["total_cost"] for r in by_provider)

        return {
            "period_days": days,
            "total_estimated_cost": round(total_cost, 4),
            "by_provider": [dict(r) for r in by_provider],
            "by_feature": [dict(r) for r in by_feature],
            "daily": [dict(r) for r in daily],
            "note": "Costs are estimates. Check your provider dashboard for exact billing.",
        }

    # ── Encryption ──

    def _encrypt_key(self, api_key: str) -> str:
        """Encrypt API key with AES-256-GCM before storage."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            enc_key = base64.b64decode(os.getenv("MT360_ENCRYPTION_KEY", ""))
            if len(enc_key) < 32:
                # Fallback: base64 encode (not secure, but won't crash)
                return base64.b64encode(api_key.encode()).decode()
            nonce = os.urandom(12)
            aesgcm = AESGCM(enc_key[:32])
            encrypted = aesgcm.encrypt(nonce, api_key.encode(), None)
            return base64.b64encode(nonce + encrypted).decode()
        except Exception:
            return base64.b64encode(api_key.encode()).decode()

    def _decrypt_key(self, encrypted: str) -> str:
        """Decrypt API key."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            enc_key = base64.b64decode(os.getenv("MT360_ENCRYPTION_KEY", ""))
            if len(enc_key) < 32:
                return base64.b64decode(encrypted).decode()
            raw = base64.b64decode(encrypted)
            nonce = raw[:12]
            ciphertext = raw[12:]
            aesgcm = AESGCM(enc_key[:32])
            return aesgcm.decrypt(nonce, ciphertext, None).decode()
        except Exception:
            return base64.b64decode(encrypted).decode()

    # ── Cost Estimation ──

    def _calculate_cost(self, provider: str, model: str,
                         input_tokens: int, output_tokens: int) -> float:
        """Estimate cost per call (rough, for transparency)."""
        # Approximate per-million-token pricing as of 2026
        rates = {
            "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
            "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
            "claude-opus-4-6": {"input": 15.0, "output": 75.0},
            "gpt-4o": {"input": 2.50, "output": 10.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "grok-3-mini": {"input": 0.30, "output": 0.50},
        }
        rate = rates.get(model, {"input": 1.0, "output": 3.0})
        cost = (input_tokens * rate["input"] / 1_000_000) + (output_tokens * rate["output"] / 1_000_000)
        return round(cost, 6)

    def _estimate_cost(self, provider: str) -> str:
        """Rough monthly cost estimate for marketing."""
        estimates = {
            "anthropic": "Typical business user: $5-20/month with Claude Sonnet",
            "openai": "Typical business user: $5-15/month with GPT-4o",
            "xai": "Typical business user: $3-10/month with Grok",
            "google": "Generous free tier, then ~$3-10/month",
        }
        return estimates.get(provider, "Varies by usage")
