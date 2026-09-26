#!/usr/bin/env python3
"""Hermetic recovery checks for isolated flat-round review contributions."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader(
    "aq_collab_round", str(ROOT / "scripts" / "ai" / "aq-collab-round")
)
module = importlib.util.module_from_spec(importlib.util.spec_from_loader("aq_collab_round", loader))
loader.exec_module(module)

SUBJECT = "1" * 40


def main() -> int:
    with TemporaryDirectory() as raw:
        repo = Path(raw)
        round_dir = repo / ".agents" / "plans" / "round-a"
        task_id = "codex-test"
        worktree = repo / ".agents" / "delegation" / "worktrees" / task_id
        owned_dir = worktree / ".agents" / "plans" / "round-a"
        output_dir = repo / ".agents" / "delegation" / "outputs"
        for path in (round_dir, owned_dir, output_dir):
            path.mkdir(parents=True, exist_ok=True)
        registry = repo / ".agents" / "delegation" / "registry.jsonl"
        patch_file = repo / ".agents" / "delegation" / "outputs" / f"{task_id}.patch"
        (round_dir / ".round-prompt.txt").write_text(
            f"Review exact subject: `{SUBJECT}` and finish with a disposition.\n"
        )
        (round_dir / ".round-dispatch.json").write_text(
            json.dumps({"dispatch": {"codex": task_id, "local": "local-test"}})
        )
        owned_rel = ".agents/plans/round-a/codex.md"
        patch_file.write_text(f"diff --git a/{owned_rel} b/{owned_rel}\n")
        registry.write_text(json.dumps({
            "id": task_id, "agent": "codex", "status": "done", "worktree": str(worktree),
            "worktree_branch": f"delegate/{task_id}", "patch_file": str(patch_file),
        }) + "\n")
        valid = f"Subject: `{SUBJECT}`\n\nNo blocking findings.\n\nACCEPTED\n"
        (owned_dir / "codex.md").write_text(valid)

        module.REPO = repo
        module.OUTPUTS = output_dir
        module.DELEGATION_REGISTRY = registry
        assert module._import_isolated_contribution(round_dir, "codex") == "imported"
        assert (round_dir / "codex.md").read_text() == valid
        receipt = json.loads((round_dir / ".codex.import.json").read_text())
        assert receipt["dispatch_id"] == task_id and len(receipt["sha256"]) == 64

        truncated = f"Subject: `{SUBJECT}`\npartial analysis without verdict"
        assert module._validate_review_contribution(round_dir, truncated) == (
            False, "terminal-disposition-missing"
        )
        stale = f"Subject: `{'2' * 40}`\n\nREJECTED\n"
        assert module._validate_review_contribution(round_dir, stale) == (
            False, "subject-missing"
        )
        ambiguous = f"Subject: `{SUBJECT}`\nACCEPTED\nmore text\nREJECTED\n"
        assert module._validate_review_contribution(round_dir, ambiguous) == (
            False, "terminal-disposition-ambiguous"
        )

        local_log = output_dir / "local-test.log"
        local_log.write_text(json.dumps({
            "status": "completed", "result": truncated, "tool_calls": [],
            "success": True, "incomplete_result": False,
        }))
        assert module._extract_local_verdict(round_dir).startswith("local-completed-invalid:")
        assert not (round_dir / "local.md").exists()

    print("PASS: isolated review import is receipt-backed and truncated/stale verdicts fail closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
