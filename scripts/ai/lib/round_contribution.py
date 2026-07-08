#!/usr/bin/env python3
"""Typed contribution schema and text fallback extraction for collaboration rounds."""

from __future__ import annotations

import ast
import json
import re
import sys
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_AGENTS_DIR = REPO_ROOT / "ai-stack" / "local-agents"
if LOCAL_AGENTS_DIR.exists() and str(LOCAL_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_AGENTS_DIR))

try:
    import training_capture
except Exception:  # pragma: no cover - capture is best-effort instrumentation.
    training_capture = None  # type: ignore[assignment]


class Verdict(StrEnum):
    """Review verdict for one round contribution."""

    APPROVE = "APPROVE"
    APPROVE_WITH_CHANGES = "APPROVE_WITH_CHANGES"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"


class Severity(StrEnum):
    """Severity for a required change."""

    critical = "critical"
    minor = "minor"


class StrictModel(BaseModel):
    """Base model that rejects undeclared contribution fields."""

    model_config = ConfigDict(extra="forbid")


class RequiredChange(StrictModel):
    """One change required before approval."""

    file_path: str
    line_range: str | None
    description: str
    severity: Severity


class ModelProvenance(StrictModel):
    """Model identity and parameters used to produce a contribution."""

    model_name: str
    model_version: str | None
    params: dict[str, Any] = Field(default_factory=dict)


class Contribution(StrictModel):
    """Pydantic SSOT for one typed round contribution."""

    schema_version: str = "1.0"
    agent_id: str
    model_provenance: ModelProvenance
    verdict: Verdict
    required_changes: list[RequiredChange] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    anchors: list[str] = Field(default_factory=list)
    top_changes: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None
    body_markdown: str | None = None


FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
JSON_OBJECT_START_RE = re.compile(r"\{")


def extract_contribution(
    agent: str,
    round_dir: Path,
    output_log: Path | None = None,
) -> tuple[Contribution | None, str]:
    """Resolve one agent contribution from sidecar JSON or text-only fallback."""

    sidecar = round_dir / f"{agent}.json"
    if sidecar.exists():
        try:
            return Contribution.model_validate_json(sidecar.read_text(encoding="utf-8")), "sidecar"
        except (OSError, ValidationError, ValueError):
            return None, "failed:invalid-sidecar"

    markdown = round_dir / f"{agent}.md"
    for path in _candidate_paths(markdown, output_log):
        text = _read_text(path)
        if not text.strip():
            continue

        recovered = _extract_structured_payload(text)
        if recovered and "verdict" in recovered:
            contribution = _build_fallback_contribution(agent, recovered, text)
            if contribution is not None:
                _capture_fallback_failure(
                    agent=agent,
                    round_dir=round_dir,
                    output_log=output_log,
                    bad_output=text,
                    failure_class="round_contribution_structured_fallback",
                )
                return contribution, "extracted-fallback"

        if path == markdown:
            contribution = _minimal_prose_contribution(agent, text)
            _capture_fallback_failure(
                agent=agent,
                round_dir=round_dir,
                output_log=output_log,
                bad_output=text,
                failure_class="round_contribution_prose_fallback",
            )
            return contribution, "extracted-prose"

        prose = _extract_prose_from_log(text)
        if prose.strip():
            contribution = _minimal_prose_contribution(agent, prose)
            _capture_fallback_failure(
                agent=agent,
                round_dir=round_dir,
                output_log=output_log,
                bad_output=prose,
                failure_class="round_contribution_log_prose_fallback",
            )
            return contribution, "extracted-prose"

    return None, "absent"


def export_json_schema() -> dict[str, Any]:
    """Export the contribution JSON Schema from the Pydantic SSOT."""

    return Contribution.model_json_schema()


def _capture_fallback_failure(
    *,
    agent: str,
    round_dir: Path,
    output_log: Path | None,
    bad_output: str,
    failure_class: str,
) -> None:
    """Capture fallback-only contributions as teacher-correctable training samples."""

    if training_capture is None:
        return
    prompt = (
        "Emit a valid collaboration Contribution JSON sidecar for the agent output. "
        "The JSON must satisfy scripts/ai/lib/round_contribution.py::Contribution."
    )
    try:
        training_capture.capture_failure(
            prompt=prompt,
            bad_output=bad_output,
            failure_class=failure_class,
            tools_available=["contribution_json_sidecar"],
            model_provenance={
                "agent_id": agent,
                "round_dir": str(round_dir),
                "output_log": str(output_log) if output_log is not None else None,
            },
            source="round_contribution.extract_contribution",
        )
    except Exception:
        return


def _candidate_paths(markdown: Path, output_log: Path | None) -> list[Path]:
    paths = [markdown]
    if output_log is not None:
        paths.append(output_log)
    return paths


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _extract_structured_payload(text: str) -> dict[str, Any] | None:
    candidates: list[str] = []

    front_matter = FRONT_MATTER_RE.search(text)
    if front_matter:
        candidates.append(front_matter.group(1))

    candidates.extend(match.group(1) for match in FENCED_JSON_RE.finditer(text))
    candidates.extend(_json_object_candidates(text))
    candidates.extend(_json_object_candidates(_unescape_text(text)))

    for candidate in candidates:
        parsed = _parse_object_prefix(candidate)
        if isinstance(parsed, dict):
            return parsed
        parsed = _parse_simple_yaml(candidate)
        if isinstance(parsed, dict):
            return parsed
    return None


def _json_object_candidates(text: str) -> list[str]:
    return [text[match.start() :] for match in JSON_OBJECT_START_RE.finditer(text)]


def _parse_object_prefix(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index in range(len(text)):
        if text[index] != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _parse_simple_yaml(text: str) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            return None
        payload[key] = _coerce_scalar(value.strip())
    return payload or None


def _coerce_scalar(value: str) -> Any:
    if value == "":
        return None
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value.strip("\"'")


def _unescape_text(text: str) -> str:
    try:
        return bytes(text, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return text


def _build_fallback_contribution(
    agent: str,
    payload: dict[str, Any],
    body_markdown: str,
) -> Contribution | None:
    normalized = dict(payload)
    normalized.setdefault("agent_id", agent)
    normalized.setdefault("schema_version", "1.0")
    normalized.setdefault("required_changes", [])
    normalized.setdefault("risks", [])
    normalized.setdefault("tests", [])
    normalized.setdefault("anchors", [])
    normalized.setdefault("top_changes", [])
    normalized.setdefault("metrics", {})
    normalized.setdefault("signature", None)
    normalized.setdefault("body_markdown", body_markdown)
    normalized["verdict"] = _normalize_verdict(normalized["verdict"])

    provenance = normalized.get("model_provenance")
    if not isinstance(provenance, dict):
        normalized["model_provenance"] = {
            "model_name": str(
                normalized.pop("model_name", None)
                or normalized.pop("model", None)
                or normalized.pop("provider_model", None)
                or "unknown"
            ),
            "model_version": normalized.pop("model_version", None),
            "params": normalized.pop("params", {}),
        }

    try:
        return Contribution.model_validate(normalized)
    except ValidationError:
        return None


def _normalize_verdict(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().upper().replace("-", "_").replace(" ", "_")
    return value


def _minimal_prose_contribution(agent: str, body_markdown: str) -> Contribution:
    return Contribution(
        agent_id=agent,
        model_provenance=ModelProvenance(
            model_name="unknown",
            model_version=None,
        ),
        verdict=Verdict.ABSTAIN,
        body_markdown=body_markdown,
    )


def _extract_prose_from_log(text: str) -> str:
    unescaped = _unescape_text(text)
    result_match = re.search(r'"result"\s*:\s*"(.*?)(?:",\s*"error"|$)', unescaped, re.DOTALL)
    if result_match:
        return result_match.group(1)
    return unescaped
