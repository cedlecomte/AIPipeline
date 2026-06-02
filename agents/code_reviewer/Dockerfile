# Code Reviewer Agent
FROM ansible-agent-base:latest

# Install code analysis tools
RUN pip install --no-cache-dir \
    ansible-lint>=6.0.0 \
    pylint \
    black \
    ruff \
    bandit

# Copy agent-specific code
COPY agents/code_reviewer/ ./agents/code_reviewer/

# Set entrypoint
CMD ["python", "-m", "agents.code_reviewer.agent"]
