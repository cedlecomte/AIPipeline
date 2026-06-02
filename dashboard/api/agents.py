"""CRUD API for agent definitions."""

import json
import re
import uuid
from datetime import datetime
from typing import Any

import redis.asyncio as redis_lib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.models.definitions import AgentDefinition, PluginConfig

router = APIRouter(prefix="/api/agents", tags=["agents"])

_redis: redis_lib.Redis | None = None


def init_redis(client: redis_lib.Redis) -> None:
    global _redis
    _redis = client


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    skill_ids: list[str] = []
    tools: list[dict[str, Any]] = []
    plugins: list[PluginConfig] = []
    model: str = "claude-sonnet-4-5@20250929"
    max_tokens: int = 16000
    effort: str = "enabled"


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    skill_ids: list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    plugins: list[PluginConfig] | None = None
    model: str | None = None
    max_tokens: int | None = None
    effort: str | None = None


@router.get("")
async def list_agents() -> list[dict]:
    agent_ids = await _redis.smembers("agent_defs:index")
    agents = []
    for aid in agent_ids:
        data = await _redis.get(f"agent_def:{aid}")
        if data:
            agent = AgentDefinition.model_validate_json(data)
            agents.append({
                "agent_id": agent.agent_id,
                "name": agent.name,
                "slug": agent.slug,
                "description": agent.description,
                "model": agent.model,
                "is_builtin": agent.is_builtin,
                "skill_ids": agent.skill_ids,
                "updated_at": agent.updated_at.isoformat(),
            })
    return agents


@router.post("", status_code=201)
async def create_agent(body: AgentCreate) -> dict:
    agent = AgentDefinition(
        agent_id=str(uuid.uuid4()),
        name=body.name,
        slug=_slugify(body.name),
        description=body.description,
        system_prompt=body.system_prompt,
        skill_ids=body.skill_ids,
        tools=body.tools,
        plugins=body.plugins,
        model=body.model,
        max_tokens=body.max_tokens,
        effort=body.effort,
    )
    await _redis.set(f"agent_def:{agent.agent_id}", agent.model_dump_json())
    await _redis.set(f"agent_def:slug:{agent.slug}", agent.agent_id)
    await _redis.sadd("agent_defs:index", agent.agent_id)

    await _redis.publish("control:agent_defs", json.dumps({
        "action": "create", "agent_id": agent.agent_id,
    }))

    return agent.model_dump(mode="json")


@router.get("/{agent_id}/prompt-preview")
async def preview_agent_prompt(agent_id: str) -> dict:
    """Preview the full assembled prompt including skills."""
    data = await _redis.get(f"agent_def:{agent_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = AgentDefinition.model_validate_json(data)
    parts = [agent.system_prompt]
    skills_loaded = []

    for skill_id in agent.skill_ids:
        skill_data = await _redis.get(f"skill:{skill_id}")
        if skill_data:
            from shared.models.definitions import SkillDefinition
            skill = SkillDefinition.model_validate_json(skill_data)
            parts.append(f"\n\n---\n## Skill: {skill.name}\n{skill.content}")
            skills_loaded.append({"skill_id": skill.skill_id, "name": skill.name, "chars": len(skill.content)})

    full_prompt = "\n".join(parts)
    return {
        "agent_name": agent.name,
        "model": agent.model,
        "skills_count": len(skills_loaded),
        "skills_loaded": skills_loaded,
        "full_prompt": full_prompt,
        "prompt_length": len(full_prompt),
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    data = await _redis.get(f"agent_def:{agent_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentDefinition.model_validate_json(data).model_dump(mode="json")


@router.put("/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate) -> dict:
    data = await _redis.get(f"agent_def:{agent_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = AgentDefinition.model_validate_json(data)
    if agent.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot modify builtin agent")

    old_slug = agent.slug
    updates = body.model_dump(exclude_none=True)
    if "name" in updates:
        updates["slug"] = _slugify(updates["name"])
    updates["updated_at"] = datetime.utcnow()

    updated = agent.model_copy(update=updates)
    await _redis.set(f"agent_def:{agent_id}", updated.model_dump_json())

    if updated.slug != old_slug:
        await _redis.delete(f"agent_def:slug:{old_slug}")
        await _redis.set(f"agent_def:slug:{updated.slug}", agent_id)

    await _redis.publish("control:agent_defs", json.dumps({
        "action": "update", "agent_id": agent_id,
    }))

    return updated.model_dump(mode="json")


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str) -> None:
    data = await _redis.get(f"agent_def:{agent_id}")
    if data:
        agent = AgentDefinition.model_validate_json(data)
        if agent.is_builtin:
            raise HTTPException(status_code=403, detail="Cannot delete builtin agent")
        await _redis.delete(f"agent_def:slug:{agent.slug}")

    await _redis.delete(f"agent_def:{agent_id}")
    await _redis.srem("agent_defs:index", agent_id)

    await _redis.publish("control:agent_defs", json.dumps({
        "action": "delete", "agent_id": agent_id,
    }))


@router.post("/seed-builtins")
async def seed_builtins() -> dict:
    """Seed the builtin agents from the existing Python classes into Redis."""
    from agents.architect.agent import ArchitectAgent
    from agents.certification.agent import CertificationAgent
    from agents.code_reviewer.agent import CodeReviewerAgent
    from agents.developer.agent import DeveloperAgent
    from agents.jira_integration.agent import JiraIntegrationAgent
    from agents.release.agent import ReleaseAgent
    from agents.tester.agent import TesterAgent
    from shared.utils.claude_client import ClaudeClient
    from shared.utils.message_bus import MessageBus

    mb = MessageBus("redis://localhost")
    cc = ClaudeClient()

    builtin_classes = [
        ("jira_integration", "Jira Integration", JiraIntegrationAgent),
        ("architect", "Architect", ArchitectAgent),
        ("developer", "Developer", DeveloperAgent),
        ("tester", "Tester", TesterAgent),
        ("code_reviewer", "Code Reviewer", CodeReviewerAgent),
        ("release", "Release", ReleaseAgent),
        ("certification", "Certification", CertificationAgent),
    ]

    seeded = []
    for slug, name, cls in builtin_classes:
        existing_id = await _redis.get(f"agent_def:slug:{slug}")
        if existing_id:
            seeded.append({"slug": slug, "status": "already_exists"})
            continue

        instance = cls(mb, cc)
        agent = AgentDefinition(
            agent_id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            description=f"Builtin {name} agent",
            system_prompt=instance.get_system_prompt(),
            tools=instance.get_tools(),
            model="claude-opus-4-7",
            is_builtin=True,
        )
        await _redis.set(f"agent_def:{agent.agent_id}", agent.model_dump_json())
        await _redis.set(f"agent_def:slug:{slug}", agent.agent_id)
        await _redis.sadd("agent_defs:index", agent.agent_id)
        seeded.append({"slug": slug, "status": "created", "agent_id": agent.agent_id})

    return {"seeded": seeded}
