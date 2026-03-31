#!/usr/bin/env python3
"""Static regression checks for audit defaults and classified overrides."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPTIONS = ROOT / "nix" / "modules" / "core" / "options.nix"
HOSPITAL = ROOT / "nix" / "modules" / "core" / "hospital-classified.nix"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    options_text = OPTIONS.read_text(encoding="utf-8")
    hospital_text = HOSPITAL.read_text(encoding="utf-8")

    assert_true(
        "default = false;" in options_text,
        "general systems should not enable kernel audit by default",
    )
    assert_true(
        "hospital/classified mode explicitly force this on" in options_text,
        "audit option description should document the classified override",
    )
    assert_true(
        'mySystem.logging.audit.enable = lib.mkDefault true;' in hospital_text,
        "hospital/classified posture should keep audit enabled",
    )
    assert_true(
        'Hospital/classified posture requires mySystem.logging.audit.enable=true' in hospital_text,
        "hospital/classified posture should assert audit stays enabled",
    )

    print("PASS: audit defaults are opt-in while hospital/classified posture remains enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
