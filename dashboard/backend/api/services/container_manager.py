"""Container management using Podman"""
import subprocess
import json
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ContainerManager:
    """Manages Podman containers"""
    
    async def list_containers(self) -> List[Dict[str, Any]]:
        """List all containers"""
        try:
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