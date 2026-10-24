#!/usr/bin/env python3
"""
Unit tests for aq-decide DEC-S5 (learned head gates) and DEC-S6 (I3/I4 shadow routing).
"""

import sys
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "ai" / "lib"))

from aq_decide import validate_head_gates, shadow_evaluate_rag_route, shadow_evaluate_retry_escalate


def test_validate_head_gates():
    # Test Gate 1: At least 150 effective examples per class (300 total for binary choice)
    insufficient_samples = {"human": 50, "outcome": 20, "teacher": 100}
    res, reason = validate_head_gates("approval_grant", insufficient_samples)
    assert res is False
    assert "insufficient_effective_examples" in reason

    # Test Gate 1 pass
    sufficient_samples = {"human": 200, "outcome": 250, "teacher": 500} # effective = 200 + 125 = 325 >= 300
    res, reason = validate_head_gates("approval_grant", sufficient_samples)
    assert res is True
    assert reason is None


def test_shadow_evaluate_rag_route():
    # Query with code symbol should route to best-practices / skills-patterns
    route = shadow_evaluate_rag_route("How do I implement UnixSite in peer_identity.py?")
    assert route in ("skills-patterns", "best-practices", "code-context")

    # General error should route to error-solutions
    route_err = shadow_evaluate_rag_route("Traceback: KeyError 'client_class' in authz.py")
    assert route_err == "error-solutions"


def test_shadow_evaluate_retry_escalate():
    # Attempt 1 -> retry
    decision = shadow_evaluate_retry_escalate(attempt=1, error_class="network_timeout")
    assert decision == "retry"

    # Attempt 3 -> escalate per Rule 6
    decision_max = shadow_evaluate_retry_escalate(attempt=3, error_class="network_timeout")
    assert decision_max == "escalate"

    # Fatal security violation -> escalate immediately
    decision_sec = shadow_evaluate_retry_escalate(attempt=1, error_class="security_policy_deny")
    assert decision_sec == "escalate"


if __name__ == "__main__":
    test_validate_head_gates()
    test_shadow_evaluate_rag_route()
    test_shadow_evaluate_retry_escalate()
    print("ALL PASS")
