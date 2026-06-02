# Developer Agent
FROM ansible-agent-base:latest

# Copy agent-specific code
COPY agents/developer/ ./agents/developer/

# Set entrypoint
CMD ["python", "-m", "agents.developer.agent"]
