#!/usr/bin/env python3
"""Verify Ralph server configuration and unit Nix evaluation."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_service_path() -> None:
    """Verify Ralph's systemd service includes Python in PATH."""
    result = subprocess.run(
        [
            "nix", "eval", "--json",
            ".#nixosConfigurations.hyperd-ai-dev.config.systemd.services.ai-ralph-wiggum.path",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    service_path = json.loads(result.stdout)
    check(
        any("python" in entry.lower() for entry in service_path),
        f"Ralph service PATH must include its Python runtime; got {service_path!r}",
    )


if __name__ == "__main__":
    check_service_path()
    print("PASS: Ralph systemd service configured correctly")
