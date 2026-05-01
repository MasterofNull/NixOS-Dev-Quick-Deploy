"""
Signal Detectors — Phase 19: Values Signals

All detectors use observable behavioral proxies only. No emotion recognition,
no NLP classifiers. Stateless — no side effects.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict

# Configurable via env
_COMPASSION_WORD_THRESHOLD: int = int(os.environ.get("AFFECTIVE_COMPASSION_WORD_THRESHOLD", "2"))
_EMPATHY_RETRY_THRESHOLD: int = int(os.environ.get("AFFECTIVE_EMPATHY_RETRY_THRESHOLD", "3"))

_COMPASSION_WORDS = frozenset({"error", "broken", "wrong", "not working", "help", "stuck", "fail", "failed", "crash", "issue"})
_MAGIC_NUMBER_RE = re.compile(r"\b(?!0\b|1\b)\d{2,}\b")
_HARDCODED_STRING_RE = re.compile(r'(?:localhost|127\.0\.0\.1|http://|https://)[^\s"\'`]+')


class SignalDetectors:
    """Stateless observable-proxy detectors."""

    def detect_empathy(self, request_context: Dict[str, Any]) -> float:
        """Detect frustration proxy from retry count and recent error rate.

        Returns 0.0 if no session context available.
        """
        retry_count = 0

        # Proxy 1: explicit retry count from header or context
        retry_count = int(request_context.get("retry_count", 0))

        # Proxy 2: error rate from session context (0.0–1.0 if available)
        error_rate: float = float(request_context.get("recent_error_rate", 0.0))

        if retry_count == 0 and error_rate == 0.0:
            return 0.0

        # Normalise: retries contribute up to 0.8, error_rate up to 0.5
        retry_signal = min(retry_count / _EMPATHY_RETRY_THRESHOLD, 1.0) * 0.8
        error_signal = min(error_rate, 1.0) * 0.5
        return min(retry_signal + error_signal, 1.0)

    def detect_aesthetic_gap(self, response_content: str) -> float:
        """Detect low-quality code output proxies.

        Returns 0.0 for non-code responses.
        """
        if not response_content:
            return 0.0

        # Only inspect code blocks
        code_blocks = re.findall(r"```[\s\S]*?```", response_content)
        if not code_blocks:
            return 0.0

        combined = "\n".join(code_blocks)
        lines = combined.splitlines()
        if not lines:
            return 0.0

        # Proxy 1: low comment ratio in code blocks
        comment_lines = sum(1 for l in lines if l.strip().startswith(("#", "//", "/*", "*", "--")))
        comment_ratio = comment_lines / len(lines)

        # Proxy 2: presence of magic numbers
        magic_count = len(_MAGIC_NUMBER_RE.findall(combined))

        # Proxy 3: hardcoded URLs / localhost strings
        hardcoded_count = len(_HARDCODED_STRING_RE.findall(combined))

        score = 0.0
        if comment_ratio < 0.05:
            score += 0.35
        if magic_count > 2:
            score += min(magic_count / 10, 0.4)
        if hardcoded_count > 0:
            score += min(hardcoded_count / 5, 0.25)

        return min(score, 1.0)

    def detect_compassion(self, request_context: Dict[str, Any]) -> float:
        """Detect distress markers in the query text.

        Uses word-set matching + question-mark density as proxies.
        """
        query: str = str(request_context.get("query", "")).lower()
        if not query:
            return 0.0

        # Proxy 1: count compassion-marker words / phrases
        word_hits = sum(1 for w in _COMPASSION_WORDS if w in query)

        # Proxy 2: question mark density (confusion indicator)
        qmark_count = query.count("?")

        if word_hits < _COMPASSION_WORD_THRESHOLD and qmark_count < 2:
            return 0.0

        score = 0.0
        if word_hits >= _COMPASSION_WORD_THRESHOLD:
            score += min(word_hits / 5, 0.7)
        if qmark_count >= 2:
            score += min(qmark_count / 6, 0.3)

        return min(score, 1.0)
