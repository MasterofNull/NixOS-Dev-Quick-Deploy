#!/usr/bin/env python3
"""span_projector — Foundation C, C5 pure folds over the closed span taxonomy.

Design: `.agents/plans/aqos-foundation-c/C5-DESIGN-AND-AUTHORIZATION.md` §4, §5.
Generalizes B3's `resume_projector.py` (which folds `resume.update`/
`pulse.append` EVENTS into RESUME.json/PULSE.log) to a richer event source:
the closed-taxonomy SPANS validated by `span_taxonomy.py`. Every projection
here is a PURE FOLD over the span stream — same spans in, byte-identical
projection out (reproducible + idempotent, the B3 property) — and NEVER
decides anything; it only reads spans and writes a derived view.

Shadow-first (§5): while `CAPABILITY_SPAN_TRUTH` is OFF, the pre-existing
hand-owned surfaces (`PULSE.log`, `.agent/collaboration/a2a-audit.log`,
`.agent/ACTIVATION-AUDIT.md`, `docs/AGENT-PARITY-MATRIX.md`) stay
authoritative and untouched by this module. This projector writes to
SEPARATE `span-*` shadow artifacts for comparison — it never overwrites a
hand-owned surface. Q-C5-2: the activation-audit projection additionally
performs a ONE-CYCLE SHADOW CROSS-CHECK against the hand-appended
`.agent/ACTIVATION-AUDIT.md` (advisory discrepancy report, not a
replacement).

CLI:
    span_projector.py [pulse|a2a-audit|activation-audit|parity-matrix|all]
    span_projector.py <target> --check   # drift check only; no write; exit 1 on drift
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

_LIB = Path(__file__).resolve().parent
_REPO_ROOT = _LIB.parents[2]
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import event_log  # noqa: E402
import span_taxonomy as taxo  # noqa: E402

_COLLAB = _REPO_ROOT / ".agent" / "collaboration"

_TAXONOMY_KINDS_FOR_PULSE = ("tool", "lease", "workspace", "broker")


# ---------------------------------------------------------------------------
# Output paths — env-overridable, resolved at CALL time (same discipline as
# resume_projector.py: never let a sandboxed/test run touch the real
# session anchor).
# ---------------------------------------------------------------------------


def _pulse_shadow_path() -> Path:
    return Path(os.environ.get("SPAN_PULSE_SHADOW_PATH", str(_COLLAB / "span-pulse-shadow.log")))


def _a2a_audit_shadow_path() -> Path:
    return Path(os.environ.get("SPAN_A2A_AUDIT_PATH", str(_COLLAB / "span-a2a-audit.jsonl")))


def _activation_audit_shadow_path() -> Path:
    return Path(os.environ.get("SPAN_ACTIVATION_AUDIT_SHADOW_PATH", str(_COLLAB / "span-activation-audit-shadow.json")))


def _parity_matrix_shadow_path() -> Path:
    return Path(os.environ.get("SPAN_PARITY_MATRIX_PATH", str(_COLLAB / "span-parity-matrix.json")))


def _hand_activation_audit_path() -> Path:
    return Path(os.environ.get("ACTIVATION_AUDIT_MD_PATH", str(_REPO_ROOT / ".agent" / "ACTIVATION-AUDIT.md")))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Candidate extraction — the ONE place raw log events become taxonomy
# records. Every projection below is built ONLY from this function's output.
# ---------------------------------------------------------------------------


def iter_taxonomy_records(events: Optional[list] = None) -> tuple[list[dict], list[dict]]:
    """Split the event log into `(valid, flagged)` taxonomy span records.

    Only `trace.span.end` events carrying the `_span_taxonomy` marker
    (stamped by `span_taxonomy.emit_taxonomy_span`) are candidates — every
    other event (untraced events, pre-existing non-taxonomy spans such as
    `dispatch.local`) is silently skipped, never flagged (they were never
    claiming to be a C5 span). Among candidates, malformed ones (unknown
    kind, missing required attr, secret/high-card/raw-path attr) are
    dropped from every projection and instead appended to `flagged` — never
    silently trusted (§3/§8-2). Pure: identical `events` in -> byte-
    identical `(valid, flagged)` out, sorted by ts for reproducibility."""
    events = events if events is not None else event_log.read_all()
    valid: list[dict] = []
    flagged: list[dict] = []
    for ev in events:
        if ev.type != "trace.span.end":
            continue
        payload = ev.payload or {}
        attrs = payload.get("attrs")
        if not isinstance(attrs, dict) or attrs.get(taxo.TAXONOMY_MARKER_KEY) != taxo.TAXONOMY_MARKER_VALUE:
            continue
        record = {
            "kind": ev.subject,
            "attrs": attrs,
            "agent": ev.agent,
            "ts": ev.ts,
            "event_id": ev.event_id,
            "trace_id": ev.trace_id,
            "span_id": ev.span_id,
            "parent_span_id": ev.parent_span_id,
            "status": payload.get("status"),
        }
        outcome = taxo.validate_span(record)
        if outcome.ok:
            valid.append(record)
        else:
            flagged.append({
                "kind": record["kind"],
                "reason": outcome.reason,
                "ts": ev.ts,
                "event_id": ev.event_id,
            })
    valid.sort(key=lambda r: (r["ts"], r["event_id"]))
    flagged.sort(key=lambda r: (r["ts"], r["event_id"]))
    return valid, flagged


# ---------------------------------------------------------------------------
# PULSE ← tool/lease/workspace/broker spans (§4)
# ---------------------------------------------------------------------------


def project_pulse_spans(events: Optional[list] = None) -> tuple[str, list[dict]]:
    valid, flagged = iter_taxonomy_records(events)
    lines: list[str] = []
    for r in valid:
        if r["kind"] not in _TAXONOMY_KINDS_FOR_PULSE:
            continue
        a = r["attrs"]
        iso = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(r["ts"]))
        action = f"span.{r['kind']}"
        scope = a.get("tool") or a.get("lease_id") or a.get("cell_id") or a.get("broker") or ""
        outcome = a.get("decision") or a.get("verdict") or a.get("event") or ""
        tail = f": {scope}" if scope else ""
        tail += f" — {outcome}" if outcome else ""
        lines.append(f"[{iso}] [{r['agent']}] [{action}]{tail}")
    text = "\n".join(lines) + ("\n" if lines else "")
    return text, flagged


def write_pulse_shadow(events: Optional[list] = None) -> tuple[Path, bool]:
    text, _flagged = project_pulse_spans(events)
    path = _pulse_shadow_path()
    try:
        changed = path.read_text(encoding="utf-8") != text
    except OSError:
        changed = True
    _atomic_write(path, text)
    return path, changed


def check_pulse_shadow(events: Optional[list] = None) -> Optional[str]:
    text, _flagged = project_pulse_spans(events)
    path = _pulse_shadow_path()
    try:
        on_disk = path.read_text(encoding="utf-8")
    except OSError:
        on_disk = None
    if on_disk != text:
        return f"drift: {path} does not match the span-derived pulse projection"
    return None


# ---------------------------------------------------------------------------
# a2a-audit ← broker (A2A effect/egress) spans (§4)
# ---------------------------------------------------------------------------


def project_a2a_audit_spans(events: Optional[list] = None) -> tuple[list[dict], list[dict]]:
    valid, flagged = iter_taxonomy_records(events)
    records: list[dict] = []
    for r in valid:
        if r["kind"] != "broker":
            continue
        a = r["attrs"]
        records.append({
            "ts": r["ts"],
            "trace_id": r["trace_id"],
            "broker": a.get("broker"),
            "effect": a.get("effect"),
            "decision": a.get("decision"),
            "reason": a.get("reason"),
            "profile_id": a.get("profile_id"),
            "lease_id": a.get("lease_id"),
        })
    records.sort(key=lambda x: x["ts"])
    return records, flagged


def _a2a_audit_shadow_text(events: Optional[list] = None) -> str:
    records, _flagged = project_a2a_audit_spans(events)
    lines = [json.dumps(r, sort_keys=True) for r in records]
    return "\n".join(lines) + ("\n" if lines else "")


def write_a2a_audit_shadow(events: Optional[list] = None) -> tuple[Path, bool]:
    text = _a2a_audit_shadow_text(events)
    path = _a2a_audit_shadow_path()
    try:
        changed = path.read_text(encoding="utf-8") != text
    except OSError:
        changed = True
    _atomic_write(path, text)
    return path, changed


def check_a2a_audit_shadow(events: Optional[list] = None) -> Optional[str]:
    text = _a2a_audit_shadow_text(events)
    path = _a2a_audit_shadow_path()
    try:
        on_disk = path.read_text(encoding="utf-8")
    except OSError:
        on_disk = None
    if on_disk != text:
        return f"drift: {path} does not match the span-derived a2a-audit projection"
    return None


# ---------------------------------------------------------------------------
# ACTIVATION-AUDIT ← activation.grant events + lease/workspace spans (§4)
# Q-C5-2: shadow cross-check ONLY — never replaces the hand-appended file.
# ---------------------------------------------------------------------------


def project_activation_audit_spans(events: Optional[list] = None) -> dict:
    events = events if events is not None else event_log.read_all()
    grants = sorted((e for e in events if e.type == "activation.grant"), key=lambda e: e.ts)
    valid, flagged = iter_taxonomy_records(events)
    lease_ws = [r for r in valid if r["kind"] in ("lease", "workspace")]

    grant_rows = []
    for g in grants:
        gid = str(g.payload.get("activation_id") or g.event_id)
        authorized = sum(1 for r in lease_ws if r["ts"] >= g.ts)
        grant_rows.append({"activation_id": gid, "ts": g.ts, "agent": g.agent, "authorized_span_count": authorized})

    return {
        "_generated": (
            "projection of .agents/events/a2a-events.jsonl (activation.grant + "
            "lease/workspace spans) — SHADOW cross-check only (Q-C5-2); does NOT "
            "replace .agent/ACTIVATION-AUDIT.md"
        ),
        "grants": grant_rows,
        "lease_workspace_span_count": len(lease_ws),
        "flagged_span_count": len(flagged),
        "flagged": flagged,
    }


def cross_check_activation_audit(events: Optional[list] = None, hand_path: Optional[Path] = None) -> dict:
    """One-cycle shadow cross-check (Q-C5-2). Heuristic, one-directional
    (span-derived activation ids -> substring search in the hand-appended
    markdown): advisory only, never authoritative. NEVER raises — a missing
    hand-audit file is reported (`hand_audit_present: false`), not an
    error."""
    ledger = project_activation_audit_spans(events)
    path = hand_path or _hand_activation_audit_path()
    try:
        hand_text = path.read_text(encoding="utf-8")
    except OSError:
        hand_text = ""
    discrepancies = []
    for g in ledger["grants"]:
        aid = g["activation_id"]
        if aid and aid not in hand_text:
            discrepancies.append({"activation_id": aid, "reason": "not-found-in-hand-appended-audit"})
    return {
        "ledger": ledger,
        "hand_audit_path": str(path),
        "hand_audit_present": bool(hand_text),
        "discrepancy_count": len(discrepancies),
        "discrepancies": discrepancies,
    }


def write_activation_audit_shadow(events: Optional[list] = None) -> tuple[Path, bool]:
    report = cross_check_activation_audit(events)
    text = _json_dumps(report)
    path = _activation_audit_shadow_path()
    try:
        changed = path.read_text(encoding="utf-8") != text
    except OSError:
        changed = True
    _atomic_write(path, text)
    return path, changed


def check_activation_audit_shadow(events: Optional[list] = None) -> Optional[str]:
    text = _json_dumps(cross_check_activation_audit(events))
    path = _activation_audit_shadow_path()
    try:
        on_disk = path.read_text(encoding="utf-8")
    except OSError:
        on_disk = None
    if on_disk != text:
        return f"drift: {path} does not match the span-derived activation-audit shadow report"
    return None


# ---------------------------------------------------------------------------
# parity matrix ← tool/lease spans (§4): agent/lane coverage
# ---------------------------------------------------------------------------


def project_parity_matrix_spans(events: Optional[list] = None) -> dict:
    valid, flagged = iter_taxonomy_records(events)
    matrix: dict[str, dict[str, int]] = {}
    for r in valid:
        if r["kind"] not in ("tool", "lease"):
            continue
        agent = r["agent"] or "unknown"
        decision = r["attrs"].get("decision") or "unknown"
        row = matrix.setdefault(agent, {})
        key = f"{r['kind']}:{decision}"
        row[key] = row.get(key, 0) + 1
    return {
        "_generated": (
            "projection of .agents/events/a2a-events.jsonl (tool/lease spans) — "
            "advisory agent/lane coverage view; does NOT replace docs/AGENT-PARITY-MATRIX.md"
        ),
        "agents": matrix,
        "flagged_span_count": len(flagged),
    }


def write_parity_matrix_shadow(events: Optional[list] = None) -> tuple[Path, bool]:
    text = _json_dumps(project_parity_matrix_spans(events))
    path = _parity_matrix_shadow_path()
    try:
        changed = path.read_text(encoding="utf-8") != text
    except OSError:
        changed = True
    _atomic_write(path, text)
    return path, changed


def check_parity_matrix_shadow(events: Optional[list] = None) -> Optional[str]:
    text = _json_dumps(project_parity_matrix_spans(events))
    path = _parity_matrix_shadow_path()
    try:
        on_disk = path.read_text(encoding="utf-8")
    except OSError:
        on_disk = None
    if on_disk != text:
        return f"drift: {path} does not match the span-derived parity-matrix projection"
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_WRITERS = {
    "pulse": write_pulse_shadow,
    "a2a-audit": write_a2a_audit_shadow,
    "activation-audit": write_activation_audit_shadow,
    "parity-matrix": write_parity_matrix_shadow,
}

_CHECKERS = {
    "pulse": check_pulse_shadow,
    "a2a-audit": check_a2a_audit_shadow,
    "activation-audit": check_activation_audit_shadow,
    "parity-matrix": check_parity_matrix_shadow,
}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="span_projector.py")
    ap.add_argument("target", nargs="?", default="all",
                     choices=["pulse", "a2a-audit", "activation-audit", "parity-matrix", "all"])
    ap.add_argument("--check", action="store_true", help="drift check only; no write; exit 1 on drift")
    args = ap.parse_args()

    targets = list(_WRITERS.keys()) if args.target == "all" else [args.target]
    events = event_log.read_all()
    drift = False
    for t in targets:
        if args.check:
            msg = _CHECKERS[t](events)
            if msg:
                print(f"DRIFT {t}: {msg}")
                drift = True
            else:
                print(f"OK {t}: no drift")
        else:
            path, changed = _WRITERS[t](events)
            print(f"{t} <- {path} ({'updated' if changed else 'unchanged'})")
    return 1 if (args.check and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
