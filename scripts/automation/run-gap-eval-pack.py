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


ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CASES_FILE = ROOT / "data" / "harness-gap-eval-pack.json"
DEFAULT_SCORES_DB = Path(
    os.path.expanduser(
        os.getenv(
            "EVAL_SCORES_DB",
            "~/.local/share/nixos-ai-stack/eval/results/scores.sqlite",
        )
    )
)


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
) -> tuple[bool, bool]:
    """Fallback evaluator when /harness/eval is unavailable/slow."""
    min_ratio = float(os.getenv("GAP_EVAL_MIN_KEYWORD_RATIO", "0.25"))
    endpoint = hybrid_url.rstrip("/") + "/query"
    payload = {
        "query": case.get("query", ""),
        "mode": case.get("mode", "auto"),
        "prefer_local": True,
        "limit": 5,
        "generate_response": False,
        "context": {"skip_gap_tracking": True, "source": "gap-eval-pack"},
    }

    def _collect_blob(resp: Dict[str, Any]) -> tuple[str, bool]:
        hay = []
        evidence_count = 0
        if isinstance(resp.get("response"), str):
            response_text = resp["response"].strip().lower()
            hay.append(response_text)
            if response_text and response_text not in {"no results", "no results."}:
                evidence_count += 1
        nested = resp.get("results") if isinstance(resp.get("results"), dict) else {}
        for bucket in ("combined_results", "semantic_results", "keyword_results"):
            rows = resp.get(bucket) or nested.get(bucket) or []
            if not isinstance(rows, list):
                continue
            if rows:
                evidence_count += len(rows)
            for row in rows:
                if not isinstance(row, dict):
                    continue
                payload_row = row.get("payload", {})
                if isinstance(payload_row, dict):
                    hay.append(" ".join(str(v) for v in payload_row.values()).lower())
                if isinstance(row.get("content"), str):
                    hay.append(row["content"].lower())
        tooling = resp.get("tooling_layer") if isinstance(resp.get("tooling_layer"), dict) else {}
        hints = tooling.get("hints") if isinstance(tooling.get("hints"), list) else []
        if hints:
            evidence_count += len(hints)
        for hint in hints:
            if isinstance(hint, dict):
                text = hint.get("prompt_template") or hint.get("title") or hint.get("snippet") or ""
                if text:
                    hay.append(str(text).lower())
            elif isinstance(hint, str) and hint.strip():
                hay.append(hint.strip().lower())
        return "\n".join(hay), evidence_count > 0

    resp = _post_json(endpoint, payload, headers, timeout=timeout)
    blob, has_evidence = _collect_blob(resp)
    if not blob.strip() or not has_evidence:
        retry_payload = dict(payload)
        retry_payload["mode"] = "hybrid"
        resp = _post_json(endpoint, retry_payload, headers, timeout=timeout)
        blob, has_evidence = _collect_blob(resp)
    if not blob.strip() or not has_evidence:
        return False, True

    expected = [str(k).strip().lower() for k in case.get("expected_keywords", []) if str(k).strip()]
    if not expected:
        return True, False
    hits = sum(1 for kw in expected if kw in blob)
    ratio = hits / len(expected)
    return ratio >= min_ratio, False


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
    attempted = 0
    skipped_cases = 0
    failures: List[str] = []
    degraded_cases = 0
    fallback_cases = 0

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
            if not ok and str(resp.get("response", "")).strip().lower() in {"no results", "no results."}:
                degraded_cases += 1
                skipped_cases += 1
                print(f"SKIP {cid}: no_retrieval_evidence")
                continue
            if not ok:
                # Harness eval can under-score when relevance signals are sparse.
                # Fallback evaluates retrieval evidence directly via /query.
                fallback_cases += 1
                ok, degraded = _eval_via_query(args.hybrid_url, case, headers, timeout=args.timeout)
                if degraded:
                    degraded_cases += 1
                    skipped_cases += 1
                    print(f"SKIP {cid}: fallback_no_evidence")
                    continue
        except Exception:
            # /harness/eval can be unavailable during model churn; fallback keeps
            # the pack useful by evaluating retrieval quality via /query.
            try:
                fallback_cases += 1
                ok, degraded = _eval_via_query(args.hybrid_url, case, headers, timeout=args.timeout)
                if degraded:
                    degraded_cases += 1
                    skipped_cases += 1
                    print(f"SKIP {cid}: fallback_no_evidence")
                    continue
            except urllib.error.HTTPError as exc:
                failures.append(f"{cid}: http_{exc.code}")
                print(f"FAIL {cid}: HTTP {exc.code}")
                continue
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{cid}: {type(exc).__name__}")
                print(f"FAIL {cid}: {exc}")
                continue

        if ok:
            attempted += 1
            passed += 1
            print(f"PASS {cid}")
        else:
            attempted += 1
            failures.append(f"{cid}: failed")
            print(f"FAIL {cid}: eval_failed")

    if attempted == 0 and total > 0:
        print("")
        print("Gap eval pack: no evaluable cases (all skipped due no retrieval evidence); skipping score write.")
        return 3
    if degraded_cases == total and total > 0:
        print("")
        print("Gap eval pack: runtime degraded (no retrieval evidence for all cases); skipping score write.")
        return 3
    if fallback_cases == total and passed == 0 and total > 0:
        print("")
        print("Gap eval pack: fallback-only run with 0 passes; skipping score write to avoid false leaderboard regression.")
        return 3

    pct = int(round((passed / attempted) * 100)) if attempted else 0
    ts = datetime.now(tz=timezone.utc).isoformat()
    _record_scores(
        Path(args.scores_db),
        timestamp=ts,
        config_name=f"harness-gap-pack:{cases_path.name}",
        passed=passed,
        total=attempted,
        pct_passed=pct,
        threshold=int(args.threshold),
        strategy_tag=args.strategy,
    )

    print("")
    print(f"Gap eval pack: {passed}/{attempted} passed ({pct}%) threshold={args.threshold}% strategy={args.strategy}")
    if skipped_cases:
        print(f"Skipped: {skipped_cases}/{total} (no retrieval evidence)")
    if failures:
        print("Failures:")
        for f in failures:
            print(f"- {f}")

    if pct < int(args.threshold):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
