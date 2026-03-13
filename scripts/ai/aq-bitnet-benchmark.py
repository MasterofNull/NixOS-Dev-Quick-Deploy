#!/usr/bin/env python3
"""Run a bounded local bitnet.cpp dummy-model benchmark on the current host."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKDIR = Path(os.path.expanduser("~/.local/share/nixos-ai-stack/bitnet-benchmark"))
BITNET_REPO_URL = "https://github.com/microsoft/BitNet"
DUMMY_MODEL_CONFIGS = {
    "125M": {
        "architectures": ["BitnetForCausalLM"],
        "model_type": "bitnet",
        "vocab_size": 32002,
        "hidden_size": 1536,
        "intermediate_size": 4096,
        "num_hidden_layers": 11,
        "num_attention_heads": 12,
        "num_key_value_heads": 12,
        "max_position_embeddings": 2048,
        "rope_theta": 10000.0,
        "rms_norm_eps": 1.0e-6,
    },
}


def ensure_tool(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"required tool missing from PATH: {name}")
    return resolved


def resolve_python(preferred: str | None = None) -> str:
    candidates = [preferred, os.environ.get("BITNET_PYTHON_BIN"), "python3.12", "python3"]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        if Path(candidate).exists():
            return candidate
    raise RuntimeError("unable to find a compatible Python interpreter for BitNet; tried BITNET_PYTHON_BIN, python3.12, and python3")


def run(argv: List[str], *, cwd: Path | None = None, env: Dict[str, str] | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        capture_output=capture,
        check=True,
    )


def require_path(path: Path, description: str) -> None:
    if not path.exists():
        raise RuntimeError(f"bitnet repository missing {description}: {path}")


def python_version(python_bin: str) -> str:
    result = run([python_bin, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], capture=True)
    return (result.stdout or "").strip()


def build_cmake_flags() -> Dict[str, str]:
    flags: Dict[str, str] = {}
    if platform.machine().lower() in {"x86_64", "amd64"}:
        # Nix strips -march=native, so request the x86 features BitNet expects explicitly.
        flags["CMAKE_C_FLAGS"] = "-mavx2 -mfma -mssse3"
        flags["CMAKE_CXX_FLAGS"] = "-mavx2 -mfma -mssse3"
    return flags


def apply_upstream_compat_shims(repo_dir: Path) -> List[str]:
    shims: List[str] = []
    ggml_mad = repo_dir / "src" / "ggml-bitnet-mad.cpp"
    source = ggml_mad.read_text(encoding="utf-8")
    original = "        int8_t * y_col = y + col * by;\n"
    replacement = "        const int8_t * y_col = y + col * by;\n"
    if original in source:
        ggml_mad.write_text(source.replace(original, replacement), encoding="utf-8")
        shims.append("ggml-bitnet-mad.cpp const y_col compatibility fix")

    dummy_model_script = repo_dir / "utils" / "generate-dummy-bitnet-model.py"
    script_source = dummy_model_script.read_text(encoding="utf-8")
    dummy_original = """    \"125M\": {\n        \"hidden_size\": 768,\n        \"intermediate_size\": 3072,\n        \"num_hidden_layers\": 11,\n        \"num_attention_heads\": 12\n    },\n"""
    dummy_replacement = """    \"125M\": {\n        \"hidden_size\": 1536,\n        \"intermediate_size\": 4096,\n        \"num_hidden_layers\": 11,\n        \"num_attention_heads\": 12\n    },\n"""
    if dummy_original in script_source:
        dummy_model_script.write_text(script_source.replace(dummy_original, dummy_replacement), encoding="utf-8")
        shims.append("generate-dummy-bitnet-model.py tl2-compatible 125M dimensions")
    return shims


def ensure_dummy_tokenizer(venv_python: Path, model_layout_dir: Path) -> List[str]:
    artifacts: List[str] = []
    tokenizer_path = model_layout_dir / "tokenizer.model"

    corpus_path = model_layout_dir / "tokenizer_corpus.txt"
    corpus_path.write_text(
        "\n".join(
            [
                "bitnet benchmark dummy tokenizer",
                "hello world from the local ai harness",
                "token generation prompt response reasoning coding review",
                "plants habitat native species garden ecology conservation",
            ]
            * 64
        )
        + "\n",
        encoding="utf-8",
    )
    run(
        [
            str(venv_python),
            "-c",
            (
                "from sentencepiece import SentencePieceTrainer; "
                f"SentencePieceTrainer.Train(input=r'{corpus_path}', "
                f"model_prefix=r'{model_layout_dir / 'tokenizer'}', "
                "vocab_size=59, model_type='unigram', "
                "bos_id=1, eos_id=2, unk_id=0, pad_id=3)"
            ),
        ],
    )
    artifacts.extend([str(corpus_path), str(tokenizer_path)])
    return artifacts


def ensure_dummy_model_seed(venv_python: Path, model_layout_dir: Path, *, model_size: str) -> List[str]:
    artifacts: List[str] = []
    model_layout_dir.mkdir(parents=True, exist_ok=True)
    config_path = model_layout_dir / "config.json"
    if model_size not in DUMMY_MODEL_CONFIGS:
        raise RuntimeError(f"unsupported BitNet dummy model size for local seed materialization: {model_size}")
    config_path.write_text(json.dumps(DUMMY_MODEL_CONFIGS[model_size], indent=2) + "\n", encoding="utf-8")
    artifacts.append(str(config_path))
    artifacts.extend(ensure_dummy_tokenizer(venv_python, model_layout_dir))
    return artifacts


def build_plan(workdir: Path, *, threads: int, prompt_tokens: int, gen_tokens: int) -> Dict[str, Any]:
    repo_dir = workdir / "BitNet"
    venv_dir = workdir / ".venv"
    model_layout_dir = repo_dir / "models" / "bitnet_b1_58-large"
    model_path = repo_dir / "models" / "dummy-bitnet-125m.tl2.gguf"
    log_dir = workdir / "logs"
    benchmark_log = log_dir / "benchmark.log"
    return {
        "repo_dir": repo_dir,
        "venv_dir": venv_dir,
        "model_layout_dir": model_layout_dir,
        "model_path": model_path,
        "dummy_model_size": "125M",
        "log_dir": log_dir,
        "benchmark_log": benchmark_log,
        "steps": [
            ["git", "clone", "--depth", "1", "--recurse-submodules", BITNET_REPO_URL, str(repo_dir)],
            [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "-r", "requirements.txt"],
            [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "3rdparty/llama.cpp/gguf-py"],
            [
                str(venv_dir / "bin" / "python"),
                "utils/codegen_tl2.py",
                "--model",
                "bitnet_b1_58-large",
                "--BM",
                "256,128,256",
                "--BK",
                "96,192,96",
                "--bm",
                "32,32,32",
            ],
            [
                "cmake",
                "-B",
                "build",
                "-DBITNET_X86_TL2=OFF",
                "-DCMAKE_C_COMPILER=clang",
                "-DCMAKE_CXX_COMPILER=clang++",
                "-DCMAKE_C_FLAGS=-mavx2 -mfma -mssse3",
                "-DCMAKE_CXX_FLAGS=-mavx2 -mfma -mssse3",
            ],
            ["cmake", "--build", "build", "--config", "Release"],
            [
                str(venv_dir / "bin" / "python"),
                "utils/generate-dummy-bitnet-model.py",
                str(model_layout_dir),
                "--outfile",
                str(model_path),
                "--outtype",
                "tl2",
                "--model-size",
                "125M",
            ],
            [
                str(venv_dir / "bin" / "python"),
                "utils/e2e_benchmark.py",
                "-m",
                str(model_path),
                "-p",
                str(prompt_tokens),
                "-n",
                str(gen_tokens),
                "-t",
                str(threads),
            ],
        ],
    }


def prepare_repo(repo_dir: Path) -> None:
    if repo_dir.exists():
        status = run(["git", "-C", str(repo_dir), "status", "--porcelain"], capture=True)
        if not (status.stdout or "").strip():
            run(["git", "-C", str(repo_dir), "pull", "--ff-only"])
        run(["git", "-C", str(repo_dir), "submodule", "update", "--init", "--recursive"])
    else:
        run(["git", "clone", "--depth", "1", "--recurse-submodules", BITNET_REPO_URL, str(repo_dir)])
    require_path(repo_dir / "3rdparty" / "llama.cpp" / "requirements", "llama.cpp submodule requirements")
    require_path(repo_dir / "utils" / "e2e_benchmark.py", "benchmark utility")


def prepare_venv(venv_dir: Path, repo_dir: Path, *, python_bin: str) -> Path:
    target_version = python_version(python_bin)
    venv_python = venv_dir / "bin" / "python"
    if venv_python.exists():
        current_version = python_version(str(venv_python))
        if current_version != target_version:
            shutil.rmtree(venv_dir)
    if not venv_python.exists():
        run([python_bin, "-m", "venv", str(venv_dir)])
    venv_python = venv_dir / "bin" / "python"
    run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=repo_dir)
    run([str(venv_python), "-m", "pip", "install", "3rdparty/llama.cpp/gguf-py"], cwd=repo_dir)
    return venv_python


def execute_benchmark(plan: Dict[str, Any], *, keep_repo: bool, python_bin: str | None) -> Dict[str, Any]:
    repo_dir = Path(plan["repo_dir"])
    venv_dir = Path(plan["venv_dir"])
    log_dir = Path(plan["log_dir"])
    benchmark_log = Path(plan["benchmark_log"])
    model_layout_dir = Path(plan["model_layout_dir"])
    model_path = Path(plan["model_path"])

    resolved_python = resolve_python(python_bin)
    ensure_tool("git")
    ensure_tool("clang")
    ensure_tool("clang++")
    ensure_tool("cmake")
    log_dir.mkdir(parents=True, exist_ok=True)
    prepare_repo(repo_dir)
    venv_python = prepare_venv(venv_dir, repo_dir, python_bin=resolved_python)
    model_seed_artifacts = ensure_dummy_model_seed(
        venv_python,
        model_layout_dir,
        model_size=str(plan["dummy_model_size"]),
    )
    applied_shims = apply_upstream_compat_shims(repo_dir)
    cmake_flags = build_cmake_flags()

    run(
        [
            str(venv_python),
            "utils/codegen_tl2.py",
            "--model",
            "bitnet_b1_58-large",
            "--BM",
            "256,128,256",
            "--BK",
            "96,192,96",
            "--bm",
            "32,32,32",
        ],
        cwd=repo_dir,
    )
    cmake_argv = [
        "cmake",
        "-B",
        "build",
        "-DBITNET_X86_TL2=OFF",
        "-DCMAKE_C_COMPILER=clang",
        "-DCMAKE_CXX_COMPILER=clang++",
    ]
    for key, value in cmake_flags.items():
        cmake_argv.append(f"-D{key}={value}")
    run(cmake_argv, cwd=repo_dir)
    run(["cmake", "--build", "build", "--config", "Release"], cwd=repo_dir)
    run(
        [
            str(venv_python),
            "utils/generate-dummy-bitnet-model.py",
            str(model_layout_dir),
            "--outfile",
            str(model_path),
            "--outtype",
            "tl2",
            "--model-size",
            "125M",
        ],
        cwd=repo_dir,
    )
    bench = run(
        [
            str(venv_python),
            "utils/e2e_benchmark.py",
            "-m",
            str(model_path),
            "-p",
            str(plan["steps"][-1][5]),
            "-n",
            str(plan["steps"][-1][7]),
            "-t",
            str(plan["steps"][-1][9]),
        ],
        cwd=repo_dir,
        capture=True,
    )
    benchmark_log.write_text((bench.stdout or "") + ("\n" + bench.stderr if bench.stderr else ""), encoding="utf-8")
    result = {
        "status": "ok",
        "repo_dir": str(repo_dir),
        "python_bin": resolved_python,
        "compat_shims": applied_shims,
        "model_seed_artifacts": model_seed_artifacts,
        "venv_python": str(venv_python),
        "model_path": str(model_path),
        "benchmark_log": str(benchmark_log),
        "stdout_excerpt": (bench.stdout or "").strip()[:2000],
    }
    if not keep_repo:
        result["keep_repo"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded local bitnet.cpp dummy-model benchmark.")
    parser.add_argument("--workdir", default=str(DEFAULT_WORKDIR), help="Persistent work directory for the benchmark checkout and venv.")
    parser.add_argument("--threads", type=int, default=4, help="Benchmark threads.")
    parser.add_argument("--prompt-tokens", type=int, default=256, help="Benchmark prompt tokens.")
    parser.add_argument("--gen-tokens", type=int, default=64, help="Benchmark generated tokens.")
    parser.add_argument("--python-bin", help="Preferred Python interpreter for the BitNet venv. Defaults to BITNET_PYTHON_BIN, then python3.12, then python3.")
    parser.add_argument("--print-plan", action="store_true", help="Print the benchmark plan JSON without executing.")
    parser.add_argument("--keep-repo", action="store_true", help="Keep the cloned BitNet checkout after the run.")
    args = parser.parse_args()

    plan = build_plan(Path(args.workdir), threads=args.threads, prompt_tokens=args.prompt_tokens, gen_tokens=args.gen_tokens)
    if args.print_plan:
        print(json.dumps(plan, indent=2, default=str))
        return 0

    result = execute_benchmark(plan, keep_repo=args.keep_repo, python_bin=args.python_bin)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
