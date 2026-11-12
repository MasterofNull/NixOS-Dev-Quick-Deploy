#!/usr/bin/env python3
"""Static regression check for the VSCodium GPU mitigation."""

from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_NIX = REPO_ROOT / "nix" / "home" / "base.nix"


REQUIRED_SNIPPETS = [
    '"disable-hardware-acceleration" = true;',
    '"ozone-platform" = "x11";',
    '--add-flags --ozone-platform=x11',
    'home.file.".config/VSCodium/User/argv.json".source = vscodiumArgvJSON;',
]


def main() -> int:
    text = BASE_NIX.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    # alejandra puts the writeText call on the line after `vscodiumArgvJSON =`.
    if not re.search(r'vscodiumArgvJSON\s*=\s*pkgs\.writeText\s+"vscodium-argv-baseline\.json"', text):
        missing.append('vscodiumArgvJSON = pkgs.writeText "vscodium-argv-baseline.json"')
    if missing:
        print("Missing VSCodium GPU mitigation snippets:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1
    print("PASS: VSCodium GPU mitigation is configured declaratively")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
