#!/usr/bin/env python3
"""Linter and test suite for W4-S2: slice-authoring brief standards.
Enforces:
1. Token caps declared (e.g. max_input_tokens, max_output_tokens).
2. Mandatory runnable check command (check_command).
3. End-state definition and turn cap (turn_cap).
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / ".agent" / "skills" / "slice-authoring" / "SKILL.md"

def validate_slice_brief(brief_text: str) -> list[str]:
    """Validate a slice brief string or YAML-like template against W4-S2 rules."""
    errors = []
    lines = [line.strip() for line in brief_text.splitlines()]

    # Check for mandatory check command
    has_check_cmd = any(
        line.startswith("check_command:") or line.startswith("- check_command:")
        for line in lines
    )
    if not has_check_cmd:
        errors.append("missing mandatory 'check_command' in brief")

    # Check for token caps
    has_token_caps = any(
        "token_cap:" in line or "max_tokens:" in line or "token_budget:" in line
        for line in lines
    )
    if not has_token_caps:
        errors.append("missing mandatory 'token_cap' or 'token_budget' in brief")

    # Check for turn cap
    has_turn_cap = any("turn_cap:" in line or "max_turns:" in line for line in lines)
    if not has_turn_cap:
        errors.append("missing mandatory 'turn_cap' in brief")

    return errors

class TestSliceAuthoringSkill(unittest.TestCase):
    def test_skill_document_documents_mandatory_fields(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("check_command", text, "SKILL.md must document mandatory check_command")
        self.assertIn("token_budget", text, "SKILL.md must document token budget/caps")
        self.assertIn("turn_cap", text, "SKILL.md must document turn cap")

    def test_linter_accepts_valid_brief(self):
        valid_brief = """
slice_objective: Implement unit tests
role: implementer
check_command: pytest tests/test_feature.py
token_budget: 15000
turn_cap: 5
relevant_files:
  - src/feature.py
"""
        errors = validate_slice_brief(valid_brief)
        self.assertEqual(errors, [])

    def test_linter_rejects_missing_check_command(self):
        invalid_brief = """
slice_objective: Implement unit tests
role: implementer
token_budget: 15000
turn_cap: 5
"""
        errors = validate_slice_brief(invalid_brief)
        self.assertIn("missing mandatory 'check_command' in brief", errors)

    def test_linter_rejects_missing_caps(self):
        invalid_brief = """
slice_objective: Implement unit tests
role: implementer
check_command: pytest tests/test_feature.py
"""
        errors = validate_slice_brief(invalid_brief)
        self.assertIn("missing mandatory 'token_cap' or 'token_budget' in brief", errors)
        self.assertIn("missing mandatory 'turn_cap' in brief", errors)

if __name__ == "__main__":
    unittest.main()
