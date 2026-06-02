"""Agent worker — runs multiple dynamic agents in a single container."""

import asyncio
import json

import structlog

from config.settings import settings
from shared.models.definitions import AgentDefinition
from shared.utils.claude_client import ClaudeClient
from shared.utils.dynamic_agent import DynamicAgent
from shared.utils.message_bus import MessageBus

logger = structlog.get_logger()


class AgentWorker:
    """Loads dynamic agent definitions from Redis and runs them."""

    def __init__(self):
        self.message_bus = MessageBus(settings.redis_url)
        self.claude = ClaudeClient()
        self.agents: dict[str, DynamicAgent] = {}
        self.logger = logger.bind(component="agent_worker")

    async def load_agents(self) -> None:
        """Load all non-builtin agent definitions from Redis."""
        agent_ids = await self.message_bus.client.smembers("agent_defs:index")
        for aid in agent_ids:
            data = await self.message_bus.client.get(f"agent_def:{aid}")
            if not data:
                continue
            agent_def = AgentDefinition.model_validate_json(data)
            if agent_def.is_builtin:
                continue
            await self._start_agent(agent_def)

        self.logger.info("agent_worker.loaded", count=len(self.agents))

    async def _start_agent(self, agent_def: AgentDefinition) -> None:
        """Start a single dynamic agent."""
        if agent_def.slug in self.agents:
            self.logger.info("agent_worker.agent_already_running", slug=agent_def.slug)
            return

        agent = DynamicAgent(agent_def, self.message_bus, self.claude)
        await agent.start()
        self.agents[agent_def.slug] = agent
        self.logger.info("agent_worker.agent_started", slug=agent_def.slug)

    async def _stop_agent(self, slug: str) -> None:
        """Stop a running dynamic agent."""
        agent = self.agents.pop(slug, None)
        if agent:
            await agent.stop()
            self.logger.info("agent_worker.agent_stopped", slug=slug)

    async def _reload_agent(self, agent_id: str) -> None:
        """Reload an agent definition from Redis."""
        data = await self.message_bus.client.get(f"agent_def:{agent_id}")
        if not data:
            return
        agent_def = AgentDefinition.model_validate_json(data)
        if agent_def.is_builtin:
            return

        await self._stop_agent(agent_def.slug)
        await self._start_agent(agent_def)

    async def watch_control_channel(self) -> None:
        """Watch the control channel for agent definition changes."""
        pubsub = self.message_bus.client.pubsub()
        await pubsub.subscribe("control:agent_defs")

        self.logger.info("agent_worker.watching_control_channel")

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    action = payload.get("action")
                    agent_id = payload.get("agent_id")

                    self.logger.info("agent_worker.control_event", action=action, agent_id=agent_id)

                    if action == "create":
                        await self._reload_agent(agent_id)
                    elif action == "update":
                        await self._reload_agent(agent_id)
                    elif action == "delete":
                        data = await self.message_bus.client.get(f"agent_def:{agent_id}")
                        if data:
                            agent_def = AgentDefinition.model_validate_json(data)
                            await self._stop_agent(agent_def.slug)
                        else:
                            for slug, agent in list(self.agents.items()):
                                if agent.agent_def.agent_id == agent_id:
                                    await self._stop_agent(slug)
                                    break

                except Exception as e:
                    self.logger.error("agent_worker.control_error", error=str(e))

    async def run(self) -> None:
        """Main entry point."""
        self.logger.info("agent_worker.starting")

        await self.message_bus.connect()
        await self.load_agents()

        tasks = [
            asyncio.create_task(self.watch_control_channel()),
            asyncio.create_task(self.message_bus.start_listening()),
        ]

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            self.logger.info("agent_worker.shutdown")
        finally:
            await self.message_bus.disconnect()


async def main() -> None:
    worker = AgentWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
