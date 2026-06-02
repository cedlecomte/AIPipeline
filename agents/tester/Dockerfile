# Tester Agent
FROM ansible-agent-base:latest

# Install Ansible and testing tools
# Note: Using pip for Ansible to get latest version
# Fedora's ansible-core package can be used as alternative: dnf install ansible-core
RUN pip install --no-cache-dir \
    ansible-core>=2.14 \
    pytest>=8.0.0 \
    pytest-asyncio \
    pytest-mock \
    molecule \
    molecule-podman

# Copy agent-specific code
COPY agents/tester/ ./agents/tester/

# Set entrypoint
CMD ["python", "-m", "agents.tester.agent"]
