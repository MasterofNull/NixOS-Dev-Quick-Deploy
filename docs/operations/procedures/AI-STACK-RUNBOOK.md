# AI Stack Operator Runbook

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05

## Quick Reference

### Health Checks

```bash
# Basic stack health
curl -sf http://localhost:8003/health | jq '.status'

# Detailed health with dependencies
curl -sf http://localhost:8003/health/detailed | jq

# Service status
systemctl status llama-cpp ai-hybrid-coordinator ai-aidb qdrant

# All AI services at once
systemctl list-units 'ai-*.service' 'llama-*.service' 'qdrant.service' --no-pager
```

### Log Access

```bash
# Live logs for specific service
journalctl -u llama-cpp -f

# Recent errors across AI stack
journalctl -u 'ai-*.service' -u 'llama-*.service' --since="1 hour ago" -p err

# Hybrid coordinator with full output
journalctl -u ai-hybrid-coordinator --no-pager -n 200
```

---

## Failure Modes and Resolution

### 1. llama-cpp Service Won't Start

**Symptoms:**
- `systemctl status llama-cpp` shows failed
- No response on port 8080

**Diagnosis:**
```bash
journalctl -u llama-cpp -n 50 --no-pager
ls -la /var/lib/llama-cpp/models/
```

**Common Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Model file missing | `systemctl restart llama-cpp-model-fetch` |
| Model file corrupt | Remove and re-download: `rm /var/lib/llama-cpp/models/*.gguf && systemctl restart llama-cpp-model-fetch` |
| Out of memory | Check `free -h`; reduce model size or increase swap |
| ROCm GPU error | Check `HSA_OVERRIDE_GFX_VERSION` in service env; try `rocm-smi` |
| AppArmor denial | Check `dmesg | grep DENIED`; verify `/etc/apparmor.d/` profile |

**Recovery:**
```bash
# Full restart sequence
systemctl restart llama-cpp-model-fetch
systemctl restart llama-cpp
systemctl status llama-cpp
```

---

### 2. Hybrid Coordinator Returns 503

**Symptoms:**
- `/health` returns `status: degraded` or fails
- API calls timeout or return 503

**Diagnosis:**
```bash
curl -s http://localhost:8003/health/detailed | jq '.circuit_breakers'
journalctl -u ai-hybrid-coordinator --since="10 minutes ago" | grep -i error
```

**Common Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| Circuit breaker open | Wait 30s for half-open; check upstream service |
| Qdrant unreachable | `systemctl restart qdrant` |
| llama-server down | `systemctl restart llama-cpp` |
| Rate limit exhausted | Wait for window reset (check `Retry-After` header) |

**Recovery:**
```bash
# Restart dependencies in order
systemctl restart qdrant
sleep 5
systemctl restart ai-aidb
sleep 5
systemctl restart ai-hybrid-coordinator
```

---

### 3. Qdrant Collection Empty or Missing

**Symptoms:**
- RAG queries return no results
- `/discovery/capabilities` shows `points_count: 0`

**Diagnosis:**
```bash
curl -s http://localhost:6333/collections | jq '.result.collections[].name'
curl -s http://localhost:6333/collections/error-solutions | jq '.result.points_count'
```

**Fixes:**
```bash
# Rebuild collections from AIDB
scripts/data/rebuild-qdrant-collections.sh

# Or import specific knowledge
scripts/data/import-agent-instructions.sh
```

---

### 4. High Latency / Slow Responses

**Symptoms:**
- API responses take >5s
- Prometheus metrics show high latency

**Diagnosis:**
```bash
# Check metrics
curl -s http://localhost:8003/metrics | grep request_latency

# Check system resources
htop
nvidia-smi  # or rocm-smi for AMD
free -h
```

**Common Causes & Fixes:**

| Cause | Fix |
|-------|-----|
| CPU thermal throttling | Check `sensors`; improve cooling |
| GPU memory full | Restart llama-cpp to clear VRAM |
| Swap thrashing | Reduce context size or model quantization |
| Cache cold | Run `scripts/data/seed-routing-traffic.sh --count 20` |

---

### 5. Model Fails After Suspend/Resume

**Symptoms:**
- llama-cpp unresponsive after laptop wake
- ROCm errors in journal

**Diagnosis:**
```bash
journalctl -u llama-cpp --since="5 minutes ago"
rocm-smi  # Check GPU state
```

**Fix:**
The system has automatic recovery via `llama-cpp-resume.service`. If it doesn't trigger:
```bash
systemctl restart llama-cpp
```

---

### 6. Harness Eval Timeouts

**Symptoms:**
- `/harness/eval` returns timeout errors
- Eval runs take >180s

**Diagnosis:**
```bash
journalctl -u ai-hybrid-coordinator | grep -i "harness.*timeout"
```

**Fixes:**
```bash
# Increase timeout in options (requires rebuild)
# mySystem.aiStack.aiHarness.eval.timeoutSeconds = 300

# Or run with reduced iterations
curl -X POST http://localhost:8003/harness/eval \
  -H "Content-Type: application/json" \
  -d '{"max_runs": 10, "timeout_seconds": 60}'
```

---

### 7. Rate Limiting Blocks Legitimate Traffic

**Symptoms:**
- 429 responses with `Retry-After` header
- Burst traffic blocked

**Diagnosis:**
```bash
curl -s http://localhost:8003/stats | jq '.rate_limiter'
```

**Temporary Override:**
```bash
# Set environment variable before restart
RATE_LIMIT_ENABLED=false systemctl restart ai-hybrid-coordinator

# Or increase limits
RATE_LIMIT_DEFAULT_RPM=200 systemctl restart ai-hybrid-coordinator
```

---

### 8. COSMIC Desktop Issues

**Symptoms:**
- cosmic-greeter shows blank screen
- Session won't start

**Diagnosis:**
```bash
journalctl -u cosmic-greeter --since="5 minutes ago"
ls -la /var/lib/cosmic-greeter/.config/cosmic/
```

**Fixes:**
```bash
# Regenerate greeter config directories
sudo systemd-tmpfiles --create

# Restart display manager
sudo systemctl restart cosmic-greeter
```

---

## Preventive Maintenance

### Daily Checks
```bash
# Quick health validation
scripts/testing/check-mcp-health.sh
```

### Weekly Tasks
```bash
# Review performance report
scripts/ai/aq-report --since=7d --format=text

# Check for knowledge gaps
scripts/ai/aq-hints --query "recent errors" --format json | jq '.gaps'
```

### After System Rebuild
```bash
# Verify all services started
systemctl list-units 'ai-*.service' --state=failed

# Warm semantic cache
scripts/data/seed-routing-traffic.sh --count 20

# Run quick eval
scripts/ai/aq-prompt-eval --id quick-check
```

---

## Emergency Contacts

| Issue | Resource |
|-------|----------|
| Critical service down | Check `journalctl -p err --since="1 hour ago"` |
| Data corruption | Restore from Qdrant/PostgreSQL snapshots |
| Security incident | Review `/var/log/ai-stack/tool-audit.jsonl` |

---

## Related Documentation

- [Architecture Overview](../../architecture/AI-STACK-ARCHITECTURE.md)
- [API Reference](../../api/hybrid-openapi.yaml)
- [COSMIC Keyboard Shortcuts](../reference/COSMIC-KEYBOARD-SHORTCUTS.md)
- [Security Audit](../../SECURITY-AUDIT-DEC-2025.md)
