# Architect Agent
FROM ansible-agent-base:latest

# Copy agent-specific code
COPY agents/architect/ ./agents/architect/

# Set entrypoint
CMD ["python", "-m", "agents.architect.agent"]
