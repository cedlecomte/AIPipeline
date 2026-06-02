"""Redis-based message bus for inter-agent communication."""

import asyncio
import json
from typing import Any, Callable

import redis.asyncio as redis
import structlog
from redis.asyncio.client import PubSub

from shared.models.messages import AgentMessage, AgentType

logger = structlog.get_logger()


class MessageBus:
    """Async Redis-based message bus for agent communication."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: redis.Redis | None = None
        self.pubsub: PubSub | None = None
        self.subscriptions: dict[str, Callable] = {}
        self._raw_channels: set[str] = set()
        self._running = False

    async def connect(self) -> None:
        """Establish connection to Redis."""
        self.client = redis.from_url(self.redis_url, decode_responses=True)
        self.pubsub = self.client.pubsub()
        logger.info("message_bus.connected", redis_url=self.redis_url)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        self._running = False
        if self.pubsub:
            await self.pubsub.close()
        if self.client:
            await self.client.close()
        logger.info("message_bus.disconnected")

    async def publish(self, message: AgentMessage) -> None:
        """Publish a message to an agent's channel."""
        if not self.client:
            raise RuntimeError("Message bus not connected")

        channel = f"agent:{message.to_agent.value}"
        message_json = message.model_dump_json()

        await self.client.publish(channel, message_json)

        logger.info(
            "message_bus.published",
            from_agent=message.from_agent.value,
            to_agent=message.to_agent.value,
            message_type=message.message_type.value,
            task_id=message.task_id,
        )

    async def subscribe(
        self, agent_type: AgentType, handler: Callable[[AgentMessage], Any]
    ) -> None:
        """Subscribe to messages for a specific agent."""
        if not self.pubsub:
            raise RuntimeError("Message bus not connected")

        channel = f"agent:{agent_type.value}"
        await self.pubsub.subscribe(channel)
        self.subscriptions[channel] = handler

        logger.info("message_bus.subscribed", agent=agent_type.value, channel=channel)

    async def subscribe_channel(
        self, channel_name: str, handler: Callable
    ) -> None:
        """Subscribe to a raw channel name (for dynamic agents)."""
        if not self.pubsub:
            raise RuntimeError("Message bus not connected")

        await self.pubsub.subscribe(channel_name)
        self.subscriptions[channel_name] = handler
        self._raw_channels.add(channel_name)

        logger.info("message_bus.subscribed_channel", channel=channel_name)

    async def publish_to_channel(self, channel: str, message_json: str) -> None:
        """Publish raw JSON to a named channel."""
        if not self.client:
            raise RuntimeError("Message bus not connected")

        await self.client.publish(channel, message_json)
        logger.info("message_bus.published_to_channel", channel=channel)

    async def start_listening(self) -> None:
        """Start listening for messages (blocking)."""
        if not self.pubsub:
            raise RuntimeError("Message bus not connected")

        self._running = True
        logger.info("message_bus.listening_started")

        try:
            while self._running:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )

                if message and message["type"] == "message":
                    channel = message["channel"]
                    data = message["data"]

                    if channel in self.subscriptions:
                        try:
                            handler = self.subscriptions[channel]

                            if channel in self._raw_channels:
                                asyncio.create_task(handler(data))
                            else:
                                agent_message = AgentMessage.model_validate_json(data)
                                asyncio.create_task(handler(agent_message))

                        except Exception as e:
                            logger.error(
                                "message_bus.handler_error",
                                channel=channel,
                                error=str(e),
                                exc_info=True,
                            )

        except asyncio.CancelledError:
            logger.info("message_bus.listening_cancelled")
            raise

    async def set_task_status(self, task_id: str, status: dict[str, Any]) -> None:
        """Store task status in Redis for dashboard tracking."""
        if not self.client:
            raise RuntimeError("Message bus not connected")

        key = f"task:{task_id}:status"
        await self.client.set(key, json.dumps(status))
        await self.client.expire(key, 86400)  # 24 hour TTL

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Retrieve task status from Redis."""
        if not self.client:
            raise RuntimeError("Message bus not connected")

        key = f"task:{task_id}:status"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def append_log(self, correlation_id: str, entry: dict[str, Any]) -> None:
        """Append a log entry for a pipeline run."""
        if not self.client:
            raise RuntimeError("Message bus not connected")
        key = f"pipeline_log:{correlation_id}"
        await self.client.rpush(key, json.dumps(entry, default=str))
        await self.client.expire(key, 86400 * 7)

    async def get_logs(self, correlation_id: str) -> list[dict[str, Any]]:
        """Get all log entries for a pipeline run."""
        if not self.client:
            raise RuntimeError("Message bus not connected")
        key = f"pipeline_log:{correlation_id}"
        entries = await self.client.lrange(key, 0, -1)
        return [json.loads(e) for e in entries]

    async def store_artifact(self, task_id: str, artifact_type: str, data: Any) -> None:
        """Store an artifact in Redis."""
        if not self.client:
            raise RuntimeError("Message bus not connected")

        key = f"artifact:{task_id}:{artifact_type}"
        await self.client.set(key, json.dumps(data))
        await self.client.expire(key, 86400)  # 24 hour TTL

    async def get_artifact(self, task_id: str, artifact_type: str) -> Any | None:
        """Retrieve an artifact from Redis."""
        if not self.client:
            raise RuntimeError("Message bus not connected")

        key = f"artifact:{task_id}:{artifact_type}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
