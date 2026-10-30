"""Service management."""
import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List

from api.services.systemd_units import get_monitored_units

logger = logging.getLogger(__name__)

# The NixOS module sets SYSTEMCTL_BIN to the exact store path that the
# per-unit sudoers rules (command-center-dashboard.nix) are written against.
SYSTEMCTL_BIN = os.environ.get("SYSTEMCTL_BIN") or (
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
        # One systemctl call per unit: sudoers rules are exact per-unit commands.
        monitored_services = get_monitored_units(include_dashboard=False)
        results: List[Dict[str, Any]] = [
            await self._run_unit_action(service_id, action) for service_id in monitored_services
        ]
        failed = sum(1 for r in results if not r["success"])
        return {
            "action": f"{action}_all",
            "success": failed == 0,
            "succeeded": len(results) - failed,
            "failed": failed,
            "message": f"{action} submitted for {len(results) - failed}/{len(results)} services",
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
    def _sudo_allows(command: List[str]) -> bool:
        """True when sudoers permits this exact command without a password."""
        if not SUDO_BIN:
            return False
        probe = subprocess.run(
            [SUDO_BIN, "-n", "-l", *command],
            capture_output=True,
            text=True,
            check=False,
        )
        return probe.returncode == 0

    def _systemctl_action_command(self, action: str, unit: str) -> List[str]:
        base = [SYSTEMCTL_BIN, "--no-block", action, unit]
        if self._sudo_allows(base):
            return [SUDO_BIN, "-n", *base]
        return base

    @staticmethod
    def _to_unit(service_id: str) -> str:
        return service_id if service_id.endswith(".service") else f"{service_id}.service"
