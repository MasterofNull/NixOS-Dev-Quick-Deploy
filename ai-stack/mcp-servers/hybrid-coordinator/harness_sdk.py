"""
Hybrid Coordinator Harness SDK

Unified client for workflow planning/session orchestration, deterministic review
gates, and harness eval calls across local and remote agent runtimes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class HarnessClient:
    base_url: str = "http://127.0.0.1:8003"
    api_key: str = ""
    timeout_s: float = 30.0

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def plan(self, query: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/workflow/plan"), headers=self._headers(), json={"query": query})
            r.raise_for_status()
            return r.json()

    def start_session(self, query: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/workflow/session/start"), headers=self._headers(), json={"query": query})
            r.raise_for_status()
            return r.json()

    def get_session(self, session_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url(f"/workflow/session/{session_id}"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def get_session_with_lineage(self, session_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(
                self._url(f"/workflow/session/{session_id}?lineage=true"),
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    def list_sessions(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url("/workflow/sessions"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def workflow_tree(
        self,
        include_completed: bool = True,
        include_failed: bool = True,
        include_objective: bool = True,
    ) -> Dict[str, Any]:
        qs = (
            f"include_completed={'true' if include_completed else 'false'}"
            f"&include_failed={'true' if include_failed else 'false'}"
            f"&include_objective={'true' if include_objective else 'false'}"
        )
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url(f"/workflow/tree?{qs}"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def advance_session(self, session_id: str, action: str, note: str = "") -> Dict[str, Any]:
        payload = {"action": action}
        if note:
            payload["note"] = note
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(
                self._url(f"/workflow/session/{session_id}/advance"),
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            return r.json()

    def fork_session(self, session_id: str, note: str = "forked session") -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(
                self._url(f"/workflow/session/{session_id}/fork"),
                headers=self._headers(),
                json={"note": note},
            )
            r.raise_for_status()
            return r.json()

    def review_acceptance(
        self,
        response: str,
        query: str = "",
        criteria: Optional[List[str]] = None,
        expected_keywords: Optional[List[str]] = None,
        min_criteria_ratio: float = 0.7,
        min_keyword_ratio: float = 0.6,
        run_harness_eval: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "response": response,
            "query": query,
            "criteria": criteria or [],
            "expected_keywords": expected_keywords or [],
            "min_criteria_ratio": min_criteria_ratio,
            "min_keyword_ratio": min_keyword_ratio,
            "run_harness_eval": run_harness_eval,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/review/acceptance"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def harness_eval(
        self,
        query: str,
        expected_keywords: Optional[List[str]] = None,
        mode: str = "auto",
        max_latency_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "query": query,
            "mode": mode,
            "expected_keywords": expected_keywords or [],
        }
        if max_latency_ms is not None:
            payload["max_latency_ms"] = max_latency_ms
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/harness/eval"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()
