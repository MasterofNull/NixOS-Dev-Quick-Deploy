#!/usr/bin/env python3
"""Fast tests for typed round contribution extraction."""

from __future__ import annotations

import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

import round_contribution  # noqa: E402


def valid_payload(agent_id: str = "codex") -> dict[str, object]:
    """Build a minimal valid contribution payload."""

    return {
        "agent_id": agent_id,
        "model_provenance": {
            "model_name": "gpt-5-codex",
            "model_version": None,
            "params": {},
        },
        "verdict": "APPROVE_WITH_CHANGES",
        "required_changes": [
            {
                "file_path": "scripts/ai/lib/round_contribution.py",
                "line_range": "10-20",
                "description": "Tighten fallback parsing.",
                "severity": "minor",
            }
        ],
    }


def test_valid_sidecar_is_loaded(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    previous_capture = round_contribution.training_capture
    round_contribution.training_capture = _FakeTrainingCapture(calls)  # type: ignore[assignment]
    sidecar = tmp_path / "codex.json"
    sidecar.write_text(
        round_contribution.Contribution.model_validate(valid_payload()).model_dump_json(),
        encoding="utf-8",
    )

    try:
        contribution, status = round_contribution.extract_contribution("codex", tmp_path)
    finally:
        round_contribution.training_capture = previous_capture

    assert status == "sidecar"
    assert contribution is not None
    assert contribution.agent_id == "codex"
    assert contribution.verdict == round_contribution.Verdict.APPROVE_WITH_CHANGES
    assert contribution.required_changes[0].severity == round_contribution.Severity.minor
    assert calls == []


def test_present_but_invalid_sidecar_fails_without_markdown_fallback(tmp_path: Path) -> None:
    (tmp_path / "local.json").write_text('{"verdict": "APPROVE"}', encoding="utf-8")
    (tmp_path / "local.md").write_text(
        "```json\n{\"verdict\":\"REJECT\"}\n```\n",
        encoding="utf-8",
    )

    contribution, status = round_contribution.extract_contribution("local", tmp_path)

    assert contribution is None
    assert status == "failed:invalid-sidecar"


def test_absent_sidecar_fenced_json_markdown_extracts_fallback(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    previous_capture = round_contribution.training_capture
    round_contribution.training_capture = _FakeTrainingCapture(calls)  # type: ignore[assignment]
    (tmp_path / "gemini.md").write_text(
        "Review notes.\n"
        "```json\n"
        '{"verdict":"approve","risks":["late local lane"],"top_changes":["Add schema"]}\n'
        "```\n",
        encoding="utf-8",
    )

    try:
        contribution, status = round_contribution.extract_contribution("gemini", tmp_path)
    finally:
        round_contribution.training_capture = previous_capture

    assert status == "extracted-fallback"
    assert contribution is not None
    assert contribution.agent_id == "gemini"
    assert contribution.model_provenance.model_name == "unknown"
    assert contribution.verdict == round_contribution.Verdict.APPROVE
    assert contribution.risks == ["late local lane"]
    assert contribution.body_markdown is not None
    assert calls[0]["failure_class"] == "round_contribution_structured_fallback"
    assert calls[0]["source"] == "round_contribution.extract_contribution"
    assert "Contribution JSON sidecar" in str(calls[0]["prompt"])
    assert "late local lane" in str(calls[0]["bad_output"])


def test_prose_only_markdown_extracts_abstain(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    previous_capture = round_contribution.training_capture
    round_contribution.training_capture = _FakeTrainingCapture(calls)  # type: ignore[assignment]
    prose = "I could not produce typed JSON, but the design looks internally consistent."
    (tmp_path / "local.md").write_text(prose, encoding="utf-8")

    try:
        contribution, status = round_contribution.extract_contribution("local", tmp_path)
    finally:
        round_contribution.training_capture = previous_capture

    assert status == "extracted-prose"
    assert contribution is not None
    assert contribution.verdict == round_contribution.Verdict.ABSTAIN
    assert contribution.body_markdown == prose
    assert contribution.top_changes == []
    assert calls[0]["failure_class"] == "round_contribution_prose_fallback"
    assert calls[0]["bad_output"] == prose


def test_real_truncated_local_dispatch_log_recovers_contribution(tmp_path: Path) -> None:
    fixture = REPO_ROOT / ".agents" / "delegation" / "outputs" / "local-20260707-165501-e1k8vc.log"

    contribution, status = round_contribution.extract_contribution(
        "local",
        tmp_path,
        output_log=fixture,
    )

    assert status in {"extracted-fallback", "extracted-prose"}
    assert contribution is not None
    assert contribution.agent_id == "local"
    assert contribution.body_markdown
    assert contribution.verdict in set(round_contribution.Verdict)


def test_export_json_schema_is_valid_draft_2020_12_schema() -> None:
    schema = round_contribution.export_json_schema()

    jsonschema.Draft202012Validator.check_schema(schema)


class _FakeTrainingCapture:
    def __init__(self, calls: list[dict[str, object]]) -> None:
        self.calls = calls

    def capture_failure(self, **kwargs: object) -> Path:
        self.calls.append(kwargs)
        return Path("training-samples.jsonl")
