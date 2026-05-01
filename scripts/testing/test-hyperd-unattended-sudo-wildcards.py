#!/usr/bin/env python3
"""Static regression checks for hyperd unattended sudo wildcard coverage."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_CLASS_PATH = REPO_ROOT / "nix/modules/host-classes/p14s-amd-ai-workstation.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = HOST_CLASS_PATH.read_text(encoding="utf-8")

    expected_commands = [
        '/Documents/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh *',
        '/run/current-system/sw/bin/nixos-rebuild *',
        '/run/current-system/sw/bin/systemctl *',
        '/run/current-system/sw/bin/journalctl *',
        '/run/current-system/sw/bin/flatpak *',
    ]
    for command in expected_commands:
        assert_true(
            command in text,
            f"expected unattended sudo rule to include wildcard command {command}",
        )

    print("PASS: hyperd unattended sudo rules allow bounded argument-bearing commands")


if __name__ == "__main__":
    main()
