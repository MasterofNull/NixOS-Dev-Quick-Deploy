---
name: testing-patterns
description: "Testing Patterns Skill"
---

# Testing Patterns Skill
## Tags
qa, testing, harness_qa, http_get, check, phase, smoke, unit, mock, qdrant, coordinator, timeout
## When to Use
Writing a new QA check; understanding why a check is failing; adding a new phase to harness_qa;
deciding whether to mock or call live services; debugging 3-second timeout failures; understanding
the `http_get()` return type.

---

## 1. http_get() Returns a Tuple — Not a Dict

```python
# CORRECT — http_get returns (status_code: int, body: str):
status, body = http_get(f"{BASE}/api/health")
if status != 200:
    return False, f"health returned {status}"
data = json.loads(body)

# WRONG — will raise TypeError: cannot unpack non-sequence:
response = http_get(f"{BASE}/api/health")
if response["status"] != 200:    # AttributeError: 'tuple' has no attribute...
```

This bites every new check author. Always unpack immediately.

---

## 2. Timeout: 3s (curl bash) vs 5s (Python http_get)

The bash smoke tests use `curl --max-time 3`. The Python `http_get()` uses a 5-second timeout.

**Symptom**: check passes in Python harness but fails in bash health-spider or vice versa.
**Cause**: slow endpoints (coordinator with large RAG result, local model warm-up) hit the 3s
curl limit but not the 5s Python limit.

When writing a new check for an endpoint known to be slow:
```python
# Use explicit timeout for slow endpoints:
status, body = http_get(url, timeout=15)
```

For bash smoke tests, use `--max-time 10` for coordinator/llama endpoints.

---

## 3. QA Phase Registration Contract

New checks must be registered in `harness_qa/phases/` as a phase file:

```python
# harness_qa/phases/phase86.py
PHASE_CHECKS = [
    ("86.1", "Description of check", check_86_1),
    ("86.2", "Description of check", check_86_2),
]

def check_86_1() -> tuple[bool, str]:
    """Returns (pass: bool, detail: str)."""
    status, body = http_get(f"{BASE}/api/aistack/new-endpoint")
    if status != 200:
        return False, f"status {status}"
    data = json.loads(body)
    if data.get("field") != "expected_value":
        return False, f"got {data.get('field')}"
    return True, "ok"
```

Register the phase in `harness_qa/runner.py` PHASES list:
```python
from phases.phase86 import PHASE_CHECKS
PHASES.extend(PHASE_CHECKS)
```

Always number checks sequentially within a phase (86.1, 86.2, etc.). Check IDs are permanent —
once a check is in git history, do not renumber.

---

## 4. Mock vs Live Service Boundaries

| Service | Mock for unit tests | Live for QA |
|---------|---------------------|-------------|
| Qdrant / AIDB | YES — use in-memory dict fixture | NO — QA must verify real collection |
| Coordinator (:8003) | YES for unit; NO for integration | YES — QA runs full stack |
| llama.cpp (:8080) | YES for unit | NO — QA verifies model is responsive |
| Dashboard API (:8889) | Never mock in QA | Always hit live |
| Redis | OK to mock for unit | Live for QA |

Rule: **harness_qa checks are always integration tests**. They hit live services.
Unit test mocks live in `tests/` (if they exist). Don't mix contexts.

---

## 5. Dashboard API Check Pattern

```python
BASE = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8889")

def check_dashboard_endpoint() -> tuple[bool, str]:
    status, body = http_get(f"{BASE}/api/aistack/my-route")
    if status == 404:
        return False, "route not registered — did you add router.include_router()?"
    if status == 500:
        return False, f"server error: {body[:200]}"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False, f"non-JSON response: {body[:100]}"
    # Validate shape:
    if "expected_key" not in data:
        return False, f"missing expected_key in response: {data.keys()}"
    return True, f"ok — value={data['expected_key']}"
```

Always check 404 explicitly — it means the route was never wired, not a runtime error.

---

## 6. Coordinator Check Pattern

Coordinator checks must handle the auth header for non-loopback test runners:

```python
COORD = os.environ.get("COORD_URL", "http://127.0.0.1:8003")
COORD_KEY = os.environ.get("COORD_API_KEY", "")

def check_coordinator_query() -> tuple[bool, str]:
    payload = {"query": "test pattern", "n_results": 1}
    headers = {"X-API-Key": COORD_KEY} if COORD_KEY else {}
    status, body = http_post(f"{COORD}/query", payload, headers=headers)
    if status != 200:
        return False, f"coordinator /query returned {status}"
    data = json.loads(body)
    if "results" not in data:
        return False, f"missing results key: {list(data.keys())}"
    return True, f"ok — {len(data['results'])} results"
```

From 127.0.0.1 (loopback), coordinator doesn't require API key for paths in LOOPBACK_AGENT_PREFIXES.
`/query` IS in that list. `X-API-Key` is optional for loopback.

---

## 7. xfail / Known Failures

Mark checks that are known to be broken or environment-dependent:

```python
PHASE_CHECKS = [
    ("86.1", "Normal check", check_86_1),
    ("86.2", "[xfail] Feature requires GPU", check_86_2),  # xfail in description
]
```

The harness runner skips `[xfail]` checks from the pass/fail tally.
Do not remove a failing check — mark it xfail with a comment explaining why.
xfail checks should be resolved within 2 phases or escalated to issues-backlog.md.

---

## 8. Running Specific Phase Checks

```bash
# Run all checks:
aq-qa 0

# Run specific phase checks:
python3 scripts/testing/harness_qa/runner.py --phase 86

# Run single check by ID:
python3 scripts/testing/harness_qa/runner.py --check 86.1

# Verbose output (shows pass detail, not just failures):
python3 scripts/testing/harness_qa/runner.py --verbose
```

---

## 9. Service Restart Between Test Runs

After editing dashboard backend Python files:
```bash
systemctl restart command-center-dashboard-api
sleep 2   # cold start takes ~1-2 seconds
aq-qa 0   # now run checks
```

After NixOS module changes (AppArmor, service units, new packages):
```bash
# User must run in terminal (sudo not available in agent shell):
sudo nixos-rebuild switch --flake .#hyperd-ai-dev
```

Stale `.pyc` files can make edits appear to not take effect:
```bash
find dashboard/backend -name "*.pyc" -newer dashboard/backend/api/routes/aistack.py -delete
systemctl restart command-center-dashboard-api
```

---

## 10. Adding a New Dashboard Route (Full Checklist)

1. Add route handler in `dashboard/backend/api/routes/aistack.py`
2. Verify router is included in `dashboard/backend/api/app.py` (it is — shared router)
3. Add a QA check in the current phase file
4. Restart service: `systemctl restart command-center-dashboard-api`
5. Verify: `curl -s http://127.0.0.1:8889/api/aistack/new-route | jq .`
6. Run QA: `aq-qa 0`
7. If AppArmor is in enforce mode — check `journalctl -u apparmor.service` for denials
