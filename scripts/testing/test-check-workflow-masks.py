#!/usr/bin/env python3
"""Tests for scripts/governance/check-workflow-masks.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cwm", ROOT / "scripts/governance/check-workflow-masks.py")
cwm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cwm)


def main() -> int:
    assert cwm.scan_text("run: nix flake check || true\n") == [1], "bare || true must fail"
    assert cwm.scan_text("        continue-on-error: true\n") == [1], "bare continue-on-error must fail"
    assert cwm.scan_text("run: df -h || true  # NON-GATING: best effort\n") == []
    assert cwm.scan_text("# KNOWN-FAILING: x; tracked CI-MASK-A\nrun: a || true\n") == []
    assert cwm.scan_text("# NON-GATING: upload\ncontinue-on-error: true\n") == []
    assert cwm.scan_text("# NON-GATING:\nrun: a || true\n") == [2], "empty reason must fail"
    assert cwm.scan_text("# just a comment about || true\n") == []
    assert cwm.main(["x", str(ROOT)]) == 0, "real repo workflows must pass"
    print("test-check-workflow-masks: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
