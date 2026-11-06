#!/usr/bin/env bash
# tier0.d: every scripts/testing/test-*.{py,sh} must be a config/ci-checks.json check cmd (or member of a check's `tests` list run by
# scripts/testing/run-test-group.py) or a
# test_exempt entry with a reason, so a test cannot exist that no gate ever runs (P0.5 of
# system-integrity-recovery: four red tests went unnoticed). Also fails on stale/duplicate
# exemptions. Each exemption needs a `class` (live-service|sandbox-env|known-failing|unstable|slow|mutates-state), and
# every check that runs a test must be invoked (`--only <id>`) by a workflow, so a declared test is actually run by CI.
# Env overrides: CI_MANIFEST_FILE, CI_TEST_ROOT (repo root to scan), CI_WORKFLOW_DIR.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export CI_TEST_ROOT="${CI_TEST_ROOT:-$REPO}"
export CI_MANIFEST_FILE="${CI_MANIFEST_FILE:-$REPO/config/ci-checks.json}"
export CI_WORKFLOW_DIR="${CI_WORKFLOW_DIR:-$CI_TEST_ROOT/.github/workflows}"
python3 - <<'PY'
import glob, json, os, re, sys
TAG = "[tier0.d/check-ci-test-coverage]"
root = os.environ["CI_TEST_ROOT"]
m = json.load(open(os.environ["CI_MANIFEST_FILE"]))
pat = re.compile(r"scripts/testing/test-[\w.-]+\.(?:py|sh)")
declared = set()
for c in m["checks"]:
    declared.update(pat.findall(c["cmd"]))
    declared.update(t for t in c.get("tests", []) if pat.fullmatch(t))
CLASSES = {"live-service", "sandbox-env", "known-failing", "unstable", "slow", "mutates-state"}
errs = []
exempt = {}
for e in m.get("test_exempt", []):
    s = e.get("script", "")
    if not (e.get("reason") or "").strip():
        errs.append(f"test_exempt {s or e} has no reason")
    if e.get("class") not in CLASSES:
        errs.append(f"test_exempt {s} has class {e.get('class')!r}; must be one of {sorted(CLASSES)}")
    if not os.path.isfile(os.path.join(root, s)):
        errs.append(f"test_exempt {s} does not exist (stale entry)")
    if s in declared:
        errs.append(f"test_exempt {s} is also a checks cmd (remove the exemption)")
    if s in exempt:
        errs.append(f"test_exempt {s} listed twice")
    exempt[s] = e.get("reason", "")
tests = sorted(os.path.relpath(p, root) for ext in ("py", "sh")
               for p in glob.glob(os.path.join(root, f"scripts/testing/test-*.{ext}")))
for t in tests:
    if t not in declared and t not in exempt:
        errs.append(f"{t} is not a config/ci-checks.json check cmd nor a test_exempt entry")
for d in sorted(declared):
    if not os.path.isfile(os.path.join(root, d)):
        errs.append(f"checks cmd references missing test {d}")
RUNNERS = {"run-ci-checks.sh", "ci-clean-env.sh"}


def run_only_ids(text):
    """--only ids from workflow run: commands that invoke the check runner (not comments, names, echoes)."""
    segs = []
    block = None  # column of a `run: |` key; deeper-indented lines belong to its script
    for raw in text.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw).rstrip()
        indent = len(line) - len(line.lstrip())
        if block is not None:
            if not line.strip() or indent > block:
                segs.append(line.strip())
                continue
            block = None
        m = re.match(r"\s*(?:-\s+)?run:\s*(.*)$", line)
        if m:
            if m.group(1) in ("|", "|-", "|+", ">", ">-", ">+"):
                block = line.index("run:")
            else:
                segs.append(m.group(1).strip())
    logical, cur = [], None
    for seg in segs:
        if cur is not None and cur.endswith("\\"):
            cur = cur[:-1] + " " + seg
        else:
            if cur is not None:
                logical.append(cur)
            cur = seg
    if cur is not None:
        logical.append(cur)
    ids = []
    for cmd in logical:
        for simple in re.split(r"&&|\|\||;|\|", cmd):
            words = simple.split()
            if words and os.path.basename(words[0]) in RUNNERS:
                ids += re.findall(r"--only ([\w-]+)", simple)
    return set(ids)


invoked = set()
for f in glob.glob(os.path.join(os.environ["CI_WORKFLOW_DIR"], "*.y*ml")):
    invoked |= run_only_ids(open(f, encoding="utf-8").read())
for c in m["checks"]:
    if (c.get("tests") or pat.search(c["cmd"])) and c["id"] not in invoked:
        errs.append(f"check {c['id']} runs tests but no workflow invokes it (--only {c['id']}); CI would never run it")
if errs:
    for e in errs:
        print(f"{TAG} FAIL: {e}", file=sys.stderr)
    print(f"{TAG} {len(errs)} problem(s); declare the test in config/ci-checks.json checks or add a test_exempt entry with a reason", file=sys.stderr)
    sys.exit(1)
print(f"{TAG} PASS ({len(tests)} tests: {len([t for t in tests if t in declared])} declared, {len([t for t in tests if t in exempt])} exempt)")
PY
