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
- Checkpointing for crash recovery (P2-REL-001)
- Circuit breakers for external dependencies (P2-REL-002)
"""

import asyncio
import hashlib  # P6-OPS-002: For pattern deduplication
import json
import os
import sys
import re
from collections import Counter
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta, timezone
from pathlib import Path
import structlog
from pydantic import BaseModel

# P2-REL-002: Import circuit breaker for preventing cascade failures
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from shared.circuit_breaker import CircuitBreakerRegistry
from shared.auth_http_client import create_embeddings_client

logger = structlog.get_logger()


def _read_secret(path: str) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


class Checkpointer:
    """
    P2-REL-001: Checkpoint manager for crash recovery
    Saves pipeline state periodically to prevent data loss
    Uses JSON (not pickle) so checkpoints survive nixos-rebuild Python version changes.
    """
    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: dict):
        """Save checkpoint atomically to prevent corruption"""
        temp_path = self.checkpoint_dir / "checkpoint.tmp"
        final_path = self.checkpoint_dir / "checkpoint.json"

        try:
            # Write to temp file first (atomic write pattern)
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump({**state, "schema_version": 1}, f, default=str)

            # Atomic rename (prevents partial writes)
            temp_path.rename(final_path)

            logger.info("checkpoint_saved", state_keys=list(state.keys()))

        except Exception as e:
            logger.error("checkpoint_save_failed", error=str(e))
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()

    def load(self) -> dict:
        """Load last checkpoint if exists"""
        # Migration: legacy pickle checkpoint — cannot safely load without running
        # pickle.load on an untrusted/version-mismatched file; discard and delete.
        legacy_path = self.checkpoint_dir / "checkpoint.pkl"
        if legacy_path.exists():
            logger.warning("legacy_checkpoint_found",
                           path=str(legacy_path),
                           message="Discarding legacy pickle checkpoint; starting fresh")
            try:
                legacy_path.unlink()
            except Exception as e:
                logger.error("legacy_checkpoint_delete_failed", error=str(e))
            return {}

        checkpoint_path = self.checkpoint_dir / "checkpoint.json"

        if not checkpoint_path.exists():
            logger.info("no_checkpoint_found", message="Starting fresh")
            return {}

        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            # If schema_version is missing this is an unknown legacy format; discard.
            if "schema_version" not in state:
                logger.warning("checkpoint_missing_schema_version",
                               message="Treating as legacy; starting fresh")
                return {}

            logger.info("checkpoint_loaded", state_keys=list(state.keys()))
            return state

        except Exception as e:
            logger.error("checkpoint_load_failed", error=str(e))
            return {}

    def clear(self):
        """Clear checkpoint (useful for testing or reset)"""
        checkpoint_path = self.checkpoint_dir / "checkpoint.json"
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            logger.info("checkpoint_cleared")


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


class OptimizationProposal(BaseModel):
    """Learning-based optimization proposal"""
    proposal_id: str
    proposal_type: str
    title: str
    rationale: str
    recommended_action: str
    evidence: Dict[str, Any]
    status: str = "pending"
    approval_required: bool = True
    created_at: datetime
    submitted_as_task: bool = False


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
        self.embedding_service_url = getattr(settings, "embedding_service_url", None) or os.getenv(
            "EMBEDDING_SERVICE_URL", "http://embeddings:8081"
        )
        self.embedding_dimensions = getattr(settings, "embedding_dimensions", 384)
        self.embeddings_client = create_embeddings_client(timeout=30.0)

        # Base writable data root for continuous-learning artifacts.
        data_root = Path(
            os.path.expanduser(
                os.getenv("CONTINUOUS_LEARNING_DATA_ROOT")
                or os.getenv("DATA_DIR")
                or "~/.local/share/nixos-ai-stack/hybrid"
            )
        )
        telemetry_dir = Path(
            os.getenv("CONTINUOUS_LEARNING_TELEMETRY_DIR", str(data_root / "telemetry"))
        )

        # Telemetry paths
        self.telemetry_paths = [
            telemetry_dir / "ralph-events.jsonl",
            telemetry_dir / "aidb-events.jsonl",
            telemetry_dir / "hybrid-events.jsonl",
        ]

        # Fine-tuning dataset path
        dataset_default = (
            os.getenv("FINETUNE_DATA_PATH")
            or getattr(settings, "finetune_data_path", None)
            or str(data_root / "fine-tuning" / "dataset.jsonl")
        )
        self.dataset_path = Path(os.path.expanduser(dataset_default))
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)

        # Continuous learning stats snapshot path
        self.stats_path = Path(os.getenv("CONTINUOUS_LEARNING_STATS_PATH", str(telemetry_dir / "continuous_learning_stats.json")))
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)

        # Optimization proposal log path
        self.proposals_path = Path(os.getenv("OPTIMIZATION_PROPOSALS_PATH", str(telemetry_dir / "optimization_proposals.jsonl")))
        self.proposals_path.parent.mkdir(parents=True, exist_ok=True)

        # Pattern catalog
        self.patterns: List[InteractionPattern] = []

        # Performance history
        self.metrics: List[PerformanceMetric] = []

        # Optimization proposals
        self.proposals: List[OptimizationProposal] = []
        self.proposal_hashes: Set[str] = set()
        self._load_proposal_hashes()

        # Proposal configuration
        self.proposals_enabled = os.getenv("OPTIMIZATION_PROPOSALS_ENABLED", "true").lower() == "true"
        self.proposal_submission_enabled = (
            os.getenv("OPTIMIZATION_PROPOSAL_SUBMISSION_ENABLED", "true").lower() == "true"
        )
        self.proposal_batch_limit = int(os.getenv("OPTIMIZATION_PROPOSAL_BATCH_LIMIT", "5"))
        self.ralph_url = os.getenv("RALPH_WIGGUM_URL", "http://localhost:8004")
        self.ralph_api_key = _read_secret(os.getenv("RALPH_WIGGUM_API_KEY_FILE", "/run/secrets/ralph_wiggum_api_key"))

        # Batch insights (reset each telemetry batch)
        self._reset_batch_insights()

        # Processing task
        self.learning_task: Optional[asyncio.Task] = None

        # P2-REL-001: Initialize checkpointer for crash recovery
        checkpoints_dir = Path(
            os.getenv("CONTINUOUS_LEARNING_CHECKPOINT_DIR", str(data_root / "checkpoints"))
        )
        self.checkpointer = Checkpointer(checkpoints_dir)
        self.checkpoint_interval = 100  # Checkpoint every N events
        self.processed_count = 0

        # Load last checkpoint to resume from where we left off
        checkpoint = self.checkpointer.load()
        self.last_positions: Dict[str, int] = checkpoint.get("last_positions", {})
        self.processed_count = checkpoint.get("processed_count", 0)

        if checkpoint:
            logger.info(
                "resuming_from_checkpoint",
                processed_count=self.processed_count,
                files=len(self.last_positions)
            )

        # P2-REL-002: Initialize circuit breakers for external dependencies
        self.circuit_breakers = CircuitBreakerRegistry(default_config={
            'failure_threshold': 5,  # Open after 5 failures
            'timeout': 30.0,  # Retry after 30 seconds
            'success_threshold': 2  # Need 2 successes to close
        })
        logger.info("circuit_breakers_initialized", services=["qdrant", "postgresql"])

        # P2-REL-004: Initialize backpressure monitoring
        self.backpressure_threshold_mb = 100  # Pause if unprocessed telemetry > 100MB
        self.backpressure_paused = False
        logger.info("backpressure_monitoring_initialized", threshold_mb=self.backpressure_threshold_mb)

        # P6-OPS-002: Initialize pattern deduplication
        self.pattern_hashes: Set[str] = set()  # Tracks seen patterns
        self.dedup_stats = {
            'total_patterns': 0,
            'duplicates_found': 0,
            'unique_patterns': 0
        }
        logger.info("deduplication_initialized")

    def _reset_batch_insights(self) -> None:
        """Reset telemetry analysis for the current batch."""
        self.batch_insights = {
            "high_iteration_tasks": [],
            "limit_hits": [],
            "failure_signals": Counter(),
            "timeout_signals": 0,
            "dependency_signals": Counter(),
            "success_characteristics": Counter(),
        }

    def _load_proposal_hashes(self) -> None:
        """Load existing proposals to avoid duplicates across restarts."""
        if not self.proposals_path.exists():
            return

        try:
            with open(self.proposals_path, "r") as handle:
                for line in handle:
                    try:
                        payload = json.loads(line)
                        proposal_hash = payload.get("proposal_hash")
                        if proposal_hash:
                            self.proposal_hashes.add(proposal_hash)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning("proposal_hash_load_failed", error=str(e))

    def _record_proposal(self, proposal: OptimizationProposal, proposal_hash: str) -> None:
        """Persist proposal to telemetry log."""
        try:
            payload = proposal.model_dump()
            payload["proposal_hash"] = proposal_hash
            with open(self.proposals_path, "a") as handle:
                handle.write(json.dumps(payload) + "\n")
            self.proposal_hashes.add(proposal_hash)
        except Exception as e:
            logger.error("proposal_record_failed", error=str(e))

    def _extract_task_type(self, prompt: str) -> str:
        """Extract coarse task type from prompt text."""
        prompt_lower = prompt.lower()
        if any(k in prompt_lower for k in ["deploy", "installation", "install"]):
            return "deployment"
        if any(k in prompt_lower for k in ["test", "validation", "verify", "health check"]):
            return "testing"
        if any(k in prompt_lower for k in ["debug", "error", "failed", "fix"]):
            return "debugging"
        if any(k in prompt_lower for k in ["config", "configuration", "nixos", "yaml"]):
            return "configuration"
        if any(k in prompt_lower for k in ["doc", "documentation", "readme"]):
            return "documentation"
        return "general"

    def _extract_dependency_name(self, error_text: str) -> Optional[str]:
        """Best-effort extraction of dependency name from error text."""
        patterns = [
            r"host ['\"]?([a-z0-9\\-]+)['\"]?",
            r"service \"([a-z0-9\\-]+)\"",
            r"http://([a-z0-9\\-]+):",
        ]
        for pattern in patterns:
            match = re.search(pattern, error_text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _update_batch_insights(self, event: Dict[str, Any]) -> None:
        """Update analysis counters for the current batch."""
        event_type = event.get("event")
        if event_type != "task_completed":
            return

        task = event.get("task", {})
        prompt = task.get("prompt", "")
        total_iterations = int(event.get("total_iterations", 0))
        adaptive_limit = int(event.get("adaptive_limit_used", 0))
        backend = task.get("backend", "unknown")
        status = event.get("status", "unknown")
        context = task.get("context", {}) if isinstance(task.get("context"), dict) else {}
        last_error = context.get("last_error") or context.get("last_exception")

        if total_iterations >= 10:
            self.batch_insights["high_iteration_tasks"].append({
                "task_id": event.get("task_id"),
                "prompt_preview": prompt[:200],
                "iterations": total_iterations,
                "adaptive_limit": adaptive_limit,
                "backend": backend,
                "task_type": self._extract_task_type(prompt),
            })

        if adaptive_limit > 0 and total_iterations >= adaptive_limit:
            self.batch_insights["limit_hits"].append({
                "task_id": event.get("task_id"),
                "prompt_preview": prompt[:200],
                "iterations": total_iterations,
                "adaptive_limit": adaptive_limit,
                "backend": backend,
                "task_type": self._extract_task_type(prompt),
            })

        if status == "completed" and total_iterations <= 3:
            self.batch_insights["success_characteristics"].update([
                self._extract_task_type(prompt),
                f"backend:{backend}",
                f"prompt_len:{min(len(prompt) // 50, 10)}"
            ])

        if isinstance(last_error, str) and last_error:
            error_lower = last_error.lower()
            if "timeout" in error_lower:
                self.batch_insights["timeout_signals"] += 1
            if any(token in error_lower for token in ["connection refused", "name or service not known", "failed to resolve host"]):
                dependency = self._extract_dependency_name(last_error) or "unknown"
                self.batch_insights["dependency_signals"][dependency] += 1
            for token in ["permission denied", "not found", "invalid"]:
                if token in error_lower:
                    self.batch_insights["failure_signals"][token] += 1

    def _proposal_hash(self, proposal: OptimizationProposal) -> str:
        """Stable hash for proposal deduplication."""
        content = f"{proposal.proposal_type}:{proposal.title}:{proposal.recommended_action}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _build_iteration_limit_proposals(self) -> List[OptimizationProposal]:
        proposals = []
        for item in self.batch_insights["limit_hits"]:
            title = f"Increase iteration limit for {item['task_type']} tasks"
            rationale = (
                f"Task hit iteration cap ({item['adaptive_limit']}) "
                f"after {item['iterations']} iterations."
            )
            recommended_action = (
                f"Increase {item['task_type']} iteration limit by 25% "
                f"(current cap {item['adaptive_limit']})."
            )
            proposal = OptimizationProposal(
                proposal_id=f"proposal-{item['task_id']}",
                proposal_type="iteration_limit_increase",
                title=title,
                rationale=rationale,
                recommended_action=recommended_action,
                evidence=item,
                created_at=datetime.now(timezone.utc),
            )
            proposals.append(proposal)
        return proposals

    def _build_dependency_check_proposals(self) -> List[OptimizationProposal]:
        proposals = []
        for dependency, count in self.batch_insights["dependency_signals"].most_common():
            title = f"Add dependency pre-flight check for {dependency}"
            rationale = f"Detected {count} connection errors referencing {dependency}."
            recommended_action = (
                f"Add startup dependency check for {dependency} "
                f"in the relevant service(s) before execution."
            )
            proposal = OptimizationProposal(
                proposal_id=f"proposal-dependency-{dependency}",
                proposal_type="dependency_check_addition",
                title=title,
                rationale=rationale,
                recommended_action=recommended_action,
                evidence={"dependency": dependency, "count": count},
                created_at=datetime.now(timezone.utc),
            )
            proposals.append(proposal)
        return proposals

    def _build_timeout_adjustment_proposals(self) -> List[OptimizationProposal]:
        proposals = []
        if self.batch_insights["timeout_signals"] == 0:
            return proposals
        title = "Increase timeout budget for long-running tasks"
        rationale = f"Observed {self.batch_insights['timeout_signals']} timeout-related failures."
        recommended_action = "Increase task timeout budget by 20% for long-running tasks."
        proposal = OptimizationProposal(
            proposal_id="proposal-timeout-adjustment",
            proposal_type="timeout_adjustment",
            title=title,
            rationale=rationale,
            recommended_action=recommended_action,
            evidence={"timeout_signals": self.batch_insights["timeout_signals"]},
            created_at=datetime.now(timezone.utc),
        )
        proposals.append(proposal)
        return proposals

    def generate_optimization_proposals(self) -> List[OptimizationProposal]:
        """Generate optimization proposals from batch insights."""
        if not self.proposals_enabled:
            return []

        proposals = []
        proposals.extend(self._build_iteration_limit_proposals())
        proposals.extend(self._build_dependency_check_proposals())
        proposals.extend(self._build_timeout_adjustment_proposals())

        # Deduplicate and limit batch size
        unique: List[OptimizationProposal] = []
        for proposal in proposals:
            proposal_hash = self._proposal_hash(proposal)
            if proposal_hash in self.proposal_hashes:
                continue
            self._record_proposal(proposal, proposal_hash)
            unique.append(proposal)
            if len(unique) >= self.proposal_batch_limit:
                break

        return unique

    async def _submit_proposals(self, proposals: List[OptimizationProposal]) -> None:
        """Submit proposals as Ralph tasks (requires approval)."""
        if not proposals or not self.proposal_submission_enabled:
            return

        try:
            import httpx
        except Exception as e:
            logger.warning("proposal_submission_disabled", error=str(e))
            return

        headers = {}
        if self.ralph_api_key:
            headers["x-api-key"] = self.ralph_api_key

        async with httpx.AsyncClient(timeout=10) as client:
            for proposal in proposals:
                prompt = (
                    "Optimization Proposal (requires approval)\n"
                    f"Type: {proposal.proposal_type}\n"
                    f"Title: {proposal.title}\n"
                    f"Rationale: {proposal.rationale}\n"
                    f"Recommended Action: {proposal.recommended_action}\n"
                    "If approved, apply the change and report back."
                )
                payload = {
                    "prompt": prompt,
                    "require_approval": True,
                    "max_iterations": 1,
                    "context": {
                        "proposal_id": proposal.proposal_id,
                        "proposal_type": proposal.proposal_type,
                        "evidence": proposal.evidence,
                    },
                }
                try:
                    response = await client.post(
                        f"{self.ralph_url}/tasks",
                        json=payload,
                        headers=headers
                    )
                    response.raise_for_status()
                    proposal.submitted_as_task = True
                except Exception as e:
                    logger.warning(
                        "proposal_submission_failed",
                        proposal_id=proposal.proposal_id,
                        error=str(e)
                    )

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
        try:
            await self.embeddings_client.aclose()
        except Exception:
            pass
        logger.info("continuous_learning_stopped")

    async def _learning_loop(self):
        """Background learning loop with backpressure monitoring"""
        while True:
            try:
                # P2-REL-004: Check backpressure before processing
                backpressure_status = self._check_backpressure()

                if backpressure_status['paused']:
                    if not self.backpressure_paused:
                        logger.warning(
                            "learning_paused_backpressure",
                            unprocessed_mb=backpressure_status['unprocessed_mb'],
                            threshold_mb=self.backpressure_threshold_mb
                        )
                        self.backpressure_paused = True

                    # Wait before checking again
                    await asyncio.sleep(300)  # Check every 5 minutes
                    continue

                elif self.backpressure_paused:
                    logger.info(
                        "learning_resumed",
                        unprocessed_mb=backpressure_status['unprocessed_mb']
                    )
                    self.backpressure_paused = False

                # Process new telemetry
                patterns = await self.process_telemetry_batch()

                if patterns:
                    self.patterns.extend(patterns)

                    # Generate fine-tuning examples
                    examples = await self.generate_finetuning_examples(patterns)

                    # Save to dataset
                    await self._save_finetuning_examples(examples)

                    # Update pattern catalog in Qdrant
                    await self._index_patterns(patterns)

                proposals = self.generate_optimization_proposals()
                if proposals:
                    self.proposals.extend(proposals)
                    await self._submit_proposals(proposals)

                await self._write_stats_snapshot()

                # Sleep for 1 hour between processing
                await asyncio.sleep(3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("learning_loop_error", error=str(e))
                await asyncio.sleep(300)  # Retry after 5 min on error

    async def process_telemetry_batch(self) -> List[InteractionPattern]:
        """Process new telemetry events and extract patterns"""
        self._reset_batch_insights()
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
        """Process a specific telemetry file with checkpointing (P2-REL-001)"""
        patterns: List[InteractionPattern] = []

        # Get last processed position from checkpoint
        last_pos = self.last_positions.get(str(telemetry_path), 0)

        events_since_checkpoint = 0

        with open(telemetry_path, "r") as f:
            # Skip to last position (resume from checkpoint)
            f.seek(last_pos)

            for line in f:
                try:
                    event = json.loads(line)

                    self._update_batch_insights(event)

                    # Extract pattern from event
                    pattern = await self._extract_pattern_from_event(event)

                    if pattern:
                        patterns.append(pattern)

                    # Increment counters
                    self.processed_count += 1
                    events_since_checkpoint += 1

                    # P2-REL-001: Checkpoint periodically
                    if events_since_checkpoint % self.checkpoint_interval == 0:
                        # Update position before checkpointing
                        self.last_positions[str(telemetry_path)] = f.tell()

                        self.checkpointer.save({
                            "last_positions": self.last_positions,
                            "processed_count": self.processed_count,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "file": str(telemetry_path.name)
                        })

                        logger.info(
                            "checkpoint_created",
                            events_processed=events_since_checkpoint,
                            total_processed=self.processed_count,
                            file=telemetry_path.name
                        )

                        events_since_checkpoint = 0

                except json.JSONDecodeError:
                    # Skip malformed JSON lines
                    continue
                except Exception as e:
                    # Log error but continue processing (P2-REL-001: resilience)
                    logger.error(
                        "event_processing_failed",
                        file=telemetry_path.name,
                        error=str(e)
                    )
                    continue

            # Update final position for this file
            self.last_positions[str(telemetry_path)] = f.tell()

        # Final checkpoint for this file
        if patterns:
            self.checkpointer.save({
                "last_positions": self.last_positions,
                "processed_count": self.processed_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            logger.info(
                "file_processing_complete",
                file=telemetry_path.name,
                patterns_extracted=len(patterns),
                total_processed=self.processed_count
            )

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

    def _compute_pattern_hash(self, pattern: InteractionPattern) -> str:
        """
        P6-OPS-002: Compute hash for pattern deduplication

        Uses prompt + response content to identify duplicates
        """
        # Normalize content for hashing
        content = f"{pattern.prompt.strip()}\n{pattern.response.strip()}"
        content_normalized = content.lower().strip()

        # Compute SHA256 hash
        return hashlib.sha256(content_normalized.encode('utf-8')).hexdigest()

    def _is_duplicate(self, pattern: InteractionPattern) -> bool:
        """
        P6-OPS-002: Check if pattern is a duplicate

        Returns True if pattern was seen before
        """
        pattern_hash = self._compute_pattern_hash(pattern)

        self.dedup_stats['total_patterns'] += 1

        if pattern_hash in self.pattern_hashes:
            self.dedup_stats['duplicates_found'] += 1
            return True

        # New pattern - add to seen set
        self.pattern_hashes.add(pattern_hash)
        self.dedup_stats['unique_patterns'] += 1
        return False

    async def generate_finetuning_examples(
        self, patterns: List[InteractionPattern]
    ) -> List[FinetuningExample]:
        """Generate fine-tuning examples from patterns (with deduplication)"""
        examples: List[FinetuningExample] = []

        for pattern in patterns:
            # P6-OPS-002: Skip duplicate patterns
            if self._is_duplicate(pattern):
                logger.debug(
                    "duplicate_pattern_skipped",
                    pattern_id=pattern.pattern_id,
                    interaction_type=pattern.interaction_type
                )
                continue
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

    async def _write_stats_snapshot(self):
        """Persist current learning statistics for API consumption."""
        try:
            stats = await self.get_statistics()
            temp_path = self.stats_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(stats, f)
            temp_path.replace(self.stats_path)
        except Exception as e:
            logger.error("stats_snapshot_failed", error=str(e))

    async def _fetch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Fetch embeddings from the embeddings service."""
        if not texts:
            return []

        try:
            response = await self.embeddings_client.post(
                f"{self.embedding_service_url}/embed",
                json={"inputs": texts},
                timeout=30.0,
            )
            response.raise_for_status()
            embeddings = response.json()
            if not isinstance(embeddings, list):
                raise ValueError("Embeddings response must be a list")
            if len(embeddings) != len(texts):
                raise ValueError("Embeddings response length mismatch")
            return embeddings
        except Exception as e:
            logger.warning("embeddings_fetch_failed", error=str(e), count=len(texts))
            return []

    async def _index_patterns(self, patterns: List[InteractionPattern]):
        """Index patterns in Qdrant for retrieval"""
        if not patterns:
            return

        try:
            from qdrant_client.models import PointStruct

            points = []
            searchable_texts = []

            for pattern in patterns:
                searchable_texts.append(f"{pattern.prompt} {pattern.response}")

            embeddings = await self._fetch_embeddings(searchable_texts)
            if not embeddings:
                logger.warning("pattern_embeddings_unavailable", count=len(patterns))
                return

            for pattern, embedding in zip(patterns, embeddings):
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

            # P2-REL-002: Upsert to Qdrant with circuit breaker protection
            if points:
                qdrant_breaker = self.circuit_breakers.get("qdrant")
                try:
                    def _upsert():
                        # Wrap async call in sync function for circuit breaker
                        import asyncio
                        loop = asyncio.get_event_loop()
                        return loop.run_until_complete(self.qdrant.upsert(
                            collection_name="skills-patterns",
                            points=points,
                            wait=True,
                        ))

                    await qdrant_breaker.call(_upsert)
                    logger.info("patterns_indexed", count=len(points))

                except Exception as e:
                    logger.error("qdrant_upsert_failed", error=str(e), circuit_state=qdrant_breaker.state.value)

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

        # P2-REL-002: Save to database with circuit breaker protection
        if self.postgres:
            postgres_breaker = self.circuit_breakers.get("postgresql")
            try:
                def _insert():
                    import asyncio
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(self.postgres.execute(
                        """
                        INSERT INTO performance_metrics
                        (metric_name, value, model_version, timestamp)
                        VALUES ($1, $2, $3, $4)
                        """,
                        metric_name,
                        value,
                        model_version,
                        metric.timestamp,
                    ))

                await postgres_breaker.call(_insert)
            except Exception as e:
                logger.debug("metric_save_failed", error=str(e), circuit_state=postgres_breaker.state.value)

    def _check_backpressure(self) -> Dict[str, Any]:
        """
        P2-REL-004: Check if telemetry queue is backed up

        Returns:
            {
                'unprocessed_mb': float,  # Size of unprocessed telemetry
                'paused': bool,           # Whether to pause learning
                'file_sizes': dict        # Size per telemetry file
            }
        """
        total_unprocessed_bytes = 0
        file_sizes = {}

        for telemetry_path in self.telemetry_paths:
            if not telemetry_path.exists():
                file_sizes[str(telemetry_path.name)] = 0
                continue

            try:
                file_size = telemetry_path.stat().st_size
                file_sizes[str(telemetry_path.name)] = file_size

                # Calculate unprocessed portion
                last_position = self.last_positions.get(str(telemetry_path), 0)
                unprocessed = max(0, file_size - last_position)
                total_unprocessed_bytes += unprocessed

            except Exception as e:
                logger.error("backpressure_check_failed", file=str(telemetry_path), error=str(e))

        unprocessed_mb = total_unprocessed_bytes / (1024 * 1024)
        paused = unprocessed_mb > self.backpressure_threshold_mb

        return {
            'unprocessed_mb': round(unprocessed_mb, 2),
            'paused': paused,
            'file_sizes': file_sizes
        }

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

        # P2-REL-004: Include backpressure status
        backpressure_status = self._check_backpressure()

        # P6-OPS-002: Calculate deduplication rate
        dedup_rate = 0.0
        if self.dedup_stats['total_patterns'] > 0:
            dedup_rate = (self.dedup_stats['duplicates_found'] /
                         self.dedup_stats['total_patterns']) * 100

        return {
            "total_patterns_learned": len(self.patterns),
            "patterns_by_type": by_type,
            "finetuning_dataset_size": dataset_size,
            "total_metrics_tracked": len(self.metrics),
            "recent_metrics": recent_metrics,
            "optimization_proposals": {
                "total": len(self.proposals),
                "last_batch_count": len(self.proposals[-self.proposal_batch_limit:]) if self.proposals else 0,
            },
            "batch_insights": {
                "high_iteration_tasks": len(self.batch_insights["high_iteration_tasks"]),
                "limit_hits": len(self.batch_insights["limit_hits"]),
                "timeout_signals": self.batch_insights["timeout_signals"],
                "dependency_signals": dict(self.batch_insights["dependency_signals"]),
                "success_characteristics": dict(self.batch_insights["success_characteristics"]),
            },
            "backpressure": backpressure_status,  # P2-REL-004
            "learning_paused": self.backpressure_paused,  # P2-REL-004
            "deduplication": {  # P6-OPS-002
                "total_patterns_seen": self.dedup_stats['total_patterns'],
                "duplicates_found": self.dedup_stats['duplicates_found'],
                "unique_patterns": self.dedup_stats['unique_patterns'],
                "deduplication_rate": round(dedup_rate, 2)
            }
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
            output_path = Path(
                os.path.expanduser(
                    os.getenv("FINETUNE_EXPORT_PATH")
                    or str(self.dataset_path.parent / "dataset_export.jsonl")
                )
            )

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
