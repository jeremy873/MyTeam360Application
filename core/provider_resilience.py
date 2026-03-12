# ═══════════════════════════════════════════════════════════════════
# MyTeam360 — AI Platform
# Copyright © 2026 Praxis Holdings LLC. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL — TRADE SECRET
# Report IP violations: legal@praxisholdingsllc.com
# ═══════════════════════════════════════════════════════════════════

"""
Provider Independence Strategy — Never depend on a single AI provider.

LAYERS OF RESILIENCE:
  Layer 1: Multi-provider BYOK (Anthropic, OpenAI, xAI, Google)
    → User picks their preferred provider. If one blocks us, 3 others work.

  Layer 2: Open-source model support (Llama, Mistral, DeepSeek, Qwen)
    → Users can point to their own self-hosted models
    → Users can use services like Together.ai, Fireworks.ai, Groq
    → NOBODY can revoke access to open-source models

  Layer 3: Local model support (Ollama, LM Studio, llama.cpp)
    → User runs a model on their own hardware
    → Complete independence from any cloud provider
    → Works offline

  Layer 4: Platform intelligence without AI
    → CRM, invoicing, tasks, social media, goals, expenses ALL work
      without any AI provider. The platform is useful WITHOUT AI.
    → AI is an enhancement, not a dependency.

BUSINESS TRUTH:
  If every AI provider shut us out tomorrow, users would still have:
  ✅ Full CRM with pipeline management
  ✅ Invoice generation and tracking
  ✅ Task/project management
  ✅ Social media scheduling
  ✅ Goal tracking
  ✅ Expense tracking
  ✅ Email composer
  ✅ Booking links
  ✅ Calendar integration
  ✅ Global search, notes, favorites
  ✅ Workflow automation (rule-based)
  ✅ Daily briefing (data aggregation, no AI needed)

  They would LOSE:
  ❌ AI conversations (roundtables, spaces)
  ❌ AI content generation (social posts, emails)
  ❌ AI meeting prep summaries
  ❌ Smart suggestions (AI-powered)

  That means ~70% of the platform's VALUE works without AI.
  The AI makes it magical, but the platform stands on its own.
"""

import json
import logging
import os
import requests
from datetime import datetime

logger = logging.getLogger("MyTeam360.provider_resilience")


# ══════════════════════════════════════════════════════════════
# OPEN-SOURCE PROVIDER REGISTRY
# ══════════════════════════════════════════════════════════════

OPEN_SOURCE_PROVIDERS = {
    # ── Hosted open-source (cloud, BYOK) ──
    "together": {
        "name": "Together AI",
        "type": "hosted_open_source",
        "description": "Run Llama, Mistral, and other open-source models via API",
        "signup_url": "https://www.together.ai/",
        "api_base": "https://api.together.xyz/v1",
        "api_format": "openai_compatible",
        "key_prefix": "",
        "models": [
            {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "name": "Llama 3.3 70B", "context": 128000},
            {"id": "meta-llama/Llama-3.1-405B-Instruct-Turbo", "name": "Llama 3.1 405B", "context": 128000},
            {"id": "mistralai/Mixtral-8x22B-Instruct-v0.1", "name": "Mixtral 8x22B", "context": 65536},
            {"id": "Qwen/Qwen2.5-72B-Instruct-Turbo", "name": "Qwen 2.5 72B", "context": 32768},
            {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3", "context": 128000},
        ],
        "estimated_cost": "Most models: $0.50-2.00 per million tokens",
        "revocable": False,  # Can't be taken away — open source models
    },
    "fireworks": {
        "name": "Fireworks AI",
        "type": "hosted_open_source",
        "description": "Fast inference for open-source models",
        "signup_url": "https://fireworks.ai/",
        "api_base": "https://api.fireworks.ai/inference/v1",
        "api_format": "openai_compatible",
        "key_prefix": "",
        "models": [
            {"id": "accounts/fireworks/models/llama-v3p3-70b-instruct", "name": "Llama 3.3 70B", "context": 128000},
            {"id": "accounts/fireworks/models/mixtral-8x22b-instruct", "name": "Mixtral 8x22B", "context": 65536},
            {"id": "accounts/fireworks/models/qwen2p5-72b-instruct", "name": "Qwen 2.5 72B", "context": 32768},
        ],
        "estimated_cost": "$0.20-1.50 per million tokens",
        "revocable": False,
    },
    "groq": {
        "name": "Groq",
        "type": "hosted_open_source",
        "description": "Fastest inference — custom LPU hardware",
        "signup_url": "https://console.groq.com/",
        "api_base": "https://api.groq.com/openai/v1",
        "api_format": "openai_compatible",
        "key_prefix": "gsk_",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "context": 128000},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "context": 32768},
            {"id": "gemma2-9b-it", "name": "Gemma 2 9B", "context": 8192},
        ],
        "estimated_cost": "Very generous free tier, then $0.05-0.80/M tokens",
        "revocable": False,
    },

    # ── Self-hosted (local, zero dependency) ──
    "ollama": {
        "name": "Ollama (Local)",
        "type": "self_hosted",
        "description": "Run AI models on your own computer. No cloud, no API keys, no cost.",
        "signup_url": "https://ollama.com/",
        "api_base": "http://localhost:11434/v1",
        "api_format": "openai_compatible",
        "key_prefix": "",
        "models": [
            {"id": "llama3.3", "name": "Llama 3.3", "context": 128000, "local": True},
            {"id": "mistral", "name": "Mistral 7B", "context": 32768, "local": True},
            {"id": "qwen2.5", "name": "Qwen 2.5", "context": 32768, "local": True},
            {"id": "deepseek-r1", "name": "DeepSeek R1", "context": 128000, "local": True},
            {"id": "phi4", "name": "Phi-4", "context": 16384, "local": True},
        ],
        "estimated_cost": "Free. Runs on your hardware.",
        "revocable": False,
        "requirements": "8GB+ RAM for small models, 32GB+ for large models",
    },
    "lmstudio": {
        "name": "LM Studio (Local)",
        "type": "self_hosted",
        "description": "Desktop app to run models locally with OpenAI-compatible API",
        "signup_url": "https://lmstudio.ai/",
        "api_base": "http://localhost:1234/v1",
        "api_format": "openai_compatible",
        "key_prefix": "",
        "models": [
            {"id": "user_choice", "name": "Any GGUF model from HuggingFace", "local": True},
        ],
        "estimated_cost": "Free. Runs on your hardware.",
        "revocable": False,
    },
    "custom": {
        "name": "Custom Endpoint",
        "type": "custom",
        "description": "Any OpenAI-compatible API endpoint. Self-hosted vLLM, text-generation-inference, or custom server.",
        "api_base": "user_configured",
        "api_format": "openai_compatible",
        "models": [{"id": "user_configured", "name": "User's choice"}],
        "estimated_cost": "Depends on hosting",
        "revocable": False,
    },
}


# ══════════════════════════════════════════════════════════════
# OPENAI-COMPATIBLE UNIVERSAL CALLER
# ══════════════════════════════════════════════════════════════

class UniversalAICaller:
    """Call ANY OpenAI-compatible endpoint.

    Because Together, Fireworks, Groq, Ollama, LM Studio, and vLLM
    all use the OpenAI API format, we only need ONE caller.
    """

    def call(self, api_base: str, api_key: str, model: str,
             messages: list, max_tokens: int = 2048,
             temperature: float = 0.7, stream: bool = False) -> dict:
        """Make a chat completion call to any OpenAI-compatible endpoint."""
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            body = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": stream,
            }

            resp = requests.post(
                f"{api_base.rstrip('/')}/chat/completions",
                headers=headers,
                json=body,
                timeout=60)

            if resp.status_code != 200:
                return {
                    "error": True,
                    "status": resp.status_code,
                    "message": resp.text[:500],
                }

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            usage = data.get("usage", {})

            return {
                "error": False,
                "content": choice.get("message", {}).get("content", ""),
                "model": data.get("model", model),
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "finish_reason": choice.get("finish_reason", ""),
            }

        except requests.exceptions.ConnectionError:
            return {"error": True, "message": f"Cannot connect to {api_base}. Is the server running?"}
        except requests.exceptions.Timeout:
            return {"error": True, "message": "Request timed out (60s). Model may be loading."}
        except Exception as e:
            return {"error": True, "message": str(e)}


# ══════════════════════════════════════════════════════════════
# RESILIENCE MANAGER
# ══════════════════════════════════════════════════════════════

class ProviderResilienceManager:
    """Manages provider fallback and independence strategy."""

    def get_all_providers(self) -> dict:
        """Get all available providers — commercial AND open source."""
        from .byok import SUPPORTED_PROVIDERS
        return {
            "commercial": SUPPORTED_PROVIDERS,
            "open_source": OPEN_SOURCE_PROVIDERS,
            "total_providers": len(SUPPORTED_PROVIDERS) + len(OPEN_SOURCE_PROVIDERS),
            "total_models": self._count_models(),
            "independence_note": (
                "Open-source providers cannot be revoked. Even if every commercial "
                "provider blocked MyTeam360, users could run Llama, Mistral, or "
                "DeepSeek via Together.ai, Groq, Ollama (local), or any "
                "OpenAI-compatible endpoint. The platform is provider-independent."
            ),
        }

    def get_fallback_chain(self, user_id: str) -> list:
        """Get the user's provider fallback order."""
        from .byok import BYOKManager
        bm = BYOKManager()
        keys = bm.list_keys(user_id)
        active = [k for k in keys if k["status"] == "active"]

        chain = []
        for k in active:
            chain.append({
                "provider": k["provider"],
                "model": k["preferred_model"],
                "type": "commercial" if k["provider"] in ["anthropic", "openai", "xai", "google"] else "open_source",
            })

        if not chain:
            chain.append({
                "provider": "none",
                "model": "none",
                "type": "no_key",
                "message": "Add an API key to use AI features. Platform features work without AI.",
            })

        return chain

    def get_independence_report(self) -> dict:
        """Report on platform's provider independence."""
        features_without_ai = [
            "CRM (contacts, deals, companies, pipeline)",
            "Invoicing (create, send, track, partial payments)",
            "Task management (kanban, subtasks, time tracking)",
            "Social media scheduling (campaigns, calendar, bulk schedule)",
            "Goal/KPI tracking (OKRs, progress, dashboard)",
            "Expense tracking (categories, tax deductibility)",
            "Email composer (drafts, templates, signatures, outbox)",
            "Booking links (schedule meetings)",
            "Calendar integration (read-only)",
            "Client portal (secure sharing)",
            "Document export (Word, PDF, Excel, CSV)",
            "Global search",
            "Activity feed",
            "Notes/scratchpad",
            "Favorites/pins",
            "Workflow automation (rule-based triggers)",
            "Daily briefing (data aggregation)",
            "Quick capture (entity extraction)",
            "Financial dashboard",
            "Win/loss analysis",
            "Client health scores",
            "Revenue forecasting",
            "Flight tracking",
            "Weather integration",
        ]

        features_requiring_ai = [
            "AI conversations (Spaces, Roundtables)",
            "AI content generation (social posts, emails)",
            "AI meeting prep summaries",
            "AI competitive analysis",
            "AI job descriptions and interview questions",
            "AI contract generation",
            "Content repurposing (AI rewrites for each platform)",
        ]

        pct_without = round(len(features_without_ai) / (len(features_without_ai) + len(features_requiring_ai)) * 100)

        return {
            "features_without_ai": len(features_without_ai),
            "features_requiring_ai": len(features_requiring_ai),
            "percent_functional_without_ai": pct_without,
            "without_ai_list": features_without_ai,
            "requires_ai_list": features_requiring_ai,
            "commercial_providers": 4,
            "open_source_providers": len([p for p in OPEN_SOURCE_PROVIDERS.values() if p["type"] == "hosted_open_source"]),
            "self_hosted_options": len([p for p in OPEN_SOURCE_PROVIDERS.values() if p["type"] == "self_hosted"]),
            "unrevocable_options": len([p for p in OPEN_SOURCE_PROVIDERS.values() if not p.get("revocable", True)]),
            "conclusion": (
                f"{pct_without}% of platform features work WITHOUT any AI provider. "
                f"For the remaining {100-pct_without}%, users have {4 + len(OPEN_SOURCE_PROVIDERS)} "
                f"provider options including {len([p for p in OPEN_SOURCE_PROVIDERS.values() if p['type'] == 'self_hosted'])} "
                f"self-hosted options that cannot be revoked by anyone."
            ),
        }

    def _count_models(self) -> int:
        from .byok import SUPPORTED_PROVIDERS
        count = sum(len(p["models"]) for p in SUPPORTED_PROVIDERS.values())
        count += sum(len(p["models"]) for p in OPEN_SOURCE_PROVIDERS.values())
        return count
