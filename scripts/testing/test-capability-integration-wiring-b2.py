#!/usr/bin/env python3
"""ci-7 batch 2: 20 high-value capabilities each get a static hint rule; 5 undiscoverable entries get a domain."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack/mcp-servers/hybrid-coordinator"))

from hints_engine import HintsEngine  # noqa: E402
from knowledge.static_rules import STATIC_RULES  # noqa: E402
from knowledge.token_manager import _tokenize  # noqa: E402

# (script, rule id, a natural query that must fire it)
WIRING = [
    ("aq-memory", "store_recall_facts_aq_memory", "please remember this decision"),
    ("aq-context-bootstrap", "bootstrap_minimal_context", "I want to start a task on the router"),
    ("aq-context-manage", "monitor_context_window", "how full is the context window"),
    ("aq-commit-facts", "extract_commit_facts", "extract facts from commits"),
    ("aq-health-spider", "sample_service_health", "check service health now"),
    ("aq-feedback-loop", "turn_feedback_into_loop", "turn feedback into a plan"),
    ("aq-runtime-diagnose", "diagnose_runtime_service", "the service is failing after boot"),
    ("aq-runtime-plan", "plan_runtime_incident", "we have a runtime incident"),
    ("aq-rsi-pending", "list_pending_rsi_repairs", "what is awaiting sign off"),
    ("aq-collab-round", "open_collab_round", "start a collab round"),
    ("aq-workflow-deviation", "submit_workflow_deviation", "record a workflow deviation"),
    ("aq-patterns", "analyze_recurring_patterns", "look at recurring failures"),
    ("aq-gaps", "show_top_gap_queries", "what are the knowledge gaps"),
    ("aq-report", "weekly_stack_report", "give me the weekly report"),
    ("aq-wiki", "query_wiki_section_first", "I need a subsystem overview"),
    ("aq-context-card", "recommend_context_card", "show a context card"),
    ("aq-rag-prewarm", "prewarm_local_rag", "prewarm rag for these prompts"),
    ("aq-index-logic-patterns", "index_logic_patterns", "index code patterns into aidb"),
    ("aq-operational-perspective", "operational_perspective_bundle", "get the operational perspective"),
    ("aq-reject", "reject_alert_with_reason", "reject the alert as noise"),
]


def fired(query):
    engine = HintsEngine.__new__(HintsEngine)
    return {h.id for h in engine._hints_from_static_rules(_tokenize(query))}


def test_each_capability_has_firing_rule():
    rules = {r["id"]: r for r in STATIC_RULES}
    assert len(rules) == len(STATIC_RULES), "duplicate rule ids"
    for script, rid, query in WIRING:
        assert (ROOT / "scripts/ai" / script).exists(), script
        assert script in rules[rid]["snippet"], (script, rid)
        assert rid in fired(query), (rid, query)


def test_undiscoverable_entries_in_domain():
    dom = json.loads((ROOT / "config/progressive-disclosure-domains.json").read_text())["domains"]["external-tool-packs"]
    text = json.dumps(dom)
    for cid in ("github-mcp-readonly", "semgrep-mcp", "nixos-static-analysis", "osint-research-store",
                "identity-kernel-service"):
        assert cid in text, cid


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("PASS: ci-7 batch 2 wiring (20 hint rules, external-tool-packs domain)")


if __name__ == "__main__":
    main()
