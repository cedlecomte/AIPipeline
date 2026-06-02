# Ansible Agent Pipeline

Multi-agent system for automated Ansible collection development using Claude AI via Google VertexAI.

## Overview

**Input**: Jira issue → **Output**: Production-ready Ansible collection  
**Time**: 20-45 minutes, fully autonomous

7 AI agents working together:
1. **Jira Integration** - Extracts requirements
2. **Architect** - Designs architecture
3. **Developer** - Writes Ansible code
4. **Tester** - Creates and runs tests
5. **Code Reviewer** - Security & quality review
6. **Release** - Versioning & publishing
7. **Certification** - Galaxy validation

## Stack

- **OS**: Fedora 44 (container base: `fedora:latest`)
- **Container**: Podman (rootless, daemonless)
- **AI**: Claude Opus 4.7 via Google VertexAI
- **Backend**: Python 3.11, Redis, FastAPI
- **Security**: SELinux, rootless containers

## Quick Start

### Prerequisites

```bash
# Already on Fedora 44
podman --version          # 5.0+
podman-compose --version  # or podman compose
python3 --version         # 3.11+
```

### Setup

```bash
cd /home/cedric/storage/Sources/SDLC_Ansible/ansible-agent-pipeline

# 1. Auth VertexAI
gcloud auth application-default login

# 2. Config
cat > .env << 'EOF'
ANTHROPIC_VERTEX_PROJECT_ID=your-project-id
CLOUD_ML_REGION=global
GITHUB_TOKEN=ghp_your_token
REDIS_HOST=redis
AGENT_MODEL=claude-opus-4-7
AGENT_EFFORT=xhigh
YOLO_MODE=true
DASHBOARD_PORT=8080
EOF

# 3. Pre-pull Redis (fix registry issue)
podman pull docker.io/redis:7-alpine

# 4. Build & Start
make build
make start

# 5. Verify
make status
python scripts/health_check.py

# 6. Dashboard
firefox http://localhost:8080
```

## VertexAI Authentication

Credentials are mounted from your Fedora 44 host to containers:

```yaml
# In podman-compose.yml (already configured)
volumes:
  - ${HOME}/.config/gcloud:/root/.config/gcloud:ro,z
```

**Required IAM Role**: `roles/aiplatform.user` (same as Claude Code)

**Give permission**:
```bash
gcloud projects add-iam-policy-binding $ANTHROPIC_VERTEX_PROJECT_ID \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/aiplatform.user"
```

## Configuration

### Required Variables

```bash
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
CLOUD_ML_REGION=global  # or us-east5, europe-west1
```

### Optional Variables

```bash
# Agent tuning
AGENT_MODEL=claude-opus-4-7  # or claude-sonnet-4-6
AGENT_EFFORT=xhigh           # xhigh|high|medium|low
AGENT_MAX_TOKENS=64000
YOLO_MODE=true               # Fully autonomous

# Git platform
GITHUB_TOKEN=ghp_token
GIT_PLATFORM=github
GIT_REPO_OWNER=ansible-collections
GIT_REPO_NAME=amazon.aws

# Jira (optional)
JIRA_CLOUD_ID=your-site.atlassian.net
JIRA_API_TOKEN=your_token
```

## Usage

### Via Dashboard

1. Open http://localhost:8080
2. Enter Jira issue key: `TEST-001`
3. Add issue data or use default
4. Click "Start Pipeline"
5. Watch agents progress through 7 stages

### Via API

```bash
curl -X POST http://localhost:8080/api/pipeline/start \
  -H "Content-Type: application/json" \
  -d '{
    "jira_issue_key": "ANSIBLE-123",
    "jira_data": {
      "summary": "Add AWS S3 encryption module",
      "description": "Module for S3 bucket encryption",
      "labels": ["aws", "s3"],
      "priority": "High"
    }
  }'
```

### Via Python

```bash
python examples/full_pipeline_example.py
```

## Commands

```bash
make build              # Build all images
make start              # Start all services
make stop               # Stop all services
make restart            # Restart
make logs               # View all logs
make logs-agent         # View specific agent
make status             # Service status
make clean              # Remove everything
make trigger-pipeline   # Start test pipeline
```

## Project Structure

```
ansible-agent-pipeline/
├── agents/               # 7 AI agents
│   ├── jira_integration/
│   ├── architect/
│   ├── developer/
│   ├── tester/
│   ├── code_reviewer/
│   ├── release/
│   └── certification/
├── shared/
│   ├── models/           # Pydantic models
│   └── utils/            # Message bus, Claude client
├── orchestrator/         # Pipeline coordinator
├── dashboard/            # FastAPI web UI
├── docker-compose.yml    # Podman compose (podman-compose default filename)
├── Dockerfile.base       # Fedora:latest base
└── Makefile              # Commands
```

## Troubleshooting

### VertexAI Auth Error

```bash
# Re-authenticate
gcloud auth application-default login

# Verify
gcloud auth application-default print-access-token

# Enable API
gcloud services enable aiplatform.googleapis.com
```

### Redis Connection Error

```bash
# Check Redis
podman exec ansible-pipeline-redis redis-cli ping
# Should return: PONG

# Restart
podman restart ansible-pipeline-redis
```

### Agent Not Responding

```bash
# View logs
make logs-agent
# Or: podman logs ansible-pipeline-<agent-name>

# Restart
podman restart ansible-pipeline-<agent-name>
```

### Registry Error (manifest unknown)

The `docker-compose.yml` now specifies `docker.io/redis:7-alpine` explicitly to avoid Podman searching wrong registry.

Pre-pull if needed:
```bash
podman pull docker.io/redis:7-alpine
```

## Production Deployment

### systemd Services (Fedora/RHEL)

```bash
# Generate systemd units
./scripts/generate_systemd_units.sh

# Enable auto-start
systemctl --user enable ansible-pipeline-*.service
loginctl enable-linger $USER

# Start
systemctl --user start ansible-pipeline-*.service
```

### Service Account (Production)

```bash
# Create service account
gcloud iam service-accounts create ansible-agents \
    --display-name="Ansible Pipeline"

# Grant permissions
gcloud projects add-iam-policy-binding $ANTHROPIC_VERTEX_PROJECT_ID \
    --member="serviceAccount:ansible-agents@PROJECT.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Create key
gcloud iam service-accounts keys create ./sa-key.json \
    --iam-account=ansible-agents@PROJECT.iam.gserviceaccount.com

# Use in .env
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
```

## Monitoring

**Dashboard**: http://localhost:8080
- Real-time agent status
- Pipeline progress
- Event logs

**Logs**:
```bash
make logs                    # All services
podman logs <container>      # Specific
journalctl -f CONTAINER_NAME=ansible-pipeline-orchestrator  # systemd
```

**Health**:
```bash
python scripts/health_check.py
```

## Architecture

Redis message bus connects all agents. Orchestrator coordinates workflow:

```
Jira → Requirements → Architecture → Code → Tests → Review → Release → Certification → Published
```

Each agent:
- Receives task via Redis pub/sub
- Calls Claude via VertexAI
- Stores artifacts in Redis
- Sends to next agent

## Cost

With Claude Opus 4.7:
- ~$4-5 per pipeline run
- ~155K tokens average
- Use Sonnet 4.6 for ~$1-2 per run

## Security

- Rootless Podman containers
- SELinux mandatory access control
- No credentials in code
- Audit trail in logs

## Development

### Add New Agent

1. Create: `mkdir -p agents/new_agent`
2. Implement extending `BaseAgent`
3. Create Dockerfile
4. Add to docker-compose.yml
5. Update `AgentType` enum
6. `make build`

### Modify Agent Behavior

Edit `agents/*/agent.py`:

```python
def get_system_prompt(self):
    return "Your custom instructions..."
```

Restart: `make restart`

## License

MIT
