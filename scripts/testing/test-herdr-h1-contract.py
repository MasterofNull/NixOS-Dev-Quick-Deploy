#!/usr/bin/env python3
"""Hermetic H1 contract proof; it never builds, starts, or contacts Herdr."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = (ROOT / "nix/pkgs/herdr.nix").read_text()
HOME_MODULE = (ROOT / "nix/home/herdr.nix").read_text()
FLAKE = (ROOT / "flake.nix").read_text()
CLI = ROOT / "scripts/ai/aq-herdr"
CLI_TEXT = CLI.read_text()
REPORT = (ROOT / ".agents/plans/herdr-agent-operations/H1-SUPPLY-CHAIN-REPORT.md").read_text()
BASH = shutil.which("bash")
assert BASH, "focused test requires an already-installed bash interpreter"

REVISION = "ef4c23f5775bb8cfec05f05d0844226ff959a07a"
SOURCE_HASH = "sha256-3BA8eredGku+vsL2Af7sUf43QiArR5XTHNrI+X11vFM="
CARGO_HASH = "4d590b4abf9d6088704ae7ab9811c8bb766286ec75ca63364c7e23cb14be6ecf"
LICENSE_HASH = "a7fa24f74382fb3e4d320a608533a7c2999dbc0f780f1f734c8b891b31f0d9bd"
EXPECTED_CONFIG = """onboarding = false
[update]
version_check = false
manifest_check = false
[session]
resume_agents_on_restore = false
[remote]
manage_ssh_config = false
[experimental]
allow_nested = false
pane_history = false
"""
CLOSED_STATUS_KEYS = {
    "schema_version",
    "command",
    "configured",
    "effective",
    "runtime",
    "package",
    "reason",
}

for value in (REVISION, SOURCE_HASH, CARGO_HASH, LICENSE_HASH):
    assert value in PKG and value in REPORT
assert "builtins.fetchTree" in PKG and "narHash" in PKG and "nix/package.nix" in PKG
assert PKG.count('builtins.hashFile "sha256"') == 2
assert "postPatch" not in PKG, "full-tree provenance checks must not run after upstream filters LICENSE"
assert "./nix/home/herdr.nix" in FLAKE
assert "default = false" in HOME_MODULE and "assertion = !cfg.runtimeEnable" in HOME_MODULE
assert "writeShellApplication" in HOME_MODULE and "runtimeInputs = [pkgs.coreutils]" in HOME_MODULE
assert "home.packages = [ herdr facade ]" not in HOME_MODULE
assert "herdrBuild = herdr" in HOME_MODULE
assert "home.packages = [" in HOME_MODULE and "(facade.overrideAttrs" in HOME_MODULE
assert "command -v herdr" not in CLI_TEXT
for setting in (
    "onboarding = false",
    "version_check = false",
    "manifest_check = false",
    "resume_agents_on_restore = false",
    "manage_ssh_config = false",
    "allow_nested = false",
    "pane_history = false",
):
    assert setting in HOME_MODULE
for unsupported in ("[plugins]", "[integrations]", "remote]\n        enabled"):
    assert unsupported not in HOME_MODULE
for forbidden in (
    "systemd.user",
    "wantedby",
    "listenstream",
    "restart",
    "herdr server",
    "herdr pane",
    "send-keys",
    "send-text",
    "agent prompt",
):
    assert forbidden not in HOME_MODULE.lower() and forbidden not in CLI_TEXT.lower()


def invoke(home: Path, *args: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        "HOME": str(home),
        "PATH": path or os.environ.get("PATH", "/run/current-system/sw/bin:/usr/bin:/bin"),
    }
    return subprocess.run([BASH, str(CLI), *args], env=env, text=True, capture_output=True)


def payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    data = json.loads(result.stdout)
    assert set(data) == CLOSED_STATUS_KEYS
    assert data["runtime"] == "not-activated"
    return data


with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    config_dir = home / ".config/herdr"
    config_dir.mkdir(parents=True)

    status = invoke(home, "status", "--json")
    assert status.returncode == 0
    assert payload(status)["configured"] == "disabled"

    attach = invoke(home, "attach")
    assert attach.returncode == 3 and payload(attach)["reason"] == "config-absent"

    config = config_dir / "config.toml"
    config.write_text(EXPECTED_CONFIG)
    config.chmod(0o444)
    status = invoke(home, "status")
    assert status.returncode == 0 and payload(status)["configured"] == "configured"
    doctor = invoke(home, "doctor", "--json")
    assert doctor.returncode == 4 and payload(doctor)["reason"] == "config-not-store-backed"

    config.chmod(0o666)
    unsafe = invoke(home, "status", "--json")
    assert unsafe.returncode == 0 and payload(unsafe)["reason"] == "config-mode-unsafe"

    config.chmod(0o644)
    config.write_text(EXPECTED_CONFIG + "# drift\n")
    config.chmod(0o444)
    drift = invoke(home, "status", "--json")
    assert payload(drift)["reason"] == "config-policy-drift"

    config.unlink()
    outside = home / "outside-config"
    outside.write_text(EXPECTED_CONFIG)
    outside.chmod(0o444)
    config.symlink_to(outside)
    untrusted = invoke(home, "doctor", "--json")
    assert untrusted.returncode == 4 and payload(untrusted)["reason"] == "config-target-untrusted"

    fake_bin = home / "bin"
    fake_bin.mkdir()
    marker = home / "herdr-was-executed"
    fake_herdr = fake_bin / "herdr"
    fake_herdr.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n")
    fake_herdr.chmod(0o700)
    probe = invoke(home, "status", "--json", path=f"{fake_bin}:{os.environ.get('PATH', '')}")
    assert probe.returncode == 0
    assert payload(probe)["package"] == "sealed-not-exposed"
    assert not marker.exists(), "H1 facade must neither discover nor execute a raw Herdr binary"

    invalid = invoke(home, "status", "--unexpected")
    assert invalid.returncode == 2 and not invalid.stdout

version = subprocess.run([BASH, str(CLI), "version"], text=True, capture_output=True, check=True)
version_payload = json.loads(version.stdout)
assert set(version_payload) == {"schema_version", "command", "version", "revision", "license"}
assert version_payload["version"] == "0.7.5" and version_payload["license"] == "AGPL-3.0-or-later"
print("herdr-h1-contract: PASS")
