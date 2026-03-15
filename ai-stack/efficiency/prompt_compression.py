#!/usr/bin/env python3
"""
Prompt Compression & Optimization Framework

Minimize token usage through intelligent prompt compression and optimization.
Part of Phase 7 Batch 7.1: Prompt Compression & Optimization

Key Features:
- LLMLingua-inspired prompt compression
- Semantic compression for long contexts
- Prompt template optimization
- Dynamic prompt generation based on task complexity
- A/B testing framework for prompt variants

Reference: LLMLingua (https://arxiv.org/abs/2310.05736)
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


class CompressionStrategy(Enum):
    """Prompt compression strategies"""
    REMOVE_STOPWORDS = "remove_stopwords"
    ABBREVIATE = "abbreviate"
    SEMANTIC_CHUNK = "semantic_chunk"
    SUMMARIZE = "summarize"
    TEMPLATE_VARS = "template_vars"


@dataclass
class CompressionResult:
    """Result of prompt compression"""
    original_text: str
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    strategy: CompressionStrategy
    metadata: Dict = field(default_factory=dict)

    def savings_pct(self) -> float:
        """Calculate token savings percentage"""
        if self.original_tokens == 0:
            return 0.0
        return ((self.original_tokens - self.compressed_tokens) / self.original_tokens) * 100


@dataclass
class PromptTemplate:
    """Optimized prompt template"""
    template_id: str
    name: str
    template: str
    variables: List[str]
    avg_tokens: int
    success_rate: float = 0.0
    usage_count: int = 0


@dataclass
class ABTestResult:
    """A/B test result for prompt variants"""
    test_id: str
    variant_a: str
    variant_b: str
    variant_a_tokens: int
    variant_b_tokens: int
    variant_a_success: int
    variant_b_success: int
    variant_a_trials: int
    variant_b_trials: int
    winner: Optional[str] = None


class PromptCompressor:
    """Compress prompts to reduce token usage"""

    def __init__(self):
        self.stopwords = self._load_stopwords()
        self.abbreviations = self._load_abbreviations()
        logger.info("Prompt Compressor initialized")

    def _load_stopwords(self) -> Set[str]:
        """Load common stopwords"""
        # English stopwords (subset for compression)
        return {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "been", "be", "have", "has", "had", "do", "does", "did", "will",
            "would", "should", "could", "may", "might", "must", "can",
        }

    def _load_abbreviations(self) -> Dict[str, str]:
        """Load abbreviation mappings"""
        return {
            "because": "bc",
            "without": "w/o",
            "with": "w/",
            "you": "u",
            "are": "r",
            "for example": "e.g.",
            "that is": "i.e.",
            "approximately": "~",
            "function": "fn",
            "variable": "var",
            "parameter": "param",
            "configuration": "config",
            "implementation": "impl",
            "documentation": "docs",
            "repository": "repo",
            "application": "app",
            "development": "dev",
            "production": "prod",
            "environment": "env",
        }

    def compress(
        self,
        text: str,
        strategy: CompressionStrategy = CompressionStrategy.REMOVE_STOPWORDS,
        max_tokens: Optional[int] = None,
    ) -> CompressionResult:
        """Compress prompt text"""
        original_tokens = self._estimate_tokens(text)

        if strategy == CompressionStrategy.REMOVE_STOPWORDS:
            compressed = self._remove_stopwords(text)

        elif strategy == CompressionStrategy.ABBREVIATE:
            compressed = self._abbreviate(text)

        elif strategy == CompressionStrategy.SEMANTIC_CHUNK:
            compressed = self._semantic_chunk(text, max_tokens)

        elif strategy == CompressionStrategy.SUMMARIZE:
            compressed = self._summarize(text, max_tokens)

        elif strategy == CompressionStrategy.TEMPLATE_VARS:
            compressed = self._extract_template_vars(text)

        else:
            compressed = text

        compressed_tokens = self._estimate_tokens(compressed)

        return CompressionResult(
            original_text=text,
            compressed_text=compressed,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            strategy=strategy,
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (simple heuristic)"""
        # Rough estimate: ~1.3 tokens per word for English
        words = len(text.split())
        return int(words * 1.3)

    def _remove_stopwords(self, text: str) -> str:
        """Remove stopwords while preserving meaning"""
        words = text.split()
        filtered = []

        for i, word in enumerate(words):
            word_lower = word.lower().strip(".,!?;:")

            # Keep first/last words
            if i == 0 or i == len(words) - 1:
                filtered.append(word)
                continue

            # Keep if not a stopword
            if word_lower not in self.stopwords:
                filtered.append(word)

        return " ".join(filtered)

    def _abbreviate(self, text: str) -> str:
        """Apply abbreviations"""
        compressed = text

        # Apply abbreviation mappings (case-insensitive)
        for full, abbr in self.abbreviations.items():
            pattern = re.compile(re.escape(full), re.IGNORECASE)
            compressed = pattern.sub(abbr, compressed)

        return compressed

    def _semantic_chunk(self, text: str, max_tokens: Optional[int]) -> str:
        """Chunk by semantic units (sentences)"""
        if not max_tokens:
            return text

        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            if current_tokens + sentence_tokens <= max_tokens:
                chunks.append(sentence)
                current_tokens += sentence_tokens
            else:
                break

        return " ".join(chunks)

    def _summarize(self, text: str, max_tokens: Optional[int]) -> str:
        """Extractive summarization (keep key sentences)"""
        if not max_tokens or self._estimate_tokens(text) <= max_tokens:
            return text

        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Score sentences by importance (simple: length and keyword presence)
        scored_sentences = []
        keywords = {"important", "critical", "must", "required", "should", "error", "warning"}

        for sentence in sentences:
            score = len(sentence.split())  # Length score
            if any(kw in sentence.lower() for kw in keywords):
                score *= 2  # Boost keyword sentences

            scored_sentences.append((score, sentence))

        # Sort by score and keep top sentences
        scored_sentences.sort(reverse=True, key=lambda x: x[0])

        result = []
        current_tokens = 0

        for score, sentence in scored_sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            if current_tokens + sentence_tokens <= max_tokens:
                result.append(sentence)
                current_tokens += sentence_tokens

        return " ".join(result)

    def _extract_template_vars(self, text: str) -> str:
        """Extract variables to create reusable template"""
        # Replace specific values with placeholders
        compressed = text

        # Replace file paths
        compressed = re.sub(r'/[\w/.-]+\.\w+', '{file_path}', compressed)

        # Replace numbers
        compressed = re.sub(r'\b\d+\b', '{number}', compressed)

        # Replace quoted strings
        compressed = re.sub(r'"[^"]+"', '{string}', compressed)

        return compressed


class PromptOptimizer:
    """Optimize prompts for efficiency"""

    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_default_templates()
        logger.info("Prompt Optimizer initialized")

    def _load_default_templates(self):
        """Load default optimized templates"""
        # Code analysis template
        self.add_template(PromptTemplate(
            template_id="code_analysis",
            name="Code Analysis",
            template=(
                "Analyze {language} code in {file_path}. "
                "Focus on: {focus_areas}. "
                "Return: {output_format}."
            ),
            variables=["language", "file_path", "focus_areas", "output_format"],
            avg_tokens=25,
        ))

        # Bug fix template
        self.add_template(PromptTemplate(
            template_id="bug_fix",
            name="Bug Fix",
            template=(
                "Fix {bug_type} in {file_path}. "
                "Error: {error_message}. "
                "Constraints: {constraints}."
            ),
            variables=["bug_type", "file_path", "error_message", "constraints"],
            avg_tokens=20,
        ))

        # Code generation template
        self.add_template(PromptTemplate(
            template_id="code_gen",
            name="Code Generation",
            template=(
                "Generate {language} {code_type}. "
                "Spec: {specification}. "
                "Style: {style_guide}."
            ),
            variables=["language", "code_type", "specification", "style_guide"],
            avg_tokens=18,
        ))

    def add_template(self, template: PromptTemplate):
        """Add template"""
        self.templates[template.template_id] = template

    def generate_from_template(
        self,
        template_id: str,
        variables: Dict[str, str],
    ) -> str:
        """Generate prompt from template"""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Fill template
        prompt = template.template
        for var, value in variables.items():
            prompt = prompt.replace(f"{{{var}}}", value)

        # Update usage stats
        template.usage_count += 1

        return prompt

    def optimize_template(
        self,
        template_id: str,
        successful_outcomes: int,
        total_outcomes: int,
    ):
        """Update template success rate"""
        template = self.templates.get(template_id)
        if not template:
            return

        template.success_rate = successful_outcomes / total_outcomes if total_outcomes > 0 else 0.0

        logger.info(
            f"Template {template_id} updated: "
            f"success_rate={template.success_rate:.2%}, "
            f"usage_count={template.usage_count}"
        )

    def suggest_template(self, task_description: str) -> Optional[PromptTemplate]:
        """Suggest best template for task"""
        # Simple keyword matching
        keywords = {
            "analyze": "code_analysis",
            "fix": "bug_fix",
            "generate": "code_gen",
            "create": "code_gen",
        }

        task_lower = task_description.lower()

        for keyword, template_id in keywords.items():
            if keyword in task_lower:
                return self.templates.get(template_id)

        return None


class PromptABTester:
    """A/B testing framework for prompts"""

    def __init__(self):
        self.tests: Dict[str, ABTestResult] = {}
        logger.info("Prompt A/B Tester initialized")

    def create_test(
        self,
        test_id: str,
        variant_a: str,
        variant_b: str,
    ) -> ABTestResult:
        """Create A/B test"""
        compressor = PromptCompressor()

        test = ABTestResult(
            test_id=test_id,
            variant_a=variant_a,
            variant_b=variant_b,
            variant_a_tokens=compressor._estimate_tokens(variant_a),
            variant_b_tokens=compressor._estimate_tokens(variant_b),
            variant_a_success=0,
            variant_b_success=0,
            variant_a_trials=0,
            variant_b_trials=0,
        )

        self.tests[test_id] = test

        logger.info(
            f"A/B test created: {test_id} "
            f"(A: {test.variant_a_tokens} tokens, B: {test.variant_b_tokens} tokens)"
        )

        return test

    def record_outcome(
        self,
        test_id: str,
        variant: str,  # "A" or "B"
        success: bool,
    ):
        """Record test outcome"""
        test = self.tests.get(test_id)
        if not test:
            return

        if variant == "A":
            test.variant_a_trials += 1
            if success:
                test.variant_a_success += 1
        else:
            test.variant_b_trials += 1
            if success:
                test.variant_b_success += 1

    def analyze_test(self, test_id: str, min_trials: int = 10) -> Optional[str]:
        """Analyze test and determine winner"""
        test = self.tests.get(test_id)
        if not test:
            return None

        # Need minimum trials
        if test.variant_a_trials < min_trials or test.variant_b_trials < min_trials:
            return None

        # Calculate success rates
        success_rate_a = test.variant_a_success / test.variant_a_trials
        success_rate_b = test.variant_b_success / test.variant_b_trials

        # Calculate efficiency (success per token)
        efficiency_a = success_rate_a / test.variant_a_tokens
        efficiency_b = success_rate_b / test.variant_b_tokens

        # Determine winner
        if efficiency_a > efficiency_b * 1.1:  # 10% threshold
            test.winner = "A"
        elif efficiency_b > efficiency_a * 1.1:
            test.winner = "B"
        else:
            test.winner = "tie"

        logger.info(
            f"A/B test {test_id} results: "
            f"A={success_rate_a:.1%}@{test.variant_a_tokens}tok, "
            f"B={success_rate_b:.1%}@{test.variant_b_tokens}tok, "
            f"winner={test.winner}"
        )

        return test.winner


async def main():
    """Test prompt compression framework"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Prompt Compression & Optimization Test")
    logger.info("=" * 60)

    # Test 1: Compression
    logger.info("\n1. Prompt Compression Test:")
    compressor = PromptCompressor()

    original = (
        "Please analyze the Python code in the file located at "
        "/home/user/project/main.py and identify any potential security "
        "vulnerabilities, performance issues, and code quality problems. "
        "Focus on SQL injection, XSS, and inefficient algorithms."
    )

    logger.info(f"  Original ({compressor._estimate_tokens(original)} tokens):")
    logger.info(f"    {original}")

    # Try different strategies
    strategies = [
        CompressionStrategy.REMOVE_STOPWORDS,
        CompressionStrategy.ABBREVIATE,
        CompressionStrategy.SUMMARIZE,
    ]

    for strategy in strategies:
        result = compressor.compress(original, strategy=strategy)
        logger.info(
            f"\n  {strategy.value} ({result.compressed_tokens} tokens, "
            f"{result.savings_pct():.1f}% savings):"
        )
        logger.info(f"    {result.compressed_text}")

    # Test 2: Template optimization
    logger.info("\n2. Template Optimization Test:")
    optimizer = PromptOptimizer()

    prompt = optimizer.generate_from_template(
        "code_analysis",
        {
            "language": "Python",
            "file_path": "main.py",
            "focus_areas": "security, performance",
            "output_format": "JSON",
        },
    )

    logger.info(f"  Generated prompt: {prompt}")
    logger.info(f"  Tokens: {compressor._estimate_tokens(prompt)}")

    # Test 3: A/B testing
    logger.info("\n3. A/B Testing:")
    ab_tester = PromptABTester()

    variant_a = "Analyze this code for bugs and suggest fixes"
    variant_b = "Find bugs, suggest fixes"

    test = ab_tester.create_test("test_1", variant_a, variant_b)

    # Simulate outcomes
    for _ in range(15):
        ab_tester.record_outcome("test_1", "A", True)
        ab_tester.record_outcome("test_1", "B", True)

    winner = ab_tester.analyze_test("test_1")
    logger.info(f"  Winner: {winner}")


if __name__ == "__main__":
    asyncio.run(main())
