#!/usr/bin/env python3
"""Bounded, cadence-driven, review-gated frontier scan (W3-S5).

`scan_due` finds PRIMARY sources whose cadence elapsed, fetches each through an
injected fetcher (default: SSRF + robots guarded), fingerprints the normalized text,
and on a change vs last-seen state files ONE candidate (verdict=monitor,
status=new -> unreviewed). It never accepts or folds; the debate gate still applies.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import types
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import frontier_backlog as fb

DEFAULT_STATE = ".agents/plans/frontier-evidence-intake/scan-state.json"
CADENCE_DAYS = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90}
UA = "aq-frontier-scan/1.0 (+bounded weekly; robots-respecting)"
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3


def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _parse_iso(s: str | None) -> float | None:
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone if s else None
    except (ValueError, TypeError):
        return None


def normalize(text: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_state(path: str | os.PathLike) -> dict[str, Any]:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(path: str | os.PathLike, state: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def due_sources(catalog: dict[str, Any], state: dict[str, Any], now: float) -> list[dict[str, Any]]:
    """Every catalog source with cadence/age/due flag (primary only are fetchable)."""
    rows = []
    for s in catalog.get("sources") or []:
        days = CADENCE_DAYS.get(s.get("cadence"))
        last = _parse_iso((state.get(s["id"]) or {}).get("last_scan"))
        age = None if last is None else round((now - last) / 86400, 2)
        due = days is not None and (age is None or age >= days)
        rows.append({"id": s["id"], "url": s.get("url"), "trust_tier": s.get("trust_tier"),
                     "cadence": s.get("cadence"), "last_scan_age_days": age,
                     "due": bool(due and s.get("trust_tier") == "primary"),
                     "last_error": (state.get(s["id"]) or {}).get("last_error")})
    return rows


def scan_due(catalog: dict[str, Any], *, state_path: str, store: str,
             fetcher: Callable[..., dict[str, Any]], now: float | None = None,
             dry_run: bool = False, max_sources: int = 6, per_fetch_timeout: float = 20.0,
             total_budget: float = 300.0, clock: Callable[[], float] = time.time) -> dict[str, Any]:
    now = clock() if now is None else now
    t0 = clock()
    state = load_state(state_path)
    rows = due_sources(catalog, state, now)
    by_id = {s["id"]: s for s in catalog.get("sources") or []}
    due = [r for r in rows if r["due"]]
    due.sort(key=lambda r: (r["last_scan_age_days"] is not None, -(r["last_scan_age_days"] or 0), r["id"]))
    results, skipped = [], 0
    for r in due:
        if len(results) >= max_sources or (clock() - t0) >= total_budget:
            skipped += 1
            continue
        sid, entry = r["id"], dict(state.get(r["id"]) or {})
        res = {"id": sid, "outcome": None}
        if dry_run:
            res["outcome"] = "would_scan"; results.append(res); continue
        try:
            got = fetcher(r["url"], timeout=per_fetch_timeout, etag=entry.get("etag"))
            if got.get("not_modified"):
                fp = entry.get("fingerprint")
            else:
                fp = hashlib.sha256(normalize(got.get("text", "")).encode("utf-8")).hexdigest()
            prev = entry.get("fingerprint")
            entry.update({"last_scan": _iso(now), "last_error": None, "fingerprint": fp,
                          "etag": got.get("etag") or entry.get("etag")})
            if prev is None:
                res["outcome"] = "baseline"
            elif fp == prev:
                res["outcome"] = "unchanged"
            else:
                src = by_id[sid]
                cand = fb.add(store, {
                    "id": f"SC-{sid}-{fp[:8]}",
                    "technique": f"Source changed: {src.get('name', sid)}",
                    "source": r["url"],
                    "claim": f"Content fingerprint changed {prev[:8]} -> {fp[:8]}; unreviewed, needs triage.",
                    "verdict": "monitor", "aqos_mapping": f"pillar={src.get('pillar')}; mapping pending review",
                    "proposed_slice": "triage the change; add a mapped candidate via aq-frontier add if relevant, else drop",
                    "acceptance_goal": "n/a until triaged", "status": "new", "source_ids": [sid]}, now=now)
                res["outcome"] = "candidate_filed" if cand.get("added") else "candidate_duplicate"
                res["candidate"] = cand.get("id")
        except Exception as exc:  # recorded, never fatal
            entry.update({"last_scan": _iso(now), "last_error": f"{type(exc).__name__}: {exc}"[:300]})
            res["outcome"] = "error"; res["error"] = entry["last_error"]
        state[sid] = entry
        results.append(res)
    if not dry_run and results:
        save_state(state_path, state)
    return {"dry_run": dry_run, "due": len(due), "scanned": len(results), "deferred_by_cap": skipped,
            "results": results, "sources": due_sources(catalog, state, now)}


def _load_guard():
    """Reuse the repo SSRF policy; shim its logging/http deps when absent from the CLI python."""
    for name in ("structlog", "httpx"):
        try:
            __import__(name)
        except ImportError:
            m = types.ModuleType(name)
            if name == "structlog":
                class _L:
                    def __getattr__(self, _): return lambda *a, **k: None
                m.get_logger = lambda *a, **k: _L()
            else:
                m.AsyncClient = object
            sys.modules[name] = m
    root = Path(__file__).resolve().parents[3] / "ai-stack" / "mcp-servers"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from shared.ssrf_protection import assert_safe_outbound_url
    return assert_safe_outbound_url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def guarded_fetch(url: str, *, timeout: float = 20.0, etag: str | None = None) -> dict[str, Any]:
    """SSRF-guarded (every redirect hop) + robots.txt-respecting GET; size-capped."""
    guard = _load_guard()
    opener = urllib.request.build_opener(_NoRedirect)
    cur = url
    for _ in range(MAX_REDIRECTS + 1):
        guard(cur, purpose="frontier_scan")
        p = urlparse(cur)
        rp = urllib.robotparser.RobotFileParser()
        try:
            rq = urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers={"User-Agent": UA})
            with opener.open(rq, timeout=timeout) as rr:
                rp.parse(rr.read(200_000).decode("utf-8", "replace").splitlines())
            if not rp.can_fetch(UA, cur):
                raise PermissionError(f"robots.txt disallows {cur}")
        except urllib.error.HTTPError:
            pass  # missing/blocked robots.txt -> no restriction published
        hdr = {"User-Agent": UA, "Accept": "text/html,text/plain,application/json;q=0.9"}
        if etag:
            hdr["If-None-Match"] = etag
        try:
            with opener.open(urllib.request.Request(cur, headers=hdr), timeout=timeout) as resp:
                return {"text": resp.read(MAX_BYTES).decode("utf-8", "replace"),
                        "etag": resp.headers.get("ETag")}
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return {"not_modified": True, "etag": etag}
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                cur = urljoin(cur, e.headers["Location"])
                continue
            raise
    raise RuntimeError("too many redirects")
