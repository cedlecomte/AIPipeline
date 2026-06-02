# Jira Integration Agent
FROM ansible-agent-base:latest

# Copy agent-specific code
COPY agents/jira_integration/ ./agents/jira_integration/

# Set entrypoint
CMD ["python", "-m", "agents.jira_integration.agent"]
