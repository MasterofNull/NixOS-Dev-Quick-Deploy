"""
slot_scheduler — Poll /slots until llama.cpp slot is free before submitting.

Phase 74A — extracted from run_direct inline Python heredoc in delegate-to-local.
All modes that submit directly to llama.cpp should call wait_for_slot() first.
"""

import json
import time
import urllib.request


def wait_for_slot(base_url: str, timeout_secs: int) -> None:
    """Block until /slots[0].is_processing is False, or timeout expires.

    Args:
        base_url:     llama.cpp base URL, e.g. "http://127.0.0.1:8080"
        timeout_secs: max seconds to wait before giving up and submitting anyway

    On timeout or /slots unavailability, returns without raising — the caller
    submits the request and lets the server's own queue handle saturation.
    """
    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(f"{base_url}/slots")
            with urllib.request.urlopen(req, timeout=5) as resp:
                slots = json.loads(resp.read())
                if not slots[0].get("is_processing", True):
                    return  # slot free — proceed
        except Exception:
            return  # /slots unavailable — submit anyway
        time.sleep(3)
    # Deadline exceeded — submit anyway; SLOT_WAIT_S in caller is the safety net
