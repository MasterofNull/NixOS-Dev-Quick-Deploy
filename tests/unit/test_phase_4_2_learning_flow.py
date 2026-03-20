"""
Phase 4.2 validation tests for query -> agent -> storage -> learning flow.

These checks pin the HTTP endpoint contract used by the new smoke validation.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTTP_SERVER = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py"
SMOKE_SCRIPT = ROOT / "scripts" / "testing" / "smoke-query-agent-storage-learning.sh"


def test_hybrid_http_server_exposes_phase_4_2_routes():
    source = HTTP_SERVER.read_text(encoding="utf-8")
    assert 'http_app.router.add_post("/query", handle_query)' in source
    assert 'http_app.router.add_post("/feedback", handle_feedback)' in source
    assert 'http_app.router.add_get("/learning/stats", handle_learning_stats)' in source
    assert 'http_app.router.add_post("/learning/export", handle_learning_export)' in source


def test_phase_4_2_smoke_script_checks_query_feedback_learning_and_report():
    script = SMOKE_SCRIPT.read_text(encoding="utf-8")
    assert "/query" in script
    assert "/feedback" in script
    assert "/learning/stats" in script
    assert "/learning/export" in script
    assert "aq-report --format=json" in script
