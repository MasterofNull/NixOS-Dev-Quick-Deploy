# Architecture Revamp — Implementation Contract
**Status:** FINAL — All senior agents confirmed; all Open Questions resolved; ready for Round 1 execution
**Date:** 2026-05-15
**Lead:** Claude Sonnet 4.6 (Orchestrator)
**Agents:** Gemini CLI · Codex CLI · Qwen (local, aq-agent-loop)
**Source PRD:** `.agents/plans/ARCH-REVAMP-PRD.md` (§1–§16)

This contract defines the shared standards, slice ownership, and integration
protocol for implementing the architecture revamp. ALL agents must read and
confirm their section before any code is written.

---

## Part 1 — Non-Negotiable Standards

Every agent, every file, every commit MUST follow these rules. Tier0 gate
enforces most of them automatically. Violations block merge.

### 1.1 Port / URL hygiene
- **Never hardcode ports or URLs** in Python or shell
- Python: read from env vars (`os.environ["COORDINATOR_URL"]`, etc.)
- Shell: use `${PORT:-default}` form and source `config/service-endpoints.sh`
- Nix: use `${toString cfg.ports.xxx}` — never a bare integer literal
- Single source of truth: `nix/modules/core/options.nix`

### 1.2 Response header convention (X-AI-* namespace)
All new response headers follow the `X-AI-` prefix pattern established in the
switchboard. New headers introduced in this revamp:

| Header | Set by | Meaning |
|--------|--------|---------|
| `X-AI-Route` | switchboard | `local` or `remote` |
| `X-AI-Profile` | switchboard | active profile name |
| `X-AI-Hints-Skipped` | switchboard | `timeout` or `disabled` if hints not injected |
| `X-AI-Fallback` | switchboard | `budget-exceeded` or `remote-unavailable` when downgraded |
| `X-AI-Model-Alias` | switchboard | actual model used when alias rewrite occurred |
| `X-AI-Profile-Card` | switchboard | `1` when profile card was injected |

No agent may introduce headers outside the `X-AI-` namespace without approval.

### 1.3 Routing taxonomy — canonical source of truth
`ai-stack/mcp-servers/hybrid-coordinator/routing_contract.py` is the ONLY
authoritative definition of routing tiers and decisions.

```
RoutingTier: LOCAL → EDGE → REMOTE_FREE → REMOTE_PAID → REMOTE_FLAGSHIP
RoutingDecision: dataclass carrying tier + rationale + model_hint
```

- Any new routing logic MUST use `RoutingTier` and `RoutingDecision`
- No vendor model names (no "claude", "gpt", "gemini") in code — use tier names
- Thin adapters for legacy `router.py` / `task_router.py` must emit `RoutingDecision`
- No new routing taxonomy may be created without PRD amendment

### 1.4 Python conventions
- HTTP client: `httpx` (async) — never `requests`
- Async: `async/await` + `asyncio.create_task` — never `asyncio.coroutine`
- Type hints on all new functions
- `python -m py_compile <file>` must pass before commit
- No `sys.path.insert` in new code — import from installed packages only

### 1.5 Nix conventions
- All new switchboard profile fields MUST appear in `switchboardProfileDefaults`
  at `switchboard.nix:202–365` in the same format as existing profiles
- New profiles need: `injectHints`, `forceProvider`, `maxInputTokens`,
  `maxMessages`, `maxOutputTokens`, `profileCard` (can be empty string)
- env var names: `SWB_` prefix for switchboard config, `AI_STACK_` for stack config
- `nix flake check` must pass

### 1.6 Commit hygiene
- Every commit: `scripts/governance/tier0-validation-gate.sh --pre-commit`
- Commit format: `type(scope): description`
- Co-Authored-By line for every agent that contributed to the commit
- Never `--no-verify`

### 1.7 Forbidden patterns
| Pattern | Why forbidden | Alternative |
|---------|--------------|-------------|
| Hardcoded `127.0.0.1:8080` etc. | Violates port SOT | env var `LLAMA_CPP_URL` |
| `import requests` | Use httpx | `import httpx` |
| Vendor names in routing code | Couples to specific providers | `RoutingTier.REMOTE_PAID` |
| New orphaned routing taxonomy | Adds a 4th parallel system | Extend `routing_contract.py` |
| `sys.path.insert` in production code | Creates split-brain vs nix store | package properly |
| Appending hints to last sys message | Breaks client prompt structure | Inject as first sys message |

---

## Part 2 — Slice Registry

Slices are grouped by agent owner. Each slice has a clear Done criterion.
No slice may be marked done until Done criterion is met AND tier0 passes.

### 2.1 Nix/Switchboard Slice — Owner: Claude (orchestrator)

These changes all live in `nix/modules/services/switchboard.nix`. They require
`nixos-rebuild switch` after commit. Claude owns the Nix layer.

| ID | Priority | Bug ref | Change | Done when |
|----|----------|---------|--------|-----------|
| N-1 | **P0** | §15.1 | Add `coordinator-internal` profile: `injectHints=false`, `forceProvider=local`, no profile card, no loop detect | Profile appears in catalog; coordinator-tagged calls skip hints |
| N-2 | **P1** | §15.2/§16 | Force `stream=True` for ALL local profiles (add `continue-local`, `embedded-assist`, `local-tool-calling` to the forced-streaming list at line 1842–1850) | continue-local streams; no 90s blank screen |
| N-3 | **P1** | §16.A | Increase `HINTS_TIMEOUT_S` default from 1.5→3.0; add 1 retry (sleep 0.5s); set `X-AI-Hints-Skipped: timeout` response header on failure | Hints survive coordinator 2s latency spike |
| N-4 | **P1** | §14.1 BUG-2 | Fix hint injection position: inject hints as FIRST system message, not appended to last | Hints always appear at head of system section |
| N-5 | P2 | §15.3 | Set `X-AI-Fallback: budget-exceeded` response header when remote budget triggers local downgrade | Header present in response when fallback activates |
| N-6 | P2 | §16.B | Set `X-AI-Model-Alias: <actual_model>` response header when model alias rewrite occurs | Header present; client can detect rewrite |
| N-7 | P2 | §16.C | After 2+ consecutive loop guard triggers on same conversation, return HTTP 503 `{"error":"loop_detected"}` instead of forwarding | 503 returned after 2 loop flags; not on first |

### 2.2 Coordinator Python Slice — Owner: Codex

These changes live in the coordinator Python files. They require `nixos-rebuild switch`.

| ID | Priority | Bug ref | Change | Done when |
|----|----------|---------|--------|-----------|
| C-1 | **P0** | §15.1 | Inject `X-AI-Profile: coordinator-internal` header at outbound switchboard POST in `core/llm_client.py:460-473` ONLY | Coordinator-originated calls never trigger circular hints fetch |
| C-2 | **P1** | §13 | Fix `_probe_remote_fallback()` in `ai-stack/local-agents/agent_executor.py`: 401/403/404 must be treated as unhealthy (not healthy) | Probe returns unhealthy for auth failures |
| C-3 | **P1** | §13 | Fix hardcoded `127.0.0.1:*` endpoints in `ai-stack/local-agents/agent_executor.py` — replace with env var reads | No bare `127.0.0.1` strings remain in file |
| C-4 | P2 | §13 | Fix `can (you|i|we)` regex in `ai-stack/local-orchestrator/router.py:97–108`: implementation requests must NOT route as QUERY | `"can you implement X"` → IMPLEMENTATION category |
| C-5 | P2 | §9 | Thin adapter in `ai-stack/local-orchestrator/router.py`: emit canonical `RoutingDecision` from `routing_contract.py`; preserve `AgentBackend` as compatibility shim while callers migrate | Callers receive `RoutingDecision`; old enum still importable |
| C-6 | P2 | §9 | Staged retirement of `ai-stack/local-agents/task_router.py`: update callers (self_improvement.py, __init__.py) to use `routing_contract.RoutingDecision`; then delete | All callers migrated; file removed |

### 2.3 Module Audit Slice — Owner: Gemini

Read-and-report first, then targeted deletions/merges. Gemini confirms findings
before Claude executes the delete/merge.

| ID | Priority | Bug ref | Change | Done when |
|----|----------|---------|--------|-----------|
| G-1 | P2 | §9/§10.7 | Grep all callers of `garbage_collection.py` AND `garbage_collector.py`; identify which is dead; produce deletion/merge recommendation | Report delivered with file:line caller list |
| G-2 | P2 | §9 | Grep all callers of `continuous_learning.py` AND `real_time_learning_engine.py`; identify symbol overlap; produce merge/deprecate plan | Report with symbol map and recommended canonical |
| G-3 | P2 | §9 | Review Codex's C-5/C-6 thin adapter code for routing_contract.py conformance before merge | Approval comment in PRD/delegation output |
| G-4 | P3 | §14.3 | Audit all docs for "hybrid coordinator" misnomer usage; list occurrences; propose replacement phrasing ("orchestration brain" or shorter) | Occurrence list + recommendation delivered |

### 2.4 Docs + Prep Slice — Owner: Qwen (local, aq-agent-loop)

Documentation updates and structural prep that do not require nixos-rebuild.

| ID | Priority | Bug ref | Change | Done when |
|----|----------|---------|--------|-----------|
| Q-1 | P3 | §16.D | Add note to `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`: compact guidance contract (`[compact-guidance]`) applies to `continue-local` and `embedded-assist` only — not `local-agent` | Note present in correct section |
| Q-2 | P3 | §14.1 | Add stale-hints trade-off note to `docs/architecture/REQUEST-ROUTING-FLOW.md` under Profile Behavior: hints locked to first user message for KV cache locality | Note present |
| Q-3 | P3 | §14.1 | Add forceProvider=null resolution note to REQUEST-ROUTING-FLOW.md profile table: "auto = local when REMOTE_URL unset (out-of-the-box default)" | Note in profile table |
| Q-4 | P4 | §9 | Produce Phase B.2 file map: list all 121 coordinator Python files with their proposed subdir (core/workflow/knowledge/extensions/tests) | `PHASE-B2-FILEMAP.md` created in `.agents/plans/` |

---

## Part 3 — Integration Protocol

### 3.1 Execution order

```
Round 1 (parallel, no code interdependencies):
  Gemini: G-1, G-2, G-4 (audit/report only — no code)
  Qwen:   Q-1, Q-2, Q-3 (docs only — no rebuild needed)

Round 2 (after Round 1 complete, parallel):
  Claude: N-1 through N-7 (Nix — needs rebuild)
  Codex:  C-1 through C-4 (Python — needs rebuild)

Round 3 (after Round 2 deployed and tested):
  Gemini: G-3 (review C-5/C-6 adapter)
  Codex:  C-5, C-6 (routing adapter — after G-3 approval)
  Qwen:   Q-4 (Phase B.2 file map)

Round 4 (after G-3 approval):
  Claude: Execute G-1/G-2 deletion/merge based on Gemini recommendations
```

### 3.2 Hand-off protocol
- Each completed slice: agent writes summary to `.agents/delegation/outputs/<agent>-slice-<ID>-done.md`
- Claude reads all summaries before starting Round N+1
- No slice may depend on another's output unless explicitly sequenced above

### 3.3 Rebuild gate
All Nix and Python changes (N-*, C-*) require:
1. `tier0-validation-gate.sh --pre-commit` PASS
2. Commit to main
3. `sudo nixos-rebuild switch` from a terminal session (NOT Claude shell — sudo setuid missing)
4. `aq-qa 0` 61/61 pass after rebuild
5. Smoke-test the specific fix endpoint/behavior

---

## Part 4 — Agent Review Section (to be filled by each agent)

Each agent must add their section confirming they have read the contract,
flagging any concerns, and confirming their slice assignments.

### 4.1 Claude (Orchestrator) — CONFIRMED
- Owns N-1 through N-7 (Nix/Switchboard)
- Owns integration gating, tier0, final commits
- Concern: N-1 requires careful profile card wiring — new profile must not
  accidentally receive hints or loop detection
- Note: nixos-rebuild must be run from terminal, not Claude shell

### 4.2 Gemini — CONFIRMED (2026-05-15)
- **Slice Assignments:** Confirmed G-1, G-2, G-4 (Round 1) and G-3 (Round 3)
- **Role:** Audit, risk identification, conformance review — aligns with senior architecture critique in §14 of PRD
- **Concerns:**
  - G-1/G-2 (dead code): "dead" status may be obscured by shell script calls or dynamic endpoints; report will categorize as `CONFIRMED_DEAD` vs `POTENTIALLY_REACHABLE`
  - G-3 (review): requires Codex to publish C-5/C-6 adapter output to `.agents/delegation/outputs/` before formal approval can be issued
- **Constraints:**
  - Will use sub-agent for high-volume G-1/G-2 audits to keep main session lean
  - Strictly adheres to `X-AI-` header namespace and `RoutingTier` taxonomy in all recommendations
- **Q3 answer:** Report only — destructive ops (git rm) consolidated under Claude for single point of accountability; Gemini delivers "Ready-to-Execute" report with exact commands
- **Q4 answer:** Document only — no `SWB_HINTS_MODE` toggle; stale hints behavior is a deliberate KV cache optimization; document as "intended architectural priority" in REQUEST-ROUTING-FLOW.md

### 4.3 Codex — CONFIRMED (2026-05-15)
- Owns **C-1 through C-6**, all compatible with Part 1 standards
- C-1 uses existing `X-AI-*` namespace; C-2/C-3 are Python hygiene; C-4–C-6 converge onto routing_contract.py
- New code will be typed, async-safe, httpx-only, no hardcoded URLs, no vendor routing names

**Exact files per slice (corrected from draft):**

| Slice | Files |
|-------|-------|
| C-1 | `ai-stack/mcp-servers/hybrid-coordinator/core/llm_client.py:460-473`; `tests/test_llm_client.py` |
| C-2 | `ai-stack/local-agents/agent_executor.py`; `ai-stack/local-agents/test_agent_executor.py` |
| C-3 | `ai-stack/local-agents/agent_executor.py`; `ai-stack/local-agents/test_agent_executor.py` |
| C-4 | `ai-stack/local-orchestrator/router.py`; add `test_router.py` regression coverage |
| C-5 | `ai-stack/local-orchestrator/router.py`, `orchestrator.py`, `__init__.py`, `test_router.py` |
| C-6 | `ai-stack/local-agents/task_router.py`, `__init__.py`, `self_improvement.py`, `scripts/testing/test-local-agent-offline-resilience.py` |

**Concerns / corrections:**
1. Root `llm_client.py` and `llm_router.py` are shim re-exports only; live implementations are `core/llm_client.py` and `knowledge/llm_router.py`
2. C-1: inject `X-AI-Profile: coordinator-internal` ONLY at `core/llm_client.py:460-473` (coordinator → switchboard path), NOT at every local profile use
3. C-5: router.py has live runtime callers — thin compatibility adapter required, not deletion
4. C-6: task_router.py has live source imports (self_improvement.py:27) — staged retirement, not immediate deletion

**Q2 answer:** `local-orchestrator/router.py` is live. Active callers: `orchestrator.py:21,78,117`, `__init__.py:10`. **Adapt with thin adapter.**
**Q5 answer:** Forcing `stream=True` does not materially hurt KV cache. Cache reuse is driven by prompt-prefix stability, not HTTP transport. N-2 fix is acceptable.

### 4.4 Qwen (local) — PENDING REVIEW
*(Qwen to fill in: confirm Q-1 through Q-4, flag any doc structure issues)*

---

## Part 5 — Open Questions (resolve before Round 1)

1. **N-1 profile name:** ~~RESOLVED~~ — **`coordinator-internal`**. Clear, self-documenting
   (tells callers and log readers who set it), consistent with `coordinator-*` naming
   used elsewhere. Short enough for headers and logs.

2. **C-5 adapter scope:** ~~RESOLVED~~ — Live callers confirmed: `orchestrator.py:21,78,117`
   and `__init__.py:10`. **Adapt** with thin compatibility shim, do NOT delete.

3. **G-1/G-2 delete authority:** ~~RESOLVED~~ — Gemini report-only; Claude
   executes `git rm` after reviewing "Ready-to-Execute" report. Single
   committer on destructive ops.

4. **§14.1 BUG-1 stale hints:** ~~RESOLVED~~ — Document only. No
   `SWB_HINTS_MODE` toggle. Stale hints = intentional KV cache optimization.
   Document in REQUEST-ROUTING-FLOW.md as "intended architectural priority."

5. **Streaming (N-2) and KV cache:** ~~RESOLVED~~ — Acceptable. `stream=True` only
   changes HTTP transport, not prompt prefix or slot selection in llama.cpp.
   Cache reuse is driven by prompt stability, not streaming. N-2 fix approved.
