"""Release Agent - Handles versioning, changelog, and publishing."""

import json
from typing import Any

from shared.models.messages import AgentMessage, AgentType, ReleaseInfo
from shared.utils.base_agent import BaseAgent
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus


class ReleaseAgent(BaseAgent):
    """Agent responsible for version management and publishing."""

    def __init__(self, message_bus: MessageBus, claude_client: ClaudeClient):
        super().__init__(AgentType.RELEASE, message_bus, claude_client)

    def get_system_prompt(self) -> str:
        """Return system prompt for release management."""
        return """You are an Ansible Collection Release Manager.

Your role is to manage versioning, changelogs, and publishing to GitHub/GitLab and Ansible Galaxy.

Responsibilities:
1. Determine appropriate semantic version (MAJOR.MINOR.PATCH)
2. Generate comprehensive changelogs following Keep a Changelog format
3. Create release notes highlighting key features and breaking changes
4. Prepare galaxy.yml metadata
5. Create Git tags and GitHub/GitLab releases
6. Publish to Ansible Galaxy
7. Update documentation

Semantic Versioning Rules:
- MAJOR: Breaking changes, incompatible API changes
- MINOR: New features, backward-compatible functionality
- PATCH: Bug fixes, backward-compatible patches

Changelog Format (Keep a Changelog):
- [Version] - Date
- Added: New features
- Changed: Changes in existing functionality
- Deprecated: Soon-to-be removed features
- Removed: Removed features
- Fixed: Bug fixes
- Security: Security fixes

Galaxy Publishing:
- Ensure galaxy.yml is complete and valid
- Include proper namespace and collection name
- List all dependencies
- Specify supported Ansible versions
- Add repository and documentation links

Output Format:
Provide structured JSON with:
- version: semantic version string
- changelog: markdown changelog content
- release_notes: highlights for this release
- git_tag: tag name (e.g., v1.2.3)
- galaxy_metadata: complete galaxy.yml content
- publish_commands: list of commands to execute"""

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for release management."""
        return [
            {
                "name": "determine_version",
                "description": "Determine the next semantic version",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "current_version": {"type": "string"},
                        "change_type": {
                            "type": "string",
                            "enum": ["major", "minor", "patch"],
                        },
                    },
                    "required": ["current_version", "change_type"],
                },
            },
            {
                "name": "generate_changelog",
                "description": "Generate changelog from changes",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "changes": {"type": "array"},
                        "version": {"type": "string"},
                    },
                    "required": ["changes", "version"],
                },
            },
            {
                "name": "publish_to_git",
                "description": "Publish release to GitHub or GitLab",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "version": {"type": "string"},
                        "release_notes": {"type": "string"},
                        "tag_name": {"type": "string"},
                    },
                    "required": ["version", "tag_name"],
                },
            },
        ]

    async def process_task(self, message: AgentMessage) -> dict[str, Any]:
        """Create release and publish.

        Args:
            message: Task message containing artifacts and test results

        Returns:
            Release information
        """
        requirements = await self.message_bus.get_artifact(message.task_id, "requirements")
        plan = await self.message_bus.get_artifact(message.task_id, "architecture_plan")

        self.logger.info("release.preparing")

        messages = [
            {
                "role": "user",
                "content": f"""Prepare a release for this Ansible collection:

Requirements:
{json.dumps(requirements, indent=2)}

Architecture:
{json.dumps(plan, indent=2)}

Tasks:
1. Determine the appropriate semantic version (assume current is 1.0.0)
2. Generate a comprehensive changelog
3. Create release notes highlighting key features
4. Prepare the Git tag name
5. Generate complete galaxy.yml metadata

Provide the output as JSON with the structure defined in your system prompt.""",
            }
        ]

        response = await self.claude.create_message(
            messages=messages,
            system=self.get_system_prompt(),
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
        )

        release_data = json.loads(self.claude.extract_text(response))

        release_info = ReleaseInfo(
            version=release_data.get("version", "1.0.0"),
            changelog=release_data.get("changelog", ""),
            release_notes=release_data.get("release_notes", ""),
            git_tag=release_data.get("git_tag", "v1.0.0"),
            published_url=None,  # Will be set after actual publishing
        )

        await self.message_bus.store_artifact(message.task_id, "release_info", release_info.model_dump())

        self.logger.info("release.prepared", version=release_info.version)

        return {
            "release_info": release_info.model_dump(),
            "next_agent": AgentType.CERTIFICATION.value,
        }


async def main() -> None:
    """Run the Release Agent."""
    from config.settings import settings

    message_bus = MessageBus(settings.redis_url)
    claude_client = ClaudeClient()
    agent = ReleaseAgent(message_bus, claude_client)

    try:
        await agent.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
