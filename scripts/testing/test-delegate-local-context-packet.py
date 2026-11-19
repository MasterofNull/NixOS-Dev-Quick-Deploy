#!/usr/bin/env python3
"""delegate-to-local attaches an aq-context-packet for repo files named in the prompt, and fails open.

Runs the shim against a dead llama port: preflight refuses (nothing is launched), but the attach line
is printed before that, which is what this checks.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIM = ROOT / "scripts/ai/delegate-to-local"


def run(prompt: str, **env: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        e = {**os.environ, "AQ_DELEGATION_DIR": d, "LLAMA_PORT": "1", **env}
        r = subprocess.run([str(SHIM), "--mode", "direct", "--no-consult", "--ignore-power-gate", "--prompt", prompt],
                           capture_output=True, text=True, env=e, timeout=90)
        return r.stdout + r.stderr


class ContextPacket(unittest.TestCase):
    def test_named_repo_file_gets_a_packet(self) -> None:
        self.assertIn("Context packet attached: 1 file(s)", run("review scripts/ai/aq-scoreboard briefly"))

    def test_no_repo_path_leaves_prompt_untouched(self) -> None:
        self.assertNotIn("Context packet attached", run("say hello; nothing/here/exists.py"))

    def test_kill_switch(self) -> None:
        self.assertNotIn("Context packet attached", run("review scripts/ai/aq-scoreboard", AQ_CONTEXT_PACKET="0"))

    def test_packet_tool_failure_fails_open(self) -> None:
        out = run("review scripts/ai/aq-scoreboard", PATH="/nonexistent")  # python3 missing: every helper fails
        self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()
