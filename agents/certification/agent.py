"""Certification Agent - Validates against Ansible Galaxy standards."""

import json
from typing import Any

from shared.models.messages import AgentMessage, AgentType, CertificationReport
from shared.utils.base_agent import BaseAgent
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus


class CertificationAgent(BaseAgent):
    """Agent responsible for Ansible Galaxy certification validation."""

    def __init__(self, message_bus: MessageBus, claude_client: ClaudeClient):
        super().__init__(AgentType.CERTIFICATION, message_bus, claude_client)

    def get_system_prompt(self) -> str:
        """Return system prompt for certification."""
        return """You are an Ansible Galaxy Certification Specialist.

Your role is to validate Ansible collections against Galaxy certification requirements.

Certification Criteria:

1. Collection Structure:
   - Proper directory layout per Ansible standards
   - Valid galaxy.yml with all required fields
   - README.md with usage documentation
   - LICENSE file present
   - CHANGELOG.md following Keep a Changelog format

2. Code Quality:
   - All ansible-test sanity checks pass
   - No ansible-lint violations
   - Proper documentation in all modules
   - Python code follows PEP 8
   - No deprecated features used

3. Testing:
   - Integration tests for all modules
   - Unit tests with good coverage (>70%)
   - Tests pass on supported Ansible versions
   - Molecule tests for roles (if applicable)

4. Documentation:
   - README with clear installation and usage instructions
   - DOCUMENTATION blocks in all modules
   - Example playbooks demonstrating usage
   - Links to official documentation

5. Metadata:
   - Proper galaxy.yml with namespace, name, version
   - Valid semantic versioning
   - Accurate dependency declarations
   - Repository and documentation URLs

6. Security:
   - No hardcoded credentials
   - Secure handling of sensitive parameters
   - No known vulnerabilities in dependencies

Output Format:
Provide structured JSON with:
- compliant: boolean (true if meets all requirements)
- ansible_version_tested: string
- galaxy_score: float (0-100)
- issues: [{severity, category, description, recommendation}]
- recommendations: [list of improvements]
- certification_status: approved|conditional|rejected"""

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for certification."""
        return [
            {
                "name": "validate_galaxy_yml",
                "description": "Validate galaxy.yml metadata",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "galaxy_content": {"type": "string"},
                    },
                    "required": ["galaxy_content"],
                },
            },
            {
                "name": "run_ansible_test_sanity",
                "description": "Run ansible-test sanity validation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "collection_path": {"type": "string"},
                    },
                    "required": ["collection_path"],
                },
            },
        ]

    async def process_task(self, message: AgentMessage) -> dict[str, Any]:
        """Validate collection against certification requirements.

        Args:
            message: Task message with collection artifacts

        Returns:
            Certification report
        """
        artifacts = message.payload.get("artifacts", [])
        test_results = message.payload.get("test_results", [])

        self.logger.info("certification.validating")

        # Analyze all artifacts and test results
        messages = [
            {
                "role": "user",
                "content": f"""Validate this Ansible collection against Galaxy certification requirements:

Artifacts:
{json.dumps([{k: v for k, v in a.items() if k != 'content'} for a in artifacts], indent=2)}

Test Results:
{json.dumps(test_results, indent=2)}

Perform a complete certification review and provide a detailed report as JSON.""",
            }
        ]

        response = await self.claude.create_message(
            messages=messages,
            system=self.get_system_prompt(),
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
        )

        cert_data = json.loads(self.claude.extract_text(response))

        # Determine if certified
        critical_issues = len([i for i in cert_data.get("issues", []) if i.get("severity") == "critical"])

        certification = CertificationReport(
            compliant=cert_data.get("compliant", critical_issues == 0),
            ansible_version_tested="2.14",
            galaxy_score=cert_data.get("galaxy_score", 75.0),
            issues=cert_data.get("issues", []),
            recommendations=cert_data.get("recommendations", []),
        )

        await self.message_bus.store_artifact(
            message.task_id, "certification_report", certification.model_dump()
        )

        self.logger.info(
            "certification.complete",
            compliant=certification.compliant,
            score=certification.galaxy_score,
        )

        return {
            "certification": certification.model_dump(),
            "pipeline_complete": certification.compliant,
        }


async def main() -> None:
    """Run the Certification Agent."""
    from config.settings import settings

    message_bus = MessageBus(settings.redis_url)
    claude_client = ClaudeClient()
    agent = CertificationAgent(message_bus, claude_client)

    try:
        await agent.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
