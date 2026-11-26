"""aq-baseline core: reproducible measurement snapshots over EXISTING producers (experience-capture PRD, S-M1).

Contract (DESIGN.md "Measurement baseline contract", AT-1..AT-5):
  * snapshot  reads producers, stores each input as a digest-addressed copy, writes one row per metric.
  * verify    recomputes every row from the RETAINED copies only (never live producers) and must equal the stored rows.
  * compare   binds a pre/post snapshot pair to a subject and an effective start; rejects with a named reason.
No model, no network, no run-event dependency. A metric with no producer is value=None + gap, never 0.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

DEFINITION_FLOOR_N = 20  # independent units for any rate/improvement claim
DISPLAY_N = 5  # display-only threshold
CONCENTRATION_THRESHOLD = 0.30  # trigger for inspection, not proof; rows carry both numbers
STALE_DAYS = 35
BOOTSTRAP_B = 2000
SNAPSHOT_FILE = "baseline-snapshots.jsonl"
DISABLED_MARKER = "baseline-schedule.disabled"
INPUT_DIR = "baseline-inputs"
METRIC_DEFINITIONS_VERSION = "s-m1.v1"
LOCK_FILE = ".baseline.lock"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

Row = dict[str, Any]

# Registry status -> S-M1 own eligibility rule (no Phase 2 predicate).
_SUCCEEDED = {"done"}
_FAILED = {"failed"}
_INFRA = {"timeout", "failed_orphaned_no_output"}
_IN_FLIGHT = {"running", "started", "queued", "pending"}
_SKIPPED = {"cancelled"}
_UNKNOWN_STATUS = {"orphaned", "stale", "partial-success"}


class BaselineError(Exception):
    """Operator-facing failure (bad args, rejected compare, unreadable store)."""


class ScheduleDisabled(BaselineError):
    """A scheduled tick found the rollback marker; nothing was written."""


# --------------------------------------------------------------------------- time / paths

def parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc() -> datetime:
    override = os.environ.get("AQ_BASELINE_NOW")  # test clock
    return parse_ts(override) if override else datetime.now(timezone.utc)


def main_root() -> Path:
    env = os.environ.get("AQ_BASELINE_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    try:
        common = subprocess.run(
            ["git", "-C", str(here), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        if common:
            return Path(common).parent
    except (OSError, subprocess.SubprocessError):
        pass
    return here.parents[2]


def telemetry_dir(root: Path) -> Path:
    return root / ".agents" / "telemetry"


def _training_loop_path(deleg: Path) -> Path:
    """Same resolution as the owner (scripts/ai/aq-local-training-loop RESULTS_LOG): TELEMETRY_DIR is the primary
    store; the delegation-dir file is only its PermissionError fallback (_persist_result)."""
    primary = Path(os.environ.get("TELEMETRY_DIR", "/var/lib/ai-stack/hybrid/telemetry")) / "training-loop-results.jsonl"
    return primary if primary.is_file() else deleg / "training-loop-results.jsonl"


def _rsi_incidents_path(root: Path) -> Path:
    """Read-only resolution with the same precedence as the ledger's owner (scripts/ai/lib/rsi_paths.py):
    PRSI_INCIDENTS_FILE, RSI_RUNTIME_DIR, RSI_STATE_DIR are explicit (a missing or unreadable explicit ledger
    yields no_producer, never the seed); otherwise the default state ledger when it is readable (no write access
    needed); the tracked seed only when no override is set and no state ledger exists."""
    lib = str(Path(__file__).resolve().parent)
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import rsi_paths
    env_file = os.environ.get("PRSI_INCIDENTS_FILE")
    if env_file:
        return Path(env_file)
    for var in ("RSI_RUNTIME_DIR", "RSI_STATE_DIR"):
        if os.environ.get(var):
            return Path(os.environ[var]) / rsi_paths.LEDGER
    state = Path(rsi_paths.DEFAULT_STATE_DIR) / rsi_paths.LEDGER
    if state.is_file() and os.access(state, os.R_OK):
        return state
    return rsi_paths.seed_dir(root) / rsi_paths.LEDGER


def producer_paths(root: Path) -> dict[str, Path]:
    deleg = Path(os.environ.get("AQ_DELEGATION_DIR") or root / ".agents" / "delegation")
    return {
        "registry": deleg / "registry.jsonl",
        "outcome_receipts": deleg / "outcome-receipts.jsonl",
        "aq_land_failures": deleg / "outputs" / "aq-land" / "failure-events.jsonl",
        "training_loop": _training_loop_path(deleg),
        "rsi_incidents": _rsi_incidents_path(root),
        "aq_report": Path(os.environ.get("AQ_REPORT_LATEST_JSON", "/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json")),
    }


def _leanctx_bytes() -> tuple[str, bytes] | None:
    override = os.environ.get("AQ_BASELINE_LEANCTX_JSON")
    if override:
        p = Path(override)
        return (str(p), p.read_bytes()) if p.is_file() else None
    try:
        r = subprocess.run(["lean-ctx", "gain", "--by-tool", "--json"], capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return ("cmd:lean-ctx gain --by-tool --json", r.stdout)


def read_live_inputs(root: Path) -> dict[str, tuple[str, bytes]]:
    """name -> (origin, exact bytes). Absent producers are simply absent (rows then carry a gap, never 0)."""
    out: dict[str, tuple[str, bytes]] = {}
    for name, p in producer_paths(root).items():
        try:
            if p.is_file():
                out[name] = (str(p), p.read_bytes())
        except OSError:
            continue
    lc = _leanctx_bytes()
    if lc:
        out["leanctx_gain"] = lc
    return out


# --------------------------------------------------------------------------- store

def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


@contextlib.contextmanager
def store_lock(tdir: Path) -> Iterator[None]:
    tdir.mkdir(parents=True, exist_ok=True)
    fd = os.open(tdir / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)  # closing releases the flock


def _secure_append(path: Path, text: str) -> None:
    """Caller holds store_lock. Full-write loop + fsync so a short write never leaves a torn row set unnoticed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        _write_all(fd, text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def retain_input(tdir: Path, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    d = tdir / INPUT_DIR
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    target = d / digest
    if not target.exists():
        tmp = d / f".{digest}.{os.getpid()}.{os.urandom(4).hex()}.tmp"  # unique: concurrent writers never share a temp
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            _write_all(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, target)
    os.chmod(target, 0o600)
    return digest


def load_rows(tdir: Path) -> list[Row]:
    path = tdir / SNAPSHOT_FILE
    if not path.is_file():
        return []
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def snapshot_rows(tdir: Path, snapshot_id: str) -> list[Row]:
    rows: dict[str, Row] = {}
    for r in load_rows(tdir):
        if r.get("snapshot_id") != snapshot_id:
            continue
        mid = str(r.get("metric_id"))
        if mid in rows and _canonical(rows[mid]) != _canonical(r):
            raise BaselineError(f"snapshot {snapshot_id} has conflicting rows for {mid}")
        rows[mid] = r  # identical duplicates (older same-second appends) collapse to one
    if not rows:
        raise BaselineError(f"unknown snapshot {snapshot_id}")
    return list(rows.values())


# --------------------------------------------------------------------------- parsing helpers

def _jsonl(data: bytes | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in (data or b"").decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _json(data: bytes | None) -> Any:
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return None


def _in_window(ts: Any, window: tuple[datetime, datetime]) -> bool:
    if not isinstance(ts, str) or not ts:
        return False
    try:
        t = parse_ts(ts)
    except ValueError:
        return False
    return window[0] <= t <= window[1]


def _ts_key(value: Any) -> datetime:
    """Chronological sort key; mixed Z / +00:00 / -08:00 strings must not be ordered lexically."""
    try:
        return parse_ts(str(value))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _digest(items: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(items)).encode()).hexdigest()


def _membership(ids: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"count": len(ids), "digest": _digest(ids)}
    if len(ids) <= 500:
        out["ids"] = sorted(ids)
    return out


def _concentration(parts: dict[str, float]) -> tuple[bool, float | None, float | None]:
    total = sum(parts.values())
    if total <= 0 or not parts:
        return False, None, None
    top = max(parts.values())
    share = top / total
    return share > CONCENTRATION_THRESHOLD, round(share, 6), total - top


def new_row(metric_id: str, *, improves_when: str, unit_label: str, time_coverage: str, producer: str,
            eligibility_filter: str, **kw: Any) -> Row:
    row: Row = {
        "metric_id": metric_id, "improves_when": improves_when, "unit_label": unit_label,
        "time_coverage": time_coverage, "producer": producer, "eligibility_filter": eligibility_filter,
        "numerator": None, "denominator": None, "value": None, "n": 0, "unknown_n": 0, "in_flight_n": 0,
        "skipped_n": 0, "observations": [], "observation_membership": None, "concentrated": False,
        "value_ex_top": None, "top_share": None, "concentration_threshold": CONCENTRATION_THRESHOLD,
        "gap": None, "display": "descriptive",
    }
    row.update(kw)
    return row


def _no_data(metric_id: str, gap: str, *, improves_when: str, unit_label: str, producer: str, detail: str,
             time_coverage: str = "current-only") -> Row:
    return new_row(metric_id, improves_when=improves_when, unit_label=unit_label, time_coverage=time_coverage,
                   producer=producer, eligibility_filter=detail, gap=gap, display="no_data")


# --------------------------------------------------------------------------- metrics

def _registry_ts(r: dict[str, Any]) -> Any:
    return r.get("created") or r.get("created_at")


def _classify_registry(r: dict[str, Any]) -> str:
    status = str(r.get("status") or "")
    outcome = str(r.get("outcome") or "")
    if status in _IN_FLIGHT:
        return "in_flight"
    if status in _SKIPPED:
        return "skipped"
    if status in _INFRA:
        return "infra"
    if status in _UNKNOWN_STATUS:
        return "unknown"
    if status in _FAILED:
        return "failed"
    if status in _SUCCEEDED:
        if outcome == "refused":
            return "blocked"
        if outcome in ("failed", "FAIL"):
            return "unknown"  # contradictory success + error evidence counts neutral
        return "succeeded"
    return "unknown"


def _registry_rows(data: bytes | None, window: tuple[datetime, datetime], lane_filter: str | None) -> list[Row]:
    producer = "registry.jsonl"
    if data is None:
        return [_no_data("delegation_success_raw", "no_producer", improves_when="up", unit_label="dispatch",
                         producer=producer, detail="registry.jsonl not found")]
    latest: dict[str, dict[str, Any]] = {}
    undated = 0
    for r in _jsonl(data):
        rid = str(r.get("id") or "")
        if not rid:
            continue
        if lane_filter and str(r.get("agent")) != lane_filter:
            continue
        if not _registry_ts(r):
            undated += 1
            continue
        if _in_window(_registry_ts(r), window):
            latest[rid] = r  # duplicate events for one dispatch collapse to the last record

    def cluster(recs: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
        by_key: dict[str, dict[str, Any]] = {}
        for rid, r in sorted(recs):
            pr = r.get("pr")
            key = f"pr:{pr}" if pr not in (None, "", "None") else f"dispatch:{rid}"
            prev = by_key.get(key)
            if prev is None or _ts_key(_registry_ts(r)) >= _ts_key(_registry_ts(prev)):
                by_key[key] = r  # retries linked to one PR cluster; the final attempt decides
        return list(by_key.items())

    by_lane: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for rid, r in latest.items():
        by_lane.setdefault(f"lane.{r.get('agent')}", []).append((rid, r))
    # clustering happens WITHIN each group: a PR worked by two lanes keeps one unit per lane row and one in "all"
    groups: dict[str, list[tuple[str, dict[str, Any]]]] = {"all": cluster(list(latest.items()))}
    for gname, recs in by_lane.items():
        groups[gname] = cluster(recs)

    rows: list[Row] = []
    for gname in sorted(groups):
        items = groups[gname]
        counts = {k: 0 for k in ("succeeded", "failed", "blocked", "infra", "unknown", "in_flight", "skipped")}
        obs: list[dict[str, Any]] = []
        outcome_unknown = 0
        for key, r in items:
            c = _classify_registry(r)
            counts[c] += 1
            if c in ("succeeded", "failed", "blocked"):
                obs.append({"u": key, "v": 1 if c == "succeeded" else 0})
            if c in ("succeeded", "failed") and str(r.get("outcome") or "unknown") in ("unknown", "None", ""):
                outcome_unknown += 1
        den = counts["succeeded"] + counts["failed"] + counts["blocked"]
        linked = sum(1 for k, _ in items if k.startswith("pr:"))
        rows.append(new_row(
            "delegation_success_raw" if gname == "all" else f"delegation_success_raw.{gname}",
            improves_when="up", unit_label="dispatch", time_coverage="windowed", producer=producer,
            eligibility_filter="registry status done|failed|refused-outcome; timeout/orphan-no-output as infra_n; "
                               "orphaned/stale/partial-success unknown; cancelled skipped; running in-flight; PR-linked retries cluster",
            numerator=counts["succeeded"], denominator=den, value=(counts["succeeded"] / den) if den else None,
            n=len(obs), unknown_n=counts["unknown"], in_flight_n=counts["in_flight"], skipped_n=counts["skipped"],
            observations=sorted(obs, key=lambda o: o["u"]),
            infra_n=counts["infra"], blocked_n=counts["blocked"], undated_n=undated if gname == "all" else 0,
            outcome_unknown_n=outcome_unknown, pr_linked_units=linked,
            display=_unit_display(len(obs)),
        ))
    return rows


def _unit_display(n: int) -> str:
    if n >= DEFINITION_FLOOR_N:
        return "eligible"
    return "counts_only" if n >= DISPLAY_N else "insufficient"


def _model_known_row(data: bytes | None, window: tuple[datetime, datetime], lane_filter: str | None) -> Row:
    if data is None:
        return _no_data("registry_model_known_share", "no_producer", improves_when="up", unit_label="dispatch",
                        producer="registry.jsonl", detail="registry.jsonl not found")
    latest: dict[str, dict[str, Any]] = {}
    for r in _jsonl(data):
        rid = str(r.get("id") or "")
        if rid and (not lane_filter or str(r.get("agent")) == lane_filter) and _in_window(_registry_ts(r), window):
            latest[rid] = r
    known = [rid for rid, r in latest.items() if str(r.get("model_effective")) not in ("None", "unknown", "n/a", "")]
    n = len(latest)
    return new_row("registry_model_known_share", improves_when="up", unit_label="dispatch", time_coverage="windowed",
                   producer="registry.jsonl", eligibility_filter="dated dispatches with model_effective not unknown/n/a",
                   numerator=len(known), denominator=n, value=(len(known) / n) if n else None, n=n,
                   unknown_n=n - len(known),
                   observations=[{"u": rid, "v": 1 if rid in known else 0} for rid in sorted(latest)],
                   display=_unit_display(n))


def _land_failure_rows(data: bytes | None, window: tuple[datetime, datetime]) -> list[Row]:
    producer = "outputs/aq-land/failure-events.jsonl"
    if data is None:
        gap_rows = [
            _no_data(mid, "no_producer", improves_when="down", unit_label="aggregate", producer=producer,
                     detail="failure-events.jsonl not found", time_coverage="windowed")
            for mid in ("aq_land_structured_failures", "receipt_mint_failures", "wasted_reviews")]
        return gap_rows
    events = _jsonl(data)
    all_kinds = [str(e.get("kind") or "") for e in events]
    in_win = [e for e in events if _in_window(e.get("at"), window)]

    def ev_key(e: dict[str, Any]) -> str:
        return f"{e.get('at')}|{e.get('head_sha')}|{e.get('kind')}|{e.get('stage')}"

    kinds: dict[str, float] = {}
    for e in in_win:
        kinds[str(e.get("kind"))] = kinds.get(str(e.get("kind")), 0) + 1
    conc, share, rest = _concentration(kinds)
    rows = [new_row(
        "aq_land_structured_failures", improves_when="down", unit_label="aggregate", time_coverage="windowed",
        producer=producer, eligibility_filter="failure-events.jsonl rows with `at` in window (records exist from aq-land #865 merge only)",
        value=len(in_win), n=len(in_win), observation_membership=_membership([ev_key(e) for e in in_win]),
        concentrated=conc, top_share=share, value_ex_top=rest, by_kind={k: int(v) for k, v in sorted(kinds.items())},
        display="insufficient" if len(in_win) < DEFINITION_FLOOR_N else "descriptive")]
    # Mint failures and wasted reviews: a quiet window and an unobserved failure both read as zero, so the
    # row stays no_producer until the producer has emitted at least one record of that kind (AT-3).
    for mid, token, why in (
            ("receipt_mint_failures", "mint", "aq-land raises Stop at mint and prints to stderr; no durable mint-failure kind"),
            ("wasted_reviews", "wasted", "no durable producer records repeat/wasted reviews on one head")):
        if any(token in k for k in all_kinds):
            hits = [e for e in in_win if token in str(e.get("kind"))]
            rows.append(new_row(mid, improves_when="down", unit_label="aggregate", time_coverage="windowed",
                                producer=producer, eligibility_filter=f"failure-events kind contains '{token}'",
                                value=len(hits), n=len(hits),
                                observation_membership=_membership([ev_key(e) for e in hits]),
                                display="insufficient" if len(hits) < DEFINITION_FLOOR_N else "descriptive"))
        else:
            rows.append(_no_data(mid, "no_producer", improves_when="down", unit_label="aggregate", producer=producer,
                                 detail=why, time_coverage="windowed"))
    return rows


def _rework_row(data: bytes | None, window: tuple[datetime, datetime]) -> Row:
    producer = "outcome-receipts.jsonl"
    if data is None:
        return _no_data("rework_rounds_per_pr", "no_producer", improves_when="down", unit_label="pr",
                        producer=producer, detail="outcome-receipts.jsonl not found", time_coverage="windowed")
    latest: dict[str, dict[str, Any]] = {}
    for r in _jsonl(data):
        if r.get("pr") is None or not _in_window(r.get("recorded_at"), window):
            continue
        key = str(r["pr"])
        prev = latest.get(key)
        if prev is None or _ts_key(r.get("recorded_at")) >= _ts_key(prev.get("recorded_at")):
            latest[key] = r  # repeated landing records for one PR count once
    obs: list[dict[str, Any]] = []
    unknown = 0
    for pr, r in sorted(latest.items(), key=lambda kv: kv[0]):
        rounds = r.get("request_changes_rounds")
        if isinstance(rounds, (int, float)) and not isinstance(rounds, bool):
            obs.append({"u": f"pr:{pr}", "v": rounds})
        else:
            unknown += 1  # zero is a value; missing is unknown
    total = sum(o["v"] for o in obs)
    return new_row("rework_rounds_per_pr", improves_when="down", unit_label="pr", time_coverage="windowed",
                   producer=producer, eligibility_filter="latest landing receipt per PR in window; request_changes_rounds present",
                   numerator=total, denominator=len(obs), value=(total / len(obs)) if obs else None, n=len(obs),
                   unknown_n=unknown, observations=obs, display=_unit_display(len(obs)))


def _training_row(data: bytes | None, window: tuple[datetime, datetime]) -> Row:
    producer = "training-loop-results.jsonl"
    if data is None:
        return _no_data("training_loop_pass_rate", "no_producer", improves_when="up", unit_label="aggregate",
                        producer=producer, detail="training-loop-results.jsonl not found", time_coverage="windowed")
    runs = [r for r in _jsonl(data) if _in_window(r.get("timestamp"), window)]
    ids = [str(r.get("run_id") or r.get("timestamp")) for r in runs]
    passed = sum(int(r.get("pass_count") or 0) for r in runs)
    cases = sum(int(r.get("cases_total") or 0) for r in runs)
    samples = sum(int(((r.get("ingest") or {}).get("samples_added")) or 0) for r in runs)
    return new_row("training_loop_pass_rate", improves_when="up", unit_label="aggregate", time_coverage="windowed",
                   producer=producer, eligibility_filter="runs with timestamp in window; sum(pass_count)/sum(cases_total)",
                   numerator=passed, denominator=cases, value=(passed / cases) if cases else None, n=len(runs),
                   observation_membership=_membership(ids), samples_added=samples,
                   display="insufficient" if len(runs) < DEFINITION_FLOOR_N else "descriptive")


def _rsi_row(data: bytes | None, window: tuple[datetime, datetime]) -> Row:
    producer = "rsi-incidents.json"
    doc = _json(data)
    incidents = doc.get("incidents") if isinstance(doc, dict) else None
    if not isinstance(incidents, dict):
        return _no_data("rsi_incident_count", "no_producer", improves_when="down", unit_label="aggregate",
                        producer=producer, detail="rsi-incidents.json missing or malformed", time_coverage="windowed")
    hit = {k: v for k, v in incidents.items() if isinstance(v, dict) and _in_window(v.get("first_seen"), window)}
    by_producer: dict[str, float] = {}
    for v in hit.values():
        by_producer[str(v.get("producer"))] = by_producer.get(str(v.get("producer")), 0) + 1
    conc, share, rest = _concentration(by_producer)
    return new_row("rsi_incident_count", improves_when="down", unit_label="aggregate", time_coverage="windowed",
                   producer=producer, eligibility_filter="incidents with first_seen in window (post-guard recurrence is not linkable)",
                   value=len(hit), n=len(hit), observation_membership=_membership(list(hit)), concentrated=conc,
                   top_share=share, value_ex_top=rest, by_producer={k: int(v) for k, v in sorted(by_producer.items())},
                   display="insufficient" if len(hit) < DEFINITION_FLOOR_N else "descriptive")


def _leanctx_row(data: bytes | None) -> Row:
    producer = "lean-ctx gain --by-tool --json"
    tools = _json(data)
    if not isinstance(tools, list):
        return _no_data("leanctx_token_savings", "no_producer", improves_when="up", unit_label="aggregate",
                        producer=producer, detail="lean-ctx gain output unavailable")
    saved = {str(t.get("tool")): float(t.get("saved_tokens") or 0) for t in tools if isinstance(t, dict)}
    base = {str(t.get("tool")): float(t.get("baseline_tokens") or 0) for t in tools if isinstance(t, dict)}
    tot_s, tot_b = sum(saved.values()), sum(base.values())
    conc, share, rest = _concentration({k: v for k, v in saved.items() if v > 0})
    top = max(saved, key=lambda k: saved[k]) if saved else None
    ex_top = None
    if top is not None and (tot_b - base[top]) > 0:
        ex_top = round((tot_s - saved[top]) / (tot_b - base[top]), 6)
    return new_row("leanctx_token_savings", improves_when="up", unit_label="aggregate", time_coverage="current-only",
                   producer=producer, eligibility_filter="all tools in the live gain output (primary = full population)",
                   numerator=tot_s, denominator=tot_b, value=(tot_s / tot_b) if tot_b else None, n=len(saved),
                   observation_membership=_membership(sorted(saved)), concentrated=conc, top_share=share,
                   value_ex_top=ex_top if rest is not None else None, top_contributor=top,
                   counterfactual="baseline_tokens as reported by lean-ctx per tool (unattributed; no per-tool counterfactual named)",
                   per_tool=[{"tool": k, "saved_tokens": saved[k], "baseline_tokens": base[k]} for k in sorted(saved)],
                   display="insufficient" if len(saved) < DEFINITION_FLOOR_N else "descriptive")


def _report_rows(data: bytes | None) -> list[Row]:
    producer = "latest-aq-report.json"
    doc = _json(data)
    if not isinstance(doc, dict):
        return [_no_data(mid, "no_producer", improves_when=iw, unit_label=ul, producer=producer,
                         detail="latest-aq-report.json unavailable")
                for mid, iw, ul in (("delegation_success_report", "up", "dispatch"), ("hint_adoption_observability", "up", "aggregate"),
                                    ("useful_ratio", "up", "aggregate"))]
    rows: list[Row] = []
    cr = ((doc.get("effectiveness_scorecard") or {}).get("completion_reliability")) or {}
    total, fails = cr.get("delegation_total"), cr.get("delegation_failures")
    if isinstance(total, int) and isinstance(fails, int) and total > 0:
        rows.append(new_row("delegation_success_report", improves_when="up", unit_label="dispatch",
                            time_coverage="current-only", producer=producer,
                            eligibility_filter=f"aq-report scorecard delegation window {cr.get('delegation_window_s')}s (separate population from the registry row)",
                            numerator=total - fails, denominator=total, value=(total - fails) / total, n=total,
                            report_generated_at=doc.get("generated_at"), display="descriptive"))
    else:
        rows.append(_no_data("delegation_success_report", "no_data", improves_when="up", unit_label="dispatch",
                             producer=producer, detail="scorecard has no delegation_total"))
    ha = doc.get("hint_adoption") or {}
    if isinstance(ha.get("total"), int) and ha["total"] > 0:
        rows.append(new_row("hint_adoption_observability", improves_when="up", unit_label="aggregate",
                            time_coverage="current-only", producer=producer,
                            eligibility_filter="OBSERVABILITY only: adoption is not a benefit metric",
                            numerator=ha.get("accepted"), denominator=ha["total"],
                            value=(ha.get("accepted") or 0) / ha["total"], n=ha["total"],
                            observation_membership={"count": ha["total"], "digest": None},
                            report_generated_at=doc.get("generated_at"),
                            display="descriptive"))
    ut = doc.get("useful_tokens") or {}
    rows.append(new_row("useful_ratio", improves_when="up", unit_label="aggregate", time_coverage="current-only",
                        producer=producer, eligibility_filter="blocker only: denominator undefined",
                        gap="no_denominator", value=None, display="no_data", blocker_status=ut.get("status"),
                        report_generated_at=doc.get("generated_at")))
    return rows


def compute_rows(inputs: dict[str, bytes], window: tuple[datetime, datetime], cohort: str) -> list[Row]:
    """Pure function of (input bytes, window, cohort): used by snapshot AND verify."""
    lane = None
    if cohort != "all":
        if not cohort.startswith("lane=") or len(cohort) <= 5:
            raise BaselineError(f"cohort must be 'all' or 'lane=<agent>', got {cohort!r}")
        lane = cohort[5:]
    rows: list[Row] = []
    rows += _registry_rows(inputs.get("registry"), window, lane)
    rows.append(_model_known_row(inputs.get("registry"), window, lane))
    rows += _land_failure_rows(inputs.get("aq_land_failures"), window)
    rows.append(_rework_row(inputs.get("outcome_receipts"), window))
    rows.append(_leanctx_row(inputs.get("leanctx_gain")))
    rows.append(_training_row(inputs.get("training_loop"), window))
    rows.append(_rsi_row(inputs.get("rsi_incidents"), window))
    rows += _report_rows(inputs.get("aq_report"))
    for r in rows:
        # AT-2: a current-only aggregate never receives a verdict; fewer than 20 memberships prints insufficient.
        if r["unit_label"] == "aggregate" and r["display"] not in ("no_data",):
            m = (r.get("observation_membership") or {}).get("count", r.get("n") or 0)
            r["display"] = "insufficient" if m < DEFINITION_FLOOR_N else "descriptive"
        if r["time_coverage"] == "windowed":
            r["window"] = {"start": fmt_ts(window[0]), "end": fmt_ts(window[1])}
    return sorted(rows, key=lambda r: r["metric_id"])


# --------------------------------------------------------------------------- rollback

def rollback(root: Path) -> Path:
    """Rollback order (DESIGN.md): 1. disable the schedule (a scheduled tick then refuses to write),
    2. archive (never delete, Rule 12) the snapshot file and retained inputs into a timestamped directory that
    is never reused or overwritten. Removing the aq-qa / aq-report / aq-pm-tracker checks is a code revert."""
    tdir = telemetry_dir(root)
    with store_lock(tdir):
        (tdir / DISABLED_MARKER).write_text(f"disabled {fmt_ts(now_utc())}\n", encoding="utf-8")
        base = root / ".agent" / "archive" / f"{now_utc().strftime('%Y%m%dT%H%M%SZ')}-aq-baseline"
        dest, n = base, 1
        while dest.exists():
            n += 1
            dest = base.with_name(f"{base.name}-{n}")
        dest.mkdir(parents=True)
        for name in (SNAPSHOT_FILE, INPUT_DIR):
            src = tdir / name
            if src.exists():
                shutil.move(str(src), str(dest / name))
    return dest


# --------------------------------------------------------------------------- snapshot / verify

def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_snapshot_id(*, subject: str, cohort: str, definition_version: str, horizon_days: int, min_effect: float,
                        captured_at: str, window: dict[str, str], input_digests: list[str], metric_ids: list[str]) -> str:
    return hashlib.sha256(_canonical({
        "subject": subject, "cohort": cohort, "definition_version": definition_version,
        "horizon_days": horizon_days, "min_effect": min_effect, "captured_at": captured_at, "window": window,
        "inputs": sorted(input_digests), "metrics": sorted(metric_ids)}).encode()).hexdigest()


def _repo_head(root: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def take_snapshot(root: Path, *, subject: str, cohort: str, definition_version: str, horizon_days: int,
                  min_effect: float, as_of: str | None, window_days: int,
                  scheduled: bool = False) -> tuple[str, list[Row]]:
    if window_days <= 0 or horizon_days <= 0:
        raise BaselineError("--window-days and --horizon-days must be positive")
    if not subject.strip():
        raise BaselineError("--subject is required")
    if not math.isfinite(min_effect) or min_effect < 0:
        raise BaselineError("--min-effect must be a finite number >= 0")
    captured = now_utc()
    end = parse_ts(as_of) if as_of else captured
    if end > captured:
        raise BaselineError(f"--as-of {fmt_ts(end)} is after capture time {fmt_ts(captured)}")
    window = (end - timedelta(days=window_days), end)
    tdir = telemetry_dir(root)
    live = read_live_inputs(root)
    inputs: list[dict[str, str]] = []
    raw: dict[str, bytes] = {}
    for name in sorted(live):
        origin, data = live[name]
        inputs.append({"name": name, "path": origin, "sha256": hashlib.sha256(data).hexdigest()})
        raw[name] = data
    rows = compute_rows(raw, window, cohort)
    win = {"start": fmt_ts(window[0]), "end": fmt_ts(window[1])}
    sid = compute_snapshot_id(subject=subject, cohort=cohort, definition_version=definition_version,
                              horizon_days=horizon_days, min_effect=min_effect, captured_at=fmt_ts(captured),
                              window=win, input_digests=[i["sha256"] + ":" + i["name"] for i in inputs],
                              metric_ids=[r["metric_id"] for r in rows])
    head = _repo_head(root)
    out: list[Row] = []
    for r in rows:
        out.append({"snapshot_id": sid, "captured_at": fmt_ts(captured), "input_window": win, "inputs": inputs,
                    "repo_head": head, "subject": subject, "cohort": cohort, "definition_version": definition_version,
                    "horizon_days": horizon_days, "min_effect": min_effect, **r})
    with store_lock(tdir):
        # marker check, input retention and append are one critical section: a rollback cannot interleave
        if scheduled and (tdir / DISABLED_MARKER).exists():
            raise ScheduleDisabled("schedule disabled (rollback marker present); nothing written")
        for i in inputs:
            retain_input(tdir, raw[i["name"]])
        existing = {str(r.get("metric_id")): r for r in load_rows(tdir) if r.get("snapshot_id") == sid}
        if existing:
            # same id = same subject/params/second/inputs: identical rows are a no-op, anything else is a collision
            if {str(r["metric_id"]): _canonical(r) for r in out} == {m: _canonical(r) for m, r in existing.items()}:
                return sid, out
            raise BaselineError(f"snapshot id {sid[:12]} already recorded with different rows; refusing to append")
        _secure_append(tdir / SNAPSHOT_FILE, "".join(_canonical(r) + "\n" for r in out))
    return sid, out


def verify_snapshot(root: Path, snapshot_id: str) -> tuple[bool, str]:
    tdir = telemetry_dir(root)
    stored = snapshot_rows(tdir, snapshot_id)
    first = stored[0]
    raw: dict[str, bytes] = {}
    for i in first["inputs"]:
        if not _SHA256_RE.match(str(i.get("sha256"))):
            return False, f"invalid retained-input digest for {i.get('name')}"
        p = tdir / INPUT_DIR / i["sha256"]
        try:
            data = p.read_bytes()
        except OSError:
            return False, f"retained input missing: {i['name']} {i['sha256'][:12]}"
        if hashlib.sha256(data).hexdigest() != i["sha256"]:
            return False, f"retained input digest mismatch: {i['name']}"
        raw[i["name"]] = data
    win = first["input_window"]
    recomputed = compute_rows(raw, (parse_ts(win["start"]), parse_ts(win["end"])), first["cohort"])
    header_keys = ("snapshot_id", "captured_at", "input_window", "inputs", "repo_head", "subject", "cohort",
                   "definition_version", "horizon_days", "min_effect")
    expect = sorted(({**{k: first[k] for k in header_keys}, **r} for r in recomputed), key=lambda r: r["metric_id"])
    got = sorted(stored, key=lambda r: r["metric_id"])
    if _canonical(expect) != _canonical(got):
        diff = [e["metric_id"] for e, g in zip(expect, got, strict=False) if _canonical(e) != _canonical(g)]
        return False, f"recomputed rows differ from stored rows ({len(expect)} vs {len(got)}): {','.join(diff) or 'row set'}"
    sid = compute_snapshot_id(subject=first["subject"], cohort=first["cohort"], definition_version=first["definition_version"],
                              horizon_days=first["horizon_days"], min_effect=first["min_effect"],
                              captured_at=first["captured_at"], window=win,
                              input_digests=[i["sha256"] + ":" + i["name"] for i in first["inputs"]],
                              metric_ids=[r["metric_id"] for r in stored])
    if sid != snapshot_id:
        return False, "snapshot_id does not match its contents"
    return True, f"{len(stored)} rows recomputed from {len(raw)} retained inputs"


# --------------------------------------------------------------------------- compare

def resolve_effective_start(root: Path, value: str) -> datetime:
    try:
        return parse_ts(value)
    except ValueError:
        pass
    try:
        out = subprocess.run(["git", "-C", str(root), "show", "-s", "--format=%cI", value], capture_output=True,
                             text=True, timeout=10, check=True).stdout.strip()
        return parse_ts(out)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise BaselineError(f"effective start {value!r} is neither an ISO time nor a resolvable commit") from exc


def bind_check(pre: Row, post: Row, subject: str, effective: datetime) -> str | None:
    """Named rejection reason, or None when the pair is correctly bound (AT-1)."""
    if pre["subject"] != subject or post["subject"] != subject:
        return "subject_mismatch"
    if not parse_ts(pre["captured_at"]) < effective:
        return "retrospective_capture"
    pw, qw = pre["input_window"], post["input_window"]
    p_start, p_end, q_start, q_end = (parse_ts(pw["start"]), parse_ts(pw["end"]), parse_ts(qw["start"]), parse_ts(qw["end"]))
    if p_end > effective:
        return "pre_window_ends_after_effective_start"
    if q_end < effective:
        return "post_window_ends_before_effective_start"
    if q_start < effective:
        return "post_window_starts_before_effective_start"
    if p_end > q_start:
        return "windows_overlap"
    if (p_end - p_start) != (q_end - q_start):
        return "windows_unequal"
    for key, name in (("cohort", "cohort_mismatch"), ("definition_version", "definition_mismatch"),
                      ("horizon_days", "horizon_mismatch"), ("min_effect", "min_effect_mismatch")):
        if pre[key] != post[key]:
            return name
    return None


def _bootstrap_lower(pre: list[float], post: list[float], improves_when: str, seed: str) -> tuple[float, float]:
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))
    sign = 1.0 if improves_when == "up" else -1.0
    diffs: list[float] = []
    for _ in range(BOOTSTRAP_B):
        a = sum(rng.choice(pre) for _ in pre) / len(pre)
        b = sum(rng.choice(post) for _ in post) / len(post)
        diffs.append(sign * (b - a))
    diffs.sort()
    point = sign * (sum(post) / len(post) - sum(pre) / len(pre))
    return point, diffs[int(math.floor(0.10 * (len(diffs) - 1)))]  # one-sided 90% lower bound


def metric_verdict(pre: Row | None, post: Row | None, min_effect: float, seed: str) -> dict[str, Any]:
    if pre is None or post is None:
        return {"verdict": "no_baseline", "reason": "metric absent from the pre or post snapshot"}
    if pre.get("gap") or post.get("gap") or pre.get("value") is None or post.get("value") is None:
        return {"verdict": "prospective-only", "reason": pre.get("gap") or post.get("gap") or "no value in one arm"}
    if "aggregate" in (pre["unit_label"], post["unit_label"]) or "current-only" in (pre["time_coverage"], post["time_coverage"]):
        return {"verdict": "insufficient" if "insufficient" in (pre["display"], post["display"]) else "descriptive",
                "reason": "aggregate or current-only rows carry no verdict"}
    n_pre, n_post = len(pre["observations"]), len(post["observations"])
    base = {"n_pre": n_pre, "n_post": n_post, "pre_value": pre["value"], "post_value": post["value"]}
    if min(n_pre, n_post) < DEFINITION_FLOOR_N:
        return {"verdict": "insufficient", "reason": f"n<{DEFINITION_FLOOR_N} independent units per arm", **base}
    point, lower = _bootstrap_lower([float(o["v"]) for o in pre["observations"]],
                                    [float(o["v"]) for o in post["observations"]], pre["improves_when"], seed)
    improved = point > min_effect and lower > 0
    return {"verdict": "improved" if improved else "no demonstrated change", "improvement": round(point, 6),
            "lower_bound_90": round(lower, 6), **base}


def compare_snapshots(root: Path, subject: str, effective_start: str, pre_id: str, post_id: str) -> dict[str, Any]:
    tdir = telemetry_dir(root)
    pre_rows, post_rows = snapshot_rows(tdir, pre_id), snapshot_rows(tdir, post_id)
    effective = resolve_effective_start(root, effective_start)
    reason = bind_check(pre_rows[0], post_rows[0], subject, effective)
    if reason:
        raise BaselineError(f"REJECT {reason}")
    pre_by = {r["metric_id"]: r for r in pre_rows}
    post_by = {r["metric_id"]: r for r in post_rows}
    out = {}
    for mid in sorted(set(pre_by) | set(post_by)):
        out[mid] = metric_verdict(pre_by.get(mid), post_by.get(mid), float(pre_rows[0]["min_effect"]),
                                  f"{pre_id}:{post_id}:{mid}")
    return {"subject": subject, "effective_start": fmt_ts(effective), "pre": pre_id, "post": post_id, "metrics": out}


# --------------------------------------------------------------------------- live indicator (aq-qa / aq-report)

def snapshot_status(root: Path | None = None, now: datetime | None = None, verify: Callable[[Path, str], tuple[bool, str]] | None = None) -> dict[str, Any]:
    """Age and last verify status of the newest snapshot; shared by the aq-qa check and the aq-report line."""
    root = root or main_root()
    now = now or now_utc()
    rows = load_rows(telemetry_dir(root))
    if not rows:
        return {"available": False, "status": "no_snapshot", "age_days": None, "verify": "not_run", "stale": True,
                "reason": f"no snapshot in {telemetry_dir(root) / SNAPSHOT_FILE}"}
    newest = max(rows, key=lambda r: r["captured_at"])
    age = (now - parse_ts(newest["captured_at"])).total_seconds() / 86400
    try:
        ok, detail = (verify or verify_snapshot)(root, newest["snapshot_id"])
    except BaselineError as exc:
        ok, detail = False, str(exc)
    stale = age > STALE_DAYS
    status = "ok" if ok and not stale else ("stale" if ok else "verify_failed")
    return {"available": True, "status": status, "snapshot_id": newest["snapshot_id"], "subject": newest["subject"],
            "captured_at": newest["captured_at"], "age_days": round(age, 2), "stale": stale,
            "verify": "pass" if ok else "fail", "detail": detail}


def status_line(st: dict[str, Any]) -> str:
    if not st.get("available"):
        return "Baseline snapshot: none (no_baseline); run aq-baseline snapshot"
    return (f"Baseline snapshot: {st['snapshot_id'][:12]} age {st['age_days']}d "
            f"({'STALE >' + str(STALE_DAYS) + 'd' if st['stale'] else 'fresh'}) verify {st['verify']}")
