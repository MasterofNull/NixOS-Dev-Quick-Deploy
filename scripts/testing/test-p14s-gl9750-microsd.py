#!/usr/bin/env python3
"""Static contract for the host-scoped GL9750 microSD data-integrity workaround."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOST_CLASS = ROOT / "nix/modules/host-classes/p14s-amd-ai-workstation.nix"


def main() -> int:
    text = HOST_CLASS.read_text(encoding="utf-8")
    guard = (
        'cfg.profile\n    == "ai-dev"\n'
        '    && cfg.hardware.nixosHardwareModule == "lenovo-thinkpad-p14s-amd-gen2"'
    )
    assert guard in text, "P14s workaround must remain behind the exact host-class guard"
    assert text.count('"sdhci.debug_quirks=0x60"') == 1, "GL9750 quirk must be declared exactly once"
    assert "Disable SDHCI DMA + ADMA" in text, "PIO safety tradeoff must remain documented"
    assert "pcie_aspm=off" not in text, "do not replace the narrow reader quirk with global ASPM disable"
    print("test-p14s-gl9750-microsd: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
