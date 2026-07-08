#!/usr/bin/env python3
"""P1.3 — correction step: turn PENDING local failures into repair pairs via a remote teacher.

The closed-loop's learning step. P1.1/P1.2 capture local failures and ingest the ones that already have
a corrected_output; failures WITHOUT a correction sit as `pending`. Here a remote agent (codex/claude —
the "teacher" in the local-first-improve-via-remote model) is asked for the CORRECT output for each
pending case; the correction is written back as a new failure_sample WITH corrected_output, which
training_ingest (P1.2) then turns into an SFT repair pair. This is what makes the harness IMPROVE local
from its failures, not merely record them.

This module is PURE (prompt construction + record shaping + selection). The actual remote call + file
I/O live in the driver (scripts/ai/aq-correct-failures) so the logic is unit-testable without a lane.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional


def is_pending(record: dict) -> bool:
    """A capture that still needs a correction: a failure_sample with no usable corrected_output."""
    return record.get("kind") == "failure_sample" and not record.get("corrected_output")


def build_correction_prompt(record: dict) -> str:
    """Prompt asking the remote teacher for the CORRECT output the local model should have produced.
    Deterministic (no timestamps) so identical failures produce identical prompts (cache-friendly)."""
    prompt = record.get("prompt", "")
    tools = record.get("tools_available") or []
    bad = record.get("bad_output", "")
    fclass = record.get("failure_class", "unknown")
    tool_line = ", ".join(tools) if tools else "(none)"
    return (
        "You are the TEACHER for a smaller local model that FAILED a task. Produce ONLY the single "
        "correct output it should have emitted — no explanation, no preamble, no markdown fences.\n\n"
        f"TASK PROMPT:\n{prompt}\n\n"
        f"AVAILABLE TOOLS: {tool_line}\n\n"
        f"WHAT THE LOCAL MODEL PRODUCED (WRONG — failure_class={fclass}):\n{bad}\n\n"
        "Output the CORRECT response. If a tool call was required, emit ONLY the valid JSON tool-call "
        'envelope {\"function\": \"<one of the available tools>\", \"arguments\": {...}} — no other text. '
        "If a final answer was required, emit just that answer. Output nothing else."
    )


def _looks_valid(corrected: str, record: dict) -> bool:
    """Reject empty / obviously-non-correction teacher output. For tool-call failure classes, require a
    parseable JSON object naming an available tool; otherwise accept non-empty text."""
    if not corrected or not corrected.strip():
        return False
    fclass = record.get("failure_class", "")
    if fclass in ("text_as_tool_call", "invalid_tool_json", "truncated", "parse_failed"):
        try:
            obj = json.loads(corrected.strip())
        except Exception:  # noqa: BLE001
            return False
        if not (isinstance(obj, dict) and "function" in obj and "arguments" in obj):
            return False
        tools = record.get("tools_available") or []
        if tools and obj.get("function") not in tools:
            return False
    return True


def corrected_record(record: dict, corrected_output: str) -> Optional[dict]:
    """Shape a new failure_sample with corrected_output filled (ingestable as a repair pair), or None if
    the teacher's correction fails validation. Carries provenance of the correction."""
    if not _looks_valid(corrected_output, record):
        return None
    out = dict(record)
    out["corrected_output"] = corrected_output.strip()
    out["kind"] = "failure_sample"
    out["corrected_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["correction_source"] = "remote-teacher"
    return out
