#!/usr/bin/env python3
"""test-network-dns-policy.py — offline vector/oracle test suite for N0 pure resolver contract.

Tests:
  1. Forbidden module import assertion: verifies subprocess, socket, requests, urllib, dbus, NetworkManager
     are NEVER imported by network_dns_policy.
  2. Draft 2020-12 schema validation for input, eligibility, decision, and health schemas.
  3. Rejection of extra keys and non-enums.
  4. Sole permit tuple verification (only link_kind=wifi ∧ connection_class=trusted_full ∧
     connectivity=full ∧ dns_topology=ordinary ∧ evidence_age_bucket=fresh -> eligible=true).
  5. Deny vectors (portal, limited, site, split, stale, non-wifi, untrusted, unknown).
  6. Malformed input fail-closed vectors.
  7. Transition resolution vectors (clean admit, idempotent refresh, downgrade, link_down,
     watchdog expiry, restart recovery, crash recovery, legacy mode).
  8. Deterministic pure interleaving sequences (apply -> downgrade, apply -> duplicate apply, etc.).
  9. Telemetry sanitizer verification (scrubbing UUIDs, MACs, IPv4, IPv6, domains, hex digests, sensitive keys).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import jsonschema

# Locate repo root relative to this test file
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

FORBIDDEN_MODULES = [
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "dbus",
    "NetworkManager",
]


class TestNetworkDnsPolicyN0(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Verify forbidden modules are NOT imported prior to loading network_dns_policy
        for mod in FORBIDDEN_MODULES:
            if mod in sys.modules:
                del sys.modules[mod]

        # Import the pure module under test
        import scripts.ai.lib.network_dns_policy as ndp
        cls.ndp = ndp

        # 2. Assert forbidden modules are STILL NOT imported
        for mod in FORBIDDEN_MODULES:
            assert mod not in sys.modules, f"Forbidden module '{mod}' was imported by network_dns_policy!"

        # Load schema
        schema_path = _REPO / "config" / "network-dns-policy.schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            cls.schema_doc = json.load(f)

        # Build schema validators
        # Build schema validators with local $defs
        defs = cls.schema_doc["$defs"]
        cls.validator_root = jsonschema.Draft202012Validator(cls.schema_doc)

        cls.validator_input = jsonschema.Draft202012Validator({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": defs,
            "$ref": "#/$defs/policyInput",
        })
        cls.validator_eligibility = jsonschema.Draft202012Validator({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": defs,
            "$ref": "#/$defs/policyEligibility",
        })
        cls.validator_decision = jsonschema.Draft202012Validator({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": defs,
            "$ref": "#/$defs/policyDecision",
        })
        cls.validator_health = jsonschema.Draft202012Validator({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": defs,
            "$ref": "#/$defs/policyHealth",
        })

        # Load test vectors
        vectors_path = _REPO / "scripts" / "testing" / "fixtures" / "network-dns-policy-vectors.json"
        with open(vectors_path, "r", encoding="utf-8") as f:
            cls.vectors = json.load(f)

    def test_forbidden_imports(self):
        """Re-verify that forbidden modules are absent from sys.modules."""
        for mod in FORBIDDEN_MODULES:
            self.assertNotIn(mod, sys.modules, f"Forbidden module '{mod}' found in sys.modules")

    def test_schema_constants(self):
        """Verify protocol constants match schema declarations."""
        schema_constants = self.schema_doc.get("constants", {})
        self.assertEqual(schema_constants.get("receipt_lease_duration_s"), 55)
        self.assertEqual(schema_constants.get("max_effect_ceiling_s"), 90)
        self.assertEqual(self.ndp.RECEIPT_LEASE_DURATION_S, 55)
        self.assertEqual(self.ndp.MAX_EFFECT_CEILING_S, 90)

    def test_permit_vector(self):
        """Verify sole permit tuple yields eligible=true, lease_duration_s=55."""
        pvec = self.vectors["permit_vector"]
        inp = pvec["input"]
        expected = pvec["expected_eligibility"]

        # Validate input against schema
        ok, msg = self.ndp.validate_input(inp)
        self.assertTrue(ok, f"validate_input failed: {msg}")

        # Resolve eligibility
        result = self.ndp.resolve_eligibility(inp)
        self.assertEqual(result, expected)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "trusted_full")
        self.assertEqual(result["lease_duration_s"], 55)

        # Validate result against schema
        self.validator_eligibility.validate(result)

    def test_deny_vectors(self):
        """Verify all non-permit combinations fail closed with eligible=false and appropriate reason."""
        for dvec in self.vectors["deny_vectors"]:
            name = dvec["name"]
            inp = dvec["input"]
            expected = dvec["expected_eligibility"]

            with self.subTest(vector_name=name):
                # Validate input matches schema
                ok, msg = self.ndp.validate_input(inp)
                self.assertTrue(ok, f"validate_input failed for {name}: {msg}")

                # Resolve eligibility
                result = self.ndp.resolve_eligibility(inp)
                self.assertEqual(result, expected)
                self.assertFalse(result["eligible"])
                self.assertEqual(result["lease_duration_s"], 0)
                self.assertEqual(result["reason"], expected["reason"])

                # Validate result against schema
                self.validator_eligibility.validate(result)

    def test_malformed_vectors_fail_closed(self):
        """Verify malformed, extra-keyed, or non-dict inputs fail closed safely."""
        for mvec in self.vectors["malformed_vectors"]:
            name = mvec["name"]
            inp = mvec["input"]
            expected = mvec["expected_eligibility"]

            with self.subTest(vector_name=name):
                # Pure validator should reject
                ok, msg = self.ndp.validate_input(inp)
                self.assertFalse(ok, f"Expected validate_input to fail for {name}")

                # Resolver should fail closed to unknown_state
                result = self.ndp.resolve_eligibility(inp)
                self.assertEqual(result, expected)
                self.assertFalse(result["eligible"])
                self.assertEqual(result["reason"], "unknown_state")
                self.assertEqual(result["lease_duration_s"], 0)

                # Validate result against schema
                self.validator_eligibility.validate(result)

    def test_transition_vectors(self):
        """Verify pure transition resolution matches expected decisions and validates against schema."""
        for tvec in self.vectors["transition_vectors"]:
            name = tvec["name"]
            eligibility = tvec["eligibility"]
            executor_state = tvec["executor_state"]
            expected = tvec["expected_decision"]

            with self.subTest(transition_name=name):
                decision = self.ndp.resolve_transition(eligibility, executor_state)
                self.assertEqual(decision, expected)

                # Validate decision schema with jsonschema Draft202012
                self.validator_decision.validate(decision)
                ok, msg = self.ndp.validate_decision(decision)
                self.assertTrue(ok, f"Internal validate_decision failed: {msg}")

    def test_pure_interleaving_sequences(self):
        """Test deterministic interleaving sequences."""
        # Sequence 1: Clean admit -> apply_public_override; then downgrade -> revert_override
        elig_permit = self.ndp.resolve_eligibility(self.vectors["permit_vector"]["input"])
        state_init = {
            "prior_effect": "none",
            "receipt_state": "missing",
            "event": "admit",
            "mode": "policy",
        }
        dec1 = self.ndp.resolve_transition(elig_permit, state_init)
        self.assertEqual(dec1["action"], "apply_public_override")
        self.assertTrue(dec1["rollback_required"])
        self.assertEqual(dec1["lease_ttl_s"], 55)

        # After apply succeeds, simulated executor state is active_override + active_fresh
        state_active = {
            "prior_effect": "active_override",
            "receipt_state": "active_fresh",
            "event": "downgrade",
            "mode": "policy",
        }
        elig_downgrade = {"schema_version": self.ndp.SCHEMA_ELIGIBILITY, "eligible": False, "reason": "limited_or_site", "lease_duration_s": 0}
        dec2 = self.ndp.resolve_transition(elig_downgrade, state_active)
        self.assertEqual(dec2["action"], "revert_override")
        self.assertTrue(dec2["rollback_required"])
        self.assertEqual(dec2["lease_ttl_s"], 0)

        # Sequence 2: Duplicate apply is idempotent refresh, does not stack effects
        state_duplicate = {
            "prior_effect": "active_override",
            "receipt_state": "active_fresh",
            "event": "admit",
            "mode": "policy",
        }
        dec3 = self.ndp.resolve_transition(elig_permit, state_duplicate)
        self.assertEqual(dec3["action"], "refresh_override")
        self.assertFalse(dec3["rollback_required"])
        self.assertEqual(dec3["lease_ttl_s"], 55)

        # Sequence 3: Watchdog after expiry
        state_expired = {
            "prior_effect": "active_override",
            "receipt_state": "expired",
            "event": "watchdog",
            "mode": "policy",
        }
        elig_expired = {"schema_version": self.ndp.SCHEMA_ELIGIBILITY, "eligible": False, "reason": "stale_evidence", "lease_duration_s": 0}
        dec4 = self.ndp.resolve_transition(elig_expired, state_expired)
        self.assertEqual(dec4["action"], "revert_override")
        self.assertTrue(dec4["rollback_required"])
        self.assertEqual(dec4["telemetry_state"]["lease"], "expired")

    def test_telemetry_sanitizer(self):
        """Verify telemetry sanitizer scrubs identifiers, secrets, IPs, MACs, domains, and tokens."""
        for svec in self.vectors["sanitizer_vectors"]:
            name = svec["name"]
            raw = svec["raw"]
            expected = svec["expected"]

            with self.subTest(sanitizer_name=name):
                sanitized = self.ndp.sanitize_telemetry(raw)
                self.assertEqual(sanitized, expected)

    def test_validate_health_schema(self):
        """Verify validate_health rejects extra keys and non-enums."""
        valid_health = {
            "schema_version": "network.dns-policy-health.v1",
            "policy_state": "preserving",
            "connectivity": "full",
            "reason": "trusted_full",
            "freshness": "fresh",
            "lease": "not_applicable",
            "last_transition_age": "lt_30s",
            "transition_count_bucket": "1",
            "acquisition_error": "none",
        }
        ok, msg = self.ndp.validate_health(valid_health)
        self.assertTrue(ok, f"Expected health to be valid: {msg}")
        self.validator_health.validate(valid_health)

        # Extra key rejection
        extra_health = dict(valid_health, extra_fact="bad")
        ok, _ = self.ndp.validate_health(extra_health)
        self.assertFalse(ok)
        with self.assertRaises(jsonschema.ValidationError):
            self.validator_health.validate(extra_health)

        # Invalid enum rejection
        bad_enum_health = dict(valid_health, policy_state="random_state")
        ok, _ = self.ndp.validate_health(bad_enum_health)
        self.assertFalse(ok)
        with self.assertRaises(jsonschema.ValidationError):
            self.validator_health.validate(bad_enum_health)


class TestNetworkDnsPolicyN1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import scripts.ai.lib.network_dns_policy as ndp
        cls.ndp = ndp

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.health_path = self.tmp_path / "health.json"
        self.lock_path = self.tmp_path / "health.lock"
        self.sysfs_dir = self.tmp_path / "sysfs_net"
        self.sysfs_dir.mkdir()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_interface_validation(self):
        """Verify interface token matching ^[A-Za-z0-9_.:-]{1,32}$."""
        valid_ifaces = ["wlan0", "wlp3s0", "eth0", "enp2s0f0", "wlan_0", "net-1:2.3"]
        for iface in valid_ifaces:
            self.assertTrue(self.ndp.is_valid_interface(iface), f"Expected valid: {iface}")

        invalid_ifaces = ["", "wlan 0", "wlan;rm -rf /", "wlan\n0", "../wlan", "a" * 33, None, 123]
        for iface in invalid_ifaces:
            self.assertFalse(self.ndp.is_valid_interface(iface), f"Expected invalid: {iface}")

    def test_sysfs_wifi_detection(self):
        """Verify Wi-Fi detection via sysfs wireless or phy80211 directories."""
        # Non-wifi interface
        eth = self.sysfs_dir / "eth0"
        eth.mkdir()
        self.assertFalse(self.ndp.is_wifi_interface("eth0", sysfs_base=self.sysfs_dir))

        # Wi-Fi interface with wireless directory
        wlan0 = self.sysfs_dir / "wlan0"
        wlan0.mkdir()
        (wlan0 / "wireless").mkdir()
        self.assertTrue(self.ndp.is_wifi_interface("wlan0", sysfs_base=self.sysfs_dir))

        # Wi-Fi interface with phy80211 directory
        wlan1 = self.sysfs_dir / "wlan1"
        wlan1.mkdir()
        (wlan1 / "phy80211").mkdir()
        self.assertTrue(self.ndp.is_wifi_interface("wlan1", sysfs_base=self.sysfs_dir))

    def test_bounded_fact_acquisition_synthetic(self):
        """Verify fact acquisition adapter maps synthetic outputs to N0 facts."""
        wlan0 = self.sysfs_dir / "wlan0"
        wlan0.mkdir()
        (wlan0 / "wireless").mkdir()

        # Synthetic runner simulating nmcli and resolvectl
        def synthetic_runner(argv):
            cmd = argv[0]
            if cmd == "nmcli" and "CONNECTIVITY" in argv:
                return "full\n", self.ndp.AcquisitionError.NONE
            elif cmd == "nmcli" and "GENERAL.CON-UUID" in argv:
                return "11111111-2222-3333-4444-555555555555\n", self.ndp.AcquisitionError.NONE
            elif cmd == "resolvectl" and "domain" in argv:
                return "Link 2 (wlan0): ~.\n", self.ndp.AcquisitionError.NONE
            return None, self.ndp.AcquisitionError.MISSING_COMMAND

        facts, err = self.ndp.acquire_facts("wlan0", sysfs_base=self.sysfs_dir, cmd_runner=synthetic_runner)
        self.assertEqual(err, self.ndp.AcquisitionError.NONE)
        self.assertEqual(facts["connectivity"], "full")
        self.assertEqual(facts["dns_topology"], "split")
        self.assertEqual(facts["link_kind"], "wifi")
        self.assertEqual(facts["connection_class"], "untrusted")
        self.assertEqual(facts["evidence_age_bucket"], "fresh")

        # Derive health record
        health = self.ndp.derive_health_record(facts, err)
        self.assertEqual(health["policy_state"], "preserving")
        self.assertEqual(health["connectivity"], "full")
        self.assertEqual(health["reason"], "untrusted_profile")

    def test_durable_atomic_health_persistence(self):
        """Verify atomic publication, locking, fsync, and read_health."""
        health_data = {
            "schema_version": "network.dns-policy-health.v1",
            "policy_state": "preserving",
            "connectivity": "portal",
            "reason": "portal",
            "freshness": "fresh",
            "lease": "not_applicable",
            "last_transition_age": "lt_30s",
            "transition_count_bucket": "1",
            "acquisition_error": "none",
        }

        # Successful publication
        ok = self.ndp.publish_health(health_data, health_path=self.health_path, lock_path=self.lock_path)
        self.assertTrue(ok)
        self.assertTrue(self.health_path.exists())

        # Read back
        read_back = self.ndp.read_health(self.health_path)
        self.assertEqual(read_back["policy_state"], "preserving")
        self.assertEqual(read_back["connectivity"], "portal")
        self.assertEqual(read_back["reason"], "portal")

        # Invalid data is rejected before writing
        invalid_data = dict(health_data, extra_key="illegal")
        ok_bad = self.ndp.publish_health(invalid_data, health_path=self.health_path, lock_path=self.lock_path)
        self.assertFalse(ok_bad)

        # Missing file falls back to closed unavailable
        non_existent = self.tmp_path / "non_existent.json"
        fallback = self.ndp.read_health(non_existent)
        self.assertEqual(fallback["policy_state"], "unavailable")
        self.assertEqual(fallback["connectivity"], "unknown")
        self.assertEqual(fallback["reason"], "unknown_state")

    def test_cli_facade_smoke(self):
        """Verify aq-network-policy status, health, json, and verb prohibition."""
        import subprocess

        facade = _REPO / "scripts" / "ai" / "aq-network-policy"
        self.assertTrue(facade.exists())

        # Publish a valid health record first
        health_data = {
            "schema_version": "network.dns-policy-health.v1",
            "policy_state": "preserving",
            "connectivity": "full",
            "reason": "untrusted_profile",
            "freshness": "fresh",
            "lease": "not_applicable",
            "last_transition_age": "lt_30s",
            "transition_count_bucket": "1",
            "acquisition_error": "none",
        }
        self.ndp.publish_health(health_data, health_path=self.health_path, lock_path=self.lock_path)

        # 1. status
        res = subprocess.run([sys.executable, str(facade), "status", "--path", str(self.health_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Network DNS Policy Status:", res.stdout)
        self.assertIn("preserving", res.stdout)

        # 2. health
        res = subprocess.run([sys.executable, str(facade), "health", "--path", str(self.health_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        parsed = json.loads(res.stdout)
        self.assertEqual(parsed["policy_state"], "preserving")

        # 3. json
        res = subprocess.run([sys.executable, str(facade), "json", "--path", str(self.health_path)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        parsed = json.loads(res.stdout)
        self.assertEqual(parsed["schema_version"], "network.dns-policy-health.v1")

        # 4. Prohibited verbs reject with code 2
        for bad_verb in ["apply", "revert", "set", "modify"]:
            res = subprocess.run([sys.executable, str(facade), bad_verb], capture_output=True, text=True)
            self.assertEqual(res.returncode, 2)
            self.assertIn("strictly prohibited", res.stderr)


if __name__ == "__main__":
    unittest.main()
