"""
Prompt injection detection and input sanitization for the RAG retrieval pipeline.

Scans retrieved chunks and incoming queries for prompt injection patterns before
they enter the context window or reach the LLM.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Module-level sanitization function
# ---------------------------------------------------------------------------

def sanitize_query(text: str) -> str:
    """
    Strip unsafe Unicode: null bytes, C0/C1 control chars (except tab/newline/CR),
    Unicode direction overrides (U+202A–U+202E, U+2066–U+2069),
    zero-width characters (U+200B, U+200C, U+200D, U+FEFF).
    """
    STRIP_CHARS = (
        set('\x00')
        | set(chr(c) for c in range(0x202A, 0x202F))
        | set(chr(c) for c in range(0x2066, 0x206A))
        | {'\u200b', '\u200c', '\u200d', '\ufeff'}
    )
    STRIP_CONTROL = (
        set(chr(c) for c in range(0x00, 0x20) if c not in (0x09, 0x0a, 0x0d))
        | set(chr(c) for c in range(0x7f, 0xa0))
    )

    original_len = len(text)
    result = ''.join(
        c for c in text
        if c not in STRIP_CHARS and c not in STRIP_CONTROL
    )
    if len(result) != original_len:
        logger.info(
            "input_sanitized",
            original_len=original_len,
            sanitized_len=len(result),
            delta=original_len - len(result),
        )
    return result


# ---------------------------------------------------------------------------
# PromptInjectionScanner
# ---------------------------------------------------------------------------

class PromptInjectionScanner:
    """
    Detect prompt injection patterns in retrieved RAG chunks or incoming queries.

    Usage:
        scanner = PromptInjectionScanner()
        result = scanner.scan(text)
        clean_results, n_removed = scanner.filter_results(results, content_key="content")
    """

    # Patterns that indicate prompt injection attempts
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
        r"disregard\s+(the\s+)?(above|previous|prior)",
        r"new\s+instructions?\s*:",
        r"^\s*system\s*:",
        r"<\|im_start\|>\s*system",
        r"\[INST\]",
        r"override\s+(your\s+)?(previous\s+)?instructions?",
        r"forget\s+(everything|all)\s+(you('ve|\s+have)\s+)?(been\s+)?told",
        r"you\s+are\s+now\s+(a\s+)?(different|new|another)",
        r"pretend\s+(you\s+are|to\s+be)",
        r"act\s+as\s+(if\s+you\s+(are|were)\s+)?a",
        r"your\s+(new\s+)?role\s+is",
        r"from\s+now\s+on\s+(you\s+(are|will))",
    ]

    def __init__(self) -> None:
        self._compiled = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in self.INJECTION_PATTERNS
        ]

    def scan(self, text: str) -> Dict[str, Any]:
        """
        Scan text for prompt injection patterns.

        Returns a dict with:
            injected (bool): True if ANY pattern matched.
            matched_pattern (str|None): String form of the first matching pattern.
            risk_score (float): 0.0–1.0 based on number of distinct patterns matched.
                                Computed as min(1.0, match_count / 3.0).
        """
        if not text:
            return {"injected": False, "matched_pattern": None, "risk_score": 0.0}

        matched_patterns: List[str] = []
        first_match: Optional[str] = None

        for pattern, compiled in zip(self.INJECTION_PATTERNS, self._compiled):
            if compiled.search(text):
                matched_patterns.append(pattern)
                if first_match is None:
                    first_match = pattern

        match_count = len(matched_patterns)
        risk_score = min(1.0, match_count / 3.0)
        return {
            "injected": match_count > 0,
            "matched_pattern": first_match,
            "risk_score": risk_score,
        }

    def _extract_text(self, result: Dict[str, Any], content_key: str) -> str:
        """
        Extract a plain string to scan from a result dict.

        If the value at content_key is a dict (e.g. a Qdrant payload), concatenate
        all its string values so the scanner covers the full document text.
        If the key is absent, fall back to scanning inside a 'payload' sub-dict.
        """
        value = result.get(content_key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            # Payload dict: join all string fields
            return " ".join(str(v) for v in value.values() if isinstance(v, str))
        # Fallback: look inside 'payload' for a 'content' field
        payload = result.get("payload")
        if isinstance(payload, dict):
            return " ".join(str(v) for v in payload.values() if isinstance(v, str))
        return ""

    def filter_results(
        self,
        results: List[Dict[str, Any]],
        content_key: str = "content",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filter a list of result dicts, removing any where the scanned text
        contains prompt injection patterns.

        Args:
            results: List of result dicts from Qdrant / hybrid search.
            content_key: Key whose value is scanned. Supports both plain string
                         values and nested payload dicts.

        Returns:
            (filtered_results, n_removed): clean list and count of dropped items.
        """
        clean: List[Dict[str, Any]] = []
        n_removed = 0

        for item in results:
            text = self._extract_text(item, content_key)
            scan_result = self.scan(text)
            if scan_result["injected"]:
                logger.warning(
                    "prompt_injection_detected",
                    collection=item.get("collection", "unknown"),
                    doc_id=str(item.get("id", "unknown")),
                    matched_pattern=scan_result["matched_pattern"],
                    risk_score=scan_result["risk_score"],
                )
                n_removed += 1
            else:
                clean.append(item)

        return clean, n_removed
