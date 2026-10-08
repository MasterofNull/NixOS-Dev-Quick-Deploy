"""ECC P1 operator diagnostics: one bounded, read-only report over the ECC surfaces.

Aggregates P0-A (outcome catalog), P0-B (provider projection drift), P0-C (lifecycle
health) and the P1 gaps P0-A proved: memory recall completeness and the eval
dimensions. Each section reports ok | degraded | unverified; the overall status is
the worst section, and nothing is ever reported as a silent pass.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path

MAX_FILES = 5000          # mirrors the ECC vault scan bounds (ledger: memory/learning pass)
MAX_BYTES = 16 * 1024 * 1024
MAX_RECORD_BYTES = 256 * 1024
_RANK = {"ok": 0, "unverified": 1, "degraded": 2}

# dimension -> (test file, marker). Static presence only: never a runtime verdict.
EVAL_DIMENSIONS = {
    "silent_failure": ("scripts/testing/test-decompose-loop.py", "must be recorded as a failure"),
    "cancellation": ("scripts/testing/test-agent-dispatch-contract.py", "cancel"),
    "suspend_resume": ("scripts/testing/test-suspend-resume-contract.py", "suspend"),
    "permission_denial": ("scripts/testing/test-capability-lease-gate.py", "denied"),
    "resource_budget": ("scripts/testing/test-agent-loop-bounds.py", "bound"),
    "completion_truth": ("scripts/testing/test-local-delegation-artifact.py", "missing_final_answer"),
}


def _load(repo: Path, rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, repo / rel)
    if spec is None or spec.loader is None:
        raise ImportError(rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _unverified(reason: str) -> dict:
    return {"status": "unverified", "reason": reason}


def outcomes_section(repo: Path) -> dict:
    try:
        mod = _load(repo, "scripts/ai/lib/capability_outcomes.py", "ecc_diag_outcomes")
        outcomes = mod.load_outcome_catalog(repo / "config" / "capability-gap-catalog.json")["outcomes"]
    except Exception as exc:  # noqa: BLE001 - any failure is UNVERIFIED, never a pass
        return _unverified(f"catalog_unavailable:{type(exc).__name__}")
    # A partial outcome with no QA check or dashboard visibility is an open, proven gap.
    open_gaps = sorted(o["id"] for o in outcomes
                       if o.get("status") in ("partial", "missing") and not (o.get("qa") and o.get("visibility")))
    return {"status": "degraded" if open_gaps else "ok", "total": len(outcomes), "open_gaps": open_gaps}


def projection_section(repo: Path) -> dict:
    try:
        pp = _load(repo, "scripts/ai/lib/provider_projection.py", "ecc_diag_projection")
        doc = pp.check(repo)
    except Exception as exc:  # noqa: BLE001
        return _unverified(f"projection_unavailable:{type(exc).__name__}")
    drift = doc.get("status") == "drift"
    return {"status": "degraded" if drift else "ok", "projection": doc.get("status"),
            "findings": len(doc.get("findings", []))}


def lifecycle_section(repo: Path, state_file: str | None) -> dict:
    try:
        mod = _load(repo, "scripts/ai/lib/lifecycle_events.py", "ecc_diag_lifecycle")
        h = mod.health_summary(state_file or None)
    except Exception as exc:  # noqa: BLE001
        return _unverified(f"adapter_unavailable:{type(exc).__name__}")
    if h.get("status") == "unverified":
        return {"status": "unverified", "reason": h.get("reason", "state_invalid")}
    if h.get("status") == "dormant":
        # Dormant = nothing observed; do not present as healthy.
        return {"status": "unverified", "reason": "dormant_no_state_observed", "lifecycle": "dormant"}
    return {"status": "degraded" if h.get("status") == "degraded" else "ok", "lifecycle": h.get("status"),
            "failures": h.get("failures", 0), "disabled": len(h.get("disabled", []))}


def memory_recall_section(dirs: list[Path]) -> dict:
    """Bounded recall-completeness telemetry for file-based memory topic dirs."""
    t = {"scanned": 0, "bytes": 0, "malformed": 0, "symlinks": 0, "oversize": 0,
         "unreadable": 0, "truncated": False, "dirs_missing": 0}
    for d in dirs:
        if not d.is_dir() or d.is_symlink():
            t["dirs_missing"] += 1
            continue
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError:
            t["unreadable"] += 1
            continue
        for e in entries:
            if not e.name.endswith(".md"):
                continue
            if t["scanned"] >= MAX_FILES or t["bytes"] >= MAX_BYTES:
                t["truncated"] = True
                break
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                t["unreadable"] += 1
                continue
            if stat.S_ISLNK(st.st_mode):
                t["symlinks"] += 1
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            t["scanned"] += 1
            if st.st_size > MAX_RECORD_BYTES:
                t["oversize"] += 1
                continue
            t["bytes"] += st.st_size
            try:
                text = Path(e.path).read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                t["malformed"] += 1
                continue
            if not text.strip():
                t["malformed"] += 1
    if t["scanned"] == 0:
        return {**t, "status": "unverified", "reason": "no_records_scanned"}
    bad = t["malformed"] or t["symlinks"] or t["oversize"] or t["unreadable"] or t["truncated"]
    return {**t, "status": "degraded" if bad else "ok"}


def eval_dimensions_section(repo: Path) -> dict:
    dims, missing = {}, []
    for name, (rel, marker) in EVAL_DIMENSIONS.items():
        try:
            present = marker in (repo / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            present = False
        dims[name] = "covered-static" if present else "unverified"
        if not present:
            missing.append(name)
    return {"status": "unverified" if missing else "ok", "evidence_scope": "static-marker-presence",
            "dimensions": dims, "unverified": missing}


def collect(repo: Path, *, state_file: str | None = None, memory_dirs: list[Path] | None = None) -> dict:
    repo = Path(repo)
    sections = {
        "outcomes": outcomes_section(repo),
        "projection": projection_section(repo),
        "lifecycle": lifecycle_section(repo, state_file),
        "memory_recall": memory_recall_section(memory_dirs if memory_dirs is not None
                                               else [repo / ".agent" / "memory"]),
        "eval_dimensions": eval_dimensions_section(repo),
    }
    worst = max(sections.values(), key=lambda s: _RANK[s["status"]])["status"]
    return {"status": worst, "evidence_scope": "metadata-only", "sections": sections}


def dashboard_summary(repo: Path) -> dict:
    """Compact form for the dashboard capability-gap card (never raises)."""
    try:
        doc = collect(repo, state_file=os.getenv("LIFECYCLE_EVENTS_STATE_FILE") or None)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "status": "unverified", "reason": f"diagnostics_unavailable:{type(exc).__name__}"}
    return {"available": True, "status": doc["status"],
            "sections": {k: v["status"] for k, v in doc["sections"].items()}}


_SHOW = ("open_gaps", "projection", "unverified", "malformed", "symlinks", "oversize", "truncated", "scanned", "failures")


def render_text(doc: dict) -> str:
    lines = [f"ECC diagnostics: {doc['status'].upper()} ({doc['evidence_scope']})"]
    for name, sec in doc["sections"].items():
        extra = sec.get("reason") or ", ".join(
            f"{k}={v}" for k, v in sec.items() if k in _SHOW and v not in ([], 0, False))
        lines.append(f"  {name}: {sec['status'].upper()}" + (f" -- {extra}" if extra else ""))
    return "\n".join(lines)
