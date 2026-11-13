"""instance_label — build the persona instance label `Simurg@<lane>/<model>#<session>`.

SSOT for the format: canon/blocks/persona.md. Provenance is per instance; the label
never grants independence, so reviewer/author checks still compare lanes.
Kill switch: PERSONA=0 returns the plain `<lane>/<model>` identity (no prefix, no session).
"""

from __future__ import annotations

import os
import re

PERSONA_NAME = "Simurg"
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _clean(value: str, fallback: str) -> str:
    return _UNSAFE.sub("-", (value or "").strip()).strip("-") or fallback


def build_label(lane: str, model: str = "", session: str = "") -> str:
    lane_s = _clean(lane.lower(), "unknown")
    ident = f"{lane_s}/{_clean(model, 'unknown')}"
    if os.environ.get("PERSONA", "1") == "0":
        return ident
    sess = _clean(session, "")[:8]
    return f"{PERSONA_NAME}@{ident}" + (f"#{sess}" if sess else "")
