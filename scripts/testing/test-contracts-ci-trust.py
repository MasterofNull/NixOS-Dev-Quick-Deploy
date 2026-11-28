#!/usr/bin/env python3
"""N2, N4 and N8 for the contracts-boundaries gate (control-plane consolidation S1).

Each case runs the fix and the unfixed behaviour side by side, so the test proves the control is what
makes the difference: a lying checker is invisible without the trusted corpus (N2), a weakened corpus
passes it unless the corpus is read from the trusted checkout (N4), and a privileged workflow that
builds the PR head is invisible to the old lint but not to check-workflow-trust.py (N8).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None, rel
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


trust = load("cwt", "scripts/governance/check-workflow-trust.py")
masks = load("cwm", "scripts/governance/check-workflow-masks.py")
RUNNER = ROOT / "scripts/governance/contracts-corpus.sh"

BAD_CHECKOUT = """name: bad
on:
  pull_request_target:
    types: [opened]
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@abc
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: cargo build
"""
BAD_FETCH_BUILD = """name: bad
on: pull_request_target
jobs:
  j:
    runs-on: ubuntu-latest
    steps:
      - run: git fetch origin refs/pull/1/head
      - run: |
          git worktree add ../cand FETCH_HEAD
          cd ../cand && cargo build
"""
BAD_SAME_STEP = """name: bad
on:
  pull_request_target:
jobs:
  j:
    steps:
      - run: git fetch origin refs/pull/1/head && ./scripts/check.sh
"""
OK_BASE_ONLY = """name: ok
on:
  pull_request_target:
jobs:
  j:
    steps:
      - uses: actions/checkout@abc
      - run: cargo build --release
      - run: git fetch origin refs/pull/1/head
      - run: |
          BIN=target/release/harness-contracts
          "$BIN" --root cand contracts
"""
NOT_PRIVILEGED = """name: fine
on:
  pull_request:
jobs:
  j:
    steps:
      - uses: actions/checkout@abc
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: cargo build
"""


def run_corpus(binary: Path, trusted: Path) -> int:
    return subprocess.run([str(RUNNER), str(binary), str(trusted)], capture_output=True, text=True).returncode


def real_binary() -> Path:
    env = os.environ.get("HARNESS_CONTRACTS_BIN")
    if env:
        return Path(env)
    out = ROOT / "target/release/harness-contracts"
    if not out.exists():
        subprocess.run(["cargo", "build", "--release", "-p", "harness-contracts"], cwd=ROOT, check=True)
    return out


def n8() -> None:
    for name, text in (("checkout-head", BAD_CHECKOUT), ("fetch-then-build", BAD_FETCH_BUILD), ("same-step", BAD_SAME_STEP)):
        assert trust.scan_text(text), f"N8: lint must fail '{name}'"
        assert masks.scan_text(text) == [], f"N8 control: the old mask lint is blind to '{name}' (no fix, no detection)"
    assert trust.scan_text(OK_BASE_ONLY) == [], "N8: base build, candidate as data, prebuilt checker only must pass"
    assert trust.scan_text(NOT_PRIVILEGED) == [], "N8: pull_request jobs may build the PR head"
    assert trust.main(["x", str(ROOT)]) == 0, "N8: every real workflow must pass"
    wf = (ROOT / ".github/workflows/contracts-boundaries.yml").read_text()
    code = trust.strip_comments(wf)
    assert "secrets." not in code and "GH_TOKEN" not in code, "privileged job must hold no secrets or token"
    assert "pull_request_target" in code and "permissions:\n  contents: read\n" in code
    assert code.index("cargo build") < code.index("refs/pull/"), "base checker must be built before the candidate exists"
    cand = (ROOT / ".github/workflows/contracts-candidate.yml").read_text()
    ccode = trust.strip_comments(cand)
    assert "pull_request_target" not in ccode and "secrets." not in ccode and "permissions:\n  contents: read\n" in ccode


def n2_n4() -> None:
    tmp = Path(tempfile.mkdtemp())
    stub = tmp / "lying-checker"
    stub.write_text("#!/usr/bin/env bash\necho 'PASS: lying checker'\nexit 0\n")
    stub.chmod(0o755)
    # Without the corpus a checker edited to return success is indistinguishable from a good one.
    assert subprocess.run([str(stub), "--root", ".", "contracts"], capture_output=True).returncode == 0
    # N2: the trusted corpus catches it.
    assert run_corpus(stub, ROOT) != 0, "N2: a checker that returns success on known-bad input must fail the corpus"
    # N4: a candidate rewrites the corpus so every case passes; reading it from the candidate hides the lie.
    weak = tmp / "weak"
    (weak / "tests/contracts-corpus").mkdir(parents=True)
    shutil.copytree(ROOT / "tests/contracts-corpus/cases", weak / "tests/contracts-corpus/cases")
    for case in (weak / "tests/contracts-corpus/cases").iterdir():
        case.rename(case.parent / ("ok-" + case.name.removeprefix("ok-")))
        (case.parent / ("ok-" + case.name.removeprefix("ok-")) / "expect").write_text("PASS")
    subprocess.run(["git", "init", "-q"], cwd=weak, check=True)
    for part in ("scripts", "ai-stack", "dashboard", "contracts", "config"):
        src = ROOT / part
        if src.exists():
            shutil.copytree(src, weak / part, dirs_exist_ok=True)
    subprocess.run(["git", "add", "-A"], cwd=weak, check=True, capture_output=True)
    assert run_corpus(stub, weak) == 0, "N4 control: reading the corpus from the candidate lets the lying checker pass"
    assert run_corpus(stub, ROOT) != 0, "N4: the corpus read from the trusted checkout still fails it"
    # The real checker passes the real corpus (the corpus is satisfiable).
    assert run_corpus(real_binary(), ROOT) == 0, "the packaged checker must pass the trusted corpus"
    shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    n8()
    n2_n4()
    print("test-contracts-ci-trust: PASS (N2, N4, N8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
