#!/usr/bin/env python3
"""Focused contract tests for aq.workflow-deviation.v1."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/ai/lib/workflow_deviation.py"
FIXTURE = ROOT / "scripts/testing/fixtures/workflow-deviation-golden.json"
SCHEMA = ROOT / "config/schemas/workflow-deviation.schema.json"

spec = importlib.util.spec_from_file_location("workflow_deviation", MODULE)
assert spec and spec.loader
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


def expect_error(label: str, record: dict) -> None:
    try:
        wd.validate(record)
    except wd.DeviationContractError:
        print(f"PASS: {label}")
        return
    raise AssertionError(label)


fixture = json.loads(FIXTURE.read_text())
schema = json.loads(SCHEMA.read_text())
assert schema["$schema"].endswith("2020-12/schema")
assert schema["additionalProperties"] is False

record = wd.build(
    occurred_at=fixture["occurred_at"], source=fixture["source"],
    reason_code=fixture["reason_code"], summary=fixture["summary"],
    root_issue_key=fixture["root_issue_key"], evidence=fixture["evidence"],
)
wd.validate(record)
Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)
print("PASS: golden record validates")
assert {key: record[key] for key in fixture["expected_policy"]} == fixture["expected_policy"]
print("PASS: policy is derived exactly")

same = wd.build(
    occurred_at=fixture["occurred_at"], source=fixture["source"],
    reason_code=fixture["reason_code"], summary=fixture["summary"],
    root_issue_key=fixture["root_issue_key"], evidence=fixture["evidence"],
)
assert same["deviation_id"] == record["deviation_id"]
print("PASS: identical input is deterministic")

changed = wd.build(
    occurred_at=fixture["occurred_at"], source=fixture["source"],
    reason_code=fixture["reason_code"], summary=fixture["summary"],
    root_issue_key=fixture["root_issue_key"],
    evidence=[{**fixture["evidence"][0], "digest": "c" * 64}],
)
assert changed["deviation_id"] != record["deviation_id"]
assert changed["root_issue_key"] == record["root_issue_key"]
print("PASS: evidence revisions are distinct but share one root issue")

candidate = wd.learning_candidate(record)
assert candidate["eligible"] is True and candidate["risk"] == "low"
print("PASS: bounded observation repair is shadow-eligible")

for reason in (
    "authorization.invalid", "release.boundary", "security.policy",
    "deployment.runtime", "secret.exposure", "external.side_effect",
):
    blocked = wd.build(
        occurred_at=fixture["occurred_at"], source=fixture["source"],
        reason_code=reason, summary=fixture["summary"],
        root_issue_key=reason, evidence=fixture["evidence"],
    )
    projection = wd.learning_candidate(blocked)
    assert projection["eligible"] is False
    assert projection["disposition"] == "approval_required"
print("PASS: authority and live-effect classes are never automatic")

assert wd.classify("new.failure-class") == {
    "severity": "high", "mutation_risk": "medium", "retryable": False,
    "requires_owner": True, "automatic_eligible": False,
}
print("PASS: unknown reason codes fail closed")

extra = copy.deepcopy(record)
extra["unexpected"] = True
expect_error("unknown top-level field rejected", extra)

forged = copy.deepcopy(record)
forged["automatic_eligible"] = False
forged["deviation_id"] = wd.deviation_id({k: v for k, v in forged.items() if k != "deviation_id"})
expect_error("caller cannot override derived policy", forged)

raw = copy.deepcopy(record)
raw["evidence"][0]["raw"] = "secret"
raw["deviation_id"] = wd.deviation_id({k: v for k, v in raw.items() if k != "deviation_id"})
expect_error("raw evidence content rejected", raw)

for label, mutate in (
    ("invalid timestamp rejected", lambda r: r.__setitem__("occurred_at", "not-a-date")),
    ("naive timestamp rejected", lambda r: r.__setitem__("occurred_at", "2026-08-08T21:00:00")),
    ("space-separated timestamp rejected", lambda r: r.__setitem__("occurred_at", "2026-08-08 21:00:00+00:00")),
    ("compact offset timestamp rejected", lambda r: r.__setitem__("occurred_at", "2026-08-08T21:00:00+0000")),
    ("oversized lane rejected", lambda r: r["source"].__setitem__("lane", "x" * 65)),
    ("non-string workflow id rejected", lambda r: r["source"].__setitem__("workflow_id", 7)),
    ("oversized evidence ref rejected", lambda r: r["evidence"][0].__setitem__("ref", "x" * 257)),
):
    invalid = copy.deepcopy(record)
    mutate(invalid)
    invalid["deviation_id"] = wd.deviation_id({k: v for k, v in invalid.items() if k != "deviation_id"})
    expect_error(label, invalid)

try:
    wd.classify("a" + "b" * 96)
except wd.DeviationContractError:
    print("PASS: schema-invalid reason length rejected")
else:
    raise AssertionError("schema-invalid reason length rejected")

print("PASS: workflow deviation C0 contract")
