"""Regression coverage for attribution-gated learning sinks."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


class _PointStruct:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Condition:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Qdrant:
    def __init__(self):
        self.interactions = {}
        self.feedback = []
        self.scroll_records = []
        self.scroll_filter = None
        self.retrieve_error: Exception | None = None

    def upsert(self, *, collection_name, points):
        for point in points:
            if collection_name == "interaction-history":
                self.interactions[str(point.id)] = dict(point.payload)
            elif collection_name == "learning-feedback":
                self.feedback.append(point.payload)

    def retrieve(self, *, collection_name, ids):
        if collection_name != "interaction-history":
            return []
        if self.retrieve_error is not None:
            raise self.retrieve_error
        return [
            types.SimpleNamespace(id=item, payload=self.interactions[item])
            for item in ids
            if item in self.interactions
        ]

    def set_payload(self, *, collection_name, payload, points):
        if collection_name == "interaction-history":
            for point in points:
                self.interactions[point] = dict(payload)

    def scroll(self, *, collection_name, scroll_filter, limit):
        self.scroll_filter = scroll_filter
        return self.scroll_records, None


class _Postgres:
    def __init__(self):
        self.executed = []
        self.feedback_rows = []

    async def fetch_all(self, sql, *args):
        return [dict(r) for r in reversed(self.feedback_rows) if r["rating"] < 0 and r["query"] and r["interaction_id"]]

    async def execute(self, *args):
        self.executed.append(args)


@pytest.fixture
def tracker(monkeypatch, tmp_path):
    config = types.SimpleNamespace(
        Config=types.SimpleNamespace(
            AI_MEMORY_ENABLED=True,
            HIGH_VALUE_THRESHOLD=0.0,
            PATTERN_EXTRACTION_ENABLED=True,
            FINETUNE_DATA_PATH=str(tmp_path / "training.jsonl"),
        )
    )
    models = types.SimpleNamespace(
        FieldCondition=_Condition,
        Filter=_Condition,
        MatchValue=_Condition,
        PointStruct=_PointStruct,
        Range=_Condition,
    )
    monkeypatch.setitem(sys.modules, "config", config)
    monkeypatch.setitem(sys.modules, "qdrant_client", types.SimpleNamespace(models=models))
    monkeypatch.setitem(sys.modules, "qdrant_client.models", models)
    monkeypatch.setitem(
        sys.modules,
        "shared.llm_config",
        types.SimpleNamespace(build_llama_payload=lambda *args, **kwargs: {}),
    )
    module_name = "interaction_tracker_attribution_test"
    spec = importlib.util.spec_from_file_location(
        module_name,
        Path(__file__).resolve().parents[1] / "extensions" / "interaction_tracker.py",
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    qdrant = _Qdrant()
    postgres = _Postgres()
    calls = {"training": [], "performance": [], "patterns": [], "context": [], "memory": []}

    async def embed(_text):
        return [0.1]

    async def store_memory(*args, **kwargs):
        calls["memory"].append((args, kwargs))

    async def training(**kwargs):
        calls["training"].append(kwargs)

    async def performance(**kwargs):
        calls["performance"].append(kwargs)

    async def patterns(interaction):
        calls["patterns"].append(interaction)

    async def context(ids, success):
        calls["context"].append((ids, success))

    monkeypatch.setitem(
        sys.modules,
        "model_optimization",
        types.SimpleNamespace(
            capture_training_example=training,
            record_model_performance=performance,
        ),
    )
    monkeypatch.setattr(module, "extract_patterns", patterns)
    monkeypatch.setattr(module, "update_context_metrics", context)
    module.init(
        qdrant_client=qdrant,
        postgres_client=postgres,
        llama_cpp_client=None,
        embed_fn=embed,
        store_memory_fn=store_memory,
        record_telemetry_fn=lambda *_args: None,
        performance_window=object(),
        collections={},
    )
    return module, qdrant, postgres, calls


@pytest.mark.parametrize(
    ("attribution", "outcome", "feedback", "performance", "positive", "eligible"),
    [
        (None, "success", 0, 1, True, True),
        ("unknown", "success", 0, 0, False, False),
        ("infrastructure_error", "failure", -1, 0, False, False),
        ("infeasible", "failure", -1, 0, False, False),
        ("cancelled", "failure", -1, 0, False, False),
        ("agent_error", "success", 0, 0, False, False),
        ("agent_error", "failure", 0, 1, False, True),
        ("agent_error", "unknown", -1, 1, False, True),
        ("agent_error", "unknown", 0, 0, False, False),
    ],
)
def test_outcome_attribution_gates_every_learning_sink(
    tracker, attribution, outcome, feedback, performance, positive, eligible
):
    module, qdrant, _postgres, calls = tracker

    interaction_id = asyncio.run(
        module.track_interaction(
            "how to configure",
            "1. Configure it",
            "agent",
            "model-a",
            ["context-1"],
            attribution=attribution,
        )
    )
    calls["memory"].clear()  # Raw observation storage is intentionally retained.
    asyncio.run(module.update_interaction_outcome(interaction_id, outcome, feedback))

    assert qdrant.interactions[interaction_id]["learning_eligible"] is eligible
    assert len(calls["performance"]) == performance
    assert len(calls["training"]) == int(positive)
    assert len(calls["patterns"]) == int(positive)
    assert len(calls["context"]) == int(positive)
    assert len(calls["memory"]) == int(positive)


def test_dataset_excludes_historical_and_ineligible_records(tracker):
    module, qdrant, _postgres, _calls = tracker
    qdrant.scroll_records = [
        types.SimpleNamespace(payload={"learning_eligible": True, "query": "included", "response": "ok"}),
        types.SimpleNamespace(payload={"query": "historical", "response": "excluded"}),
        types.SimpleNamespace(payload={"learning_eligible": False, "query": "excluded", "response": "no"}),
    ]

    output = asyncio.run(module.generate_fine_tuning_dataset())

    assert Path(output).read_text(encoding="utf-8").count("included") == 1
    assert "historical" not in Path(output).read_text(encoding="utf-8")
    assert any(condition.key == "learning_eligible" for condition in qdrant.scroll_filter.must)


def test_simple_feedback_retains_raw_ratings_without_performance_signal(tracker):
    module, _qdrant, postgres, _calls = tracker

    for rating in (-1, 0, 1):
        asyncio.run(module.record_simple_feedback("interaction", rating))

    assert len(postgres.executed) == 3


def test_linked_negative_feedback_requires_stored_agent_error_attribution(tracker):
    module, qdrant, _postgres, calls = tracker
    qdrant.interactions["agent"] = {
        "attribution": "agent_error",
        "attribution_supplied": True,
        "outcome": "unknown",
    }
    qdrant.interactions["unknown"] = {
        "attribution": "unknown",
        "attribution_supplied": True,
        "outcome": "failure",
    }

    for rating in (-1, 0, 1):
        asyncio.run(module.record_learning_feedback("q", "correction", rating=rating))
    asyncio.run(module.record_learning_feedback("q", "correction", interaction_id="unknown", rating=-1))
    asyncio.run(module.record_learning_feedback("q", "correction", interaction_id="agent", rating=-1))

    assert len(qdrant.feedback) == 5
    assert len(calls["memory"]) == 1


def _gap_sync(module, tmp_path, **kwargs):
    path = tmp_path / "gaps.jsonl"
    count = asyncio.run(module.sync_feedback_corrections_to_gaps(str(path), **kwargs))
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return count, [__import__("json").loads(line) for line in lines]


def _seed_gap_rows(qdrant, postgres, specs):
    for i, (iid, query, rating) in enumerate(specs):
        postgres.feedback_rows.append(
            {"feedback_id": f"f{i}", "interaction_id": iid, "query": query, "rating": rating}
        )


@pytest.mark.parametrize(
    ("payload", "exported"),
    [
        ({"attribution": "agent_error", "attribution_supplied": True, "outcome": "failure"}, True),
        ({"attribution": "infrastructure_error", "attribution_supplied": True, "outcome": "failure"}, False),
        ({"attribution": "cancelled", "attribution_supplied": True, "outcome": "failure"}, False),
        ({"attribution": "infeasible", "attribution_supplied": True, "outcome": "failure"}, False),
        ({"attribution": "agent_error", "attribution_supplied": True, "outcome": "partial"}, False),
        ({"attribution": "agent_error", "attribution_supplied": True, "outcome": "success"}, False),
        ({"attribution": "unknown", "attribution_supplied": True, "outcome": "failure"}, False),
        ({"outcome": "failure"}, False),
    ],
)
def test_gap_sync_exports_only_eligible_linked_negatives(tracker, tmp_path, payload, exported):
    module, qdrant, postgres, _calls = tracker
    qdrant.interactions["00000000-0000-4000-8000-000000000001"] = payload
    _seed_gap_rows(qdrant, postgres, [("00000000-0000-4000-8000-000000000001", "q", -1)])

    count, records = _gap_sync(module, tmp_path, min_occurrences=1)

    assert count == int(exported)
    assert [r["query_text"] for r in records] == (["q"] if exported else [])
    if exported:
        assert records[0]["source"] == "feedback_negative"
        assert records[0]["occurrences"] == 1
        assert records[0]["avg_score"] == -1.0


def test_gap_sync_excludes_unlinked_feedback(tracker, tmp_path):
    module, qdrant, postgres, _calls = tracker
    _seed_gap_rows(qdrant, postgres, [(None, "q", -1), ("00000000-0000-4000-8000-0000000000ff", "q", -1)])

    count, records = _gap_sync(module, tmp_path, min_occurrences=1)

    assert count == 0 and records == []


def test_gap_sync_counts_only_eligible_rows_per_query(tracker, tmp_path):
    module, qdrant, postgres, _calls = tracker
    qdrant.interactions["00000000-0000-4000-8000-000000000002"] = {"attribution": "agent_error", "attribution_supplied": True, "outcome": "failure"}
    qdrant.interactions["00000000-0000-4000-8000-000000000003"] = {
        "attribution": "infrastructure_error", "attribution_supplied": True, "outcome": "failure",
    }
    _seed_gap_rows(qdrant, postgres, [("00000000-0000-4000-8000-000000000002", "q", -1), ("00000000-0000-4000-8000-000000000003", "q", -1)])

    count, records = _gap_sync(module, tmp_path, min_occurrences=2)

    assert count == 0 and records == []

    _seed_gap_rows(qdrant, postgres, [("00000000-0000-4000-8000-000000000002", "q", -3)])
    count, records = _gap_sync(module, tmp_path, min_occurrences=2)
    assert count == 1
    assert records[0]["occurrences"] == 2
    assert records[0]["avg_score"] == -2.0


def test_gap_sync_fails_closed_when_lookup_raises_and_keeps_raw_rows(tracker, tmp_path):
    module, qdrant, postgres, _calls = tracker
    qdrant.interactions["00000000-0000-4000-8000-000000000002"] = {"attribution": "agent_error", "attribution_supplied": True, "outcome": "failure"}
    _seed_gap_rows(qdrant, postgres, [("00000000-0000-4000-8000-000000000002", "q", -1)])
    before = [dict(r) for r in postgres.feedback_rows]
    qdrant.retrieve_error = RuntimeError("qdrant down")

    count, records = _gap_sync(module, tmp_path, min_occurrences=1)

    assert count == 0 and records == []
    assert postgres.feedback_rows == before
    assert postgres.executed == []


def test_gap_sync_skips_malformed_interaction_ids_without_blocking_others(tracker, tmp_path):
    module, qdrant, postgres, _calls = tracker
    ok = "00000000-0000-4000-8000-000000000002"
    qdrant.interactions[ok] = {"attribution": "agent_error", "attribution_supplied": True, "outcome": "failure"}
    _seed_gap_rows(
        qdrant, postgres,
        [("not-a-uuid", "q", -1), (ok.upper(), "q", -1), (ok, "q", -1)],
    )

    count, records = _gap_sync(module, tmp_path, min_occurrences=2)

    assert count == 1
    assert records[0]["occurrences"] == 2
