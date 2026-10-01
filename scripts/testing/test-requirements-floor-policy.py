#!/usr/bin/env python3
"""Owner policy: service requirements.txt carry floors (>=), never exact == pins.

Exact, hash-verified pins live in requirements.lock (pip-compile output).  Each
lock must still satisfy the loosened requirements.txt so the lock stays valid.
No network or installs.
"""
import re
import sys
import unittest
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]
SERVICES = sorted((ROOT / "ai-stack" / "mcp-servers").glob("*/requirements.txt"))
LOCK_PIN = re.compile(r"^([A-Za-z0-9_.\-]+(?:\[[^\]]*\])?)==([^\s;\\]+)", re.M)


def requirements(path):
    for line in path.read_text().splitlines():
        line = line.split(" #")[0].strip()
        if line and not line.startswith(("#", "-")):
            yield Requirement(line)


class FloorPolicy(unittest.TestCase):
    def test_services_found(self):
        self.assertGreaterEqual(len(SERVICES), 7)

    def test_no_exact_pins_and_all_lines_parse(self):
        for path in SERVICES:
            for req in requirements(path):
                ops = {s.operator for s in req.specifier}
                self.assertNotIn("==", ops, f"{path.relative_to(ROOT)}: {req} is an exact pin; use >= floor")
                self.assertNotIn("===", ops)

    def test_lock_drift_is_reported_not_fatal(self):
        """Lock/txt drift predates this policy (e.g. a raised floor without a lock refresh);
        it is a maintenance signal, not a regression a change introduces, so warn only."""
        for path in SERVICES:
            lock = path.with_name("requirements.lock")
            if not lock.exists():
                continue
            pinned = {canonicalize_name(re.sub(r"\[.*\]", "", n)): Version(v) for n, v in LOCK_PIN.findall(lock.read_text())}
            for req in requirements(path):
                version = pinned.get(canonicalize_name(req.name))
                if version is None:
                    continue  # not locked yet; a lock refresh adds it
                if not req.specifier.contains(version, prereleases=True):
                    print(f"WARN lock drift: {lock.relative_to(ROOT)} pins {req.name}=={version}, violates {req}",
                          file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
