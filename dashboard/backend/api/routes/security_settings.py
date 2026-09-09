"""Read-only, metadata-only Security Center projection.

This router reads a root-published snapshot. It has no SOPS, password, broker,
or mutation authority and intentionally fails closed when that snapshot cannot
be safely read or validated.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()
_SCHEMA = "aqos.security-credential-status.v1"
_ROOT_FIELDS = {"schema", "generated_at", "overall_state", "summary", "credentials"}
_CREDENTIAL_FIELDS = {"id", "label", "purpose", "storage", "risk_class", "consumers", "rotation", "readiness", "mutation_state"}
_STORAGES = {"sops", "pam", "gnome-keyring", "password-store", "hardware", "external"}
_RISK_CLASSES = {"R0", "R1", "R2", "R3", "R4"}
_READINESS = {"present", "missing", "unavailable", "managed_separately", "not_enabled"}
_OVERALL_STATES = {"protected", "needs_attention", "unavailable"}
_MAX_SNAPSHOT_BYTES = 256 * 1024
_MAX_SNAPSHOT_AGE_SECONDS = 15 * 60
_MAX_FUTURE_SKEW_SECONDS = 60
_SNAPSHOT_PATH = Path("/run/aqos-security/credential-status.json")


def _snapshot_path() -> Path:
    return _SNAPSHOT_PATH


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Security Center status is temporarily unavailable.")


def _read_snapshot(
    path: Path | None = None,
    *,
    expected_uid: int = 0,
    now: datetime | None = None,
) -> dict[str, Any]:
    path = path or _snapshot_path()
    directory = -1
    descriptor = -1
    try:
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        parent_info = os.fstat(directory)
        if parent_info.st_uid != expected_uid or parent_info.st_mode & 0o022:
            raise ValueError("unsafe snapshot directory")
        descriptor = os.open(path.name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=directory)
        info = os.fstat(descriptor)
        allowed_gids = {os.getegid(), *os.getgroups()}
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != expected_uid
            or info.st_gid not in allowed_gids
            or info.st_mode & 0o027
            or not (0 < info.st_size <= _MAX_SNAPSHOT_BYTES)
        ):
            raise ValueError("unsafe snapshot")
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            raw = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        raise _unavailable()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if directory >= 0:
            os.close(directory)
    if not isinstance(raw, dict) or set(raw) != _ROOT_FIELDS or raw.get("schema") != _SCHEMA:
        raise _unavailable()
    if raw.get("overall_state") not in _OVERALL_STATES or not isinstance(raw.get("generated_at"), str):
        raise _unavailable()
    try:
        generated_at = datetime.fromisoformat(raw["generated_at"].replace("Z", "+00:00"))
        if generated_at.tzinfo is None:
            raise ValueError("timestamp lacks timezone")
        age = ((now or datetime.now(timezone.utc)) - generated_at).total_seconds()
        if age > _MAX_SNAPSHOT_AGE_SECONDS or age < -_MAX_FUTURE_SKEW_SECONDS:
            raise ValueError("stale or future snapshot")
    except (TypeError, ValueError, OverflowError):
        raise _unavailable()
    summary = raw.get("summary")
    credentials = raw.get("credentials")
    state_keys = {"present", "missing", "unavailable", "managed_separately", "not_enabled"}
    if not isinstance(summary, dict) or set(summary) != {"total", "uncataloged", *state_keys}:
        raise _unavailable()
    if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in summary.values()) or not isinstance(credentials, list):
        raise _unavailable()
    if summary["total"] != len(credentials) or sum(summary[key] for key in state_keys) != summary["total"]:
        raise _unavailable()
    seen: set[str] = set()
    for credential in credentials:
        if not isinstance(credential, dict) or set(credential) != _CREDENTIAL_FIELDS:
            raise _unavailable()
        if not all(isinstance(credential[key], str) for key in _CREDENTIAL_FIELDS - {"consumers"}):
            raise _unavailable()
        if not isinstance(credential["consumers"], list) or not all(isinstance(item, str) for item in credential["consumers"]):
            raise _unavailable()
        if (
            not credential["id"]
            or credential["id"] in seen
            or credential["storage"] not in _STORAGES
            or credential["risk_class"] not in _RISK_CLASSES
            or credential["readiness"] not in _READINESS
            or credential["mutation_state"] != "not_available_yet"
            or any(len(value) > 512 for key, value in credential.items() if key != "consumers")
            or any(not item or len(item) > 128 for item in credential["consumers"])
        ):
            raise _unavailable()
        seen.add(credential["id"])
    observed = {key: sum(row["readiness"] == key for row in credentials) for key in state_keys}
    if any(summary[key] != observed[key] for key in state_keys):
        raise _unavailable()
    expected_overall = "protected"
    if summary["unavailable"]:
        expected_overall = "unavailable"
    elif summary["missing"] or summary["uncataloged"]:
        expected_overall = "needs_attention"
    if raw["overall_state"] != expected_overall:
        raise _unavailable()
    return raw


@router.get("/security-settings/status")
def get_security_settings_status() -> JSONResponse:
    """Return the validated metadata-only snapshot; never secrets or paths."""
    response = JSONResponse(_read_snapshot())
    response.headers["Cache-Control"] = "no-store"
    return response
