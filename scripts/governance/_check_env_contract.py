#!/usr/bin/env python3
"""Helper for gate_env_contract: checks a single file for undocumented env var names.

Usage: python3 _check_env_contract.py <file_path> <known_vars_newline_separated>

Prints one undocumented var name per line (empty output = all vars are documented).
"""
from __future__ import annotations

import re
import sys

SERVICE_PREFIXES = (
    "LLAMA", "EMBED", "HYBRID", "AIDB", "QDRANT", "REDIS", "POSTGRES",
    "SWITCHBOARD", "DASHBOARD", "RALPH", "AQ_QA", "REPO_ROOT",
    "RUNTIME_", "WORKFLOW_", "MODEL_", "AI_ROUTING", "SWB_",
)


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(0)
    path = sys.argv[1]
    known = set(sys.argv[2].split("\n")) if sys.argv[2] else set()
    try:
        text = open(path, errors="replace").read()
    except OSError:
        sys.exit(0)

    # Python patterns: os.environ.get("VAR") or os.environ["VAR"]
    py_vars = re.findall(r'os\.environ(?:\.get)?\(["\']([A-Z][A-Z0-9_]{2,})["\']', text)

    # Shell array expansions such as ${ARRAY[$key]} and ${!ARRAY[@]} are
    # internal variable references, not environment contract reads. Strip them
    # before scanning scalar shell references so uppercase associative arrays do
    # not create false undocumented-env warnings.
    shell_text = re.sub(r'\$\{!?[A-Z][A-Z0-9_]{2,}\[[^\]]*\][^}]*\}', ' ', text)

    # Shell patterns: ${VAR} or $VAR
    sh_vars = re.findall(r'\$\{?([A-Z][A-Z0-9_]{2,})\b', shell_text)
    # Shell export: export VAR=
    sh_exp  = re.findall(r'\bexport\s+([A-Z][A-Z0-9_]{2,})\s*=', shell_text)

    new_vars = set()
    for v in set(py_vars + sh_vars + sh_exp):
        if v in known:
            continue
        if any(v.startswith(p) for p in SERVICE_PREFIXES):
            new_vars.add(v)

    for v in sorted(new_vars):
        print(v)


if __name__ == "__main__":
    main()
