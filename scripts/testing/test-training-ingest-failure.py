#!/usr/bin/env python3
"""P1.2 — capture->ingest loop: failure samples become dataset repair pairs."""

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
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    added, pending = ing._ingest_failure_samples(_since())
    assert added == 1 and pending == 0
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
    added, pending = ing._ingest_failure_samples(_since())
    assert added == 0 and pending == 1
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
    added, pending = ing._ingest_failure_samples(_since())
    assert added == 1 and pending == 0
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
    ing = training_ingest.TrainingIngestor(dataset_path=dataset, dry_run=False)
    a1, _ = ing._ingest_failure_samples(_since())
    a2, _ = ing._ingest_failure_samples(_since())  # rerun: already in dataset
    assert a1 == 1 and a2 == 0
    assert len(dataset.read_text().strip().splitlines()) == 1


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
