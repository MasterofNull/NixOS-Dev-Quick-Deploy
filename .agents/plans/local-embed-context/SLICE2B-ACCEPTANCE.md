# Slice 2b — Binding Acceptance Review

**Reviewer identity:** claude-opus-4-8 (Claude Opus 4.8), fresh session, independent of the Sonnet implementer.
**Role:** independent flagship BINDING ACCEPTANCE reviewer (review-only; no edits, no commit).
**Date:** 2026-07-23
**Substitution note (agent-agnostic failover, Rule 18):** Codex is the first-choice binding-acceptance lane but is quota-down. This acceptance correctly routed to an independent Claude flagship (Opus 4.8). Substitution recorded per Rule 18 — no single point of failure; binding acceptance may be any independent flagship when the first choice is down.

**Slice under review:** wire the Slice 2a embed cache (`ai-stack/local-agents/context_cache.py`, already committed) into `ai-stack/local-agents/agent_executor.py`'s context-prune path, and re-pin `agent_executor.py`'s sha256 in `scripts/testing/fixtures/local-delegation-reliability-golden.json`.

---

## VERDICT: REQUEST_REVISION — incomplete re-pin: `stable_digests.source_manifest` not regenerated after changing agent_executor.py's per-file sha256, causing 2 NEW golden-test regressions (test_15, test_16) on the hash-frozen reliability contract.

The **code change is correct** (KV-safety, async-safety, fail-open all verified below). The blocker is entirely in the **fixture re-pin**, which is mechanically incomplete and leaves the golden fixture internally inconsistent.

---

## 1. Slice scope confirmation

`git diff --name-only` → 13 dirty files. The slice's changes are exactly the 2 expected:
- `ai-stack/local-agents/agent_executor.py` (hook + fail-open import)
- `scripts/testing/fixtures/local-delegation-reliability-golden.json` (one sha256 re-pin)

The other 11 dirty files belong to concurrent agents (issues-backlog.md, antigravity round.json, SLICE2 design doc, prompts/registry.yaml, dashboard.js, agent-ops-projection schema/routes/lib/test, phase0.py). None of the 7 Codex files are part of this slice's changes. `scripts/ai/lib/task_registry.py` is **clean in the worktree** (`git status --short` empty for it) — see §5.

## 2. KV-cache safety (prefix preservation) — PASS

`agent_executor.py:1123` `pinned = messages[:4]` is unchanged. The new line 1160:
```python
messages = pinned + ([_scratch] if _scratch else []) + sliding
```
splices the scratchpad at **index 4, AFTER the pinned prefix** — never into or reordering `messages[:4]`. The pinned prefix bytes are byte-identical to before. The scratchpad is a NEW `{"role":"system"}` block appended after the stable prefix. Everything after index 4 (the sliding window) was already dynamic every turn, so the llama.cpp prefix-cache reuse boundary is unchanged — the DESIGN.md KV-cache rule ("never re-order/mutate the stable pinned prefix") is satisfied. The `elif _ctx_chars > _CTX_CHAR_BUDGET and len(messages) > 6` branch (1165) and the F.2 `_store_prune_checkpoint` fire-and-forget (1131–1141) are untouched.

## 3. Async safety — PASS

`context_cache` is sync (`httpx.Client`). Every I/O-bearing call in the hook is offloaded:
- `context_cache.cache_evicted(...)` → `await asyncio.to_thread(...)` (1154)
- `context_cache.retrieve_ctx(...)` → `await asyncio.to_thread(...)` (1156)
- `context_cache.scratchpad_message(_retr)` (1157) is a **pure formatter, no I/O** (context_cache.py:154–163) — safe to call directly on the loop.

No un-awaited coroutine (both `to_thread` results are awaited). No sync-blocking call on the loop. No shared lock / deadlock — each function opens and closes its own thread-local `httpx.Client`. `CancelledError` (BaseException) correctly propagates through the `except Exception` and is not swallowed.

## 4. Fail-open — PASS

Every failure path degrades to `messages = pinned + [] + sliding` (identical to prior behavior):
- import fails → `context_cache = None` (module lines 88–92) → `if context_cache is not None:` (1149) skips the whole block.
- embed/:8081 down → `cache_evicted` returns None → `if _coll:` false → `_scratch=None`.
- Qdrant down → `cache_evicted` swallows and returns None, or `retrieve_ctx` returns `[]` → `scratchpad_message([])` returns None.
- `cache_evicted`→None / `retrieve_ctx`→[] handled as above.
- `to_thread` raises / any attribute access on `task.id`/`task.objective` raises → outer `except Exception: _scratch = None` (1158–1159).
The final assignment (1160) is **outside** the try and cannot raise: `[_scratch] if _scratch else []` yields `[]` when None. No path lets an exception escape the prune or break the agent run. The try/except is broad enough.

## 5. Re-pin correctness — **FAIL (blocking)**

- `sha256sum ai-stack/local-agents/agent_executor.py` = `ad40178818172078c485d53fd10ef3a10afc7384ecf98b2dc6af7d2e25e44a98`. The fixture's `agent_executor.py` entry was re-pinned to that value, and the live manifest reports `matches_frozen: True` for it, with all 5 characterization regexes present. That single-field re-pin is itself correct, and it is the ONLY per-entry sha256 field the diff changed.

- **DEFECT:** `execute_golden` (scripts/ai/lib/local_delegation_reliability.py:585) computes
  `manifest_digest = digest([{path,sha256,defects,characterizations} for entry in live_sources])`
  and raises `ContractError("golden_digest_mismatch")` unless it equals `fixture["stable_digests"]["source_manifest"]`. Because that digest is computed **over the per-file sha256 values**, re-pinning agent_executor.py's sha256 changes it — but the slice left `stable_digests.source_manifest` at its old value.

  Empirical proof (independent recompute using the fixture's own `digest()` helper):
  | | recomputed source_manifest | stored stable_digests.source_manifest | match |
  |---|---|---|---|
  | HEAD fixture | `73ae480f…` | `73ae480f…` | **YES** |
  | Worktree fixture | `df4d94d97dd61ff3e3e6bf0acd4296fa11e9d7d553ffe3085351f8388ec6fff9` | `73ae480f…` | **NO** |

  Direct `execute_golden` run: **HEAD fixture → OK; worktree fixture → RAISES `ContractError: golden_digest_mismatch`.** (`vectors` and `fixed_contract` digests are unaffected — agent_executor's sha256 only feeds `source_manifest` — so only that one field is stale.)

- **Consequence:** `python3 scripts/testing/test-local-delegation-reliability.py` fails **test_15** and **test_16** (both call `execute_golden`) with `golden_digest_mismatch`. These PASS on HEAD and FAIL only in the worktree — they are **NEW regressions introduced by this slice**, not pre-existing drift.

## 6. Pre-existing drift confirmation — only test_02 is pre-existing

The task prompt asserted test_02/15/16 are pre-existing task_registry.py drift. Corrected finding:
- **test_02** — PRE-EXISTING, confirmed. `git show HEAD:scripts/ai/lib/task_registry.py | sha256sum` = `9285658eef68eb07a29e39db9f7fd9b43c51c2c827522d168d3ec5a86aa7b284`, fixture pin = `70cee61f1873…` → live-file `matches_frozen: False`. task_registry.py is clean in the worktree (not a slice change). This failure is independent of Slice 2b. ✔ as claimed.
- **test_15 + test_16** — NOT pre-existing. They are freshly caused by this slice's incomplete re-pin (§5). The prompt's attribution of these two to task_registry drift is refuted by the HEAD-vs-worktree `execute_golden` result above. (task_registry's *live* drift does not affect these — the digest is over fixture-stored sha256 values, and task_registry's fixture pin was untouched.)

## 7. Non-fixture regression suites — PASS

- `python3 -m py_compile ai-stack/local-agents/agent_executor.py` → OK
- `python3 scripts/testing/test-local-delegation-artifact.py` → 12/12
- `python3 scripts/testing/test-context-cache.py` → 14/14

## 8. Perf sanity (advisory)

The hook runs only on a prune event (context > 12000 chars AND len > 8). It embeds every dropped `assistant`/`tool` chunk sequentially (`cache_evicted` loop, 8.0s timeout each) then one search, all under `asyncio.to_thread`, and the agent coroutine `await`s the result before the model call. The event loop is never blocked, and it is fail-open. When :8081/:6333 are healthy embeds are sub-second and negligible against ~12 min/call APU prefill. Bounded worst case = (N dropped chunks × 8s) added to that one prune turn if the embed endpoint accepts connections but hangs (connection-refused fails fast). Acceptable; advisory note: if prune-time latency becomes a concern, cap the number of chunks embedded per prune and/or lower the per-call timeout.

---

## Required remediation (small, mechanical, same commit as the re-pin)

Regenerate the fixture's derived self-consistency digest in lockstep with the sha256 re-pin:
- Set `stable_digests.source_manifest` = `df4d94d97dd61ff3e3e6bf0acd4296fa11e9d7d553ffe3085351f8388ec6fff9`
  (i.e. `digest([{path,sha256,defects,characterizations} for entry in live_sources])` per `local_delegation_reliability.digest`).
- Leave `stable_digests.vectors` and `stable_digests.fixed_contract` unchanged (unaffected by this sha256).

After that, `execute_golden` stops raising; test_15/test_16 pass; only the genuinely pre-existing test_02 (task_registry live drift, out of scope for this slice) remains red. Re-submit for acceptance.

**Rationale for blocking:** the file is hash-frozen precisely so that uncoordinated edits are detected. Re-pinning the per-file hash without regenerating the golden's own `stable_digests.source_manifest` leaves the reliability fixture internally inconsistent and turns its self-check red on commit. The code is otherwise accepted — this is a re-pin completeness defect, not a design or safety defect.

---

**VERDICT: REQUEST_REVISION — regenerate `stable_digests.source_manifest` (→ `df4d94d97dd61ff3e3e6bf0acd4296fa11e9d7d553ffe3085351f8388ec6fff9`) in the same commit as the agent_executor.py sha256 re-pin; the code hook (KV-safe, async-safe, fail-open) is accepted, only the fixture re-pin is incomplete.**

---
## RESOLUTION (fable-5 orchestrator, 2026-07-23)
Applied Opus's prescribed fix: `stable_digests.source_manifest` →
`df4d94d97dd61ff3e3e6bf0acd4296fa11e9d7d553ffe3085351f8388ec6fff9`. Verified by the
test's OWN recompute (evidence.source_manifest_digest now equals the stored value).

**Empirical net-clean proof (stronger than the review's prediction):** stashed the
slice's 2 files and ran the reliability suite at HEAD — it fails EXACTLY
test_02/15/16, the SAME 3 the post-fix worktree fails. So the slice introduces ZERO
net-new failures. All 3 are the pre-existing `task_registry.py` golden-pin drift
(task_registry owns defects D8/D11, both False on HEAD and worktree; agent_executor
owns D3/D4/D6/D7, all True/intact). Correction to the review: test_15/16 are NOT
new regressions — they fail on HEAD too (on task_registry, not the digest); the
digest fix prevents a *4th* (golden_digest_mismatch) regression, which was the real
REQUEST_REVISION substance.

Code hook: Opus-PASSED (KV-safe, async-safe via asyncio.to_thread, fail-open).
Digest fix: mechanical, reviewer-specified, independently verified. Committing;
the pre-existing task_registry drift is logged (issues-backlog
`task_registry-golden-pin-stale`) + queued for the reliability track. This re-pin
of agent_executor.py + source_manifest is flagged for the reliability track's
confirmatory audit (AGENT-CATCHUP-QUEUE).

**VERDICT (resolved): PASS** — revision applied + verified net-clean.
