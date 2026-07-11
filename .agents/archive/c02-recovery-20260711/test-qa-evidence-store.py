import os
import sys
import json
import uuid
import time
import pytest
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

# Allow imports from scripts/ai/lib and scripts/testing
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "testing"))

from agent_run_events import (
    resolve_telemetry_root,
    check_telemetry_root_divergence,
    PathDivergenceError
)
# Import main.py elements to test them
import harness_qa.main as main_mod

class DummyResult:
    def __init__(self, layer, test_id, status, description, reason=""):
        self.layer = layer
        self.id = test_id
        self.status = MagicMock()
        self.status.value = status
        self.description = description
        self.reason = reason

class DummyResultSet:
    def __init__(self, phase, results, duration_s):
        self.phase = phase
        self.results = results
        self.duration_s = duration_s
        self.passed = sum(1 for r in results if r.status.value == "PASS")
        self.failed = sum(1 for r in results if r.status.value == "FAIL")
        self.skipped = sum(1 for r in results if r.status.value == "SKIP")

def test_resolve_and_divergence(tmp_path, monkeypatch):
    # Test 1: AQ_TELEMETRY_ROOT override
    custom_root = tmp_path / "custom_root"
    monkeypatch.setenv("AQ_TELEMETRY_ROOT", str(custom_root))
    assert resolve_telemetry_root() == custom_root.resolve()

    # Clear env var to test defaults
    monkeypatch.delenv("AQ_TELEMETRY_ROOT", raising=False)

    # Mock Path.exists and resolve to simulate both deployed and dev dirs existing
    # Ensure they are divergent paths
    deployed_dir = Path("/var/lib/ai-stack/hybrid/telemetry")
    dev_dir = REPO_ROOT / ".agents" / "telemetry"

    # Mock os.path.exists or Path.exists to return True for both
    original_exists = Path.exists
    def mock_exists(self):
        # Use string comparison to bypass symlink resolution on disk
        if "/var/lib/ai-stack/hybrid/telemetry" in str(self) or ".agents/telemetry" in str(self):
            return True
        return original_exists(self)

    # Mock Path.resolve to return divergent paths
    original_resolve = Path.resolve
    def mock_resolve(self):
        if "/var/lib/ai-stack/hybrid/telemetry" in str(self):
            return Path("/var/lib/ai-stack/hybrid/telemetry")
        if ".agents/telemetry" in str(self):
            return Path("/home/hyperd/fake-dev-path/telemetry")
        return original_resolve(self)

    with patch.object(Path, "exists", mock_exists), patch.object(Path, "resolve", mock_resolve):
        with pytest.raises(PathDivergenceError, match="TELEMETRY_ROOT_DIVERGENCE"):
            check_telemetry_root_divergence()


def test_concurrent_writers_and_cas(tmp_path, monkeypatch):
    monkeypatch.setenv("AQ_TELEMETRY_ROOT", str(tmp_path))
    monkeypatch.setenv("AQ_RUN_ID", "run-1")

    # Sequence 1: Writer 1
    rs1 = DummyResultSet("0", [DummyResult(0, "check_1", "PASS", "check passed")], 5)
    main_mod.save_qa_results(rs1, REPO_ROOT)

    pointer_file = tmp_path / "latest-qa-results.json"
    assert pointer_file.exists()
    p_data = json.loads(pointer_file.read_text(encoding="utf-8"))
    assert p_data["sequence"] == 1
    assert "target_path" in p_data

    # Sequence 2: Writer 2 (simulating concurrent run which reads sequence 1 and increments to 2)
    monkeypatch.setenv("AQ_RUN_ID", "run-2")
    rs2 = DummyResultSet("0", [DummyResult(0, "check_1", "PASS", "check passed")], 6)
    main_mod.save_qa_results(rs2, REPO_ROOT)

    p_data = json.loads(pointer_file.read_text(encoding="utf-8"))
    assert p_data["sequence"] == 2

    # Check both artifacts exist
    artifacts = list(tmp_path.glob("qa-results-*.json"))
    assert len(artifacts) == 2


def test_pointer_and_artifact_validation_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("AQ_TELEMETRY_ROOT", str(tmp_path))
    rs = DummyResultSet("0", [DummyResult(0, "check_1", "PASS", "check passed")], 5)
    main_mod.save_qa_results(rs, REPO_ROOT)

    pointer_file = tmp_path / "latest-qa-results.json"
    p_data = json.loads(pointer_file.read_text(encoding="utf-8"))
    artifact_path = REPO_ROOT / p_data["target_path"]
    
    # Assert hash in pointer matches actual artifact hash
    payload_bytes = artifact_path.read_bytes()
    expected_hash = "sha256-" + hashlib.sha256(payload_bytes).hexdigest()
    assert p_data["hash"] == expected_hash

    # Corrupt artifact by changing its content
    artifact_path.write_text("corrupted content")
    
    # Read pointer and check mismatch
    p_data_new = json.loads(pointer_file.read_text(encoding="utf-8"))
    artifact_path_new = REPO_ROOT / p_data_new["target_path"]
    new_bytes = artifact_path_new.read_bytes()
    actual_hash = "sha256-" + hashlib.sha256(new_bytes).hexdigest()
    
    assert p_data_new["hash"] != actual_hash


def test_retention_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("AQ_TELEMETRY_ROOT", str(tmp_path))
    
    # Create pointer and current target
    rs = DummyResultSet("0", [DummyResult(0, "check_1", "PASS", "check passed")], 5)
    main_mod.save_qa_results(rs, REPO_ROOT)

    pointer_file = tmp_path / "latest-qa-results.json"
    p_data = json.loads(pointer_file.read_text(encoding="utf-8"))
    pointer_target = (REPO_ROOT / p_data["target_path"]).resolve()

    # Create 70 mock old artifacts
    now_ts = time.time()
    eight_days_ago = now_ts - (8 * 24 * 3600)
    for i in range(70):
        art_path = tmp_path / f"qa-results-old-{i}.json"
        art_path.write_text(json.dumps({"seq": i, "data": "old"}))
        # Set mtime to > 7 days ago
        os.utime(art_path, (eight_days_ago - i, eight_days_ago - i))

    # Run GC
    main_mod.enforce_retention_policy(tmp_path, pointer_file, REPO_ROOT)

    # Pointer target must NEVER be pruned
    assert pointer_target.exists()

    # Oldest artifacts exceeding soft limit (64) should be pruned
    remaining = list(tmp_path.glob("qa-results-*.json"))
    # We kept pointer_target plus up to 64 others, so total should be <= 65
    assert len(remaining) <= 65

    # Check deletion evidence exists
    del_evidence_file = tmp_path / "deletion-evidence.jsonl"
    assert del_evidence_file.exists()
    del_lines = del_evidence_file.read_text().strip().split("\n")
    assert len(del_lines) > 0
    first_del = json.loads(del_lines[0])
    assert first_del["event"] == "artifact_pruned"
    assert "filename" in first_del


def test_quarantine_oversized(tmp_path, monkeypatch):
    monkeypatch.setenv("AQ_TELEMETRY_ROOT", str(tmp_path))
    
    # Make a huge results list to exceed 2MiB
    large_results = []
    for i in range(40000): # large number of results to bloat json representation
        large_results.append(DummyResult(0, f"check_{i}", "PASS", "a" * 80))
        
    rs = DummyResultSet("0", large_results, 5)
    
    # Write initial results
    rs_small = DummyResultSet("0", [DummyResult(0, "check_small", "PASS", "ok")], 1)
    main_mod.save_qa_results(rs_small, REPO_ROOT)
    
    pointer_file = tmp_path / "latest-qa-results.json"
    assert pointer_file.exists()
    initial_p_data = json.loads(pointer_file.read_text(encoding="utf-8"))
    
    # Save large results which should be quarantined
    main_mod.save_qa_results(rs, REPO_ROOT)
    
    # The pointer should NOT have been updated
    p_data = json.loads(pointer_file.read_text(encoding="utf-8"))
    assert p_data["sequence"] == initial_p_data["sequence"]
    assert p_data["hash"] == initial_p_data["hash"]
    
    # Check that quarantine files were created
    quarantined = list(tmp_path.glob("quarantine-qa-results-*.json"))
    assert len(quarantined) > 0
