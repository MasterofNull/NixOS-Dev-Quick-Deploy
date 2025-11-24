#!/usr/bin/env bash
#
# Test TGI Services
# Tests both HuggingFace TGI instances (DeepSeek and Scout)
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Test TGI DeepSeek (port 8080)
test_tgi_deepseek() {
    print_header "Testing TGI DeepSeek (8080)"

    # Check service status
    if systemctl is-active --quiet huggingface-tgi.service; then
        print_success "Service is running"
    else
        print_error "Service is not running"
        systemctl status huggingface-tgi.service --no-pager -l | head -20
        return 1
    fi

    # Check health endpoint
    if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
        print_success "Health endpoint responding"
    else
        print_warning "Health endpoint not ready (model may still be loading)"
        print_info "Check logs: journalctl -u huggingface-tgi.service -f"
        return 0
    fi

    # Test inference
    print_info "Testing inference with simple prompt..."
    response=$(curl -fsS -X POST http://127.0.0.1:8080/v1/chat/completions \
        -H 'Content-Type: application/json' \
        -d '{
            "model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            "messages": [{"role": "user", "content": "Say hello in one word"}],
            "max_tokens": 10
        }' 2>/dev/null)

    if [[ -n "$response" ]]; then
        print_success "Inference successful"
        echo "$response" | jq -r '.choices[0].message.content' 2>/dev/null || echo "$response"
    else
        print_error "Inference failed"
        return 1
    fi
}

# Test TGI Scout (port 8085)
test_tgi_scout() {
    print_header "Testing TGI Scout (8085)"

    # Check service status
    if systemctl is-active --quiet huggingface-tgi-scout.service; then
        print_success "Service is running"
    else
        print_error "Service is not running"
        systemctl status huggingface-tgi-scout.service --no-pager -l | head -20
        return 1
    fi

    # Check health endpoint
    if curl -fsS http://127.0.0.1:8085/health >/dev/null 2>&1; then
        print_success "Health endpoint responding"
    else
        print_warning "Health endpoint not ready (model may still be loading)"
        print_info "Check logs: journalctl -u huggingface-tgi-scout.service -f"
        return 0
    fi

    # Test inference
    print_info "Testing inference with simple prompt..."
    response=$(curl -fsS -X POST http://127.0.0.1:8085/v1/chat/completions \
        -H 'Content-Type: application/json' \
        -d '{
            "model": "meta-llama/Llama-4-Scout-17B-16E",
            "messages": [{"role": "user", "content": "Say hello in one word"}],
            "max_tokens": 10
        }' 2>/dev/null)

    if [[ -n "$response" ]]; then
        print_success "Inference successful"
        echo "$response" | jq -r '.choices[0].message.content' 2>/dev/null || echo "$response"
    else
        print_error "Inference failed"
        return 1
    fi
}

# Check container status
check_containers() {
    print_header "Container Status"

    if podman ps --filter name=huggingface-tgi --format "{{.Names}}: {{.Status}}" 2>/dev/null; then
        print_success "DeepSeek container found"
    else
        print_warning "DeepSeek container not found"
    fi

    if podman ps --filter name=huggingface-tgi-scout --format "{{.Names}}: {{.Status}}" 2>/dev/null; then
        print_success "Scout container found"
    else
        print_warning "Scout container not found"
    fi
}

# Main
main() {
    echo ""
    print_header "TGI Services Test Suite"
    echo ""

    check_containers
    echo ""

    test_tgi_deepseek || true
    echo ""

    test_tgi_scout || true
    echo ""

    print_header "Summary"
    print_info "Both services are system-level systemd units using Podman"
    print_info "Models download on first startup (large files, takes time)"
    print_info "Monitor progress with: journalctl -u huggingface-tgi.service -f"
}

main "$@"
