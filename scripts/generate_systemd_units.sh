#!/bin/bash
# Generate systemd unit files for all Ansible Agent Pipeline services

set -e

echo "🔧 Generating systemd unit files for Ansible Agent Pipeline"
echo "============================================================="
echo ""

# Check if services are running
if ! podman ps | grep -q ansible-pipeline; then
    echo "⚠️  Warning: No ansible-pipeline containers are running"
    echo "   Start services first with: make start"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create systemd user directory
mkdir -p ~/.config/systemd/user

# List of all services
SERVICES=(
    "redis"
    "jira-agent"
    "architect-agent"
    "developer-agent"
    "tester-agent"
    "reviewer-agent"
    "release-agent"
    "certification-agent"
    "orchestrator"
    "dashboard"
)

echo "Generating unit files..."
echo ""

GENERATED=0
FAILED=0

for service in "${SERVICES[@]}"; do
    CONTAINER_NAME="ansible-pipeline-$service"
    UNIT_FILE="$HOME/.config/systemd/user/ansible-pipeline-$service.service"

    echo -n "  $service ... "

    if podman generate systemd \
        --new \
        --name "$CONTAINER_NAME" \
        --restart-policy=always \
        --start-timeout=90 \
        --stop-timeout=30 \
        > "$UNIT_FILE" 2>/dev/null; then

        echo "✅"
        GENERATED=$((GENERATED + 1))
    else
        echo "❌ (container may not exist)"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "============================================================="
echo "Generated $GENERATED unit files"
echo ""

if [ $GENERATED -gt 0 ]; then
    echo "Unit files created in: ~/.config/systemd/user/"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Reload systemd:"
    echo "   systemctl --user daemon-reload"
    echo ""
    echo "2. Enable services (auto-start on boot):"
    echo "   systemctl --user enable ansible-pipeline-*.service"
    echo ""
    echo "3. Enable linger (survive logout):"
    echo "   loginctl enable-linger \$USER"
    echo ""
    echo "4. Start services:"
    echo "   systemctl --user start ansible-pipeline-*.service"
    echo ""
    echo "5. Check status:"
    echo "   systemctl --user status ansible-pipeline-*.service"
    echo ""
    echo "Management commands:"
    echo "  systemctl --user stop ansible-pipeline-redis.service"
    echo "  systemctl --user restart ansible-pipeline-orchestrator.service"
    echo "  systemctl --user disable ansible-pipeline-*.service"
    echo ""

    # Offer to enable now
    read -p "Enable all services now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl --user daemon-reload
        systemctl --user enable ansible-pipeline-*.service
        loginctl enable-linger $USER

        echo ""
        echo "✅ All services enabled!"
        echo ""
        echo "Start them with:"
        echo "  systemctl --user start ansible-pipeline-*.service"
        echo ""
        echo "Or individually:"
        echo "  systemctl --user start ansible-pipeline-redis.service"
        echo "  systemctl --user start ansible-pipeline-orchestrator.service"
        echo ""
    fi
else
    echo "❌ No unit files generated"
    echo ""
    echo "Make sure containers are running first:"
    echo "  make start"
    echo ""
fi

if [ $FAILED -gt 0 ]; then
    echo "⚠️  $FAILED services could not be converted"
    echo "   Start those containers first with: make start"
    echo ""
fi
