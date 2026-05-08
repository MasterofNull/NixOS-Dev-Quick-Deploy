"""
Model Optimization Integration for Hybrid Coordinator

Integrates Phase 5 model optimization components:
- Data curation and quality filtering (5.1)
- Continuous fine-tuning pipeline (5.2)
- Model distillation and compression (5.3)

This module bridges the standalone implementations in ai-stack/model-optimization
with the live hybrid coordinator service.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from config import Config

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# Module-level state — populated by init()
# ---------------------------------------------------------------------------
_qdrant: Optional[Any] = None
_embed: Optional[Callable] = None
_record_telemetry: Optional[Callable] = None
_initialized: bool = False

# Runtime paths - use writable state directories
MODEL_OPTIMIZATION_STATE = Path(os.getenv(
    "MODEL_OPTIMIZATION_STATE",
    "/var/lib/ai-stack/hybrid/model-optimization"
))
TRAINING_DATA_DIR = MODEL_OPTIMIZATION_STATE / "training-data"
MODEL_VARIANTS_DIR = MODEL_OPTIMIZATION_STATE / "model-variants"
METRICS_DIR = MODEL_OPTIMIZATION_STATE / "metrics"
SYNTHETIC_DATA_DIR = MODEL_OPTIMIZATION_STATE / "synthetic-data"
ACTIVE_LEARNING_DIR = MODEL_OPTIMIZATION_STATE / "active-learning"
DISTILLATION_DIR = MODEL_OPTIMIZATION_STATE / "distillation"
_MODEL_OPTIMIZATION_IMPL_ROOT = Path(__file__).resolve().parents[2] / "model-optimization"
if str(_MODEL_OPTIMIZATION_IMPL_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODEL_OPTIMIZATION_IMPL_ROOT))


def init(
    *,
    qdrant_client: Any,
    embed_fn: Callable,
    record_telemetry_fn: Optional[Callable] = None,
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _qdrant, _embed, _record_telemetry, _initialized
    _qdrant = qdrant_client
    _embed = embed_fn
    _record_telemetry = record_telemetry_fn
    _initialized = True

    # Ensure runtime directories exist
    for dir_path in [
        TRAINING_DATA_DIR,
        MODEL_VARIANTS_DIR,
        METRICS_DIR,
        SYNTHETIC_DATA_DIR,
        ACTIVE_LEARNING_DIR,
        DISTILLATION_DIR,
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)

    logger.info("model_optimization module initialized, state_dir=%s", MODEL_OPTIMIZATION_STATE)


# ---------------------------------------------------------------------------
# Data Quality Classification
# ---------------------------------------------------------------------------

class DataQuality:
    """Data quality levels matching ai-stack/model-optimization/data_curator.py"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


def assess_interaction_quality(
    query: str,
    response: str,
    outcome: str = "unknown",
    user_feedback: Optional[int] = None,
    latency_ms: Optional[float] = None,
) -> Tuple[DataQuality, float]:
    """
    Assess quality of an interaction for training data inclusion.

    Returns:
        Tuple of (quality_level, numeric_score)
    """
    score = 0.5  # Base score

    # Outcome contribution (0.3 weight)
    if outcome == "success":
        score += 0.3
    elif outcome == "partial":
        score += 0.15
    elif outcome == "failure":
        score -= 0.2

    # User feedback contribution (0.25 weight)
    if user_feedback is not None:
        if user_feedback == 1:
            score += 0.25
        elif user_feedback == 0:
            score += 0.1
        elif user_feedback == -1:
            score -= 0.15

    # Content quality heuristics (0.25 weight)
    query_words = len(query.split())
    response_words = len(response.split())

    # Reasonable query length
    if 5 <= query_words <= 200:
        score += 0.05
    # Substantial response
    if response_words >= 20:
        score += 0.1
    # Code presence bonus
    if "```" in response or "def " in response or "function " in response:
        score += 0.1

    # Latency penalty for slow responses
    if latency_ms is not None and latency_ms > 10000:
        score -= 0.05

    # Clamp to valid range
    score = max(0.0, min(1.0, score))

    # Map to quality level
    if score >= 0.85:
        quality = DataQuality.EXCELLENT
    elif score >= 0.7:
        quality = DataQuality.GOOD
    elif score >= 0.5:
        quality = DataQuality.FAIR
    else:
        quality = DataQuality.POOR

    return quality, score


# ---------------------------------------------------------------------------
# PII Detection and Anonymization
# ---------------------------------------------------------------------------

import re

PII_PATTERNS = {
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone": re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
    "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "credit_card": re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'),
    "api_key": re.compile(r'\b(sk-|pk_|api[_-]?key)[a-zA-Z0-9_-]{20,}\b', re.IGNORECASE),
    "jwt": re.compile(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'),
}


def detect_pii(text: str) -> Dict[str, bool]:
    """Detect PII in text, returning dict of detected types."""
    detected = {}
    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            detected[pii_type] = True
    return detected


def anonymize_pii(text: str) -> str:
    """Anonymize PII in text by replacing with placeholders."""
    result = text

    # Replace in order of specificity
    result = PII_PATTERNS["jwt"].sub("[JWT_TOKEN]", result)
    result = PII_PATTERNS["api_key"].sub("[API_KEY]", result)
    result = PII_PATTERNS["email"].sub("[EMAIL]", result)
    result = PII_PATTERNS["phone"].sub("[PHONE]", result)
    result = PII_PATTERNS["ssn"].sub("[SSN]", result)
    result = PII_PATTERNS["credit_card"].sub("[CREDIT_CARD]", result)

    return result


# ---------------------------------------------------------------------------
# Training Data Capture
# ---------------------------------------------------------------------------

class TrainingDataCapture:
    """
    Captures high-quality interactions for model training.
    Integrates with interaction_tracker for seamless data collection.
    """

    def __init__(self, output_dir: Path = TRAINING_DATA_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pending_examples: List[Dict] = []
        self.stats = {
            "captured": 0,
            "filtered_low_quality": 0,
            "filtered_pii": 0,
        }

    def capture(
        self,
        query: str,
        response: str,
        outcome: str = "unknown",
        user_feedback: Optional[int] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Capture an interaction for training if it meets quality threshold.

        Returns the captured example dict or None if filtered out.
        """
        # Assess quality
        quality, score = assess_interaction_quality(
            query, response, outcome, user_feedback, latency_ms
        )

        # Filter low quality
        if quality == DataQuality.POOR:
            self.stats["filtered_low_quality"] += 1
            logger.debug("Filtered low-quality interaction (score=%.2f)", score)
            return None

        # Check for PII
        pii_in_query = detect_pii(query)
        pii_in_response = detect_pii(response)

        if pii_in_query or pii_in_response:
            self.stats["filtered_pii"] += 1
            # Anonymize instead of rejecting
            query = anonymize_pii(query)
            response = anonymize_pii(response)
            logger.info("Anonymized PII in training example")

        # Create training example
        example = {
            "example_id": str(uuid4()),
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful NixOS and coding assistant specialized in system configuration and development."
                },
                {"role": "user", "content": query},
                {"role": "assistant", "content": response},
            ],
            "quality": quality,
            "quality_score": score,
            "metadata": {
                "outcome": outcome,
                "user_feedback": user_feedback,
                "captured_at": datetime.now().isoformat(),
                **(metadata or {}),
            },
        }

        self.pending_examples.append(example)
        self.stats["captured"] += 1

        logger.debug(
            "Captured training example: quality=%s, score=%.2f",
            quality, score
        )

        return example

    def flush(self) -> str:
        """Save pending examples to disk and return the output path."""
        if not self.pending_examples:
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"captured_{timestamp}.jsonl"

        with open(output_path, "w") as f:
            for example in self.pending_examples:
                # Write in OpenAI chat format for compatibility
                f.write(json.dumps({
                    "messages": example["messages"],
                    "quality_score": example["quality_score"],
                }) + "\n")

        count = len(self.pending_examples)
        self.pending_examples = []

        logger.info("Flushed %d training examples to %s", count, output_path)
        return str(output_path)

    def get_stats(self) -> Dict:
        """Get capture statistics."""
        return {
            **self.stats,
            "pending": len(self.pending_examples),
            "output_dir": str(self.output_dir),
        }


# Singleton instance
_capture: Optional[TrainingDataCapture] = None


def get_capture() -> TrainingDataCapture:
    """Get or create the training data capture instance."""
    global _capture
    if _capture is None:
        _capture = TrainingDataCapture()
    return _capture


# ---------------------------------------------------------------------------
# Fine-Tuning Integration
# ---------------------------------------------------------------------------

class FineTuningStatus:
    """Fine-tuning job status tracking."""

    def __init__(self):
        self.jobs: Dict[str, Dict] = {}
        self.status_file = METRICS_DIR / "finetuning_status.json"
        self._load_status()

    def _load_status(self):
        """Load status from disk if exists."""
        if self.status_file.exists():
            try:
                with open(self.status_file) as f:
                    self.jobs = json.load(f)
            except Exception as e:
                logger.warning("Failed to load finetuning status: %s", e)

    def _save_status(self):
        """Persist status to disk."""
        try:
            with open(self.status_file, "w") as f:
                json.dump(self.jobs, f, indent=2)
        except Exception as e:
            logger.error("Failed to save finetuning status: %s", e)

    def create_job(
        self,
        job_id: str,
        base_model: str,
        task_type: str,
        training_data_path: str,
    ) -> Dict:
        """Create a new fine-tuning job record."""
        job = {
            "job_id": job_id,
            "base_model": base_model,
            "task_type": task_type,
            "training_data_path": training_data_path,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metrics": {},
        }
        self.jobs[job_id] = job
        self._save_status()
        return job

    def update_job(self, job_id: str, **updates) -> Optional[Dict]:
        """Update job status."""
        if job_id not in self.jobs:
            return None

        self.jobs[job_id].update(updates)
        self.jobs[job_id]["updated_at"] = datetime.now().isoformat()
        self._save_status()
        return self.jobs[job_id]

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(self, status: Optional[str] = None) -> List[Dict]:
        """List all jobs, optionally filtered by status."""
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        return sorted(jobs, key=lambda j: j["created_at"], reverse=True)


_finetuning_status: Optional[FineTuningStatus] = None


def get_finetuning_status() -> FineTuningStatus:
    """Get or create fine-tuning status tracker."""
    global _finetuning_status
    if _finetuning_status is None:
        _finetuning_status = FineTuningStatus()
    return _finetuning_status


# ---------------------------------------------------------------------------
# Model Performance Tracking
# ---------------------------------------------------------------------------

class ModelPerformanceTracker:
    """Track model performance metrics over time."""

    def __init__(self):
        self.metrics_file = METRICS_DIR / "model_performance.json"
        self.history: Dict[str, List[Dict]] = {}
        self._load()

    def _load(self):
        """Load metrics from disk."""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    self.history = json.load(f)
            except Exception as e:
                logger.warning("Failed to load model performance: %s", e)

    def _save(self):
        """Persist metrics to disk."""
        try:
            with open(self.metrics_file, "w") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error("Failed to save model performance: %s", e)

    def record(
        self,
        model_id: str,
        task_type: str,
        accuracy: float,
        latency_ms: float,
        quality_score: float,
    ):
        """Record performance metrics for a model."""
        if model_id not in self.history:
            self.history[model_id] = []

        self.history[model_id].append({
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "accuracy": accuracy,
            "latency_ms": latency_ms,
            "quality_score": quality_score,
        })

        # Keep last 1000 records per model
        if len(self.history[model_id]) > 1000:
            self.history[model_id] = self.history[model_id][-1000:]

        self._save()

        logger.debug(
            "Recorded performance for %s: accuracy=%.2f, latency=%.1fms",
            model_id, accuracy, latency_ms
        )

    def get_trend(self, model_id: str, window: int = 10) -> Dict:
        """Get performance trend for a model."""
        if model_id not in self.history:
            return {"status": "no_data", "model_id": model_id}

        records = self.history[model_id][-window:]
        if not records:
            return {"status": "no_data", "model_id": model_id}

        avg_accuracy = sum(r["accuracy"] for r in records) / len(records)
        avg_latency = sum(r["latency_ms"] for r in records) / len(records)
        avg_quality = sum(r["quality_score"] for r in records) / len(records)

        # Determine trend
        if len(records) >= 2:
            first_quality = records[0]["quality_score"]
            last_quality = records[-1]["quality_score"]
            if last_quality > first_quality * 1.05:
                trend = "improving"
            elif last_quality < first_quality * 0.95:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "model_id": model_id,
            "samples": len(records),
            "avg_accuracy": avg_accuracy,
            "avg_latency_ms": avg_latency,
            "avg_quality_score": avg_quality,
            "trend": trend,
        }

    def list_models(self) -> List[str]:
        """List all tracked models."""
        return list(self.history.keys())


_performance_tracker: Optional[ModelPerformanceTracker] = None


def get_performance_tracker() -> ModelPerformanceTracker:
    """Get or create performance tracker."""
    global _performance_tracker
    if _performance_tracker is None:
        _performance_tracker = ModelPerformanceTracker()
    return _performance_tracker


class DistillationJobTracker:
    """Track distillation/compression jobs and persisted artifacts."""

    def __init__(self):
        self.jobs_file = METRICS_DIR / "distillation_jobs.json"
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.jobs_file.exists():
            try:
                with open(self.jobs_file, encoding="utf-8") as handle:
                    self.jobs = json.load(handle)
            except Exception as exc:
                logger.warning("Failed to load distillation jobs: %s", exc)

    def _save(self) -> None:
        try:
            with open(self.jobs_file, "w", encoding="utf-8") as handle:
                json.dump(self.jobs, handle, indent=2)
        except Exception as exc:
            logger.error("Failed to save distillation jobs: %s", exc)

    def record_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.jobs[job_id] = payload
        self._save()
        return payload

    def list_jobs(self) -> List[Dict[str, Any]]:
        return sorted(
            self.jobs.values(),
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )


_distillation_jobs: Optional[DistillationJobTracker] = None


def get_distillation_jobs() -> DistillationJobTracker:
    global _distillation_jobs
    if _distillation_jobs is None:
        _distillation_jobs = DistillationJobTracker()
    return _distillation_jobs


def _iter_jsonl_records(paths: List[Path]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return records


def _latest_jsonl_files(directory: Path, limit: int = 5) -> List[Path]:
    return sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def _as_model_optimization_prompt(record: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    messages = record.get("messages") or []
    prompt = str(record.get("prompt") or record.get("instruction") or "")
    response = str(record.get("response") or record.get("output") or "")
    if messages and not prompt:
        prompt = str(next((m.get("content") for m in messages if m.get("role") == "user"), ""))
    if messages and not response:
        response = str(next((m.get("content") for m in messages if m.get("role") == "assistant"), ""))
    metadata = dict(record.get("metadata") or {})
    if record.get("quality_score") is not None and "quality_score" not in metadata:
        metadata["quality_score"] = record.get("quality_score")
    if record.get("category") is not None and "category" not in metadata:
        metadata["category"] = record.get("category")
    return prompt, response, metadata


# ---------------------------------------------------------------------------
# API Functions for MCP Handlers
# ---------------------------------------------------------------------------

async def capture_training_example(
    query: str,
    response: str,
    outcome: str = "unknown",
    user_feedback: Optional[int] = None,
    latency_ms: Optional[float] = None,
    metadata: Optional[Dict] = None,
) -> Dict:
    """
    Capture a training example from an interaction.
    Called from interaction_tracker after successful interactions.
    """
    capture = get_capture()
    example = capture.capture(
        query=query,
        response=response,
        outcome=outcome,
        user_feedback=user_feedback,
        latency_ms=latency_ms,
        metadata=metadata,
    )

    return {
        "captured": example is not None,
        "example_id": example["example_id"] if example else None,
        "quality": example["quality"] if example else None,
        "quality_score": example["quality_score"] if example else None,
    }


async def flush_training_data() -> Dict:
    """Flush pending training examples to disk."""
    capture = get_capture()
    output_path = capture.flush()
    stats = capture.get_stats()

    return {
        "output_path": output_path,
        "stats": stats,
    }


async def get_training_data_stats() -> Dict:
    """Get training data capture statistics."""
    capture = get_capture()
    stats = capture.get_stats()

    # Also list existing data files
    data_files = list(TRAINING_DATA_DIR.glob("*.jsonl"))
    total_size = sum(f.stat().st_size for f in data_files)
    synthetic_files = list(SYNTHETIC_DATA_DIR.glob("*.jsonl"))
    synthetic_size = sum(f.stat().st_size for f in synthetic_files)

    return {
        "capture_stats": stats,
        "files": len(data_files),
        "total_size_bytes": total_size,
        "data_dir": str(TRAINING_DATA_DIR),
        "synthetic_files": len(synthetic_files),
        "synthetic_size_bytes": synthetic_size,
        "synthetic_data_dir": str(SYNTHETIC_DATA_DIR),
    }


async def start_finetuning_job(
    base_model: str,
    task_type: str = "general",
    training_data_path: Optional[str] = None,
) -> Dict:
    """
    Start a fine-tuning job.

    Note: Actual training execution requires system deployment.
    This creates a job record for tracking.
    """
    status = get_finetuning_status()
    job_id = str(uuid4())

    # Use latest training data if not specified
    if not training_data_path:
        data_files = sorted(TRAINING_DATA_DIR.glob("*.jsonl"), reverse=True)
        if data_files:
            training_data_path = str(data_files[0])
        else:
            return {
                "error": "No training data available",
                "suggestion": "Call flush_training_data first to generate training data",
            }

    job = status.create_job(
        job_id=job_id,
        base_model=base_model,
        task_type=task_type,
        training_data_path=training_data_path,
    )

    logger.info(
        "Created fine-tuning job: id=%s, model=%s, task=%s",
        job_id, base_model, task_type
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Fine-tuning job created. Actual training requires system deployment.",
        "job": job,
    }


async def get_finetuning_jobs(status_filter: Optional[str] = None) -> Dict:
    """Get fine-tuning jobs."""
    status = get_finetuning_status()
    jobs = status.list_jobs(status=status_filter)

    return {
        "jobs": jobs,
        "count": len(jobs),
    }


async def record_model_performance(
    model_id: str,
    task_type: str,
    accuracy: float,
    latency_ms: float,
    quality_score: float,
) -> Dict:
    """Record model performance metrics."""
    tracker = get_performance_tracker()
    tracker.record(
        model_id=model_id,
        task_type=task_type,
        accuracy=accuracy,
        latency_ms=latency_ms,
        quality_score=quality_score,
    )

    trend = tracker.get_trend(model_id)
    return {
        "recorded": True,
        "model_id": model_id,
        "trend": trend,
    }


async def get_model_performance(model_id: Optional[str] = None) -> Dict:
    """Get model performance metrics and trends."""
    tracker = get_performance_tracker()

    if model_id:
        trend = tracker.get_trend(model_id)
        return {"model": trend}
    else:
        models = tracker.list_models()
        trends = {m: tracker.get_trend(m) for m in models}
        return {
            "models": models,
            "trends": trends,
        }


async def generate_synthetic_training_data(
    target_examples: int = 50,
    categories: Optional[List[str]] = None,
    strategies: Optional[List[str]] = None,
    min_quality: float = 0.7,
) -> Dict[str, Any]:
    """Generate synthetic training examples into writable runtime state."""
    from synthetic_data import (
        GenerationConfig,
        GenerationStrategy,
        SyntheticDataGenerator,
        TaskCategory,
    )

    selected_categories = []
    for category in categories or [TaskCategory.CODE_GENERATION.value, TaskCategory.DEBUGGING.value]:
        try:
            selected_categories.append(TaskCategory(category))
        except ValueError:
            logger.warning("Ignoring unknown synthetic-data category: %s", category)
    if not selected_categories:
        selected_categories = [TaskCategory.CODE_GENERATION, TaskCategory.DEBUGGING]

    selected_strategies = []
    for strategy in strategies or [GenerationStrategy.SEED_EXPANSION.value, GenerationStrategy.SELF_INSTRUCT.value]:
        try:
            selected_strategies.append(GenerationStrategy(strategy))
        except ValueError:
            logger.warning("Ignoring unknown synthetic-data strategy: %s", strategy)
    if not selected_strategies:
        selected_strategies = [GenerationStrategy.SEED_EXPANSION, GenerationStrategy.SELF_INSTRUCT]

    generator = SyntheticDataGenerator(output_dir=SYNTHETIC_DATA_DIR)
    config = GenerationConfig(
        target_examples=max(int(target_examples), 1),
        categories=selected_categories,
        strategies=selected_strategies,
        min_quality=float(min_quality),
    )
    generated = await generator.generate_batch(config)
    output_path = generator.save_examples(format="jsonl")
    stats = generator.get_stats()

    return {
        "generated_count": len(generated),
        "output_path": str(output_path) if output_path else "",
        "stats": stats,
        "categories": [category.value for category in selected_categories],
        "strategies": [strategy.value for strategy in selected_strategies],
    }


async def select_active_learning_examples(
    budget: int = 25,
    strategy: str = "hybrid",
    candidate_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Select the highest-value training examples from captured and synthetic corpora."""
    from active_learning import AcquisitionStrategy, ActiveLearner, CandidateExample

    try:
        selected_strategy = AcquisitionStrategy(strategy)
    except ValueError:
        selected_strategy = AcquisitionStrategy.HYBRID

    candidate_files = [Path(path) for path in (candidate_paths or []) if path]
    if not candidate_files:
        candidate_files = _latest_jsonl_files(TRAINING_DATA_DIR, limit=3) + _latest_jsonl_files(SYNTHETIC_DATA_DIR, limit=3)

    records = _iter_jsonl_records(candidate_files)
    candidates: List[CandidateExample] = []
    for index, record in enumerate(records):
        prompt, response, metadata = _as_model_optimization_prompt(record)
        if not prompt:
            continue
        candidate_id = str(record.get("id") or record.get("example_id") or f"candidate-{index}")
        candidates.append(
            CandidateExample(
                id=candidate_id,
                prompt=prompt,
                response=response or None,
                metadata=metadata,
            )
        )

    learner = ActiveLearner(strategy=selected_strategy, output_dir=ACTIVE_LEARNING_DIR)
    result = await learner.select(candidates, budget=max(int(budget), 1))
    state_path = learner.save_state()
    selected_examples = [
        {
            "id": candidate.id,
            "prompt_preview": candidate.prompt[:120],
            "quality_score": candidate.metadata.get("quality_score"),
            "category": candidate.metadata.get("category"),
        }
        for candidate in candidates
        if candidate.id in result.selected_ids
    ]

    return {
        "selected_ids": result.selected_ids,
        "selected_examples": selected_examples,
        "total_candidates": result.total_candidates,
        "selection_budget": result.selection_budget,
        "strategy": result.strategy.value,
        "avg_uncertainty": result.avg_uncertainty,
        "avg_diversity": result.avg_diversity,
        "coverage_estimate": result.coverage_estimate,
        "selection_time_ms": result.selection_time_ms,
        "state_path": str(state_path),
    }


async def run_distillation_pipeline(
    teacher_model: str,
    student_model: str,
    training_data_path: Optional[str] = None,
    quantization_method: str = "gguf",
    quantization_bits: int = 4,
    pruning_sparsity: float = 0.2,
    enable_speculative_decoding: bool = True,
) -> Dict[str, Any]:
    """Run a bounded distillation/compression pipeline and persist artifacts."""
    from distillation import (
        CompressionOptimizer,
        CompressionTarget,
        DistillationConfig,
        KnowledgeDistiller,
        ModelPruner,
        ModelQuantizer,
        PruningConfig,
        QuantizationConfig,
        QuantizationMethod,
        SpeculativeDecoder,
    )

    latest_training = _latest_jsonl_files(TRAINING_DATA_DIR, limit=1) + _latest_jsonl_files(SYNTHETIC_DATA_DIR, limit=1)
    selected_training_path = Path(training_data_path) if training_data_path else (latest_training[0] if latest_training else None)
    if selected_training_path is None:
        return {
            "error": "No training data available for distillation",
            "suggestion": "Capture/flush or generate synthetic training data first",
        }

    job_id = str(uuid4())
    job_dir = DISTILLATION_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    distiller = KnowledgeDistiller()
    config = DistillationConfig(
        teacher_model=teacher_model,
        student_model=student_model,
        dataset_size=10000,
    )
    distillation_result = await distiller.distill(
        config=config,
        training_data_path=selected_training_path,
        output_path=job_dir / "distillation.json",
    )

    quant_method = QuantizationMethod(str(quantization_method).lower())
    quantization_result = ModelQuantizer().quantize(
        Path(student_model),
        QuantizationConfig(method=quant_method, bits=max(int(quantization_bits), 4)),
        job_dir / "quantization.json",
    )

    pruning_result = None
    if pruning_sparsity and float(pruning_sparsity) > 0:
        pruning_result = ModelPruner().prune(
            model_path=Path(student_model),
            sparsity=float(pruning_sparsity),
            output_path=job_dir / "pruning.json",
            config=PruningConfig(sparsity=float(pruning_sparsity)),
        )

    speculative = None
    if enable_speculative_decoding:
        speculative = SpeculativeDecoder().setup_speculative_pair(
            draft_model_path=Path(student_model),
            target_model_path=Path(teacher_model),
        )

    recommended = CompressionOptimizer().find_optimal_compression(
        model_path=Path(student_model),
        target=CompressionTarget.BALANCED,
        max_accuracy_drop=0.08,
    )

    job_payload = {
        "job_id": job_id,
        "teacher_model": teacher_model,
        "student_model": student_model,
        "training_data_path": str(selected_training_path),
        "created_at": datetime.now().isoformat(),
        "status": "ready_for_deploy",
        "distillation": {
            "artifact": str(distillation_result.output_path),
            "compression_ratio": distillation_result.compression_ratio,
            "accuracy_drop": distillation_result.accuracy_drop,
            "latency_improvement": distillation_result.latency_improvement,
        },
        "quantization": {
            "artifact": str(quantization_result.output_path),
            "method": quantization_result.method,
            "compression_ratio": quantization_result.compression_ratio,
            "accuracy_drop": quantization_result.accuracy_drop,
        },
        "pruning": (
            {
                "artifact": str(pruning_result.output_path),
                "method": pruning_result.method,
                "compression_ratio": pruning_result.compression_ratio,
                "accuracy_drop": pruning_result.accuracy_drop,
            }
            if pruning_result
            else None
        ),
        "speculative_decoding": speculative,
        "recommended_profile": (
            {
                "method": recommended.method,
                "compression_ratio": recommended.compression_ratio,
                "accuracy_drop": recommended.accuracy_drop,
                "latency_improvement": recommended.latency_improvement,
                "artifact": str(recommended.output_path),
            }
            if recommended
            else None
        ),
        "job_dir": str(job_dir),
    }
    get_distillation_jobs().record_job(job_id, job_payload)

    return job_payload


async def get_optimization_readiness() -> Dict:
    """
    Get readiness status for Phase 5 model optimization.
    Reports what's operational vs pending integration.
    """
    capture = get_capture()
    capture_stats = capture.get_stats()

    # Check training data availability
    data_files = list(TRAINING_DATA_DIR.glob("*.jsonl"))
    total_examples = 0
    for f in data_files:
        with open(f) as fp:
            total_examples += sum(1 for _ in fp)

    # Check fine-tuning jobs
    status = get_finetuning_status()
    jobs = status.list_jobs()
    distillation_jobs = get_distillation_jobs().list_jobs()
    synthetic_files = list(SYNTHETIC_DATA_DIR.glob("*.jsonl"))
    active_learning_state = ACTIVE_LEARNING_DIR / "learner_state.json"

    return {
        "readiness": {
            "data_capture": {
                "status": "operational",
                "captured_count": capture_stats["captured"],
                "total_examples": total_examples,
            },
            "quality_assessment": {
                "status": "operational",
                "description": "PII detection, quality scoring active",
            },
            "synthetic_generation": {
                "status": "operational",
                "description": "Synthetic data generator integrated via coordinator control plane",
                "generated_files": len(synthetic_files),
            },
            "active_learning": {
                "status": "operational",
                "description": "Active learner integrated via coordinator control plane",
                "state_available": active_learning_state.exists(),
            },
            "finetuning_pipeline": {
                "status": "infrastructure_ready",
                "description": "Job tracking ready, actual training pending deployment",
                "pending_jobs": len([j for j in jobs if j["status"] == "pending"]),
            },
            "distillation": {
                "status": "runtime_integrated",
                "description": "Distillation pipeline integrated via coordinator control plane",
                "jobs": len(distillation_jobs),
                "integration": "ready_for_artifact_generation",
            },
            "model_compression": {
                "status": "runtime_integrated",
                "description": "Quantization, pruning, and speculative decoding integrated via coordinator control plane",
                "integration": "pending_deployment",
            },
        },
        "next_steps": [
            "Continue capturing high-quality interactions",
            "Generate synthetic and actively selected examples for targeted domains",
            "Flush training data periodically",
            "Create fine-tuning jobs for deployment",
            "Produce distillation/compression artifacts before deployment",
            "Track model performance after deployment",
        ],
    }
