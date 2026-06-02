"""FastAPI dashboard for the agent pipeline."""

import asyncio
import os
from datetime import datetime
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config.settings import settings
from dashboard.api import agents as agents_api
from dashboard.api import pipelines as pipelines_api
from dashboard.api import skills as skills_api
from orchestrator.pipeline import PipelineOrchestrator
from shared.utils.message_bus import MessageBus

logger = structlog.get_logger()

app = FastAPI(title="Ansible Agent Pipeline Dashboard", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

message_bus: MessageBus | None = None
orchestrator: PipelineOrchestrator | None = None


class PipelineRequest(BaseModel):
    jira_issue_key: str


@app.on_event("startup")
async def startup() -> None:
    global message_bus, orchestrator

    message_bus = MessageBus(settings.redis_url)
    await message_bus.connect()

    orchestrator = PipelineOrchestrator()
    await orchestrator.message_bus.connect()
    await orchestrator.message_bus.subscribe_channel(
        "agent:orchestrator", orchestrator.handle_graph_response
    )
    asyncio.create_task(orchestrator.message_bus.start_listening())

    skills_api.init_redis(message_bus.client)
    agents_api.init_redis(message_bus.client)
    pipelines_api.init_redis(message_bus.client)
    pipelines_api.init_orchestrator(orchestrator)

    logger.info("dashboard.started", host=settings.dashboard_host, port=settings.dashboard_port)


@app.on_event("shutdown")
async def shutdown() -> None:
    if message_bus:
        await message_bus.disconnect()
    logger.info("dashboard.shutdown")


# Mount API routers
app.include_router(skills_api.router)
app.include_router(agents_api.router)
app.include_router(pipelines_api.router)


@app.post("/api/pipeline/start")
async def start_pipeline_endpoint(request: PipelineRequest) -> dict[str, str]:
    """Legacy endpoint: start pipeline with a Jira issue key."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    correlation_id = await orchestrator.start_pipeline(request.jira_issue_key)
    return {"correlation_id": correlation_id, "status": "started"}


@app.get("/api/pipeline/runs")
async def list_pipeline_runs() -> list[dict[str, Any]]:
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    return list(orchestrator.active_pipelines.values())


@app.get("/api/pipeline/{correlation_id}")
async def get_pipeline_status(correlation_id: str) -> dict[str, Any]:
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    if correlation_id not in orchestrator.active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return orchestrator.active_pipelines[correlation_id]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            if orchestrator:
                pipelines = list(orchestrator.active_pipelines.values())
                await websocket.send_json({
                    "event_type": "pipeline_update",
                    "timestamp": datetime.utcnow().isoformat(),
                    "payload": {"pipelines": pipelines},
                })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("websocket.disconnected")


# Serve Vue SPA if the dist directory exists (production build)
_frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    _index_html = os.path.join(_frontend_dist, "index.html")

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    # SPA fallback: serve index.html for all non-API routes
    @app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def spa_fallback(path: str) -> str:
        with open(_index_html) as f:
            return f.read()
else:
    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        return """<!DOCTYPE html>
<html><head><title>Ansible Agent Pipeline</title>
<style>
body { font-family: system-ui; margin: 40px auto; max-width: 600px; background: #1a1a2e; color: #eee; }
h1 { color: #667eea; } a { color: #667eea; }
.info { background: #16213e; padding: 20px; border-radius: 8px; margin: 20px 0; }
</style></head><body>
<h1>Ansible Agent Pipeline</h1>
<div class="info">
<p>The Vue frontend has not been built yet.</p>
<p>Run: <code>cd dashboard/frontend && npm install && npm run build</code></p>
<p>API endpoints are available at <a href="/docs">/docs</a></p>
</div>
</body></html>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level=settings.log_level.lower(),
    )
