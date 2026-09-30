#!/usr/bin/env python3
"""Regression checks for truthful aq-memory persistence results."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_MEMORY = ROOT / "scripts/ai/aq-memory"


def run_memory(storage: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AQ_MEMORY), "--storage", str(storage), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class AqMemoryPersistenceTests(unittest.TestCase):
    def test_failed_text_add_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_memory(
                Path(directory),
                "add",
                "must not be reported as saved",
                "--project",
                "test",
            )

        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Added fact", result.stdout)

    def test_failed_json_store_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_memory(
                Path(directory),
                "--json",
                "store",
                "must not be reported as saved",
                "--project",
                "test",
            )

        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"status": "added"', result.stdout)

    def test_successful_add_reloads_in_a_new_process(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory) / "facts.json"
            added = run_memory(
                storage,
                "--json",
                "add",
                "persistent test fact",
                "--project",
                "test",
            )
            listed = run_memory(storage, "--json", "list")

        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        facts = json.loads(listed.stdout)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["content"], "persistent test fact")

    def test_failed_json_expire_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory) / "facts.json"
            added = run_memory(
                storage,
                "--json",
                "add",
                "fact that cannot expire",
                "--project",
                "test",
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            fact_id = json.loads(added.stdout)["fact_id"]
            storage.chmod(0o400)
            try:
                expired = run_memory(
                    storage,
                    "--json",
                    "expire",
                    fact_id,
                    "--until",
                    "2026-12-31T00:00:00Z",
                )
            finally:
                storage.chmod(0o600)

        self.assertNotEqual(expired.returncode, 0, expired.stderr)
        self.assertNotIn('"status": "expired"', expired.stdout)


if __name__ == "__main__":
    unittest.main()
