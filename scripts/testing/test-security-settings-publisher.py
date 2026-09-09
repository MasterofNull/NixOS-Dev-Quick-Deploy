#!/usr/bin/env python3
"""Focused SC-1 publisher tests; no secret material is created or read."""
import importlib.util
import grp
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("publisher", ROOT / "scripts/security/publish-credential-status.py")
publisher = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(publisher)

full_catalog = publisher.load_catalog(ROOT / "config/security-credential-catalog-v1.json")
assert len(full_catalog) == 17
assert sum(entry["status_source"] == "runtime-secret" for entry in full_catalog) == 14
assert {entry["storage"] for entry in full_catalog} >= {"sops", "pam", "gnome-keyring", "password-store"}

with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    catalog = base / "catalog.json"
    catalog.write_text(json.dumps({"schema": publisher.CATALOG_SCHEMA, "credentials": [{"id":"example","label":"Example","purpose":"Example purpose","storage":"sops","risk_class":"R2","scope":"core","owner":"example-owner","status_source":"runtime-secret","runtime_name":"example-runtime","consumers":["example-service"],"capabilities":["replace"],"value_policy":"example-policy","actions":["replace"],"impact":"Example impact.","rotation_evidence":"example-receipt","authentication":"fresh-auth","recovery":"rollback","provider_semantics":"local"}]}))
    runtime = base / "runtime"
    runtime.mkdir()
    (runtime / "example-runtime").touch()
    snapshot = publisher.build_snapshot(publisher.load_catalog(catalog), runtime, {"example-runtime"})
    assert snapshot["summary"] == {"total": 1, "present": 1, "missing": 0, "unavailable": 0, "managed_separately": 0, "not_enabled": 0, "uncataloged": 0}
    assert "runtime_name" not in json.dumps(snapshot)
    assert str(runtime) not in json.dumps(snapshot)
    assert publisher.runtime_presence(base / "absent", "example-runtime") == "unavailable"
    (runtime / "unsafe-runtime").symlink_to(runtime / "example-runtime")
    assert publisher.runtime_presence(runtime, "unsafe-runtime") == "unavailable"
    (runtime / "unknown-runtime").touch()
    unknown = publisher.build_snapshot(publisher.load_catalog(catalog), runtime, {"example-runtime", "unknown-runtime"})
    assert unknown["summary"]["uncataloged"] == 1
    output_dir = base / "root-owned-for-test"
    output_dir.mkdir(mode=0o750)
    output = output_dir / "credential-status.json"
    group = grp.getgrgid(os.getgid()).gr_name
    publisher.atomic_publish(snapshot, output, group, owner_uid=os.getuid())
    assert output.is_file() and output.stat().st_mode & 0o777 == 0o640
    real_dir = base / "real"
    real_dir.mkdir(mode=0o750)
    linked_dir = base / "linked"
    linked_dir.symlink_to(real_dir, target_is_directory=True)
    try:
        publisher.atomic_publish(snapshot, linked_dir / "credential-status.json", group, owner_uid=os.getuid())
        raise AssertionError("publisher followed a swapped parent symlink")
    except OSError:
        pass
print("security-settings publisher: PASS")
