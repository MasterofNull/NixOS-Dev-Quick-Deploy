"""
slot_scheduler — Poll /slots until llama.cpp slot is free before submitting.

Phase 74A — extracted from run_direct inline Python heredoc in delegate-to-local.
All modes that submit directly to llama.cpp should call wait_for_slot() first.
"""

import json
import time
import urllib.request


class SlotWaitTimeout(TimeoutError):
    """Raised when the local inference slot does not become available."""


def wait_for_slot(base_url: str, timeout_secs: int) -> None:
    """Block until /slots[0].is_processing is False, or timeout expires.

    Args:
        base_url:     llama.cpp base URL, e.g. "http://127.0.0.1:8080"
        timeout_secs: max seconds to wait before failing as queued/busy

    On timeout or /slots unavailability, raises SlotWaitTimeout. Callers must
    surface queue/busy state instead of submitting uncoordinated extra load.
    """
    last_observation = "no slot observation yet"
    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(f"{base_url}/slots")
            with urllib.request.urlopen(req, timeout=5) as resp:
                slots = json.loads(resp.read())
                if slots and not slots[0].get("is_processing", True):
                    return  # slot free — proceed
                last_observation = "slot busy"
        except Exception as exc:
            last_observation = f"/slots unavailable: {type(exc).__name__}: {exc}"
        time.sleep(3)
    raise SlotWaitTimeout(f"local inference slot unavailable after {timeout_secs}s ({last_observation})")
