"""Base agent class for all specialized agents."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import structlog

from shared.models.messages import AgentMessage, AgentType, MessageType, TaskStatus
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Base class for all agents in the pipeline."""

    def __init__(
        self,
        agent_type: AgentType,
        message_bus: MessageBus,
        claude_client: ClaudeClient,
    ):
        """Initialize the base agent.

        Args:
            agent_type: Type of this agent
            message_bus: Message bus for inter-agent communication
            claude_client: Claude API client
        """
        self.agent_type = agent_type
        self.message_bus = message_bus
        self.claude = claude_client
        self.logger = logger.bind(agent=agent_type.value)
        self._running = False

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent.

        Returns:
            System prompt string defining the agent's role and capabilities
        """
        pass

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """Return the tool definitions for this agent.

        Returns:
            List of tool definition dictionaries
        """
        pass

    @abstractmethod
    async def process_task(self, message: AgentMessage) -> dict[str, Any]:
        """Process a task message and return the result.

        Args:
            message: Incoming task message

        Returns:
            Result dictionary containing the agent's output
        """
        pass

    async def handle_message(self, message: AgentMessage) -> None:
        """Handle an incoming message.

        Args:
            message: Incoming message from another agent
        """
        self.logger.info(
            "message.received",
            from_agent=message.from_agent.value,
            message_type=message.message_type.value,
            task_id=message.task_id,
        )

        try:
            # Update task status to in_progress
            await self.message_bus.set_task_status(
                message.task_id,
                {
                    "status": TaskStatus.IN_PROGRESS.value,
                    "current_agent": self.agent_type.value,
                    "timestamp": message.timestamp.isoformat(),
                },
            )

            # Process the task
            result = await self.process_task(message)

            # Send response message
            response = AgentMessage(
                message_type=MessageType.TASK_RESPONSE,
                from_agent=self.agent_type,
                to_agent=message.from_agent,  # Reply to sender
                task_id=message.task_id,
                correlation_id=message.correlation_id,
                payload=result,
            )

            await self.message_bus.publish(response)

            # Update task status to completed
            await self.message_bus.set_task_status(
                message.task_id,
                {
                    "status": TaskStatus.COMPLETED.value,
                    "current_agent": self.agent_type.value,
                    "timestamp": response.timestamp.isoformat(),
                },
            )

            self.logger.info("task.completed", task_id=message.task_id)

        except Exception as e:
            self.logger.error(
                "task.failed",
                task_id=message.task_id,
                error=str(e),
                exc_info=True,
            )

            # Send error message
            error_msg = AgentMessage(
                message_type=MessageType.TASK_ERROR,
                from_agent=self.agent_type,
                to_agent=message.from_agent,
                task_id=message.task_id,
                correlation_id=message.correlation_id,
                payload={"error": str(e), "error_type": type(e).__name__},
            )

            await self.message_bus.publish(error_msg)

            # Update task status to failed
            await self.message_bus.set_task_status(
                message.task_id,
                {
                    "status": TaskStatus.FAILED.value,
                    "current_agent": self.agent_type.value,
                    "error": str(e),
                    "timestamp": error_msg.timestamp.isoformat(),
                },
            )

    async def run(self) -> None:
        """Start the agent and begin listening for messages."""
        self.logger.info("agent.starting")

        await self.message_bus.connect()
        await self.message_bus.subscribe(self.agent_type, self.handle_message)

        self._running = True

        # Start listening in background
        listen_task = asyncio.create_task(self.message_bus.start_listening())

        self.logger.info("agent.running", agent=self.agent_type.value)

        try:
            await listen_task
        except asyncio.CancelledError:
            self.logger.info("agent.cancelled")
            self._running = False
        finally:
            await self.message_bus.disconnect()
            self.logger.info("agent.stopped")

    async def send_status_update(
        self, task_id: str, correlation_id: str, target_agent: AgentType, status: str
    ) -> None:
        """Send a status update to another agent or orchestrator.

        Args:
            task_id: Task ID
            correlation_id: Correlation ID for the pipeline run
            target_agent: Agent to send the update to
            status: Status message
        """
        message = AgentMessage(
            message_type=MessageType.STATUS_UPDATE,
            from_agent=self.agent_type,
            to_agent=target_agent,
            task_id=task_id,
            correlation_id=correlation_id,
            payload={"status": status},
        )

        await self.message_bus.publish(message)
