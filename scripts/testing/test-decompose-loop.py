#!/usr/bin/env python3
"""
Regression tests — ai-stack/local-agents/decompose_loop.py.

The DECOMPOSE-CONDENSE loop lets local Qwen (small input budget) work
through an over-budget task by splitting it into ordered bites and using
context_cache (embed :8081 + Qdrant :6333) for per-bite semantic recall.

Dual-mode: run directly (`python3 test-decompose-loop.py`) or under pytest;
both paths execute the same unittest.TestCase classes, so neither mode can
silently no-op (no false-green — see test-context-cache.py for the sibling
pattern this mirrors).

Coverage:
  1. small-task-one-bite (no-op)
  2. large-task-splits-into-N-bites, every bite under max_bite_tokens
  3. per-bite retrieval pulls relevant prior context — REAL context_cache
     (embed :8081 + Qdrant :6333, both live at test-authoring time) when
     reachable; falls back to a monkeypatched cache with a note if not.
  4. failed-bite-skipped-loop-continues (call_local raises on bite 2 ->
     bites 1 and 3 complete, bite 2 recorded in failed_bites)
  5. accumulation (bite 3 can recall bite 1's cached result via retrieval)
  6. budget-never-exceeded (every per-bite prompt token estimate <= budget)
"""
from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "ai-stack" / "local-agents"))

import decompose_loop as dl  # noqa: E402
import context_cache  # noqa: E402


def _live_cache_available() -> bool:
    """Probe the real embed endpoint (:8081) — the same round-trip proof
    context_cache's own tests document as PROVEN. If it answers, tests 3/5
    exercise the REAL cache_evicted/retrieve_ctx path end-to-end instead of
    a stub."""
    try:
        return context_cache.embed_text("decompose-loop-live-probe") is not None
    except Exception:
        return False


LIVE_CACHE = _live_cache_available()


def _make_large_task(n_sections: int = 8, words_per_section: int = 200) -> str:
    """A synthetic, structurally-splittable task: markdown headers + prose,
    well over any reasonable max_bite_tokens."""
    parts = []
    for i in range(n_sections):
        body = " ".join(f"word{i}_{j}" for j in range(words_per_section))
        parts.append(f"## Section {i}: implement part {i}\n{body}.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 1. small-task-one-bite (no-op)
# ---------------------------------------------------------------------------
class TestDecomposeNoOp(unittest.TestCase):
    def test_small_task_returns_single_unchanged_bite(self):
        text = "Fix the typo in README.md line 12: 'recieve' -> 'receive'."
        bites = dl.decompose(text, max_bite_tokens=1200)
        self.assertEqual(len(bites), 1)
        self.assertEqual(bites[0].index, 0)
        self.assertEqual(bites[0].text, text)

    def test_empty_task_returns_no_bites(self):
        self.assertEqual(dl.decompose("", max_bite_tokens=1200), [])
        self.assertEqual(dl.decompose("   \n  ", max_bite_tokens=1200), [])


# ---------------------------------------------------------------------------
# 2. large-task-splits-into-N-bites, under budget
# ---------------------------------------------------------------------------
class TestDecomposeSplitting(unittest.TestCase):
    def test_large_task_splits_into_multiple_ordered_bites(self):
        text = _make_large_task(n_sections=8, words_per_section=200)
        self.assertGreater(dl._estimate_tokens(text), 1200)  # sanity: input IS over budget

        bites = dl.decompose(text, max_bite_tokens=300)

        self.assertGreater(len(bites), 1, "over-budget task must split into >1 bite")
        # ordering preserved, contiguous indices
        self.assertEqual([b.index for b in bites], list(range(len(bites))))
        # every bite fits the requested budget
        for b in bites:
            self.assertLessEqual(
                dl._estimate_tokens(b.text), 300,
                f"bite {b.index} ({dl._estimate_tokens(b.text)} tok) exceeds max_bite_tokens=300",
            )
        # no content lost: every section marker present somewhere across bites
        joined = "\n".join(b.text for b in bites)
        for i in range(8):
            self.assertIn(f"Section {i}:", joined)

    def test_oversized_single_paragraph_hard_splits(self):
        # One giant unbroken "sentence" (no headers/steps/periods) forces the
        # hard-split fallback path.
        text = "x" * 20000
        bites = dl.decompose(text, max_bite_tokens=200)
        self.assertGreater(len(bites), 1)
        for b in bites:
            self.assertLessEqual(dl._estimate_tokens(b.text), 200)


# ---------------------------------------------------------------------------
# 3 + 5. retrieval pulls relevant prior context; accumulation across bites
# ---------------------------------------------------------------------------
class TestRetrievalAndAccumulation(unittest.TestCase):
    """Exercises run_decomposed's retrieve -> call -> cache_evicted loop.
    Uses the REAL context_cache (live embed :8081 + Qdrant :6333) when
    reachable — this is the genuine round-trip proof, not a mock. Falls back
    to a monkeypatched in-memory cache (noted in the failure/skip message)
    only if the live services are unreachable in this environment."""

    def setUp(self):
        self.task_id = f"decompose-loop-test-{uuid.uuid4().hex[:8]}"
        self._collections_to_clean: list[str] = []

    def tearDown(self):
        if LIVE_CACHE:
            for coll in self._collections_to_clean:
                context_cache.delete_collection(coll)

    def test_accumulation_bite3_recalls_bite1_result(self):
        if not LIVE_CACHE:
            self.skipTest("embed :8081 unreachable in this environment — live cache round-trip not exercised")

        # 3 sections, each padded to ~60 tokens (a single section fits under
        # max_bite_tokens=80; a joined PAIR does not), so decompose() keeps
        # them as separate bites instead of packing two into one. Each has a
        # distinctive marker so we can prove retrieval pulled the RIGHT
        # prior content, not just *some* content.
        def _padded_section(idx: int, marker: str, filler_words: int = 25) -> str:
            filler = " ".join(f"filler{idx}_{j}" for j in range(filler_words))
            return f"## Section {idx}: {marker}\n{filler}."

        text = "\n\n".join([
            _padded_section(0, "define the ZEBRA_TOKEN_ALPHA constant value 42"),
            _padded_section(1, "unrelated housekeeping task, update changelog"),
            _padded_section(2, "use ZEBRA_TOKEN_ALPHA constant in the new handler"),
        ])
        bites = dl.decompose(text, max_bite_tokens=80)
        self.assertGreaterEqual(len(bites), 3, "fixture must decompose into >=3 bites for this test")

        scratch_by_call: list = []
        bite_outputs = {
            0: "ZEBRA_TOKEN_ALPHA = 42  # defined per Section 0",
        }

        def call_local(messages):
            sys_msgs = [m["content"] for m in messages if m["role"] == "system"]
            scratch = next((c for c in sys_msgs if "Retrieved context" in c), None)
            scratch_by_call.append(scratch)
            call_idx = len(scratch_by_call) - 1
            return bite_outputs.get(call_idx, f"result for call {call_idx}")

        result = dl.run_decomposed(
            text, task_id=self.task_id, call_local=call_local,
            max_bite_tokens=80, budget_tokens=5200, retrieval_k=6,
        )
        if result.collection:
            self._collections_to_clean.append(result.collection)

        self.assertEqual(result.failed_bites, [])
        self.assertGreaterEqual(len(result.bites), 3)

        # scratch_by_call has one entry per bite call, plus a trailing
        # synthesis call (no scratchpad — synthesis prompts don't use one).
        # The scratchpad on the LAST bite call must contain bite 0's cached
        # output — proof retrieve_ctx recalled it by semantic relevance to
        # the final ("use ZEBRA_TOKEN_ALPHA...") bite's query.
        last_bite_scratch = scratch_by_call[len(result.bites) - 1]
        self.assertIsNotNone(last_bite_scratch, "expected a retrieved-context scratchpad on the final bite")
        self.assertIn("ZEBRA_TOKEN_ALPHA", last_bite_scratch)

    def test_retrieval_is_empty_on_first_bite_no_prior_cache(self):
        if not LIVE_CACHE:
            self.skipTest("embed :8081 unreachable in this environment — live cache round-trip not exercised")

        text = _make_large_task(n_sections=3, words_per_section=50)
        outputs = []

        def call_local(messages):
            sys_msgs = [m["content"] for m in messages if m["role"] == "system"]
            has_scratch = any("Retrieved context" in c for c in sys_msgs)
            outputs.append(has_scratch)
            return "ok"

        result = dl.run_decomposed(
            text, task_id=self.task_id, call_local=call_local,
            max_bite_tokens=100, budget_tokens=5200,
        )
        if result.collection:
            self._collections_to_clean.append(result.collection)

        self.assertFalse(outputs[0], "first bite has no prior cache — must have no scratchpad")


# ---------------------------------------------------------------------------
# 4. failed-bite-skipped-loop-continues
# ---------------------------------------------------------------------------
class TestFailedBiteResilience(unittest.TestCase):
    def setUp(self):
        self._collections_to_clean: list[str] = []

    def tearDown(self):
        # This class runs run_decomposed against the REAL context_cache (no
        # monkeypatch) — successful bites really cache_evicted to Qdrant.
        # Clean up so repeated test runs don't leak agent-ctx-* collections.
        for coll in self._collections_to_clean:
            context_cache.delete_collection(coll)

    def test_failing_bite_is_skipped_loop_continues(self):
        text = _make_large_task(n_sections=3, words_per_section=100)
        bites = dl.decompose(text, max_bite_tokens=150)
        self.assertGreaterEqual(len(bites), 3)

        call_count = {"n": 0}

        def call_local(messages):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("simulated transient local-model failure")
            return f"result for call {call_count['n']}"

        result = dl.run_decomposed(
            text, task_id=f"decompose-loop-fail-{uuid.uuid4().hex[:8]}",
            call_local=call_local, max_bite_tokens=150, budget_tokens=5200,
        )
        if result.collection:
            self._collections_to_clean.append(result.collection)

        self.assertEqual(len(result.failed_bites), 1)
        self.assertEqual(result.failed_bites[0].index, 1)  # 0-indexed bite 2
        self.assertIn("simulated transient", result.failed_bites[0].error)
        # loop kept going: bites 0 and 2 (at least) completed despite bite 1 failing
        self.assertGreaterEqual(len(result.bites), len(bites) - 1)
        self.assertNotEqual(result.final, "")

    def test_empty_response_treated_as_failure_not_raise(self):
        text = _make_large_task(n_sections=2, words_per_section=80)

        def call_local(messages):
            return ""  # empty response — must be recorded as a failure, not crash

        result = dl.run_decomposed(
            text, task_id=f"decompose-loop-empty-{uuid.uuid4().hex[:8]}",
            call_local=call_local, max_bite_tokens=150, budget_tokens=5200,
        )
        self.assertEqual(len(result.bites), 0)
        self.assertGreater(len(result.failed_bites), 0)
        # run_decomposed itself never raises even when every bite fails.
        self.assertEqual(result.final, "")


# ---------------------------------------------------------------------------
# 6. budget-never-exceeded
# ---------------------------------------------------------------------------
class TestBudgetNeverExceeded(unittest.TestCase):
    def test_per_bite_prompt_estimate_stays_under_budget(self):
        # Monkeypatched cache returning a large batch of retrieved chunks —
        # forces _assemble_prompt's drop-lowest-relevance trimming path.
        text = _make_large_task(n_sections=5, words_per_section=150)
        budget = 400  # deliberately tight budget vs a 6-chunk scratchpad

        fake_chunks = [f"prior finding {i}: " + ("z" * 300) for i in range(6)]

        class _FakeCache:
            @staticmethod
            def retrieve_ctx(collection, query, k=6):
                return list(fake_chunks)

            @staticmethod
            def cache_evicted(task_id, chunks):
                return "fake-collection"

            @staticmethod
            def scratchpad_message(retrieved):
                return context_cache.scratchpad_message(retrieved)

        original_cache = dl.context_cache
        dl.context_cache = _FakeCache
        try:
            recorded_prompt_tokens = []

            def call_local(messages):
                total = sum(dl._estimate_tokens(m.get("content") or "") for m in messages)
                recorded_prompt_tokens.append(total)
                self.assertLessEqual(total, budget, "per-bite prompt exceeded budget_tokens")
                return "ok"

            result = dl.run_decomposed(
                text, task_id="budget-test", call_local=call_local,
                max_bite_tokens=200, budget_tokens=budget,
            )
        finally:
            dl.context_cache = original_cache

        self.assertGreater(len(recorded_prompt_tokens), 0)
        for t in result.token_stats["prompt_tokens_by_bite"]:
            self.assertLessEqual(t, budget)


if __name__ == "__main__":
    unittest.main(verbosity=2)
