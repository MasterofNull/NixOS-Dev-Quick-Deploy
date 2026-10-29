#!/usr/bin/env bash
# tier0.d: every scripts/testing/test-*.{py,sh} must be a config/ci-checks.json check cmd (or member of a check's `tests` list run by
# scripts/testing/run-test-group.py) or a
# test_exempt entry with a reason, so a test cannot exist that no gate ever runs (P0.5 of
# system-integrity-recovery: four red tests went unnoticed). Also fails on stale/duplicate
# exemptions. Env overrides: CI_MANIFEST_FILE, CI_TEST_ROOT (repo root to scan).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export CI_TEST_ROOT="${CI_TEST_ROOT:-$REPO}"
export CI_MANIFEST_FILE="${CI_MANIFEST_FILE:-$REPO/config/ci-checks.json}"
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
errs = []
exempt = {}
for e in m.get("test_exempt", []):
    s = e.get("script", "")
    if not (e.get("reason") or "").strip():
        errs.append(f"test_exempt {s or e} has no reason")
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
if errs:
    for e in errs:
        print(f"{TAG} FAIL: {e}", file=sys.stderr)
    print(f"{TAG} {len(errs)} problem(s); declare the test in config/ci-checks.json checks or add a test_exempt entry with a reason", file=sys.stderr)
    sys.exit(1)
print(f"{TAG} PASS ({len(tests)} tests: {len([t for t in tests if t in declared])} declared, {len([t for t in tests if t in exempt])} exempt)")
PY
