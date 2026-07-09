"""Event envelope schema for the harness A2A event log (WS2).

One signed, idempotent envelope type carries every agent-to-agent event.
PULSE.log and RESUME.json become read-only PROJECTIONS of this append-only
log — no agent writes those files directly, so the clobber class dies.
"""

from .envelope import Envelope, new_event_id  # noqa: F401
