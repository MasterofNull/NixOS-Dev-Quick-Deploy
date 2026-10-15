#!/usr/bin/env bash
# tier0.d: every repo script (scripts/**) invoked by a workflow `run:` step must be a manifest
# entry cmd in config/ci-checks.json or listed in its ci_exempt (with a reason), so CI-only
# checks cannot exist without a local runner. Env overrides: CI_MANIFEST_FILE, CI_WORKFLOW_DIR.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export CI_MANIFEST_FILE="${CI_MANIFEST_FILE:-$REPO/config/ci-checks.json}"
export CI_WORKFLOW_DIR="${CI_WORKFLOW_DIR:-$REPO/.github/workflows}"
python3 - <<'PY'
import glob, json, os, re, sys
m = json.load(open(os.environ["CI_MANIFEST_FILE"]))
known = {c["cmd"].split()[0] for c in m["checks"]} | {"scripts/governance/run-ci-checks.sh", "scripts/governance/ci-clean-env.sh", "scripts/governance/ci-merge-parity.sh"}
exempt = {}
for e in m.get("ci_exempt", []):
    if not e.get("reason"): print(f"[tier0.d/check-ci-manifest-coverage] FAIL: ci_exempt {e.get('script')} has no reason", file=sys.stderr); sys.exit(1)
    exempt[e["script"]] = e["reason"]
root = os.path.dirname(os.path.dirname(os.environ["CI_MANIFEST_FILE"]))
miss = [e["script"] for e in m.get("ci_exempt", []) if not os.path.isfile(os.path.join(root, e["script"]))]
miss += [c["ci_workflow"] for c in m["checks"] if not os.path.isfile(os.path.join(root, c["ci_workflow"].split("#")[0]))]
if miss:
    for x in miss: print(f"[tier0.d/check-ci-manifest-coverage] FAIL: path does not exist: {x}", file=sys.stderr)
    sys.exit(1)
pat = re.compile(r"(?<![\w./-])(?:\./)?(scripts/[\w./-]+\.(?:sh|py))")
bad = {}
for wf in sorted(glob.glob(os.path.join(os.environ["CI_WORKFLOW_DIR"], "*.y*ml"))):
    for ln, line in enumerate(open(wf, encoding="utf-8"), 1):
        s = line.strip()
        if s.startswith("#") or s.startswith("uses:") or s.startswith("- uses:") or s.startswith("name:") or s.startswith("- name:"):
            continue
        if re.search(r"working-directory:\s*\.?/?scripts\b|\bcd\s+(\./)?scripts\b", line):
            print(f"[tier0.d/check-ci-manifest-coverage] WARN: {os.path.basename(wf)}:{ln} runs from scripts/ (relative script paths evade coverage)", file=sys.stderr)
        for p in pat.findall(line):
            if p not in known and p not in exempt:
                bad.setdefault(p, f"{os.path.basename(wf)}:{ln}")
if bad:
    for p, w in sorted(bad.items()):
        print(f"[tier0.d/check-ci-manifest-coverage] FAIL: {w} invokes {p}, not in config/ci-checks.json checks or ci_exempt", file=sys.stderr)
    sys.exit(1)
print("[tier0.d/check-ci-manifest-coverage] PASS")
PY
