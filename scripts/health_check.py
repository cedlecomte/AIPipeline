#!/usr/bin/env python3
"""Health check script for all services."""

import asyncio
import sys

import redis.asyncio as redis
import structlog
from anthropic import AnthropicVertex

from config.settings import settings

logger = structlog.get_logger()


async def check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        await client.close()
        logger.info("health_check.redis", status="OK")
        return True
    except Exception as e:
        logger.error("health_check.redis", status="FAILED", error=str(e))
        return False


async def check_vertexai() -> bool:
    """Check VertexAI connectivity."""
    try:
        client = AnthropicVertex(
            project_id=settings.google_cloud_project,
            region=settings.google_cloud_location,
        )

        # Simple API call to verify auth
        response = client.messages.create(
            model=settings.agent_model,
            max_tokens=50,
            messages=[{"role": "user", "content": "Hello"}],
        )

        if response.content:
            logger.info("health_check.vertexai", status="OK", model=settings.agent_model)
            return True

        return False

    except Exception as e:
        logger.error("health_check.vertexai", status="FAILED", error=str(e))
        return False


async def check_message_bus() -> bool:
    """Check message bus functionality."""
    try:
        from shared.utils.message_bus import MessageBus

        bus = MessageBus(settings.redis_url)
        await bus.connect()

        # Try to publish and receive a test message
        test_key = "test:health_check"
        await bus.client.set(test_key, "OK")
        value = await bus.client.get(test_key)
        await bus.client.delete(test_key)

        await bus.disconnect()

        if value == "OK":
            logger.info("health_check.message_bus", status="OK")
            return True

        return False

    except Exception as e:
        logger.error("health_check.message_bus", status="FAILED", error=str(e))
        return False


async def main() -> None:
    """Run all health checks."""
    print("🏥 Running health checks...\n")

    checks = {
        "Redis": check_redis(),
        "VertexAI": check_vertexai(),
        "Message Bus": check_message_bus(),
    }

    results = {}
    for name, check_coro in checks.items():
        print(f"Checking {name}...", end=" ")
        results[name] = await check_coro
        print("✅ OK" if results[name] else "❌ FAILED")

    print("\n" + "=" * 50)

    if all(results.values()):
        print("✅ All health checks passed!")
        sys.exit(0)
    else:
        print("❌ Some health checks failed")
        print("\nFailed checks:")
        for name, passed in results.items():
            if not passed:
                print(f"  - {name}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
