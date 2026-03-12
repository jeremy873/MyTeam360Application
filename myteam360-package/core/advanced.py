"""
MyTeam360 - Advanced AI Features
Multi-model routing, prompt chains, agent-to-agent delegation, vision support.
"""

import os
import re
import json
import uuid
import time
import base64
import logging
from .database import get_db

logger = logging.getLogger("MyTeam360.advanced")


# ====================================================================
# MULTI-MODEL ROUTER
# ====================================================================

# Keywords that signal task complexity
COMPLEXITY_SIGNALS = {
    "simple": [
        "hello", "hi ", "hey", "thanks", "what is", "define", "who is",
        "translate", "summarize this", "tldr", "yes", "no", "ok",
    ],
    "code": [
        "code", "function", "class ", "debug", "error", "stack trace",
        "python", "javascript", "typescript", "sql", "api", "bug",
        "refactor", "implement", "algorithm", "regex", "script",
    ],
    "complex": [
        "analyze", "compare", "evaluate", "design", "architect",
        "strategy", "plan", "research", "investigate", "explain why",
        "pros and cons", "trade-off", "implications", "deep dive",
    ],
    "creative": [
        "write", "story", "poem", "creative", "imagine", "brainstorm",
        "draft", "compose", "generate ideas", "blog post", "article",
        "marketing copy", "slogan", "tagline", "narrative",
    ],
}


class ModelRouter:
    """Routes requests to optimal model based on task analysis."""

    def classify_task(self, message):
        """Classify the task type from the user message."""
        lower = message.lower().strip()
        scores = {"simple": 0, "code": 0, "complex": 0, "creative": 0}

        for category, keywords in COMPLEXITY_SIGNALS.items():
            for kw in keywords:
                if kw in lower:
                    scores[category] += 1

        # Length heuristic: short messages are likely simple
        if len(lower) < 30 and scores["code"] == 0:
            scores["simple"] += 2

        # Long messages with questions are likely complex
        if len(lower) > 200 and "?" in lower:
            scores["complex"] += 1

        # Code blocks
        if "```" in message or "def " in message or "function " in message:
            scores["code"] += 3

        best = max(scores, key=scores.get)
        confidence = scores[best] / max(sum(scores.values()), 1)
        return {"category": best, "confidence": round(confidence, 2), "scores": scores}

    def get_route(self, message, rule_id=None):
        """Get the optimal provider/model for a message."""
        classification = self.classify_task(message)
        category = classification["category"]

        with get_db() as db:
            if rule_id:
                rule = db.execute("SELECT * FROM routing_rules WHERE id=? AND is_active=1",
                                  (rule_id,)).fetchone()
            else:
                rule = db.execute("SELECT * FROM routing_rules WHERE is_active=1 ORDER BY created_at LIMIT 1"
                                  ).fetchone()

        if not rule:
            return {"provider": "", "model": "", "classification": classification, "routed": False}

        rules_list = json.loads(rule["rules"] or "[]")
        for r in rules_list:
            if r.get("match") == category:
                return {
                    "provider": r.get("provider", rule["fallback_provider"]),
                    "model": r.get("model", rule["fallback_model"]),
                    "max_tokens": r.get("max_tokens"),
                    "classification": classification,
                    "rule_name": rule["name"],
                    "routed": True,
                }

        return {
            "provider": rule["fallback_provider"],
            "model": rule["fallback_model"],
            "classification": classification,
            "rule_name": rule["name"],
            "routed": True,
        }

    def list_rules(self):
        with get_db() as db:
            rows = db.execute("SELECT * FROM routing_rules ORDER BY created_at").fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["rules"] = json.loads(d.get("rules") or "[]")
                results.append(d)
            return results

    def create_rule(self, data):
        rid = "route_" + uuid.uuid4().hex[:8]
        with get_db() as db:
            db.execute(
                "INSERT INTO routing_rules (id, name, description, strategy, rules,"
                " fallback_provider, fallback_model) VALUES (?,?,?,?,?,?,?)",
                (rid, data["name"], data.get("description", ""),
                 data.get("strategy", "auto"),
                 json.dumps(data.get("rules", [])),
                 data.get("fallback_provider", "anthropic"),
                 data.get("fallback_model", "")))
        return {"id": rid, "name": data["name"]}

    def update_rule(self, rule_id, data):
        with get_db() as db:
            sets = []
            vals = []
            for key in ["name", "description", "strategy", "fallback_provider",
                         "fallback_model", "is_active"]:
                if key in data:
                    sets.append("{}=?".format(key))
                    vals.append(data[key])
            if "rules" in data:
                sets.append("rules=?")
                vals.append(json.dumps(data["rules"]))
            if sets:
                vals.append(rule_id)
                db.execute("UPDATE routing_rules SET {} WHERE id=?".format(",".join(sets)), vals)
        return self.get_rule(rule_id)

    def get_rule(self, rule_id):
        with get_db() as db:
            r = db.execute("SELECT * FROM routing_rules WHERE id=?", (rule_id,)).fetchone()
            if r:
                d = dict(r)
                d["rules"] = json.loads(d.get("rules") or "[]")
                return d
        return None


# ====================================================================
# PROMPT CHAIN ENGINE
# ====================================================================

class PromptChainEngine:
    """Execute multi-step prompt chains with variable interpolation."""

    def __init__(self, agent_manager):
        self.agents = agent_manager

    def create_chain(self, data, owner_id):
        chain_id = "chain_" + uuid.uuid4().hex[:8]
        with get_db() as db:
            db.execute(
                "INSERT INTO prompt_chains (id, name, description, icon, owner_id, steps, variables)"
                " VALUES (?,?,?,?,?,?,?)",
                (chain_id, data["name"], data.get("description", ""),
                 data.get("icon", "🔗"), owner_id,
                 json.dumps(data.get("steps", [])),
                 json.dumps(data.get("variables", {}))))
        return self.get_chain(chain_id)

    def get_chain(self, chain_id):
        with get_db() as db:
            r = db.execute("SELECT * FROM prompt_chains WHERE id=?", (chain_id,)).fetchone()
            if r:
                d = dict(r)
                d["steps"] = json.loads(d.get("steps") or "[]")
                d["variables"] = json.loads(d.get("variables") or "{}")
                return d
        return None

    def list_chains(self, owner_id=None):
        with get_db() as db:
            if owner_id:
                rows = db.execute(
                    "SELECT * FROM prompt_chains WHERE owner_id=? ORDER BY created_at DESC",
                    (owner_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM prompt_chains ORDER BY created_at DESC").fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["steps"] = json.loads(d.get("steps") or "[]")
                d["variables"] = json.loads(d.get("variables") or "{}")
                results.append(d)
            return results

    def run_chain(self, chain_id, input_text="", variables=None, user_id=None):
        """
        Execute a prompt chain sequentially.
        Each step's output becomes available as {{step_N}} in subsequent steps.
        Returns: {steps: [{step, agent, prompt, output, duration, tokens}], total_duration, total_tokens}
        """
        chain = self.get_chain(chain_id)
        if not chain:
            return {"error": "Chain not found"}

        steps = chain["steps"]
        if not steps:
            return {"error": "Chain has no steps"}

        # Initialize variables
        ctx = dict(chain.get("variables") or {})
        if variables:
            ctx.update(variables)
        ctx["input"] = input_text

        results = []
        total_tokens = 0
        start_time = time.time()

        for i, step in enumerate(steps):
            step_start = time.time()
            agent_id = step.get("agent_id")
            prompt_template = step.get("prompt", "{{input}}")

            # Interpolate variables: {{var_name}} and {{step_N}}
            prompt = prompt_template
            for key, val in ctx.items():
                prompt = prompt.replace("{{" + str(key) + "}}", str(val))

            # Run the agent
            result = self.agents.run_agent(agent_id, prompt, user_id=user_id)

            output = result.get("text", "")
            tokens = result.get("usage", {}).get("total_tokens", 0)
            total_tokens += tokens
            duration = round(time.time() - step_start, 2)

            # Store output for next steps
            ctx["step_{}".format(i + 1)] = output
            ctx["last_output"] = output

            results.append({
                "step": i + 1,
                "name": step.get("name", "Step {}".format(i + 1)),
                "agent_id": agent_id,
                "agent_name": result.get("agent_name", ""),
                "prompt": prompt[:200],
                "output": output,
                "tokens": tokens,
                "model": result.get("model", ""),
                "duration": duration,
                "error": result.get("error", False),
            })

            # Stop on error if configured
            if result.get("error") and step.get("stop_on_error", True):
                break

            # Optional transform between steps
            if step.get("output_transform") == "first_line":
                ctx["step_{}".format(i + 1)] = output.split("\n")[0]
            elif step.get("output_transform") == "json":
                try:
                    ctx["step_{}".format(i + 1)] = json.dumps(json.loads(output))
                except Exception:
                    pass

        total_duration = round(time.time() - start_time, 2)

        # Update run count
        with get_db() as db:
            db.execute(
                "UPDATE prompt_chains SET run_count=run_count+1,"
                " avg_duration=((avg_duration*run_count)+?)/(run_count) WHERE id=?",
                (total_duration, chain_id))

        return {
            "chain_id": chain_id,
            "chain_name": chain["name"],
            "steps": results,
            "total_duration": total_duration,
            "total_tokens": total_tokens,
            "final_output": results[-1]["output"] if results else "",
        }

    def delete_chain(self, chain_id):
        with get_db() as db:
            db.execute("DELETE FROM prompt_chains WHERE id=?", (chain_id,))
        return True


# ====================================================================
# AGENT-TO-AGENT DELEGATION
# ====================================================================

class DelegationManager:
    """Allows agents to delegate subtasks to other agents."""

    DELEGATION_PATTERN = re.compile(
        r"\[DELEGATE:([a-zA-Z0-9_-]+)\](.*?)\[/DELEGATE\]", re.DOTALL
    )

    def __init__(self, agent_manager):
        self.agents = agent_manager

    def build_delegation_prompt(self, agent):
        """Add delegation instructions to agent system prompt if enabled."""
        if not agent.get("can_delegate"):
            return ""

        delegate_ids = json.loads(agent.get("delegate_agents") or "[]")
        if not delegate_ids:
            return ""

        # Look up delegate agent names
        delegates = []
        for did in delegate_ids:
            a = self.agents.get_agent(did)
            if a:
                delegates.append({"id": did, "name": a["name"], "role": a.get("role", "")})

        if not delegates:
            return ""

        lines = [
            "\n\n--- DELEGATION CAPABILITY ---",
            "You can delegate subtasks to specialist agents. To delegate, use this exact format:",
            "[DELEGATE:agent_id]your question or instruction to the other agent[/DELEGATE]",
            "",
            "Available agents for delegation:",
        ]
        for d in delegates:
            lines.append("- {} ({}): {}".format(d["id"], d["name"], d["role"]))

        lines.append("")
        lines.append("The delegated agent's response will be inserted in place of the DELEGATE block.")
        lines.append("Only delegate when another agent's expertise would genuinely help.")
        lines.append("--- END DELEGATION ---")

        return "\n".join(lines)

    def process_delegations(self, text, user_id=None, depth=0, max_depth=3):
        """
        Scan agent output for DELEGATE blocks and execute them.
        Returns the text with delegations resolved.
        """
        if depth >= max_depth:
            return text

        matches = list(self.DELEGATION_PATTERN.finditer(text))
        if not matches:
            return text

        result = text
        for match in reversed(matches):  # Reverse to preserve positions
            agent_id = match.group(1).strip()
            sub_prompt = match.group(2).strip()

            logger.info("Delegation depth={}: {} -> {}".format(depth, agent_id, sub_prompt[:80]))

            sub_result = self.agents.run_agent(agent_id, sub_prompt, user_id=user_id)
            sub_text = sub_result.get("text", "[Delegation failed]")

            # Recursively process sub-delegations
            sub_text = self.process_delegations(sub_text, user_id, depth + 1, max_depth)

            # Replace the DELEGATE block with the response
            header = "\n> **Delegated to {}** ({})\n".format(
                sub_result.get("agent_name", agent_id),
                sub_result.get("agent_icon", "🤖"))
            replacement = header + sub_text + "\n"
            result = result[:match.start()] + replacement + result[match.end():]

        return result


# ====================================================================
# VISION HANDLER
# ====================================================================

class VisionHandler:
    """Handle image uploads and build vision-capable messages."""

    SUPPORTED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    MAX_SIZE = 20 * 1024 * 1024  # 20MB

    def validate_image(self, data_url):
        """Validate a base64 data URL. Returns (media_type, base64_data) or None."""
        if not data_url or not data_url.startswith("data:"):
            return None

        try:
            header, b64data = data_url.split(",", 1)
            media_type = header.split(":")[1].split(";")[0]

            if media_type not in self.SUPPORTED_TYPES:
                return None

            raw = base64.b64decode(b64data)
            if len(raw) > self.MAX_SIZE:
                return None

            return (media_type, b64data)
        except Exception:
            return None

    def build_vision_message(self, text, image_data_urls):
        """
        Build a multimodal message content array for vision-capable models.
        Returns content suitable for Anthropic/OpenAI vision APIs.
        """
        content = []

        # Add images first
        for url in image_data_urls:
            validated = self.validate_image(url)
            if validated:
                media_type, b64data = validated
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64data,
                    }
                })

        # Add text
        if text:
            content.append({"type": "text", "text": text})

        return content

    def is_vision_model(self, model):
        """Check if a model supports vision/images."""
        vision_models = {
            "claude-opus-4-5-20250929", "claude-sonnet-4-5-20250929",
            "claude-sonnet-4-5-20250514", "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
            "grok-2",
        }
        return model in vision_models or not model  # Default models typically support vision

    def save_image(self, data_url, conversation_id):
        """Save image to uploads directory and return the file path."""
        validated = self.validate_image(data_url)
        if not validated:
            return None

        media_type, b64data = validated
        ext = media_type.split("/")[1]
        if ext == "jpeg":
            ext = "jpg"

        filename = "img_{}.{}".format(uuid.uuid4().hex[:12], ext)
        upload_dir = os.path.join("data", "uploads", conversation_id or "general")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)

        with open(filepath, "wb") as f:
            f.write(base64.b64decode(b64data))

        return "/" + filepath
