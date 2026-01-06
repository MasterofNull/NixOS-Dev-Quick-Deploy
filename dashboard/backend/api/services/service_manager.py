"""Service management"""
import subprocess
import asyncio
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages systemd and container services"""
    
    MONITORED_SERVICES = [
        # Core AI Stack Services
        "llama-cpp",
        "qdrant",
        "redis",
        "postgres",

        # MCP Servers
        "aidb",
        "hybrid-coordinator",
        "nixos-docs",
        "ralph-wiggum",
        "health-monitor",

        # UI & Additional Services
        "dashboard-api",
        "open-webui",
        "mindsdb",
    ]
    
    async def list_services(self) -> List[Dict[str, Any]]:
        """List all monitored services"""
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
