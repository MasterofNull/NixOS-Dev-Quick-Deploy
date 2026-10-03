#!/usr/bin/env python3
"""Regression test suite for Antigravity autonomous delegation in sub-agent & collaborative workflows.

Verifies:
1. aq-antigravity-inbox accepts collaborative & workflow actors (aq-collab-round, workflow-executor, subagent, delegate-fanout).
2. WAKE_PROMPT is generalized to support implementation, review, and plans without artificial role blocks.
3. delegate-to-antigravity accepts 'subagent' and 'coordinator' roles.
4. aq-collab-round _drop_antigravity writes explicit Output: and Role: metadata.
5. delegate-fanout maps gemini and antigravity to delegate-to-antigravity.
6. Interactive and CLI consoles (aq-subagent-interactive, aq-agent-window, aq-coordinator-repl) map antigravity to delegate-to-antigravity.
7. workflow_executor forwards target lane to spawn payload.
8. agents_task_handlers supports delegated agent spawning for antigravity.
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestSubagentWorkflowsAntigravity(unittest.TestCase):

    def test_inbox_actors_and_wake_prompt(self):
        inbox_script = REPO_ROOT / "scripts" / "ai" / "aq-antigravity-inbox"
        loader = importlib.machinery.SourceFileLoader("aq_inbox", str(inbox_script))
        spec = importlib.util.spec_from_loader("aq_inbox", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)

        # WAKE_PROMPT assertions
        self.assertIn("claim <basename>", mod.WAKE_PROMPT)
        self.assertIn("complete .claimed-<task-id>", mod.WAKE_PROMPT)
        self.assertIn("Perform only non-editing advisory", mod.WAKE_PROMPT)
        self.assertIn("Do not modify files in any IDE workspace or shared checkout", mod.WAKE_PROMPT)
        self.assertIn("cannot verify a task-specific workspace binding", mod.WAKE_PROMPT)

        # Actor choices
        parser = mod.build_parser()
        wake_parser = parser._subparsers._actions[1].choices["wake"]
        actor_action = next(a for a in wake_parser._actions if a.dest == "actor")
        for expected in ("aq-collab-round", "workflow-executor", "subagent", "delegate-fanout", "auto-delegate", "owner-manual"):
            self.assertIn(expected, actor_action.choices)

    def test_delegate_to_antigravity_roles(self):
        delegate_script = REPO_ROOT / "scripts" / "ai" / "delegate-to-antigravity"
        loader = importlib.machinery.SourceFileLoader("del_ag", str(delegate_script))
        spec = importlib.util.spec_from_loader("del_ag", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)

        self.assertIn("subagent", mod._VALID_ROLES)
        self.assertIn("coordinator", mod._VALID_ROLES)
        self.assertIn("implementer", mod._VALID_ROLES)
        self.assertIn("reviewer", mod._VALID_ROLES)

    def test_collab_round_drop_antigravity_metadata(self):
        collab_script = REPO_ROOT / "scripts" / "ai" / "aq-collab-round"
        loader = importlib.machinery.SourceFileLoader("aq_collab", str(collab_script))
        spec = importlib.util.spec_from_loader("aq_collab", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)

        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp_repo = Path(td)
            prompt_file = tmp_repo / "prompt.txt"
            prompt_file.write_text("Review PRD for correctness.")
            inbox_dir = tmp_repo / ".agent" / "collaboration" / "antigravity-inbox"
            with mock.patch.object(mod, "REPO", tmp_repo), \
                 mock.patch.object(mod, "ANTIGRAVITY_INBOX", inbox_dir):
                mod._drop_antigravity("test-round", prompt_file)
                dropped = inbox_dir / "test-round.md"
                self.assertTrue(dropped.is_file())
                content = dropped.read_text()
                self.assertIn("Output: .agents/plans/test-round/antigravity.md", content)
                self.assertIn("Role: review", content)

    def test_delegate_fanout_routing(self):
        fanout_script = REPO_ROOT / "scripts" / "ai" / "delegate-fanout"
        content = fanout_script.read_text(encoding="utf-8")
        self.assertIn('if [[ "$agent" == "gemini" || "$agent" == "antigravity" ]]; then', content)
        self.assertIn('delegate_script="$SCRIPT_DIR/delegate-to-antigravity"', content)

    def test_interactive_consoles_map_antigravity(self):
        # 1. aq-subagent-interactive
        subagent_script = REPO_ROOT / "scripts" / "ai" / "aq-subagent-interactive"
        content_sub = subagent_script.read_text(encoding="utf-8")
        self.assertIn('"antigravity": REPO_ROOT / "scripts" / "ai" / "delegate-to-antigravity"', content_sub)

        # 2. aq-agent-window
        window_script = REPO_ROOT / "scripts" / "ai" / "aq-agent-window"
        content_win = window_script.read_text(encoding="utf-8")
        self.assertIn('"antigravity": REPO_ROOT / "scripts" / "ai" / "delegate-to-antigravity"', content_win)

        # 3. aq-coordinator-repl
        repl_script = REPO_ROOT / "scripts" / "ai" / "aq-coordinator-repl"
        content_repl = repl_script.read_text(encoding="utf-8")
        self.assertIn('"antigravity": REPO_ROOT / "scripts" / "ai" / "delegate-to-antigravity"', content_repl)

    def test_workflow_executor_lane_forwarding(self):
        we_script = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "workflow_executor.py"
        content = we_script.read_text(encoding="utf-8")
        self.assertIn('target_lane = str(phase.get("lane") or phase.get("agent") or context.get("lane", "local")).lower().strip()', content)
        self.assertIn('"lane": target_lane,', content)
        self.assertIn('"event_type": "phase_delegation",', content)

    def test_agents_task_handlers_delegation(self):
        ath_script = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "workflow" / "agents_task_handlers.py"
        content = ath_script.read_text(encoding="utf-8")
        self.assertIn("async def _spawn_delegated_agent_instance(", content)
        self.assertIn('"antigravity": repo_root / "scripts" / "ai" / "delegate-to-antigravity"', content)
        self.assertIn('if lane in ("antigravity", "gemini", "codex", "claude"):', content)


if __name__ == "__main__":
    unittest.main()
