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
    for dir_path in [TRAINING_DATA_DIR, MODEL_VARIANTS_DIR, METRICS_DIR]:
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

    return {
        "capture_stats": stats,
        "files": len(data_files),
        "total_size_bytes": total_size,
        "data_dir": str(TRAINING_DATA_DIR),
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
            "finetuning_pipeline": {
                "status": "infrastructure_ready",
                "description": "Job tracking ready, actual training pending deployment",
                "pending_jobs": len([j for j in jobs if j["status"] == "pending"]),
            },
            "distillation": {
                "status": "implementation_exists",
                "description": "ai-stack/model-optimization/distillation.py available",
                "integration": "pending",
            },
            "model_compression": {
                "status": "implementation_exists",
                "description": "GPTQ, AWQ, GGUF quantization available",
                "integration": "pending_deployment",
            },
        },
        "next_steps": [
            "Continue capturing high-quality interactions",
            "Flush training data periodically",
            "Create fine-tuning jobs for deployment",
            "Track model performance after deployment",
        ],
    }
