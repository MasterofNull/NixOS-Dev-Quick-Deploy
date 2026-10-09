#!/usr/bin/env python3
"""Static hint rules: multi-word keywords match as consecutive query tokens."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from hints_engine import HintsEngine  # noqa: E402
from knowledge.token_manager import _tokenize  # noqa: E402


def fired(query: str) -> set:
    engine = HintsEngine.__new__(HintsEngine)
    return {h.id for h in engine._hints_from_static_rules(_tokenize(query))}


def main() -> int:
    ids = fired("please write a new script to parse the logs")
    assert "check_capability_index_before_new_code" in ids, ids
    ids = fired("there is a hash mismatch on the committed bytes")
    assert "verify_committed_bytes_not_piped_hash" in ids, ids
    # Words present but not consecutive must not satisfy a multi-word keyword alone.
    assert "check_capability_index_before_new_code" not in fired("script that is new mismatch"), "non-consecutive matched"
    print("PASS: static hint rules match multi-word keywords as consecutive tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
