#!/usr/bin/env python3
"""Validate the MAEAH live-validation runbook stays aligned with static contracts."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / ".agents/plans/multi-agent-edge-harness/LIVE-VALIDATION-RUNBOOK.md"
EDGEAI = ROOT / "scripts/ai/edgeai"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    edgeai = EDGEAI.read_text(encoding="utf-8")

    for heading in (
        "## Phase 0 — Repo-static contract gate",
        "## Phase 1 — Surface health",
        "## Phase 2 — Responses compatibility smoke",
        "## Phase 3 — User-defined model lifecycle smoke",
        "## Phase 4 — Full MAEAH acceptance",
        "## Promotion criteria",
        "## Failure handling",
    ):
        require(heading in text, f"missing runbook section: {heading}")

    required_commands = (
        "edgeai contracts check --json",
        "scripts/testing/test-edgeai-cli-contract.sh",
        "python3 scripts/testing/test-maeah-api-surface-contract.py",
        "python3 scripts/testing/test-maeah-contract-artifacts.py",
        "python3 scripts/testing/test-maeah-model-registry-schema.py",
        "edgeai doctor --json",
        "edgeai models list --json",
        "edgeai a2a card validate --json",
        "edgeai mcp tools list --json",
        "edgeai traces tail --last 1 --json",
        "edgeai chat --json",
        "edgeai models add",
        "edgeai models delete local-smoke",
        "bash scripts/testing/maeah-acceptance-tests.sh --verbose",
        "scripts/ai/aq-memory-recall-benchmark --json",
        "scripts/governance/tier0-validation-gate.sh --pre-commit",
    )
    for command in required_commands:
        require(command in text, f"runbook missing command/reference: {command}")

    cli_surface = (
        "edgeai contracts check [--json]",
        "edgeai models add --id ID --name NAME --repo REPO --file FILE",
        "edgeai models delete <model-id>",
        "edgeai chat [--model MODEL] [--json]",
    )
    for surface in cli_surface:
        require(surface in edgeai, f"edgeai help missing surface required by runbook: {surface}")

    phase_numbers = [int(n) for n in re.findall(r"^## Phase (\d+) ", text, flags=re.MULTILINE)]
    require(phase_numbers == [0, 1, 2, 3, 4], f"unexpected runbook phase order: {phase_numbers}")

    require("Do **not** run `download`, `promote`, or `rollback`" in text, "runbook must warn against destructive/heavy model lifecycle actions")
    require("Do not promote MAEAH readiness on repo-static evidence alone." in text, "runbook must block repo-static-only readiness promotion")

    print("PASS: MAEAH live validation runbook contract")


if __name__ == "__main__":
    main()
