#!/usr/bin/env python3
"""
MCP Client for Local Orchestrator

Provides typed access to MCP tools via the hybrid-coordinator and AIDB services.
"""

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


HYBRID_URL = os.getenv("HYBRID_URL", "http://127.0.0.1:8003")
AIDB_URL = os.getenv("AIDB_URL", "http://127.0.0.1:8002")
LLAMA_URL = os.getenv("LLAMA_URL", "http://127.0.0.1:8080")


def _read_key(path_env: str, key_env: str) -> str:
    """Read API key from file or environment."""
    path = os.getenv(path_env, "")
    if path and os.path.isfile(path):
        return open(path).read().strip()
    return os.getenv(key_env, "")


HYBRID_KEY = _read_key("HYBRID_API_KEY_FILE", "HYBRID_API_KEY")
AIDB_KEY = _read_key("AIDB_API_KEY_FILE", "AIDB_API_KEY")


@dataclass
class SearchResult:
    """Result from hybrid search."""
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Hint:
    """Workflow hint from harness."""
    hint_id: str
    content: str
    category: str
    priority: int = 0


@dataclass
class MemoryRecord:
    """Agent memory record."""
    content: str
    memory_type: str
    timestamp: str
    relevance: float = 1.0


class MCPClient:
    """
    MCP client for accessing local AI harness tools.

    Provides typed methods for all MCP tools exposed by mcp-bridge-hybrid.py.
    """

    def __init__(
        self,
        hybrid_url: str = HYBRID_URL,
        aidb_url: str = AIDB_URL,
        llama_url: str = LLAMA_URL,
    ):
        self.hybrid_url = hybrid_url
        self.aidb_url = aidb_url
        self.llama_url = llama_url
        self._stats = {
            "searches": 0,
            "hints": 0,
            "memories_stored": 0,
            "memories_recalled": 0,
            "workflows": 0,
            "errors": 0,
        }

    def _post(self, url: str, payload: dict, key: str = "") -> dict:
        """Make POST request to service."""
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["X-API-Key"] = key

        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            self._stats["errors"] += 1
            return {"error": e.reason, "status": e.code}
        except Exception as e:
            self._stats["errors"] += 1
            return {"error": str(e)}

    def _get(self, url: str, key: str = "") -> dict:
        """Make GET request to service."""
        headers = {}
        if key:
            headers["X-API-Key"] = key

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except Exception as e:
            self._stats["errors"] += 1
            return {"error": str(e)}

    # ── Knowledge & Context Tools ──────────────────────────────────────────

    def hybrid_search(
        self,
        query: str,
        mode: str = "auto",
        generate_response: bool = False,
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Search knowledge base using semantic + keyword hybrid search.

        Args:
            query: Search query
            mode: "auto", "local", or "remote"
            generate_response: Whether to generate LLM synthesis
            limit: Maximum results

        Returns:
            List of SearchResult objects
        """
        self._stats["searches"] += 1

        result = self._post(
            f"{self.hybrid_url}/query",
            {
                "query": query,
                "mode": mode,
                "prefer_local": True,
                "limit": limit,
                "generate_response": generate_response,
            },
            HYBRID_KEY,
        )

        if "error" in result:
            return []

        results = []
        for item in result.get("results", []):
            results.append(SearchResult(
                content=item.get("content", ""),
                source=item.get("source", ""),
                score=item.get("score", 0.0),
                metadata=item.get("metadata", {}),
            ))

        return results

    def get_hints(self, query: str = "", limit: int = 3) -> List[Hint]:
        """
        Get workflow hints for current task.

        Args:
            query: Task description or query
            limit: Maximum hints

        Returns:
            List of Hint objects
        """
        self._stats["hints"] += 1

        params = f"?limit={limit}"
        if query:
            import urllib.parse
            params += f"&q={urllib.parse.quote(query)}"

        result = self._get(f"{self.hybrid_url}/hints{params}", HYBRID_KEY)

        if "error" in result:
            return []

        hints = []
        for item in result.get("hints", []):
            hints.append(Hint(
                hint_id=item.get("hint_id", ""),
                content=item.get("content", ""),
                category=item.get("category", "general"),
                priority=item.get("priority", 0),
            ))

        return hints

    def query_aidb(self, query: str, limit: int = 5) -> List[SearchResult]:
        """
        Direct search of AIDB knowledge base.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of SearchResult objects
        """
        self._stats["searches"] += 1

        result = self._post(
            f"{self.aidb_url}/search",
            {"query": query, "limit": limit},
            AIDB_KEY,
        )

        if "error" in result:
            return []

        results = []
        for item in result.get("results", []):
            results.append(SearchResult(
                content=item.get("content", ""),
                source=item.get("source", ""),
                score=item.get("score", 0.0),
                metadata=item.get("metadata", {}),
            ))

        return results

    # ── Memory Tools ───────────────────────────────────────────────────────

    def store_memory(
        self,
        content: str,
        agent_id: str = "local-orchestrator",
        memory_type: str = "semantic",
    ) -> bool:
        """
        Store fact or decision in agent memory.

        Args:
            content: Content to store
            agent_id: Agent identifier
            memory_type: "semantic", "procedural", or "episodic"

        Returns:
            True if successful
        """
        self._stats["memories_stored"] += 1

        result = self._post(
            f"{self.hybrid_url}/memory/store",
            {
                "content": content,
                "agent_id": agent_id,
                "memory_type": memory_type,
            },
            HYBRID_KEY,
        )

        return "error" not in result

    def recall_memory(
        self,
        query: str,
        agent_id: str = "local-orchestrator",
        limit: int = 5,
    ) -> List[MemoryRecord]:
        """
        Recall stored agent memory.

        Args:
            query: What to recall
            agent_id: Agent identifier
            limit: Maximum records

        Returns:
            List of MemoryRecord objects
        """
        self._stats["memories_recalled"] += 1

        result = self._post(
            f"{self.hybrid_url}/memory/recall",
            {
                "query": query,
                "agent_id": agent_id,
                "limit": limit,
            },
            HYBRID_KEY,
        )

        if "error" in result:
            return []

        memories = []
        for item in result.get("memories", []):
            memories.append(MemoryRecord(
                content=item.get("content", ""),
                memory_type=item.get("memory_type", "semantic"),
                timestamp=item.get("timestamp", ""),
                relevance=item.get("relevance", 1.0),
            ))

        return memories

    # ── Workflow Tools ─────────────────────────────────────────────────────

    def workflow_plan(self, query: str) -> Dict[str, Any]:
        """
        Create phased workflow plan.

        Args:
            query: Task objective

        Returns:
            Plan dict with phases and steps
        """
        self._stats["workflows"] += 1

        return self._post(
            f"{self.hybrid_url}/workflow/plan",
            {"query": query},
            HYBRID_KEY,
        )

    def workflow_blueprints(self) -> List[Dict[str, Any]]:
        """
        Fetch available workflow blueprints.

        Returns:
            List of blueprint definitions
        """
        result = self._get(f"{self.hybrid_url}/workflow/blueprints", HYBRID_KEY)
        return result.get("blueprints", [])

    def workflow_run_start(
        self,
        query: str,
        safety_mode: str = "plan-readonly",
        token_limit: int = 8000,
        tool_call_limit: int = 40,
        intent_contract: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Start guarded workflow run.

        Args:
            query: Task objective
            safety_mode: "plan-readonly" or "execute-mutating"
            token_limit: Maximum tokens for run
            tool_call_limit: Maximum tool calls
            intent_contract: Optional intent contract override

        Returns:
            Run result with status and outputs
        """
        self._stats["workflows"] += 1

        if intent_contract is None:
            intent_contract = {
                "user_intent": query,
                "definition_of_done": f"Complete: {query[:120]}",
                "depth_expectation": "minimum",
                "spirit_constraints": [
                    "follow declarative-first policy",
                    "capture validation evidence",
                ],
                "no_early_exit_without": ["all requested checks complete"],
            }

        return self._post(
            f"{self.hybrid_url}/workflow/run/start",
            {
                "query": query,
                "safety_mode": safety_mode,
                "token_limit": token_limit,
                "tool_call_limit": tool_call_limit,
                "intent_contract": intent_contract,
            },
            HYBRID_KEY,
        )

    # ── Local Model Tools ──────────────────────────────────────────────────

    def llm_complete(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
    ) -> str:
        """
        Generate completion using local llama-cpp model.

        Args:
            prompt: Input prompt
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            stop: Stop sequences

        Returns:
            Generated text
        """
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": stop or [],
        }

        result = self._post(f"{self.llama_url}/completion", payload)

        if "error" in result:
            return f"[ERROR: {result['error']}]"

        return result.get("content", "")

    def llm_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Chat completion using local llama-cpp model.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            max_tokens: Maximum output tokens
            temperature: Sampling temperature

        Returns:
            Assistant response
        """
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        result = self._post(f"{self.llama_url}/v1/chat/completions", payload)

        if "error" in result:
            return f"[ERROR: {result['error']}]"

        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")

        return ""

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about loaded model.

        Returns:
            Model metadata dict
        """
        result = self._get(f"{self.llama_url}/v1/models")

        models = result.get("data", [])
        if models:
            return models[0]

        return {}

    # ── Utility Methods ────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, bool]:
        """
        Check health of all services.

        Returns:
            Dict mapping service name to health status
        """
        return {
            "hybrid": "error" not in self._get(f"{self.hybrid_url}/health", HYBRID_KEY),
            "aidb": "error" not in self._get(f"{self.aidb_url}/health", AIDB_KEY),
            "llama": "error" not in self._get(f"{self.llama_url}/health"),
        }

    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics."""
        return dict(self._stats)


# Singleton instance
_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get global MCP client instance."""
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
