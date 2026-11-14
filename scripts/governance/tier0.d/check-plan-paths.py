#!/usr/bin/env python3
"""tier0.d: plan reality check. A staged plan cites repo files that do not exist unless the line says NEW.

Scope: staged .agents/plans/**/*.md and .agent/PROJECT-*.md. A backticked token counts as a repo path when it has a
'/' and either a file extension or a scripts/ nix/ docs/ config/ ai-stack/ prefix. A line containing "NEW" or "(new)"
declares the path as not-yet-created. Globs, placeholders, URLs and absolute paths are ignored.
"""
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("PLAN_PATHS_ROOT") or subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
SCOPE = (".agents/plans/**/*.md", ".agent/PROJECT-*.md")
PREFIXES = ("scripts/", "nix/", "docs/", "config/", "ai-stack/")
TICK = re.compile(r"`([^`\s]+)`")
NEW = re.compile(r"\bNEW\b|\(new\)")
SKIP = re.compile(r"[*<>{}$|\\]|://|^[/~.]|^\w+@")


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout


def looks_like_path(tok):
    tok = re.sub(r":\d+(?::\d+)?$", "", tok.rstrip(".,;:)"))
    if SKIP.search(tok) or "/" not in tok:
        return None
    if tok.startswith(PREFIXES) or re.search(r"\.[A-Za-z0-9]{1,6}$", tok):
        return tok
    return None


def main():
    staged = [p for p in git("diff", "--cached", "--name-only", "--diff-filter=AM").splitlines()
              if any(fnmatch.fnmatch(p, g) for g in SCOPE)]
    bad = []
    for path in staged:
        text = git("show", f":{path}")
        for n, line in enumerate(text.splitlines(), 1):
            if NEW.search(line):
                continue
            for tok in TICK.findall(line):
                rel = looks_like_path(tok)
                if rel and not (ROOT / rel).exists():
                    bad.append(f"{path}:{n}: `{rel}` does not exist (mark the line NEW if it will be created)")
    if bad:
        print("[tier0.d/check-plan-paths] FAIL: plan cites missing repo paths:", file=sys.stderr)
        for b in bad:
            print(f"  {b}", file=sys.stderr)
        return 1
    print(f"[tier0.d/check-plan-paths] PASS: {len(staged)} staged plan file(s) cite only existing paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
