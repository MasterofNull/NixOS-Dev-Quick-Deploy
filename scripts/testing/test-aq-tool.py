#!/usr/bin/env python3
"""Regression checks for aq-tool — live, on-demand reach to the factory's
PINNED nixpkgs (ST-2, .agents/plans/factory-shared-toolchain/DESIGN.md).
No restart, no manifest/permission gate. Never fakes a pass: if the sandbox
cannot run `nix` at all, the nix-invoking cases SKIP with a clear message
instead of being reported as passed."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CMD = ROOT / "scripts" / "ai" / "aq-tool"


def run(*args: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CMD), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def nix_usable() -> bool:
    """Live probe, never assumed: is `nix` present and does it actually run.
    A sandboxed/offline environment with no nix daemon returns False here,
    and the caller SKIPs the nix-invoking cases rather than faking a pass."""
    if shutil.which("nix") is None:
        return False
    try:
        proc = subprocess.run(
            ["nix", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def resolved_pinned_ref() -> str:
    lock = json.loads((ROOT / "flake.lock").read_text(encoding="utf-8"))
    root_node = lock["nodes"][lock["root"]]
    nixpkgs_node = root_node["inputs"]["nixpkgs"]
    locked = lock["nodes"][nixpkgs_node]["locked"]
    return f"github:{locked['owner']}/{locked['repo']}/{locked['rev']}"


def main() -> int:
    # --- (c) read-only paths never invoke nix; always exercised ---
    listing = run("--list")
    check(listing.returncode == 0, f"--list exited {listing.returncode}: {listing.stderr}")
    check("aq-tool" in listing.stdout, "--list output missing usage banner")
    check(
        "hello" in listing.stdout and "jq" in listing.stdout,
        "--list missing expected curated tool names",
    )

    listing_alias = run("list")
    check(listing_alias.returncode == 0, "bare 'list' subcommand should also work")
    check(listing_alias.stdout == listing.stdout, "'list' and '--list' should be identical")

    helped = run("--help")
    check(helped.returncode == 0, f"--help exited {helped.returncode}: {helped.stderr}")
    check("aq-tool" in helped.stdout, "--help output missing usage text")

    no_args = run()
    check(no_args.returncode == 0, "no-args should print help, not error")

    # malformed package name must be refused before any nix invocation
    malformed = run("not a valid pkg name!")
    check(malformed.returncode != 0, "malformed package name must be refused")
    check("refus" in malformed.stderr.lower(), f"expected a 'refusing' message, got: {malformed.stderr}")

    print("PASS: aq-tool --list/--help/arg-parsing/error-formatting (no nix invoked)")

    # --- (a)/(b) nix-invoking cases: SKIP cleanly if nix is unusable here ---
    if not nix_usable():
        print(
            "SKIP: nix is unavailable or non-functional in this sandbox — "
            "skipped the nix-invoking cases (known-pkg exec forwarding + "
            "unknown-pkg typed 'tool unavailable' message). Re-run on a host "
            "with a working nix daemon to exercise them."
        )
        print("PASS (partial — read-only paths only): scripts/testing/test-aq-tool.py")
        return 0

    ref = resolved_pinned_ref()
    check(ref.startswith("github:"), f"unexpected pinned nixpkgs ref shape: {ref}")

    # (a) known trivial pkg: forwards exit code + args, resolved against the pinned ref
    known = run("hello", "--version", timeout=180)
    check(known.returncode == 0, f"known pkg 'hello' should run and exit 0: {known.stderr}")
    check("hello" in known.stdout.lower(), f"hello --version output should mention 'hello', got: {known.stdout!r}")

    # a legitimate non-zero exit FROM the tool itself must be forwarded as-is,
    # never rewritten into the "tool unavailable" message
    own_failure = run("hello", "--made-up-flag-xyz", timeout=180)
    check(own_failure.returncode != 0, "hello with a bad flag should exit non-zero")
    check(
        "tool unavailable" not in own_failure.stderr,
        "a tool's own non-zero exit must not be reported as 'tool unavailable'",
    )

    # (b) unknown pkg: typed message, non-zero exit, never hangs (bounded timeout above)
    unknown = run("definitely-not-a-real-package-xyz123", timeout=180)
    check(unknown.returncode != 0, "unknown pkg must exit non-zero")
    check(
        "tool unavailable: definitely-not-a-real-package-xyz123" in unknown.stderr,
        f"unknown pkg must print the typed unavailable message, got: {unknown.stderr}",
    )
    check(
        "(not in pinned nixpkgs)" in unknown.stderr,
        f"unavailable message must name the pinned-nixpkgs reason, got: {unknown.stderr}",
    )

    print("PASS: aq-tool live pinned-nixpkgs reach (known-pkg forwarding + unknown-pkg typed refusal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
