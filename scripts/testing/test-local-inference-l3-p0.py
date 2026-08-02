#!/usr/bin/env python3
"""Static + subtest contract suite for the L3-P0 local-inference provenance/shadow kernel
(scripts/ai/lib/local_inference_provenance.py): exact fact vocabulary, digest-only trust
envelope, shadow-observation schema conformance, and golden-fixture parity."""
import ast
import copy
import importlib.util
import json
import pathlib
import unittest

import jsonschema


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/ai/lib/local_inference_provenance.py"
FIXTURE_PATH = ROOT / "scripts/testing/fixtures/local-inference-l3-p0-golden.json"
SCHEMA_ROOT = ROOT / "config/schemas"
SCHEMAS = {
    "fact": "local-inference-trusted-fact-envelope-v1.schema.json",
    "revisions": "local-inference-producer-revision-set-v1.schema.json",
    "request": "local-inference-shadow-request-projection-v1.schema.json",
    "plan": "local-inference-resolved-shadow-plan-v1.schema.json",
    "metadata": "local-inference-shadow-observation-metadata-v1.schema.json",
    "observation": "local-inference-shadow-observation-v1.schema.json",
    "unavailable": "local-inference-trusted-fact-unavailable-v1.schema.json",
}
spec = importlib.util.spec_from_file_location("local_inference_provenance", MODULE_PATH)
kernel = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(kernel)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_recursively_closed(testcase, node, location="$"):
    if not isinstance(node, dict):
        return
    if node.get("type") == "object" or "properties" in node:
        testcase.assertIs(node.get("additionalProperties"), False, location)
    for key in ("properties", "$defs", "patternProperties"):
        for name, child in node.get(key, {}).items():
            assert_recursively_closed(testcase, child, location + "/" + key + "/" + name)
    if isinstance(node.get("items"), dict):
        assert_recursively_closed(testcase, node["items"], location + "/items")
    for key in ("allOf", "anyOf", "oneOf"):
        for index, child in enumerate(node.get(key, [])):
            assert_recursively_closed(testcase, child, f"{location}/{key}/{index}")


class L3P0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_json(FIXTURE_PATH)
        cls.schemas = {name: load_json(SCHEMA_ROOT / path) for name, path in SCHEMAS.items()}

    def setUp(self):
        self.facts = copy.deepcopy(self.fixture["facts"])
        self.revisions = copy.deepcopy(self.fixture["producer_revision_set"])
        self.request = copy.deepcopy(self.fixture["request_projection"])
        self.metadata = copy.deepcopy(self.fixture["observation_metadata"])

    def plan(self):
        return kernel.resolve_shadow_plan(self.facts, self.request, self.revisions)

    def observation(self, plan=None, metadata=None, legacy=None):
        return kernel.build_shadow_observation(
            metadata or self.metadata, plan or self.plan(),
            legacy or self.fixture["legacy_observation_digest"])

    def test_all_schemas_are_valid_recursively_closed_draft_2020_12(self):
        for name, schema in self.schemas.items():
            jsonschema.Draft202012Validator.check_schema(schema)
            assert_recursively_closed(self, schema, name)

    def test_every_success_shape_validates(self):
        for fact in self.facts:
            jsonschema.validate(fact, self.schemas["fact"], cls=jsonschema.Draft202012Validator)
        jsonschema.validate(self.revisions, self.schemas["revisions"], cls=jsonschema.Draft202012Validator)
        jsonschema.validate(self.request, self.schemas["request"], cls=jsonschema.Draft202012Validator)
        jsonschema.validate(self.metadata, self.schemas["metadata"], cls=jsonschema.Draft202012Validator)
        plan = self.plan()
        observation = self.observation(plan)
        jsonschema.validate(plan, self.schemas["plan"], cls=jsonschema.Draft202012Validator)
        jsonschema.validate(observation, self.schemas["observation"], cls=jsonschema.Draft202012Validator)
        self.assertTrue(plan["shadow"] and plan["non_authoritative"] and plan["no_live_cutover"])
        self.assertTrue(observation["shadow"] and observation["non_authoritative"] and observation["no_live_cutover"])

    def test_digest_only_fact_contract_rejects_raw_values_and_capabilities(self):
        forbidden = ("value", "task", "route", "grant", "tool", "cli", "environment",
                     "provider", "endpoint", "process", "network", "filesystem", "persistence")
        for field in forbidden:
            candidate = copy.deepcopy(self.facts[0])
            candidate[field] = {"authority": True}
            with self.subTest(field=field), self.assertRaises(kernel.ProvenanceError):
                kernel.validate_trusted_fact(candidate)
        self.assertNotIn("value", self.schemas["fact"]["properties"])
        self.assertIn("value_digest", self.schemas["fact"]["required"])

    def test_required_fact_type_vocabulary_is_exact(self):
        self.assertEqual(kernel.REQUIRED_FACT_TYPES, (
            "authenticated_principal", "role", "approval_or_lease", "profile",
            "eligibility", "budget", "path", "clock"))
        candidate = copy.deepcopy(self.facts[1])
        candidate["fact_type"] = "role_authorization"
        with self.assertRaises(kernel.ProvenanceError):
            kernel.validate_trusted_fact(candidate)

    def test_producer_revision_set_is_required_unique_sorted_and_exact(self):
        with self.assertRaises(TypeError):
            kernel.resolve_shadow_plan(self.facts, self.request)
        variants = []
        missing = copy.deepcopy(self.revisions); missing["producers"].pop(); variants.append(missing)
        stale = copy.deepcopy(self.revisions); stale["producers"][0]["revision"] = "stale"; variants.append(stale)
        duplicate = copy.deepcopy(self.revisions); duplicate["producers"][-1] = duplicate["producers"][0]; variants.append(duplicate)
        unordered = copy.deepcopy(self.revisions); unordered["producers"].reverse(); variants.append(unordered)
        for candidate in variants:
            with self.subTest(candidate=candidate), self.assertRaises(kernel.ProvenanceError):
                kernel.resolve_shadow_plan(self.facts, self.request, candidate)

    def test_canonical_json_is_nfc_utf8_sorted_and_nonfinite_closed(self):
        decomposed = {"z": "e\u0301", "a": {"y": 2, "x": 1}}
        composed = {"a": {"x": 1, "y": 2}, "z": "é"}
        self.assertEqual(kernel.canonical_json_bytes(decomposed), kernel.canonical_json_bytes(composed))
        self.assertEqual(kernel.canonical_digest(decomposed), kernel.canonical_digest(composed))
        self.assertIn("é".encode(), kernel.canonical_json_bytes(decomposed))
        for value in (float("nan"), float("inf"), {"x": object()}):
            with self.assertRaises(kernel.ProvenanceError):
                kernel.canonical_digest(value)
        with self.assertRaises(kernel.ProvenanceError):
            kernel.parse_json_strict('{"x":1,"x":2}')
        with self.assertRaises(kernel.ProvenanceError):
            kernel.parse_json_strict('{"é":1,"e\\u0301":2}')

    def test_digest_references_are_lower_hex_and_mutation_sensitive(self):
        for mutate in ("value_digest", "producer_revision", "evidence_ref"):
            facts = copy.deepcopy(self.facts)
            if mutate == "value_digest": facts[0][mutate] = "9" * 64
            else: facts[0][mutate] += "-changed"
            revisions = copy.deepcopy(self.revisions)
            if mutate == "producer_revision": revisions["producers"][0]["revision"] += "-changed"
            changed = kernel.resolve_shadow_plan(facts, self.request, revisions)
            baseline = self.plan()
            self.assertNotEqual(changed["provenance_vector_digest"], baseline["provenance_vector_digest"])
        for bad in ("", "A" * 64, "0" * 63, "g" * 64):
            candidate = copy.deepcopy(self.facts[0]); candidate["value_digest"] = bad
            with self.assertRaises(kernel.ProvenanceError): kernel.validate_trusted_fact(candidate)

    def test_projection_and_revision_mutations_change_bound_digests(self):
        baseline = self.plan()
        changed_request = copy.deepcopy(self.request); changed_request["request_ref"] += ":changed"
        request_plan = kernel.resolve_shadow_plan(self.facts, changed_request, self.revisions)
        self.assertNotEqual(request_plan["request_projection_digest"], baseline["request_projection_digest"])
        changed_revisions = copy.deepcopy(self.revisions)
        changed_facts = copy.deepcopy(self.facts)
        changed_revisions["producers"][0]["revision"] = "rev-2"
        changed_facts[0]["producer_revision"] = "rev-2"
        revision_plan = kernel.resolve_shadow_plan(changed_facts, self.request, changed_revisions)
        self.assertNotEqual(revision_plan["producer_revision_set_digest"], baseline["producer_revision_set_digest"])

    def test_unavailable_is_internal_typed_and_schema_valid(self):
        self.assertFalse(hasattr(kernel, "trusted_fact_unavailable"))
        missing = kernel.resolve_shadow_plan(self.facts[:-1], self.request, self.revisions)
        self.assertEqual((missing["failing_fact_type"], missing["category"]), ("clock", "missing"))
        unavailable_facts = copy.deepcopy(self.facts); unavailable_facts[5]["status"] = "unavailable"
        unavailable = kernel.resolve_shadow_plan(unavailable_facts, self.request, self.revisions)
        self.assertEqual((unavailable["failing_fact_type"], unavailable["category"]), ("budget", "producer_unavailable"))
        for result in (missing, unavailable):
            jsonschema.validate(result, self.schemas["unavailable"], cls=jsonschema.Draft202012Validator)
            self.assertNotIn("decision", result)
        with self.assertRaises(kernel.ProvenanceError):
            kernel._trusted_fact_unavailable("budget", "caller_failure", "x")

    def test_observation_is_complete_digest_bound_and_metadata_sensitive(self):
        plan = self.plan()
        baseline = self.observation(plan)
        body = dict(baseline); digest = body.pop("observation_digest")
        self.assertEqual(digest, kernel.canonical_digest(body))
        self.assertEqual(baseline["resolved_plan_digest"], kernel.canonical_digest(plan))
        for field, value in (("observation_id", "other"), ("shadow_sequence", 8),
                             ("observed_at", "2026-08-01T00:00:01Z"), ("trace_ref", "trace:other")):
            metadata = copy.deepcopy(self.metadata); metadata[field] = value
            changed = self.observation(plan, metadata=metadata)
            self.assertNotEqual(changed["observation_digest"], baseline["observation_digest"])
            self.assertEqual(changed["resolved_plan_digest"], baseline["resolved_plan_digest"])
        changed_legacy = self.observation(plan, legacy="c" * 64)
        self.assertNotEqual(changed_legacy["observation_digest"], baseline["observation_digest"])
        changed_plan = copy.deepcopy(plan); changed_plan["request_projection_digest"] = "d" * 64
        changed = self.observation(changed_plan)
        self.assertNotEqual(changed["resolved_plan_digest"], baseline["resolved_plan_digest"])

    def test_unknown_and_missing_observation_fields_are_rejected(self):
        metadata = copy.deepcopy(self.metadata); metadata["provider"] = "forbidden"
        with self.assertRaises(kernel.ProvenanceError): self.observation(metadata=metadata)
        metadata = copy.deepcopy(self.metadata); metadata.pop("trace_ref")
        with self.assertRaises(kernel.ProvenanceError): self.observation(metadata=metadata)
        observation = self.observation(); observation["route"] = "forbidden"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(observation, self.schemas["observation"], cls=jsonschema.Draft202012Validator)

    def test_resolved_plan_rejects_digest_and_provenance_tampering(self):
        plan = self.plan(); plan["provenance_refs"][0]["value_digest"] = "f" * 64
        with self.assertRaises(kernel.ProvenanceError): kernel.validate_resolved_plan(plan)
        plan = self.plan(); plan.pop("producer_revision_set_digest")
        with self.assertRaises(kernel.ProvenanceError): kernel.validate_resolved_plan(plan)

    def test_source_is_pure_and_fixture_location_is_authorized(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        self.assertEqual(imported, {"__future__", "hashlib", "json", "unicodedata", "typing"})
        self.assertTrue(FIXTURE_PATH.is_file())
        self.assertFalse((ROOT / "config/testing/local-inference-l3-p0-golden.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
