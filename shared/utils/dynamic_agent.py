"""Dynamic agent that loads its configuration from Redis."""

import asyncio
import json
from datetime import datetime
from typing import Any

import structlog

from shared.models.definitions import AgentDefinition
from shared.models.messages import DynamicAgentMessage, MessageType, TaskStatus
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus

logger = structlog.get_logger()


class DynamicAgent:
    """An agent whose prompt, tools, and config are loaded from an AgentDefinition."""

    def __init__(
        self,
        agent_def: AgentDefinition,
        message_bus: MessageBus,
        claude_client: ClaudeClient,
    ):
        self.agent_def = agent_def
        self.slug = agent_def.slug
        self.message_bus = message_bus
        self.claude = claude_client
        self.logger = logger.bind(agent=self.slug)
        self._task: asyncio.Task | None = None

    async def get_system_prompt(self) -> str:
        """Build system prompt from definition + attached skills."""
        parts = [self.agent_def.system_prompt]

        for skill_id in self.agent_def.skill_ids:
            data = await self.message_bus.client.get(f"skill:{skill_id}")
            if data:
                from shared.models.definitions import SkillDefinition
                skill = SkillDefinition.model_validate_json(data)
                parts.append(f"\n\n---\n## Skill: {skill.name}\n{skill.content}")

        return "\n".join(parts)

    def get_tools(self) -> list[dict[str, Any]]:
        return self.agent_def.tools

    async def handle_message(self, raw_data: str) -> None:
        """Handle a raw message from Redis pub/sub."""
        try:
            msg = DynamicAgentMessage.model_validate_json(raw_data)

            self.logger.info(
                "dynamic_agent.message_received",
                from_agent=msg.from_agent,
                task_id=msg.task_id,
            )

            await self.message_bus.set_task_status(
                msg.task_id,
                {
                    "status": TaskStatus.IN_PROGRESS.value,
                    "current_agent": self.slug,
                    "timestamp": msg.timestamp.isoformat(),
                },
            )

            result = await self.process_task(msg)

            response = DynamicAgentMessage(
                message_type=MessageType.TASK_RESPONSE,
                from_agent=self.slug,
                to_agent=msg.from_agent,
                task_id=msg.task_id,
                correlation_id=msg.correlation_id,
                payload=result,
            )

            await self.message_bus.publish_to_channel(
                f"agent:{msg.from_agent}",
                response.model_dump_json(),
            )

            await self.message_bus.set_task_status(
                msg.task_id,
                {
                    "status": TaskStatus.COMPLETED.value,
                    "current_agent": self.slug,
                },
            )

            self.logger.info("dynamic_agent.task_completed", task_id=msg.task_id)

        except Exception as e:
            self.logger.error("dynamic_agent.error", error=str(e), exc_info=True)
            try:
                error_msg = DynamicAgentMessage(
                    message_type=MessageType.TASK_ERROR,
                    from_agent=self.slug,
                    to_agent=msg.from_agent,
                    task_id=msg.task_id,
                    correlation_id=msg.correlation_id,
                    payload={"error": str(e)},
                )
                await self.message_bus.publish_to_channel(
                    f"agent:{msg.from_agent}",
                    error_msg.model_dump_json(),
                )
            except Exception:
                pass

    def _get_workspace_tools(self, access: str) -> list[dict[str, Any]]:
        """Build workspace tool definitions based on access level."""
        tools = [
            {
                "name": "list_files",
                "description": "List files in the workspace repository",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Subdirectory to list (default: root)"}},
                },
            },
            {
                "name": "read_file",
                "description": "Read the contents of a file in the workspace",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "File path relative to workspace root"}},
                    "required": ["path"],
                },
            },
            {
                "name": "git_diff",
                "description": "Show all uncommitted changes in the workspace",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]
        if access == "readwrite":
            tools.extend([
                {
                    "name": "write_file",
                    "description": "Write content to a file in the workspace (creates directories as needed)",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path relative to workspace root"},
                            "content": {"type": "string", "description": "File content to write"},
                        },
                        "required": ["path", "content"],
                    },
                },
                {
                    "name": "git_commit",
                    "description": "Stage all changes and commit with a message",
                    "input_schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string", "description": "Commit message"}},
                        "required": ["message"],
                    },
                },
                {
                    "name": "run_command",
                    "description": "Run a shell command in the workspace directory (for tests, linting, etc.)",
                    "input_schema": {
                        "type": "object",
                        "properties": {"command": {"type": "string", "description": "Shell command to run"}},
                        "required": ["command"],
                    },
                },
            ])
        return tools

    async def _execute_tool(self, tool_name: str, tool_input: dict, ws: Any, access: str) -> str:
        """Execute a workspace tool and return the result."""
        if tool_name == "list_files":
            files = await ws.list_files(tool_input.get("path", "."))
            return "\n".join(files) if files else "(empty)"
        elif tool_name == "read_file":
            return await ws.read_file(tool_input["path"])
        elif tool_name == "git_diff":
            return await ws.diff()
        elif tool_name == "write_file" and access == "readwrite":
            await ws.write_file(tool_input["path"], tool_input["content"])
            return f"Written {len(tool_input['content'])} bytes to {tool_input['path']}"
        elif tool_name == "git_commit" and access == "readwrite":
            return await ws.commit(tool_input["message"])
        elif tool_name == "run_command" and access == "readwrite":
            return await ws.run_command(tool_input["command"])
        return f"Unknown or unauthorized tool: {tool_name}"

    async def process_task(self, message: DynamicAgentMessage) -> dict[str, Any]:
        """Process a task using the LLM, with optional workspace tool-use loop."""
        from shared.utils.workspace import WorkspaceManager

        system_prompt = await self.get_system_prompt()
        tools = list(self.get_tools())

        workspace_path = message.payload.get("workspace_path")
        workspace_access = message.payload.get("workspace_access", "none")
        ws = None

        if workspace_path and workspace_access in ("read", "readwrite"):
            ws = WorkspaceManager(message.correlation_id)
            tools.extend(self._get_workspace_tools(workspace_access))
            system_prompt += f"\n\nYou have access to a Git workspace at {workspace_path}. Use the workspace tools to read, write, and manage files."

        user_content = json.dumps(message.payload, default=str)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

        kwargs: dict[str, Any] = {}
        if self.agent_def.model:
            kwargs["model"] = self.agent_def.model
        if self.agent_def.effort in ("enabled", "disabled"):
            kwargs["thinking_mode"] = self.agent_def.effort

        await self.message_bus.append_log(message.correlation_id, {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "debug",
            "stage": self.slug,
            "message": f"Calling Claude (skills: {len(self.agent_def.skill_ids)}, tools: {len(tools)}, workspace: {workspace_access})",
            "data": {
                "model": self.agent_def.model,
                "max_tokens": self.agent_def.max_tokens,
                "system_prompt": system_prompt[:500] + ("..." if len(system_prompt) > 500 else ""),
                "user_message": user_content[:500] + ("..." if len(user_content) > 500 else ""),
                "tools_count": len(tools),
                "workspace_access": workspace_access,
            },
        })

        max_iterations = 20
        result_text = ""

        for iteration in range(max_iterations):
            response = await self.claude.create_message(
                messages=messages,
                system=system_prompt,
                tools=tools if tools else None,
                max_tokens=self.agent_def.max_tokens,
                **kwargs,
            )

            result_text = self.claude.extract_text(response)
            tool_calls = self.claude.extract_tool_calls(response)
            usage = response.usage.model_dump() if response.usage else {}

            if not tool_calls or not ws:
                thinking_text = self.claude.extract_thinking(response)
                await self.message_bus.append_log(message.correlation_id, {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": "debug",
                    "stage": self.slug,
                    "message": f"Claude responded ({usage.get('input_tokens', '?')} in / {usage.get('output_tokens', '?')} out, iteration {iteration + 1})",
                    "data": {
                        "response": result_text,
                        "thinking": thinking_text[:500] + ("..." if len(thinking_text) > 500 else "") if thinking_text else None,
                        "usage": usage,
                        "stop_reason": response.stop_reason,
                    },
                })
                break

            # Build assistant message with all content blocks
            assistant_content = []
            for block in response.content:
                if block.type == "thinking":
                    assistant_content.append({"type": "thinking", "thinking": block.thinking, "signature": block.signature})
                elif block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
            messages.append({"role": "assistant", "content": assistant_content})

            # Execute tools and build tool results
            tool_results = []
            for tc in tool_calls:
                await self.message_bus.append_log(message.correlation_id, {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": "debug",
                    "stage": self.slug,
                    "message": f"Tool call: {tc['name']}",
                    "data": {"input": tc["input"]},
                })
                try:
                    result = await self._execute_tool(tc["name"], tc["input"], ws, workspace_access)
                except Exception as e:
                    result = f"Error: {e}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": result[:10000],
                })
            messages.append({"role": "user", "content": tool_results})

        return {"result": result_text}

    async def start(self) -> None:
        """Subscribe to this agent's channel and start listening."""
        channel = f"agent:{self.slug}"

        async def raw_handler(data: str) -> None:
            asyncio.create_task(self.handle_message(data))

        await self.message_bus.subscribe_channel(channel, raw_handler)
        self.logger.info("dynamic_agent.started", channel=channel)

    async def stop(self) -> None:
        """Stop this agent."""
        self.logger.info("dynamic_agent.stopped")
