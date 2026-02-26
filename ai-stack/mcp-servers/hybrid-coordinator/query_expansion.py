#!/usr/bin/env python3
"""
Query Expansion and Reranking Module
Improves RAG retrieval quality through query expansion and result reranking
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from config import AI_CROSS_ENCODER_ENABLED

logger = logging.getLogger("query-expansion")


class QueryExpander:
    """
    Expand queries to improve retrieval quality

    Strategies:
    1. Synonym expansion (e.g., "error" -> "error, issue, problem, failure")
    2. Technical term expansion (e.g., "NixOS" -> "NixOS, Nix package manager")
    3. Question reformulation (e.g., "How to X?" -> "X tutorial", "X guide", "X steps")
    4. Context-aware expansion using LLM
    """

    def __init__(self, llama_cpp_url: str = "http://localhost:8080"):
        self.llama_cpp_url = llama_cpp_url

        # Common technical synonyms
        self.synonym_map = {
            'flake': ['flake.nix', 'inputs', 'outputs', 'follows', 'lock', 'flake-utils'],
            'module': ['NixOS module', 'nixos-module', 'options declaration', 'config block'],
            'derivation': ['mkDerivation', 'stdenv', 'buildInputs', 'nativeBuildInputs'],
            'quantization': ['GGUF', 'Q4_K_M', 'Q8_0', 'IQ2_M', 'bpw', 'bits-per-weight'],
            'inference': ['llama.cpp', 'llama-server', 'context window', 'tokens/sec', 'KV cache'],
            'embedding': ['sentence-transformers', 'vector', 'cosine similarity', 'HNSW'],
            'error': ['error', 'issue', 'problem', 'failure', 'exception', 'traceback'],
            'fix': ['fix', 'solve', 'resolve', 'repair', 'workaround'],
            'config': ['configuration', 'options', 'settings', 'config attribute'],
            'build': ['build', 'compile', 'nix build', 'nixos-rebuild'],
            'service': ['systemd service', 'systemd unit', 'daemon'],
            'package': ['pkgs', 'nixpkgs', 'derivation', 'nix expression'],
            'deploy': ['nixos-rebuild switch', 'nixos-rebuild test', 'provision'],
            'model': ['GGUF', 'weights', 'checkpoint', 'language model'],
            'memory': ['RAM', 'VRAM', 'context length', 'KV cache', 'offload'],
        }

        # Domain-specific expansions
        self.domain_expansions = {
            'nixos': ['NixOS', 'nixpkgs', 'nix-shell', 'home-manager', 'flake'],
            'nix': ['Nix language', 'nix expression', 'derivation', 'nixpkgs'],
            'llama': ['llama.cpp', 'llama-server', 'GGUF', 'llama-cpp', 'ggml'],
            'qdrant': ['Qdrant', 'vector database', 'vector store', 'HNSW'],
            'rag': ['retrieval', 'RAG pipeline', 'context injection', 'vector search'],
            'amd': ['ROCm', 'AMD GPU', 'amdgpu', 'HIP', 'Radeon'],
            'embedding': ['sentence-transformers', 'nomic-embed', 'bge', 'vector encoding'],
            'rocm': ['ROCm', 'AMD compute', 'HIP', 'amdgpu', 'GPU acceleration'],
        }

    def expand_simple(self, query: str, max_expansions: int = 3) -> List[str]:
        """
        Simple query expansion using synonym map

        Args:
            query: Original query
            max_expansions: Maximum number of expanded queries

        Returns:
            List of expanded queries (including original)
        """
        query_lower = query.lower()
        expansions = [query]  # Always include original

        # Find synonyms for keywords in query
        for keyword, synonyms in self.synonym_map.items():
            if keyword in query_lower:
                # Create variant with synonym
                for synonym in synonyms[:2]:  # Use top 2 synonyms
                    if synonym != keyword:
                        expanded = query_lower.replace(keyword, synonym)
                        expansions.append(expanded)
                        if len(expansions) >= max_expansions:
                            return expansions

        # Try domain expansions
        for domain, terms in self.domain_expansions.items():
            if domain in query_lower:
                for term in terms[:2]:
                    if term.lower() != domain:
                        expanded = query_lower.replace(domain, term.lower())
                        expansions.append(expanded)
                        if len(expansions) >= max_expansions:
                            return expansions

        return expansions[:max_expansions]

    async def expand_with_llm(
        self,
        query: str,
        max_expansions: int = 3
    ) -> List[str]:
        """
        Use local LLM to generate query expansions

        Args:
            query: Original query
            max_expansions: Maximum number of expanded queries

        Returns:
            List of expanded queries
        """
        prompt = f"""Generate {max_expansions - 1} alternative phrasings of this query for better search results.
Original query: {query}

Generate queries that:
1. Use different keywords with same meaning
2. Rephrase as statements instead of questions
3. Focus on specific technical terms

Return ONLY the alternative queries, one per line, without numbering or explanations.
"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.llama_cpp_url}/v1/completions",
                    json={
                        "prompt": prompt,
                        "max_tokens": 150,
                        "temperature": 0.7,
                        "stop": ["\n\n"]
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get("choices", [{}])[0].get("text", "")

                    # Parse expansions
                    expansions = [query]  # Original first
                    for line in text.strip().split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Remove numbering if present
                            cleaned = line.lstrip('0123456789.-) ')
                            if cleaned:
                                expansions.append(cleaned)

                    return expansions[:max_expansions]
                else:
                    logger.warning(f"LLM expansion failed: {response.status_code}")
                    return [query]

        except Exception as e:
            logger.error(f"Error in LLM expansion: {e}")
            return [query]

    def expand_question_to_keywords(self, query: str) -> str:
        """
        Convert question format to keyword search

        "How to fix X?" -> "fix X tutorial guide"
        "What is X?" -> "X definition explanation"
        """
        query_lower = query.lower().strip()

        # Question patterns
        patterns = {
            "how to": ["tutorial", "guide", "steps"],
            "how do i": ["tutorial", "guide", "steps"],
            "what is": ["definition", "explanation", "overview"],
            "why": ["reason", "explanation", "cause"],
            "when to": ["when", "timing", "use case"],
            "where": ["location", "path", "configuration"],
        }

        for pattern, keywords in patterns.items():
            if query_lower.startswith(pattern):
                # Remove question pattern and question mark
                content = query_lower.replace(pattern, "").strip('? ')
                # Add keywords
                keyword_query = f"{content} {' '.join(keywords)}"
                return keyword_query

        return query


def _to_unix(value: Any) -> Optional[float]:
    """Convert a Unix timestamp (float/int) or ISO-8601 string to a float epoch."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (ValueError, TypeError):
        return None


class ResultReranker:
    """
    Rerank search results for better relevance

    Strategies:
    1. Score boosting based on metadata (verified solutions, high success rate)
    2. Recency boosting (newer content scores higher)
    3. Cross-encoder reranking (semantic similarity)
    4. Diversity-aware reranking (avoid redundant results)
    """

    def __init__(self, cross_encoder: Optional["CrossEncoderReranker"] = None):
        self._cross_encoder = cross_encoder

    def rerank_by_metadata(
        self,
        results: List[Dict[str, Any]],
        boost_factors: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank results based on metadata quality signals

        Args:
            results: List of search results with score and payload
            boost_factors: Custom boost factors for different signals

        Returns:
            Reranked results
        """
        if not boost_factors:
            boost_factors = {
                "verified": 1.5,        # Verified solutions get 50% boost
                "high_success": 1.3,    # High success rate gets 30% boost
                "feedback_linked": 1.3, # Feedback-linked content gets 30% boost
                "hot_recent": 1.25,     # Last 7 days gets 25% boost
                "recent": 1.2,          # Recent content gets 20% boost
                "has_examples": 1.15,   # Content with examples gets 15% boost
            }

        reranked = []

        for result in results:
            payload = result.get("payload", {})
            original_score = result.get("score", 0.0)
            boost = 1.0

            # Boost verified solutions
            if payload.get("solution_verified") or payload.get("verified"):
                boost *= boost_factors["verified"]

            # Boost high success rate
            success_rate = payload.get("success_rate", 0.0)
            if success_rate >= 0.8:
                boost *= boost_factors["high_success"]

            # Boost feedback-linked vectors
            if payload.get("feedback_linked") == "true":
                boost *= boost_factors["feedback_linked"]

            # Boost hot recent content (last 7 days)
            hot_ts = _to_unix(payload.get("last_accessed_at") or payload.get("last_used"))
            if hot_ts is not None and (time.time() - hot_ts) / 86400 <= 7:
                boost *= boost_factors["hot_recent"]

            # Boost recent content (last 90 days)
            recent_ts = _to_unix(payload.get("last_used") or payload.get("last_updated"))
            if recent_ts is not None and (time.time() - recent_ts) / 86400 <= 90:
                boost *= boost_factors["recent"]

            # Boost content with code examples
            content = payload.get("content", "") or payload.get("solution", "")
            if "```" in content or "def " in content or "function " in content:
                boost *= boost_factors["has_examples"]

            # Apply boost
            boosted_score = original_score * boost

            reranked.append({
                **result,
                "score": boosted_score,
                "original_score": original_score,
                "boost_factor": boost
            })

        # Sort by boosted score
        reranked.sort(key=lambda x: x["score"], reverse=True)

        return reranked

    def rerank_for_diversity(
        self,
        results: List[Dict[str, Any]],
        diversity_weight: float = 0.3,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Rerank to promote diversity (avoid redundant results)

        Uses MMR (Maximal Marginal Relevance) algorithm

        Args:
            results: Search results
            diversity_weight: Weight for diversity (0=relevance only, 1=diversity only)
            top_k: Number of diverse results to return

        Returns:
            Diverse results
        """
        if len(results) <= top_k:
            return results

        selected = []
        remaining = list(results)

        # Select first result (highest score)
        selected.append(remaining.pop(0))

        # Iteratively select most diverse result
        while len(selected) < top_k and remaining:
            best_score = -float('inf')
            best_idx = 0

            for i, candidate in enumerate(remaining):
                # Relevance score
                relevance = candidate.get("score", 0.0)

                # Diversity score (minimum similarity to selected results)
                min_similarity = min(
                    self._text_similarity(
                        candidate.get("payload", {}).get("content", ""),
                        selected_result.get("payload", {}).get("content", "")
                    )
                    for selected_result in selected
                )
                diversity = 1.0 - min_similarity

                # MMR score
                mmr_score = (1 - diversity_weight) * relevance + diversity_weight * diversity

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple Jaccard similarity between texts"""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def hybrid_rerank(
        self,
        results: List[Dict[str, Any]],
        top_k: int = 10,
        query: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Combined metadata boosting + diversity reranking

        Args:
            results: Search results
            top_k: Number of results to return

        Returns:
            Reranked results
        """
        # First: boost by metadata
        metadata_ranked = self.rerank_by_metadata(results)

        # Second: ensure diversity in top-k
        diverse_results = self.rerank_for_diversity(
            metadata_ranked,
            diversity_weight=0.3,
            top_k=top_k
        )

        # Third: optional cross-encoder rerank for final ordering
        if self._cross_encoder and self._cross_encoder.is_available and AI_CROSS_ENCODER_ENABLED:
            return self._cross_encoder.rerank_sync(query, diverse_results)[:top_k]

        return diverse_results


class CrossEncoderReranker:
    """Optional cross-encoder reranker with graceful fallback."""

    def __init__(self):
        self._model = None
        self.is_available = False

        if not AI_CROSS_ENCODER_ENABLED:
            return

        try:
            from sentence_transformers.cross_encoder import CrossEncoder  # type: ignore
        except ImportError:
            logger.warning("Cross encoder disabled: sentence_transformers not installed")
            return

        for model_name in (
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "ms-marco-MiniLM-L-6-v2",
        ):
            try:
                self._model = CrossEncoder(model_name)
                self.is_available = True
                logger.info("Cross encoder enabled with model: %s", model_name)
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load cross encoder model %s: %s", model_name, exc)

    def _extract_text(self, result: Dict[str, Any]) -> str:
        payload = result.get("payload", {})
        return payload.get("content") or payload.get("solution") or ""

    def rerank_sync(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.is_available or self._model is None or not results:
            return results

        try:
            pairs = [(query, self._extract_text(result)) for result in results]
            scores = self._model.predict(pairs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cross encoder rerank failed: %s", exc)
            return results

        reranked: List[Dict[str, Any]] = []
        for result, score in zip(results, scores):
            reranked.append({**result, "cross_encoder_score": float(score)})

        reranked.sort(key=lambda item: item.get("cross_encoder_score", float("-inf")), reverse=True)
        return reranked

    async def rerank(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.rerank_sync, query, results)


class QueryExpansionReranking:
    """
    Combined query expansion and reranking pipeline
    """

    def __init__(self, llama_cpp_url: str = "http://localhost:8080"):
        self.expander = QueryExpander(llama_cpp_url)
        self._cross_encoder = CrossEncoderReranker()
        self.reranker = ResultReranker(cross_encoder=self._cross_encoder)

    async def expand_query(
        self,
        query: str,
        strategy: str = "simple",
        max_expansions: int = 3
    ) -> List[str]:
        """
        Expand query using selected strategy

        Args:
            query: Original query
            strategy: "simple" or "llm"
            max_expansions: Max expansions to generate

        Returns:
            List of expanded queries
        """
        if strategy == "llm":
            return await self.expander.expand_with_llm(query, max_expansions)
        else:
            return self.expander.expand_simple(query, max_expansions)

    def rerank_results(
        self,
        results: List[Dict[str, Any]],
        strategy: str = "hybrid",
        top_k: int = 10,
        query: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Rerank results using selected strategy

        Args:
            results: Search results
            strategy: "metadata", "diversity", or "hybrid"
            top_k: Number of results to return

        Returns:
            Reranked results
        """
        if strategy == "metadata":
            return self.reranker.rerank_by_metadata(results)[:top_k]
        elif strategy == "diversity":
            return self.reranker.rerank_for_diversity(results, top_k=top_k)
        elif strategy == "cross_encoder":
            if self._cross_encoder and self._cross_encoder.is_available and AI_CROSS_ENCODER_ENABLED:
                return self._cross_encoder.rerank_sync(query, results)[:top_k]
            return results[:top_k]
        else:  # hybrid
            return self.reranker.hybrid_rerank(results, top_k=top_k, query=query)
