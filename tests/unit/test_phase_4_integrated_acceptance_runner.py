"""
Static contract checks for the consolidated Phase 4 acceptance runner.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "testing" / "smoke-phase-4-integrated-workflows.sh"


def test_phase_4_runner_executes_all_phase_smokes_and_writes_report():
    script = RUNNER.read_text(encoding="utf-8")
    assert "smoke-deployment-monitoring-alerting.sh" in script
    assert "smoke-query-agent-storage-learning.sh" in script
    assert "smoke-security-audit-compliance.sh" in script
    assert "phase-4-acceptance-report.json" in script
    assert '"phase": "4"' in script
    assert 'jq -e \'.status == "passed"\'' in script
