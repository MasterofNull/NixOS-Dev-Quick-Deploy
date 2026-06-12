#!/usr/bin/env python3
"""Static regression checks for recent boot-stability fixes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "nix" / "modules" / "core" / "base.nix"
SYNC = ROOT / "scripts" / "data" / "sync-aidb-library-catalog.sh"
P14S = ROOT / "nix" / "modules" / "host-classes" / "p14s-amd-ai-workstation.nix"
MONITORING = ROOT / "nix" / "modules" / "services" / "monitoring.nix"
MCP_SERVERS = ROOT / "nix" / "modules" / "services" / "mcp-servers.nix"
AUTO_REMEDIATE = ROOT / "scripts" / "automation" / "auto-remediate.sh"
HEALTH_SPIDER = ROOT / "scripts" / "ai" / "aq-health-spider"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    base_text = BASE.read_text(encoding="utf-8")
    sync_text = SYNC.read_text(encoding="utf-8")
    p14s_text = P14S.read_text(encoding="utf-8")
    monitoring_text = MONITORING.read_text(encoding="utf-8")
    mcp_servers_text = MCP_SERVERS.read_text(encoding="utf-8")
    auto_remediate_text = AUTO_REMEDIATE.read_text(encoding="utf-8")
    health_spider_text = HEALTH_SPIDER.read_text(encoding="utf-8")
    switchboard_text = (ROOT / "ai-stack" / "switchboard" / "switchboard.py").read_text(encoding="utf-8")
    qa_runner_text = (ROOT / "dashboard" / "backend" / "api" / "services" / "qa_runner.py").read_text(encoding="utf-8")

    assert_true(
        'mutableUserServicePaths = lib.unique [mutableOptimizerDir mutableLogDir];' in base_text,
        "base module should identify user-writable service workdirs separately from root-owned state roots",
    )
    assert_true(
        'mutableSharedTraversePaths = [mutableStateDir];' in base_text,
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
        base_text.index('map (path: "z ${path} 0711 root root -") mutableSharedTraversePaths')
        < base_text.index('map (path: "d ${path} 0750 root root -") mutableRootProgramPaths'),
        "tmpfiles should repair shared parent ownership before processing child paths",
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
    assert_true(
        'prsi-orchestrator.py" queue' not in auto_remediate_text,
        "auto-remediate should not call removed PRSI queue subcommand",
    )
    assert_true(
        'prsi-orchestrator.py" cycle --since=1d --execute-limit=1' in auto_remediate_text,
        "auto-remediate should use the supported PRSI cycle command",
    )
    assert_true(
        '"d ${dataDir} 0755 ${svcUser} ${aiGroup} -"' not in mcp_servers_text,
        "post-deploy tmpfiles block should not duplicate the main /var/lib/ai-stack declaration",
    )
    assert_true(
        '"d ${mutableStateDir} 0755 ${svcUser} ${aiGroup} -"' not in mcp_servers_text,
        "post-deploy tmpfiles block should not fight base.nix ownership for mutable state root",
    )
    assert_true(
        '"f ${dataDir}/hybrid/telemetry/latest-aq-report.json 0664 ${svcUser} ${aiGroup} - -"' in mcp_servers_text,
        "latest aq-report artifact should be explicitly created with group-writable telemetry permissions",
    )
    assert_true(
        '"z ${mutableLogDir}                       0770 root ${aiGroup} -"' in mcp_servers_text,
        "AI log parent should be root-owned to avoid unsafe transitions to service-owned log files",
    )
    assert_true(
        "/tmp/ r," in mcp_servers_text and "/tmp/*.db rwk," in mcp_servers_text,
        "dashboard AppArmor profile should allow reading /tmp directory before opening tmp SQLite files",
    )
    assert_true(
        "/run/current-system/sw/bin/aq-qa ix," in mcp_servers_text,
        "dashboard AppArmor profile should execute the exact aq-qa symlink path used by qa_runner",
    )
    assert_true(
        'return await self._fix_apparmor(anomaly) != "covered"' in health_spider_text,
        "health spider should not fail a cycle for AppArmor denials when rules are already covered",
    )
    assert_true(
        "total += len(anomalies)" not in health_spider_text,
        "health spider should count unresolved anomalies after remediation handling",
    )
    assert_true(
        "def _failed_systemd_units" in health_spider_text
        and '["systemctl", "--failed", "--no-legend", "--no-pager"]' in health_spider_text,
        "health spider should include a global systemd failed-unit probe",
    )
    assert_true(
        '"type": "systemd_failed_units"' in health_spider_text
        and 'title=f"Systemd failed units detected: {len(units)}"' in health_spider_text,
        "health spider should surface failed systemd units to attention/telemetry",
    )
    assert_true(
        '"name": "routing-analytics"' in health_spider_text
        and '"required_keys": ["logic_discipline", "logic_discipline_rate"]' in health_spider_text,
        "health spider should catch stale dashboard routing analytics code by requiring logic-discipline telemetry keys",
    )
    assert_true(
        'missing = [key for key in (required_keys or []) if key not in data]' in health_spider_text
        and "missing_keys=" in health_spider_text,
        "health spider JSON probes should fail when required dashboard semantic keys are absent",
    )
    assert_true(
        '"name": "osi-layered"' in health_spider_text
        and '"semantic_checks": ["osi_layered_ready"]' in health_spider_text
        and "osi_layered_pending" in health_spider_text,
        "health spider should catch OSI layer cards stuck pending or showing 0/0",
    )
    assert_true(
        '"name": "ragas-faithfulness"' in health_spider_text
        and '"semantic_checks": ["ragas_faithfulness"]' in health_spider_text
        and "faithfulness_sample_count=0" in health_spider_text,
        "health spider should catch enabled RAGAS faithfulness metrics that render as 0.0%",
    )
    assert_true(
        '"name": "audit-integrity"' in health_spider_text
        and '"semantic_checks": ["audit_integrity"]' in health_spider_text
        and "audit_integrity_sealed" in health_spider_text,
        "health spider should catch operator audit integrity cards that are not fully sealed",
    )
    assert_true(
        '"semantic_checks": ["aggregate_services"]' in health_spider_text
        and "degraded_services=" in health_spider_text,
        "health spider aggregate probe should inspect child service status, not only top-level HTTP status",
    )
    assert_true(
        "block behind active inference" in switchboard_text
        and "connect=0.35" in switchboard_text
        and 'client.get(f"{LLAMA_URL}/metrics")' in switchboard_text,
        "switchboard /health should not block dashboard probes on optional llama metrics",
    )
    assert_true(
        "stderr={stderr_text[:300]}" in qa_runner_text
        and "stdout={stdout_text[:300]}" in qa_runner_text
        and "aq-qa exited {proc.returncode}{detail}" in qa_runner_text,
        "dashboard qa_runner should preserve stdout/stderr snippets for unexpected aq-qa exits",
    )

    print("PASS: boot stability regressions are covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
