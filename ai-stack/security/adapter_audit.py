"""
ai-stack/security/adapter_audit.py

MIC-G Phase 164: Static Integrity Guard for PEFT/LoRA adapters (P1 + P2)

P1 — Supply Chain RCE: malicious adapter_config.json with dangerous parent_library
     imports; pickle-serialized weights with __reduce__ payloads.
P2 — Adapter Combinatorial Interference (CoLoRA): overlapping rank-1 weight updates
     that collude to trigger safety bypasses or reasoning collapse.

Design doc: .agents/designs/MODEL-INTEGRITY-CAPABILITY-GUARD.md §3.1

Usage:
    from ai_stack.security.adapter_audit import audit_adapter, AdapterAuditResult

    result = audit_adapter(Path("/var/lib/models/my-adapter"))
    if not result.safe:
        raise RuntimeError(f"Adapter rejected: {result.violations}")
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Allowlists
# ---------------------------------------------------------------------------

TRUSTED_PARENT_LIBRARIES: frozenset[str] = frozenset({
    "transformers",
    "diffusers",
    "peft",
    "safetensors",
    "sentence_transformers",
    "harness-core",
    "trl",
    "bitsandbytes",
})

# Known safe adapter types (peft AdapterType values)
SAFE_ADAPTER_TYPES: frozenset[str] = frozenset({
    "LORA",
    "LOHA",
    "LOKR",
    "ADALORA",
    "IA3",
    "VERA",
    "BONE",
    "BOFT",
    "FOURIERFT",
    "OFT",
    "POLY",
    "LN_TUNING",
    "PREFIX_TUNING",
    "PROMPT_TUNING",
    "P_TUNING",
    "MULTITASK_PROMPT_TUNING",
    "XLORA",
})

# Config keys that should NEVER contain code-like strings
SAFE_VALUE_TYPES: tuple[type, ...] = (str, int, float, bool, list, dict, type(None))

_MAX_CONFIG_VALUE_LEN = 512  # flag values longer than this for manual review
_MAX_METADATA_VALUE_LEN = 256  # safetensors header metadata


@dataclass
class AdapterAuditResult:
    adapter_path: str
    safe: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    format: str = "unknown"
    hash_sha256: Optional[str] = None
    hash_verified: bool = False
    parent_library: Optional[str] = None
    adapter_type: Optional[str] = None
    combinatorial_risk: float = 0.0
    checked_at: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_SAFETENSORS_MAGIC = b'{'  # safetensors header starts with '{'
_PYTORCH_MAGIC = b'\x80\x02'  # pickle protocol 2 magic
_PYTORCH_MAGIC2 = b'PK'  # zip-based (newer torch.save)


def _detect_weight_format(path: Path) -> str:
    """Detect the format of a model weight file."""
    try:
        with open(path, "rb") as f:
            header = f.read(8)
    except OSError:
        return "unreadable"

    # safetensors: 8-byte little-endian uint64 header length, then JSON
    if len(header) >= 8:
        try:
            hlen = struct.unpack_from("<Q", header)[0]
            if 0 < hlen < 10_000_000:  # plausible header length
                return "safetensors"
        except struct.error:
            pass

    if header[:2] in (_PYTORCH_MAGIC, _PYTORCH_MAGIC2):
        return "pickle"  # DANGEROUS

    return "unknown"


def _scan_safetensors_metadata(path: Path) -> list[str]:
    """
    Scan safetensors header metadata for suspicious content.
    Returns list of violation descriptions.
    """
    violations: list[str] = []
    try:
        with open(path, "rb") as f:
            raw_len = f.read(8)
            hlen = struct.unpack_from("<Q", raw_len)[0]
            if hlen > 10_000_000:
                violations.append(f"safetensors header length suspiciously large: {hlen}")
                return violations
            header_bytes = f.read(hlen)
        header = json.loads(header_bytes)
        metadata = header.get("__metadata__", {})
        for key, value in metadata.items():
            if not isinstance(value, str):
                continue
            if len(value) > _MAX_METADATA_VALUE_LEN:
                violations.append(f"metadata[{key!r}] length {len(value)} > {_MAX_METADATA_VALUE_LEN} (possible payload)")
            # Check for obvious code patterns in metadata
            if any(tok in value for tok in ["import ", "exec(", "eval(", "__import__", "subprocess"]):
                violations.append(f"metadata[{key!r}] contains code-like pattern")
    except Exception as exc:
        violations.append(f"safetensors header parse error: {exc}")
    return violations


# ---------------------------------------------------------------------------
# Config audit
# ---------------------------------------------------------------------------

def _audit_adapter_config(config_path: Path) -> tuple[list[str], list[str], dict]:
    """
    Audit adapter_config.json for supply chain risks.
    Returns (violations, warnings, config_dict).
    """
    violations: list[str] = []
    warnings: list[str] = []

    if not config_path.exists():
        warnings.append("adapter_config.json not found — cannot verify adapter metadata")
        return violations, warnings, {}

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        violations.append(f"adapter_config.json is not valid JSON: {exc}")
        return violations, warnings, {}

    # P1: parent_library check
    parent_lib = config.get("base_model_name_or_path") or config.get("parent_library") or ""
    if parent_lib:
        # Strip to just the package name (not the full model path)
        pkg = parent_lib.split("/")[0].split("\\")[0].lower()
        if pkg not in {lib.lower() for lib in TRUSTED_PARENT_LIBRARIES}:
            # Model paths like "meta-llama/Llama-2-7b" are fine; only flag if it looks like a package
            if not ("/" in parent_lib or "\\" in parent_lib):
                violations.append(
                    f"parent_library '{parent_lib}' not in trusted set: {sorted(TRUSTED_PARENT_LIBRARIES)}"
                )

    # Check peft_type / task_type for known safe values
    peft_type = config.get("peft_type", "").upper()
    if peft_type and peft_type not in SAFE_ADAPTER_TYPES:
        warnings.append(f"Unknown peft_type '{peft_type}' — not in known safe adapter types")

    # Check for suspiciously long config values
    for key, value in config.items():
        if isinstance(value, str) and len(value) > _MAX_CONFIG_VALUE_LEN:
            violations.append(f"config[{key!r}] has unusually long string value ({len(value)} chars) — possible code embedding")
        # Check for code-like patterns in string values
        if isinstance(value, str) and any(
            tok in value for tok in ["exec(", "eval(", "__import__", "subprocess.run", "os.system"]
        ):
            violations.append(f"config[{key!r}] contains code-execution pattern")

    return violations, warnings, config


# ---------------------------------------------------------------------------
# Hash verification
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _verify_hash(weight_path: Path, expected_hash: Optional[str]) -> bool:
    """Check if file hash matches expected. Returns True if verified (or no hash to check)."""
    if not expected_hash:
        return False  # cannot verify
    actual = _sha256_file(weight_path)
    return actual == expected_hash


# ---------------------------------------------------------------------------
# Combinatorial risk (P2) — simplified geometry check
# ---------------------------------------------------------------------------

def _estimate_combinatorial_risk(
    adapter_path: Path,
    loaded_adapters: list[Path],
) -> float:
    """
    Estimate collision risk between this adapter and already-loaded adapters.
    For now: uses filename/config overlap as a proxy for weight-space similarity.
    Real implementation would compare dominant singular vectors of LoRA matrices.
    Returns 0.0-1.0 risk score.
    """
    if not loaded_adapters:
        return 0.0

    # Read this adapter's target modules
    config_path = adapter_path / "adapter_config.json"
    if not config_path.exists():
        return 0.0

    try:
        this_config = json.loads(config_path.read_text())
        this_modules = set(this_config.get("target_modules", []))
        this_rank = this_config.get("r", this_config.get("rank", 0))
    except Exception:
        return 0.0

    max_overlap = 0.0
    for other_path in loaded_adapters:
        other_config_path = other_path / "adapter_config.json"
        if not other_config_path.exists():
            continue
        try:
            other_config = json.loads(other_config_path.read_text())
            other_modules = set(other_config.get("target_modules", []))
            other_rank = other_config.get("r", other_config.get("rank", 0))
        except Exception:
            continue

        if not this_modules or not other_modules:
            continue

        # Module overlap ratio
        module_overlap = len(this_modules & other_modules) / len(this_modules | other_modules)

        # Rank similarity penalty (same-rank adapters targeting same modules = highest risk)
        rank_factor = 1.0 if (this_rank and other_rank and abs(this_rank - other_rank) <= 4) else 0.7

        risk = module_overlap * rank_factor
        max_overlap = max(max_overlap, risk)

    return round(max_overlap, 3)


# ---------------------------------------------------------------------------
# Main audit entry point
# ---------------------------------------------------------------------------

def audit_adapter(
    adapter_path: Path,
    loaded_adapters: Optional[list[Path]] = None,
    expected_hash: Optional[str] = None,
) -> AdapterAuditResult:
    """
    Audit a PEFT/LoRA adapter directory for supply chain and combinatorial risks.

    Args:
        adapter_path: Path to adapter directory (contains adapter_config.json + weight files).
        loaded_adapters: List of already-loaded adapter paths (for combinatorial risk check).
        expected_hash: Expected SHA256 hash of the primary weight file (for hash verification).

    Returns:
        AdapterAuditResult with safe=True only if no hard violations found.
    """
    from datetime import datetime, timezone
    result = AdapterAuditResult(
        adapter_path=str(adapter_path),
        safe=True,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )

    if not adapter_path.exists():
        result.safe = False
        result.violations.append(f"Adapter path does not exist: {adapter_path}")
        return result

    # 1. Audit adapter_config.json
    config_path = adapter_path / "adapter_config.json"
    config_violations, config_warnings, config = _audit_adapter_config(config_path)
    result.violations.extend(config_violations)
    result.warnings.extend(config_warnings)
    result.parent_library = config.get("base_model_name_or_path")
    result.adapter_type = config.get("peft_type")

    # 2. Find and audit weight files
    weight_candidates = (
        list(adapter_path.glob("*.safetensors")) +
        list(adapter_path.glob("*.bin")) +
        list(adapter_path.glob("*.pt")) +
        list(adapter_path.glob("adapter_model.*"))
    )

    for weight_path in weight_candidates:
        fmt = _detect_weight_format(weight_path)

        if fmt == "pickle":
            result.violations.append(
                f"DANGEROUS: {weight_path.name} is pickle-serialized — "
                "arbitrary code execution risk. Only safetensors format is allowed."
            )
            result.format = "pickle"
        elif fmt == "safetensors":
            result.format = "safetensors"
            # Scan safetensors metadata for embedded code
            metadata_violations = _scan_safetensors_metadata(weight_path)
            result.violations.extend(metadata_violations)
            # Hash verification
            if expected_hash:
                result.hash_sha256 = _sha256_file(weight_path)
                result.hash_verified = (result.hash_sha256 == expected_hash)
                if not result.hash_verified:
                    result.violations.append(
                        f"Hash mismatch: expected {expected_hash[:16]}... "
                        f"got {(result.hash_sha256 or '')[:16]}..."
                    )
        elif fmt == "unknown" and weight_path.suffix not in (".json", ".md", ".txt", ".yaml", ".yml"):
            result.warnings.append(f"Unknown format for {weight_path.name}")

    if not weight_candidates:
        result.warnings.append("No weight files found in adapter directory")

    # 3. Combinatorial risk
    if loaded_adapters:
        result.combinatorial_risk = _estimate_combinatorial_risk(adapter_path, loaded_adapters)
        if result.combinatorial_risk > 0.7:
            result.violations.append(
                f"HIGH combinatorial risk ({result.combinatorial_risk:.2f}) with already-loaded adapters "
                "— overlapping target modules with same rank may cause safety collapse or reasoning interference"
            )
        elif result.combinatorial_risk > 0.4:
            result.warnings.append(
                f"Moderate combinatorial risk ({result.combinatorial_risk:.2f}) with loaded adapters"
            )

    # Final safe determination
    result.safe = len(result.violations) == 0

    if result.violations:
        logger.warning(
            "adapter_audit: REJECTED %s — %d violation(s): %s",
            adapter_path.name,
            len(result.violations),
            result.violations[:2],
        )
    else:
        logger.info(
            "adapter_audit: PASSED %s (format=%s, comb_risk=%.2f, warnings=%d)",
            adapter_path.name,
            result.format,
            result.combinatorial_risk,
            len(result.warnings),
        )

    return result


def audit_adapters_bulk(
    adapter_paths: list[Path],
    expected_hashes: Optional[dict[str, str]] = None,
) -> tuple[list[AdapterAuditResult], bool]:
    """
    Audit multiple adapters with combinatorial risk checking.
    Returns (results, all_safe).
    """
    results: list[AdapterAuditResult] = []
    loaded_so_far: list[Path] = []
    all_safe = True

    for path in adapter_paths:
        expected_hash = (expected_hashes or {}).get(str(path))
        result = audit_adapter(path, loaded_adapters=loaded_so_far, expected_hash=expected_hash)
        results.append(result)
        if result.safe:
            loaded_so_far.append(path)
        else:
            all_safe = False

    return results, all_safe
