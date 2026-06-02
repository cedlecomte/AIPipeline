"""CRUD API for pipeline definitions, execution, and webhooks."""

import json
import uuid
from datetime import datetime
from typing import Any

import httpx
import redis.asyncio as redis_lib
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = structlog.get_logger()

from shared.models.definitions import PipelineDefinition, PipelineEdge, PipelineNode

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

_redis: redis_lib.Redis | None = None
_orchestrator = None


def init_redis(client: redis_lib.Redis) -> None:
    global _redis
    _redis = client


def init_orchestrator(orch) -> None:
    global _orchestrator
    _orchestrator = orch


class PipelineCreate(BaseModel):
    name: str
    description: str = ""
    nodes: list[PipelineNode] = []
    edges: list[PipelineEdge] = []
    entry_node_id: str = ""


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[PipelineNode] | None = None
    edges: list[PipelineEdge] | None = None
    entry_node_id: str | None = None


class PipelineExecuteRequest(BaseModel):
    input_data: dict[str, Any] = {}


@router.get("/definitions")
async def list_pipelines() -> list[dict]:
    pipeline_ids = await _redis.smembers("pipelines:index")
    pipelines = []
    for pid in pipeline_ids:
        data = await _redis.get(f"pipeline:{pid}")
        if data:
            p = PipelineDefinition.model_validate_json(data)
            pipelines.append({
                "pipeline_id": p.pipeline_id,
                "name": p.name,
                "description": p.description,
                "node_count": len(p.nodes),
                "edge_count": len(p.edges),
                "is_active": p.is_active,
                "updated_at": p.updated_at.isoformat(),
            })
    return pipelines


@router.post("/definitions", status_code=201)
async def create_pipeline(body: PipelineCreate) -> dict:
    pipeline = PipelineDefinition(
        pipeline_id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        nodes=body.nodes,
        edges=body.edges,
        entry_node_id=body.entry_node_id,
    )
    await _redis.set(f"pipeline:{pipeline.pipeline_id}", pipeline.model_dump_json())
    await _redis.sadd("pipelines:index", pipeline.pipeline_id)
    return pipeline.model_dump(mode="json")


@router.get("/definitions/{pipeline_id}")
async def get_pipeline(pipeline_id: str) -> dict:
    data = await _redis.get(f"pipeline:{pipeline_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return PipelineDefinition.model_validate_json(data).model_dump(mode="json")


@router.put("/definitions/{pipeline_id}")
async def update_pipeline(pipeline_id: str, body: PipelineUpdate) -> dict:
    data = await _redis.get(f"pipeline:{pipeline_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline = PipelineDefinition.model_validate_json(data)
    updates = body.model_dump(exclude_none=True)
    updates["updated_at"] = datetime.utcnow()

    updated = pipeline.model_copy(update=updates)
    await _redis.set(f"pipeline:{pipeline_id}", updated.model_dump_json())
    return updated.model_dump(mode="json")


@router.delete("/definitions/{pipeline_id}", status_code=204)
async def delete_pipeline(pipeline_id: str) -> None:
    await _redis.delete(f"pipeline:{pipeline_id}")
    await _redis.srem("pipelines:index", pipeline_id)


@router.post("/definitions/{pipeline_id}/activate")
async def activate_pipeline(pipeline_id: str) -> dict:
    data = await _redis.get(f"pipeline:{pipeline_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    current_active_id = await _redis.get("pipeline:active")
    if current_active_id:
        current_data = await _redis.get(f"pipeline:{current_active_id}")
        if current_data:
            current = PipelineDefinition.model_validate_json(current_data)
            deactivated = current.model_copy(update={"is_active": False})
            await _redis.set(f"pipeline:{current_active_id}", deactivated.model_dump_json())

    pipeline = PipelineDefinition.model_validate_json(data)
    activated = pipeline.model_copy(update={"is_active": True})
    await _redis.set(f"pipeline:{pipeline_id}", activated.model_dump_json())
    await _redis.set("pipeline:active", pipeline_id)

    return {"status": "activated", "pipeline_id": pipeline_id}


@router.post("/execute/{pipeline_id}")
async def execute_pipeline(pipeline_id: str, body: PipelineExecuteRequest) -> dict:
    data = await _redis.get(f"pipeline:{pipeline_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if not _orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    pipeline = PipelineDefinition.model_validate_json(data)
    correlation_id = await _orchestrator.start_graph_pipeline(pipeline, body.input_data)

    return {"correlation_id": correlation_id, "pipeline_id": pipeline_id, "status": "started"}


@router.get("/runs")
async def list_runs() -> list[dict]:
    if not _orchestrator:
        return []
    return list(_orchestrator.active_pipelines.values())


@router.get("/runs/{correlation_id}/logs")
async def get_run_logs(correlation_id: str) -> list[dict]:
    """Get all log entries for a pipeline run."""
    key = f"pipeline_log:{correlation_id}"
    entries = await _redis.lrange(key, 0, -1)
    return [json.loads(e) for e in entries]


@router.post("/webhook/{pipeline_id}")
async def webhook_trigger(pipeline_id: str, request: Request) -> dict:
    """Webhook entry point — triggers a pipeline from an external HTTP call."""
    data = await _redis.get(f"pipeline:{pipeline_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if not _orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    body = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
        except Exception:
            raw = (await request.body()).decode("utf-8", errors="replace")
            body = {"raw_text": raw}

    pipeline = PipelineDefinition.model_validate_json(data)
    correlation_id = await _orchestrator.start_graph_pipeline(pipeline, {
        "webhook_payload": body,
        "webhook_headers": dict(request.headers),
        "source": "webhook",
    })

    logger.info("pipeline.webhook_triggered", pipeline_id=pipeline_id, correlation_id=correlation_id)
    return {"correlation_id": correlation_id, "pipeline_id": pipeline_id, "status": "started"}


async def execute_output_node(node: PipelineNode, payload: dict[str, Any]) -> None:
    """Execute an output node action (webhook or Slack)."""
    config = node.config
    output_type = config.get("output_type", "webhook")

    if output_type == "webhook":
        url = config.get("url", "")
        if not url:
            logger.warning("output_node.no_url", node_id=node.node_id)
            return
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(url, json=payload)
        logger.info("output_node.webhook_sent", node_id=node.node_id, url=url)

    elif output_type == "slack":
        webhook_url = config.get("slack_webhook_url", "")
        if not webhook_url:
            logger.warning("output_node.no_slack_url", node_id=node.node_id)
            return
        channel = config.get("slack_channel", "")
        text = config.get("slack_message_template", "Pipeline completed: {{correlation_id}}")
        for key, val in payload.items():
            text = text.replace(f"{{{{{key}}}}}", str(val))
        slack_body: dict[str, Any] = {"text": text}
        if channel:
            slack_body["channel"] = channel
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(webhook_url, json=slack_body)
        logger.info("output_node.slack_sent", node_id=node.node_id)
