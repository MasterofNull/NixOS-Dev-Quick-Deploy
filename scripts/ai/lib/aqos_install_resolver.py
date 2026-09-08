#!/usr/bin/env python3
"""Trusted AQ-OS install-plan resolver and projection compiler."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA_VERSION = "aqos-install-plan/v1"
HARDWARE_SUMMARY_VERSION = "aqos-hardware-summary/v1"
MAX_SAFE_INTEGER = (1 << 53) - 1


class ResolverError(ValueError):
    """Fail-closed resolver error with a stable reason code."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def _reject(reason: str, message: str) -> None:
    raise ResolverError(reason, message)


def parse_json_strict(payload: str | bytes) -> Any:
    """Parse JSON input while rejecting duplicate keys and non-finite numbers."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                _reject("duplicate_json_key", f"duplicate JSON key: {key}")
            out[key] = value
        return out

    try:
        return json.loads(
            payload,
            object_pairs_hook=pairs,
            parse_constant=lambda value: _reject("number_not_finite", f"non-finite number: {value}"),
        )
    except ResolverError:
        raise
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
        raise ResolverError("json_invalid", "invalid JSON input") from exc


def _jcs_string(value: str) -> str:
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        _reject("unicode_invalid", "lone UTF-16 surrogate is not valid I-JSON")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def jcs_bytes(value: Any) -> bytes:
    """RFC 8785 canonical JSON for the resolver's integer-only I-JSON domain."""
    def encode(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > MAX_SAFE_INTEGER:
                _reject("integer_out_of_range", "integer exceeds the I-JSON exact range")
            return str(item)
        if isinstance(item, float):
            if not math.isfinite(item):
                _reject("number_not_finite", "non-finite number is not valid I-JSON")
            _reject("number_not_supported", "resolver artifacts use integer-only numbers")
        if isinstance(item, str):
            return _jcs_string(item)
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, Mapping):
            if not all(isinstance(key, str) for key in item):
                _reject("object_key_invalid", "JSON object keys must be strings")
            for key in item:
                _jcs_string(key)
            keys = sorted(item, key=_utf16_sort_key)
            return "{" + ",".join(_jcs_string(key) + ":" + encode(item[key]) for key in keys) + "}"
        _reject("value_type_invalid", f"unsupported JSON value: {type(item).__name__}")
        raise AssertionError("unreachable")

    return encode(value).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_schema(instance: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    try:
        import jsonschema
        jsonschema.Draft202012Validator(schema).validate(instance)
    except ImportError as exc:
        raise ResolverError("schema_validator_unavailable", "jsonschema is required") from exc
    except jsonschema.ValidationError as exc:
        raise ResolverError("schema_invalid", exc.message) from exc


def _catalog_index(catalog: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {entry["id"]: entry for entry in catalog.get("modules", [])}


def _ai_evidence_material(hw: Mapping[str, Any] | None) -> dict[str, Any]:
    hw = hw or {}
    ram = hw.get("ram") or {}
    gpu = hw.get("gpu") or {}
    primary = gpu.get("primary") or {}
    return {
        "input_schema_version": hw.get("schema_version"),
        "ram_total_bytes": ram.get("total_bytes"),
        "gpu_present": bool(gpu.get("present")),
        "gpu_outcome": gpu.get("outcome"),
        "gpu_count": len(gpu.get("devices") or []),
        "memory_type": primary.get("memory_type"),
        "vendor_id": (primary.get("vendor_id") or "").lower() or None,
        "vram_total_bytes": primary.get("vram_total_bytes"),
    }


def _load_ai_fit_module():
    path = Path(__file__).with_name("ai_fit.py")
    spec = importlib.util.spec_from_file_location("aqos_resolver_ai_fit", path)
    if not spec or not spec.loader:
        _reject("ai_fit_unavailable", "cannot load the AI-fit policy evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_fit_result(result: Mapping[str, Any], hw: Mapping[str, Any] | None,
                         ai_catalog_digest: str) -> None:
    if result.get("verdict") not in {"recommended", "limited", "not_advised"}:
        _reject("ai_fit_verdict_invalid", "AI-fit evaluator returned an unknown verdict")
    if result.get("ai_fit_policy_catalog_sha256") != ai_catalog_digest:
        _reject("ai_fit_catalog_mismatch", "AI-fit result is not bound to the selected catalog")
    expected_evidence = sha256_bytes(jcs_bytes(_ai_evidence_material(hw)))
    if result.get("hardware_evidence_sha256") != expected_evidence:
        _reject("ai_fit_hardware_mismatch", "AI-fit result is not bound to this hardware evidence")


def _resolve_roles(requested: list[str], catalog: Mapping[str, Any], include_ai: bool) -> list[str]:
    index = _catalog_index(catalog)
    roles = set(requested)
    if include_ai:
        roles.add("role.ai-stack")
    pending = list(roles)
    while pending:
        role_id = pending.pop()
        entry = index.get(role_id)
        if not entry or entry.get("category") != "role":
            _reject("role_unknown", f"unknown installer role: {role_id}")
        for dependency in entry.get("deps", []):
            if dependency not in roles:
                roles.add(dependency)
                pending.append(dependency)
    for role_id in roles:
        conflicts = roles.intersection(index[role_id].get("conflicts", []))
        if conflicts:
            _reject("role_conflict", f"{role_id} conflicts with {sorted(conflicts)}")
    return sorted(roles)


def summarize_hardware(hw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Produce the closed, redacted summary bound into a resolved lock."""
    hw = hw or {}
    cpu = hw.get("cpu") or {}
    ram = hw.get("ram") or {}
    gpu = hw.get("gpu") or {}
    devices = gpu.get("devices") or []
    outcome = gpu.get("outcome")
    if ram.get("total_bytes") is None:
        evidence_status = "unknown"
    elif outcome == "insufficient_evidence":
        evidence_status = "insufficient_evidence"
    else:
        evidence_status = "sufficient"
    identity_material = {
        "probe_schema_version": hw.get("schema_version"),
        "cpu": {"architecture": cpu.get("architecture"), "model": cpu.get("model"),
                "cores": cpu.get("cores"), "threads": cpu.get("threads")},
        "ram_total_bytes": ram.get("total_bytes"),
        "gpu_devices": [
            {key: device.get(key) for key in ("bdf", "pci_class", "vendor_id", "device_id")}
            for device in devices
        ],
    }
    return {
        "summary_version": HARDWARE_SUMMARY_VERSION,
        "hardware_identity_sha256": sha256_bytes(jcs_bytes(identity_material)),
        "evidence_status": evidence_status,
        "gpu_count": len(devices),
    }


def _run(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(args, cwd=repo, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ResolverError("source_unverifiable", f"source probe failed: {' '.join(args)}") from exc
    return result.stdout.strip()


def collect_source_identity(
    repo_root: Path | str,
    host_target: str,
    nix_system: str,
    flake_installable: str,
    target_probe: Callable[[str], bool] | None = None,
    system_probe: Callable[[], str] | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    if _run(repo, "git", "status", "--porcelain=v1", "--untracked-files=all"):
        _reject("source_dirty", "resolved plans require a clean Git worktree")
    commit = _run(repo, "git", "rev-parse", "HEAD")
    tree = _run(repo, "git", "rev-parse", "HEAD^{tree}")
    object_format = _run(repo, "git", "rev-parse", "--show-object-format")
    if object_format not in {"sha1", "sha256"}:
        _reject("source_object_format", f"unsupported Git object format: {object_format}")
    lock_path = repo / "flake.lock"
    if not lock_path.is_file():
        _reject("flake_lock_missing", "flake.lock is required")
    expected_ref = f"path:{repo}#"
    if not flake_installable.startswith(expected_ref):
        _reject("flake_source_mismatch", "flake installable must reference the verified local repository")
    observed_system = (system_probe or (lambda: _nix_system(repo)))()
    if observed_system != nix_system:
        _reject("nix_system_mismatch", f"expected {nix_system}, observed {observed_system}")
    probe = target_probe or (lambda installable: _target_available(repo, installable))
    if not probe(flake_installable):
        _reject("flake_target_unavailable", f"flake target is unavailable: {flake_installable}")
    return {
        "oid_algorithm": object_format,
        "git_commit": commit,
        "git_tree": tree,
        "clean_worktree": True,
        "flake_lock_sha256": sha256_bytes(lock_path.read_bytes()),
        "nix_system": nix_system,
        "flake_installable": flake_installable,
        "host_target": host_target,
    }


def _target_available(repo: Path, installable: str) -> bool:
    try:
        subprocess.run(
            ["nix", "eval", "--raw", installable + ".config.system.stateVersion"],
            cwd=repo, check=True, capture_output=True, text=True, timeout=90,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _nix_system(repo: Path) -> str:
    return _run(repo, "nix", "eval", "--raw", "--impure", "--expr", "builtins.currentSystem")


def verify_source_identity(
    expected: Mapping[str, Any], repo_root: Path | str,
    target_probe: Callable[[str], bool] | None = None,
    system_probe: Callable[[], str] | None = None,
) -> None:
    actual = collect_source_identity(
        repo_root, expected["host_target"], expected["nix_system"],
        expected["flake_installable"], target_probe, system_probe,
    )
    if dict(expected) != actual:
        _reject("source_identity_mismatch", "checked source does not match the resolved lock")


def normalize_adapter(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize thin guided/AI/manual/legacy adapters to one request shape."""
    if kind == "manual":
        return dict(payload)
    if kind in {"guided", "ai"}:
        answers = payload.get("answers") if kind == "guided" else payload.get("proposal")
        return {"artifact_type": "request_plan", "schema_version": SCHEMA_VERSION,
                "selection": dict(answers or {}), "host_target": payload.get("host_target")}
    if kind == "legacy":
        profile = payload.get("profile", "ai-dev")
        return {"artifact_type": "request_plan", "schema_version": SCHEMA_VERSION,
                "selection": {"golden_profile": f"profile.{profile}",
                              "roles": list(payload.get("roles", [])),
                              "include_local_ai": bool(payload.get("include_local_ai", profile == "ai-dev"))},
                "host_target": payload.get("host")}
    _reject("adapter_unknown", f"unknown adapter: {kind}")
    raise AssertionError("unreachable")


def resolve_plan(
    request: Mapping[str, Any], hw: Mapping[str, Any] | None,
    module_catalog: Mapping[str, Any], module_catalog_bytes: bytes,
    ai_catalog_bytes: bytes, fieldset_bytes: bytes, schema: Mapping[str, Any],
    source_identity: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_schema(request, schema)
    parsed_module_catalog = parse_json_strict(module_catalog_bytes)
    if parsed_module_catalog != module_catalog:
        _reject("module_catalog_mismatch", "module catalog object does not match the digest-bound bytes")
    parsed_fieldset = parse_json_strict(fieldset_bytes)
    if not isinstance(parsed_fieldset, Mapping) or parsed_fieldset.get("activation") != "p0-inert":
        _reject("fieldset_invalid", "P0 requires the inert mySystem field-set contract")
    if request.get("host_target") and request["host_target"] != source_identity.get("host_target"):
        _reject("host_target_mismatch", "request host target does not match verified source identity")
    selection = request.get("selection") or {}
    profile = selection.get("golden_profile", "aqos-workstation")
    catalog_profiles = {entry["id"] for entry in module_catalog.get("modules", []) if entry.get("category") == "profile"}
    if profile != "aqos-workstation" and profile not in catalog_profiles:
        _reject("profile_unknown", f"unknown installer profile: {profile}")
    include_ai = bool(selection.get("include_local_ai", False))
    if include_ai:
        expected_ai_digest = sha256_bytes(ai_catalog_bytes)
        ai_catalog = parse_json_strict(ai_catalog_bytes)
        ai_fit_result = _load_ai_fit_module().evaluate_fit(dict(hw or {}), ai_catalog, expected_ai_digest)
        _validate_fit_result(ai_fit_result, hw, expected_ai_digest)
        if ai_fit_result.get("verdict") == "not_advised":
            _reject("local_ai_not_advised", "local AI was requested but hardware policy reports not_advised")
    roles = _resolve_roles(list(selection.get("roles", [])), module_catalog, include_ai)
    lock = {
        "artifact_type": "resolved_plan_lock",
        "schema_version": SCHEMA_VERSION,
        "selection": {"golden_profile": profile, "roles": roles, "include_local_ai": include_ai},
        "hardware_summary": summarize_hardware(hw),
        "catalog_digests": {
            "module_catalog_sha256": sha256_bytes(module_catalog_bytes),
            "ai_fit_policy_catalog_sha256": sha256_bytes(ai_catalog_bytes),
            "mysystem_fieldset_sha256": sha256_bytes(fieldset_bytes),
        },
        "source_identity": dict(source_identity),
    }
    _validate_schema(lock, schema)
    return lock


def compile_projection(
    lock: Mapping[str, Any], module_catalog: Mapping[str, Any], fieldset_bytes: bytes,
) -> dict[str, Any]:
    fieldset = parse_json_strict(fieldset_bytes)
    if not isinstance(fieldset, Mapping):
        _reject("fieldset_invalid", "mySystem field-set contract must be an object")
    if sha256_bytes(fieldset_bytes) != lock["catalog_digests"].get("mysystem_fieldset_sha256"):
        _reject("fieldset_digest_mismatch", "mySystem field-set bytes do not match the resolved lock")
    if fieldset.get("activation") != "p0-inert":
        _reject("fieldset_activation_invalid", "P0 projection requires the inert field-set contract")
    selection = lock["selection"]
    profile_id = selection["golden_profile"]
    active_profile = profile_id.removeprefix("profile.") if profile_id.startswith("profile.") else None
    # P0 can compile and hash the desired projection, but the active executor
    # cannot yet consume arbitrary mySystem role fields or independently verify
    # the lock. Activation remains fail-closed until the field-set/gateway slice.
    executable = False
    fields: dict[str, Any] = {"profile": active_profile or profile_id}
    index = _catalog_index(module_catalog)
    for role_id in selection["roles"]:
        for field in index[role_id].get("projected_mysystem_fields", []):
            fields[field] = True
    authorities = {entry["path"]: entry["authority"] for entry in fieldset.get("fields", [])}
    for field in fields:
        if authorities.get(field) != "user-intent":
            _reject("fieldset_authority_violation", f"projection cannot set installer field: {field}")
    source = lock["source_identity"]
    flake_ref, fragment = source["flake_installable"].split("#", 1)
    prefix = "nixosConfigurations."
    if not fragment.startswith(prefix) or not fragment[len(prefix):]:
        _reject("flake_installable_invalid", "P0 supports a nixosConfigurations flake installable")
    nixos_target = fragment[len(prefix):]
    repo_path = Path(flake_ref.removeprefix("path:")).resolve()
    entrypoint = str(repo_path / "nixos-quick-deploy.sh")
    argv = [entrypoint, "--host", source["host_target"],
            "--profile", active_profile or profile_id,
            "--nixos-target", nixos_target, "--flake-ref", flake_ref,
            "--skip-model-selection", "--skip-ai-secrets-bootstrap",
            "--skip-home-switch", "--build-only"]
    return {
        "resolved_plan_sha256": sha256_bytes(jcs_bytes(lock)),
        "source_identity_sha256": sha256_bytes(jcs_bytes(source)),
        "executor": {"entrypoint": entrypoint, "argv": argv, "env": {},
                     "executable": executable,
                     "blocked_reason": ("profile-not-active-until-p1" if active_profile is None
                                        else "fieldset-and-execution-verifier-not-active")},
        "nix": {"system": source["nix_system"], "flake_installable": source["flake_installable"],
                "nixos_target": nixos_target, "mySystem": fields},
    }
