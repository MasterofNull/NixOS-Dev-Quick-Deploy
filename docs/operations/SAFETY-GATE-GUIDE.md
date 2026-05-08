# Safety Gate — Phase 28 Operations Guide

Status: Active
Owner: AI Harness Team
Last Updated: 2026-05-08

The safety gate is a runtime enforcement layer that sits at the
DELEGATE → VALIDATE transition of the UAG lifecycle FSM.

Before a session advances out of DELEGATE, every action string is classified
by the blast-radius classifier and checked against the session's safety mode.

---

## Blast-Radius Tiers

| Tier | Examples | Risk |
|------|----------|------|
| `critical` | `rm -rf`, `DROP TABLE`, `nixos-rebuild switch`, `--force` | Irreversible at scale; production-state change |
| `high` | `git push`, `systemctl stop`, `git reset --hard`, `kill -9` | Hard-to-reverse or externally visible |
| `medium` | `git commit`, file writes, `POST /api/*`, `INSERT INTO` | Local state mutations, API side effects |
| `low` | `GET /`, `cat`, `ls`, `grep`, `git status`, `aq-qa` | Read-only; no lasting effect |

Unknown actions default to `medium` (non-trivially risky).

---

## Safety Modes

| Mode | `critical` | `high` | `medium` | `low` |
|------|-----------|--------|---------|-------|
| `open` (default) | ✅ allow | ✅ allow | ✅ allow | ✅ allow |
| `review` | ❌ block → ABORTED | ⏳ queue → PRSI | ✅ allow | ✅ allow |
| `strict` | ❌ block → ABORTED | ❌ block → ABORTED | ❌ block → ABORTED | ✅ allow |

`open` is the default for backward compatibility. Existing sessions without an
explicit mode are treated as `open` — no regression.

---

## HTTP API

### Set safety mode for a session

```
POST /control/safety/gate
Content-Type: application/json

{"session_id": "<id>", "safety_mode": "open" | "review" | "strict"}
```

Response: `{"ok": true, "session_id": "...", "safety_mode": "..."}`

### Read gate state for a session

```
GET /control/safety/gate/{session_id}
```

Response:
```json
{
  "session_id": "...",
  "safety_mode": "review",
  "gate_log": [
    {
      "ts": 1746700000.0,
      "mode": "review",
      "allowed": false,
      "tiers": {"nixos-rebuild switch": "critical"},
      "blocked": ["nixos-rebuild switch"],
      "queued": [],
      "reason": "review mode — 1 critical action(s) blocked"
    }
  ]
}
```

---

## DELEGATE Advance with Actions

When advancing a DELEGATE phase, include `delegation_actions` in the request body
so the gate has a concrete list to classify:

```
POST /agent/lifecycle/{session_id}/advance
Content-Type: application/json

{
  "status": "passed",
  "output_summary": "Executed deployment plan",
  "delegation_actions": [
    "git commit -m 'deploy'",
    "nixos-rebuild switch"
  ]
}
```

If the gate blocks (mode=`review` and a critical action is present), the response
returns HTTP 403 and the session is moved to `ABORTED`:

```json
{
  "session_id": "...",
  "previous_phase": "delegate",
  "current_phase": "aborted",
  "is_terminal": true,
  "safety_gate": {
    "blocked": true,
    "reason": "review mode — 1 critical action(s) blocked",
    "blocked_actions": ["nixos-rebuild switch"],
    "queued_actions": []
  }
}
```

Actions in `queued_actions` (review mode + high tier) require PRSI approval
before the session can proceed. Use the PRSI approval queue to approve/reject.

---

## Operator Configuration

Set a session to strict mode for high-stakes autonomous runs:

```bash
curl -sf -X POST http://127.0.0.1:8003/control/safety/gate \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>","safety_mode":"strict"}'
```

Read the gate log after an advance:

```bash
curl -sf http://127.0.0.1:8003/control/safety/gate/<session_id> | python3 -m json.tool
```

---

## Key Files

| File | Purpose |
|------|---------|
| `extensions/blast_radius_classifier.py` | Pattern-based action classifier |
| `workflow/safety_gate.py` | Policy evaluation + GateResult |
| `workflow/lifecycle_fsm.py` | LifecycleSession.safety_mode field |
| `workflow/intake_gateway.py` | Gate wired at DELEGATE→VALIDATE |
| `workflow/evidence_safety_handlers.py` | HTTP endpoints |
| `scripts/testing/test-blast-radius-classifier.py` | 49 classifier unit tests |
| `scripts/testing/test-safety-gate.py` | 28 gate policy unit tests |

---

## Health Check

```bash
# aq-qa check 0.9.1
curl -sf -X POST http://127.0.0.1:8003/control/safety/gate \
  -H "Content-Type: application/json" \
  -d '{"session_id":"healthcheck","safety_mode":"open"}'
# Expects: {"ok": true, ...}
```

This check is included in `aq-qa 0` as check `0.9.1`.
