#!/usr/bin/env python3
"""Regression test for scripts/maintenance/aq-update-tiers (fixtures only: no
network, no nix; versions and build/test commands injected via env)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "maintenance" / "aq-update-tiers"
REAL_MANIFEST = ROOT / "nix" / "overlays" / "fast-lane-manifest.nix"

CONFIG = {"frontier": {
    "agent-cli": [{"attr": "alpha"}, {"attr": "beta"}],
    "ide": [{"attr": "ide-old", "rename": "ide-new"}],
    "kernel": [{"attr": "linuxPackages_9_9", "version_attr": "kernel.version", "promote": False}],
}}
VERSIONS = {
    "stable:alpha": "1.0", "unstable:alpha": "1.0",   # current
    "stable:beta": "1.0", "unstable:beta": "2.0",     # candidate
    "stable:ide-old": "1", "unstable:ide-new": "2",   # candidate (renamed)
    "stable:linuxPackages_9_9": "9.9.1", "unstable:linuxPackages_9_9": "9.9.2",
}


def setup(tmp: Path, versions=VERSIONS):
    (tmp / "config.json").write_text(json.dumps(CONFIG))
    (tmp / "versions.json").write_text(json.dumps(versions))
    shutil.copy(REAL_MANIFEST, tmp / "manifest.nix")
    return {**os.environ,
            "AQ_UPDATE_TIERS_CONFIG": str(tmp / "config.json"),
            "AQ_UPDATE_TIERS_MANIFEST": str(tmp / "manifest.nix"),
            "AQ_UPDATE_TIERS_VERSION_FIXTURE": str(tmp / "versions.json"),
            "AQ_UPDATE_TIERS_TEST_CMD": "true"}


def run(env, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True)


def test_check_reports_candidates_and_kernel_staged():
    with tempfile.TemporaryDirectory() as t:
        env = setup(Path(t))
        rows = {r["attr"]: r["status"] for r in json.loads(run(env, "check", "--json").stdout)}
    assert rows == {"alpha": "current", "beta": "candidate", "ide-old": "candidate",
                    "linuxPackages_9_9": "staged-only"}


def test_promote_one_success_adds_first_candidate_only():
    with tempfile.TemporaryDirectory() as t:
        env = setup(Path(t))
        env["AQ_UPDATE_TIERS_BUILD_CMD"] = "true {attr}"
        r = run(env, "promote", "--one")
        text = (Path(t) / "manifest.nix").read_text()
    assert r.returncode == 0, r.stderr
    assert '"beta" # frontier/agent-cli' in text
    assert "ide-old" not in text and "linuxPackages" not in text


def test_promote_renamed_adds_rename_entry():
    with tempfile.TemporaryDirectory() as t:
        env = setup(Path(t), {**VERSIONS, "unstable:beta": "1.0"})
        env["AQ_UPDATE_TIERS_BUILD_CMD"] = "true {attr}"
        r = run(env, "promote", "--one")
        text = (Path(t) / "manifest.nix").read_text()
    assert r.returncode == 0, r.stderr
    assert '"ide-old" # frontier/ide' in text and 'ide-old = "ide-new";' in text


def test_promote_failure_restores_manifest_byte_identical():
    with tempfile.TemporaryDirectory() as t:
        env = setup(Path(t))
        before = (Path(t) / "manifest.nix").read_bytes()
        env["AQ_UPDATE_TIERS_BUILD_CMD"] = "false {attr}"
        r = run(env, "promote", "--one")
        after = (Path(t) / "manifest.nix").read_bytes()
    assert r.returncode == 1
    assert before == after


def test_promote_test_failure_restores_manifest():
    with tempfile.TemporaryDirectory() as t:
        env = setup(Path(t))
        before = (Path(t) / "manifest.nix").read_bytes()
        env["AQ_UPDATE_TIERS_BUILD_CMD"] = "true {attr}"
        env["AQ_UPDATE_TIERS_TEST_CMD"] = "false"
        r = run(env, "promote", "--one")
        assert r.returncode == 1
        assert before == (Path(t) / "manifest.nix").read_bytes()


def test_promote_never_touches_kernel_when_only_kernel_differs():
    with tempfile.TemporaryDirectory() as t:
        v = {**VERSIONS, "unstable:beta": "1.0", "unstable:ide-new": "1"}
        env = setup(Path(t), v)
        before = (Path(t) / "manifest.nix").read_bytes()
        r = run(env, "promote", "--one")
        assert r.returncode == 0 and "no eligible" in r.stdout and "staged separately" in r.stdout
        assert before == (Path(t) / "manifest.nix").read_bytes()


def test_leaf_mode_installs_without_global_override():
    # Widely-linked libraries promote into `leaf` (install-only), never `active`,
    # and an existing leaf member counts as promoted (not re-proposed globally).
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp, {"stable:libz": "1.0", "unstable:libz": "2.0"})
        (tmp / "config.json").write_text(json.dumps({"frontier": {"media": [{"attr": "libz", "mode": "leaf"}]}}))
        env["AQ_UPDATE_TIERS_BUILD_CMD"] = "true"
        r = run(env, "promote", "--one")
        assert r.returncode == 0, r.stderr
        text = (tmp / "manifest.nix").read_text()
        import re
        leaf = re.search(r"leaf\s*=\s*\[(.*?)\];", text, re.S).group(1)
        active = re.search(r"active\s*=\s*\[(.*?)\];", text, re.S).group(1)
        assert '"libz"' in leaf and '"libz"' not in active, text
        r2 = run(env, "promote", "--one")
        assert "no eligible" in r2.stdout, r2.stdout


def test_real_config_is_well_formed():
    cfg = json.loads((ROOT / "config" / "update-tiers.json").read_text())
    cats = set(cfg["frontier"])
    assert {"agent-cli", "ide", "toolchain", "db-client-lang", "sops-cli", "kernel", "perf-tools"} <= cats
    assert "core" in cfg
    # Owner security protocol: newest stable kernel, never an LTS pin.
    kernel = cfg["frontier"]["kernel"]
    assert [e["attr"] for e in kernel] == ["linuxPackages_latest"], kernel
    assert all(e.get("promote") is True for e in kernel), kernel


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
