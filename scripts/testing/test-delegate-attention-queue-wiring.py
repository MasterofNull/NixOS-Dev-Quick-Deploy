#!/usr/bin/env python3
"""
Phase 138.1 regression: attention queue pushed on remote delegate HTTP 5xx.

Static analysis checks — no live coordinator required.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(COORDINATOR))


class TestDelegateAttentionQueueWiring(unittest.TestCase):

    def _src(self):
        return (COORDINATOR / "extensions" / "ai_coordinator_handlers.py").read_text(encoding="utf-8")

    def test_phase138_block_present(self):
        """Static: Phase 138.1 comment must exist in handlers."""
        self.assertIn("Phase 138.1", self._src())

    def test_push_on_5xx_condition(self):
        """Static: attention push gates on status_code >= 500 and _is_remote_profile."""
        src = self._src()
        self.assertIn("response.status_code >= 500", src)
        self.assertIn("_is_remote_profile(effective_profile)", src)

    def test_auto_ok_boundary(self):
        """Static: autonomy_boundary must be auto_ok (goes to archive, never blocks queue)."""
        self.assertIn('autonomy_boundary="auto_ok"', self._src())

    def test_source_label(self):
        """Static: source must be 'delegate-handler'."""
        self.assertIn('source="delegate-handler"', self._src())

    def test_create_task_wraps_thread(self):
        """Static: push is run in asyncio.to_thread to avoid blocking event loop."""
        src = self._src()
        self.assertIn("asyncio.to_thread(_push_delegate_attention)", src)

    def test_compile_clean(self):
        """ai_coordinator_handlers.py must compile without errors."""
        import py_compile
        try:
            py_compile.compile(
                str(COORDINATOR / "extensions" / "ai_coordinator_handlers.py"),
                doraise=True,
            )
        except py_compile.PyCompileError as exc:
            self.fail(f"Compile error: {exc}")

    def test_parity_plan_updated(self):
        """Parity plan must reflect Phase 138.1 delegate boundary."""
        plan = (
            REPO_ROOT / ".agents" / "plans" / "multi-agent-edge-harness" / "PARITY-INTEGRATION-PLAN.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Phase 138.1", plan)
        self.assertIn("delegate boundary", plan)


if __name__ == "__main__":
    unittest.main(verbosity=2)
