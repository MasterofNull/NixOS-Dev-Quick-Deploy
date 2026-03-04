#!/usr/bin/env python3
"""Regression smoke tests for shared.tool_security_auditor."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def _load_auditor():
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "ai-stack" / "mcp-servers"))
    from shared.tool_security_auditor import ToolSecurityAuditor  # type: ignore
    return ToolSecurityAuditor


def main() -> int:
    ToolSecurityAuditor = _load_auditor()
    with tempfile.TemporaryDirectory(prefix="tool-auditor-test-") as td:
        td_path = Path(td)
        policy_path = td_path / "policy.json"
        cache_path = td_path / "cache.json"
        policy_path.write_text(
            json.dumps(
                {
                    "version": "2.0",
                    "blocked_tools": ["danger_tool"],
                    "blocked_reason_keywords": ["shell", "exec"],
                }
            ),
            encoding="utf-8",
        )

        auditor = ToolSecurityAuditor(
            service_name="test",
            policy_path=policy_path,
            cache_path=cache_path,
            enabled=True,
            enforce=True,
            cache_ttl_hours=24,
        )
        safe_meta_v1 = {
            "endpoint": "/hints",
            "reason": "query assistance",
            "manifest": {"name": "hints", "version": "1.0.0"},
        }
        d1 = auditor.audit_tool("hints", safe_meta_v1)
        assert d1["safe"] is True and d1["cached"] is False and d1["first_seen"] is True

        d2 = auditor.audit_tool("hints", safe_meta_v1)
        assert d2["safe"] is True and d2["cached"] is True and d2["first_seen"] is False

        # Cache key must change when manifest/version changes.
        safe_meta_v2 = {
            "endpoint": "/hints",
            "reason": "query assistance",
            "manifest": {"name": "hints", "version": "1.0.1"},
        }
        d3 = auditor.audit_tool("hints", safe_meta_v2)
        assert d3["safe"] is True and d3["cached"] is False and d3["first_seen"] is True

        blocked_raised = False
        try:
            auditor.audit_tool("danger_tool", {"endpoint": "/exec", "reason": "run shell command"})
        except PermissionError:
            blocked_raised = True
        assert blocked_raised, "danger_tool should be blocked in enforce mode"

        # Non-enforcing mode should return unsafe decision without raising.
        auditor_relaxed = ToolSecurityAuditor(
            service_name="test",
            policy_path=policy_path,
            cache_path=cache_path,
            enabled=True,
            enforce=False,
            cache_ttl_hours=24,
        )
        d4 = auditor_relaxed.audit_tool("danger_tool", {"endpoint": "/exec", "reason": "run shell command"})
        assert d4["safe"] is False and d4["approved"] is False

    print("PASS: tool security auditor regression checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
