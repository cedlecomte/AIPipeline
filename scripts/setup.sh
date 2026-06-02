#!/bin/bash
# Setup script for the Ansible Agent Pipeline

set -e

echo "🚀 Setting up Ansible Agent Pipeline (Podman)..."

# Check prerequisites
command -v podman >/dev/null 2>&1 || { echo "❌ Podman is required but not installed. Aborting." >&2; exit 1; }

# Check for podman-compose or podman compose
if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE="podman-compose"
elif podman compose version >/dev/null 2>&1; then
    COMPOSE="podman compose"
else
    echo "❌ Neither podman-compose nor 'podman compose' is available. Please install podman-compose." >&2
    exit 1
fi

echo "✅ Using: $COMPOSE"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your credentials before continuing"
    exit 0
fi

# Verify required environment variables
source .env

if [ -z "$ANTHROPIC_VERTEX_PROJECT_ID" ]; then
    echo "❌ ANTHROPIC_VERTEX_PROJECT_ID not set in .env"
    exit 1
fi

if [ -z "$CLOUD_ML_REGION" ]; then
    echo "❌ CLOUD_ML_REGION not set in .env"
    exit 1
fi

# Check for authentication
# VertexAI uses Google Cloud Application Default Credentials
# Either gcloud auth or service account JSON
if [ ! -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        echo "❌ Service account file not found: $GOOGLE_APPLICATION_CREDENTIALS"
        exit 1
    fi
    echo "✅ Using service account: $GOOGLE_APPLICATION_CREDENTIALS"
else
    # Check if gcloud auth is configured
    if ! gcloud auth application-default print-access-token &>/dev/null; then
        echo "⚠️  No authentication configured!"
        echo "   Run: gcloud auth application-default login"
        echo "   Or set: GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
        exit 1
    fi
    echo "✅ Using gcloud application-default credentials"
fi

echo "✅ Prerequisites check passed"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs test_results outputs

# Build Podman images
echo "🏗️  Building Podman images..."
podman build -t ansible-agent-base:latest -f Dockerfile.base .
$COMPOSE build

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Review and update .env with your credentials"
echo "  2. Run: make start"
echo "  3. Open dashboard: http://localhost:${DASHBOARD_PORT:-8080}"
echo ""
