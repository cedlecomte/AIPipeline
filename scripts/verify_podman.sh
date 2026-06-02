#!/bin/bash
# Verify Podman migration and installation

set -e

echo "🔍 Verifying Podman Setup for Ansible Agent Pipeline"
echo "=========================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# 1. Check Podman installation
echo "1. Checking Podman installation..."
if command -v podman &> /dev/null; then
    VERSION=$(podman --version | awk '{print $3}')
    echo -e "${GREEN}✅ Podman installed: $VERSION${NC}"

    if [ "$(printf '%s\n' "4.0.0" "$VERSION" | sort -V | head -n1)" = "4.0.0" ]; then
        echo -e "${GREEN}   Version is 4.0.0 or higher ✓${NC}"
    else
        echo -e "${YELLOW}⚠️  Version is below 4.0.0${NC}"
    fi
else
    echo -e "${RED}❌ Podman not found${NC}"
    echo "   Install with: sudo dnf install podman"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 2. Check Compose
echo "2. Checking Compose tool..."
if command -v podman-compose &> /dev/null; then
    echo -e "${GREEN}✅ podman-compose installed${NC}"
elif podman compose version &> /dev/null 2>&1; then
    echo -e "${GREEN}✅ podman compose available${NC}"
else
    echo -e "${RED}❌ No compose tool found${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 3. Check rootless
echo "3. Checking rootless mode..."
if podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null | grep -q true; then
    echo -e "${GREEN}✅ Running rootless (recommended)${NC}"
else
    echo -e "${YELLOW}⚠️  Running rootful${NC}"
fi
echo ""

# 4. Test functionality
echo "4. Testing Podman..."
if podman run --rm alpine echo "Test passed" &> /dev/null; then
    echo -e "${GREEN}✅ Can run containers${NC}"
else
    echo -e "${RED}❌ Cannot run containers${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Summary
echo "=========================================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. make build"
    echo "  2. make start"
    echo "  3. Open http://localhost:8080"
    exit 0
else
    echo -e "${RED}❌ Found $ERRORS error(s)${NC}"
    echo ""
    echo "See INSTALL_PODMAN.md for help"
    exit 1
fi
