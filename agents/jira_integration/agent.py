"""Jira Integration Agent - Reads and extracts requirements from Jira cards."""

from typing import Any

import structlog

from shared.models.messages import AgentMessage, AgentType, JiraRequirements, MessageType
from shared.utils.base_agent import BaseAgent
from shared.utils.claude_client import ClaudeClient
from shared.utils.jira_client import JiraClient
from shared.utils.message_bus import MessageBus

logger = structlog.get_logger()


class JiraIntegrationAgent(BaseAgent):
    """Agent responsible for reading Jira cards and extracting requirements."""

    def __init__(self, message_bus: MessageBus, claude_client: ClaudeClient):
        super().__init__(AgentType.JIRA_INTEGRATION, message_bus, claude_client)
        self.jira = JiraClient()

    def get_system_prompt(self) -> str:
        """Return system prompt for Jira integration."""
        return """You are a Jira Integration Specialist for Ansible collection development.

Your role is to:
1. Read Jira cards and extract structured requirements
2. Identify the type of work (new module, bug fix, enhancement, new collection)
3. Extract acceptance criteria and technical specifications
4. Determine dependencies and related issues
5. Clarify ambiguous requirements

Output Format:
- Provide structured JSON with: summary, description, acceptance_criteria, technical_specs, dependencies
- Flag any missing or ambiguous information
- Suggest additional context needed for implementation

You have access to Jira via MCP tools. Use them to fetch issue details, comments, and linked issues."""

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for Jira integration."""
        return [
            {
                "name": "parse_jira_requirements",
                "description": "Parse and structure Jira card requirements for Ansible development",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "Jira issue key (e.g., ANSIBLE-123)"},
                        "raw_data": {"type": "object", "description": "Raw Jira issue data"},
                    },
                    "required": ["issue_key", "raw_data"],
                },
            }
        ]

    async def process_task(self, message: AgentMessage) -> dict[str, Any]:
        """Process Jira requirement extraction task.

        Args:
            message: Task message containing Jira issue key

        Returns:
            Extracted and structured requirements
        """
        issue_key = message.payload.get("issue_key")
        if not issue_key:
            raise ValueError("Missing issue_key in payload")

        jira_data = await self.jira.get_issue(issue_key)

        import json

        messages = [
            {
                "role": "user",
                "content": f"""Analyze this Jira card and extract structured requirements for Ansible collection development.

Issue Key: {issue_key}
Raw Data: {json.dumps(jira_data, indent=2, default=str)}

Extract:
1. Summary: Brief description of what needs to be built
2. Detailed Description: Full technical requirements
3. Acceptance Criteria: List of testable conditions for completion
4. Technical Specifications: API endpoints, cloud service details, parameters
5. Dependencies: Other issues, modules, or external services
6. Labels and Components: Categorization
7. Priority: How urgent is this work

Format the output as structured JSON.""",
            }
        ]

        response = await self.claude.create_message(
            messages=messages,
            system=self.get_system_prompt(),
            tools=self.get_tools(),
        )

        text_content = self.claude.extract_text(response)

        fields = jira_data.get("fields", {})
        try:
            requirements_data = json.loads(text_content)
        except json.JSONDecodeError:
            requirements_data = {
                "summary": fields.get("summary", ""),
                "description": text_content,
                "acceptance_criteria": [],
                "technical_specs": {},
                "dependencies": [],
                "labels": fields.get("labels", []),
                "components": [c.get("name", "") for c in fields.get("components", [])],
                "priority": (fields.get("priority") or {}).get("name", "Medium"),
            }

        requirements = JiraRequirements(
            issue_key=issue_key,
            summary=requirements_data.get("summary", ""),
            description=requirements_data.get("description", ""),
            acceptance_criteria=requirements_data.get("acceptance_criteria", []),
            labels=requirements_data.get("labels", []),
            components=requirements_data.get("components", []),
            priority=requirements_data.get("priority", "Medium"),
            raw_data=jira_data,
        )

        self.logger.info("jira.requirements_extracted", issue_key=issue_key)

        return {
            "requirements": requirements.model_dump(),
            "next_agent": AgentType.ARCHITECT.value,
        }


async def main() -> None:
    """Run the Jira Integration Agent."""
    from config.settings import settings

    message_bus = MessageBus(settings.redis_url)
    claude_client = ClaudeClient()
    agent = JiraIntegrationAgent(message_bus, claude_client)

    logger.info("jira_integration_agent.starting")

    try:
        await agent.run()
    except KeyboardInterrupt:
        logger.info("jira_integration_agent.shutdown")
    except Exception as e:
        logger.error("jira_integration_agent.error", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
