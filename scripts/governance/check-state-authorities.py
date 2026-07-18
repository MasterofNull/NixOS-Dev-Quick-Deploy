#!/usr/bin/env python3
"""C0.3 bounded, read-only System State Authority checker.

Discovery only. This checker NEVER mutates inspected state, adds a runtime
writer/route/service/store, migrates storage, or writes any file. It has **no
filesystem side effects**: it emits its ``{meta, findings}`` machine document to
stdout and nothing else. Projection publication (writing the audit-card snapshot)
is the responsibility of the authorized Phase-0 integration
(``_check_state_authorities`` in ``scripts/testing/harness_qa/phases/phase0.py``),
which parses this checker's stdout and atomically publishes the fixed repo-path
snapshot. There is no ``--snapshot``/caller-supplied output path.

Operator commands: ``--machine`` (emit JSON to stdout), ``--changed`` (incremental
scan of changed tracked files), ``--explain OBJECT`` (print one registry row), and
``--strict`` (exit 1 on any ratification-blocker finding). None of them write.

Contract (CONSOLIDATED-PLAN.md §C0.3):
  * Machine output is exactly ``{"meta": {...}, "findings": [...]}``.
  * SINGLE|SPLIT_BRAIN|UNKNOWN|UNOWNED are truthful discovery values. SPLIT_BRAIN,
    UNKNOWN and UNOWNED are valid for discovery but block C0.3 *ratification*.
  * Budgets: full run <=15s, incremental <=10s, peak RSS <=256 MiB, output <=5 MiB,
    registry <=128 objects, scan <=8000 tracked production-candidate files, and
    zero inference/APU/GPU work.

Exit codes:
  0  checker ran; registry structurally valid; scan bounded (ratification-blocker
     findings may be present — that is honest discovery, not a checker failure).
  1  ``--strict`` and at least one ratification-blocker finding is present.
  2  structural/contract error (invalid registry or schema, shim missing
     owner/telemetry/deadline, projection missing rebuild source).
  3  budget breach (scan exceeds file cap, output exceeds 5 MiB, or timeout).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
import time
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    import resource  # POSIX only; used for peak-RSS evidence
except ImportError:  # pragma: no cover
    resource = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "config" / "system-state-authorities.yaml"
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "system-state-authorities.schema.json"

# Hard budget ceilings (independent of registry meta; the registry cap must be <= these).
FILE_CAP_CEILING = 8000
OUTPUT_BYTE_CEILING = 5 * 1024 * 1024
OBJECT_CEILING = 128
FULL_BUDGET_S = 15.0
INCREMENTAL_BUDGET_S = 10.0
RSS_CEILING_MIB = 256

CONDITIONS = ("SINGLE", "SPLIT_BRAIN", "UNKNOWN", "UNOWNED")
BLOCKING_CONDITIONS = ("SPLIT_BRAIN", "UNKNOWN", "UNOWNED")
ADJUDICATION_STATUSES = ("PENDING", "ADJUDICATED")
PLACEHOLDER_TOKENS = frozenset({"unassigned", "unknown", "tbd", "none", "pending"})
PLACEHOLDER_VALUES = frozenset({
    "", "owner", "system owner", "to be determined", "n a", "na", "decider",
})

# Scan only text-like source; skip anything that would read as binary or that is
# large-generated. Belt-and-suspenders alongside the registry's path exclusions.
BINARY_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".wasm", ".bin", ".so", ".o", ".pyc",
    ".map", ".onnx", ".safetensors", ".gguf",
)
MAX_FILE_BYTES = 512 * 1024  # do not read files larger than 512 KiB during the scan


def _store_in_code(line: str, store: str) -> bool:
    """True only when ``store`` occurs in code, not inside a comment or doc-string.

    The scanner is a supplementary drift detector for *literal* store writes; it
    deliberately ignores prose (Nix ``description =`` option docs, ``#``/``//``
    comments) that merely narrates a write. Variable-indirected writes are covered
    by the human-verified observed_writers census, not by this heuristic.
    """
    idx = line.find(store)
    if idx < 0:
        return False
    prefix = line[:idx]
    if "#" in prefix or "//" in prefix:
        return False
    if "description" in prefix and "=" in prefix:
        return False
    return True


def _load_yaml(path: Path) -> Any:
    try:
        import yaml
    except ImportError:
        raise SystemExit("check-state-authorities: PyYAML is required (import yaml failed)")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _peak_rss_mib() -> float | None:
    if resource is None:
        return None
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB; macOS reports bytes. Assume Linux (this harness is NixOS).
    return round(ru / 1024.0, 1)


def _git_tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False
    )
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def _git_changed() -> list[str]:
    """Tracked files changed vs HEAD plus staged — for --changed incremental mode."""
    cmd = [
        "bash", "-lc",
        "{ git diff --name-only --diff-filter=ACM 2>/dev/null || true; "
        "git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true; } "
        "| awk 'NF && !seen[$0]++'",
    ]
    out = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def _excluded(path: str, exclusions: list[str]) -> bool:
    if path.endswith(BINARY_SUFFIXES):
        return True
    for tok in exclusions:
        if tok in path:
            return True
    return False


def _validate_schema(registry: Any, findings: list[dict]) -> bool:
    """Full schema validation when jsonschema is available; structural fallback otherwise."""
    ok = True
    try:
        import jsonschema

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(registry, schema)
        except jsonschema.ValidationError as exc:  # type: ignore[attr-defined]
            ok = False
            findings.append(_f("schema_violation", "registry", "error",
                              f"{'/'.join(str(p) for p in exc.absolute_path)}: {exc.message}"[:400],
                              blocks_ratification=False))
    except ImportError:
        # Minimal structural fallback so a missing dep never masks real defects.
        if not isinstance(registry, dict) or "meta" not in registry or "authorities" not in registry:
            ok = False
            findings.append(_f("schema_violation", "registry", "error",
                              "registry missing top-level meta/authorities (jsonschema unavailable)",
                              blocks_ratification=False))
    return ok


def _f(kind: str, obj: str, severity: str, detail: str,
       blocks_ratification: bool, path: str | None = None, line: int | None = None,
       *, owner_decision_blocker: bool = False,
       observed_convergence_blocker: bool = False) -> dict:
    return {
        "kind": kind,
        "object": obj,
        "severity": severity,
        "detail": detail,
        "path": path,
        "line": line,
        "blocks_ratification": blocks_ratification,
        "owner_decision_blocker": owner_decision_blocker,
        "observed_convergence_blocker": observed_convergence_blocker,
    }


def _normalized_identity(value: Any) -> str:
    """Return the frozen NFKC/casefold/punctuation-normalized identity."""
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    alphanumeric_or_space = "".join(char if char.isalnum() else " " for char in normalized)
    return " ".join(alphanumeric_or_space.split())


def _is_placeholder_identity(value: Any) -> bool:
    normalized = _normalized_identity(value)
    return normalized in PLACEHOLDER_VALUES or bool(
        PLACEHOLDER_TOKENS.intersection(normalized.split())
    )


def _is_placeholder_owner(value: Any) -> bool:
    """Owners are placeholders only when the entire normalized identity is one."""
    normalized = _normalized_identity(value)
    return normalized in PLACEHOLDER_VALUES or normalized in PLACEHOLDER_TOKENS


def _parse_calendar_date(value: Any) -> date | None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _provenance_failure(aid: str, detail: str, findings: list[dict],
                        path: str | None = None) -> None:
    findings.append(_f(
        "adjudication_provenance_invalid", aid, "ratification-blocker", detail,
        blocks_ratification=True, path=path, owner_decision_blocker=True,
    ))


def _validate_provenance(aid: str, provenance: dict[str, Any],
                         findings: list[dict]) -> tuple[date | None, bool]:
    """Validate content-bound owner provenance without interpreting its prose."""
    valid = True
    decision_date = _parse_calendar_date(provenance.get("decision_date"))
    if decision_date is None:
        _provenance_failure(aid, "decision_date is not a real YYYY-MM-DD calendar date", findings)
        valid = False

    source_value = provenance.get("source_path")
    source_path = str(source_value or "")
    rel = Path(source_path)
    if not source_path or rel.is_absolute() or ".." in rel.parts:
        _provenance_failure(aid, "source_path must be a non-escaping repo-relative path", findings,
                            source_path or None)
        return decision_date, False

    root = REPO_ROOT.resolve()
    candidate = REPO_ROOT / rel
    try:
        cursor = candidate
        while cursor != REPO_ROOT:
            if cursor.is_symlink():
                raise ValueError("source_path or one of its parents is a symlink")
            cursor = cursor.parent
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        mode = resolved.stat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError("source_path is not a regular file")
    except (OSError, RuntimeError, ValueError) as exc:
        _provenance_failure(aid, f"invalid source artifact: {str(exc)[:220]}", findings, source_path)
        return decision_date, False

    try:
        actual_sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
    except OSError as exc:
        _provenance_failure(aid, f"source artifact is unreadable: {str(exc)[:220]}", findings,
                            source_path)
        return decision_date, False
    if actual_sha != provenance.get("source_sha256"):
        _provenance_failure(aid, "source_sha256 does not match the exact source artifact bytes",
                            findings, source_path)
        valid = False
    return decision_date, valid


def _validate_adjudications(authorities: list[dict], findings: list[dict],
                            check_date: date) -> set[str]:
    """Validate owner decisions and return authority IDs blocked on owner adjudication."""
    owner_blocked: set[str] = set()
    for authority in authorities:
        aid = str(authority.get("id", "<unnamed>"))
        status_value = authority.get("adjudication_status", "PENDING")
        status = status_value if status_value in ADJUDICATION_STATUSES else "PENDING"
        condition = authority.get("current_condition")

        if status == "PENDING":
            owner_blocked.add(aid)
            # A non-SINGLE condition finding carries the pending-decision dimension so
            # legacy Stage A retains exactly one blocker finding per row.
            if condition not in BLOCKING_CONDITIONS:
                findings.append(_f(
                    "adjudication_incomplete", aid, "ratification-blocker",
                    "owner adjudication is pending",
                    blocks_ratification=True, owner_decision_blocker=True,
                ))
            continue

        required = {
            "selected_target_authority": authority.get("selected_target_authority"),
            "transition_owner": authority.get("transition_owner"),
            "decision_provenance": authority.get("decision_provenance"),
            "rollback_boundary": authority.get("rollback_boundary"),
            "resolution_deadline": authority.get("resolution_deadline"),
        }
        missing = [key for key, value in required.items()
                   if value is None or (isinstance(value, str) and not value.strip())]
        if missing:
            owner_blocked.add(aid)
            findings.append(_f(
                "adjudication_incomplete", aid, "ratification-blocker",
                "adjudicated row is incomplete: " + ", ".join(sorted(missing)),
                blocks_ratification=True, owner_decision_blocker=True,
            ))
            continue

        provenance = required["decision_provenance"]
        rollback = required["rollback_boundary"]
        if not isinstance(provenance, dict) or not isinstance(rollback, dict):
            owner_blocked.add(aid)
            findings.append(_f(
                "adjudication_incomplete", aid, "ratification-blocker",
                "decision_provenance and rollback_boundary must be closed objects",
                blocks_ratification=True, owner_decision_blocker=True,
            ))
            continue

        if _is_placeholder_identity(provenance.get("decided_by")):
            owner_blocked.add(aid)
            findings.append(_f(
                "adjudication_placeholder_decided_by", aid, "ratification-blocker",
                "decided_by is a forbidden placeholder identity",
                blocks_ratification=True, owner_decision_blocker=True,
            ))

        placeholder_owners = [
            name for name, value in (
                ("transition_owner", required["transition_owner"]),
                ("rollback_boundary.owner", rollback.get("owner")),
            ) if _is_placeholder_owner(value)
        ]
        if placeholder_owners:
            owner_blocked.add(aid)
            findings.append(_f(
                "adjudication_incomplete", aid, "ratification-blocker",
                "placeholder owner fields: " + ", ".join(placeholder_owners),
                blocks_ratification=True, owner_decision_blocker=True,
            ))

        blank_rollback_fields = [
            key for key in ("trigger", "action", "authority_during_rollback")
            if not isinstance(rollback.get(key), str) or not rollback[key].strip()
        ]
        if blank_rollback_fields:
            owner_blocked.add(aid)
            findings.append(_f(
                "adjudication_incomplete", aid, "ratification-blocker",
                "blank rollback fields: " + ", ".join(blank_rollback_fields),
                blocks_ratification=True, owner_decision_blocker=True,
            ))

        decision_date, provenance_valid = _validate_provenance(aid, provenance, findings)
        if not provenance_valid:
            owner_blocked.add(aid)

        deadline = _parse_calendar_date(required["resolution_deadline"])
        if deadline is None:
            owner_blocked.add(aid)
            findings.append(_f(
                "adjudication_incomplete", aid, "ratification-blocker",
                "resolution_deadline is not a real YYYY-MM-DD calendar date",
                blocks_ratification=True, owner_decision_blocker=True,
            ))
        if decision_date is not None and decision_date > check_date:
            owner_blocked.add(aid)
            findings.append(_f(
                "adjudication_decision_date_future", aid, "ratification-blocker",
                f"decision_date {decision_date.isoformat()} is later than checker UTC date "
                f"{check_date.isoformat()}",
                blocks_ratification=True, owner_decision_blocker=True,
            ))
        if decision_date is not None and deadline is not None and decision_date > deadline:
            owner_blocked.add(aid)
            findings.append(_f(
                "adjudication_chronology_invalid", aid, "ratification-blocker",
                "decision_date is later than resolution_deadline",
                blocks_ratification=True, owner_decision_blocker=True,
            ))
        if deadline is not None and deadline < check_date:
            findings.append(_f(
                "adjudication_deadline_expired", aid, "ratification-blocker",
                f"resolution_deadline {deadline.isoformat()} has expired and requires amendment",
                blocks_ratification=True,
            ))
    return owner_blocked


def _check_contract(authorities: list[dict], findings: list[dict]) -> bool:
    """Structural contract: rebuild sources and fully owned compatibility shims."""
    ok = True
    for a in authorities:
        aid = a.get("id", "<unnamed>")
        cond = a.get("current_condition")
        if cond not in CONDITIONS:
            ok = False
            findings.append(_f("invalid_condition", aid, "error",
                              f"current_condition={cond!r} not in {CONDITIONS}", blocks_ratification=False))
        # Every projection needs a rebuild source.
        for proj in a.get("projections", []):
            if not str(proj.get("rebuild_source", "")).strip():
                ok = False
                findings.append(_f("missing_rebuild_source", aid, "error",
                                  f"projection {proj.get('name')!r} lacks rebuild_source",
                                  blocks_ratification=False))
        # Every shim needs owner + telemetry + deadline.
        for shim in a.get("shims", []):
            for key in ("owner", "telemetry", "deadline"):
                if not str(shim.get(key, "")).strip():
                    ok = False
                    findings.append(_f("shim_contract", aid, "error",
                                      f"shim {shim.get('name')!r} missing {key}",
                                      blocks_ratification=False))
    return ok


def _condition_findings(authorities: list[dict], findings: list[dict],
                        owner_blocked: set[str]) -> None:
    for a in authorities:
        cond = a.get("current_condition")
        if cond in BLOCKING_CONDITIONS:
            aid = str(a.get("id", "<unnamed>"))
            decision_pending = aid in owner_blocked
            if decision_pending:
                detail = (
                    f"{a.get('domain','')}: {cond} — blocks C0.3 ratification until adjudicated "
                    f"(target hypothesis: {a.get('target_hypothesis','')[:160]})"
                )
            else:
                detail = (
                    f"{a.get('domain','')}: {cond} — target is adjudicated; physical convergence "
                    "is pending"
                )
            findings.append(_f(
                f"condition_{cond.lower()}", aid, "ratification-blocker", detail,
                blocks_ratification=True,
                owner_decision_blocker=decision_pending,
                observed_convergence_blocker=True,
            ))


def _scan_undeclared_writers(
    authorities: list[dict], candidate_files: list[str], findings: list[dict]
) -> None:
    """Surface tracked production files that write a declared store but are not declared writers."""
    sigs: list[tuple[str, str, re.Pattern, list[str], set[str]]] = []
    for a in authorities:
        declared = {w.get("path") for w in a.get("observed_writers", [])}
        for sig in a.get("writer_signatures", []) or []:
            store = sig.get("store_token", "")
            writes = sig.get("write_tokens", []) or []
            if not store or not writes:
                continue
            sigs.append((a.get("id", "<unnamed>"), store, re.compile(re.escape(store)), writes, declared))
    if not sigs:
        return
    for rel in candidate_files:
        fpath = REPO_ROOT / rel
        try:
            if fpath.stat().st_size > MAX_FILE_BYTES:
                continue
            text = fpath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, ValueError):
            continue
        for aid, store, store_re, writes, declared in sigs:
            if store not in text:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _store_in_code(line, store) and any(w in line for w in writes):
                    if rel not in declared:
                        findings.append(_f(
                            "undeclared_writer", aid, "ratification-blocker",
                            f"writes declared store '{store}' but is not a declared observed_writer",
                            blocks_ratification=True, path=rel, line=lineno))
                    break  # one hit per (file, authority) is enough evidence


def run(mode: str, strict: bool, *, check_date: date | None = None) -> tuple[dict, list[dict], int]:
    started = time.monotonic()
    findings: list[dict] = []
    effective_date = check_date or datetime.now(timezone.utc).date()

    if not REGISTRY_PATH.exists():
        meta = _base_meta(mode, registry_valid=False, files_scanned=0, truncated=False,
                          authorities_total=0, duration=time.monotonic() - started)
        findings.append(_f("invalid_registry", "registry", "error",
                          f"registry not found at {REGISTRY_PATH}", blocks_ratification=False))
        return meta, findings, 2

    try:
        registry = _load_yaml(REGISTRY_PATH)
    except Exception as exc:  # noqa: BLE001 - report any parse failure as structural error
        meta = _base_meta(mode, registry_valid=False, files_scanned=0, truncated=False,
                          authorities_total=0, duration=time.monotonic() - started)
        findings.append(_f("invalid_registry", "registry", "error",
                          f"YAML parse error: {str(exc)[:300]}", blocks_ratification=False))
        return meta, findings, 2

    registry_valid = isinstance(registry, dict)
    authorities = registry.get("authorities", []) if registry_valid else []
    meta_block = registry.get("meta", {}) if registry_valid else {}
    scan_cfg = meta_block.get("scan", {}) if isinstance(meta_block, dict) else {}
    exclusions = list(scan_cfg.get("exclusions", []) or [])
    file_cap = int(scan_cfg.get("file_cap", FILE_CAP_CEILING) or FILE_CAP_CEILING)
    baseline = int(scan_cfg.get("measured_baseline", 0) or 0)

    structural_ok = _validate_schema(registry, findings)
    if len(authorities) > OBJECT_CEILING:
        structural_ok = False
        findings.append(_f("object_cap", "registry", "error",
                          f"{len(authorities)} authorities > {OBJECT_CEILING} object ceiling",
                          blocks_ratification=False))
    structural_ok = _check_contract(authorities, findings) and structural_ok
    owner_blocked = _validate_adjudications(authorities, findings, effective_date)
    _condition_findings(authorities, findings, owner_blocked)

    # Bounded scan.
    if mode == "incremental":
        changed = _git_changed()
        pool = [p for p in changed if (REPO_ROOT / p).exists() and not _excluded(p, exclusions)]
    else:
        pool = [p for p in _git_tracked() if not _excluded(p, exclusions)]

    truncated = False
    if len(pool) > min(file_cap, FILE_CAP_CEILING):
        truncated = True
        pool = pool[: min(file_cap, FILE_CAP_CEILING)]

    _scan_undeclared_writers(authorities, pool, findings)

    if truncated:
        findings.append(_f("scan_truncated", "registry", "degraded",
                          f"scan pool exceeded cap {min(file_cap, FILE_CAP_CEILING)}; DEGRADED discovery",
                          blocks_ratification=True))

    duration = time.monotonic() - started
    cond_counts = {c: 0 for c in CONDITIONS}
    adjudication_counts = {status: 0 for status in ADJUDICATION_STATUSES}
    for a in authorities:
        c = a.get("current_condition")
        if c in cond_counts:
            cond_counts[c] += 1
        status = a.get("adjudication_status", "PENDING")
        adjudication_counts[status if status in adjudication_counts else "PENDING"] += 1

    budget_s = INCREMENTAL_BUDGET_S if mode == "incremental" else FULL_BUDGET_S
    rss = _peak_rss_mib()
    budget_ok = duration <= budget_s and (rss is None or rss <= RSS_CEILING_MIB) and not (
        len(pool) > FILE_CAP_CEILING)

    meta = _base_meta(mode, registry_valid=registry_valid, files_scanned=len(pool),
                      truncated=truncated, authorities_total=len(authorities), duration=duration)
    meta.update({
        "registry_path": str(REGISTRY_PATH.relative_to(REPO_ROOT)),
        "file_cap": min(file_cap, FILE_CAP_CEILING),
        "measured_baseline": baseline,
        "exclusions_count": len(exclusions),
        "condition_counts": cond_counts,
        "adjudication_counts": adjudication_counts,
        "owner_decision_blocker_count": len(owner_blocked),
        "observed_convergence_blocker_count": sum(
            1 for authority in authorities
            if authority.get("current_condition") in BLOCKING_CONDITIONS
        ),
        "blocker_count": sum(1 for f in findings if f["blocks_ratification"]),
        "error_count": sum(1 for f in findings if f["severity"] == "error"),
        "peak_rss_mib": rss,
        "budget": {
            "limit_seconds": budget_s,
            "duration_seconds": round(duration, 3),
            "rss_ceiling_mib": RSS_CEILING_MIB,
            "ok": bool(budget_ok),
        },
    })

    # Exit code policy.
    exit_code = 0
    if not structural_ok or not registry_valid or meta["error_count"] > 0:
        exit_code = 2
    if not budget_ok:
        exit_code = 3
    if strict and exit_code == 0 and meta["blocker_count"] > 0:
        exit_code = 1
    return meta, findings, exit_code


def _base_meta(mode: str, *, registry_valid: bool, files_scanned: int,
               truncated: bool, authorities_total: int, duration: float) -> dict:
    return {
        "slice": "C0.3",
        "artifact": "system-state-authorities",
        "generated_by": "scripts/governance/check-state-authorities.py",
        "mode": mode,
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "registry_valid": registry_valid,
        "files_scanned": files_scanned,
        "truncated": truncated,
        "authorities_total": authorities_total,
        "cycle1_authority": "NOT_AUTHORIZED",
        "adjudication_counts": {"PENDING": 0, "ADJUDICATED": 0},
        "owner_decision_blocker_count": 0,
        "observed_convergence_blocker_count": 0,
    }


def _explain(obj: str) -> int:
    registry = _load_yaml(REGISTRY_PATH)
    for a in registry.get("authorities", []):
        if a.get("id") == obj:
            print(json.dumps(a, indent=2, sort_keys=False))
            return 0
    print(f"no authority object with id={obj!r}", file=sys.stderr)
    print("known objects: " + ", ".join(a.get("id", "?") for a in registry.get("authorities", [])),
          file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--machine", action="store_true", help="emit machine JSON {meta, findings}")
    ap.add_argument("--changed", action="store_true", help="incremental: scan only changed tracked files")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any ratification-blocker finding present")
    ap.add_argument("--explain", metavar="OBJECT", help="print the full registry row for one authority id")
    args = ap.parse_args(argv)

    if args.explain:
        return _explain(args.explain)

    mode = "incremental" if args.changed else "full"
    checker_utc_date = datetime.now(timezone.utc).date()
    meta, findings, exit_code = run(mode, args.strict, check_date=checker_utc_date)
    payload = {"meta": meta, "findings": findings}
    encoded = json.dumps(payload, indent=2, sort_keys=False)
    meta["output_bytes"] = len(encoded.encode("utf-8"))

    if meta["output_bytes"] > OUTPUT_BYTE_CEILING:
        # Enforce the output budget without printing an oversized blob.
        trimmed = {"meta": meta, "findings": findings[:64]}
        print(json.dumps(trimmed, indent=2))
        return 3

    encoded = json.dumps(payload, indent=2, sort_keys=False)

    if args.machine or not sys.stdout.isatty():
        print(encoded)
    else:
        # Human summary.
        cc = meta["condition_counts"]
        print(f"C0.3 state-authority checker — mode={meta['mode']} "
              f"files={meta['files_scanned']}/{meta['file_cap']} "
              f"duration={meta['budget']['duration_seconds']}s rss={meta['peak_rss_mib']}MiB")
        print(f"  authorities={meta['authorities_total']}  conditions={cc}")
        print(f"  ratification-blockers={meta['blocker_count']}  errors={meta['error_count']}  "
              f"budget_ok={meta['budget']['ok']}  registry_valid={meta['registry_valid']}")
        for f in findings:
            loc = f" @ {f['path']}:{f['line']}" if f.get("path") else ""
            print(f"  [{f['severity']}] {f['object']}/{f['kind']}: {f['detail']}{loc}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
