"""Reusable RAG pipeline helpers for AIDB."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class RAGConfig:
    default_limit: int = 5
    default_context_chars: int = 4000
    max_context_chars: int = 12000


class RAGPipeline:
    def __init__(
        self,
        *,
        search_vectors: Callable[..., Any],
        get_document_content: Callable[[int], str],
        config: Optional[RAGConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._search_vectors = search_vectors
        self._get_document_content = get_document_content
        self._config = config or RAGConfig()
        self._logger = logger or logging.getLogger("aidb.rag")

    def status(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "default_limit": self._config.default_limit,
            "default_context_chars": self._config.default_context_chars,
            "max_context_chars": self._config.max_context_chars,
        }

    def _normalize_limit(self, limit: Optional[int]) -> int:
        if limit is None:
            return self._config.default_limit
        try:
            normalized = int(limit)
        except (TypeError, ValueError):
            self._logger.debug("Invalid limit %r; using default", limit)
            return self._config.default_limit
        return max(1, normalized)

    def _normalize_context_chars(self, max_context_chars: Optional[int]) -> int:
        if max_context_chars is None:
            return self._config.default_context_chars
        try:
            normalized = int(max_context_chars)
        except (TypeError, ValueError):
            self._logger.debug("Invalid max_context_chars %r; using default", max_context_chars)
            return self._config.default_context_chars
        normalized = max(0, normalized)
        return min(normalized, self._config.max_context_chars)

    def _format_result(self, idx: int, result: Dict[str, Any]) -> str:
        title = (
            result.get("title")
            or result.get("relative_path")
            or result.get("project")
            or f"document {result.get('document_id', '?')}"
        )
        header = f"[{idx}] {title}"
        content = (result.get("content") or "").strip()
        if content:
            return f"{header}\n{content}".strip()
        return header

    def _build_context(self, results: Sequence[Dict[str, Any]], max_chars: int) -> str:
        if max_chars <= 0:
            return ""
        separator = "\n\n---\n\n"
        parts: List[str] = []
        for idx, result in enumerate(results, start=1):
            snippet = self._format_result(idx, result)
            if snippet:
                parts.append(snippet)
        if not parts:
            return ""
        context = separator.join(parts)
        if len(context) > max_chars:
            context = context[:max_chars].rstrip()
        return context

    async def semantic_search(
        self,
        *,
        query_text: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        limit: Optional[int] = None,
        project: Optional[str] = None,
        include_context: bool = False,
        max_context_chars: Optional[int] = None,
    ) -> Dict[str, Any]:
        limit_value = self._normalize_limit(limit)
        results = await self._search_vectors(
            query_text=query_text,
            embedding=embedding,
            limit=limit_value,
            project=project,
        )
        response: Dict[str, Any] = {"results": results}
        if include_context:
            context_chars = self._normalize_context_chars(max_context_chars)
            context = self._build_context(results, context_chars)
            response["context"] = context
            response["context_chars"] = len(context)
        return response

    async def get_related_docs(
        self,
        *,
        document_id: Optional[int] = None,
        query_text: Optional[str] = None,
        limit: Optional[int] = None,
        project: Optional[str] = None,
        include_context: bool = False,
        max_context_chars: Optional[int] = None,
    ) -> Dict[str, Any]:
        if document_id is not None:
            query_text = self._get_document_content(document_id)
        if not query_text:
            raise ValueError("document_id or query_text is required")

        limit_value = self._normalize_limit(limit)
        search_limit = limit_value + 1 if document_id is not None else limit_value
        results = await self._search_vectors(
            query_text=query_text,
            embedding=None,
            limit=search_limit,
            project=project,
        )
        if document_id is not None:
            results = [row for row in results if row.get("document_id") != document_id]
        results = results[:limit_value]

        response: Dict[str, Any] = {"results": results}
        if document_id is not None:
            response["source_document_id"] = document_id
        if include_context:
            context_chars = self._normalize_context_chars(max_context_chars)
            context = self._build_context(results, context_chars)
            response["context"] = context
            response["context_chars"] = len(context)
        return response
