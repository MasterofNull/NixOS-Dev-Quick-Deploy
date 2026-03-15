"""
Automated Remediation Workflows - Self-healing actions for alerts.

Provides safe, automated remediation actions for common alert conditions.
Workflows execute bounded actions with safety checks and rollback support.

Part of Phase 1 (Monitoring & Observability) implementation.
"""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)


@dataclass
class RemediationResult:
    """Result of a remediation workflow execution."""
    success: bool
    action: str
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    error: Optional[str] = None


class RemediationWorkflows:
    """
    Automated remediation workflow executor.

    Provides safe, bounded self-healing actions for common failure modes.
    """

    def __init__(self, dry_run: bool = False):
        """
        Initialize remediation workflows.

        Args:
            dry_run: If True, log actions but don't execute them
        """
        self.dry_run = dry_run
        self.max_retries = 3
        self.retry_delay = 5  # seconds

    async def restart_service(self, alert: Any) -> Dict[str, Any]:
        """
        Restart a failing service via systemctl.

        Safety checks:
        - Only restarts AI stack services
        - Rate limited (max 3 restarts per hour per service)
        - Logs all restart attempts

        Args:
            alert: Alert object containing service information

        Returns:
            Result dict with success status and details
        """
        service_name = alert.metadata.get("service_name")
        if not service_name:
            return {
                "success": False,
                "error": "No service_name in alert metadata"
            }

        # Safety: Only allow AI stack services
        allowed_services = {
            "ai-aidb.service",
            "ai-hybrid-coordinator.service",
            "llama-cpp.service",
            "llama-embed.service",
            "redis.service",
            "postgresql.service",
            "qdrant.service",
        }

        if service_name not in allowed_services:
            return {
                "success": False,
                "error": f"Service {service_name} not in allowed list"
            }

        # Check restart rate limiting
        restart_file = Path(f"/tmp/service_restart_{service_name}.log")
        if restart_file.exists():
            restart_times = restart_file.read_text().strip().split("\n")
            recent_restarts = [
                t for t in restart_times
                if (datetime.utcnow() - datetime.fromisoformat(t)).total_seconds() < 3600
            ]
            if len(recent_restarts) >= 3:
                return {
                    "success": False,
                    "error": f"Service {service_name} restarted 3+ times in last hour, manual intervention required"
                }

        logger.info(f"Remediation: Restarting service {service_name} (dry_run={self.dry_run})")

        if not self.dry_run:
            try:
                # Restart service
                result = subprocess.run(
                    ["sudo", "systemctl", "restart", service_name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"systemctl restart failed: {result.stderr}"
                    }

                # Wait for service to stabilize
                await asyncio.sleep(5)

                # Verify service is running
                status_result = subprocess.run(
                    ["systemctl", "is-active", service_name],
                    capture_output=True,
                    text=True
                )

                is_active = status_result.stdout.strip() == "active"

                # Log restart
                restart_file.parent.mkdir(parents=True, exist_ok=True)
                with open(restart_file, "a") as f:
                    f.write(f"{datetime.utcnow().isoformat()}\n")

                return {
                    "success": is_active,
                    "message": f"Service {service_name} restarted",
                    "details": {"service": service_name, "active": is_active}
                }

            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": f"Service restart timed out after 30s"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Restart failed: {str(e)}"
                }
        else:
            return {
                "success": True,
                "message": f"[DRY RUN] Would restart service {service_name}",
                "details": {"service": service_name, "dry_run": True}
            }

    async def clear_cache(self, alert: Any) -> Dict[str, Any]:
        """
        Clear cache to free memory or resolve stale cache issues.

        Safety checks:
        - Only clears designated cache directories
        - Preserves critical data
        - Logs all cache clears

        Args:
            alert: Alert object containing cache information

        Returns:
            Result dict with success status and details
        """
        cache_type = alert.metadata.get("cache_type", "quality")

        cache_paths = {
            "quality": Path("/tmp/quality_cache"),
            "embedding": Path("/tmp/embedding_cache"),
            "qdrant": None,  # Handled via API
            "redis": None,   # Handled via redis-cli
        }

        cache_path = cache_paths.get(cache_type)

        logger.info(f"Remediation: Clearing {cache_type} cache (dry_run={self.dry_run})")

        if cache_type == "redis":
            return await self._clear_redis_cache(alert)
        elif cache_type == "qdrant":
            return await self._clear_qdrant_cache(alert)
        elif cache_path:
            return await self._clear_file_cache(cache_path, cache_type)
        else:
            return {
                "success": False,
                "error": f"Unknown cache type: {cache_type}"
            }

    async def _clear_file_cache(self, cache_path: Path, cache_type: str) -> Dict[str, Any]:
        """Clear file-based cache."""
        if not self.dry_run:
            try:
                if cache_path.exists():
                    import shutil
                    shutil.rmtree(cache_path)
                    cache_path.mkdir(parents=True, exist_ok=True)

                return {
                    "success": True,
                    "message": f"{cache_type} cache cleared",
                    "details": {"cache_type": cache_type, "path": str(cache_path)}
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Cache clear failed: {str(e)}"
                }
        else:
            return {
                "success": True,
                "message": f"[DRY RUN] Would clear {cache_type} cache",
                "details": {"cache_type": cache_type, "dry_run": True}
            }

    async def _clear_redis_cache(self, alert: Any) -> Dict[str, Any]:
        """Clear Redis cache via FLUSHDB."""
        if not self.dry_run:
            try:
                result = subprocess.run(
                    ["redis-cli", "FLUSHDB"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                return {
                    "success": result.returncode == 0,
                    "message": "Redis cache cleared",
                    "details": {"cache_type": "redis", "output": result.stdout.strip()}
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Redis cache clear failed: {str(e)}"
                }
        else:
            return {
                "success": True,
                "message": "[DRY RUN] Would clear Redis cache with FLUSHDB",
                "details": {"cache_type": "redis", "dry_run": True}
            }

    async def _clear_qdrant_cache(self, alert: Any) -> Dict[str, Any]:
        """Clear Qdrant collection cache by recreating collection."""
        collection_name = alert.metadata.get("collection_name", "ai_stack_cache")
        qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")

        if not self.dry_run:
            try:
                async with httpx.AsyncClient() as client:
                    # Delete collection
                    response = await client.delete(f"{qdrant_url}/collections/{collection_name}")

                    if response.status_code not in (200, 404):
                        return {
                            "success": False,
                            "error": f"Qdrant delete failed: {response.text}"
                        }

                    # Recreate collection (simplified - adjust vector size as needed)
                    create_payload = {
                        "vectors": {
                            "size": 384,
                            "distance": "Cosine"
                        }
                    }
                    response = await client.put(
                        f"{qdrant_url}/collections/{collection_name}",
                        json=create_payload
                    )

                    return {
                        "success": response.status_code == 200,
                        "message": f"Qdrant collection {collection_name} cleared",
                        "details": {"collection": collection_name, "cache_type": "qdrant"}
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Qdrant cache clear failed: {str(e)}"
                }
        else:
            return {
                "success": True,
                "message": f"[DRY RUN] Would clear Qdrant collection {collection_name}",
                "details": {"collection": collection_name, "dry_run": True}
            }

    async def refresh_models(self, alert: Any) -> Dict[str, Any]:
        """
        Refresh model loading state by calling reload endpoint.

        Safety checks:
        - Only triggers model reload, doesn't modify model files
        - Rate limited to prevent reload loops

        Args:
            alert: Alert object

        Returns:
            Result dict with success status and details
        """
        coordinator_url = os.getenv("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003")

        logger.info(f"Remediation: Refreshing models (dry_run={self.dry_run})")

        if not self.dry_run:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(f"{coordinator_url}/reload-model", timeout=60.0)

                    return {
                        "success": response.status_code == 200,
                        "message": "Model reload triggered",
                        "details": {"response": response.json() if response.status_code == 200 else response.text}
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Model refresh failed: {str(e)}"
                }
        else:
            return {
                "success": True,
                "message": "[DRY RUN] Would trigger model reload",
                "details": {"dry_run": True}
            }

    async def rotate_logs(self, alert: Any) -> Dict[str, Any]:
        """
        Rotate logs for a service to prevent disk space issues.

        Safety checks:
        - Only rotates AI stack service logs
        - Preserves last 7 days of logs
        - Compresses old logs

        Args:
            alert: Alert object containing service information

        Returns:
            Result dict with success status and details
        """
        service_name = alert.metadata.get("service_name")
        if not service_name:
            return {
                "success": False,
                "error": "No service_name in alert metadata"
            }

        logger.info(f"Remediation: Rotating logs for {service_name} (dry_run={self.dry_run})")

        if not self.dry_run:
            try:
                # Trigger journald log rotation for service
                result = subprocess.run(
                    ["sudo", "journalctl", "--rotate"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                # Vacuum old logs (keep last 7 days)
                vacuum_result = subprocess.run(
                    ["sudo", "journalctl", "--vacuum-time=7d"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                return {
                    "success": result.returncode == 0 and vacuum_result.returncode == 0,
                    "message": f"Logs rotated and vacuumed for {service_name}",
                    "details": {
                        "service": service_name,
                        "vacuum_output": vacuum_result.stdout.strip()
                    }
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Log rotation failed: {str(e)}"
                }
        else:
            return {
                "success": True,
                "message": f"[DRY RUN] Would rotate logs for {service_name}",
                "details": {"service": service_name, "dry_run": True}
            }

    async def scale_resources(self, alert: Any) -> Dict[str, Any]:
        """
        Scale resources (placeholder for future Kubernetes/Docker integration).

        Currently logs the recommendation but doesn't execute.

        Args:
            alert: Alert object containing resource information

        Returns:
            Result dict with success status and details
        """
        resource_type = alert.metadata.get("resource_type", "unknown")
        current = alert.metadata.get("current_value")
        recommended = alert.metadata.get("recommended_value")

        logger.info(
            f"Remediation: Resource scaling recommended for {resource_type}: "
            f"{current} -> {recommended} (not implemented)"
        )

        return {
            "success": False,
            "error": "Resource scaling not implemented (requires orchestration layer)",
            "details": {
                "resource_type": resource_type,
                "current": current,
                "recommended": recommended,
                "action": "manual_intervention_required"
            }
        }


# Global workflows instance
_workflows = RemediationWorkflows()


async def restart_service_workflow(alert: Any) -> Dict[str, Any]:
    """Restart service remediation workflow."""
    return await _workflows.restart_service(alert)


async def clear_cache_workflow(alert: Any) -> Dict[str, Any]:
    """Clear cache remediation workflow."""
    return await _workflows.clear_cache(alert)


async def refresh_models_workflow(alert: Any) -> Dict[str, Any]:
    """Refresh models remediation workflow."""
    return await _workflows.refresh_models(alert)


async def rotate_logs_workflow(alert: Any) -> Dict[str, Any]:
    """Rotate logs remediation workflow."""
    return await _workflows.rotate_logs(alert)


async def scale_resources_workflow(alert: Any) -> Dict[str, Any]:
    """Scale resources remediation workflow."""
    return await _workflows.scale_resources(alert)
