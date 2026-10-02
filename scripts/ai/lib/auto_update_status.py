"""Read-only projection of aq-auto-update state (status.json + halted/pending-reboot markers).

Shared by `aq-rsi status` and the dashboard health route. Unknown != healthy: an unreadable or
non-object status.json yields state "unknown", never "ok".
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_STATE_DIR = "/var/lib/aq-auto-update"


def state_dir() -> Path:
    return Path(os.getenv("AQ_AUTO_UPDATE_STATE_DIR", DEFAULT_STATE_DIR))


def read_status(sdir: Path | None = None) -> dict:
    sdir = sdir or state_dir()
    if not sdir.is_dir():
        return {"state": "not_enabled", "summary": "auto-update: not enabled"}
    halted = (sdir / "halted").exists()
    try:
        raw = json.loads((sdir / "status.json").read_text())
        if not isinstance(raw, dict):
            raise ValueError("status.json is not an object")
    except (OSError, ValueError) as exc:
        return {"state": "unknown", "halted": halted, "error": f"status.json unreadable: {exc}",
                "summary": f"auto-update: UNKNOWN (status.json unreadable: {exc})"}
    moved = raw.get("versions_moved")
    hours, sla = raw.get("pending_reboot_hours"), raw.get("reboot_sla_hours")
    pending = bool(raw.get("pending_reboot"))
    breach = bool(pending and isinstance(hours, (int, float)) and isinstance(sla, (int, float)) and hours > sla)
    rollback = bool(raw.get("rollback"))
    out = {
        "outcome": raw.get("outcome"), "started_at": raw.get("started_at"), "reason": raw.get("reason", ""),
        "rollback": rollback, "halted": halted, "versions_moved": len(moved) if isinstance(moved, list) else 0,
        "pending_reboot": pending, "pending_reboot_hours": hours, "reboot_sla_hours": sla,
        "reboot_breach": breach, "booted_kernel": raw.get("booted_kernel"),
        "installed_kernel": raw.get("installed_kernel"),
    }
    out["state"] = "attention" if (rollback or halted or breach) else "ok"
    return out


def format_lines(s: dict) -> list[str]:
    if s["state"] in ("not_enabled", "unknown"):
        return [s["summary"]] + (["auto-update halted: YES"] if s.get("halted") else [])
    lines = [f"auto-update: {s['state'].upper()} last run {s['outcome']} at {s['started_at']} "
             f"versions_moved={s['versions_moved']} rollback={'YES' if s['rollback'] else 'no'} "
             f"halted={'YES' if s['halted'] else 'no'}"]
    if s["pending_reboot"]:
        tag = " BREACH" if s["reboot_breach"] else ""
        lines.append(f"auto-update pending reboot: {s['pending_reboot_hours']}h of {s['reboot_sla_hours']}h SLA{tag}")
    else:
        lines.append("auto-update pending reboot: none")
    return lines
