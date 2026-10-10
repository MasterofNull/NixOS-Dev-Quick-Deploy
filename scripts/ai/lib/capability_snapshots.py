"""Atomic capability audit snapshots and read-only status for QA/dashboard."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from capability_audit import CLASSES

SNAPSHOT_PATH = Path('.agent/collaboration/capability-audit-snapshots.json')
MAX_AGE_SECONDS = 26 * 60 * 60


def validate_evidence(row: dict, stamp: datetime) -> None:
    ev = row.get("evidence")
    if not isinstance(ev, dict) or any(type(ev.get(k)) is not bool for k in
            ("discoverable", "used", "wired", "tested", "stale", "dead")):
        raise ValueError("missing boolean evidence")
    for k in ("discovered_in", "wired_by", "use_sources"):
        if not isinstance(ev.get(k), list) or any(not isinstance(v, str) for v in ev[k]):
            raise ValueError("missing source evidence")
    for k in ("discovered_in_count", "wired_by_count", "tested_by_count", "use_count"):
        if type(ev.get(k)) is not int or ev[k] < 0:
            raise ValueError("invalid evidence count")
    if ev["discoverable"] != bool(ev["discovered_in_count"]) or ev["wired"] != bool(ev["wired_by_count"]) or ev["used"] != bool(ev["use_count"]):
        raise ValueError("inconsistent evidence counts")
    if ev["discoverable"] and not ev["discovered_in"] or ev["wired"] and not ev["wired_by"]:
        raise ValueError("missing discovery or wiring evidence")
    if ev["used"]:
        seen = datetime.fromisoformat(ev["last_seen"].replace("Z", "+00:00"))
        if seen.tzinfo is None or seen.timestamp() > stamp.timestamp() or not ev["use_sources"]:
            raise ValueError("invalid usage evidence")
    elif ev.get("last_seen") is not None:
        raise ValueError("inconsistent last_seen")
    if row["class"] == "BROKEN" and not (isinstance(ev.get("broken"), str) and ev["broken"]):
        raise ValueError("missing broken evidence")
    if ev["tested"] != bool(ev["tested_by_count"]):
        raise ValueError("inconsistent tested evidence")
    category = row["class"]
    if ((category == "UNDISCOVERABLE" and ev["discoverable"]) or
            (category == "DEAD-CANDIDATE" and (not ev["dead"] or ev["wired"] or ev["discoverable"] or ev["used"])) or
            (category == "STALE-CLAIM" and not ev["stale"]) or
            (category in ("ACTIVE", "UNUSED-AVAILABLE") and (ev.get("broken") or ev["stale"] or ev["dead"]))):
        raise ValueError("class disagrees with evidence")
    if "unit" in ev and (not isinstance(ev["unit"], dict) or any(not isinstance(unit, dict)
            for unit in ev["unit"].values())):
        raise ValueError("malformed unit evidence")


def validate_report(report: dict) -> datetime:
    if not isinstance(report, dict) or report.get('schema') != 'capability-audit/1':
        raise ValueError('invalid capability audit report schema')
    generated = datetime.fromisoformat(report['generated_at'].replace('Z', '+00:00'))
    if generated.tzinfo is None:
        raise ValueError('audit timestamp must include timezone')
    for key in ('repo_root', 'live_root'):
        if not isinstance(report.get(key), str) or not report[key]:
            raise ValueError(f'invalid {key}')
    if type(report.get('window_days')) is not int or report['window_days'] <= 0:
        raise ValueError('invalid audit window')
    rows, totals = report.get('capabilities'), report.get('totals')
    if not isinstance(rows, list) or not isinstance(totals, dict):
        raise ValueError('missing audit rows or totals')
    keys = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('key'), str) or not row['key'] or row['key'] in keys or row.get('class') not in CLASSES:
            raise ValueError('invalid or duplicate audit capability')
        if any(ord(c) < 32 for c in row['key']):
            raise ValueError('invalid capability key')
        validate_evidence(row, generated)
        keys.add(row['key'])
    counts = Counter(row['class'] for row in rows)
    by_class = totals.get('by_class')
    if type(totals.get('capabilities')) is not int or totals['capabilities'] != len(rows) or not isinstance(by_class, dict):
        raise ValueError('invalid audit totals')
    if set(by_class) != set(CLASSES) or any(type(by_class[c]) is not int or by_class[c] != counts[c] for c in CLASSES):
        raise ValueError('audit class counts disagree with rows')
    return generated


def validate_bundle(bundle: dict) -> datetime:
    if not isinstance(bundle, dict) or bundle.get('schema') != 'capability-audit-snapshots/1' or 'previous' not in bundle:
        raise ValueError('invalid capability snapshot schema')
    generated = validate_report(bundle['current'])
    previous = bundle['previous']
    if previous is not None:
        if validate_report(previous) >= generated:
            raise ValueError('snapshot timestamps must increase')
        if any(previous[k] != bundle['current'][k] for k in ('repo_root', 'live_root', 'window_days')):
            raise ValueError('snapshot audit scopes differ')
    return generated


def write_snapshot(path: Path, report: dict) -> None:
    """Preserve existing snapshots unless the new report and rotation are valid."""
    validate_report(report)
    previous = None
    if path.exists():
        old = json.loads(path.read_text())
        validate_bundle(old)
        previous = old['current']
    bundle = {'schema': 'capability-audit-snapshots/1', 'previous': previous, 'current': report}
    validate_bundle(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.capability-audit-', suffix='.tmp', delete=False) as handle:
        json.dump(bundle, handle, indent=1)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
        temporary = handle.name
    os.replace(temporary, path)


def snapshot_status(path: Path, now: datetime | None = None) -> dict:
    try:
        bundle = json.loads(path.read_text())
        generated = validate_bundle(bundle)
        age = ((now or datetime.now(timezone.utc)) - generated).total_seconds()
        status = 'stale' if age > MAX_AGE_SECONDS else 'fresh'
        if age < 0:
            raise ValueError('snapshot timestamp is in the future')
        if status == 'fresh' and bundle['previous'] is None:
            status = 'warming-up'
        return {'status': status, 'generated_at': bundle['current']['generated_at'], 'age_seconds': age,
                'counts': bundle['current']['totals']['by_class']}
    except FileNotFoundError:
        return {'status': 'missing', 'counts': None, 'age_seconds': None}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {'status': 'invalid', 'counts': None, 'age_seconds': None, 'error': str(exc)[:200]}
