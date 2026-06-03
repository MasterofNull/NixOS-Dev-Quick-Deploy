#!/usr/bin/env python3
"""
Phase 101 regression: attention_queue must respect ATTENTION_QUEUE_DIR env var.

When the coordinator (running from Nix store) imports attention_queue, the
default _REPO_ROOT computed from __file__ points to a read-only Nix store path.
ATTENTION_QUEUE_DIR lets callers redirect writes to the live repo directory.
"""
from __future__ import annotations

import os
import sys
import tempfile
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}")
        FAIL += 1


def reload_attention_queue(env_dir=None):
    """Reload attention_queue with optional ATTENTION_QUEUE_DIR set."""
    if "attention_queue" in sys.modules:
        del sys.modules["attention_queue"]
    if env_dir is not None:
        os.environ["ATTENTION_QUEUE_DIR"] = str(env_dir)
    elif "ATTENTION_QUEUE_DIR" in os.environ:
        del os.environ["ATTENTION_QUEUE_DIR"]
    import attention_queue
    return attention_queue


def test_default_path():
    """Without env var, _ATTENTION_DIR is derived from __file__."""
    aq = reload_attention_queue(env_dir=None)
    # Should be 3 parents up from scripts/ai/lib/attention_queue.py
    expected = ROOT / ".agents" / "attention"
    check("default _ATTENTION_DIR derived from file location", aq._ATTENTION_DIR == expected)


def test_env_override():
    """With ATTENTION_QUEUE_DIR set, _ATTENTION_DIR uses that path."""
    with tempfile.TemporaryDirectory() as tmp:
        aq = reload_attention_queue(env_dir=tmp)
        check("ATTENTION_QUEUE_DIR env var overrides _ATTENTION_DIR", str(aq._ATTENTION_DIR) == tmp)
        check("_QUEUE_FILE under overridden dir", str(aq._QUEUE_FILE).startswith(tmp))
        check("_ARCHIVE_FILE under overridden dir", str(aq._ARCHIVE_FILE).startswith(tmp))
    # cleanup
    reload_attention_queue(env_dir=None)


def test_push_to_temp_dir():
    """push() writes to the overridden dir without permission error.
    auto_ok events bypass the queue and go straight to ATTENTION_ARCHIVE.jsonl.
    """
    with tempfile.TemporaryDirectory() as tmp:
        aq = reload_attention_queue(env_dir=tmp)
        try:
            aq.push(
                source="test-circuit-breaker",
                severity="high",
                autonomy_boundary="auto_ok",
                title="Test: circuit breaker trip",
                detail="Phase 101 wiring test — safe to dismiss",
                proposed_action="No action needed",
            )
            # auto_ok goes to archive, not ATTENTION.json
            archive_file = Path(tmp) / "ATTENTION_ARCHIVE.jsonl"
            check("push(auto_ok) writes to ATTENTION_ARCHIVE in overridden dir", archive_file.exists())
        except Exception as e:
            print(f"    push() raised: {e}")
            check("push(auto_ok) writes to ATTENTION_ARCHIVE in overridden dir", False)
    reload_attention_queue(env_dir=None)


def test_circuit_breaker_imports_attention_queue():
    """core/circuit_breaker._trip() pushes auto_ok alert when ATTENTION_QUEUE_DIR is set."""
    coord_path = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
    if str(coord_path) not in sys.path:
        sys.path.insert(0, str(coord_path))
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["ATTENTION_QUEUE_DIR"] = tmp
        for mod in ["attention_queue", "core.circuit_breaker"]:
            sys.modules.pop(mod, None)
        try:
            from core.circuit_breaker import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1)
            cb._trip()  # sync method in core/circuit_breaker.py
            archive = Path(tmp) / "ATTENTION_ARCHIVE.jsonl"
            queue = Path(tmp) / "ATTENTION.json"
            pushed = archive.exists() or queue.exists()
            check("core circuit breaker _trip() pushes to attention queue", pushed)
        except Exception as e:
            print(f"    _trip() raised: {e}")
            check("core circuit breaker _trip() pushes to attention queue", False)
        finally:
            os.environ.pop("ATTENTION_QUEUE_DIR", None)
            reload_attention_queue(env_dir=None)


def main():
    test_default_path()
    test_env_override()
    test_push_to_temp_dir()
    test_circuit_breaker_imports_attention_queue()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
