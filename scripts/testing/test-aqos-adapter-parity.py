#!/usr/bin/env python3
"""P1 parity suite — guided / AI / manual / legacy produce the IDENTICAL resolved plan.

The "one engine" proof (installer PRD): every front-end is a thin adapter over the
SAME resolver, so equivalent inputs expressed through any adapter must normalize to
one request and resolve to a BYTE-IDENTICAL canonical (RFC 8785 JCS) resolved lock
and the IDENTICAL projection. A guided click, an AI proposal, a manual request, and
a legacy flag set cannot diverge.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts/ai/lib"
sys.path.insert(0, str(LIB))
import aqos_install_resolver as resolver  # noqa: E402


def _load_guided():
    # SourceFileLoader handles the extensionless `aqos-guided-install` producer.
    path = ROOT / "scripts/ai/aqos-guided-install"
    loader = importlib.machinery.SourceFileLoader("guided_producer", str(path))
    spec = importlib.util.spec_from_loader("guided_producer", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m

SCHEMA = json.loads((ROOT / "config/schemas/aqos-install-plan-v1.schema.json").read_text())
MODULE_BYTES = (ROOT / "config/aqos-module-catalog-v1.json").read_bytes()
MODULES = resolver.parse_json_strict(MODULE_BYTES)
AI_BYTES = (ROOT / "config/aqos-ai-fit-policy-catalog-v1.json").read_bytes()
FIELDSET_BYTES = (ROOT / "config/aqos-mysystem-fieldset-v1.json").read_bytes()
HOST = "parityhost"


def source():
    return {"oid_algorithm": "sha1", "git_commit": "a" * 40, "git_tree": "b" * 40,
            "clean_worktree": True, "flake_lock_sha256": "c" * 64,
            "nix_system": "x86_64-linux",
            "flake_installable": f"path:/repo#nixosConfigurations.{HOST}", "host_target": HOST}


def hardware():
    return {"schema_version": 2, "cpu": {"architecture": "x86_64", "model": "t", "cores": 8, "threads": 16},
            "ram": {"total_bytes": 32 * 1024**3},
            "gpu": {"outcome": "detected", "devices": [], "present": False}}


def _resolve(kind, payload):
    req = resolver.normalize_adapter(kind, payload)
    lock = resolver.resolve_plan(req, hardware(), MODULES, MODULE_BYTES, AI_BYTES, FIELDSET_BYTES, SCHEMA, source())
    proj = resolver.compile_projection(lock, MODULES, FIELDSET_BYTES)
    return resolver.jcs_bytes(lock), resolver.jcs_bytes(proj)


# The SAME intent expressed four ways (AI off -> no hardware-fit dependency).
_SELECTION = {"golden_profile": "profile.gaming", "roles": ["role.gaming"], "include_local_ai": False}
_PAYLOADS = {
    "manual": {"artifact_type": "request_plan", "schema_version": resolver.SCHEMA_VERSION,
               "selection": dict(_SELECTION), "host_target": HOST},
    "guided": {"answers": dict(_SELECTION), "host_target": HOST},
    "ai": {"proposal": dict(_SELECTION), "host_target": HOST},
    "legacy": {"profile": "gaming", "roles": ["role.gaming"], "include_local_ai": False, "host": HOST},
}


def test_all_adapters_produce_identical_lock_and_projection():
    results = {k: _resolve(k, p) for k, p in _PAYLOADS.items()}
    locks = {k: v[0] for k, v in results.items()}
    projs = {k: v[1] for k, v in results.items()}
    # Byte-identical canonical lock across ALL adapters.
    assert len(set(locks.values())) == 1, {k: resolver.sha256_bytes(v) for k, v in locks.items()}
    # Byte-identical projection across ALL adapters.
    assert len(set(projs.values())) == 1, {k: resolver.sha256_bytes(v) for k, v in projs.items()}


def test_parity_is_not_trivial_different_intent_differs():
    """Guard against a degenerate 'always equal' pass: a different selection must
    produce a different lock (so the parity assertion above has real content)."""
    base_lock, _ = _resolve("manual", _PAYLOADS["manual"])
    other = {"artifact_type": "request_plan", "schema_version": resolver.SCHEMA_VERSION,
             "selection": {"golden_profile": "profile.minimal", "roles": [], "include_local_ai": False},
             "host_target": HOST}
    other_lock, _ = _resolve("manual", other)
    assert base_lock != other_lock


def test_legacy_profile_maps_into_the_same_engine():
    """Legacy 'gaming' flag resolves to the same golden_profile the others name explicitly."""
    lock_bytes, _ = _resolve("legacy", _PAYLOADS["legacy"])
    lock = json.loads(lock_bytes)
    assert lock["selection"]["golden_profile"] == "profile.gaming"


def test_REAL_guided_producer_matches_manual_no_data_loss():
    """Certify the ACTUAL seam, not a fixture: feed the REAL aqos-guided-install output
    through the SAME `--adapter guided` the tool prints, and require a byte-identical lock
    to the manual adapter given the equivalent selection. This is the test the earlier
    hand-fabricated {"answers": ...} fixture skipped — it would have caught the silent
    data-loss bug (guided emitting a request_plan while the command said --adapter guided)."""
    guided = _load_guided()
    real = guided.build_guided_request(HOST, include_local_ai=False, roles=["role.gaming"])
    guided_lock, guided_proj = _resolve("guided", real)
    manual_equiv = {"artifact_type": "request_plan", "schema_version": resolver.SCHEMA_VERSION,
                    "selection": {"golden_profile": guided.GOLDEN_PROFILE, "roles": ["role.gaming"],
                                  "include_local_ai": False}, "host_target": HOST}
    manual_lock, manual_proj = _resolve("manual", manual_equiv)
    assert guided_lock == manual_lock, "real guided output diverges from manual through the resolver"
    assert guided_proj == manual_proj
    # And the choices actually survived (the bug emptied selection -> roles == []).
    sel = json.loads(guided_lock)["selection"]
    assert sel["roles"], f"guided role choice was dropped: {sel}"  # non-empty; [] under the old bug
    assert sel["golden_profile"] == guided.GOLDEN_PROFILE


def main() -> int:
    test_all_adapters_produce_identical_lock_and_projection()
    test_parity_is_not_trivial_different_intent_differs()
    test_legacy_profile_maps_into_the_same_engine()
    test_REAL_guided_producer_matches_manual_no_data_loss()
    print("test-aqos-adapter-parity: ok 4/4 (guided==ai==manual==legacy + REAL producer, byte-identical)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
