"""Container-style controls backed by systemd services."""
import logging
import subprocess
from typing import Any, Dict, List

from api.services.systemd_units import get_ai_runtime_units

logger = logging.getLogger(__name__)


class ContainerManager:
    """Compatibility layer for old container endpoints."""

    async def list_containers(self) -> List[Dict[str, Any]]:
        ai_units = get_ai_runtime_units()
        entries: List[Dict[str, Any]] = []
        for unit in ai_units:
            state = self._unit_state(unit)
            entries.append(
                {
                    "id": unit,
                    "name": unit,
                    "image": "n/a",
                    "status": state,
                    "created": "",
                }
            )
        return entries

    async def start_ai_stack(self) -> Dict[str, Any]:
        return await self._batch("start")

    async def stop_ai_stack(self) -> Dict[str, Any]:
        return await self._batch("stop")

    async def restart_ai_stack(self) -> Dict[str, Any]:
        return await self._batch("restart")

    async def start_container(self, container_id: str) -> Dict[str, Any]:
        return self._unit_action(container_id, "start")

    async def stop_container(self, container_id: str) -> Dict[str, Any]:
        return self._unit_action(container_id, "stop")

    async def restart_container(self, container_id: str) -> Dict[str, Any]:
        return self._unit_action(container_id, "restart")

    async def get_logs(self, container_id: str, tail: int = 100) -> str:
        unit = self._to_unit(container_id)
        result = subprocess.run(
            ["journalctl", "-u", unit, "-n", str(tail), "--no-pager"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return (result.stderr or result.stdout).strip()
        return result.stdout

    async def _batch(self, action: str) -> Dict[str, Any]:
        ai_units = get_ai_runtime_units()
        results: List[Dict[str, Any]] = []
        for unit in ai_units:
            results.append(self._unit_action(unit, action))
        return {"action": f"{action}_ai_stack", "results": results}

    def _unit_action(self, container_id: str, action: str) -> Dict[str, Any]:
        unit = self._to_unit(container_id)
        try:
            result = subprocess.run(
                ["systemctl", action, unit],
                capture_output=True,
                text=True,
                check=False,
            )
            return {
                "container": container_id,
                "action": action,
                "success": result.returncode == 0,
                "message": (result.stdout or result.stderr).strip(),
            }
        except Exception as exc:
            logger.error("unit_action_failed unit=%s action=%s error=%s", unit, action, exc)
            return {
                "container": container_id,
                "action": action,
                "success": False,
                "message": str(exc),
            }

    def _unit_state(self, unit_name: str) -> str:
        unit = self._to_unit(unit_name)
        result = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        return "running" if result.returncode == 0 else "stopped"

    @staticmethod
    def _to_unit(unit_name: str) -> str:
        return unit_name if unit_name.endswith(".service") else f"{unit_name}.service"
