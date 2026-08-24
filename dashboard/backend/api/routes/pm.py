"""PM Progress Dashboard — the live backend for `assets/aqos-progress-tracker.html`.

Implements `GET /api/pm/progress`: the program-wide PM rollup, projected from
read-only git evidence (commits + freeze records + activation grants — never
hand-typed) by `scripts/ai/aq-pm-tracker --all-json`, per the standard in
`.agents/plans/pm-tracker-standard/DESIGN.md`. Shallow or unavailable history
is returned as explicit degraded provenance; a dashboard request never repairs
or changes repository state.

Deliberately SHELLS OUT rather than importing `aq-pm-tracker`'s project()
functions directly. Same posture as `approvals.py`'s module docstring
("avoid importing anything at module load that needs deps absent from the
dashboard's BARE python"): the CLI runs under system python (which has
whatever deps its git/subprocess plumbing needs), while the dashboard
backend's own venv is a narrower surface. Shelling out keeps this route free
of any dependency on the CLI's runtime beyond "the file exists and runs."
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# The dashboard runs sandboxed (ProtectSystem) under a bare python whose PATH has
# systemctl but NOT git, and where the CLI's `#!/usr/bin/env python3` shebang
# cannot resolve (/usr/bin/env hidden). So invoke aq-pm-tracker with an EXPLICIT
# interpreter (sys.executable — the CLI is stdlib-only) and an augmented PATH so
# its bounded read-only git/systemctl/aq-event evidence sources resolve.
_TRACKER_ENV = {
    **os.environ,
    "PATH": "/run/current-system/sw/bin:/run/wrappers/bin:" + os.environ.get("PATH", ""),
}

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TRACKER_CLI = _REPO_ROOT / "scripts" / "ai" / "aq-pm-tracker"
_SUBPROCESS_TIMEOUT_SECONDS = 30

router = APIRouter(tags=["pm"])


@router.get("/pm/progress")
async def get_pm_progress() -> dict:
    """Live program-management rollup for the dashboard's Program tab.

    Returns the `aq-pm-tracker --all-json` aggregate verbatim:
    `{generated_at, plans: [{id, title, rollup_pct, shipped, total, phases,
    items: [{id, name, phase, status, pct}]}], program_rollup_pct}`.
    Every field is PROJECTED (git log + aq-event grants + freeze records) —
    no hand-maintained status anywhere in this path.
    """
    if not _TRACKER_CLI.is_file():
        raise HTTPException(status_code=503, detail="aq-pm-tracker CLI not found")

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(_TRACKER_CLI),
            "--all-json",
            cwd=str(_REPO_ROOT),
            env=_TRACKER_ENV,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_SUBPROCESS_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.error("aq-pm-tracker --all-json timed out after %ss", _SUBPROCESS_TIMEOUT_SECONDS)
        raise HTTPException(status_code=504, detail="pm-tracker projection timed out")
    except Exception as exc:  # noqa: BLE001 — surface as a 500, log the real cause
        logger.error("aq-pm-tracker --all-json failed to launch: %s", exc)
        raise HTTPException(status_code=500, detail="pm-tracker projection failed to launch")

    if proc.returncode != 0:
        logger.error(
            "aq-pm-tracker --all-json exited %s: %s",
            proc.returncode,
            stderr.decode("utf-8", errors="replace")[:500],
        )
        raise HTTPException(status_code=500, detail="pm-tracker projection failed")

    try:
        data = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("aq-pm-tracker --all-json emitted invalid JSON: %s", exc)
        raise HTTPException(status_code=500, detail="pm-tracker projection returned invalid JSON")

    return data
