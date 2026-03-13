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

    def query(
        self,
        query: str,
        *,
        agent_type: str = "human",
        prefer_local: bool = True,
        generate_response: bool = False,
        mode: str = "auto",
        context: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        keyword_limit: int = 5,
        score_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "query": query,
            "agent_type": agent_type,
            "prefer_local": prefer_local,
            "generate_response": generate_response,
            "mode": mode,
            "limit": limit,
            "keyword_limit": keyword_limit,
            "score_threshold": score_threshold,
        }
        if context is not None:
            payload["context"] = context
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/query"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def tooling_manifest(
        self,
        query: str,
        runtime: str = "python",
        max_tools: Optional[int] = None,
        max_result_chars: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query, "runtime": runtime}
        if max_tools is not None:
            payload["max_tools"] = max_tools
        if max_result_chars is not None:
            payload["max_result_chars"] = max_result_chars
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/workflow/tooling-manifest"), headers=self._headers(), json=payload)
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

    def qa_check(
        self,
        phase: str = "0",
        output_format: str = "json",
        timeout_seconds: int = 60,
        include_sudo: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "phase": phase,
            "format": output_format,
            "timeout_seconds": timeout_seconds,
            "include_sudo": include_sudo,
        }
        with httpx.Client(timeout=max(self.timeout_s, float(timeout_seconds) + 5.0)) as client:
            r = client.post(self._url("/qa/check"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def run_start(
        self,
        query: str,
        safety_mode: str = "plan-readonly",
        token_limit: int = 8000,
        tool_call_limit: int = 40,
        intent_contract: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        contract = intent_contract or {
            "user_intent": query,
            "definition_of_done": "Workflow plan is created and execution can proceed safely.",
            "depth_expectation": "standard",
            "spirit_constraints": [
                "Favor declarative changes over ad-hoc imperative mutations.",
                "Preserve safety guardrails and explicit rollback paths.",
            ],
            "no_early_exit_without": [
                "Validation evidence is captured.",
                "Critical blockers are reported with next action.",
            ],
        }
        payload = {
            "query": query,
            "safety_mode": safety_mode,
            "token_limit": token_limit,
            "tool_call_limit": tool_call_limit,
            "intent_contract": contract,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/workflow/run/start"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def run_get(self, session_id: str, replay: bool = False) -> Dict[str, Any]:
        suffix = "?replay=true" if replay else ""
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url(f"/workflow/run/{session_id}{suffix}"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def run_set_mode(self, session_id: str, safety_mode: str, confirm: bool = False) -> Dict[str, Any]:
        payload = {"safety_mode": safety_mode, "confirm": confirm}
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(
                self._url(f"/workflow/run/{session_id}/mode"),
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            return r.json()

    def run_get_isolation(self, session_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url(f"/workflow/run/{session_id}/isolation"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def run_set_isolation(
        self,
        session_id: str,
        profile: str = "",
        workspace_root: str = "",
        network_policy: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "profile": profile,
            "workspace_root": workspace_root,
            "network_policy": network_policy,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(
                self._url(f"/workflow/run/{session_id}/isolation"),
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            return r.json()

    def run_event(
        self,
        session_id: str,
        event_type: str,
        risk_class: str = "safe",
        approved: bool = False,
        token_delta: int = 0,
        tool_call_delta: int = 0,
        detail: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "event_type": event_type,
            "risk_class": risk_class,
            "approved": approved,
            "token_delta": token_delta,
            "tool_call_delta": tool_call_delta,
            "detail": detail,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(
                self._url(f"/workflow/run/{session_id}/event"),
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            return r.json()

    def run_replay(self, session_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url(f"/workflow/run/{session_id}/replay"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def list_blueprints(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url("/workflow/blueprints"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def parity_scorecard(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url("/parity/scorecard"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def register_runtime(
        self,
        name: str,
        runtime_id: str = "",
        profile: str = "default",
        status: str = "ready",
        runtime_class: str = "generic",
        transport: str = "http",
        endpoint_env_var: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "runtime_id": runtime_id,
            "name": name,
            "profile": profile,
            "status": status,
            "runtime_class": runtime_class,
            "transport": transport,
            "endpoint_env_var": endpoint_env_var,
            "tags": tags or [],
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/control/runtimes/register"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def list_runtimes(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url("/control/runtimes"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def get_runtime(self, runtime_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url(f"/control/runtimes/{runtime_id}"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def update_runtime_status(self, runtime_id: str, status: str, note: str = "") -> Dict[str, Any]:
        payload = {"status": status, "note": note}
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url(f"/control/runtimes/{runtime_id}/status"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def runtime_deploy(
        self,
        runtime_id: str,
        version: str,
        profile: str = "default",
        target: str = "local",
        status: str = "deployed",
        note: str = "",
        deployment_id: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "deployment_id": deployment_id,
            "version": version,
            "profile": profile,
            "target": target,
            "status": status,
            "note": note,
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url(f"/control/runtimes/{runtime_id}/deployments"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def runtime_rollback(self, runtime_id: str, to_deployment_id: str, reason: str = "") -> Dict[str, Any]:
        payload = {"to_deployment_id": to_deployment_id, "reason": reason}
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url(f"/control/runtimes/{runtime_id}/rollback"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def runtime_schedule_policy(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url("/control/runtimes/schedule/policy"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def runtime_schedule(
        self,
        objective: str,
        runtime_class: str = "",
        transport: str = "",
        tags: Optional[List[str]] = None,
        strategy: str = "weighted",
        include_degraded: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "objective": objective,
            "strategy": strategy,
            "include_degraded": include_degraded,
            "requirements": {
                "runtime_class": runtime_class,
                "transport": transport,
                "tags": tags or [],
            },
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(self._url("/control/runtimes/schedule/select"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()

    def ai_coordinator_status(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.get(self._url("/control/ai-coordinator/status"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def ai_coordinator_delegate(
        self,
        task: str,
        *,
        profile: str = "",
        messages: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any] | str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"task": task}
        if profile:
            payload["profile"] = profile
        if messages is not None:
            payload["messages"] = messages
        if context is not None:
            payload["context"] = context
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        with httpx.Client(timeout=max(self.timeout_s, 60.0)) as client:
            r = client.post(self._url("/control/ai-coordinator/delegate"), headers=self._headers(), json=payload)
            r.raise_for_status()
            return r.json()
