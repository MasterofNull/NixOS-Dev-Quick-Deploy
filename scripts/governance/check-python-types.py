#!/usr/bin/env python3
"""Python type/lint gate: basedpyright + ruff compared against a baseline that only shrinks.

  check-python-types.py --staged            staged .py files (tier0 --pre-commit)
  check-python-types.py --all               every tracked .py file (CI)
  check-python-types.py --write-baseline    regenerate config/python-check-baseline.json from the full tree;
                                            refuses to grow any count unless --allow-growth (give a reason in the commit)

A diagnostic is fingerprinted as (tool, path, rule, message) with no line/column, so moving code is not new.
Only fingerprints whose count rose above the baseline fail (Rule 19 gate corollary). A tool that is neither on PATH
nor buildable from the repo flake's pinned nixpkgs FAILs; it is never skipped.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys

BASELINE = "config/python-check-baseline.json"
TOOLS = {"basedpyright": "basedpyright", "ruff": "ruff"}  # tool -> attr in the repo flake's pinned nixpkgs
EXCLUDE_PARTS = {"archive", "archived", "node_modules", "__pycache__"}
EXCLUDE_PREFIXES = (".agent/archive/", ".agents/archive/", ".agents/delegation/")


def run(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def excluded(path):
    parts = path.split("/")
    return (path.startswith(EXCLUDE_PREFIXES) or fnmatch.fnmatch(parts[0], "result*")
            or any(p in EXCLUDE_PARTS for p in parts[:-1]))


def git_files(root, args):
    r = run(["git", *args], root)
    if r.returncode != 0:
        raise SystemExit(f"FAIL: git {' '.join(args)} failed: {r.stderr.strip()}")
    return [f for f in r.stdout.splitlines() if f.endswith(".py") and not excluded(f)
            and os.path.isfile(os.path.join(root, f))]


def resolve_tool(name, root):
    found = shutil.which(name)
    if found:
        return found
    nix = shutil.which("nix")
    if nix:
        # --inputs-from pins nixpkgs to the repo's flake.lock without adding flake outputs that
        # `nix flake check --all-systems` would have to evaluate (that load killed the CI runner).
        r = run([nix, "build", "--no-link", "--print-out-paths", "--inputs-from", str(root),
                 f"nixpkgs#{TOOLS[name]}"], root)
        out = r.stdout.split()
        if r.returncode == 0 and out:
            cand = os.path.join(out[0], "bin", name)
            if os.access(cand, os.X_OK):
                return cand
        detail = r.stderr.strip().splitlines()[-1:] or ["no output"]
    else:
        detail = ["nix not on PATH"]
    raise SystemExit(f"FAIL: {name} not on PATH and not buildable from the flake ({detail[0]})")


def norm(msg):
    return re.sub(r"\s+", " ", msg).strip()


def rel(root, p):
    return os.path.relpath(p, root) if os.path.isabs(p) else p


def collect(root, files):
    """Return {fingerprint: count} over all tools for the given files."""
    counts = {}
    if not files:
        return counts
    bp = resolve_tool("basedpyright", root)
    ruff = resolve_tool("ruff", root)
    r = run([bp, "--outputjson", *files], root)
    try:
        diags = json.loads(r.stdout)["generalDiagnostics"]
    except (ValueError, KeyError):
        raise SystemExit(f"FAIL: basedpyright produced no JSON (rc={r.returncode}): {r.stderr.strip()[:300]}")
    for d in diags:
        if d.get("severity") != "error":
            continue
        key = "|".join(("basedpyright", rel(root, d["file"]), d.get("rule", ""), norm(d["message"])))
        counts[key] = counts.get(key, 0) + 1
    r = run([ruff, "check", "--output-format", "json", "--force-exclude", "--no-cache", *files], root)
    try:
        diags = json.loads(r.stdout or "[]")
    except ValueError:
        raise SystemExit(f"FAIL: ruff produced no JSON (rc={r.returncode}): {r.stderr.strip()[:300]}")
    for d in diags:
        key = "|".join(("ruff", rel(root, d["filename"]), d.get("code") or "", norm(d["message"])))
        counts[key] = counts.get(key, 0) + 1
    return counts


def totals(counts):
    t = {name: 0 for name in TOOLS}
    for k, n in counts.items():
        t[k.split("|", 1)[0]] += n
    return t


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--staged", action="store_true")
    g.add_argument("--all", action="store_true")
    g.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--allow-growth", action="store_true")
    a = ap.parse_args(argv)
    top = run(["git", "rev-parse", "--show-toplevel"], os.getcwd())
    if top.returncode != 0:
        raise SystemExit("FAIL: not inside a git repository")
    root = top.stdout.strip()
    bpath = os.path.join(root, BASELINE)
    base = {}
    if os.path.isfile(bpath):
        base = json.load(open(bpath)).get("counts", {})

    if a.staged:
        files = git_files(root, ["diff", "--cached", "--name-only", "--diff-filter=ACM"])
        if files:
            dirty = run(["git", "diff", "--name-only", "--", *files], root).stdout.split()
            if dirty:
                print("FAIL: staged Python files have unstaged changes; stage or revert them so the gate checks "
                      "what you commit:")
                for f in dirty:
                    print(f"  {f}")
                return 1
    else:
        files = git_files(root, ["ls-files", "*.py"])
    cur = collect(root, files)

    if a.write_baseline:
        grown = {k: (base.get(k, 0), n) for k, n in cur.items() if n > base.get(k, 0)}
        if base and grown and not a.allow_growth:
            print(f"FAIL: --write-baseline would grow {len(grown)} count(s); pass --allow-growth with a reason in the commit:")
            for k, (b, n) in sorted(grown.items())[:20]:
                print(f"  {b} -> {n}  {k}")
            return 1
        os.makedirs(os.path.dirname(bpath), exist_ok=True)
        with open(bpath, "w") as f:
            json.dump({"version": 1, "totals": totals(cur), "counts": dict(sorted(cur.items()))}, f, indent=1)
            f.write("\n")
        print(f"baseline written: {totals(cur)} ({len(cur)} fingerprints)")
        return 0

    new = {k: (base.get(k, 0), n) for k, n in cur.items() if n > base.get(k, 0)}
    if new:
        print(f"FAIL: {len(new)} new Python diagnostic fingerprint(s) over the baseline ({len(files)} files checked):")
        for k, (b, n) in sorted(new.items()):
            tool, path, rule, msg = k.split("|", 3)
            print(f"  [{tool}] {path}: {rule}: {msg} (baseline {b}, now {n})")
        return 1
    print(f"PASS: python type/lint gate, {len(files)} files, {totals(cur)} within baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
