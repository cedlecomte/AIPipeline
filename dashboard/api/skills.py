"""CRUD API for skill definitions."""

import json
import re
import uuid
from datetime import datetime

import redis.asyncio as redis_lib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.models.definitions import SkillDefinition

router = APIRouter(prefix="/api/skills", tags=["skills"])

_redis: redis_lib.Redis | None = None


def init_redis(client: redis_lib.Redis) -> None:
    global _redis
    _redis = client


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    content: str = ""
    tags: list[str] = []


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    tags: list[str] | None = None


@router.get("")
async def list_skills() -> list[dict]:
    skill_ids = await _redis.smembers("skills:index")
    skills = []
    for sid in skill_ids:
        data = await _redis.get(f"skill:{sid}")
        if data:
            skill = SkillDefinition.model_validate_json(data)
            skills.append({
                "skill_id": skill.skill_id,
                "name": skill.name,
                "slug": skill.slug,
                "description": skill.description,
                "tags": skill.tags,
                "updated_at": skill.updated_at.isoformat(),
            })
    return skills


@router.post("", status_code=201)
async def create_skill(body: SkillCreate) -> dict:
    skill = SkillDefinition(
        skill_id=str(uuid.uuid4()),
        name=body.name,
        slug=_slugify(body.name),
        description=body.description,
        content=body.content,
        tags=body.tags,
    )
    await _redis.set(f"skill:{skill.skill_id}", skill.model_dump_json())
    await _redis.sadd("skills:index", skill.skill_id)
    return skill.model_dump(mode="json")


@router.get("/{skill_id}")
async def get_skill(skill_id: str) -> dict:
    data = await _redis.get(f"skill:{skill_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillDefinition.model_validate_json(data).model_dump(mode="json")


@router.put("/{skill_id}")
async def update_skill(skill_id: str, body: SkillUpdate) -> dict:
    data = await _redis.get(f"skill:{skill_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill = SkillDefinition.model_validate_json(data)
    updates = body.model_dump(exclude_none=True)
    if "name" in updates:
        updates["slug"] = _slugify(updates["name"])
    updates["updated_at"] = datetime.utcnow()

    updated = skill.model_copy(update=updates)
    await _redis.set(f"skill:{skill_id}", updated.model_dump_json())
    return updated.model_dump(mode="json")


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str) -> None:
    await _redis.delete(f"skill:{skill_id}")
    await _redis.srem("skills:index", skill_id)
