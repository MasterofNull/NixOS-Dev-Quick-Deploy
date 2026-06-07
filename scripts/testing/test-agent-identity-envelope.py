#!/usr/bin/env python3
"""
Phase 140 regression: agent identity envelope (P0 parity) — caller source/role/boundary
captured from X-Agent-Source/Role/Boundary headers and surfaced in OTel trace attributes.

Static analysis — no live coordinator required.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(COORDINATOR))


class TestAgentIdentityEnvelope(unittest.TestCase):

    def _http_src(self):
        return (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")

    def _trace_src(self):
        return (COORDINATOR / "trace_collector.py").read_text(encoding="utf-8")

    def test_phase140_block_in_http_server(self):
        """Static: Phase 140 comment must exist in http_server_impl.py."""
        self.assertIn("Phase 140", self._http_src())

    def test_set_caller_invoked_with_headers(self):
        """Static: set_caller must be called with X-Agent-Source/Role/Boundary."""
        src = self._http_src()
        self.assertIn("set_caller(", src)
        self.assertIn("X-Agent-Source", src)
        self.assertIn("X-Agent-Role", src)
        self.assertIn("X-Agent-Boundary", src)

    def test_trace_collector_has_set_caller(self):
        """Static: TraceCollector.set_caller method must exist."""
        self.assertIn("def set_caller(", self._trace_src())

    def test_caller_fields_in_otel_span(self):
        """Static: gen_ai.maeah.caller.* keys must appear in otel_span."""
        src = self._trace_src()
        self.assertIn("gen_ai.maeah.caller.source", src)
        self.assertIn("gen_ai.maeah.caller.role", src)
        self.assertIn("gen_ai.maeah.caller.autonomy_boundary", src)

    def test_caller_fields_initialised_in_init(self):
        """Static: caller_source/role/boundary must be initialised in __init__."""
        src = self._trace_src()
        self.assertIn("self.caller_source", src)
        self.assertIn("self.caller_role", src)
        self.assertIn("self.caller_boundary", src)

    def test_set_caller_truncates_fields(self):
        """Unit: set_caller truncates source to 64, role/boundary to 32 chars."""
        import trace_collector  # noqa: PLC0415
        tc = trace_collector.TraceCollector()
        tc.set_caller(source="s" * 100, role="r" * 50, boundary="b" * 50)
        self.assertEqual(len(tc.caller_source), 64)
        self.assertEqual(len(tc.caller_role), 32)
        self.assertEqual(len(tc.caller_boundary), 32)

    def test_set_caller_empty_defaults(self):
        """Unit: set_caller with no args leaves fields empty (non-breaking)."""
        import trace_collector  # noqa: PLC0415
        tc = trace_collector.TraceCollector()
        tc.set_caller()
        self.assertEqual(tc.caller_source, "")
        self.assertEqual(tc.caller_role, "")
        self.assertEqual(tc.caller_boundary, "")

    def test_otel_span_includes_caller_keys(self):
        """Unit: otel_span() dict includes caller identity keys."""
        import trace_collector  # noqa: PLC0415
        tc = trace_collector.TraceCollector(query="test")
        tc.set_caller(source="aq-chat", role="orchestrator", boundary="auto_ok")
        span = tc.otel_span(100)
        self.assertEqual(span.get("gen_ai.maeah.caller.source"), "aq-chat")
        self.assertEqual(span.get("gen_ai.maeah.caller.role"), "orchestrator")
        self.assertEqual(span.get("gen_ai.maeah.caller.autonomy_boundary"), "auto_ok")

    def test_compile_clean_trace_collector(self):
        """trace_collector.py must compile without errors."""
        import py_compile
        try:
            py_compile.compile(str(COORDINATOR / "trace_collector.py"), doraise=True)
        except py_compile.PyCompileError as exc:
            self.fail(f"Compile error: {exc}")

    def test_compile_clean_http_server_impl(self):
        """http_server_impl.py must compile without errors."""
        import py_compile
        try:
            py_compile.compile(str(COORDINATOR / "http_server_impl.py"), doraise=True)
        except py_compile.PyCompileError as exc:
            self.fail(f"Compile error: {exc}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
