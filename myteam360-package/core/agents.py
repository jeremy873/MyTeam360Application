"""
Agents — Multi-user agent system with per-agent provider assignment,
knowledge base integration, and shared/private visibility.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from .database import get_db

logger = logging.getLogger("MyTeam360.agents")

STARTER_TEMPLATES = [
    {"id":"tpl_rfp_reviewer","name":"RFP Reviewer","role":"RFP Analyst","icon":"🔍","color":"#f59e0b",
     "provider":"anthropic","temperature":0.3,
     "description":"Analyzes RFPs to extract requirements, deadlines, and red flags",
     "instructions":"You are an expert RFP Reviewer. Analyze documents and extract:\n- Key requirements (mandatory vs optional)\n- Deadlines and milestones\n- Evaluation criteria and scoring\n- Red flags, ambiguities, or unrealistic expectations\n- Budget constraints or pricing guidance\n\nBe thorough but organized. Flag anything needing clarification."},
    {"id":"tpl_rfp_writer","name":"RFP Writer","role":"Proposal Writer","icon":"✍️","color":"#3b82f6",
     "provider":"openai","temperature":0.5,
     "description":"Writes compelling, compliant RFP responses",
     "instructions":"You are a senior Proposal Writer. Given requirements and context:\n- Write persuasive, compliant responses\n- Address every requirement point-by-point\n- Highlight differentiators and value propositions\n- Include relevant experience and metrics\n\nBe confident and specific. Never make unsupported claims."},
    {"id":"tpl_editor","name":"Editor","role":"Content Editor","icon":"📝","color":"#10b981",
     "provider":"anthropic","temperature":0.2,
     "description":"Polishes content for grammar, clarity, tone, and consistency",
     "instructions":"You are a meticulous Editor. Review and improve:\n- Grammar, spelling, punctuation\n- Clarity and readability\n- Consistent tone and voice\n- Logical flow\n- Tighten verbose language\n\nProvide edited version then summary of changes."},
    {"id":"tpl_researcher","name":"Researcher","role":"Research Analyst","icon":"🔬","color":"#ef4444",
     "provider":"","temperature":0.4,
     "description":"Gathers background research, data, and competitive intelligence",
     "instructions":"You are a Research Analyst. Gather and synthesize:\n- Relevant background information\n- Statistics and data points\n- Competitive intelligence\n- Industry trends\n- Supporting evidence\n\nCite sources when possible. Distinguish facts from estimates."},
    {"id":"tpl_strategist","name":"Strategist","role":"Strategic Advisor","icon":"♟️","color":"#ec4899",
     "provider":"anthropic","temperature":0.6,
     "description":"High-level strategic analysis and positioning",
     "instructions":"You are a Strategic Advisor. Analyze situations and provide:\n- SWOT analysis\n- Risk assessment\n- Opportunity identification\n- Competitive positioning\n- Actionable recommendations\n\nThink long-term. Consider multiple scenarios."},
    {"id":"tpl_qa_checker","name":"QA Checker","role":"Quality Assurance","icon":"✅","color":"#14b8a6",
     "provider":"anthropic","temperature":0.1,
     "description":"Final compliance and accuracy verification",
     "instructions":"You are a QA Specialist. Perform final checks:\n- Requirements compliance checklist\n- Factual accuracy verification\n- Formatting consistency\n- Missing sections or content gaps\n- Final PASS/FAIL assessment with issues list"},
    {"id":"tpl_email","name":"Email Drafter","role":"Communications","icon":"📧","color":"#6366f1",
     "provider":"anthropic","temperature":0.4,
     "description":"Writes professional emails in your voice",
     "instructions":"You are a professional Email Drafter. Write emails that are:\n- Clear and concise\n- Appropriate in tone for the audience\n- Action-oriented with clear next steps\n- Professional but personable\n\nMatch the user's writing style when a profile is available."},
]


class AgentManager:
    """Manages AI agents with multi-user ownership and shared visibility."""

    def __init__(self, provider_registry, user_manager=None):
        self.providers = provider_registry
        self.users = user_manager

    def list_templates(self) -> list:
        return STARTER_TEMPLATES

    def create_agent(self, data: dict, owner_id: str = None) -> dict:
        agent_id = f"agt_{uuid.uuid4().hex[:10]}"
        with get_db() as db:
            db.execute("""
                INSERT INTO agents (id, owner_id, name, role, icon, color, description, instructions,
                    additional_context, provider, model, temperature, max_tokens,
                    use_user_profile, use_user_style, use_knowledge_base, knowledge_folders, shared)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                agent_id, owner_id or "system",
                data.get("name", "New Agent"), data.get("role", ""),
                data.get("icon", "🤖"), data.get("color", "#7c5cfc"),
                data.get("description", ""), data.get("instructions", ""),
                data.get("additional_context", ""),
                data.get("provider", ""), data.get("model", ""),
                data.get("temperature", 0.7), data.get("max_tokens", 4096),
                int(data.get("use_user_profile", True)),
                int(data.get("use_user_style", True)),
                int(data.get("use_knowledge_base", False)),
                json.dumps(data.get("knowledge_folders", [])),
                int(data.get("shared", False)),
            ))
        return self.get_agent(agent_id)

    def create_from_template(self, template_id: str, owner_id: str = None,
                             overrides: dict = None) -> dict:
        tpl = next((t for t in STARTER_TEMPLATES if t["id"] == template_id), None)
        if not tpl:
            raise ValueError(f"Template not found: {template_id}")
        data = {k: v for k, v in tpl.items() if k != "id"}
        if overrides:
            data.update(overrides)
        return self.create_agent(data, owner_id=owner_id)

    def get_agent(self, agent_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["knowledge_folders"] = json.loads(d.get("knowledge_folders", "[]"))
            except Exception:
                d["knowledge_folders"] = []
            return d

    def list_agents(self, user_id: str = None) -> list:
        with get_db() as db:
            if user_id:
                rows = db.execute("""
                    SELECT * FROM agents WHERE owner_id=? OR shared=1
                    ORDER BY shared ASC, name ASC
                """, (user_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM agents ORDER BY name").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["knowledge_folders"] = json.loads(d.get("knowledge_folders", "[]"))
                except Exception:
                    d["knowledge_folders"] = []
                result.append(d)
            return result

    def update_agent(self, agent_id: str, data: dict) -> dict | None:
        allowed = {"name","role","icon","color","description","instructions","additional_context",
                   "provider","model","temperature","max_tokens","use_user_profile","use_user_style",
                   "use_knowledge_base","knowledge_folders","shared"}
        updates = {}
        for k, v in data.items():
            if k in allowed:
                if k == "knowledge_folders":
                    updates[k] = json.dumps(v)
                elif k in ("use_user_profile","use_user_style","use_knowledge_base","shared"):
                    updates[k] = int(v)
                else:
                    updates[k] = v
        if not updates:
            return self.get_agent(agent_id)
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [agent_id]
        with get_db() as db:
            db.execute(f"UPDATE agents SET {sets} WHERE id=?", vals)
        return self.get_agent(agent_id)

    def delete_agent(self, agent_id: str) -> bool:
        with get_db() as db:
            return db.execute("DELETE FROM agents WHERE id=?", (agent_id,)).rowcount > 0

    def duplicate_agent(self, agent_id: str, new_name: str = "", owner_id: str = None) -> dict | None:
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        data = {k: v for k, v in agent.items() if k not in ("id", "run_count", "total_tokens_used", "created_at", "updated_at")}
        data["name"] = new_name or f"{agent['name']} (copy)"
        data["shared"] = False
        return self.create_agent(data, owner_id=owner_id or agent.get("owner_id"))

    # ── Execution ──

    def _build_system_prompt(self, agent: dict, user_id: str = None,
                             extra_context: str = "") -> str:
        parts = []
        if agent.get("instructions"):
            parts.append(agent["instructions"])
        if agent.get("additional_context"):
            parts.append(f"\n[ADDITIONAL CONTEXT]\n{agent['additional_context']}")

        # Inject user profile
        if user_id and self.users and agent.get("use_user_profile"):
            profile_ctx = self.users.get_profile_context(user_id)
            if profile_ctx:
                parts.append(f"\n{profile_ctx}")
        if user_id and self.users and agent.get("use_user_style"):
            style_ctx = self.users.get_style_context(user_id)
            if style_ctx:
                parts.append(f"\n[WRITING STYLE]\n{style_ctx}")

        if extra_context:
            parts.append(f"\n{extra_context}")
        return "\n\n".join(parts)

    def run_agent(self, agent_id: str, user_input: str, user_id: str = None,
                  context: str = "", conversation_messages: list = None) -> dict:
        agent = self.get_agent(agent_id)
        if not agent:
            return {"text": "Agent not found", "error": True}

        system_prompt = self._build_system_prompt(agent, user_id=user_id, extra_context=context)
        provider_name = agent.get("provider") or "anthropic"
        model = agent.get("model") or ""
        temp = agent.get("temperature", 0.7)
        max_tokens = agent.get("max_tokens", 4096)

        # Build messages
        messages = conversation_messages or []
        if not messages or messages[-1].get("content") != user_input:
            messages.append({"role": "user", "content": user_input})

        try:
            provider = self.providers.get_provider(provider_name)
            if not provider:
                # Try first available
                all_providers = self.providers.list_all()
                if all_providers:
                    provider = self.providers.get_provider(all_providers[0]["name"])
                if not provider:
                    return {"text": "No AI provider available", "error": True}

            result = provider.generate(
                messages=messages, system=system_prompt,
                model=model, temperature=temp, max_tokens=max_tokens
            )

            # Update run count
            with get_db() as db:
                db.execute("""
                    UPDATE agents SET run_count=run_count+1,
                    total_tokens_used=total_tokens_used+? WHERE id=?
                """, (result.get("usage", {}).get("total_tokens", 0), agent_id))

            return {
                "text": result.get("text", ""),
                "provider": provider_name,
                "model": result.get("model", model),
                "usage": result.get("usage", {}),
                "agent_id": agent_id,
                "agent_name": agent["name"],
                "agent_icon": agent["icon"],
                "sources": [],
            }
        except Exception as e:
            logger.error(f"Agent run error [{agent['name']}]: {e}")
            return {"text": f"Error: {str(e)}", "error": True}

    def run_agent_stream(self, agent_id: str, user_input: str, user_id: str = None,
                         context: str = "", conversation_messages: list = None):
        agent = self.get_agent(agent_id)
        if not agent:
            yield {"type": "error", "text": "Agent not found"}
            return

        system_prompt = self._build_system_prompt(agent, user_id=user_id, extra_context=context)
        provider_name = agent.get("provider") or "anthropic"
        model = agent.get("model") or ""
        temp = agent.get("temperature", 0.7)
        max_tokens = agent.get("max_tokens", 4096)

        messages = conversation_messages or []
        if not messages or messages[-1].get("content") != user_input:
            messages.append({"role": "user", "content": user_input})

        try:
            provider = self.providers.get_provider(provider_name)
            if not provider:
                all_providers = self.providers.list_all()
                if all_providers:
                    provider = self.providers.get_provider(all_providers[0]["name"])
            if not provider:
                yield {"type": "error", "text": "No provider"}
                return

            yield {"type": "start", "agent": agent["name"], "icon": agent["icon"], "provider": provider_name}

            if hasattr(provider, "generate_stream"):
                full_text = ""
                for chunk in provider.generate_stream(
                    messages=messages, system=system_prompt,
                    model=model, temperature=temp, max_tokens=max_tokens
                ):
                    if chunk.get("text"):
                        full_text += chunk["text"]
                        yield {"type": "chunk", "text": chunk["text"]}
                yield {"type": "done", "text": full_text, "provider": provider_name}
            else:
                result = provider.generate(
                    messages=messages, system=system_prompt,
                    model=model, temperature=temp, max_tokens=max_tokens
                )
                yield {"type": "done", "text": result.get("text", ""), "provider": provider_name}

            with get_db() as db:
                db.execute("UPDATE agents SET run_count=run_count+1 WHERE id=?", (agent_id,))

        except Exception as e:
            yield {"type": "error", "text": str(e)}
