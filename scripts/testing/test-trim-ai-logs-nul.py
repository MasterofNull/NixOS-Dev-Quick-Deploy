#!/usr/bin/env python3
"""Test that trim-ai-logs.sh correctly strips NUL bytes and ages out old records."""

import json
import os
import sys
import tempfile
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path


def create_test_jsonl(path: Path, days: int) -> None:
    """Create a test JSONL with NUL-prefixed and normal records, beyond and within TTL."""
    cutoff_epoch = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

    # Records that should be removed (older than cutoff)
    old_ts = cutoff_epoch - 86400  # 1 day before cutoff
    # Records that should be kept (newer than cutoff)
    recent_ts = cutoff_epoch + 86400  # 1 day after cutoff

    records = [
        # NUL-prefixed old record (should be removed after NUL stripping)
        f'\x00{json.dumps({"timestamp": old_ts, "label": "nul_old"})}',
        # NUL-prefixed recent record (should be kept with NUL stripped)
        f'\x00{json.dumps({"timestamp": recent_ts, "label": "nul_recent"})}',
        # Normal old record (should be removed)
        json.dumps({"timestamp": old_ts, "label": "normal_old"}),
        # Normal recent record (should be kept)
        json.dumps({"timestamp": recent_ts, "label": "normal_recent"}),
    ]

    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(record + "\n")


def run_trim(file_path: Path, days: int) -> None:
    """Run the trim_jsonl Python logic against the test file."""
    cutoff_epoch = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

    # Extract and run the trim_jsonl Python code
    # Run the trim_jsonl heredoc extracted from the real script, not a copy.
    script = (Path(__file__).resolve().parents[2] / "scripts" / "data" / "trim-ai-logs.sh").read_text()
    trim_code = script.split("<<'PYEOF'\n", 1)[1].split("\nPYEOF\n", 1)[0]

    result = subprocess.run(
        [sys.executable, "-c", trim_code, str(file_path), str(cutoff_epoch), "false", "test-jsonl"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Trim failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout, end="")


def verify_results(file_path: Path) -> None:
    """Verify that only recent records remain and no NUL bytes are present."""
    # Check for NUL bytes in raw output (should be none)
    with open(file_path, "rb") as f:
        raw = f.read()
        if 0x00 in raw:
            print("FAIL: NUL bytes still present in output", file=sys.stderr)
            sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        lines = [line for line in content.split("\n") if line.strip()]

    # Check that we have exactly 2 records (the two recent ones)
    if len(lines) != 2:
        print(f"FAIL: Expected 2 lines, got {len(lines)}", file=sys.stderr)
        for i, line in enumerate(lines):
            print(f"  Line {i}: {line}", file=sys.stderr)
        sys.exit(1)

    # Verify labels
    labels = set()
    for line in lines:
        try:
            obj = json.loads(line)
            labels.add(obj.get("label"))
        except json.JSONDecodeError:
            print(f"FAIL: Invalid JSON in output: {line}", file=sys.stderr)
            sys.exit(1)

    expected_labels = {"nul_recent", "normal_recent"}
    if labels != expected_labels:
        print(f"FAIL: Expected labels {expected_labels}, got {labels}", file=sys.stderr)
        sys.exit(1)


def main():
    days = 14
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.jsonl"

        # Create test file with NUL bytes and mixed old/recent records
        create_test_jsonl(test_file, days)

        # Run trim
        run_trim(test_file, days)

        # Verify results
        verify_results(test_file)

    print("PASS")


if __name__ == "__main__":
    main()
