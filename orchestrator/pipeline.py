"""Orchestrator - Coordinates the entire agent pipeline."""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Any

import structlog

from config.settings import settings
from orchestrator.graph_router import GraphRouter
from shared.models.definitions import AgentDefinition, PipelineDefinition, PipelineNode
from shared.utils.workspace import WorkspaceManager
from shared.models.messages import (
    AgentMessage,
    AgentType,
    DynamicAgentMessage,
    MessageType,
    TaskStatus,
)
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus

logger = structlog.get_logger()


class PipelineOrchestrator:
    """Orchestrates the multi-agent Ansible development pipeline."""

    def __init__(self):
        """Initialize the orchestrator."""
        self.message_bus = MessageBus(settings.redis_url)
        self.claude = ClaudeClient()
        self.active_pipelines: dict[str, dict[str, Any]] = {}
        self.graph_routers: dict[str, GraphRouter] = {}
        self.logger = logger.bind(component="orchestrator")

    async def start_pipeline(self, jira_issue_key: str) -> str:
        """Start a new pipeline run for a Jira issue.

        Args:
            jira_issue_key: Jira issue identifier

        Returns:
            Correlation ID for tracking this pipeline run
        """
        correlation_id = str(uuid.uuid4())
        task_id = f"{jira_issue_key}-{correlation_id[:8]}"

        self.logger.info(
            "pipeline.starting",
            correlation_id=correlation_id,
            task_id=task_id,
            jira_issue=jira_issue_key,
        )

        # Store pipeline metadata
        self.active_pipelines[correlation_id] = {
            "correlation_id": correlation_id,
            "task_id": task_id,
            "jira_issue_key": jira_issue_key,
            "started_at": datetime.utcnow().isoformat(),
            "status": TaskStatus.IN_PROGRESS.value,
            "current_stage": AgentType.JIRA_INTEGRATION.value,
            "stages_completed": [],
        }

        await self.message_bus.set_task_status(
            task_id,
            {
                "status": TaskStatus.IN_PROGRESS.value,
                "stage": "jira_integration",
                "correlation_id": correlation_id,
                "started_at": datetime.utcnow().isoformat(),
            },
        )

        # Send initial message to Jira Integration Agent
        initial_message = AgentMessage(
            message_type=MessageType.TASK_REQUEST,
            from_agent=AgentType.ORCHESTRATOR,
            to_agent=AgentType.JIRA_INTEGRATION,
            task_id=task_id,
            correlation_id=correlation_id,
            payload={
                "issue_key": jira_issue_key,
            },
        )

        await self.message_bus.publish(initial_message)

        return correlation_id

    async def start_graph_pipeline(
        self, pipeline_def: PipelineDefinition, input_data: dict[str, Any]
    ) -> str:
        """Start a pipeline run from a visual pipeline definition."""
        correlation_id = str(uuid.uuid4())
        task_id = f"graph-{correlation_id[:8]}"

        router = GraphRouter(pipeline_def)
        self.graph_routers[correlation_id] = router

        # Find first agent nodes (skip trigger node)
        first_agents = router.get_first_agent_after_trigger()
        if not first_agents:
            raise ValueError("Pipeline has no agent nodes connected to the trigger")

        trigger_node = router.get_entry_node()
        trigger_config = trigger_node.config

        # Create workspace if trigger has repo config
        workspace_path = None
        repo_url = trigger_config.get("repo_url", "")
        branch = trigger_config.get("branch", "main") or "main"
        git_token_var = trigger_config.get("git_token_var", "")
        git_token = os.environ.get(git_token_var, "") if git_token_var else ""

        ws = WorkspaceManager(correlation_id)
        if repo_url or any(
            n.config.get("workspace_access") in ("read", "readwrite")
            for n in pipeline_def.nodes if n.node_type == "agent"
        ):
            workspace_path = await ws.create(
                repo_url=repo_url or None,
                branch=branch,
                git_token=git_token or None,
            )

        self.active_pipelines[correlation_id] = {
            "correlation_id": correlation_id,
            "task_id": task_id,
            "pipeline_id": pipeline_def.pipeline_id,
            "started_at": datetime.utcnow().isoformat(),
            "status": TaskStatus.IN_PROGRESS.value,
            "current_stage": "starting",
            "current_node_id": trigger_node.node_id,
            "stages_completed": ["trigger"],
            "workspace_path": workspace_path,
        }

        await self.message_bus.append_log(correlation_id, {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "info",
            "stage": "trigger",
            "message": f"Pipeline started (pipeline_id={pipeline_def.pipeline_id})"
                + (f", workspace: {workspace_path}" if workspace_path else ""),
            "data": input_data,
        })

        for node in first_agents:
            await self._dispatch_to_node(node, task_id, correlation_id, input_data)

        self.logger.info(
            "pipeline.graph_started",
            correlation_id=correlation_id,
            pipeline_id=pipeline_def.pipeline_id,
        )

        return correlation_id

    async def _dispatch_to_node(
        self, node: PipelineNode, task_id: str, correlation_id: str, payload: dict[str, Any]
    ) -> None:
        """Route to a node based on its type: condition, output, or agent."""
        pipeline = self.active_pipelines.get(correlation_id, {})
        router = self.graph_routers.get(correlation_id)

        if node.node_type == "condition":
            pipeline["current_stage"] = node.label or "condition"
            pipeline["current_node_id"] = node.node_id
            pipeline["stages_completed"].append(node.label or "condition")

            if not router:
                return
            next_nodes = router.evaluate_condition_node(node, payload)
            result_branch = "true" if next_nodes else "false"
            await self.message_bus.append_log(correlation_id, {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "info",
                "stage": node.label or "condition",
                "message": f"Condition evaluated: {result_branch}",
                "data": {"config": node.config, "branch": result_branch},
            })
            for next_node in next_nodes:
                await self._dispatch_to_node(next_node, task_id, correlation_id, payload)
            if not next_nodes:
                pipeline["status"] = TaskStatus.COMPLETED.value
                pipeline["completed_at"] = datetime.utcnow().isoformat()
                self.graph_routers.pop(correlation_id, None)
                await self.message_bus.append_log(correlation_id, {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": "warning",
                    "stage": "condition",
                    "message": "No matching branch — pipeline ended",
                })
            return

        if node.node_type == "output":
            from dashboard.api.pipelines import execute_output_node

            pipeline["current_stage"] = node.label or "output"
            pipeline["current_node_id"] = node.node_id
            pipeline["stages_completed"].append(node.label or "output")

            await self.message_bus.append_log(correlation_id, {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "info",
                "stage": node.label or "output",
                "message": f"Executing output node ({node.config.get('output_type', 'webhook')})",
            })

            await execute_output_node(node, {
                **payload,
                "correlation_id": correlation_id,
                "task_id": task_id,
            })

            pipeline["status"] = TaskStatus.COMPLETED.value
            pipeline["completed_at"] = datetime.utcnow().isoformat()
            self.graph_routers.pop(correlation_id, None)
            await self.message_bus.append_log(correlation_id, {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "info",
                "stage": "pipeline",
                "message": "Pipeline completed",
            })
            return

        agent_def = await self._load_agent_def(node.agent_id)
        if not agent_def:
            await self.message_bus.append_log(correlation_id, {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "error",
                "stage": "dispatch",
                "message": f"Agent not found: {node.agent_id}",
            })
            return

        pipeline["current_stage"] = agent_def.slug
        pipeline["current_node_id"] = node.node_id

        # Inject workspace access if configured on this node
        agent_payload = {**payload}
        workspace_access = node.config.get("workspace_access", "none")
        workspace_path = pipeline.get("workspace_path")

        if workspace_access in ("read", "readwrite") and workspace_path:
            agent_payload["workspace_path"] = workspace_path
            agent_payload["workspace_access"] = workspace_access

        await self.message_bus.append_log(correlation_id, {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "info",
            "stage": agent_def.slug,
            "message": f"Dispatching to agent: {agent_def.name}"
                + (f" (workspace: {workspace_access})" if workspace_access != "none" else ""),
        })

        msg = DynamicAgentMessage(
            message_type=MessageType.TASK_REQUEST,
            from_agent="orchestrator",
            to_agent=agent_def.slug,
            task_id=task_id,
            correlation_id=correlation_id,
            payload=agent_payload,
        )

        await self.message_bus.publish_to_channel(
            f"agent:{agent_def.slug}",
            msg.model_dump_json(),
        )

    async def _load_agent_def(self, agent_id: str) -> AgentDefinition | None:
        """Load an agent definition from Redis."""
        data = await self.message_bus.client.get(f"agent_def:{agent_id}")
        if data:
            return AgentDefinition.model_validate_json(data)
        return None

    async def handle_graph_response(self, raw_data: str) -> None:
        """Handle response for graph-based pipelines."""
        msg = DynamicAgentMessage.model_validate_json(raw_data)
        correlation_id = msg.correlation_id

        if correlation_id not in self.active_pipelines:
            return

        pipeline = self.active_pipelines[correlation_id]
        if "pipeline_id" not in pipeline:
            return

        pipeline["stages_completed"].append(msg.from_agent)

        if msg.message_type == MessageType.TASK_ERROR:
            pipeline["status"] = TaskStatus.FAILED.value
            pipeline["error"] = msg.payload.get("error")
            self.graph_routers.pop(correlation_id, None)
            await self.message_bus.append_log(correlation_id, {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "error",
                "stage": msg.from_agent,
                "message": f"Agent error: {msg.payload.get('error', 'unknown')}",
                "data": msg.payload,
            })
            return

        result_preview = msg.payload.get("result", "")
        if isinstance(result_preview, str) and len(result_preview) > 500:
            result_preview = result_preview[:500] + "..."

        await self.message_bus.append_log(correlation_id, {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "info",
            "stage": msg.from_agent,
            "message": f"Agent completed",
            "data": {"result": result_preview},
        })

        router = self.graph_routers.get(correlation_id)
        if not router:
            return

        current_node_id = pipeline.get("current_node_id")
        next_nodes = router.get_next_nodes(current_node_id, msg.payload)

        if next_nodes:
            for node in next_nodes:
                await self._dispatch_to_node(node, msg.task_id, correlation_id, msg.payload)
        else:
            pipeline["status"] = TaskStatus.COMPLETED.value
            pipeline["completed_at"] = datetime.utcnow().isoformat()
            self.graph_routers.pop(correlation_id, None)
            self.logger.info("pipeline.graph_completed", correlation_id=correlation_id)

    async def handle_agent_response(self, message: AgentMessage) -> None:
        """Handle response from an agent and route to next stage.

        Args:
            message: Response message from an agent
        """
        correlation_id = message.correlation_id

        if correlation_id not in self.active_pipelines:
            self.logger.warning("pipeline.unknown_correlation_id", correlation_id=correlation_id)
            return

        pipeline = self.active_pipelines[correlation_id]
        pipeline["stages_completed"].append(message.from_agent.value)

        self.logger.info(
            "pipeline.stage_completed",
            correlation_id=correlation_id,
            stage=message.from_agent.value,
            next_agent=message.payload.get("next_agent"),
        )

        # Check if pipeline should continue
        if message.message_type == MessageType.TASK_ERROR:
            pipeline["status"] = TaskStatus.FAILED.value
            pipeline["error"] = message.payload.get("error")
            self.logger.error("pipeline.failed", correlation_id=correlation_id)
            return

        # Route to next agent
        next_agent_str = message.payload.get("next_agent")

        if next_agent_str:
            next_agent = AgentType(next_agent_str)
            pipeline["current_stage"] = next_agent.value

            # Create message for next agent
            next_message = AgentMessage(
                message_type=MessageType.TASK_REQUEST,
                from_agent=AgentType.ORCHESTRATOR,
                to_agent=next_agent,
                task_id=message.task_id,
                correlation_id=correlation_id,
                payload=message.payload,
            )

            await self.message_bus.publish(next_message)

        else:
            # Pipeline complete
            pipeline["status"] = TaskStatus.COMPLETED.value
            pipeline["completed_at"] = datetime.utcnow().isoformat()

            await self.message_bus.set_task_status(
                message.task_id,
                {
                    "status": TaskStatus.COMPLETED.value,
                    "completed_at": datetime.utcnow().isoformat(),
                    "stages_completed": pipeline["stages_completed"],
                },
            )

            self.logger.info("pipeline.completed", correlation_id=correlation_id)

    async def run(self) -> None:
        """Run the orchestrator."""
        self.logger.info("orchestrator.starting")

        await self.message_bus.connect()

        # Subscribe to responses from builtin agents (legacy)
        await self.message_bus.subscribe(AgentType.ORCHESTRATOR, self.handle_agent_response)
        # Subscribe to responses from dynamic agents (graph-based)
        await self.message_bus.subscribe_channel("agent:orchestrator", self.handle_graph_response)

        # Start listening
        try:
            await self.message_bus.start_listening()
        except KeyboardInterrupt:
            self.logger.info("orchestrator.shutdown")
        finally:
            await self.message_bus.disconnect()


async def main() -> None:
    """Run the pipeline orchestrator."""
    orchestrator = PipelineOrchestrator()
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
