#!/usr/bin/env python3
"""Static regression checks for COSMIC greeter stability scaffolding."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESKTOP_MODULE = ROOT / "nix" / "modules" / "roles" / "desktop.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = DESKTOP_MODULE.read_text(encoding="utf-8")
    assert_true(
        'com.system76.CosmicTheme.Dark.Builder' in text,
        "desktop role should create COSMIC greeter Dark.Builder directories",
    )
    assert_true(
        'systemd.services.cosmic-greeter-config-seed' in text,
        "desktop role should seed minimal COSMIC greeter config before greetd",
    )
    assert_true(
        'before = [ "greetd.service" "cosmic-greeter-daemon.service" ];' in text,
        "COSMIC greeter config seed should run before greeter startup",
    )
    assert_true(
        'Royal Wine-inner.ron' in text,
        "COSMIC greeter config seed should reuse the declarative palette source",
    )
    assert_true(
        'rm -rf "$base/com.system76.CosmicTheme.Dark.Builder/v1"' in text,
        "COSMIC greeter config seed should wipe stale builder files before startup",
    )
    print("PASS: desktop role seeds minimal COSMIC greeter config declaratively")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
