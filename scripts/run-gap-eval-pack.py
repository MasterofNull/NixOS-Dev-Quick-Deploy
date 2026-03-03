#!/usr/bin/env python3
"""
Run targeted harness eval cases and record aggregate score into scores.sqlite.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES_FILE = ROOT / "data" / "harness-gap-eval-pack.json"
DEFAULT_SCORES_DB = ROOT / "ai-stack" / "eval" / "results" / "scores.sqlite"


def _read_api_key() -> str:
    if os.getenv("HYBRID_API_KEY"):
        return os.getenv("HYBRID_API_KEY", "").strip()
    for candidate in (
        os.getenv("HYBRID_API_KEY_FILE", ""),
        "/run/secrets/hybrid_coordinator_api_key",
        "/run/secrets/hybrid_api_key",
    ):
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            try:
                return path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
    return ""


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _eval_via_query(
    hybrid_url: str,
    case: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float,
) -> bool:
    """Fallback evaluator when /harness/eval is unavailable/slow."""
    endpoint = hybrid_url.rstrip("/") + "/query"
    payload = {
        "query": case.get("query", ""),
        "mode": case.get("mode", "auto"),
        "prefer_local": True,
        "limit": 5,
        "generate_response": False,
        "context": {"skip_gap_tracking": True, "source": "gap-eval-pack"},
    }
    resp = _post_json(endpoint, payload, headers, timeout=timeout)
    expected = [str(k).strip().lower() for k in case.get("expected_keywords", []) if str(k).strip()]
    if not expected:
        return True
    hay = []
    if isinstance(resp.get("response"), str):
        hay.append(resp["response"].lower())
    for bucket in ("combined_results", "semantic_results", "keyword_results"):
        rows = resp.get(bucket) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload_row = row.get("payload", {})
            if isinstance(payload_row, dict):
                hay.append(" ".join(str(v) for v in payload_row.values()).lower())
    blob = "\n".join(hay)
    hits = sum(1 for kw in expected if kw in blob)
    ratio = hits / len(expected)
    return ratio >= 0.4


def _ensure_scores_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS eval_scores (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp TEXT NOT NULL,
          config TEXT NOT NULL,
          passed INTEGER NOT NULL,
          total INTEGER NOT NULL,
          pct_passed INTEGER NOT NULL,
          threshold INTEGER NOT NULL,
          strategy_tag TEXT
        );
        """
    )
    try:
        conn.execute("ALTER TABLE eval_scores ADD COLUMN strategy_tag TEXT;")
    except sqlite3.OperationalError:
        pass


def _record_scores(
    db_path: Path,
    *,
    timestamp: str,
    config_name: str,
    passed: int,
    total: int,
    pct_passed: int,
    threshold: int,
    strategy_tag: str,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_scores_schema(conn)
        conn.execute(
            """
            INSERT INTO eval_scores (timestamp, config, passed, total, pct_passed, threshold, strategy_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (timestamp, config_name, passed, total, pct_passed, threshold, strategy_tag),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Run harness gap eval pack and store aggregate score.")
    ap.add_argument("--cases", default=str(DEFAULT_CASES_FILE), help="Path to eval cases JSON.")
    ap.add_argument("--hybrid-url", default=os.getenv("HYB_URL", "http://127.0.0.1:8003"), help="Hybrid coordinator base URL.")
    ap.add_argument("--scores-db", default=str(DEFAULT_SCORES_DB), help="scores.sqlite path.")
    ap.add_argument("--threshold", type=int, default=75, help="Required pass percent.")
    ap.add_argument("--timeout", type=float, default=25.0, help="Per-case HTTP timeout seconds.")
    ap.add_argument("--strategy", default="gap_pack_v1", help="Strategy tag for leaderboard.")
    args = ap.parse_args()

    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"ERROR: cases file not found: {cases_path}", file=sys.stderr)
        return 2

    data = json.loads(cases_path.read_text(encoding="utf-8"))
    cases: List[Dict[str, Any]] = data.get("cases", [])
    if not cases:
        print("ERROR: no cases in eval pack", file=sys.stderr)
        return 2

    api_key = _read_api_key()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    total = len(cases)
    passed = 0
    failures: List[str] = []

    endpoint = args.hybrid_url.rstrip("/") + "/harness/eval"
    for case in cases:
        payload = {
            "query": case.get("query", ""),
            "expected_keywords": case.get("expected_keywords", []),
            "mode": case.get("mode", "auto"),
        }
        cid = str(case.get("id", "unknown"))
        try:
            resp = _post_json(endpoint, payload, headers, timeout=min(args.timeout, 8.0))
            ok = bool(resp.get("passed", False))
        except Exception:
            # /harness/eval can be unavailable during model churn; fallback keeps
            # the pack useful by evaluating retrieval quality via /query.
            try:
                ok = _eval_via_query(args.hybrid_url, case, headers, timeout=args.timeout)
            except urllib.error.HTTPError as exc:
                failures.append(f"{cid}: http_{exc.code}")
                print(f"FAIL {cid}: HTTP {exc.code}")
                continue
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{cid}: {type(exc).__name__}")
                print(f"FAIL {cid}: {exc}")
                continue

        if ok:
            passed += 1
            print(f"PASS {cid}")
        else:
            failures.append(f"{cid}: failed")
            print(f"FAIL {cid}: eval_failed")

    pct = int(round((passed / total) * 100)) if total else 0
    ts = datetime.now(tz=timezone.utc).isoformat()
    _record_scores(
        Path(args.scores_db),
        timestamp=ts,
        config_name=f"harness-gap-pack:{cases_path.name}",
        passed=passed,
        total=total,
        pct_passed=pct,
        threshold=int(args.threshold),
        strategy_tag=args.strategy,
    )

    print("")
    print(f"Gap eval pack: {passed}/{total} passed ({pct}%) threshold={args.threshold}% strategy={args.strategy}")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"- {f}")

    if pct < int(args.threshold):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
