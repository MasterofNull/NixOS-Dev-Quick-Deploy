#!/usr/bin/env python3
"""Hermetic H2A-P0 contract oracle: closure, samples, vectors, and purity."""
from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
schema = json.loads((ROOT / "config/schemas/operator-context.schema.json").read_text())
ledger = json.loads((ROOT / "config/operator-context-source-to-field-ledger.v1.json").read_text())
fixture = json.loads((ROOT / "scripts/testing/fixtures/operator-context-golden.json").read_text())
module_path = ROOT / "scripts/ai/lib/operator_context_projection.py"
spec = importlib.util.spec_from_file_location("projection", module_path)
assert spec and spec.loader
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)

assert schema["$id"] == ledger["projection_schema"] == "aq.operator-context.v1"

def leaves(node: dict, prefix: str = "") -> set[str]:
    if "$ref" in node:
        return leaves(schema["$defs"][node["$ref"].split("/")[-1]], prefix)
    if "anyOf" in node:
        return set().union(*(leaves(choice, prefix) for choice in node["anyOf"]))
    if node.get("type") == "object":
        assert node.get("additionalProperties") is False
        return set().union(*(leaves(value, f"{prefix}.{key}" if prefix else key) for key, value in node["properties"].items()))
    if node.get("type") == "array" and "items" in node:
        assert node.get("maxItems", 65) <= 64
        return leaves(node["items"], prefix + "[]")
    return {prefix}

ledger_paths = [row["path"] for row in ledger["leaves"]]
assert len(ledger_paths) == len(set(ledger_paths))
assert leaves(schema) == set(ledger_paths)
allowed_sources = {"projection_meta_facts", "program_workflow_facts", "exclusive_lease_facts", "independent_review_facts", "agent_progress_facts", "canonical_attention_facts", "learning_facts", "pure.v2"}
for row in ledger["leaves"]:
    assert set(row) == {"path", "source", "rule"}
    assert row["source"] in allowed_sources

def validate(value: object, node: dict) -> None:
    if "$ref" in node:
        validate(value, schema["$defs"][node["$ref"].split("/")[-1]]); return
    if "anyOf" in node:
        for branch in node["anyOf"]:
            try: validate(value, branch); return
            except AssertionError: pass
        raise AssertionError("anyOf")
    if "allOf" in node:
        for branch in node["allOf"]: validate(value, branch)
    if "if" in node:
        try:
            validate(value, node["if"])
        except AssertionError:
            if "else" in node: validate(value, node["else"])
        else:
            if "then" in node: validate(value, node["then"])
    if "const" in node: assert value == node["const"]; return
    if "enum" in node: assert value in node["enum"]; return
    kind = node.get("type", "object" if "properties" in node else None)
    if kind == "object":
        assert isinstance(value, dict)
        if node.get("additionalProperties") is False:
            assert set(value) == set(node["properties"])
        else:
            assert set(node.get("required", ())).issubset(value)
        for key, child in node["properties"].items(): validate(value[key], child)
    elif kind == "array":
        assert isinstance(value, list) and len(value) <= node.get("maxItems", len(value))
        for item in value: validate(item, node["items"])
    elif kind == "string":
        assert isinstance(value, str) and len(value) >= node.get("minLength", 0) and len(value) <= node.get("maxLength", len(value))
        if "pattern" in node: assert re.fullmatch(node["pattern"], value)
    elif kind == "integer": assert isinstance(value, int) and not isinstance(value, bool) and node.get("minimum", value) <= value <= node.get("maximum", value)
    elif kind == "null": assert value is None

vectors = {item["id"]: item for item in fixture["vectors"]}
for vector in vectors.values():
    payload, output_bytes, digest = projection.project(vector["facts"])
    input_bytes = projection.canonical_bytes(vector["facts"])
    assert input_bytes.decode("utf-8") == vector["input_bytes"]
    assert projection.sha256_hex(vector["facts"]) == vector["input_sha256"]
    assert payload["policy"]["input_digest"] == projection.sha256_hex(vector["facts"])
    assert digest == projection.sha256_hex(payload) and output_bytes == projection.canonical_bytes(payload)
    assert output_bytes.decode("utf-8") == vector["expected"]["output_bytes"]
    assert digest == vector["expected"]["output_sha256"]
    validate(payload, schema)
fresh = vectors["all-fresh-r1-r7"]
payload, _, _ = projection.project(fresh["facts"])
assert payload["freshness"]["state"] == "fresh" and payload["coverage"]["known_sources"]["value"] == 6
assert payload["work"][0]["canonical_state"] == "needs_review"
assert payload["work"][0]["interaction_mode"] == "through_parent" and payload["work"][0]["progress_age"] == "recent"
assert payload["attention"][0]["recommended_action"] == "request_review" and payload["work"][0]["allowed_controls"] == []
assert payload["learning"]["accepted_count"] == {"state":"unknown","value":None}
unavailable, _, _ = projection.project(vectors["unavailable-explicit-counts"]["facts"])
assert unavailable["freshness"]["state"] == "unavailable"
assert unavailable["mission"]["definition_of_done"]["total"] == {"state":"unknown","value":None}
assert unavailable["learning"]["accepted_count"] == {"state":"unavailable","value":None}

# Canonical bytes bind semantic content, not insertion order.
def reversed_mappings(value):
    if isinstance(value, dict): return {key: reversed_mappings(value[key]) for key in reversed(list(value))}
    if isinstance(value, list): return [reversed_mappings(item) for item in value]
    return value
assert projection.project(reversed_mappings(fresh["facts"]))[1:] == projection.project(fresh["facts"])[1:]

# Draft 2020 conditional count contract: known is numeric; nonknown is null.
bad_count = copy.deepcopy(payload); bad_count["coverage"]["known_sources"] = {"state":"known","value":None}
try: validate(bad_count, schema)
except AssertionError: pass
else: raise AssertionError("known-null count accepted")
bad_count = copy.deepcopy(payload); bad_count["coverage"]["known_sources"] = {"state":"unknown","value":0}
try: validate(bad_count, schema)
except AssertionError: pass
else: raise AssertionError("unknown-numeric count accepted")

def rejects(mutator) -> None:
    facts = copy.deepcopy(fresh["facts"]); mutator(facts)
    try: projection.project(facts)
    except projection.ProjectionError as error:
        # Errors are stable bounded identifiers, never reflected payload text.
        assert re.fullmatch(r"[a-z0-9_]{1,96}", str(error))
        return
    raise AssertionError("mutation accepted")

rejects(lambda f: f.__setitem__("raw_prompt", "secret"))
rejects(lambda f: f["exclusive_lease_facts"].__setitem__("sample_id", "sample-x"))
rejects(lambda f: f["exclusive_lease_facts"].__setitem__("sampled_at_bucket", "b20"))
rejects(lambda f: f["exclusive_lease_facts"].update(adapter_revision="adapter-program", digest=f["program_workflow_facts"]["digest"]))
rejects(lambda f: f["exclusive_lease_facts"].__setitem__("digest", f["program_workflow_facts"]["digest"]))
rejects(lambda f: f["program_workflow_facts"].__setitem__("reference_status", "revoked"))
rejects(lambda f: f["program_workflow_facts"].__setitem__("reference_status", "expired"))
rejects(lambda f: f["program_workflow_facts"].__setitem__("reference_status", "superseded"))
rejects(lambda f: f["program_workflow_facts"].__setitem__("issuer", "unknown"))
rejects(lambda f: f["program_workflow_facts"].__setitem__("supersedes", "aqref:v1:task:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"))
rejects(lambda f: f["program_workflow_facts"]["work"].append(copy.deepcopy(f["program_workflow_facts"]["work"][0])))
rejects(lambda f: f["program_workflow_facts"].__setitem__("work", [copy.deepcopy(f["program_workflow_facts"]["work"][0]) for _ in range(65)]))
rejects(lambda f: f["program_workflow_facts"]["mission"].__setitem__("objective", "/run/secrets/key"))
rejects(lambda f: f["program_workflow_facts"]["mission"].__setitem__("objective", "x" * 161))
rejects(lambda f: f["program_workflow_facts"]["mission"].__setitem__("objective", "bad\ntext"))
rejects(lambda f: f["program_workflow_facts"]["mission"].__setitem__("total", {"state":"known","value":-1}))
# Lifecycle registry: a valid replacement is permitted; only bad bindings and
# directed cycles fail.  Failure text is bounded and never echoes the input.
replaced = copy.deepcopy(fresh["facts"])
old = replaced["program_workflow_facts"]
old.update(state="unavailable", reference_status="superseded", replacement_ref="aqref:v1:replacement:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", replacement_subject_digest=replaced["exclusive_lease_facts"]["subject_digest"], supersession_chain=[replaced["exclusive_lease_facts"]["subject_digest"]])
superseded_payload, _, _ = projection.project(replaced)
assert superseded_payload["freshness"]["state"] != "fresh" and superseded_payload["mission"]["objective"] == "unknown"
cycle = copy.deepcopy(fresh["facts"])
for left, right in (("program_workflow_facts", "exclusive_lease_facts"), ("exclusive_lease_facts", "program_workflow_facts")):
    cycle[left].update(state="unavailable", reference_status="superseded", replacement_ref="aqref:v1:replacement:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", replacement_subject_digest=cycle[right]["subject_digest"], supersession_chain=[cycle[right]["subject_digest"], cycle[left]["subject_digest"]])
try: projection.project(cycle)
except projection.ProjectionError as error: assert str(error) == "supersession_cycle"
else: raise AssertionError("actual supersession cycle accepted")
for mutate in (
    lambda f: f["program_workflow_facts"].__setitem__("expires_at_bucket", "b1"),
    lambda f: f["program_workflow_facts"].__setitem__("issuer_revision", "unknown"),
    lambda f: f["program_workflow_facts"].__setitem__("subject_digest", f["exclusive_lease_facts"]["subject_digest"]),
    lambda f: f["program_workflow_facts"].update(reference_status="superseded", replacement_ref="aqref:v1:replacement:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", replacement_subject_digest=f["program_workflow_facts"]["subject_digest"]),
): rejects(mutate)
for rejection in fixture["rejections"]:
    assert set(rejection) == {"id", "path", "value"}
    facts = copy.deepcopy(fresh["facts"]); cursor = facts
    parts = rejection["path"].split(".")
    for part in parts[:-1]: cursor = cursor[int(part)] if part.isdigit() else cursor[part]
    leaf = parts[-1]
    if leaf == "__extra__": cursor[rejection["value"]["key"]] = rejection["value"]["value"]
    else: cursor[int(leaf) if leaf.isdigit() else leaf] = rejection["value"]
    try: projection.project(facts)
    except projection.ProjectionError as error:
        assert re.fullmatch(r"[a-z0-9_]{1,96}", str(error))
        if rejection["id"] in {"shell_fragment", "shell_semicolon", "command_filesystem", "command_interpreter", "command_privilege", "command_service", "command_build", "command_cargo", "command_terraform", "command_signal"}:
            assert rejection["value"] not in str(error)
        continue
    raise AssertionError(f"literal rejection accepted: {rejection['id']}")
for objective in fixture["positive_objectives"]:
    facts = copy.deepcopy(fresh["facts"])
    facts["program_workflow_facts"]["mission"]["objective"] = objective
    assert projection.project(facts)[0]["mission"]["objective"] == objective
for state, expected in (("stale", "degraded"), ("conflict", "conflict"), ("unavailable", "unknown")):
    changed = copy.deepcopy(fresh["facts"]); changed["agent_progress_facts"]["state"] = state
    got, _, _ = projection.project(changed)
    assert got["freshness"]["state"] == expected

source = module_path.read_text().lower()
for forbidden in ("open(", "os.environ", "subprocess", "socket", "requests", "time.", "pathlib", "import herdr"):
    assert forbidden not in source
print("operator-context-projection: PASS")
