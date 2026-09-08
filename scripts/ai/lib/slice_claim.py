#!/usr/bin/env python3
"""Slice/path claim registry — stop two lanes editing the same files concurrently.

C-1 from SWARM-LESSONS-INTEGRATION-20260907.md. The multi-agent swarm field-report
showed uncoordinated agents overwrite each other's work ("claim violation"); our own
coordination was advisory narration only (PULSE), with nothing a second lane must
check. This is a lightweight, durable claim store: a lane takes a claim over a set
of repo-relative paths before editing; another lane checking overlapping paths sees
the active claimant and routes elsewhere or queues, instead of colliding.

Design notes:
- Advisory-first, fail-SAFE for reads: an unreadable/corrupt store yields "no active
  claims" so a broken store never hard-blocks work (the enforcement seam decides how
  strict to be). Writes are atomic (tmp + os.replace).
- Same-lane re-claim of a slice is idempotent (refreshes ttl); it never self-conflicts.
- Path overlap = exact match OR ancestor/descendant directory relationship, so
  claiming `scripts/ai/` conflicts with `scripts/ai/foo.py` but not `scripts/other`.
- Claims carry a TTL; expired claims are dropped on every load (auto-release), so a
  crashed lane cannot hold paths forever.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import PurePosixPath
from typing import Any

DEFAULT_STORE = ".agent/collaboration/slice-claims.json"
DEFAULT_TTL_SECONDS = 7200


@dataclass(frozen=True)
class Claim:
    slice_id: str
    lane: str
    paths: tuple[str, ...]
    created_at: float
    expires_at: float

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["paths"] = list(self.paths)
        return d


def _norm(path: str) -> str:
    # Repo-relative POSIX normalization; strip leading ./ and trailing /.
    p = PurePosixPath(path.strip().lstrip("./")) if path.strip() not in ("", ".") else PurePosixPath(".")
    return p.as_posix()


def _overlaps(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return True
    pa, pb = PurePosixPath(na), PurePosixPath(nb)
    return pa in pb.parents or pb in pa.parents


def load_claims(store_path: str | os.PathLike = DEFAULT_STORE, *, now: float | None = None) -> list[Claim]:
    """Active (non-expired) claims. Fail-safe: any read/parse error -> empty list."""
    now = time.time() if now is None else now
    try:
        raw = json.loads(open(store_path, encoding="utf-8").read())
        rows = raw.get("claims", []) if isinstance(raw, dict) else []
    except Exception:
        return []
    out: list[Claim] = []
    for r in rows:
        try:
            c = Claim(str(r["slice_id"]), str(r["lane"]), tuple(str(p) for p in r["paths"]),
                      float(r["created_at"]), float(r["expires_at"]))
        except Exception:
            continue  # skip malformed row, never crash the registry
        if c.expires_at > now:
            out.append(c)
    return sorted(out, key=lambda c: (c.slice_id, c.lane))


def find_conflicts(claims: list[Claim], paths: list[str], lane: str) -> list[Claim]:
    """Active claims held by OTHER lanes whose paths overlap the requested paths."""
    hits: list[Claim] = []
    for c in claims:
        if c.lane == lane:
            continue
        if any(_overlaps(rp, cp) for rp in paths for cp in c.paths):
            hits.append(c)
    return hits


def _write(store_path: str | os.PathLike, claims: list[Claim]) -> None:
    payload = json.dumps({"claims": [c.to_json() for c in claims]}, indent=2, sort_keys=True) + "\n"
    tmp = f"{store_path}.tmp.{os.getpid()}"
    os.makedirs(os.path.dirname(str(store_path)) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp, store_path)


def take_claim(store_path: str | os.PathLike, slice_id: str, lane: str, paths: list[str],
               *, ttl_seconds: int = DEFAULT_TTL_SECONDS, now: float | None = None) -> dict[str, Any]:
    """Attempt a claim. Returns {"ok": True, "claim": ...} or {"ok": False, "conflicts": [...]}.

    A conflict with another lane is NOT recorded (the caller must route elsewhere).
    Re-claiming the same slice_id from the same lane refreshes it in place."""
    now = time.time() if now is None else now
    norm_paths = sorted({_norm(p) for p in paths if p.strip()})
    if not norm_paths:
        return {"ok": False, "error": "no paths given"}
    claims = load_claims(store_path, now=now)
    conflicts = find_conflicts(claims, norm_paths, lane)
    if conflicts:
        return {"ok": False, "conflicts": [c.to_json() for c in conflicts]}
    kept = [c for c in claims if not (c.slice_id == slice_id and c.lane == lane)]
    claim = Claim(slice_id, lane, tuple(norm_paths), now, now + ttl_seconds)
    _write(store_path, sorted(kept + [claim], key=lambda c: (c.slice_id, c.lane)))
    return {"ok": True, "claim": claim.to_json()}


def release_claim(store_path: str | os.PathLike, slice_id: str, lane: str,
                  *, now: float | None = None) -> dict[str, Any]:
    claims = load_claims(store_path, now=now)
    kept = [c for c in claims if not (c.slice_id == slice_id and c.lane == lane)]
    _write(store_path, kept)
    return {"ok": True, "released": len(claims) - len(kept)}


def check_paths(store_path: str | os.PathLike, paths: list[str], lane: str,
                *, now: float | None = None) -> dict[str, Any]:
    """Read-only: would these paths conflict for this lane right now?"""
    norm_paths = sorted({_norm(p) for p in paths if p.strip()})
    conflicts = find_conflicts(load_claims(store_path, now=now), norm_paths, lane)
    return {"clear": not conflicts, "conflicts": [c.to_json() for c in conflicts]}
