#!/usr/bin/env python3
"""Hermetic contract tests for the H2A-P0B pure projection."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts" / "ai" / "lib" / "herdr_presentation_projection.py"
SCHEMA = ROOT / "config" / "schemas" / "herdr-presentation.schema.json"
LEDGER = ROOT / "config" / "herdr-presentation-source-to-field-ledger.v1.json"
FIXTURE = ROOT / "scripts" / "testing" / "fixtures" / "herdr-presentation-golden.json"
spec = importlib.util.spec_from_file_location("herdr_presentation_projection", MODULE)
assert spec and spec.loader
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)


class PresentationProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA.read_text())
        self.ledger = json.loads(LEDGER.read_text())
        fixture = json.loads(FIXTURE.read_text())
        self.vectors = fixture["vectors"]
        self.expected_sha256 = fixture["expected_sha256"]
        self.canonical_json = fixture["canonical_json"]
        self.negative_vectors = fixture["negative_vectors"]
        self.validator = Draft202012Validator(self.schema)

    @staticmethod
    def _coverage_oracle(value: dict) -> tuple[dict[str, int], int]:
        """Independent branch-table oracle for every emitted state-bearing leaf."""
        states = [item["state"] for item in value["source_health"]] + [
            value["configured"]["state"], value["runtime"]["state"],
            value["freshness"]["state"], value["reconciliation"]["state"],
            value["version"]["compatibility"], value["protocol"]["compatibility"],
            value["layout"]["observation_delta"],
            value["session"]["expected_count"]["state"],
            value["session"]["observed_count"]["state"],
            value["socket"]["state"], value["socket"]["presence"],
            value["socket"]["type"], value["socket"]["permission"],
            value["socket"]["peer"],
        ]
        states += [item["health"] for item in value["session"]["refs"]]
        states += [item["detach_state"] for item in value["session"]["refs"]]
        states += [item["health"] for item in value["panes"]]
        states += [item["freshness"] for item in value["panes"]]
        states += [item["observation_delta"] for item in value["panes"]]
        states += [item["state"] for item in value["counts"].values()]
        known = {"healthy", "known", "fresh", "enabled", "disabled", "degraded",
                 "compatible", "incompatible", "match", "mismatch", "pending",
                 "succeeded", "failed", "stale", "conflict", "reachable",
                 "unreachable", "present", "absent", "expected", "unexpected", "ok",
                 "denied", "attached", "detached"}
        return ({"known": sum(state in known for state in states),
                 "unknown": sum(state == "unknown" for state in states),
                 "unavailable": sum(state == "unavailable" for state in states),
                 "overflow": 0}, len(states))

    def test_schema_and_ledger_are_closed(self) -> None:
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], projection.SCHEMA_VERSION)
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(self.ledger["authority"], "read_only_presentation")
        self.assertIn("canonical_work_state", self.ledger["prohibitions"])
        self.assertEqual(set(self.schema["properties"]), {"schema_version", "observation_revision", "generated_at", "freshness", "source_health", "source_digests", "configured", "runtime", "socket", "session", "version", "protocol", "panes", "layout", "counts", "reconciliation", "coverage", "policy"})
        defs = self.schema["$defs"]
        def deref(node):
            return defs[node["$ref"].split("/")[-1]] if isinstance(node, dict) and "$ref" in node else node
        def leaves(node, prefix=()):
            node = deref(node)
            if "properties" in node:
                return {path for key, child in node["properties"].items() for path in leaves(child, prefix + (key,))}
            if "items" in node:
                return leaves(node["items"], prefix + ("[]",))
            return {".".join(prefix)}
        schema_paths = leaves(self.schema)
        ledger_paths = [row["path"] for row in self.ledger["rules"]]
        self.assertEqual(len(ledger_paths), len(set(ledger_paths)), "duplicate ledger leaf")
        self.assertEqual(schema_paths - set(ledger_paths), set())
        self.assertEqual(set(ledger_paths) - schema_paths, set())
        self.assertEqual(len(schema_paths), 82)
        self.assertEqual(self.ledger["normative_leaf_count"], 82)

    def test_golden_vectors_and_replay(self) -> None:
        for index, vector in enumerate(self.vectors):
            first = projection.project(vector["input"])
            second = projection.project(vector["input"])
            self.assertEqual(list(self.validator.iter_errors(first)), [], vector["name"])
            self.assertEqual(projection.canonical_bytes(first), projection.canonical_bytes(second), vector["name"])
            self.assertEqual(projection.projection_digest(first), projection.projection_digest(second), vector["name"])
            self.assertEqual(projection.projection_digest(first), self.expected_sha256[index], vector["name"])
            self.assertEqual(projection.canonical_bytes(first), self.canonical_json[index].encode("ascii"), vector["name"])
            expect = vector["expect"]
            self.assertEqual(first["source_health"][0]["authorization"], expect["source_authorization"])
            self.assertEqual(first["runtime"]["state"], expect["runtime_state"])
            self.assertEqual(first["counts"]["managed"]["state"], expect["known_count_state"])
            self.assertEqual(first["version"]["observed"], expect["observed_version"])

    def test_unauthorized_is_not_inferred_healthy(self) -> None:
        value = projection.project({"observation_revision":"r1", "generated_at":"bucket0", "static_expected":{"version":"0.7.5"}})
        self.assertEqual(value["runtime"]["state"], "unknown")
        self.assertEqual(value["counts"]["unknown"], {"state":"unknown", "value":None})
        self.assertEqual(value["version"]["expected"], "0.7.5")
        self.assertIsNone(value["version"]["observed"])

    def test_stale_and_conflict_remain_visible(self) -> None:
        for state in ("stale", "conflict"):
            value = projection.project({"observation_revision":"r1", "generated_at":"bucket0", "observer":{"id":"observer1", "authorization":"authorized", "state":state, "reason":"sample_" + state, "revision":"r1", "digest":"a" * 64}})
            self.assertEqual(value["source_health"][0]["state"], state)
            self.assertEqual(value["runtime"]["state"], "unknown")

    def test_complete_authorized_dimensions_and_sample_coherence(self) -> None:
        value = projection.project(self.vectors[1]["input"])
        for name in ("socket", "session", "version", "protocol", "panes", "layout", "reconciliation"):
            self.assertIn(name, value)
        self.assertTrue(value["observation_revision"].startswith("r1:sample1:"))
        self.assertEqual(value["policy"]["observer_policy_revision"], "p1")
        bad = dict(self.vectors[1]["input"])
        bad["sampled_at_bucket"] = "bucket2"
        with self.assertRaises(ValueError):
            projection.project(bad)

    def test_canonical_bytes_ignore_input_mapping_insertion_order(self) -> None:
        original = self.vectors[1]["input"]
        def reverse(value):
            if isinstance(value, dict): return {key: reverse(item) for key, item in reversed(list(value.items()))}
            if isinstance(value, list): return [reverse(item) for item in value]
            return value
        self.assertEqual(projection.canonical_bytes(projection.project(original)), projection.canonical_bytes(projection.project(reverse(original))))
        self.assertEqual(projection.projection_digest(projection.project(original)), projection.projection_digest(projection.project(reverse(original))))

    def test_coverage_accounts_for_every_visible_contract_dimension(self) -> None:
        """Keep coverage tied to the complete closed output, not selected tiles."""
        value = projection.project(self.vectors[1]["input"])
        expected, dimension_total = self._coverage_oracle(value)
        self.assertEqual(value["coverage"], expected)
        self.assertEqual(sum(value["coverage"].values()), dimension_total)

        targeted = json.loads(json.dumps(self.vectors[1]["input"]))
        targeted["observation"]["socket"]["peer"] = "unknown"
        changed = projection.project(targeted)
        self.assertEqual(changed["coverage"]["unknown"], value["coverage"]["unknown"] + 1)
        self.assertEqual(changed["coverage"]["known"], value["coverage"]["known"] - 1)
        self.assertEqual(changed["coverage"]["unavailable"], value["coverage"]["unavailable"])

    def test_coverage_reducer_is_total_over_every_return_class(self) -> None:
        missing_observation = json.loads(json.dumps(self.vectors[1]["input"]))
        missing_observation.pop("observation")
        branches = {
            "no_adapter": self.vectors[0]["input"],
            "unauthorized": self.vectors[2]["input"],
            "stale": self.vectors[3]["input"],
            "conflict": self.vectors[4]["input"],
            "missing_observation": missing_observation,
            "authorized_known": self.vectors[1]["input"],
        }
        for name, envelope in branches.items():
            with self.subTest(branch=name):
                value = projection.project(envelope)
                expected, dimension_total = self._coverage_oracle(value)
                self.assertEqual(value["coverage"], expected)
                self.assertEqual(sum(value["coverage"].values()), dimension_total)
                self.assertEqual(list(self.validator.iter_errors(value)), [])

    def test_rejects_injection_and_adapter_dimensions(self) -> None:
        with self.assertRaises(ValueError):
            projection.project({"observation_revision":"r1;rm", "generated_at":"bucket0"})
        with self.assertRaises(ValueError):
            projection.project({"observation_revision":"r1", "generated_at":"bucket0", "observer":{"id":"observer1","authorization":"authorized","state":"known","reason":"ok","revision":"r1","digest":"a" * 64}, "observation":{"socket":{"raw":"/tmp/socket;rm"}}})
        with self.assertRaises(ValueError):
            projection.project({"observation_revision":"r1", "generated_at":"bucket0", "observer":{"id":"observer1","authorization":"authorized","state":"known","reason":"ok","revision":"r1","digest":"a" * 64}, "observation":{"counts":{"managed":{"state":"stale","value":0}}}})

    def test_schema_rejects_count_pairing_and_required_reference_null(self) -> None:
        value = projection.project(self.vectors[0]["input"])
        value["counts"]["managed"] = {"state":"known", "value":None}
        self.assertTrue(list(self.validator.iter_errors(value)))

    def test_observation_cannot_supply_static_expected_or_unsafe_identifiers(self) -> None:
        base = self.vectors[1]["input"]
        for dimension, member in (("version", "expected"), ("protocol", "expected"), ("layout", "expected_revision"), ("session", "expected_count")):
            candidate = json.loads(json.dumps(base))
            candidate["observation"][dimension][member] = "injected" if member != "expected_count" else {"state":"known","value":1}
            with self.assertRaises(ValueError):
                projection.project(candidate)
        candidate = json.loads(json.dumps(base))
        candidate["observation"]["socket"]["peer"] = "reachable;curl"
        with self.assertRaises(ValueError):
            projection.project(candidate)

    def test_fail_closed_lifecycle_bounds_and_privacy_inputs(self) -> None:
        base = self.vectors[1]["input"]
        for bad in ("issuer_unknown", "reference_revoked", "reference_expired", "reference_superseded", "reference_cycle"):
            candidate = json.loads(json.dumps(base))
            candidate["observer"]["reason"] = bad
            # Lifecycle cannot be represented by Contract #5 normalized facts; raw claim is rejected.
            candidate["observation"]["lifecycle"] = bad
            with self.assertRaises(ValueError): projection.project(candidate)
        for bad in ("a" * 129, "secret=abcd", "../socket", "x;curl", "line\nfeed", "nul\u0000byte"):
            candidate = json.loads(json.dumps(base)); candidate["observer"]["id"] = bad
            with self.assertRaises(ValueError): projection.project(candidate)
        candidate = json.loads(json.dumps(base)); candidate["observation"]["panes"] = []
        for _ in range(65): candidate["observation"]["panes"].append({"pane_ref":"aqref:v1:pane:abcdefghijklmnopqrstuv","role":"r","work_ref":None,"health":"healthy","freshness":"fresh","observed_state":None,"observation_delta":"match"})
        with self.assertRaises(ValueError): projection.project(candidate)

    def test_closed_reference_binding_registry_rejects_collisions_and_lifecycle(self) -> None:
        base = json.loads(json.dumps(self.vectors[1]["input"]))
        ref = "aqref:v1:pane:abcdefghijklmnopqrstuv"
        binding = {"ref":ref,"issuer_revision":"i1","subject_digest":"a" * 64,"state":"active","expiry_bucket":"future","replacement_ref":None,"replacement_subject_digest":None}
        base["reference_bindings"] = [binding]
        first = projection.project(base)
        self.assertIn(":", first["observation_revision"])
        collision = json.loads(json.dumps(base)); collision["reference_bindings"].append({**binding,"subject_digest":"b" * 64})
        with self.assertRaises(ValueError): projection.project(collision)
        revoked = json.loads(json.dumps(base)); revoked["reference_bindings"][0]["state"]="revoked"
        # A raw lifecycle registry is validated but cannot become presentation truth on its own.
        self.assertIsNotNone(projection.project(revoked))
        bad = json.loads(json.dumps(base)); bad["reference_bindings"][0]["state"]="superseded"
        with self.assertRaises(ValueError): projection.project(bad)

    def test_reference_replacement_target_and_expiry_probes(self) -> None:
        for vector in self.negative_vectors:
            expected = "reference_supersession_cycle" if vector["name"] == "two_node_cycle" else "reference_"
            with self.assertRaisesRegex(ValueError, expected, msg=vector["name"]):
                projection.project(vector["input"])
        base = json.loads(json.dumps(self.vectors[1]["input"])); ref="aqref:v1:pane:abcdefghijklmnopqrstuv"
        active={"ref":ref,"issuer_revision":"i1","subject_digest":"a"*64,"state":"active","expiry_bucket":"future","replacement_ref":None,"replacement_subject_digest":None}
        superseded={"ref":"aqref:v1:pane:zyxwvutsrqponmlkjihgfedc","issuer_revision":"i1","subject_digest":"a"*64,"state":"superseded","expiry_bucket":"future","replacement_ref":ref,"replacement_subject_digest":"a"*64}
        base["reference_bindings"]=[active,superseded]
        self.assertIsNotNone(projection.project(base))
        for mutate in (lambda x: x[1].update(replacement_subject_digest="b"*64), lambda x: x[0].update(expiry_bucket="../expired"), lambda x: x[0].update(issuer_revision="unknown")):
            candidate=json.loads(json.dumps(base)); mutate(candidate["reference_bindings"])
            with self.assertRaises(ValueError): projection.project(candidate)
        value = projection.project(self.vectors[0]["input"])
        value["session"]["refs"] = [{"session_ref":None,"health":"healthy","detach_state":"attached"}]
        self.assertTrue(list(self.validator.iter_errors(value)))


if __name__ == "__main__":
    unittest.main()
