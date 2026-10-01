#!/usr/bin/env python3
"""Owner policy: service requirements.txt carry floors (>=), never exact == pins.

Since the 2026-10-01 Nix-only decision, deployed dependencies come from the Nix
closure; the remaining requirements.txt files (aidb, hybrid-coordinator,
nixos-docs) only feed CI unit-test environments.  Dockerfiles and
requirements.lock were archived under .agent/archive/20261001-docker-pip-layer.
No network or installs.
"""
import unittest
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]
SERVICES = sorted((ROOT / "ai-stack" / "mcp-servers").glob("*/requirements.txt"))


def requirements(path):
    for line in path.read_text().splitlines():
        line = line.split(" #")[0].strip()
        if line and not line.startswith(("#", "-")):
            yield Requirement(line)


class FloorPolicy(unittest.TestCase):
    def test_services_found(self):
        self.assertGreaterEqual(len(SERVICES), 3)

    def test_no_exact_pins_and_all_lines_parse(self):
        for path in SERVICES:
            for req in requirements(path):
                ops = {s.operator for s in req.specifier}
                self.assertNotIn("==", ops, f"{path.relative_to(ROOT)}: {req} is an exact pin; use >= floor")
                self.assertNotIn("===", ops)


if __name__ == "__main__":
    unittest.main()
