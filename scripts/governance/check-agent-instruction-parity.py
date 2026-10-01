#!/usr/bin/env python3
"""check-agent-instruction-parity — always-on agent files stay complete and small.

Reads canon/canon.yaml. For every file listed under `agent_files.files`:
  * each canon block that targets the file must have its begin/end region present
    (content drift is canon-compile.py --check's job; this gate catches a block
    that was never wired in or whose markers were deleted);
  * exactly one <!-- lane:begin --> ... <!-- lane:end --> region must exist and
    stay within `agent_files.lane_budget_bytes`;
  * total size must stay within `agent_files.budget_bytes`.
Exit 1 on any violation. Budgets are bounded always-on prompt cost, not style.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent.parent
LANE_BEGIN, LANE_END = "<!-- lane:begin -->", "<!-- lane:end -->"


def _target_path(t) -> str:
    return t if isinstance(t, str) else t["path"]


def check(repo: Path) -> list[str]:
    manifest = yaml.safe_load((repo / "canon" / "canon.yaml").read_text(encoding="utf-8"))
    cfg = manifest.get("agent_files") or {}
    budget = int(cfg.get("budget_bytes", 24000))
    lane_budget = int(cfg.get("lane_budget_bytes", 8000))
    problems: list[str] = []
    for rel in cfg.get("files", []):
        path = repo / rel
        if not path.exists():
            problems.append(f"{rel}: file missing")
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        if len(raw) > budget:
            problems.append(f"{rel}: {len(raw)} bytes exceeds budget {budget}")
        for name, spec in manifest["blocks"].items():
            if rel not in {_target_path(t) for t in spec["targets"]}:
                continue
            if f"<!-- canon:begin {name} -->" not in text or f"<!-- canon:end {name} -->" not in text:
                problems.append(f"{rel}: required canon block '{name}' missing")
        if text.count(LANE_BEGIN) != 1 or text.count(LANE_END) != 1:
            problems.append(f"{rel}: needs exactly one {LANE_BEGIN} / {LANE_END} lane region")
            continue
        b, e = text.index(LANE_BEGIN), text.index(LANE_END)
        if e < b:
            problems.append(f"{rel}: lane:end precedes lane:begin")
            continue
        lane = len(text[b : e + len(LANE_END)].encode("utf-8"))
        if lane > lane_budget:
            problems.append(f"{rel}: lane region {lane} bytes exceeds lane budget {lane_budget}")
    return problems


def main() -> int:
    problems = check(REPO)
    if problems:
        for p in problems:
            print(f"VIOLATION: {p}", file=sys.stderr)
        print(f"FAIL: {len(problems)} agent-instruction parity violation(s)", file=sys.stderr)
        return 1
    print("OK: agent instruction files carry all required canon blocks within budget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
