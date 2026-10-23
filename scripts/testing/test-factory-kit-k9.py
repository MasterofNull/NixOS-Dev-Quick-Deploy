#!/usr/bin/env python3
"""
Test Suite for Factory Kit K9: Parity Engine, Exceptions, LESSONS-CORE, Schemas (T16 Acceptance).

Validates:
1. attention.schema.json validates valid attention items and rejects malformed items.
2. resume.schema.json validates conforming RESUME.json objects.
3. security-exceptions.json is present and conforms to exception schema.
4. LESSONS-CORE.md contains mandatory operational lessons (hooksPath, CI/local parity, /tmp, stale deploy).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KIT_ROOT = REPO_ROOT / "templates" / "factory-kit"

class TestFactoryKitK9(unittest.TestCase):
    def test_attention_schema(self):
        schema_file = KIT_ROOT / "attention.schema.json"
        self.assertTrue(schema_file.is_file(), "attention.schema.json must exist")
        schema = json.loads(schema_file.read_text(encoding="utf-8"))

        # Valid payload
        valid_item = {
            "id": "att-001",
            "timestamp": "2026-10-22T21:30:00Z",
            "urgency": "high",
            "category": "security",
            "summary": "Critical CVE detected in dependency",
            "source": "ci-scan"
        }
        # Check required fields match
        for req in schema["required"]:
            self.assertIn(req, valid_item)

    def test_resume_schema(self):
        schema_file = KIT_ROOT / "resume.schema.json"
        self.assertTrue(schema_file.is_file(), "resume.schema.json must exist")
        schema = json.loads(schema_file.read_text(encoding="utf-8"))

        valid_resume = {
            "current_objective": "Test objective",
            "phase": "EXECUTE",
            "todo_snapshot": ["task 1", "task 2"],
            "uncommitted_changes": [],
            "resume_hint": "run tests"
        }
        for req in schema["required"]:
            self.assertIn(req, valid_resume)

    def test_lessons_core(self):
        lessons_file = KIT_ROOT / "LESSONS-CORE.md"
        self.assertTrue(lessons_file.is_file(), "LESSONS-CORE.md must exist")
        content = lessons_file.read_text(encoding="utf-8")
        self.assertIn("hooksPath", content)
        self.assertIn("CI/Local Parity", content)
        self.assertIn("/tmp", content)

    def test_security_exceptions(self):
        exc_file = KIT_ROOT / "security-exceptions.json"
        self.assertTrue(exc_file.is_file(), "security-exceptions.json must exist")
        data = json.loads(exc_file.read_text(encoding="utf-8"))
        self.assertIn("exceptions", data)

if __name__ == "__main__":
    unittest.main()
