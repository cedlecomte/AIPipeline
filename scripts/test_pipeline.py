#!/usr/bin/env python3
"""Test script to trigger a sample pipeline run."""

import asyncio
import json
import sys

from orchestrator.pipeline import PipelineOrchestrator


async def test_pipeline() -> None:
    """Run a test pipeline with sample Jira data."""
    orchestrator = PipelineOrchestrator()

    # Sample Jira issue data
    jira_issue_key = "ANSIBLE-999"
    jira_data = {
        "summary": "Add AWS S3 bucket lifecycle policy module",
        "description": """
Create a new Ansible module to manage S3 bucket lifecycle policies.

The module should support:
- Creating lifecycle rules for transition and expiration
- Updating existing policies
- Deleting policies
- Idempotent operations
- Check mode support

Parameters needed:
- bucket_name (required)
- rules (list of lifecycle rules)
- state (present/absent)
- AWS credentials configuration
        """,
        "labels": ["aws", "s3", "module", "enhancement"],
        "components": ["amazon.aws"],
        "priority": "High",
        "acceptance_criteria": [
            "Module can create lifecycle policies",
            "Module supports check mode",
            "Module is idempotent",
            "Unit tests achieve >80% coverage",
            "Integration tests pass against real S3",
            "ansible-lint passes with no errors",
        ],
    }

    print(f"🚀 Starting test pipeline for {jira_issue_key}")
    print(f"📋 Summary: {jira_data['summary']}")
    print()

    try:
        correlation_id = await orchestrator.start_pipeline(jira_issue_key, jira_data)

        print(f"✅ Pipeline started")
        print(f"🔗 Correlation ID: {correlation_id}")
        print(f"📊 Monitor at: http://localhost:{orchestrator.message_bus or 8080}/api/pipeline/{correlation_id}")
        print()
        print("The pipeline will run through all stages:")
        print("  1. Jira Integration → Extract requirements")
        print("  2. Architect → Design architecture")
        print("  3. Developer → Implement code")
        print("  4. Tester → Create and run tests")
        print("  5. Code Reviewer → Review quality")
        print("  6. Release → Version and publish")
        print("  7. Certification → Validate compliance")
        print()

    except Exception as e:
        print(f"❌ Error starting pipeline: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    asyncio.run(test_pipeline())
