# Production Hardening Roadmap - Complete Implementation Plan
**Date:** 2026-01-09
**Status:** 📋 COMPREHENSIVE PLAN
**Execution Method:** Ralph Wiggum Loop + Testing

---

## Executive Summary

This roadmap addresses all P0/P1 issues from the senior dev code review and restructures the orchestration layer to be **cooperative and nested**, not isolated. Each component helps the others instead of working independently.

**New Architecture:** Nested orchestration where Ralph Wiggum can invoke Hybrid Coordinator, which uses AIDB, and continuous learning flows through all layers.

---

## Table of Contents

1. [Phase 1: Critical Security Fixes (P0)](#phase-1-critical-security-fixes-p0)
2. [Phase 2: Reliability & Error Recovery (P0)](#phase-2-reliability--error-recovery-p0)
3. [Phase 3: Resource Management (P0)](#phase-3-resource-management-p0)
4. [Phase 4: Orchestration Restructuring (P1)](#phase-4-orchestration-restructuring-p1)
5. [Phase 5: Observability & Monitoring (P1)](#phase-5-observability--monitoring-p1)
6. [Phase 6: Data Lifecycle & Operations (P1)](#phase-6-data-lifecycle--operations-p1)
7. [Phase 7: Testing & Validation (All)](#phase-7-testing--validation-all)
8. [Ralph Wiggum Task Definitions](#ralph-wiggum-task-definitions)
9. [Verification Checklist](#verification-checklist)

---

## Phase 1: Critical Security Fixes (P0)

**Timeline:** Week 1
**Blocker:** YES - Cannot deploy without these
**Ralph Task IDs:** P1-SEC-001 through P1-SEC-003

### Task P1-SEC-001: Fix Dashboard Proxy Subprocess Vulnerability

**Problem:** Using `subprocess` with unsanitized input → shell injection

**Solution Options:**

#### Option 1: Expose Port Properly (Recommended)
```yaml
# docker-compose.yml
aidb:
  ports:
    - "127.0.0.1:8091:8091"  # Expose to localhost only

# Remove subprocess proxy entirely
# Dashboard accesses http://localhost:8091 directly
```

#### Option 2: HTTP Client Proxy (If port exposure not allowed)
```python
# scripts/serve-dashboard.sh
import httpx
from urllib.parse import quote

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Create HTTP client pool
        self.http_client = httpx.Client(
            base_url="http://local-ai-aidb:8091",
            timeout=2.0,
            limits=httpx.Limits(max_connections=10)
        )
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path

        # Proxy AIDB health check requests
        if clean_path.startswith('/aidb/'):
            try:
                # Input validation
                aidb_path = clean_path.replace('/aidb/', '')

                # Whitelist allowed paths
                ALLOWED_PATHS = {
                    'health/live',
                    'health/ready',
                    'health/startup',
                    'health/detailed',
                    'metrics'
                }

                if aidb_path not in ALLOWED_PATHS:
                    self.send_error(403, "Path not allowed")
                    return

                # Safe HTTP request (no subprocess)
                response = self.http_client.get(f"/{aidb_path}")

                self.send_response(response.status_code)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(response.content)
                return

            except httpx.TimeoutException:
                self.send_error(504, "Gateway timeout")
                return
            except Exception as e:
                logger.error("proxy_error", error=str(e))
                self.send_error(500, "Internal server error")
                return
```

**Ralph Wiggum Task:**
```yaml
task_id: P1-SEC-001
name: "Fix dashboard proxy subprocess vulnerability"
backend: aider
files:
  - scripts/serve-dashboard.sh
  - ai-stack/compose/docker-compose.yml
steps:
  1. Choose solution (Option 1 or 2)
  2. Implement changes
  3. Test with curl
  4. Test with malicious input
  5. Verify no subprocess calls
completion_criteria:
  - No subprocess.run in serve-dashboard.sh
  - Health endpoints accessible
  - Input validation tests pass
  - Shell injection tests fail safely
```

**Testing:**
```bash
# Test 1: Normal access
curl http://localhost:8888/aidb/health/live
# Expected: {"status": "healthy"}

# Test 2: Path traversal attempt
curl "http://localhost:8888/aidb/../../etc/passwd"
# Expected: 403 Forbidden

# Test 3: Command injection attempt
curl "http://localhost:8888/aidb/health;rm%20-rf%20/"
# Expected: 403 Forbidden or 404 Not Found

# Test 4: Process count
ps aux | grep -c "podman exec"
# Expected: 0 (no subprocess spawning)
```

---

### Task P1-SEC-002: Add Rate Limiting to Proxy

**Problem:** No rate limiting → DOS via process exhaustion

**Solution:**
```python
# scripts/serve-dashboard.sh
from collections import defaultdict
from datetime import datetime, timedelta
import threading

class RateLimiter:
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        with self.lock:
            now = datetime.now()
            cutoff = now - self.window

            # Clean old requests
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if req_time > cutoff
            ]

            # Check limit
            if len(self.requests[client_ip]) >= self.max_requests:
                return False

            # Record request
            self.requests[client_ip].append(now)
            return True

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    rate_limiter = RateLimiter(max_requests=60, window_seconds=60)

    def do_GET(self):
        # Check rate limit
        client_ip = self.client_address[0]
        if not self.rate_limiter.is_allowed(client_ip):
            self.send_error(429, "Too many requests")
            return

        # ... rest of handler
```

**Ralph Wiggum Task:**
```yaml
task_id: P1-SEC-002
name: "Add rate limiting to dashboard proxy"
backend: aider
files:
  - scripts/serve-dashboard.sh
steps:
  1. Implement RateLimiter class
  2. Add to DashboardHandler
  3. Test with burst requests
  4. Verify 429 responses
completion_criteria:
  - Rate limiter implemented
  - 429 status on excess requests
  - Burst test passes
```

**Testing:**
```bash
# Test: Burst requests
for i in {1..100}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8888/aidb/health/live &
done | sort | uniq -c

# Expected output:
#  60 200  (first 60 succeed)
#  40 429  (next 40 rate limited)
```

---

### Task P1-SEC-003: Move Secrets to Environment Variables

**Problem:** Passwords in plain text config files

**Solution:**
```yaml
# docker-compose.yml
services:
  postgres:
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?error}  # Required from env

  aidb:
    environment:
      AIDB_POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?error}
```

```bash
# .env.example (checked into git)
POSTGRES_PASSWORD=change_me_in_production
GRAFANA_ADMIN_PASSWORD=change_me_in_production

# .env (NOT checked into git)
POSTGRES_PASSWORD=actual_secure_password_here
GRAFANA_ADMIN_PASSWORD=actual_secure_password_here
```

```bash
# .gitignore
.env
*.secret
```

**Ralph Wiggum Task:**
```yaml
task_id: P1-SEC-003
name: "Move secrets to environment variables"
backend: aider
files:
  - ai-stack/compose/.env.example
  - ai-stack/compose/docker-compose.yml
  - ai-stack/mcp-servers/config/config.yaml
  - .gitignore
steps:
  1. Update docker-compose.yml to use env vars
  2. Update config.yaml to use env vars
  3. Create .env.example
  4. Add .env to .gitignore
  5. Update documentation
completion_criteria:
  - No plain text passwords in git
  - Services start with env vars
  - .env.example documented
```

---

## Phase 2: Reliability & Error Recovery (P0)

**Timeline:** Week 1-2
**Blocker:** YES - Will crash in production
**Ralph Task IDs:** P2-REL-001 through P2-REL-004

### Task P2-REL-001: Add Checkpointing to Continuous Learning

**Problem:** Lost telemetry after crash during batch processing

**Solution:**
```python
# ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py
import pickle
from pathlib import Path

class Checkpointer:
    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: dict):
        """Save checkpoint atomically"""
        temp_path = self.checkpoint_dir / "checkpoint.tmp"
        final_path = self.checkpoint_dir / "checkpoint.pkl"

        # Write to temp file
        with open(temp_path, "wb") as f:
            pickle.dump(state, f)

        # Atomic rename
        temp_path.rename(final_path)

    def load(self) -> dict:
        """Load last checkpoint"""
        checkpoint_path = self.checkpoint_dir / "checkpoint.pkl"
        if not checkpoint_path.exists():
            return {}

        with open(checkpoint_path, "rb") as f:
            return pickle.load(f)

class ContinuousLearningPipeline:
    def __init__(self, settings, qdrant_client, postgres_client):
        # ... existing init ...
        self.checkpointer = Checkpointer(Path("/data/checkpoints"))

        # Load last checkpoint
        checkpoint = self.checkpointer.load()
        self.last_positions = checkpoint.get("last_positions", {})
        self.processed_count = checkpoint.get("processed_count", 0)

    async def process_telemetry_batch(self) -> List[InteractionPattern]:
        """Process with checkpointing every N events"""
        all_patterns = []
        checkpoint_interval = 100  # Checkpoint every 100 events

        for telemetry_path in self.telemetry_paths:
            if not telemetry_path.exists():
                continue

            events_processed = 0

            async for event in self._read_telemetry_streaming(telemetry_path):
                try:
                    pattern = await self._extract_pattern_from_event(event)
                    if pattern:
                        all_patterns.append(pattern)

                    events_processed += 1
                    self.processed_count += 1

                    # Checkpoint periodically
                    if events_processed % checkpoint_interval == 0:
                        self.checkpointer.save({
                            "last_positions": self.last_positions,
                            "processed_count": self.processed_count,
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info("checkpoint_saved", events=events_processed)

                except Exception as e:
                    logger.error(
                        "event_processing_failed",
                        event_id=event.get("id"),
                        error=str(e)
                    )
                    # Continue to next event instead of crashing

            # Final checkpoint for this file
            self.checkpointer.save({
                "last_positions": self.last_positions,
                "processed_count": self.processed_count
            })

        return all_patterns
```

**Ralph Wiggum Task:**
```yaml
task_id: P2-REL-001
name: "Add checkpointing to continuous learning"
backend: aider
files:
  - ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py
steps:
  1. Implement Checkpointer class
  2. Add checkpoint saving every 100 events
  3. Add checkpoint loading on startup
  4. Handle checkpoint corruption
  5. Test crash recovery
completion_criteria:
  - Checkpoints saved every 100 events
  - Crash recovery test passes
  - No duplicate processing
```

**Testing:**
```bash
# Test 1: Normal checkpointing
# 1. Start learning daemon
# 2. Generate 500 events
# 3. Check checkpoint file exists
ls -lh /data/checkpoints/checkpoint.pkl

# Test 2: Crash recovery
# 1. Start learning daemon
# 2. Process 250 events
# 3. Kill daemon (kill -9)
# 4. Restart daemon
# 5. Verify starts from event 251, not event 1
tail -f /var/log/learning-daemon.log | grep "resuming from checkpoint"
```

---

### Task P2-REL-002: Add Circuit Breaker Pattern

**Problem:** No circuit breaker → infinite retries when dependencies down

**Solution:**
```python
# ai-stack/mcp-servers/hybrid-coordinator/circuit_breaker.py
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""

        if self.state == CircuitState.OPEN:
            # Check if should try recovery
            if datetime.now() - self.last_failure_time > self.recovery_timeout:
                logger.info("circuit_breaker_half_open", func=func.__name__)
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpen(f"Circuit breaker open for {func.__name__}")

        try:
            result = await func(*args, **kwargs)

            # Success - reset circuit
            if self.state == CircuitState.HALF_OPEN:
                logger.info("circuit_breaker_closed", func=func.__name__)
                self.state = CircuitState.CLOSED
                self.failure_count = 0

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            logger.warning(
                "circuit_breaker_failure",
                func=func.__name__,
                failures=self.failure_count,
                threshold=self.failure_threshold
            )

            if self.failure_count >= self.failure_threshold:
                logger.error("circuit_breaker_open", func=func.__name__)
                self.state = CircuitState.OPEN

            raise

class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""
    pass
```

**Usage in Learning Pipeline:**
```python
class ContinuousLearningPipeline:
    def __init__(self, settings, qdrant_client, postgres_client):
        # ... existing init ...
        self.qdrant_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60
        )
        self.postgres_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60
        )

    async def _index_patterns(self, patterns: List[InteractionPattern]):
        """Store patterns in Qdrant with circuit breaker"""
        try:
            await self.qdrant_breaker.call(
                self._do_qdrant_upsert,
                patterns
            )
        except CircuitBreakerOpen:
            logger.error("qdrant_circuit_open", patterns_lost=len(patterns))
            # Store patterns in fallback location
            await self._store_patterns_fallback(patterns)
```

**Ralph Wiggum Task:**
```yaml
task_id: P2-REL-002
name: "Add circuit breaker pattern"
backend: aider
files:
  - ai-stack/mcp-servers/hybrid-coordinator/circuit_breaker.py
  - ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py
steps:
  1. Implement CircuitBreaker class
  2. Add to Qdrant operations
  3. Add to PostgreSQL operations
  4. Add fallback storage
  5. Test with simulated failures
completion_criteria:
  - Circuit breaker implemented
  - Opens after 5 failures
  - Recovers after 60 seconds
  - Fallback storage works
```

**Testing:**
```bash
# Test 1: Circuit opens
# 1. Stop Qdrant
podman stop local-ai-qdrant
# 2. Trigger 5 pattern storage attempts
# 3. Verify circuit opens
tail -f /var/log/learning-daemon.log | grep "circuit_breaker_open"

# Test 2: Circuit recovers
# 1. Start Qdrant
podman start local-ai-qdrant
# 2. Wait 60 seconds
# 3. Verify circuit tries again
tail -f /var/log/learning-daemon.log | grep "circuit_breaker_half_open"
```

---

### Task P2-REL-003: Add Backpressure Monitoring

**Problem:** No backpressure → telemetry grows faster than processing

**Solution:**
```python
# ai-stack/mcp-servers/hybrid-coordinator/backpressure.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

@dataclass
class BackpressureStatus:
    is_overloaded: bool
    lag_seconds: float
    queue_size: int
    recommendation: str

class BackpressureMonitor:
    def __init__(
        self,
        max_lag_seconds: int = 300,
        max_queue_size: int = 10000
    ):
        self.max_lag_seconds = max_lag_seconds
        self.max_queue_size = max_queue_size

    def check_status(
        self,
        last_processed_timestamp: datetime,
        queue_size: int
    ) -> BackpressureStatus:
        """Check if system is overloaded"""

        # Calculate lag
        now = datetime.now()
        lag = (now - last_processed_timestamp).total_seconds()

        # Determine if overloaded
        is_overloaded = (
            lag > self.max_lag_seconds or
            queue_size > self.max_queue_size
        )

        # Generate recommendation
        if not is_overloaded:
            recommendation = "OK"
        elif lag > self.max_lag_seconds:
            recommendation = f"Falling behind by {int(lag)}s. Consider scaling."
        else:
            recommendation = f"Queue size {queue_size} too high. Consider batching."

        return BackpressureStatus(
            is_overloaded=is_overloaded,
            lag_seconds=lag,
            queue_size=queue_size,
            recommendation=recommendation
        )
```

**Ralph Wiggum Task:**
```yaml
task_id: P2-REL-003
name: "Add backpressure monitoring"
backend: aider
files:
  - ai-stack/mcp-servers/hybrid-coordinator/backpressure.py
  - ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py
steps:
  1. Implement BackpressureMonitor
  2. Add to learning loop
  3. Add Prometheus metrics
  4. Add alerting
completion_criteria:
  - Backpressure monitoring active
  - Metrics exported
  - Alert fires when overloaded
```

---

### Task P2-REL-004: Add Telemetry File Locking

**Problem:** Race conditions with log rotation and concurrent access

**Solution:**
```python
# ai-stack/mcp-servers/hybrid-coordinator/telemetry_reader.py
from filelock import FileLock
import fcntl
from pathlib import Path

class TelemetryReader:
    def __init__(self):
        self.locks = {}
        self.last_positions = {}
        self.last_inodes = {}

    async def read_with_lock(self, path: Path):
        """Read telemetry file with proper locking"""

        lock_path = Path(f"{path}.lock")
        lock = FileLock(str(lock_path), timeout=10)

        try:
            with lock:
                # Get file stats
                if not path.exists():
                    logger.warning("telemetry_file_missing", path=str(path))
                    return

                stat = path.stat()
                current_inode = stat.st_ino

                # Detect file rotation
                last_inode = self.last_inodes.get(str(path))
                if last_inode and last_inode != current_inode:
                    logger.info("telemetry_file_rotated", path=str(path))
                    self.last_positions[str(path)] = 0

                # Read from last position
                last_pos = self.last_positions.get(str(path), 0)

                with open(path, "r", encoding="utf-8") as f:
                    f.seek(last_pos)

                    while True:
                        line = f.readline()

                        # EOF
                        if not line:
                            break

                        # Incomplete line (writer still writing)
                        if not line.endswith("\n"):
                            logger.debug("incomplete_line", path=str(path))
                            break

                        # Parse JSON
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError as e:
                            logger.error(
                                "corrupt_telemetry_line",
                                path=str(path),
                                line=line[:100],
                                error=str(e)
                            )
                            # Continue to next line

                    # Update position
                    self.last_positions[str(path)] = f.tell()
                    self.last_inodes[str(path)] = current_inode

        except Timeout:
            logger.error("telemetry_lock_timeout", path=str(path))
```

**Ralph Wiggum Task:**
```yaml
task_id: P2-REL-004
name: "Add telemetry file locking"
backend: aider
files:
  - ai-stack/mcp-servers/hybrid-coordinator/telemetry_reader.py
  - ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py
dependencies:
  - pip install filelock
steps:
  1. Implement TelemetryReader with file locking
  2. Handle log rotation
  3. Handle incomplete lines
  4. Test concurrent access
completion_criteria:
  - File locking works
  - Rotation detected
  - No data loss
```

---

## Phase 3: Resource Management (P0)

**Timeline:** Week 2
**Blocker:** YES - Will OOM user systems
**Ralph Task IDs:** P3-RES-001 through P3-RES-003

### Task P3-RES-001: Implement Resource Tier System

**Problem:** Profile removal causes resource explosion

**Solution:**
```bash
# scripts/detect-resources.sh
#!/usr/bin/env bash
set -euo pipefail

# Detect system resources
TOTAL_RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
TOTAL_CPU=$(nproc)

echo "Detected: ${TOTAL_RAM_GB}GB RAM, ${TOTAL_CPU} CPUs"

# Determine profile
if [ "$TOTAL_RAM_GB" -lt 8 ]; then
    echo "⚠️  WARNING: Only ${TOTAL_RAM_GB}GB RAM detected"
    echo "Recommended: 8GB minimum, 16GB optimal"
    echo "Starting MINIMAL profile (core services only)"
    PROFILE="minimal"
elif [ "$TOTAL_RAM_GB" -lt 16 ]; then
    echo "Starting STANDARD profile (no ML services)"
    PROFILE="standard"
else
    echo "Starting FULL profile (all services)"
    PROFILE="full"
fi

export AI_STACK_PROFILE="$PROFILE"

# Start services based on profile
case "$PROFILE" in
    minimal)
        podman-compose up -d postgres redis qdrant embeddings aidb
        ;;
    standard)
        podman-compose up -d postgres redis qdrant embeddings aidb \
            hybrid-coordinator ralph-wiggum prometheus
        ;;
    full)
        podman-compose up -d
        ;;
esac
```

```yaml
# docker-compose.profiles.yml
# Restore profiles but make them intelligent
services:
  # Always run (no profile)
  postgres:
  redis:
  qdrant:
  embeddings:
  aidb:

  # Standard profile
  hybrid-coordinator:
    profiles: ["standard", "full"]

  ralph-wiggum:
    profiles: ["standard", "full"]

  prometheus:
    profiles: ["standard", "full"]

  # Full profile only
  mindsdb:
    profiles: ["full"]
    deploy:
      resources:
        reservations:
          memory: 1G
        limits:
          memory: 4G

  llama-cpp:
    profiles: ["full"]
    deploy:
      resources:
        reservations:
          memory: 2G
        limits:
          memory: 4G

  grafana:
    profiles: ["full"]

  jaeger:
    profiles: ["full"]
```

**Ralph Wiggum Task:**
```yaml
task_id: P3-RES-001
name: "Implement resource tier system"
backend: aider
files:
  - scripts/detect-resources.sh
  - ai-stack/compose/docker-compose.yml
  - scripts/start-ai-stack.sh
steps:
  1. Create detect-resources.sh
  2. Restore intelligent profiles
  3. Update start script
  4. Test on 8GB, 16GB, 32GB systems
completion_criteria:
  - Auto-detects resources
  - Starts appropriate profile
  - No OOM on 8GB system
```

---

### Task P3-RES-002: Add Resource Monitoring

**Problem:** No capacity planning, no alerts

**Solution:**
```python
# ai-stack/mcp-servers/shared/resource_monitor.py
import psutil
from prometheus_client import Gauge

# Prometheus metrics
MEMORY_USAGE = Gauge('system_memory_usage_bytes', 'Memory usage')
MEMORY_AVAILABLE = Gauge('system_memory_available_bytes', 'Memory available')
CPU_USAGE = Gauge('system_cpu_usage_percent', 'CPU usage')
DISK_USAGE = Gauge('system_disk_usage_bytes', 'Disk usage', ['path'])

class ResourceMonitor:
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval

    async def monitor_loop(self):
        """Background monitoring loop"""
        while True:
            # Memory
            mem = psutil.virtual_memory()
            MEMORY_USAGE.set(mem.used)
            MEMORY_AVAILABLE.set(mem.available)

            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            CPU_USAGE.set(cpu_percent)

            # Disk
            for path in ['/data', '/var/lib/postgresql']:
                usage = psutil.disk_usage(path)
                DISK_USAGE.labels(path=path).set(usage.used)

            # Check thresholds
            if mem.percent > 90:
                logger.error("memory_critical", percent=mem.percent)
                await self.alert_ops("Memory usage > 90%")

            if cpu_percent > 90:
                logger.warning("cpu_high", percent=cpu_percent)

            if usage.percent > 85:
                logger.error("disk_critical", path=path, percent=usage.percent)
                await self.alert_ops(f"Disk usage > 85% on {path}")

            await asyncio.sleep(self.check_interval)
```

**Ralph Wiggum Task:**
```yaml
task_id: P3-RES-002
name: "Add resource monitoring"
backend: aider
files:
  - ai-stack/mcp-servers/shared/resource_monitor.py
  - ai-stack/mcp-servers/aidb/server.py
  - ai-stack/compose/prometheus/alerts.yml
dependencies:
  - pip install psutil
steps:
  1. Implement ResourceMonitor
  2. Add to AIDB startup
  3. Add Prometheus alerts
  4. Test threshold triggers
completion_criteria:
  - Metrics exported
  - Alerts fire when > 90% memory
  - Dashboard shows resources
```

---

## Phase 4: Orchestration Restructuring (P1)

**Timeline:** Week 3
**Critical:** YES - Core architecture change
**Ralph Task IDs:** P4-ORCH-001 through P4-ORCH-004

### Task P4-ORCH-001: Nested Orchestration Architecture

**Problem:** Orchestrators work in isolation, not cooperatively

**New Architecture:**
```
User Request
    ↓
┌─────────────────────────────────────────┐
│ Layer 1: Ralph Wiggum (Task Loop)      │
│ - Handles: Iterative tasks            │
│ - Can invoke: Hybrid Coordinator       │
│ - Learning: Stores task telemetry     │
└──────────────┬──────────────────────────┘
               ↓
┌──────────────▼──────────────────────────┐
│ Layer 2: Hybrid Coordinator (Router)    │
│ - Handles: Query routing               │
│ - Can invoke: AIDB, Local/Remote LLM   │
│ - Learning: Extracts patterns          │
└──────────────┬──────────────────────────┘
               ↓
┌──────────────▼──────────────────────────┐
│ Layer 3: AIDB (Knowledge Base)         │
│ - Handles: Context retrieval           │
│ - Can invoke: Qdrant, PostgreSQL       │
│ - Learning: Stores learned skills      │
└──────────────┬──────────────────────────┘
               ↓
┌──────────────▼──────────────────────────┐
│ Layer 4: Execution Layer                │
│ - llama.cpp (local)                    │
│ - Claude/GPT (remote)                   │
│ - Aider/Continue (agents)               │
└─────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Cross-Cutting: Continuous Learning      │
│ - Monitors ALL layers                   │
│ - Learns from ALL interactions          │
│ - Improves ALL components               │
└─────────────────────────────────────────┘
```

**Implementation:**

```python
# ai-stack/mcp-servers/ralph-wiggum/orchestrator.py
class RalphOrchestrator:
    def __init__(self, hybrid_client, aidb_client):
        self.hybrid = hybrid_client  # Can use Hybrid Coordinator
        self.aidb = aidb_client      # Can use AIDB directly
        self.learning = LearningClient()  # Contributes to learning

    async def execute_task(self, task: Task) -> TaskResult:
        """Execute task with nested orchestration"""

        # Start task telemetry
        task_id = str(uuid4())
        await self.learning.start_task(task_id, task)

        iteration = 0
        while not self.is_complete(task):
            iteration += 1

            # Step 1: Get context from AIDB
            context = await self.aidb.get_context(task.description)

            # Step 2: Route query through Hybrid Coordinator
            # (which handles local/remote decision)
            response = await self.hybrid.route_query(
                query=task.description,
                context=context,
                iteration=iteration
            )

            # Step 3: Execute with agent backend
            result = await self.execute_with_backend(
                task=task,
                context=context,
                guidance=response
            )

            # Step 4: Check completion
            if self.check_exit_code(result) == 2:
                # Block premature exit
                logger.info("exit_blocked", iteration=iteration)
                await self.learning.log_event(task_id, "exit_blocked")
                continue

            # Step 5: Log to continuous learning
            await self.learning.log_iteration(
                task_id=task_id,
                iteration=iteration,
                input=task.description,
                output=result.output,
                success=result.success
            )

            # Step 6: Check if truly done
            if await self.verify_completion(task, result):
                break

        # Final learning update
        await self.learning.complete_task(
            task_id=task_id,
            iterations=iteration,
            success=True
        )

        return TaskResult(
            success=True,
            iterations=iteration,
            output=result.output
        )
```

```python
# ai-stack/mcp-servers/hybrid-coordinator/coordinator.py
class HybridCoordinator:
    def __init__(self, aidb_client, local_llm, remote_llm):
        self.aidb = aidb_client  # Can use AIDB
        self.local_llm = local_llm
        self.remote_llm = remote_llm
        self.learning = LearningClient()

    async def route_query(
        self,
        query: str,
        context: Optional[dict] = None,
        iteration: Optional[int] = None
    ) -> QueryResult:
        """Route query with learning integration"""

        # If called by Ralph Wiggum, context may already be provided
        if not context:
            # Get context from AIDB ourselves
            context = await self.aidb.get_context(query)

        # Route decision
        confidence = await self.score_query(query, context)

        if confidence >= 0.85:
            result = await self.local_llm.execute(query, context)
            route = "local"
        else:
            result = await self.remote_llm.execute(query, context)
            route = "remote"

        # Contribute to learning
        await self.learning.log_routing(
            query=query,
            context=context,
            route=route,
            confidence=confidence,
            result=result,
            iteration=iteration  # From Ralph if nested
        )

        return QueryResult(
            response=result.text,
            route=route,
            confidence=confidence
        )
```

```python
# ai-stack/mcp-servers/aidb/server.py
class AIDBServer:
    def __init__(self, postgres, qdrant, redis):
        self.postgres = postgres
        self.qdrant = qdrant
        self.redis = redis
        self.learning = LearningClient()

    async def get_context(self, query: str) -> ContextResult:
        """Retrieve context with learning integration"""

        # Check cache
        cached = await self.redis.get(f"context:{hash(query)}")
        if cached:
            return cached

        # Search Qdrant
        vectors = await self.qdrant.search(
            collection="skills-patterns",
            query_vector=self.embed(query),
            limit=5
        )

        # Search PostgreSQL
        documents = await self.postgres.search(query)

        # Combine results
        context = self.merge_context(vectors, documents)

        # Cache result
        await self.redis.set(f"context:{hash(query)}", context, ttl=3600)

        # Contribute to learning
        await self.learning.log_context_retrieval(
            query=query,
            results_count=len(context),
            sources=["qdrant", "postgres"]
        )

        return context
```

```python
# ai-stack/mcp-servers/shared/learning_client.py
class LearningClient:
    """Unified learning client for all components"""

    def __init__(self):
        self.telemetry_path = Path("/data/telemetry/unified-events.jsonl")

    async def log_event(self, event_type: str, data: dict):
        """Log event to unified telemetry stream"""
        event = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        # Append to telemetry
        async with aiofiles.open(self.telemetry_path, "a") as f:
            await f.write(json.dumps(event) + "\n")

    async def start_task(self, task_id: str, task: Task):
        await self.log_event("task_started", {
            "task_id": task_id,
            "description": task.description,
            "backend": task.backend
        })

    async def log_iteration(self, task_id: str, iteration: int, **kwargs):
        await self.log_event("task_iteration", {
            "task_id": task_id,
            "iteration": iteration,
            **kwargs
        })

    async def log_routing(self, query: str, route: str, **kwargs):
        await self.log_event("query_routed", {
            "query": query,
            "route": route,
            **kwargs
        })

    async def log_context_retrieval(self, query: str, **kwargs):
        await self.log_event("context_retrieved", {
            "query": query,
            **kwargs
        })
```

**Ralph Wiggum Task:**
```yaml
task_id: P4-ORCH-001
name: "Implement nested orchestration architecture"
backend: aider
files:
  - ai-stack/mcp-servers/ralph-wiggum/orchestrator.py
  - ai-stack/mcp-servers/hybrid-coordinator/coordinator.py
  - ai-stack/mcp-servers/aidb/server.py
  - ai-stack/mcp-servers/shared/learning_client.py
steps:
  1. Create LearningClient (unified telemetry)
  2. Update RalphOrchestrator to use Hybrid
  3. Update HybridCoordinator to use AIDB
  4. Update AIDB to log learning events
  5. Test nested workflow
completion_criteria:
  - Ralph can invoke Hybrid
  - Hybrid can invoke AIDB
  - All layers log to unified telemetry
  - Nested workflow test passes
```

**Testing:**
```bash
# Test: Nested workflow
# Submit task to Ralph that requires routing

curl -X POST http://localhost:8090/submit \
  -d '{
    "task": "Explain how NixOS networking works",
    "backend": "aider",
    "use_hybrid": true
  }'

# Verify flow:
# 1. Ralph receives task
# 2. Ralph calls Hybrid for routing
# 3. Hybrid calls AIDB for context
# 4. AIDB retrieves from Qdrant
# 5. Hybrid routes to local/remote
# 6. Result flows back up
# 7. All layers log to unified telemetry

tail -f /data/telemetry/unified-events.jsonl | jq .
```

---

## Phase 5: Observability & Monitoring (P1)

**Timeline:** Week 3-4
**Critical:** YES - Flying blind without this
**Ralph Task IDs:** P5-OBS-001 through P5-OBS-003

### Task P5-OBS-001: Add Prometheus Metrics

**Solution:**
```python
# ai-stack/mcp-servers/hybrid-coordinator/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Summary

# Learning metrics
LEARNING_EVENTS_PROCESSED = Counter(
    'learning_events_processed_total',
    'Total learning events processed'
)

LEARNING_PATTERNS_EXTRACTED = Counter(
    'learning_patterns_extracted_total',
    'Total patterns extracted'
)

LEARNING_DATASET_SIZE = Gauge(
    'learning_dataset_size_bytes',
    'Size of fine-tuning dataset'
)

LEARNING_LATENCY = Histogram(
    'learning_latency_seconds',
    'Learning pipeline latency',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

LEARNING_ERRORS = Counter(
    'learning_errors_total',
    'Learning pipeline errors',
    ['type']
)

LEARNING_VALUE_SCORE = Summary(
    'learning_value_score',
    'Distribution of value scores'
)

# Add to continuous_learning.py
async def process_telemetry_batch(self):
    with LEARNING_LATENCY.time():
        patterns = []

        for event in self.read_events():
            LEARNING_EVENTS_PROCESSED.inc()

            try:
                pattern = await self.extract_pattern(event)
                if pattern:
                    LEARNING_PATTERNS_EXTRACTED.inc()
                    LEARNING_VALUE_SCORE.observe(pattern.value_score)
                    patterns.append(pattern)
            except Exception as e:
                LEARNING_ERRORS.labels(type=type(e).__name__).inc()

        # Update dataset size
        if self.dataset_path.exists():
            LEARNING_DATASET_SIZE.set(self.dataset_path.stat().st_size)

        return patterns
```

**Ralph Wiggum Task:**
```yaml
task_id: P5-OBS-001
name: "Add Prometheus metrics to learning pipeline"
backend: aider
files:
  - ai-stack/mcp-servers/hybrid-coordinator/metrics.py
  - ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py
  - ai-stack/compose/prometheus/prometheus.yml
steps:
  1. Define metrics
  2. Add instrumentation
  3. Configure Prometheus scraping
  4. Test metric export
completion_criteria:
  - Metrics exported on /metrics
  - Prometheus scrapes successfully
  - Grafana dashboard shows metrics
```

---

### Task P5-OBS-002: Add Alerting Rules

**Solution:**
```yaml
# ai-stack/compose/prometheus/alerts.yml
groups:
  - name: learning_pipeline
    interval: 30s
    rules:
      - alert: LearningDaemonDown
        expr: up{job="learning-daemon"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Learning daemon is down"
          description: "The continuous learning daemon has been down for 5 minutes"

      - alert: LearningFallingBehind
        expr: learning_lag_seconds > 300
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Learning falling behind"
          description: "Learning daemon is {{ $value }}s behind real-time"

      - alert: DatasetGrowthAnomalous
        expr: rate(learning_dataset_size_bytes[1h]) > 10485760  # 10MB/hr
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Dataset growing too fast"
          description: "Dataset growing at {{ $value | humanize }}B/hr"

      - alert: LearningErrorRateHigh
        expr: rate(learning_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in learning pipeline"
          description: "{{ $value | humanizePercentage }} error rate"

      - alert: MemoryCritical
        expr: system_memory_usage_percent > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Memory usage critical"
          description: "Memory usage at {{ $value }}%"

      - alert: DiskCritical
        expr: system_disk_usage_percent{path="/data"} > 85
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Disk usage critical"
          description: "Disk usage at {{ $value }}% on /data"
```

**Ralph Wiggum Task:**
```yaml
task_id: P5-OBS-002
name: "Add alerting rules"
backend: aider
files:
  - ai-stack/compose/prometheus/alerts.yml
  - ai-stack/compose/prometheus/prometheus.yml
steps:
  1. Define alert rules
  2. Configure Prometheus
  3. Test alerts fire
completion_criteria:
  - Alerts configured
  - Test alerts fire correctly
  - Prometheus shows pending/firing
```

---

## Phase 6: Data Lifecycle & Operations (P1)

**Timeline:** Week 4
**Ralph Task IDs:** P6-OPS-001 through P6-OPS-003

### Task P6-OPS-001: Implement Telemetry Rotation

**Solution:**
```python
# ai-stack/mcp-servers/shared/telemetry_rotation.py
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta

class TelemetryRotator:
    def __init__(
        self,
        telemetry_dir: Path,
        max_age_days: int = 30,
        compress_after_days: int = 7
    ):
        self.telemetry_dir = telemetry_dir
        self.max_age_days = max_age_days
        self.compress_after_days = compress_after_days

    async def rotate(self):
        """Rotate and compress telemetry files"""

        now = datetime.now()
        cutoff_compress = now - timedelta(days=self.compress_after_days)
        cutoff_delete = now - timedelta(days=self.max_age_days)

        for jsonl_file in self.telemetry_dir.glob("*.jsonl"):
            mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)

            # Delete old files
            if mtime < cutoff_delete:
                logger.info("deleting_old_telemetry", file=jsonl_file.name)
                jsonl_file.unlink()
                continue

            # Compress old files
            if mtime < cutoff_compress:
                if not Path(f"{jsonl_file}.gz").exists():
                    logger.info("compressing_telemetry", file=jsonl_file.name)
                    with open(jsonl_file, 'rb') as f_in:
                        with gzip.open(f"{jsonl_file}.gz", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    jsonl_file.unlink()
```

**Ralph Wiggum Task:**
```yaml
task_id: P6-OPS-001
name: "Implement telemetry rotation"
backend: aider
files:
  - ai-stack/mcp-servers/shared/telemetry_rotation.py
  - systemd/telemetry-rotation.timer
  - systemd/telemetry-rotation.service
steps:
  1. Implement TelemetryRotator
  2. Create systemd timer (daily)
  3. Test rotation
completion_criteria:
  - Files compressed after 7 days
  - Files deleted after 30 days
  - Timer runs daily
```

---

### Task P6-OPS-002: Add Dataset Deduplication

**Solution:**
```python
# ai-stack/mcp-servers/hybrid-coordinator/dataset_cleanup.py
from typing import Set
import json
from pathlib import Path

class DatasetDeduplicator:
    def __init__(self, dataset_path: Path, similarity_threshold: float = 0.95):
        self.dataset_path = dataset_path
        self.similarity_threshold = similarity_threshold

    async def deduplicate(self) -> int:
        """Remove duplicate examples from dataset"""

        seen_hashes: Set[str] = set()
        unique_examples = []
        duplicates_removed = 0

        # Read dataset
        with open(self.dataset_path, 'r') as f:
            for line in f:
                example = json.loads(line)

                # Create hash of content
                content_hash = self._hash_example(example)

                if content_hash in seen_hashes:
                    duplicates_removed += 1
                    continue

                seen_hashes.add(content_hash)
                unique_examples.append(example)

        # Write deduplicated dataset
        temp_path = Path(f"{self.dataset_path}.tmp")
        with open(temp_path, 'w') as f:
            for example in unique_examples:
                f.write(json.dumps(example) + '\n')

        # Atomic replace
        temp_path.rename(self.dataset_path)

        logger.info(
            "dataset_deduplicated",
            removed=duplicates_removed,
            remaining=len(unique_examples)
        )

        return duplicates_removed

    def _hash_example(self, example: dict) -> str:
        """Create hash of example content"""
        # Hash based on messages content, not metadata
        messages = example.get('messages', [])
        content = json.dumps(messages, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
```

**Ralph Wiggum Task:**
```yaml
task_id: P6-OPS-002
name: "Add dataset deduplication"
backend: aider
files:
  - ai-stack/mcp-servers/hybrid-coordinator/dataset_cleanup.py
  - ai-stack/mcp-servers/hybrid-coordinator/continuous_learning.py
steps:
  1. Implement DatasetDeduplicator
  2. Run after each batch
  3. Test deduplication
completion_criteria:
  - Duplicates removed
  - Dataset size decreases
  - No data loss
```

---

## Phase 7: Testing & Validation (All)

**Timeline:** Week 5
**Ralph Task IDs:** P7-TEST-001 through P7-TEST-005

### Task P7-TEST-001: Create Integration Test Suite

**Solution:**
```python
# ai-stack/tests/test_orchestration_integration.py
import pytest
import asyncio
from pathlib import Path

@pytest.mark.asyncio
async def test_nested_orchestration():
    """Test Ralph → Hybrid → AIDB flow"""

    # Submit task to Ralph
    task = {
        "description": "How to configure NixOS networking?",
        "backend": "aider",
        "use_hybrid": true
    }

    result = await ralph_client.submit_task(task)

    # Verify all layers invoked
    telemetry = read_telemetry("/data/telemetry/unified-events.jsonl")

    assert any(e["event_type"] == "task_started" for e in telemetry)
    assert any(e["event_type"] == "query_routed" for e in telemetry)
    assert any(e["event_type"] == "context_retrieved" for e in telemetry)

    # Verify result
    assert result.success is True
    assert len(result.output) > 0

@pytest.mark.asyncio
async def test_learning_from_nested_workflow():
    """Test that learning captures nested workflow"""

    # Execute workflow
    await test_nested_orchestration()

    # Wait for learning processing
    await asyncio.sleep(5)

    # Verify pattern extracted
    patterns = list_patterns(qdrant_client, collection="skills-patterns")

    assert len(patterns) > 0
    assert any("nixos" in p.tags for p in patterns)

@pytest.mark.asyncio
async def test_circuit_breaker():
    """Test circuit breaker opens on failures"""

    # Stop Qdrant
    subprocess.run(["podman", "stop", "local-ai-qdrant"])

    # Trigger 5 failures
    for i in range(5):
        try:
            await learning_pipeline.process_telemetry_batch()
        except Exception:
            pass

    # Verify circuit open
    assert learning_pipeline.qdrant_breaker.state == CircuitState.OPEN

    # Start Qdrant
    subprocess.run(["podman", "start", "local-ai-qdrant"])

    # Wait for recovery
    await asyncio.sleep(60)

    # Verify circuit recovers
    await learning_pipeline.process_telemetry_batch()
    assert learning_pipeline.qdrant_breaker.state == CircuitState.CLOSED

@pytest.mark.asyncio
async def test_telemetry_checkpointing():
    """Test crash recovery with checkpoints"""

    # Process 500 events
    events = generate_test_events(500)
    write_telemetry(events)

    # Process 250
    pipeline = ContinuousLearningPipeline(...)
    await pipeline.process_telemetry_batch()

    # Verify checkpoint exists
    assert Path("/data/checkpoints/checkpoint.pkl").exists()

    # Simulate crash and restart
    del pipeline
    pipeline = ContinuousLearningPipeline(...)

    # Verify resumes from checkpoint
    assert pipeline.processed_count == 250

    # Process remaining
    await pipeline.process_telemetry_batch()

    # Verify no duplicates
    assert pipeline.processed_count == 500

@pytest.mark.asyncio
async def test_resource_tier_detection():
    """Test resource detection and profile selection"""

    # Mock system with 8GB RAM
    with mock.patch('psutil.virtual_memory') as mock_mem:
        mock_mem.return_value.total = 8 * 1024**3

        profile = detect_resource_profile()
        assert profile == "minimal"

    # Mock system with 16GB RAM
    with mock.patch('psutil.virtual_memory') as mock_mem:
        mock_mem.return_value.total = 16 * 1024**3

        profile = detect_resource_profile()
        assert profile == "standard"

    # Mock system with 32GB RAM
    with mock.patch('psutil.virtual_memory') as mock_mem:
        mock_mem.return_value.total = 32 * 1024**3

        profile = detect_resource_profile()
        assert profile == "full"
```

**Ralph Wiggum Task:**
```yaml
task_id: P7-TEST-001
name: "Create integration test suite"
backend: aider
files:
  - ai-stack/tests/test_orchestration_integration.py
  - ai-stack/tests/conftest.py
steps:
  1. Write test cases
  2. Add fixtures
  3. Run tests
completion_criteria:
  - All tests pass
  - Coverage > 80%
```

---

## Ralph Wiggum Task Definitions

### Complete Task List (Ready to Execute)

```yaml
# Phase 1: Security (Week 1)
- task_id: P1-SEC-001
  priority: P0
  estimated_iterations: 5

- task_id: P1-SEC-002
  priority: P0
  estimated_iterations: 3

- task_id: P1-SEC-003
  priority: P0
  estimated_iterations: 2

# Phase 2: Reliability (Week 1-2)
- task_id: P2-REL-001
  priority: P0
  estimated_iterations: 8

- task_id: P2-REL-002
  priority: P0
  estimated_iterations: 6

- task_id: P2-REL-003
  priority: P0
  estimated_iterations: 4

- task_id: P2-REL-004
  priority: P0
  estimated_iterations: 5

# Phase 3: Resources (Week 2)
- task_id: P3-RES-001
  priority: P0
  estimated_iterations: 6

- task_id: P3-RES-002
  priority: P0
  estimated_iterations: 4

# Phase 4: Orchestration (Week 3)
- task_id: P4-ORCH-001
  priority: P1
  estimated_iterations: 10

# Phase 5: Observability (Week 3-4)
- task_id: P5-OBS-001
  priority: P1
  estimated_iterations: 4

- task_id: P5-OBS-002
  priority: P1
  estimated_iterations: 3

# Phase 6: Operations (Week 4)
- task_id: P6-OPS-001
  priority: P1
  estimated_iterations: 3

- task_id: P6-OPS-002
  priority: P1
  estimated_iterations: 4

# Phase 7: Testing (Week 5)
- task_id: P7-TEST-001
  priority: P1
  estimated_iterations: 12
```

### Execution Commands

```bash
# Submit all P0 tasks to Ralph Wiggum
for task_id in P1-SEC-{001..003} P2-REL-{001..004} P3-RES-{001..002}; do
  curl -X POST http://localhost:8090/submit \
    -H "Content-Type: application/json" \
    -d @tasks/${task_id}.json
done

# Monitor progress
curl http://localhost:8090/status | jq '.tasks[] | select(.priority == "P0")'

# View results
curl http://localhost:8090/results?phase=1 | jq .
```

---

## Verification Checklist

### Security ✅
- [ ] No subprocess calls in dashboard proxy
- [ ] Rate limiting active
- [ ] Secrets in environment variables
- [ ] Shell injection tests pass

### Reliability ✅
- [ ] Checkpointing works
- [ ] Circuit breaker opens/closes
- [ ] Backpressure monitoring active
- [ ] File locking prevents corruption

### Resources ✅
- [ ] Resource detection works
- [ ] Appropriate profile selected
- [ ] No OOM on 8GB system
- [ ] Resource monitoring active

### Orchestration ✅
- [ ] Ralph can invoke Hybrid
- [ ] Hybrid can invoke AIDB
- [ ] All layers log to unified telemetry
- [ ] Nested workflow test passes

### Observability ✅
- [ ] Prometheus metrics exported
- [ ] Alerts configured
- [ ] Grafana dashboards working
- [ ] Alerts fire correctly

### Operations ✅
- [ ] Telemetry rotation works
- [ ] Dataset deduplication works
- [ ] Backups automated
- [ ] Rollback procedure documented

### Testing ✅
- [ ] Integration tests pass
- [ ] Load tests pass
- [ ] Crash recovery tests pass
- [ ] Coverage > 80%

---

## Success Metrics

### Week 1 (P0 Complete)
- Security vulnerabilities: 0
- Crash recovery: Working
- Resource usage: Controlled

### Week 3 (P1 Complete)
- Nested orchestration: Working
- Observability: Complete
- Tests: Passing

### Week 5 (Production Ready)
- All tests: Passing
- Documentation: Complete
- Deployment: Automated
- Grade: A (9/10) ⬆️ from D+ (3/10)

---

**Status: Ready for Execution via Ralph Wiggum Loop**

*All tasks defined, all tests specified, all success criteria clear*
*Let Ralph iterate through each task until production-ready*
