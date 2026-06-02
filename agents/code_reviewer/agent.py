"""Code Reviewer Agent - Reviews code quality, security, and best practices."""

import json
from typing import Any

from shared.models.messages import AgentMessage, AgentType, ReviewFeedback
from shared.utils.base_agent import BaseAgent
from shared.utils.claude_client import ClaudeClient
from shared.utils.message_bus import MessageBus


class CodeReviewerAgent(BaseAgent):
    """Agent responsible for comprehensive code review."""

    def __init__(self, message_bus: MessageBus, claude_client: ClaudeClient):
        super().__init__(AgentType.CODE_REVIEWER, message_bus, claude_client)

    def get_system_prompt(self) -> str:
        """Return system prompt for code review."""
        return """You are a Senior Ansible Code Reviewer and Security Expert.

Your role is to conduct thorough code reviews for Ansible collections.

Review Areas:

1. Security Issues:
   - No hardcoded credentials or API keys
   - Proper input validation and sanitization
   - No command injection vulnerabilities
   - Secure handling of sensitive data
   - No use of deprecated or insecure functions

2. Code Quality:
   - Proper error handling and exception management
   - Clear and maintainable code structure
   - Appropriate use of Ansible idioms
   - Correct module return values
   - Proper check_mode implementation

3. Ansible Best Practices:
   - Idempotent operations
   - Proper DOCUMENTATION blocks
   - Correct argument_spec definitions
   - Following ansible-lint rules
   - FQCN usage
   - Proper module structure

4. Testing Coverage:
   - All critical paths tested
   - Edge cases covered
   - Proper mock usage
   - Integration test completeness

Scoring:
Rate code 0-10 where:
- 0-3: Major issues, reject
- 4-6: Significant issues, needs rework
- 7-8: Minor issues, recommend fixes
- 9-10: Excellent, approve with minor suggestions

Output Format:
Provide structured JSON with:
- overall_score: float
- security_issues: [{severity, description, file, line, recommendation}]
- quality_issues: [{severity, description, file, recommendation}]
- best_practices: [{type, description, recommendation}]
- recommendations: [list of improvement suggestions]
- approved: boolean"""

    def get_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for code review."""
        return [
            {
                "name": "analyze_security",
                "description": "Perform security analysis on code",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "file_path": {"type": "string"},
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "check_ansible_lint",
                "description": "Check code against ansible-lint rules",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_content": {"type": "string"},
                    },
                    "required": ["file_content"],
                },
            },
        ]

    async def process_task(self, message: AgentMessage) -> dict[str, Any]:
        """Review code artifacts.

        Args:
            message: Task message containing code artifacts

        Returns:
            Review feedback
        """
        artifacts = message.payload.get("artifacts", [])

        self.logger.info("reviewer.reviewing", artifacts_count=len(artifacts))

        all_security_issues = []
        all_quality_issues = []
        all_best_practices = []
        all_recommendations = []

        # Review each artifact
        for artifact in artifacts:
            messages = [
                {
                    "role": "user",
                    "content": f"""Conduct a comprehensive code review of this Ansible {artifact['artifact_type']}:

File: {artifact['file_path']}

Code:
```
{artifact['content']}
```

Review for:
1. Security vulnerabilities
2. Code quality issues
3. Ansible best practices compliance
4. Potential bugs or edge cases
5. Maintainability concerns

Provide detailed findings as JSON with the structure defined in your system prompt.""",
                }
            ]

            response = await self.claude.create_message(
                messages=messages,
                system=self.get_system_prompt(),
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},
            )

            review_data = json.loads(self.claude.extract_text(response))

            all_security_issues.extend(review_data.get("security_issues", []))
            all_quality_issues.extend(review_data.get("quality_issues", []))
            all_best_practices.extend(review_data.get("best_practices", []))
            all_recommendations.extend(review_data.get("recommendations", []))

        # Calculate overall score
        critical_issues = len([i for i in all_security_issues if i.get("severity") == "critical"])
        high_issues = len([i for i in all_security_issues + all_quality_issues if i.get("severity") == "high"])

        if critical_issues > 0:
            overall_score = 3.0
        elif high_issues > 2:
            overall_score = 5.0
        elif high_issues > 0:
            overall_score = 7.0
        else:
            overall_score = 9.0

        feedback = ReviewFeedback(
            overall_score=overall_score,
            security_issues=all_security_issues,
            quality_issues=all_quality_issues,
            best_practices=all_best_practices,
            recommendations=all_recommendations,
            approved=overall_score >= 7.0,
        )

        await self.message_bus.store_artifact(message.task_id, "review_feedback", feedback.model_dump())

        self.logger.info(
            "reviewer.review_complete",
            score=overall_score,
            approved=feedback.approved,
        )

        return {
            "feedback": feedback.model_dump(),
            "next_agent": AgentType.RELEASE.value if feedback.approved else AgentType.DEVELOPER.value,
        }


async def main() -> None:
    """Run the Code Reviewer Agent."""
    from config.settings import settings

    message_bus = MessageBus(settings.redis_url)
    claude_client = ClaudeClient()
    agent = CodeReviewerAgent(message_bus, claude_client)

    try:
        await agent.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
