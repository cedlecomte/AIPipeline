"""Developer Agent - Writes Ansible modules, roles, and plugins."""

import json
from typing import Any

from shared.models.messages import AgentMessage, AgentType, CodeArtifact
from shared.utils.base_agent import BaseAgent
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus


class DeveloperAgent(BaseAgent):
    """Agent responsible for writing Ansible code based on architecture plans."""

    def __init__(self, message_bus: MessageBus, claude_client: ClaudeClient):
        super().__init__(AgentType.DEVELOPER, message_bus, claude_client)

    def get_system_prompt(self) -> str:
        """Return system prompt for code development."""
        return """You are an Expert Ansible Collection Developer.

Your role is to write production-ready Ansible code following the architecture plan.

Core Responsibilities:
1. Implement Ansible modules in Python following ansible-core standards
2. Create roles with proper task organization, handlers, and defaults
3. Write plugins (connection, lookup, filter, test) as needed
4. Ensure all code is idempotent and supports check_mode
5. Add comprehensive docstrings and DOCUMENTATION blocks
6. Follow ansible-dev-tools and ansible-lint rules
7. Write secure, maintainable code

Ansible Module Standards:
- Use AnsibleModule from ansible.module_utils.basic
- Define DOCUMENTATION, EXAMPLES, and RETURN blocks
- Implement proper argument spec with type validation
- Support check_mode for dry-run capability
- Return changed status and relevant data
- Handle errors gracefully with module.fail_json()
- Use module.exit_json() for successful completion

Code Quality:
- Follow PEP 8 and ansible-lint rules
- Add type hints where beneficial
- Write defensive code with input validation
- No hardcoded credentials or secrets
- Proper exception handling
- Clear variable naming

Output Format:
For each file, provide:
- Full file path relative to collection root
- Complete file content
- Brief explanation of key implementation decisions"""

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for code development."""
        return [
            {
                "name": "create_ansible_module",
                "description": "Generate a complete Ansible module implementation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string"},
                        "file_path": {"type": "string"},
                        "parameters": {"type": "object"},
                        "implementation": {"type": "string"},
                    },
                    "required": ["module_name", "file_path", "implementation"],
                },
            },
            {
                "name": "create_ansible_role",
                "description": "Generate a complete Ansible role structure",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "role_name": {"type": "string"},
                        "tasks": {"type": "string"},
                        "defaults": {"type": "string"},
                        "handlers": {"type": "string"},
                    },
                    "required": ["role_name", "tasks"],
                },
            },
        ]

    async def process_task(self, message: AgentMessage) -> dict[str, Any]:
        """Implement code based on architecture plan.

        Args:
            message: Task message containing architecture plan

        Returns:
            Generated code artifacts
        """
        plan = message.payload.get("plan")
        if not plan:
            raise ValueError("Missing architecture plan in payload")

        self.logger.info(
            "developer.implementing",
            modules_count=len(plan.get("modules", [])),
            roles_count=len(plan.get("roles", [])),
        )

        # Generate code for each component in the plan
        artifacts = []

        # Implement modules
        for module_spec in plan.get("modules", []):
            messages = [
                {
                    "role": "user",
                    "content": f"""Implement this Ansible module following the specification:

Module Specification:
{json.dumps(module_spec, indent=2)}

Generate the complete Python module code with:
1. Complete DOCUMENTATION block in YAML
2. EXAMPLES block with practical usage examples
3. RETURN block documenting all return values
4. Full implementation with AnsibleModule
5. Proper argument_spec with validation
6. check_mode support
7. Comprehensive error handling

Return ONLY the complete Python code, no explanations outside the code.""",
                }
            ]

            response = await self.claude.create_message(
                messages=messages,
                system=self.get_system_prompt(),
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},
            )

            code_content = self.claude.extract_text(response)

            artifact = CodeArtifact(
                file_path=module_spec.get("file_path", f"plugins/modules/{module_spec['name']}.py"),
                content=code_content,
                artifact_type="module",
                dependencies=module_spec.get("dependencies", []),
            )

            artifacts.append(artifact.model_dump())

        # Implement roles
        for role_spec in plan.get("roles", []):
            # Create role tasks
            messages = [
                {
                    "role": "user",
                    "content": f"""Create the main tasks file for this Ansible role:

Role Specification:
{json.dumps(role_spec, indent=2)}

Generate tasks/main.yml with proper task organization, tags, and error handling.""",
                }
            ]

            response = await self.claude.create_message(
                messages=messages,
                system=self.get_system_prompt(),
                output_config={"effort": "medium"},
            )

            role_tasks = self.claude.extract_text(response)

            artifact = CodeArtifact(
                file_path=f"roles/{role_spec['name']}/tasks/main.yml",
                content=role_tasks,
                artifact_type="role",
            )

            artifacts.append(artifact.model_dump())

        # Store all artifacts
        await self.message_bus.store_artifact(message.task_id, "code_artifacts", artifacts)

        self.logger.info("developer.implementation_complete", artifacts_count=len(artifacts))

        return {
            "artifacts": artifacts,
            "next_agent": AgentType.TESTER.value,
        }


async def main() -> None:
    """Run the Developer Agent."""
    from config.settings import settings

    message_bus = MessageBus(settings.redis_url)
    claude_client = ClaudeClient()
    agent = DeveloperAgent(message_bus, claude_client)

    try:
        await agent.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
