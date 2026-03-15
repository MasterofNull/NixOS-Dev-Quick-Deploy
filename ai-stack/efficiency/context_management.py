#!/usr/bin/env python3
"""
Context Window Management Framework

Intelligent context pruning, summarization, and relevance scoring.
Part of Phase 7 Batch 7.2: Context Window Management

Key Features:
- Intelligent context pruning based on relevance
- Hierarchical summarization for long contexts
- Context relevance scoring
- Sliding window attention for long documents
- Context reuse across similar queries

Reference: LongLLMLingua, RULER (https://arxiv.org/abs/2402.14848)
"""

import asyncio
import hashlib
import json
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ContextTier(Enum):
    """Context detail tiers"""
    MINIMAL = "minimal"  # Absolute minimum
    BRIEF = "brief"  # Key points only
    STANDARD = "standard"  # Balanced detail
    DETAILED = "detailed"  # Comprehensive
    EXHAUSTIVE = "exhaustive"  # Everything


@dataclass
class ContextChunk:
    """Chunk of context"""
    chunk_id: str
    content: str
    tokens: int
    relevance_score: float = 0.0
    source: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class ContextWindow:
    """Managed context window"""
    window_id: str
    max_tokens: int
    chunks: List[ContextChunk] = field(default_factory=list)
    total_tokens: int = 0
    pruned_chunks: List[ContextChunk] = field(default_factory=list)


@dataclass
class SummarizationResult:
    """Result of hierarchical summarization"""
    original_text: str
    summary: str
    original_tokens: int
    summary_tokens: int
    compression_ratio: float
    levels: int  # Summarization levels used


class ContextPruner:
    """Intelligent context pruning"""

    def __init__(self):
        logger.info("Context Pruner initialized")

    def prune(
        self,
        chunks: List[ContextChunk],
        max_tokens: int,
        query: Optional[str] = None,
    ) -> tuple[List[ContextChunk], List[ContextChunk]]:
        """Prune context to fit within token limit"""
        if not chunks:
            return [], []

        # Calculate current tokens
        total_tokens = sum(c.tokens for c in chunks)

        if total_tokens <= max_tokens:
            return chunks, []

        # Score chunks by relevance
        scored_chunks = []
        for chunk in chunks:
            score = self._calculate_relevance(chunk, query)
            chunk.relevance_score = score
            scored_chunks.append((score, chunk))

        # Sort by relevance (descending)
        scored_chunks.sort(reverse=True, key=lambda x: x[0])

        # Select chunks to keep
        kept = []
        pruned = []
        current_tokens = 0

        for score, chunk in scored_chunks:
            if current_tokens + chunk.tokens <= max_tokens:
                kept.append(chunk)
                current_tokens += chunk.tokens
            else:
                pruned.append(chunk)

        # Sort kept chunks by original order
        kept.sort(key=lambda c: chunks.index(c))

        logger.info(
            f"Pruned context: kept {len(kept)}/{len(chunks)} chunks "
            f"({current_tokens}/{total_tokens} tokens)"
        )

        return kept, pruned

    def _calculate_relevance(
        self,
        chunk: ContextChunk,
        query: Optional[str],
    ) -> float:
        """Calculate chunk relevance score"""
        score = 1.0

        # Boost if query terms present
        if query:
            query_terms = set(query.lower().split())
            chunk_terms = set(chunk.content.lower().split())
            overlap = query_terms & chunk_terms

            if overlap:
                score += len(overlap) / len(query_terms)

        # Boost recent chunks
        if "timestamp" in chunk.metadata:
            age_hours = (datetime.now() - chunk.metadata["timestamp"]).total_seconds() / 3600
            if age_hours < 24:
                score *= 1.5  # Recent content is more relevant

        # Boost important sources
        important_sources = {"error", "warning", "critical", "requirement"}
        if any(src in chunk.source.lower() for src in important_sources):
            score *= 1.3

        return score


class HierarchicalSummarizer:
    """Hierarchical summarization for long contexts"""

    def __init__(self):
        logger.info("Hierarchical Summarizer initialized")

    def summarize(
        self,
        text: str,
        target_tokens: int,
        current_tokens: Optional[int] = None,
    ) -> SummarizationResult:
        """Summarize text to target token count"""
        if current_tokens is None:
            current_tokens = self._estimate_tokens(text)

        if current_tokens <= target_tokens:
            return SummarizationResult(
                original_text=text,
                summary=text,
                original_tokens=current_tokens,
                summary_tokens=current_tokens,
                compression_ratio=1.0,
                levels=0,
            )

        # Apply hierarchical summarization
        summary = text
        levels = 0

        while self._estimate_tokens(summary) > target_tokens and levels < 3:
            summary = self._summarize_level(summary, target_tokens)
            levels += 1

        summary_tokens = self._estimate_tokens(summary)

        return SummarizationResult(
            original_text=text,
            summary=summary,
            original_tokens=current_tokens,
            summary_tokens=summary_tokens,
            compression_ratio=summary_tokens / current_tokens if current_tokens > 0 else 1.0,
            levels=levels,
        )

    def _summarize_level(self, text: str, target_tokens: int) -> str:
        """Single level of summarization"""
        sentences = re.split(r'(?<=[.!?])\s+', text)

        if len(sentences) <= 3:
            return text

        # Extract key sentences (simple extractive summarization)
        # Score by: length, position, keywords
        scored = []
        keywords = {
            "important", "critical", "must", "should", "required",
            "error", "warning", "problem", "issue", "solution",
        }

        for i, sentence in enumerate(sentences):
            score = 0

            # Position score (first and last sentences are important)
            if i == 0 or i == len(sentences) - 1:
                score += 2

            # Length score (prefer medium-length sentences)
            word_count = len(sentence.split())
            if 10 <= word_count <= 30:
                score += 1

            # Keyword score
            if any(kw in sentence.lower() for kw in keywords):
                score += 2

            scored.append((score, sentence))

        # Sort by score and select top sentences
        scored.sort(reverse=True, key=lambda x: x[0])

        # Keep approximately half the sentences
        keep_count = max(3, len(scored) // 2)
        selected = [s for _, s in scored[:keep_count]]

        # Maintain original order
        result = []
        for sentence in sentences:
            if sentence in selected:
                result.append(sentence)

        return " ".join(result)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count"""
        return int(len(text.split()) * 1.3)


class RelevanceScorer:
    """Score context relevance"""

    def __init__(self):
        self.query_cache: Dict[str, Set[str]] = {}
        logger.info("Relevance Scorer initialized")

    def score_context(
        self,
        context: str,
        query: str,
    ) -> float:
        """Score context relevance to query"""
        # Extract query terms
        query_terms = self._extract_terms(query)
        context_terms = self._extract_terms(context)

        if not query_terms:
            return 0.5  # Neutral score

        # Calculate term overlap
        overlap = query_terms & context_terms
        if not overlap:
            return 0.0

        # Jaccard similarity
        jaccard = len(overlap) / len(query_terms | context_terms)

        # Term frequency boost
        tf_score = 0.0
        for term in overlap:
            # Count occurrences in context
            count = context.lower().count(term.lower())
            tf_score += min(count / 10.0, 1.0)  # Cap at 1.0

        tf_score /= len(overlap) if overlap else 1.0

        # Combine scores
        score = (jaccard * 0.6) + (tf_score * 0.4)

        return min(score, 1.0)

    def _extract_terms(self, text: str) -> Set[str]:
        """Extract relevant terms"""
        # Remove stopwords and short words
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "was", "are", "be",
        }

        terms = set()
        for word in text.lower().split():
            word = re.sub(r'[^a-z0-9]', '', word)
            if len(word) > 2 and word not in stopwords:
                terms.add(word)

        return terms


class SlidingWindowManager:
    """Manage sliding window for long documents"""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.windows: List[ContextWindow] = []
        logger.info(f"Sliding Window Manager initialized (window_size={window_size})")

    def create_windows(
        self,
        document: str,
        overlap: int = 100,
    ) -> List[ContextWindow]:
        """Create sliding windows from document"""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', document)

        windows = []
        current_window = []
        current_tokens = 0
        window_id = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            if current_tokens + sentence_tokens > self.window_size and current_window:
                # Save current window
                window = self._create_window(
                    window_id,
                    current_window,
                    current_tokens,
                )
                windows.append(window)
                window_id += 1

                # Start new window with overlap
                overlap_sentences = current_window[-overlap:]
                current_window = overlap_sentences + [sentence]
                current_tokens = sum(self._estimate_tokens(s) for s in current_window)
            else:
                current_window.append(sentence)
                current_tokens += sentence_tokens

        # Add final window
        if current_window:
            window = self._create_window(window_id, current_window, current_tokens)
            windows.append(window)

        self.windows = windows

        logger.info(f"Created {len(windows)} sliding windows from document")
        return windows

    def _create_window(
        self,
        window_id: int,
        sentences: List[str],
        total_tokens: int,
    ) -> ContextWindow:
        """Create a context window"""
        content = " ".join(sentences)

        chunk = ContextChunk(
            chunk_id=f"window_{window_id}",
            content=content,
            tokens=total_tokens,
            source="sliding_window",
        )

        return ContextWindow(
            window_id=f"window_{window_id}",
            max_tokens=self.window_size,
            chunks=[chunk],
            total_tokens=total_tokens,
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count"""
        return int(len(text.split()) * 1.3)


class ContextReuser:
    """Reuse context across similar queries"""

    def __init__(self):
        self.context_cache: Dict[str, tuple[str, datetime]] = {}
        self.similarity_threshold = 0.7
        logger.info("Context Reuser initialized")

    def get_cached_context(
        self,
        query: str,
        max_age_hours: int = 24,
    ) -> Optional[str]:
        """Get cached context for similar query"""
        query_hash = self._hash_query(query)

        # Check exact match
        if query_hash in self.context_cache:
            context, timestamp = self.context_cache[query_hash]

            # Check age
            age_hours = (datetime.now() - timestamp).total_seconds() / 3600
            if age_hours <= max_age_hours:
                logger.info(f"Cache hit (exact): {query_hash}")
                return context

        # Check similar queries
        query_terms = set(query.lower().split())

        for cached_hash, (context, timestamp) in self.context_cache.items():
            age_hours = (datetime.now() - timestamp).total_seconds() / 3600
            if age_hours > max_age_hours:
                continue

            # Calculate similarity
            cached_terms = self._get_cached_terms(cached_hash)
            if not cached_terms:
                continue

            similarity = len(query_terms & cached_terms) / len(query_terms | cached_terms)

            if similarity >= self.similarity_threshold:
                logger.info(f"Cache hit (similar, {similarity:.2%}): {cached_hash}")
                return context

        logger.debug(f"Cache miss: {query_hash}")
        return None

    def cache_context(
        self,
        query: str,
        context: str,
    ):
        """Cache context for query"""
        query_hash = self._hash_query(query)
        self.context_cache[query_hash] = (context, datetime.now())

        # Store query terms for similarity matching
        self.context_cache[f"{query_hash}_terms"] = (set(query.lower().split()), datetime.now())

        logger.debug(f"Cached context: {query_hash}")

    def _hash_query(self, query: str) -> str:
        """Hash query for caching"""
        return hashlib.sha256(query.lower().encode()).hexdigest()[:16]

    def _get_cached_terms(self, query_hash: str) -> Optional[Set[str]]:
        """Get cached query terms"""
        terms_key = f"{query_hash}_terms"
        if terms_key in self.context_cache:
            return self.context_cache[terms_key][0]
        return None

    def clear_expired(self, max_age_hours: int = 24):
        """Clear expired cache entries"""
        now = datetime.now()
        expired = []

        for key, (_, timestamp) in self.context_cache.items():
            age_hours = (now - timestamp).total_seconds() / 3600
            if age_hours > max_age_hours:
                expired.append(key)

        for key in expired:
            del self.context_cache[key]

        if expired:
            logger.info(f"Cleared {len(expired)} expired cache entries")


async def main():
    """Test context management framework"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Context Window Management Test")
    logger.info("=" * 60)

    # Sample long document
    document = (
        "The AI stack consists of multiple components. "
        "The hybrid coordinator manages task delegation. "
        "The local agents execute tasks using tools. "
        "The memory store maintains state across sessions. "
        "Performance monitoring tracks system health. "
        "Security measures protect against unauthorized access. "
        "The system uses mTLS for secure communication. "
        "Audit logging records all significant events. "
        "The workflow engine orchestrates complex tasks. "
        "Context management optimizes token usage."
    )

    # Test 1: Context Pruning
    logger.info("\n1. Context Pruning Test:")
    pruner = ContextPruner()

    chunks = [
        ContextChunk(f"chunk_{i}", sentence, len(sentence.split()) * 1.3, source="doc")
        for i, sentence in enumerate(document.split(". "))
    ]

    query = "security and audit logging"
    kept, pruned = pruner.prune(chunks, max_tokens=100, query=query)

    logger.info(f"  Query: {query}")
    logger.info(f"  Kept: {len(kept)} chunks")
    logger.info(f"  Pruned: {len(pruned)} chunks")

    # Test 2: Hierarchical Summarization
    logger.info("\n2. Hierarchical Summarization Test:")
    summarizer = HierarchicalSummarizer()

    result = summarizer.summarize(document, target_tokens=50)

    logger.info(f"  Original: {result.original_tokens} tokens")
    logger.info(f"  Summary: {result.summary_tokens} tokens ({result.compression_ratio:.2%})")
    logger.info(f"  Levels: {result.levels}")
    logger.info(f"  Text: {result.summary[:100]}...")

    # Test 3: Relevance Scoring
    logger.info("\n3. Relevance Scoring Test:")
    scorer = RelevanceScorer()

    test_contexts = [
        "The system uses mTLS for secure communication",
        "Performance monitoring tracks system health",
        "The hybrid coordinator manages task delegation",
    ]

    query = "security authentication"

    for context in test_contexts:
        score = scorer.score_context(context, query)
        logger.info(f"  Score: {score:.2f} - {context}")

    # Test 4: Sliding Windows
    logger.info("\n4. Sliding Window Test:")
    window_mgr = SlidingWindowManager(window_size=50)

    windows = window_mgr.create_windows(document, overlap=2)

    for window in windows:
        logger.info(f"  {window.window_id}: {window.total_tokens} tokens")

    # Test 5: Context Reuse
    logger.info("\n5. Context Reuse Test:")
    reuser = ContextReuser()

    # Cache context
    reuser.cache_context("security measures", "Context about security...")

    # Try to retrieve
    cached = reuser.get_cached_context("security authentication")
    logger.info(f"  Similar query cached: {cached is not None}")


if __name__ == "__main__":
    asyncio.run(main())
