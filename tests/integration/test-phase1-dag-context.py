#!/usr/bin/env python3
"""
test-phase1-dag-context.py — Validation for Phase 1 of P.A.E.A.
"""

import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import sys
# Add scripts/ai/lib to path for context_merger
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(REPO_ROOT / "scripts" / "ai" / "lib"))
sys.path.append(str(REPO_ROOT / "ai-stack" / "agent-memory"))

from dag_manager import DAGSessionManager, AgentHandoff
from context_merger import get_hierarchical_context

class TestPhase1(unittest.TestCase):
    def setUp(self):
        self.test_dir = TemporaryDirectory()
        self.session_dir = Path(self.test_dir.name) / "sessions"
        self.dag_manager = DAGSessionManager(self.session_dir)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_dag_manager_basic(self):
        session_id = "test-session-1"
        root = self.dag_manager.create_entry(session_id, "message", role="user", content="Hello")
        child = self.dag_manager.create_entry(session_id, "message", parent_id=root.id, role="assistant", content="Hi there")
        
        entries = self.dag_manager.load_session(session_id)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].id, root.id)
        self.assertEqual(entries[1].parent_id, root.id)

    def test_dag_branching(self):
        session_id = "main"
        root = self.dag_manager.create_entry(session_id, "message", role="user", content="Start")
        turn1 = self.dag_manager.create_entry(session_id, "message", parent_id=root.id, role="assistant", content="Turn 1")
        turn2 = self.dag_manager.create_entry(session_id, "message", parent_id=turn1.id, role="assistant", content="Turn 2")
        
        # Branch from turn1
        new_session_id = self.dag_manager.branch_session(session_id, turn1.id, "branch-1")
        branch_entries = self.dag_manager.load_session(new_session_id)
        
        self.assertEqual(len(branch_entries), 2)
        self.assertEqual(branch_entries[0].content, "Start")
        self.assertEqual(branch_entries[1].content, "Turn 1")
        self.assertNotIn("Turn 2", [e.content for e in branch_entries])

    def test_handoff_validation(self):
        # Valid handoff
        handoff = AgentHandoff(
            source="Architect",
            target="Coder",
            handoff_count=1,
            reason="Planning done",
            payload={"task": "Fix bug"}
        )
        self.assertEqual(handoff.source, "Architect")
        
        # Invalid handoff (too many handoffs)
        with self.assertRaises(Exception):
            AgentHandoff(
                source="A", target="B", handoff_count=11, reason="Too many"
            )

    def test_hierarchical_context(self):
        # Setup fake repo structure
        repo = Path(self.test_dir.name) / "repo"
        repo.mkdir()
        (repo / "flake.nix").touch()
        (repo / "AGENTS.md").write_text("Root rules")
        
        sub = repo / "src" / "api"
        sub.mkdir(parents=True)
        (sub / "CLAUDE.md").write_text("API rules")
        
        context = get_hierarchical_context(sub)
        self.assertIn("Root rules", context)
        self.assertIn("API rules", context)
        self.assertTrue(context.find("Root rules") < context.find("API rules"), "Root rules should come before API rules")

if __name__ == "__main__":
    unittest.main()
