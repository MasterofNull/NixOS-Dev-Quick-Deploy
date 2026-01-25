# Systematic Improvements Plan
## Analysis of Current Issues & Professional Solutions

**Date**: 2026-01-10
**Purpose**: Document systemic problems and implement professional development practices

---

## Executive Summary

**Current State**: Chaotic development with repeated container failures, wasted tokens, and fragile deployments.

**Root Causes**:
1. No validation before deployment
2. Configuration scattered (hardcoded, env files, compose vars)
3. No systematic container lifecycle management
4. Missing dependency checks
5. Iteration limits too restrictive
6. No rollback mechanisms

**Solution**: Implement professional DevOps practices with validation, centralized config, automated testing, and gradual optimization.

---

## Problem 1: Container Networking Chaos

### Symptoms
- Services hardcode `localhost:PORT` but run in containers
- Network state corruption (netavark errors)
- Containers can't find each other
- Manual fixes with `podman rm -f`, `podman start` ad-hoc

### Root Cause
**Lack of systematic approach to container networking:**
- Services deployed without checking if dependencies are reachable
- Hostname resolution not tested
- No network validation before startup

### Solution

**A. Centralized Network Configuration**

Create `/home/hyperd/.config/nixos-ai-stack/.env`:
```bash
# Service Discovery
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379
QDRANT_HOST=qdrant
QDRANT_PORT=6333
LLAMA_CPP_HOST=llama-cpp
LLAMA_CPP_PORT=8080
AIDB_HOST=aidb
AIDB_PORT=8091
HYBRID_COORDINATOR_HOST=hybrid-coordinator
HYBRID_COORDINATOR_PORT=8092

# Network validation
STARTUP_DEPENDENCY_CHECK=true
STARTUP_TIMEOUT_SECONDS=30
```

**B. Pre-Flight Dependency Checks**

Add to EVERY service's `server.py`:
```python
import os
import sys
import socket
import time

REQUIRED_DEPENDENCIES = {
    "postgres": ("postgres", 5432),
    "redis": ("redis", 6379),
    # ... service-specific deps
}

def validate_dependencies():
    """Check all required services are reachable before starting"""
    if not os.getenv("STARTUP_DEPENDENCY_CHECK", "true") == "true":
        return

    timeout = int(os.getenv("STARTUP_TIMEOUT_SECONDS", "30"))
    start_time = time.time()

    for name, (host, port) in REQUIRED_DEPENDENCIES.items():
        logger.info(f"Checking dependency: {name} at {host}:{port}")

        while time.time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    logger.info(f"✓ {name} is reachable")
                    break
            except Exception as e:
                pass

            time.sleep(2)
        else:
            logger.critical(f"✗ DEPENDENCY MISSING: {name} at {host}:{port}")
            logger.critical(f"Cannot start without {name}. Exiting.")
            sys.exit(1)

# Call during startup
if __name__ == "__main__":
    validate_dependencies()
    # ... rest of startup
```

**C. Container Lifecycle Script**

Create `scripts/container-lifecycle.sh`:
```bash
#!/usr/bin/env bash
# Safe container management with validation

set -euo pipefail

validate_syntax() {
    local service=$1
    echo "→ Validating Python syntax..."
    python3 -m py_compile "ai-stack/mcp-servers/${service}/server.py"
    echo "✓ Syntax valid"
}

build_with_validation() {
    local service=$1
    echo "→ Building ${service} container..."

    # Build image
    podman build \
        -f "ai-stack/mcp-servers/${service}/Dockerfile" \
        -t "${service}" \
        "ai-stack/mcp-servers/" || {
        echo "✗ Build failed"
        return 1
    }

    echo "✓ Build successful"
}

test_container() {
    local service=$1
    echo "→ Testing ${service} in isolation..."

    # Start in test network
    podman run -d \
        --name "test-${service}" \
        --network "test-network" \
        "${service}" || {
        echo "✗ Container failed to start"
        return 1
    }

    # Wait for health check
    sleep 5

    # Test health endpoint
    podman exec "test-${service}" \
        python -c "import requests; r=requests.get('http://localhost:8099/health'); assert r.status_code==200" || {
        echo "✗ Health check failed"
        podman logs "test-${service}"
        podman rm -f "test-${service}"
        return 1
    }

    podman rm -f "test-${service}"
    echo "✓ Tests passed"
}

safe_deploy() {
    local service=$1
    echo "→ Deploying ${service}..."

    # Stop old container (save ID for rollback)
    local old_id=$(podman ps -a --filter "name=local-ai-${service}" --format "{{.ID}}")

    if [[ -n "$old_id" ]]; then
        podman rename "local-ai-${service}" "local-ai-${service}-backup"
        podman stop "local-ai-${service}-backup"
    fi

    # Start new container
    podman run -d \
        --name "local-ai-${service}" \
        --hostname "${service}" \
        --network "local-ai" \
        "${service}" || {
        echo "✗ Deploy failed, rolling back..."
        if [[ -n "$old_id" ]]; then
            podman rename "local-ai-${service}-backup" "local-ai-${service}"
            podman start "local-ai-${service}"
        fi
        return 1
    }

    # Wait for health
    sleep 5
    if ! podman exec "local-ai-${service}" \
        python -c "import requests; requests.get('http://localhost:8099/health')"; then
        echo "✗ New container unhealthy, rolling back..."
        podman rm -f "local-ai-${service}"
        if [[ -n "$old_id" ]]; then
            podman rename "local-ai-${service}-backup" "local-ai-${service}"
            podman start "local-ai-${service}"
        fi
        return 1
    fi

    # Success - remove backup
    if [[ -n "$old_id" ]]; then
        podman rm -f "local-ai-${service}-backup"
    fi

    echo "✓ Deploy successful"
}

# Main workflow
main() {
    local service=$1

    echo "=== Safe Deploy: ${service} ==="
    validate_syntax "${service}"
    build_with_validation "${service}"
    test_container "${service}"
    safe_deploy "${service}"
    echo "✓ All steps complete"
}

main "$@"
```

---

## Problem 2: Ralph Iteration Limits Too Restrictive

### Symptoms
- Tasks marked "complete" after 3 iterations with no actual work done
- Network failures count against iteration limit
- No way to adjust limits without editing JSON files

### Root Cause
- Hardcoded `max_iterations: 3` in task definitions
- No adaptive limits based on task complexity
- No UI controls for operators

### Solution

**A. Increase Default Iterations**

In `.env`:
```bash
RALPH_MAX_ITERATIONS_SIMPLE=10
RALPH_MAX_ITERATIONS_MEDIUM=30
RALPH_MAX_ITERATIONS_COMPLEX=50
RALPH_ADAPTIVE_ITERATIONS=true
```

**B. Adaptive Iteration Logic**

Modify `ralph-wiggum/loop_engine.py`:
```python
def calculate_iteration_limit(self, task_prompt: str, base_limit: int) -> int:
    """Dynamically adjust iteration limit based on task complexity"""
    if not os.getenv("RALPH_ADAPTIVE_ITERATIONS", "true") == "true":
        return base_limit

    # Complexity indicators
    complexity_score = 0

    if "implement" in task_prompt.lower() or "create" in task_prompt.lower():
        complexity_score += 2

    if len(task_prompt) > 200:  # Detailed instructions
        complexity_score += 1

    if "test" in task_prompt.lower():
        complexity_score += 1

    # Adjust limit
    multiplier = 1 + (complexity_score * 0.5)
    adjusted_limit = int(base_limit * multiplier)

    logger.info(f"Adjusted iteration limit: {base_limit} → {adjusted_limit} (complexity: {complexity_score})")
    return adjusted_limit
```

**C. Dashboard Controls**

Add to dashboard `control-center.html`:
```html
<section id="ralph-controls">
    <h2>Ralph Wiggum Loop Controls</h2>

    <div class="control-group">
        <label>Simple Tasks Max Iterations:</label>
        <input type="range" min="5" max="50" value="10" id="ralph-simple-iterations">
        <span id="ralph-simple-value">10</span>
    </div>

    <div class="control-group">
        <label>Complex Tasks Max Iterations:</label>
        <input type="range" min="10" max="100" value="50" id="ralph-complex-iterations">
        <span id="ralph-complex-value">50</span>
    </div>

    <div class="control-group">
        <label>
            <input type="checkbox" id="ralph-adaptive" checked>
            Enable Adaptive Iteration Limits
        </label>
    </div>

    <button onclick="updateRalphSettings()">Apply Settings</button>
</section>
```

---

## Problem 3: No Validation Before Deployment

### Symptoms
- Syntax errors discovered after container starts
- Missing dependencies crash services
- Wasted tokens rebuilding same errors

### Solution

**A. Pre-Commit Validation**

Create `.git/hooks/pre-commit`:
```bash
#!/usr/bin/env bash
# Validate all Python files before commit

echo "Running pre-commit validation..."

# Find all changed Python files
changed_files=$(git diff --cached --name-only --diff-filter=ACM | grep '.py$')

if [[ -z "$changed_files" ]]; then
    exit 0
fi

# Validate syntax
for file in $changed_files; do
    echo "Checking $file..."
    python3 -m py_compile "$file" || {
        echo "✗ Syntax error in $file"
        exit 1
    }
done

# Run import tests
for file in $changed_files; do
    python3 -c "import sys; sys.path.insert(0, '.'); __import__('$(echo $file | sed 's|/|.|g' | sed 's|.py||')') " 2>/dev/null || {
        echo "⚠ Warning: $file has import issues"
    }
done

echo "✓ All checks passed"
exit 0
```

**B. API Contract Testing**

Create `ai-stack/tests/test_api_contracts.py`:
```python
import pytest
import requests

def test_aider_wrapper_accepts_ralph_payload():
    """Ensure aider-wrapper API matches Ralph's expectations"""
    response = requests.post("http://aider-wrapper:8099/api/execute", json={
        "prompt": "test task",
        "context": {},
        "iteration": 1,
        "mode": "autonomous"
    }, timeout=5)

    assert response.status_code == 200
    result = response.json()

    # Ralph expects these fields
    assert "exit_code" in result
    assert "output" in result
    assert "completed" in result
    assert isinstance(result["completed"], bool)

def test_ralph_health_endpoint():
    """Verify Ralph health endpoint responds"""
    response = requests.get("http://ralph-wiggum:8098/health", timeout=5)
    assert response.status_code == 200
    assert "status" in response.json()

def test_llama_cpp_availability():
    """Check if llama-cpp is reachable"""
    try:
        response = requests.get("http://llama-cpp:8080/health", timeout=5)
        assert response.status_code == 200
    except requests.exceptions.ConnectionError:
        pytest.skip("llama-cpp not running (optional)")

# Run with: pytest ai-stack/tests/test_api_contracts.py -v
```

---

## Problem 4: Configuration Scattered

### Current State
- Hardcoded values: `localhost:8080`, `max_iterations: 3`
- Docker compose env vars: `${LLAMA_CPP_PORT:-8080}`
- Missing .env files causing failures

### Solution

**Single Source of Truth**: `/home/hyperd/.config/nixos-ai-stack/.env`

```bash
# ============================================================================
# NixOS AI Stack Configuration
# Single source of truth for all services
# ============================================================================

# Container Network Discovery
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=aidb
POSTGRES_USER=mcp
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}

REDIS_HOST=redis
REDIS_PORT=6379

QDRANT_HOST=qdrant
QDRANT_PORT=6333

LLAMA_CPP_HOST=llama-cpp
LLAMA_CPP_PORT=8080
LLAMA_CPP_MODEL_FILE=qwen2.5-coder-7b-instruct-q4_k_m.gguf

# Ralph Wiggum Settings
RALPH_MAX_ITERATIONS_DEFAULT=20
RALPH_MAX_ITERATIONS_SIMPLE=10
RALPH_MAX_ITERATIONS_COMPLEX=50
RALPH_ADAPTIVE_ITERATIONS=true
RALPH_LOOP_ENABLED=true
RALPH_EXIT_CODE_BLOCK=2

# Continuous Learning
CONTINUOUS_LEARNING_ENABLED=true
LEARNING_PROCESSING_INTERVAL=3600
PATTERN_EXTRACTION_ENABLED=true

# Startup Validation
STARTUP_DEPENDENCY_CHECK=true
STARTUP_TIMEOUT_SECONDS=30

# Telemetry
TELEMETRY_PATH=/data/telemetry
OTEL_TRACING_ENABLED=true

# Feature Flags
ADAPTIVE_ITERATION_LIMITS=true
SELF_HEALING_ENABLED=false
```

**Every service loads this file:**
```python
from dotenv import load_dotenv
load_dotenv("/home/hyperd/.config/nixos-ai-stack/.env")

LLAMA_HOST = os.getenv("LLAMA_CPP_HOST", "llama-cpp")
LLAMA_PORT = os.getenv("LLAMA_CPP_PORT", "8080")
```

---

## Problem 5: Continuous Learning Not Optimizing System

### Current State
- Learning pipeline runs but doesn't trigger improvements
- No feedback loop to Ralph
- Insights stored but not acted upon

### Solution

**A. Learning → Action Pipeline**

Modify `continuous_learning.py`:
```python
async def propose_optimizations(self):
    """Analyze patterns and submit Ralph tasks for improvements"""
    patterns = await self.extract_patterns()

    for pattern in patterns:
        if pattern["type"] == "high_iteration_tasks":
            # Suggest increasing iteration limits
            task = {
                "prompt": f"Increase max_iterations for tasks matching '{pattern['task_pattern']}' from {pattern['current_avg']} to {pattern['suggested']}",
                "backend": "aider",
                "max_iterations": 10,
                "require_approval": True  # Human review for system changes
            }
            await self.submit_to_ralph(task)

        elif pattern["type"] == "common_failure":
            # Suggest adding pre-flight check
            task = {
                "prompt": f"Add pre-flight dependency check for {pattern['service']} to detect {pattern['error_pattern']}",
                "backend": "aider",
                "max_iterations": 15,
                "require_approval": True
            }
            await self.submit_to_ralph(task)
```

---

## Implementation Priority

### Phase 1: Stop the Bleeding (Immediate)
1. ✅ Fix aider-wrapper to use `llama-cpp` hostname (done)
2. ⏳ Create `.env` file with defaults
3. ⏳ Add pre-flight checks to aider-wrapper, ralph-wiggum
4. ⏳ Increase default iteration limits to 20

### Phase 2: Systematic Deployment (This Week)
1. Create `container-lifecycle.sh` script
2. Add API contract tests
3. Implement pre-commit validation
4. Document deployment procedures

### Phase 3: Dashboard Controls (Next Week)
1. Add Ralph iteration controls to dashboard
2. Add container health monitoring
3. Add "Safe Redeploy" buttons
4. Configuration editor for .env

### Phase 4: Continuous Learning Integration (Future)
1. Connect learning pipeline to Ralph task submission
2. Implement adaptive iteration limits
3. Automated optimization proposals

---

## Success Metrics

**Before (Current)**:
- 90% of deployments fail initially
- Average 5 rebuild cycles per container
- ~50k tokens wasted on repeated errors
- No rollback mechanism

**After (Target)**:
- 95% of deployments succeed first try
- Average 1 rebuild cycle (validation catches issues)
- <5k tokens wasted (pre-flight checks catch problems)
- Automatic rollback on failure

---

## Next Steps

1. Create the `.env` file
2. Implement pre-flight dependency checks
3. Test end-to-end Ralph workflow
4. Document what works
5. Iterate and improve

**Philosophy**: Start permissive, then optimize based on data from continuous learning.
