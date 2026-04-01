#!/usr/bin/env python3
"""Static regression checks for recent boot-stability fixes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "nix" / "modules" / "core" / "base.nix"
SYNC = ROOT / "scripts" / "data" / "sync-aidb-library-catalog.sh"
P14S = ROOT / "nix" / "modules" / "host-classes" / "p14s-amd-ai-workstation.nix"
MONITORING = ROOT / "nix" / "modules" / "services" / "monitoring.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    base_text = BASE.read_text(encoding="utf-8")
    sync_text = SYNC.read_text(encoding="utf-8")
    p14s_text = P14S.read_text(encoding="utf-8")
    monitoring_text = MONITORING.read_text(encoding="utf-8")

    assert_true(
        'mutableUserServicePaths = lib.unique [ mutableOptimizerDir mutableLogDir ];' in base_text,
        "base module should identify user-writable service workdirs separately from root-owned state roots",
    )
    assert_true(
        'mutableSharedTraversePaths = [ mutableStateDir ];' in base_text,
        "base module should isolate shared traverse-only parents for user-run services",
    )
    assert_true(
        'map (path: "d ${path} 0711 root root -") mutableSharedTraversePaths' in base_text,
        "AI state root should stay root-owned but traversable so user-run services can reach their writable child dirs",
    )
    assert_true(
        'map (path: "d ${path} 0750 root root -") mutableRootProgramPaths' in base_text,
        "root-owned mutable state roots should stay protected by tmpfiles ownership",
    )
    assert_true(
        'map (path: "z ${path} 0711 root root -") mutableSharedTraversePaths' in base_text,
        "tmpfiles should repair the shared traverse-only state root during activation",
    )
    assert_true(
        'map (path: "d ${path} 0750 ${cfg.primaryUser} ${primaryGroup} -") mutableUserServicePaths' in base_text,
        "optimizer and AI log workdirs should stay writable for user-run orchestration services",
    )
    assert_true(
        'map (path: "z ${path} 0750 ${cfg.primaryUser} ${primaryGroup} -") mutableUserServicePaths' in base_text,
        "tmpfiles should repair ownership on existing optimizer and AI log workdirs during activation",
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
        'hardware.amdgpu.overdrive.enable = lib.mkForce false;' in p14s_text,
        "P14s AMD host class should keep AMD overdrive disabled for stability",
    )
    assert_true(
        'config.hardware.amdgpu.overdrive.enable' in (ROOT / "nix" / "modules" / "roles" / "ai-stack.nix").read_text(encoding="utf-8"),
        "AI stack kernel tuning should respect the centralized AMD overdrive toggle",
    )
    assert_true(
        'amdgpu.dcdebugmask=0x10' not in p14s_text,
        "P14s AMD host class should not keep the amdgpu dcdebugmask boot override",
    )
    assert_true(
        'ENABLE_HDR_WSI = lib.mkForce "0";' in p14s_text,
        "P14s AMD host class should disable the global HDR session path for desktop stability",
    )
    assert_true(
        'DXVK_HDR = lib.mkForce "0";' in p14s_text,
        "P14s AMD host class should disable DXVK HDR on the conservative desktop profile",
    )
    assert_true(
        '${pkgs.coreutils}/bin/chmod 0644 "$tmp_file"' in monitoring_text,
        "AMD GPU exporter should make the emitted textfile world-readable for node_exporter",
    )

    print("PASS: boot stability regressions are covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
