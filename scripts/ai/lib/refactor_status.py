#!/usr/bin/env python3
"""AQ-OS refactor status projector.

Pure derivation of the refactor overview from ground truth so it can never
hand-drift the way ``UNIFIED-PROGRAM-PLAN.md``'s narrative status column has
(see ``.agents/plans/aqos-refactor-status/SPEC.md``). Same pattern as the
PULSE/RESUME event projections: the manifest (``config/refactor-milestones.json``)
carries only EDITORIAL content (name/sub/note/decision/unblocks/issues); the
``status``/``resolved``/``pct`` fields below are always computed here from:

  - git log commit subjects matched against each track's ``commit_match`` regexes
  - ``.agents/events/*.jsonl`` activation.grant events (agent=owner) naming a
    track's ``activation_subject``
  - presence of a ``freeze_record`` file with no matching activation event
  - an open claim file under ``.agent/collaboration/slice-claims/``
  - a ``blocker_note`` field in the manifest (issues-backlog lives outside the
    repo, so the manifest carries the blocker text directly)

No network access. Deterministic for a given repo state. Never raises --
a missing/unreadable signal source is treated as "absent", not fatal.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Ground-truth signal gathering
# ---------------------------------------------------------------------------


def _git_log_subjects(repo_root: Path) -> list[str]:
    """Return commit subjects (``%s``) for the whole reachable history.

    Uses a plain space-delimited format (no ``|`` — a literal pipe character
    embedded in ``--pretty`` has been observed to confuse at least one shell
    wrapper in this environment) and never raises: git being absent, the path
    not being a repo, or any subprocess error all resolve to an empty list.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--all", "--format=%s"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _matches_any(subjects: list[str], patterns: list[str]) -> bool:
    if not patterns:
        return False
    compiled = []
    for pat in patterns:
        try:
            compiled.append(re.compile(pat, re.IGNORECASE))
        except re.error:
            continue
    if not compiled:
        return False
    for subj in subjects:
        for rx in compiled:
            if rx.search(subj):
                return True
    return False


def _activation_events(repo_root: Path) -> set[str]:
    """Return the set of ``subject`` values granted by an owner activation.grant."""
    granted: set[str] = set()
    events_dir = repo_root / ".agents" / "events"
    if not events_dir.is_dir():
        return granted
    for path in sorted(events_dir.glob("*.jsonl")):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(evt, dict):
                        continue
                    if evt.get("type") != "activation.grant":
                        continue
                    if evt.get("agent") != "owner":
                        continue
                    subj = evt.get("subject")
                    if subj:
                        granted.add(subj)
        except Exception:
            continue
    return granted


def _open_slice_claim(repo_root: Path, code: str) -> bool:
    """True if an open (non-lock) claim file exists whose name references ``code``.

    Matches on a whole delimiter-bounded TOKEN of the claim filename's stem,
    never a bare substring: short codes like "A", "C", "D", "E", "F", "G" are
    single characters, and a naive ``code in filename`` check would false-
    positive against almost any claim filename in the directory (e.g. every
    "local-2026...-<random>.claim" ephemeral dispatch claim contains the
    letter "a"). Tokenizing on non-alphanumeric separators and requiring an
    exact token match avoids that.
    """
    claims_dir = repo_root / ".agent" / "collaboration" / "slice-claims"
    if not claims_dir.is_dir():
        return False
    needle = code.lower()
    if not needle:
        return False
    try:
        for entry in claims_dir.iterdir():
            name = entry.name
            if name.startswith("."):
                continue  # lock files are dotfiles
            if not name.endswith(".claim"):
                continue
            stem = name[: -len(".claim")].lower()
            tokens = re.split(r"[^a-z0-9]+", stem)
            if needle in tokens:
                return True
    except Exception:
        return False
    return False


def _freeze_record_exists(repo_root: Path, freeze_record: str | None) -> bool:
    if not freeze_record:
        return False
    return (repo_root / freeze_record).is_file()


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------

TRACK_STATUSES = ("done", "active", "blocked", "notstarted")


def _track_status_and_pct(
    track: dict[str, Any],
    subjects: list[str],
    activated_subjects: set[str],
    repo_root: Path,
) -> tuple[str, int]:
    """Derive (status, pct) for one track.

    Precedence (highest wins), a total ordering over the original SPEC's
    ACTIVATED > SHIPPED > BLOCKED > FROZEN > IN_PROGRESS > NOT_STARTED ladder,
    with one deliberate deviation:

      1. blocker_note present                                -> blocked
      2. activation_subject matched by an owner activation    -> done   (ACTIVATED)
      3. a commit matches commit_match, track NOT ongoing     -> done   (SHIPPED)
      4. freeze_record file exists (no activation)            -> active (FROZEN)
      5. a commit matches commit_match, track IS ongoing      -> active (partial SHIPPED)
      6. an open slice-claim references this track's code     -> active (IN_PROGRESS)
      7. else                                                 -> notstarted

    Rule 1 (blocked) is promoted above SHIPPED/FROZEN -- a deliberate
    deviation from the strict original ladder, matching the SPEC's own stated
    intent ("BLOCKED outranks FROZEN so the C2 built-in-tool gap shows") and
    its acceptance bar, which explicitly accepts either FROZEN or BLOCKED for
    C2. A track can be committed AND frozen AND still gate-blocked; the
    blocker must win so the gap stays visible instead of reading as shipped.

    Everywhere else this preserves the original ladder: a real SHIPPED commit
    (rule 3) outranks a merely open IN_PROGRESS claim (rule 6) -- a stale
    claim file left lying around must never mask a milestone that has since
    actually shipped.
    """
    detection = track.get("detection", {}) or {}
    ongoing = bool(track.get("ongoing", False))
    manifest_pct = track.get("pct")

    if detection.get("blocker_note"):
        pct = manifest_pct if isinstance(manifest_pct, int) else 100
        return "blocked", pct

    activation_subject = detection.get("activation_subject")
    if activation_subject and activation_subject in activated_subjects:
        return "done", 100

    commit_hit = _matches_any(subjects, detection.get("commit_match", []) or [])
    if commit_hit and not ongoing:
        return "done", 100

    if _freeze_record_exists(repo_root, detection.get("freeze_record")):
        pct = manifest_pct if isinstance(manifest_pct, int) else 50
        return "active", pct

    if commit_hit and ongoing:
        pct = manifest_pct if isinstance(manifest_pct, int) else 50
        return "active", pct

    if _open_slice_claim(repo_root, track.get("code", "")):
        pct = manifest_pct if isinstance(manifest_pct, int) else 50
        return "active", pct

    return "notstarted", 0


def _gate_resolved(gate: dict[str, Any], subjects: list[str]) -> bool:
    detection = gate.get("detection", {}) or {}
    return _matches_any(subjects, detection.get("ratified_commit_match", []) or [])


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def project(manifest_path: str | Path, repo_root: str | Path) -> dict[str, Any]:
    """Project the refactor-status overview from ``manifest_path`` + ``repo_root``.

    Returns a dict shaped for the HTML progress tracker:
    ``{"updated": "YYYY-MM-DD", "tracks": [...], "gate": [...], "issues": [...],
    "stats": {...}}``. Never raises: a missing/unparseable manifest yields an
    empty projection rather than an exception, since this tool must never be
    the thing that breaks a drift-check gate.
    """
    manifest_path = Path(manifest_path)
    repo_root = Path(repo_root)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}

    tracks_in = manifest.get("tracks", []) or []
    gate_in = manifest.get("gate", []) or []
    issues_in = manifest.get("issues", []) or []

    subjects = _git_log_subjects(repo_root)
    activated_subjects = _activation_events(repo_root)

    tracks_out: list[dict[str, Any]] = []
    for track in sorted(tracks_in, key=lambda t: t.get("order", 0)):
        status, pct = _track_status_and_pct(track, subjects, activated_subjects, repo_root)
        tracks_out.append(
            {
                "code": track.get("code"),
                "name": track.get("name"),
                "sub": track.get("sub"),
                "note": track.get("note"),
                "order": track.get("order"),
                "parent": track.get("parent"),
                "status": status,
                "pct": pct,
            }
        )

    gate_out: list[dict[str, Any]] = []
    for gate in gate_in:
        resolved = _gate_resolved(gate, subjects)
        gate_out.append(
            {
                "id": gate.get("id"),
                "decision": gate.get("decision"),
                "unblocks": gate.get("unblocks"),
                "resolved": resolved,
            }
        )

    issues_out: list[dict[str, Any]] = []
    for issue in issues_in:
        issues_out.append(
            {
                "title": issue.get("title"),
                "sev": issue.get("sev"),
                "note": issue.get("note"),
            }
        )

    stats = {
        "tracks_done_or_active": sum(1 for t in tracks_out if t["status"] in ("done", "active")),
        "blocking_gates": sum(1 for t in tracks_out if t["status"] == "blocked"),
        "decisions_pending": sum(1 for g in gate_out if not g["resolved"]),
        "open_high_issues": sum(1 for i in issues_out if str(i.get("sev", "")).lower() == "high"),
    }

    return {
        "updated": date.today().isoformat(),
        "tracks": tracks_out,
        "gate": gate_out,
        "issues": issues_out,
        "stats": stats,
    }


def project_json(manifest_path: str | Path, repo_root: str | Path) -> str:
    """Convenience wrapper: ``project()`` serialized as pretty JSON."""
    return json.dumps(project(manifest_path, repo_root), indent=2, sort_keys=False)


def strip_updated(projection: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of ``projection`` with the ``updated`` date removed.

    Used by drift checks so a same-day-vs-next-day timestamp difference never
    counts as drift -- only real content changes do.
    """
    out = dict(projection)
    out.pop("updated", None)
    return out


__all__ = ["project", "project_json", "strip_updated", "TRACK_STATUSES"]
