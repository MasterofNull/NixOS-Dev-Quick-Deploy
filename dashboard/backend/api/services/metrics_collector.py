"""Metrics collection service"""
import psutil
import platform
import subprocess
import re
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects system metrics"""
    
    def __init__(self):
        self.history: Dict[str, List] = {}
        self.max_history = 1000
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get all current system metrics"""
        return {
            "timestamp": datetime.now().isoformat(),
            **await self.get_system_metrics(),
            "containers": await self.get_container_stats(),
        }
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics (CPU, memory, disk, network)"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net_io = psutil.net_io_counters()
        
        # Get CPU temperature if available
        cpu_temp = await self._get_cpu_temperature()
        
        # Get GPU info if available
        gpu_info = await self._get_gpu_info()
        
        return {
            "cpu": {
                "usage_percent": cpu_percent,
                "count": psutil.cpu_count(),
                "temperature": cpu_temp,
                "model": platform.processor() or "Unknown",
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
            },
            "gpu": gpu_info,
            "uptime": self._get_uptime(),
            "load_average": self._get_load_average(),
            "hostname": platform.node(),
        }
    
    async def get_metric_history(self, metric: str, limit: int) -> List[Any]:
        """Get historical data for a metric"""
        if metric not in self.history:
            return []
        return self.history[metric][-limit:]
    
    async def calculate_health_score(self) -> int:
        """Calculate overall system health score (0-100)"""
        metrics = await self.get_system_metrics()
        
        # Simple health score calculation
        cpu_score = max(0, 100 - metrics["cpu"]["usage_percent"])
        memory_score = max(0, 100 - metrics["memory"]["percent"])
        disk_score = max(0, 100 - metrics["disk"]["percent"])
        
        # Weighted average
        health_score = int((cpu_score * 0.4) + (memory_score * 0.4) + (disk_score * 0.2))
        
        return health_score
    
    async def _get_cpu_temperature(self) -> str:
        """Get CPU temperature"""
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if entries:
                            return f"{entries[0].current}°C"
            return "N/A"
        except Exception:
            return "N/A"
    
    async def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU information"""
        try:
            # Try AMD GPU first
            result = subprocess.run(
                ["radeontop", "-d", "-", "-l", "1"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                # Parse radeontop output
                return {"name": "AMD GPU", "usage": "N/A", "memory": "N/A"}
        except Exception:
            pass
        
        return {"name": "N/A", "usage": "N/A", "memory": "N/A"}
    
    def _get_uptime(self) -> int:
        """Get system uptime in seconds"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                return int(uptime_seconds)
        except Exception:
            return 0
    
    def _get_load_average(self) -> str:
        """Get system load average"""
        try:
            load = psutil.getloadavg()
            return f"{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}"
        except Exception:
            return "N/A"

    async def get_container_stats(self) -> Dict[str, Any]:
        """Get Podman container statistics"""
        try:
            # Get list of running containers
            result = subprocess.run(
                ["podman", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return {"count": 0, "running": [], "stats": {}}

            container_names = [name for name in result.stdout.strip().split('\n') if name]

            # Get stats for each container
            stats = {}
            for name in container_names:
                stat_result = subprocess.run(
                    ["podman", "stats", "--no-stream", "--format",
                     "{{.CPUPerc}},{{.MemUsage}},{{.NetIO}},{{.BlockIO}}", name],
                    capture_output=True,
                    text=True,
                    timeout=3
                )

                if stat_result.returncode == 0:
                    parts = stat_result.stdout.strip().split(',')
                    if len(parts) >= 4:
                        stats[name] = {
                            "cpu": parts[0],
                            "memory": parts[1],
                            "network": parts[2],
                            "disk": parts[3],
                        }

            return {
                "count": len(container_names),
                "running": container_names,
                "stats": stats
            }
        except Exception as e:
            logger.error(f"Error getting container stats: {e}")
            return {"count": 0, "running": [], "stats": {}}