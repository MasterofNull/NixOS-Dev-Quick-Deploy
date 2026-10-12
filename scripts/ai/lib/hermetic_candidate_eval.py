#!/usr/bin/env python3
"""Hermetic candidate evaluation evidence -- ECC outcome parity P0-D.

Binds artifact digest, exact containment config (bwrap/sandbox), fixtures,
actual exit/output/resource metrics, and reviewed promotion into a tamper-evident,
fail-closed receipt. Receipt integrity alone never passes candidate behavior;
an independent, authorized reviewer promotion is strictly required.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

SCHEMA_VERSION = "aqos-hermetic-candidate-eval/v1"

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9/+_=-]{24,}"),
)


class HermeticEvalError(ValueError):
    """Fail-closed evaluation verification error with a stable reason code."""

    def __init__(self, reason: str, message: str):
        super().__init__(f"{reason}: {message}")
        self.reason = reason


def canonical_bytes(data: Mapping[str, Any]) -> bytes:
    """Deterministic JSON serialization for cryptographic digest chaining."""
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256_digest(content: bytes | str) -> str:
    """Return hex SHA-256 digest."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def compute_file_digest(file_path: Path | str) -> str:
    """Compute SHA-256 hex digest of a file."""
    path = Path(file_path)
    if not path.is_file():
        raise HermeticEvalError("artifact_not_found", f"Target artifact file missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_for_secrets(text: str) -> bool:
    """Return True if any forbidden secret token pattern is found."""
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False


def build_evaluation_receipt(
    artifact_path: Path | str,
    candidate_id: str,
    containment_config: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    reviewer_promotion: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a canonical evaluation receipt binding containment, execution and review."""
    artifact_digest = compute_file_digest(artifact_path)

    backend = containment_config.get("backend", "bwrap")
    if backend not in {"bwrap", "mock", "process"}:
        raise HermeticEvalError("invalid_backend", f"Unsupported containment backend: {backend}")

    network = containment_config.get("network", "none")
    if network not in {"none", "allow"}:
        raise HermeticEvalError("invalid_network", f"Invalid network mode: {network}")

    stdout = execution_result.get("stdout", "")
    stderr = execution_result.get("stderr", "")
    combined_output = f"{stdout}\n{stderr}"

    secret_detected = scan_for_secrets(combined_output)
    escape_detected = bool(execution_result.get("escape_detected", False))
    network_attempted = bool(execution_result.get("network_attempted", False))
    write_violation = bool(execution_result.get("write_violation", False))
    timeout_hit = bool(execution_result.get("timeout_hit", False))
    exit_code = int(execution_result.get("exit_code", 0))

    evidence = {
        "escape_denied": not escape_detected,
        "secret_scan_clean": not secret_detected,
        "network_denied": not (network == "none" and network_attempted),
        "write_denied": not write_violation,
        "within_timeout": not timeout_hit,
    }

    if not all(evidence.values()) or exit_code != 0:
        verdict = "FAIL_CLOSED"
    else:
        verdict = "CANDIDATE_EXECUTED_PASS"

    core_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "artifact_digest": artifact_digest,
        "containment": {
            "backend": backend,
            "network": network,
            "read_only_paths": list(containment_config.get("read_only_paths", ["/"])),
            "writable_tmp": str(containment_config.get("writable_tmp", "/tmp/sandbox")),
            "memory_limit_mb": int(containment_config.get("memory_limit_mb", 512)),
            "timeout_seconds": int(containment_config.get("timeout_seconds", 30)),
        },
        "execution_metrics": {
            "exit_code": exit_code,
            "duration_ms": float(execution_result.get("duration_ms", 0.0)),
            "peak_memory_mb": float(execution_result.get("peak_memory_mb", 0.0)),
            "stdout_digest": sha256_digest(stdout),
            "stderr_digest": sha256_digest(stderr),
        },
        "evidence": evidence,
        "evaluation_verdict": verdict,
    }

    if reviewer_promotion is not None:
        core_payload["reviewer_promotion"] = dict(reviewer_promotion)

    payload_hash = sha256_digest(canonical_bytes(core_payload))
    core_payload["receipt_digest"] = payload_hash
    return core_payload


def verify_evaluation_receipt(receipt: Mapping[str, Any], expected_artifact_path: Path | str | None = None) -> dict[str, Any]:
    """Fail-closed verification of a candidate evaluation receipt.

    Requires:
    1. Schema version conformance.
    2. Valid cryptographic digest chain over canonical bytes.
    3. Matching artifact digest (when artifact path provided).
    4. Clean containment evidence (no escape, secrets, network leaks, write violations, or timeouts).
    5. Independent reviewed promotion (implementer self-review rejected).
    """
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise HermeticEvalError("schema_mismatch", f"Unsupported schema: {receipt.get('schema_version')}")

    receipt_digest = receipt.get("receipt_digest")
    if not isinstance(receipt_digest, str) or len(receipt_digest) != 64:
        raise HermeticEvalError("receipt_corrupted", "Missing or invalid receipt_digest format")

    # Reconstruct core payload without receipt_digest to check signature
    test_payload = {k: v for k, v in receipt.items() if k != "receipt_digest"}
    expected_digest = sha256_digest(canonical_bytes(test_payload))
    if receipt_digest != expected_digest:
        raise HermeticEvalError("receipt_corrupted", "Receipt hash mismatch: data has been altered")

    # Artifact digest verification
    if expected_artifact_path is not None:
        actual_artifact_digest = compute_file_digest(expected_artifact_path)
        if receipt.get("artifact_digest") != actual_artifact_digest:
            raise HermeticEvalError("artifact_digest_mismatch", "Artifact digest does not match evaluated evidence")

    # Containment assertions
    evidence = receipt.get("evidence", {})
    if not evidence.get("escape_denied"):
        raise HermeticEvalError("escape_detected", "Containment escape violation detected")
    if not evidence.get("secret_scan_clean"):
        raise HermeticEvalError("secret_detected", "Forbidden secret credentials detected in execution output")
    if not evidence.get("network_denied"):
        raise HermeticEvalError("network_violation", "Unauthorized network activity attempted in hermetic sandbox")
    if not evidence.get("write_denied"):
        raise HermeticEvalError("write_violation", "Host file modification attempted outside sandbox writable root")
    if not evidence.get("within_timeout"):
        raise HermeticEvalError("timeout", "Execution exceeded allotted hermetic timeout limit")

    if receipt.get("evaluation_verdict") != "CANDIDATE_EXECUTED_PASS":
        raise HermeticEvalError("execution_failed", f"Underlying execution failed: {receipt.get('evaluation_verdict')}")

    # Reviewer promotion requirement
    promotion = receipt.get("reviewer_promotion")
    if not promotion:
        raise HermeticEvalError("promotion_missing", "Receipt integrity alone cannot promote; independent review required")

    reviewer_role = promotion.get("reviewer_role", "")
    if reviewer_role in {"implementer", "author", "self"}:
        raise HermeticEvalError("reviewer_conflict", f"Reviewer role '{reviewer_role}' cannot self-promote candidate")

    verdict = promotion.get("reviewer_verdict")
    if verdict != "PROMOTED":
        raise HermeticEvalError("promotion_rejected", f"Reviewer did not grant promotion (verdict={verdict})")

    return {
        "status": "verified",
        "candidate_id": receipt.get("candidate_id"),
        "verdict": "PROMOTED",
        "receipt_digest": receipt_digest,
    }


def dashboard_summary(repo_root: Path | str | None = None) -> dict[str, Any]:
    """Summary of hermetic candidate evaluation capability for dashboard integration."""
    return {
        "available": True,
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "containment_backends": ["bwrap", "mock", "process"],
        "policy": "fail_closed_independent_review_required",
    }
