#!/usr/bin/env python3
"""
A/B Testing Framework for AI Stack Services

Implements A/B testing capabilities for model comparisons, feature validation,
and performance evaluation across the AI stack.
"""

import asyncio
import hashlib
import json
import os
import random
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
import logging

import asyncpg
from qdrant_client import QdrantClient
from redis import asyncio as redis_asyncio


logger = logging.getLogger(__name__)


class ExperimentType(Enum):
    """Types of experiments supported"""
    MODEL_COMPARISON = "model_comparison"
    FEATURE_VALIDATION = "feature_validation"
    PERFORMANCE_EVALUATION = "performance_evaluation"
    USER_EXPERIENCE = "user_experience"


class ExperimentStatus(Enum):
    """Status of an experiment"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExperimentConfig:
    """Configuration for an A/B test experiment"""
    name: str
    description: str
    variant_a: Dict[str, Any]  # Control group
    variant_b: Dict[str, Any]  # Treatment group
    traffic_split: float = 0.5  # Fraction of traffic to variant B (0.0 to 1.0)
    duration_days: int = 7
    minimum_sample_size: int = 100
    statistical_significance: float = 0.05  # Alpha level (5%)
    metrics: List[str] = field(default_factory=list)
    experiment_type: ExperimentType = ExperimentType.MODEL_COMPARISON
    hypothesis: str = ""
    success_criteria: str = ""


@dataclass
class ExperimentResult:
    """Result of an A/B test"""
    experiment_id: str
    variant: str  # 'A' or 'B'
    timestamp: datetime
    metrics: Dict[str, float]
    sample_size: int
    statistical_significance: Optional[float] = None
    confidence_interval: Optional[Dict[str, float]] = None
    winner: Optional[str] = None  # 'A', 'B', or None if inconclusive


@dataclass
class ExperimentAssignment:
    """Assignment of a user/request to a variant"""
    experiment_id: str
    user_id: str
    variant: str  # 'A' or 'B'
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)


class ABTestStorage:
    """Storage backend for A/B test data"""
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None, redis_client: Optional[redis_asyncio.Redis] = None):
        self.db_pool = db_pool
        self.redis = redis_client
    
    async def save_assignment(self, assignment: ExperimentAssignment):
        """Save experiment assignment"""
        if self.redis:
            # Cache assignment in Redis for quick lookup
            key = f"ab:{assignment.experiment_id}:{assignment.user_id}"
            await self.redis.setex(
                key,
                86400 * 30,  # 30 days expiry
                json.dumps({
                    "variant": assignment.variant,
                    "timestamp": assignment.timestamp.isoformat(),
                    "context": assignment.context
                })
            )
        
        if self.db_pool:
            # Also save to database for persistence
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO experiment_assignments 
                    (experiment_id, user_id, variant, timestamp, context)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    assignment.experiment_id,
                    assignment.user_id,
                    assignment.variant,
                    assignment.timestamp,
                    json.dumps(assignment.context)
                )
    
    async def get_assignment(self, experiment_id: str, user_id: str) -> Optional[ExperimentAssignment]:
        """Get cached assignment for a user"""
        if self.redis:
            key = f"ab:{experiment_id}:{user_id}"
            cached = await self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return ExperimentAssignment(
                    experiment_id=experiment_id,
                    user_id=user_id,
                    variant=data["variant"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    context=data.get("context", {})
                )
        
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT variant, timestamp, context
                    FROM experiment_assignments
                    WHERE experiment_id = $1 AND user_id = $2
                    """,
                    experiment_id,
                    user_id
                )
                if row:
                    return ExperimentAssignment(
                        experiment_id=experiment_id,
                        user_id=user_id,
                        variant=row["variant"],
                        timestamp=row["timestamp"],
                        context=json.loads(row["context"]) if row["context"] else {}
                    )
        
        return None
    
    async def save_result(self, result: ExperimentResult):
        """Save experiment result"""
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO experiment_results 
                    (experiment_id, variant, timestamp, metrics, sample_size, statistical_significance, confidence_interval, winner)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    result.experiment_id,
                    result.variant,
                    result.timestamp,
                    json.dumps(result.metrics),
                    result.sample_size,
                    result.statistical_significance,
                    json.dumps(result.confidence_interval) if result.confidence_interval else None,
                    result.winner
                )
    
    async def get_results(self, experiment_id: str) -> List[ExperimentResult]:
        """Get all results for an experiment"""
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT variant, timestamp, metrics, sample_size, statistical_significance, confidence_interval, winner
                    FROM experiment_results
                    WHERE experiment_id = $1
                    ORDER BY timestamp DESC
                    """,
                    experiment_id
                )
                return [
                    ExperimentResult(
                        experiment_id=experiment_id,
                        variant=row["variant"],
                        timestamp=row["timestamp"],
                        metrics=json.loads(row["metrics"]),
                        sample_size=row["sample_size"],
                        statistical_significance=row["statistical_significance"],
                        confidence_interval=json.loads(row["confidence_interval"]) if row["confidence_interval"] else None,
                        winner=row["winner"]
                    )
                    for row in rows
                ]
        return []


class ABTestEngine:
    """Main A/B testing engine"""
    
    def __init__(self, storage: ABTestStorage, qdrant_client: Optional[QdrantClient] = None):
        self.storage = storage
        self.qdrant = qdrant_client
        self.experiments: Dict[str, ExperimentConfig] = {}
        self.running_experiments: Dict[str, asyncio.Task] = {}
    
    def register_experiment(self, config: ExperimentConfig) -> str:
        """Register a new experiment"""
        # Generate unique experiment ID
        experiment_id = hashlib.sha256(
            f"{config.name}_{int(time.time())}".encode()
        ).hexdigest()[:12]
        
        config_dict = {
            "id": experiment_id,
            "name": config.name,
            "description": config.description,
            "variant_a": config.variant_a,
            "variant_b": config.variant_b,
            "traffic_split": config.traffic_split,
            "duration_days": config.duration_days,
            "minimum_sample_size": config.minimum_sample_size,
            "statistical_significance": config.statistical_significance,
            "metrics": config.metrics,
            "experiment_type": config.experiment_type.value,
            "hypothesis": config.hypothesis,
            "success_criteria": config.success_criteria,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": ExperimentStatus.DRAFT.value
        }
        
        self.experiments[experiment_id] = config
        
        # If Qdrant is available, store experiment config
        if self.qdrant:
            try:
                from qdrant_client.models import PointStruct
                import numpy as np
                
                # Create a simple embedding from the experiment description
                desc_embedding = [float(ord(c) % 100) for c in config.description[:100]]
                # Pad or truncate to a fixed size
                desc_embedding = (desc_embedding + [0.0] * 100)[:100]
                
                self.qdrant.upsert(
                    collection_name="ab_experiments",
                    points=[
                        PointStruct(
                            id=experiment_id,
                            vector=desc_embedding,
                            payload=config_dict
                        )
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to store experiment in Qdrant: {e}")
        
        return experiment_id
    
    def start_experiment(self, experiment_id: str) -> bool:
        """Start a registered experiment"""
        if experiment_id not in self.experiments:
            return False
        
        config = self.experiments[experiment_id]
        config_dict = self._get_experiment_dict(config, experiment_id)
        config_dict["status"] = ExperimentStatus.RUNNING.value
        config_dict["started_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update in Qdrant if available
        if self.qdrant:
            try:
                from qdrant_client.models import PointStruct
                desc_embedding = [float(ord(c) % 100) for c in config.description[:100]]
                desc_embedding = (desc_embedding + [0.0] * 100)[:100]
                
                self.qdrant.upsert(
                    collection_name="ab_experiments",
                    points=[
                        PointStruct(
                            id=experiment_id,
                            vector=desc_embedding,
                            payload=config_dict
                        )
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to update experiment in Qdrant: {e}")
        
        # Start monitoring task
        self.running_experiments[experiment_id] = asyncio.create_task(
            self._monitor_experiment(experiment_id, config)
        )
        
        return True
    
    def stop_experiment(self, experiment_id: str) -> bool:
        """Stop a running experiment"""
        if experiment_id in self.running_experiments:
            task = self.running_experiments[experiment_id]
            task.cancel()
            del self.running_experiments[experiment_id]
            
            # Update status in Qdrant
            if self.qdrant:
                try:
                    config = self.experiments[experiment_id]
                    config_dict = self._get_experiment_dict(config, experiment_id)
                    config_dict["status"] = ExperimentStatus.COMPLETED.value
                    config_dict["completed_at"] = datetime.now(timezone.utc).isoformat()
                    
                    desc_embedding = [float(ord(c) % 100) for c in config.description[:100]]
                    desc_embedding = (desc_embedding + [0.0] * 100)[:100]
                    
                    self.qdrant.upsert(
                        collection_name="ab_experiments",
                        points=[
                            PointStruct(
                                id=experiment_id,
                                vector=desc_embedding,
                                payload=config_dict
                            )
                        ]
                    )
                except Exception as e:
                    logger.warning(f"Failed to update experiment in Qdrant: {e}")
            
            return True
        return False
    
    async def assign_variant(self, experiment_id: str, user_id: str, context: Dict[str, Any] = None) -> str:
        """Assign a user to a variant for an experiment"""
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        # Check if user already assigned
        assignment = await self.storage.get_assignment(experiment_id, user_id)
        if assignment:
            return assignment.variant
        
        # Assign based on traffic split
        config = self.experiments[experiment_id]
        
        # Use consistent hashing to ensure same user gets same variant
        hash_input = f"{experiment_id}_{user_id}".encode()
        hash_val = int(hashlib.md5(hash_input).hexdigest(), 16)
        rand_val = (hash_val % 10000) / 10000.0  # 0.0 to 1.0
        
        variant = "B" if rand_val < config.traffic_split else "A"
        
        # Save assignment
        assignment = ExperimentAssignment(
            experiment_id=experiment_id,
            user_id=user_id,
            variant=variant,
            timestamp=datetime.now(timezone.utc),
            context=context or {}
        )
        await self.storage.save_assignment(assignment)
        
        return variant
    
    async def record_metric(self, experiment_id: str, user_id: str, variant: str, metrics: Dict[str, float]):
        """Record metrics for a user's interaction with a variant"""
        result = ExperimentResult(
            experiment_id=experiment_id,
            variant=variant,
            timestamp=datetime.now(timezone.utc),
            metrics=metrics,
            sample_size=1  # Will be aggregated later
        )
        await self.storage.save_result(result)
    
    async def get_experiment_results(self, experiment_id: str) -> List[ExperimentResult]:
        """Get results for an experiment"""
        return await self.storage.get_results(experiment_id)
    
    async def _monitor_experiment(self, experiment_id: str, config: ExperimentConfig):
        """Monitor an experiment and check for completion criteria"""
        start_time = datetime.now(timezone.utc)
        duration = config.duration_days * 24 * 60 * 60  # seconds
        
        while True:
            try:
                # Check if experiment duration has passed
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed >= duration:
                    logger.info(f"Experiment {experiment_id} duration exceeded, stopping")
                    self.stop_experiment(experiment_id)
                    break
                
                # Check sample size
                results = await self.get_experiment_results(experiment_id)
                total_samples = sum(r.sample_size for r in results)
                
                if total_samples >= config.minimum_sample_size:
                    # Check for statistical significance
                    if await self._is_statistically_significant(results, config.statistical_significance):
                        logger.info(f"Experiment {experiment_id} reached statistical significance, stopping early")
                        self.stop_experiment(experiment_id)
                        break
                
                # Wait before next check
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except asyncio.CancelledError:
                logger.info(f"Experiment {experiment_id} monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error monitoring experiment {experiment_id}: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _is_statistically_significant(self, results: List[ExperimentResult], alpha: float) -> bool:
        """Check if results are statistically significant"""
        # This is a simplified check - in practice you'd use proper statistical tests
        # like t-test, chi-square, etc. depending on the metric type
        
        if len(results) < 2:
            return False
        
        # Group results by variant
        variant_a_results = [r for r in results if r.variant == "A"]
        variant_b_results = [r for r in results if r.variant == "B"]
        
        if not variant_a_results or not variant_b_results:
            return False
        
        # Calculate average metrics for each variant
        avg_a = {}
        avg_b = {}
        
        for metric in results[0].metrics.keys():
            a_values = [r.metrics[metric] for r in variant_a_results if metric in r.metrics]
            b_values = [r.metrics[metric] for r in variant_b_results if metric in r.metrics]
            
            if a_values and b_values:
                avg_a[metric] = sum(a_values) / len(a_values)
                avg_b[metric] = sum(b_values) / len(b_values)
        
        # Simple comparison - in practice use proper statistical tests
        for metric in avg_a.keys():
            if metric in avg_b:
                diff = abs(avg_a[metric] - avg_b[metric])
                baseline = avg_a[metric]
                
                # If difference is significant relative to baseline
                if baseline != 0 and (diff / abs(baseline)) > 0.05:  # 5% difference
                    return True
        
        return False
    
    def _get_experiment_dict(self, config: ExperimentConfig, experiment_id: str) -> Dict[str, Any]:
        """Convert experiment config to dictionary"""
        return {
            "id": experiment_id,
            "name": config.name,
            "description": config.description,
            "variant_a": config.variant_a,
            "variant_b": config.variant_b,
            "traffic_split": config.traffic_split,
            "duration_days": config.duration_days,
            "minimum_sample_size": config.minimum_sample_size,
            "statistical_significance": config.statistical_significance,
            "metrics": config.metrics,
            "experiment_type": config.experiment_type.value,
            "hypothesis": config.hypothesis,
            "success_criteria": config.success_criteria,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


class ABTestMiddleware:
    """Middleware to integrate A/B testing into request handling"""
    
    def __init__(self, ab_test_engine: ABTestEngine):
        self.engine = ab_test_engine
    
    async def process_request(self, request_data: Dict[str, Any], user_id: str = "anonymous") -> Dict[str, Any]:
        """Process a request through A/B testing middleware"""
        # Check for active experiments
        # For now, return the original request data
        # In a real implementation, this would modify the request based on assigned variant
        return request_data


# Example usage
async def example_usage():
    """Example of how to use the A/B testing framework"""
    
    # This would typically be connected to your actual database/redis/qdrant
    # For this example, we'll use mock objects
    storage = ABTestStorage()
    
    # Create A/B test engine
    engine = ABTestEngine(storage)
    
    # Define an experiment comparing two models
    experiment_config = ExperimentConfig(
        name="model-comparison-qwen-vs-deepseek",
        description="Compare Qwen2.5-Coder-7B vs DeepSeek-Coder-V2-Lite for code generation quality",
        variant_a={
            "model": "Qwen2.5-Coder-7B",
            "parameters": {"temperature": 0.7, "max_tokens": 512}
        },
        variant_b={
            "model": "DeepSeek-Coder-V2-Lite",
            "parameters": {"temperature": 0.7, "max_tokens": 512}
        },
        traffic_split=0.5,  # 50/50 split
        duration_days=7,
        minimum_sample_size=1000,
        statistical_significance=0.05,
        metrics=["response_time", "accuracy_score", "user_satisfaction"],
        experiment_type=ExperimentType.MODEL_COMPARISON,
        hypothesis="DeepSeek-Coder-V2-Lite will have higher accuracy for algorithmic problems",
        success_criteria="Statistical significance of 95% with 5% improvement in accuracy"
    )
    
    # Register the experiment
    experiment_id = engine.register_experiment(experiment_config)
    print(f"Registered experiment: {experiment_id}")
    
    # Start the experiment
    engine.start_experiment(experiment_id)
    print(f"Started experiment: {experiment_id}")
    
    # Simulate assigning users to variants
    for i in range(10):
        user_id = f"user_{i}"
        variant = await engine.assign_variant(experiment_id, user_id)
        print(f"User {user_id} assigned to variant {variant}")
        
        # Simulate recording metrics
        metrics = {
            "response_time": random.uniform(1.0, 3.0),
            "accuracy_score": random.uniform(0.7, 0.95),
            "user_satisfaction": random.uniform(3.0, 5.0)
        }
        await engine.record_metric(experiment_id, user_id, variant, metrics)
    
    # Get results
    results = await engine.get_experiment_results(experiment_id)
    print(f"Collected {len(results)} results")
    
    # Stop the experiment
    engine.stop_experiment(experiment_id)
    print(f"Stopped experiment: {experiment_id}")


if __name__ == "__main__":
    asyncio.run(example_usage())