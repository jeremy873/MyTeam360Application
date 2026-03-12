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
Messaging Hub — Unified interface for all chat platforms.
Slack, Telegram, SMS/iMessage, Discord, and Web all route through this layer.
Handles user identification, agent routing, command parsing, and response delivery.
"""

import re
import json
import logging
from .database import get_db

logger = logging.getLogger("MyTeam360.messaging")

# Command patterns
COMMANDS = {
    r"^/agent\s+(.+)": "switch_agent",
    r"^/switch\s+(.+)": "switch_agent",
    r"^/workflow\s+(.+)": "run_workflow",
    r"^/agents?\s*$": "list_agents",
    r"^/workflows?\s*$": "list_workflows",
    r"^/help\s*$": "help",
    r"^/new\s*$": "new_conversation",
    r"^/search\s+(.+)": "search",
    r"^/status\s*$": "status",
}


class MessagingHub:
    """Routes messages from any platform through agents and back."""

    def __init__(self, user_manager, agent_manager, conversation_manager,
                 knowledge_base=None, workflow_engine=None):
        self.users = user_manager
        self.agents = agent_manager
        self.conversations = conversation_manager
        self.kb = knowledge_base
        self.workflows = workflow_engine

    def resolve_user(self, platform: str, platform_user_id: str) -> dict | None:
        """Find the platform user's account. Returns None if not linked."""
        with get_db() as db:
            link = db.execute("""
                SELECT user_id FROM platform_links
                WHERE platform=? AND platform_user_id=?
            """, (platform, platform_user_id)).fetchone()
            if link:
                return self.users.get_user(link["user_id"])
        return None

    def link_user(self, platform: str, platform_user_id: str, user_id: str,
                  display_name: str = "") -> bool:
        """Link a platform identity to a user account."""
        import uuid
        link_id = f"lnk_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO platform_links (id, user_id, platform, platform_user_id, display_name)
                VALUES (?, ?, ?, ?, ?)
            """, (link_id, user_id, platform, platform_user_id, display_name))
        return True

    def process_message(self, platform: str, platform_user_id: str,
                        text: str, files: list = None) -> dict:
        """
        Main entry point for all platforms.
        Returns: {"text": str, "sources": list, "error": str|None}
        """
        # 1. Resolve user
        user = self.resolve_user(platform, platform_user_id)
        if not user:
            return {
                "text": "You're not linked to an account yet. Please visit the web app to connect your account, or reply with your API token to link: /link <your-token>",
                "sources": [], "error": "unlinked"
            }

        user_id = user["id"]

        # 2. Check budget
        budget = self.users.check_budget(user_id)
        if not budget["allowed"]:
            return {"text": f"You've reached your monthly AI budget (${budget['limit']:.2f}). Contact your admin to increase the limit.",
                    "sources": [], "error": "budget_exceeded"}

        # 3. Parse commands
        cmd = self._parse_command(text)
        if cmd:
            return self._handle_command(cmd, user_id, platform)

        # 4. Get or create conversation
        conv = self.conversations.get_or_create_platform_conversation(user_id, platform)

        # 5. Get active agent
        agent_id = conv.get("agent_id")
        if not agent_id:
            # Use user's default agent preference or first available
            pref = self.users.get_preferences(user_id)
            agent_id = pref.get("default_agent")
            if not agent_id:
                agents = self.agents.list_agents(user_id=user_id)
                if agents:
                    agent_id = agents[0]["id"]

        if not agent_id:
            return {"text": "No agents configured. Create one in the web app first.",
                    "sources": [], "error": "no_agent"}

        # 6. Save user message
        self.conversations.add_message(conv["id"], "user", text)

        # 7. Build context
        context_messages = self.conversations.get_context_messages(conv["id"], max_messages=20)

        # 8. Get KB context if agent uses it
        kb_context = ""
        agent = self.agents.get_agent(agent_id)
        if agent and agent.get("use_knowledge_base") and self.kb:
            folder_ids = json.loads(agent.get("knowledge_folders", "[]")) if agent.get("knowledge_folders") else None
            kb_context = self.kb.get_context_for_agent(text, user_id, folder_ids=folder_ids)

        # 9. Run agent
        try:
            result = self.agents.run_agent(
                agent_id, text, user_id=user_id,
                context=kb_context,
                conversation_messages=context_messages
            )
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return {"text": f"Error running agent: {str(e)}", "sources": [], "error": "agent_error"}

        # 10. Save assistant message
        sources = result.get("sources", [])
        self.conversations.add_message(
            conv["id"], "assistant", result.get("text", ""),
            agent_id=agent_id,
            provider=result.get("provider"),
            model=result.get("model"),
            tokens_used=result.get("usage", {}).get("total_tokens", 0),
            cost_estimate=result.get("usage", {}).get("cost", 0),
            sources=sources
        )

        # 11. Log usage
        usage = result.get("usage", {})
        self.users.log_usage(
            user_id, agent_id, result.get("provider", ""), result.get("model", ""),
            usage.get("input_tokens", 0), usage.get("output_tokens", 0),
            usage.get("cost", 0)
        )

        return {
            "text": result.get("text", ""),
            "sources": sources,
            "error": None
        }

    def _parse_command(self, text: str) -> dict | None:
        text = text.strip()
        # Check for /link command
        link_match = re.match(r"^/link\s+(.+)", text)
        if link_match:
            return {"action": "link", "arg": link_match.group(1).strip()}

        for pattern, action in COMMANDS.items():
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                return {"action": action, "arg": match.group(1) if match.lastindex else ""}
        return None

    def _handle_command(self, cmd: dict, user_id: str, platform: str) -> dict:
        action = cmd["action"]
        arg = cmd.get("arg", "")

        if action == "switch_agent":
            agents = self.agents.list_agents(user_id=user_id)
            match = None
            for a in agents:
                if a["name"].lower() == arg.lower() or a["id"] == arg:
                    match = a
                    break
            if not match:
                # Fuzzy match
                for a in agents:
                    if arg.lower() in a["name"].lower():
                        match = a
                        break
            if match:
                conv = self.conversations.get_or_create_platform_conversation(user_id, platform)
                self.conversations.update_conversation(conv["id"], {"agent_id": match["id"]})
                return {"text": f"Switched to {match['icon']} {match['name']}", "sources": [], "error": None}
            return {"text": f"Agent '{arg}' not found. Use /agents to see available agents.", "sources": [], "error": None}

        elif action == "list_agents":
            agents = self.agents.list_agents(user_id=user_id)
            if not agents:
                return {"text": "No agents configured yet.", "sources": [], "error": None}
            lines = ["Your agents:"]
            for a in agents:
                lines.append(f"  {a['icon']} {a['name']} — {a.get('provider', 'default')}")
            lines.append("\nSwitch with: /agent <name>")
            return {"text": "\n".join(lines), "sources": [], "error": None}

        elif action == "list_workflows":
            if not self.workflows:
                return {"text": "Workflows not available.", "sources": [], "error": None}
            wfs = self.workflows.list_workflows(user_id=user_id)
            if not wfs:
                return {"text": "No workflows configured.", "sources": [], "error": None}
            lines = ["Your workflows:"]
            for w in wfs:
                lines.append(f"  {w.get('icon','⚡')} {w['name']}")
            lines.append("\nRun with: /workflow <name> <input>")
            return {"text": "\n".join(lines), "sources": [], "error": None}

        elif action == "new_conversation":
            conv = self.conversations.create_conversation(user_id, platform=platform)
            return {"text": "Started a new conversation.", "sources": [], "error": None}

        elif action == "search":
            results = self.conversations.search(user_id, arg, limit=5)
            if not results:
                return {"text": f"No results for '{arg}'.", "sources": [], "error": None}
            lines = [f"Search results for '{arg}':"]
            for r in results:
                preview = r["content"][:100] + "..." if len(r["content"]) > 100 else r["content"]
                lines.append(f"  [{r['conversation_title']}] {preview}")
            return {"text": "\n".join(lines), "sources": [], "error": None}

        elif action == "status":
            budget = self.users.check_budget(user_id)
            usage = self.users.get_monthly_usage(user_id)
            return {"text": f"Budget: ${budget['used']:.2f} / ${budget['limit']:.2f} ({budget['pct']}%)\nRequests this month: {usage['requests']}",
                    "sources": [], "error": None}

        elif action == "help":
            return {"text": (
                "Commands:\n"
                "  /agents — List your agents\n"
                "  /agent <name> — Switch to an agent\n"
                "  /workflows — List workflows\n"
                "  /workflow <name> <input> — Run a workflow\n"
                "  /new — Start fresh conversation\n"
                "  /search <query> — Search past chats\n"
                "  /status — Check usage and budget\n"
                "  /help — Show this message"
            ), "sources": [], "error": None}

        return {"text": "Unknown command. Try /help", "sources": [], "error": None}
