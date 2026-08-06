#!/usr/bin/env python3
"""Deploy-context preflight for the execution-cell runner (WR-3 / T2).

Statically asserts — WITHOUT a live deploy/rebuild — that the runner's Nix deployment surface
is complete. This is the class of gap that cost five rebuilds during R7, each discoverable only
live, one at a time:
  - #10 runnerBundle missing a module the runner imports at load -> crash-loop
  - #11 TRUSTED_REPO_MIRRORS not systemd-quote-safe (bare JSON) -> unknown-trusted-repo
  - #13 bare `git` not on the service PATH -> cell-create quarantine

Fail-safe by design: any parse ambiguity is a FAILURE (blocks), never a silent pass. Exit 0 iff
the deployment context is complete.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NIX = ROOT / "nix" / "modules" / "services" / "execution-cell-runner.nix"
LOCAL_DIRS = [ROOT / "scripts" / "ai" / "lib", ROOT / "ai-stack" / "switchboard"]


def local_module_names() -> set:
    names = set()
    for d in LOCAL_DIRS:
        if d.is_dir():
            for p in d.glob("*.py"):
                names.add(p.stem)
    return names


def bundle_sources(nix_text: str) -> dict:
    """module_name -> resolved source Path, parsed from the runnerBundle `cp` lines."""
    out = {}
    for m in re.finditer(r"cp \$\{(\.\.[^}]+?)\} \$out/([a-z_]+)\.py", nix_text):
        rel, base_out = m.group(1), m.group(2)
        out[base_out] = (NIX.parent / rel).resolve()
    return out


def top_level_imports(pyfile: Path) -> set:
    """Module names imported at MODULE level (these execute on import — the crash-at-load
    surface; in-function lazy imports only fail if that path runs, so they are out of scope)."""
    mods = set()
    tree = ast.parse(pyfile.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    return mods


def main() -> int:
    failures = []
    if not NIX.exists():
        print(f"FAIL: runner nix module missing: {NIX}")
        return 1
    nix_text = NIX.read_text(encoding="utf-8")
    locals_ = local_module_names()
    bundle = bundle_sources(nix_text)
    bundle_names = set(bundle)

    if "execution_cell_runner" not in bundle_names:
        failures.append("runnerBundle does not copy execution_cell_runner.py (parse gap or regression)")

    # 1. Bundle closure: every module-level LOCAL import in every bundled file must itself be
    #    bundled (cf #10 durable_reservation missing -> ModuleNotFoundError crash-loop).
    for name in sorted(bundle_names):
        src = bundle[name]
        if not src.exists():
            failures.append(f"bundle source missing on disk: {src}")
            continue
        for imp in sorted(top_level_imports(src)):
            if imp in locals_ and imp not in bundle_names:
                failures.append(
                    f"{name}.py imports local module '{imp}' not in runnerBundle "
                    f"(crash-at-load class, cf #10)"
                )

    # 2. git on the service PATH — create_cell + the out-of-cell validator invoke bare `git`
    #    (cf #13: absent git -> FAILURE_QUARANTINED at cell-create).
    if not re.search(r"path\s*=\s*\[\s*pkgs\.git\s*\]", nix_text):
        failures.append("runner service does not declare `path = [pkgs.git]` (bare-git deps -> cell-create quarantine, cf #13)")

    # 3. TRUSTED_REPO_MIRRORS must be single-quote-wrapped builtins.toJSON so systemd's
    #    quote-removal keeps the inner JSON quotes (cf #11: bare JSON -> {} -> unknown-trusted-repo).
    if not re.search(r"TRUSTED_REPO_MIRRORS='\$\{builtins\.toJSON", nix_text):
        failures.append("TRUSTED_REPO_MIRRORS is not single-quote-wrapped builtins.toJSON (systemd strips bare JSON quotes, cf #11)")

    if failures:
        print("FAIL: execution-cell-runner deploy-context preflight")
        for f in failures:
            print("  - " + f)
        return 1
    print(
        f"PASS: runner deploy-context complete "
        f"({len(bundle_names)} bundled modules; git on PATH; JSON env systemd-safe)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
