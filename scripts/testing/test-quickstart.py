#!/usr/bin/env python3
"""Tests for aq-quickstart — per-hardware quickstart + first-delegation doctor (P10).

Run: python3 scripts/testing/test-quickstart.py
"""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
loader = importlib.machinery.SourceFileLoader("aq_quickstart", str(REPO / "scripts" / "ai" / "aq-quickstart"))
Q = importlib.util.module_from_spec(importlib.util.spec_from_loader("aq_quickstart", loader))
loader.exec_module(Q)
import model_budget as MB  # noqa: E402


def _probe(ram_gb, hw, main_b, quant, cpu="Test CPU", layers=12):
    return {
        "ram": {"total_bytes": int(ram_gb * 1e9)},
        "cpu": {"model": cpu},
        "gpu": {"primary": {"memory_type": "shared"}},
        "derived": {
            "hardware_class": hw, "suggested_n_gpu_layers": layers,
            "tok_per_sec_estimate": None,
            "model_size_class": {"max_local_model_b_params": main_b, "quant_ladder_step": quant},
        },
    }


def test_quickstart_adapts_per_class():
    for ram, hw, b, q in [(4, "embedded", 3, "Q4_K_M"), (16, "laptop", 14, "Q4_K_M"),
                          (29, "desktop", 35, "Q4_K_M"), (128, "server", 70, "Q5_K_M")]:
        p = _probe(ram, hw, b, q)
        doc = Q.render_quickstart(p, MB.derive_budget(p))
        assert hw in doc, f"class {hw} not reflected"
        assert f"{b}" in doc, f"model size {b}B not in {hw} quickstart"
        assert "first local delegation < 1 hour" in doc
        assert "aq quickstart --doctor" in doc
    print("PASS quickstart adapts per hardware class (embedded/laptop/desktop/server)")


def test_quickstart_reflects_small_resident_decision():
    # Server -> small fits; embedded -> not on this hardware.
    server = Q.render_quickstart(*(lambda p: (p, MB.derive_budget(p)))(_probe(128, "server", 70, "Q5_K_M")))
    embedded = Q.render_quickstart(*(lambda p: (p, MB.derive_budget(p)))(_probe(4, "embedded", 3, "Q4_K_M")))
    assert "fits" in server
    assert "not on this hardware" in embedded
    print("PASS quickstart reflects the model_budget small-resident decision")


def test_doctor_structure():
    d = Q.doctor()
    gates = {g["gate"] for g in d["gates"]}
    assert gates == {"repo", "nix", "llama_health", "model_generate"}
    assert "ready_for_first_delegation" in d
    for g in d["gates"]:
        assert isinstance(g["ok"], bool) and g["detail"]
    print(f"PASS doctor gates well-formed (ready={d['ready_for_first_delegation']})")


def test_doctor_repo_gate_passes_here():
    ok, _ = Q._gate_repo()
    assert ok, "repo gate must pass when run from the checkout"
    print("PASS doctor repo gate passes in-repo")


if __name__ == "__main__":
    test_quickstart_adapts_per_class()
    test_quickstart_reflects_small_resident_decision()
    test_doctor_structure()
    test_doctor_repo_gate_passes_here()
    print("ALL PASS")
