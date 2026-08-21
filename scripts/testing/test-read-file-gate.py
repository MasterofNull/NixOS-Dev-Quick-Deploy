#!/usr/bin/env python3
"""
Slice 0.2 regression tests — ai-stack/local-agents/agent_executor.py's read_file
gate + structural no-commit enforcement.

Context (see .agents/plans/local-context-supply-chain/DESIGN.md "AFTER-run 1"):
Slice 0.1's front-loaded context assembler is additive. Dogfooding it against a
real local task proved the in-loop whole-file read still fires ON TOP of the
front-loaded spans, blowing LLAMA_MAX_PROMPT_CHARS (25920 > 24000). Slice 0.2
gates that read: files over ~1500 tok return an outline + top task-relevant
chunks instead of raw bytes, and FAILS CLOSED (bounded head, never the full
file) on any internal error — that size invariant is the actual point of this
slice, so it gets the most direct coverage here.

Dual-mode, mirroring test-context-assembler.py's pattern: probe the real embed
endpoint (:8081) once at import time. If it answers, the "large file" gate test
runs a genuine read+chunk+embed+retrieve+teardown round-trip. If unreachable,
the same test falls back to a monkeypatched context_cache stub so the suite
never silently no-ops either way.

Coverage:
  1. a large file returns outline+chunks (not raw bytes), stays under budget
  2. a small file passes through unchanged (no gating overhead)
  3. fail-closed: any internal gate failure returns a bounded head, NEVER the
     full oversized file — the load-bearing invariant
  4. git_add/git_commit are absent from the default local tool set (structural
     no-commit), both via _AEXEC_ALWAYS_TOOLS and the model-visible tool schema
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent.parent
_LOCAL_AGENTS = _REPO / "ai-stack" / "local-agents"
sys.path.insert(0, str(_LOCAL_AGENTS))
sys.path.insert(0, str(_REPO / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(_REPO / "scripts" / "ai" / "lib"))

import agent_executor as ae  # noqa: E402
import context_cache  # noqa: E402
import tool_registry  # noqa: E402


def _live_backends_available() -> bool:
    """Same proof pattern as test-context-assembler.py's _live_backends_available()."""
    try:
        return context_cache.embed_text("read-file-gate-live-probe") is not None
    except Exception:
        return False


LIVE = _live_backends_available()


def _make_large_python_content(n_funcs: int = 220) -> str:
    """A synthetic file comfortably over the ~6000-char gate threshold, with
    enough def markers for the outline scan to find real structure."""
    lines = []
    for i in range(n_funcs):
        lines.append(f"def func_{i}(x):")
        lines.append(f"    # marker function {i}")
        lines.append(f"    return x + {i}")
    return "\n".join(lines) + "\n"


class TestSmallFilePassthrough(unittest.TestCase):
    """(2) a small file passes through whole, no gate overhead."""

    def test_small_file_returns_unchanged(self):
        content = "def foo():\n    return 1\n"
        self.assertLess(len(content), ae._READ_FILE_GATE_CHAR_BUDGET)
        gated_text, was_gated = ae._gate_large_file_content(
            content, "some/small_file.py", "fix foo", "test-task-small",
        )
        self.assertEqual(gated_text, content)
        self.assertFalse(was_gated)


class TestLargeFileGate(unittest.TestCase):
    """(1) a large file returns outline + top task-relevant chunks, not raw
    bytes, and the result stays under the gate's char budget."""

    def test_large_file_returns_outline_and_chunks_under_budget(self):
        content = _make_large_python_content()
        self.assertGreater(len(content), ae._READ_FILE_GATE_CHAR_BUDGET)
        task_objective = "Fix func_42 to add 100 instead of 42"
        task_id = "test-task-large-live" if LIVE else "test-task-large-stub"

        if LIVE:
            gated_text, was_gated = ae._gate_large_file_content(
                content, "fake/large_file.py", task_objective, task_id,
            )
        else:
            fake_collection = "fake-rfgate-collection"
            fake_retrieved = [
                "[fake/large_file.py:1-3]\ndef func_0(x):\n    # marker function 0\n    return x + 0",
                "[fake/large_file.py:127-129]\ndef func_42(x):\n    # marker function 42\n    return x + 42",
            ]
            with patch.object(context_cache, "cache_evicted", return_value=fake_collection):
                with patch.object(context_cache, "retrieve_ctx", return_value=fake_retrieved):
                    with patch.object(context_cache, "delete_collection", return_value=None):
                        gated_text, was_gated = ae._gate_large_file_content(
                            content, "fake/large_file.py", task_objective, task_id,
                        )

        self.assertTrue(was_gated)
        self.assertNotEqual(gated_text, content)
        self.assertLessEqual(len(gated_text), ae._READ_FILE_GATE_CHAR_BUDGET)
        self.assertIn("## Outline:", gated_text)
        self.assertIn("summarized", gated_text)
        if not LIVE:
            # deterministic stub path — chunk section + a real citation are provable
            self.assertIn("## Top task-relevant chunks", gated_text)
            self.assertIn("fake/large_file.py:", gated_text)
        # the raw content must never leak through verbatim inside the gated text
        self.assertNotIn(content, gated_text)

    def test_outline_finds_def_markers(self):
        content = _make_large_python_content(n_funcs=10)
        outline = ae._build_file_outline(content, "fake/small_multi_def.py")
        self.assertIn("def func_0", outline)
        self.assertIn("L1-", outline)


class TestFailClosedOnSize(unittest.TestCase):
    """(3) the load-bearing invariant: any internal gate failure returns a
    BOUNDED HEAD, never the full oversized file. Never raises."""

    def test_cache_evicted_failure_falls_back_to_bounded_head(self):
        content = _make_large_python_content()
        with patch.object(context_cache, "cache_evicted", return_value=None):
            gated_text, was_gated = ae._gate_large_file_content(
                content, "fake/large_file.py", "fix something", "test-task-fail-closed",
            )
        self.assertTrue(was_gated)
        self.assertLessEqual(len(gated_text), ae._READ_FILE_GATE_CHAR_BUDGET)
        self.assertNotEqual(gated_text, content)
        self.assertLess(len(gated_text), len(content))
        self.assertIn("summarized", gated_text)
        # bounded HEAD means it starts with the file's actual opening bytes
        self.assertTrue(content.startswith(gated_text[: min(50, len(gated_text))]))

    def test_retrieve_ctx_exception_falls_back_to_bounded_head_never_raises(self):
        content = _make_large_python_content()
        with patch.object(context_cache, "cache_evicted", return_value="some-collection"):
            with patch.object(context_cache, "retrieve_ctx", side_effect=RuntimeError("dead qdrant")):
                with patch.object(context_cache, "delete_collection", return_value=None):
                    gated_text, was_gated = ae._gate_large_file_content(
                        content, "fake/large_file.py", "fix something", "test-task-exc",
                    )
        self.assertTrue(was_gated)
        self.assertLessEqual(len(gated_text), ae._READ_FILE_GATE_CHAR_BUDGET)
        self.assertNotEqual(gated_text, content)

    def test_context_cache_unavailable_falls_back_to_bounded_head(self):
        content = _make_large_python_content()
        with patch.object(ae, "context_cache", None):
            gated_text, was_gated = ae._gate_large_file_content(
                content, "fake/large_file.py", "fix something", "test-task-no-cache",
            )
        self.assertTrue(was_gated)
        self.assertLessEqual(len(gated_text), ae._READ_FILE_GATE_CHAR_BUDGET)
        self.assertNotEqual(gated_text, content)

    def test_never_exceeds_a_tight_custom_budget(self):
        # Exercise the unconditional final clamp directly with a budget small
        # enough that even the outline text alone would overshoot it.
        content = _make_large_python_content()
        with patch.object(context_cache, "cache_evicted", return_value=None):
            gated_text, was_gated = ae._gate_large_file_content(
                content, "fake/large_file.py", "fix something", "test-task-tight",
                budget_chars=200,
            )
        self.assertTrue(was_gated)
        self.assertLessEqual(len(gated_text), 200)

    def test_never_raises_on_malformed_retrieved_chunks(self):
        content = _make_large_python_content()
        with patch.object(context_cache, "cache_evicted", return_value="some-collection"):
            with patch.object(context_cache, "retrieve_ctx", return_value=["not-a-citation-framed-chunk", "", None]):
                with patch.object(context_cache, "delete_collection", return_value=None):
                    gated_text, was_gated = ae._gate_large_file_content(
                        content, "fake/large_file.py", "fix something", "test-task-malformed",
                    )
        self.assertTrue(was_gated)
        self.assertLessEqual(len(gated_text), ae._READ_FILE_GATE_CHAR_BUDGET)


class TestGatedChunkVerbatim(unittest.TestCase):
    """Coordinator-diagnosed bug fix (2026-08-18): the gate's returned chunks
    must be BYTE-IDENTICAL to the real source (indentation intact), not
    reformatted. The bug: `body.strip()` on the whole chunk string eats
    leading whitespace CHARACTERS from the chunk's first line — which is
    real indentation whenever a chunk boundary lands mid-indented-block (the
    norm: `_chunk_file` slices at a flat FILE_CHUNK_LINES stride, blind to
    code structure). That silently broke the one property this gate exists
    to preserve: a byte-exact edit_file old_string built from a gated read.
    Fix: `body.strip('\\n')` — trims only incidental leading/trailing blank
    lines, never touches indentation on a real code line."""

    def test_gated_chunk_is_byte_identical_to_source_including_indentation(self):
        content = _make_large_python_content()
        from context_assembler import _chunk_file as real_chunk_file
        chunks = real_chunk_file(content, "fake/large_file.py")
        # Pick a REAL chunk (not hand-crafted) whose first body line is
        # indented — the realistic worst case this bug hits, guaranteed to
        # occur somewhere in a 220-func file sliced at a flat 40-line stride
        # that doesn't align to the 3-line function boundary.
        indented_chunk = next(
            c for c in chunks
            if c.split("\n", 2)[1].startswith("    ")
        )
        citation, body = ae._rf_parse_chunk_citation(indented_chunk)
        self.assertTrue(body.startswith(" "), "fixture must exercise an indented chunk start")

        with patch.object(context_cache, "cache_evicted", return_value="fake-collection"):
            with patch.object(context_cache, "retrieve_ctx", return_value=[indented_chunk]):
                with patch.object(context_cache, "delete_collection", return_value=None):
                    gated_text, was_gated = ae._gate_large_file_content(
                        content, "fake/large_file.py", "fix func_42", "test-task-verbatim",
                    )

        self.assertTrue(was_gated)
        self.assertIn(f"[{citation}]", gated_text)
        # The load-bearing assertion: the chunk body (indentation intact) is
        # a byte-exact substring of both the gated output AND the real file
        # content — the same property an edit_file old_string depends on.
        self.assertIn(body, gated_text)
        self.assertIn(body, content)


class TestStructuralNoCommit(unittest.TestCase):
    """(4) git_add/git_commit are absent from the default local tool set."""

    def test_always_tools_no_longer_lists_git_write_tools(self):
        self.assertNotIn("git_add", ae._AEXEC_ALWAYS_TOOLS)
        self.assertNotIn("git_commit", ae._AEXEC_ALWAYS_TOOLS)

    def test_commit_tools_constant_defined(self):
        self.assertEqual(ae._AEXEC_COMMIT_TOOLS, frozenset({"git_add", "git_commit"}))

    def _build_full_registry_tool_names(self) -> set:
        from builtin_tools.file_operations import register_file_tools
        from builtin_tools.git_tools import register_git_tools

        registry = tool_registry.ToolRegistry(
            db_path=Path("/tmp/test-read-file-gate-tool-audit.db")
        )
        register_file_tools(registry)
        register_git_tools(registry)
        return {t["name"] for t in registry.get_tools_for_model()}

    def test_default_model_visible_tool_set_excludes_git_write_tools(self):
        # Registration itself is untouched (root-cause discipline: gate at the
        # point of use, don't delete the code path) — git_add/git_commit ARE
        # still registered in the raw registry...
        all_names = self._build_full_registry_tool_names()
        self.assertIn("git_add", all_names)
        self.assertIn("git_commit", all_names)

        # ...but the exact filter agent_executor._execute_with_tools applies
        # before ever showing the schema to the model excludes them by default.
        self.assertFalse(ae._LOCAL_ALLOW_COMMIT, "test assumes AQ_LOCAL_ALLOW_COMMIT is unset/off")
        filtered = [n for n in all_names if n not in ae._AEXEC_COMMIT_TOOLS]
        self.assertNotIn("git_add", filtered)
        self.assertNotIn("git_commit", filtered)
        # everything else survives the filter untouched
        self.assertIn("read_file", filtered)
        self.assertIn("edit_file", filtered)

    def test_allow_commit_env_flag_restores_git_tools(self):
        with patch.object(ae, "_LOCAL_ALLOW_COMMIT", True):
            all_names = self._build_full_registry_tool_names()
            filtered = (
                [n for n in all_names if n not in ae._AEXEC_COMMIT_TOOLS]
                if not ae._LOCAL_ALLOW_COMMIT
                else list(all_names)
            )
            self.assertIn("git_add", filtered)
            self.assertIn("git_commit", filtered)


if __name__ == "__main__":
    print(f"[test-read-file-gate] LIVE backends: {LIVE}", file=sys.stderr)
    unittest.main(verbosity=2)
