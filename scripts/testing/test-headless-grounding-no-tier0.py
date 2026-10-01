#!/usr/bin/env python3
"""
Test that headless grounding does not contain legacy interactive instructions.

Verifies that:
1. Headless agents (codex, gemini) do NOT see "re-run tier0 gate"
2. Headless agents do NOT see "Max 4 read_file per slice"
3. Headless agents do NOT see "validate_before_commit"
4. Interactive agents (claude, local) still see the full workflow
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
HARNESS_GROUNDING = REPO_ROOT / "scripts" / "ai" / "lib" / "harness-grounding.sh"


def get_grounding(agent_name):
    """Get grounding text for an agent."""
    cmd = f"""
    source {HARNESS_GROUNDING}
    harness_grounding {agent_name}
    """
    result = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.stdout + result.stderr


def test_headless_no_tier0_gate():
    """Headless agents should NOT see 're-run tier0 gate' instruction."""
    for agent in ["codex", "gemini"]:
        grounding = get_grounding(agent)
        assert "re-run tier0 gate" not in grounding, \
            f"{agent} headless grounding contains legacy 're-run tier0 gate': {grounding[-500:]}"
    print("✓ test_headless_no_tier0_gate passed")


def test_headless_no_max_4_read_file():
    """Headless agents should NOT see 'Max 4 read_file per slice' limit."""
    for agent in ["codex", "gemini"]:
        grounding = get_grounding(agent)
        assert "Max 4 read_file" not in grounding, \
            f"{agent} headless grounding contains legacy 'Max 4 read_file': {grounding[-500:]}"
    print("✓ test_headless_no_max_4_read_file passed")


def test_headless_no_validate_before_commit():
    """Headless agents should NOT see 'validate_before_commit' tool."""
    for agent in ["codex", "gemini"]:
        grounding = get_grounding(agent)
        # In the Workflow Phases section for headless, there should be no validate_before_commit
        # (though it might appear in other sections like "Tool Result Messages" as [local-inference])
        phases_start = grounding.find("## Workflow Phases")
        if phases_start != -1:
            phases_section = grounding[phases_start:phases_start+500]
            assert "validate_before_commit" not in phases_section, \
                f"{agent} headless workflow phases should not reference validate_before_commit: {phases_section}"
    print("✓ test_headless_no_validate_before_commit passed")


def test_interactive_still_has_full_workflow():
    """Interactive agents (claude) should still see the full workflow with all instructions."""
    claude_grounding = get_grounding("claude")
    # Claude should still have the interactive workflow phases
    assert "## Workflow Phases" in claude_grounding, "Claude missing Workflow Phases section"
    # Claude should see either the full interactive version or at least some workflow guidance
    assert ("ORIENT" in claude_grounding or "git_commit" in claude_grounding), \
        "Claude grounding missing core workflow context"
    print("✓ test_interactive_still_has_full_workflow passed")


def test_headless_has_delegate_mode_block():
    """Headless agents should start with explicit DELEGATE MODE block."""
    for agent in ["codex", "gemini"]:
        grounding = get_grounding(agent)
        assert "=== DELEGATE MODE (headless) ===" in grounding, \
            f"{agent} missing DELEGATE MODE block"
        assert "Do NOT run aq-resume/aq-session-start/tier0" in grounding, \
            f"{agent} missing tier0 warning in DELEGATE MODE"
    print("✓ test_headless_has_delegate_mode_block passed")


def test_headless_has_custom_workflow_phases():
    """Headless agents should have custom 'Workflow Phases (Headless Slice)' section."""
    for agent in ["codex", "gemini"]:
        grounding = get_grounding(agent)
        assert "## Workflow Phases (Headless Slice)" in grounding, \
            f"{agent} missing custom headless workflow phases section"
        assert "Headless agents do NOT run tier0 gates or commit" in grounding, \
            f"{agent} missing headless-specific guidance"
    print("✓ test_headless_has_custom_workflow_phases passed")


if __name__ == "__main__":
    try:
        test_headless_no_tier0_gate()
        test_headless_no_max_4_read_file()
        test_headless_no_validate_before_commit()
        test_interactive_still_has_full_workflow()
        test_headless_has_delegate_mode_block()
        test_headless_has_custom_workflow_phases()
        print("\n✓ All grounding tests passed")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
