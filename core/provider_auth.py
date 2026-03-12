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
Provider Auth — Configurable authentication for AI providers.
Supports API key and OAuth2 flows. Stores credentials in DB with
optional macOS Keychain support via the native bridge.
"""

import os
import json
import uuid
import time
import secrets
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from .database import get_db
from .security_hardening import get_encryptor

logger = logging.getLogger("MyTeam360.provider_auth")


# ══════════════════════════════════════════════════════════════
# KNOWN PROVIDER TEMPLATES
# ══════════════════════════════════════════════════════════════

PROVIDER_TEMPLATES = {
    "anthropic": {
        "display_name": "Anthropic (Claude)",
        "auth_methods": ["api_key"],
        "default_model": "claude-sonnet-4-5-20250929",
        "models": [
            "claude-opus-4-5-20250929", "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
        ],
        "api_key_url": "https://console.anthropic.com/settings/keys",
        "docs_url": "https://docs.anthropic.com/en/api",
        "env_var": "ANTHROPIC_API_KEY",
        "key_prefix": "sk-ant-",
        "category": "flagship",
    },
    "openai": {
        "display_name": "OpenAI (GPT)",
        "auth_methods": ["api_key", "oauth"],
        "default_model": "gpt-4o",
        "models": [
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4",
            "o1-preview", "o1-mini", "o3-mini",
        ],
        "api_key_url": "https://platform.openai.com/api-keys",
        "docs_url": "https://platform.openai.com/docs",
        "env_var": "OPENAI_API_KEY",
        "key_prefix": "sk-",
        "category": "flagship",
        "oauth": {
            "authorize_url": "https://auth.openai.com/authorize",
            "token_url": "https://auth.openai.com/oauth/token",
            "scope": "model.read model.request",
        },
    },
    "xai": {
        "display_name": "xAI (Grok)",
        "auth_methods": ["api_key"],
        "default_model": "grok-2-latest",
        "models": [
            "grok-2-latest", "grok-2-vision-latest",
            "grok-3", "grok-3-mini",
        ],
        "api_key_url": "https://console.x.ai/",
        "docs_url": "https://docs.x.ai/",
        "env_var": "XAI_API_KEY",
        "key_prefix": "xai-",
        "category": "flagship",
    },
    "google": {
        "display_name": "Google (Gemini)",
        "auth_methods": ["api_key", "oauth"],
        "default_model": "gemini-2.0-flash",
        "models": [
            "gemini-2.0-flash", "gemini-2.0-flash-lite",
            "gemini-1.5-pro", "gemini-1.5-flash",
        ],
        "api_key_url": "https://aistudio.google.com/apikey",
        "docs_url": "https://ai.google.dev/docs",
        "env_var": "GOOGLE_API_KEY",
        "key_prefix": "AI",
        "category": "flagship",
        "oauth": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scope": "https://www.googleapis.com/auth/generative-language",
        },
    },
    "mistral": {
        "display_name": "Mistral AI",
        "auth_methods": ["api_key"],
        "default_model": "mistral-large-latest",
        "models": [
            "mistral-large-latest", "mistral-medium-latest",
            "mistral-small-latest", "open-mistral-nemo",
            "codestral-latest", "mistral-embed",
        ],
        "api_key_url": "https://console.mistral.ai/api-keys/",
        "docs_url": "https://docs.mistral.ai/",
        "env_var": "MISTRAL_API_KEY",
        "key_prefix": "",
        "base_url": "https://api.mistral.ai/v1",
        "category": "premium",
        "description": "High-performance European AI. GDPR compliant.",
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "auth_methods": ["api_key"],
        "default_model": "deepseek-chat",
        "models": [
            "deepseek-chat", "deepseek-coder", "deepseek-reasoner",
        ],
        "api_key_url": "https://platform.deepseek.com/api_keys",
        "docs_url": "https://platform.deepseek.com/api-docs",
        "env_var": "DEEPSEEK_API_KEY",
        "key_prefix": "sk-",
        "base_url": "https://api.deepseek.com/v1",
        "category": "value",
        "description": "High-performance at very low cost.",
    },
    "cohere": {
        "display_name": "Cohere",
        "auth_methods": ["api_key"],
        "default_model": "command-r-plus",
        "models": [
            "command-r-plus", "command-r", "command-light",
            "command-r-plus-08-2024",
        ],
        "api_key_url": "https://dashboard.cohere.com/api-keys",
        "docs_url": "https://docs.cohere.com/",
        "env_var": "COHERE_API_KEY",
        "key_prefix": "",
        "base_url": "https://api.cohere.com/v2",
        "category": "enterprise",
        "description": "Enterprise search, RAG, and NLP specialist.",
    },
    "together": {
        "display_name": "Together AI",
        "auth_methods": ["api_key"],
        "default_model": "meta-llama/Llama-3.1-70B-Instruct-Turbo",
        "models": [
            "meta-llama/Llama-3.1-405B-Instruct-Turbo",
            "meta-llama/Llama-3.1-70B-Instruct-Turbo",
            "meta-llama/Llama-3.1-8B-Instruct-Turbo",
            "mistralai/Mixtral-8x22B-Instruct-v0.1",
            "mistralai/Mistral-7B-Instruct-v0.3",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-V3",
            "google/gemma-2-27b-it",
        ],
        "api_key_url": "https://api.together.xyz/settings/api-keys",
        "docs_url": "https://docs.together.ai/",
        "env_var": "TOGETHER_API_KEY",
        "key_prefix": "",
        "base_url": "https://api.together.xyz/v1",
        "category": "open_source",
        "description": "Run Llama, Mixtral, Qwen, and 100+ open models.",
    },
    "perplexity": {
        "display_name": "Perplexity",
        "auth_methods": ["api_key"],
        "default_model": "sonar-pro",
        "models": [
            "sonar-pro", "sonar", "sonar-reasoning-pro",
            "sonar-reasoning",
        ],
        "api_key_url": "https://www.perplexity.ai/settings/api",
        "docs_url": "https://docs.perplexity.ai/",
        "env_var": "PERPLEXITY_API_KEY",
        "key_prefix": "pplx-",
        "base_url": "https://api.perplexity.ai",
        "category": "search",
        "description": "AI search — answers with real-time web citations.",
    },
    "fireworks": {
        "display_name": "Fireworks AI",
        "auth_methods": ["api_key"],
        "default_model": "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "models": [
            "accounts/fireworks/models/llama-v3p1-405b-instruct",
            "accounts/fireworks/models/llama-v3p1-70b-instruct",
            "accounts/fireworks/models/llama-v3p1-8b-instruct",
            "accounts/fireworks/models/mixtral-8x22b-instruct",
            "accounts/fireworks/models/qwen2p5-72b-instruct",
            "accounts/fireworks/models/deepseek-v3",
        ],
        "api_key_url": "https://fireworks.ai/api-keys",
        "docs_url": "https://docs.fireworks.ai/",
        "env_var": "FIREWORKS_API_KEY",
        "key_prefix": "",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "category": "open_source",
        "description": "Fastest open-model inference. Llama, Mixtral, Qwen.",
    },
    "groq": {
        "display_name": "Groq",
        "auth_methods": ["api_key"],
        "default_model": "llama-3.1-70b-versatile",
        "models": [
            "llama-3.1-70b-versatile", "llama-3.1-8b-instant",
            "mixtral-8x7b-32768", "gemma2-9b-it",
            "llama-3.3-70b-versatile",
        ],
        "api_key_url": "https://console.groq.com/keys",
        "docs_url": "https://console.groq.com/docs/",
        "env_var": "GROQ_API_KEY",
        "key_prefix": "gsk_",
        "base_url": "https://api.groq.com/openai/v1",
        "category": "speed",
        "description": "Ultra-fast inference on custom LPU hardware.",
    },
    "azure_openai": {
        "display_name": "Azure OpenAI",
        "auth_methods": ["api_key", "oauth"],
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4-turbo", "gpt-4"],
        "api_key_url": "https://portal.azure.com/",
        "docs_url": "https://learn.microsoft.com/en-us/azure/ai-services/openai/",
        "env_var": "AZURE_OPENAI_KEY",
        "key_prefix": "",
        "requires_base_url": True,
        "category": "enterprise",
        "oauth": {
            "authorize_url": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            "scope": "https://cognitiveservices.azure.com/.default",
        },
    },
    "aws_bedrock": {
        "display_name": "AWS Bedrock",
        "auth_methods": ["api_key"],
        "default_model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "models": [
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-3-5-haiku-20241022-v1:0",
            "meta.llama3-1-70b-instruct-v1:0",
            "amazon.titan-text-premier-v2:0",
            "mistral.mistral-large-2407-v1:0",
            "cohere.command-r-plus-v1:0",
        ],
        "api_key_url": "https://console.aws.amazon.com/iam/",
        "docs_url": "https://docs.aws.amazon.com/bedrock/",
        "env_var": "AWS_ACCESS_KEY_ID",
        "key_prefix": "AKIA",
        "requires_base_url": True,
        "category": "enterprise",
        "description": "Multi-model access via AWS. Claude, Llama, Titan.",
    },
    "ollama": {
        "display_name": "Ollama (Local)",
        "auth_methods": ["none"],
        "default_model": "llama3.1",
        "models": [
            "llama3.1", "llama3.2", "mistral", "codellama",
            "deepseek-coder", "phi3", "gemma2", "qwen2.5",
        ],
        "docs_url": "https://ollama.ai/",
        "env_var": "OLLAMA_BASE_URL",
        "requires_base_url": True,
        "default_base_url": "http://localhost:11434/v1",
        "category": "local",
        "description": "Run models locally. Complete privacy. No API costs.",
    },
}


# ══════════════════════════════════════════════════════════════
# PROVIDER AUTH MANAGER
# ══════════════════════════════════════════════════════════════

class ProviderAuthManager:
    """Manages provider authentication configs (API keys & OAuth)."""

    def __init__(self):
        self._oauth_states = {}  # state -> {provider, redirect_uri, created}

    # ── List / Get ──

    def list_providers(self):
        """List all providers with their config status."""
        with get_db() as db:
            rows = db.execute("SELECT * FROM provider_auth ORDER BY provider").fetchall()
        configured = {r["provider"]: dict(r) for r in rows}

        result = []
        for pid, tmpl in PROVIDER_TEMPLATES.items():
            conf = configured.get(pid, {})
            env_key = os.getenv(tmpl.get("env_var", ""), "")

            result.append({
                "provider": pid,
                "display_name": tmpl["display_name"],
                "auth_methods": tmpl["auth_methods"],
                "supported_models": tmpl["models"],
                "default_model": conf.get("default_model") or tmpl["default_model"],
                "docs_url": tmpl.get("docs_url", ""),
                "api_key_url": tmpl.get("api_key_url", ""),
                "requires_base_url": tmpl.get("requires_base_url", False),
                # Current config
                "configured": bool(conf) or bool(env_key),
                "auth_method": conf.get("auth_method", "api_key" if env_key else "none"),
                "has_api_key": bool(conf.get("api_key") or env_key),
                "has_oauth_token": bool(conf.get("oauth_access_token")),
                "oauth_token_expiry": conf.get("oauth_token_expiry"),
                "base_url": conf.get("base_url", tmpl.get("default_base_url", "")),
                "is_enabled": conf.get("is_enabled", 1) if conf else (1 if env_key else 0),
                "source": "database" if conf else ("env" if env_key else "unconfigured"),
                "custom_models": json.loads(conf.get("custom_models", "[]")) if conf else [],
            })

        return result

    def get_provider(self, provider):
        """Get a single provider's config."""
        with get_db() as db:
            row = db.execute("SELECT * FROM provider_auth WHERE provider=?", (provider,)).fetchone()
        if row:
            d = dict(row)
            d["custom_models"] = json.loads(d.get("custom_models") or "[]")
            # Mask sensitive fields
            if d.get("api_key"):
                d["api_key_masked"] = d["api_key"][:8] + "..." + d["api_key"][-4:]
            if d.get("oauth_client_secret"):
                d["oauth_client_secret"] = "***"
            if d.get("oauth_access_token"):
                d["oauth_access_token"] = "***"
            if d.get("oauth_refresh_token"):
                d["oauth_refresh_token"] = "***"
            return d

        # Fall back to env var
        tmpl = PROVIDER_TEMPLATES.get(provider, {})
        env_key = os.getenv(tmpl.get("env_var", ""), "")
        if env_key:
            return {
                "provider": provider,
                "auth_method": "api_key",
                "has_api_key": True,
                "api_key_masked": env_key[:8] + "..." + env_key[-4:] if len(env_key) > 12 else "***",
                "source": "env",
                "is_enabled": 1,
            }
        return None

    # ── Configure API Key ──

    def set_api_key(self, provider, api_key, configured_by=None, base_url=None, default_model=None):
        """Set or update API key for a provider."""
        tmpl = PROVIDER_TEMPLATES.get(provider)
        if not tmpl:
            return {"error": f"Unknown provider: {provider}"}

        if "api_key" not in tmpl.get("auth_methods", []) and "none" not in tmpl.get("auth_methods", []):
            return {"error": f"{provider} does not support API key auth"}

        # Basic validation
        prefix = tmpl.get("key_prefix", "")
        if prefix and api_key and not api_key.startswith(prefix):
            logger.warning(f"API key for {provider} doesn't start with expected prefix '{prefix}'")

        # Encrypt the key before storage
        enc = get_encryptor()
        encrypted_key = enc.encrypt(api_key)

        record_id = f"pa_{provider}"
        with get_db() as db:
            existing = db.execute("SELECT id FROM provider_auth WHERE provider=?", (provider,)).fetchone()
            if existing:
                updates = ["api_key=?", "auth_method='api_key'", "is_enabled=1",
                           "updated_at=CURRENT_TIMESTAMP"]
                vals = [encrypted_key]
                if base_url is not None:
                    updates.append("base_url=?")
                    vals.append(base_url)
                if default_model:
                    updates.append("default_model=?")
                    vals.append(default_model)
                if configured_by:
                    updates.append("configured_by=?")
                    vals.append(configured_by)
                vals.append(provider)
                db.execute(f"UPDATE provider_auth SET {','.join(updates)} WHERE provider=?", vals)
            else:
                db.execute(
                    "INSERT INTO provider_auth (id, provider, auth_method, api_key, base_url,"
                    " default_model, is_enabled, configured_by) VALUES (?,?,?,?,?,?,?,?)",
                    (record_id, provider, "api_key", encrypted_key,
                     base_url or tmpl.get("default_base_url", ""),
                     default_model or tmpl["default_model"], 1, configured_by))

        return {"updated": True, "provider": provider, "auth_method": "api_key"}

    # ── Configure OAuth ──

    def set_oauth_credentials(self, provider, client_id, client_secret,
                              configured_by=None, tenant=None):
        """Store OAuth client credentials for a provider."""
        tmpl = PROVIDER_TEMPLATES.get(provider)
        if not tmpl:
            return {"error": f"Unknown provider: {provider}"}
        if "oauth" not in tmpl.get("auth_methods", []):
            return {"error": f"{provider} does not support OAuth"}

        oauth_conf = tmpl.get("oauth", {})
        authorize_url = oauth_conf.get("authorize_url", "")
        token_url = oauth_conf.get("token_url", "")

        # Azure tenant substitution
        if tenant:
            authorize_url = authorize_url.replace("{tenant}", tenant)
            token_url = token_url.replace("{tenant}", tenant)

        record_id = f"pa_{provider}"
        enc = get_encryptor()
        encrypted_secret = enc.encrypt(client_secret)
        with get_db() as db:
            existing = db.execute("SELECT id FROM provider_auth WHERE provider=?", (provider,)).fetchone()
            if existing:
                db.execute(
                    "UPDATE provider_auth SET auth_method='oauth', oauth_client_id=?,"
                    " oauth_client_secret=?, oauth_authorize_url=?, oauth_token_url=?,"
                    " oauth_scope=?, is_enabled=1, configured_by=?, updated_at=CURRENT_TIMESTAMP"
                    " WHERE provider=?",
                    (client_id, encrypted_secret, authorize_url, token_url,
                     oauth_conf.get("scope", ""), configured_by, provider))
            else:
                db.execute(
                    "INSERT INTO provider_auth (id, provider, auth_method, oauth_client_id,"
                    " oauth_client_secret, oauth_authorize_url, oauth_token_url, oauth_scope,"
                    " default_model, is_enabled, configured_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (record_id, provider, "oauth", client_id, encrypted_secret,
                     authorize_url, token_url, oauth_conf.get("scope", ""),
                     tmpl["default_model"], 1, configured_by))

        return {"updated": True, "provider": provider, "auth_method": "oauth"}

    def get_oauth_authorize_url(self, provider, redirect_uri):
        """Generate OAuth authorize URL with state parameter."""
        with get_db() as db:
            row = db.execute(
                "SELECT oauth_client_id, oauth_authorize_url, oauth_scope"
                " FROM provider_auth WHERE provider=?", (provider,)).fetchone()
        if not row or not row["oauth_client_id"]:
            return {"error": "OAuth not configured for this provider"}

        state = secrets.token_urlsafe(32)
        self._oauth_states[state] = {
            "provider": provider,
            "redirect_uri": redirect_uri,
            "created": time.time(),
        }
        # Clean old states (>10 min)
        cutoff = time.time() - 600
        self._oauth_states = {k: v for k, v in self._oauth_states.items() if v["created"] > cutoff}

        params = {
            "client_id": row["oauth_client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": row["oauth_scope"],
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        url = row["oauth_authorize_url"] + "?" + urllib.parse.urlencode(params)
        return {"authorize_url": url, "state": state}

    def exchange_oauth_code(self, code, state):
        """Exchange authorization code for access/refresh tokens."""
        if state not in self._oauth_states:
            return {"error": "Invalid or expired state parameter"}

        state_data = self._oauth_states.pop(state)
        provider = state_data["provider"]
        redirect_uri = state_data["redirect_uri"]

        with get_db() as db:
            row = db.execute(
                "SELECT oauth_client_id, oauth_client_secret, oauth_token_url"
                " FROM provider_auth WHERE provider=?", (provider,)).fetchone()
        if not row:
            return {"error": "Provider not found"}

        enc = get_encryptor()
        # Exchange code for token
        token_data = self._token_request(
            row["oauth_token_url"],
            grant_type="authorization_code",
            code=code,
            client_id=row["oauth_client_id"],
            client_secret=enc.decrypt(row["oauth_client_secret"]),
            redirect_uri=redirect_uri,
        )

        if "error" in token_data:
            return token_data

        # Store tokens (encrypted)
        expiry = None
        if token_data.get("expires_in"):
            expiry = (datetime.utcnow() + timedelta(seconds=int(token_data["expires_in"]))).isoformat()

        with get_db() as db:
            db.execute(
                "UPDATE provider_auth SET oauth_access_token=?, oauth_refresh_token=?,"
                " oauth_token_expiry=?, is_enabled=1, updated_at=CURRENT_TIMESTAMP"
                " WHERE provider=?",
                (enc.encrypt(token_data.get("access_token", "")),
                 enc.encrypt(token_data.get("refresh_token", "")),
                 expiry, provider))

        return {
            "success": True,
            "provider": provider,
            "expires_in": token_data.get("expires_in"),
            "token_type": token_data.get("token_type", "Bearer"),
        }

    def refresh_oauth_token(self, provider):
        """Refresh an expired OAuth access token."""
        with get_db() as db:
            row = db.execute(
                "SELECT oauth_client_id, oauth_client_secret, oauth_token_url,"
                " oauth_refresh_token FROM provider_auth WHERE provider=?",
                (provider,)).fetchone()
        if not row or not row["oauth_refresh_token"]:
            return {"error": "No refresh token available"}

        enc = get_encryptor()
        token_data = self._token_request(
            row["oauth_token_url"],
            grant_type="refresh_token",
            refresh_token=enc.decrypt(row["oauth_refresh_token"]),
            client_id=row["oauth_client_id"],
            client_secret=enc.decrypt(row["oauth_client_secret"]),
        )

        if "error" in token_data:
            return token_data

        expiry = None
        if token_data.get("expires_in"):
            expiry = (datetime.utcnow() + timedelta(seconds=int(token_data["expires_in"]))).isoformat()

        with get_db() as db:
            updates = ["oauth_access_token=?", "oauth_token_expiry=?", "updated_at=CURRENT_TIMESTAMP"]
            vals = [enc.encrypt(token_data.get("access_token", "")), expiry]
            if token_data.get("refresh_token"):
                updates.append("oauth_refresh_token=?")
                vals.append(enc.encrypt(token_data["refresh_token"]))
            vals.append(provider)
            db.execute(f"UPDATE provider_auth SET {','.join(updates)} WHERE provider=?", vals)

        return {"refreshed": True, "expires_in": token_data.get("expires_in")}

    # ── Get Active Credentials (used by ProviderRegistry) ──

    def get_credentials(self, provider):
        """Get the active API key or OAuth token for a provider.
        Returns: {auth_method, api_key/access_token, base_url, default_model, models}
        Falls back to environment variables."""
        tmpl = PROVIDER_TEMPLATES.get(provider, {})

        with get_db() as db:
            row = db.execute(
                "SELECT * FROM provider_auth WHERE provider=? AND is_enabled=1",
                (provider,)).fetchone()

        if row:
            r = dict(row)
            custom_models = json.loads(r.get("custom_models") or "[]")
            all_models = list(set(tmpl.get("models", []) + custom_models))

            if r["auth_method"] == "oauth" and r.get("oauth_access_token"):
                # Check if token is expired
                if r.get("oauth_token_expiry"):
                    try:
                        expiry = datetime.fromisoformat(r["oauth_token_expiry"])
                        if datetime.utcnow() > expiry - timedelta(minutes=5):
                            # Auto-refresh
                            refresh_result = self.refresh_oauth_token(provider)
                            if refresh_result.get("refreshed"):
                                # Re-read the updated token
                                row2 = db.execute(
                                    "SELECT oauth_access_token FROM provider_auth WHERE provider=?",
                                    (provider,)).fetchone()
                                if row2:
                                    r["oauth_access_token"] = row2["oauth_access_token"]
                    except Exception as e:
                        logger.warning(f"Token expiry check failed for {provider}: {e}")

                enc = get_encryptor()
                return {
                    "auth_method": "oauth",
                    "access_token": enc.decrypt(r["oauth_access_token"]),
                    "base_url": r.get("base_url", ""),
                    "default_model": r.get("default_model") or tmpl.get("default_model", ""),
                    "models": all_models,
                }
            elif r.get("api_key"):
                enc = get_encryptor()
                decrypted_key = enc.decrypt(r["api_key"])
                return {
                    "auth_method": "api_key",
                    "api_key": decrypted_key,
                    "base_url": r.get("base_url", ""),
                    "default_model": r.get("default_model") or tmpl.get("default_model", ""),
                    "models": all_models,
                }

        # Fall back to environment variable
        env_var = tmpl.get("env_var", "")
        env_val = os.getenv(env_var, "")
        if env_val:
            return {
                "auth_method": "env",
                "api_key": env_val,
                "base_url": os.getenv("AZURE_OPENAI_ENDPOINT", "") if provider == "azure_openai"
                    else tmpl.get("default_base_url", ""),
                "default_model": tmpl.get("default_model", ""),
                "models": tmpl.get("models", []),
            }

        return None

    # ── Enable / Disable ──

    def toggle_provider(self, provider, enabled):
        with get_db() as db:
            db.execute("UPDATE provider_auth SET is_enabled=?, updated_at=CURRENT_TIMESTAMP WHERE provider=?",
                       (1 if enabled else 0, provider))
        return {"provider": provider, "is_enabled": enabled}

    def set_custom_models(self, provider, models):
        with get_db() as db:
            db.execute("UPDATE provider_auth SET custom_models=?, updated_at=CURRENT_TIMESTAMP WHERE provider=?",
                       (json.dumps(models), provider))
        return {"provider": provider, "custom_models": models}

    def delete_provider_config(self, provider):
        with get_db() as db:
            db.execute("DELETE FROM provider_auth WHERE provider=?", (provider,))
        return {"deleted": True, "provider": provider}

    # ── Helpers ──

    def _token_request(self, token_url, **params):
        """Make an OAuth token request."""
        try:
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(token_url, data=data, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            })
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            logger.error(f"OAuth token error ({e.code}): {body[:200]}")
            return {"error": f"Token exchange failed: {e.code}", "details": body[:200]}
        except Exception as e:
            logger.error(f"OAuth request failed: {e}")
            return {"error": str(e)}

    def validate_api_key(self, provider, api_key):
        """Quick validation that an API key is formatted correctly."""
        tmpl = PROVIDER_TEMPLATES.get(provider, {})
        prefix = tmpl.get("key_prefix", "")
        issues = []
        if not api_key:
            issues.append("API key is empty")
        elif prefix and not api_key.startswith(prefix):
            issues.append(f"Expected key to start with '{prefix}'")
        if len(api_key) < 10:
            issues.append("Key seems too short")
        return {"valid": len(issues) == 0, "issues": issues}

    def get_templates(self):
        """Return provider templates (for UI setup)."""
        result = {}
        for pid, tmpl in PROVIDER_TEMPLATES.items():
            t = {**tmpl}
            # Don't expose OAuth secrets in templates
            if "oauth" in t:
                t["oauth_supported"] = True
                del t["oauth"]
            result[pid] = t
        return result
