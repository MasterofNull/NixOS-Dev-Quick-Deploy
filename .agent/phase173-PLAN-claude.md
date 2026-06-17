---
title: "Phase 173: Training Pipeline Review — Claude Implementation Plan (Slice 173-A)"
agent: claude-sonnet-4-6
expert_roles: ["Data Pipeline Architect", "MLOps Systems Engineer"]
phase: "Phase 5 — Independent Plan Draft"
slice: "173-A"
date: 2026-06-17
status: draft
---

# Phase 173 — Slice 173-A Implementation Plan

## Scope

File: `ai-stack/local-agents/training_ingest.py`

Six discrete changes, all non-architectural (no new classes, no refactors):
1. Add `redact_secrets` import (PII guard — REQUIRED before tool_result expansion)
2. Add `tool_result` to `_is_useful_hybrid_event()` accepted types
3. Add `success == True` guard for `tool_result` events
4. Add `'{"success": true'` and `'{"result":'` to `_STRUCTURED_MARKERS`
5. Add PII scrub call in `_ingest_hybrid_events()` before quality scoring
6. Add `tool_result` floor (0.35) in floor selection logic

## Critical Correction: scrub_telemetry_payload vs redact_secrets

The consolidated PRD says "must call `scrub_telemetry_payload`". This is WRONG for training data.

`scrub_telemetry_payload(value, parent_key="response")` hashes the entire response to
`sha256:HASH` — it's designed for telemetry STORAGE where content must be opaque.
Training data must preserve content while only stripping actual secrets (API keys, tokens).

**Correct function: `redact_secrets(text: str) -> Tuple[str, List[str]]`**
- Scans for secret patterns (API keys, JWT tokens, Bearer tokens, RSA private keys, etc.)
- Returns `(cleaned_text, detected_types)` — text with secrets replaced, content preserved
- Does NOT hash or obscure normal text

This is a plan-level correction that must be surfaced in Phase 6 consolidation.

---

## Change 1 — Import setup (line ~36, after `_REPO_ROOT` declaration)

**File:** `ai-stack/local-agents/training_ingest.py`
**After:** `_REPO_ROOT = ...` block (line ~36)

```python
# PII guard: scan response/query text for secrets before quality scoring.
# Uses redact_secrets (not scrub_telemetry_payload — see plan for reasoning).
try:
    _SHARED_PATH = str(_SCRIPT_DIR.parent / "mcp-servers")
    if _SHARED_PATH not in sys.path:
        sys.path.insert(0, _SHARED_PATH)
    from shared.telemetry_privacy import redact_secrets as _redact_secrets  # noqa: E402

    def _scrub_text(text: str) -> str:
        cleaned, _ = _redact_secrets(text)
        return cleaned
except ImportError:
    def _scrub_text(text: str) -> str:  # type: ignore[misc]
        return text
```

**Validation:** `python3 -c "from shared.telemetry_privacy import redact_secrets"` from
`ai-stack/mcp-servers/` confirms the module is reachable.

---

## Change 2 — `_STRUCTURED_MARKERS` (line 123)

**Current (line 123-128):**
```python
_STRUCTURED_MARKERS = (
    "```", "def ", "class ", "import ", "return ", "function ",
    "## ", "### ", "1. ", "2. ", "- [", "* ", "| ",
    '"function"', '"arguments"',
    "COMPLETED:",
)
```

**Change:** Add two markers for short successful tool return JSON:
```python
_STRUCTURED_MARKERS = (
    "```", "def ", "class ", "import ", "return ", "function ",
    "## ", "### ", "1. ", "2. ", "- [", "* ", "| ",
    '"function"', '"arguments"',
    "COMPLETED:",
    '{"success": true',   # short tool result JSON (success path)
    '{"result":',         # tool result JSON wrapper
)
```

**Validation:** `python3 -c "from training_ingest import _STRUCTURED_MARKERS; print(len(_STRUCTURED_MARKERS))"` should print 17.

---

## Change 3 — `_is_useful_hybrid_event()` (lines 164-175)

**Current (line 164-175):**
```python
def _is_useful_hybrid_event(event: Dict) -> bool:
    """Return True for events that represent a completed successful inference."""
    etype = event.get("event_type", "")
    if etype not in ("inference_complete", "chat_completion", "hybrid_completion",
                     "local_inference", "agent_step_complete"):
        return False
    if event.get("error") or event.get("success") is False:
        return False
    latency = event.get("latency_ms", 0.0)
    if latency < MIN_LATENCY_MS:
        return False
    return True
```

**Change:** Add `"tool_result"` to accepted types; add explicit success guard for tool_result
(tool_result events use `success` field to signal outcome, unlike inference events):
```python
def _is_useful_hybrid_event(event: Dict) -> bool:
    """Return True for events that represent a completed successful inference."""
    etype = event.get("event_type", "")
    if etype not in ("inference_complete", "chat_completion", "hybrid_completion",
                     "local_inference", "agent_step_complete", "tool_result"):
        return False
    # tool_result events must explicitly succeed; other events use absence-of-error signal.
    if etype == "tool_result" and not event.get("success", False):
        return False
    if event.get("error") or event.get("success") is False:
        return False
    latency = event.get("latency_ms", 0.0)
    if latency < MIN_LATENCY_MS:
        return False
    return True
```

**Note on latency gate:** `MIN_LATENCY_MS = 500` will filter most tool_result events (tool
executions typically complete in <500ms). The latency gate may need to be bypassed for
tool_result type specifically — leave as-is for Phase 173, track as Phase 174 candidate
once we see actual tool_result sample count in the dataset.

**Validation:** `python3 -c "from training_ingest import _is_useful_hybrid_event; print(_is_useful_hybrid_event({'event_type':'tool_result','success':True,'latency_ms':600}))"` should print True.

---

## Change 4 — Scrub call + floor selection in `_ingest_hybrid_events()` (line ~279-285)

**Current (lines ~269-285):**
```python
            query = (
                event.get("query") or event.get("prompt") or
                event.get("task") or event.get("input", "")
            )
            response = (
                event.get("response") or event.get("output") or
                event.get("result") or event.get("content", "")
            )
            if not query or not response:
                continue
            if _token_count(response) < MIN_RESPONSE_TOKENS:
                continue

            score = _quality_score(response, query)
            floor = 0.40 if event.get("event_type") == "agent_step_complete" else self.min_quality
            if score < floor:
                continue
```

**Change:** Add scrub calls after extraction, before quality scoring; add tool_result floor:
```python
            query = (
                event.get("query") or event.get("prompt") or
                event.get("task") or event.get("input", "")
            )
            response = (
                event.get("response") or event.get("output") or
                event.get("result") or event.get("content", "")
            )
            if not query or not response:
                continue
            if _token_count(response) < MIN_RESPONSE_TOKENS:
                continue

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
            if score < floor:
                continue
```

**Validation:** `python3 training_ingest.py --dry-run --hours 1 --json` should complete
without ImportError. `grep '"source": "tool_result"' dataset.jsonl | wc -l` > 0 after
a full run against live telemetry.

---

## Change 5 — Sample `source` field for tool_result tracking (line ~292-307)

In the sample dict construction, the `"source"` field is hardcoded to `"hybrid-events"`.
Update to use the actual event_type for tool_result samples so aq-qa check 0.13.4 can
count them:

**Current (line ~300):**
```python
            sample = {
                "messages": [...],
                "source": "hybrid-events",
```

**Change:**
```python
            sample = {
                "messages": [...],
                "source": event.get("event_type", "hybrid-events"),
```

**Validation:** `grep '"source": "tool_result"' /var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl | wc -l`
must be > 0 after a full ingest run with live tool_result events in the telemetry file.

---

## Integration Contract (173-A ↔ 173-E)

173-A adds `tool_result_samples` counting to the ingest pipeline. 173-E's health endpoint
needs this count. The contract proposed in `.agent/collaboration/integration-contracts/173-A--173-E.md`
is acceptable. My AGREED conditions:

1. `tool_result_samples` counts rows where `source == "tool_result"` in dataset.jsonl —
   this is a `grep | wc -l` from the backend route; no coordinator API call needed.
2. `last_ingest_ts` should be the `max(timestamp)` of processed events, NOT a filesystem
   mtime (mtime changes on any write, not just training_ingest runs).
3. `ragas_sample_count` and `ragas_status` fields must be sourced from continuous_learning.py
   (173-B's domain) — the backend route must call the coordinator or read a shared state file.

**AGREED** — pending 173-B owner confirming data source for `ragas_sample_count`.

---

## Dependency Table

| 173-A task | Depends on | Type |
|-----------|-----------|------|
| scrub call (Change 4) | `shared/telemetry_privacy.py` exists and is importable | Runtime |
| tool_result floor (Change 4) | Change 3 (event type expansion) | Same-file ordering |
| `source` field (Change 5) | Change 3 (tool_result events admitted) | Same-file ordering |
| 173-E health endpoint | 173-A deployed + emitting tool_result source field | Integration |
| 173-E aq-qa 0.13.4 | 173-A deployed + dataset has tool_result entries | Integration |

## Validation Sequence

1. `python3 -m py_compile ai-stack/local-agents/training_ingest.py` — no syntax errors
2. `python3 training_ingest.py --dry-run --hours 24` — completes, no ImportError
3. `python3 training_ingest.py --hours 24 --json | jq .positive_samples_added` — number increases vs baseline
4. `grep '"source": "tool_result"' /var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl | wc -l` > 0
5. `grep -i "password\|api_key\|bearer\|sk-" /var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl` — zero matches

## Risks

- **Latency gate may over-filter tool_result**: `MIN_LATENCY_MS = 500` was set for cached response detection. Tool executions complete in <500ms by design. If `tool_result_samples` stays 0 after fix, reduce MIN_LATENCY_MS for tool_result events specifically (Phase 174 candidate).
- **`redact_secrets` scan overhead**: each response/query string scanned with 14 regex patterns. At 312 samples → negligible. At 10k+ events → benchmark before declaring acceptable.
- **`_scrub_text` fallback is silent**: if shared import fails, scrubbing is silently skipped. This is acceptable for the standalone CLI path (no coordinator dependency) but must be visible in the dry-run report.

---
*Drafted by Claude Sonnet 4.6 (Data Pipeline Architect + MLOps Systems Engineer)*
*Phase 5 of Flat Collaborative Design Protocol — no cross-agent visibility during drafting*
*Date: 2026-06-17*
