# Architecture Revamp — Implementation Contract
**Status:** DRAFT — Awaiting agent review and sign-off
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
| C-1 | **P0** | §15.1 | In coordinator outbound switchboard calls (find in `llm_client.py` or `llm_router.py`), inject `X-AI-Profile: coordinator-internal` header | Coordinator calls never trigger circular hints fetch |
| C-2 | **P1** | §13 | Fix `_probe_remote_fallback()` in `agent_executor.py:654–663`: 401/403/404 must be treated as unhealthy (not healthy) | Probe returns unhealthy for auth failures |
| C-3 | **P1** | §13 | Fix hardcoded endpoints in `agent_executor.py:201–207` — replace with env var reads | No bare `127.0.0.1` strings in file |
| C-4 | P2 | §13 | Fix `can (you|i|we)` regex misclassification in `router.py:97–108`: implementation requests should NOT route as QUERY | `"can you implement X"` → IMPLEMENTATION tier |
| C-5 | P2 | §9 | Create thin adapter in `ai-stack/local-orchestrator/router.py`: replace `AgentBackend.*` enum with `RoutingDecision` from `routing_contract.py` | Old enum gone; callers receive `RoutingDecision` |
| C-6 | P2 | §9 | Retire `ai-stack/local-agents/task_router.py`: verify zero callers then delete OR convert to `RoutingDecision` emitter if called | File deleted or emits `RoutingDecision` only |

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

### 4.2 Gemini — PENDING REVIEW
*(Gemini to fill in: confirm slice assignments, flag concerns, add constraints)*

### 4.3 Codex — PENDING REVIEW
*(Codex to fill in: confirm slice assignments, flag any API surface concerns,
note which files will be touched)*

### 4.4 Qwen (local) — PENDING REVIEW
*(Qwen to fill in: confirm Q-1 through Q-4, flag any doc structure issues)*

---

## Part 5 — Open Questions (resolve before Round 1)

1. **N-1 profile name:** `coordinator-internal` vs `internal` vs `local-nocard`?
   Should be short, clear, and not break existing profile validation.

2. **C-5 adapter scope:** Does `local-orchestrator/router.py` have any live
   callers in the running service? If zero, should we delete it entirely rather
   than write an adapter?

3. **G-1/G-2 delete authority:** Gemini audit produces recommendation; Claude
   executes delete. Is Gemini authorized to write the delete directly, or
   report only? (Recommend: report only, Claude executes to maintain single
   committer on destructive ops.)

4. **§14.1 BUG-1 stale hints:** Document the trade-off only (N-4-adjacent) or
   also add a `SWB_HINTS_MODE=first|latest` toggle? Toggling busts KV cache
   when `latest` — needs explicit opt-in. Current plan: document only.

5. **Streaming (N-2) and KV cache:** Forcing stream=True on continue-local
   eliminates blank-screen UX but may affect KV cache hit rate in llama-server.
   Is this acceptable? (Recommend: yes — UX > marginal cache benefit.)
