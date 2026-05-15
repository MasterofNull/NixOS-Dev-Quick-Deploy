#!/usr/bin/env python3
"""Compare the active local llama.cpp baseline against the current BitNet artifact."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BITNET_WORKDIR = Path.home() / ".local" / "share" / "nixos-ai-stack" / "bitnet-benchmark"
DEFAULT_BASELINE_URL = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_BASELINE_MODEL = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"


def local_baseline(url: str, model: str, prompt: str, max_tokens: int, timeout_seconds: int) -> Dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    started = time.time()
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = json.load(response)
    return {
        "status": "ok",
        "latency_s": round(time.time() - started, 3),
        "content": body["choices"][0]["message"]["content"],
        "model": model,
        "url": url,
    }


def bitnet_benchmark(workdir: Path, prompt_tokens: int, gen_tokens: int, threads: int, timeout_seconds: int) -> Dict[str, Any]:
    repo_dir = workdir / "BitNet"
    python_bin = workdir / ".venv" / "bin" / "python"
    model_path = repo_dir / "models" / "dummy-bitnet-125m.tl2.gguf"
    bench_script = repo_dir / "utils" / "e2e_benchmark.py"
    bench_bin = repo_dir / "build" / "bin" / "llama-bench"

    for path in (python_bin, model_path, bench_script, bench_bin):
        if not path.exists():
            return {
                "status": "missing_artifact",
                "missing": str(path),
                "repo_dir": str(repo_dir),
            }

    command = [
        str(python_bin),
        str(bench_script),
        "-m",
        str(model_path),
        "-p",
        str(prompt_tokens),
        "-n",
        str(gen_tokens),
        "-t",
        str(threads),
    ]
    started = time.time()
    try:
        result = subprocess.run(
            command,
            cwd=str(repo_dir),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=True,
        )
        return {
            "status": "ok",
            "latency_s": round(time.time() - started, 3),
            "stdout": (result.stdout or "").strip()[:4000],
            "stderr": (result.stderr or "").strip()[:2000],
            "model_path": str(model_path),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "latency_s": round(time.time() - started, 3),
            "stdout": ((exc.stdout or "") if isinstance(exc.stdout, str) else "").strip()[:4000],
            "stderr": ((exc.stderr or "") if isinstance(exc.stderr, str) else "").strip()[:2000],
            "model_path": str(model_path),
        }
    except subprocess.CalledProcessError as exc:
        return {
            "status": "failed",
            "latency_s": round(time.time() - started, 3),
            "returncode": exc.returncode,
            "stdout": (exc.stdout or "").strip()[:4000],
            "stderr": (exc.stderr or "").strip()[:2000],
            "model_path": str(model_path),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare local llama.cpp baseline and current BitNet benchmark artifact.")
    parser.add_argument("--baseline-url", default=DEFAULT_BASELINE_URL)
    parser.add_argument("--baseline-model", default=DEFAULT_BASELINE_MODEL)
    parser.add_argument("--baseline-prompt", default="Reply with exactly BASELINE_OK")
    parser.add_argument("--baseline-max-tokens", type=int, default=8)
    parser.add_argument("--bitnet-workdir", default=str(DEFAULT_BITNET_WORKDIR))
    parser.add_argument("--bitnet-prompt-tokens", type=int, default=64)
    parser.add_argument("--bitnet-gen-tokens", type=int, default=16)
    parser.add_argument("--bitnet-threads", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    report: Dict[str, Any] = {"status": "ok"}
    try:
        report["baseline"] = local_baseline(
            args.baseline_url,
            args.baseline_model,
            args.baseline_prompt,
            args.baseline_max_tokens,
            args.timeout_seconds,
        )
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        report["baseline"] = {"status": "failed", "error": str(exc)}
        report["status"] = "degraded"

    report["bitnet"] = bitnet_benchmark(
        Path(args.bitnet_workdir),
        args.bitnet_prompt_tokens,
        args.bitnet_gen_tokens,
        args.bitnet_threads,
        args.timeout_seconds,
    )
    if report["bitnet"].get("status") != "ok":
        report["status"] = "degraded"

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
