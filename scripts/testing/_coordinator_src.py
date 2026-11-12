#!/usr/bin/env python3
"""Read hybrid-coordinator source files for static wiring tests.

http_server.py was deleted (e67f4289d) after its code moved into domain modules, so
static tests name the module that owns each behaviour; a missing file fails loudly.
"""

from pathlib import Path

HC = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "hybrid-coordinator"


def read(*rels: str) -> str:
    """Concatenate the named files (paths relative to hybrid-coordinator)."""
    return "\n".join((HC / rel).read_text(encoding="utf-8") for rel in rels)
