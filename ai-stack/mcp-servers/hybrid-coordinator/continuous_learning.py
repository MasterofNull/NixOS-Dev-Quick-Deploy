#!/usr/bin/env python3
"""
Continuous Learning Pipeline
Extracts patterns from interactions and generates fine-tuning datasets

Features:
- Pattern extraction from telemetry
- Fine-tuning dataset generation (JSONL)
- Model performance tracking
- A/B testing support
- Success pattern identification
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class InteractionPattern(BaseModel):
    """Extracted interaction pattern"""
    pattern_id: str
    interaction_type: str  # task_completion, error_resolution, code_review
    prompt: str
    response: str
    context: Dict[str, Any]
    success_metrics: Dict[str, float]
    iterations: int
    timestamp: datetime
    backend: str = "unknown"


class FinetuningExample(BaseModel):
    """Fine-tuning dataset example"""
    messages: List[Dict[str, str]]
    metadata: Dict[str, Any]


class PerformanceMetric(BaseModel):
    """Model performance metrics"""
    metric_name: str
    value: float
    timestamp: datetime
    model_version: str = "base"


class ContinuousLearningPipeline:
    """
    Learns from user interactions to improve system performance

    Usage:
        pipeline = ContinuousLearningPipeline(settings, qdrant, postgres)
        await pipeline.start()  # Begin processing telemetry

        # Manual processing
        patterns = await pipeline.process_telemetry_batch()
        dataset = await pipeline.generate_finetuning_dataset()
    """

    def __init__(self, settings, qdrant_client, postgres_client):
        self.settings = settings
        self.qdrant = qdrant_client
        self.postgres = postgres_client

        # Telemetry paths
        self.telemetry_paths = [
            Path("/data/telemetry/ralph-events.jsonl"),
            Path("/data/telemetry/aidb-events.jsonl"),
            Path("/data/telemetry/hybrid-events.jsonl"),
        ]

        # Fine-tuning dataset path
        self.dataset_path = Path("/data/fine-tuning/dataset.jsonl")
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)

        # Pattern catalog
        self.patterns: List[InteractionPattern] = []

        # Performance history
        self.metrics: List[PerformanceMetric] = []

        # Processing task
        self.learning_task: Optional[asyncio.Task] = None

        # Last processed position for each telemetry file
        self.last_positions: Dict[str, int] = {}

    async def start(self):
        """Start continuous learning pipeline"""
        logger.info("continuous_learning_starting")
        self.learning_task = asyncio.create_task(self._learning_loop())

    async def stop(self):
        """Stop learning pipeline"""
        if self.learning_task:
            self.learning_task.cancel()
            try:
                await self.learning_task
            except asyncio.CancelledError:
                pass
        logger.info("continuous_learning_stopped")

    async def _learning_loop(self):
        """Background learning loop"""
        while True:
            try:
                # Process new telemetry
                patterns = await self.process_telemetry_batch()

                if patterns:
                    # Generate fine-tuning examples
                    examples = await self.generate_finetuning_examples(patterns)

                    # Save to dataset
                    await self._save_finetuning_examples(examples)

                    # Update pattern catalog in Qdrant
                    await self._index_patterns(patterns)

                # Sleep for 1 hour between processing
                await asyncio.sleep(3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("learning_loop_error", error=str(e))
                await asyncio.sleep(300)  # Retry after 5 min on error

    async def process_telemetry_batch(self) -> List[InteractionPattern]:
        """Process new telemetry events and extract patterns"""
        all_patterns: List[InteractionPattern] = []

        for telemetry_path in self.telemetry_paths:
            if not telemetry_path.exists():
                continue

            try:
                patterns = await self._process_telemetry_file(telemetry_path)
                all_patterns.extend(patterns)

                logger.info(
                    "telemetry_processed",
                    file=telemetry_path.name,
                    patterns=len(patterns)
                )

            except Exception as e:
                logger.error(
                    "telemetry_processing_failed",
                    file=telemetry_path.name,
                    error=str(e)
                )

        # Filter for high-quality patterns
        quality_patterns = await self._filter_quality_patterns(all_patterns)

        logger.info(
            "batch_processing_complete",
            total_patterns=len(all_patterns),
            quality_patterns=len(quality_patterns)
        )

        return quality_patterns

    async def _process_telemetry_file(
        self, telemetry_path: Path
    ) -> List[InteractionPattern]:
        """Process a specific telemetry file"""
        patterns: List[InteractionPattern] = []

        # Get last processed position
        last_pos = self.last_positions.get(str(telemetry_path), 0)

        with open(telemetry_path, "r") as f:
            # Skip to last position
            f.seek(last_pos)

            for line in f:
                try:
                    event = json.loads(line)

                    # Extract pattern from event
                    pattern = await self._extract_pattern_from_event(event)

                    if pattern:
                        patterns.append(pattern)

                except json.JSONDecodeError:
                    continue

            # Update last position
            self.last_positions[str(telemetry_path)] = f.tell()

        return patterns

    async def _extract_pattern_from_event(
        self, event: Dict[str, Any]
    ) -> Optional[InteractionPattern]:
        """Extract learning pattern from telemetry event"""
        event_type = event.get("event")

        if event_type == "task_completed":
            # Successful task completion
            task = event.get("task", {})
            iterations = task.get("iteration", 0)

            # Only learn from successful, efficient completions
            if iterations <= 5:  # Completed in few iterations
                return InteractionPattern(
                    pattern_id=f"task_{task.get('task_id', 'unknown')}",
                    interaction_type="task_completion",
                    prompt=task.get("prompt", ""),
                    response=task.get("output", ""),
                    context=task.get("context", {}),
                    success_metrics={
                        "iterations": float(iterations),
                        "efficiency": 1.0 / max(iterations, 1),
                    },
                    iterations=iterations,
                    timestamp=datetime.fromisoformat(
                        event.get("timestamp", datetime.now(timezone.utc).isoformat())
                    ),
                    backend=task.get("backend", "unknown"),
                )

        elif event_type == "error_resolution":
            # Successful error fix
            return InteractionPattern(
                pattern_id=f"error_{event.get('error_id', 'unknown')}",
                interaction_type="error_resolution",
                prompt=event.get("error_description", ""),
                response=event.get("solution", ""),
                context=event.get("context", {}),
                success_metrics={"resolution_time": event.get("resolution_time", 0.0)},
                iterations=1,
                timestamp=datetime.fromisoformat(
                    event.get("timestamp", datetime.now(timezone.utc).isoformat())
                ),
            )

        return None

    async def _filter_quality_patterns(
        self, patterns: List[InteractionPattern]
    ) -> List[InteractionPattern]:
        """Filter patterns to keep only high-quality examples"""
        quality_patterns = []

        for pattern in patterns:
            # Quality criteria
            if (
                len(pattern.prompt) > 20  # Meaningful prompt
                and len(pattern.response) > 10  # Meaningful response
                and pattern.iterations <= 5  # Efficient solution
                and pattern.prompt != pattern.response  # Not identical
            ):
                quality_patterns.append(pattern)

        return quality_patterns

    async def generate_finetuning_examples(
        self, patterns: List[InteractionPattern]
    ) -> List[FinetuningExample]:
        """Generate fine-tuning examples from patterns"""
        examples: List[FinetuningExample] = []

        for pattern in patterns:
            # Create conversation format
            if pattern.interaction_type == "task_completion":
                messages = [
                    {
                        "role": "system",
                        "content": "You are a helpful AI coding assistant. "
                        "Provide clear, efficient solutions."
                    },
                    {"role": "user", "content": pattern.prompt},
                    {"role": "assistant", "content": pattern.response},
                ]

            elif pattern.interaction_type == "error_resolution":
                messages = [
                    {
                        "role": "system",
                        "content": "You are an expert at debugging and fixing errors. "
                        "Provide clear explanations and solutions."
                    },
                    {
                        "role": "user",
                        "content": f"Error: {pattern.prompt}\nHow do I fix this?"
                    },
                    {"role": "assistant", "content": pattern.response},
                ]

            else:
                # Generic format
                messages = [
                    {"role": "user", "content": pattern.prompt},
                    {"role": "assistant", "content": pattern.response},
                ]

            example = FinetuningExample(
                messages=messages,
                metadata={
                    "pattern_id": pattern.pattern_id,
                    "interaction_type": pattern.interaction_type,
                    "backend": pattern.backend,
                    "iterations": pattern.iterations,
                    "timestamp": pattern.timestamp.isoformat(),
                    "success_metrics": pattern.success_metrics,
                },
            )

            examples.append(example)

        return examples

    async def _save_finetuning_examples(
        self, examples: List[FinetuningExample]
    ):
        """Append examples to fine-tuning dataset"""
        if not examples:
            return

        try:
            with open(self.dataset_path, "a") as f:
                for example in examples:
                    # Convert to JSONL format
                    json_line = json.dumps(example.dict())
                    f.write(json_line + "\n")

            logger.info(
                "finetuning_examples_saved",
                count=len(examples),
                path=str(self.dataset_path)
            )

        except Exception as e:
            logger.error("dataset_save_failed", error=str(e))

    async def _index_patterns(self, patterns: List[InteractionPattern]):
        """Index patterns in Qdrant for retrieval"""
        if not patterns:
            return

        try:
            from qdrant_client.models import PointStruct

            points = []

            for pattern in patterns:
                # Create searchable text
                searchable = f"{pattern.prompt} {pattern.response}"

                # Generate embedding (placeholder - would use llama.cpp)
                embedding = [0.0] * 384  # TODO: Use real embeddings

                point = PointStruct(
                    id=hash(pattern.pattern_id) % (10 ** 8),
                    vector=embedding,
                    payload={
                        "pattern_id": pattern.pattern_id,
                        "interaction_type": pattern.interaction_type,
                        "prompt": pattern.prompt[:500],  # Truncate
                        "response": pattern.response[:500],
                        "backend": pattern.backend,
                        "iterations": pattern.iterations,
                        "timestamp": pattern.timestamp.isoformat(),
                    },
                )

                points.append(point)

            # Upsert to Qdrant
            if points:
                await self.qdrant.upsert(
                    collection_name="skills-patterns",
                    points=points,
                    wait=True,
                )

                logger.info("patterns_indexed", count=len(points))

        except Exception as e:
            logger.error("pattern_indexing_failed", error=str(e))

    async def track_performance_metric(
        self,
        metric_name: str,
        value: float,
        model_version: str = "base"
    ):
        """Track a performance metric"""
        metric = PerformanceMetric(
            metric_name=metric_name,
            value=value,
            timestamp=datetime.now(timezone.utc),
            model_version=model_version,
        )

        self.metrics.append(metric)

        # Save to database if available
        if self.postgres:
            try:
                await self.postgres.execute(
                    """
                    INSERT INTO performance_metrics
                    (metric_name, value, model_version, timestamp)
                    VALUES ($1, $2, $3, $4)
                    """,
                    metric_name,
                    value,
                    model_version,
                    metric.timestamp,
                )
            except Exception as e:
                logger.debug("metric_save_failed", error=str(e))

    async def get_statistics(self) -> Dict[str, Any]:
        """Get learning pipeline statistics"""
        # Count patterns by type
        by_type: Dict[str, int] = {}
        for pattern in self.patterns:
            by_type[pattern.interaction_type] = (
                by_type.get(pattern.interaction_type, 0) + 1
            )

        # Check dataset size
        dataset_size = 0
        if self.dataset_path.exists():
            with open(self.dataset_path, "r") as f:
                dataset_size = sum(1 for _ in f)

        # Recent metrics
        recent_metrics = [
            {
                "name": m.metric_name,
                "value": m.value,
                "model": m.model_version,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in self.metrics[-10:]
        ]

        return {
            "total_patterns_learned": len(self.patterns),
            "patterns_by_type": by_type,
            "finetuning_dataset_size": dataset_size,
            "total_metrics_tracked": len(self.metrics),
            "recent_metrics": recent_metrics,
        }

    async def should_trigger_finetuning(self) -> bool:
        """Determine if we should trigger a fine-tuning run"""
        # Check if dataset is large enough
        dataset_size = 0
        if self.dataset_path.exists():
            with open(self.dataset_path, "r") as f:
                dataset_size = sum(1 for _ in f)

        # Trigger if we have at least 1000 quality examples
        return dataset_size >= 1000

    async def export_dataset_for_training(
        self, output_path: Optional[Path] = None
    ) -> Path:
        """Export dataset in OpenAI fine-tuning format"""
        if output_path is None:
            output_path = Path("/data/fine-tuning/dataset_export.jsonl")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy and validate dataset
        valid_count = 0

        with open(self.dataset_path, "r") as infile:
            with open(output_path, "w") as outfile:
                for line in infile:
                    try:
                        example = json.loads(line)

                        # Validate format
                        if "messages" in example and len(example["messages"]) >= 2:
                            outfile.write(line)
                            valid_count += 1
                    except json.JSONDecodeError:
                        continue

        logger.info(
            "dataset_exported",
            valid_examples=valid_count,
            output=str(output_path)
        )

        return output_path
