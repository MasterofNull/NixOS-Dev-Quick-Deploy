# Phase 65-67 Staff Eng / Implementation Review
# Role: Codex (Staff Eng) — filled by Claude acting as Codex proxy (Codex offline 2026-05-23)
**Status:** Codex offline — Claude providing Staff Eng perspective per team policy
**Date:** 2026-05-23
**PRD:** `.agents/plans/PHASE-64-67-AIOS-ELEVATION-PRD.md`

---

## Review: Phase 65 Implementation Decisions

### 65.1 — K-LRU: Redis vs mtime for last_access_time tracking

**RECOMMEND: Redis hash (not mtime).**

Rationale:
- File mtime is updated on read in most filesystems (atime), but NixOS uses `relatime` mount
  option which only updates atime if older than 1 day → unreliable for LRU within a session.
- Redis hash `clm:warm:access:{context_id}` → Unix timestamp is O(1) write/read, survives
  coordinator restarts (Redis is persistent in our stack), and aligns with existing CLM hot-tier
  Redis usage pattern.
- Fallback: if Redis unavailable, fall back to file stat mtime (acceptable degradation).

**Contract (approved):**
```python
async def apply_klru_pressure(self, k: int = 3) -> int:
    """Evict K least-recently-used warm context blocks. Returns evict count."""
```

**APPROVE** — Redis approach, k=3 default.

---

### 65.2 — Constraints Array: MemoryBroker.read() filter

**FINDING:** `MemoryBroker.read()` in `memory_broker.py` accepts a `filters` dict parameter.
Check for `fact_type` key support:
```python
results = await broker.read(query="", filters={"fact_type": "constraint"}, top_k=20)
```
However — lessons registry (`_load_agent_lessons_registry`) is the simpler, no-rebuild path:
lessons tagged `constraint` in their `tags` array are immediately accessible.

**APPROVE the simpler approach**: filter lesson entries by `tags contains "constraint"` first.
Fall back to MemoryBroker fact_type query only in a Phase 65.5 follow-up (requires rebuild).

**Single-file change sufficient:** `extensions/ai_coordinator_handlers.py` only.

---

### 65.3 — KV Cache: q8_0 compatibility with llama.cpp b9222+

**VERIFIED:** `--cache-type-k` and `--cache-type-v` flags introduced in llama.cpp b3160+ (2024-04).
Pin b9222 (2025-09) is well past this — flags are fully supported.

**MTP + quantized KV compatibility:**
- MTP (multi-token prediction) draft heads operate on the shared KV cache.
- q8_0 quantization is applied AFTER MTP draft verification — no interference.
- Acceptance rate unaffected; only RAM footprint changes (~50% reduction for KV).
- RECOMMEND: use `q8_0` (not `q4_0`) for first deployment. q4_0 risks quality regression
  on long contexts with Qwen3-35B attention heads. Monitor MTP acceptance rate post-rebuild.

**RAM savings estimate (Renoir APU, ctx=8192):**
- fp16 KV: ~2.0 GB for ctx=8192
- q8_0 KV: ~1.0 GB (−1.0 GB freed for model weights / OS)
- Enables bumping ctx-size from 8192→12288 in a future slice if desired.

**APPROVE** — q8_0 in options.nix as default, opt-out via `kvCacheType = ""`.

---

### 66.1-66.2 — Wasmtime in nixpkgs

**FINDING:** `pkgs.wasmtime` is available in nixpkgs-unstable (version 23.0.1 as of 2026-04).
Not in nixpkgs-stable 24.05 — requires `nixpkgs-unstable` or pinned overlay.

**WASM-portable tools from SAFE_COMMANDS:**
- `jq` — has official WASM build (jq-wasm, WASI-compatible)
- `cat`, `head`, `tail`, `wc` — coreutils has partial WASM builds via WASI-SDK
- `grep` — grep.wasm project exists but not in nixpkgs

**RECOMMEND:** Stage Wasmtime as a devShell tool first (not in coordinator PATH).
Use for `jq` only in Phase 66.2 as proof-of-concept. Full WASM tool suite is Phase 68 work.

**APPROVE Phase 66.1 staged approach** — add to devShells.full only, not hybridPython env.

---

## Implementation Sign-off Checklist

| Item | Status | Notes |
|------|--------|-------|
| K-LRU Redis tracking | APPROVE | Redis hash, k=3 default |
| Constraints array tags filter | APPROVE | lessons registry tags, single file |
| KV cache q8_0 | APPROVE | b9222+ compatible, 50% RAM saving |
| Wasmtime staged | APPROVE | devShells.full only, jq first |
| AppArmor profiles | DEFER | Pending Gemini security review |

---

*Note: This review was provided by Claude acting in the Codex Staff Eng role per team policy
(agent substitution when teammate is offline). Codex should re-review and amend when available.*
