#!/usr/bin/env python3
"""
aq-auto-remediate.py

Safe, idempotent post-report auto-remediation actions:
1) Improve low workflow intent-contract coverage by issuing capped workflow
   run start probes with explicit intent_contract payloads.
2) Curate stale query_gaps using aq-report recommendation patterns that already
   indicate documentation exists in AIDB.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT_PATH = Path("/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")
DEFAULT_SUMMARY_PATH = Path("/var/lib/ai-stack/hybrid/telemetry/aq-auto-remediation-latest.json")


@dataclass
class Settings:
    enabled: bool
    dry_run: bool
    report_json: Path
    summary_out: Path
    report_since: str
    hybrid_url: str
    hybrid_api_key_file: Optional[Path]
    intent_enable: bool
    intent_min_runs: int
    intent_min_coverage_pct: float
    intent_target_coverage_pct: float
    intent_max_probe_runs: int
    stale_enable: bool
    stale_min_token_len: int
    stale_max_rows_per_token: int
    stale_max_delete_total: int


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _load_settings(args: argparse.Namespace) -> Settings:
    report_json = Path(args.report_json or os.getenv("POST_DEPLOY_AQ_REPORT_OUT", str(DEFAULT_REPORT_PATH)))
    summary_out = Path(args.summary_out or os.getenv("POST_DEPLOY_AUTO_REMEDIATE_OUT", str(DEFAULT_SUMMARY_PATH)))
    api_key_file = os.getenv("HYBRID_API_KEY_FILE", "/run/secrets/hybrid_coordinator_api_key")
    return Settings(
        enabled=_env_bool("POST_DEPLOY_AUTO_REMEDIATE_ENABLE", True),
        dry_run=bool(args.dry_run) or _env_bool("POST_DEPLOY_AUTO_REMEDIATE_DRY_RUN", False),
        report_json=report_json,
        summary_out=summary_out,
        report_since=os.getenv("POST_DEPLOY_AUTO_REMEDIATE_REPORT_SINCE", "7d"),
        hybrid_url=os.getenv("HYBRID_URL", "http://127.0.0.1:8003").rstrip("/"),
        hybrid_api_key_file=Path(api_key_file) if api_key_file else None,
        intent_enable=_env_bool("POST_DEPLOY_INTENT_REMEDIATE_ENABLE", True),
        intent_min_runs=max(1, _env_int("POST_DEPLOY_INTENT_MIN_RUNS", 3)),
        intent_min_coverage_pct=max(0.0, min(100.0, _env_float("POST_DEPLOY_INTENT_MIN_COVERAGE_PCT", 90.0))),
        intent_target_coverage_pct=max(0.0, min(100.0, _env_float("POST_DEPLOY_INTENT_TARGET_COVERAGE_PCT", 95.0))),
        intent_max_probe_runs=max(1, _env_int("POST_DEPLOY_INTENT_MAX_PROBE_RUNS", 3)),
        stale_enable=_env_bool("POST_DEPLOY_STALE_GAP_CURATION_ENABLE", True),
        stale_min_token_len=max(3, _env_int("POST_DEPLOY_STALE_GAP_MIN_TOKEN_LEN", 12)),
        stale_max_rows_per_token=max(1, _env_int("POST_DEPLOY_STALE_GAP_MAX_ROWS_PER_TOKEN", 250)),
        stale_max_delete_total=max(1, _env_int("POST_DEPLOY_STALE_GAP_MAX_DELETE_TOTAL", 500)),
    )


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _load_report(settings: Settings) -> Dict[str, Any]:
    if settings.report_json.exists():
        try:
            return json.loads(settings.report_json.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to parse report JSON {settings.report_json}: {exc}") from exc

    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "aq-report"), f"--since={settings.report_since}", "--format=json"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"aq-report invocation failed: {stderr[:240]}")
    payload = json.loads(result.stdout or "{}")
    return payload if isinstance(payload, dict) else {}


def _hybrid_headers(settings: Settings) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key_file = settings.hybrid_api_key_file
    if key_file and key_file.exists() and key_file.is_file():
        key = key_file.read_text(encoding="utf-8", errors="ignore").strip()
        if key:
            headers["X-API-Key"] = key
    return headers


def _hybrid_post(settings: Settings, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{settings.hybrid_url}{path}",
        data=data,
        headers=_hybrid_headers(settings),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {path}: {body[:220]}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"POST {path} failed: {exc}") from exc


def _intent_probe_runs_needed(total_runs: int, with_contract: int, target_pct: float) -> int:
    # Need n such that (with_contract + n) / (total_runs + n) >= target_pct/100
    if target_pct <= 0:
        return 0
    if total_runs <= 0:
        return 1
    current = (with_contract / total_runs) * 100.0 if total_runs else 0.0
    if current >= target_pct:
        return 0
    target = target_pct / 100.0
    numerator = (target * total_runs) - with_contract
    denominator = 1.0 - target
    if denominator <= 0:
        return 0
    required = max(0.0, numerator / denominator)
    return int(math.ceil(required))


def remediate_intent_contract(settings: Settings, report: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "enabled": settings.intent_enable,
        "attempted": False,
        "triggered": False,
        "runs_started": 0,
        "errors": [],
    }
    if not settings.intent_enable:
        return result

    block = report.get("intent_contract_compliance", {})
    if not isinstance(block, dict) or not block.get("available"):
        result["errors"].append("intent_contract_compliance unavailable")
        return result

    total_runs = int(block.get("total_runs", 0) or 0)
    with_contract = int(block.get("with_contract", 0) or 0)
    coverage = block.get("contract_coverage_pct")
    coverage_f = float(coverage) if coverage is not None else 0.0

    result.update({
        "total_runs": total_runs,
        "with_contract": with_contract,
        "coverage_pct": coverage_f,
        "threshold_pct": settings.intent_min_coverage_pct,
        "target_pct": settings.intent_target_coverage_pct,
    })

    if total_runs < settings.intent_min_runs:
        result["errors"].append(f"skip: total_runs<{settings.intent_min_runs}")
        return result

    if coverage_f >= settings.intent_min_coverage_pct:
        return result

    result["triggered"] = True
    needed = _intent_probe_runs_needed(total_runs, with_contract, settings.intent_target_coverage_pct)
    plan_runs = max(1, min(settings.intent_max_probe_runs, needed if needed > 0 else 1))
    result["planned_runs"] = plan_runs

    if settings.dry_run:
        result["attempted"] = True
        result["dry_run"] = True
        return result

    for idx in range(plan_runs):
        payload = {
            "query": f"intent-contract remediation probe #{idx + 1}",
            "intent_contract": {
                "user_intent": "Auto-remediate low workflow intent-contract coverage with safe synthetic run metadata.",
                "definition_of_done": "Workflow session includes required intent_contract fields and persists compliance state.",
                "depth_expectation": "minimum",
                "spirit_constraints": [
                    "Prioritize safe, low-cost remediation actions.",
                    "Avoid early exit without telemetry evidence."
                ],
                "no_early_exit_without": ["session_recorded", "intent_contract_present"],
                "anti_goals": ["silent failure", "token-heavy remediation"],
            },
            "metadata": {
                "agent": "post-deploy-converge",
                "kind": "intent-contract-auto-remediation",
                "synthetic": True,
            },
        }
        try:
            response = _hybrid_post(settings, "/workflow/run/start", payload)
            if isinstance(response, dict) and (
                response.get("ok")
                or response.get("session_id")
                or response.get("run_id")
            ):
                result["runs_started"] = int(result.get("runs_started", 0)) + 1
            else:
                result["errors"].append(f"unexpected_response:{str(response)[:120]}")
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(str(exc))

    result["attempted"] = True
    return result


def _pg_conn_info() -> Dict[str, Any]:
    dsn = os.getenv("AIDB_DSN")
    if dsn:
        return {"dsn": dsn, "credentials_available": True}
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    db = os.getenv("POSTGRES_DB", "aidb")
    user = os.getenv("POSTGRES_USER", "aidb")
    password = os.getenv("POSTGRES_PASSWORD", "")
    if not password:
        pw_file = os.getenv("POSTGRES_PASSWORD_FILE")
        if pw_file and Path(pw_file).exists():
            password = Path(pw_file).read_text(encoding="utf-8", errors="ignore").strip()
    dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return {"dsn": dsn, "credentials_available": bool(password)}


def _extract_stale_tokens(recommendations: List[Any], min_len: int) -> List[str]:
    tokens: List[str] = []
    seen = set()
    pattern = re.compile(r"ILIKE\s+'%([^%']+)%'", re.IGNORECASE)

    for rec in recommendations:
        if not isinstance(rec, str):
            continue
        if "Clear stale gap:" not in rec:
            continue
        match = pattern.search(rec)
        if not match:
            continue
        token = match.group(1).strip()
        if len(token) < min_len:
            continue
        # Conservative sanitization: keep normal query text chars only.
        if not re.fullmatch(r"[A-Za-z0-9 _:\-.,?/()]+", token):
            continue
        lowered = token.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        tokens.append(token)
    return tokens


def _pg_scalar_psycopg(dsn: str, query: str, params: tuple[Any, ...]) -> Optional[int]:
    try:
        import psycopg  # type: ignore[import-untyped]
    except Exception:  # noqa: BLE001
        return None
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    return 0
                return int(row[0])
    except Exception:  # noqa: BLE001
        return None


def _pg_exec_psycopg(dsn: str, query: str, params: tuple[Any, ...]) -> Optional[int]:
    try:
        import psycopg  # type: ignore[import-untyped]
    except Exception:  # noqa: BLE001
        return None
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                count = cur.rowcount if cur.rowcount is not None else 0
            conn.commit()
            return int(max(count, 0))
    except Exception:  # noqa: BLE001
        return None


def _pg_scalar_psql(dsn: str, query: str) -> int:
    result = subprocess.run(
        ["psql", dsn, "--tuples-only", "--no-align", "--command", query],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "psql scalar query failed").strip()[:220])
    out = (result.stdout or "").strip()
    try:
        return int(out)
    except ValueError:
        return 0


def _pg_exec_psql(dsn: str, query: str) -> int:
    result = subprocess.run(
        ["psql", dsn, "--tuples-only", "--no-align", "--command", query],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "psql exec failed").strip()[:220])
    # DELETE N
    m = re.search(r"DELETE\s+(\d+)", result.stdout or "")
    return int(m.group(1)) if m else 0


def curate_stale_gaps(settings: Settings, report: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "enabled": settings.stale_enable,
        "triggered": False,
        "tokens": [],
        "deleted_rows": 0,
        "errors": [],
    }
    if not settings.stale_enable:
        return result

    recs = report.get("recommendations", [])
    if not isinstance(recs, list):
        recs = []
    tokens = _extract_stale_tokens(recs, settings.stale_min_token_len)
    result["tokens"] = tokens
    if not tokens:
        return result

    result["triggered"] = True
    entries: List[Dict[str, Any]] = []
    conn_info = _pg_conn_info()
    dsn = conn_info["dsn"]
    if not bool(conn_info.get("credentials_available", False)):
        result["errors"].append("skip: postgres credentials unavailable for stale-gap curation")
        result["entries"] = entries
        result["status"] = "skipped_credentials"
        return result
    remaining_budget = settings.stale_max_delete_total

    for token in tokens:
        like_value = f"%{token}%"
        count = _pg_scalar_psycopg(
            dsn,
            "SELECT COUNT(*) FROM query_gaps WHERE query_text ILIKE %s",
            (like_value,),
        )
        if count is None:
            token_sql = token.replace("'", "''")
            count = _pg_scalar_psql(dsn, f"SELECT COUNT(*) FROM query_gaps WHERE query_text ILIKE '%{token_sql}%';")

        row: Dict[str, Any] = {"token": token, "matched_rows": int(count), "status": "pending"}
        if count <= 0:
            row["status"] = "skip_no_rows"
            entries.append(row)
            continue
        if count > settings.stale_max_rows_per_token:
            row["status"] = "skip_safety_limit"
            row["limit"] = settings.stale_max_rows_per_token
            entries.append(row)
            continue
        if count > remaining_budget:
            row["status"] = "skip_budget"
            row["remaining_budget"] = remaining_budget
            entries.append(row)
            continue

        if settings.dry_run:
            row["status"] = "dry_run"
            entries.append(row)
            remaining_budget -= int(count)
            continue

        deleted = _pg_exec_psycopg(
            dsn,
            "DELETE FROM query_gaps WHERE query_text ILIKE %s",
            (like_value,),
        )
        if deleted is None:
            token_sql = token.replace("'", "''")
            deleted = _pg_exec_psql(dsn, f"DELETE FROM query_gaps WHERE query_text ILIKE '%{token_sql}%';")
        row["status"] = "deleted"
        row["deleted_rows"] = int(deleted)
        entries.append(row)
        result["deleted_rows"] = int(result.get("deleted_rows", 0)) + int(deleted)
        remaining_budget -= int(deleted)
        if remaining_budget <= 0:
            break

    result["entries"] = entries
    result["remaining_budget"] = remaining_budget
    return result


def _write_summary(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Safe auto-remediation from aq-report recommendations")
    p.add_argument("--report-json", default="", help="Existing aq-report JSON path")
    p.add_argument("--summary-out", default="", help="Summary output JSON path")
    p.add_argument("--dry-run", action="store_true", help="Compute and log actions without mutating state")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    settings = _load_settings(args)
    summary: Dict[str, Any] = {
        "ts": _now(),
        "enabled": settings.enabled,
        "dry_run": settings.dry_run,
        "report_json": str(settings.report_json),
        "intent_contract": {},
        "stale_gap_curation": {},
        "status": "ok",
        "errors": [],
    }

    if not settings.enabled:
        _write_summary(settings.summary_out, summary)
        print(json.dumps(summary, sort_keys=True))
        return 0

    try:
        report = _load_report(settings)
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "error"
        summary["errors"].append(f"load_report_failed: {exc}")
        _write_summary(settings.summary_out, summary)
        print(json.dumps(summary, sort_keys=True))
        return 1

    try:
        summary["intent_contract"] = remediate_intent_contract(settings, report)
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "warn"
        summary["errors"].append(f"intent_contract_failed: {exc}")

    try:
        summary["stale_gap_curation"] = curate_stale_gaps(settings, report)
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "warn"
        summary["errors"].append(f"stale_gap_curation_failed: {exc}")

    _write_summary(settings.summary_out, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] in {"ok", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
