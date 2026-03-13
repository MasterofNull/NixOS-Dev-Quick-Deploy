#!/usr/bin/env python3
"""Assess whether bitnet.cpp is a plausible sidecar candidate on this host.

This is a feasibility probe only. It does not build or deploy BitNet.
The checks are grounded in the public BitNet README requirements and supported
model matrix, then combined with local host facts to recommend a bounded next
step for this repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FACTS = ROOT / "nix" / "hosts" / "nixos" / "facts.nix"

BITNET_MODELS = [
    {
        "name": "BitNet-b1.58-2B-4T",
        "source": "official",
        "params_b": 2.4,
        "x86_kernels": ["i2_s", "tl2"],
        "arm_kernels": ["i2_s", "tl1"],
        "min_ram_gb_heuristic": 16,
    },
    {
        "name": "bitnet_b1_58-large",
        "source": "supported",
        "params_b": 0.7,
        "x86_kernels": ["i2_s", "tl2"],
        "arm_kernels": ["i2_s", "tl1"],
        "min_ram_gb_heuristic": 8,
    },
    {
        "name": "Llama3-8B-1.58-100B-tokens",
        "source": "supported",
        "params_b": 8.0,
        "x86_kernels": ["i2_s", "tl2"],
        "arm_kernels": ["i2_s", "tl1"],
        "min_ram_gb_heuristic": 32,
    },
]


def _run_command(argv: List[str]) -> Dict[str, Any]:
    try:
        result = subprocess.run(argv, check=False, capture_output=True, text=True)
    except OSError as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "returncode": 127}
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "returncode": result.returncode,
    }


def _parse_version(text: str) -> List[int]:
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", text or "")
    if not match:
        return []
    return [int(part) for part in match.groups(default="0")]


def _version_at_least(actual: List[int], minimum: List[int]) -> bool:
    if not actual:
        return False
    padded_actual = actual + [0] * (len(minimum) - len(actual))
    padded_min = minimum + [0] * (len(padded_actual) - len(minimum))
    return padded_actual >= padded_min


def _parse_facts(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")

    def grab(pattern: str, default: str = "") -> str:
        match = re.search(pattern, text)
        return match.group(1) if match else default

    ram_raw = grab(r"systemRamGb\s*=\s*(\d+)")
    return {
        "system": grab(r'system\s*=\s*"([^"]+)"'),
        "cpu_vendor": grab(r'cpuVendor\s*=\s*"([^"]+)"'),
        "gpu_vendor": grab(r'gpuVendor\s*=\s*"([^"]+)"'),
        "system_ram_gb": int(ram_raw) if ram_raw else 0,
    }


def _host_cpu_family(system_name: str) -> str:
    normalized = (system_name or "").strip().lower()
    if normalized.startswith("x86_64"):
        return "x86"
    if normalized.startswith("aarch64") or normalized.startswith("arm"):
        return "arm"
    return "unsupported"


def _tool_status(command: str, minimum: str) -> Dict[str, Any]:
    resolved = shutil.which(command)
    if not resolved:
        return {"available": False, "path": "", "minimum": minimum, "version": "", "meets_minimum": False}
    probe = _run_command([resolved, "--version"])
    version_text = probe["stdout"] or probe["stderr"]
    return {
        "available": True,
        "path": resolved,
        "minimum": minimum,
        "version": version_text.splitlines()[0] if version_text else "",
        "meets_minimum": _version_at_least(_parse_version(version_text), _parse_version(minimum)),
    }


def build_report(facts: Dict[str, Any], *, command_overrides: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    cpu_family = _host_cpu_family(str(facts.get("system") or ""))
    ram_gb = int(facts.get("system_ram_gb") or 0)
    overrides = command_overrides or {}

    tools = {
        "python3": overrides.get("python3") or _tool_status("python3", "3.9"),
        "cmake": overrides.get("cmake") or _tool_status("cmake", "3.22"),
        "clang": overrides.get("clang") or _tool_status("clang", "18"),
        "git": overrides.get("git") or {
            "available": bool(shutil.which("git")),
            "path": shutil.which("git") or "",
            "minimum": "required",
            "version": (_run_command(["git", "--version"]).get("stdout") if shutil.which("git") else ""),
            "meets_minimum": bool(shutil.which("git")),
        },
    }

    supported_models = []
    for model in BITNET_MODELS:
        kernels = model["x86_kernels"] if cpu_family == "x86" else model["arm_kernels"] if cpu_family == "arm" else []
        heuristic_ok = ram_gb >= int(model["min_ram_gb_heuristic"])
        supported_models.append(
            {
                "name": model["name"],
                "source": model["source"],
                "params_b": model["params_b"],
                "kernels": kernels,
                "ram_fit_heuristic": heuristic_ok,
                "min_ram_gb_heuristic": model["min_ram_gb_heuristic"],
            }
        )

    blockers = []
    if cpu_family == "unsupported":
        blockers.append("unsupported_host_architecture")
    for tool_name, payload in tools.items():
        if not payload.get("meets_minimum", False):
            blockers.append(f"missing_requirement:{tool_name}")

    sidecar_viable = cpu_family in {"x86", "arm"} and all(payload.get("meets_minimum", False) for payload in tools.values())
    preferred_models = [m for m in supported_models if m["kernels"] and m["ram_fit_heuristic"]]
    next_actions = []
    if not sidecar_viable:
        if "missing_requirement:clang" in blockers:
            next_actions.append(
                "Add a declarative clang>=18 toolchain path for isolated bitnet.cpp build experiments before any runtime integration."
            )
        if "missing_requirement:cmake" in blockers:
            next_actions.append("Provide cmake>=3.22 in the benchmark shell before attempting a bitnet.cpp source build.")
        if cpu_family == "unsupported":
            next_actions.append("Do not pursue bitnet.cpp on this host class until upstream architecture support changes.")
    else:
        next_actions.append(
            "Run a sidecar-only benchmark using BitNet's official dummy-model/e2e_benchmark flow before considering any NixOS service role."
        )
        if preferred_models:
            next_actions.append(
                f"Start with {preferred_models[0]['name']} or a dummy model matching that layout; keep llama.cpp as the baseline and compare latency/tokens/sec."
            )

    benchmark_plan = {
        "sidecar_only": True,
        "commands": [
            "git clone --recursive https://github.com/microsoft/BitNet.git",
            "python setup_env.py -md models/BitNet-b1.58-2B-4T -q i2_s",
            "python utils/e2e_benchmark.py -m /path/to/model -n 200 -p 256 -t 4",
            "python utils/generate-dummy-bitnet-model.py models/bitnet_b1_58-large --outfile models/dummy-bitnet-125m.tl1.gguf --outtype tl1 --model-size 125M",
        ],
    }
    declarative_sidecar_scaffold = {
        "option_path": "mySystem.aiStack.bitnet",
        "port_option": "mySystem.ports.bitnet",
        "endpoint_env": "BITNET_URL",
        "default_host": "127.0.0.1",
        "default_port": 8086,
        "enabled_by_default": False,
        "benchmark_only_default": True,
        "switchboard_integration": "disabled",
    }
    if sidecar_viable:
        next_actions.append(
            "Keep routing on llama.cpp, but use the declarative BitNet sidecar scaffold for host-local benchmark-only experiments."
        )

    return {
        "status": "ok",
        "source_basis": {
            "bitnet_requirements": {
                "python_min": "3.9",
                "cmake_min": "3.22",
                "clang_min": "18",
            },
            "note": "Model support and build requirements are derived from the public microsoft/BitNet README; RAM fit is a local heuristic, not an upstream guarantee.",
        },
        "host": {
            "system": facts.get("system"),
            "cpu_vendor": facts.get("cpu_vendor"),
            "gpu_vendor": facts.get("gpu_vendor"),
            "cpu_family": cpu_family,
            "system_ram_gb": ram_gb,
        },
        "requirements": tools,
        "supported_models": supported_models,
        "preferred_models": preferred_models[:3],
        "blockers": blockers,
        "sidecar_viable": sidecar_viable,
        "declarative_sidecar_scaffold": declarative_sidecar_scaffold,
        "benchmark_plan": benchmark_plan,
        "next_actions": next_actions,
    }


def _format_text(report: Dict[str, Any]) -> str:
    lines = [
        "BitNet Feasibility",
        f"Host: {report['host']['system']} ({report['host']['cpu_family']}, {report['host']['system_ram_gb']} GiB RAM)",
        f"Sidecar viable: {'yes' if report.get('sidecar_viable') else 'no'}",
        "",
        "Requirements:",
    ]
    for name, payload in report.get("requirements", {}).items():
        state = "ok" if payload.get("meets_minimum") else "missing"
        lines.append(f"- {name}: {state} ({payload.get('version') or 'not found'})")
    lines.append("")
    lines.append("Preferred models:")
    preferred = report.get("preferred_models") or []
    if not preferred:
        lines.append("- none")
    else:
        for model in preferred:
            lines.append(f"- {model['name']} [{', '.join(model['kernels'])}]")
    if report.get("blockers"):
        lines.append("")
        lines.append("Blockers:")
        for blocker in report["blockers"]:
            lines.append(f"- {blocker}")
    if report.get("next_actions"):
        lines.append("")
        lines.append("Next actions:")
        for action in report["next_actions"]:
            lines.append(f"- {action}")
    scaffold = report.get("declarative_sidecar_scaffold") or {}
    if scaffold:
        lines.append("")
        lines.append("Declarative scaffold:")
        lines.append(
            f"- {scaffold.get('option_path')} via {scaffold.get('endpoint_env')} "
            f"({scaffold.get('default_host')}:{scaffold.get('default_port')})"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess bitnet.cpp sidecar feasibility on the current host.")
    parser.add_argument("--facts", default=str(DEFAULT_FACTS), help="Path to facts.nix")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--command-json", default="", help="Optional JSON file overriding tool requirement probe results")
    args = parser.parse_args()

    facts_path = Path(args.facts)
    facts = _parse_facts(facts_path)
    overrides = None
    if args.command_json:
        overrides = json.loads(Path(args.command_json).read_text(encoding="utf-8"))
    report = build_report(facts, command_overrides=overrides)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(_format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
