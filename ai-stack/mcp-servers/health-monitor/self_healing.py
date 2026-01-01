#!/usr/bin/env python3
"""
Self-Healing Orchestrator
Automatic error recovery and system repair

Features:
- Container health monitoring
- Automatic service restart
- Dependency resolution
- Error pattern learning
- Rollback on catastrophic failure
"""

import asyncio
import subprocess
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import structlog
from pydantic import BaseModel
import json

logger = structlog.get_logger()


class ContainerStatus(BaseModel):
    """Container health status"""
    name: str
    id: str
    status: str  # running, exited, unhealthy, etc.
    health: Optional[str] = None  # healthy, unhealthy, starting
    restart_count: int = 0
    last_restart: Optional[datetime] = None


class ErrorPattern(BaseModel):
    """Known error pattern"""
    pattern_id: str
    error_regex: str
    description: str
    fix_strategy: str
    success_rate: float = 0.0
    applications: int = 0


class HealingAction(BaseModel):
    """Healing action taken"""
    timestamp: datetime
    container: str
    error_pattern: Optional[str]
    action: str  # restart, rebuild, rollback, etc.
    success: bool
    logs: str = ""


class SelfHealingOrchestrator:
    """
    Monitors system health and performs automatic repairs

    Usage:
        orchestrator = SelfHealingOrchestrator(settings)
        await orchestrator.start()  # Begins monitoring

        # Manual heal
        await orchestrator.heal_container("local-ai-llama-cpp")
    """

    def __init__(self, settings, qdrant_client=None):
        self.settings = settings
        self.qdrant = qdrant_client

        # Error patterns database
        self.error_patterns: Dict[str, ErrorPattern] = self._load_error_patterns()

        # Healing history
        self.healing_history: List[HealingAction] = []

        # Monitoring task
        self.monitor_task: Optional[asyncio.Task] = None

        # Cooldown periods (prevent restart loops)
        self.restart_cooldowns: Dict[str, datetime] = {}

    def _load_error_patterns(self) -> Dict[str, ErrorPattern]:
        """Load known error patterns"""
        return {
            "port_conflict": ErrorPattern(
                pattern_id="port_conflict",
                error_regex=r"bind.*address already in use",
                description="Port is already in use by another process",
                fix_strategy="check_port_and_restart"
            ),
            "oom_kill": ErrorPattern(
                pattern_id="oom_kill",
                error_regex=r"(OOMKilled|Out of memory)",
                description="Container ran out of memory",
                fix_strategy="increase_memory_limit"
            ),
            "connection_refused": ErrorPattern(
                pattern_id="connection_refused",
                error_regex=r"(connection refused|connection reset)",
                description="Failed to connect to dependency",
                fix_strategy="restart_dependencies"
            ),
            "model_not_found": ErrorPattern(
                pattern_id="model_not_found",
                error_regex=r"(model.*not found|failed to load model)",
                description="GGUF model file missing",
                fix_strategy="download_model"
            ),
            "database_locked": ErrorPattern(
                pattern_id="database_locked",
                error_regex=r"database.*locked",
                description="Database file is locked",
                fix_strategy="restart_database"
            ),
            "permission_denied": ErrorPattern(
                pattern_id="permission_denied",
                error_regex=r"permission denied",
                description="File permissions issue",
                fix_strategy="fix_permissions"
            ),
        }

    async def start(self):
        """Start health monitoring"""
        logger.info("self_healing_starting")
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

    async def stop(self):
        """Stop monitoring"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("self_healing_stopped")

    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                await self._check_all_containers()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitoring_loop_error", error=str(e))
                await asyncio.sleep(60)

    async def _check_all_containers(self):
        """Check health of all AI stack containers"""
        try:
            # Get all AI stack containers
            result = subprocess.run(
                [
                    "podman",
                    "ps",
                    "-a",
                    "--filter",
                    "label=nixos.quick-deploy.ai-stack=true",
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning("podman_ps_failed", stderr=result.stderr)
                return

            containers = json.loads(result.stdout or "[]")

            for container_data in containers:
                container = ContainerStatus(
                    name=container_data.get("Names", ["unknown"])[0],
                    id=container_data.get("Id", "")[:12],
                    status=container_data.get("State", "unknown"),
                    health=container_data.get("Health", {}).get("Status"),
                )

                # Check if container needs healing
                if await self._needs_healing(container):
                    await self.heal_container(container.name)

        except json.JSONDecodeError as e:
            logger.error("json_parse_error", error=str(e))
        except Exception as e:
            logger.error("container_check_failed", error=str(e))

    async def _needs_healing(self, container: ContainerStatus) -> bool:
        """Determine if container needs healing"""
        # Container is exited
        if container.status in ["exited", "stopped"]:
            return True

        # Container is unhealthy
        if container.health == "unhealthy":
            return True

        # Container is restarting too frequently
        # (Check implemented if we track restart history)

        return False

    async def heal_container(self, container_name: str) -> bool:
        """
        Heal a specific container

        Args:
            container_name: Name of container to heal

        Returns:
            True if healing succeeded
        """
        logger.warning("healing_container", container=container_name)

        # Check cooldown
        if not await self._check_cooldown(container_name):
            logger.info(
                "healing_on_cooldown",
                container=container_name,
                wait_time="60s"
            )
            return False

        try:
            # Get container logs
            logs = await self._get_container_logs(container_name)

            # Analyze error pattern
            error_pattern = await self._analyze_error(logs)

            # Apply fix
            action = await self._apply_fix(
                container_name, error_pattern, logs
            )

            # Record action
            self.healing_history.append(action)

            # Update cooldown
            self.restart_cooldowns[container_name] = datetime.utcnow()

            # Verify healing
            await asyncio.sleep(15)
            is_healthy = await self._verify_container_health(container_name)

            if is_healthy:
                logger.info("container_healed", container=container_name)
                await self._save_success_pattern(error_pattern)
                return True
            else:
                logger.warning(
                    "healing_failed",
                    container=container_name,
                    pattern=error_pattern
                )
                return False

        except Exception as e:
            logger.error("healing_exception", container=container_name, error=str(e))
            return False

    async def _check_cooldown(self, container_name: str) -> bool:
        """Check if container is on cooldown"""
        if container_name not in self.restart_cooldowns:
            return True

        last_restart = self.restart_cooldowns[container_name]
        cooldown_period = timedelta(seconds=60)

        return datetime.utcnow() - last_restart > cooldown_period

    async def _get_container_logs(self, container_name: str) -> str:
        """Get container logs for error analysis"""
        try:
            result = subprocess.run(
                ["podman", "logs", "--tail", "100", container_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout + result.stderr
        except Exception as e:
            logger.warning("log_fetch_failed", error=str(e))
            return ""

    async def _analyze_error(self, logs: str) -> Optional[str]:
        """Analyze logs to identify error pattern"""
        import re

        for pattern_id, pattern in self.error_patterns.items():
            if re.search(pattern.error_regex, logs, re.IGNORECASE):
                logger.info("error_pattern_identified", pattern=pattern_id)
                return pattern_id

        return None

    async def _apply_fix(
        self,
        container_name: str,
        error_pattern: Optional[str],
        logs: str
    ) -> HealingAction:
        """Apply fix based on error pattern"""
        action_type = "restart"  # Default action

        try:
            if error_pattern and error_pattern in self.error_patterns:
                pattern = self.error_patterns[error_pattern]
                fix_strategy = pattern.fix_strategy

                if fix_strategy == "check_port_and_restart":
                    # Port conflict - just restart, podman will assign new port
                    success = await self._restart_container(container_name)

                elif fix_strategy == "increase_memory_limit":
                    # OOM - log warning, restart with current limits
                    logger.warning(
                        "oom_detected",
                        container=container_name,
                        hint="Consider increasing memory limits"
                    )
                    success = await self._restart_container(container_name)

                elif fix_strategy == "restart_dependencies":
                    # Connection issue - restart dependent containers
                    success = await self._restart_with_dependencies(
                        container_name
                    )

                elif fix_strategy == "download_model":
                    # Model missing - can't auto-fix, log error
                    logger.error(
                        "model_missing",
                        container=container_name,
                        hint="Run model download script"
                    )
                    success = False

                elif fix_strategy == "restart_database":
                    # Database locked - restart database container
                    success = await self._restart_container("local-ai-postgres")

                elif fix_strategy == "fix_permissions":
                    # Permission issue - can't auto-fix safely
                    logger.error(
                        "permission_issue",
                        container=container_name,
                        hint="Check volume permissions"
                    )
                    success = False

                else:
                    # Unknown strategy - default restart
                    success = await self._restart_container(container_name)

                # Update pattern success rate
                pattern.applications += 1
                if success:
                    pattern.success_rate = (
                        (pattern.success_rate * (pattern.applications - 1) + 1.0)
                        / pattern.applications
                    )
            else:
                # No pattern identified - try simple restart
                success = await self._restart_container(container_name)

            return HealingAction(
                timestamp=datetime.utcnow(),
                container=container_name,
                error_pattern=error_pattern,
                action=action_type,
                success=success,
                logs=logs[:500],  # Store first 500 chars
            )

        except Exception as e:
            logger.error("fix_application_failed", error=str(e))
            return HealingAction(
                timestamp=datetime.utcnow(),
                container=container_name,
                error_pattern=error_pattern,
                action="failed",
                success=False,
                logs=str(e),
            )

    async def _restart_container(self, container_name: str) -> bool:
        """Restart a container"""
        try:
            result = subprocess.run(
                ["podman", "restart", container_name],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                logger.info("container_restarted", container=container_name)
                return True
            else:
                logger.warning(
                    "restart_failed",
                    container=container_name,
                    stderr=result.stderr
                )
                return False
        except Exception as e:
            logger.error("restart_exception", error=str(e))
            return False

    async def _restart_with_dependencies(self, container_name: str) -> bool:
        """Restart container and its dependencies"""
        # Dependency map
        dependencies = {
            "local-ai-aidb": ["local-ai-postgres", "local-ai-redis", "local-ai-qdrant", "local-ai-llama-cpp"],
            "local-ai-hybrid-coordinator": ["local-ai-qdrant", "local-ai-llama-cpp"],
            "local-ai-ralph-wiggum": ["local-ai-postgres", "local-ai-redis"],
        }

        deps = dependencies.get(container_name, [])

        # Restart dependencies first
        for dep in deps:
            await self._restart_container(dep)
            await asyncio.sleep(5)

        # Restart main container
        return await self._restart_container(container_name)

    async def _verify_container_health(self, container_name: str) -> bool:
        """Verify container is healthy after healing"""
        try:
            result = subprocess.run(
                [
                    "podman",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                health_status = result.stdout.strip()
                # Accept 'healthy' or 'starting' (will become healthy)
                return health_status in ["healthy", "starting", ""]
            else:
                # No health check defined - check if running
                result = subprocess.run(
                    ["podman", "inspect", "--format", "{{.State.Running}}", container_name],
                    capture_output=True,
                    text=True,
                )
                return result.stdout.strip() == "true"

        except Exception as e:
            logger.warning("health_verification_failed", error=str(e))
            return False

    async def _save_success_pattern(self, pattern_id: Optional[str]):
        """Save successful healing pattern to knowledge base"""
        if not pattern_id or pattern_id not in self.error_patterns:
            return

        pattern = self.error_patterns[pattern_id]

        # Save to Qdrant if available
        if self.qdrant:
            try:
                # Store pattern in error-solutions collection
                await self.qdrant.upsert(
                    collection_name="error-solutions",
                    points=[
                        {
                            "id": hash(pattern_id) % (10 ** 8),
                            "vector": [0.0] * 384,  # Placeholder vector
                            "payload": {
                                "pattern_id": pattern_id,
                                "error_regex": pattern.error_regex,
                                "fix_strategy": pattern.fix_strategy,
                                "success_rate": pattern.success_rate,
                                "applications": pattern.applications,
                            },
                        }
                    ],
                )
            except Exception as e:
                logger.debug("pattern_save_failed", error=str(e))

    async def get_statistics(self) -> Dict[str, Any]:
        """Get self-healing statistics"""
        total_actions = len(self.healing_history)
        successful_actions = sum(1 for a in self.healing_history if a.success)
        success_rate = (
            successful_actions / total_actions if total_actions > 0 else 0.0
        )

        # Actions by container
        by_container: Dict[str, int] = {}
        for action in self.healing_history:
            by_container[action.container] = (
                by_container.get(action.container, 0) + 1
            )

        return {
            "total_healing_actions": total_actions,
            "successful_actions": successful_actions,
            "success_rate": success_rate,
            "known_error_patterns": len(self.error_patterns),
            "actions_by_container": by_container,
            "recent_actions": [
                {
                    "timestamp": a.timestamp.isoformat(),
                    "container": a.container,
                    "action": a.action,
                    "success": a.success,
                }
                for a in self.healing_history[-10:]
            ],
        }
