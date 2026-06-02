# Certification Agent
FROM ansible-agent-base:latest

# Install Ansible and validation tools
RUN pip install --no-cache-dir \
    ansible-core>=2.14 \
    ansible-lint>=6.0.0 \
    yamllint

# Copy agent-specific code
COPY agents/certification/ ./agents/certification/

# Set entrypoint
CMD ["python", "-m", "agents.certification.agent"]
