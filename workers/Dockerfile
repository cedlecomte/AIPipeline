FROM ansible-agent-base:latest

COPY workers/ ./workers/

CMD ["python", "-m", "workers.agent_worker"]
