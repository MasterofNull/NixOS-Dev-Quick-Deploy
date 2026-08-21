#!/usr/bin/env python3
"""
Slice 0.1 regression tests — ai-stack/local-agents/context_assembler.py.

Dual-mode, mirroring test-decompose-loop.py's pattern: probe the real embed
endpoint (:8081) once at import time. If it answers, tests that need a code
task pulling from multiple collections run against the REAL bge-m3 + Qdrant
(:6333) — a genuine round-trip proof, not a mock. If unreachable, those tests
fall back to a monkeypatched httpx.Client stub (test-context-cache.py's
FakeClient/FakeResponse pattern) so the suite never silently no-ops either way.

Coverage:
  1. code-ish task pulls from >=2 collections when backends are up (real or stub)
  2. output respects token_budget (tight budget -> small assembled block)
  3. fail-open: dead embed endpoint -> valid, empty AssembledContext (no raise)
  4. fail-open: one collection missing (404) -> its source skipped, others kept
  5. citations present in the formatted block (per-source, per-item)
  6. AQ_CONTEXT_ASSEMBLER wiring smoke test (dispatch.py's gate helper)
"""
from __future__ import annotations

import contextlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "ai-stack" / "local-agents"))

import context_assembler as ca  # noqa: E402
import context_cache  # noqa: E402


def _live_backends_available() -> bool:
    """Probe the real embed endpoint (:8081) — same proof pattern as
    test-decompose-loop.py's _live_cache_available()."""
    try:
        return context_cache.embed_text("context-assembler-live-probe") is not None
    except Exception:
        return False


LIVE = _live_backends_available()


class FakeResponse:
    """Minimal stand-in for httpx.Response — only what context_assembler reads."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


class FakeClient:
    """Stand-in for httpx.Client — routes calls through a test dispatcher."""

    def __init__(self, dispatcher, *args, **kwargs):
        self._dispatcher = dispatcher

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def post(self, url, json=None, params=None):
        return self._dispatcher("POST", url, json, params)


def _client_factory(dispatcher):
    def _factory(*args, **kwargs):
        return FakeClient(dispatcher)
    return _factory


def _stub_hit(text_field: str, value: str, score: float, extra=None):
    payload = {text_field: value}
    if extra:
        payload.update(extra)
    return {"id": f"id-{value[:8]}", "score": score, "payload": payload}


@contextlib.contextmanager
def _stub_qdrant(dispatcher, embed_vector=None):
    """Patch BOTH context_cache.embed_text and ca.httpx.Client together.

    ca.httpx and context_cache.httpx are the SAME cached module object (both
    modules do a plain `import httpx`), so patching only `ca.httpx.Client`
    also silently reroutes context_cache.embed_text's own /v1/embeddings call
    through the Qdrant-only stub dispatcher, starving it of a valid vector
    and short-circuiting assemble_context via the (correct, but here
    unintended) fail-open path before search ever runs. Patching embed_text
    directly decouples the two so the stub dispatcher only has to answer for
    Qdrant search calls, regardless of whether the real embed endpoint is
    reachable in this environment."""
    vector = embed_vector if embed_vector is not None else [0.1] * 1024
    with patch.object(context_cache, "embed_text", return_value=vector):
        with patch.object(ca.httpx, "Client", _client_factory(dispatcher)):
            yield


def _default_stub_dispatcher(method, url, json, params):
    """Serves plausible hits for every DEFAULT_SOURCES collection so a
    'code-ish task pulls from >=2 collections' assertion is meaningful even
    fully offline. 404s one collection (wiki-sections) to also exercise the
    missing-collection fail-open path in the same run."""
    if url.endswith("/collections/codebase-context/points/search"):
        return FakeResponse(200, {"result": [
            _stub_hit("commit_subject", "fix(dispatch): guard slot queue race", 0.91,
                      {"commit_hash": "abcd1234ef", "commit_body": "root cause: ...",
                       "files_changed": ["scripts/ai/lib/dispatch.py"]}),
        ]})
    if url.endswith("/collections/error-solutions/points/search"):
        return FakeResponse(200, {"result": [
            _stub_hit("title", "slot queue deadlock", 0.87,
                      {"content": "acquire before release ordering fixes it"}),
        ]})
    if url.endswith("/collections/best-practices/points/search"):
        return FakeResponse(200, {"result": [
            _stub_hit("title", "fail-open httpx calls", 0.75,
                      {"content": "wrap every network call in try/except"}),
        ]})
    if url.endswith("/collections/skills-patterns/points/search"):
        return FakeResponse(200, {"result": [
            _stub_hit("prompt", "how to guard a dispatch race?", 0.70,
                      {"response": "use a slot scheduler", "pattern_id": "sp-42"}),
        ]})
    if url.endswith("/collections/wiki-sections/points/search"):
        return FakeResponse(404, {})  # exercise the missing-collection path
    if url.endswith("/collections/agent-memory-semantic/points/search"):
        return FakeResponse(200, {"result": [
            _stub_hit("summary", "dispatch.py owns local delegation entry", 0.60,
                      {"memory_id": "mem-7"}),
        ]})
    return FakeResponse(500, {})


class TestMultiCollectionPull(unittest.TestCase):
    """(a) a code-ish task pulls from >=2 collections when backends are up."""

    def test_code_task_pulls_multiple_collections(self):
        task = "Fix the race condition in the slot queue dispatch acquire/release ordering."
        if LIVE:
            result = ca.assemble_context(task, task_id="test-multi-live")
        else:
            with _stub_qdrant(_default_stub_dispatcher):
                result = ca.assemble_context(task, task_id="test-multi-stub")
        self.assertGreaterEqual(
            result.stats.get("collections_hit", 0), 2,
            f"expected >=2 collections hit, stats={result.stats}",
        )
        collections_seen = {s["collection"] for s in result.sources}
        self.assertGreaterEqual(len(collections_seen), 2)


class TestTokenBudget(unittest.TestCase):
    """(b) output respects token_budget."""

    def test_tight_budget_yields_small_block(self):
        task = "Fix the race condition in the slot queue dispatch acquire/release ordering."
        tight_budget = 40
        with _stub_qdrant(_default_stub_dispatcher):
            result = ca.assemble_context(task, task_id="test-budget", token_budget=tight_budget)
        # Small header overhead (section labels) is allowed on top of the
        # item budget; the block must still stay materially bounded, not
        # balloon to the full default (~few hundred tokens) it would need to
        # fit every hit from every collection.
        self.assertLessEqual(result.tokens, tight_budget + 40,
                              f"tokens={result.tokens} stats={result.stats}")

    def test_generous_budget_fits_everything_stub_offers(self):
        task = "Fix the race condition in the slot queue dispatch acquire/release ordering."
        with _stub_qdrant(_default_stub_dispatcher):
            result = ca.assemble_context(task, task_id="test-budget-wide", token_budget=3500)
        self.assertLessEqual(result.tokens, 3500)
        self.assertGreater(result.tokens, 0)


class TestFailOpen(unittest.TestCase):
    """(c) fail-open returns a valid empty context when embed/Qdrant is down."""

    def test_dead_embed_returns_empty_valid_context(self):
        with patch.object(context_cache, "embed_text", return_value=None):
            result = ca.assemble_context("anything", task_id="test-dead-embed")
        self.assertIsInstance(result, ca.AssembledContext)
        self.assertEqual(result.text, "")
        self.assertEqual(result.sources, [])
        self.assertEqual(result.tokens, 0)
        self.assertFalse(result.stats.get("embed_ok"))

    def test_dead_qdrant_returns_empty_valid_context(self):
        def _dead_dispatcher(method, url, json, params):
            raise ConnectionError(f"dead endpoint: {method} {url}")
        with patch.object(context_cache, "embed_text", return_value=[0.1] * 1024):
            with patch.object(ca.httpx, "Client", _client_factory(_dead_dispatcher)):
                result = ca.assemble_context("anything", task_id="test-dead-qdrant")
        self.assertIsInstance(result, ca.AssembledContext)
        self.assertEqual(result.text, "")
        self.assertEqual(result.tokens, 0)

    def test_empty_task_text_returns_empty_valid_context_no_network(self):
        # Must short-circuit before any embed/network call.
        with patch.object(context_cache, "embed_text") as mock_embed:
            result = ca.assemble_context("   ", task_id="test-empty-text")
        mock_embed.assert_not_called()
        self.assertEqual(result.text, "")
        self.assertEqual(result.sources, [])

    def test_missing_collection_skipped_others_kept(self):
        # wiki-sections 404s in _default_stub_dispatcher; others succeed.
        with _stub_qdrant(_default_stub_dispatcher):
            result = ca.assemble_context(
                "Fix the race condition in dispatch.", task_id="test-missing-coll",
            )
        collections_seen = {s["collection"] for s in result.sources}
        self.assertNotIn("wiki-sections", collections_seen)
        self.assertGreater(len(collections_seen), 0)

    def test_never_raises_on_totally_broken_response_json(self):
        def _bad_dispatcher(method, url, json, params):
            return FakeResponse(200, None)  # .json() -> None, no "result" key
        with patch.object(ca.httpx, "Client", _client_factory(_bad_dispatcher)):
            result = ca.assemble_context("Fix the bug.", task_id="test-bad-json")
        self.assertIsInstance(result, ca.AssembledContext)


class TestCitations(unittest.TestCase):
    """(d) citations present in the block."""

    def test_citations_present_per_source(self):
        with _stub_qdrant(_default_stub_dispatcher):
            result = ca.assemble_context(
                "Fix the race condition in the slot queue.", task_id="test-citations",
            )
        self.assertIn("## Relevant prior knowledge (front-loaded — do NOT re-fetch)", result.text)
        for source in result.sources:
            self.assertTrue(source["citation"], f"empty citation for {source}")
            self.assertIn(f"[{source['citation']}]", result.text)
        # spot-check the codebase-context citation shape: <hash>:<file>
        codebase_sources = [s for s in result.sources if s["collection"] == "codebase-context"]
        if codebase_sources:
            self.assertIn(":", codebase_sources[0]["citation"])


class TestFileTargetedRetrieval(unittest.TestCase):
    """Tier 0 — file-targeted retrieval (coordinator design refinement,
    2026-08-17): codebase-context semantic search does not reliably index
    every file (shebang scripts with no .py extension are absent from it),
    so a task naming a real file must get THAT file's actual content
    front-loaded, not a thematically-similar neighbor. Reuses
    context_cache.cache_evicted/retrieve_ctx for the embed round-trip."""

    TARGET_REL_PATH = "ai-stack/local-agents/context_cache.py"

    def test_named_existing_file_produces_file_targeted_citation(self):
        task = f"Fix the embed_text timeout handling. File: {self.TARGET_REL_PATH}"
        if LIVE:
            # Genuine round-trip: real read+chunk+embed+upsert+search+teardown
            # against the live embed (:8081) + Qdrant (:6333) — this is the
            # actual proof the coordinator asked for, not a mock.
            result = ca.assemble_context(task, task_id="test-filetargeted-live")
        else:
            with patch.object(context_cache, "cache_evicted", return_value="fake-ft-collection"):
                with patch.object(context_cache, "retrieve_ctx", return_value=[
                    f"[{self.TARGET_REL_PATH}:1-40]\ndef embed_text(text): ...",
                ]):
                    with patch.object(context_cache, "delete_collection", return_value=None):
                        with _stub_qdrant(_default_stub_dispatcher):
                            result = ca.assemble_context(task, task_id="test-filetargeted-stub")
        self.assertTrue(result.stats.get("file_targeted_hit"), result.stats)
        self.assertIn(self.TARGET_REL_PATH, result.stats.get("file_targeted_files", []))
        file_targeted_sources = [s for s in result.sources if s["collection"] == "file-targeted"]
        self.assertGreater(len(file_targeted_sources), 0)
        for s in file_targeted_sources:
            self.assertTrue(
                s["citation"].startswith(self.TARGET_REL_PATH + ":"), s["citation"],
            )
        self.assertIn("file-targeted", result.text)
        self.assertIn("file-targeted", result.stats.get("chunk_sources", []))

    def test_named_nonexistent_file_falls_back_to_semantic_only(self):
        task = "Fix the bug. File: this/path/does/not/exist.py"
        with _stub_qdrant(_default_stub_dispatcher):
            result = ca.assemble_context(task, task_id="test-filetargeted-missing")
        self.assertFalse(result.stats.get("file_targeted_hit"))
        collections_seen = {s["collection"] for s in result.sources}
        self.assertNotIn("file-targeted", collections_seen)
        # semantic tiers still contributed — Tier 0 absence must not starve Tiers 1/2.
        self.assertGreater(len(collections_seen), 0)

    def test_file_targeted_fail_open_on_cache_evicted_failure(self):
        task = f"Fix something. File: {self.TARGET_REL_PATH}"
        with patch.object(context_cache, "cache_evicted", return_value=None):
            with _stub_qdrant(_default_stub_dispatcher):
                result = ca.assemble_context(task, task_id="test-filetargeted-embed-fail")
        # embed for Tier 0 failed -> Tier 0 contributes nothing, but the call
        # as a whole must still succeed and fall through to semantic tiers.
        self.assertFalse(result.stats.get("file_targeted_hit"))
        self.assertIsInstance(result, ca.AssembledContext)
        collections_seen = {s["collection"] for s in result.sources}
        self.assertGreater(len(collections_seen), 0)

    def test_file_targeted_gets_budget_priority_over_semantic(self):
        # File-targeted chunks must land in the assembled sources even under
        # a tight combined budget, proving Tier 0 is filled before Tiers 1/2
        # (not merged into one global score sort where a low `score=1.0`
        # could lose to nothing — Tier 0 has no semantic competitor to lose
        # to by construction, but this proves the ordering wires correctly
        # end-to-end under a real budget constraint).
        task = f"Fix the bug. File: {self.TARGET_REL_PATH}"
        with patch.object(context_cache, "cache_evicted", return_value="fake-ft-collection"):
            with patch.object(context_cache, "retrieve_ctx", return_value=[
                f"[{self.TARGET_REL_PATH}:1-40]\n" + ("word " * 150),
            ]):
                with patch.object(context_cache, "delete_collection", return_value=None):
                    with _stub_qdrant(_default_stub_dispatcher):
                        result = ca.assemble_context(
                            task, task_id="test-filetargeted-priority", token_budget=250,
                        )
        collections_seen = {s["collection"] for s in result.sources}
        self.assertIn("file-targeted", collections_seen)
        # Exact budget-conformance (incl. section-header overhead) is
        # TestTokenBudget's job; this test's point is Tier-0 priority.


class TestFileTargetedVerbatim(unittest.TestCase):
    """Coordinator-diagnosed bug fix (2026-08-18): a file-targeted span's
    rendered code must be BYTE-IDENTICAL to the real source lines it cites.
    `_excerpt`'s whitespace-collapse (single-space-joins the whole span,
    destroying newlines/indentation) broke this — an `edit_file` old_string
    built from the collapsed line could never match multi-line indented
    source, which is why local's agent failed ~95% of bounded edit tasks.
    `_verbatim` + fenced-code rendering restores the property: the rendered
    span body must be found verbatim (source_text.find(...) succeeds) inside
    the real file."""

    TARGET_REL_PATH = "ai-stack/local-agents/context_cache.py"

    def _read_source_span(self, start: int, end: int) -> str:
        path = _REPO / self.TARGET_REL_PATH
        lines = path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[start - 1:end])

    def test_rendered_span_body_is_byte_identical_to_source_lines(self):
        task = f"Fix the embed_text timeout handling. File: {self.TARGET_REL_PATH}"
        # A real multi-line, indented span (function body lines carry leading
        # whitespace) — exactly what `_excerpt`'s whitespace-collapse used to
        # mangle into a single space-joined line.
        real_span = self._read_source_span(1, 30)
        fake_chunk = f"[{self.TARGET_REL_PATH}:1-30]\n{real_span}"
        with patch.object(context_cache, "cache_evicted", return_value="fake-ft-collection"):
            with patch.object(context_cache, "retrieve_ctx", return_value=[fake_chunk]):
                with patch.object(context_cache, "delete_collection", return_value=None):
                    with _stub_qdrant(_default_stub_dispatcher):
                        result = ca.assemble_context(task, task_id="test-verbatim-stub")

        file_targeted_sources = [s for s in result.sources if s["collection"] == "file-targeted"]
        self.assertGreater(len(file_targeted_sources), 0, result.stats)
        self.assertIn("```", result.text)

        # Extract the fenced code body from the file-targeted section only
        # (scoped past the section header so an incidental ``` elsewhere in
        # the block can't produce a false match).
        ft_idx = result.text.index("### file-targeted")
        ft_section = result.text[ft_idx:]
        fence_start = ft_section.index("```") + 3
        fence_end = ft_section.index("```", fence_start)
        rendered_body = ft_section[fence_start:fence_end].strip("\n")

        # (1) byte-identical to the real span as read straight from disk.
        self.assertEqual(rendered_body, real_span)
        # (2) the actual property this whole fix is for: an old_string built
        # from the rendered block is found verbatim in the real source file.
        source_text = (_REPO / self.TARGET_REL_PATH).read_text(encoding="utf-8")
        self.assertNotEqual(
            source_text.find(rendered_body), -1,
            "rendered file-targeted span must byte-match the real source file "
            "(this is what makes an edit_file old_string built from it work)",
        )

    def test_verbatim_helper_preserves_indentation_and_truncates_on_line_boundary(self):
        indented = "def foo():\n    if True:\n        return 1\n    return 2\n"
        out = ca._verbatim(indented, max_lines=100, max_chars=1000)
        self.assertEqual(out, indented.rstrip("\n"))  # no collapsing, only trailing newline dropped by splitlines
        self.assertIn("        return 1", out)  # 8-space indentation intact

        many_lines = "\n".join(f"line {i}" for i in range(100))
        truncated = ca._verbatim(many_lines, max_lines=10, max_chars=10_000)
        self.assertEqual(truncated.count("\n"), 9)  # exactly 10 lines kept
        self.assertNotIn("line 10", truncated)  # 11th line (0-indexed 10) dropped


class TestDispatchWiring(unittest.TestCase):
    """(smoke) dispatch.py's gate helper prepends assembled text and honours
    AQ_CONTEXT_ASSEMBLER=0 as a kill switch, without needing a live registry
    or output file beyond a throwaway sidecar path."""

    def setUp(self):
        sys.path.insert(0, str(_REPO / "scripts" / "ai" / "lib"))
        import dispatch as _dispatch  # noqa: E402
        self.dispatch = _dispatch
        self.tmp_output = Path("/tmp") / "context-assembler-dispatch-wiring-test.out"

    def test_kill_switch_returns_prompt_unchanged(self):
        import os
        with patch.dict(os.environ, {"AQ_CONTEXT_ASSEMBLER": "0"}):
            result = self.dispatch._apply_context_assembler(
                "original prompt", "wiring-test-off", self.tmp_output,
            )
        self.assertEqual(result, "original prompt")

    def test_enabled_prepends_when_assembler_finds_content(self):
        import os
        fake_assembled = ca.AssembledContext(
            text="## Relevant prior knowledge (front-loaded — do NOT re-fetch)\n\n### x\n- [c] y",
            sources=[{"collection": "x", "score": 0.9, "citation": "c"}],
            tokens=12,
            stats={"collections_hit": 1, "collections_queried": 1},
        )
        mod = self.dispatch._load_context_assembler()
        if mod is None:
            self.skipTest("context_assembler module unavailable via dispatch's lazy import")
        with patch.dict(os.environ, {"AQ_CONTEXT_ASSEMBLER": "1"}):
            with patch.object(mod, "assemble_context", return_value=fake_assembled):
                result = self.dispatch._apply_context_assembler(
                    "original prompt", "wiring-test-on", self.tmp_output,
                )
        self.assertIn("original prompt", result)
        self.assertIn("front-loaded", result)
        sidecar = Path(str(self.tmp_output) + ".context.json")
        self.assertTrue(sidecar.exists())
        sidecar.unlink(missing_ok=True)


if __name__ == "__main__":
    print(f"[test-context-assembler] LIVE backends: {LIVE}", file=sys.stderr)
    unittest.main(verbosity=2)
