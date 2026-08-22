#!/usr/bin/env python3
"""Hermetic contract guard for llama.cpp AppArmor attachment."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    role = (ROOT / "nix/modules/roles/ai-stack.nix").read_text(encoding="utf-8")
    phase0 = (ROOT / "scripts/testing/harness_qa/phases/phase0.py").read_text(
        encoding="utf-8"
    )

    check(
        'llamaServerExec = "${pkgs.llama-cpp}/bin/llama-server";' in role,
        "llama service does not use the package executable directly",
    )
    check("llama-server-unconfined" not in role, "unconfined llama binary bypass returned")
    check(
        'AppArmorProfile = "ai-llama-cpp";' in role,
        "llama systemd unit does not explicitly request the profile",
    )
    check(
        "assertion = !llama.enable || config.security.apparmor.enable;" in role,
        "llama enablement does not fail Nix evaluation when AppArmor is disabled",
    )
    check(
        'RestrictAddressFamilies = ["AF_UNIX" "AF_INET" "AF_INET6"];' in role,
        "llama systemd unit does not restrict address families",
    )
    check(
        'CapabilityBoundingSet = ["CAP_IPC_LOCK"];' in role,
        "llama systemd unit retains an over-broad capability set",
    )
    check(
        "profile ai-llama-cpp ${pkgs.llama-cpp}/bin/llama-server {" in role,
        "profile attachment is not bound to the selected package executable",
    )
    check(
        "${pkgs.coreutils}/bin/coreutils ix," in role
        and "${pkgs.curl}/bin/curl ix," in role
        and "/nix/store/** ix," not in role,
        "readiness probe helpers are not narrowly executable inside the llama profile",
    )
    check(
        '"0.3.3"' in phase0
        and 'expected_runtime = "ai-llama-cpp (enforce)"' in phase0
        and '"--property=AppArmorProfile"' in phase0
        and '"--property=MainPID"' in phase0
        and 'attr/current' in phase0,
        "phase0 lacks an effective runtime confinement probe",
    )
    print("PASS: llama AppArmor contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
