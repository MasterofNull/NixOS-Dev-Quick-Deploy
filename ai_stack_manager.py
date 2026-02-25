#!/usr/bin/env python3
"""
Legacy shim for the retired ai_stack_manager bridge.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    payload = {
        "status": "deprecated",
        "message": (
            "ai_stack_manager.py has been retired. "
            "Use declarative systemd services and scripts/ai-stack-manage.sh."
        ),
    }
    print(json.dumps(payload))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
