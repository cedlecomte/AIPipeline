#!/usr/bin/env python3
"""Complete example: Jira issue → Published Ansible collection."""

import asyncio
import json

import structlog

from config.settings import settings
from orchestrator.pipeline import PipelineOrchestrator
from shared.utils.message_bus import MessageBus

logger = structlog.get_logger()


async def run_full_pipeline_example() -> None:
    """Run a complete pipeline from Jira to published collection."""

    # Example: Create an AWS CloudFormation stack module
    jira_issue_key = "ANSIBLE-456"
    jira_data = {
        "summary": "Add AWS CloudFormation stack module",
        "description": """
Create a new Ansible module for managing AWS CloudFormation stacks.

Requirements:
- Create, update, and delete CloudFormation stacks
- Support stack parameters and tags
- Handle stack events and outputs
- Check stack status
- Support change sets for previewing changes
- Idempotent operations

Technical Details:
- Use boto3 CloudFormation client
- Support all regions
- Handle pagination for large stacks
- Proper error messages for common failures (e.g., rollback)

API Reference:
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudformation.html
        """,
        "labels": ["aws", "cloudformation", "module", "enhancement"],
        "components": ["amazon.aws"],
        "priority": "High",
        "acceptance_criteria": [
            "Module can create CloudFormation stacks with parameters",
            "Module can update existing stacks",
            "Module can delete stacks",
            "Module retrieves stack outputs",
            "Module supports check mode (doesn't apply changes)",
            "Module is idempotent (running twice doesn't change state)",
            "Unit tests achieve >85% coverage",
            "Integration tests pass against real AWS",
            "ansible-lint passes with no errors",
            "Documentation is complete and accurate",
        ],
        "custom_fields": {
            "aws_services": ["CloudFormation"],
            "python_dependencies": ["boto3>=1.28.0", "botocore>=1.31.0"],
            "ansible_version_min": "2.14.0",
        },
    }

    print("=" * 80)
    print("🚀 ANSIBLE AGENT PIPELINE - FULL EXAMPLE")
    print("=" * 80)
    print()
    print(f"📋 Jira Issue: {jira_issue_key}")
    print(f"📝 Summary: {jira_data['summary']}")
    print()

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator()
    await orchestrator.message_bus.connect()

    try:
        # Start the pipeline
        print("▶️  Starting pipeline...")
        correlation_id = await orchestrator.start_pipeline(jira_issue_key, jira_data)

        print(f"✅ Pipeline started!")
        print(f"🔗 Correlation ID: {correlation_id}")
        print(f"📊 Task ID: {jira_issue_key}-{correlation_id[:8]}")
        print()

        # Monitor progress
        print("📡 Monitoring pipeline progress...\n")

        task_id = f"{jira_issue_key}-{correlation_id[:8]}"

        # Poll for completion (in production, this would be event-driven)
        max_wait = 3600  # 1 hour timeout
        poll_interval = 5  # Check every 5 seconds
        elapsed = 0

        while elapsed < max_wait:
            status = await orchestrator.message_bus.get_task_status(task_id)

            if status:
                current_status = status.get("status")
                current_agent = status.get("current_agent", "unknown")

                print(f"⏱️  [{elapsed}s] Status: {current_status} | Agent: {current_agent}")

                if current_status == "completed":
                    print()
                    print("🎉 Pipeline completed successfully!")
                    print()

                    # Retrieve all artifacts
                    print("📦 Artifacts Generated:")
                    print()

                    # Requirements
                    requirements = await orchestrator.message_bus.get_artifact(
                        task_id, "requirements"
                    )
                    if requirements:
                        print("  ✓ Requirements extracted")

                    # Architecture plan
                    plan = await orchestrator.message_bus.get_artifact(
                        task_id, "architecture_plan"
                    )
                    if plan:
                        print(f"  ✓ Architecture plan (modules: {len(plan.get('modules', []))})")

                    # Code artifacts
                    artifacts = await orchestrator.message_bus.get_artifact(
                        task_id, "code_artifacts"
                    )
                    if artifacts:
                        print(f"  ✓ Code artifacts ({len(artifacts)} files)")

                    # Test results
                    test_results = await orchestrator.message_bus.get_artifact(
                        task_id, "test_results"
                    )
                    if test_results:
                        total_tests = sum(r["total"] for r in test_results)
                        print(f"  ✓ Test suite ({total_tests} tests)")

                    # Review feedback
                    review = await orchestrator.message_bus.get_artifact(
                        task_id, "review_feedback"
                    )
                    if review:
                        print(f"  ✓ Code review (score: {review['overall_score']}/10)")

                    # Release info
                    release = await orchestrator.message_bus.get_artifact(
                        task_id, "release_info"
                    )
                    if release:
                        print(f"  ✓ Release {release['version']}")

                    # Certification
                    cert = await orchestrator.message_bus.get_artifact(
                        task_id, "certification_report"
                    )
                    if cert:
                        status_icon = "✓" if cert["compliant"] else "✗"
                        print(f"  {status_icon} Certification (score: {cert.get('galaxy_score', 0)})")

                    print()
                    break

                elif current_status == "failed":
                    print()
                    print("❌ Pipeline failed!")
                    print(f"Error: {status.get('error', 'Unknown error')}")
                    break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if elapsed >= max_wait:
            print()
            print("⏱️  Pipeline timeout - still running after 1 hour")

    finally:
        await orchestrator.message_bus.disconnect()

    print()
    print("=" * 80)
    print("Dashboard: http://localhost:8080")
    print("=" * 80)


if __name__ == "__main__":
    # Configure logging for the example
    import structlog

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    asyncio.run(run_full_pipeline_example())
