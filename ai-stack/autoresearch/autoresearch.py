#!/usr/bin/env python3
"""
Autoresearch Integration for AI Stack Harness

Adapted from Karpathy's autoresearch concept for local model optimization.
Focuses on:
- Token efficiency per successful task completion
- Prompt/system message optimization
- Tool use pattern improvement
- Response quality scoring

Architecture:
- experiment_runner: Executes bounded experiments
- evaluator: Measures token efficiency and task success
- optimizer: Suggests improvements based on results
- ledger: Tracks all experiments and outcomes
"""

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger("autoresearch")

# Configuration
AUTORESEARCH_DIR = Path(os.getenv("AUTORESEARCH_DIR", Path(__file__).parent))
EXPERIMENTS_DB = AUTORESEARCH_DIR / "experiments.sqlite"
RESULTS_DIR = AUTORESEARCH_DIR / "results"
MAX_EXPERIMENT_DURATION_S = int(os.getenv("AUTORESEARCH_MAX_DURATION_S", "300"))  # 5 min default


class ExperimentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ExperimentType(Enum):
    PROMPT_OPTIMIZATION = "prompt_optimization"
    SYSTEM_MESSAGE = "system_message"
    TOOL_CALLING = "tool_calling"
    RESPONSE_FORMAT = "response_format"
    TEMPERATURE_TUNING = "temperature_tuning"
    CONTEXT_COMPRESSION = "context_compression"


@dataclass
class TokenMetrics:
    """Track token usage for efficiency measurement."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_per_task: float = 0.0
    success_rate: float = 0.0
    efficiency_score: float = 0.0  # success_rate / tokens_per_task (higher is better)

    def compute_efficiency(self, task_count: int = 1) -> float:
        """Compute efficiency score: success per token."""
        if self.total_tokens == 0 or task_count == 0:
            return 0.0
        self.tokens_per_task = self.total_tokens / task_count
        if self.tokens_per_task > 0:
            self.efficiency_score = self.success_rate / self.tokens_per_task * 1000
        return self.efficiency_score


@dataclass
class Experiment:
    """Represents a single optimization experiment."""
    id: str
    experiment_type: ExperimentType
    hypothesis: str
    baseline_config: Dict[str, Any]
    variant_config: Dict[str, Any]
    status: ExperimentStatus = ExperimentStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    baseline_metrics: Optional[TokenMetrics] = None
    variant_metrics: Optional[TokenMetrics] = None
    improvement_pct: float = 0.0
    accepted: bool = False
    notes: str = ""


class ExperimentLedger:
    """SQLite-backed experiment tracking."""

    def __init__(self, db_path: Path = EXPERIMENTS_DB):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the experiments database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    experiment_type TEXT NOT NULL,
                    hypothesis TEXT NOT NULL,
                    baseline_config TEXT NOT NULL,
                    variant_config TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    baseline_metrics TEXT,
                    variant_metrics TEXT,
                    improvement_pct REAL DEFAULT 0.0,
                    accepted INTEGER DEFAULT 0,
                    notes TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_completions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    is_baseline INTEGER NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_experiment
                ON task_completions(experiment_id, is_baseline)
            """)
            conn.commit()

    def create_experiment(self, exp: Experiment) -> str:
        """Create a new experiment record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO experiments (
                    id, experiment_type, hypothesis, baseline_config, variant_config,
                    status, created_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exp.id, exp.experiment_type.value, exp.hypothesis,
                json.dumps(exp.baseline_config), json.dumps(exp.variant_config),
                exp.status.value, exp.created_at, exp.notes
            ))
            conn.commit()
        return exp.id

    def update_experiment(self, exp: Experiment):
        """Update an experiment record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE experiments SET
                    status = ?,
                    started_at = ?,
                    completed_at = ?,
                    baseline_metrics = ?,
                    variant_metrics = ?,
                    improvement_pct = ?,
                    accepted = ?,
                    notes = ?
                WHERE id = ?
            """, (
                exp.status.value,
                exp.started_at,
                exp.completed_at,
                json.dumps(asdict(exp.baseline_metrics)) if exp.baseline_metrics else None,
                json.dumps(asdict(exp.variant_metrics)) if exp.variant_metrics else None,
                exp.improvement_pct,
                1 if exp.accepted else 0,
                exp.notes,
                exp.id
            ))
            conn.commit()

    def record_task_completion(
        self,
        experiment_id: str,
        task_type: str,
        is_baseline: bool,
        prompt_tokens: int,
        completion_tokens: int,
        success: bool,
        duration_ms: int
    ):
        """Record a task completion for an experiment."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO task_completions (
                    experiment_id, task_type, is_baseline, prompt_tokens,
                    completion_tokens, success, duration_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                experiment_id, task_type, 1 if is_baseline else 0,
                prompt_tokens, completion_tokens, 1 if success else 0,
                duration_ms, datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

    def get_experiment_metrics(self, experiment_id: str, is_baseline: bool) -> TokenMetrics:
        """Compute token metrics for an experiment arm."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(prompt_tokens + completion_tokens) as total_tokens,
                    AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                    COUNT(*) as task_count
                FROM task_completions
                WHERE experiment_id = ? AND is_baseline = ?
            """, (experiment_id, 1 if is_baseline else 0)).fetchone()

            if not rows or rows["task_count"] == 0:
                return TokenMetrics()

            metrics = TokenMetrics(
                prompt_tokens=rows["prompt_tokens"] or 0,
                completion_tokens=rows["completion_tokens"] or 0,
                total_tokens=rows["total_tokens"] or 0,
                success_rate=rows["success_rate"] or 0.0
            )
            metrics.compute_efficiency(rows["task_count"])
            return metrics

    def get_accepted_experiments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently accepted experiments."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM experiments
                WHERE accepted = 1
                ORDER BY completed_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_experiment_summary(self) -> Dict[str, Any]:
        """Get summary statistics of all experiments."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) as accepted,
                    AVG(CASE WHEN accepted = 1 THEN improvement_pct ELSE NULL END) as avg_improvement
                FROM experiments
            """).fetchone()

            by_type = conn.execute("""
                SELECT
                    experiment_type,
                    COUNT(*) as count,
                    SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) as accepted,
                    AVG(CASE WHEN accepted = 1 THEN improvement_pct ELSE NULL END) as avg_improvement
                FROM experiments
                GROUP BY experiment_type
            """).fetchall()

            return {
                "total": stats["total"] or 0,
                "completed": stats["completed"] or 0,
                "accepted": stats["accepted"] or 0,
                "avg_improvement_pct": round(stats["avg_improvement"] or 0, 2),
                "by_type": {r["experiment_type"]: {
                    "count": r["count"],
                    "accepted": r["accepted"],
                    "avg_improvement": round(r["avg_improvement"] or 0, 2)
                } for r in by_type}
            }


class ExperimentRunner:
    """Runs optimization experiments with bounded duration."""

    def __init__(
        self,
        ledger: ExperimentLedger,
        coordinator_url: str = "http://127.0.0.1:8003",
        max_duration_s: int = MAX_EXPERIMENT_DURATION_S
    ):
        self.ledger = ledger
        self.coordinator_url = coordinator_url
        self.max_duration_s = max_duration_s

    async def run_experiment(
        self,
        experiment: Experiment,
        task_suite: List[Dict[str, Any]]
    ) -> Experiment:
        """Run an experiment comparing baseline vs variant."""
        import httpx

        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now(timezone.utc).isoformat()
        self.ledger.update_experiment(experiment)

        start_time = time.time()

        try:
            # Run baseline tasks
            logger.info(f"Running baseline for experiment {experiment.id}")
            for task in task_suite:
                if time.time() - start_time > self.max_duration_s / 2:
                    break
                await self._run_task(experiment, task, is_baseline=True)

            # Run variant tasks
            logger.info(f"Running variant for experiment {experiment.id}")
            for task in task_suite:
                if time.time() - start_time > self.max_duration_s:
                    break
                await self._run_task(experiment, task, is_baseline=False)

            # Compute metrics
            experiment.baseline_metrics = self.ledger.get_experiment_metrics(experiment.id, True)
            experiment.variant_metrics = self.ledger.get_experiment_metrics(experiment.id, False)

            # Compute improvement
            if experiment.baseline_metrics.efficiency_score > 0:
                experiment.improvement_pct = (
                    (experiment.variant_metrics.efficiency_score - experiment.baseline_metrics.efficiency_score)
                    / experiment.baseline_metrics.efficiency_score * 100
                )

            # Auto-accept if improvement > 5%
            experiment.accepted = experiment.improvement_pct > 5.0
            experiment.status = ExperimentStatus.ACCEPTED if experiment.accepted else ExperimentStatus.REJECTED

        except Exception as e:
            experiment.status = ExperimentStatus.FAILED
            experiment.notes = f"Error: {str(e)}"
            logger.exception(f"Experiment {experiment.id} failed")

        experiment.completed_at = datetime.now(timezone.utc).isoformat()
        self.ledger.update_experiment(experiment)
        return experiment

    async def _run_task(
        self,
        experiment: Experiment,
        task: Dict[str, Any],
        is_baseline: bool
    ):
        """Run a single task and record metrics."""
        import httpx

        config = experiment.baseline_config if is_baseline else experiment.variant_config

        # Apply config to task
        task_with_config = {**task}
        if "system_message" in config:
            task_with_config["system_message"] = config["system_message"]
        if "temperature" in config:
            task_with_config["temperature"] = config["temperature"]

        start_ms = int(time.time() * 1000)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.coordinator_url}/query",
                    json={
                        "query": task_with_config.get("query", ""),
                        "mode": "local",
                        "generate_response": True,
                        **{k: v for k, v in task_with_config.items() if k not in ("query",)}
                    }
                )
                result = resp.json()

                duration_ms = int(time.time() * 1000) - start_ms

                # Extract token counts from response
                prompt_tokens = result.get("usage", {}).get("prompt_tokens", 0)
                completion_tokens = result.get("usage", {}).get("completion_tokens", 0)

                # Estimate if not provided
                if prompt_tokens == 0:
                    prompt_tokens = len(task_with_config.get("query", "")) // 4
                if completion_tokens == 0:
                    response_text = result.get("response", "") or result.get("synthesis", "")
                    completion_tokens = len(response_text) // 4

                # Determine success (has meaningful response)
                success = bool(
                    result.get("response") or
                    result.get("synthesis") or
                    (result.get("results") and len(result["results"]) > 0)
                )

                self.ledger.record_task_completion(
                    experiment.id,
                    task.get("type", "general"),
                    is_baseline,
                    prompt_tokens,
                    completion_tokens,
                    success,
                    duration_ms
                )

        except Exception as e:
            logger.warning(f"Task failed: {e}")
            self.ledger.record_task_completion(
                experiment.id,
                task.get("type", "general"),
                is_baseline,
                0, 0, False, 0
            )


class OptimizationProposer:
    """Proposes new experiments based on current performance."""

    DEFAULT_TASK_SUITE = [
        {"query": "Fix a TypeError in Python", "type": "coding"},
        {"query": "List files matching *.py", "type": "tool_use"},
        {"query": "Explain the git rebase command", "type": "explanation"},
        {"query": "Write a function to parse JSON", "type": "coding"},
        {"query": "Search for database connection code", "type": "tool_use"},
    ]

    PROMPT_VARIANTS = [
        {
            "name": "concise",
            "system_message": "You are a concise coding assistant. Provide minimal, direct answers."
        },
        {
            "name": "structured",
            "system_message": "You are a coding assistant. Structure responses with: 1) Summary 2) Code 3) Notes"
        },
        {
            "name": "tool_focused",
            "system_message": "You are a coding assistant that prefers using tools over generating text."
        },
    ]

    def __init__(self, ledger: ExperimentLedger):
        self.ledger = ledger

    def propose_next_experiment(self) -> Optional[Experiment]:
        """Propose the next experiment to run."""
        summary = self.ledger.get_experiment_summary()

        # Find experiment type with lowest acceptance rate
        type_stats = summary.get("by_type", {})

        # Default to prompt optimization if no experiments yet
        if summary["total"] == 0:
            return self._create_prompt_experiment(0)

        # Try each type in order of potential
        for exp_type in ExperimentType:
            stats = type_stats.get(exp_type.value, {"count": 0})
            if stats["count"] < 3:  # Each type needs at least 3 experiments
                if exp_type == ExperimentType.PROMPT_OPTIMIZATION:
                    variant_idx = stats["count"] % len(self.PROMPT_VARIANTS)
                    return self._create_prompt_experiment(variant_idx)
                elif exp_type == ExperimentType.TEMPERATURE_TUNING:
                    return self._create_temperature_experiment(stats["count"])

        # Default: keep optimizing prompts
        return self._create_prompt_experiment(summary["total"] % len(self.PROMPT_VARIANTS))

    def _create_prompt_experiment(self, variant_idx: int) -> Experiment:
        """Create a prompt optimization experiment."""
        variant = self.PROMPT_VARIANTS[variant_idx % len(self.PROMPT_VARIANTS)]
        exp_id = hashlib.sha256(
            f"prompt_{variant['name']}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        return Experiment(
            id=exp_id,
            experiment_type=ExperimentType.PROMPT_OPTIMIZATION,
            hypothesis=f"Using '{variant['name']}' prompt style improves token efficiency",
            baseline_config={"system_message": "You are a helpful coding assistant."},
            variant_config={"system_message": variant["system_message"]},
            notes=f"Testing {variant['name']} prompt variant"
        )

    def _create_temperature_experiment(self, iteration: int) -> Experiment:
        """Create a temperature tuning experiment."""
        temperatures = [0.0, 0.3, 0.5, 0.7, 1.0]
        temp = temperatures[iteration % len(temperatures)]
        exp_id = hashlib.sha256(
            f"temp_{temp}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        return Experiment(
            id=exp_id,
            experiment_type=ExperimentType.TEMPERATURE_TUNING,
            hypothesis=f"Temperature {temp} improves token efficiency for coding tasks",
            baseline_config={"temperature": 0.7},
            variant_config={"temperature": temp},
            notes=f"Testing temperature {temp}"
        )

    def get_task_suite(self) -> List[Dict[str, Any]]:
        """Get the standard task suite for experiments."""
        return self.DEFAULT_TASK_SUITE.copy()


async def run_autoresearch_loop(
    max_experiments: int = 5,
    coordinator_url: str = "http://127.0.0.1:8003"
) -> Dict[str, Any]:
    """Run the autoresearch optimization loop."""
    ledger = ExperimentLedger()
    runner = ExperimentRunner(ledger, coordinator_url)
    proposer = OptimizationProposer(ledger)

    results = []

    for i in range(max_experiments):
        experiment = proposer.propose_next_experiment()
        if not experiment:
            break

        ledger.create_experiment(experiment)
        task_suite = proposer.get_task_suite()

        logger.info(f"Running experiment {i+1}/{max_experiments}: {experiment.hypothesis}")
        experiment = await runner.run_experiment(experiment, task_suite)

        results.append({
            "id": experiment.id,
            "type": experiment.experiment_type.value,
            "hypothesis": experiment.hypothesis,
            "improvement_pct": round(experiment.improvement_pct, 2),
            "accepted": experiment.accepted,
            "baseline_efficiency": experiment.baseline_metrics.efficiency_score if experiment.baseline_metrics else 0,
            "variant_efficiency": experiment.variant_metrics.efficiency_score if experiment.variant_metrics else 0,
        })

        if experiment.accepted:
            logger.info(f"Experiment ACCEPTED: {experiment.improvement_pct:.1f}% improvement")
        else:
            logger.info(f"Experiment rejected: {experiment.improvement_pct:.1f}% change")

    return {
        "experiments_run": len(results),
        "accepted": sum(1 for r in results if r["accepted"]),
        "results": results,
        "summary": ledger.get_experiment_summary()
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    max_exp = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    result = asyncio.run(run_autoresearch_loop(max_experiments=max_exp))
    print(json.dumps(result, indent=2))
