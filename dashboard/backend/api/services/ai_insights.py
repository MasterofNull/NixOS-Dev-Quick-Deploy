"""
AI Insights Service
Provides analytics and insights from the AI stack's operational data.
Integrates with aq-report for comprehensive system intelligence.
"""

import asyncio
import subprocess
import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from api.config.service_endpoints import HYBRID_URL
from api.services.runtime_controls import get_dashboard_rate_limiter, get_operator_audit_log

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _phase4_acceptance_report_path() -> Path:
    configured = os.getenv("PHASE4_ACCEPTANCE_REPORT_PATH", "").strip()
    if configured:
        return Path(configured)
    return _repo_root() / ".reports" / "phase-4-acceptance-report.json"

class AIInsightsService:
    """Service for AI stack insights and analytics."""

    def __init__(self):
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # 1 minute cache

    async def get_full_report(self) -> Dict[str, Any]:
        """Get the complete aq-report data."""
        # Check cache
        if self._is_cache_valid():
            return self._cache

        # Execute aq-report
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["python3", "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/aq-report", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            data = json.loads(result.stdout)

            # Update cache
            self._cache = data
            self._cache_timestamp = datetime.now(timezone.utc)

            return data

        except subprocess.CalledProcessError as e:
            logger.error(f"aq-report execution failed: {e.stderr}")
            raise RuntimeError(f"Failed to generate AI insights report: {e.stderr}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse aq-report JSON: {e}")
            raise RuntimeError(f"Invalid JSON from aq-report: {e}")
        except asyncio.TimeoutError:
            logger.error("aq-report execution timed out")
            raise RuntimeError("AI insights report generation timed out")

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if self._cache is None or self._cache_timestamp is None:
            return False

        age = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
        return age < self._cache_ttl_seconds

    async def get_tool_performance_summary(self) -> Dict[str, Any]:
        """Get summarized tool performance metrics."""
        report = await self.get_full_report()
        tool_perf = report.get("tool_performance", {})

        # Calculate summary statistics
        total_calls = sum(t.get("calls", 0) for t in tool_perf.values())
        total_errors = sum(t.get("error_count", 0) for t in tool_perf.values())

        # Find slowest tools (p95 > 1000ms)
        slow_tools = [
            {
                "name": name,
                "calls": metrics["calls"],
                "p95_ms": metrics["p95_ms"],
                "success_pct": metrics["success_pct"],
            }
            for name, metrics in tool_perf.items()
            if metrics.get("p95_ms", 0) > 1000
        ]
        slow_tools.sort(key=lambda x: x["p95_ms"], reverse=True)

        # Find most-used tools
        top_tools = sorted(
            [
                {
                    "name": name,
                    "calls": metrics["calls"],
                    "p50_ms": metrics["p50_ms"],
                    "success_pct": metrics["success_pct"],
                }
                for name, metrics in tool_perf.items()
            ],
            key=lambda x: x["calls"],
            reverse=True,
        )[:10]

        # Find tools with errors
        error_tools = [
            {
                "name": name,
                "calls": metrics["calls"],
                "error_count": metrics["error_count"],
                "success_pct": metrics["success_pct"],
            }
            for name, metrics in tool_perf.items()
            if metrics.get("error_count", 0) > 0
        ]
        error_tools.sort(key=lambda x: x["error_count"], reverse=True)

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "summary": {
                "total_tools": len(tool_perf),
                "total_calls": total_calls,
                "total_errors": total_errors,
                "error_rate_pct": (total_errors / total_calls * 100) if total_calls > 0 else 0,
            },
            "top_tools": top_tools,
            "slow_tools": slow_tools,
            "error_tools": error_tools,
        }

    async def get_routing_analytics(self) -> Dict[str, Any]:
        """Get LLM routing analytics and model performance."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "current": report.get("routing", {}),
            "recent": report.get("recent_routing", {}),
            "windows": report.get("routing_windows", {}),
            "remote_profile_utilization": report.get("remote_profile_utilization_windows", {}),
        }

    async def get_hint_effectiveness(self) -> Dict[str, Any]:
        """Get hint adoption and effectiveness metrics."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "adoption": report.get("hint_adoption", {}),
            "recent_adoption": report.get("recent_hint_adoption", {}),
            "diversity": report.get("hint_diversity", {}),
            "recent_diversity": report.get("recent_hint_diversity", {}),
            "watchlist": report.get("historical_hint_watchlist", {}),
        }

    async def get_workflow_compliance(self) -> Dict[str, Any]:
        """Get agentic workflow success and compliance metrics."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "intent_contract": report.get("intent_contract_compliance", {}),
            "task_tooling": report.get("task_tooling_quality", {}),
            "delegated_failures": report.get("delegated_prompt_failures", {}),
            "delegated_failure_windows": report.get("delegated_prompt_failure_windows", {}),
            "feedback_acceleration": report.get("feedback_acceleration", {}),
        }

    async def get_phase4_acceptance_summary(self) -> Dict[str, Any]:
        """Return the latest consolidated Phase 4 workflow acceptance report."""
        report_path = _phase4_acceptance_report_path()
        if not report_path.exists():
            return {
                "available": False,
                "status": "no_report",
                "phase": "4",
                "report_path": str(report_path),
                "flows": {},
            }

        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to read Phase 4 acceptance report: %s", exc)
            return {
                "available": False,
                "status": "error",
                "phase": "4",
                "report_path": str(report_path),
                "message": str(exc),
                "flows": {},
            }

        flows = payload.get("flows", {}) if isinstance(payload.get("flows"), dict) else {}
        summarized_flows = {
            key: {
                "label": flow.get("label"),
                "status": flow.get("status"),
                "script": flow.get("script"),
                "ended_at": flow.get("ended_at"),
            }
            for key, flow in flows.items()
            if isinstance(flow, dict)
        }
        passed = sum(1 for flow in summarized_flows.values() if flow.get("status") == "passed")
        failed = sum(1 for flow in summarized_flows.values() if flow.get("status") != "passed")
        return {
            "available": True,
            "status": payload.get("status", "unknown"),
            "phase": str(payload.get("phase", "4")),
            "generated_at": payload.get("generated_at"),
            "report_path": str(report_path),
            "summary": {
                "total_flows": len(summarized_flows),
                "passed_flows": passed,
                "failed_flows": failed,
            },
            "flows": summarized_flows,
        }

    async def get_a2a_readiness(self) -> Dict[str, Any]:
        """Get A2A compatibility readiness from the live hybrid coordinator."""
        agent_card_url = f"{HYBRID_URL.rstrip('/')}/.well-known/agent.json"
        rpc_url = f"{HYBRID_URL.rstrip('/')}/a2a"
        try:
            request = Request(agent_card_url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=10.0) as response:
                card = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.error("Failed to get A2A agent card: %s", exc)
            return {
                "available": False,
                "status": "unavailable",
                "agent_card_url": agent_card_url,
                "rpc_url": rpc_url,
                "error": str(exc),
            }

        capabilities = card.get("capabilities", {}) if isinstance(card.get("capabilities"), dict) else {}
        skills = card.get("skills", []) if isinstance(card.get("skills"), list) else []
        endpoints = card.get("endpoints", {}) if isinstance(card.get("endpoints"), dict) else {}
        protocol_version = str(card.get("protocolVersion", "") or "")
        required_methods = [
            "agent/getCard",
            "message/send",
            "message/stream",
            "tasks/get",
            "tasks/list",
            "tasks/cancel",
        ]
        input_modes = card.get("defaultInputModes", []) if isinstance(card.get("defaultInputModes"), list) else []
        output_modes = card.get("defaultOutputModes", []) if isinstance(card.get("defaultOutputModes"), list) else []
        task_events_url = endpoints.get("taskEvents")

        return {
            "available": True,
            "status": "ready" if protocol_version and endpoints.get("rpc") and task_events_url else "degraded",
            "protocol_version": protocol_version,
            "agent_card_url": agent_card_url,
            "rpc_url": endpoints.get("rpc") or rpc_url,
            "task_events_url": task_events_url,
            "streaming": bool(capabilities.get("streaming", False)),
            "push_notifications": bool(capabilities.get("pushNotifications", False)),
            "state_transition_history": bool(capabilities.get("stateTransitionHistory", False)),
            "input_modes": input_modes,
            "output_modes": output_modes,
            "features": {
                "message_stream": True,
                "task_events": bool(task_events_url),
                "task_artifacts": True,
                "status_messages": True,
            },
            "skills": {
                "count": len(skills),
                "ids": [str(item.get("id", "")).strip() for item in skills if isinstance(item, dict)][:10],
            },
            "methods": {
                "implemented": required_methods,
                "count": len(required_methods),
            },
        }

    async def get_security_compliance_summary(self) -> Dict[str, Any]:
        """Summarize dashboard/operator security and compliance controls."""
        audit_log = get_operator_audit_log()
        rate_limiter = get_dashboard_rate_limiter()
        audit_summary = audit_log.summary(limit=500)
        integrity = audit_summary.get("integrity") or {}
        csp = str(
            os.getenv(
                "DASHBOARD_CSP",
                "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'",
            )
        )
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "in_progress",
            "controls": {
                "content_security_policy": bool(csp),
                "security_headers": True,
                "rate_limiting": bool(rate_limiter.enabled()),
                "operator_audit_log": bool(audit_summary.get("append_only")),
                "tamper_evident_audit_sealing": bool(audit_summary.get("tamper_evident")),
                "dashboard_security_scan_automation": True,
                "secrets_rotation_planning": True,
            },
            "rate_limiting": {
                "enabled": bool(rate_limiter.enabled()),
                "window_seconds": int(os.getenv("DASHBOARD_RATE_LIMIT_WINDOW_SECONDS", "60") or 60),
                "default_rpm": int(os.getenv("DASHBOARD_RATE_LIMIT_DEFAULT_RPM", "240") or 240),
                "operator_write_rpm": int(os.getenv("DASHBOARD_RATE_LIMIT_OPERATOR_WRITE_RPM", "30") or 30),
                "search_rpm": int(os.getenv("DASHBOARD_RATE_LIMIT_SEARCH_RPM", "90") or 90),
            },
            "audit": audit_summary,
            "audit_integrity": integrity,
            "gaps": [
                "automated compliance report export still pending",
                "external security scan automation still pending",
                "live secrets rotation execution still requires explicit operator approval",
            ],
        }

    async def get_query_complexity_analysis(self) -> Dict[str, Any]:
        """Get query complexity and gap analysis."""
        report = await self.get_full_report()

        # Extract route_search latency decomposition for complexity analysis
        route_decomp = report.get("route_search_latency_decomposition", {})

        # Get query gaps (unanswered queries)
        query_gaps = report.get("query_gaps", [])

        # Get retrieval breadth (complexity indicator)
        retrieval_breadth = report.get("route_retrieval_breadth_windows", {})

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "latency_breakdown": route_decomp,
            "query_gaps": query_gaps,
            "gap_remediation": report.get("gap_remediation", {}),
            "retrieval_breadth": retrieval_breadth,
            "rag_posture": report.get("rag_posture", {}),
        }

    async def get_performance_hotspots(self) -> Dict[str, Any]:
        """Return the highest-signal performance hotspots for current optimization work."""
        report = await self.get_full_report()
        cache = report.get("cache", {}) if isinstance(report.get("cache"), dict) else {}
        rag_posture = report.get("rag_posture", {}) if isinstance(report.get("rag_posture"), dict) else {}
        route_latency = (
            report.get("route_search_latency_decomposition", {})
            if isinstance(report.get("route_search_latency_decomposition"), dict)
            else {}
        )
        retrieval_breadth = (
            report.get("route_retrieval_breadth", {})
            if isinstance(report.get("route_retrieval_breadth"), dict)
            else {}
        )
        retrieval_windows = (
            report.get("route_retrieval_breadth_windows", {})
            if isinstance(report.get("route_retrieval_breadth_windows"), dict)
            else {}
        )
        recent_mix = ((rag_posture.get("retrieval_mix") or {}).get("recent") or {}) if isinstance(rag_posture, dict) else {}
        top_candidate = None
        for candidate in rag_posture.get("prewarm_candidates", []) or []:
            if isinstance(candidate, dict) and candidate.get("id"):
                top_candidate = {
                    "id": candidate.get("id"),
                    "name": candidate.get("name"),
                }
                break

        hotspots: List[Dict[str, Any]] = []
        route_p95 = route_latency.get("p95_ms")
        if route_p95 is None:
            route_p95 = route_latency.get("overall_p95_ms")
        if route_p95 is not None:
            hotspots.append(
                {
                    "id": "route_latency",
                    "label": "Route Search Latency",
                    "status": "watch" if float(route_p95) >= 2500 else "healthy",
                    "summary": f"p95={float(route_p95):.0f}ms",
                }
            )
        if cache.get("available") and cache.get("hit_pct") is not None:
            cache_hit = float(cache.get("hit_pct") or 0.0)
            hotspots.append(
                {
                    "id": "semantic_cache",
                    "label": "Semantic Cache Hit Rate",
                    "status": "watch" if cache_hit < 60.0 else "healthy",
                    "summary": f"hit_rate={cache_hit:.1f}%",
                }
            )
        breadth_avg = retrieval_breadth.get("avg_collection_count")
        if breadth_avg is not None:
            hotspots.append(
                {
                    "id": "retrieval_breadth",
                    "label": "Retrieval Breadth",
                    "status": "watch" if float(breadth_avg) > 2.5 else "healthy",
                    "summary": f"avg_collections={float(breadth_avg):.2f}",
                }
            )
        memory_miss_pct = rag_posture.get("memory_recall_miss_pct")
        if memory_miss_pct is not None:
            hotspots.append(
                {
                    "id": "memory_recall_quality",
                    "label": "Memory Recall Quality",
                    "status": "watch" if float(memory_miss_pct) >= 50.0 else "healthy",
                    "summary": f"miss_rate={float(memory_miss_pct):.1f}%",
                }
            )

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "hotspots": hotspots,
            "route_latency": route_latency,
            "cache": cache,
            "retrieval_breadth": retrieval_breadth,
            "retrieval_breadth_windows": retrieval_windows,
            "rag_posture": {
                "status": rag_posture.get("status"),
                "reasons": rag_posture.get("reasons", []),
                "recent_retrieval_calls": rag_posture.get("recent_retrieval_calls"),
                "retrieval_mix_recent": recent_mix,
                "memory_recall_share_pct": rag_posture.get("memory_recall_share_pct"),
                "memory_recall_miss_pct": memory_miss_pct,
                "top_prewarm_candidate": top_candidate,
            },
        }

    async def get_operator_insight_digest(self, insight_target: str) -> Dict[str, Any]:
        """Return a compact insight summary suitable for operator search guidance."""
        normalized_target = str(insight_target or "full_report").strip().lower()
        if normalized_target == "a2a_readiness":
            readiness = await self.get_a2a_readiness()
            return {
                "target": normalized_target,
                "title": "A2A Readiness",
                "status": readiness.get("status", "unknown"),
                "summary": (
                    f"protocol={readiness.get('protocol_version', '--')} "
                    f"| streaming={readiness.get('streaming', False)} "
                    f"| methods={readiness.get('methods', {}).get('count', 0)}"
                ),
            }
        if normalized_target == "query_complexity":
            complexity = await self.get_query_complexity_analysis()
            query_gaps = complexity.get("query_gaps") or []
            rag_posture = complexity.get("rag_posture") or {}
            return {
                "target": normalized_target,
                "title": "Query Complexity",
                "status": "active",
                "summary": (
                    f"query_gaps={len(query_gaps)} "
                    f"| rag_enabled={rag_posture.get('enabled', 'unknown')} "
                    f"| breadth_windows={len(complexity.get('retrieval_breadth') or {})}"
                ),
            }
        if normalized_target == "performance_hotspots":
            hotspots = await self.get_performance_hotspots()
            top_hotspot = (hotspots.get("hotspots") or [{}])[0]
            return {
                "target": normalized_target,
                "title": "Performance Hotspots",
                "status": "active",
                "summary": (
                    f"hotspots={len(hotspots.get('hotspots') or [])} "
                    f"| top={top_hotspot.get('id', '--')} "
                    f"| prewarm={((hotspots.get('rag_posture') or {}).get('top_prewarm_candidate') or {}).get('id', '--')}"
                ),
            }

        report = await self.get_full_report()
        recommendations = report.get("structured_recommendations") or report.get("recommendations") or []
        query_gaps = report.get("query_gaps") or []
        return {
            "target": "full_report",
            "title": "Full Insights Report",
            "status": "ready",
            "summary": (
                f"recommendations={len(recommendations)} "
                f"| query_gaps={len(query_gaps)} "
                f"| generated={report.get('generated_at', '--')}"
            ),
        }

    async def get_cache_analytics(self) -> Dict[str, Any]:
        """Get cache performance analytics."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "cache": report.get("cache", {}),
            "cache_prewarm": report.get("cache_prewarm", {}),
        }

    async def get_system_health_overview(self) -> Dict[str, Any]:
        """Get high-level system health overview."""
        report = await self.get_full_report()
        a2a = await self.get_a2a_readiness()

        # Aggregate health indicators
        routing = report.get("routing", {})
        cache = report.get("cache", {})
        recent_health = report.get("recent_health", {})
        eval_trend = report.get("eval_trend", {})

        # Determine overall health status
        issues = []

        if not routing.get("available", False):
            issues.append("LLM routing unavailable")

        if not cache.get("available", False):
            issues.append("Cache unavailable")

        if not recent_health.get("healthy", True):
            issues.append(f"{len(recent_health.get('slow_tools', []))} slow tools, {len(recent_health.get('flaky_tools', []))} flaky tools")

        if eval_trend.get("trend") == "falling":
            issues.append(f"Eval score falling (latest: {eval_trend.get('latest_pct')}%)")

        overall_status = "healthy" if len(issues) == 0 else "degraded" if len(issues) < 3 else "unhealthy"

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "status": overall_status,
            "issues": issues,
            "a2a": a2a,
            "routing": routing,
            "cache": cache,
            "recent_health": recent_health,
            "eval_trend": eval_trend,
            "recommendations": report.get("recommendations", []),
        }

    async def get_agent_lessons(self) -> Dict[str, Any]:
        """Get agent lessons and continuous learning metrics."""
        report = await self.get_full_report()

        return {
            "timestamp": report.get("generated_at"),
            "window": report.get("window"),
            "lessons": report.get("agent_lessons", {}),
        }

    async def get_structured_actions(self) -> List[Dict[str, Any]]:
        """Get structured actionable recommendations."""
        report = await self.get_full_report()
        return report.get("structured_actions", [])


# Singleton instance
_insights_service: Optional[AIInsightsService] = None


def get_insights_service() -> AIInsightsService:
    """Get singleton insights service instance."""
    global _insights_service
    if _insights_service is None:
        _insights_service = AIInsightsService()
    return _insights_service
