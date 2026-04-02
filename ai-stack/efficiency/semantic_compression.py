#!/usr/bin/env python3
"""
Semantic Compression for Long Contexts

Advanced semantic compression techniques for reducing context size while
preserving meaning and relevance.
Part of Phase 7 Batch 7.1: Prompt Compression & Optimization

Key Features:
- Hierarchical summarization for long documents
- Semantic chunking with importance scoring
- Dynamic prompt generation based on task complexity
- A/B testing framework for prompt variants
- Template optimization with usage analytics
- Context relevance filtering

Reference: LLMLingua, Selective Context, Lost in the Middle
"""

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Runtime writable state
SEMANTIC_COMPRESSION_STATE = Path(os.getenv(
    "SEMANTIC_COMPRESSION_STATE",
    "/var/lib/ai-stack/hybrid/semantic-compression"
))


class ImportanceLevel(Enum):
    """Importance levels for content sections"""
    CRITICAL = "critical"  # Must include
    HIGH = "high"  # Should include if space
    MEDIUM = "medium"  # Include if possible
    LOW = "low"  # Can drop
    NOISE = "noise"  # Should drop


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"  # Single-step, clear task
    MODERATE = "moderate"  # Multi-step, straightforward
    COMPLEX = "complex"  # Multi-step, requires reasoning
    EXPERT = "expert"  # Deep domain knowledge needed


@dataclass
class SemanticChunk:
    """A semantically coherent text chunk"""
    id: str
    text: str
    token_count: int
    importance: ImportanceLevel
    relevance_score: float  # 0-1 relevance to query
    position: int  # Original position in document
    metadata: Dict = field(default_factory=dict)


@dataclass
class CompressionPlan:
    """Plan for compressing a document"""
    chunks: List[SemanticChunk]
    target_tokens: int
    total_original_tokens: int
    strategy: str
    keep_chunks: List[str]  # Chunk IDs to keep
    estimated_final_tokens: int


@dataclass
class PromptVariant:
    """A prompt variant for A/B testing"""
    variant_id: str
    name: str
    prompt_template: str
    variables: Dict[str, str]
    token_count: int
    metrics: Dict[str, float] = field(default_factory=dict)
    trials: int = 0
    successes: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ABTestResult:
    """Result of an A/B test"""
    test_id: str
    variant_a: PromptVariant
    variant_b: PromptVariant
    winner: Optional[str]
    confidence: float
    summary: str
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SemanticChunker:
    """Break text into semantically coherent chunks"""

    def __init__(
        self,
        min_chunk_tokens: int = 50,
        max_chunk_tokens: int = 500,
        overlap_tokens: int = 20,
    ):
        self.min_chunk_tokens = min_chunk_tokens
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens
        logger.info("Semantic Chunker initialized")

    def chunk(self, text: str, query: Optional[str] = None) -> List[SemanticChunk]:
        """Break text into semantic chunks with relevance scoring"""
        # First split by major structural elements
        sections = self._split_by_structure(text)

        chunks = []
        for i, section in enumerate(sections):
            # Split large sections further
            if self._estimate_tokens(section) > self.max_chunk_tokens:
                sub_chunks = self._split_by_sentences(section)
            else:
                sub_chunks = [section]

            for j, chunk_text in enumerate(sub_chunks):
                token_count = self._estimate_tokens(chunk_text)

                if token_count < self.min_chunk_tokens:
                    continue

                chunk_id = hashlib.sha256(
                    f"{i}_{j}_{chunk_text[:50]}".encode()
                ).hexdigest()[:12]

                # Score importance and relevance
                importance = self._assess_importance(chunk_text)
                relevance = self._calculate_relevance(chunk_text, query) if query else 0.5

                chunks.append(SemanticChunk(
                    id=chunk_id,
                    text=chunk_text,
                    token_count=token_count,
                    importance=importance,
                    relevance_score=relevance,
                    position=i * 1000 + j,
                ))

        return chunks

    def _split_by_structure(self, text: str) -> List[str]:
        """Split by structural elements (headers, blank lines, etc.)"""
        # Split by double newlines or headers
        patterns = [
            r'\n\n+',  # Blank lines
            r'\n#{1,6}\s',  # Markdown headers
            r'\n={3,}',  # Horizontal rules
        ]

        combined_pattern = '|'.join(f'({p})' for p in patterns)
        sections = re.split(combined_pattern, text)

        # Filter out empty sections and separator matches
        return [s.strip() for s in sections if s and s.strip() and len(s.strip()) > 10]

    def _split_by_sentences(self, text: str) -> List[str]:
        """Split into sentence-based chunks respecting max token limit"""
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            if current_tokens + sentence_tokens > self.max_chunk_tokens:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count"""
        return int(len(text.split()) * 1.3)

    def _assess_importance(self, text: str) -> ImportanceLevel:
        """Assess importance of a chunk"""
        text_lower = text.lower()

        # Critical indicators
        critical_patterns = [
            r'\b(error|exception|failure|crash)\b',
            r'\b(critical|urgent|important|required)\b',
            r'\b(warning|danger|caution)\b',
            r'^(note|important|warning|error):',
        ]

        for pattern in critical_patterns:
            if re.search(pattern, text_lower):
                return ImportanceLevel.CRITICAL

        # High importance indicators
        high_patterns = [
            r'\b(should|must|need|require)\b',
            r'\b(key|main|primary|essential)\b',
            r'^\s*(def|class|function|method)\b',  # Code definitions
        ]

        for pattern in high_patterns:
            if re.search(pattern, text_lower):
                return ImportanceLevel.HIGH

        # Low importance indicators
        low_patterns = [
            r'\b(example|e\.g\.|for instance)\b',
            r'\b(optional|alternatively|also)\b',
            r'^(see also|related|references)',
        ]

        for pattern in low_patterns:
            if re.search(pattern, text_lower):
                return ImportanceLevel.LOW

        # Default to medium
        return ImportanceLevel.MEDIUM

    def _calculate_relevance(self, chunk: str, query: str) -> float:
        """Calculate relevance of chunk to query"""
        if not query:
            return 0.5

        chunk_words = set(chunk.lower().split())
        query_words = set(query.lower().split())

        # Simple word overlap
        if not query_words:
            return 0.5

        overlap = len(chunk_words & query_words)
        relevance = min(1.0, overlap / len(query_words))

        # Boost for exact phrase matches
        if query.lower() in chunk.lower():
            relevance = min(1.0, relevance + 0.3)

        return relevance


class HierarchicalSummarizer:
    """Hierarchical summarization for long documents"""

    def __init__(
        self,
        levels: int = 3,
        summarize_fn: Optional[Callable] = None,
    ):
        self.levels = levels
        self.summarize_fn = summarize_fn
        logger.info(f"Hierarchical Summarizer initialized ({levels} levels)")

    async def summarize(
        self,
        chunks: List[SemanticChunk],
        target_tokens: int,
        level: int = 0,
    ) -> str:
        """Hierarchically summarize chunks to target token count"""
        total_tokens = sum(c.token_count for c in chunks)

        if total_tokens <= target_tokens:
            # Already within target, just concatenate
            return '\n\n'.join(c.text for c in chunks)

        if level >= self.levels:
            # Max levels reached, use extractive summary
            return self._extractive_summary(chunks, target_tokens)

        # Group chunks into sections
        section_size = max(3, len(chunks) // 4)
        sections = [
            chunks[i:i + section_size]
            for i in range(0, len(chunks), section_size)
        ]

        # Summarize each section
        summaries = []
        for section in sections:
            section_text = '\n'.join(c.text for c in section)
            if self.summarize_fn:
                summary = await self.summarize_fn(section_text)
            else:
                summary = self._simple_summarize(section_text)
            summaries.append(summary)

        # Recursively summarize summaries if still too long
        summary_chunks = [
            SemanticChunk(
                id=f"summary_{i}",
                text=s,
                token_count=self._estimate_tokens(s),
                importance=ImportanceLevel.HIGH,
                relevance_score=0.8,
                position=i,
            )
            for i, s in enumerate(summaries)
        ]

        return await self.summarize(summary_chunks, target_tokens, level + 1)

    def _extractive_summary(
        self,
        chunks: List[SemanticChunk],
        target_tokens: int,
    ) -> str:
        """Extract most important sentences to fit target"""
        # Sort by importance and relevance
        importance_order = {
            ImportanceLevel.CRITICAL: 4,
            ImportanceLevel.HIGH: 3,
            ImportanceLevel.MEDIUM: 2,
            ImportanceLevel.LOW: 1,
            ImportanceLevel.NOISE: 0,
        }

        sorted_chunks = sorted(
            chunks,
            key=lambda c: (
                importance_order[c.importance] * 0.4 +
                c.relevance_score * 0.6
            ),
            reverse=True,
        )

        # Take chunks until target reached
        result = []
        current_tokens = 0

        for chunk in sorted_chunks:
            if current_tokens + chunk.token_count <= target_tokens:
                result.append(chunk)
                current_tokens += chunk.token_count

        # Restore original order
        result.sort(key=lambda c: c.position)

        return '\n\n'.join(c.text for c in result)

    def _simple_summarize(self, text: str) -> str:
        """Simple extractive summarization (first and last sentences)"""
        sentences = re.split(r'(?<=[.!?])\s+', text)

        if len(sentences) <= 3:
            return text

        # Keep first, important middle, and last
        important_keywords = {"important", "critical", "key", "must", "should", "error"}
        middle = sentences[1:-1]

        important_middle = [
            s for s in middle
            if any(kw in s.lower() for kw in important_keywords)
        ][:2]

        if not important_middle:
            important_middle = middle[:1]

        return ' '.join([sentences[0]] + important_middle + [sentences[-1]])

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)


class DynamicPromptGenerator:
    """Generate prompts dynamically based on task complexity"""

    def __init__(self):
        self.templates: Dict[TaskComplexity, List[Dict]] = {
            TaskComplexity.SIMPLE: [
                {
                    "format": "concise",
                    "instructions": "{task}",
                    "expected_tokens": 50,
                },
            ],
            TaskComplexity.MODERATE: [
                {
                    "format": "structured",
                    "instructions": "Task: {task}\n\nContext: {context}\n\nOutput: {output_format}",
                    "expected_tokens": 150,
                },
            ],
            TaskComplexity.COMPLEX: [
                {
                    "format": "detailed",
                    "instructions": (
                        "## Task\n{task}\n\n"
                        "## Context\n{context}\n\n"
                        "## Requirements\n{requirements}\n\n"
                        "## Output Format\n{output_format}"
                    ),
                    "expected_tokens": 300,
                },
            ],
            TaskComplexity.EXPERT: [
                {
                    "format": "comprehensive",
                    "instructions": (
                        "## Objective\n{task}\n\n"
                        "## Background\n{context}\n\n"
                        "## Technical Requirements\n{requirements}\n\n"
                        "## Constraints\n{constraints}\n\n"
                        "## Success Criteria\n{criteria}\n\n"
                        "## Expected Output\n{output_format}"
                    ),
                    "expected_tokens": 500,
                },
            ],
        }

        logger.info("Dynamic Prompt Generator initialized")

    def assess_complexity(
        self,
        task: str,
        context: Optional[str] = None,
    ) -> TaskComplexity:
        """Assess task complexity"""
        task_lower = task.lower()

        # Expert indicators
        expert_patterns = [
            r'\b(architect|design|optimize|refactor)\b.*\b(system|architecture|performance)\b',
            r'\b(security|audit|compliance|vulnerability)\b',
            r'\b(distributed|concurrent|scalable)\b',
        ]

        for pattern in expert_patterns:
            if re.search(pattern, task_lower):
                return TaskComplexity.EXPERT

        # Complex indicators
        complex_patterns = [
            r'\b(implement|create|build)\b.*\b(feature|module|service)\b',
            r'\b(debug|fix|resolve)\b.*\b(issue|bug|error)\b',
            r'\b(integrate|connect|combine)\b',
        ]

        for pattern in complex_patterns:
            if re.search(pattern, task_lower):
                return TaskComplexity.COMPLEX

        # Moderate indicators
        moderate_patterns = [
            r'\b(update|modify|change|add)\b',
            r'\b(explain|describe|document)\b',
        ]

        for pattern in moderate_patterns:
            if re.search(pattern, task_lower):
                return TaskComplexity.MODERATE

        # Default to simple
        return TaskComplexity.SIMPLE

    def generate(
        self,
        task: str,
        context: Optional[str] = None,
        requirements: Optional[str] = None,
        output_format: Optional[str] = None,
        constraints: Optional[str] = None,
        criteria: Optional[str] = None,
        force_complexity: Optional[TaskComplexity] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate dynamic prompt based on task"""
        complexity = force_complexity or self.assess_complexity(task, context)

        templates = self.templates[complexity]
        template = templates[0]  # Use first template for now

        # Build variables
        variables = {
            "task": task,
            "context": context or "No additional context provided.",
            "requirements": requirements or "Follow best practices.",
            "output_format": output_format or "Provide a clear, well-structured response.",
            "constraints": constraints or "None specified.",
            "criteria": criteria or "Correctness and clarity.",
        }

        # Format prompt
        prompt = template["instructions"]
        for var, value in variables.items():
            prompt = prompt.replace(f"{{{var}}}", value)

        metadata = {
            "complexity": complexity.value,
            "format": template["format"],
            "expected_tokens": template["expected_tokens"],
            "actual_tokens": int(len(prompt.split()) * 1.3),
        }

        return prompt, metadata


class PromptABTester:
    """A/B testing framework for prompt variants"""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        min_trials: int = 20,
        confidence_threshold: float = 0.95,
    ):
        self.output_dir = output_dir or SEMANTIC_COMPRESSION_STATE / "ab-tests"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.min_trials = min_trials
        self.confidence_threshold = confidence_threshold

        self.tests: Dict[str, Dict] = {}
        self.variants: Dict[str, PromptVariant] = {}

        logger.info("Prompt A/B Tester initialized")

    def create_variant(
        self,
        name: str,
        prompt_template: str,
        variables: Optional[Dict] = None,
    ) -> PromptVariant:
        """Create a prompt variant"""
        variant_id = hashlib.sha256(
            f"{name}_{prompt_template[:50]}".encode()
        ).hexdigest()[:12]

        variant = PromptVariant(
            variant_id=variant_id,
            name=name,
            prompt_template=prompt_template,
            variables=variables or {},
            token_count=int(len(prompt_template.split()) * 1.3),
        )

        self.variants[variant_id] = variant
        return variant

    def create_test(
        self,
        test_name: str,
        variant_a: PromptVariant,
        variant_b: PromptVariant,
    ) -> str:
        """Create an A/B test between two variants"""
        test_id = hashlib.sha256(
            f"{test_name}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        self.tests[test_id] = {
            "test_id": test_id,
            "name": test_name,
            "variant_a": variant_a.variant_id,
            "variant_b": variant_b.variant_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

        logger.info(f"Created A/B test {test_id}: {test_name}")
        return test_id

    def record_result(
        self,
        test_id: str,
        variant_id: str,
        success: bool,
        metrics: Optional[Dict[str, float]] = None,
    ):
        """Record a trial result"""
        if test_id not in self.tests:
            return

        variant = self.variants.get(variant_id)
        if not variant:
            return

        variant.trials += 1
        if success:
            variant.successes += 1

        if metrics:
            for key, value in metrics.items():
                if key not in variant.metrics:
                    variant.metrics[key] = []
                if isinstance(variant.metrics[key], list):
                    variant.metrics[key].append(value)

    def evaluate_test(self, test_id: str) -> Optional[ABTestResult]:
        """Evaluate A/B test results"""
        test = self.tests.get(test_id)
        if not test:
            return None

        variant_a = self.variants.get(test["variant_a"])
        variant_b = self.variants.get(test["variant_b"])

        if not variant_a or not variant_b:
            return None

        # Check minimum trials
        total_trials = variant_a.trials + variant_b.trials
        if total_trials < self.min_trials:
            return ABTestResult(
                test_id=test_id,
                variant_a=variant_a,
                variant_b=variant_b,
                winner=None,
                confidence=0.0,
                summary=f"Insufficient trials ({total_trials}/{self.min_trials})",
            )

        # Calculate success rates
        rate_a = variant_a.successes / variant_a.trials if variant_a.trials > 0 else 0
        rate_b = variant_b.successes / variant_b.trials if variant_b.trials > 0 else 0

        # Simple z-test for proportion difference
        pooled_rate = (variant_a.successes + variant_b.successes) / total_trials
        se = math.sqrt(pooled_rate * (1 - pooled_rate) * (1/variant_a.trials + 1/variant_b.trials))

        if se > 0:
            z = abs(rate_a - rate_b) / se
            # Approximate p-value from z-score
            confidence = 1 - math.exp(-0.5 * z * z) * (1 + 0.2316419 * z)
        else:
            confidence = 0.0

        # Determine winner
        if confidence >= self.confidence_threshold:
            winner = variant_a.name if rate_a > rate_b else variant_b.name
            test["status"] = "completed"
        else:
            winner = None

        summary = (
            f"A ({variant_a.name}): {rate_a:.1%} ({variant_a.trials} trials), "
            f"B ({variant_b.name}): {rate_b:.1%} ({variant_b.trials} trials). "
            f"Confidence: {confidence:.1%}"
        )

        if winner:
            summary += f". Winner: {winner}"

        return ABTestResult(
            test_id=test_id,
            variant_a=variant_a,
            variant_b=variant_b,
            winner=winner,
            confidence=confidence,
            summary=summary,
        )

    def get_variant_to_test(self, test_id: str) -> Optional[str]:
        """Get which variant to use for next trial (balanced allocation)"""
        test = self.tests.get(test_id)
        if not test:
            return None

        variant_a = self.variants.get(test["variant_a"])
        variant_b = self.variants.get(test["variant_b"])

        if not variant_a or not variant_b:
            return None

        # Return variant with fewer trials
        if variant_a.trials <= variant_b.trials:
            return variant_a.variant_id
        return variant_b.variant_id


class SemanticCompressor:
    """
    Main semantic compression orchestrator.

    Combines chunking, hierarchical summarization, dynamic generation,
    and A/B testing for optimal prompt compression.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        summarize_fn: Optional[Callable] = None,
    ):
        self.output_dir = output_dir or SEMANTIC_COMPRESSION_STATE
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.chunker = SemanticChunker()
        self.summarizer = HierarchicalSummarizer(summarize_fn=summarize_fn)
        self.prompt_generator = DynamicPromptGenerator()
        self.ab_tester = PromptABTester(output_dir=self.output_dir)

        # Statistics
        self.stats = {
            "compressions": 0,
            "total_tokens_saved": 0,
            "avg_compression_ratio": 0.0,
        }

        logger.info(f"Semantic Compressor initialized: {self.output_dir}")

    async def compress(
        self,
        text: str,
        target_tokens: int,
        query: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Compress text to target token count"""
        original_tokens = self._estimate_tokens(text)

        if original_tokens <= target_tokens:
            return text, {
                "original_tokens": original_tokens,
                "final_tokens": original_tokens,
                "compression_ratio": 1.0,
                "method": "none_needed",
            }

        # Chunk the text
        chunks = self.chunker.chunk(text, query)

        # Create compression plan
        plan = self._create_compression_plan(chunks, target_tokens)

        # Apply hierarchical summarization
        compressed = await self.summarizer.summarize(
            [c for c in chunks if c.id in plan.keep_chunks],
            target_tokens,
        )

        final_tokens = self._estimate_tokens(compressed)
        compression_ratio = final_tokens / original_tokens if original_tokens > 0 else 1.0

        # Update stats
        self.stats["compressions"] += 1
        self.stats["total_tokens_saved"] += original_tokens - final_tokens
        self.stats["avg_compression_ratio"] = (
            0.9 * self.stats["avg_compression_ratio"] + 0.1 * compression_ratio
        )

        metadata = {
            "original_tokens": original_tokens,
            "final_tokens": final_tokens,
            "compression_ratio": compression_ratio,
            "tokens_saved": original_tokens - final_tokens,
            "chunks_kept": len(plan.keep_chunks),
            "chunks_dropped": len(chunks) - len(plan.keep_chunks),
            "method": "semantic_hierarchical",
        }

        return compressed, metadata

    def _create_compression_plan(
        self,
        chunks: List[SemanticChunk],
        target_tokens: int,
    ) -> CompressionPlan:
        """Create plan for which chunks to keep"""
        importance_order = {
            ImportanceLevel.CRITICAL: 4,
            ImportanceLevel.HIGH: 3,
            ImportanceLevel.MEDIUM: 2,
            ImportanceLevel.LOW: 1,
            ImportanceLevel.NOISE: 0,
        }

        # Score chunks
        scored = sorted(
            chunks,
            key=lambda c: (
                importance_order[c.importance] * 0.4 +
                c.relevance_score * 0.6
            ),
            reverse=True,
        )

        # Select chunks to keep
        keep_chunks = []
        current_tokens = 0

        for chunk in scored:
            if current_tokens + chunk.token_count <= target_tokens:
                keep_chunks.append(chunk.id)
                current_tokens += chunk.token_count

        return CompressionPlan(
            chunks=chunks,
            target_tokens=target_tokens,
            total_original_tokens=sum(c.token_count for c in chunks),
            strategy="importance_relevance",
            keep_chunks=keep_chunks,
            estimated_final_tokens=current_tokens,
        )

    def generate_dynamic_prompt(
        self,
        task: str,
        context: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate dynamic prompt based on task complexity"""
        return self.prompt_generator.generate(
            task=task,
            context=context,
            **kwargs,
        )

    def create_ab_test(
        self,
        name: str,
        prompt_a: str,
        prompt_b: str,
    ) -> str:
        """Create A/B test for prompt variants"""
        variant_a = self.ab_tester.create_variant(f"{name}_A", prompt_a)
        variant_b = self.ab_tester.create_variant(f"{name}_B", prompt_b)

        return self.ab_tester.create_test(name, variant_a, variant_b)

    def record_ab_result(
        self,
        test_id: str,
        variant_id: str,
        success: bool,
        metrics: Optional[Dict] = None,
    ):
        """Record A/B test result"""
        self.ab_tester.record_result(test_id, variant_id, success, metrics)

    def evaluate_ab_test(self, test_id: str) -> Optional[ABTestResult]:
        """Evaluate A/B test"""
        return self.ab_tester.evaluate_test(test_id)

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)

    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics"""
        return {
            **self.stats,
            "avg_tokens_saved_per_compression": (
                self.stats["total_tokens_saved"] / max(self.stats["compressions"], 1)
            ),
        }


async def main():
    """Test semantic compression"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Semantic Compression Test")
    logger.info("=" * 60)

    # Create compressor
    compressor = SemanticCompressor()

    # Test long text compression
    long_text = """
    # Introduction to Machine Learning

    Machine learning is a subset of artificial intelligence that enables systems
    to learn and improve from experience without being explicitly programmed.

    ## Supervised Learning

    Supervised learning is the most common type of machine learning. In supervised
    learning, the algorithm learns from labeled training data, and makes predictions
    based on that data. The key characteristic is that the training data includes
    the desired output, called the label or target.

    Important: Supervised learning requires high-quality labeled data for training.

    Examples include:
    - Classification: Predicting categories (spam/not spam)
    - Regression: Predicting continuous values (house prices)

    ## Unsupervised Learning

    In unsupervised learning, the algorithm works on unlabeled data. The system
    tries to learn the patterns and structure from the data without any guidance.

    Warning: Unsupervised learning can be challenging to evaluate since there's
    no ground truth to compare against.

    Common techniques include:
    - Clustering: Grouping similar data points
    - Dimensionality reduction: Reducing features while preserving information

    ## Deep Learning

    Deep learning is a subset of machine learning that uses neural networks with
    many layers. These deep neural networks can automatically learn hierarchical
    representations of data.

    Critical: Deep learning requires significant computational resources and
    large amounts of training data to be effective.

    Applications include:
    - Computer vision
    - Natural language processing
    - Speech recognition

    ## Conclusion

    Machine learning continues to evolve rapidly, with new techniques and
    applications emerging regularly. Understanding the fundamentals is
    essential for anyone working in data science or AI.
    """

    # Compress to target
    compressed, metadata = await compressor.compress(
        long_text,
        target_tokens=200,
        query="deep learning neural networks",
    )

    logger.info("\n1. Text Compression:")
    logger.info(f"  Original tokens: {metadata['original_tokens']}")
    logger.info(f"  Final tokens: {metadata['final_tokens']}")
    logger.info(f"  Compression ratio: {metadata['compression_ratio']:.2f}")
    logger.info(f"  Tokens saved: {metadata['tokens_saved']}")
    logger.info(f"\n  Compressed text preview:\n  {compressed[:300]}...")

    # Test dynamic prompt generation
    logger.info("\n2. Dynamic Prompt Generation:")

    prompts = [
        ("Fix the typo in line 5", None),
        ("Implement user authentication with OAuth2", "React frontend"),
        ("Design a scalable microservice architecture for payment processing", "High availability required"),
    ]

    for task, context in prompts:
        prompt, meta = compressor.generate_dynamic_prompt(task, context)
        logger.info(f"\n  Task: {task[:50]}...")
        logger.info(f"  Complexity: {meta['complexity']}")
        logger.info(f"  Tokens: {meta['actual_tokens']}")

    # Test A/B testing
    logger.info("\n3. A/B Testing:")

    test_id = compressor.create_ab_test(
        "concise_vs_detailed",
        "Explain X briefly.",
        "Please provide a detailed explanation of X, including examples and context.",
    )

    # Simulate results
    import random
    for _ in range(25):
        variant_id = compressor.ab_tester.get_variant_to_test(test_id)
        success = random.random() < (0.8 if "A" in variant_id else 0.7)
        compressor.record_ab_result(test_id, variant_id, success)

    result = compressor.evaluate_ab_test(test_id)
    logger.info(f"  {result.summary}")

    # Show stats
    stats = compressor.get_stats()
    logger.info(f"\n4. Overall Stats:")
    logger.info(f"  Total compressions: {stats['compressions']}")
    logger.info(f"  Total tokens saved: {stats['total_tokens_saved']}")
    logger.info(f"  Avg compression ratio: {stats['avg_compression_ratio']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
