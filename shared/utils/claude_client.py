"""Claude API client with VertexAI authentication — async streaming."""

from typing import Any

import structlog
from anthropic import AsyncAnthropicVertex
from config.settings import settings

logger = structlog.get_logger()


class ClaudeClient:
    """Wrapper for Claude API via VertexAI with async streaming."""

    def __init__(self):
        self.client = AsyncAnthropicVertex(
            project_id=settings.anthropic_vertex_project_id,
            region=settings.cloud_ml_region,
        )

        logger.info(
            "claude_client.initialized",
            project=settings.anthropic_vertex_project_id,
            region=settings.cloud_ml_region,
            model=settings.agent_model,
        )

    async def create_message(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        thinking: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a message using Claude via VertexAI with async streaming."""
        params: dict[str, Any] = {
            "model": settings.agent_model,
            "max_tokens": max_tokens or settings.agent_max_tokens,
            "messages": messages,
        }

        if system:
            params["system"] = system

        if tools:
            params["tools"] = tools

        if thinking:
            params["thinking"] = thinking
        else:
            params["thinking"] = {"type": "enabled", "budget_tokens": min(params["max_tokens"] // 2, 10000)}

        params.update(kwargs)

        # If the caller passed thinking_mode="disabled", override
        thinking_mode = params.pop("thinking_mode", None)
        if thinking_mode == "disabled":
            params["thinking"] = {"type": "disabled"}

        logger.debug("claude_client.create_message", model=params.get("model"))

        try:
            async with self.client.messages.stream(**params) as stream:
                response = await stream.get_final_message()

            logger.info(
                "claude_client.response_received",
                usage=response.usage.model_dump() if response.usage else None,
                stop_reason=response.stop_reason,
            )
            return response

        except Exception as e:
            logger.error("claude_client.error", error=str(e), exc_info=True)
            raise

    def extract_text(self, response: Any) -> str:
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts)

    def extract_thinking(self, response: Any) -> str:
        thinking_parts = []
        for block in response.content:
            if block.type == "thinking":
                thinking_parts.append(block.thinking)
        return "\n".join(thinking_parts)

    def extract_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        tool_calls = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        return tool_calls
