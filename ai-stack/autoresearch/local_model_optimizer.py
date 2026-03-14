#!/usr/bin/env python3
"""
Local Model Optimizer for AI Stack

Optimizes both chat and embedding models:
- Chat model (llama-cpp): prompt templates, system messages, temperature
- Embedding model: batch sizes, normalization, dimensionality

Measures:
- Tokens per successful task completion
- Latency per operation
- Quality scores (semantic similarity, task success)
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import httpx

logger = logging.getLogger("local_model_optimizer")

# Endpoints
SWITCHBOARD_URL = os.getenv("SWITCHBOARD_URL", "http://127.0.0.1:8085")
LLAMA_CHAT_URL = os.getenv("LLAMA_CHAT_URL", "http://127.0.0.1:8080")
LLAMA_EMBED_URL = os.getenv("LLAMA_EMBED_URL", "http://127.0.0.1:8081")
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://127.0.0.1:8003")


@dataclass
class ModelMetrics:
    """Metrics for a model configuration."""
    total_tokens: int = 0
    total_tasks: int = 0
    successful_tasks: int = 0
    total_latency_ms: int = 0
    embedding_dimensions: int = 0

    @property
    def tokens_per_task(self) -> float:
        return self.total_tokens / max(1, self.total_tasks)

    @property
    def success_rate(self) -> float:
        return self.successful_tasks / max(1, self.total_tasks)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(1, self.total_tasks)

    @property
    def efficiency_score(self) -> float:
        """Higher is better: success per token, penalized by latency."""
        if self.tokens_per_task == 0:
            return 0.0
        base_efficiency = self.success_rate / self.tokens_per_task * 1000
        latency_penalty = min(1.0, 1000 / max(100, self.avg_latency_ms))
        return base_efficiency * latency_penalty


@dataclass
class OptimizationConfig:
    """Configuration variant to test."""
    name: str
    model_type: str  # "chat" or "embed"
    parameters: Dict[str, Any]
    description: str = ""


class LocalChatOptimizer:
    """Optimizes local chat model (llama-cpp) for token efficiency."""

    SYSTEM_PROMPT_VARIANTS = [
        {
            "name": "minimal",
            "prompt": "You are a coding assistant. Be concise.",
        },
        {
            "name": "structured",
            "prompt": "You are a coding assistant. Format responses as:\n1. Brief answer\n2. Code (if needed)\n3. One-line explanation",
        },
        {
            "name": "tool_first",
            "prompt": "You are a coding assistant. Prefer using tools over generating long explanations. Be direct.",
        },
        {
            "name": "token_efficient",
            "prompt": "You are an efficient coding assistant. Use minimal tokens. Skip pleasantries. Code only when asked.",
        },
    ]

    TEMPERATURE_VARIANTS = [0.0, 0.1, 0.3, 0.5, 0.7]

    TEST_TASKS = [
        {"query": "Write a Python function to reverse a string", "type": "coding", "expected_has_code": True},
        {"query": "What does git rebase do?", "type": "explanation", "expected_has_code": False},
        {"query": "Fix: TypeError: 'NoneType' object is not subscriptable", "type": "debugging", "expected_has_code": True},
        {"query": "List all .py files in current directory", "type": "tool_use", "expected_has_code": True},
        {"query": "Explain async/await in 2 sentences", "type": "explanation", "expected_has_code": False},
    ]

    def __init__(self, base_url: str = SWITCHBOARD_URL):
        self.base_url = base_url
        self.results: List[Tuple[OptimizationConfig, ModelMetrics]] = []

    async def run_optimization(self, max_variants: int = 5) -> Dict[str, Any]:
        """Run optimization experiments on chat model."""
        logger.info("Starting chat model optimization")

        # Test system prompt variants
        for i, variant in enumerate(self.SYSTEM_PROMPT_VARIANTS[:max_variants]):
            config = OptimizationConfig(
                name=f"system_{variant['name']}",
                model_type="chat",
                parameters={"system_message": variant["prompt"]},
                description=f"System prompt: {variant['name']}"
            )
            metrics = await self._evaluate_config(config)
            self.results.append((config, metrics))
            logger.info(f"Config {config.name}: efficiency={metrics.efficiency_score:.2f}, success={metrics.success_rate:.1%}")

        # Test temperature variants
        for temp in self.TEMPERATURE_VARIANTS[:max_variants]:
            config = OptimizationConfig(
                name=f"temp_{temp}",
                model_type="chat",
                parameters={"temperature": temp},
                description=f"Temperature: {temp}"
            )
            metrics = await self._evaluate_config(config)
            self.results.append((config, metrics))
            logger.info(f"Config {config.name}: efficiency={metrics.efficiency_score:.2f}, success={metrics.success_rate:.1%}")

        # Find best config
        best_config, best_metrics = max(self.results, key=lambda x: x[1].efficiency_score)

        return {
            "best_config": {
                "name": best_config.name,
                "parameters": best_config.parameters,
                "efficiency_score": best_metrics.efficiency_score,
                "tokens_per_task": best_metrics.tokens_per_task,
                "success_rate": best_metrics.success_rate,
            },
            "all_results": [
                {
                    "name": c.name,
                    "efficiency": m.efficiency_score,
                    "tokens_per_task": m.tokens_per_task,
                    "success_rate": m.success_rate,
                    "avg_latency_ms": m.avg_latency_ms,
                }
                for c, m in sorted(self.results, key=lambda x: -x[1].efficiency_score)
            ]
        }

    async def _evaluate_config(self, config: OptimizationConfig) -> ModelMetrics:
        """Evaluate a configuration against test tasks."""
        metrics = ModelMetrics()

        async with httpx.AsyncClient(timeout=60.0) as client:
            for task in self.TEST_TASKS:
                start_ms = int(time.time() * 1000)

                try:
                    payload = {
                        "model": "continue-local",
                        "messages": [
                            {"role": "system", "content": config.parameters.get("system_message", "You are a helpful assistant.")},
                            {"role": "user", "content": task["query"]}
                        ],
                        "temperature": config.parameters.get("temperature", 0.7),
                        "max_tokens": 512,
                    }

                    resp = await client.post(
                        f"{self.base_url}/v1/chat/completions",
                        json=payload,
                        headers={"Authorization": "Bearer local-llama-cpp"}
                    )

                    if resp.status_code == 200:
                        result = resp.json()
                        usage = result.get("usage", {})
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                        metrics.total_tokens += usage.get("total_tokens", len(content) // 4)
                        metrics.total_tasks += 1

                        # Check success based on task type
                        has_code = "```" in content or "def " in content or "function " in content
                        if task["expected_has_code"]:
                            success = has_code and len(content) > 50
                        else:
                            success = len(content) > 20 and len(content) < 500

                        if success:
                            metrics.successful_tasks += 1

                        metrics.total_latency_ms += int(time.time() * 1000) - start_ms

                except Exception as e:
                    logger.warning(f"Task failed: {e}")
                    metrics.total_tasks += 1

        return metrics


class LocalEmbedOptimizer:
    """Optimizes local embedding model for efficiency."""

    BATCH_SIZE_VARIANTS = [1, 4, 8, 16, 32]

    TEST_TEXTS = [
        "How to implement a binary search tree in Python",
        "NixOS module configuration for systemd services",
        "Fix memory leak in async JavaScript code",
        "Docker compose networking best practices",
        "Git rebase vs merge workflow comparison",
        "TypeScript generics with constraints",
        "Kubernetes pod scheduling affinity rules",
        "PostgreSQL query optimization techniques",
    ]

    def __init__(self, embed_url: str = LLAMA_EMBED_URL):
        self.embed_url = embed_url
        self.results: List[Tuple[OptimizationConfig, ModelMetrics]] = []

    async def run_optimization(self, max_variants: int = 5) -> Dict[str, Any]:
        """Run optimization experiments on embedding model."""
        logger.info("Starting embedding model optimization")

        for batch_size in self.BATCH_SIZE_VARIANTS[:max_variants]:
            config = OptimizationConfig(
                name=f"batch_{batch_size}",
                model_type="embed",
                parameters={"batch_size": batch_size},
                description=f"Batch size: {batch_size}"
            )
            metrics = await self._evaluate_config(config)
            self.results.append((config, metrics))
            logger.info(f"Config {config.name}: efficiency={metrics.efficiency_score:.2f}, latency={metrics.avg_latency_ms:.0f}ms")

        # Find best config
        best_config, best_metrics = max(self.results, key=lambda x: x[1].efficiency_score)

        return {
            "best_config": {
                "name": best_config.name,
                "parameters": best_config.parameters,
                "efficiency_score": best_metrics.efficiency_score,
                "avg_latency_ms": best_metrics.avg_latency_ms,
                "embedding_dimensions": best_metrics.embedding_dimensions,
            },
            "all_results": [
                {
                    "name": c.name,
                    "efficiency": m.efficiency_score,
                    "avg_latency_ms": m.avg_latency_ms,
                    "dimensions": m.embedding_dimensions,
                }
                for c, m in sorted(self.results, key=lambda x: -x[1].efficiency_score)
            ]
        }

    async def _evaluate_config(self, config: OptimizationConfig) -> ModelMetrics:
        """Evaluate embedding configuration."""
        metrics = ModelMetrics()
        batch_size = config.parameters.get("batch_size", 1)

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Process texts in batches
            for i in range(0, len(self.TEST_TEXTS), batch_size):
                batch = self.TEST_TEXTS[i:i + batch_size]
                start_ms = int(time.time() * 1000)

                try:
                    resp = await client.post(
                        f"{self.embed_url}/v1/embeddings",
                        json={"input": batch, "model": "embedding"}
                    )

                    if resp.status_code == 200:
                        result = resp.json()
                        embeddings = result.get("data", [])

                        for emb in embeddings:
                            metrics.total_tasks += 1
                            metrics.successful_tasks += 1
                            if "embedding" in emb:
                                metrics.embedding_dimensions = len(emb["embedding"])

                        # Estimate tokens (roughly 4 chars per token)
                        metrics.total_tokens += sum(len(t) // 4 for t in batch)
                        metrics.total_latency_ms += int(time.time() * 1000) - start_ms

                except Exception as e:
                    logger.warning(f"Batch failed: {e}")
                    metrics.total_tasks += len(batch)

        return metrics


async def run_full_optimization(
    chat_variants: int = 5,
    embed_variants: int = 5
) -> Dict[str, Any]:
    """Run full optimization across both model types."""
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chat": None,
        "embed": None,
        "recommendations": []
    }

    # Optimize chat model
    try:
        chat_optimizer = LocalChatOptimizer()
        results["chat"] = await chat_optimizer.run_optimization(chat_variants)

        if results["chat"]["best_config"]["efficiency_score"] > 0:
            results["recommendations"].append({
                "type": "chat",
                "action": "apply_config",
                "config": results["chat"]["best_config"]["parameters"],
                "expected_improvement": f"{results['chat']['best_config']['efficiency_score']:.1f} efficiency score"
            })
    except Exception as e:
        logger.error(f"Chat optimization failed: {e}")
        results["chat"] = {"error": str(e)}

    # Optimize embedding model
    try:
        embed_optimizer = LocalEmbedOptimizer()
        results["embed"] = await embed_optimizer.run_optimization(embed_variants)

        if results["embed"]["best_config"]["efficiency_score"] > 0:
            results["recommendations"].append({
                "type": "embed",
                "action": "apply_config",
                "config": results["embed"]["best_config"]["parameters"],
                "expected_improvement": f"{results['embed']['best_config']['avg_latency_ms']:.0f}ms avg latency"
            })
    except Exception as e:
        logger.error(f"Embed optimization failed: {e}")
        results["embed"] = {"error": str(e)}

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    chat_n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    embed_n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    result = asyncio.run(run_full_optimization(chat_n, embed_n))
    print(json.dumps(result, indent=2))
