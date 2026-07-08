#!/usr/bin/env python3
"""harness_runner.py — bridge from the aq-qa launcher to the Python QA harness (harness_qa package).

aq-qa (scripts/ai/aq-qa) execs this file as ${REPO_ROOT}/scripts/ai/lib/harness_runner.py. Its
absence is why aq-qa silently fell back to the bash smoke-runner (_aq-qa-bash) as its DEFAULT path —
making a fallback the main workflow. This restores the intended primary: the richer, faster Python
harness (state-aware contract checks, more phases, structured reporters). _aq-qa-bash stays as the
genuine fallback for environments without python3 or the harness package.

Thin by design — all logic lives in harness_qa.main.main(); this only puts the package on sys.path
and forwards argv (aq-qa passes e.g. `0` or `0 --machine`)."""
from __future__ import annotations

import sys
from pathlib import Path

# harness_qa lives under scripts/testing/. This file is scripts/ai/lib/harness_runner.py, so the repo
# root is three parents up; the package parent is <repo>/scripts/testing.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HARNESS_PARENT = _REPO_ROOT / "scripts" / "testing"
if str(_HARNESS_PARENT) not in sys.path:
    sys.path.insert(0, str(_HARNESS_PARENT))

from harness_qa.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
