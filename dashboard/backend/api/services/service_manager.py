"""Service management."""
import asyncio
import logging
import subprocess
from typing import Any, Dict, List

from api.services.systemd_units import get_monitored_units

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manage AI stack services via systemd."""

    async def list_services(self) -> List[Dict[str, Any]]:
        monitored_services = get_monitored_units(include_dashboard=True)
        services: List[Dict[str, Any]] = []
        for service_id in monitored_services:
            status = await self._get_service_status(service_id)
            services.append(
                {
                    "id": service_id,
                    "name": service_id.replace("-", " ").title(),
                    "status": status["status"],
                    "type": "systemd",
                }
            )
        return services

    async def start_service(self, service_id: str) -> Dict[str, Any]:
        return await self._run_unit_action(service_id, "start")

    async def stop_service(self, service_id: str) -> Dict[str, Any]:
        return await self._run_unit_action(service_id, "stop")

    async def restart_service(self, service_id: str) -> Dict[str, Any]:
        return await self._run_unit_action(service_id, "restart")

    async def start_all_services(self) -> Dict[str, Any]:
        return await self._run_batch("start")

    async def stop_all_services(self) -> Dict[str, Any]:
        return await self._run_batch("stop")

    async def restart_all_services(self) -> Dict[str, Any]:
        return await self._run_batch("restart")

    async def _run_batch(self, action: str) -> Dict[str, Any]:
        monitored_services = get_monitored_units(include_dashboard=True)
        results: List[Dict[str, Any]] = []
        for service_id in monitored_services:
            results.append(await self._run_unit_action(service_id, action))
            await asyncio.sleep(0.05)
        return {"action": f"{action}_all", "results": results}

    async def _run_unit_action(self, service_id: str, action: str) -> Dict[str, Any]:
        unit = self._to_unit(service_id)
        try:
            result = subprocess.run(
                ["systemctl", action, unit],
                capture_output=True,
                text=True,
                check=False,
            )
            return {
                "service": service_id,
                "action": action,
                "success": result.returncode == 0,
                "message": (result.stdout or result.stderr).strip(),
            }
        except Exception as exc:
            logger.error("service_action_failed service=%s action=%s error=%s", service_id, action, exc)
            return {
                "service": service_id,
                "action": action,
                "success": False,
                "message": str(exc),
            }

    async def _get_service_status(self, service_id: str) -> Dict[str, str]:
        unit = self._to_unit(service_id)
        active = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        if active.returncode == 0:
            return {"status": "running"}

        exists = subprocess.run(
            ["systemctl", "status", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        if exists.returncode == 4:
            return {"status": "missing"}
        return {"status": "stopped"}

    @staticmethod
    def _to_unit(service_id: str) -> str:
        return service_id if service_id.endswith(".service") else f"{service_id}.service"
