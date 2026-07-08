#!/usr/bin/env python3
"""P1.2 — capture->ingest loop: failure samples become dataset repair pairs.
Also covers the HITL poison guard (P-HITL): a corrected repair pair only ingests once approved."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ai-stack" / "local-agents"))

import training_capture  # noqa: E402
import training_ingest  # noqa: E402


def _since():
    return datetime.now(timezone.utc) - timedelta(days=1)


def _write_records(path: Path, records: list[dict]) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def test_failure_with_correction_becomes_sft_repair_pair(tmp_path, monkeypatch):
    samples = tmp_path / "training-samples.jsonl"
    dataset = tmp_path / "dataset.jsonl"
    training_capture.capture_failure(
        prompt="call read_file on x", bad_output="I will read it.",
        failure_class="text_as_tool_call",
        corrected_output='{"function":"read_file","arguments":{"path":"x"}}',
        path=samples,
    )
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES", samples)
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES_SPOOL", tmp_path / "nope.jsonl")
    # Gate OFF here: this test asserts the ingest mechanics, not the review gate.
    monkeypatch.setattr(training_ingest, "_REQUIRE_REPAIR_APPROVAL", False)
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    added, pending, pending_review = ing._ingest_failure_samples(_since())
    assert added == 1 and pending == 0 and pending_review == 0
    row = json.loads(dataset.read_text().strip())
    assert row["source"] == "failure-repair:text_as_tool_call"
    assert row["messages"][0]["role"] == "user"
    assert row["messages"][1]["content"] == '{"function":"read_file","arguments":{"path":"x"}}'


def test_uncorrected_failure_is_pending_not_written(tmp_path, monkeypatch):
    samples = tmp_path / "s.jsonl"
    dataset = tmp_path / "d.jsonl"
    training_capture.capture_failure(prompt="p", bad_output="bad", failure_class="invalid_tool_json", path=samples)
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES", samples)
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES_SPOOL", tmp_path / "nope.jsonl")
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    added, pending, pending_review = ing._ingest_failure_samples(_since())
    assert added == 0 and pending == 1 and pending_review == 0
    assert not dataset.exists() or dataset.read_text().strip() == ""


def test_success_sample_becomes_positive_pair(tmp_path, monkeypatch):
    samples = tmp_path / "s.jsonl"
    dataset = tmp_path / "d.jsonl"
    training_capture.capture_success(
        prompt="summarize the file", good_output="COMPLETED: summarized config.nix in 3 bullets.",
        source="agent_executor.final", path=samples,
    )
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES", samples)
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES_SPOOL", tmp_path / "nope.jsonl")
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    added, pending, pending_review = ing._ingest_failure_samples(_since())
    assert added == 1 and pending == 0 and pending_review == 0
    row = json.loads(dataset.read_text().strip())
    assert row["source"].startswith("success-capture")
    assert row["messages"][1]["content"].startswith("COMPLETED:")


def test_dedupe_on_second_ingest(tmp_path, monkeypatch):
    samples = tmp_path / "s.jsonl"
    dataset = tmp_path / "d.jsonl"
    training_capture.capture_failure(
        prompt="p", bad_output="b", failure_class="x", corrected_output="correct", path=samples,
    )
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES", samples)
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES_SPOOL", tmp_path / "nope.jsonl")
    monkeypatch.setattr(training_ingest, "_REQUIRE_REPAIR_APPROVAL", False)
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    a1, _, _ = ing._ingest_failure_samples(_since())
    a2, _, _ = ing._ingest_failure_samples(_since())  # rerun: already in dataset
    assert a1 == 1 and a2 == 0
    assert len(dataset.read_text().strip().splitlines()) == 1


# ── HITL poison guard (gate ON) ────────────────────────────────────────────────

def test_corrected_but_unapproved_is_held_for_review(tmp_path, monkeypatch):
    """Gate ON + a correction with no review_status -> NOT ingested, counted as pending_review."""
    samples = tmp_path / "s.jsonl"
    dataset = tmp_path / "d.jsonl"
    _write_records(samples, [{
        "kind": "failure_sample", "prompt": "call read_file", "bad_output": "prose",
        "failure_class": "text_as_tool_call",
        "corrected_output": '{"function":"read_file","arguments":{"path":"x"}}',
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }])
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES", samples)
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES_SPOOL", tmp_path / "nope.jsonl")
    monkeypatch.setattr(training_ingest, "_REQUIRE_REPAIR_APPROVAL", True)
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    added, pending, pending_review = ing._ingest_failure_samples(_since())
    assert added == 0 and pending_review == 1
    assert not dataset.exists() or dataset.read_text().strip() == ""


def test_approved_correction_ingests(tmp_path, monkeypatch):
    samples = tmp_path / "s.jsonl"
    dataset = tmp_path / "d.jsonl"
    _write_records(samples, [{
        "kind": "failure_sample", "prompt": "call read_file", "bad_output": "prose",
        "failure_class": "text_as_tool_call",
        "corrected_output": '{"function":"read_file","arguments":{"path":"x"}}',
        "review_status": "approved",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }])
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES", samples)
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES_SPOOL", tmp_path / "nope.jsonl")
    monkeypatch.setattr(training_ingest, "_REQUIRE_REPAIR_APPROVAL", True)
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    added, pending, pending_review = ing._ingest_failure_samples(_since())
    assert added == 1 and pending_review == 0
    assert dataset.read_text().strip() != ""


def test_rejected_correction_is_dropped(tmp_path, monkeypatch):
    samples = tmp_path / "s.jsonl"
    dataset = tmp_path / "d.jsonl"
    _write_records(samples, [{
        "kind": "failure_sample", "prompt": "call read_file", "bad_output": "prose",
        "failure_class": "text_as_tool_call",
        "corrected_output": '{"function":"delete_everything","arguments":{}}',  # a bad teacher correction
        "review_status": "rejected", "review_reason": "wrong tool",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }])
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES", samples)
    monkeypatch.setattr(training_ingest, "TRAINING_SAMPLES_SPOOL", tmp_path / "nope.jsonl")
    monkeypatch.setattr(training_ingest, "_REQUIRE_REPAIR_APPROVAL", True)
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    added, pending, pending_review = ing._ingest_failure_samples(_since())
    assert added == 0 and pending_review == 0  # rejected is neither ingested nor pending
    assert not dataset.exists() or dataset.read_text().strip() == ""


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
