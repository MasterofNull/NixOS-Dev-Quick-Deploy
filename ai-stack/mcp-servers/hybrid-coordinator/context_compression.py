#!/usr/bin/env python3
"""
Context Compression Engine
Intelligently compress retrieved context to fit token budgets
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("context-compression")


class ContextCompressor:
    """
    Compress retrieved context to fit within token budgets

    Strategies:
    1. Relevance-based truncation (keep most relevant chunks)
    2. Redundancy removal (deduplicate similar content)
    3. Extractive summarization (keep key sentences)
    4. Metadata stripping (remove non-essential fields)
    5. Code simplification (remove comments, collapse whitespace)

    Token estimation: ~4 characters per token (English text)
    """

    def __init__(self):
        # Approximate token counting (4 chars = 1 token)
        self.chars_per_token = 4

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text

        Uses 4 characters per token heuristic (conservative estimate)
        """
        return len(text) // self.chars_per_token

    def compress_to_budget(
        self,
        contexts: List[Dict[str, Any]],
        max_tokens: int,
        strategy: str = "hybrid"
    ) -> Tuple[str, List[str], int]:
        """
        Compress context list to fit within token budget

        Args:
            contexts: List of context dicts with 'text', 'score', 'id', etc.
            max_tokens: Maximum tokens allowed
            strategy: Compression strategy (hybrid|truncate|summarize)

        Returns:
            Tuple of (compressed_text, context_ids_used, actual_tokens)
        """
        if not contexts:
            return "", [], 0

        # Sort by relevance score (highest first)
        sorted_contexts = sorted(
            contexts,
            key=lambda x: x.get('score', 0.0),
            reverse=True
        )

        if strategy == "truncate":
            return self._compress_truncate(sorted_contexts, max_tokens)
        elif strategy == "summarize":
            return self._compress_summarize(sorted_contexts, max_tokens)
        else:  # hybrid (default)
            return self._compress_hybrid(sorted_contexts, max_tokens)

    def _compress_truncate(
        self,
        contexts: List[Dict[str, Any]],
        max_tokens: int
    ) -> Tuple[str, List[str], int]:
        """
        Simple truncation: keep highest-scoring contexts until budget exhausted
        """
        result_parts = []
        context_ids = []
        current_tokens = 0

        for ctx in contexts:
            text = ctx.get('text', ctx.get('payload', {}).get('content', ''))
            ctx_id = ctx.get('id', '')
            tokens = self.estimate_tokens(text)

            if current_tokens + tokens <= max_tokens:
                result_parts.append(text)
                context_ids.append(ctx_id)
                current_tokens += tokens
            else:
                # Try to fit partial content
                remaining_tokens = max_tokens - current_tokens
                if remaining_tokens > 50:  # Only if significant space left
                    partial_text = self._truncate_text(text, remaining_tokens)
                    result_parts.append(partial_text)
                    context_ids.append(ctx_id)
                    current_tokens += self.estimate_tokens(partial_text)
                break

        combined_text = "\n\n".join(result_parts)
        return combined_text, context_ids, current_tokens

    def _compress_summarize(
        self,
        contexts: List[Dict[str, Any]],
        max_tokens: int
    ) -> Tuple[str, List[str], int]:
        """
        Extractive summarization: extract key sentences from each context
        """
        result_parts = []
        context_ids = []
        current_tokens = 0

        for ctx in contexts:
            text = ctx.get('text', ctx.get('payload', {}).get('content', ''))
            ctx_id = ctx.get('id', '')

            # Extract key sentences (simple heuristic: shorter sentences, ends with punctuation)
            key_sentences = self._extract_key_sentences(text, max_sentences=3)
            summary = " ".join(key_sentences)

            tokens = self.estimate_tokens(summary)

            if current_tokens + tokens <= max_tokens:
                result_parts.append(summary)
                context_ids.append(ctx_id)
                current_tokens += tokens
            else:
                remaining_tokens = max_tokens - current_tokens
                if remaining_tokens > 30:
                    # Fit what we can
                    partial = self._truncate_text(summary, remaining_tokens)
                    result_parts.append(partial)
                    context_ids.append(ctx_id)
                    current_tokens += self.estimate_tokens(partial)
                break

        combined_text = "\n\n".join(result_parts)
        return combined_text, context_ids, current_tokens

    def _compress_hybrid(
        self,
        contexts: List[Dict[str, Any]],
        max_tokens: int
    ) -> Tuple[str, List[str], int]:
        """
        Hybrid strategy: combine truncation and summarization

        - High-scoring contexts (top 30%): Keep full text
        - Mid-scoring contexts (30-70%): Extract key sentences
        - Low-scoring contexts (70-100%): Skip unless budget allows
        """
        if not contexts:
            return "", [], 0

        result_parts = []
        context_ids = []
        current_tokens = 0

        n_contexts = len(contexts)
        high_threshold = int(n_contexts * 0.3)
        mid_threshold = int(n_contexts * 0.7)

        for i, ctx in enumerate(contexts):
            text = ctx.get('text', ctx.get('payload', {}).get('content', ''))
            ctx_id = ctx.get('id', '')

            # Determine processing strategy based on rank
            if i < high_threshold:
                # High priority: keep full text (with minor cleanup)
                processed_text = self._cleanup_text(text)
            elif i < mid_threshold:
                # Medium priority: extract key sentences
                key_sentences = self._extract_key_sentences(text, max_sentences=2)
                processed_text = " ".join(key_sentences)
            else:
                # Low priority: skip unless we have budget
                if current_tokens > max_tokens * 0.8:
                    continue
                key_sentences = self._extract_key_sentences(text, max_sentences=1)
                processed_text = " ".join(key_sentences)

            tokens = self.estimate_tokens(processed_text)

            if current_tokens + tokens <= max_tokens:
                result_parts.append(processed_text)
                context_ids.append(ctx_id)
                current_tokens += tokens
            else:
                # Try partial fit
                remaining_tokens = max_tokens - current_tokens
                if remaining_tokens > 50:
                    partial = self._truncate_text(processed_text, remaining_tokens)
                    result_parts.append(partial)
                    context_ids.append(ctx_id)
                    current_tokens += self.estimate_tokens(partial)
                break

        combined_text = "\n\n---\n\n".join(result_parts)
        return combined_text, context_ids, current_tokens

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit token budget"""
        max_chars = max_tokens * self.chars_per_token

        if len(text) <= max_chars:
            return text

        # Try to truncate at sentence boundary
        truncated = text[:max_chars]
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        break_point = max(last_period, last_newline)

        if break_point > max_chars * 0.7:  # If we can save 70%+ of content
            return truncated[:break_point + 1]
        else:
            return truncated + "..."

    def _cleanup_text(self, text: str) -> str:
        """
        Clean up text to reduce token usage

        - Remove excessive whitespace
        - Collapse multiple newlines
        - Remove code comments (if code block)
        """
        # Collapse multiple spaces
        text = re.sub(r' +', ' ', text)

        # Collapse multiple newlines (keep max 2)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove trailing whitespace
        text = '\n'.join(line.rstrip() for line in text.split('\n'))

        return text.strip()

    def _extract_key_sentences(self, text: str, max_sentences: int = 3) -> List[str]:
        """
        Extract key sentences using simple heuristics

        Heuristics:
        1. Shorter sentences (easier to parse)
        2. Contains keywords (error, solution, fix, install, configure)
        3. Starts with capital letter
        4. Ends with proper punctuation
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+\s+', text)

        # Filter and score sentences
        scored_sentences = []
        keywords = ['error', 'solution', 'fix', 'install', 'configure', 'deploy',
                    'setup', 'enable', 'disable', 'create', 'update', 'remove']

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Too short
                continue

            score = 0

            # Prefer shorter sentences (30-150 chars ideal)
            length = len(sentence)
            if 30 <= length <= 150:
                score += 2
            elif length < 30:
                score += 1

            # Check for keywords
            sentence_lower = sentence.lower()
            keyword_count = sum(1 for kw in keywords if kw in sentence_lower)
            score += keyword_count

            # Prefer sentences starting with capital
            if sentence[0].isupper():
                score += 1

            # Prefer command-like sentences (starts with verb)
            verbs = ['use', 'add', 'run', 'set', 'update', 'install', 'enable',
                     'configure', 'create', 'remove', 'edit', 'modify']
            if any(sentence_lower.startswith(v) for v in verbs):
                score += 2

            scored_sentences.append((score, sentence))

        # Sort by score and take top N
        scored_sentences.sort(reverse=True, key=lambda x: x[0])
        top_sentences = [sent for _, sent in scored_sentences[:max_sentences]]

        return top_sentences

    def remove_duplicates(
        self,
        contexts: List[Dict[str, Any]],
        similarity_threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate or highly similar contexts

        Uses simple Jaccard similarity on word sets
        """
        if len(contexts) <= 1:
            return contexts

        unique_contexts = []
        seen_texts = []

        for ctx in contexts:
            text = ctx.get('text', ctx.get('payload', {}).get('content', ''))

            # Check similarity with already-seen texts
            is_duplicate = False
            for seen_text in seen_texts:
                similarity = self._jaccard_similarity(text, seen_text)
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_contexts.append(ctx)
                seen_texts.append(text)

        removed_count = len(contexts) - len(unique_contexts)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate contexts")

        return unique_contexts

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate Jaccard similarity between two texts

        Jaccard = |A ∩ B| / |A ∪ B|
        """
        # Convert to word sets
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def format_compressed_context(
        self,
        compressed_text: str,
        context_ids: List[str],
        original_count: int,
        used_count: int,
        token_budget: int,
        actual_tokens: int
    ) -> str:
        """
        Format compressed context with metadata header

        Helps remote LLM understand compression applied
        """
        header = f"""[CONTEXT COMPRESSION APPLIED]
Original contexts: {original_count}
Contexts used: {used_count} ({used_count/original_count*100:.0f}%)
Token budget: {token_budget}
Actual tokens: {actual_tokens} ({actual_tokens/token_budget*100:.0f}% of budget)
Context IDs: {', '.join(context_ids[:5])}{'...' if len(context_ids) > 5 else ''}

---

"""
        return header + compressed_text
