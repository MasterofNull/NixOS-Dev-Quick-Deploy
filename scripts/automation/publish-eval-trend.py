#!/usr/bin/env python3
"""
publish-eval-trend.py — Phase 43 (PAR-011): Score trend publication.

Reads the eval_scores table from scores.sqlite and emits an eval-trend.json
artifact summarising recent runs, delta vs previous, and regression status.

Usage:
    publish-eval-trend.py [--scores-db PATH] [--output PATH] [--window N]
                          [--threshold N] [--strategy STRATEGY]

Output JSON schema:
    {
      "generated_at_epoch_s": int,
      "strategy": str,
      "window": int,           # number of recent runs examined
      "total_runs": int,
      "latest": { timestamp, score, passed, total, strategy_tag },
      "previous": { ... } | null,
      "delta_pct": float | null,   # latest.score - previous.score
      "trend": "improving" | "stable" | "degrading" | "insufficient_data",
      "threshold": int,
      "regression": bool,          # true if latest.score < threshold
      "runs": [ ... ]              # window most-recent runs
    }
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_SCORES_DB = Path(
    os.path.expanduser(
        os.getenv(
            "EVAL_SCORES_DB",
            "~/.local/share/nixos-ai-stack/eval/results/scores.sqlite",
        )
    )
)
DEFAULT_OUTPUT = Path(
    os.path.expanduser(
        os.getenv(
            "EVAL_TREND_OUTPUT",
            "~/.local/share/nixos-ai-stack/eval/results/eval-trend.json",
        )
    )
)
DEFAULT_WINDOW = 10
DEFAULT_THRESHOLD = 75


def _load_runs(db_path: Path, strategy: str, window: int) -> List[Dict[str, Any]]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE strategy_tag = ?" if strategy else ""
        params: list = [strategy] if strategy else []
        rows = conn.execute(
            f"""
            SELECT id, timestamp, config, passed, total, pct_passed, threshold, strategy_tag
            FROM eval_scores
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params + [window],
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _trend_label(delta: Optional[float]) -> str:
    if delta is None:
        return "insufficient_data"
    if delta > 2.0:
        return "improving"
    if delta < -2.0:
        return "degrading"
    return "stable"


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish eval score trend artifact.")
    ap.add_argument("--scores-db", default=str(DEFAULT_SCORES_DB), help="Path to scores.sqlite.")
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output eval-trend.json path.")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW, help="Number of recent runs to include.")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help="Regression threshold percent.")
    ap.add_argument("--strategy", default="", help="Filter by strategy_tag (empty = all).")
    args = ap.parse_args()

    db_path = Path(args.scores_db)
    runs = _load_runs(db_path, args.strategy, args.window)

    latest: Optional[Dict[str, Any]] = runs[0] if runs else None
    previous: Optional[Dict[str, Any]] = runs[1] if len(runs) > 1 else None

    delta: Optional[float] = None
    if latest and previous:
        delta = float(latest.get("pct_passed", 0)) - float(previous.get("pct_passed", 0))

    regression = bool(latest and int(latest.get("pct_passed", 0)) < args.threshold)

    payload: Dict[str, Any] = {
        "generated_at_epoch_s": int(time.time()),
        "strategy": args.strategy or "all",
        "window": args.window,
        "total_runs": len(runs),
        "latest": latest,
        "previous": previous,
        "delta_pct": round(delta, 1) if delta is not None else None,
        "trend": _trend_label(delta),
        "threshold": args.threshold,
        "regression": regression,
        "runs": runs,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    trend = payload["trend"]
    score_str = f"{latest['pct_passed']}%" if latest else "no data"
    delta_str = f" (delta {delta:+.1f}%)" if delta is not None else ""
    regression_str = " REGRESSION" if regression else ""
    print(f"eval-trend: {score_str}{delta_str} trend={trend}{regression_str} → {out}")

    return 1 if regression else 0


if __name__ == "__main__":
    raise SystemExit(main())
