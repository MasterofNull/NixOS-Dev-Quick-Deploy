#!/usr/bin/env python3
"""
test-phase3-arbitrage.py — Validation for Phase 3 of P.A.E.A.
"""

import unittest
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(REPO_ROOT / "scripts" / "ai" / "lib"))
sys.path.append(str(REPO_ROOT / "ai-stack" / "agent-memory"))

from model_tiering import estimate_task_complexity
from dag_manager import DAGSessionManager

class TestPhase3(unittest.TestCase):
    def test_complexity_estimation(self):
        # L1 tasks
        self.assertEqual(estimate_task_complexity("list files in src"), "L1")
        self.assertEqual(estimate_task_complexity("search for pattern", ["grep"]), "L1")
        self.assertEqual(estimate_task_complexity("hello"), "L1")
        
        # L2 tasks
        self.assertEqual(estimate_task_complexity("plan a refactor for the entire module"), "L2")
        self.assertEqual(estimate_task_complexity("implement a new feature for multi-agent coordination"), "L2")

    def test_compaction(self):
        with TemporaryDirectory() as tmp_dir:
            dag_manager = DAGSessionManager(Path(tmp_dir) / "sessions")
            session_id = "compaction-test"
            
            # Create a long history
            h1 = dag_manager.create_entry(session_id, "message", role="user", content="Turn 1")
            h2 = dag_manager.create_entry(session_id, "message", parent_id=h1.id, role="assistant", content="Response 1")
            h3 = dag_manager.create_entry(session_id, "message", parent_id=h2.id, role="user", content="Turn 2")
            
            # Compact
            comp_entry = dag_manager.compact_session(
                session_id, h3.id, 
                summary="Initial turns summarized", 
                key_facts=["User said hello", "Assistant responded"]
            )
            
            # Check effective history - new turn linked to compaction
            h4 = dag_manager.create_entry(session_id, "message", parent_id=comp_entry.id, role="user", content="Turn 3")
            effective = dag_manager.get_effective_history(session_id, h4.id)
            
            self.assertEqual(len(effective), 2)
            self.assertEqual(effective[0]["role"], "system")
            self.assertIn("HISTORY COMPACTION", effective[0]["content"])
            self.assertEqual(effective[1]["content"], "Turn 3")

if __name__ == "__main__":
    unittest.main()
