#!/usr/bin/env python3
"""
Sync workflow sessions from coordinator API to executor's file.

This bridges the gap between the hybrid coordinator (which keeps sessions
in memory) and the workflow executor (which reads from a JSON file).
"""

import json
import sys
from pathlib import Path
import httpx

COORDINATOR_URL = "http://127.0.0.1:8003"
SESSIONS_FILE = Path.home() / ".local/share/nixos-ai-stack/hybrid/workflow-sessions.json"


def fetch_session(session_id: str) -> dict:
    """Fetch a session from the coordinator API."""
    url = f"{COORDINATOR_URL}/workflow/run/{session_id}?replay=true"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()


def load_sessions_file() -> dict:
    """Load existing sessions from file."""
    if not SESSIONS_FILE.exists():
        SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        return {}

    try:
        return json.loads(SESSIONS_FILE.read_text())
    except Exception:
        return {}


def save_sessions_file(sessions: dict):
    """Save sessions to file."""
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SESSIONS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(sessions, indent=2, sort_keys=True))
    tmp.replace(SESSIONS_FILE)


def main():
    if len(sys.argv) < 2:
        print("Usage: sync-workflow-sessions.py <session_id>")
        sys.exit(1)

    session_id = sys.argv[1]

    print(f"Fetching session {session_id} from coordinator...")
    try:
        session = fetch_session(session_id)
    except Exception as e:
        print(f"Error fetching session: {e}")
        sys.exit(1)

    print(f"Loading sessions file: {SESSIONS_FILE}")
    sessions = load_sessions_file()

    print(f"Adding session to file...")
    sessions[session_id] = session

    print(f"Saving to {SESSIONS_FILE}")
    save_sessions_file(sessions)

    print(f"✓ Session synced successfully!")
    print(f"  Status: {session.get('status')}")
    print(f"  Phase: {session.get('phase_state', [{}])[0].get('id')}")
    print(f"  File: {SESSIONS_FILE}")


if __name__ == "__main__":
    main()
