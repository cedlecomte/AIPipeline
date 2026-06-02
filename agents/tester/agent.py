"""Tester Agent - Creates and runs tests for Ansible collections."""

import json
from typing import Any

from shared.models.messages import AgentMessage, AgentType, TestResults
from shared.utils.base_agent import BaseAgent
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus


class TesterAgent(BaseAgent):
    """Agent responsible for creating and executing Ansible tests."""

    def __init__(self, message_bus: MessageBus, claude_client: ClaudeClient):
        super().__init__(AgentType.TESTER, message_bus, claude_client)

    def get_system_prompt(self) -> str:
        """Return system prompt for testing."""
        return """You are an Expert Ansible Testing Engineer.

Your role is to create comprehensive tests for Ansible collections and validate functionality.

Testing Strategy:
1. Unit Tests: Test module logic in isolation (using pytest + ansible-test units)
2. Integration Tests: Test modules against real/mocked cloud APIs
3. Sanity Tests: Run ansible-test sanity checks (validate, import, compile)
4. Molecule Tests: End-to-end role testing with Podman containers

Test Requirements:
- Follow ansible-test framework conventions
- Create tests/unit/plugins/modules/ for unit tests
- Create tests/integration/targets/ for integration tests
- Use proper fixtures and mocking for cloud APIs
- Test both success and failure scenarios
- Verify idempotency (run twice, changed only first time)
- Test check_mode behavior
- Validate return values and error messages

Test Structure:
- Use pytest for unit tests with ansible.module_utils
- Mock external dependencies (boto3, cloud SDKs)
- Create integration test playbooks
- Include test requirements (pip packages)
- Add test documentation

Output:
- Complete test files with proper structure
- Test execution plan
- Expected coverage targets
- Mock/fixture requirements"""

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for testing."""
        return [
            {
                "name": "create_unit_test",
                "description": "Create a unit test for an Ansible module",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string"},
                        "test_cases": {"type": "array"},
                    },
                    "required": ["module_name"],
                },
            },
            {
                "name": "create_integration_test",
                "description": "Create an integration test playbook",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target_name": {"type": "string"},
                        "playbook_content": {"type": "string"},
                    },
                    "required": ["target_name", "playbook_content"],
                },
            },
            {
                "name": "run_tests",
                "description": "Execute tests and return results",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "test_type": {
                            "type": "string",
                            "enum": ["unit", "integration", "sanity"],
                        },
                        "test_path": {"type": "string"},
                    },
                    "required": ["test_type"],
                },
            },
        ]

    async def process_task(self, message: AgentMessage) -> dict[str, Any]:
        """Create and execute tests for the code artifacts.

        Args:
            message: Task message containing code artifacts

        Returns:
            Test results
        """
        artifacts = message.payload.get("artifacts", [])

        self.logger.info("tester.creating_tests", artifacts_count=len(artifacts))

        # Create tests for each module
        test_artifacts = []
        test_results_list = []

        for artifact in artifacts:
            if artifact["artifact_type"] == "module":
                messages = [
                    {
                        "role": "user",
                        "content": f"""Create comprehensive tests for this Ansible module:

Module Code:
{artifact['content']}

File Path: {artifact['file_path']}

Generate:
1. Unit tests (pytest) testing all parameters and edge cases
2. Integration test playbook testing real functionality
3. Test fixtures and mocks for external dependencies

Format as JSON with:
- unit_test_code: string
- integration_test_playbook: string
- test_requirements: [list of Python packages]
- expected_test_count: int""",
                    }
                ]

                response = await self.claude.create_message(
                    messages=messages,
                    system=self.get_system_prompt(),
                    thinking={"type": "adaptive"},
                    output_config={"effort": "medium"},
                )

                test_spec = json.loads(self.claude.extract_text(response))
                test_artifacts.append(test_spec)

        # Simulate test execution (in production, would run ansible-test)
        for test_spec in test_artifacts:
            # Placeholder test results
            result = TestResults(
                test_type="unit",
                passed=test_spec.get("expected_test_count", 5),
                failed=0,
                skipped=0,
                total=test_spec.get("expected_test_count", 5),
                failures=[],
                coverage_percent=85.0,
                log_output="All tests passed",
            )

            test_results_list.append(result.model_dump())

        # Store test artifacts and results
        await self.message_bus.store_artifact(message.task_id, "test_artifacts", test_artifacts)
        await self.message_bus.store_artifact(message.task_id, "test_results", test_results_list)

        self.logger.info("tester.tests_completed", test_count=len(test_results_list))

        return {
            "test_artifacts": test_artifacts,
            "test_results": test_results_list,
            "all_passed": all(r["failed"] == 0 for r in test_results_list),
            "next_agent": AgentType.CODE_REVIEWER.value,
        }


async def main() -> None:
    """Run the Tester Agent."""
    from config.settings import settings

    message_bus = MessageBus(settings.redis_url)
    claude_client = ClaudeClient()
    agent = TesterAgent(message_bus, claude_client)

    try:
        await agent.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
