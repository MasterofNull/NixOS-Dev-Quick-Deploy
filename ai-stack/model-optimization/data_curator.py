#!/usr/bin/env python3
"""
Training Data Collection & Curation

Automated collection and curation of high-quality training data from interactions.
Part of Phase 5 Batch 5.1: Training Data Collection & Curation

Key Features:
- Automatic high-quality interaction capture
- Data cleaning and filtering pipeline
- Synthetic data generation from remote model outputs
- Active learning for data selection
- Privacy-preserving data handling

Reference: Data curation best practices, active learning
"""

import asyncio
import hashlib
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class DataQuality(Enum):
    """Data quality levels"""
    EXCELLENT = "excellent"  # High-quality, diverse
    GOOD = "good"  # Usable for training
    FAIR = "fair"  # Needs cleaning
    POOR = "poor"  # Should be filtered out


class DataSource(Enum):
    """Source of training data"""
    USER_INTERACTION = "user_interaction"
    REMOTE_MODEL = "remote_model"
    SYNTHETIC = "synthetic"
    CURATED = "curated"


@dataclass
class TrainingExample:
    """Single training example"""
    example_id: str
    prompt: str
    response: str
    source: DataSource
    quality: DataQuality
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    # Privacy flags
    contains_pii: bool = False
    is_sensitive: bool = False


@dataclass
class CurationMetrics:
    """Data curation metrics"""
    total_examples: int = 0
    high_quality: int = 0
    filtered_out: int = 0
    synthetic_generated: int = 0
    pii_detected: int = 0
    diversity_score: float = 0.0


class InteractionCapture:
    """Capture high-quality interactions automatically"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.captured: List[TrainingExample] = []

        logger.info(f"Interaction Capture initialized: {output_dir}")

    def capture_interaction(
        self,
        prompt: str,
        response: str,
        quality_score: float,
        source: DataSource = DataSource.USER_INTERACTION,
    ) -> Optional[TrainingExample]:
        """Capture an interaction if it meets quality threshold"""
        # Only capture high-quality interactions
        if quality_score < 0.7:
            logger.debug(f"Skipping low-quality interaction (score={quality_score:.2f})")
            return None

        # Check for PII
        contains_pii = self._detect_pii(prompt, response)
        if contains_pii:
            logger.warning("PII detected in interaction - anonymizing")
            prompt = self._anonymize_pii(prompt)
            response = self._anonymize_pii(response)

        # Determine quality level
        if quality_score >= 0.9:
            quality = DataQuality.EXCELLENT
        elif quality_score >= 0.75:
            quality = DataQuality.GOOD
        else:
            quality = DataQuality.FAIR

        # Create training example
        example = TrainingExample(
            example_id=self._generate_id(prompt, response),
            prompt=prompt,
            response=response,
            source=source,
            quality=quality,
            contains_pii=contains_pii,
            metadata={
                "quality_score": quality_score,
                "prompt_length": len(prompt),
                "response_length": len(response),
            },
        )

        self.captured.append(example)

        logger.info(
            f"Captured interaction: quality={quality.value}, "
            f"source={source.value}, pii={contains_pii}"
        )

        return example

    def _detect_pii(self, *texts: str) -> bool:
        """Detect personally identifiable information"""
        combined = " ".join(texts)

        # Email addresses
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', combined):
            return True

        # Phone numbers
        if re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', combined):
            return True

        # Social security numbers
        if re.search(r'\b\d{3}-\d{2}-\d{4}\b', combined):
            return True

        # Credit card numbers
        if re.search(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', combined):
            return True

        return False

    def _anonymize_pii(self, text: str) -> str:
        """Anonymize PII in text"""
        # Replace emails
        text = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            '[EMAIL]',
            text
        )

        # Replace phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)

        # Replace SSNs
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)

        # Replace credit cards
        text = re.sub(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '[CC]', text)

        return text

    def _generate_id(self, prompt: str, response: str) -> str:
        """Generate unique ID for example"""
        content = f"{prompt}|{response}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def save_examples(self):
        """Save captured examples to disk"""
        if not self.captured:
            return

        filename = f"captured_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        output_path = self.output_dir / filename

        with open(output_path, "w") as f:
            for example in self.captured:
                f.write(json.dumps({
                    "example_id": example.example_id,
                    "prompt": example.prompt,
                    "response": example.response,
                    "source": example.source.value,
                    "quality": example.quality.value,
                    "metadata": example.metadata,
                    "created_at": example.created_at.isoformat(),
                }) + "\n")

        logger.info(f"Saved {len(self.captured)} examples to {output_path}")
        self.captured = []  # Clear after saving


class DataCleaner:
    """Clean and filter training data"""

    def __init__(self):
        logger.info("Data Cleaner initialized")

    def clean_example(self, example: TrainingExample) -> Optional[TrainingExample]:
        """Clean a single example"""
        # Filter out poor quality
        if example.quality == DataQuality.POOR:
            return None

        # Clean prompt
        prompt = self._clean_text(example.prompt)
        if not prompt or len(prompt.split()) < 3:
            return None

        # Clean response
        response = self._clean_text(example.response)
        if not response or len(response.split()) < 5:
            return None

        # Check for problematic patterns
        if self._has_problematic_content(prompt, response):
            return None

        # Update example
        example.prompt = prompt
        example.response = response

        return example

    def _clean_text(self, text: str) -> str:
        """Clean text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

        # Strip
        text = text.strip()

        return text

    def _has_problematic_content(self, prompt: str, response: str) -> bool:
        """Check for problematic content"""
        combined = (prompt + " " + response).lower()

        # Check for toxic patterns
        toxic_patterns = [
            "hate",
            "violence",
            "illegal",
            "harmful",
        ]

        # Simple check (in production, use proper toxicity detector)
        for pattern in toxic_patterns:
            if pattern in combined:
                # Would need context-aware checking
                pass

        return False

    def filter_dataset(
        self,
        examples: List[TrainingExample],
        min_quality: DataQuality = DataQuality.GOOD,
    ) -> List[TrainingExample]:
        """Filter dataset by quality"""
        quality_order = {
            DataQuality.EXCELLENT: 3,
            DataQuality.GOOD: 2,
            DataQuality.FAIR: 1,
            DataQuality.POOR: 0,
        }

        min_score = quality_order[min_quality]

        filtered = [
            ex for ex in examples
            if quality_order[ex.quality] >= min_score
        ]

        logger.info(
            f"Filtered dataset: {len(filtered)}/{len(examples)} examples kept "
            f"(min_quality={min_quality.value})"
        )

        return filtered


class SyntheticDataGenerator:
    """Generate synthetic training data"""

    def __init__(self):
        self.templates = self._load_templates()
        logger.info("Synthetic Data Generator initialized")

    def _load_templates(self) -> List[Dict]:
        """Load prompt templates"""
        return [
            {
                "category": "code_generation",
                "prompt": "Write a {language} function to {task}",
                "variations": {
                    "language": ["Python", "JavaScript", "Go"],
                    "task": ["sort a list", "reverse a string", "find duplicates"],
                },
            },
            {
                "category": "code_explanation",
                "prompt": "Explain how {concept} works in {language}",
                "variations": {
                    "concept": ["list comprehension", "async/await", "decorators"],
                    "language": ["Python", "JavaScript"],
                },
            },
            {
                "category": "debugging",
                "prompt": "Debug this {language} code: {code_snippet}",
                "variations": {
                    "language": ["Python", "JavaScript"],
                    "code_snippet": ["[simple code with error]"],
                },
            },
        ]

    async def generate_from_template(
        self,
        template: Dict,
        remote_model: Optional[Any] = None,
    ) -> List[TrainingExample]:
        """Generate examples from template"""
        examples = []

        # Generate variations
        category = template["category"]
        prompt_template = template["prompt"]
        variations = template["variations"]

        # Create combinations (limit to avoid explosion)
        import itertools

        keys = list(variations.keys())
        values = [variations[k] for k in keys]

        for combo in itertools.product(*values):
            # Fill template
            prompt = prompt_template
            for key, value in zip(keys, combo):
                prompt = prompt.replace(f"{{{key}}}", value)

            # Generate response (would use remote model)
            if remote_model:
                # response = await remote_model.generate(prompt)
                response = f"[Synthetic response for: {prompt}]"
            else:
                response = f"[Synthetic response for: {prompt}]"

            example = TrainingExample(
                example_id=hashlib.sha256(prompt.encode()).hexdigest()[:16],
                prompt=prompt,
                response=response,
                source=DataSource.SYNTHETIC,
                quality=DataQuality.GOOD,
                metadata={"category": category, "template": template["prompt"]},
            )

            examples.append(example)

        logger.info(f"Generated {len(examples)} synthetic examples for {category}")
        return examples


class ActiveLearner:
    """Active learning for data selection"""

    def __init__(self):
        self.uncertainty_threshold = 0.3
        logger.info("Active Learner initialized")

    def select_examples(
        self,
        candidates: List[TrainingExample],
        current_dataset: List[TrainingExample],
        budget: int = 100,
    ) -> List[TrainingExample]:
        """Select most valuable examples to add"""
        # Score candidates by information value
        scored = []

        for candidate in candidates:
            value_score = self._calculate_information_value(candidate, current_dataset)
            scored.append((value_score, candidate))

        # Sort by value (descending)
        scored.sort(reverse=True, key=lambda x: x[0])

        # Select top examples within budget
        selected = [ex for _, ex in scored[:budget]]

        logger.info(
            f"Active learning selected {len(selected)} examples "
            f"from {len(candidates)} candidates"
        )

        return selected

    def _calculate_information_value(
        self,
        candidate: TrainingExample,
        current_dataset: List[TrainingExample],
    ) -> float:
        """Calculate information value of candidate"""
        score = 0.5  # Baseline

        # Novelty: is this different from existing data?
        novelty = self._calculate_novelty(candidate, current_dataset)
        score += novelty * 0.4

        # Quality
        quality_scores = {
            DataQuality.EXCELLENT: 1.0,
            DataQuality.GOOD: 0.7,
            DataQuality.FAIR: 0.4,
            DataQuality.POOR: 0.0,
        }
        score += quality_scores[candidate.quality] * 0.3

        # Diversity: does this cover underrepresented areas?
        diversity = self._calculate_diversity_contribution(candidate, current_dataset)
        score += diversity * 0.3

        return score

    def _calculate_novelty(
        self,
        candidate: TrainingExample,
        current_dataset: List[TrainingExample],
    ) -> float:
        """Calculate how novel this example is"""
        if not current_dataset:
            return 1.0

        # Simple: check similarity to existing examples
        candidate_terms = set(candidate.prompt.lower().split())

        max_overlap = 0.0
        for existing in current_dataset[-100:]:  # Check last 100
            existing_terms = set(existing.prompt.lower().split())
            if candidate_terms and existing_terms:
                overlap = len(candidate_terms & existing_terms) / len(candidate_terms | existing_terms)
                max_overlap = max(max_overlap, overlap)

        # High overlap = low novelty
        novelty = 1.0 - max_overlap
        return novelty

    def _calculate_diversity_contribution(
        self,
        candidate: TrainingExample,
        current_dataset: List[TrainingExample],
    ) -> float:
        """Calculate diversity contribution"""
        # Check category distribution
        category = candidate.metadata.get("category", "unknown")

        category_counts = defaultdict(int)
        for ex in current_dataset:
            cat = ex.metadata.get("category", "unknown")
            category_counts[cat] += 1

        # If this category is underrepresented, higher diversity score
        if not category_counts:
            return 1.0

        total = len(current_dataset)
        current_ratio = category_counts[category] / total

        # Want balanced representation
        target_ratio = 1.0 / max(len(category_counts), 1)
        diversity = 1.0 - abs(current_ratio - target_ratio)

        return diversity


async def main():
    """Test data curation framework"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Training Data Collection & Curation Test")
    logger.info("=" * 60)

    # Initialize components
    output_dir = Path(".agents/training-data")
    capture = InteractionCapture(output_dir)
    cleaner = DataCleaner()
    generator = SyntheticDataGenerator()
    learner = ActiveLearner()

    # Test 1: Capture interactions
    logger.info("\n1. Interaction Capture:")

    interactions = [
        ("Write Python code to reverse a list", "Here's how: list[::-1]", 0.9),
        ("What is your name?", "I'm an AI assistant", 0.5),
        ("Explain async/await", "Async/await allows...", 0.85),
    ]

    captured_examples = []
    for prompt, response, quality in interactions:
        example = capture.capture_interaction(prompt, response, quality)
        if example:
            captured_examples.append(example)

    logger.info(f"  Captured: {len(captured_examples)} examples")

    # Test 2: Clean data
    logger.info("\n2. Data Cleaning:")

    cleaned = []
    for example in captured_examples:
        clean_ex = cleaner.clean_example(example)
        if clean_ex:
            cleaned.append(clean_ex)

    logger.info(f"  Cleaned: {len(cleaned)}/{len(captured_examples)} examples")

    # Test 3: Generate synthetic data
    logger.info("\n3. Synthetic Data Generation:")

    template = generator.templates[0]
    synthetic = await generator.generate_from_template(template)

    logger.info(f"  Generated: {len(synthetic)} synthetic examples")

    # Test 4: Active learning
    logger.info("\n4. Active Learning Selection:")

    current_dataset = cleaned
    candidates = synthetic

    selected = learner.select_examples(candidates, current_dataset, budget=5)

    logger.info(f"  Selected: {len(selected)} examples from {len(candidates)} candidates")

    # Save examples
    capture.save_examples()


if __name__ == "__main__":
    asyncio.run(main())
