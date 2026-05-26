#!/usr/bin/env python3
"""
test-phase2-drop-zones.py — Validation for Phase 2 of P.A.E.A.
"""

import asyncio
import json
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import time

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DAEMON_PATH = REPO_ROOT / "scripts" / "ai" / "aq-drop-daemon"
LOCK_PATH = REPO_ROOT / ".agent" / "collaboration" / "PENDING.json"

class TestPhase2(unittest.TestCase):
    def setUp(self):
        # Create a temporary research_inbox for testing
        self.test_inbox = REPO_ROOT / "research_inbox"
        self.test_inbox.mkdir(exist_ok=True)
        
        # Backup existing PENDING.json
        self.lock_backup = None
        if LOCK_PATH.exists():
            self.lock_backup = LOCK_PATH.read_text()
            LOCK_PATH.unlink()

    def tearDown(self):
        # Cleanup test inbox
        for f in self.test_inbox.glob("*"):
            f.unlink()
        self.test_inbox.rmdir()
        
        # Restore PENDING.json
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
        if self.lock_backup:
            LOCK_PATH.write_text(self.lock_backup)

    def test_drop_zone_trigger(self):
        # Start daemon with short interval
        daemon_proc = subprocess.Popen(
            [str(DAEMON_PATH), "--interval", "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        try:
            # Wait for daemon to initialize
            time.sleep(2)
            
            # Create a file in the inbox
            test_file = self.test_inbox / "new_research.txt"
            test_file.write_text("New research topic")
            
            # Wait for daemon to scan and trigger
            time.sleep(3)
            
            # Check if PENDING.json lock was created
            self.assertTrue(LOCK_PATH.exists(), "PENDING.json should be created by the daemon")
            
            lock_data = json.loads(LOCK_PATH.read_text())
            self.assertEqual(lock_data["active_agent"], "Architect")
            self.assertIn("new_research.txt", str(lock_data["locks"]))
            
        finally:
            daemon_proc.terminate()
            daemon_proc.wait()

if __name__ == "__main__":
    unittest.main()
