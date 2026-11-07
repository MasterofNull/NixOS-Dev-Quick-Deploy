#!/usr/bin/env python3
"""Tests for scripts/governance/sweep-gates.py: each finding class is detected on a fixture gate, and an honest gate is not flagged."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sweep_gates", ROOT / "scripts/governance/sweep-gates.py")
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)

TIER0 = r'''#!/usr/bin/env bash
set -euo pipefail
collect_changed_files() {
  git diff --cached --name-only 2>/dev/null || true
}
gate_prints_only() {
  log "x"
  pass "always"
}
gate_honest() {
  if bash ./true-gate.sh; then pass "ok"; else fail "bad"; return 1; fi
}
gate_empty_ok() {
  local files=()
  while IFS= read -r f; do files+=("$f"); done < <(collect_changed_files)
  if [[ ${#files[@]} -eq 0 ]]; then pass "No changes detected"; return 0; fi
  fail "x"
}
gate_never_called() {
  fail "x"
}
gate_prints_only || true
gate_honest || true
gate_empty_ok || true
TIER0D="${SCRIPT_DIR}/tier0.d"
for ext_check in "${TIER0D}"/*.sh; do bash "$ext_check"; done
'''
FILES = {
    "scripts/governance/tier0-validation-gate.sh": TIER0,
    "scripts/governance/tier0.d/check-always-pass.sh": "#!/usr/bin/env bash\necho checking\nexit 0\n",
    "scripts/governance/tier0.d/check-honest.sh": "#!/usr/bin/env bash\nset -euo pipefail\n[ -f needed.txt ] || { echo missing >&2; exit 1; }\n",
    "scripts/governance/tier0.d/check-skips-tool.sh":
        "#!/usr/bin/env bash\nset -euo pipefail\nif ! command -v zzz-missing >/dev/null 2>&1; then\n  echo skip\n  exit 0\nfi\ngrep -q x input.txt\n",
    "scripts/governance/tier0.d/check-nosuffix": "#!/usr/bin/env bash\nexit 1\n",
    "scripts/governance/tier0.d/check-other": "#!/usr/bin/env bash\nexit 1\n",
    "scripts/run-other.sh": "#!/usr/bin/env bash\nbash scripts/governance/tier0.d/check-other\n",
    "scripts/testing/test-check-honest.py": "# runs check-honest.sh on bad input\nassert rc != 0, 'check-honest must fail on known-bad input'\n",
    "scripts/install-hooks.sh": "#!/usr/bin/env bash\ngit config core.hooksPath .githooks\n",
    ".githooks/pre-commit": "#!/usr/bin/env bash\nset -e\nexit 1\n",
    ".github/workflows/ci.yml": """name: ci
on:
  pull_request:
jobs:
  masked:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/check-x.py || true
  annotated:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/check-y.py || true  # NON-GATING: cosmetic
  piped:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/check-z.py | tee out.log
  honest:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/check-z.py
""",
    "config/ci-checks.json": json.dumps({"description": "CI-hard checks", "checks": [], "ci_exempt": [], "test_exempt": []}),
}


def build(root: Path):
    for rel, text in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    (root / "true-gate.sh").write_text("exit 0\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


def by_unit(res, cls):
    return {f["unit"] for f in res["findings"] if f["class"] == cls}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sweep-gates-test-") as d:
        root = Path(d)
        build(root)
        res = sg.sweep(root, required={"honest"})
        # CANNOT_FAIL
        cf = by_unit(res, "CANNOT_FAIL")
        assert "tier0.d/check-always-pass.sh" in cf, cf
        assert "tier0:gate_prints_only" in cf, cf
        sev = {(f["unit"], f["class"]): f["severity"] for f in res["findings"]}
        assert sev[("tier0.d/check-always-pass.sh", "CANNOT_FAIL")] == "high", sev
        assert sev[("tier0.d/check-skips-tool.sh", "NO_BAD_INPUT_TEST")] == "medium", sev
        assert sev[("tier0.d/check-other", "UNCOVERED")] == "medium", "referenced elsewhere but not run by tier0"
        assert sev[("tier0.d/check-nosuffix", "UNCOVERED")] == "high", "referenced by nothing"
        assert "tier0.d/check-honest.sh" not in cf and "tier0:gate_honest" not in cf, f"honest gate flagged CANNOT_FAIL: {cf}"
        # NO_BAD_INPUT_TEST: tested honest gate clean, untested gate flagged
        nb = by_unit(res, "NO_BAD_INPUT_TEST")
        assert "tier0.d/check-skips-tool.sh" in nb, nb
        assert "tier0.d/check-honest.sh" not in nb, f"gate with a failing-input test flagged: {nb}"
        # FAIL_OPEN: tool missing, empty list from `|| true` git, honest gate clean
        fo = by_unit(res, "FAIL_OPEN")
        assert "tier0.d/check-skips-tool.sh" in fo, fo
        assert "tier0:gate_empty_ok" in fo, fo
        assert "tier0.d/check-honest.sh" not in fo and "tier0:gate_honest" not in fo, f"honest gate flagged FAIL_OPEN: {fo}"
        # MASKED_IN_CI: unannotated and pipe masks flagged high/medium, annotated low, honest job clean
        mk = {f["unit"]: f for f in res["findings"] if f["class"] == "MASKED_IN_CI"}
        assert mk["workflow:ci.yml#masked"]["severity"] == "high", mk
        assert mk["workflow:ci.yml#annotated"]["severity"] == "low", mk
        assert mk["workflow:ci.yml#piped"]["severity"] == "medium", mk
        assert "workflow:ci.yml#honest" not in mk, "honest workflow job flagged as masked"
        # NOT_REQUIRED: only the required job is exempt
        nr = by_unit(res, "NOT_REQUIRED")
        assert "workflow:ci.yml#masked" in nr and "workflow:ci.yml#honest" not in nr, nr
        claimed = [f for f in res["findings"] if f["class"] == "NOT_REQUIRED" and f["unit"] == "workflow:ci.yml#masked"]
        assert claimed and "claim:" in claimed[0]["evidence"]
        # UNCOVERED: file tier0 never globs, and a gate function nobody calls
        uc = by_unit(res, "UNCOVERED")
        assert "tier0.d/check-nosuffix" in uc, uc
        assert "tier0:gate_never_called" in uc, uc
        assert "tier0.d/check-honest.sh" not in uc and "tier0:gate_honest" not in uc, uc
        # a required check with no job is UNCOVERED
        res2 = sg.sweep(root, required={"honest", "ghost"})
        assert "required:ghost" in by_unit(res2, "UNCOVERED")
        # unknown stays unknown: no required list means NOT_REQUIRED is unknown, never silently clean
        res3 = sg.sweep(root, required=None)
        assert not by_unit(res3, "NOT_REQUIRED") and any("required status checks" in u["what"] for u in res3["unknown"])
        # report-only exit status, and --fail-on makes it non-zero
        assert sg.main(["--repo", str(root), "--required-checks", "honest"]) == 0
        assert sg.main(["--repo", str(root), "--required-checks", "honest", "--fail-on", "CANNOT_FAIL"]) == 1
        # honest-only tree: mutate the fixtures into good gates and nothing is flagged for those units
        (root / "scripts/governance/tier0.d/check-always-pass.sh").write_text("#!/usr/bin/env bash\nset -e\nexit 1\n")
        res4 = sg.sweep(root, required={"honest"})
        assert "tier0.d/check-always-pass.sh" not in by_unit(res4, "CANNOT_FAIL"), "fixed gate still flagged"
        # exercised probes: a gate that exits 0 on bad input becomes a CANNOT_FAIL finding
        sg_probe = {"id": "p", "unit": "fixture:gate", "script": "g.sh", "seed": "bad", "setup": lambda w: None,
                    "cmd": ["bash", "g.sh"]}
        saved = sg.PROBES
        try:
            (root / "g.sh").write_text("exit 0\n")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e.invalid", "-c", "commit.gpgsign=false",
                            "commit", "-q", "--no-verify", "-m", "x"], cwd=root, check=True)
            sg.PROBES = [sg_probe]
            res5 = sg.sweep(root, required={"honest"}, do_exercise=True)
            assert "fixture:gate" in by_unit(res5, "CANNOT_FAIL") and res5["exercised"][0]["outcome"] == "PASSED_ON_BAD_INPUT"
            (root / "g.sh").write_text("exit 1\n")
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e.invalid", "-c", "commit.gpgsign=false",
                            "commit", "-qam", "y", "--no-verify"], cwd=root, check=True)
            res6 = sg.sweep(root, required={"honest"}, do_exercise=True)
            assert "fixture:gate" not in by_unit(res6, "CANNOT_FAIL") and res6["exercised"][0]["outcome"] == "FAILED_AS_EXPECTED"
        finally:
            sg.PROBES = saved
    print("test-sweep-gates: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
