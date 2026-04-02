#!/usr/bin/env python3
"""
Synthetic Data Generation

Real implementation of synthetic training data generation from remote model outputs.
Part of Phase 5 Batch 5.1: Training Data Collection & Curation

Key Features:
- Generate diverse training data from flagship models
- Task-specific prompt templates with variations
- Response quality filtering and validation
- Batch generation with rate limiting
- Format preservation for different model targets

Reference: Self-Instruct, Evol-Instruct, WizardLM
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Runtime writable state
SYNTHETIC_DATA_STATE = Path(os.getenv(
    "SYNTHETIC_DATA_STATE",
    "/var/lib/ai-stack/hybrid/synthetic-data"
))


class GenerationStrategy(Enum):
    """Synthetic data generation strategies"""
    SELF_INSTRUCT = "self_instruct"  # Generate instructions from seed tasks
    EVOL_INSTRUCT = "evol_instruct"  # Evolve complexity of instructions
    BACKTRANSLATE = "backtranslate"  # Reverse engineer prompts from responses
    SEED_EXPANSION = "seed_expansion"  # Expand from seed examples
    TASK_DECOMPOSITION = "task_decomposition"  # Break complex tasks into steps


class TaskCategory(Enum):
    """Task categories for synthetic data"""
    CODE_GENERATION = "code_generation"
    CODE_EXPLANATION = "code_explanation"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    TESTING = "testing"
    ARCHITECTURE = "architecture"
    GENERAL_QA = "general_qa"


@dataclass
class SyntheticExample:
    """A synthetic training example"""
    id: str
    prompt: str
    response: str
    category: TaskCategory
    strategy: GenerationStrategy
    complexity: int  # 1-5 scale
    quality_score: float  # 0-1
    teacher_model: str
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    validated: bool = False


@dataclass
class GenerationConfig:
    """Configuration for synthetic data generation"""
    target_examples: int = 1000
    categories: List[TaskCategory] = field(default_factory=lambda: list(TaskCategory))
    strategies: List[GenerationStrategy] = field(default_factory=lambda: [
        GenerationStrategy.SELF_INSTRUCT,
        GenerationStrategy.EVOL_INSTRUCT,
    ])
    min_quality: float = 0.7
    max_complexity: int = 5
    batch_size: int = 10
    rate_limit_delay: float = 1.0  # seconds between batches


class PromptTemplateLibrary:
    """Library of prompt templates for synthetic generation"""

    def __init__(self):
        self.templates: Dict[TaskCategory, List[Dict]] = {
            TaskCategory.CODE_GENERATION: [
                {
                    "template": "Write a {language} function that {task_description}",
                    "variables": {
                        "language": ["Python", "JavaScript", "TypeScript", "Go", "Rust"],
                        "task_description": [
                            "sorts a list of integers in ascending order",
                            "finds the longest common prefix among strings",
                            "validates email addresses using regex",
                            "implements a binary search algorithm",
                            "calculates the factorial of a number recursively",
                            "reverses a linked list in-place",
                            "finds all permutations of a string",
                            "implements a rate limiter with sliding window",
                            "parses JSON from a string safely",
                            "implements retry logic with exponential backoff",
                        ],
                    },
                    "complexity_range": (1, 4),
                },
                {
                    "template": "Implement a {data_structure} in {language} with the following operations: {operations}",
                    "variables": {
                        "data_structure": ["stack", "queue", "hash map", "binary tree", "graph"],
                        "language": ["Python", "JavaScript", "TypeScript"],
                        "operations": [
                            "insert, delete, search",
                            "push, pop, peek, is_empty",
                            "enqueue, dequeue, front, size",
                        ],
                    },
                    "complexity_range": (3, 5),
                },
            ],
            TaskCategory.CODE_EXPLANATION: [
                {
                    "template": "Explain how {concept} works in {language}, with examples",
                    "variables": {
                        "concept": [
                            "async/await",
                            "decorators",
                            "context managers",
                            "generators and iterators",
                            "metaclasses",
                            "closures",
                            "higher-order functions",
                            "type hints",
                        ],
                        "language": ["Python", "JavaScript", "TypeScript"],
                    },
                    "complexity_range": (2, 4),
                },
            ],
            TaskCategory.DEBUGGING: [
                {
                    "template": "Debug the following {language} code that should {expected_behavior} but instead {actual_behavior}:\n```{language}\n{code_snippet}\n```",
                    "variables": {
                        "language": ["Python", "JavaScript"],
                        "expected_behavior": [
                            "return the sum of all elements",
                            "filter out None values",
                            "sort in descending order",
                        ],
                        "actual_behavior": [
                            "raises a TypeError",
                            "returns an empty list",
                            "hangs indefinitely",
                        ],
                        "code_snippet": ["# [Placeholder for actual buggy code]"],
                    },
                    "complexity_range": (2, 5),
                },
            ],
            TaskCategory.CODE_REVIEW: [
                {
                    "template": "Review this {language} code for {review_focus}:\n```{language}\n{code_to_review}\n```",
                    "variables": {
                        "language": ["Python", "JavaScript", "TypeScript"],
                        "review_focus": [
                            "performance issues",
                            "security vulnerabilities",
                            "code quality and best practices",
                            "potential bugs",
                            "readability improvements",
                        ],
                        "code_to_review": ["# [Placeholder for code to review]"],
                    },
                    "complexity_range": (2, 4),
                },
            ],
            TaskCategory.REFACTORING: [
                {
                    "template": "Refactor this {language} code to {refactoring_goal}:\n```{language}\n{code_to_refactor}\n```",
                    "variables": {
                        "language": ["Python", "JavaScript", "TypeScript"],
                        "refactoring_goal": [
                            "use more idiomatic patterns",
                            "improve testability",
                            "reduce complexity",
                            "follow SOLID principles",
                            "add proper error handling",
                        ],
                        "code_to_refactor": ["# [Placeholder for code]"],
                    },
                    "complexity_range": (3, 5),
                },
            ],
            TaskCategory.DOCUMENTATION: [
                {
                    "template": "Write comprehensive documentation for this {language} {code_type}:\n```{language}\n{code_to_document}\n```",
                    "variables": {
                        "language": ["Python", "JavaScript", "TypeScript"],
                        "code_type": ["function", "class", "module", "API endpoint"],
                        "code_to_document": ["# [Placeholder for code]"],
                    },
                    "complexity_range": (1, 3),
                },
            ],
            TaskCategory.TESTING: [
                {
                    "template": "Write {test_type} tests for this {language} {code_type}:\n```{language}\n{code_to_test}\n```",
                    "variables": {
                        "language": ["Python", "JavaScript", "TypeScript"],
                        "test_type": ["unit", "integration", "property-based"],
                        "code_type": ["function", "class", "module"],
                        "code_to_test": ["# [Placeholder for code]"],
                    },
                    "complexity_range": (2, 4),
                },
            ],
            TaskCategory.ARCHITECTURE: [
                {
                    "template": "Design the architecture for {system_description} considering {requirements}",
                    "variables": {
                        "system_description": [
                            "a real-time notification service",
                            "an event-driven microservice",
                            "a distributed caching layer",
                            "an API gateway with rate limiting",
                        ],
                        "requirements": [
                            "high availability and fault tolerance",
                            "horizontal scalability",
                            "low latency requirements",
                            "security and compliance",
                        ],
                    },
                    "complexity_range": (4, 5),
                },
            ],
            TaskCategory.GENERAL_QA: [
                {
                    "template": "What is the best approach to {task} when {context}?",
                    "variables": {
                        "task": [
                            "handle concurrent requests",
                            "manage application state",
                            "implement authentication",
                            "structure a large codebase",
                        ],
                        "context": [
                            "working with a small team",
                            "optimizing for performance",
                            "building for maintainability",
                            "following security best practices",
                        ],
                    },
                    "complexity_range": (2, 4),
                },
            ],
        }

    def get_templates(self, category: TaskCategory) -> List[Dict]:
        """Get templates for a category"""
        return self.templates.get(category, [])

    def generate_prompt(self, category: TaskCategory) -> Tuple[str, int]:
        """Generate a prompt from templates, returns (prompt, complexity)"""
        templates = self.get_templates(category)
        if not templates:
            return None, 0

        template_def = random.choice(templates)
        template = template_def["template"]
        variables = template_def["variables"]
        complexity_range = template_def["complexity_range"]

        # Fill in variables
        prompt = template
        for var_name, var_options in variables.items():
            value = random.choice(var_options)
            prompt = prompt.replace(f"{{{var_name}}}", value)

        complexity = random.randint(*complexity_range)

        return prompt, complexity


class SelfInstructGenerator:
    """Generate instructions using Self-Instruct methodology"""

    def __init__(self, seed_tasks: Optional[List[Dict]] = None):
        self.seed_tasks = seed_tasks or self._default_seed_tasks()
        logger.info(f"Self-Instruct Generator initialized with {len(self.seed_tasks)} seeds")

    def _default_seed_tasks(self) -> List[Dict]:
        """Default seed tasks for bootstrapping"""
        return [
            {
                "instruction": "Write a Python function to find the largest number in a list",
                "input": "[3, 1, 4, 1, 5, 9, 2, 6]",
                "output": "def find_largest(lst):\n    return max(lst)\n\nresult = find_largest([3, 1, 4, 1, 5, 9, 2, 6])  # Returns 9",
            },
            {
                "instruction": "Explain the difference between a list and a tuple in Python",
                "input": "",
                "output": "Lists are mutable (can be modified after creation) while tuples are immutable. Lists use square brackets [], tuples use parentheses (). Tuples are hashable and can be dictionary keys, lists cannot.",
            },
            {
                "instruction": "Write a regex pattern to validate an email address",
                "input": "",
                "output": "r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'",
            },
            {
                "instruction": "Fix the bug in this Python code that should sum numbers",
                "input": "def sum_numbers(numbers):\n    total = 0\n    for n in numbers\n        total += n\n    return total",
                "output": "The code is missing a colon after 'for n in numbers'. Fixed:\n\ndef sum_numbers(numbers):\n    total = 0\n    for n in numbers:  # Added colon here\n        total += n\n    return total",
            },
        ]

    def generate_instruction_prompt(self) -> str:
        """Generate a meta-prompt for creating new instructions"""
        samples = random.sample(self.seed_tasks, min(3, len(self.seed_tasks)))

        prompt = """Generate a new coding task instruction. The instruction should be:
- Clear and specific
- Achievable with code
- Different from the examples below

Examples:
"""
        for i, sample in enumerate(samples, 1):
            prompt += f"\n{i}. {sample['instruction']}"

        prompt += "\n\nGenerate a new, different instruction:"
        return prompt


class EvolInstructGenerator:
    """Evolve instructions to higher complexity using Evol-Instruct methodology"""

    EVOLUTION_STRATEGIES = [
        "add_constraints",
        "increase_depth",
        "add_reasoning",
        "complicate_input",
        "in_breadth",
    ]

    def __init__(self):
        logger.info("Evol-Instruct Generator initialized")

    def get_evolution_prompt(
        self,
        instruction: str,
        strategy: Optional[str] = None,
    ) -> str:
        """Generate prompt to evolve an instruction"""
        strategy = strategy or random.choice(self.EVOLUTION_STRATEGIES)

        evolution_prompts = {
            "add_constraints": f"""Rewrite this instruction to add more constraints or requirements:

Original: {instruction}

Make it more specific by adding constraints like:
- Time or space complexity requirements
- Edge case handling
- Specific format requirements

Evolved instruction:""",

            "increase_depth": f"""Rewrite this instruction to require deeper understanding:

Original: {instruction}

Increase the complexity by:
- Requiring explanation of tradeoffs
- Adding multi-step reasoning
- Requiring consideration of alternatives

Evolved instruction:""",

            "add_reasoning": f"""Rewrite this instruction to require step-by-step reasoning:

Original: {instruction}

Add requirements for:
- Explaining the approach
- Justifying design decisions
- Considering edge cases

Evolved instruction:""",

            "complicate_input": f"""Rewrite this instruction with more complex input requirements:

Original: {instruction}

Complicate by:
- Adding nested data structures
- Requiring handling of multiple input types
- Adding error handling requirements

Evolved instruction:""",

            "in_breadth": f"""Create a related but different instruction inspired by:

Original: {instruction}

Create a new instruction that:
- Addresses a related but different problem
- Uses similar skills but different application
- Has comparable complexity

New instruction:""",
        }

        return evolution_prompts.get(strategy, evolution_prompts["add_constraints"])


class SyntheticDataGenerator:
    """
    Main class for generating synthetic training data.

    Combines multiple strategies to create diverse, high-quality training examples.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        teacher_model_fn: Optional[Callable] = None,
    ):
        self.output_dir = output_dir or SYNTHETIC_DATA_STATE / "generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.teacher_model_fn = teacher_model_fn
        self.template_library = PromptTemplateLibrary()
        self.self_instruct = SelfInstructGenerator()
        self.evol_instruct = EvolInstructGenerator()

        self.generated: List[SyntheticExample] = []
        self.stats = {
            "total_generated": 0,
            "passed_quality": 0,
            "by_category": {},
            "by_strategy": {},
        }

        logger.info(f"Synthetic Data Generator initialized: {self.output_dir}")

    async def generate_batch(
        self,
        config: GenerationConfig,
        progress_callback: Optional[Callable] = None,
    ) -> List[SyntheticExample]:
        """Generate a batch of synthetic examples"""
        logger.info(f"Generating {config.target_examples} synthetic examples")

        examples = []
        examples_per_category = config.target_examples // len(config.categories)

        for category in config.categories:
            for _ in range(examples_per_category):
                strategy = random.choice(config.strategies)

                example = await self._generate_single(
                    category=category,
                    strategy=strategy,
                    config=config,
                )

                if example and example.quality_score >= config.min_quality:
                    examples.append(example)
                    self.stats["passed_quality"] += 1

                self.stats["total_generated"] += 1

                # Rate limiting
                if self.stats["total_generated"] % config.batch_size == 0:
                    if progress_callback:
                        progress_callback(len(examples), config.target_examples)
                    await asyncio.sleep(config.rate_limit_delay)

        self.generated.extend(examples)
        logger.info(
            f"Generated {len(examples)} examples "
            f"({self.stats['passed_quality']}/{self.stats['total_generated']} passed quality)"
        )

        return examples

    async def _generate_single(
        self,
        category: TaskCategory,
        strategy: GenerationStrategy,
        config: GenerationConfig,
    ) -> Optional[SyntheticExample]:
        """Generate a single synthetic example"""
        try:
            # Generate prompt based on strategy
            if strategy == GenerationStrategy.SELF_INSTRUCT:
                prompt, complexity = await self._self_instruct_generate(category)
            elif strategy == GenerationStrategy.EVOL_INSTRUCT:
                prompt, complexity = await self._evol_instruct_generate(category, config)
            elif strategy == GenerationStrategy.SEED_EXPANSION:
                prompt, complexity = self.template_library.generate_prompt(category)
            else:
                prompt, complexity = self.template_library.generate_prompt(category)

            if not prompt:
                return None

            # Generate response from teacher model
            response = await self._generate_response(prompt)
            if not response:
                return None

            # Calculate quality score
            quality_score = self._assess_quality(prompt, response)

            # Create example
            example = SyntheticExample(
                id=self._generate_id(prompt, response),
                prompt=prompt,
                response=response,
                category=category,
                strategy=strategy,
                complexity=complexity,
                quality_score=quality_score,
                teacher_model=self._get_teacher_model_name(),
                metadata={
                    "prompt_length": len(prompt),
                    "response_length": len(response),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Update stats
            self.stats["by_category"][category.value] = (
                self.stats["by_category"].get(category.value, 0) + 1
            )
            self.stats["by_strategy"][strategy.value] = (
                self.stats["by_strategy"].get(strategy.value, 0) + 1
            )

            return example

        except Exception as e:
            logger.warning(f"Failed to generate example: {e}")
            return None

    async def _self_instruct_generate(
        self,
        category: TaskCategory,
    ) -> Tuple[str, int]:
        """Generate using Self-Instruct methodology"""
        meta_prompt = self.self_instruct.generate_instruction_prompt()

        if self.teacher_model_fn:
            instruction = await self.teacher_model_fn(meta_prompt)
            return instruction, random.randint(2, 4)
        else:
            # Fallback to template-based generation
            return self.template_library.generate_prompt(category)

    async def _evol_instruct_generate(
        self,
        category: TaskCategory,
        config: GenerationConfig,
    ) -> Tuple[str, int]:
        """Generate using Evol-Instruct methodology"""
        # Start with a base instruction
        base_prompt, base_complexity = self.template_library.generate_prompt(category)
        if not base_prompt:
            return None, 0

        # Evolve to higher complexity if we haven't hit max
        target_complexity = min(base_complexity + 1, config.max_complexity)

        if self.teacher_model_fn and target_complexity > base_complexity:
            evol_prompt = self.evol_instruct.get_evolution_prompt(base_prompt)
            evolved = await self.teacher_model_fn(evol_prompt)
            return evolved, target_complexity

        return base_prompt, base_complexity

    async def _generate_response(self, prompt: str) -> Optional[str]:
        """Generate response from teacher model"""
        if self.teacher_model_fn:
            try:
                return await self.teacher_model_fn(prompt)
            except Exception as e:
                logger.warning(f"Teacher model failed: {e}")
                return None
        else:
            # Placeholder response for testing without model
            return f"[Synthetic response for: {prompt[:50]}...]"

    def _assess_quality(self, prompt: str, response: str) -> float:
        """Assess quality of generated example"""
        score = 0.5  # Baseline

        # Length appropriateness
        prompt_len = len(prompt.split())
        response_len = len(response.split())

        if prompt_len >= 5 and prompt_len <= 200:
            score += 0.1
        if response_len >= 20 and response_len <= 2000:
            score += 0.1

        # Contains code if appropriate
        if "```" in prompt or "code" in prompt.lower():
            if "```" in response or re.search(r'def |function |class ', response):
                score += 0.15

        # Response relevance (simple keyword matching)
        prompt_keywords = set(prompt.lower().split())
        response_keywords = set(response.lower().split())
        overlap = len(prompt_keywords & response_keywords) / max(len(prompt_keywords), 1)
        score += min(overlap * 0.15, 0.15)

        return min(score, 1.0)

    def _generate_id(self, prompt: str, response: str) -> str:
        """Generate unique ID for example"""
        content = f"{prompt}|{response}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_teacher_model_name(self) -> str:
        """Get teacher model name"""
        if hasattr(self.teacher_model_fn, "__name__"):
            return self.teacher_model_fn.__name__
        return "unknown"

    def save_examples(
        self,
        format: str = "jsonl",
        filename: Optional[str] = None,
    ) -> Path:
        """Save generated examples to disk"""
        if not self.generated:
            logger.warning("No examples to save")
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = filename or f"synthetic_{timestamp}.{format}"
        output_path = self.output_dir / filename

        if format == "jsonl":
            with open(output_path, "w") as f:
                for example in self.generated:
                    f.write(json.dumps({
                        "id": example.id,
                        "prompt": example.prompt,
                        "response": example.response,
                        "category": example.category.value,
                        "strategy": example.strategy.value,
                        "complexity": example.complexity,
                        "quality_score": example.quality_score,
                        "teacher_model": example.teacher_model,
                        "metadata": example.metadata,
                        "created_at": example.created_at.isoformat(),
                    }) + "\n")

        elif format == "parquet":
            # For larger datasets, Parquet is more efficient
            try:
                import pandas as pd
                df = pd.DataFrame([
                    {
                        "id": ex.id,
                        "prompt": ex.prompt,
                        "response": ex.response,
                        "category": ex.category.value,
                        "strategy": ex.strategy.value,
                        "complexity": ex.complexity,
                        "quality_score": ex.quality_score,
                    }
                    for ex in self.generated
                ])
                df.to_parquet(output_path)
            except ImportError:
                logger.warning("pandas not available, falling back to JSONL")
                return self.save_examples(format="jsonl", filename=filename.replace(".parquet", ".jsonl"))

        logger.info(f"Saved {len(self.generated)} examples to {output_path}")
        return output_path

    def get_stats(self) -> Dict[str, Any]:
        """Get generation statistics"""
        return {
            **self.stats,
            "saved_examples": len(self.generated),
            "quality_pass_rate": (
                self.stats["passed_quality"] / max(self.stats["total_generated"], 1)
            ),
        }


async def main():
    """Test synthetic data generation"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Synthetic Data Generation Test")
    logger.info("=" * 60)

    # Initialize generator (without real model for testing)
    generator = SyntheticDataGenerator()

    # Configure generation
    config = GenerationConfig(
        target_examples=20,
        categories=[
            TaskCategory.CODE_GENERATION,
            TaskCategory.CODE_EXPLANATION,
            TaskCategory.DEBUGGING,
        ],
        strategies=[
            GenerationStrategy.SELF_INSTRUCT,
            GenerationStrategy.SEED_EXPANSION,
        ],
        min_quality=0.5,  # Lower for testing
        batch_size=5,
        rate_limit_delay=0.1,
    )

    # Generate examples
    def progress(current, total):
        logger.info(f"Progress: {current}/{total}")

    examples = await generator.generate_batch(config, progress)

    # Show some examples
    logger.info(f"\nGenerated {len(examples)} examples:")
    for i, example in enumerate(examples[:3]):
        logger.info(f"\n{i+1}. [{example.category.value}] {example.prompt[:80]}...")
        logger.info(f"   Quality: {example.quality_score:.2f}, Complexity: {example.complexity}")

    # Save examples
    output_path = generator.save_examples()
    if output_path:
        logger.info(f"\nSaved to: {output_path}")

    # Show stats
    stats = generator.get_stats()
    logger.info(f"\nStatistics:")
    logger.info(f"  Total generated: {stats['total_generated']}")
    logger.info(f"  Passed quality: {stats['passed_quality']}")
    logger.info(f"  Quality pass rate: {stats['quality_pass_rate']:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
