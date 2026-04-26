#!/usr/bin/env python3
# Validate the AI harness slice registry and emit a maturity scorecard.
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / "config" / "ai-harness-slice-registry.json"
VALID_MATURITY = ("defined", "validated", "observable", "governed")
VALID_RISK = ("low", "medium", "high")
DIMENSIONS = (
    "contract",
    "owner_surface",
    "control_plane",
    "data_plane",
    "observability",
    "quality_gate",
    "discoverability",
    "governance",
)
PATH_KEYS = (
    "primary_paths",
    "config_paths",
    "policy_paths",
    "runtime_paths",
    "storage_paths",
    "test_paths",
    "docs",
)
PROBE_KINDS = ("http", "command")
RUNTIME_AUTH_PROFILES = {
    "hybrid_api_key": {
        "header": "X-API-Key",
        "env_var": "HYBRID_API_KEY",
        "file_env_var": "HYBRID_API_KEY_FILE",
    },
}
SERVICE_URL_ENV_MAP = {
    "hybrid": ("HYBRID_URL",),
    "dashboard_api": ("DASHBOARD_API_URL", "DASHBOARD_URL"),
    "aidb": ("AIDB_URL",),
    "switchboard": ("SWITCHBOARD_URL",),
}
SERVICE_URL_ATTR_MAP = {
    "hybrid": "HYBRID_URL",
    "dashboard_api": "DASHBOARD_API_URL",
    "aidb": "AIDB_URL",
    "switchboard": "SWITCHBOARD_URL",
}
SERVICE_PORT_ATTR_MAP = {
    "dashboard_api": "DASHBOARD_API_PORT",
}


def _load_service_endpoints_module() -> Optional[object]:
    module_path = REPO_ROOT / "dashboard" / "backend" / "api" / "config" / "service_endpoints.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("slice_scorecard_service_endpoints", module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SERVICE_ENDPOINTS = _load_service_endpoints_module()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def path_exists(rel_path: str) -> bool:
    text = str(rel_path or "").strip()
    if not text:
        return False
    if text.startswith("runtime:"):
        return True
    if text.startswith("/") or text.startswith("journalctl ") or text.startswith("git revert "):
        return True
    if text.startswith("http://") or text.startswith("https://"):
        return True
    return (REPO_ROOT / text).exists()


def _read_secret(env_var: str, file_env_var: str) -> str:
    direct = os.getenv(env_var, "").strip()
    if direct:
        return direct
    file_path = os.getenv(file_env_var, "").strip()
    if not file_path:
        return ""
    try:
        return Path(file_path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _resolve_service_base_url(service: str) -> str:
    key = str(service or "").strip()
    if not key:
        return ""
    for env_name in SERVICE_URL_ENV_MAP.get(key, ()):
        value = os.getenv(env_name, "").strip()
        if value:
            return value.rstrip("/")
    attr_name = SERVICE_URL_ATTR_MAP.get(key, "")
    if SERVICE_ENDPOINTS is not None and attr_name and hasattr(SERVICE_ENDPOINTS, attr_name):
        value = str(getattr(SERVICE_ENDPOINTS, attr_name) or "").strip()
        if value:
            return value.rstrip("/")
    port_attr = SERVICE_PORT_ATTR_MAP.get(key, "")
    if SERVICE_ENDPOINTS is not None and port_attr and hasattr(SERVICE_ENDPOINTS, port_attr):
        port_value = getattr(SERVICE_ENDPOINTS, port_attr)
        host_value = str(getattr(SERVICE_ENDPOINTS, "SERVICE_HOST", "localhost") or "localhost").strip()
        if port_value:
            return f"http://{host_value}:{int(port_value)}"
    return ""


def _resolve_json_path(payload: Any, dotted_path: str) -> Tuple[bool, Any]:
    current = payload
    for part in str(dotted_path or "").split("."):
        if not part:
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return False, None
    return True, current


def _runtime_probe_errors(slice_id: str, probe: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    probe_id = str(probe.get("id", "")).strip()
    kind = str(probe.get("kind", "")).strip()
    dimension = str(probe.get("dimension", "")).strip()
    if not probe_id:
        errors.append(f"{slice_id}: runtime probe missing id")
    if kind not in PROBE_KINDS:
        errors.append(f"{slice_id}: runtime probe {probe_id or '<unknown>'} has invalid kind {kind!r}")
    if dimension not in DIMENSIONS:
        errors.append(f"{slice_id}: runtime probe {probe_id or '<unknown>'} has invalid dimension {dimension!r}")

    if kind == "http":
        service = str(probe.get("service", "")).strip()
        url = str(probe.get("url", "")).strip()
        path = str(probe.get("path", "")).strip()
        if not service and not url:
            errors.append(f"{slice_id}: runtime probe {probe_id} must declare service or url")
        if service and not _resolve_service_base_url(service):
            errors.append(f"{slice_id}: runtime probe {probe_id} references unknown service {service!r}")
        if service and not path:
            errors.append(f"{slice_id}: runtime probe {probe_id} must declare path when service is used")
    elif kind == "command":
        command = probe.get("command")
        if not isinstance(command, list) or not all(str(item).strip() for item in command):
            errors.append(f"{slice_id}: runtime probe {probe_id} command must be a non-empty list")
    return errors


def _build_runtime_probe_url(probe: Dict[str, Any]) -> str:
    direct_url = str(probe.get("url", "")).strip()
    if direct_url:
        return direct_url
    base_url = _resolve_service_base_url(str(probe.get("service", "")).strip())
    path = str(probe.get("path", "")).strip()
    if not base_url or not path:
        return ""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _run_http_probe(probe: Dict[str, Any], timeout_seconds: float) -> Dict[str, Any]:
    url = _build_runtime_probe_url(probe)
    method = str(probe.get("method", "GET") or "GET").upper()
    expect_status = int(probe.get("expect_status", 200))
    expect_json = bool(probe.get("expect_json", True))
    expect_nonempty = bool(probe.get("expect_nonempty", False))
    timeout = float(probe.get("timeout_seconds", timeout_seconds))
    payload = probe.get("payload")
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")

    auth_profile = str(probe.get("auth_profile", "")).strip()
    if auth_profile:
        auth_config = RUNTIME_AUTH_PROFILES.get(auth_profile)
        if auth_config:
            secret = _read_secret(auth_config["env_var"], auth_config["file_env_var"])
            if secret:
                headers[auth_config["header"]] = secret

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8", errors="replace")
            parsed: Any = raw_body
            if expect_json or probe.get("expect_keys"):
                parsed = json.loads(raw_body)
            if response.status != expect_status:
                return {
                    "passed": False,
                    "detail": f"expected status {expect_status}, got {response.status}",
                    "url": url,
                }
            for dotted_path in as_list(probe.get("expect_keys")):
                found, value = _resolve_json_path(parsed, str(dotted_path))
                if not found:
                    return {
                        "passed": False,
                        "detail": f"missing expected key {dotted_path}",
                        "url": url,
                    }
                if value in ("", None, [], {}):
                    return {
                        "passed": False,
                        "detail": f"empty value for expected key {dotted_path}",
                        "url": url,
                    }
            if expect_nonempty and parsed in ("", None, [], {}):
                return {
                    "passed": False,
                    "detail": "response payload was empty",
                    "url": url,
                }
            return {
                "passed": True,
                "detail": f"{method} {url} -> {response.status}",
                "url": url,
            }
    except HTTPError as exc:
        return {"passed": False, "detail": f"http error {exc.code}", "url": url}
    except URLError as exc:
        return {"passed": False, "detail": f"url error {exc.reason}", "url": url}
    except TimeoutError:
        return {"passed": False, "detail": f"timed out after {timeout:.1f}s", "url": url}
    except json.JSONDecodeError:
        return {"passed": False, "detail": "response was not valid json", "url": url}
    except Exception as exc:
        return {"passed": False, "detail": str(exc), "url": url}


def _run_command_probe(probe: Dict[str, Any], timeout_seconds: float) -> Dict[str, Any]:
    command = [str(item) for item in as_list(probe.get("command"))]
    timeout = float(probe.get("timeout_seconds", timeout_seconds))
    expected_exit = int(probe.get("expect_exit_code", 0))
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"passed": False, "detail": f"timed out after {timeout:.1f}s", "command": command}
    except Exception as exc:
        return {"passed": False, "detail": str(exc), "command": command}

    output = f"{result.stdout}\n{result.stderr}".strip()
    if result.returncode != expected_exit:
        return {
            "passed": False,
            "detail": f"expected exit {expected_exit}, got {result.returncode}",
            "command": command,
            "output_excerpt": output[-200:],
        }
    stdout_contains = str(probe.get("stdout_contains", "")).strip()
    if stdout_contains and stdout_contains not in output:
        return {
            "passed": False,
            "detail": f"missing output fragment {stdout_contains!r}",
            "command": command,
            "output_excerpt": output[-200:],
        }
    return {
        "passed": True,
        "detail": f"{' '.join(command)} -> {result.returncode}",
        "command": command,
    }


def run_runtime_probes(data: Dict[str, Any], timeout_seconds: float) -> Tuple[Dict[str, Any], List[str]]:
    results: Dict[str, Any] = {}
    errors: List[str] = []
    for slice_data in as_list(data.get("slices")):
        slice_id = str(slice_data.get("id", "")).strip()
        runtime_verification = slice_data.get("runtime_verification") or {}
        probes = as_list(runtime_verification.get("probes"))
        if not probes:
            continue

        slice_results: List[Dict[str, Any]] = []
        required_failures = 0
        for probe in probes:
            probe_errors = _runtime_probe_errors(slice_id, probe)
            if probe_errors:
                errors.extend(probe_errors)
                continue

            if str(probe.get("kind")) == "http":
                probe_result = _run_http_probe(probe, timeout_seconds)
            else:
                probe_result = _run_command_probe(probe, timeout_seconds)

            required = bool(probe.get("required", True))
            probe_summary = {
                "id": str(probe.get("id")),
                "kind": str(probe.get("kind")),
                "dimension": str(probe.get("dimension")),
                "required": required,
                **probe_result,
            }
            if required and not probe_result["passed"]:
                required_failures += 1
                errors.append(f"{slice_id}: runtime probe {probe_summary['id']} failed: {probe_result['detail']}")
            slice_results.append(probe_summary)

        results[slice_id] = {
            "enabled": True,
            "probes": slice_results,
            "total": len(slice_results),
            "passed": sum(1 for item in slice_results if item["passed"]),
            "required_failures": required_failures,
        }
    return results, errors


def collect_declared_paths(section: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    for key in PATH_KEYS:
        for item in as_list(section.get(key)):
            yield key, str(item)


def validate_registry(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in ("version", "description", "score_dimensions", "maturity_levels", "slices"):
        if key not in data:
            errors.append(f"missing top-level key: {key}")

    slices = as_list(data.get("slices"))
    if not slices:
        errors.append("registry must declare at least one slice")
        return errors

    seen_ids: set[str] = set()
    for slice_data in slices:
        slice_id = str(slice_data.get("id", "")).strip()
        if not slice_id:
            errors.append("slice is missing id")
            continue
        if slice_id in seen_ids:
            errors.append(f"duplicate slice id: {slice_id}")
        seen_ids.add(slice_id)

        for key in ("name", "domain", "summary", "maturity_target"):
            if not str(slice_data.get(key, "")).strip():
                errors.append(f"{slice_id}: missing {key}")

        maturity_target = str(slice_data.get("maturity_target", "")).strip()
        if maturity_target and maturity_target not in VALID_MATURITY:
            errors.append(f"{slice_id}: invalid maturity_target {maturity_target!r}")

        governance = slice_data.get("governance") or {}
        risk_level = str(governance.get("risk_level", "")).strip()
        if risk_level and risk_level not in VALID_RISK:
            errors.append(f"{slice_id}: invalid risk_level {risk_level!r}")

        for section_name in DIMENSIONS:
            if section_name not in slice_data:
                errors.append(f"{slice_id}: missing section {section_name}")

        owner = slice_data.get("owner_surface") or {}
        if not as_list(owner.get("primary_paths")):
            errors.append(f"{slice_id}: owner_surface.primary_paths must not be empty")
        if not as_list(owner.get("entrypoints")):
            errors.append(f"{slice_id}: owner_surface.entrypoints must not be empty")

        contract = slice_data.get("contract") or {}
        for key in ("inputs", "outputs", "invariants", "failure_modes", "rollback_commands"):
            if not as_list(contract.get(key)):
                errors.append(f"{slice_id}: contract.{key} must not be empty")

        quality = slice_data.get("quality_gate") or {}
        if not as_list(quality.get("validation_commands")):
            errors.append(f"{slice_id}: quality_gate.validation_commands must not be empty")
        if not as_list(quality.get("acceptance_signals")):
            errors.append(f"{slice_id}: quality_gate.acceptance_signals must not be empty")

        discoverability = slice_data.get("discoverability") or {}
        if not as_list(discoverability.get("docs")):
            errors.append(f"{slice_id}: discoverability.docs must not be empty")

        for section_name in DIMENSIONS:
            section = slice_data.get(section_name) or {}
            if not isinstance(section, dict):
                errors.append(f"{slice_id}: section {section_name} must be an object")
                continue
            for path_key, rel_path in collect_declared_paths(section):
                if not path_exists(rel_path):
                    errors.append(f"{slice_id}: missing path for {section_name}.{path_key}: {rel_path}")

        for rel_path in as_list(owner.get("entrypoints")):
            if not path_exists(str(rel_path)):
                errors.append(f"{slice_id}: missing owner entrypoint: {rel_path}")

        runtime_verification = slice_data.get("runtime_verification")
        if runtime_verification is not None and not isinstance(runtime_verification, dict):
            errors.append(f"{slice_id}: runtime_verification must be an object")
        elif isinstance(runtime_verification, dict):
            probes = as_list(runtime_verification.get("probes"))
            seen_probe_ids: set[str] = set()
            for probe in probes:
                probe_id = str((probe or {}).get("id", "")).strip()
                if probe_id:
                    if probe_id in seen_probe_ids:
                        errors.append(f"{slice_id}: duplicate runtime probe id {probe_id}")
                    seen_probe_ids.add(probe_id)
                errors.extend(_runtime_probe_errors(slice_id, probe or {}))

    return errors


def dimension_status(
    slice_data: Dict[str, Any],
    dimension: str,
    runtime_slice_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    section = slice_data.get(dimension) or {}
    blockers: List[str] = []

    if dimension == "contract":
        required = ("inputs", "outputs", "invariants", "failure_modes", "rollback_commands")
        for key in required:
            if not as_list(section.get(key)):
                blockers.append(f"missing {dimension}.{key}")
    elif dimension == "owner_surface":
        if not as_list(section.get("primary_paths")):
            blockers.append("missing owner_surface.primary_paths")
        if not as_list(section.get("entrypoints")):
            blockers.append("missing owner_surface.entrypoints")
    elif dimension == "control_plane":
        if not (as_list(section.get("config_paths")) or as_list(section.get("policy_paths"))):
            blockers.append("missing control-plane config or policy paths")
    elif dimension == "data_plane":
        if not as_list(section.get("runtime_paths")):
            blockers.append("missing data_plane.runtime_paths")
        if not (
            as_list(section.get("api_endpoints"))
            or as_list(section.get("mcp_tools"))
            or as_list(section.get("storage_paths"))
            or as_list((slice_data.get("owner_surface") or {}).get("entrypoints"))
        ):
            blockers.append("missing api_endpoints, mcp_tools, storage_paths, or owner entrypoints")
    elif dimension == "observability":
        if not (as_list(section.get("health_checks")) or as_list(section.get("metrics_signals"))):
            blockers.append("missing health_checks or metrics_signals")
        if not (as_list(section.get("dashboards")) or as_list(section.get("alerts"))):
            blockers.append("missing dashboards or alerts")
    elif dimension == "quality_gate":
        if not as_list(section.get("validation_commands")):
            blockers.append("missing validation_commands")
        if not as_list(section.get("test_paths")):
            blockers.append("missing test_paths")
        if not as_list(section.get("acceptance_signals")):
            blockers.append("missing acceptance_signals")
    elif dimension == "discoverability":
        if not as_list(section.get("docs")):
            blockers.append("missing docs")
        if not (
            as_list(section.get("cli_entrypoints"))
            or as_list(section.get("dashboard_routes"))
        ):
            blockers.append("missing cli_entrypoints or dashboard_routes")
    elif dimension == "governance":
        if str(section.get("risk_level", "")).strip() not in VALID_RISK:
            blockers.append("missing or invalid risk_level")
        if not as_list(section.get("review_commands")):
            blockers.append("missing review_commands")

    for path_key, rel_path in collect_declared_paths(section):
        if not path_exists(rel_path):
            blockers.append(f"missing path {path_key}:{rel_path}")

    if runtime_slice_result:
        for probe in as_list(runtime_slice_result.get("probes")):
            if str(probe.get("dimension", "")).strip() != dimension:
                continue
            if not bool(probe.get("required", True)):
                continue
            if not bool(probe.get("passed")):
                blockers.append(
                    f"runtime probe failed: {probe.get('id')} ({probe.get('detail', 'no detail')})"
                )

    status = "pass" if not blockers else "fail"
    return {"status": status, "blockers": blockers}


def achieved_maturity(dimensions: Dict[str, Dict[str, Any]], levels: Dict[str, Any]) -> str:
    achieved = "defined"
    for level in VALID_MATURITY:
        required = as_list((levels.get(level) or {}).get("required_dimensions"))
        if required and all(dimensions.get(name, {}).get("status") == "pass" for name in required):
            achieved = level
        else:
            break
    return achieved


def build_scorecard(data: Dict[str, Any], runtime_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    levels = data.get("maturity_levels") or {}
    scorecard: Dict[str, Any] = {
        "version": data.get("version"),
        "slice_count": len(as_list(data.get("slices"))),
        "slices": [],
        "summary": {},
    }

    achieved_counts = {level: 0 for level in VALID_MATURITY}
    target_counts = {level: 0 for level in VALID_MATURITY}

    for slice_data in as_list(data.get("slices")):
        runtime_slice_result = (runtime_results or {}).get(str(slice_data.get("id", "")).strip())
        statuses = {
            name: dimension_status(slice_data, name, runtime_slice_result=runtime_slice_result)
            for name in DIMENSIONS
        }
        passed = sum(1 for item in statuses.values() if item["status"] == "pass")
        total = len(DIMENSIONS)
        achieved = achieved_maturity(statuses, levels)
        target = str(slice_data.get("maturity_target", "defined")).strip()
        blockers = [
            f"{dimension}: {detail}"
            for dimension, info in statuses.items()
            for detail in info["blockers"]
        ]
        achieved_counts[achieved] += 1
        if target in target_counts:
            target_counts[target] += 1

        scorecard["slices"].append(
            {
                "id": slice_data["id"],
                "name": slice_data["name"],
                "domain": slice_data["domain"],
                "score": passed,
                "max_score": total,
                "percent": round((passed / total) * 100, 1),
                "target_maturity": target,
                "achieved_maturity": achieved,
                "dimensions": statuses,
                "blockers": blockers,
                "runtime_verification": runtime_slice_result or {
                    "enabled": False,
                    "probes": [],
                    "total": 0,
                    "passed": 0,
                    "required_failures": 0,
                },
            }
        )

    scorecard["summary"] = {
        "achieved_maturity_counts": achieved_counts,
        "target_maturity_counts": target_counts,
        "fully_passing_slices": sum(1 for item in scorecard["slices"] if item["score"] == item["max_score"]),
        "runtime_verification": {
            "enabled": bool(runtime_results),
            "slices_with_probes": sum(
                1 for item in scorecard["slices"]
                if (item.get("runtime_verification") or {}).get("enabled")
            ),
            "fully_passing_slices": sum(
                1 for item in scorecard["slices"]
                if not (item.get("runtime_verification") or {}).get("enabled")
                or (item.get("runtime_verification") or {}).get("required_failures", 0) == 0
            ),
            "required_probe_failures": sum(
                int((item.get("runtime_verification") or {}).get("required_failures", 0))
                for item in scorecard["slices"]
            ),
        },
    }
    return scorecard


def render_text(scorecard: Dict[str, Any], errors: List[str], runtime_errors: List[str]) -> str:
    lines: List[str] = []
    lines.append("AI Harness Slice Scorecard")
    lines.append(f"Version: {scorecard.get('version', 'unknown')}")
    lines.append(f"Slices: {scorecard.get('slice_count', 0)}")
    if errors:
        lines.append("")
        lines.append("Validation Errors:")
        for error in errors:
            lines.append(f"- {error}")
    if runtime_errors:
        lines.append("")
        lines.append("Runtime Verification Failures:")
        for error in runtime_errors:
            lines.append(f"- {error}")
    lines.append("")
    lines.append("Slice Summary:")
    for item in scorecard.get("slices", []):
        runtime = item.get("runtime_verification") or {}
        runtime_fragment = ""
        if runtime.get("enabled"):
            runtime_fragment = f" | runtime={runtime.get('passed', 0)}/{runtime.get('total', 0)}"
        lines.append(
            f"- {item['id']}: {item['score']}/{item['max_score']} "
            f"({item['percent']}%) | achieved={item['achieved_maturity']} "
            f"| target={item['target_maturity']}{runtime_fragment}"
        )
        if item["blockers"]:
            for blocker in item["blockers"][:4]:
                lines.append(f"  blocker: {blocker}")
    lines.append("")
    summary = scorecard.get("summary") or {}
    lines.append("Maturity Counts:")
    for level in VALID_MATURITY:
        lines.append(
            f"- {level}: achieved={summary.get('achieved_maturity_counts', {}).get(level, 0)} "
            f"| target={summary.get('target_maturity_counts', {}).get(level, 0)}"
        )
    runtime_summary = summary.get("runtime_verification") or {}
    if runtime_summary.get("enabled"):
        lines.append("")
        lines.append("Runtime Verification:")
        lines.append(
            f"- slices_with_probes: {runtime_summary.get('slices_with_probes', 0)} "
            f"| fully_passing_slices: {runtime_summary.get('fully_passing_slices', 0)} "
            f"| required_probe_failures: {runtime_summary.get('required_probe_failures', 0)}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the AI harness slice registry and emit a scorecard.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on registry validation errors.")
    parser.add_argument(
        "--runtime-verify",
        action="store_true",
        help="Execute declared runtime probes and fold their results into dimension scoring.",
    )
    parser.add_argument(
        "--runtime-timeout-seconds",
        type=float,
        default=10.0,
        help="Default timeout for runtime probes.",
    )
    args = parser.parse_args()

    registry = load_json(Path(args.registry))
    errors = validate_registry(registry)
    runtime_results: Dict[str, Any] = {}
    runtime_errors: List[str] = []
    if args.runtime_verify:
        runtime_results, runtime_errors = run_runtime_probes(registry, args.runtime_timeout_seconds)
    scorecard = build_scorecard(registry, runtime_results=runtime_results)

    if args.format == "json":
        print(
            json.dumps(
                {"errors": errors, "runtime_errors": runtime_errors, "scorecard": scorecard},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(render_text(scorecard, errors, runtime_errors))

    if (errors or runtime_errors) and args.strict:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
