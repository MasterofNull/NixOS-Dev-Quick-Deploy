---
title: "Phase 173: Training Pipeline Review — Consolidated Implementation Plan"
phase: "Phase 6 — Consolidated Plan"
status: active
date: 2026-06-17
slices: ["173-A", "173-B", "173-E"]
agents:
  - "claude-sonnet-4-6 (173-A owner)"
  - "gemini-2.5-pro (173-B + 173-E owner)"
---

# Phase 173 — Consolidated Implementation Plan

## Scope Summary

| Slice | Owner | File | Changes |
|-------|-------|------|---------|
| 173-A | Claude | `ai-stack/local-agents/training_ingest.py` | tool_result ingestion + PII scrub |
| 173-B | Gemini | `ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py` | RAGAS gate + checkpoint tuning |
| 173-E | Gemini | `dashboard/backend/api/routes/aistack.py`, `scripts/testing/harness_qa/phases/phase0.py`, `dashboard.html`, `assets/dashboard.js` | Training health API + aq-qa checks + dashboard card |

---

## Slice 173-A — training_ingest.py (Claude owner)

### Critical Correction: scrub_telemetry_payload vs redact_secrets

The consolidated PRD erroneously specified `scrub_telemetry_payload`. This function SHA256-hashes
the entire response field (destroying training signal). The correct function for training data is
`redact_secrets(text: str) -> Tuple[str, List[str]]`, which strips actual secrets (API keys, JWT,
Bearer tokens, RSA keys) while preserving content. This correction is binding on 173-A.

### Change 1 — Import + `_scrub_text` helper (~line 36)

```python
try:
    _SHARED_PATH = str(_SCRIPT_DIR.parent / "mcp-servers")
    if _SHARED_PATH not in sys.path:
        sys.path.insert(0, _SHARED_PATH)
    from shared.telemetry_privacy import redact_secrets as _redact_secrets

    def _scrub_text(text: str) -> str:
        cleaned, _ = _redact_secrets(text)
        return cleaned
except ImportError:
    def _scrub_text(text: str) -> str:  # type: ignore[misc]
        return text
```

### Change 2 — `_STRUCTURED_MARKERS` (line 123)

Add two markers for short successful tool return JSON:
```python
'{"success": true',   # short tool result JSON (success path)
'{"result":',         # tool result JSON wrapper
```

### Change 3 — `_is_useful_hybrid_event()` (lines 164-175)

Add `"tool_result"` to accepted types + explicit success guard:
```python
if etype not in ("inference_complete", "chat_completion", "hybrid_completion",
                 "local_inference", "agent_step_complete", "tool_result"):
    return False
if etype == "tool_result" and not event.get("success", False):
    return False
```

**Note:** MIN_LATENCY_MS=500 will over-filter most tool_result events (tools complete in <500ms).
Deferred to Phase 174 — track tool_result_samples count for 24h before adjusting.

### Change 4 — Scrub + floor in `_ingest_hybrid_events()` (~line 279)

After response/query extraction, before quality scoring:
```python
# PII guard: strip secrets from content before scoring or writing.
response = _scrub_text(response)
query = _scrub_text(query)

score = _quality_score(response, query)
etype = event.get("event_type")
if etype == "agent_step_complete":
    floor = 0.40
elif etype == "tool_result":
    floor = 0.35  # tool_result success is binary — lower score floor acceptable
else:
    floor = self.min_quality
```

### Change 5 — `source` field (~line 300)

```python
"source": event.get("event_type", "hybrid-events"),
```

This is mandatory for 173-E's `tool_result_samples` count (integration contract note 1).

### Validation Sequence (173-A)

1. `python3 -m py_compile ai-stack/local-agents/training_ingest.py`
2. `python3 training_ingest.py --dry-run --hours 24`
3. `python3 -c "from training_ingest import _is_useful_hybrid_event; print(_is_useful_hybrid_event({'event_type':'tool_result','success':True,'latency_ms':600}))"`  → True
4. `grep '"source": "tool_result"' /var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl | wc -l`  → must be > 0 after live run
5. `grep -i "password\|api_key\|bearer\|sk-" /var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl`  → 0 matches

---

## Slice 173-B — continuous_learning.py (Gemini owner)

### Change 1 — RAGAS_MIN_SAMPLES constant (~line 50)

```python
RAGAS_MIN_SAMPLES = 20
```

### Change 2 — PRELIMINARY status gate in `generate_optimization_proposals` (~line 1300)

```python
if sample_count < RAGAS_MIN_SAMPLES:
    proposal.status = "PRELIMINARY"
```

### Change 3 — Reduce checkpoint_interval (line 292)

```python
self.checkpoint_interval = 50  # was 100
```

### Open Questions Resolved (Gemini)

- **FinetuningExample output path**: ACTIVE — used in `_save_finetuning_examples` (~line 1180)
- **Fine-tuning trigger threshold**: HARDCODED at 1000 in `should_trigger_finetuning` (~line 1459)

### Validation Sequence (173-B)

1. `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py`
2. Confirm RAGAS status field in coordinator health response reflects PRELIMINARY when sample_count < 20

---

## Slice 173-E — Health API + aq-qa + Dashboard (Gemini owner)

### Change 1 — GET /api/aistack/training/health route

**File:** `dashboard/backend/api/routes/aistack.py`

Extend `get_training_dataset_health` (or add new route) to return the full schema from the
integration contract. Implementation notes (binding — from 173-A--173-E.md):

1. `tool_result_samples` — count lines in `dataset.jsonl` where `source == "tool_result"` (grep/wc).
2. `last_ingest_ts` — max timestamp from dataset.jsonl content, NOT filesystem mtime.
3. `ragas_sample_count` + `ragas_status` — sourced from coordinator `/eval/trend` endpoint
   (managed by `eval_runner.py`); do NOT hardcode.
4. `rejection_rate_24h` — estimate from dataset growth rate vs telemetry volume, or dry-run output.

**Full schema:**
```json
{
  "dataset_size": 1250,
  "ingest_rate_24h": 42.5,
  "rejection_rate_24h": 12.3,
  "ragas_sample_count": 25,
  "ragas_status": "OK",
  "last_ingest_ts": "2026-06-17T14:30:00Z",
  "tool_result_samples": 840
}
```

### Change 2 — aq-qa checks 0.13.1-0.13.4

**File:** `scripts/testing/harness_qa/phases/phase0.py`

- **0.13.1**: Training telemetry path writable (check `/var/lib/ai-stack/hybrid/` is writable)
- **0.13.2**: Dataset file exists and is non-empty (`dataset.jsonl` line count > 0)
- **0.13.3**: RAGAS score non-zero (coordinator health returns ragas_sample_count > 0 or PRELIMINARY)
- **0.13.4**: tool_result_samples > 0 in dataset.jsonl (depends on 173-A being deployed)

### Change 3 — Training Pipeline dashboard card

**Files:** `dashboard.html` (card structure), `assets/dashboard.js` (data fetch + render)

New `.card` in Operations panel, polling `/api/aistack/training/health`:
- dataset_size, ingest_rate_24h, rejection_rate_24h
- ragas_status badge (OK/PRELIMINARY/INSUFFICIENT)
- last_ingest_ts, tool_result_samples

### Validation Sequence (173-E)

1. `curl http://localhost:8889/api/aistack/training/health | python3 -m json.tool` — all 7 fields present
2. `aq-qa --phase 0` — checks 0.13.1-0.13.4 pass
3. Dashboard Training Pipeline card renders live data (no `--` blanks)

---

## Inter-Slice Dependency Table

| Dependency | Consumer | Provider | Blocking? |
|-----------|----------|----------|-----------|
| `tool_result` source field in dataset.jsonl | 173-E: aq-qa 0.13.4, tool_result_samples count | 173-A deployed | 173-E aq-qa 0.13.4 blocked until 173-A live |
| coordinator RAGAS data (`/eval/trend`) | 173-E: ragas_* health fields | 173-B deployed | 173-E API can expose INSUFFICIENT if 173-B not live |
| `_scrub_text` availability | 173-A: PII guard | shared/telemetry_privacy.py (exists) | 173-A has ImportError fallback (no-op) |
| F1 + F2 must land same commit | 173-A integrity | — | Non-negotiable per consolidated PRD |

**Critical ordering:** 173-A and 173-B can be implemented in parallel. 173-E check 0.13.4 requires
173-A deployed. To unblock 173-E testing, commit 173-A first, restart training_ingest, run 1h
ingest before running aq-qa.

---

## Phase 7 Dispatch Plan

| Slice | Agent | Mode | Expected output |
|-------|-------|------|----------------|
| 173-A | Claude (direct) | inline edit | training_ingest.py patched |
| 173-B | Gemini | implementer | continuous_learning.py patched |
| 173-E | Gemini | implementer | aistack.py route + phase0.py checks + dashboard card |

Commit strategy: two commits
1. `feat(training): Phase 173-A — tool_result ingestion + PII scrub guard (training_ingest.py)`
2. `feat(training): Phase 173-B/E — RAGAS gate, checkpoint tuning, health API, aq-qa, dashboard card`

---

## Risk Register

| Risk | Slice | Severity | Mitigation |
|------|-------|----------|-----------|
| MIN_LATENCY_MS=500 over-filters tool_result | 173-A | Medium | Defer to Phase 174; check sample count after 24h |
| `_scrub_text` ImportError fallback is silent | 173-A | Low | Acceptable for standalone CLI; add dry-run warning |
| RAGAS coordinator endpoint unreachable | 173-E | Medium | Return `ragas_status: "INSUFFICIENT"` gracefully |
| 173-E aq-qa 0.13.4 fails until 173-A is live | Integration | Low | Expected — check passes after 173-A deploy |

---

*Consolidated by Claude Sonnet 4.6 (Orchestrator)*
*Phase 6 of Flat Collaborative Design Protocol*
*Plans from: claude (173-A), gemini (173-B+173-E). Qwen3 plan not received (task lost in context compaction — both owner slices have complete plans).*
*Date: 2026-06-17*
