#!/usr/bin/env python3
"""Validate the document lifecycle hygiene anchors.

This is intentionally narrow. It guards the index and lifecycle surfaces that
agents should read before loading broad historical PRDs/plans.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCS = [
    "docs/architecture/agent-behavior-parity-index.md",
    "docs/operations/document-lifecycle-hygiene.md",
    "docs/operations/agent-artifact-gc-policy.md",
    "docs/architecture/role-matrix.md",
    "docs/architecture/routing-profile-inventory.md",
    "docs/architecture/canonical-kernel-declaration.md",
    "docs/agent-guides/47-AGENT-TOOL-CONTRACT.md",
    ".agent/WORKFLOW-CANON.md",
    ".agents/plans/multi-agent-edge-harness/PARITY-INTEGRATION-PLAN.md",
    ".agents/plans/multi-agent-edge-harness/COMBINED-PRD.md",
]

METADATA_TARGETS = [
    "docs/architecture/agent-behavior-parity-index.md",
    "docs/operations/document-lifecycle-hygiene.md",
    "docs/operations/agent-artifact-gc-policy.md",
    ".agents/plans/README.md",
]


def fail(message: str) -> None:
    print(f"[doc-lifecycle] FAIL: {message}")
    raise SystemExit(1)


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        fail(f"missing required document: {rel}")
    return path.read_text(encoding="utf-8", errors="ignore")


def require_contains(rel: str, needles: list[str]) -> None:
    text = read(rel)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        fail(f"{rel} missing required text: {', '.join(missing)}")


def require_metadata(rel: str) -> None:
    head = "\n".join(read(rel).splitlines()[:30])
    missing = [
        label
        for label in ("Status:", "Owner:", "Last Updated:")
        if label not in head
    ]
    if missing:
        fail(f"{rel} missing lifecycle metadata: {', '.join(missing)}")


def main() -> int:
    for rel in REQUIRED_DOCS:
        read(rel)

    for rel in METADATA_TARGETS:
        require_metadata(rel)

    require_contains(
        "docs/architecture/agent-behavior-parity-index.md",
        [
            "docs/architecture/role-matrix.md",
            "docs/architecture/routing-profile-inventory.md",
            ".agents/plans/multi-agent-edge-harness/PARITY-INTEGRATION-PLAN.md",
            "docs/operations/document-lifecycle-hygiene.md",
            "Status: Active",
            "Status: Superseded",
            "Status: Archived",
        ],
    )
    require_contains(
        "docs/operations/document-lifecycle-hygiene.md",
        [
            "Active",
            "Draft",
            "Reference",
            "Superseded",
            "Archived",
            "Quarantined",
            "Retirement Rules",
            "docs/operations/agent-artifact-gc-policy.md",
        ],
    )
    require_contains(
        "docs/operations/agent-artifact-gc-policy.md",
        [
            "Artifact Classes",
            "Retention Targets",
            ".agents/delegation/outputs/",
            ".agents/sessions/",
            ".agents/scratchpad/",
            "scripts/governance/audit-agent-artifact-debt.py",
        ],
    )
    require_contains(
        ".agents/plans/README.md",
        [
            "docs/architecture/agent-behavior-parity-index.md",
            "docs/operations/document-lifecycle-hygiene.md",
            "Historical plans are evidence, not default instructions.",
        ],
    )

    print("[doc-lifecycle] PASS: lifecycle anchors and parity index are present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
