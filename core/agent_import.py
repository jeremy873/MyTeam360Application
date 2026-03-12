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
Agent Import — Sync external AI assistants into MyTeam360.

Supports:
  - OpenAI Assistants API (full sync: list, import, push updates)
  - Manual import (paste system prompt + config for any provider)
  - JSON import/export (portable agent configs)

Designed for migration: when OpenAI sunsets Assistants API (Aug 2026),
swap to Responses API without breaking the agent model.
"""

import json
import uuid
import logging
import urllib.request
import urllib.error
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.agent_import")


# ══════════════════════════════════════════════════════════════
# OPENAI ASSISTANTS API CLIENT
# ══════════════════════════════════════════════════════════════

class OpenAIAssistantsClient:
    """Lightweight client for OpenAI Assistants API v2."""

    BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _request(self, method: str, path: str, body: dict = None) -> dict:
        url = f"{self.BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2",
        }
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            logger.error(f"OpenAI API error {e.code}: {error_body}")
            raise RuntimeError(f"OpenAI API error {e.code}: {error_body}")

    def list_assistants(self, limit: int = 100) -> list:
        """List all assistants on the user's OpenAI account."""
        assistants = []
        after = None
        while True:
            path = f"/assistants?limit={min(limit, 100)}&order=desc"
            if after:
                path += f"&after={after}"
            result = self._request("GET", path)
            data = result.get("data", [])
            assistants.extend(data)
            if not result.get("has_more") or not data:
                break
            after = data[-1]["id"]
            if len(assistants) >= limit:
                break
        return assistants

    def get_assistant(self, assistant_id: str) -> dict:
        """Get a single assistant by ID."""
        return self._request("GET", f"/assistants/{assistant_id}")

    def update_assistant(self, assistant_id: str, updates: dict) -> dict:
        """Push updates back to OpenAI."""
        return self._request("POST", f"/assistants/{assistant_id}", updates)

    def list_vector_stores(self, assistant_id: str) -> list:
        """Get vector store IDs attached to an assistant."""
        try:
            asst = self.get_assistant(assistant_id)
            tool_resources = asst.get("tool_resources", {})
            fs = tool_resources.get("file_search", {})
            return fs.get("vector_store_ids", [])
        except Exception:
            return []

    def list_files_in_vector_store(self, vector_store_id: str) -> list:
        """List files in a vector store."""
        try:
            result = self._request("GET", f"/vector_stores/{vector_store_id}/files?limit=100")
            return result.get("data", [])
        except Exception:
            return []


# ══════════════════════════════════════════════════════════════
# ASSISTANT → AGENT MAPPER
# ══════════════════════════════════════════════════════════════

def _map_openai_tools(tools: list) -> dict:
    """Map OpenAI tool types to a capabilities dict."""
    caps = {"code_interpreter": False, "file_search": False, "functions": []}
    for tool in (tools or []):
        t = tool.get("type", "")
        if t == "code_interpreter":
            caps["code_interpreter"] = True
        elif t == "file_search":
            caps["file_search"] = True
        elif t == "function":
            fn = tool.get("function", {})
            caps["functions"].append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            })
    return caps


def _assistant_to_agent_data(asst: dict) -> dict:
    """Convert an OpenAI assistant object to MyTeam360 agent create data."""
    tools = _map_openai_tools(asst.get("tools", []))

    # Build additional context from tool info
    context_parts = []
    if tools["code_interpreter"]:
        context_parts.append("[HAS CODE INTERPRETER — can execute Python code]")
    if tools["file_search"]:
        context_parts.append("[HAS FILE SEARCH — can search attached documents]")
    for fn in tools["functions"]:
        context_parts.append(f"[FUNCTION: {fn['name']} — {fn.get('description', '')}]")

    # Map model names
    model = asst.get("model", "gpt-4o")

    # Pick an icon based on the name/description
    icon = _pick_icon(asst.get("name", ""), asst.get("description", ""))

    return {
        "name": asst.get("name") or "Untitled Assistant",
        "role": "Imported GPT",
        "icon": icon,
        "color": "#10b981",  # Green for imported
        "description": asst.get("description") or "",
        "instructions": asst.get("instructions") or "",
        "additional_context": "\n".join(context_parts) if context_parts else "",
        "provider": "openai",
        "model": model,
        "temperature": asst.get("temperature", 1.0),
        "max_tokens": 4096,
        "source": "openai_assistant",
        "source_id": asst.get("id", ""),
        "source_provider": "openai",
        "source_meta": json.dumps({
            "tools": tools,
            "tool_resources": asst.get("tool_resources", {}),
            "metadata": asst.get("metadata", {}),
            "top_p": asst.get("top_p", 1.0),
            "response_format": asst.get("response_format", "auto"),
            "created_at": asst.get("created_at"),
        }),
    }


def _pick_icon(name: str, desc: str) -> str:
    """Pick an emoji icon based on assistant name/description."""
    text = f"{name} {desc}".lower()
    mappings = [
        (["code", "program", "develop", "debug", "engineer"], "💻"),
        (["write", "blog", "content", "copy", "author"], "✍️"),
        (["research", "analy", "data", "science"], "🔬"),
        (["design", "creative", "art", "visual"], "🎨"),
        (["market", "seo", "social", "brand"], "📈"),
        (["sales", "crm", "lead", "prospect"], "💼"),
        (["support", "help", "customer", "service"], "🎧"),
        (["finance", "account", "budget", "tax"], "📊"),
        (["legal", "contract", "compliance"], "⚖️"),
        (["hr", "recruit", "hiring", "people"], "👥"),
        (["teach", "tutor", "learn", "education"], "📚"),
        (["translate", "language", "localize"], "🌍"),
        (["email", "communicate", "message"], "📧"),
        (["plan", "strateg", "consult", "advise"], "♟️"),
        (["edit", "review", "proofread", "grammar"], "📝"),
        (["math", "calcul", "formula"], "🔢"),
        (["health", "medical", "wellness"], "🏥"),
        (["cook", "recipe", "food"], "🍳"),
        (["travel", "trip", "itinerary"], "✈️"),
        (["music", "audio", "sound"], "🎵"),
    ]
    for keywords, icon in mappings:
        if any(k in text for k in keywords):
            return icon
    return "🤖"


# ══════════════════════════════════════════════════════════════
# AGENT IMPORT MANAGER
# ══════════════════════════════════════════════════════════════

class AgentImportManager:
    """Handles importing, syncing, and exporting agents from external sources."""

    def __init__(self, agent_manager=None):
        self.agents = agent_manager

    # ── OpenAI Import ──

    def list_openai_assistants(self, api_key: str) -> list:
        """List all assistants from the user's OpenAI account."""
        client = OpenAIAssistantsClient(api_key)
        assistants = client.list_assistants()

        # Check which ones are already imported
        imported_ids = self._get_imported_source_ids("openai_assistant")

        result = []
        for asst in assistants:
            mapped = _assistant_to_agent_data(asst)
            mapped["already_imported"] = asst["id"] in imported_ids
            mapped["openai_id"] = asst["id"]
            mapped["openai_created_at"] = asst.get("created_at")
            result.append(mapped)
        return result

    def import_openai_assistant(self, api_key: str, assistant_id: str,
                                 owner_id: str, overrides: dict = None) -> dict:
        """Import a single OpenAI assistant as a MyTeam360 agent."""
        # Check if already imported
        existing = self._find_by_source("openai_assistant", assistant_id)
        if existing:
            raise ValueError(f"Assistant '{assistant_id}' is already imported as agent '{existing['id']}'")

        client = OpenAIAssistantsClient(api_key)
        asst = client.get_assistant(assistant_id)
        data = _assistant_to_agent_data(asst)

        # Apply user overrides
        if overrides:
            for k in ("name", "icon", "color", "description", "provider", "model", "temperature"):
                if k in overrides:
                    data[k] = overrides[k]

        # Create the agent
        agent = self._create_imported_agent(data, owner_id)

        logger.info(f"Imported OpenAI assistant '{asst.get('name')}' ({assistant_id}) → agent '{agent['id']}'")
        return agent

    def import_all_openai(self, api_key: str, owner_id: str,
                           skip_existing: bool = True) -> dict:
        """Import all OpenAI assistants at once."""
        client = OpenAIAssistantsClient(api_key)
        assistants = client.list_assistants()
        imported_ids = self._get_imported_source_ids("openai_assistant")

        results = {"imported": [], "skipped": [], "errors": []}
        for asst in assistants:
            aid = asst["id"]
            name = asst.get("name", "Untitled")
            if skip_existing and aid in imported_ids:
                results["skipped"].append({"id": aid, "name": name, "reason": "already imported"})
                continue
            try:
                agent = self.import_openai_assistant(api_key, aid, owner_id)
                results["imported"].append({"id": agent["id"], "name": agent["name"], "source_id": aid})
            except Exception as e:
                results["errors"].append({"id": aid, "name": name, "error": str(e)})

        return results

    def sync_openai_assistant(self, api_key: str, agent_id: str,
                               direction: str = "pull") -> dict:
        """Sync an imported agent with its OpenAI source.

        direction: 'pull' = update local from OpenAI
                   'push' = update OpenAI from local
                   'both' = pull then check for conflicts
        """
        agent = self._get_agent(agent_id)
        if not agent or agent.get("source") != "openai_assistant":
            raise ValueError("Agent is not an imported OpenAI assistant")

        source_id = agent.get("source_id")
        if not source_id:
            raise ValueError("Agent has no source_id")

        client = OpenAIAssistantsClient(api_key)

        if direction == "pull":
            return self._sync_pull(client, agent)
        elif direction == "push":
            return self._sync_push(client, agent)
        else:
            raise ValueError(f"Unknown sync direction: {direction}")

    def _sync_pull(self, client: OpenAIAssistantsClient, agent: dict) -> dict:
        """Pull changes from OpenAI into local agent."""
        asst = client.get_assistant(agent["source_id"])
        data = _assistant_to_agent_data(asst)
        changes = {}

        # Compare and track what changed
        for field in ("name", "description", "instructions", "model", "temperature"):
            remote_val = data.get(field)
            local_val = agent.get(field)
            if remote_val and str(remote_val) != str(local_val):
                changes[field] = {"from": local_val, "to": remote_val}

        if changes:
            # Version the current instructions before overwriting
            self._version_prompt(agent["id"], agent.get("instructions", ""))

            # Apply remote changes
            update_data = {k: v["to"] for k, v in changes.items()}
            update_data["last_synced_at"] = datetime.now().isoformat()
            update_data["source_meta"] = data.get("source_meta", "{}")
            update_data["additional_context"] = data.get("additional_context", "")
            self._update_agent_fields(agent["id"], update_data)

        return {
            "agent_id": agent["id"],
            "source_id": agent["source_id"],
            "direction": "pull",
            "changes": changes,
            "synced_at": datetime.now().isoformat(),
        }

    def _sync_push(self, client: OpenAIAssistantsClient, agent: dict) -> dict:
        """Push local changes to OpenAI."""
        updates = {}
        if agent.get("name"):
            updates["name"] = agent["name"]
        if agent.get("description"):
            updates["description"] = agent["description"][:512]  # OpenAI limit
        if agent.get("instructions"):
            updates["instructions"] = agent["instructions"]
        if agent.get("model"):
            updates["model"] = agent["model"]
        if agent.get("temperature") is not None:
            updates["temperature"] = agent["temperature"]

        result = client.update_assistant(agent["source_id"], updates)

        # Update sync timestamp
        self._update_agent_fields(agent["id"], {
            "last_synced_at": datetime.now().isoformat()
        })

        return {
            "agent_id": agent["id"],
            "source_id": agent["source_id"],
            "direction": "push",
            "pushed_fields": list(updates.keys()),
            "synced_at": datetime.now().isoformat(),
        }

    # ── Manual Import ──

    def import_manual(self, data: dict, owner_id: str) -> dict:
        """Import an agent from a manual configuration (paste instructions + config)."""
        data.setdefault("source", "manual_import")
        data.setdefault("source_provider", data.get("provider", ""))
        data.setdefault("icon", _pick_icon(data.get("name", ""), data.get("description", "")))
        data.setdefault("color", "#6366f1")
        return self._create_imported_agent(data, owner_id)

    # ── JSON Export/Import ──

    def export_agent_json(self, agent_id: str) -> dict:
        """Export an agent as a portable JSON config."""
        agent = self._get_agent(agent_id)
        if not agent:
            raise ValueError("Agent not found")

        exportable = {
            "format": "myteam360_agent_v1",
            "exported_at": datetime.now().isoformat(),
            "agent": {
                "name": agent.get("name"),
                "role": agent.get("role"),
                "icon": agent.get("icon"),
                "color": agent.get("color"),
                "description": agent.get("description"),
                "instructions": agent.get("instructions"),
                "additional_context": agent.get("additional_context"),
                "provider": agent.get("provider"),
                "model": agent.get("model"),
                "temperature": agent.get("temperature"),
                "max_tokens": agent.get("max_tokens"),
                "use_user_profile": agent.get("use_user_profile"),
                "use_user_style": agent.get("use_user_style"),
                "use_knowledge_base": agent.get("use_knowledge_base"),
            },
        }
        # Include prompt history if exists
        try:
            history = json.loads(agent.get("prompt_history", "[]"))
            if history:
                exportable["prompt_history"] = history
        except Exception:
            pass

        return exportable

    def import_agent_json(self, config: dict, owner_id: str) -> dict:
        """Import an agent from a portable JSON config."""
        if config.get("format") != "myteam360_agent_v1":
            raise ValueError("Unknown agent config format")

        data = config.get("agent", {})
        data["source"] = "json_import"
        return self._create_imported_agent(data, owner_id)

    # ── Prompt Versioning ──

    def get_prompt_history(self, agent_id: str) -> list:
        """Get the version history of an agent's instructions."""
        with get_db() as db:
            row = db.execute(
                "SELECT prompt_history, prompt_version FROM agents WHERE id=?",
                (agent_id,)
            ).fetchone()
            if not row:
                return []
            try:
                return json.loads(row["prompt_history"] or "[]")
            except Exception:
                return []

    def rollback_prompt(self, agent_id: str, version: int) -> dict:
        """Rollback an agent's instructions to a specific version."""
        history = self.get_prompt_history(agent_id)
        target = next((h for h in history if h.get("version") == version), None)
        if not target:
            raise ValueError(f"Version {version} not found")

        agent = self._get_agent(agent_id)
        # Version current before rollback
        self._version_prompt(agent_id, agent.get("instructions", ""))

        # Apply the old version
        self._update_agent_fields(agent_id, {
            "instructions": target["instructions"],
        })

        return {
            "agent_id": agent_id,
            "rolled_back_to": version,
            "current_version": agent.get("prompt_version", 1) + 1,
        }

    def _version_prompt(self, agent_id: str, instructions: str):
        """Save current instructions as a version in history."""
        with get_db() as db:
            row = db.execute(
                "SELECT prompt_history, prompt_version FROM agents WHERE id=?",
                (agent_id,)
            ).fetchone()
            if not row:
                return

            try:
                history = json.loads(row["prompt_history"] or "[]")
            except Exception:
                history = []

            version = (row["prompt_version"] or 1)
            history.append({
                "version": version,
                "instructions": instructions,
                "saved_at": datetime.now().isoformat(),
            })

            # Keep last 50 versions
            history = history[-50:]

            db.execute(
                "UPDATE agents SET prompt_history=?, prompt_version=? WHERE id=?",
                (json.dumps(history), version + 1, agent_id)
            )

    # ── Sync Status ──

    def get_sync_status(self, owner_id: str = None) -> list:
        """Get sync status for all imported agents."""
        with get_db() as db:
            if owner_id:
                rows = db.execute(
                    "SELECT id, name, source, source_id, source_provider, last_synced_at, sync_enabled "
                    "FROM agents WHERE source != 'local' AND owner_id=?",
                    (owner_id,)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT id, name, source, source_id, source_provider, last_synced_at, sync_enabled "
                    "FROM agents WHERE source != 'local'"
                ).fetchall()
            return [dict(r) for r in rows]

    def toggle_sync(self, agent_id: str, enabled: bool) -> dict:
        """Enable/disable auto-sync for an imported agent."""
        with get_db() as db:
            db.execute(
                "UPDATE agents SET sync_enabled=? WHERE id=?",
                (int(enabled), agent_id)
            )
        return {"agent_id": agent_id, "sync_enabled": enabled}

    # ── Internal Helpers ──

    def _create_imported_agent(self, data: dict, owner_id: str) -> dict:
        """Create an agent with import metadata."""
        agent_id = f"agt_{uuid.uuid4().hex[:10]}"
        now = datetime.now().isoformat()

        with get_db() as db:
            db.execute("""
                INSERT INTO agents (
                    id, owner_id, name, role, icon, color, description, instructions,
                    additional_context, provider, model, temperature, max_tokens,
                    use_user_profile, use_user_style, use_knowledge_base, knowledge_folders,
                    shared, source, source_id, source_provider, source_meta,
                    last_synced_at, sync_enabled, prompt_version, prompt_history
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                agent_id, owner_id,
                data.get("name", "Imported Agent"),
                data.get("role", ""),
                data.get("icon", "🤖"),
                data.get("color", "#10b981"),
                data.get("description", ""),
                data.get("instructions", ""),
                data.get("additional_context", ""),
                data.get("provider", ""),
                data.get("model", ""),
                data.get("temperature", 0.7),
                data.get("max_tokens", 4096),
                int(data.get("use_user_profile", True)),
                int(data.get("use_user_style", True)),
                int(data.get("use_knowledge_base", False)),
                json.dumps(data.get("knowledge_folders", [])),
                int(data.get("shared", False)),
                data.get("source", "local"),
                data.get("source_id", ""),
                data.get("source_provider", ""),
                data.get("source_meta", "{}"),
                now,
                int(data.get("sync_enabled", True)),
                1,
                "[]",
            ))

        return self._get_agent(agent_id)

    def _get_agent(self, agent_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            return dict(row) if row else None

    def _find_by_source(self, source: str, source_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM agents WHERE source=? AND source_id=?",
                (source, source_id)
            ).fetchone()
            return dict(row) if row else None

    def _get_imported_source_ids(self, source: str) -> set:
        with get_db() as db:
            rows = db.execute(
                "SELECT source_id FROM agents WHERE source=?", (source,)
            ).fetchall()
            return {r["source_id"] for r in rows}

    def _update_agent_fields(self, agent_id: str, fields: dict):
        if not fields:
            return
        fields["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [agent_id]
        with get_db() as db:
            db.execute(f"UPDATE agents SET {sets} WHERE id=?", vals)
