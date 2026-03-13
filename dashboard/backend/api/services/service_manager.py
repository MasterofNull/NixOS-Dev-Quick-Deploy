"""Service management."""
import logging
import shutil
import subprocess
from typing import Any, Dict, List

from api.services.systemd_units import get_monitored_units

logger = logging.getLogger(__name__)

SYSTEMCTL_BIN = (
    "/run/current-system/sw/bin/systemctl"
    if shutil.which("/run/current-system/sw/bin/systemctl")
    else (shutil.which("systemctl") or "/run/current-system/sw/bin/systemctl")
)
SUDO_BIN = shutil.which("sudo") or "/run/wrappers/bin/sudo"


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
        monitored_services = get_monitored_units(include_dashboard=False)
        units = [self._to_unit(service_id) for service_id in monitored_services]
        command = self._systemctl_batch_command(action, units)
        if self._sudo_ready():
            command = [SUDO_BIN, "-n", *command]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        success = result.returncode == 0
        message = (result.stdout or result.stderr).strip()
        if success and not message:
            message = f"{action} submitted for {len(units)} services"
        results: List[Dict[str, Any]] = [
            {
                "service": service_id,
                "action": action,
                "success": success,
                "unit": self._to_unit(service_id),
                "message": message,
                "returncode": result.returncode,
            }
            for service_id in monitored_services
        ]
        return {
            "action": f"{action}_all",
            "success": success,
            "succeeded": len(results) if success else 0,
            "failed": 0 if success else len(results),
            "message": message,
            "results": results,
        }

    async def _run_unit_action(self, service_id: str, action: str) -> Dict[str, Any]:
        unit = self._to_unit(service_id)
        try:
            result = subprocess.run(
                self._systemctl_action_command(action, unit),
                capture_output=True,
                text=True,
                check=False,
            )
            message = (result.stdout or result.stderr).strip()
            if result.returncode == 0 and not message:
                message = f"{action} submitted for {unit}"
            return {
                "service": service_id,
                "action": action,
                "success": result.returncode == 0,
                "message": message,
                "unit": unit,
                "returncode": result.returncode,
            }
        except Exception as exc:
            logger.error("service_action_failed service=%s action=%s error=%s", service_id, action, exc)
            return {
                "service": service_id,
                "action": action,
                "success": False,
                "message": str(exc),
                "unit": unit,
            }

    async def _get_service_status(self, service_id: str) -> Dict[str, str]:
        unit = self._to_unit(service_id)
        active = subprocess.run(
            [SYSTEMCTL_BIN, "is-active", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        if active.returncode == 0:
            return {"status": "running"}

        exists = subprocess.run(
            [SYSTEMCTL_BIN, "status", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        if exists.returncode == 4:
            return {"status": "missing"}
        return {"status": "stopped"}

    @staticmethod
    def _sudo_ready() -> bool:
        if not SUDO_BIN:
            return False
        probe = subprocess.run(
            [SUDO_BIN, "-n", SYSTEMCTL_BIN, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        return probe.returncode == 0

    def _systemctl_action_command(self, action: str, unit: str) -> List[str]:
        base = self._systemctl_batch_command(action, [unit])
        if self._sudo_ready():
            return [SUDO_BIN, "-n", *base]
        return base

    @staticmethod
    def _systemctl_batch_command(action: str, units: List[str]) -> List[str]:
        command = [SYSTEMCTL_BIN]
        if action in {"start", "stop", "restart"}:
            command.append("--no-block")
        command.append(action)
        command.extend(units)
        return command

    @staticmethod
    def _to_unit(service_id: str) -> str:
        return service_id if service_id.endswith(".service") else f"{service_id}.service"
