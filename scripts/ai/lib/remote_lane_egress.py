"""Remote Lane Egress Rules Table (DEC-S4 / W2-S7).

Rules-only egress evaluation: adds friction only (flag, hold), never relaxes a deny,
and maintains strict per-(lane, reason) rate budgets with uncollapsible high-signal alerts.
No runtime dependency on aq-decide, but matches contract return format.
"""
from __future__ import annotations

import collections
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = REPO_ROOT / "config" / "remote-lane-egress.json"

LANES = frozenset({
    "claude", "codex", "antigravity", "agy", "gemini-legacy",
    "switchboard", "coordinator", "mcp", "other"
})

CLOSED_REASON_CODES = frozenset({
    "EGR_NOVEL_DOMAIN", "EGR_RAW_IP", "EGR_PUNYCODE", "EGR_SNI_MISMATCH",
    "EGR_CROSS_LANE", "EGR_LEGACY_LANE", "EGR_UNATTRIBUTED", "EGR_NEW_LANE",
    "EGR_VOLUME", "EGR_BYPASS", "EGR_AUTH_CRITICAL_ALERT_ONLY",
    "RULE_ALLOWLISTED", "RULE_HARD_DENY", "LOW_CONF", "ERROR"
})

HIGH_SIGNAL_REASONS = frozenset({
    "EGR_RAW_IP", "EGR_SNI_MISMATCH", "EGR_PUNYCODE", "EGR_UNATTRIBUTED"
})

IP_REGEX = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


class EgressRulesEngine:
    def __init__(self, config_path: Optional[Path] = None):
        p = config_path or DEFAULT_CONFIG
        self.cfg = json.loads(p.read_text()) if p.exists() else {}
        self.lanes = self.cfg.get("lanes", {})
        self.budgets = self.cfg.get("rate_budgets", {})
        self.max_hold = self.budgets.get("hold_per_hour", 5)
        self.max_flag = self.budgets.get("flag_per_hour", 20)
        # Tracking: (lane, reason) -> list of timestamps
        self._history: Dict[Tuple[str, str], List[float]] = collections.defaultdict(list)

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate an egress connection attempt.

        Payload schema:
          lane: str (enum)
          dest_host: str
          dest_port: int
          raw_ip: bool
          punycode: bool
          sni_mismatch: bool
          unattributed: bool
          bytes_out: int (optional)
        """
        # Validate no free text fields
        for k in payload:
            if k not in {
                "lane", "dest_host", "dest_port", "raw_ip", "punycode",
                "sni_mismatch", "unattributed", "bytes_out", "rate", "label_count"
            }:
                raise ValueError(f"Unexpected or free-text feature: {k}")

        lane = payload.get("lane", "other")
        if lane not in LANES:
            lane = "other"

        dest_host = payload.get("dest_host", "").lower()
        raw_ip = bool(payload.get("raw_ip") or IP_REGEX.match(dest_host))
        punycode = bool(payload.get("punycode") or dest_host.startswith("xn--"))
        sni_mismatch = bool(payload.get("sni_mismatch"))
        unattributed = bool(payload.get("unattributed") or lane == "other")

        now = time.time()
        # High-signal checks (Never digest-collapsed)
        if raw_ip:
            return self._verdict(lane, "hold", "EGR_RAW_IP", now, is_high_signal=True)
        if sni_mismatch:
            return self._verdict(lane, "hold", "EGR_SNI_MISMATCH", now, is_high_signal=True)
        if punycode:
            return self._verdict(lane, "flag", "EGR_PUNYCODE", now, is_high_signal=True)
        if unattributed:
            return self._verdict(lane, "hold", "EGR_UNATTRIBUTED", now, is_high_signal=True)

        # Check lane allowlist
        lane_spec = self.lanes.get(lane, {})
        allowlist = set(lane_spec.get("allowlist", []))
        if dest_host in allowlist:
            return {
                "outcome": "none",
                "reason_code": "RULE_ALLOWLISTED",
                "action": "none",
                "collapsed": False,
            }

        # Check cross-lane: is it on another lane's allowlist?
        for other_lane, spec in self.lanes.items():
            if other_lane != lane and dest_host in set(spec.get("allowlist", [])):
                return self._verdict(lane, "flag", "EGR_CROSS_LANE", now, is_high_signal=False)

        # Legacy lane check
        if lane == "gemini-legacy":
            return self._verdict(lane, "hold", "EGR_LEGACY_LANE", now, is_high_signal=False)

        # Novel domain for this lane
        action = "flag"
        if lane in {"coordinator", "switchboard"}:
            action = "flag"
        return self._verdict(lane, action, "EGR_NOVEL_DOMAIN", now, is_high_signal=False)

    def _verdict(self, lane: str, action: str, reason: str, now: float, is_high_signal: bool) -> Dict[str, Any]:
        key = (lane, reason)
        window = 3600.0
        # Clean history
        self._history[key] = [t for t in self._history[key] if now - t < window]

        if is_high_signal:
            self._history[key].append(now)
            return {
                "outcome": "flag" if action == "flag" else "hold",
                "action": action,
                "reason_code": reason,
                "collapsed": False,
            }

        limit = self.max_hold if action == "hold" else self.max_flag
        count = len(self._history[key])
        if count >= limit:
            return {
                "outcome": "none",
                "action": "none",
                "reason_code": reason,
                "collapsed": True,
            }

        self._history[key].append(now)
        return {
            "outcome": "flag" if action == "flag" else "hold",
            "action": action,
            "reason_code": reason,
            "collapsed": False,
        }
