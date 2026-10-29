#!/usr/bin/env python3
"""Activation manifest gate (Rules 15/23, P5.2).

Validates config/activation-manifest.json and requires every NEW runtime
entrypoint (relative to a base ref, or the index with --staged) to be named in it.

Per-entry checks: entrypoint exists; live_caller exists and references the
entrypoint's basename/stem; health_signal "<path>:<symbol>" file exists and holds
the symbol; a non-null `enable` option is set to true somewhere under nix/ (never in
options.nix or the declaring module). A valid dated `deferral` excuses the
live_caller-reference and enable checks only; a deferral older than 90 days is a
WARN (time-based signals never block commits, Rule 19 corollary).

Enable-match limits (textual, not a Nix evaluation): matches
`<full.path> = true`, or `<parent-last-segment> = { ... enable = true` with no
intervening `}`. Optional lib.mkDefault/mkForce around `true` is accepted. Option
values computed through let-bindings, `inherit`, or attrset merges are NOT seen.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from clean_git_env import clean_git_env  # noqa: E402

TAG = "[activation-manifest]"
STALE_DAYS = 90
MANIFEST_REL = "config/activation-manifest.json"
SYSTEMD_RE = re.compile(r'systemd\.(?:user\.)?services\.("?)([A-Za-z0-9_@-]+)\1')
TRUE_RE = r"(?:lib\.)?(?:mkDefault\s+|mkForce\s+)?true"

fails = []
warns = []


def fail(msg):
    fails.append(msg)
    print(f"{TAG} FAIL: {msg}")


def warn(msg):
    warns.append(msg)
    print(f"{TAG} WARN: {msg}")


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       env=clean_git_env())
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def read(repo, rel):
    try:
        return (repo / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def valid_deferral(d):
    if not isinstance(d, dict):
        return None
    try:
        when = datetime.strptime(str(d.get("date", "")), "%Y-%m-%d").date()
    except ValueError:
        return None
    if not str(d.get("reason", "")).strip():
        return None
    return when


def enable_is_set(repo, opt):
    parent, _, leaf = opt.rpartition(".")
    last = parent.rpartition(".")[2] or leaf
    full = re.compile(re.escape(opt) + r"\s*=\s*" + TRUE_RE + r"\b")
    block = re.compile(r"\b" + re.escape(last) + r"\s*=\s*\{[^}]*?\b" + re.escape(leaf)
                       + r"\s*=\s*" + TRUE_RE + r"\b", re.S)
    declare = "options." + parent
    for p in sorted((repo / "nix").rglob("*.nix")):
        rel = p.relative_to(repo).as_posix()
        if rel == "nix/modules/core/options.nix":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if declare in text:
            continue
        if full.search(text) or block.search(text):
            return rel
    return None


def check_entries(repo, features):
    for i, f in enumerate(features):
        name = f.get("feature") or f"#{i}"
        ep, lc, hs = f.get("entrypoint"), f.get("live_caller"), f.get("health_signal")
        if not (ep and lc and hs):
            fail(f"{name}: entrypoint, live_caller and health_signal are required")
            continue
        deferral = f.get("deferral")
        when = valid_deferral(deferral) if deferral else None
        if deferral and when is None:
            fail(f"{name}: deferral needs a valid YYYY-MM-DD date and non-empty reason")
        if when and (date.today() - when).days > STALE_DAYS:
            warn(f"{name}: deferral from {when} is older than {STALE_DAYS} days "
                 f"(tracking: {deferral.get('tracking', 'none')})")
        if not (repo / ep).exists():
            fail(f"{name}: entrypoint {ep} does not exist")
        lc_text = read(repo, lc)
        if lc_text is None:
            fail(f"{name}: live_caller {lc} does not exist")
        elif not when:
            base = Path(ep).name
            if base not in lc_text and Path(ep).stem not in lc_text:
                fail(f"{name}: live_caller {lc} does not reference {base}")
        path, _, symbol = hs.partition(":")
        hs_text = read(repo, path)
        if hs_text is None:
            fail(f"{name}: health_signal file {path} does not exist")
        elif not symbol or symbol not in hs_text:
            fail(f"{name}: health_signal symbol '{symbol}' not found in {path}")
        enable = f.get("enable")
        if enable and not when and not enable_is_set(repo, enable):
            fail(f"{name}: option {enable} is set to true nowhere under nix/ and no deferral")
        if when:
            print(f"{TAG} deferred: {name} ({when})")


def resolve_base(repo, base):
    if base:
        return base
    for ref in ("origin/main", "origin/master", "main"):
        out = git(repo, "merge-base", "HEAD", ref, check=False).strip()
        if out:
            return out
    return None


def added_lines_nix(repo, diff_args):
    """Map nix file -> list of added lines (diff vs base/index + untracked files)."""
    result = {}
    cur = None
    for line in git(repo, "diff", "-U0", "--no-color", *diff_args, "--", "*.nix").splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            result.setdefault(cur, [])
        elif line.startswith("+") and not line.startswith("+++") and cur:
            result[cur].append(line[1:])
    return result


def detect_new(repo, staged, base):
    if staged:
        # While merging, compare against the incoming side: files main brought in are not
        # new in this change (Rule 19 corollary).
        merging = git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).strip()
        diff_args = ["--cached", merging] if merging else ["--cached"]
        added = git(repo, "diff", *diff_args, "--name-only", "--diff-filter=A").split()
        untracked = []
    else:
        resolved = resolve_base(repo, base)
        if not resolved:
            warn("no base ref resolvable; new-entrypoint detection skipped")
            return []
        diff_args = [resolved]
        added = git(repo, "diff", resolved, "--name-only", "--diff-filter=A").split()
        untracked = git(repo, "ls-files", "--others", "--exclude-standard").split()
    new_files = sorted(set(added) | set(untracked))
    found = []
    for p in new_files:
        parts = p.split("/")
        if (len(parts) == 3 and p.startswith("scripts/ai/aq-")
                and Path(p).suffix in ("", ".py")):
            found.append(("file", p))
        elif (len(parts) == 4 and p.startswith("nix/modules/services/")
              and p.endswith(".nix") and parts[-1] != "default.nix"):
            found.append(("file", p))
    nix_adds = added_lines_nix(repo, diff_args)
    for p in untracked:
        if p.endswith(".nix"):
            nix_adds.setdefault(p, []).extend((read(repo, p) or "").splitlines())
    units = set()
    for lines in nix_adds.values():
        for ln in lines:
            for m in SYSTEMD_RE.finditer(ln):
                units.add(m.group(2))
    found += [("unit", u) for u in sorted(units)]
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", help="base ref (default: merge-base with origin/main)")
    ap.add_argument("--staged", action="store_true", help="compare the index")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    args = ap.parse_args()
    repo = Path(args.repo_root).resolve()

    raw = read(repo, MANIFEST_REL)
    if raw is None:
        fail(f"{MANIFEST_REL} missing")
        return 1
    try:
        manifest = json.loads(raw)
        features = manifest["features"]
        assert manifest.get("schema_version") == 1 and isinstance(features, list)
    except (ValueError, KeyError, AssertionError):
        fail(f"{MANIFEST_REL} is not valid (need schema_version 1 and a features list)")
        return 1

    check_entries(repo, features)

    named = set()
    for f in features:
        named.update(x for x in (f.get("entrypoint"), f.get("live_caller")) if x)
    blob = json.dumps(features)
    try:
        for kind, item in detect_new(repo, args.staged, args.base):
            if kind == "file" and item not in named:
                fail(f"new entrypoint {item} has no entry in {MANIFEST_REL}")
            elif kind == "unit" and item not in blob:
                fail(f"new systemd unit '{item}' is not named in any {MANIFEST_REL} entry")
    except RuntimeError as exc:
        warn(f"new-entrypoint detection skipped: {exc}")

    print(f"{TAG} {len(features)} entries, {len(fails)} fail, {len(warns)} warn")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
