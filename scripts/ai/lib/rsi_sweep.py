"""Observation-only RSI sweep: ingest persistent signals into the incident ledger.

Every adapter returns (state, findings, detail).  state is "ok", "findings" or
"unknown"; a missing/stale/unreadable source is "unknown" and is never reported
as healthy.  Findings go through rsi_lifecycle.failure so identity/dedupe is
shared with every other entrypoint.  The sweep never starts a repair, a unit or
a model call.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
AGENT = "rsi-steward"
QA_PROGRESS = Path(os.getenv("AQ_QA_PROGRESS_JSONL") or _REPO / ".agent" / "qa" / "latest-progress.jsonl")
QA_MAX_AGE_S = int(os.getenv("RSI_SWEEP_QA_MAX_AGE_S", str(6 * 3600)))
CODE_SCANNING_MAX_AGE_S = int(os.getenv("RSI_SWEEP_CODE_SCANNING_MAX_AGE_S", str(48 * 3600)))
_TAIL_BYTES = 1 << 20


def _unit_key(name: str) -> str:
    # Instance suffixes/hashes vary per run; identity is the unit template.
    return re.sub(r"@.*(?=\.)", "@*", name)


def adapter_failed_units(runner=None):
    run = runner or (lambda: subprocess.run(
        ["systemctl", "--failed", "--no-legend", "--plain", "--no-pager"],
        capture_output=True, text=True, timeout=15))
    try:
        r = run()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "unknown", [], f"systemctl unavailable: {exc}"
    if r.returncode != 0:
        return "unknown", [], f"systemctl exit {r.returncode}"
    findings = []
    for line in r.stdout.splitlines():
        parts = line.lstrip("●* \t").split()
        if parts and re.match(r"^[\w@:.\\-]+\.(service|timer|socket|mount|target)$", parts[0]):
            unit = _unit_key(parts[0])
            findings.append(dict(subject=f"failed-unit:{unit}", producer="systemd:failed-unit",
                                 path=unit, authority="systemd", os_error=f"unit {unit} in failed state",
                                 severity="medium", root_fix=f"journalctl -u {unit}; fix producer, then systemctl reset-failed"))
    return ("findings" if findings else "ok"), findings, f"{len(findings)} failed unit(s)"


DELEGATION_REGISTRY = Path(os.getenv("RSI_SWEEP_DELEGATION_REGISTRY") or _REPO / ".agents" / "delegation" / "registry.jsonl")
DELEGATION_WINDOW_S = int(os.getenv("RSI_SWEEP_DELEGATION_WINDOW_S", str(7 * 86400)))
ERROR_UNITS = os.getenv("RSI_SWEEP_ERROR_UNITS", "ai-hybrid-coordinator ai-aidb ai-switchboard command-center-dashboard-api").split()
ERROR_WINDOW_S = int(os.getenv("RSI_SWEEP_ERROR_WINDOW_S", "3600"))
ERROR_MIN_COUNT = int(os.getenv("RSI_SWEEP_ERROR_MIN_COUNT", "5"))
_LOG_TAIL_BYTES = 4096
_JOURNAL_MAX_BYTES = 4 << 20
_BAD_STATUSES = {"failed", "timeout", "orphaned", "stale", "failed_orphaned_no_output"}
_SKILL_RE = re.compile(r"failed to load skill\s+(\S+)", re.I)


def _parse_iso(value):
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()


def _log_tail(output_file):
    p = Path(output_file)
    if not p.is_absolute():
        p = _REPO / p
    try:
        with p.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - _LOG_TAIL_BYTES))
            return fh.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _classify_delegation(rec, tail):
    """Return (class, detail) or None.  Log markers outrank the bare status."""
    status = str(rec.get("status") or "")
    if status == "cancelled":
        return None
    m = _SKILL_RE.search(tail)
    if m:
        return "skill-load-error", m.group(1).rstrip(".,;:'\")")
    if "usage limit" in tail.lower():
        return "quota", ""
    if status == "done":
        if any(ln.startswith("Blocked:") or "BLOCKED" in ln for ln in tail.splitlines()):
            return "blocked", ""
        return None
    if status in _BAD_STATUSES:
        return status, ""
    return None


def adapter_delegation_outcomes(registry=None, window_s=None, now=None):
    """Group recent delegation failures by (lane, class[, skill path]), not by run."""
    registry = Path(registry or DELEGATION_REGISTRY)
    window = DELEGATION_WINDOW_S if window_s is None else window_s
    now = now if now is not None else time.time()
    try:
        lines = registry.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return "unknown", [], f"delegation registry unavailable: {exc}"
    groups: dict[tuple, dict] = {}
    seen = 0
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        ts = _parse_iso(rec.get("created"))
        if ts is None or now - ts > window:
            continue
        seen += 1
        cls = _classify_delegation(rec, _log_tail(rec["output_file"]) if rec.get("output_file") else "")
        if not cls:
            continue
        lane = str(rec.get("agent") or "unknown").strip().lower()
        g = groups.setdefault((lane, cls[0], cls[1]), {"count": 0, "latest": 0, "id": ""})
        g["count"] += 1
        if ts >= g["latest"]:
            g["latest"], g["id"] = ts, str(rec.get("id") or "")
    findings = []
    for (lane, cls, extra), g in sorted(groups.items()):
        label = f"{cls}:{extra}" if extra else cls
        severity = "medium" if cls in ("quota", "skill-load-error") or g["count"] >= 3 else "low"
        findings.append(dict(
            subject=f"delegation:{lane}:{label}", producer=f"delegation:{lane}",
            path=extra or ".agents/delegation/registry.jsonl", authority=lane,
            # Identity is lane+class(+skill path); counts/run ids live in root_fix (refreshed each sighting).
            os_error=f"{lane} delegation class {label}", severity=severity,
            root_fix=f"{g['count']} run(s) in window; latest example .agents/delegation/outputs/{g['id']}.log; fix producer for class {cls}"))
    return ("findings" if findings else "ok"), findings, f"{len(findings)} class(es) across {seen} recent run(s)"


_SIG_SUBS = [
    (re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:[.,]\d+)?(?:Z|[+-]\d\d:?\d\d)?"), ""),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F-]{4,}\b"), "<id>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b|\b(?=[0-9a-fA-F]*\d)(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{6,}\b"), "<hex>"),
    (re.compile(r"(?i)\b(request[_ -]?id|req[_ -]?id|trace[_ -]?id)\b[=:\s]*\S+"), r"\1=<id>"),
    (re.compile(r"\d+"), "<n>"),
]


def _error_signature(line):
    """Return a normalised signature for an error line, or None if it is not an error."""
    msg = None
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        rec = None
    if isinstance(rec, dict):
        if str(rec.get("level", "")).lower() == "error":
            msg = str(rec.get("event") or rec.get("message") or rec.get("msg") or line)
    if msg is None:
        if not any(k in line for k in ("Traceback", "Permission denied", "EACCES")):
            return None
        msg = line
    for rx, repl in _SIG_SUBS:
        msg = rx.sub(repl, msg)
    return re.sub(r"\s+", " ", msg).strip()[:160] or None


def adapter_service_error_rate(runner=None, units=None, window_s=None, min_count=None):
    """Recurring error signatures in services that stay 'active' (journal, bounded)."""
    units = ERROR_UNITS if units is None else units
    window = ERROR_WINDOW_S if window_s is None else window_s
    threshold = ERROR_MIN_COUNT if min_count is None else min_count

    def default(unit):
        return subprocess.run(["journalctl", "-u", unit, "--since", f"-{window}s", "-o", "cat", "--no-pager"],
                              capture_output=True, text=True, timeout=30)
    run = runner or default
    findings, readable = [], 0
    for unit in units:
        try:
            r = run(unit)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "unknown", [], f"journalctl unavailable: {exc}"
        if r.returncode != 0:
            return "unknown", [], f"journalctl exit {r.returncode} for {unit}"
        readable += 1
        counts: dict[str, list] = {}
        for line in (r.stdout or "")[-_JOURNAL_MAX_BYTES:].splitlines():
            sig = _error_signature(line.strip())
            if sig:
                entry = counts.setdefault(sig, [0, line.strip()])
                entry[0] += 1
        for sig, (n, example) in sorted(counts.items()):
            if n >= threshold:
                findings.append(dict(
                    subject=f"service-error:{unit}:{sig[:60]}", producer=f"journal:{unit}", path=unit,
                    authority="journald", os_error=f"recurring error in {unit}: {sig}",
                    severity="medium",
                    root_fix=f"{n} occurrence(s) in last {window}s; example: {example[:200]}; journalctl -u {unit}; fix producer"))
    return ("findings" if findings else "ok"), findings, f"{len(findings)} recurring signature(s) in {readable} unit(s)"


def _default_alerts_path() -> Path:
    base = os.environ.get("AI_SECURITY_AUDIT_DIR") or str(Path.home() / ".local" / "share" / "nixos-ai-stack" / "security")
    return Path(base) / "github-code-scanning-alerts.json"


def adapter_code_scanning(alerts_path=None, max_age_s=None, now=None):
    """Delegate planning to the existing intake (--dry-run); alerts come from its exported file.

    The export is a snapshot: past max age it says nothing about current alerts, so it is unknown.
    """
    alerts_path = alerts_path or _default_alerts_path()
    max_age = CODE_SCANNING_MAX_AGE_S if max_age_s is None else max_age_s
    try:
        age = (now if now is not None else time.time()) - Path(alerts_path).stat().st_mtime
    except OSError as exc:
        return "unknown", [], f"alerts export unavailable: {exc}"
    if age > max_age:
        return "unknown", [], f"alerts export stale ({int(age // 3600)}h > {max_age // 3600}h); refresh via refresh-hosted-code-scanning.sh"
    script = _REPO / "scripts" / "security" / "rsi-intake-code-scanning.py"
    cmd = [sys.executable, str(script), "--dry-run", "--alerts", str(alerts_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "unknown", [], f"intake failed: {exc}"
    if r.returncode != 0:
        return "unknown", [], f"alerts source unavailable: {r.stderr.strip()[:200]}"
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    try:
        planned = json.loads(lines[0]) if len(lines) > 1 else []
    except json.JSONDecodeError:
        return "unknown", [], "intake output not JSON"
    findings = [dict(subject=p["subject"], producer=f"github-code-scanning:{p['category']}",
                     path=p["manifest"], authority="trivy", os_error=p["os_error"],
                     severity=p["severity"], root_fix=p["root_fix"]) for p in planned]
    return ("findings" if findings else "ok"), findings, f"{len(findings)} alert group(s)"


def adapter_qa_phase0(progress=None, max_age_s=None, now=None):
    """Read the latest aq-qa machine output; never runs aq-qa."""
    progress = Path(progress or QA_PROGRESS)
    max_age = QA_MAX_AGE_S if max_age_s is None else max_age_s
    now = now if now is not None else time.time()
    try:
        age = now - progress.stat().st_mtime
        with progress.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - _TAIL_BYTES))
            data = fh.read().decode("utf-8", "replace")
    except OSError as exc:
        return "unknown", [], f"aq-qa output unavailable: {exc}"
    if age > max_age:
        return "unknown", [], f"aq-qa output stale ({int(age)}s > {max_age}s)"
    last: dict[str, dict] = {}
    for line in data.splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # first line of a tail window may be cut
        if isinstance(rec, dict) and str(rec.get("check_id", "")).startswith("0."):
            last[str(rec["check_id"])] = rec
    if not last:
        return "unknown", [], "no phase-0 records in aq-qa output (empty, truncated or other phase)"
    findings = []
    for cid, rec in sorted(last.items()):
        if rec.get("state") == "fail":
            desc = str(rec.get("description") or "")[:120]
            findings.append(dict(subject=f"aq-qa:{cid}", producer="aq-qa:phase0", path=f"aq-qa check {cid}",
                                 authority="aq-qa", os_error=f"phase-0 check {cid} failing: {desc}",
                                 severity="medium", root_fix=f"run aq-qa 0 --machine and fix check {cid} at its producer"))
    if findings:
        return "findings", findings, f"{len(findings)} failing phase-0 check(s) in {len(last)} seen"
    unfinished = sorted(c for c, r in last.items() if r.get("state") not in ("pass", "skip"))
    if unfinished:
        # No failure seen, but the run never reached a verdict for these checks: not evidence of health.
        return "unknown", [], f"aq-qa run incomplete or unrecognised state for {len(unfinished)} check(s), e.g. {unfinished[0]}"
    return "ok", [], f"all {len(last)} phase-0 checks pass/skip"


def adapter_payload_audit(runner=None):
    def default():
        return subprocess.run([sys.executable, str(_REPO / "scripts" / "ai" / "aq-payload-audit"), "--json"],
                              capture_output=True, text=True, timeout=60)
    try:
        r = (runner or default)()
        out = json.loads(r.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return "unknown", [], f"payload audit unavailable: {exc}"
    findings = []
    for f in out.get("findings", []):
        if f.get("severity") == "high":
            findings.append(dict(subject=f"payload-audit:{f.get('lane')}:{f.get('check_id')}",
                                 producer="aq-payload-audit", path=str(f.get("evidence_path") or "payload"),
                                 authority=str(f.get("lane") or "payload"),
                                 # Identity must be stable across sweeps: measurements vary every run, so they
                                 # live in root_fix (updated on each sighting), never in os_error.
                                 os_error=f"payload audit check {f.get('check_id')} high on lane {f.get('lane')}",
                                 severity="high",
                                 root_fix=f"{f.get('suggested_fix') or 'reduce payload'} (latest: measured {f.get('measured')} vs {f.get('threshold')})"))
    return ("findings" if findings else "ok"), findings, f"{len(findings)} high finding(s)"


def _load_intake():
    import importlib.util
    from importlib.machinery import SourceFileLoader
    path = _REPO / "scripts" / "security" / "rsi-intake-code-scanning.py"
    loader = SourceFileLoader("rsi_intake_code_scanning", str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


def _alert_key(alert, intake):
    recent = alert.get("most_recent_instance") or {}
    parsed = intake._parse_alert_message((recent.get("message") or {}).get("text", ""))
    category = recent.get("category") or "unknown"
    return (f"github-code-scanning:{category}", parsed.get("package", "unknown"), parsed.get("installed", "unknown"))


def plan_reconcile(alerts, incidents, intake=None):
    """Return [(incident_id, evidence)] for open code-scanning incidents with positive closure proof.

    Positive proof = at least one alert for the incident's (category, package, installed) exists in
    the API data and every such alert is fixed/dismissed.  No matching alerts = no evidence = open.
    """
    intake = intake or _load_intake()
    by_key: dict[tuple, list] = {}
    for alert in alerts:
        if isinstance(alert, dict):
            by_key.setdefault(_alert_key(alert, intake), []).append(alert)
    plan = []
    for iid, inc in sorted(incidents.items()):
        if not isinstance(inc, dict) or inc.get("status") != "open":
            continue
        if not str(inc.get("producer", "")).startswith("github-code-scanning:"):
            continue
        error = str(inc.get("error", ""))
        m = re.match(r"^(\S+) (\S+) vulnerable", error)
        if not m:
            continue
        matched = by_key.get((inc["producer"], m.group(1), m.group(2)), [])
        if not matched or any(a.get("state") not in ("fixed", "dismissed") for a in matched):
            continue
        stamps = sorted(str(a.get("fixed_at") or a.get("dismissed_at") or "") for a in matched)
        commit = ((matched[0].get("most_recent_instance") or {}).get("commit_sha") or "")[:12]
        plan.append((iid, {"alerts": len(matched), "analysis": commit or (stamps[-1][:10] if stamps and stamps[-1] else "unknown"),
                           "states": sorted({a["state"] for a in matched})}))
    return plan


def reconcile(alerts=None, dry_run=False, as_json=False) -> int:
    """Resolve code-scanning incidents whose alerts are all closed upstream; unknown source = no change."""
    os.environ.pop("REDIS_URL", None)
    import rsi_lifecycle
    intake = _load_intake()
    if alerts is None:
        try:
            alerts = intake._fetch_alerts_from_github(state="")
        except intake.AlertSourceError as exc:
            print(json.dumps({"state": "unknown", "error": str(exc)}) if as_json else f"UNKNOWN: {exc}")
            return 2
    ledger = rsi_lifecycle._RUNTIME / "rsi-incidents.json"
    try:
        incidents = json.loads(ledger.read_text()).get("incidents", {})
    except (OSError, json.JSONDecodeError) as exc:
        print(f"UNKNOWN: incident ledger unreadable: {exc}", file=sys.stderr)
        return 2
    plan = plan_reconcile(alerts, incidents, intake)
    resolved = []
    for iid, ev in plan:
        if not dry_run:
            rsi_lifecycle.resolve(
                iid,
                f"upstream fix verified: code-scanning alerts closed ({ev['alerts']} alerts, analysis {ev['analysis']})",
                "trivy rescan", "alert state fixed")
        resolved.append({"id": iid, **ev})
    summary = {"dry_run": dry_run, "resolved": resolved, "alerts_seen": len(alerts)}
    print(json.dumps(summary, sort_keys=True) if as_json else
          f"reconcile: {len(resolved)} incident(s) {'would resolve' if dry_run else 'resolved'} from {len(alerts)} alerts")
    return 0


def run(dry_run=False, as_json=False, adapters=None) -> int:
    os.environ.pop("REDIS_URL", None)
    import rsi_lifecycle
    adapters = adapters or {
        "failed-units": adapter_failed_units, "code-scanning": adapter_code_scanning,
        "aq-qa-phase0": adapter_qa_phase0, "payload-audit": adapter_payload_audit,
        "delegation-outcomes": adapter_delegation_outcomes, "service-error-rate": adapter_service_error_rate}
    report = {}
    recorded = 0
    for name, fn in adapters.items():
        try:
            state, findings, detail = fn()
        except Exception as exc:  # an adapter bug must read as unknown, never healthy
            state, findings, detail = "unknown", [], f"adapter error: {type(exc).__name__}: {exc}"
        ids = []
        for f in findings:
            if dry_run:
                continue
            ids.append(rsi_lifecycle.failure(AGENT, f["subject"], f["producer"], f["path"], f["authority"],
                                             f["os_error"], severity=f["severity"], root_fix=f["root_fix"]))
        recorded += len(ids)
        report[name] = {"state": state, "findings": len(findings), "detail": detail}
    summary = {"dry_run": dry_run, "recorded": recorded, "sources": report,
               "unknown": sorted(k for k, v in report.items() if v["state"] == "unknown"),
               "healthy_sources": sorted(k for k, v in report.items() if v["state"] == "ok")}
    # Healthy only when every source positively reported ok; unknown and findings both deny it.
    summary["healthy"] = bool(report) and len(summary["healthy_sources"]) == len(report)
    if as_json:
        print(json.dumps(summary, sort_keys=True))
    else:
        for name, v in report.items():
            print(f"{name}: {v['state']} ({v['detail']})")
        print(f"recorded={recorded} dry_run={dry_run} healthy={summary['healthy']} unknown={summary['unknown']}")
    return 0
