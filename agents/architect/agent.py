"""Architect Agent - Creates implementation plans and architecture."""

from typing import Any

import structlog

from shared.models.messages import AgentMessage, AgentType, ArchitecturePlan
from shared.utils.base_agent import BaseAgent
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus

logger = structlog.get_logger()


class ArchitectAgent(BaseAgent):
    """Agent responsible for creating architectural plans for Ansible collections."""

    def __init__(self, message_bus: MessageBus, claude_client: ClaudeClient):
        super().__init__(AgentType.ARCHITECT, message_bus, claude_client)

    def get_system_prompt(self) -> str:
        """Return system prompt for architecture planning."""
        return """You are an Expert Ansible Collection Architect.

Your role is to design comprehensive implementation plans for Ansible collections based on requirements.

Responsibilities:
1. Analyze requirements and determine the best Ansible implementation approach
2. Design module structure (module names, parameters, return values)
3. Plan role organization (tasks, handlers, defaults, vars)
4. Identify plugin needs (connection, lookup, filter, test plugins)
5. Define dependencies (Python libraries, system packages, other collections)
6. Create file structure for the collection
7. Document design decisions and architectural patterns

Ansible Best Practices:
- Follow ansible-dev-tools and ansible-lint standards
- Use FQCN (Fully Qualified Collection Names)
- Design idempotent modules with check_mode support
- Include proper error handling and return value structures
- Plan for both Python 3.9+ compatibility
- Consider integration test requirements

Output a detailed architecture plan with:
- Module specifications (parameters, options, return values)
- Role structure and task organization
- Plugin requirements and interfaces
- Collection dependency tree
- File structure with all necessary files
- Implementation notes and gotchas"""

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for architecture planning."""
        return [
            {
                "name": "design_ansible_module",
                "description": "Design an Ansible module specification",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string"},
                        "description": {"type": "string"},
                        "parameters": {"type": "object"},
                        "return_values": {"type": "object"},
                    },
                    "required": ["module_name", "description"],
                },
            },
            {
                "name": "design_ansible_role",
                "description": "Design an Ansible role structure",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "role_name": {"type": "string"},
                        "description": {"type": "string"},
                        "tasks": {"type": "array"},
                        "defaults": {"type": "object"},
                    },
                    "required": ["role_name", "description"],
                },
            },
        ]

    async def process_task(self, message: AgentMessage) -> dict[str, Any]:
        """Create architectural plan based on requirements.

        Args:
            message: Task message containing requirements

        Returns:
            Architecture plan
        """
        requirements = message.payload.get("requirements")
        if not requirements:
            raise ValueError("Missing requirements in payload")

        self.logger.info("architect.planning", issue_key=requirements.get("issue_key"))

        messages = [
            {
                "role": "user",
                "content": f"""Create a comprehensive architecture plan for this Ansible collection feature:

Requirements:
{requirements}

Design:
1. All required modules with complete parameter specifications
2. Roles needed to orchestrate these modules
3. Any custom plugins required
4. Python library dependencies
5. Complete file structure for the collection
6. Implementation strategy and patterns to follow

Provide the output as structured JSON with these top-level keys:
- modules: [{name, file_path, description, parameters, returns, check_mode_support}]
- roles: [{name, description, tasks, defaults, handlers}]
- plugins: [{type, name, description, interface}]
- dependencies: [list of Python packages and Ansible collections]
- file_structure: {{path: description}}
- implementation_notes: string with key design decisions
- estimated_complexity: low|medium|high|very_high""",
            }
        ]

        response = await self.claude.create_message(
            messages=messages,
            system=self.get_system_prompt(),
            tools=self.get_tools(),
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
        )

        text_content = self.claude.extract_text(response)

        # Parse the architecture plan
        import json

        try:
            plan_data = json.loads(text_content)
        except json.JSONDecodeError:
            # Fallback: structure the text response
            plan_data = {
                "modules": [],
                "roles": [],
                "plugins": [],
                "dependencies": ["ansible-core>=2.14"],
                "file_structure": {},
                "implementation_notes": text_content,
                "estimated_complexity": "medium",
            }

        plan = ArchitecturePlan(
            modules=plan_data.get("modules", []),
            roles=plan_data.get("roles", []),
            plugins=plan_data.get("plugins", []),
            dependencies=plan_data.get("dependencies", []),
            file_structure=plan_data.get("file_structure", {}),
            implementation_notes=plan_data.get("implementation_notes", ""),
            estimated_complexity=plan_data.get("estimated_complexity", "medium"),
        )

        # Store the plan for later agents
        await self.message_bus.store_artifact(
            message.task_id, "architecture_plan", plan.model_dump()
        )

        self.logger.info(
            "architect.plan_created",
            task_id=message.task_id,
            modules_count=len(plan.modules),
            roles_count=len(plan.roles),
        )

        return {
            "plan": plan.model_dump(),
            "next_agent": AgentType.DEVELOPER.value,
        }


async def main() -> None:
    """Run the Architect Agent."""
    from config.settings import settings

    message_bus = MessageBus(settings.redis_url)
    claude_client = ClaudeClient()
    agent = ArchitectAgent(message_bus, claude_client)

    logger.info("architect_agent.starting")

    try:
        await agent.run()
    except KeyboardInterrupt:
        logger.info("architect_agent.shutdown")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
