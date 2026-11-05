"""Single source for where the RSI incident ledger and its gate files live.

The ledger is runtime state rewritten every few minutes by services; keeping it in
the git checkout made every sweep dirty the owner checkout (P1.10). Resolution order:
  1. PRSI_INCIDENTS_FILE (ledger file only) / RSI_RUNTIME_DIR (whole dir) / RSI_STATE_DIR (set by the
     systemd units): explicit, no seed. An explicit dir that is missing or unwritable raises
     StateDirError; it never falls back to the checkout (fail closed, a unit misconfig must be loud).
  2. DEFAULT_STATE_DIR, when it exists and is writable (provisioned by tmpfiles; Nix SSOT is
     deployment.mutableSpaces.aiStackRsiDir in nix/modules/core/options.nix).
  3. The checkout's .agent/collaboration, only when no explicit env is set (fresh clones, CI, dev).
The tracked .agent/collaboration/rsi-incidents.json is the seed: read when the state ledger does
not exist yet, never written when the state dir is in use.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_STATE_DIR = "/var/lib/nixos-ai-stack/rsi"
LEDGER = "rsi-incidents.json"


class StateDirError(RuntimeError):
    """An explicitly configured state dir is missing or unwritable."""


def require_writable_dir(path: Path, var: str) -> Path:
    if not path.is_dir() or not os.access(path, os.W_OK | os.X_OK):
        raise StateDirError(f"{var}={path} is not an existing writable directory; refusing to fall back to the checkout")
    return path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def seed_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / ".agent" / "collaboration"


def state_dir() -> Path:
    return Path(os.environ.get("RSI_STATE_DIR") or DEFAULT_STATE_DIR)


def runtime_dir(root: Path | None = None) -> Path:
    env = os.environ.get("RSI_RUNTIME_DIR")
    if env:
        return require_writable_dir(Path(env), "RSI_RUNTIME_DIR")
    state = state_dir()
    if os.environ.get("RSI_STATE_DIR"):
        return require_writable_dir(state, "RSI_STATE_DIR")
    if state.is_dir() and os.access(state, os.W_OK):
        return state
    return seed_dir(root)


def incidents_path(root: Path | None = None) -> Path:
    env = os.environ.get("PRSI_INCIDENTS_FILE")
    if env:
        if not Path(env).parent.is_dir():
            raise StateDirError(f"PRSI_INCIDENTS_FILE={env}: parent directory does not exist; refusing to fall back")
        return Path(env)
    return runtime_dir(root) / LEDGER


def incidents_read_path(root: Path | None = None) -> Path:
    """Where to READ the ledger: the state ledger, else the tracked seed (default mode only)."""
    ledger = incidents_path(root)
    if ledger.exists() or seed_text(ledger, root) is None:
        return ledger
    return seed_dir(root) / LEDGER


def seed_text(ledger: Path, root: Path | None = None) -> str | None:
    """Tracked seed content, only when `ledger` is the default state-dir ledger and does not exist."""
    if os.environ.get("RSI_RUNTIME_DIR") or os.environ.get("PRSI_INCIDENTS_FILE") or ledger.parent != state_dir():
        return None
    seed = seed_dir(root) / LEDGER
    if ledger.exists() or ledger == seed:
        return None
    try:
        return seed.read_text()
    except OSError:
        return None


def read_ledger_text(ledger: Path, root: Path | None = None) -> str:
    """Ledger text, falling back to the tracked seed; raises OSError like read_text when neither exists."""
    try:
        return ledger.read_text()
    except FileNotFoundError:
        seeded = seed_text(ledger, root)
        if seeded is None:
            raise
        return seeded
