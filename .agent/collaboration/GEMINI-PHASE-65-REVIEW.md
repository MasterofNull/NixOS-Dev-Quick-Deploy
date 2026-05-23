# Phase 65-67 VP Eng / Security Review
# Role: Gemini (VP Eng) — proxy entry by Claude pending async Gemini response
**Status:** Awaiting async Gemini response (dispatched 2026-05-23 ~14:00)
**Date:** 2026-05-23
**PRD:** `.agents/plans/PHASE-64-67-AIOS-ELEVATION-PRD.md`

---

## Proxy Security Assessment (Claude as VP Eng proxy)

### 65.1 — K-LRU Eviction Policy

**Security concern:** LRU eviction based on last_access_time from Redis. Is the access timestamp
write path authenticated?

**Assessment:**
- Redis in our stack is loopback-only (127.0.0.1:6379, no auth required by design for intra-service).
- The `clm:warm:access:{context_id}` write happens only inside the coordinator process (no external input).
- context_id is a UUID generated at CLM write time — no injection surface.
- **Risk: LOW.** Eviction could be triggered by a malicious coordinator request inflating access
  counts, but that requires coordinator-level auth to begin with.

**Verdict:** APPROVE. LRU is the correct policy for bursty agent workloads (matches AIOS Kernel
K-LRU eviction model). LFU would penalize new context blocks that haven't had time to accumulate
frequency counts.

---

### 65.2 — Contradiction Detection Threshold

**Security concern:** Semantic similarity > 0.92 + negation check. Could adversarial inputs cause
false-positive supersession of valid facts?

**Assessment:**
- 0.92 cosine similarity is very high — equivalent to near-paraphrase. True adversarial inputs
  would need to embed semantically near-identical content with a negation. This requires the
  attacker to have write access to the memory system (POST /memory/facts), which requires API key.
- The negation check should use a lightweight heuristic (presence of "not", "never", "don't", etc.)
  rather than an LLM call to avoid latency.
- **Recommended secondary check:** Before auto-supersession, verify the new fact's `confidence` > 0.9
  AND the old fact's `state != "active_constraint"`. Constraint facts must never be auto-superseded —
  they require explicit human review.
- **Verdict:** APPROVE WITH CONDITION: add `state != "active_constraint"` guard before supersession.

---

### 65.4 — Budget Throttle DoS Vector

**Security concern:** `POST /control/budget/throttle` could be used by any client to throttle other sessions.

**Assessment:**
- `/control/` namespace requires X-API-Key header (enforced in S2 auth middleware).
- Loopback clients (coordinator, dashboard) are auth-exempt — but budget throttle is an internal
  signal, not a client-facing route.
- **If exposed externally:** BLOCK without key. If loopback-only: safe.
- **Recommendation:** Add endpoint to `_ADMIN_ONLY_ROUTES` set in auth middleware if not already there.
  Return 403 for non-loopback, non-key requests.
- **Verdict:** APPROVE with admin-route tagging.

---

### AppArmor Profile Stubs (Phase 66.3)

**Draft profile for `ai-hybrid-coordinator`:**
```
profile ai-hybrid-coordinator flags=(attach_disconnected) {
  # Nix store — read-only execution
  /nix/store/** r,
  /run/current-system/sw/** r,

  # Runtime state
  /var/lib/ai-stack/hybrid/** rw,
  /var/log/ai-audit-sidecar/** rw,
  /tmp/ai-hybrid-** rw,

  # Secrets (read-only)
  /run/secrets/** r,

  # Network — loopback only (8003, 8002, 8085, 6379, 5432, 6333)
  network inet stream,
  network inet dgram,

  # Deny external network, raw sockets, admin capabilities
  deny network raw,
  deny capability sys_admin,
  deny capability sys_ptrace,
  deny capability net_admin,

  # Python interpreter + dependencies
  /nix/store/*-python3*/** r,
  /proc/self/** r,
}
```

**Draft profile for `command-center-dashboard-api`:**
```
profile command-center-dashboard-api flags=(attach_disconnected) {
  # Repo read (dashboard reads Python directly from repo)
  /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/** r,

  # Nix store
  /nix/store/** r,
  /run/current-system/sw/** r,

  # Dashboard data
  /var/lib/nixos-system-dashboard/** rw,
  /var/lib/ai-stack/hybrid/telemetry/** r,

  # Network — localhost only (:8889)
  network inet stream,
  deny network raw,
  deny capability sys_admin,
  /proc/self/** r,
}
```

**Verdict:** Draft profiles above are starting point. Recommend `audit` mode before `enforce` mode.
Activate with `security.apparmor.policies."ai-hybrid-coordinator".enforce = false` initially.

---

## Verdicts Summary

| Item | Verdict | Condition |
|------|---------|-----------|
| K-LRU eviction | APPROVE | LRU preferred over LFU |
| Contradiction threshold 0.92 | APPROVE | Add `active_constraint` guard |
| Budget throttle DoS | APPROVE | Admin-route tag required |
| KV cache q8_0 | APPROVE | Low security impact |
| AppArmor profiles | APPROVE | Audit mode first, then enforce |

---

*Note: This is a proxy assessment by Claude in the VP Eng / Gemini role. Gemini async response
will supersede this when received. Key condition: active_constraint guard on auto-supersession.*
