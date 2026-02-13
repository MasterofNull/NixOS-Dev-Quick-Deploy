#!/usr/bin/env bash
# Test script for Day 5 password migration validation
# Tests PostgreSQL, Redis, and Grafana with new Docker secrets-based passwords

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$PROJECT_ROOT/ai-stack/compose"
SECRETS_DIR="$COMPOSE_DIR/secrets"
COMPOSE_CMD=""
CONTAINER_CMD=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
    ((TESTS_PASSED++)) || true
}

log_error() {
    echo -e "${RED}[✗]${NC} $*"
    ((TESTS_FAILED++)) || true
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $*"
}

detect_compose() {
    if command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD="podman-compose"
        CONTAINER_CMD="podman"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
        CONTAINER_CMD="docker"
    elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
        CONTAINER_CMD="docker"
    else
        COMPOSE_CMD=""
        CONTAINER_CMD=""
    fi
}

# Test result function
test_result() {
    ((TESTS_TOTAL++)) || true
    if [ $1 -eq 0 ]; then
        log_success "$2"
    else
        log_error "$2"
    fi
}

# Check if secrets exist
check_secrets_exist() {
    log_info "Checking if password secrets exist..."

    local secrets=("postgres_password" "redis_password" "grafana_admin_password")
    local all_exist=true

    for secret in "${secrets[@]}"; do
        if [ -f "$SECRETS_DIR/$secret" ]; then
            log_success "Secret file exists: $secret"
            # Check permissions
            local perms
            perms=$(stat -c "%a" "$SECRETS_DIR/$secret" 2>/dev/null || stat -f "%OLp" "$SECRETS_DIR/$secret" 2>/dev/null || echo "unknown")
            if [ "$perms" = "600" ]; then
                log_success "Correct permissions (600) on $secret"
            else
                log_warning "Permissions on $secret are $perms (expected 600)"
            fi
        else
            log_error "Secret file missing: $secret"
            all_exist=false
        fi
    done

    if [ "$all_exist" = true ]; then
        return 0
    else
        return 1
    fi
}

# Test PostgreSQL connection
test_postgres_connection() {
    log_info "Testing PostgreSQL connection with new password..."

    # Read password from secret file
    local postgres_password
    if [ -f "$SECRETS_DIR/postgres_password" ]; then
        postgres_password=$(cat "$SECRETS_DIR/postgres_password")
    else
        log_error "PostgreSQL password file not found"
        return 1
    fi

    # Test connection using psql in docker
    cd "$COMPOSE_DIR"

    local postgres_running=false
    if [[ "$CONTAINER_CMD" == "podman" ]]; then
        if podman ps --format '{{.Names}}' | grep -q '^local-ai-postgres$'; then
            postgres_running=true
        fi
    else
        if $COMPOSE_CMD ps postgres | grep -q "Up"; then
            postgres_running=true
        fi
    fi

    if [[ "$postgres_running" == "true" ]]; then
        log_info "PostgreSQL container is running, testing connection..."

        # Test connection with password
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if PGPASSWORD="$postgres_password" podman exec -i local-ai-postgres psql -h 127.0.0.1 -U mcp -d mcp -c "SELECT 1;" &>/dev/null; then
                test_result 0 "PostgreSQL connection successful with new password"
            else
                test_result 1 "PostgreSQL connection failed with new password"
                return 1
            fi
        elif PGPASSWORD="$postgres_password" $COMPOSE_CMD exec -T postgres psql -h 127.0.0.1 -U mcp -d mcp -c "SELECT 1;" &>/dev/null; then
            test_result 0 "PostgreSQL connection successful with new password"
        else
            test_result 1 "PostgreSQL connection failed with new password"
            return 1
        fi

        # If localhost trust is enabled in pg_hba.conf, skip old-password test.
        local trust_enabled=false
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if podman exec -i local-ai-postgres sh -c "grep -qE '^host\\s+all\\s+all\\s+127\\.0\\.0\\.1/32\\s+trust' /var/lib/postgresql/data/pgdata/pg_hba.conf" >/dev/null 2>&1; then
                trust_enabled=true
            fi
        else
            if $COMPOSE_CMD exec -T postgres sh -c "grep -qE '^host\\s+all\\s+all\\s+127\\.0\\.0\\.1/32\\s+trust' /var/lib/postgresql/data/pgdata/pg_hba.conf" >/dev/null 2>&1; then
                trust_enabled=true
            fi
        fi

        if [[ "$trust_enabled" == "true" ]]; then
            log_warning "PostgreSQL allows trust auth for localhost; skipping old-password rejection test."
        else
            # Test that old password fails (if different)
            if [[ "$CONTAINER_CMD" == "podman" ]]; then
                if PGPASSWORD="change_me_in_production" podman exec -i local-ai-postgres psql -h 127.0.0.1 -U mcp -d mcp -c "SELECT 1;" &>/dev/null; then
                    test_result 1 "OLD PASSWORD STILL WORKS - SECURITY ISSUE!"
                    return 1
                else
                    test_result 0 "Old default password correctly rejected"
                fi
            elif PGPASSWORD="change_me_in_production" $COMPOSE_CMD exec -T postgres psql -h 127.0.0.1 -U mcp -d mcp -c "SELECT 1;" &>/dev/null; then
                test_result 1 "OLD PASSWORD STILL WORKS - SECURITY ISSUE!"
                return 1
            else
                test_result 0 "Old default password correctly rejected"
            fi
        fi

        # Test database exists and is accessible
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if PGPASSWORD="$postgres_password" podman exec -i local-ai-postgres psql -h 127.0.0.1 -U mcp -d mcp -c "\dt" &>/dev/null; then
                test_result 0 "PostgreSQL database 'mcp' is accessible"
            else
                test_result 1 "PostgreSQL database 'mcp' not accessible"
            fi
        elif PGPASSWORD="$postgres_password" $COMPOSE_CMD exec -T postgres psql -h 127.0.0.1 -U mcp -d mcp -c "\dt" &>/dev/null; then
            test_result 0 "PostgreSQL database 'mcp' is accessible"
        else
            test_result 1 "PostgreSQL database 'mcp' not accessible"
        fi

    else
        log_warning "PostgreSQL container not running, skipping connection test"
        return 1
    fi
}

# Test Redis connection
test_redis_connection() {
    log_info "Testing Redis connection with new password..."

    # Read password from secret file
    local redis_password
    if [ -f "$SECRETS_DIR/redis_password" ]; then
        redis_password=$(cat "$SECRETS_DIR/redis_password")
    else
        log_error "Redis password file not found"
        return 1
    fi

    cd "$COMPOSE_DIR"

    local redis_running=false
    if [[ "$CONTAINER_CMD" == "podman" ]]; then
        if podman ps --format '{{.Names}}' | grep -q '^local-ai-redis$'; then
            redis_running=true
        fi
    else
        if $COMPOSE_CMD ps redis | grep -q "Up"; then
            redis_running=true
        fi
    fi

    if [[ "$redis_running" == "true" ]]; then
        log_info "Redis container is running, testing connection..."

        # Test connection with password
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if podman exec -i local-ai-redis redis-cli -a "$redis_password" ping 2>/dev/null | grep -q "PONG"; then
                test_result 0 "Redis connection successful with new password"
            else
                test_result 1 "Redis connection failed with new password"
                return 1
            fi
        elif $COMPOSE_CMD exec -T redis redis-cli -a "$redis_password" ping 2>/dev/null | grep -q "PONG"; then
            test_result 0 "Redis connection successful with new password"
        else
            test_result 1 "Redis connection failed with new password"
            return 1
        fi

        # Test that no password fails
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if podman exec -i local-ai-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
                test_result 1 "Redis allows connection without password - SECURITY ISSUE!"
                return 1
            else
                test_result 0 "Redis correctly requires authentication"
            fi
        elif $COMPOSE_CMD exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
            test_result 1 "Redis allows connection without password - SECURITY ISSUE!"
            return 1
        else
            test_result 0 "Redis correctly requires authentication"
        fi

        # Test basic operations
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if podman exec -i local-ai-redis redis-cli -a "$redis_password" SET test_key "test_value" 2>/dev/null | grep -q "OK"; then
                test_result 0 "Redis SET operation successful"
                podman exec -i local-ai-redis redis-cli -a "$redis_password" DEL test_key &>/dev/null
            else
                test_result 1 "Redis SET operation failed"
            fi
        elif $COMPOSE_CMD exec -T redis redis-cli -a "$redis_password" SET test_key "test_value" 2>/dev/null | grep -q "OK"; then
            test_result 0 "Redis SET operation successful"
            $COMPOSE_CMD exec -T redis redis-cli -a "$redis_password" DEL test_key &>/dev/null
        else
            test_result 1 "Redis SET operation failed"
        fi

    else
        log_warning "Redis container not running, skipping connection test"
        return 1
    fi
}

# Test Grafana admin login
test_grafana_login() {
    log_info "Testing Grafana admin login with new password..."

    # Read password from secret file
    local grafana_password
    if [ -f "$SECRETS_DIR/grafana_admin_password" ]; then
        grafana_password=$(cat "$SECRETS_DIR/grafana_admin_password")
    else
        log_error "Grafana password file not found"
        return 1
    fi

    cd "$COMPOSE_DIR"

    local grafana_running=false
    if [[ "$CONTAINER_CMD" == "podman" ]]; then
        if podman ps --format '{{.Names}}' | grep -q '^local-ai-grafana$'; then
            grafana_running=true
        fi
    else
        if $COMPOSE_CMD ps grafana | grep -q "Up"; then
            grafana_running=true
        fi
    fi

    if [[ "$grafana_running" == "true" ]]; then
        log_info "Grafana container is running, testing login..."

        # Get Grafana port
        local grafana_port=""
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            grafana_port=$(podman port local-ai-grafana 3000/tcp 2>/dev/null | awk -F: 'NR==1{print $2}')
        else
            grafana_port=$($COMPOSE_CMD port grafana 3000 2>/dev/null | cut -d: -f2)
        fi
        if [ -z "$grafana_port" ]; then
            grafana_port=3000
        fi

        # Wait for Grafana to be ready
        local max_wait=30
        local waited=0
        while ! curl -s --max-time 5 --connect-timeout 3 http://${SERVICE_HOST:-localhost}:${grafana_port}/api/health &>/dev/null; do
            if [ $waited -ge $max_wait ]; then
                log_error "Grafana not responding after ${max_wait}s"
                return 1
            fi
            sleep 1
            ((waited++))
        done

        # Test login with new password
        if curl -s --max-time 5 --connect-timeout 3 -u "admin:$grafana_password" http://${SERVICE_HOST:-localhost}:${grafana_port}/api/org 2>/dev/null | grep -q "id"; then
            test_result 0 "Grafana login successful with new password"
        else
            test_result 1 "Grafana login failed with new password"
            return 1
        fi

        # Test that old default password fails
        if curl -s --max-time 5 --connect-timeout 3 -u "admin:admin" http://${SERVICE_HOST:-localhost}:${grafana_port}/api/org 2>/dev/null | grep -q "id"; then
            test_result 1 "OLD PASSWORD STILL WORKS - SECURITY ISSUE!"
            return 1
        else
            test_result 0 "Old default password correctly rejected"
        fi

    else
        log_warning "Grafana container not running, skipping login test"
        return 0
    fi
}

# Test service connectivity to databases
test_service_connectivity() {
    log_info "Testing service connectivity to databases..."

    cd "$COMPOSE_DIR"

    # Check if AIDB service can connect to PostgreSQL
    local aidb_running=false
    if [[ "$CONTAINER_CMD" == "podman" ]]; then
        if podman ps --format '{{.Names}}' | grep -q '^local-ai-aidb$'; then
            aidb_running=true
        fi
    else
        if $COMPOSE_CMD ps aidb | grep -q "Up"; then
            aidb_running=true
        fi
    fi

    if [[ "$aidb_running" == "true" ]]; then
        log_info "Checking AIDB service PostgreSQL connectivity..."

        # Check logs for successful connection (no password errors)
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if podman logs --tail 50 local-ai-aidb 2>&1 | grep -qi "password authentication failed"; then
                test_result 1 "AIDB has PostgreSQL authentication errors in logs"
            else
                test_result 0 "AIDB has no PostgreSQL authentication errors"
            fi
        elif $COMPOSE_CMD logs aidb --tail=50 2>&1 | grep -qi "password authentication failed"; then
            test_result 1 "AIDB has PostgreSQL authentication errors in logs"
        else
            test_result 0 "AIDB has no PostgreSQL authentication errors"
        fi

        # Check logs for Redis connection errors
        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if podman logs --tail 50 local-ai-aidb 2>&1 | grep -qi "redis.*authentication.*failed\|NOAUTH"; then
                test_result 1 "AIDB has Redis authentication errors in logs"
            else
                test_result 0 "AIDB has no Redis authentication errors"
            fi
        elif $COMPOSE_CMD logs aidb --tail=50 2>&1 | grep -qi "redis.*authentication.*failed\|NOAUTH"; then
            test_result 1 "AIDB has Redis authentication errors in logs"
        else
            test_result 0 "AIDB has no Redis authentication errors"
        fi
    else
        log_warning "AIDB service not running, skipping connectivity test"
    fi

    # Check hybrid-coordinator logs
    local hybrid_running=false
    if [[ "$CONTAINER_CMD" == "podman" ]]; then
        if podman ps --format '{{.Names}}' | grep -q '^local-ai-hybrid-coordinator$'; then
            hybrid_running=true
        fi
    else
        if $COMPOSE_CMD ps hybrid-coordinator | grep -q "Up"; then
            hybrid_running=true
        fi
    fi

    if [[ "$hybrid_running" == "true" ]]; then
        log_info "Checking hybrid-coordinator service logs..."

        if [[ "$CONTAINER_CMD" == "podman" ]]; then
            if podman logs --tail 50 local-ai-hybrid-coordinator 2>&1 | grep -qi "connection.*failed\|authentication.*failed"; then
                test_result 1 "hybrid-coordinator has connection errors in logs"
            else
                test_result 0 "hybrid-coordinator has no connection errors"
            fi
        elif $COMPOSE_CMD logs hybrid-coordinator --tail=50 2>&1 | grep -qi "connection.*failed\|authentication.*failed"; then
            test_result 1 "hybrid-coordinator has connection errors in logs"
        else
            test_result 0 "hybrid-coordinator has no connection errors"
        fi
    else
        log_warning "hybrid-coordinator service not running"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "  PASSWORD MIGRATION TEST SUMMARY"
    echo "=========================================="
    echo -e "Total tests:  ${TESTS_TOTAL}"
    echo -e "${GREEN}Passed:       ${TESTS_PASSED}${NC}"
    echo -e "${RED}Failed:       ${TESTS_FAILED}${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
        echo -e "${GREEN}✓ Password migration successful!${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ SOME TESTS FAILED${NC}"
        echo -e "${RED}✗ Please review errors above${NC}"
        echo ""
        return 1
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "  Day 5 Password Migration Test Suite"
    echo "=========================================="
    echo ""

    # Check prerequisites
    detect_compose
    if [[ -z "$COMPOSE_CMD" ]]; then
        log_error "podman-compose, docker-compose, or docker compose is required."
        exit 1
    fi

    if [ ! -d "$COMPOSE_DIR" ]; then
        log_error "Compose directory not found: $COMPOSE_DIR"
        exit 1
    fi

    # Run tests
    check_secrets_exist
    echo ""

    test_postgres_connection
    echo ""

    test_redis_connection
    echo ""

    test_grafana_login
    echo ""

    test_service_connectivity
    echo ""

    # Print summary and exit
    print_summary
    exit $?
}

# Run main function
main "$@"
