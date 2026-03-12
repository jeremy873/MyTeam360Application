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
Smart Cost Routing — Automatically selects the optimal model based on
prompt complexity, saving users money without sacrificing quality.

Analyzes each message for complexity signals and routes to:
  - Cheap models (Haiku, GPT-4o-mini, Flash) for simple tasks
  - Mid models (Sonnet, GPT-4o) for standard tasks
  - Premium models (Opus, o1) for complex reasoning

Reports savings to the user after each message.
"""

import re
import logging
from .database import get_db

logger = logging.getLogger("MyTeam360.smart_routing")

# Cost per 1K tokens (input/output) — approximate as of early 2026
MODEL_COSTS = {
    # Anthropic
    "claude-haiku-4-5-20251001":    {"input": 0.001,  "output": 0.005,  "tier": "cheap"},
    "claude-sonnet-4-5-20250929":   {"input": 0.003,  "output": 0.015,  "tier": "mid"},
    "claude-opus-4-5-20250929":     {"input": 0.015,  "output": 0.075,  "tier": "premium"},
    # OpenAI
    "gpt-4o-mini":                  {"input": 0.00015,"output": 0.0006, "tier": "cheap"},
    "gpt-4o":                       {"input": 0.0025, "output": 0.01,   "tier": "mid"},
    "gpt-4-turbo":                  {"input": 0.01,   "output": 0.03,   "tier": "mid"},
    "o1-mini":                      {"input": 0.003,  "output": 0.012,  "tier": "mid"},
    "o1-preview":                   {"input": 0.015,  "output": 0.06,   "tier": "premium"},
    "o3-mini":                      {"input": 0.0011, "output": 0.0044, "tier": "cheap"},
    # Grok
    "grok-2-latest":                {"input": 0.002,  "output": 0.01,   "tier": "mid"},
    "grok-3":                       {"input": 0.003,  "output": 0.015,  "tier": "mid"},
    "grok-3-mini":                  {"input": 0.0003, "output": 0.0005, "tier": "cheap"},
    # Google
    "gemini-2.0-flash":             {"input": 0.0001, "output": 0.0004, "tier": "cheap"},
    "gemini-2.0-flash-lite":        {"input": 0.00005,"output": 0.0002, "tier": "cheap"},
    "gemini-1.5-pro":               {"input": 0.00125,"output": 0.005,  "tier": "mid"},
    # Mistral
    "mistral-large-latest":         {"input": 0.002,  "output": 0.006,  "tier": "mid"},
    "mistral-medium-latest":        {"input": 0.0027, "output": 0.0081, "tier": "mid"},
    "mistral-small-latest":         {"input": 0.0002, "output": 0.0006, "tier": "cheap"},
    "open-mistral-nemo":            {"input": 0.00015,"output": 0.00015,"tier": "cheap"},
    "codestral-latest":             {"input": 0.0003, "output": 0.0009, "tier": "cheap"},
    # DeepSeek
    "deepseek-chat":                {"input": 0.00014,"output": 0.00028,"tier": "cheap"},
    "deepseek-coder":               {"input": 0.00014,"output": 0.00028,"tier": "cheap"},
    "deepseek-reasoner":            {"input": 0.00055,"output": 0.00219,"tier": "mid"},
    # Cohere
    "command-r-plus":               {"input": 0.003,  "output": 0.015,  "tier": "mid"},
    "command-r":                    {"input": 0.0005, "output": 0.0015, "tier": "cheap"},
    "command-light":                {"input": 0.0003, "output": 0.0006, "tier": "cheap"},
    # Perplexity
    "sonar-pro":                    {"input": 0.003,  "output": 0.015,  "tier": "mid"},
    "sonar":                        {"input": 0.001,  "output": 0.001,  "tier": "cheap"},
    "sonar-reasoning-pro":          {"input": 0.002,  "output": 0.008,  "tier": "mid"},
    "sonar-reasoning":              {"input": 0.001,  "output": 0.005,  "tier": "cheap"},
    # Together / Fireworks / Groq (open model pricing varies by host)
    "meta-llama/Llama-3.1-405B-Instruct-Turbo": {"input": 0.005, "output": 0.015, "tier": "premium"},
    "meta-llama/Llama-3.1-70B-Instruct-Turbo":  {"input": 0.0009,"output": 0.0009,"tier": "cheap"},
    "meta-llama/Llama-3.1-8B-Instruct-Turbo":   {"input": 0.0002,"output": 0.0002,"tier": "cheap"},
    "llama-3.1-70b-versatile":      {"input": 0.00059,"output": 0.00079,"tier": "cheap"},
    "llama-3.1-8b-instant":         {"input": 0.00005,"output": 0.00008,"tier": "cheap"},
    "llama-3.3-70b-versatile":      {"input": 0.00059,"output": 0.00079,"tier": "cheap"},
    "mixtral-8x7b-32768":           {"input": 0.00024,"output": 0.00024,"tier": "cheap"},
    "Qwen/Qwen2.5-72B-Instruct-Turbo": {"input": 0.0012,"output": 0.0012,"tier": "mid"},
    "deepseek-ai/DeepSeek-V3":      {"input": 0.0008, "output": 0.002,  "tier": "cheap"},
}

# Preferred models per provider per tier
PROVIDER_TIERS = {
    "anthropic": {
        "cheap":   "claude-haiku-4-5-20251001",
        "mid":     "claude-sonnet-4-5-20250929",
        "premium": "claude-opus-4-5-20250929",
    },
    "openai": {
        "cheap":   "gpt-4o-mini",
        "mid":     "gpt-4o",
        "premium": "o1-preview",
    },
    "xai": {
        "cheap":   "grok-3-mini",
        "mid":     "grok-2-latest",
        "premium": "grok-3",
    },
    "google": {
        "cheap":   "gemini-2.0-flash",
        "mid":     "gemini-1.5-pro",
        "premium": "gemini-1.5-pro",
    },
    "mistral": {
        "cheap":   "mistral-small-latest",
        "mid":     "mistral-large-latest",
        "premium": "mistral-large-latest",
    },
    "deepseek": {
        "cheap":   "deepseek-chat",
        "mid":     "deepseek-reasoner",
        "premium": "deepseek-reasoner",
    },
    "cohere": {
        "cheap":   "command-light",
        "mid":     "command-r-plus",
        "premium": "command-r-plus",
    },
    "together": {
        "cheap":   "meta-llama/Llama-3.1-8B-Instruct-Turbo",
        "mid":     "meta-llama/Llama-3.1-70B-Instruct-Turbo",
        "premium": "meta-llama/Llama-3.1-405B-Instruct-Turbo",
    },
    "perplexity": {
        "cheap":   "sonar",
        "mid":     "sonar-pro",
        "premium": "sonar-reasoning-pro",
    },
    "fireworks": {
        "cheap":   "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "mid":     "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "premium": "accounts/fireworks/models/llama-v3p1-405b-instruct",
    },
    "groq": {
        "cheap":   "llama-3.1-8b-instant",
        "mid":     "llama-3.1-70b-versatile",
        "premium": "llama-3.3-70b-versatile",
    },
}

# Complexity signals
CODE_PATTERNS = re.compile(
    r'```|def |class |function |import |require\(|SELECT |CREATE |ALTER |'
    r'const |let |var |async |await |return |if\s*\(|for\s*\(|while\s*\(',
    re.IGNORECASE
)
REASONING_WORDS = {
    "analyze", "compare", "contrast", "evaluate", "synthesize", "critique",
    "prove", "derive", "explain why", "reasoning", "logic", "argument",
    "implications", "trade-offs", "tradeoffs", "advantages", "disadvantages",
    "pros and cons", "debate", "philosophy", "ethical", "moral", "paradox",
    "mathematical", "equation", "theorem", "proof", "algorithm",
}
SIMPLE_PATTERNS = {
    "translate", "summarize", "list", "define", "what is", "who is",
    "when was", "how do i", "convert", "format", "rewrite", "fix grammar",
    "spell check", "hello", "hi", "thanks", "yes", "no", "ok",
}


class SmartRouter:
    """Analyzes prompt complexity and selects optimal model."""

    def analyze_complexity(self, message: str, conversation_length: int = 0,
                           has_files: bool = False) -> dict:
        """Score the complexity of a user message."""
        text = message.lower().strip()
        word_count = len(text.split())
        signals = []
        score = 0.0

        # Length-based scoring
        if word_count < 15:
            score -= 0.2
            signals.append("short_message")
        elif word_count > 200:
            score += 0.3
            signals.append("long_message")

        # Code detection
        code_matches = len(CODE_PATTERNS.findall(message))
        if code_matches > 3:
            score += 0.4
            signals.append("heavy_code")
        elif code_matches > 0:
            score += 0.2
            signals.append("some_code")

        # Reasoning detection
        reasoning_count = sum(1 for w in REASONING_WORDS if w in text)
        if reasoning_count >= 3:
            score += 0.5
            signals.append("deep_reasoning")
        elif reasoning_count >= 1:
            score += 0.2
            signals.append("some_reasoning")

        # Simple task detection
        simple_count = sum(1 for w in SIMPLE_PATTERNS if w in text)
        if simple_count >= 1 and word_count < 30:
            score -= 0.3
            signals.append("simple_task")

        # Multi-step detection
        if any(w in text for w in ["step 1", "first,", "then,", "finally,", "step-by-step"]):
            score += 0.2
            signals.append("multi_step")

        # File/document context
        if has_files:
            score += 0.2
            signals.append("has_files")

        # Conversation depth
        if conversation_length > 10:
            score += 0.1
            signals.append("deep_conversation")

        # Clamp
        score = max(-1.0, min(1.0, score))

        # Map to tier
        if score <= -0.1:
            tier = "cheap"
        elif score >= 0.4:
            tier = "premium"
        else:
            tier = "mid"

        return {
            "score": round(score, 3),
            "tier": tier,
            "signals": signals,
            "word_count": word_count,
        }

    def select_model(self, message: str, provider: str = "anthropic",
                     conversation_length: int = 0, has_files: bool = False,
                     budget_mode: str = "balanced") -> dict:
        """Select the optimal model for a message.

        budget_mode: 'economy' always picks cheap, 'balanced' uses analysis,
                     'performance' always picks premium
        """
        analysis = self.analyze_complexity(message, conversation_length, has_files)

        if budget_mode == "economy":
            tier = "cheap"
        elif budget_mode == "performance":
            tier = "premium"
        else:
            tier = analysis["tier"]

        provider_models = PROVIDER_TIERS.get(provider, PROVIDER_TIERS["anthropic"])
        model = provider_models.get(tier, provider_models["mid"])
        cost_info = MODEL_COSTS.get(model, {})

        # Calculate estimated savings vs premium
        premium_model = provider_models.get("premium", model)
        premium_cost = MODEL_COSTS.get(premium_model, {})
        if cost_info and premium_cost and tier != "premium":
            savings_pct = round((1 - cost_info.get("input", 0) / max(premium_cost.get("input", 1), 0.0001)) * 100)
        else:
            savings_pct = 0

        return {
            "model": model,
            "tier": tier,
            "provider": provider,
            "analysis": analysis,
            "cost_per_1k_input": cost_info.get("input", 0),
            "cost_per_1k_output": cost_info.get("output", 0),
            "savings_vs_premium_pct": max(0, savings_pct),
            "budget_mode": budget_mode,
        }

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a specific model and token count."""
        costs = MODEL_COSTS.get(model, {"input": 0.003, "output": 0.015})
        return (input_tokens / 1000 * costs["input"]) + (output_tokens / 1000 * costs["output"])

    def get_model_costs(self) -> dict:
        """Return all model costs for UI display."""
        return MODEL_COSTS
