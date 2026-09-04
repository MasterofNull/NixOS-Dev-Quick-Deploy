#!/usr/bin/env python3
"""Fixture-matrix tests for the AQ-OS AI-fit evaluator + pinned catalog.

Covers PRD v2 section 92: measured reserves, backend eligibility, offload/context
caps, CPU-only honest `limited`, and conservative resolution on unknown VRAM /
insufficient evidence. Never authorizes full offload without known VRAM.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_FIT_PATH = REPO_ROOT / "scripts" / "ai" / "lib" / "ai_fit.py"
CATALOG_PATH = REPO_ROOT / "config" / "aqos-ai-fit-policy-catalog-v1.json"
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "aqos-ai-fit-policy-v1.schema.json"
GIB = 1024**3


def load_ai_fit():
    spec = importlib.util.spec_from_file_location("ai_fit", AI_FIT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_hw(ram_bytes, *, present=False, outcome="none", memory_type=None,
            vendor_id=None, vram_bytes=None, device_count=None):
    """Build a hw_probe-shaped (schema_version 2) evidence dict."""
    if device_count is None:
        device_count = 1 if present else 0
    primary = None
    if present:
        primary = {"memory_type": memory_type, "vendor_id": vendor_id,
                   "vram_total_bytes": vram_bytes}
    return {
        "schema_version": 2,
        "ram": {"total_bytes": ram_bytes},
        "gpu": {
            "present": present, "outcome": outcome,
            "devices": [{} for _ in range(device_count)],
            "primary": primary,
        },
    }


def test_catalog_matches_schema_and_digest_is_stable() -> str:
    catalog = json.loads(CATALOG_PATH.read_text())
    schema = json.loads(SCHEMA_PATH.read_text())
    assert schema["properties"]["catalog_version"]["const"] == catalog["catalog_version"]
    # Structural sanity (works without jsonschema installed).
    for key in ("policy_version", "reserves", "backends", "models"):
        assert key in catalog, key
    for m in catalog["models"]:
        for k in ("id", "ram_required_bytes", "vram_required_bytes", "context_max",
                  "cpu_only_supported", "source"):
            assert k in m, (m.get("id"), k)
        assert isinstance(m["ram_required_bytes"], int)
    # Optional strict validation if jsonschema is available.
    try:
        import jsonschema  # type: ignore
        jsonschema.validate(catalog, schema)
    except ImportError:
        pass
    # Digest determinism + matches raw file bytes.
    mod = load_ai_fit()
    _, d1 = mod.load_catalog(CATALOG_PATH)
    _, d2 = mod.load_catalog(CATALOG_PATH)
    assert d1 == d2
    assert d1 == hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()
    return d1


def test_recommended_desktop_dgpu() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(64 * GIB, present=True, outcome="detected", memory_type="dedicated",
                 vendor_id="0x10de", vram_bytes=24 * GIB)
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["verdict"] == "recommended", ev
    assert ev["backend"]["id"] == "cuda", ev
    assert ev["backend"]["offload"] == "full", ev
    assert ev["recommended_model"] is not None
    assert "cpu-only" not in ev["downgrade_reasons"], ev
    assert ev["evidence_status"] == "sufficient"


def test_apu_shared_partial_offload_capped() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    # aq-os reference box: 27GB usable, AMD APU, shared memory.
    hw = make_hw(27 * GIB, present=True, outcome="detected", memory_type="shared",
                 vendor_id="0x1002", vram_bytes=None)
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["backend"]["id"] == "vulkan", ev
    assert ev["backend"]["offload"] == "partial", ev
    assert ev["backend"]["gpu_layer_cap"] == 12, ev
    # Shared/APU must NEVER produce full offload on any model.
    assert all(m["offload"] != "full" for m in ev["eligible_models"]), ev
    assert "partial-offload" in ev["downgrade_reasons"], ev


def test_cpu_only_is_limited_not_recommended() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(32 * GIB, present=False, outcome="none")
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["verdict"] == "limited", ev  # honest cpu-only path, never recommended
    assert ev["backend"]["id"] == "cpu", ev
    assert ev["recommended_model"] is not None, ev
    assert "cpu-only" in ev["downgrade_reasons"], ev
    assert all(m["offload"] == "none" for m in ev["eligible_models"]), ev


def test_dedicated_vram_unknown_never_full() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(32 * GIB, present=True, outcome="detected", memory_type="dedicated",
                 vendor_id="0x10de", vram_bytes=None)
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["backend"]["offload"] == "none", ev  # unknown VRAM -> conservative CPU fallback
    assert all(m["offload"] != "full" for m in ev["eligible_models"]), ev


def test_unlisted_vendor_cannot_bypass_catalog_eligibility() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(64 * GIB, present=True, outcome="detected", memory_type="dedicated",
                 vendor_id="0x1234", vram_bytes=24 * GIB)
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["backend"]["id"] == "cpu", ev
    assert ev["backend"]["offload"] == "none", ev


def test_disabled_cuda_does_not_fall_through_to_ineligible_vulkan() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    catalog["backends"]["cuda"]["auto_select"] = False
    hw = make_hw(64 * GIB, present=True, outcome="detected", memory_type="dedicated",
                 vendor_id="0x10de", vram_bytes=24 * GIB)
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["backend"]["id"] == "cpu", ev
    assert ev["backend"]["offload"] == "none", ev


def test_unknown_model_vram_never_full_offloads() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(64 * GIB, present=True, outcome="detected", memory_type="dedicated",
                 vendor_id="0x10de", vram_bytes=24 * GIB)
    ev = mod.evaluate_fit(hw, catalog, digest)
    unknown = [m for m in ev["eligible_models"] if m["model_id"] == "gemma3-27b"][0]
    assert unknown["offload"] == "none", unknown
    assert unknown["gpu_layer_cap"] == 0, unknown
    assert "unknown" in unknown["downgrade_reason"], unknown


def test_insufficient_gpu_evidence_conservative() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(16 * GIB, present=False, outcome="insufficient_evidence")
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["evidence_status"] == "insufficient_evidence", ev
    assert ev["backend"]["id"] == "cpu", ev
    assert ev["verdict"] in ("limited", "not_advised"), ev
    assert "gpu-evidence-insufficient" in ev["downgrade_reasons"], ev


def test_ram_unknown_is_not_advised() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(None)
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["verdict"] == "not_advised", ev
    assert ev["evidence_status"] == "unknown", ev
    assert ev["eligible_models"] == [], ev
    assert ev["recommended_model"] is None, ev
    assert ev["backend"]["offload"] == "none", ev


def test_ram_too_small_is_not_advised() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(2 * GIB, present=False, outcome="none")
    ev = mod.evaluate_fit(hw, catalog, digest)
    assert ev["verdict"] == "not_advised", ev
    assert ev["recommended_model"] is None, ev
    assert "ram-too-small" in ev["downgrade_reasons"], ev


def test_eligible_models_deterministic_order() -> None:
    mod = load_ai_fit()
    catalog, digest = mod.load_catalog(CATALOG_PATH)
    hw = make_hw(64 * GIB, present=True, outcome="detected", memory_type="dedicated",
                 vendor_id="0x10de", vram_bytes=24 * GIB)
    ev = mod.evaluate_fit(hw, catalog, digest)
    params = [m["params_b"] for m in ev["eligible_models"]]
    assert params == sorted(params), params


def test_cli_digest_matches() -> None:
    out = subprocess.run(
        [sys.executable, str(AI_FIT_PATH), "--digest", "--catalog", str(CATALOG_PATH)],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    assert out.stdout.strip() == hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()


def main() -> int:
    digest = test_catalog_matches_schema_and_digest_is_stable()
    test_recommended_desktop_dgpu()
    test_apu_shared_partial_offload_capped()
    test_cpu_only_is_limited_not_recommended()
    test_dedicated_vram_unknown_never_full()
    test_unlisted_vendor_cannot_bypass_catalog_eligibility()
    test_disabled_cuda_does_not_fall_through_to_ineligible_vulkan()
    test_unknown_model_vram_never_full_offloads()
    test_insufficient_gpu_evidence_conservative()
    test_ram_unknown_is_not_advised()
    test_ram_too_small_is_not_advised()
    test_eligible_models_deterministic_order()
    test_cli_digest_matches()
    print(f"test-ai-fit: ok catalog_sha256={digest[:12]}… 13/13")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
