"""Service management"""
import asyncio
import json
import os
import subprocess
from typing import List, Dict, Any, Optional
import logging
import ssl
from datetime import datetime
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages systemd and container services"""

    def __init__(self):
        self.namespace = os.getenv("AI_STACK_NAMESPACE", "ai-stack")
        self.mode = self._detect_mode()
        self.k8s_host = os.getenv("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
        self.k8s_port = os.getenv("KUBERNETES_SERVICE_PORT_HTTPS", "443")
        self.k8s_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        self.k8s_ca_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")

    def _detect_mode(self) -> str:
        """Detect runtime mode (podman vs k8s)."""
        explicit = os.getenv("DASHBOARD_MODE", "").lower()
        if explicit in ("k8s", "kubernetes"):
            return "k8s"
        return "podman"
    
    MONITORED_SERVICES = [
        # Core AI Stack Services
        "llama-cpp",
        "qdrant",
        "redis",
        "postgres",
        "embeddings",
        "nginx",

        # MCP Servers
        "aidb",
        "hybrid-coordinator",
        "nixos-docs",
        "ralph-wiggum",
        "health-monitor",
        "container-engine",
        "aider-wrapper",

        # UI & Additional Services
        "dashboard-api",
        "open-webui",
        "mindsdb",
        "grafana",
        "prometheus",
        "jaeger",
        "aider",
        "autogpt",
    ]
    
    async def list_services(self) -> List[Dict[str, Any]]:
        """List all monitored services"""
        if self.mode == "k8s":
            return await self._list_k8s_services()

        services = []
        for service_name in self.MONITORED_SERVICES:
            status = await self._get_service_status(service_name)
            services.append({
                "id": service_name,
                "name": service_name.replace("-", " ").title(),
                "status": status["status"],
                "type": status["type"],
            })
        return services
    
    async def start_service(self, service_id: str) -> Dict[str, Any]:
        """Start a service"""
        try:
            if self.mode == "k8s":
                result = await self._k8s_scale_deployment(service_id, 1)
                return {
                    "service": service_id,
                    "action": "start",
                    "success": result["success"],
                    "message": result["message"]
                }

            # Check if it's a systemd service or container
            status = await self._get_service_status(service_id)
            
            if status["type"] == "systemd":
                cmd = f"systemctl --user start {service_id}.service"
            else:
                cmd = f"podman start local-ai-{service_id}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            
            return {
                "service": service_id,
                "action": "start",
                "success": result.returncode == 0,
                "message": result.stdout or result.stderr
            }
        except Exception as e:
            logger.error(f"Error starting service: {e}")
            return {
                "service": service_id,
                "action": "start",
                "success": False,
                "message": str(e)
            }
    
    async def stop_service(self, service_id: str) -> Dict[str, Any]:
        """Stop a service"""
        try:
            if self.mode == "k8s":
                result = await self._k8s_scale_deployment(service_id, 0)
                return {
                    "service": service_id,
                    "action": "stop",
                    "success": result["success"],
                    "message": result["message"]
                }

            status = await self._get_service_status(service_id)
            
            if status["type"] == "systemd":
                cmd = f"systemctl --user stop {service_id}.service"
            else:
                cmd = f"podman stop local-ai-{service_id}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            
            return {
                "service": service_id,
                "action": "stop",
                "success": result.returncode == 0,
                "message": result.stdout or result.stderr
            }
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            return {
                "service": service_id,
                "action": "stop",
                "success": False,
                "message": str(e)
            }
    
    async def restart_service(self, service_id: str) -> Dict[str, Any]:
        """Restart a service"""
        if self.mode == "k8s":
            try:
                result = await self._k8s_rollout_restart(service_id)
                return {
                    "service": service_id,
                    "action": "restart",
                    "success": result["success"],
                    "message": result["message"]
                }
            except Exception as e:
                return {
                    "service": service_id,
                    "action": "restart",
                    "success": False,
                    "message": str(e)
                }
        await self.stop_service(service_id)
        await asyncio.sleep(1)
        return await self.start_service(service_id)

    async def start_all_services(self) -> Dict[str, Any]:
        """Start all monitored services"""
        results = []
        for service_id in self.MONITORED_SERVICES:
            results.append(await self.start_service(service_id))
        return {"action": "start_all", "results": results}

    async def stop_all_services(self) -> Dict[str, Any]:
        """Stop all monitored services"""
        results = []
        for service_id in self.MONITORED_SERVICES:
            results.append(await self.stop_service(service_id))
        return {"action": "stop_all", "results": results}

    async def restart_all_services(self) -> Dict[str, Any]:
        """Restart all monitored services"""
        results = []
        for service_id in self.MONITORED_SERVICES:
            results.append(await self.restart_service(service_id))
        return {"action": "restart_all", "results": results}
    
    async def _get_service_status(self, service_name: str) -> Dict[str, str]:
        """Get service status"""
        if self.mode == "k8s":
            return await self._get_k8s_status(service_name)

        # Check systemd first
        result = subprocess.run(
            f"systemctl --user is-active {service_name}.service",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return {"status": "running", "type": "systemd"}

        unit_check = subprocess.run(
            f"systemctl --user list-unit-files --type=service --no-legend {service_name}.service",
            shell=True,
            capture_output=True,
            text=True
        )

        if unit_check.returncode == 0 and unit_check.stdout.strip():
            return {"status": "stopped", "type": "systemd"}
        
        # Check container
        result = subprocess.run(
            f"podman ps --format '{{{{.Names}}}}' | grep -q '^local-ai-{service_name}$'",
            shell=True,
            capture_output=True
        )
        
        if result.returncode == 0:
            return {"status": "running", "type": "container"}

        return {"status": "stopped", "type": "container"}

    async def _list_k8s_services(self) -> List[Dict[str, Any]]:
        """List monitored services via Kubernetes deployments."""
        try:
            payload = await self._k8s_get_json(f"/apis/apps/v1/namespaces/{self.namespace}/deployments")
            if not payload:
                return []
            deployments = {item["metadata"]["name"]: item for item in payload.get("items", [])}

            services = []
            for service_name in self.MONITORED_SERVICES:
                item = deployments.get(service_name)
                if not item:
                    services.append({
                        "id": service_name,
                        "name": service_name.replace("-", " ").title(),
                        "status": "unknown",
                        "type": "k8s",
                    })
                    continue

                desired = item.get("spec", {}).get("replicas", 0) or 0
                available = item.get("status", {}).get("availableReplicas", 0) or 0
                status = "running" if desired > 0 and available > 0 else "stopped"

                services.append({
                    "id": service_name,
                    "name": service_name.replace("-", " ").title(),
                    "status": status,
                    "type": "k8s",
                })

            return services
        except Exception as e:
            logger.error(f"k8s_list_failed: {e}")
            return []

    async def _get_k8s_status(self, service_name: str) -> Dict[str, str]:
        """Get status for a Kubernetes deployment."""
        try:
            payload = await self._k8s_get_json(f"/apis/apps/v1/namespaces/{self.namespace}/deployments/{service_name}")
            if not payload:
                return {"status": "unknown", "type": "k8s"}
            desired = payload.get("spec", {}).get("replicas", 0) or 0
            available = payload.get("status", {}).get("availableReplicas", 0) or 0
            status = "running" if desired > 0 and available > 0 else "stopped"
            return {"status": status, "type": "k8s"}
        except Exception as e:
            logger.error(f"k8s_status_failed: {e}")
            return {"status": "unknown", "type": "k8s"}

    async def _k8s_get_json(self, path: str) -> Optional[Dict[str, Any]]:
        """Fetch Kubernetes API JSON using the in-cluster service account."""
        token = self._read_k8s_token()
        if not token:
            logger.error("k8s_token_missing")
            return None

        url = f"https://{self.k8s_host}:{self.k8s_port}{path}"
        ssl_ctx = ssl.create_default_context(cafile=str(self.k8s_ca_path))
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=ssl_ctx, timeout=5) as resp:
                if resp.status != 200:
                    logger.error(f"k8s_api_error: {resp.status} {path}")
                    return None
                return await resp.json()

    async def _k8s_patch(self, path: str, payload: Dict[str, Any], content_type: str) -> Dict[str, Any]:
        token = self._read_k8s_token()
        if not token:
            return {"success": False, "message": "Missing service account token"}

        url = f"https://{self.k8s_host}:{self.k8s_port}{path}"
        ssl_ctx = ssl.create_default_context(cafile=str(self.k8s_ca_path))
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        }

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, ssl=ssl_ctx, json=payload, timeout=5) as resp:
                text = await resp.text()
                return {
                    "success": resp.status in (200, 201),
                    "message": text,
                }

    async def _k8s_scale_deployment(self, name: str, replicas: int) -> Dict[str, Any]:
        payload = {"spec": {"replicas": replicas}}
        return await self._k8s_patch(
            f"/apis/apps/v1/namespaces/{self.namespace}/deployments/{name}",
            payload,
            "application/merge-patch+json",
        )

    async def _k8s_rollout_restart(self, name: str) -> Dict[str, Any]:
        payload = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat()
                        }
                    }
                }
            }
        }
        return await self._k8s_patch(
            f"/apis/apps/v1/namespaces/{self.namespace}/deployments/{name}",
            payload,
            "application/merge-patch+json",
        )

    def _read_k8s_token(self) -> Optional[str]:
        try:
            return self.k8s_token_path.read_text().strip()
        except Exception as e:
            logger.error(f"k8s_token_read_failed: {e}")
            return None
