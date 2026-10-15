#!/usr/bin/env python3
"""Test suite for Frontier FE-2b GEPA build-time prompt compile engine and CLI."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import functional_eval as fe  # noqa: E402
import gepa_optimizer as gepa  # noqa: E402


def test_optimizer_loads_base_template() -> None:
    opt = gepa.GepaOptimizer(repo_root=ROOT)
    tmpl = opt.load_prompt_template("aider_task_systems_code")
    assert tmpl is not None, "Failed to load aider_task_systems_code from registry"
    assert "TASK: {{ task_description }}" in tmpl, "Missing TASK placeholder"
    assert "CONSTRAINTS:" in tmpl, "Missing CONSTRAINTS block"
    print("  [PASS] test_optimizer_loads_base_template")


def test_reflection_feedback_synthesis() -> None:
    opt = gepa.GepaOptimizer(repo_root=ROOT)
    mock_results = [
        {"task": "mean", "passed": False, "failures": ["Assertion failed: mean([]) must be 0.0"]},
        {"task": "dedupe", "passed": False, "failures": ["Assertion failed: dedupe must preserve order"]},
        {"task": "service_hardening", "passed": False, "failures": ["DynamicUser must be True"]},
        {"task": "clamp", "passed": True, "failures": []},
    ]
    feedback = opt.extract_reflection_feedback(mock_results)
    assert len(feedback) == 3, f"Expected 3 feedback items, got {len(feedback)}"
    assert any("Mean calculation" in fb for fb in feedback), "Missing mean directive"
    assert any("Deduplication" in fb for fb in feedback), "Missing dedupe directive"
    assert any("Systemd hardening" in fb for fb in feedback), "Missing service hardening directive"
    print("  [PASS] test_reflection_feedback_synthesis")


def test_synthesize_candidate_template() -> None:
    opt = gepa.GepaOptimizer(repo_root=ROOT)
    base = "TASK: foo\n\nCONSTRAINTS:\n- line1\n\nOUTPUT: bar"
    feedback = ["Directive A: handle empty input", "Directive B: preserve order"]
    cand = opt.synthesize_candidate_template(base, feedback)
    assert "REFLECTIVE EXECUTION DIRECTIVES (GEPA COMPILED):" in cand
    assert "- Directive A: handle empty input" in cand
    assert "- Directive B: preserve order" in cand
    assert "- line1" in cand
    print("  [PASS] test_synthesize_candidate_template")


def test_strict_gating_rule_enforcement() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        # Setup mock repo structure
        (tmp_root / "ai-stack/prompts").mkdir(parents=True)
        reg_file = tmp_root / "ai-stack/prompts/registry.yaml"
        reg_file.write_text(
            "prompts:\n  - id: test_prompt\n    template: |\n      TASK: {{ task_description }}\n      CONSTRAINTS:\n      - rule 1\n",
            encoding="utf-8",
        )
        opt = gepa.GepaOptimizer(repo_root=tmp_root)

        # Case 1: Candidate beats baseline -> gate passes and artifact is adopted
        res_improving = opt.compile(
            prompt_id="test_prompt",
            dry_run=True,
            adopt=True,
            mock_baseline_ratio=0.5,
            mock_compiled_ratio=1.0,
        )
        assert res_improving["gate_passed"] is True
        assert res_improving["score_lift"] > 0.0
        # dry-run scores are simulated and must never be adopted
        assert res_improving["adopted"] is False
        assert res_improving["saved_path"] is None
        assert res_improving["artifact"]["metadata"]["simulated"] is True

        # Case 2: Candidate does NOT beat baseline -> gate fails and artifact is NOT adopted
        res_non_improving = opt.compile(
            prompt_id="test_prompt",
            dry_run=True,
            adopt=True,
            mock_baseline_ratio=1.0,
            mock_compiled_ratio=0.8,
        )
        assert res_non_improving["gate_passed"] is False
        assert res_non_improving["score_lift"] <= 0.0
        assert res_non_improving["adopted"] is False
    print("  [PASS] test_strict_gating_rule_enforcement")


def test_non_dry_run_without_evaluator_refuses() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        (tmp_root / "ai-stack/prompts").mkdir(parents=True)
        (tmp_root / "ai-stack/prompts/registry.yaml").write_text(
            "prompts:\n  - id: p1\n    template: 'TASK: x\\nCONSTRAINTS:\\n- r'\n", encoding="utf-8"
        )
        res = gepa.GepaOptimizer(repo_root=tmp_root).compile(prompt_id="p1", dry_run=False, adopt=True)
        assert res["gate_passed"] is False and res["ok"] is False
        assert res["reason"] == "no real evaluator"
        assert res["adopted"] is False
        assert not list((tmp_root / "ai-stack/prompts/compiled").glob("*.gepa.json"))
    print("  [PASS] test_non_dry_run_without_evaluator_refuses")


def test_compiled_artifact_serialization() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        (tmp_root / "ai-stack/prompts").mkdir(parents=True)
        (tmp_root / "ai-stack/prompts/registry.yaml").write_text(
            "prompts:\n  - id: p1\n    template: 'TASK: {{ task_description }}'\n",
            encoding="utf-8",
        )
        opt = gepa.GepaOptimizer(repo_root=tmp_root)
        art = gepa.CompiledPromptArtifact(
            prompt_id="p1",
            baseline_score=0.6,
            compiled_score=1.0,
            score_lift=0.4,
            iterations=1,
            reflective_feedback=["Fix edge case"],
            compiled_template="TASK: {{ task_description }}\nReflective fix",
            timestamp="2026-10-12T00:00:00Z",
            gate_passed=True,
            metadata={"test": True},
        )
        saved = opt.save_compiled_artifact(art)
        loaded = opt.load_compiled_artifact("p1")
        assert loaded is not None
        assert loaded.prompt_id == "p1"
        assert loaded.baseline_score == 0.6
        assert loaded.compiled_score == 1.0
        assert loaded.score_lift == 0.4
        assert loaded.gate_passed is True
        assert loaded.reflective_feedback == ["Fix edge case"]
    print("  [PASS] test_compiled_artifact_serialization")


def test_cli_execution() -> None:
    cli_path = ROOT / "scripts" / "ai" / "aq-prompt-compile"
    assert cli_path.is_file(), f"CLI missing at {cli_path}"

    # Dry-run execution
    proc_dry = subprocess.run(
        [sys.executable, str(cli_path), "--dry-run", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_dry.returncode == 0, f"CLI dry-run failed: {proc_dry.stderr}"
    data_dry = json.loads(proc_dry.stdout)
    assert data_dry.get("ok") is True
    assert data_dry.get("gate_passed") is True
    assert data_dry.get("score_lift") > 0.0

    # Check-only execution
    proc_chk = subprocess.run(
        [sys.executable, str(cli_path), "--check-only", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_chk.returncode == 0, f"CLI check-only failed: {proc_chk.stderr}"
    data_chk = json.loads(proc_chk.stdout)
    assert data_chk.get("available") is True
    assert data_chk.get("gate_enforced") is True
    print("  [PASS] test_cli_execution")


def test_dashboard_and_qa_contract() -> None:
    route = ROOT / "dashboard" / "backend" / "api" / "routes" / "aistack.py"
    js = ROOT / "assets" / "dashboard.js"
    assert "_prompt_compile_health_summary" in route.read_text(encoding="utf-8")
    assert '"prompt_compile": await asyncio.to_thread(_prompt_compile_health_summary)' in route.read_text(encoding="utf-8")
    assert "· prompt compiler (GEPA)" in js.read_text(encoding="utf-8")
    print("  [PASS] test_dashboard_and_qa_contract")


def main() -> int:
    print("=== Testing Frontier FE-2b GEPA Build-Time Prompt Compile ===")
    test_optimizer_loads_base_template()
    test_reflection_feedback_synthesis()
    test_synthesize_candidate_template()
    test_strict_gating_rule_enforcement()
    test_non_dry_run_without_evaluator_refuses()
    test_compiled_artifact_serialization()
    test_cli_execution()
    test_dashboard_and_qa_contract()
    print("ALL 8 FIXTURES PASS: Frontier FE-2b GEPA prompt compile verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
