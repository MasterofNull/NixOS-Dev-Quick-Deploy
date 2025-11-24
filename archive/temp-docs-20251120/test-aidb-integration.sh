#!/usr/bin/env bash
#
# AIDB and Local AI Stack Integration Test
# Tests the complete AI development stack integration
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

# Test Gitea (AIDB) availability
test_gitea() {
    print_header "Testing Gitea (AIDB)"

    if ! systemctl is-active --quiet gitea.service; then
        print_error "Gitea service is not running"
        return 1
    fi
    print_success "Gitea service is running"

    if curl -fsS http://127.0.0.1:3000 >/dev/null 2>&1; then
        print_success "Gitea web interface responding on port 3000"
    else
        print_error "Gitea web interface not responding"
        return 1
    fi

    # Test Gitea API
    if curl -fsS http://127.0.0.1:3000/api/v1/version >/dev/null 2>&1; then
        local version=$(curl -fsS http://127.0.0.1:3000/api/v1/version | jq -r '.version' 2>/dev/null || echo "unknown")
        print_success "Gitea API responding (version: $version)"
    else
        print_warning "Gitea API not responding"
    fi
}

# Test Ollama availability and models
test_ollama() {
    print_header "Testing Ollama"

    if ! systemctl is-active --quiet ollama.service; then
        print_error "Ollama service is not running"
        return 1
    fi
    print_success "Ollama service is running"

    if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        print_error "Ollama API not responding"
        return 1
    fi
    print_success "Ollama API responding on port 11434"

    # List installed models
    local models=$(curl -fsS http://127.0.0.1:11434/api/tags 2>/dev/null | jq -r '.models[].name' 2>/dev/null || echo "")
    if [[ -n "$models" ]]; then
        print_success "Ollama models installed:"
        echo "$models" | while read -r model; do
            echo "  - $model"
        done
    else
        print_warning "No Ollama models found"
    fi
}

# Test TGI DeepSeek
test_tgi_deepseek() {
    print_header "Testing TGI DeepSeek (8080)"

    if ! systemctl is-active --quiet huggingface-tgi.service; then
        print_error "TGI DeepSeek service is not running"
        return 1
    fi
    print_success "TGI DeepSeek service is running"

    if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
        print_success "TGI DeepSeek health endpoint responding"

        # Test quick inference
        print_info "Testing inference..."
        response=$(curl -fsS -X POST http://127.0.0.1:8080/v1/chat/completions \
            -H 'Content-Type: application/json' \
            -d '{"model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}' 2>/dev/null || echo "")

        if [[ -n "$response" ]]; then
            print_success "Inference successful"
        else
            print_warning "Inference failed"
        fi
    else
        print_warning "TGI DeepSeek health endpoint not ready (model may be loading)"
        print_info "Check logs: journalctl -u huggingface-tgi.service -n 20"
    fi
}

# Test TGI Scout
test_tgi_scout() {
    print_header "Testing TGI Scout (8085)"

    if ! systemctl is-active --quiet huggingface-tgi-scout.service; then
        print_error "TGI Scout service is not running"
        return 1
    fi
    print_success "TGI Scout service is running"

    if curl -fsS http://127.0.0.1:8085/health >/dev/null 2>&1; then
        print_success "TGI Scout health endpoint responding"

        # Test quick inference
        print_info "Testing inference..."
        response=$(curl -fsS -X POST http://127.0.0.1:8085/v1/chat/completions \
            -H 'Content-Type: application/json' \
            -d '{"model": "meta-llama/Llama-4-Scout-17B-16E", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}' 2>/dev/null || echo "")

        if [[ -n "$response" ]]; then
            print_success "Inference successful"
        else
            print_warning "Inference failed"
        fi
    else
        print_warning "TGI Scout health endpoint not ready (model may be loading)"
        print_info "Check logs: journalctl -u huggingface-tgi-scout.service -n 20"
    fi
}

# Test Open WebUI
test_open_webui() {
    print_header "Testing Open WebUI"

    if ! systemctl is-active --quiet open-webui.service; then
        print_warning "Open WebUI service is not running"
        return 1
    fi
    print_success "Open WebUI service is running"

    if curl -fsS http://127.0.0.1:8081 >/dev/null 2>&1; then
        print_success "Open WebUI responding on port 8081"
    else
        print_warning "Open WebUI not responding"
        return 1
    fi
}

# Integration test: Use TGI via Ollama-compatible API
test_integration_tgi_ollama_api() {
    print_header "Integration Test: TGI via OpenAI API"

    print_info "Testing if TGI services can be queried via OpenAI-compatible API..."

    # Test DeepSeek via OpenAI API format
    local deepseek_response=$(curl -fsS -X POST http://127.0.0.1:8080/v1/chat/completions \
        -H 'Content-Type: application/json' \
        -d '{
            "model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            "messages": [{"role": "user", "content": "What is 2+2?"}],
            "max_tokens": 20
        }' 2>/dev/null || echo "")

    if [[ -n "$deepseek_response" ]]; then
        local answer=$(echo "$deepseek_response" | jq -r '.choices[0].message.content' 2>/dev/null || echo "")
        if [[ -n "$answer" ]]; then
            print_success "DeepSeek responded: $answer"
        else
            print_warning "DeepSeek API responded but no content in answer"
        fi
    else
        print_warning "DeepSeek API integration test failed (may still be loading)"
    fi
}

# Integration test: Check Podman containers
test_podman_containers() {
    print_header "Podman Container Status"

    if ! command -v podman >/dev/null 2>&1; then
        print_error "Podman not installed"
        return 1
    fi

    print_info "TGI containers (managed by systemd):"

    # Check for TGI DeepSeek container
    if podman ps --filter name=huggingface-tgi --format "{{.Names}}: {{.Status}}" 2>/dev/null | grep -q .; then
        podman ps --filter name=huggingface-tgi --format "  - {{.Names}}: {{.Status}}"
        print_success "TGI DeepSeek container running"
    else
        print_warning "TGI DeepSeek container not found"
    fi

    # Check for TGI Scout container
    if podman ps --filter name=huggingface-tgi-scout --format "{{.Names}}: {{.Status}}" 2>/dev/null | grep -q .; then
        podman ps --filter name=huggingface-tgi-scout --format "  - {{.Names}}: {{.Status}}"
        print_success "TGI Scout container running"
    else
        print_warning "TGI Scout container not found"
    fi

    # Show all AI-related containers
    echo ""
    print_info "All AI stack containers:"
    if podman ps --format "  - {{.Names}}: {{.Image}} ({{.Status}})" 2>/dev/null | grep -E 'huggingface|ollama|webui' || true; then
        :
    else
        print_warning "No AI containers found"
    fi
}

# Main test suite
main() {
    echo ""
    print_header "AIDB & Local AI Stack Integration Test"
    echo ""

    test_gitea || true
    echo ""

    test_ollama || true
    echo ""

    test_tgi_deepseek || true
    echo ""

    test_tgi_scout || true
    echo ""

    test_open_webui || true
    echo ""

    test_integration_tgi_ollama_api || true
    echo ""

    test_podman_containers || true
    echo ""

    print_header "Summary"
    print_info "AIDB Stack:"
    echo "  - Gitea (repository): http://127.0.0.1:3000"
    echo ""
    print_info "AI Inference APIs:"
    echo "  - Ollama: http://127.0.0.1:11434"
    echo "  - TGI DeepSeek: http://127.0.0.1:8080"
    echo "  - TGI Scout: http://127.0.0.1:8085"
    echo "  - Open WebUI: http://127.0.0.1:8081"
    echo ""
    print_info "Note: TGI services may take several minutes to download models on first startup"
    print_info "Monitor progress: journalctl -u huggingface-tgi.service -f"
}

main "$@"
