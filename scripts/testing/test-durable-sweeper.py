#!/usr/bin/env python3
"""
Unit and regression tests for aq-durable-sweeper state persistence, schema conformity,
and Hype vs Facts vs Signal classification.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SWEEPER_CLI = REPO_ROOT / "scripts/ai/aq-durable-sweeper"
SCHEMA_FILE = REPO_ROOT / "config/schemas/durable-sweeper-state.schema.json"

class TestDurableSweeper(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "test-state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, args):
        cmd = [str(SWEEPER_CLI), "--state-file", str(self.state_file)] + args
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res

    def test_schema_file_exists_and_valid_json(self):
        self.assertTrue(SCHEMA_FILE.exists())
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["title"], "DurableSweeperState")

    def test_init_and_status(self):
        res = self.run_cli(["status"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["schema_version"], "2026-10-19")
        self.assertEqual(data["status"], "idle")
        self.assertEqual(data["metrics"]["items_ingested"], 0)

    def test_ingest_classification(self):
        # 1. Test Signal item
        res1 = self.run_cli([
            "ingest",
            "--title", "Durable Agent Execution Architecture",
            "--source", "https://github.com/disler/pi-durable-news-agent",
            "--content", "Implements durable agent execution loops with state checkpoints across reboots.",
            "--json"
        ])
        self.assertEqual(res1.returncode, 0)
        data1 = json.loads(res1.stdout)
        self.assertEqual(data1["status"], "processed")
        self.assertEqual(data1["classification"]["category"], "signal")

        # 2. Test Hype item
        res2 = self.run_cli([
            "ingest",
            "--title", "AGI Achieved Tomorrow!",
            "--source", "https://marketing-blog.example.com",
            "--content", "This revolutionary tool that replaces all humans will blow your mind with 100x faster than everything.",
            "--json"
        ])
        self.assertEqual(res2.returncode, 0)
        data2 = json.loads(res2.stdout)
        self.assertEqual(data2["status"], "processed")
        self.assertEqual(data2["classification"]["category"], "hype")

        # 3. Test Facts item
        res3 = self.run_cli([
            "ingest",
            "--title", "Nixpkgs package bump for glibc",
            "--source", "https://github.com/NixOS/nixpkgs",
            "--content", "Nixpkgs bump release v2.40 with security advisory and bugfix.",
            "--json"
        ])
        self.assertEqual(res3.returncode, 0)
        data3 = json.loads(res3.stdout)
        self.assertEqual(data3["status"], "processed")
        self.assertEqual(data3["classification"]["category"], "facts")

        # 4. Verify status persistence
        res_status = self.run_cli(["status"])
        status_data = json.loads(res_status.stdout)
        self.assertEqual(status_data["metrics"]["items_ingested"], 3)
        self.assertEqual(status_data["metrics"]["signal_count"], 1)
        self.assertEqual(status_data["metrics"]["hype_count"], 1)
        self.assertEqual(status_data["metrics"]["facts_count"], 1)

    def test_deduplication(self):
        args = [
            "ingest",
            "--title", "Same Item",
            "--source", "https://example.com",
            "--content", "Identical content string for testing deduplication.",
            "--json"
        ]
        res1 = self.run_cli(args)
        data1 = json.loads(res1.stdout)
        self.assertEqual(data1["status"], "processed")

        res2 = self.run_cli(args)
        data2 = json.loads(res2.stdout)
        self.assertEqual(data2["status"], "skipped")
        self.assertEqual(data2["reason"], "already_processed")

    def test_tick(self):
        res = self.run_cli(["tick"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Total sweeps: 1", res.stdout)

if __name__ == "__main__":
    unittest.main()
