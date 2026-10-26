#!/usr/bin/env python3
"""
test-multidomain-sweeper.py — Verification of full-spectrum multi-domain intelligence
sweeping across all 5 engineering disciplines.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SWEEPER = ROOT / "scripts/ai/aq-durable-sweeper"
RADAR = ROOT / "scripts/ai/aq-radar-ingest"


def test_multidomain_classification():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "sweeper.json"

        # 1. Ingest item from Agentic Architecture domain
        res_agent = subprocess.run([
            sys.executable, str(SWEEPER), "--state-file", str(state_file),
            "ingest",
            "--title", "Speculative PRM Tree-of-Thought Routing",
            "--source", "https://arxiv.org/abs/2610.99991",
            "--content", "Introduces multi-agent speculative decoding and PRM token efficiency for autonomous loops.",
            "--json"
        ], capture_output=True, text=True)
        assert res_agent.returncode == 0
        d_agent = json.loads(res_agent.stdout)
        assert d_agent["domain"] == "agentic_architecture"
        assert d_agent["classification"]["category"] == "signal"

        # 2. Ingest item from OS Systems & Confinement domain
        res_os = subprocess.run([
            sys.executable, str(SWEEPER), "--state-file", str(state_file),
            "ingest",
            "--title", "VirtIO MMIO Transport MicroVM Confinement",
            "--source", "https://kernel.org/patch/123",
            "--content", "Enforces Landlock and Bubblewrap sandbox isolation with seccomp filter for microvm virtio boundaries.",
            "--json"
        ], capture_output=True, text=True)
        assert res_os.returncode == 0
        d_os = json.loads(res_os.stdout)
        assert d_os["domain"] == "os_systems_confinement"
        assert d_os["classification"]["category"] == "signal"

        # 3. Ingest item from Frontend Cockpit domain
        res_ui = subprocess.run([
            sys.executable, str(SWEEPER), "--state-file", str(state_file),
            "ingest",
            "--title", "OKLCH Mission Cockpit Low-Latency Telemetry HUD",
            "--source", "https://design.example.org",
            "--content", "Human-computer interaction and design system telemetry HUD using canvas and D3 visualization.",
            "--json"
        ], capture_output=True, text=True)
        assert res_ui.returncode == 0
        d_ui = json.loads(res_ui.stdout)
        assert d_ui["domain"] == "frontend_cockpit_ux"
        assert d_ui["classification"]["category"] == "signal"

        # 4. Ingest item from Quantitative Financial domain
        res_quant = subprocess.run([
            sys.executable, str(SWEEPER), "--state-file", str(state_file),
            "ingest",
            "--title", "Hawkes Process Market Microstructure Order Book",
            "--source", "https://arxiv.org/abs/2610.99992",
            "--content", "Applies Kalman filter state filtering and stochastic volatility to market microstructure.",
            "--json"
        ], capture_output=True, text=True)
        assert res_quant.returncode == 0
        d_quant = json.loads(res_quant.stdout)
        assert d_quant["domain"] == "quant_financial_stochastic"
        assert d_quant["classification"]["category"] == "signal"

        # 5. Ingest item from Testing & Formal Verification domain
        res_test = subprocess.run([
            sys.executable, str(SWEEPER), "--state-file", str(state_file),
            "ingest",
            "--title", "SMT Solver Invariant Fuzzing",
            "--source", "https://formal.example.org",
            "--content", "Automated invariant generation and mutation testing with SMT solver model checking.",
            "--json"
        ], capture_output=True, text=True)
        assert res_test.returncode == 0
        d_test = json.loads(res_test.stdout)
        assert d_test["domain"] == "testing_verification"
        assert d_test["classification"]["category"] == "signal"

        # Verify domain counts in state metrics
        res_stat = subprocess.run([
            sys.executable, str(SWEEPER), "--state-file", str(state_file), "status"
        ], capture_output=True, text=True)
        assert res_stat.returncode == 0
        state = json.loads(res_stat.stdout)
        dc = state["metrics"]["domain_counts"]
        assert dc["agentic_architecture"] >= 1
        assert dc["os_systems_confinement"] >= 1
        assert dc["frontend_cockpit_ux"] >= 1
        assert dc["quant_financial_stochastic"] >= 1
        assert dc["testing_verification"] >= 1

    print("PASS: Multi-domain intelligence sweeper and domain classification verified across 5 disciplines.")


def main():
    test_multidomain_classification()
    print("ALL MULTI-DOMAIN SWEEPER TESTS PASSED")


if __name__ == "__main__":
    main()
