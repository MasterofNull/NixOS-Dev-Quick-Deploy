#!/usr/bin/env bash
# Runs the CI-hard checks listed in config/ci-checks.json. CI and local hooks call this same
# runner so they cannot drift. Usage:
#   run-ci-checks.sh --all [--only <id>]
#   run-ci-checks.sh --changed [--base origin/main] [--only <id>]
#   run-ci-checks.sh --list [--changed]   # print selected ids only
# A manifest entry may carry an "env" object (string vars set for that check only).
# Merge-commit parity (CI tests the PR merge commit): scripts/governance/ci-merge-parity.sh
# Env: CI_CHECKS_MANIFEST overrides the manifest path; CI_CHECKS_CHANGED_FILES (newline list)
# overrides git change detection (tests).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
exec python3 - "$@" <<'PY'
import fnmatch, json, os, re, shutil, subprocess, sys, time

def glob_re(p):
    out, i = "", 0
    while i < len(p):
        if p.startswith("**/", i): out += "(?:.*/)?"; i += 3
        elif p.startswith("**", i): out += ".*"; i += 2
        elif p[i] == "*": out += "[^/]*"; i += 1
        elif p[i] == "?": out += "[^/]"; i += 1
        else: out += re.escape(p[i]); i += 1
    return re.compile("^" + out + "$")

def matches(paths, files):
    return not paths or any(glob_re(p).match(f) for p in paths for f in files)

def git_lines(*a):
    r = subprocess.run(["git", *a], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l] if r.returncode == 0 else None

def main(argv):
    mode, base, only, list_only = None, "origin/main", [], False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--all", "--changed"): mode = a[2:]
        elif a == "--base": i += 1; base = argv[i]
        elif a == "--only": i += 1; only.append(argv[i])
        elif a == "--list": list_only = True
        else: print(f"unknown arg: {a}", file=sys.stderr); return 2
        i += 1
    if mode is None and not list_only: print(__doc__ or "usage: --all|--changed", file=sys.stderr); return 2
    mode = mode or "all"
    manifest = json.load(open(os.environ.get("CI_CHECKS_MANIFEST", "config/ci-checks.json")))
    checks = manifest["checks"]
    if only:
        unknown = set(only) - {c["id"] for c in checks}
        if unknown: print(f"FAIL: unknown check id(s): {sorted(unknown)}", file=sys.stderr); return 2
        checks = [c for c in checks if c["id"] in only]
    if mode == "changed":
        env = os.environ.get("CI_CHECKS_CHANGED_FILES")
        if env is not None: files = [l for l in env.splitlines() if l]
        else:
            d1 = git_lines("diff", "--name-only", f"{base}...HEAD")
            d2 = git_lines("diff", "--name-only", "--cached")
            if d1 is None or d2 is None:
                print(f"WARN: git diff against {base} failed (missing base or no merge-base/shallow clone); running ALL checks", file=sys.stderr)
                files = None
            else: files = set(d1) | set(d2)
        if files is not None: checks = [c for c in checks if matches(c.get("paths", []), files)]
    if list_only:
        print("\n".join(c["id"] for c in checks)); return 0
    ci = os.environ.get("CI", "").lower() == "true"
    results = []
    for c in checks:
        missing = [t for t in c.get("needs", []) if not shutil.which(t)]
        if missing:
            results.append((c["id"], "FAIL" if ci else "WARN", f"missing tool: {','.join(missing)}")); continue
        parts = c["cmd"].split()
        if not os.path.isfile(parts[0]): results.append((c["id"], "FAIL", f"script not found: {parts[0]}")); continue
        t = time.time()
        interp = ["python3"] if parts[0].endswith(".py") else ["bash"]
        r = subprocess.run(interp + parts, capture_output=True, text=True, env={**os.environ, **c.get("env", {})})
        dt = f"{time.time()-t:.1f}s"
        if r.returncode == 0: results.append((c["id"], "PASS", dt))
        else:
            lines = (r.stdout + r.stderr).strip().splitlines()
            tail = "\n".join(lines if ci else lines[-15:])  # CI keeps full output
            results.append((c["id"], "FAIL", f"rc={r.returncode} {dt}\n{tail}"))
    for cid, st, note in results: print(f"[{st}] {cid}: {note}")
    if not results: print("run-ci-checks: no checks selected")
    fails = [r for r in results if r[1] == "FAIL"]
    print(f"run-ci-checks: {sum(r[1]=='PASS' for r in results)} pass, {len(fails)} fail, {sum(r[1]=='WARN' for r in results)} warn")
    return 1 if fails else 0

sys.exit(main(sys.argv[1:]))
PY
