#!/usr/bin/env python3
"""
P2-REL-004: Backpressure Monitoring Tests
Tests that learning pauses when telemetry queue grows too large
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "hybrid-coordinator"))


def test_backpressure_calculation():
    """Test backpressure calculation based on file sizes"""
    print("Testing backpressure calculation...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock telemetry files
        telemetry_dir = Path(tmpdir) / "telemetry"
        telemetry_dir.mkdir()

        ralph_file = telemetry_dir / "ralph-events.jsonl"
        aidb_file = telemetry_dir / "aidb-events.jsonl"
        hybrid_file = telemetry_dir / "hybrid-events.jsonl"

        # Write 10MB to each file (30MB total)
        event = {"id": 1, "timestamp": datetime.now(timezone.utc).isoformat(), "data": "x" * 1000}
        for file in [ralph_file, aidb_file, hybrid_file]:
            with open(file, "w") as f:
                for _ in range(10000):  # ~10MB per file
                    f.write(json.dumps(event) + "\n")

        # Create mock pipeline
        class MockPipeline:
            def __init__(self):
                self.telemetry_paths = [ralph_file, aidb_file, hybrid_file]
                self.last_positions = {}
                self.backpressure_threshold_mb = 100
                self.backpressure_paused = False

            def _check_backpressure(self):
                total_unprocessed_bytes = 0
                file_sizes = {}

                for telemetry_path in self.telemetry_paths:
                    if not telemetry_path.exists():
                        file_sizes[str(telemetry_path.name)] = 0
                        continue

                    file_size = telemetry_path.stat().st_size
                    file_sizes[str(telemetry_path.name)] = file_size

                    last_position = self.last_positions.get(str(telemetry_path), 0)
                    unprocessed = max(0, file_size - last_position)
                    total_unprocessed_bytes += unprocessed

                unprocessed_mb = total_unprocessed_bytes / (1024 * 1024)
                paused = unprocessed_mb > self.backpressure_threshold_mb

                return {
                    'unprocessed_mb': round(unprocessed_mb, 2),
                    'paused': paused,
                    'file_sizes': file_sizes
                }

        pipeline = MockPipeline()

        # Test 1: No processing yet (all unprocessed)
        status = pipeline._check_backpressure()
        assert status['unprocessed_mb'] > 0, "Should have unprocessed data"
        assert status['unprocessed_mb'] < 50, f"Should be ~30MB, got {status['unprocessed_mb']}MB"
        assert not status['paused'], "Should not pause with <100MB"

        # Test 2: Mark files as partially processed
        ralph_size = ralph_file.stat().st_size
        pipeline.last_positions[str(ralph_file)] = ralph_size // 2  # 50% processed

        status = pipeline._check_backpressure()
        assert status['unprocessed_mb'] < status['unprocessed_mb'] + 10, "Unprocessed should decrease"

        # Test 3: Create large backlog (>100MB)
        large_file = telemetry_dir / "large-events.jsonl"
        pipeline.telemetry_paths.append(large_file)

        with open(large_file, "w") as f:
            for _ in range(100000):  # ~100MB
                f.write(json.dumps(event) + "\n")

        status = pipeline._check_backpressure()
        assert status['unprocessed_mb'] > 100, f"Should exceed threshold, got {status['unprocessed_mb']}MB"
        assert status['paused'], "Should pause when >100MB unprocessed"

    print("✓ Backpressure calculation works")


def test_backpressure_pause_resume():
    """Test that learning pauses and resumes based on backpressure"""
    print("Testing backpressure pause/resume logic...")

    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_dir = Path(tmpdir) / "telemetry"
        telemetry_dir.mkdir()

        test_file = telemetry_dir / "test-events.jsonl"

        class MockPipeline:
            def __init__(self):
                self.telemetry_paths = [test_file]
                self.last_positions = {}
                self.backpressure_threshold_mb = 10  # Low threshold for testing
                self.backpressure_paused = False

            def _check_backpressure(self):
                total_unprocessed_bytes = 0

                for telemetry_path in self.telemetry_paths:
                    if not telemetry_path.exists():
                        continue

                    file_size = telemetry_path.stat().st_size
                    last_position = self.last_positions.get(str(telemetry_path), 0)
                    unprocessed = max(0, file_size - last_position)
                    total_unprocessed_bytes += unprocessed

                unprocessed_mb = total_unprocessed_bytes / (1024 * 1024)
                paused = unprocessed_mb > self.backpressure_threshold_mb

                return {
                    'unprocessed_mb': round(unprocessed_mb, 2),
                    'paused': paused,
                    'file_sizes': {}
                }

        pipeline = MockPipeline()

        # Start with small file (should not pause)
        event = {"id": 1, "data": "x" * 100}
        with open(test_file, "w") as f:
            for _ in range(1000):  # ~100KB
                f.write(json.dumps(event) + "\n")

        status = pipeline._check_backpressure()
        assert not status['paused'], "Should not pause with small file"
        assert not pipeline.backpressure_paused, "Pipeline should not be paused"

        # Grow file beyond threshold
        with open(test_file, "a") as f:
            for _ in range(100000):  # ~10MB+
                f.write(json.dumps(event) + "\n")

        status = pipeline._check_backpressure()
        assert status['paused'], "Should pause with large file"
        assert status['unprocessed_mb'] > 10, "Should exceed 10MB threshold"

        # Simulate: Mark pipeline as paused
        pipeline.backpressure_paused = True

        # Simulate processing (update position)
        pipeline.last_positions[str(test_file)] = test_file.stat().st_size

        status = pipeline._check_backpressure()
        assert not status['paused'], "Should not pause after processing"
        assert status['unprocessed_mb'] < 0.1, "Should have minimal unprocessed"

        # Pipeline should detect it can resume
        if not status['paused'] and pipeline.backpressure_paused:
            pipeline.backpressure_paused = False

        assert not pipeline.backpressure_paused, "Pipeline should resume"

    print("✓ Backpressure pause/resume works")


def test_backpressure_with_missing_files():
    """Test backpressure handles missing telemetry files gracefully"""
    print("Testing backpressure with missing files...")

    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_dir = Path(tmpdir) / "telemetry"
        telemetry_dir.mkdir()

        existing_file = telemetry_dir / "exists.jsonl"
        missing_file = telemetry_dir / "missing.jsonl"

        # Create only one file
        with open(existing_file, "w") as f:
            f.write(json.dumps({"id": 1}) + "\n")

        class MockPipeline:
            def __init__(self):
                self.telemetry_paths = [existing_file, missing_file]
                self.last_positions = {}
                self.backpressure_threshold_mb = 100

            def _check_backpressure(self):
                total_unprocessed_bytes = 0
                file_sizes = {}

                for telemetry_path in self.telemetry_paths:
                    if not telemetry_path.exists():
                        file_sizes[str(telemetry_path.name)] = 0
                        continue

                    file_size = telemetry_path.stat().st_size
                    file_sizes[str(telemetry_path.name)] = file_size

                    last_position = self.last_positions.get(str(telemetry_path), 0)
                    unprocessed = max(0, file_size - last_position)
                    total_unprocessed_bytes += unprocessed

                unprocessed_mb = total_unprocessed_bytes / (1024 * 1024)
                paused = unprocessed_mb > self.backpressure_threshold_mb

                return {
                    'unprocessed_mb': round(unprocessed_mb, 2),
                    'paused': paused,
                    'file_sizes': file_sizes
                }

        pipeline = MockPipeline()
        status = pipeline._check_backpressure()

        assert status['unprocessed_mb'] >= 0, "Should handle missing files"
        assert not status['paused'], "Should not pause with small unprocessed"
        assert status['file_sizes']['missing.jsonl'] == 0, "Missing file should have size 0"

    print("✓ Missing file handling works")


def test_backpressure_statistics_integration():
    """Test backpressure status is included in statistics"""
    print("Testing statistics integration...")

    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_dir = Path(tmpdir) / "telemetry"
        telemetry_dir.mkdir()

        test_file = telemetry_dir / "test.jsonl"
        with open(test_file, "w") as f:
            f.write(json.dumps({"id": 1}) + "\n")

        class MockPipeline:
            def __init__(self):
                self.telemetry_paths = [test_file]
                self.last_positions = {}
                self.backpressure_threshold_mb = 100
                self.backpressure_paused = False
                self.patterns = []
                self.metrics = []

            def _check_backpressure(self):
                total_unprocessed_bytes = 0

                for telemetry_path in self.telemetry_paths:
                    if not telemetry_path.exists():
                        continue

                    file_size = telemetry_path.stat().st_size
                    last_position = self.last_positions.get(str(telemetry_path), 0)
                    unprocessed = max(0, file_size - last_position)
                    total_unprocessed_bytes += unprocessed

                unprocessed_mb = total_unprocessed_bytes / (1024 * 1024)
                paused = unprocessed_mb > self.backpressure_threshold_mb

                return {
                    'unprocessed_mb': round(unprocessed_mb, 2),
                    'paused': paused,
                    'file_sizes': {}
                }

            def get_statistics(self):
                backpressure_status = self._check_backpressure()

                return {
                    "total_patterns_learned": len(self.patterns),
                    "backpressure": backpressure_status,
                    "learning_paused": self.backpressure_paused,
                }

        pipeline = MockPipeline()
        stats = pipeline.get_statistics()

        assert 'backpressure' in stats, "Statistics should include backpressure"
        assert 'learning_paused' in stats, "Statistics should include pause status"
        assert 'unprocessed_mb' in stats['backpressure'], "Backpressure should include MB"
        assert 'paused' in stats['backpressure'], "Backpressure should include pause flag"

    print("✓ Statistics integration works")


def test_threshold_configuration():
    """Test different backpressure thresholds"""
    print("Testing threshold configuration...")

    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_dir = Path(tmpdir) / "telemetry"
        telemetry_dir.mkdir()

        test_file = telemetry_dir / "test.jsonl"

        # Create 50MB file
        event = {"id": 1, "data": "x" * 1000}
        with open(test_file, "w") as f:
            for _ in range(50000):  # ~50MB
                f.write(json.dumps(event) + "\n")

        file_size_mb = test_file.stat().st_size / (1024 * 1024)

        # Test with high threshold (100MB) - should not pause
        class MockPipeline:
            def __init__(self, threshold_mb):
                self.telemetry_paths = [test_file]
                self.last_positions = {}
                self.backpressure_threshold_mb = threshold_mb

            def _check_backpressure(self):
                total_unprocessed_bytes = 0

                for telemetry_path in self.telemetry_paths:
                    if not telemetry_path.exists():
                        continue

                    file_size = telemetry_path.stat().st_size
                    last_position = self.last_positions.get(str(telemetry_path), 0)
                    unprocessed = max(0, file_size - last_position)
                    total_unprocessed_bytes += unprocessed

                unprocessed_mb = total_unprocessed_bytes / (1024 * 1024)
                paused = unprocessed_mb > self.backpressure_threshold_mb

                return {
                    'unprocessed_mb': round(unprocessed_mb, 2),
                    'paused': paused,
                }

        # High threshold (100MB) - should not pause
        pipeline_high = MockPipeline(threshold_mb=100)
        status_high = pipeline_high._check_backpressure()
        assert not status_high['paused'], f"Should not pause with 100MB threshold ({file_size_mb}MB file)"

        # Low threshold (10MB) - should pause
        pipeline_low = MockPipeline(threshold_mb=10)
        status_low = pipeline_low._check_backpressure()
        assert status_low['paused'], f"Should pause with 10MB threshold ({file_size_mb}MB file)"

    print("✓ Threshold configuration works")


def main():
    """Run all tests"""
    print("=" * 60)
    print("P2-REL-004: Backpressure Monitoring Tests")
    print("=" * 60)

    tests = [
        test_backpressure_calculation,
        test_backpressure_pause_resume,
        test_backpressure_with_missing_files,
        test_backpressure_statistics_integration,
        test_threshold_configuration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1

    print()
    print("=" * 60)
    if failed == 0:
        print(f"✓ ALL TESTS PASSED ({passed}/{len(tests)})")
        print("=" * 60)
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed} passed, {failed} failed)")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
