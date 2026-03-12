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
Providers — Unified interface for multiple AI backends.
Supports Anthropic (Claude), OpenAI (GPT), xAI (Grok), and extensible to others.
"""

import os
import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger("MyTeam360.providers")


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""
    name: str
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    available_models: list = field(default_factory=list)
    enabled: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7


class AIProvider(ABC):
    """Abstract base class for all AI providers."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.request_count = 0
        self.total_tokens = 0

    @abstractmethod
    def generate(self, messages: list, system: str = "", model: str = "",
                 temperature: float = None, max_tokens: int = None) -> dict:
        """Generate a response. Returns {"text": str, "usage": dict}."""
        pass

    @abstractmethod
    def generate_stream(self, messages: list, system: str = "", model: str = "",
                        temperature: float = None, max_tokens: int = None):
        """Stream a response. Yields {"type": "text"|"done"|"error", "content": str}."""
        pass

    def to_dict(self) -> dict:
        return {
            "name": self.config.name,
            "default_model": self.config.default_model,
            "available_models": self.config.available_models,
            "enabled": self.config.enabled,
            "request_count": self.request_count,
            "has_key": bool(self.config.api_key),
        }


# ═══════════════════════════════════════════════
# Anthropic (Claude)
# ═══════════════════════════════════════════════

class AnthropicProvider(AIProvider):
    """Anthropic Claude provider."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                name="anthropic",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                default_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                available_models=[
                    "claude-opus-4-5-20250929",
                    "claude-sonnet-4-5-20250929",
                    "claude-sonnet-4-20250514",
                    "claude-haiku-4-5-20251001",
                ],
            )
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.config.api_key)
        return self._client

    def generate(self, messages: list, system: str = "", model: str = "",
                 temperature: float = None, max_tokens: int = None) -> dict:
        model = model or self.config.default_model
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        try:
            kwargs = dict(
                model=model,
                max_tokens=tokens,
                messages=messages,
                temperature=temp,
            )
            if system:
                kwargs["system"] = system

            response = self.client.messages.create(**kwargs)
            self.request_count += 1

            text = response.content[0].text
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            self.total_tokens += usage["input_tokens"] + usage["output_tokens"]

            return {"text": text, "usage": usage, "model": model, "provider": "anthropic"}

        except Exception as e:
            return {"text": f"[Anthropic Error] {str(e)}", "usage": {}, "model": model, "provider": "anthropic"}

    def generate_stream(self, messages: list, system: str = "", model: str = "",
                        temperature: float = None, max_tokens: int = None):
        model = model or self.config.default_model
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        try:
            kwargs = dict(
                model=model,
                max_tokens=tokens,
                messages=messages,
                temperature=temp,
            )
            if system:
                kwargs["system"] = system

            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield {"type": "text", "content": text}
            self.request_count += 1
            yield {"type": "done", "content": ""}

        except Exception as e:
            yield {"type": "error", "content": str(e)}


# ═══════════════════════════════════════════════
# OpenAI (GPT, o-series)
# ═══════════════════════════════════════════════

class OpenAIProvider(AIProvider):
    """OpenAI GPT provider."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                name="openai",
                api_key=os.getenv("OPENAI_API_KEY", ""),
                default_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                available_models=[
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-turbo",
                    "o1-preview",
                    "o1-mini",
                    "o3-mini",
                ],
            )
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.config.api_key)
        return self._client

    def _convert_messages(self, messages: list, system: str = "") -> list:
        """Convert to OpenAI message format."""
        converted = []
        if system:
            converted.append({"role": "system", "content": system})
        for msg in messages:
            converted.append({"role": msg["role"], "content": msg["content"]})
        return converted

    def generate(self, messages: list, system: str = "", model: str = "",
                 temperature: float = None, max_tokens: int = None) -> dict:
        model = model or self.config.default_model
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=self._convert_messages(messages, system),
                temperature=temp,
                max_tokens=tokens,
            )
            self.request_count += 1

            text = response.choices[0].message.content
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
            self.total_tokens += usage["input_tokens"] + usage["output_tokens"]

            return {"text": text, "usage": usage, "model": model, "provider": "openai"}

        except Exception as e:
            return {"text": f"[OpenAI Error] {str(e)}", "usage": {}, "model": model, "provider": "openai"}

    def generate_stream(self, messages: list, system: str = "", model: str = "",
                        temperature: float = None, max_tokens: int = None):
        model = model or self.config.default_model
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=self._convert_messages(messages, system),
                temperature=temp,
                max_tokens=tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield {"type": "text", "content": chunk.choices[0].delta.content}
            self.request_count += 1
            yield {"type": "done", "content": ""}

        except Exception as e:
            yield {"type": "error", "content": str(e)}


# ═══════════════════════════════════════════════
# xAI (Grok)
# ═══════════════════════════════════════════════

class GrokProvider(AIProvider):
    """xAI Grok provider (OpenAI-compatible API)."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                name="grok",
                api_key=os.getenv("XAI_API_KEY", ""),
                base_url="https://api.x.ai/v1",
                default_model=os.getenv("GROK_MODEL", "grok-3"),
                available_models=[
                    "grok-3",
                    "grok-3-mini",
                    "grok-2",
                ],
            )
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        return self._client

    def _convert_messages(self, messages: list, system: str = "") -> list:
        converted = []
        if system:
            converted.append({"role": "system", "content": system})
        for msg in messages:
            converted.append({"role": msg["role"], "content": msg["content"]})
        return converted

    def generate(self, messages: list, system: str = "", model: str = "",
                 temperature: float = None, max_tokens: int = None) -> dict:
        model = model or self.config.default_model
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=self._convert_messages(messages, system),
                temperature=temp,
                max_tokens=tokens,
            )
            self.request_count += 1
            text = response.choices[0].message.content
            usage = {
                "input_tokens": getattr(response.usage, "prompt_tokens", 0),
                "output_tokens": getattr(response.usage, "completion_tokens", 0),
            }
            self.total_tokens += usage["input_tokens"] + usage["output_tokens"]
            return {"text": text, "usage": usage, "model": model, "provider": "grok"}

        except Exception as e:
            return {"text": f"[Grok Error] {str(e)}", "usage": {}, "model": model, "provider": "grok"}

    def generate_stream(self, messages: list, system: str = "", model: str = "",
                        temperature: float = None, max_tokens: int = None):
        model = model or self.config.default_model
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=self._convert_messages(messages, system),
                temperature=temp,
                max_tokens=tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield {"type": "text", "content": chunk.choices[0].delta.content}
            self.request_count += 1
            yield {"type": "done", "content": ""}
        except Exception as e:
            yield {"type": "error", "content": str(e)}


# ═══════════════════════════════════════════════
# Microsoft Copilot / Azure OpenAI
# ═══════════════════════════════════════════════

class AzureOpenAIProvider(AIProvider):
    """Azure OpenAI / Copilot provider."""

    def __init__(self, config: ProviderConfig = None):
        if config is None:
            config = ProviderConfig(
                name="azure_openai",
                api_key=os.getenv("AZURE_OPENAI_KEY", ""),
                base_url=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                default_model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
                available_models=["gpt-4o", "gpt-4-turbo"],
            )
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import AzureOpenAI
            self._client = AzureOpenAI(
                api_key=self.config.api_key,
                azure_endpoint=self.config.base_url,
                api_version="2024-06-01",
            )
        return self._client

    def _convert_messages(self, messages: list, system: str = "") -> list:
        converted = []
        if system:
            converted.append({"role": "system", "content": system})
        for msg in messages:
            converted.append({"role": msg["role"], "content": msg["content"]})
        return converted

    def generate(self, messages: list, system: str = "", model: str = "",
                 temperature: float = None, max_tokens: int = None) -> dict:
        model = model or self.config.default_model
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens or self.config.max_tokens

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=self._convert_messages(messages, system),
                temperature=temp,
                max_tokens=tokens,
            )
            self.request_count += 1
            text = response.choices[0].message.content
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
            return {"text": text, "usage": usage, "model": model, "provider": "azure_openai"}
        except Exception as e:
            return {"text": f"[Azure Error] {str(e)}", "usage": {}, "model": model, "provider": "azure_openai"}

    def generate_stream(self, messages: list, system: str = "", model: str = "",
                        temperature: float = None, max_tokens: int = None):
        model = model or self.config.default_model
        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=self._convert_messages(messages, system),
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield {"type": "text", "content": chunk.choices[0].delta.content}
            yield {"type": "done", "content": ""}
        except Exception as e:
            yield {"type": "error", "content": str(e)}


# ═══════════════════════════════════════════════
# Generic OpenAI-Compatible (Ollama, LM Studio, etc.)
# ═══════════════════════════════════════════════

class GenericOpenAIProvider(AIProvider):
    """Generic provider for any OpenAI-compatible API (Ollama, LM Studio, Together, etc.)."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key or "not-needed",
                base_url=self.config.base_url,
            )
        return self._client

    def _convert_messages(self, messages: list, system: str = "") -> list:
        converted = []
        if system:
            converted.append({"role": "system", "content": system})
        for msg in messages:
            converted.append({"role": msg["role"], "content": msg["content"]})
        return converted

    def generate(self, messages: list, system: str = "", model: str = "",
                 temperature: float = None, max_tokens: int = None) -> dict:
        model = model or self.config.default_model
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=self._convert_messages(messages, system),
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
            )
            self.request_count += 1
            text = response.choices[0].message.content
            return {"text": text, "usage": {}, "model": model, "provider": self.config.name}
        except Exception as e:
            return {"text": f"[{self.config.name} Error] {str(e)}", "usage": {}, "model": model, "provider": self.config.name}

    def generate_stream(self, messages: list, system: str = "", model: str = "",
                        temperature: float = None, max_tokens: int = None):
        model = model or self.config.default_model
        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=self._convert_messages(messages, system),
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield {"type": "text", "content": chunk.choices[0].delta.content}
            yield {"type": "done", "content": ""}
        except Exception as e:
            yield {"type": "error", "content": str(e)}


# ═══════════════════════════════════════════════
# Provider Registry
# ═══════════════════════════════════════════════

class ProviderRegistry:
    """Central registry for all AI providers."""

    def __init__(self):
        self.providers: dict[str, AIProvider] = {}
        self._auto_register()

    def _auto_register(self):
        """Auto-register providers from DB config first, then env vars as fallback."""
        # Try loading from provider_auth table
        db_configs = self._load_db_configs()

        # Anthropic
        ant_key = db_configs.get("anthropic", {}).get("api_key") or \
                  db_configs.get("anthropic", {}).get("access_token") or \
                  os.getenv("ANTHROPIC_API_KEY", "")
        self.register(AnthropicProvider(ProviderConfig(
            name="anthropic", api_key=ant_key,
            default_model=db_configs.get("anthropic", {}).get("default_model", "claude-sonnet-4-5-20250929"),
        )))

        # OpenAI
        oai_key = db_configs.get("openai", {}).get("api_key") or \
                  db_configs.get("openai", {}).get("access_token") or \
                  os.getenv("OPENAI_API_KEY", "")
        if oai_key:
            self.register(OpenAIProvider(ProviderConfig(
                name="openai", api_key=oai_key,
                default_model=db_configs.get("openai", {}).get("default_model", "gpt-4o"),
            )))

        # Grok
        xai_key = db_configs.get("xai", {}).get("api_key") or \
                  db_configs.get("xai", {}).get("access_token") or \
                  os.getenv("XAI_API_KEY", "")
        if xai_key:
            self.register(GrokProvider(ProviderConfig(
                name="xai", api_key=xai_key,
                default_model=db_configs.get("xai", {}).get("default_model", "grok-2-latest"),
            )))

        # Azure OpenAI
        az_key = db_configs.get("azure_openai", {}).get("api_key") or \
                 db_configs.get("azure_openai", {}).get("access_token") or \
                 os.getenv("AZURE_OPENAI_KEY", "")
        az_url = db_configs.get("azure_openai", {}).get("base_url") or \
                 os.getenv("AZURE_OPENAI_ENDPOINT", "")
        if az_key and az_url:
            self.register(AzureOpenAIProvider(ProviderConfig(
                name="azure_openai", api_key=az_key, base_url=az_url,
                default_model=db_configs.get("azure_openai", {}).get("default_model", "gpt-4o"),
            )))

        # Ollama
        ollama_url = db_configs.get("ollama", {}).get("base_url") or \
                     os.getenv("OLLAMA_BASE_URL", "")
        if ollama_url:
            self.register(GenericOpenAIProvider(ProviderConfig(
                name="ollama",
                base_url=ollama_url if "/v1" in ollama_url else ollama_url.rstrip("/") + "/v1",
                default_model=db_configs.get("ollama", {}).get("default_model", "llama3.1"),
                available_models=["llama3.1", "llama3.2", "mistral", "codellama", "deepseek-coder"],
            )))

        # Google Gemini (new via DB)
        google_key = db_configs.get("google", {}).get("api_key") or \
                     db_configs.get("google", {}).get("access_token") or \
                     os.getenv("GOOGLE_API_KEY", "")
        if google_key:
            self.register(GenericOpenAIProvider(ProviderConfig(
                name="google", api_key=google_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                default_model=db_configs.get("google", {}).get("default_model", "gemini-2.0-flash"),
                available_models=["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
            )))

        # ── OpenAI-Compatible Providers (auto-register from DB or env) ──
        # Each uses GenericOpenAIProvider with a different base_url

        OPENAI_COMPAT = {
            "mistral": {
                "base_url": "https://api.mistral.ai/v1",
                "env_var": "MISTRAL_API_KEY",
                "default_model": "mistral-large-latest",
                "models": ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest",
                           "open-mistral-nemo", "codestral-latest"],
            },
            "deepseek": {
                "base_url": "https://api.deepseek.com/v1",
                "env_var": "DEEPSEEK_API_KEY",
                "default_model": "deepseek-chat",
                "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
            },
            "together": {
                "base_url": "https://api.together.xyz/v1",
                "env_var": "TOGETHER_API_KEY",
                "default_model": "meta-llama/Llama-3.1-70B-Instruct-Turbo",
                "models": ["meta-llama/Llama-3.1-405B-Instruct-Turbo",
                           "meta-llama/Llama-3.1-70B-Instruct-Turbo",
                           "meta-llama/Llama-3.1-8B-Instruct-Turbo",
                           "mistralai/Mixtral-8x22B-Instruct-v0.1",
                           "Qwen/Qwen2.5-72B-Instruct-Turbo",
                           "deepseek-ai/DeepSeek-V3",
                           "google/gemma-2-27b-it"],
            },
            "perplexity": {
                "base_url": "https://api.perplexity.ai",
                "env_var": "PERPLEXITY_API_KEY",
                "default_model": "sonar-pro",
                "models": ["sonar-pro", "sonar", "sonar-reasoning-pro", "sonar-reasoning"],
            },
            "fireworks": {
                "base_url": "https://api.fireworks.ai/inference/v1",
                "env_var": "FIREWORKS_API_KEY",
                "default_model": "accounts/fireworks/models/llama-v3p1-70b-instruct",
                "models": ["accounts/fireworks/models/llama-v3p1-405b-instruct",
                           "accounts/fireworks/models/llama-v3p1-70b-instruct",
                           "accounts/fireworks/models/llama-v3p1-8b-instruct",
                           "accounts/fireworks/models/mixtral-8x22b-instruct",
                           "accounts/fireworks/models/deepseek-v3"],
            },
            "groq": {
                "base_url": "https://api.groq.com/openai/v1",
                "env_var": "GROQ_API_KEY",
                "default_model": "llama-3.1-70b-versatile",
                "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant",
                           "mixtral-8x7b-32768", "gemma2-9b-it",
                           "llama-3.3-70b-versatile"],
            },
            "cohere": {
                "base_url": "https://api.cohere.com/v2",
                "env_var": "COHERE_API_KEY",
                "default_model": "command-r-plus",
                "models": ["command-r-plus", "command-r", "command-light"],
            },
        }

        for name, cfg in OPENAI_COMPAT.items():
            key = db_configs.get(name, {}).get("api_key") or \
                  db_configs.get(name, {}).get("access_token") or \
                  os.getenv(cfg["env_var"], "")
            base = db_configs.get(name, {}).get("base_url") or cfg["base_url"]
            if key:
                self.register(GenericOpenAIProvider(ProviderConfig(
                    name=name, api_key=key, base_url=base,
                    default_model=db_configs.get(name, {}).get("default_model", cfg["default_model"]),
                    available_models=cfg["models"],
                )))

    def _load_db_configs(self):
        """Load provider configs from database."""
        configs = {}
        try:
            from .provider_auth import ProviderAuthManager
            mgr = ProviderAuthManager()
            all_providers = [
                "anthropic", "openai", "xai", "azure_openai", "ollama", "google",
                "mistral", "deepseek", "cohere", "together", "perplexity",
                "fireworks", "groq", "aws_bedrock",
            ]
            for provider in all_providers:
                creds = mgr.get_credentials(provider)
                if creds:
                    configs[provider] = creds
        except Exception as e:
            logger.debug(f"DB provider configs not available: {e}")
        return configs

    def reload(self):
        """Re-scan DB and environment for API keys and re-register providers."""
        self.providers.clear()
        self._auto_register()

    def register(self, provider: AIProvider):
        """Register a provider."""
        self.providers[provider.config.name] = provider
        logger.info(f"Registered provider: {provider.config.name}")

    def get(self, name: str) -> AIProvider | None:
        """Get a provider by name."""
        return self.providers.get(name)

    def get_provider(self, name: str) -> AIProvider | None:
        """Alias for get()."""
        return self.providers.get(name)

    def get_default(self) -> AIProvider:
        """Get the default (first available with a key) provider."""
        for provider in self.providers.values():
            if provider.config.enabled and provider.config.api_key:
                return provider
        # Fallback to anthropic even without key (will error gracefully)
        return self.providers.get("anthropic", list(self.providers.values())[0])

    def list_all(self) -> list:
        """List all registered providers."""
        return [p.to_dict() for p in self.providers.values()]

    def get_all_models(self) -> dict:
        """Get all available models grouped by provider."""
        models = {}
        for name, provider in self.providers.items():
            if provider.config.enabled:
                models[name] = {
                    "default": provider.config.default_model,
                    "models": provider.config.available_models,
                    "has_key": bool(provider.config.api_key),
                }
        return models
