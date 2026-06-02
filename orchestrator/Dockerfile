# Orchestrator
FROM ansible-agent-base:latest

# Copy orchestrator code
COPY orchestrator/ ./orchestrator/

# Set entrypoint
CMD ["python", "-m", "orchestrator.pipeline"]
