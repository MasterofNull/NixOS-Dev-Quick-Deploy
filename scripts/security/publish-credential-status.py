#!/usr/bin/env python3
"""Publish a metadata-only Security Center status snapshot.

This root-run one-shot intentionally checks only runtime secret *presence*.
It never opens a secret file, decrypts SOPS data, or emits file locations.
The dashboard consumes the resulting, allowlisted snapshot as an unprivileged
reader; it does not invoke this publisher.
"""

from __future__ import annotations

import argparse
import datetime as dt
import grp
import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import Any

SCHEMA = "aqos.security-credential-status.v1"
CATALOG_SCHEMA = "aqos.security-credential-catalog.v1"
ALLOWED_STORAGES = {"sops", "pam", "gnome-keyring", "password-store", "hardware", "external"}
ALLOWED_RISK_CLASSES = {"R0", "R1", "R2", "R3", "R4"}
SAFE_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}$")
SAFE_RUNTIME_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
CATALOG_FIELDS = {
    "id", "label", "purpose", "storage", "risk_class", "scope", "owner",
    "status_source", "runtime_name", "consumers", "capabilities", "value_policy",
    "actions", "impact", "rotation_evidence", "authentication", "recovery",
    "provider_semantics",
}
STATUS_SOURCES = {"runtime-secret", "managed-separately"}


def load_catalog(path: Path) -> list[dict[str, Any]]:
    """Load the fixed catalog; reject malformed declarations before publishing."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema") != CATALOG_SCHEMA or not isinstance(raw.get("credentials"), list):
        raise ValueError("invalid credential catalog")
    credentials: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw["credentials"]:
        if not isinstance(entry, dict) or set(entry) != CATALOG_FIELDS:
            raise ValueError("credential catalog has unsupported fields")
        scalar_fields = CATALOG_FIELDS - {"runtime_name", "consumers", "capabilities", "actions"}
        if not all(isinstance(entry[key], str) and entry[key] for key in scalar_fields):
            raise ValueError("credential catalog has invalid text fields")
        if (
            entry["id"] in seen
            or not SAFE_IDENTIFIER.fullmatch(entry["id"])
            or entry["storage"] not in ALLOWED_STORAGES
            or entry["risk_class"] not in ALLOWED_RISK_CLASSES
            or entry["status_source"] not in STATUS_SOURCES
        ):
            raise ValueError("credential catalog has duplicate or invalid entry")
        runtime_name = entry["runtime_name"]
        if entry["status_source"] == "runtime-secret":
            if not isinstance(runtime_name, str) or not SAFE_RUNTIME_NAME.fullmatch(runtime_name):
                raise ValueError("runtime secret has invalid runtime name")
        elif runtime_name is not None:
            raise ValueError("managed-separately credential cannot have runtime name")
        for field in ("consumers", "capabilities", "actions"):
            values = entry[field]
            if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
                raise ValueError(f"credential catalog has invalid {field}")
        seen.add(entry["id"])
        credentials.append(entry)
    return credentials


def runtime_presence(runtime_dir: Path, runtime_name: str) -> str:
    """Return presence metadata without reading a credential or exposing its path."""
    if not runtime_dir.is_dir():
        return "unavailable"
    try:
        candidate = runtime_dir / runtime_name
        info = candidate.lstat()
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unavailable"
    return "present" if stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode) else "unavailable"


def discovered_runtime_names(runtime_dir: Path) -> set[str]:
    """List safe runtime entry names without reading their contents."""
    try:
        directory = os.open(runtime_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return set()
    try:
        names: set[str] = set()
        for name in os.listdir(directory):
            if not SAFE_RUNTIME_NAME.fullmatch(name):
                continue
            try:
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                names.add(name)
        return names
    finally:
        os.close(directory)


def build_snapshot(catalog: list[dict[str, Any]], runtime_dir: Path, declared_names: set[str]) -> dict[str, Any]:
    credentials = []
    counts = {"present": 0, "missing": 0, "unavailable": 0, "managed_separately": 0, "not_enabled": 0}
    catalog_runtime_names = {
        entry["runtime_name"] for entry in catalog if entry["status_source"] == "runtime-secret"
    }
    discovered_names = discovered_runtime_names(runtime_dir)
    uncataloged = len((declared_names | discovered_names) - catalog_runtime_names)
    for entry in catalog:
        if entry["status_source"] == "managed-separately":
            readiness = "managed_separately"
        elif entry["runtime_name"] not in declared_names:
            readiness = "not_enabled"
        else:
            readiness = runtime_presence(runtime_dir, entry["runtime_name"])
        counts[readiness] += 1
        credentials.append({
            "id": entry["id"],
            "label": entry["label"],
            "purpose": entry["purpose"],
            "storage": entry["storage"],
            "risk_class": entry["risk_class"],
            "consumers": entry["consumers"],
            "rotation": entry["actions"][0],
            "readiness": readiness,
            "mutation_state": "not_available_yet",
        })
    overall = "protected" if counts["missing"] == counts["unavailable"] == uncataloged == 0 else "needs_attention"
    if counts["unavailable"]:
        overall = "unavailable"
    return {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "overall_state": overall,
        "summary": {"total": len(credentials), **counts, "uncataloged": uncataloged},
        "credentials": credentials,
    }


def atomic_publish(snapshot: dict[str, Any], output: Path, group: str, *, owner_uid: int = 0) -> None:
    """Publish through a verified directory descriptor; never follow a swapped parent."""
    group_id = grp.getgrnam(group).gr_gid
    directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    directory_info = os.fstat(directory)
    if directory_info.st_uid != owner_uid or directory_info.st_mode & 0o022:
        os.close(directory)
        raise PermissionError("unsafe output directory ownership or mode")
    temporary = f".credential-status-{secrets.token_hex(12)}"
    descriptor = -1
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(snapshot, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fchown(handle.fileno(), owner_uid, group_id)
            os.fchmod(handle.fileno(), 0o640)
            os.fsync(handle.fileno())
        os.rename(temporary, output.name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish metadata-only credential status")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, default=Path("/run/secrets"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--declared-name", action="append", default=[])
    args = parser.parse_args()
    declared = set(args.declared_name)
    if any(not SAFE_RUNTIME_NAME.fullmatch(name) for name in declared):
        raise SystemExit("invalid declared credential name")
    atomic_publish(build_snapshot(load_catalog(args.catalog), args.runtime_dir, declared), args.output, args.group)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
