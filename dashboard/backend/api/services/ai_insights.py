"""
AI Insights Service
Provides analytics and insights from the AI stack's operational data.
Integrates with aq-report for comprehensive system intelligence.
"""

import asyncio
import subprocess
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

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
            self._cache_timestamp = datetime.utcnow()

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

        age = (datetime.utcnow() - self._cache_timestamp).total_seconds()
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
            "retrieval_breadth": retrieval_breadth,
            "rag_posture": report.get("rag_posture", {}),
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
