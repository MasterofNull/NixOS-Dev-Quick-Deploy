#!/usr/bin/env python3
"""Submit one tool call to the Foundation C execution-cell shadow adapter and
print the typed decision — a reusable CLI for exercising the confinement runner.

Purpose: replace fragile inline `python3 -c "..."` invocations nested inside
`sg -c "..."` (three quote layers that mangle newlines/special chars). Invoke with
plain argparse arguments instead — no nested quoting, no shell `${}` expansion, no
embedded control characters.

Usage (from repo root, as a member of the socket's client group):
    sg aq-execution-cell-clients -c \
      "cd $PWD; CAPABILITY_CELL_ADAPTER=1 python3 scripts/testing/cell-submit.py \
        --tool write_file --file README.md"

Notes:
  - --file MUST already exist in the repo tree at HEAD: R2 does not materialize
    not-yet-existing write targets (rebase_logical_path reports a missing target as
    path-escape). The write lands only in the isolated throwaway cell, never merged.
  - Exit code: 0 iff the runner decision is GREEN, else 1 (usable as a test gate).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(description="Submit a tool call to the execution-cell shadow adapter.")
    ap.add_argument("--tool", default="write_file", help="tool name (default: write_file)")
    ap.add_argument("--file", dest="file_path", default="README.md",
                    help="target logical path (must exist in the tree at HEAD)")
    ap.add_argument("--content", default=None,
                    help="write content (default: a unique r7green-<ts> marker line)")
    ap.add_argument("--adapter-dir", default="ai-stack/switchboard",
                    help="dir containing execution_cell_adapter.py (default: ai-stack/switchboard)")
    ap.add_argument("--json", action="store_true", help="print the full result dict as JSON")
    args = ap.parse_args()

    if args.adapter_dir not in sys.path:
        sys.path.insert(0, args.adapter_dir)
    import execution_cell_adapter as adapter  # noqa: E402

    content = args.content if args.content is not None else ("r7green-%d\n" % int(time.time()))
    result = adapter.submit_to_cell_default(args.tool, {"file_path": args.file_path, "content": content})

    d = dataclasses.asdict(result) if dataclasses.is_dataclass(result) else vars(result)
    rd = d.get("runner_decision")
    rd = rd if isinstance(rd, dict) else {}

    if args.json:
        print(json.dumps(d, default=str, indent=2))
    else:
        print("ADAPTER decision=%s reason=%s" % (d.get("decision"), d.get("reason")))
        print("RUNNER  decision=%s reason=%s stage=%s tree_proven=%s receipt_id=%s"
              % (rd.get("decision"), rd.get("reason"), rd.get("stage"),
                 rd.get("tree_proven_absent"), rd.get("receipt_id")))

    decision = (rd.get("decision") or d.get("decision") or "").lower()
    return 0 if decision == "green" else 1


if __name__ == "__main__":
    sys.exit(main())
