#!/usr/bin/env python3
"""Generate and record a repo-native llama.cpp benchmark scorecard.

This tool is intentionally aligned to the current stack shape:
- it generates the requested benchmark batch and worksheet entries
- it records live scorecards from the active local llama.cpp service
- it does not attempt to hot-swap models or ctx-size on its own

Use this after manually switching the active llama.cpp service to the target
model/context under test.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_API_URL = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_METRICS_URL = "http://127.0.0.1:8080/metrics"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_CONTEXTS = [8192, 16384]
OBSERVE_MODULE_PATH = Path(__file__).with_name("aq-llama-benchmark-observe.py")
DEFAULT_RUNS_DIR = Path(
    os.getenv("AQ_LLAMA_BENCHMARK_RUNS_DIR", "~/.local/share/nixos-ai-stack/llama-benchmarks")
).expanduser()

DEFAULT_BATCH_MODELS = [
    {
        "slug": "qwen3_4b_q4_k_m",
        "label": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "family": "Qwen3 4B",
        "quant": "Q4_K_M",
        "role": "baseline",
        "notes": "Current production baseline.",
    },
    {
        "slug": "qwen3_4b_iq4_nl",
        "label": "Qwen3-4B-Instruct-2507-IQ4_NL.gguf",
        "family": "Qwen3 4B",
        "quant": "IQ4_NL",
        "role": "quality_per_byte_candidate",
        "notes": "Primary same-size upgrade candidate.",
    },
    {
        "slug": "qwen3_4b_q5_k_m",
        "label": "Qwen3-4B-Instruct-2507-Q5_K_M.gguf",
        "family": "Qwen3 4B",
        "quant": "Q5_K_M",
        "role": "quality_first_candidate",
        "notes": "Higher-fidelity 4B candidate.",
    },
    {
        "slug": "qwen3_8b_iq4_nl",
        "label": "Qwen3-8B-Instruct-IQ4_NL.gguf",
        "family": "Qwen3 8B",
        "quant": "IQ4_NL",
        "role": "larger_model_candidate",
        "notes": "First larger-model fit candidate.",
    },
    {
        "slug": "qwen3_8b_q4_k_m",
        "label": "Qwen3-8B-Instruct-Q4_K_M.gguf",
        "family": "Qwen3 8B",
        "quant": "Q4_K_M",
        "role": "larger_model_candidate",
        "notes": "Second larger-model fit candidate.",
    },
]


@dataclass(frozen=True)
class PromptCase:
    id: str
    label: str
    prompt: str
    max_tokens: int
    validation: str


PROMPT_CASES = [
    PromptCase(
        id="exact_short_answer",
        label="Exact short answer",
        prompt="Reply with exactly BASELINE_OK",
        max_tokens=8,
        validation="exact:BASELINE_OK",
    ),
    PromptCase(
        id="code_edit_reasoning",
        label="Code edit reasoning",
        prompt=(
            "You are reviewing a local NixOS/llama.cpp stack. "
            "Give a concise patch plan to reduce inference latency without changing service ports. "
            "Return 3 short bullet points."
        ),
        max_tokens=120,
        validation="non_empty",
    ),
    PromptCase(
        id="rag_synthesis",
        label="RAG synthesis",
        prompt=(
            "Summarize these snippets into two sentences:\n"
            "1. llama.cpp exposes /metrics with token throughput and KV cache stats.\n"
            "2. This host runs Qwen3-4B locally via GGUF.\n"
            "3. BitNet remains benchmark-only until runtime parity is proven."
        ),
        max_tokens=80,
        validation="non_empty",
    ),
    PromptCase(
        id="instruction_following",
        label="Instruction following",
        prompt=(
            "Return valid JSON only with keys "
            "\"risk\", \"decision\", and \"next_step\" describing whether to promote a candidate local model."
        ),
        max_tokens=120,
        validation="json_object",
    ),
]


def _load_observer_module():
    spec = importlib.util.spec_from_file_location("aq_llama_benchmark_observe", OBSERVE_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load observer module: {OBSERVE_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_batch(contexts: Iterable[int] = DEFAULT_CONTEXTS) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    for model in DEFAULT_BATCH_MODELS:
        for ctx_size in contexts:
            run_id = f"{model['slug']}_ctx{ctx_size}"
            runs.append(
                {
                    "run_id": run_id,
                    "target_model": model["label"],
                    "family": model["family"],
                    "quant": model["quant"],
                    "target_ctx_size": ctx_size,
                    "status": "pending",
                    "role": model["role"],
                    "notes": model["notes"],
                    "prompt_suite": [case.id for case in PROMPT_CASES],
                    "promotion_gate": (
                        "Do not extend this candidate to 32K until it clears the 8K and 16K runs "
                        "with stable latency, acceptable quality, and safe memory headroom."
                    ),
                }
            )
    return {
        "status": "ok",
        "benchmark_name": "llama.cpp quant and model ladder",
        "contexts_requested": list(contexts),
        "winners_extend_to_ctx": [32768],
        "runs": runs,
        "scorecard_fields": [
            "target_model",
            "active_model",
            "target_ctx_size",
            "active_ctx_size",
            "cold_latency_s",
            "warm_latency_s",
            "warm_ttft_s",
            "avg_completion_tokens_per_second",
            "prompt_tokens",
            "completion_tokens",
            "kv_cache_usage_ratio",
            "requests_processing_after",
            "requests_deferred_after",
            "quality_checks",
            "manual_cpu_utilization_pct",
            "manual_gpu_utilization_pct",
            "manual_peak_rss_mb",
            "manual_power_watts",
            "manual_notes",
        ],
    }


def parse_metrics(text: str) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        try:
            metrics[parts[0]] = float(parts[1])
        except ValueError:
            continue
    return metrics


def fetch_metrics(metrics_url: str, timeout_seconds: int) -> Dict[str, float]:
    with urllib.request.urlopen(metrics_url, timeout=timeout_seconds) as response:
        text = response.read().decode("utf-8", errors="replace")
    return parse_metrics(text)


def _usage_from_body(body: Dict[str, Any]) -> Dict[str, int]:
    usage = body.get("usage") or {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def _extract_text(body: Dict[str, Any]) -> str:
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "".join(parts).strip()
    return ""


def post_completion(api_url: str, payload: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
    request = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = json.load(response)
    elapsed = round(time.time() - started, 3)
    text = _extract_text(body)
    usage = _usage_from_body(body)
    tps = round(usage["completion_tokens"] / elapsed, 3) if elapsed > 0 and usage["completion_tokens"] > 0 else 0.0
    return {
        "latency_s": elapsed,
        "content": text,
        "usage": usage,
        "finish_reason": ((body.get("choices") or [{}])[0].get("finish_reason") or ""),
        "completion_tokens_per_second": tps,
    }


def post_completion_stream_ttft(api_url: str, payload: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
    stream_payload = dict(payload)
    stream_payload["stream"] = True
    request = urllib.request.Request(
        api_url,
        data=json.dumps(stream_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    first_token_at: Optional[float] = None
    collected: List[str] = []
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = ((event.get("choices") or [{}])[0].get("delta") or {})
            token = delta.get("content")
            if token:
                collected.append(str(token))
                if first_token_at is None:
                    first_token_at = time.time()
    ttft = round((first_token_at - started), 3) if first_token_at is not None else None
    return {
        "ttft_s": ttft,
        "content_preview": "".join(collected).strip()[:200],
    }


def validate_output(content: str, validation: str) -> Dict[str, Any]:
    if validation.startswith("exact:"):
        expected = validation.split(":", 1)[1]
        return {"passed": content.strip() == expected, "kind": "exact", "expected": expected}
    if validation == "json_object":
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {"passed": False, "kind": "json_object"}
        return {
            "passed": isinstance(parsed, dict) and {"risk", "decision", "next_step"}.issubset(parsed.keys()),
            "kind": "json_object",
        }
    return {"passed": bool(content.strip()), "kind": "non_empty"}


def metric_value(metrics: Dict[str, float], *names: str) -> Optional[float]:
    for name in names:
        if name in metrics:
            return metrics[name]
    return None


def run_scorecard(
    *,
    api_url: str,
    metrics_url: str,
    timeout_seconds: int,
    target_model: str,
    active_model: str,
    target_ctx_size: int,
    active_ctx_size: int,
    run_id: str,
    sample_interval: float,
) -> Dict[str, Any]:
    observer = _load_observer_module()
    pid = observer.discover_llama_pid("llama-cpp.service")
    device = observer.find_amd_gpu_device()
    cpu_count = observer.os.cpu_count() or 1
    stop_event = Event()
    samples: List[Dict[str, Any]] = []

    def sample_loop() -> None:
        prev_proc = observer.process_cpu_ticks(pid)
        prev_total = observer.system_cpu_ticks()
        while not stop_event.is_set():
            time.sleep(sample_interval)
            sample, prev_proc, prev_total = observer.take_sample(
                pid,
                prev_proc,
                prev_total,
                cpu_count,
                device,
            )
            samples.append(sample)

    metrics_before = fetch_metrics(metrics_url, timeout_seconds)
    prompt_reports: List[Dict[str, Any]] = []
    sampler: Optional[Thread] = None
    if pid > 0:
        sampler = Thread(target=sample_loop, daemon=True)
        sampler.start()

    try:
        for case in PROMPT_CASES:
            payload = {
                "model": active_model,
                "messages": [{"role": "user", "content": case.prompt}],
                "max_tokens": case.max_tokens,
                "temperature": 0,
            }
            cold = post_completion(api_url, payload, timeout_seconds)
            warm = post_completion(api_url, payload, timeout_seconds)
            ttft = post_completion_stream_ttft(api_url, payload, timeout_seconds)
            prompt_reports.append(
                {
                    "id": case.id,
                    "label": case.label,
                    "validation": validate_output(warm["content"], case.validation),
                    "cold": cold,
                    "warm": warm,
                    "warm_stream": ttft,
                }
            )
    finally:
        stop_event.set()
        if sampler is not None:
            sampler.join(timeout=max(1.0, sample_interval * 4))

    metrics_after = fetch_metrics(metrics_url, timeout_seconds)
    prompt_tokens_total = sum(item["warm"]["usage"]["prompt_tokens"] for item in prompt_reports)
    completion_tokens_total = sum(item["warm"]["usage"]["completion_tokens"] for item in prompt_reports)
    avg_cold_latency = round(sum(item["cold"]["latency_s"] for item in prompt_reports) / len(prompt_reports), 3)
    avg_warm_latency = round(sum(item["warm"]["latency_s"] for item in prompt_reports) / len(prompt_reports), 3)
    ttfts = [item["warm_stream"]["ttft_s"] for item in prompt_reports if item["warm_stream"]["ttft_s"] is not None]
    avg_ttft = round(sum(ttfts) / len(ttfts), 3) if ttfts else None
    avg_tps = round(
        sum(item["warm"]["completion_tokens_per_second"] for item in prompt_reports) / len(prompt_reports),
        3,
    )

    predicted_before = metric_value(metrics_before, "llamacpp:tokens_predicted_total", "llamacpp_tokens_predicted_total") or 0.0
    predicted_after = metric_value(metrics_after, "llamacpp:tokens_predicted_total", "llamacpp_tokens_predicted_total") or 0.0
    prompt_before = metric_value(metrics_before, "llamacpp:prompt_tokens_total", "llamacpp_prompt_tokens_total") or 0.0
    prompt_after = metric_value(metrics_after, "llamacpp:prompt_tokens_total", "llamacpp_prompt_tokens_total") or 0.0

    resource_summary = observer.summarize_samples(samples, pid=pid) if pid > 0 else {
        "status": "pid_unavailable",
        "pid": pid,
        "sample_count": 0,
    }

    return {
        "status": "ok",
        "run_id": run_id,
        "target_model": target_model,
        "active_model": active_model,
        "target_ctx_size": target_ctx_size,
        "active_ctx_size": active_ctx_size,
        "api_url": api_url,
        "metrics_url": metrics_url,
        "summary": {
            "avg_cold_latency_s": avg_cold_latency,
            "avg_warm_latency_s": avg_warm_latency,
            "avg_warm_ttft_s": avg_ttft,
            "avg_completion_tokens_per_second": avg_tps,
            "prompt_tokens": prompt_tokens_total,
            "completion_tokens": completion_tokens_total,
            "metrics_prompt_tokens_delta": round(prompt_after - prompt_before, 3),
            "metrics_predicted_tokens_delta": round(predicted_after - predicted_before, 3),
            "kv_cache_usage_ratio": metric_value(
                metrics_after,
                "llamacpp:kv_cache_usage_ratio",
                "llamacpp_kv_cache_usage_ratio",
            ),
            "requests_processing_after": metric_value(
                metrics_after,
                "llamacpp:requests_processing",
                "llamacpp_requests_processing",
            ),
            "requests_deferred_after": metric_value(
                metrics_after,
                "llamacpp:requests_deferred",
                "llamacpp_requests_deferred",
                "llamacpp:requests_pending",
                "llamacpp_requests_pending",
            ),
            "all_quality_checks_passed": all(item["validation"]["passed"] for item in prompt_reports),
        },
        "prompt_reports": prompt_reports,
        "manual_observations": {
            "cpu_utilization_pct": resource_summary.get("avg_cpu_percent"),
            "gpu_utilization_pct": resource_summary.get("avg_gpu_busy_percent"),
            "peak_rss_mb": resource_summary.get("peak_rss_mb"),
            "power_watts": resource_summary.get("avg_gpu_power_watts"),
            "notes": "",
        },
        "resource_observations": resource_summary,
        "acceptance_reference": {
            "promote_if": [
                "No crashes or hangs during repeated requests.",
                "Average warm latency is within 20% of the production baseline unless quality is materially better.",
                "Average completion tokens/sec is equal to baseline or within 10% if quality is better.",
                "Quality checks pass across the fixed prompt suite.",
                "Safe memory and power headroom remain after the run.",
            ]
        },
    }


def render_markdown(batch: Dict[str, Any]) -> str:
    lines = [
        "# Llama.cpp Benchmark Worksheet",
        "",
        f"- Contexts: {', '.join(str(item) for item in batch['contexts_requested'])}",
        f"- Extend winners to: {', '.join(str(item) for item in batch['winners_extend_to_ctx'])}",
        "",
        "| Run ID | Target Model | Quant | Context | Status | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for run in batch["runs"]:
        lines.append(
            f"| {run['run_id']} | {run['target_model']} | {run['quant']} | {run['target_ctx_size']} | {run['status']} | {run['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Scorecard Fields",
            "",
        ]
    )
    for field_name in batch["scorecard_fields"]:
        lines.append(f"- {field_name}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and record a llama.cpp benchmark worksheet.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--metrics-url", default=DEFAULT_METRICS_URL)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--contexts", default="8192,16384", help="Comma-separated context sizes for worksheet generation.")
    parser.add_argument("--run-id", default="", help="Worksheet run_id to record against during --run-live.")
    parser.add_argument("--run-live", action="store_true", help="Record a live scorecard from the active llama.cpp service.")
    parser.add_argument("--target-model", default="", help="Override the worksheet target model label for --run-live.")
    parser.add_argument("--active-model", default="", help="Model string to send to the active llama.cpp server.")
    parser.add_argument("--active-ctx-size", type=int, default=0, help="Active ctx-size currently configured on the llama.cpp service.")
    parser.add_argument("--output", default="", help="Optional path to write JSON/Markdown output.")
    parser.add_argument("--sample-interval", type=float, default=0.25, help="Resource sampling interval during --run-live.")
    parser.add_argument("--save-run", action="store_true", help=f"Save --run-live JSON to {DEFAULT_RUNS_DIR}.")
    return parser.parse_args()


def find_run(batch: Dict[str, Any], run_id: str) -> Optional[Dict[str, Any]]:
    for run in batch["runs"]:
        if run["run_id"] == run_id:
            return run
    return None


def emit_output(payload: str, output: str) -> None:
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    print(payload)


def datetime_utc_slug() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def save_run(report: Dict[str, Any], runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{datetime_utc_slug()}-{report.get('run_id', 'benchmark')}.json"
    payload = dict(report)
    payload["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload["saved_path"] = str(path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    contexts = [int(item.strip()) for item in args.contexts.split(",") if item.strip()]
    batch = build_batch(contexts)

    if not args.run_live:
        payload = json.dumps(batch, indent=2) if args.format == "json" else render_markdown(batch)
        emit_output(payload, args.output)
        return 0

    if not args.run_id:
        raise SystemExit("ERROR: --run-id is required with --run-live")
    run = find_run(batch, args.run_id)
    if run is None:
        raise SystemExit(f"ERROR: unknown --run-id: {args.run_id}")

    active_model = args.active_model or run["target_model"]
    active_ctx_size = args.active_ctx_size or int(run["target_ctx_size"])
    target_model = args.target_model or str(run["target_model"])

    try:
        report = run_scorecard(
            api_url=args.api_url,
            metrics_url=args.metrics_url,
            timeout_seconds=args.timeout_seconds,
            target_model=target_model,
            active_model=active_model,
            target_ctx_size=int(run["target_ctx_size"]),
            active_ctx_size=active_ctx_size,
            run_id=args.run_id,
            sample_interval=args.sample_interval,
        )
    except urllib.error.URLError as exc:
        raise SystemExit(f"ERROR: unable to reach llama.cpp endpoint: {exc}") from exc

    if args.save_run:
        saved_path = save_run(report, DEFAULT_RUNS_DIR)
        report = dict(report)
        report["saved_path"] = str(saved_path)
    payload = json.dumps(report, indent=2)
    emit_output(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
