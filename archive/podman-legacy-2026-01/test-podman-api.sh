#!/usr/bin/env bash
#
# Test Podman API Infrastructure
# Validates that Podman API is working before updating services
#
# Usage: ./scripts/test-podman-api.sh
#
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}[✗]${NC} $*"
    ((TESTS_FAILED++))
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

test_step() {
    ((TESTS_TOTAL++))
    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Test $TESTS_TOTAL: $*${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Test 1: Check if Podman is installed
test_podman_installed() {
    test_step "Check Podman Installation"

    if command -v podman &> /dev/null; then
        PODMAN_VERSION=$(podman --version)
        log_success "Podman is installed: $PODMAN_VERSION"
        return 0
    else
        log_fail "Podman is not installed"
        echo "  Install Podman first: sudo dnf install podman"
        return 1
    fi
}

# Test 2: Check if Podman API socket is enabled
test_podman_api_enabled() {
    test_step "Check Podman API Socket"

    # Try user mode first
    if systemctl --user is-active --quiet podman.socket 2>/dev/null; then
        log_success "Podman API socket is active (user mode)"
        SOCKET_PATH=$(systemctl --user show podman.socket -p Listen 2>/dev/null | cut -d= -f2 || echo "unknown")
        log_info "Socket: $SOCKET_PATH"
        return 0
    # Try system mode
    elif systemctl is-active --quiet podman.socket 2>/dev/null; then
        log_success "Podman API socket is active (system mode)"
        return 0
    else
        log_fail "Podman API socket is not active"
        echo "  Run: ./scripts/setup-podman-api.sh"
        return 1
    fi
}

# Test 3: Test API connectivity via HTTP
test_api_http_connectivity() {
    test_step "Test Podman API HTTP Connectivity"

    # Try localhost:2375 (system mode or user mode with port forwarding)
    if curl -s -f http://localhost:2375/v4.0.0/libpod/info > /tmp/podman-api-test.json 2>/dev/null; then
        log_success "Podman API responding on http://localhost:2375"

        # Parse and display info
        if command -v jq &> /dev/null; then
            PODMAN_VERSION=$(jq -r '.version.Version' /tmp/podman-api-test.json 2>/dev/null || echo "unknown")
            OS=$(jq -r '.host.os' /tmp/podman-api-test.json 2>/dev/null || echo "unknown")
            ARCH=$(jq -r '.host.arch' /tmp/podman-api-test.json 2>/dev/null || echo "unknown")
            log_info "Podman Version: $PODMAN_VERSION"
            log_info "OS: $OS"
            log_info "Architecture: $ARCH"
        fi

        rm -f /tmp/podman-api-test.json
        return 0
    else
        log_fail "Cannot reach Podman API on http://localhost:2375"
        echo "  The API may be on a Unix socket instead of HTTP"
        echo "  Run: ./scripts/setup-podman-api.sh"
        return 1
    fi
}

# Test 4: Test API - List containers
test_api_list_containers() {
    test_step "Test API - List Containers"

    if curl -s -f http://localhost:2375/v4.0.0/libpod/containers/json > /tmp/podman-containers.json 2>/dev/null; then
        if command -v jq &> /dev/null; then
            CONTAINER_COUNT=$(jq '. | length' /tmp/podman-containers.json)
            log_success "API can list containers: $CONTAINER_COUNT containers found"

            # List container names
            if [ "$CONTAINER_COUNT" -gt 0 ]; then
                log_info "Containers:"
                jq -r '.[].Names[]' /tmp/podman-containers.json | head -5 | while read name; do
                    echo "  - $name"
                done
            fi
        else
            log_success "API can list containers (jq not installed for detailed output)"
        fi

        rm -f /tmp/podman-containers.json
        return 0
    else
        log_fail "Cannot list containers via API"
        return 1
    fi
}

# Test 5: Test API - Get specific container (if any exist)
test_api_get_container() {
    test_step "Test API - Get Container Details"

    # Get first container name
    FIRST_CONTAINER=$(curl -s http://localhost:2375/v4.0.0/libpod/containers/json 2>/dev/null | jq -r '.[0].Names[0]' 2>/dev/null || echo "")

    if [ -z "$FIRST_CONTAINER" ] || [ "$FIRST_CONTAINER" = "null" ]; then
        log_warn "No containers running, skipping container details test"
        return 0
    fi

    if curl -s -f "http://localhost:2375/v4.0.0/libpod/containers/$FIRST_CONTAINER/json" > /tmp/podman-container-detail.json 2>/dev/null; then
        if command -v jq &> /dev/null; then
            CONTAINER_STATE=$(jq -r '.State.Status' /tmp/podman-container-detail.json)
            CONTAINER_IMAGE=$(jq -r '.Config.Image' /tmp/podman-container-detail.json)
            log_success "API can get container details: $FIRST_CONTAINER"
            log_info "State: $CONTAINER_STATE"
            log_info "Image: $CONTAINER_IMAGE"
        else
            log_success "API can get container details"
        fi

        rm -f /tmp/podman-container-detail.json
        return 0
    else
        log_fail "Cannot get container details via API"
        return 1
    fi
}

# Test 6: Test Python API client library
test_python_api_client() {
    test_step "Test Python API Client Library"

    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        log_warn "Python3 not found, skipping Python client test"
        return 0
    fi

    # Check if required packages are installed
    if ! python3 -c "import httpx, structlog" 2>/dev/null; then
        log_warn "Required Python packages not installed (httpx, structlog)"
        log_info "Install: pip install httpx structlog"
        return 0
    fi

    # Create test script
    cat > /tmp/test_api_client.py <<'EOF'
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/ai-stack/mcp-servers')

from shared.podman_api_client import PodmanAPIClient

async def test_client():
    """Test the API client library"""
    try:
        # Create client
        async with PodmanAPIClient(
            service_name="test-service",
            allowed_operations=["list", "inspect"],
            audit_enabled=False  # Don't write audit log during test
        ) as client:
            # Test 1: List containers
            containers = await client.list_containers()
            print(f"✓ Listed {len(containers)} containers")

            # Test 2: Get first container (if any)
            if containers:
                first_container = containers[0].get('Names', ['unknown'])[0]
                container_info = await client.get_container(first_container)
                print(f"✓ Got details for container: {first_container}")
                print(f"  State: {container_info['State']['Status']}")
            else:
                print("⚠ No containers to inspect")

            print("✓ All API client tests passed")
            return True

    except Exception as e:
        print(f"✗ API client test failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_client())
    sys.exit(0 if result else 1)
EOF

    # Run test
    if python3 /tmp/test_api_client.py 2>/dev/null; then
        log_success "Python API client library works correctly"
        rm -f /tmp/test_api_client.py
        return 0
    else
        log_fail "Python API client library test failed"
        echo "  Check if httpx and structlog are installed"
        echo "  pip install httpx structlog"
        rm -f /tmp/test_api_client.py
        return 1
    fi
}

# Test 7: Test from inside a container (Docker network connectivity)
test_api_from_container() {
    test_step "Test API Access from Container (host.containers.internal)"

    # Check if we have any running containers to test with
    RUNNING_CONTAINER=$(podman ps --format "{{.Names}}" --filter "status=running" | head -1)

    if [ -z "$RUNNING_CONTAINER" ]; then
        log_warn "No running containers, skipping container network test"
        log_info "This test validates that containers can reach host.containers.internal"
        return 0
    fi

    log_info "Testing from container: $RUNNING_CONTAINER"

    # Test if container can reach the API
    if podman exec "$RUNNING_CONTAINER" curl -s -f http://host.containers.internal:2375/v4.0.0/libpod/info > /dev/null 2>&1; then
        log_success "Container can reach Podman API via host.containers.internal"
        return 0
    else
        log_fail "Container cannot reach host.containers.internal:2375"
        echo "  This may be a network configuration issue"
        echo "  Containers need extra_hosts: - 'host.containers.internal:host-gateway'"
        return 1
    fi
}

# Test 8: Check .env file configuration
test_env_configuration() {
    test_step "Check .env File Configuration"

    ENV_FILE="ai-stack/compose/.env"

    if [ ! -f "$ENV_FILE" ]; then
        log_fail ".env file not found at $ENV_FILE"
        return 1
    fi

    # Check for Podman API configuration
    if grep -q "PODMAN_API_URL=" "$ENV_FILE"; then
        PODMAN_API_URL=$(grep "PODMAN_API_URL=" "$ENV_FILE" | cut -d= -f2)
        log_success ".env file has PODMAN_API_URL: $PODMAN_API_URL"
    else
        log_fail ".env file missing PODMAN_API_URL"
        echo "  Run: ./scripts/setup-podman-api.sh"
        return 1
    fi

    # Check for audit logging configuration
    if grep -q "CONTAINER_AUDIT_ENABLED=" "$ENV_FILE"; then
        log_success ".env file has audit logging configured"
    else
        log_warn ".env file missing audit logging configuration"
        echo "  Run: ./scripts/setup-podman-api.sh"
    fi

    # Check for operation allowlists
    if grep -q "ALLOWED_OPS=" "$ENV_FILE"; then
        log_success ".env file has operation allowlists configured"
    else
        log_warn ".env file missing operation allowlists"
        echo "  Run: ./scripts/setup-podman-api.sh"
    fi

    return 0
}

# Display summary
show_summary() {
    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}TEST SUMMARY${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    echo "Total Tests: $TESTS_TOTAL"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    echo

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo
        echo "Infrastructure is ready for service updates!"
        echo
        echo "Next steps:"
        echo "1. Update service code to use Podman API"
        echo "2. Update docker-compose.yml"
        echo "3. Deploy and test"
        return 0
    else
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${RED}✗ SOME TESTS FAILED${NC}"
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo
        echo "Fix the failed tests before proceeding:"
        echo
        if [ $TESTS_FAILED -le 2 ]; then
            echo "Most likely fix: Run ./scripts/setup-podman-api.sh"
        else
            echo "Review the test output above for specific issues"
        fi
        return 1
    fi
}

# Main execution
main() {
    echo
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       Podman API Infrastructure Validation Tests          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

    # Change to project root
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR/.."

    # Run all tests
    test_podman_installed
    test_podman_api_enabled
    test_api_http_connectivity
    test_api_list_containers
    test_api_get_container
    test_python_api_client
    test_api_from_container
    test_env_configuration

    # Show summary
    show_summary
}

# Run main function
main "$@"
