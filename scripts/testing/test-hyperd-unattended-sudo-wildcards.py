#!/usr/bin/env python3
"""Static regression checks: hyperd has no broad NOPASSWD sudo wildcards (owner boundary)."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_CLASS_PATH = REPO_ROOT / "nix/modules/host-classes/p14s-amd-ai-workstation.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = HOST_CLASS_PATH.read_text(encoding="utf-8")

    forbidden_commands = [
        '/Documents/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh *',
        '/run/current-system/sw/bin/nixos-rebuild *',
        '/run/current-system/sw/bin/systemctl *',
        '/run/current-system/sw/bin/journalctl *',
        '/run/current-system/sw/bin/flatpak *',
        'scripts/ai/aq-model-switch *',
    ]
    for command in forbidden_commands:
        assert_true(
            command not in text,
            f"root-equivalent command must not have a NOPASSWD rule: {command}",
        )
    assert_true(
        "NOPASSWD" not in text.replace("No NOPASSWD", ""),
        "host class must not declare any NOPASSWD sudo rule",
    )

    print("PASS: hyperd host class declares no NOPASSWD sudo rules")


if __name__ == "__main__":
    main()
