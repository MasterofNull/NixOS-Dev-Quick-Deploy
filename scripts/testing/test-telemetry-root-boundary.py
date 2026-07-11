#!/usr/bin/env python3
"""Recovery regression for production authority and repository projection topology."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))

import qa_evidence_store as store_module
from qa_evidence_store import EvidenceStoreError, QAEvidenceStore, mount_targets, validate_repo_projection


def test_repo_projection_is_real_directory() -> None:
    projection = ROOT / ".agents" / "telemetry"
    assert projection.is_dir()
    assert not projection.is_symlink()
    assert validate_repo_projection(mountinfo_text="") == projection


def test_environment_cannot_redirect_production() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        previous = os.environ.get("AQ_TELEMETRY_ROOT")
        os.environ["AQ_TELEMETRY_ROOT"] = tmp
        try:
            assert store_module.PRODUCTION_ROOT != Path(tmp)
        finally:
            if previous is None:
                os.environ.pop("AQ_TELEMETRY_ROOT", None)
            else:
                os.environ["AQ_TELEMETRY_ROOT"] = previous


def test_symlink_and_mount_target_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        real = base / "real"
        real.mkdir()
        link = base / "link"
        link.symlink_to(real, target_is_directory=True)
        try:
            QAEvidenceStore.for_isolated_test(link)
        except EvidenceStoreError as exc:
            assert exc.reason_code == "ROOT_SYMLINK"
        else:
            raise AssertionError("symlink root accepted")
        mount_line = f"24 1 0:1 / {real} rw - tmpfs tmpfs rw"
        try:
            QAEvidenceStore.for_isolated_test(real, mountinfo_text=mount_line)
        except EvidenceStoreError as exc:
            assert exc.reason_code == "ROOT_MOUNT_TARGET"
        else:
            raise AssertionError("mount target accepted")
        assert real.is_dir() and not real.is_symlink()


def test_absolute_and_traversal_targets_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = QAEvidenceStore.for_isolated_test(Path(tmp))
        for target in ("/etc/passwd", "../escape", "nested/file"):
            try:
                store._target(target)
            except EvidenceStoreError as exc:
                assert exc.reason_code == "TARGET_PATH_INVALID"
            else:
                raise AssertionError(f"unsafe target accepted: {target}")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
