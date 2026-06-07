#!/usr/bin/env python3
"""
Phase 138.3 regression: attention queue pushed on unexpected MCP tool dispatch exception.

Static analysis — no live coordinator required.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(COORDINATOR))


class TestMcpToolAttentionQueueWiring(unittest.TestCase):

    def _src(self):
        return (COORDINATOR / "extensions" / "mcp_handlers.py").read_text(encoding="utf-8")

    def test_phase138_3_block_present(self):
        """Static: Phase 138.3 comment must exist."""
        self.assertIn("Phase 138.3", self._src())

    def test_push_on_exception(self):
        """Static: push fires from the except Exception block."""
        src = self._src()
        self.assertIn("_push_mcp_attention", src)
        self.assertIn('source="mcp-tool-handler"', src)

    def test_auto_ok_boundary(self):
        """Static: autonomy_boundary must be auto_ok."""
        self.assertIn('autonomy_boundary="auto_ok"', self._src())

    def test_runtime_error_guard(self):
        """Static: RuntimeError guard prevents crash in test/non-async contexts."""
        self.assertIn("except RuntimeError:", self._src())

    def test_raise_preserved(self):
        """Static: original exception is still re-raised after push."""
        src = self._src()
        # The raise must come after the attention push block, not before it
        phase_pos = src.find("Phase 138.3")
        raise_pos = src.rfind("\n        raise\n")
        self.assertGreater(raise_pos, phase_pos, "raise must come after attention push")

    def test_compile_clean(self):
        """mcp_handlers.py must compile without errors."""
        import py_compile
        try:
            py_compile.compile(
                str(COORDINATOR / "extensions" / "mcp_handlers.py"),
                doraise=True,
            )
        except py_compile.PyCompileError as exc:
            self.fail(f"Compile error: {exc}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
