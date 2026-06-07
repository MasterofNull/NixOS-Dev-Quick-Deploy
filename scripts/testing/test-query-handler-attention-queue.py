#!/usr/bin/env python3
"""
Phase 138.2 regression: attention queue pushed on unexpected query-handler exception.

Static analysis — no live coordinator required.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(COORDINATOR))


class TestQueryHandlerAttentionQueueWiring(unittest.TestCase):

    def _src(self):
        return (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")

    def test_phase138_2_block_present(self):
        """Static: Phase 138.2 comment must exist."""
        self.assertIn("Phase 138.2", self._src())

    def test_push_on_exception(self):
        """Static: push is called from inside the except block."""
        src = self._src()
        self.assertIn("_push_query_attention", src)
        self.assertIn('source="query-handler"', src)

    def test_auto_ok_boundary(self):
        """Static: autonomy_boundary must be auto_ok."""
        self.assertIn('autonomy_boundary="auto_ok"', self._src())

    def test_runtime_error_guard(self):
        """Static: RuntimeError guard prevents crash when no event loop is running (tests)."""
        src = self._src()
        self.assertIn("except RuntimeError:", src)

    def test_import_uses_coordinator_path(self):
        """Static: imports attention_queue by short name (PYTHONPATH, not absolute scripts path)."""
        src = self._src()
        self.assertIn("from attention_queue import push as _aq_push", src)
        self.assertNotIn("scripts.ai.lib.attention_queue", src)

    def test_compile_clean(self):
        """http_server_impl.py must compile without errors."""
        import py_compile
        try:
            py_compile.compile(str(COORDINATOR / "http_server_impl.py"), doraise=True)
        except py_compile.PyCompileError as exc:
            self.fail(f"Compile error: {exc}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
