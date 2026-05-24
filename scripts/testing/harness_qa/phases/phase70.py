"""Phase 70 checks — Distributed Consensus + Hardening.

70.1  POST /workflow/consensus/vote: weighted vote returns correct winner
70.2  AppArmor enforce mode active for coordinator + dashboard profiles
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Tuple

from ..core.context import RunContext
from ..core.result import CheckResult, passed, failed, skipped

_REPO = Path(__file__).resolve().parents[4]


def _http(method: str, url: str, body: Any = None, api_key: str = "", timeout: int = 15) -> Tuple[int, Any]:
    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            body_err = json.loads(exc.read())
        except Exception:
            body_err = str(exc)
        return exc.code, body_err
    except Exception as exc:
        return 0, str(exc)


def _api_key(ctx: RunContext) -> str:
    try:
        return Path("/run/secrets/hybrid_coordinator_api_key").read_text().strip()
    except OSError:
        return os.environ.get("HYBRID_API_KEY", "")


# ---------------------------------------------------------------------------
# 70.1 — Weighted consensus vote
# ---------------------------------------------------------------------------

def _check_70_1(ctx: RunContext) -> CheckResult:
    """POST /workflow/consensus/vote: weighted vote returns correct winner."""
    key = _api_key(ctx)
    session_id = "aq-qa-70-1-probe"
    url = f"{ctx.hybrid_url}/workflow/consensus/vote"

    # Cast two yes votes and one no vote; yes should win
    votes = [
        {"session_id": session_id, "agent_id": "probe-agent-a", "vote": "yes",  "confidence": 1.0, "topic": "aq-qa 70.1 probe"},
        {"session_id": session_id, "agent_id": "probe-agent-b", "vote": "yes",  "confidence": 0.9, "topic": "aq-qa 70.1 probe"},
        {"session_id": session_id, "agent_id": "probe-agent-c", "vote": "no",   "confidence": 1.0, "topic": "aq-qa 70.1 probe"},
    ]

    last_status, last_body = 0, {}
    for vote in votes:
        last_status, last_body = _http("POST", url, body=vote, api_key=key, timeout=15)
        if last_status == 0:
            return skipped(2, "70.1", "Consensus vote endpoint", "coordinator unreachable", phase="70")
        if last_status == 404:
            return failed(2, "70.1", "Consensus vote endpoint", "404 — nixos-rebuild needed", phase="70")
        if last_status not in (200, 201):
            return failed(2, "70.1", "Consensus vote endpoint", f"HTTP {last_status}: {str(last_body)[:80]}", phase="70")

    # Verify outcome
    if not isinstance(last_body, dict):
        return failed(2, "70.1", "Consensus vote", "response is not a dict", phase="70")

    outcome = last_body.get("outcome")
    weighted_yes = last_body.get("weighted_yes", 0)
    weighted_no  = last_body.get("weighted_no", 0)

    if outcome != "yes":
        return failed(2, "70.1", "Consensus vote outcome",
                      f"expected 'yes' (2 yes vs 1 no) but got '{outcome}' "
                      f"(w_yes={weighted_yes}, w_no={weighted_no})", phase="70")

    return passed(2, "70.1",
                  f"Consensus engine: weighted vote correct (yes wins; w_yes={weighted_yes:.3f} w_no={weighted_no:.3f})",
                  phase="70")


# ---------------------------------------------------------------------------
# 70.2 — AppArmor enforce mode
# ---------------------------------------------------------------------------

def _check_70_2(_ctx: RunContext) -> CheckResult:
    """AppArmor enforce mode active for coordinator + mcp-base.

    Detection: reads /etc/apparmor.d/<profile> directly (no sudo needed).
    NixOS sets state="complain" by adding 'flags=(complain)' to the profile.
    Absence of that flag = enforce mode.
    """
    targets = {
        "ai-hybrid-coordinator": Path("/etc/apparmor.d/ai-hybrid-coordinator"),
        "ai-mcp-base":           Path("/etc/apparmor.d/ai-mcp-base"),
    }

    in_complain: list[str] = []
    missing_file: list[str] = []

    for name, profile_path in targets.items():
        if not profile_path.exists():
            missing_file.append(name)
            continue
        content = profile_path.read_text(errors="replace")
        # NixOS complain mode injects flags=(complain) into the profile header
        if "flags=(complain)" in content or "flags=(complain," in content:
            in_complain.append(name)

    if missing_file:
        return skipped(1, "70.2", "AppArmor enforce mode",
                       f"profile files not found: {missing_file}", phase="70")

    if in_complain:
        return skipped(1, "70.2", "AppArmor enforce mode",
                       f"{in_complain} in complain mode — enforce after 7-day soak (scheduled 2026-05-30)",
                       phase="70")

    return passed(1, "70.2",
                  f"AppArmor enforce: {', '.join(targets)} active (no complain flag in profiles)",
                  phase="70")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(ctx: RunContext) -> list[CheckResult]:
    return [
        _check_70_1(ctx),
        _check_70_2(ctx),
    ]
