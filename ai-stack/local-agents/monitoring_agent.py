#!/usr/bin/env python3
"""
Monitoring Agent - Autonomous System Health Management

Enables local agents to monitor system health, detect issues, and trigger
automated remediation:
- Health check monitoring
- Alert detection and triage
- Proactive issue detection
- Self-diagnosis capabilities
- Integration with alert engine

Part of Phase 11 Batch 11.4: Monitoring & Alert Integration
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Add observability to path for alert engine integration
sys.path.insert(0, str(Path(__file__).parent.parent / "observability"))

try:
    from alert_engine import AlertEngine, AlertSeverity
    from baseline_profiler import BaselineProfiler, MetricType
except ImportError:
    AlertEngine = None
    AlertSeverity = None
    BaselineProfiler = None
    MetricType = None

from agent_executor import AgentType, LocalAgentExecutor, Task, TaskStatus
from tool_registry import ToolRegistry, get_registry

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    """Health check result"""
    component: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metrics: Dict[str, Any] = field(default_factory=dict)
    remediation_suggested: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metrics": self.metrics,
            "remediation_suggested": self.remediation_suggested,
        }


class MonitoringAgent:
    """
    Autonomous monitoring agent that checks system health and triggers remediation.

    Features:
    - Periodic health checks
    - Alert detection and triage
    - Proactive issue detection
    - Self-diagnosis
    - Automated remediation via tools
    """

    def __init__(
        self,
        executor: Optional[LocalAgentExecutor] = None,
        tool_registry: Optional[ToolRegistry] = None,
        alert_engine: Optional["AlertEngine"] = None,
        profiler: Optional["BaselineProfiler"] = None,
        check_interval_seconds: int = 60,
    ):
        self.executor = executor
        self.tool_registry = tool_registry or get_registry()
        self.alert_engine = alert_engine
        self.profiler = profiler
        self.check_interval_seconds = check_interval_seconds

        # Health check results
        self.health_history: List[HealthCheck] = []

        # Issue detection
        self.detected_issues: List[Dict] = []

        # Remediation tracking
        self.remediations_attempted: int = 0
        self.remediations_successful: int = 0

        logger.info(
            f"Monitoring agent initialized: interval={check_interval_seconds}s, "
            f"alert_engine={alert_engine is not None}, "
            f"profiler={profiler is not None}"
        )

    async def check_system_health(self) -> List[HealthCheck]:
        """
        Check overall system health.

        Returns:
            List of health check results
        """
        checks = []

        # Check services
        checks.append(await self._check_llama_service())
        checks.append(await self._check_hybrid_coordinator())
        checks.append(await self._check_aidb_service())

        # Check resources
        checks.append(await self._check_memory_usage())
        checks.append(await self._check_disk_space())

        # Check agent performance
        if self.executor:
            checks.append(await self._check_agent_performance())

        # Store in history
        self.health_history.extend(checks)

        # Keep last 1000 checks
        self.health_history = self.health_history[-1000:]

        return checks

    async def _check_llama_service(self) -> HealthCheck:
        """Check llama.cpp service health"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://127.0.0.1:8080/health",
                    timeout=5.0,
                )

                if response.status_code == 200:
                    return HealthCheck(
                        component="llama-cpp",
                        status=HealthStatus.HEALTHY,
                        message="Service responding normally",
                    )
                else:
                    return HealthCheck(
                        component="llama-cpp",
                        status=HealthStatus.DEGRADED,
                        message=f"HTTP {response.status_code}",
                        remediation_suggested="restart_service",
                    )

        except Exception as e:
            return HealthCheck(
                component="llama-cpp",
                status=HealthStatus.CRITICAL,
                message=f"Service not responding: {e}",
                remediation_suggested="restart_service",
            )

    async def _check_hybrid_coordinator(self) -> HealthCheck:
        """Check hybrid coordinator health"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://127.0.0.1:8003/health",
                    timeout=5.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    status_str = data.get("status", "unknown")

                    if status_str == "healthy":
                        status = HealthStatus.HEALTHY
                    elif status_str == "degraded":
                        status = HealthStatus.DEGRADED
                    else:
                        status = HealthStatus.UNHEALTHY

                    return HealthCheck(
                        component="hybrid-coordinator",
                        status=status,
                        message=data.get("message", "Service responding"),
                        metrics=data.get("metrics", {}),
                    )
                else:
                    return HealthCheck(
                        component="hybrid-coordinator",
                        status=HealthStatus.DEGRADED,
                        message=f"HTTP {response.status_code}",
                    )

        except Exception as e:
            return HealthCheck(
                component="hybrid-coordinator",
                status=HealthStatus.CRITICAL,
                message=f"Service not responding: {e}",
                remediation_suggested="restart_service",
            )

    async def _check_aidb_service(self) -> HealthCheck:
        """Check AIDB service health"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://127.0.0.1:8002/health",
                    timeout=5.0,
                )

                if response.status_code == 200:
                    return HealthCheck(
                        component="aidb",
                        status=HealthStatus.HEALTHY,
                        message="Service responding normally",
                    )
                else:
                    return HealthCheck(
                        component="aidb",
                        status=HealthStatus.DEGRADED,
                        message=f"HTTP {response.status_code}",
                    )

        except Exception as e:
            return HealthCheck(
                component="aidb",
                status=HealthStatus.CRITICAL,
                message=f"Service not responding: {e}",
                remediation_suggested="restart_service",
            )

    async def _check_memory_usage(self) -> HealthCheck:
        """Check system memory usage"""
        try:
            # Use get_system_info tool if available
            tool = self.tool_registry.get_tool("get_system_info")
            if tool:
                from tool_registry import ToolCall

                tool_call = ToolCall(
                    id="health-memory",
                    tool_name="get_system_info",
                    arguments={},
                )

                result = await self.tool_registry.execute_tool_call(tool_call)

                if result.status == "completed" and result.result:
                    memory = result.result.get("memory", {})
                    total_mb = memory.get("total_mb", 0)
                    used_mb = memory.get("used_mb", 0)

                    if total_mb > 0:
                        usage_percent = (used_mb / total_mb) * 100

                        if usage_percent > 90:
                            status = HealthStatus.CRITICAL
                            remediation = "clear_cache"
                        elif usage_percent > 80:
                            status = HealthStatus.DEGRADED
                            remediation = "clear_cache"
                        else:
                            status = HealthStatus.HEALTHY
                            remediation = None

                        return HealthCheck(
                            component="memory",
                            status=status,
                            message=f"Memory usage: {usage_percent:.1f}%",
                            metrics={"usage_percent": usage_percent, "used_mb": used_mb},
                            remediation_suggested=remediation,
                        )

            # Fallback
            return HealthCheck(
                component="memory",
                status=HealthStatus.HEALTHY,
                message="Unable to check (tool unavailable)",
            )

        except Exception as e:
            return HealthCheck(
                component="memory",
                status=HealthStatus.HEALTHY,
                message=f"Check failed: {e}",
            )

    async def _check_disk_space(self) -> HealthCheck:
        """Check disk space"""
        try:
            tool = self.tool_registry.get_tool("get_system_info")
            if tool:
                from tool_registry import ToolCall

                tool_call = ToolCall(
                    id="health-disk",
                    tool_name="get_system_info",
                    arguments={},
                )

                result = await self.tool_registry.execute_tool_call(tool_call)

                if result.status == "completed" and result.result:
                    disk = result.result.get("disk", {})
                    use_percent_str = disk.get("use_percent", "0%")

                    try:
                        use_percent = float(use_percent_str.rstrip("%"))

                        if use_percent > 95:
                            status = HealthStatus.CRITICAL
                            remediation = "rotate_logs"
                        elif use_percent > 85:
                            status = HealthStatus.DEGRADED
                            remediation = "rotate_logs"
                        else:
                            status = HealthStatus.HEALTHY
                            remediation = None

                        return HealthCheck(
                            component="disk",
                            status=status,
                            message=f"Disk usage: {use_percent}%",
                            metrics={"usage_percent": use_percent},
                            remediation_suggested=remediation,
                        )
                    except ValueError:
                        pass

            # Fallback
            return HealthCheck(
                component="disk",
                status=HealthStatus.HEALTHY,
                message="Unable to check (tool unavailable)",
            )

        except Exception as e:
            return HealthCheck(
                component="disk",
                status=HealthStatus.HEALTHY,
                message=f"Check failed: {e}",
            )

    async def _check_agent_performance(self) -> HealthCheck:
        """Check local agent performance"""
        if not self.executor:
            return HealthCheck(
                component="agent-performance",
                status=HealthStatus.HEALTHY,
                message="Executor not available",
            )

        stats = self.executor.get_performance_stats()
        agent_stats = stats.get("agent", {})

        success_rate = agent_stats.get("success_rate", 1.0)
        total_tasks = agent_stats.get("total_tasks", 0)

        if total_tasks < 10:
            # Not enough data
            return HealthCheck(
                component="agent-performance",
                status=HealthStatus.HEALTHY,
                message=f"Limited data ({total_tasks} tasks)",
                metrics={"success_rate": success_rate, "total_tasks": total_tasks},
            )

        if success_rate < 0.6:
            status = HealthStatus.CRITICAL
            remediation = "switch_to_remote"
        elif success_rate < 0.75:
            status = HealthStatus.DEGRADED
            remediation = "monitor_closely"
        else:
            status = HealthStatus.HEALTHY
            remediation = None

        return HealthCheck(
            component="agent-performance",
            status=status,
            message=f"Success rate: {success_rate:.1%} ({total_tasks} tasks)",
            metrics={"success_rate": success_rate, "total_tasks": total_tasks},
            remediation_suggested=remediation,
        )

    async def triage_issue(self, check: HealthCheck) -> Optional[Task]:
        """
        Triage a health check issue and create remediation task if needed.

        Args:
            check: Health check result

        Returns:
            Remediation task or None if no action needed
        """
        if check.status == HealthStatus.HEALTHY:
            return None

        if not check.remediation_suggested:
            logger.info(f"Issue detected in {check.component} but no remediation available")
            return None

        # Create remediation task
        task = Task(
            id=f"remediation-{check.component}-{int(datetime.now().timestamp())}",
            objective=f"Remediate {check.component}: {check.remediation_suggested}",
            context={
                "component": check.component,
                "issue": check.message,
                "remediation": check.remediation_suggested,
                "health_check": check.to_dict(),
            },
            complexity=0.3,  # Remediation tasks are typically simple
            latency_critical=True,  # Want fast response
        )

        logger.info(f"Created remediation task for {check.component}: {check.remediation_suggested}")

        return task

    async def execute_remediation(self, task: Task) -> bool:
        """
        Execute a remediation task.

        Args:
            task: Remediation task

        Returns:
            True if remediation successful
        """
        self.remediations_attempted += 1

        try:
            # Execute task via executor if available
            if self.executor:
                result = await self.executor.execute_task(task, agent_type=AgentType.AGENT)

                if result.status == TaskStatus.COMPLETED:
                    self.remediations_successful += 1
                    logger.info(f"Remediation successful: {task.objective}")
                    return True
                else:
                    logger.error(f"Remediation failed: {task.objective} - {result.error}")
                    return False
            else:
                logger.warning("No executor available for remediation")
                return False

        except Exception as e:
            logger.error(f"Remediation execution failed: {e}")
            return False

    async def create_alert_for_issue(self, check: HealthCheck):
        """Create alert in alert engine for health issue"""
        if not self.alert_engine or not AlertSeverity:
            logger.warning("Alert engine not available")
            return

        # Map health status to alert severity
        severity_map = {
            HealthStatus.HEALTHY: None,
            HealthStatus.DEGRADED: AlertSeverity.WARNING,
            HealthStatus.UNHEALTHY: AlertSeverity.CRITICAL,
            HealthStatus.CRITICAL: AlertSeverity.EMERGENCY,
        }

        severity = severity_map.get(check.status)
        if not severity:
            return  # No alert for healthy status

        await self.alert_engine.create_alert(
            title=f"Health Issue: {check.component}",
            message=f"{check.message}\n\nSuggested remediation: {check.remediation_suggested or 'None'}",
            severity=severity,
            source="monitoring_agent",
            component=check.component,
            auto_remediate=check.remediation_suggested is not None,
            remediation_workflow=check.remediation_suggested,
            metadata=check.to_dict(),
        )

        logger.info(f"Created alert for {check.component} ({severity.value})")

    async def monitoring_loop(self):
        """Main monitoring loop"""
        logger.info("Starting monitoring loop")

        while True:
            try:
                # Run health checks
                checks = await self.check_system_health()

                # Process each check
                for check in checks:
                    # Create alerts for issues
                    if check.status != HealthStatus.HEALTHY:
                        await self.create_alert_for_issue(check)

                        # Triage and remediate if needed
                        task = await self.triage_issue(check)
                        if task:
                            await self.execute_remediation(task)

                # Report status
                unhealthy_count = len([c for c in checks if c.status != HealthStatus.HEALTHY])
                if unhealthy_count > 0:
                    logger.warning(f"Health check: {unhealthy_count}/{len(checks)} components unhealthy")
                else:
                    logger.info(f"Health check: All {len(checks)} components healthy")

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)

    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        recent_checks = self.health_history[-100:] if self.health_history else []

        healthy_count = len([c for c in recent_checks if c.status == HealthStatus.HEALTHY])
        degraded_count = len([c for c in recent_checks if c.status == HealthStatus.DEGRADED])
        unhealthy_count = len([c for c in recent_checks if c.status == HealthStatus.UNHEALTHY])
        critical_count = len([c for c in recent_checks if c.status == HealthStatus.CRITICAL])

        return {
            "total_checks": len(self.health_history),
            "recent_checks": len(recent_checks),
            "healthy_count": healthy_count,
            "degraded_count": degraded_count,
            "unhealthy_count": unhealthy_count,
            "critical_count": critical_count,
            "remediations_attempted": self.remediations_attempted,
            "remediations_successful": self.remediations_successful,
            "remediation_success_rate": (
                self.remediations_successful / self.remediations_attempted
                if self.remediations_attempted > 0 else 0.0
            ),
        }


if __name__ == "__main__":
    # Test monitoring agent
    logging.basicConfig(level=logging.INFO)

    async def test():
        from tool_registry import initialize_builtin_tools

        # Initialize
        registry = get_registry()
        initialize_builtin_tools(registry)

        # Create monitoring agent
        agent = MonitoringAgent(tool_registry=registry, check_interval_seconds=10)

        # Run health checks
        checks = await agent.check_system_health()

        print("\nHealth Check Results:")
        for check in checks:
            print(f"\n{check.component}:")
            print(f"  Status: {check.status.value}")
            print(f"  Message: {check.message}")
            if check.remediation_suggested:
                print(f"  Remediation: {check.remediation_suggested}")

        # Get statistics
        stats = agent.get_statistics()
        print(f"\nStatistics:")
        print(json.dumps(stats, indent=2))

    asyncio.run(test())
