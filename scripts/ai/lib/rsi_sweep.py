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
        if isinstance(rec, dict) and rec.get("check_id"):
            last[str(rec["check_id"])] = rec
    findings = []
    for cid, rec in sorted(last.items()):
        if rec.get("state") == "fail" and str(cid).startswith("0."):
            desc = str(rec.get("description") or "")[:120]
            findings.append(dict(subject=f"aq-qa:{cid}", producer="aq-qa:phase0", path=f"aq-qa check {cid}",
                                 authority="aq-qa", os_error=f"phase-0 check {cid} failing: {desc}",
                                 severity="medium", root_fix=f"run aq-qa 0 --machine and fix check {cid} at its producer"))
    return ("findings" if findings else "ok"), findings, f"{len(findings)} failing phase-0 check(s) in {len(last)} seen"


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
                                 os_error=f"check {f.get('check_id')} high: measured {f.get('measured')} vs {f.get('threshold')}",
                                 severity="high", root_fix=str(f.get("suggested_fix") or "")))
    return ("findings" if findings else "ok"), findings, f"{len(findings)} high finding(s)"


def run(dry_run=False, as_json=False, adapters=None) -> int:
    os.environ.pop("REDIS_URL", None)
    import rsi_lifecycle
    adapters = adapters or {
        "failed-units": adapter_failed_units, "code-scanning": adapter_code_scanning,
        "aq-qa-phase0": adapter_qa_phase0, "payload-audit": adapter_payload_audit}
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
               "unknown": sorted(k for k, v in report.items() if v["state"] == "unknown")}
    if as_json:
        print(json.dumps(summary, sort_keys=True))
    else:
        for name, v in report.items():
            print(f"{name}: {v['state']} ({v['detail']})")
        print(f"recorded={recorded} dry_run={dry_run}")
    return 0
