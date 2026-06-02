# Release Agent
FROM ansible-agent-base:latest

# Install release tools
RUN pip install --no-cache-dir \
    PyGithub \
    python-gitlab \
    semver \
    toml

# Copy agent-specific code
COPY agents/release/ ./agents/release/

# Set entrypoint
CMD ["python", "-m", "agents.release.agent"]
