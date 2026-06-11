"""
Harness Paths — Single Source of Truth for Agentic Data Paths

All harness components that read/write telemetry, feedback, or candidate data
MUST import from this module. Never hardcode paths or duplicate env-var logic.

Resolution chain (override order, highest priority first):

  1. HARNESS_DATA_ROOT env var              → explicit override (testing, alternate installs)
  2. DATA_DIR env var (legacy compat)        → set by NixOS hybrid service unit
  3. TELEMETRY_DIR env var (legacy compat)   → set by NixOS training-ingest service unit
  4. /var/lib/ai-stack/hybrid               → production NixOS default
  5. ~/.local/share/nixos-ai-stack/hybrid   → dev/test fallback (no systemd)

Canonical subdirectory layout (relative to data_root):
  telemetry/                    — all JSONL event streams
    delegation-feedback.jsonl
    hybrid-events.jsonl
    race-runs.jsonl
    optimization_proposals.jsonl
    agent-run-events.jsonl
  fine-tuning/
    dataset.jsonl
    dataset_export.jsonl
  checkpoints/
    <service>-checkpoint.json

Repo-relative paths (relative to REPO_ROOT):
  .agents/improvement/candidates.json   — candidate lifecycle state
  .agents/telemetry/hybrid-events.jsonl — user-space spool (DirectRunner only)
  .agent/memory/issues-backlog.md       — issues backlog source for discovery
  config/model-profile.json             — model profile source for discovery

SPOOL NOTE: .agents/telemetry/hybrid-events.jsonl is a user-space write path
for DirectRunner (aq-agent-loop) which cannot write to /var/lib/ as non-root.
training_ingest.py merges both paths. If REPO_ROOT is read-only (Nix store),
the spool is disabled silently — DirectRunner events are discarded.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------

def _resolve_data_root() -> Path:
    """Resolve the hybrid service data root, highest-priority first."""
    # 1. Explicit override
    v = os.environ.get("HARNESS_DATA_ROOT", "")
    if v:
        return Path(v)

    # 2. Legacy DATA_DIR (set by NixOS hybrid service unit as /var/lib/ai-stack/hybrid)
    data_dir = os.environ.get("DATA_DIR", "")
    if data_dir and "hybrid" in data_dir:
        return Path(data_dir)

    # 3. Legacy TELEMETRY_DIR — one level up from telemetry subdir
    tel_dir = os.environ.get("TELEMETRY_DIR", "")
    if tel_dir:
        p = Path(tel_dir)
        # If TELEMETRY_DIR points to .../hybrid/telemetry, parent is data root
        if p.name == "telemetry":
            return p.parent
        return p.parent  # best-effort

    # 4. NixOS production path
    prod = Path("/var/lib/ai-stack/hybrid")
    if prod.exists():
        return prod

    # 5. Dev/test fallback
    return Path(os.path.expanduser("~/.local/share/nixos-ai-stack/hybrid"))


def _resolve_repo_root() -> Path:
    """Resolve repo root from REPO_ROOT env or file location search."""
    v = os.environ.get("REPO_ROOT", "")
    if v:
        return Path(v)
    # Walk up from this file looking for CLAUDE.md (repo root marker)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "CLAUDE.md").exists():
            return parent
    # Fallback: 2 levels above ai-stack/local-agents/ = repo root
    return here.parent.parent.parent


# Module-level singletons — computed once
DATA_ROOT: Path = _resolve_data_root()
REPO_ROOT: Path = _resolve_repo_root()

# ---------------------------------------------------------------------------
# Telemetry paths (service-written, under DATA_ROOT)
# ---------------------------------------------------------------------------

TELEMETRY_DIR: Path = DATA_ROOT / "telemetry"

DELEGATION_FEEDBACK:    Path = TELEMETRY_DIR / "delegation-feedback.jsonl"
HYBRID_EVENTS:          Path = TELEMETRY_DIR / "hybrid-events.jsonl"
RACE_RUNS:              Path = TELEMETRY_DIR / "race-runs.jsonl"
OPTIMIZATION_PROPOSALS: Path = TELEMETRY_DIR / "optimization_proposals.jsonl"
AGENT_RUN_EVENTS:       Path = TELEMETRY_DIR / "agent-run-events.jsonl"

# Fine-tuning outputs
FINE_TUNING_DIR:    Path = DATA_ROOT / "fine-tuning"
DATASET:            Path = FINE_TUNING_DIR / "dataset.jsonl"
DATASET_EXPORT:     Path = FINE_TUNING_DIR / "dataset_export.jsonl"

# Checkpoints
CHECKPOINT_DIR: Path = DATA_ROOT / "checkpoints"

# ---------------------------------------------------------------------------
# Repo-relative paths (user-space / version-controlled context)
# ---------------------------------------------------------------------------

CANDIDATES_JSON:      Path = REPO_ROOT / ".agents" / "improvement" / "candidates.json"
USER_EVENTS_SPOOL:    Path = REPO_ROOT / ".agents" / "telemetry" / "hybrid-events.jsonl"
ISSUES_BACKLOG:       Path = REPO_ROOT / ".agent" / "memory" / "issues-backlog.md"
MODEL_PROFILE:        Path = REPO_ROOT / "config" / "model-profile.json"
CRITIQUE_SPOOL:       Path = REPO_ROOT / ".agents" / "telemetry" / "cross-model-critiques.jsonl"
PROPOSALS_DIR:        Path = REPO_ROOT / ".agents" / "proposals"
DELEGATION_OUTPUTS:   Path = REPO_ROOT / ".agents" / "delegation" / "outputs"

# ---------------------------------------------------------------------------
# Helper: resolve a single path by name (for CLIs / config files)
# ---------------------------------------------------------------------------

_PATH_REGISTRY: dict[str, Path] = {
    "delegation_feedback":    DELEGATION_FEEDBACK,
    "hybrid_events":          HYBRID_EVENTS,
    "race_runs":              RACE_RUNS,
    "optimization_proposals": OPTIMIZATION_PROPOSALS,
    "agent_run_events":       AGENT_RUN_EVENTS,
    "dataset":                DATASET,
    "dataset_export":         DATASET_EXPORT,
    "candidates":             CANDIDATES_JSON,
    "user_events_spool":      USER_EVENTS_SPOOL,
    "issues_backlog":         ISSUES_BACKLOG,
    "model_profile":          MODEL_PROFILE,
    "critique_spool":         CRITIQUE_SPOOL,
    "proposals_dir":          PROPOSALS_DIR,
    "delegation_outputs":     DELEGATION_OUTPUTS,
}


def get_path(name: str) -> Path:
    """Return the canonical path for a named data artifact.

    Raises KeyError if name is not registered.
    """
    if name not in _PATH_REGISTRY:
        raise KeyError(f"Unknown harness path: {name!r}. Known: {sorted(_PATH_REGISTRY)}")
    return _PATH_REGISTRY[name]


def summary() -> dict[str, str]:
    """Return a human-readable dict of all canonical paths (for diagnostics)."""
    return {
        "DATA_ROOT":  str(DATA_ROOT),
        "REPO_ROOT":  str(REPO_ROOT),
        **{k: str(v) for k, v in _PATH_REGISTRY.items()},
    }


# ---------------------------------------------------------------------------
# CLI entrypoint: python harness_paths.py [--name NAME]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    if "--name" in sys.argv:
        idx = sys.argv.index("--name")
        name = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        try:
            print(get_path(name))
        except KeyError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json.dumps(summary(), indent=2))
