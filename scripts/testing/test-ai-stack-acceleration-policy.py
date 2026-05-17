#!/usr/bin/env python3
"""Static regression check for AMD AI-stack acceleration defaults."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
AI_STACK_MODULE = REPO_ROOT / "nix" / "modules" / "roles" / "ai-stack.nix"
HARDWARE_LIB = REPO_ROOT / "nix" / "lib" / "ai-stack-hardware.nix"
HARDWARE_PROFILES = REPO_ROOT / "config" / "ai-stack-hardware-profiles.json"


REQUIRED_SNIPPETS = {
    AI_STACK_MODULE: [
        'then "vulkan" # Stable default for AMD APUs/iGPUs and generic AMD hosts',
        '# Keep ROCm explicit-only: generic AMD auto-detection must stay on Vulkan',
    ],
    HARDWARE_LIB: [
        'Supported accelerators:',
        'else if explicit == "rocm" then',
        '# ROCm is deprecated; remap to vulkan',
    ],
    HARDWARE_PROFILES: [
        '"status": "deprecated"',
        '"notes": "ROCm crashes on APUs; use Vulkan instead"',
        '"amd": "vulkan"',
    ],
}


def main() -> int:
    missing: list[str] = []

    for path, snippets in REQUIRED_SNIPPETS.items():
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                missing.append(f"{path.relative_to(REPO_ROOT)} :: {snippet}")

    if missing:
        print("AI-stack acceleration policy drift detected:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print("PASS: AMD auto-acceleration policy stays on Vulkan across runtime and canonical profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
