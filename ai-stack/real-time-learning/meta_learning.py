#!/usr/bin/env python3
"""
Meta-Learning for Rapid Adaptation

MAML-based meta-learning for rapid task adaptation.
Part of Phase 10 Batch 10.3: Meta-Learning for Rapid Adaptation

Key Features:
- MAML (Model-Agnostic Meta-Learning) implementation
- Few-shot learning capabilities
- Task embedding for transfer learning
- Meta-optimization for hyperparameters
- Rapid task adaptation
"""

import asyncio
import json
import logging
import numpy as np
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class TaskDomain(Enum):
    """Task domains"""
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    CONFIGURATION = "configuration"
    EXPLANATION = "explanation"
    PLANNING = "planning"


@dataclass
class Task:
    """Learning task"""
    task_id: str
    domain: TaskDomain
    description: str
    examples: List[Dict[str, Any]] = field(default_factory=list)
    embedding: Optional[np.ndarray] = None


@dataclass
class MetaLearningState:
    """State of meta-learning system"""
    meta_parameters: Dict[str, float] = field(default_factory=dict)
    task_history: List[Task] = field(default_factory=list)
    adaptation_history: List[Dict] = field(default_factory=list)


class MAMLLearner:
    """Model-Agnostic Meta-Learning implementation"""

    def __init__(self, learning_rate: float = 0.01, meta_learning_rate: float = 0.001):
        self.learning_rate = learning_rate
        self.meta_learning_rate = meta_learning_rate

        # Meta-parameters (shared initialization across tasks)
        self.meta_params = {
            "weight_query_encoding": 0.3,
            "weight_context_relevance": 0.4,
            "weight_domain_knowledge": 0.2,
            "weight_novelty": 0.1,
        }

        self.adaptation_steps = 5
        self.task_models: Dict[str, Dict[str, float]] = {}
        self.update_history: List[Dict[str, Any]] = []

        logger.info(
            f"MAML Learner initialized "
            f"(lr={learning_rate}, meta_lr={meta_learning_rate})"
        )

    async def meta_train(self, tasks: List[Task]) -> Dict[str, float]:
        """Meta-train on batch of tasks"""
        logger.info(f"Meta-training on {len(tasks)} tasks")

        meta_gradients = defaultdict(float)

        for task in tasks:
            # Split task examples into support and query sets
            support_set, query_set = self._split_examples(task.examples)

            if not support_set or not query_set:
                continue

            # Adapt to task using support set
            task_params = await self._adapt_to_task(task, support_set)

            # Evaluate on query set
            task_loss = self._evaluate_task(task_params, query_set)

            # Calculate gradients w.r.t. meta-parameters
            gradients = self._calculate_meta_gradients(task_params, task_loss)

            # Accumulate gradients
            for param, gradient in gradients.items():
                meta_gradients[param] += gradient

        # Average gradients
        for param in meta_gradients:
            meta_gradients[param] /= len(tasks)

        # Update meta-parameters
        for param, gradient in meta_gradients.items():
            self.meta_params[param] -= self.meta_learning_rate * gradient

        # Normalize
        total = sum(self.meta_params.values())
        for param in self.meta_params:
            self.meta_params[param] /= total

        logger.info(f"Meta-training complete. Updated meta-parameters: {self.meta_params}")

        return self.meta_params

    async def adapt_to_task(
        self,
        task: Task,
        few_shot_examples: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Rapidly adapt to new task using few-shot examples"""
        logger.info(f"Adapting to task: {task.task_id} with {len(few_shot_examples)} examples")

        # Start with meta-parameters
        task_params = self.meta_params.copy()

        # Fine-tune on few-shot examples
        for step in range(self.adaptation_steps):
            # Calculate loss on examples
            loss = self._evaluate_task(task_params, few_shot_examples)

            # Calculate gradients
            gradients = self._calculate_gradients(task_params, few_shot_examples)

            # Update parameters
            for param, gradient in gradients.items():
                task_params[param] -= self.learning_rate * gradient

            logger.debug(f"  Adaptation step {step+1}/{self.adaptation_steps}: loss={loss:.3f}")

        # Store adapted model
        self.task_models[task.task_id] = task_params

        logger.info(f"Adaptation complete for {task.task_id}")

        return task_params

    def _split_examples(
        self,
        examples: List[Dict[str, Any]],
        support_ratio: float = 0.7,
    ) -> Tuple[List[Dict], List[Dict]]:
        """Split examples into support and query sets"""
        if not examples:
            return [], []

        split_idx = int(len(examples) * support_ratio)
        support = examples[:split_idx]
        query = examples[split_idx:]

        return support, query

    async def _adapt_to_task(
        self,
        task: Task,
        support_set: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Inner loop: adapt to task using support set"""
        task_params = self.meta_params.copy()

        for _ in range(self.adaptation_steps):
            gradients = self._calculate_gradients(task_params, support_set)

            for param, gradient in gradients.items():
                task_params[param] -= self.learning_rate * gradient

        return task_params

    def _evaluate_task(
        self,
        params: Dict[str, float],
        examples: List[Dict[str, Any]],
    ) -> float:
        """Evaluate parameters on examples"""
        if not examples:
            return 0.0

        # Simplified loss calculation
        # In production, would use actual model predictions
        losses = []

        for example in examples:
            # Simulate prediction error
            predicted_quality = sum(params.values()) / len(params)  # Simplified
            actual_quality = example.get("quality", 0.5)

            loss = (predicted_quality - actual_quality) ** 2
            losses.append(loss)

        return sum(losses) / len(losses)

    def _calculate_gradients(
        self,
        params: Dict[str, float],
        examples: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Calculate gradients for parameters"""
        gradients = {}

        # Simplified gradient calculation
        loss = self._evaluate_task(params, examples)

        for param in params.keys():
            # Finite difference approximation
            epsilon = 0.001
            params_plus = params.copy()
            params_plus[param] += epsilon

            loss_plus = self._evaluate_task(params_plus, examples)

            gradient = (loss_plus - loss) / epsilon
            gradients[param] = gradient

        return gradients

    def _calculate_meta_gradients(
        self,
        task_params: Dict[str, float],
        task_loss: float,
    ) -> Dict[str, float]:
        """Calculate gradients w.r.t. meta-parameters"""
        gradients = {}

        # Simplified: gradient proportional to difference from meta-params
        for param in self.meta_params.keys():
            diff = task_params[param] - self.meta_params[param]
            gradients[param] = diff * task_loss

        return gradients


class FewShotLearner:
    """Few-shot learning system"""

    def __init__(self):
        self.prototypes: Dict[TaskDomain, np.ndarray] = {}
        self.examples_by_domain: Dict[TaskDomain, List[Dict]] = defaultdict(list)

        logger.info("Few-Shot Learner initialized")

    async def learn_from_examples(
        self,
        domain: TaskDomain,
        examples: List[Dict[str, Any]],
    ):
        """Learn from few examples"""
        logger.info(f"Learning from {len(examples)} examples in {domain.value}")

        # Store examples
        self.examples_by_domain[domain].extend(examples)

        # Compute prototype for domain
        prototype = self._compute_prototype(examples)
        self.prototypes[domain] = prototype

        logger.info(f"Prototype updated for {domain.value}")

    def _compute_prototype(self, examples: List[Dict[str, Any]]) -> np.ndarray:
        """Compute prototype embedding from examples"""
        # Simplified: would use actual embeddings in production
        # For now, create random prototype
        return np.random.randn(128)  # 128-dim embedding

    async def classify_task(self, task_description: str) -> TaskDomain:
        """Classify task into domain using few-shot learning"""
        # Simplified classification
        # Would use embedding similarity in production

        desc_lower = task_description.lower()

        if "implement" in desc_lower or "write" in desc_lower:
            return TaskDomain.CODE_GENERATION
        elif "debug" in desc_lower or "fix" in desc_lower:
            return TaskDomain.DEBUGGING
        elif "configure" in desc_lower or "setup" in desc_lower:
            return TaskDomain.CONFIGURATION
        elif "explain" in desc_lower or "what" in desc_lower:
            return TaskDomain.EXPLANATION
        else:
            return TaskDomain.PLANNING

    async def predict_quality(
        self,
        task: Task,
        response: str,
    ) -> float:
        """Predict response quality using few-shot learning"""
        # Get domain prototype
        prototype = self.prototypes.get(task.domain)

        if prototype is None:
            # No examples yet, return neutral
            return 0.5

        # Simplified quality prediction
        # Would use actual similarity calculation in production
        base_quality = 0.7

        # Adjust based on response characteristics
        if len(response) > 100:
            base_quality += 0.1

        if "```" in response:  # Has code block
            base_quality += 0.05

        return min(1.0, base_quality)


class TaskEmbedder:
    """Embed tasks for transfer learning"""

    def __init__(self, embedding_dim: int = 128):
        self.embedding_dim = embedding_dim
        self.task_embeddings: Dict[str, np.ndarray] = {}

        logger.info(f"Task Embedder initialized (dim={embedding_dim})")

    def embed_task(self, task: Task) -> np.ndarray:
        """Embed task into vector space"""
        # Simplified: would use learned embeddings in production
        # For now, create embedding based on task characteristics

        # Domain embedding
        domain_emb = self._domain_embedding(task.domain)

        # Description embedding (simplified)
        desc_emb = self._text_embedding(task.description)

        # Combine
        embedding = (domain_emb + desc_emb) / 2

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        # Store
        self.task_embeddings[task.task_id] = embedding
        task.embedding = embedding

        return embedding

    def find_similar_tasks(
        self,
        task: Task,
        k: int = 5,
    ) -> List[Tuple[str, float]]:
        """Find k most similar tasks"""
        if task.embedding is None:
            self.embed_task(task)

        similarities = []

        for task_id, embedding in self.task_embeddings.items():
            if task_id == task.task_id:
                continue

            # Cosine similarity
            similarity = np.dot(task.embedding, embedding)
            similarities.append((task_id, similarity))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:k]

    def _domain_embedding(self, domain: TaskDomain) -> np.ndarray:
        """Get embedding for domain"""
        # One-hot-like encoding
        domain_map = {
            TaskDomain.CODE_GENERATION: 0,
            TaskDomain.DEBUGGING: 1,
            TaskDomain.CONFIGURATION: 2,
            TaskDomain.EXPLANATION: 3,
            TaskDomain.PLANNING: 4,
        }

        embedding = np.zeros(self.embedding_dim)
        idx = domain_map.get(domain, 0)

        # Set relevant dimensions
        start_idx = idx * (self.embedding_dim // 5)
        end_idx = start_idx + (self.embedding_dim // 5)
        embedding[start_idx:end_idx] = 1.0

        return embedding

    def _text_embedding(self, text: str) -> np.ndarray:
        """Simplified text embedding"""
        # Would use actual text embeddings (BERT, etc.) in production
        # For now, simple hash-based embedding
        embedding = np.random.randn(self.embedding_dim)

        # Make it deterministic based on text
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(self.embedding_dim)

        return embedding


class MetaOptimizer:
    """Meta-optimize hyperparameters"""

    def __init__(self):
        self.hyperparams = {
            "learning_rate": 0.01,
            "meta_learning_rate": 0.001,
            "adaptation_steps": 5,
            "batch_size": 32,
        }

        self.optimization_history: List[Dict] = []

        logger.info("Meta-Optimizer initialized")

    async def optimize_hyperparameters(
        self,
        validation_tasks: List[Task],
        maml_learner: MAMLLearner,
    ) -> Dict[str, float]:
        """Optimize hyperparameters on validation tasks"""
        logger.info("Optimizing hyperparameters")

        best_params = self.hyperparams.copy()
        best_score = 0.0

        # Grid search (simplified)
        learning_rates = [0.001, 0.01, 0.1]
        adaptation_steps_options = [3, 5, 10]

        for lr in learning_rates:
            for steps in adaptation_steps_options:
                # Set hyperparameters
                maml_learner.learning_rate = lr
                maml_learner.adaptation_steps = steps

                # Evaluate on validation tasks
                score = await self._evaluate_hyperparams(
                    validation_tasks,
                    maml_learner,
                )

                logger.info(f"  lr={lr}, steps={steps}: score={score:.3f}")

                if score > best_score:
                    best_score = score
                    best_params = {
                        "learning_rate": lr,
                        "adaptation_steps": steps,
                    }

        # Update hyperparameters
        self.hyperparams.update(best_params)

        # Record optimization
        self.optimization_history.append({
            "timestamp": datetime.now(),
            "best_params": best_params,
            "best_score": best_score,
        })

        logger.info(f"Optimization complete: {best_params}")

        return best_params

    async def _evaluate_hyperparams(
        self,
        tasks: List[Task],
        maml_learner: MAMLLearner,
    ) -> float:
        """Evaluate hyperparameters on tasks"""
        scores = []

        for task in tasks:
            if not task.examples:
                continue

            # Split examples
            support, query = maml_learner._split_examples(task.examples)

            if not support or not query:
                continue

            # Adapt to task
            task_params = await maml_learner.adapt_to_task(task, support)

            # Evaluate on query set
            loss = maml_learner._evaluate_task(task_params, query)

            # Score (lower loss is better)
            score = 1.0 / (1.0 + loss)
            scores.append(score)

        if not scores:
            return 0.0

        return sum(scores) / len(scores)


class RapidAdaptor:
    """Rapid task adaptation system"""

    def __init__(self):
        self.maml = MAMLLearner()
        self.few_shot = FewShotLearner()
        self.embedder = TaskEmbedder()
        self.meta_optimizer = MetaOptimizer()

        self.adaptation_cache: Dict[str, Dict[str, float]] = {}

        logger.info("Rapid Adaptor initialized")

    async def adapt_to_new_task(
        self,
        task: Task,
        few_shot_examples: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Rapidly adapt to new task"""
        logger.info(f"Rapid adaptation to task: {task.task_id}")

        # Check cache
        if task.task_id in self.adaptation_cache:
            logger.info("  Using cached adaptation")
            return {
                "task_id": task.task_id,
                "method": "cached",
                "parameters": self.adaptation_cache[task.task_id],
            }

        # Embed task
        embedding = self.embedder.embed_task(task)

        # Find similar tasks for transfer
        similar_tasks = self.embedder.find_similar_tasks(task, k=3)

        logger.info(f"  Found {len(similar_tasks)} similar tasks")

        # MAML adaptation
        task_params = await self.maml.adapt_to_task(task, few_shot_examples)

        # Few-shot learning
        await self.few_shot.learn_from_examples(task.domain, few_shot_examples)

        # Cache adaptation
        self.adaptation_cache[task.task_id] = task_params

        return {
            "task_id": task.task_id,
            "method": "maml",
            "parameters": task_params,
            "similar_tasks": similar_tasks,
            "embedding_norm": float(np.linalg.norm(embedding)),
        }


async def main():
    """Test meta-learning system"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Meta-Learning for Rapid Adaptation Test")
    logger.info("=" * 60)

    # Test 1: MAML training
    logger.info("\n1. MAML Meta-Training:")

    maml = MAMLLearner()

    # Create sample tasks
    tasks = [
        Task(
            task_id="task_1",
            domain=TaskDomain.CODE_GENERATION,
            description="Generate Python function",
            examples=[
                {"input": "sort list", "output": "def sort...", "quality": 0.9},
                {"input": "reverse string", "output": "def reverse...", "quality": 0.85},
            ],
        ),
        Task(
            task_id="task_2",
            domain=TaskDomain.DEBUGGING,
            description="Fix Python bug",
            examples=[
                {"input": "index error", "output": "check bounds", "quality": 0.8},
                {"input": "null pointer", "output": "check none", "quality": 0.75},
            ],
        ),
    ]

    meta_params = await maml.meta_train(tasks)
    logger.info(f"  Meta-parameters learned: {list(meta_params.keys())}")

    # Test 2: Few-shot learning
    logger.info("\n2. Few-Shot Learning:")

    few_shot = FewShotLearner()

    await few_shot.learn_from_examples(
        TaskDomain.CODE_GENERATION,
        [{"input": "example 1", "output": "result 1"}],
    )

    domain = await few_shot.classify_task("implement a sorting algorithm")
    logger.info(f"  Classified task as: {domain.value}")

    # Test 3: Task embedding
    logger.info("\n3. Task Embedding:")

    embedder = TaskEmbedder()

    task = Task(
        task_id="task_3",
        domain=TaskDomain.CONFIGURATION,
        description="Configure NixOS module",
    )

    embedding = embedder.embed_task(task)
    logger.info(f"  Embedding dimension: {embedding.shape[0]}")
    logger.info(f"  Embedding norm: {np.linalg.norm(embedding):.3f}")

    # Test 4: Meta-optimization
    logger.info("\n4. Meta-Optimization:")

    optimizer = MetaOptimizer()

    best_params = await optimizer.optimize_hyperparameters(tasks, maml)
    logger.info(f"  Optimized parameters: {best_params}")

    # Test 5: Rapid adaptation
    logger.info("\n5. Rapid Task Adaptation:")

    adaptor = RapidAdaptor()

    new_task = Task(
        task_id="new_task",
        domain=TaskDomain.CODE_GENERATION,
        description="Implement binary search",
        examples=[
            {"input": "search sorted array", "output": "binary search implementation", "quality": 0.9},
        ],
    )

    result = await adaptor.adapt_to_new_task(
        new_task,
        new_task.examples,
    )

    logger.info(f"  Adaptation method: {result['method']}")
    logger.info(f"  Similar tasks found: {len(result['similar_tasks'])}")


if __name__ == "__main__":
    asyncio.run(main())
