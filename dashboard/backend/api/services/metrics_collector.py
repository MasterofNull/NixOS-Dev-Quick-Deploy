"""Metrics collection service."""
import logging
import platform
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import psutil
from api.services.systemd_units import get_ai_runtime_units

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects host and service metrics."""

    def __init__(self):
        self.history: Dict[str, List[Any]] = {}
        self.max_history = 1000
        self._gpu_name_cache: Dict[str, str] = {}
        self._lspci_bin: str | None = self._resolve_lspci_bin()

    async def get_current_metrics(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now().isoformat(),
            **await self.get_system_metrics(),
            "containers": await self.get_container_stats(),
        }

    async def get_system_metrics(self) -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net_io = psutil.net_io_counters()
        primary_iface = self._get_primary_network_interface()

        return {
            "cpu": {
                "usage_percent": cpu_percent,
                "count": psutil.cpu_count(),
                "temperature": await self._get_cpu_temperature(),
                "model": self._get_cpu_model(),
                "arch": platform.machine(),
            },
            "memory": {
                "total": memory.total,
                "used": memory.used,
                "free": memory.available,
                "percent": memory.percent,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "interface": primary_iface,
            },
            "gpu": await self._get_gpu_info(),
            "security": self._get_security_signals(),
            "uptime": self._get_uptime(),
            "load_average": self._get_load_average(),
            "hostname": platform.node(),
        }

    async def get_metric_history(self, metric: str, limit: int) -> List[Any]:
        if metric not in self.history:
            return []
        return self.history[metric][-limit:]

    async def calculate_health_score(self) -> int:
        metrics = await self.get_system_metrics()
        cpu_score = max(0, 100 - metrics["cpu"]["usage_percent"])
        memory_score = max(0, 100 - metrics["memory"]["percent"])
        disk_score = max(0, 100 - metrics["disk"]["percent"])
        return int((cpu_score * 0.4) + (memory_score * 0.4) + (disk_score * 0.2))

    async def _get_cpu_temperature(self) -> str:
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for entries in temps.values():
                        if entries:
                            return f"{entries[0].current}°C"
            return "N/A"
        except Exception:
            return "N/A"

    async def _get_gpu_info(self) -> Dict[str, Any]:
        # Prefer sysfs counters for amdgpu/radeonsi systems; fall back to radeontop.
        gpu_info = self._get_gpu_info_from_sysfs()
        if gpu_info:
            return gpu_info

        gpu_info = self._get_gpu_info_from_radeontop()
        if gpu_info:
            return gpu_info

        return {
            "name": "N/A",
            "usage": "N/A",
            "memory": "N/A",
            "busy_percent": None,
            "vram_used_mb": None,
            "vram_total_mb": None,
        }

    def _get_gpu_info_from_sysfs(self) -> Dict[str, Any] | None:
        for busy_path in Path("/sys/class/drm").glob("card*/device/gpu_busy_percent"):
            device_dir = busy_path.parent
            busy_raw = self._read_int_file(busy_path)
            if busy_raw is None:
                continue

            used_bytes = self._read_int_file(device_dir / "mem_info_vram_used")
            total_bytes = self._read_int_file(device_dir / "mem_info_vram_total")
            used_mb = int(used_bytes / (1024 * 1024)) if isinstance(used_bytes, int) else None
            total_mb = int(total_bytes / (1024 * 1024)) if isinstance(total_bytes, int) else None
            card_name = busy_path.parts[-3]
            gpu_name = self._resolve_gpu_name(card_name, device_dir)

            return {
                "name": gpu_name,
                "usage": f"{busy_raw}%",
                "memory": (
                    f"{used_mb} / {total_mb} MB"
                    if used_mb is not None and total_mb is not None
                    else "N/A"
                ),
                "busy_percent": busy_raw,
                "vram_used_mb": used_mb,
                "vram_total_mb": total_mb,
            }
        return None

    def _resolve_gpu_name(self, card_name: str, device_dir: Path) -> str:
        cached = self._gpu_name_cache.get(card_name)
        if cached:
            return cached

        # Some drivers expose a readable product name directly via sysfs.
        for path in (device_dir / "product_name", device_dir / "name"):
            try:
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    self._gpu_name_cache[card_name] = value
                    return value
            except Exception:
                continue

        pci_slot = ""
        try:
            for line in (device_dir / "uevent").read_text(encoding="utf-8").splitlines():
                if line.startswith("PCI_SLOT_NAME="):
                    pci_slot = line.split("=", 1)[1].strip()
                    break
        except Exception:
            pci_slot = ""

        if pci_slot:
            try:
                if not self._lspci_bin:
                    raise FileNotFoundError("lspci unavailable")
                result = subprocess.run(
                    [self._lspci_bin, "-s", pci_slot],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if result.returncode == 0:
                    line = (result.stdout or "").strip()
                    if ": " in line:
                        value = line.split(": ", 1)[1].strip()
                    else:
                        value = line
                    if value:
                        self._gpu_name_cache[card_name] = value
                        return value
            except Exception:
                pass

        self._gpu_name_cache[card_name] = card_name
        return card_name

    @staticmethod
    def _resolve_lspci_bin() -> str | None:
        for candidate in (
            shutil.which("lspci"),
            str(Path.home() / ".nix-profile/bin/lspci"),
            "/run/current-system/sw/bin/lspci",
            "/usr/bin/lspci",
        ):
            if candidate and Path(candidate).is_file():
                return candidate
        return None

    def _get_gpu_info_from_radeontop(self) -> Dict[str, Any] | None:
        try:
            result = subprocess.run(
                ["radeontop", "-d", "-", "-l", "1"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                output = (result.stdout or "") + "\n" + (result.stderr or "")
                match = re.search(r"gpu\s+([0-9]+(?:\.[0-9]+)?)%", output, re.IGNORECASE)
                busy = float(match.group(1)) if match else None
                return {
                    "name": "AMD GPU",
                    "usage": f"{busy:.1f}%" if busy is not None else "N/A",
                    "memory": "N/A",
                    "busy_percent": round(busy, 1) if busy is not None else None,
                    "vram_used_mb": None,
                    "vram_total_mb": None,
                }
        except Exception:
            pass
        return None

    @staticmethod
    def _read_int_file(path: Path) -> int | None:
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except Exception:
            return None

    def _get_uptime(self) -> int:
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as handle:
                return int(float(handle.readline().split()[0]))
        except Exception:
            return 0

    def _get_load_average(self) -> str:
        try:
            load = psutil.getloadavg()
            return f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
        except Exception:
            return "N/A"

    def _get_security_signals(self) -> Dict[str, Any]:
        firewall_active = self._systemctl_is_active("nftables.service")
        firewall_enabled = self._systemctl_is_enabled("nftables.service")
        apparmor_active = self._systemctl_is_active("apparmor.service")

        return {
            "firewall": {
                "provider": "nftables",
                "active": firewall_active,
                "enabled": firewall_enabled,
            },
            "mandatory_access_control": {
                "apparmor_active": apparmor_active,
            },
        }

    @staticmethod
    def _systemctl_is_active(unit: str) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _systemctl_is_enabled(unit: str) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "is-enabled", unit],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _get_primary_network_interface() -> str:
        # Prefer kernel routing table default route.
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if result.returncode == 0:
                for line in (result.stdout or "").splitlines():
                    parts = line.split()
                    if "dev" in parts:
                        idx = parts.index("dev")
                        if idx + 1 < len(parts):
                            iface = parts[idx + 1].strip()
                            if iface:
                                return iface
        except Exception:
            pass

        # Fallback to first active non-loopback interface.
        try:
            stats = psutil.net_if_stats()
            for name, info in stats.items():
                if name != "lo" and info.isup:
                    return name
        except Exception:
            pass

        return "unknown"

    @staticmethod
    def _get_cpu_model() -> str:
        # Linux primary source.
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.lower().startswith("model name"):
                        _, value = line.split(":", 1)
                        model = value.strip()
                        if model:
                            return model
        except Exception:
            pass

        # Fallback to lscpu if available.
        try:
            lscpu_bin = shutil.which("lscpu") or "/run/current-system/sw/bin/lscpu"
            if lscpu_bin and Path(lscpu_bin).is_file():
                result = subprocess.run(
                    [lscpu_bin],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if result.returncode == 0:
                    for line in (result.stdout or "").splitlines():
                        if line.lower().startswith("model name:"):
                            model = line.split(":", 1)[1].strip()
                            if model:
                                return model
        except Exception:
            pass

        return platform.processor() or "Unknown"

    async def get_container_stats(self) -> Dict[str, Any]:
        monitored_units = get_ai_runtime_units()
        stats: Dict[str, Dict[str, str]] = {}
        running: List[str] = []

        for unit in monitored_units:
            systemd_unit = f"{unit}.service"
            state_proc = subprocess.run(
                ["systemctl", "is-active", systemd_unit],
                capture_output=True,
                text=True,
                check=False,
            )
            state = "running" if state_proc.returncode == 0 else "stopped"
            if state == "running":
                running.append(unit)

            mem_proc = subprocess.run(
                ["systemctl", "show", systemd_unit, "--property=MemoryCurrent", "--value"],
                capture_output=True,
                text=True,
                check=False,
            )
            stats[unit] = {
                "status": state,
                "memory_bytes": (mem_proc.stdout or "0").strip() or "0",
            }

        return {
            "count": len(monitored_units),
            "running": running,
            "stats": stats,
        }
