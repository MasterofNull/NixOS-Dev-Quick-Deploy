#!/usr/bin/env python3
"""Watch staged llama.cpp model downloads and print ready-to-paste config values."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGING_DIR = Path(
    os.getenv("AQ_LLAMA_STAGING_DIR", "~/.local/share/nixos-ai-stack/llama-model-staging")
).expanduser()
DEFAULT_REGISTRY_PATH = ROOT / "config" / "llama-cpp-models.sha256"
DEFAULT_FACTS_PATH = ROOT / "nix" / "hosts" / "hyperd" / "facts.nix"

EXPECTED_CANDIDATES = [
    {
        "slug": "qwen3_4b_iq4_nl",
        "label": "Qwen3-4B-Instruct-2507-IQ4_NL.gguf",
        "repo": "unsloth/Qwen3-4B-Instruct-2507-GGUF",
        "filename": "Qwen3-4B-Instruct-2507-IQ4_NL.gguf",
        "model_path": "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-IQ4_NL.gguf",
    },
    {
        "slug": "qwen3_4b_q5_k_m",
        "label": "Qwen3-4B-Instruct-2507-Q5_K_M.gguf",
        "repo": "unsloth/Qwen3-4B-Instruct-2507-GGUF",
        "filename": "Qwen3-4B-Instruct-2507-Q5_K_M.gguf",
        "model_path": "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q5_K_M.gguf",
    },
    {
        "slug": "qwen3_8b_q4_k_m",
        "label": "Qwen3-8B-Q4_K_M.gguf",
        "repo": "lm-kit/qwen-3-8b-instruct-gguf",
        "filename": "Qwen3-8B-Q4_K_M.gguf",
        "model_path": "/var/lib/llama-cpp/models/Qwen3-8B-Q4_K_M.gguf",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_candidate(staging_dir: Path, candidate: Dict[str, str]) -> Dict[str, Any]:
    filename = candidate["filename"]
    path = staging_dir / filename
    part_path = staging_dir / f"{filename}.part"
    exists = path.exists()
    partial_exists = part_path.exists()
    complete = exists and not partial_exists
    size_bytes = path.stat().st_size if exists else 0
    partial_size_bytes = part_path.stat().st_size if partial_exists else 0
    sha256 = sha256_file(path) if complete else None
    sha256_nix = "null" if not sha256 else f'"{sha256}"'
    return {
        **candidate,
        "path": str(path),
        "partial_path": str(part_path),
        "exists": exists,
        "partial_exists": partial_exists,
        "complete": complete,
        "size_bytes": size_bytes,
        "partial_size_bytes": partial_size_bytes,
        "sha256": sha256,
        "registry_line": (
            f"{candidate['repo']}:{filename} {sha256}"
            if sha256
            else f"{candidate['repo']}:{filename} HASH_PENDING"
        ),
        "facts_lines": [
            f'llamaCpp.model           = "{candidate["model_path"]}";',
            f'llamaCpp.huggingFaceRepo = "{candidate["repo"]}";',
            f'llamaCpp.huggingFaceFile = "{filename}";',
            f"llamaCpp.sha256          = {sha256_nix};",
        ],
    }


def build_report(staging_dir: Path) -> Dict[str, Any]:
    candidates = [inspect_candidate(staging_dir, item) for item in EXPECTED_CANDIDATES]
    complete_n = sum(1 for item in candidates if item["complete"])
    return {
        "status": "ok",
        "staging_dir": str(staging_dir),
        "registry_path": str(DEFAULT_REGISTRY_PATH),
        "facts_path": str(DEFAULT_FACTS_PATH),
        "complete_n": complete_n,
        "total_n": len(candidates),
        "all_complete": complete_n == len(candidates),
        "candidates": candidates,
    }


def format_text(report: Dict[str, Any]) -> str:
    lines = [
        "Llama Staging Status",
        f"Staging dir: {report['staging_dir']}",
        f"Registry: {report['registry_path']}",
        f"Facts: {report['facts_path']}",
        f"Complete: {report['complete_n']}/{report['total_n']}",
        "",
    ]
    for item in report["candidates"]:
        if item["complete"]:
            state = f"complete ({item['size_bytes']} bytes)"
        elif item["partial_exists"]:
            state = f"downloading ({item['partial_size_bytes']} bytes in .part)"
        else:
            state = "missing"
        lines.append(f"- {item['label']}: {state}")
        lines.append(f"  Registry: {item['registry_line']}")
        lines.append("  Facts:")
        for line in item["facts_lines"]:
            lines.append(f"    {line}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch staged llama.cpp downloads and print patch values.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--watch", action="store_true", help="Poll until all expected candidates are complete.")
    parser.add_argument("--interval-seconds", type=float, default=5.0, help="Polling interval for --watch.")
    parser.add_argument("--staging-dir", default=str(DEFAULT_STAGING_DIR))
    return parser.parse_args()


def emit(report: Dict[str, Any], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report, indent=2))
    else:
        print(format_text(report), end="")


def main() -> int:
    args = parse_args()
    staging_dir = Path(args.staging_dir).expanduser()
    if not args.watch:
        emit(build_report(staging_dir), args.format)
        return 0

    last_snapshot = ""
    while True:
        report = build_report(staging_dir)
        rendered = json.dumps(report, sort_keys=True)
        if rendered != last_snapshot:
            emit(report, args.format)
            last_snapshot = rendered
        if report["all_complete"]:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
