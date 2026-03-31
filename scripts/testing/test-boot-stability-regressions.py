#!/usr/bin/env python3
"""Static regression checks for recent boot-stability fixes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "nix" / "modules" / "core" / "base.nix"
SYNC = ROOT / "scripts" / "data" / "sync-aidb-library-catalog.sh"
P14S = ROOT / "nix" / "modules" / "host-classes" / "p14s-amd-ai-workstation.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    base_text = BASE.read_text(encoding="utf-8")
    sync_text = SYNC.read_text(encoding="utf-8")
    p14s_text = P14S.read_text(encoding="utf-8")

    assert_true(
        'map (path: "d ${path} 0750 root root -") mutableProgramPaths' in base_text,
        "program-writable mutable paths should be root-owned to avoid tmpfiles unsafe transitions",
    )
    assert_true(
        'wait_for_aidb_health()' in sync_text,
        "AIDB catalog sync should wait for local AIDB readiness before importing",
    )
    assert_true(
        'Waiting for AIDB health before import...' in sync_text,
        "AIDB catalog sync should log the readiness wait step",
    )
    assert_true(
        '"tsc=unstable"' in p14s_text,
        "P14s AMD host class should force the kernel off unstable TSC at boot",
    )
    assert_true(
        'hardware.amdgpu.overdrive.enable = lib.mkDefault false;' in p14s_text,
        "P14s AMD host class should keep AMD overdrive disabled for stability",
    )
    assert_true(
        'amdgpu.dcdebugmask=0x10' not in p14s_text,
        "P14s AMD host class should not keep the amdgpu dcdebugmask boot override",
    )

    print("PASS: boot stability regressions are covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
