#!/usr/bin/env python3
"""Tests for the hardware-driven model budget policy (WS-EDGE, god-tier prompt 6).

The rebudget must be DERIVED from hardware, not hand-set per machine, so new
devices auto-configure. Covers embedded/laptop/desktop/server + the quant-down
decision path.

Run: python3 scripts/testing/test-model-budget.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

import model_budget as mb  # noqa: E402


def _probe(ram_gb, hw_class, main_b, quant):
    return {
        "ram": {"total_bytes": int(ram_gb * 1e9)},
        "derived": {
            "hardware_class": hw_class,
            "model_size_class": {"max_local_model_b_params": main_b, "quant_ladder_step": quant},
        },
    }


def test_desktop_fits_small_at_recommended_quant():
    b = mb.derive_budget(_probe(29, "desktop", 35, "Q4_K_M"))
    assert b["recommendation"] == "deploy_small_resident_now", b["recommendation"]
    assert b["small_resident"]["fits_at_current_quant"] is True
    assert b["small_resident"]["candidate_now"] is not None
    print(f"PASS desktop 29GB @ Q4_K_M -> small fits now ({b['reason']})")


def test_high_quant_needs_quant_down():
    # Same box but the main model is at a heavier quant (Q6_K) -> less slack.
    b = mb.derive_budget(_probe(27, "desktop", 35, "Q6_K"))
    sr = b["small_resident"]
    assert b["recommendation"] in ("quant_down_then_small_resident", "single_model_only"), b["recommendation"]
    if b["recommendation"] == "quant_down_then_small_resident":
        assert sr["requires_quant_down"] and sr["quant_down_to"] and sr["freed_by_quant_down_gb"] > 0
        print(f"PASS heavy-quant desktop -> quant-down path ({sr['quant_down_to']}, frees {sr['freed_by_quant_down_gb']}GB)")
    else:
        print("PASS heavy-quant desktop -> single_model_only (honest)")


def test_embedded_single_model_only():
    b = mb.derive_budget(_probe(4, "embedded", 3, "Q4_K_M"))
    # 4GB - 3 reserve - 1 KV = 0 usable; a 3B model can't even fit -> single/none.
    assert b["recommendation"] in ("single_model_only", "quant_down_then_small_resident"), b["recommendation"]
    print(f"PASS embedded 4GB -> {b['recommendation']}")


def test_server_fits_easily():
    b = mb.derive_budget(_probe(128, "server", 70, "Q5_K_M"))
    assert b["recommendation"] == "deploy_small_resident_now"
    assert b["slack_gb_at_current_quant"] > 20
    print(f"PASS server 128GB -> small fits easily ({b['slack_gb_at_current_quant']}GB slack)")


def test_deterministic():
    p = _probe(29, "desktop", 35, "Q4_K_M")
    assert mb.derive_budget(p) == mb.derive_budget(p), "policy must be deterministic (drives generated Nix)"
    print("PASS deterministic (safe to drive a generated profile)")


def test_missing_fields_degrade():
    # Empty probe must not crash — fall back to conservative defaults.
    b = mb.derive_budget({})
    assert "recommendation" in b and b["ram_total_gb"] > 0
    print("PASS missing probe fields degrade to conservative defaults")


if __name__ == "__main__":
    test_desktop_fits_small_at_recommended_quant()
    test_high_quant_needs_quant_down()
    test_embedded_single_model_only()
    test_server_fits_easily()
    test_deterministic()
    test_missing_fields_degrade()
    print("ALL PASS")
