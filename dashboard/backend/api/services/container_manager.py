"""Container management using Podman or Kubernetes"""
import json
import os
import subprocess
from typing import List, Dict, Any, Optional
import logging
import ssl
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)


class ContainerManager:
    """Manages Podman containers"""

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

    async def list_containers(self) -> List[Dict[str, Any]]:
        """List all containers"""
        try:
            if self.mode == "k8s":
                return await self._list_k8s_pods()

            result = subprocess.run(
                ["podman", "ps", "-a", "--format", "json"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return []
            
            containers = json.loads(result.stdout)
            
            return [
                {
                    "id": c.get("Id", "")[:12],
                    "name": c.get("Names", [""])[0] if isinstance(c.get("Names"), list) else c.get("Names", ""),
                    "image": c.get("Image", ""),
                    "status": c.get("State", ""),
                    "created": c.get("Created", ""),
                }
                for c in containers
            ]
        except Exception as e:
            logger.error(f"Error listing containers: {e}")
            return []
    
    async def start_container(self, container_id: str) -> Dict[str, Any]:
        """Start a container"""
        try:
            if self.mode == "k8s":
                return {
                    "container": container_id,
                    "action": "start",
                    "success": False,
                    "message": "Kubernetes pods are managed by deployments; use service controls."
                }

            result = subprocess.run(
                ["podman", "start", container_id],
                capture_output=True,
                text=True
            )
            
            return {
                "container": container_id,
                "action": "start",
                "success": result.returncode == 0,
                "message": result.stdout or result.stderr
            }
        except Exception as e:
            return {
                "container": container_id,
                "action": "start",
                "success": False,
                "message": str(e)
            }
    
    async def stop_container(self, container_id: str) -> Dict[str, Any]:
        """Stop a container"""
        try:
            if self.mode == "k8s":
                result = await self._k8s_delete_pod(container_id)
                return {
                    "container": container_id,
                    "action": "stop",
                    "success": result["success"],
                    "message": result["message"]
                }

            result = subprocess.run(
                ["podman", "stop", container_id],
                capture_output=True,
                text=True
            )
            
            return {
                "container": container_id,
                "action": "stop",
                "success": result.returncode == 0,
                "message": result.stdout or result.stderr
            }
        except Exception as e:
            return {
                "container": container_id,
                "action": "stop",
                "success": False,
                "message": str(e)
            }
    
    async def restart_container(self, container_id: str) -> Dict[str, Any]:
        """Restart a container"""
        try:
            if self.mode == "k8s":
                result = await self._k8s_delete_pod(container_id)
                return {
                    "container": container_id,
                    "action": "restart",
                    "success": result["success"],
                    "message": result["message"]
                }

            result = subprocess.run(
                ["podman", "restart", container_id],
                capture_output=True,
                text=True
            )
            
            return {
                "container": container_id,
                "action": "restart",
                "success": result.returncode == 0,
                "message": result.stdout or result.stderr
            }
        except Exception as e:
            return {
                "container": container_id,
                "action": "restart",
                "success": False,
                "message": str(e)
            }
    
    async def get_logs(self, container_id: str, tail: int = 100) -> str:
        """Get container logs"""
        try:
            if self.mode == "k8s":
                return await self._k8s_get_pod_logs(container_id, tail)

            result = subprocess.run(
                ["podman", "logs", "--tail", str(tail), container_id],
                capture_output=True,
                text=True
            )

            return result.stdout
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return f"Error: {str(e)}"

    async def _get_ai_stack_containers(self) -> List[str]:
        """Get list of AI stack container names"""
        if self.mode == "k8s":
            return []

        ai_containers = [
            "local-ai-qdrant",
            "local-ai-postgres",
            "local-ai-redis",
            "local-ai-llama-cpp",
            "local-ai-open-webui",
            "local-ai-mindsdb",
            "local-ai-aidb",
            "local-ai-hybrid-coordinator",
            "local-ai-nixos-docs",
            "local-ai-health-monitor"
        ]

        # Check which containers actually exist
        existing = []
        try:
            result = subprocess.run(
                ["podman", "ps", "-a", "--format", "{{.Names}}"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                all_containers = result.stdout.strip().split('\n')
                existing = [c for c in ai_containers if c in all_containers]
        except Exception as e:
            logger.error(f"Error getting AI stack containers: {e}")

        return existing

    async def _list_k8s_pods(self) -> List[Dict[str, Any]]:
        """List pods as containers for Kubernetes mode."""
        try:
            payload = await self._k8s_get_json(f"/api/v1/namespaces/{self.namespace}/pods")
            if not payload:
                return []
            pods = payload.get("items", [])
            entries = []
            for pod in pods:
                name = pod.get("metadata", {}).get("name", "")
                phase = pod.get("status", {}).get("phase", "unknown").lower()
                containers = pod.get("spec", {}).get("containers", [])
                image = containers[0].get("image", "") if containers else ""
                entries.append({
                    "id": name,
                    "name": name,
                    "image": image,
                    "status": phase,
                    "created": pod.get("metadata", {}).get("creationTimestamp", ""),
                })
            return entries
        except Exception as e:
            logger.error(f"Error listing pods: {e}")
            return []

    async def _k8s_get_json(self, path: str) -> Optional[Dict[str, Any]]:
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

    async def _k8s_delete_pod(self, name: str) -> Dict[str, Any]:
        token = self._read_k8s_token()
        if not token:
            return {"success": False, "message": "Missing service account token"}

        url = f"https://{self.k8s_host}:{self.k8s_port}/api/v1/namespaces/{self.namespace}/pods/{name}"
        ssl_ctx = ssl.create_default_context(cafile=str(self.k8s_ca_path))
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers, ssl=ssl_ctx, timeout=5) as resp:
                text = await resp.text()
                return {"success": resp.status in (200, 202), "message": text}

    async def _k8s_get_pod_logs(self, name: str, tail: int) -> str:
        token = self._read_k8s_token()
        if not token:
            return "Missing service account token"

        url = (
            f"https://{self.k8s_host}:{self.k8s_port}/api/v1/namespaces/{self.namespace}/pods/{name}/log"
            f"?tailLines={tail}"
        )
        ssl_ctx = ssl.create_default_context(cafile=str(self.k8s_ca_path))
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=ssl_ctx, timeout=5) as resp:
                if resp.status != 200:
                    return f"Error fetching logs: {resp.status}"
                return await resp.text()

    def _read_k8s_token(self) -> Optional[str]:
        try:
            return self.k8s_token_path.read_text().strip()
        except Exception as e:
            logger.error(f"k8s_token_read_failed: {e}")
            return None

    async def start_ai_stack(self) -> Dict[str, Any]:
        """Start all AI stack containers using podman-compose"""
        try:
            import os
            project_root = os.path.expanduser("~/Documents/try/NixOS-Dev-Quick-Deploy")
            compose_dir = f"{project_root}/ai-stack/compose"

            # Use podman-compose up to start all containers
            result = subprocess.run(
                ["podman-compose", "up", "-d"],
                capture_output=True,
                text=True,
                cwd=compose_dir,
                timeout=300
            )

            return {
                "action": "start_ai_stack",
                "success": result.returncode == 0,
                "message": "AI stack started successfully" if result.returncode == 0 else "Failed to start AI stack",
                "output": result.stdout[-1000:] if result.stdout else result.stderr[-1000:] if result.stderr else ""
            }
        except subprocess.TimeoutExpired:
            return {
                "action": "start_ai_stack",
                "success": False,
                "message": "Command timed out after 5 minutes",
                "output": ""
            }
        except Exception as e:
            logger.error(f"Error starting AI stack: {e}")
            return {
                "action": "start_ai_stack",
                "success": False,
                "message": str(e),
                "output": ""
            }

    async def stop_ai_stack(self) -> Dict[str, Any]:
        """Stop all AI stack containers"""
        try:
            containers = await self._get_ai_stack_containers()

            if not containers:
                return {
                    "action": "stop_ai_stack",
                    "success": True,
                    "message": "No AI stack containers found",
                    "stopped": []
                }

            # Stop all containers
            result = subprocess.run(
                ["podman", "stop"] + containers,
                capture_output=True,
                text=True,
                timeout=60
            )

            return {
                "action": "stop_ai_stack",
                "success": result.returncode == 0,
                "message": f"Stopped {len(containers)} containers" if result.returncode == 0 else "Failed to stop some containers",
                "stopped": containers,
                "output": result.stdout if result.stdout else result.stderr if result.stderr else ""
            }
        except Exception as e:
            logger.error(f"Error stopping AI stack: {e}")
            return {
                "action": "stop_ai_stack",
                "success": False,
                "message": str(e),
                "stopped": []
            }

    async def restart_ai_stack(self) -> Dict[str, Any]:
        """Restart all AI stack containers"""
        try:
            import os
            project_root = os.path.expanduser("~/Documents/try/NixOS-Dev-Quick-Deploy")
            compose_dir = f"{project_root}/ai-stack/compose"

            # Use podman-compose restart
            result = subprocess.run(
                ["podman-compose", "restart"],
                capture_output=True,
                text=True,
                cwd=compose_dir,
                timeout=300
            )

            return {
                "action": "restart_ai_stack",
                "success": result.returncode == 0,
                "message": "AI stack restarted successfully" if result.returncode == 0 else "Failed to restart AI stack",
                "output": result.stdout[-1000:] if result.stdout else result.stderr[-1000:] if result.stderr else ""
            }
        except subprocess.TimeoutExpired:
            return {
                "action": "restart_ai_stack",
                "success": False,
                "message": "Command timed out after 5 minutes",
                "output": ""
            }
        except Exception as e:
            logger.error(f"Error restarting AI stack: {e}")
            return {
                "action": "restart_ai_stack",
                "success": False,
                "message": str(e),
                "output": ""
            }
