#!/usr/bin/env python3
"""Focused SC-1 route tests using only synthetic metadata snapshots."""
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "dashboard/backend/api/routes/security_settings.py"
spec = importlib.util.spec_from_file_location("security_settings", ROUTE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    folder = base / "security"
    folder.mkdir()
    now = datetime.now(timezone.utc)
    snapshot = {"schema": "aqos.security-credential-status.v1", "generated_at": now.isoformat().replace("+00:00", "Z"), "overall_state": "protected", "summary": {"total": 1, "present": 1, "missing": 0, "unavailable": 0, "managed_separately": 0, "not_enabled": 0, "uncataloged": 0}, "credentials": [{"id":"example", "label":"Example", "purpose":"Example purpose", "storage":"sops", "risk_class":"R2", "consumers":["example-service"], "rotation":"replace", "readiness":"present", "mutation_state":"not_available_yet"}]}
    target = folder / "credential-status.json"
    target.write_text(json.dumps(snapshot))
    target.chmod(0o640)
    assert module._read_snapshot(target, expected_uid=os.getuid(), now=now) == snapshot
    real_parent = base / "real-parent"
    real_parent.mkdir()
    linked_parent = base / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    linked_target = real_parent / "credential-status.json"
    linked_target.write_text(json.dumps(snapshot))
    linked_target.chmod(0o640)
    try:
        module._read_snapshot(linked_parent / "credential-status.json", expected_uid=os.getuid(), now=now)
        raise AssertionError("route followed a swapped parent symlink")
    except module.HTTPException as error:
        assert error.status_code == 503
    target.unlink()
    target.symlink_to(folder / "elsewhere.json")
    (folder / "elsewhere.json").write_text(json.dumps(snapshot))
    try:
        module._read_snapshot(target, expected_uid=os.getuid(), now=now)
        raise AssertionError("route followed a snapshot symlink")
    except module.HTTPException as error:
        assert error.status_code == 503
    target.unlink()
    target.write_text(json.dumps(snapshot))
    target.chmod(0o640)
    snapshot["credentials"][0]["secret"] = "forbidden"
    target.write_text(json.dumps(snapshot))
    try:
        module._read_snapshot(target, expected_uid=os.getuid(), now=now)
        raise AssertionError("route accepted an unallowlisted field")
    except module.HTTPException as error:
        assert error.status_code == 503
    snapshot["credentials"][0].pop("secret")
    snapshot["generated_at"] = (now - timedelta(hours=1)).isoformat()
    target.write_text(json.dumps(snapshot))
    try:
        module._read_snapshot(target, expected_uid=os.getuid(), now=now)
        raise AssertionError("route accepted a stale snapshot")
    except module.HTTPException as error:
        assert error.status_code == 503
    snapshot["generated_at"] = now.isoformat()
    snapshot["credentials"][0]["readiness"] = "missing"
    target.write_text(json.dumps(snapshot))
    try:
        module._read_snapshot(target, expected_uid=os.getuid(), now=now)
        raise AssertionError("route accepted contradictory summary counts")
    except module.HTTPException as error:
        assert error.status_code == 503
print("security-settings route: PASS")
