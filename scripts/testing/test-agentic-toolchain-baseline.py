#!/usr/bin/env python3
"""Check process utilities remain declared in both Nix package baselines."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]


def package_list(relative_path, name):
    source = (ROOT / relative_path).read_text()
    source = re.sub(r"/\*.*?\*/|#[^\n]*", "", source, flags=re.DOTALL)
    match = re.search(
        rf"\b{re.escape(name)}\s*=\s*(?:with\s+pkgs\s*;\s*)?\[([^\]]*)\]\s*;",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError(f"{relative_path}: missing {name} list")
    return match.group(1).split()


def main():
    baseline = package_list("nix/modules/roles/agentic-toolchain.nix", "baselinePackages")
    core = package_list("nix/modules/core/base.nix", "basePackageNames")
    checks = (
        ("psmisc" in baseline, "baselinePackages missing psmisc"),
        ('"psmisc"' in core, "basePackageNames missing psmisc"),
        ("procps" in baseline, "baselinePackages missing procps"),
    )
    failures = [message for passed, message in checks if not passed]
    for message in failures:
        print(f"FAIL {message}", file=sys.stderr)
    if failures:
        return 1
    print("PASS baseline toolchain psmisc declarations verified")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        sys.exit(1)
