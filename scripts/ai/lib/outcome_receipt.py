"""Append-only per-landing outcome receipts (raw facts, no derived metrics).

One JSON line per landed PR in <delegation dir>/outcome-receipts.jsonl (0600). A line that trips redaction
or the fail-closed scan goes (redacted) to outcome-receipts.quarantine.jsonl and never to the main log.
Token counts come from the delegation registry rows of the review runs; unknown stays null.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LOG = "outcome-receipts.jsonl"
QUARANTINE = "outcome-receipts.quarantine.jsonl"
_PRIVACY = Path(__file__).resolve().parents[3] / "ai-stack/mcp-servers/shared"
_HITS = [
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S{4,}"),
    re.compile(r"Bearer\s+\S+"),
    re.compile(r"/home/[^\s\"']+|/run/secrets[^\s\"']*"),
]
_BLOB = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
_HEX = re.compile(r"[0-9a-f]{32,}")


def _entropy(s: str) -> float:
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def _entropy_text(text: str, allowed_paths: set[str] | frozenset[str]) -> str:
    """Return `text` with verified multi-segment `files[*].path`/`renamed_from` values split on `/`.

    Replacing `/` with a space prevents path separators from joining benign directory/filename
    segments into a single 32+ char `_BLOB` match while keeping every individual path component
    subject to the entropy check.
    """
    if not allowed_paths:
        return text
    try:
        obj = json.loads(text)
    except ValueError:
        return text
    if not isinstance(obj, dict) or not isinstance(obj.get("files"), list):
        return text
    masked_files = []
    changed = False
    for entry in obj["files"]:
        if isinstance(entry, dict):
            copy = dict(entry)
            for key in ("path", "renamed_from"):
                val = copy.get(key)
                if isinstance(val, str) and "/" in val and val in allowed_paths:
                    copy[key] = val.replace("/", " ")
                    changed = True
            masked_files.append(copy)
        else:
            masked_files.append(entry)
    if not changed:
        return text
    return json.dumps(dict(obj, files=masked_files), sort_keys=True)


def scan(text: str, *, allowed_paths: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Names of fail-closed findings in already-redacted text; empty means clean.

    `allowed_paths` splits multi-segment (`/`-containing) verified `files[*].path` and
    `files[*].renamed_from` field values on `/` before the generic entropy heuristic so path
    separators do not join short segments into a 32+ char token. Individual path components,
    tokens in any other field, pattern checks (`_HITS`), and `_redact` remain checked.
    """
    hits = [f"pattern{i}" for i, p in enumerate(_HITS) if p.search(text)]
    target = _entropy_text(text, allowed_paths)
    if any(not _HEX.fullmatch(b) and _entropy(b) > 4.0 for b in _BLOB.findall(target)):
        hits.append("entropy")
    return hits


def is_eligible(rec: dict) -> bool:
    """Independently reviewed (PASS, author not a reviewer) and CI-passing: eligible as a verified trajectory."""
    return ("PASS" in (rec.get("review_verdicts") or []) and rec.get("ci") == "pass"
            and rec.get("author_lane") not in (rec.get("reviewer_lanes") or []))


def _redact(text: str) -> tuple[str, list[str]]:
    sys.path.insert(0, str(_PRIVACY))
    try:
        from telemetry_privacy import redact_secrets
    except ImportError:
        return text, ["redactor_unavailable"]
    finally:
        sys.path.remove(str(_PRIVACY))
    return redact_secrets(text)


def _append(path: Path, line: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


def _registry_row(delegation_dir: Path, run_id: str) -> dict:
    row: dict = {}
    try:
        for ln in (delegation_dir / "registry.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("id") == run_id:
                row = r  # last row wins
    except OSError:
        pass
    return row


_USED = re.compile(r"^tokens used\s*\n\s*([\d,]+)\s*$", re.M)


def _logged_total(delegation_dir: Path, row: dict) -> int | None:
    """Codex logs end with 'tokens used' and a total (no in/out split); the registry row never carries it."""
    name = Path(str(row.get("output_file") or "")).name
    if not name:
        return None
    try:
        hits = _USED.findall((delegation_dir / "outputs" / name).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    return int(hits[-1].replace(",", "")) if hits else None


def record_landing(delegation_dir: Path, *, pr: int, head: str, author_lane: str, reviews: list[dict],
                   request_changes_rounds: int = 0, tier0: str | None = None, ci: str | None = None,
                   tier0_failures: int = 0, ci_failures: int = 0, now: str | None = None) -> str:
    """Append one receipt. reviews: [{lane, run_id, verdict}]. Returns 'written', 'quarantined' or 'duplicate'."""
    d = Path(delegation_dir)
    d.mkdir(parents=True, exist_ok=True)
    tokens: dict = {}
    for rv in reviews:
        row = _registry_row(d, rv.get("run_id", ""))
        tin, tout = row.get("tokens_in"), row.get("tokens_out")
        tokens[rv["lane"]] = {"in": tin if isinstance(tin, int) else None, "out": tout if isinstance(tout, int) else None}
        total = _logged_total(d, row) if tokens[rv["lane"]] == {"in": None, "out": None} else None
        if total is not None:
            tokens[rv["lane"]]["total"] = total
    rec = {
        "schema": 1, "pr": pr, "head_sha": head, "author_lane": author_lane,
        "reviewer_lanes": sorted({r["lane"] for r in reviews}),
        "review_verdicts": [r.get("verdict") for r in reviews],
        "request_changes_rounds": request_changes_rounds,
        "tier0": tier0, "ci": ci, "tier0_failures": tier0_failures, "ci_failures": ci_failures,
        "tokens": tokens,  # {lane: {in, out}}; the author lane is absent: no per-PR author count is recorded anywhere
        "recorded_at": now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    main = d / LOG
    try:
        if any(json.loads(ln).get("pr") == pr for ln in main.read_text(encoding="utf-8").splitlines() if ln.strip()):
            return "duplicate"
    except (OSError, ValueError):
        pass
    redacted, found = _redact(json.dumps(rec, sort_keys=True))
    found = found + scan(redacted)
    if found:
        _append(d / QUARANTINE, json.dumps({"pr": pr, "recorded_at": rec["recorded_at"], "reasons": sorted(set(found)),
                                            "redacted": redacted}))
        print(f"WARN: outcome receipt for PR #{pr} quarantined ({','.join(sorted(set(found)))})", file=sys.stderr)
        return "quarantined"
    _append(main, redacted)
    return "written"
