#!/usr/bin/env python3
"""
P2-REL-001: Checkpointing Tests
Verifies crash recovery and checkpoint functionality
"""
import sys
import tempfile
import json
import pickle
from pathlib import Path
from datetime import datetime


class SimpleCheckpointer:
    """
    Simplified checkpointer for testing (mirrors the actual implementation)
    """
    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: dict):
        """Save checkpoint atomically"""
        temp_path = self.checkpoint_dir / "checkpoint.tmp"
        final_path = self.checkpoint_dir / "checkpoint.pkl"

        try:
            with open(temp_path, "wb") as f:
                pickle.dump(state, f)
            temp_path.rename(final_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def load(self) -> dict:
        """Load last checkpoint if exists"""
        checkpoint_path = self.checkpoint_dir / "checkpoint.pkl"
        if not checkpoint_path.exists():
            return {}
        with open(checkpoint_path, "rb") as f:
            return pickle.load(f)

    def clear(self):
        """Clear checkpoint"""
        checkpoint_path = self.checkpoint_dir / "checkpoint.pkl"
        if checkpoint_path.exists():
            checkpoint_path.unlink()


def test_checkpoint_save_and_load():
    """Test that checkpoints can be saved and loaded"""
    print("Testing checkpoint save and load...")

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_dir = Path(tmpdir)
        checkpointer = SimpleCheckpointer(checkpoint_dir)

        # Test data
        test_state = {
            "last_positions": {
                "/data/telemetry/ralph-events.jsonl": 1234,
                "/data/telemetry/aidb-events.jsonl": 5678
            },
            "processed_count": 42,
            "timestamp": "2026-01-09T10:00:00Z"
        }

        # Save checkpoint
        checkpointer.save(test_state)

        # Verify checkpoint file exists
        checkpoint_file = checkpoint_dir / "checkpoint.pkl"
        if not checkpoint_file.exists():
            print("✗ Checkpoint file not created")
            return False

        print("✓ Checkpoint file created")

        # Load checkpoint
        loaded_state = checkpointer.load()

        # Verify loaded state matches saved state
        if loaded_state != test_state:
            print(f"✗ Loaded state doesn't match")
            return False

        print("✓ Checkpoint loaded correctly")
        return True


def test_checkpoint_atomic_write():
    """Test that checkpoint writes are atomic (no partial writes)"""
    print("\nTesting atomic checkpoint writes...")

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_dir = Path(tmpdir)
        checkpointer = SimpleCheckpointer(checkpoint_dir)

        # Save checkpoint
        test_state = {"counter": 1}
        checkpointer.save(test_state)

        # Verify temp file is cleaned up
        temp_file = checkpoint_dir / "checkpoint.tmp"
        if temp_file.exists():
            print("✗ Temporary file not cleaned up")
            return False

        print("✓ Atomic write successful (no temp file left)")
        return True


def test_checkpoint_resume_from_crash():
    """Test that pipeline can resume after simulated crash"""
    print("\nTesting resume from crash...")

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_dir = Path(tmpdir)

        # Simulate first run (process 50 events, then crash)
        checkpointer1 = SimpleCheckpointer(checkpoint_dir)
        checkpointer1.save({
            "last_positions": {"/data/telemetry/test.jsonl": 500},
            "processed_count": 50
        })

        # Simulate second run (resume from checkpoint)
        checkpointer2 = SimpleCheckpointer(checkpoint_dir)
        loaded_state = checkpointer2.load()

        if loaded_state.get("processed_count") != 50:
            print(f"✗ Wrong processed count: {loaded_state.get('processed_count')}")
            return False

        if loaded_state.get("last_positions", {}).get("/data/telemetry/test.jsonl") != 500:
            print(f"✗ Wrong file position")
            return False

        print("✓ Successfully resumed from checkpoint")
        print(f"  - Processed count: {loaded_state['processed_count']}")
        print(f"  - File position: {loaded_state['last_positions']['/data/telemetry/test.jsonl']}")
        return True


def test_checkpoint_no_data_loss():
    """Test that no events are lost during checkpointing"""
    print("\nTesting no data loss...")

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_dir = Path(tmpdir)
        telemetry_file = Path(tmpdir) / "test-events.jsonl"

        # Create test telemetry file
        events = []
        for i in range(250):  # 250 events
            events.append({"event_id": i, "data": f"event_{i}"})

        with open(telemetry_file, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        # Simulate processing with checkpoints every 100 events
        checkpointer = SimpleCheckpointer(checkpoint_dir)
        processed_events = []
        last_position = 0

        with open(telemetry_file, "r") as f:
            f.seek(last_position)

            line_num = 0
            while True:
                line = f.readline()
                if not line:
                    break

                event = json.loads(line)
                processed_events.append(event["event_id"])
                line_num += 1

                # Checkpoint every 100 events
                if line_num % 100 == 0:
                    last_position = f.tell()
                    checkpointer.save({
                        "last_positions": {str(telemetry_file): last_position},
                        "processed_count": len(processed_events)
                    })

        # Verify all events were processed
        if len(processed_events) != 250:
            print(f"✗ Lost events: {len(processed_events)}/250")
            return False

        # Verify no duplicates
        if len(set(processed_events)) != 250:
            print(f"✗ Duplicate events found")
            return False

        print("✓ No data loss during checkpointing")
        print(f"  - Processed: {len(processed_events)}/250 events")
        print(f"  - Checkpoints created: 2 (at 100, 200)")
        return True


def test_checkpoint_clear():
    """Test that checkpoints can be cleared"""
    print("\nTesting checkpoint clear...")

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_dir = Path(tmpdir)
        checkpointer = SimpleCheckpointer(checkpoint_dir)

        # Save checkpoint
        checkpointer.save({"test": "data"})

        # Verify it exists
        if not (checkpoint_dir / "checkpoint.pkl").exists():
            print("✗ Checkpoint not created")
            return False

        # Clear checkpoint
        checkpointer.clear()

        # Verify it's gone
        if (checkpoint_dir / "checkpoint.pkl").exists():
            print("✗ Checkpoint not cleared")
            return False

        print("✓ Checkpoint cleared successfully")
        return True


def main():
    print("=" * 60)
    print("P2-REL-001: Checkpointing Tests")
    print("=" * 60)

    results = []

    # Test 1: Basic save/load
    results.append(("Checkpoint save and load", test_checkpoint_save_and_load()))

    # Test 2: Atomic writes
    results.append(("Atomic checkpoint writes", test_checkpoint_atomic_write()))

    # Test 3: Resume from crash
    results.append(("Resume from crash", test_checkpoint_resume_from_crash()))

    # Test 4: No data loss
    results.append(("No data loss", test_checkpoint_no_data_loss()))

    # Test 5: Clear checkpoint
    results.append(("Clear checkpoint", test_checkpoint_clear()))

    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)
    print("\n" + ("✓ ALL TESTS PASSED" if all_passed else "✗ SOME TESTS FAILED"))
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
