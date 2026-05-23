"""inference_param_manager.py — Thermal + hardware state monitor for IPM Phase B.

Phase B scope (read-only path):
- Read thermal sensors from /sys/class/hwmon (AMD k10temp/amdgpu)
- Read RAM utilization from /proc/meminfo
- Emit thermal_state events for future scheduler consumption (AM-G3)
- Expose GET /api/hardware/state endpoint (JSON)
- Track MTP acceptance rate from llama.cpp /metrics (Prometheus)
- NO enforcement yet — thresholds pending Qwen sign-off

Phase C will wire thermal_state events into MLFQScheduler admission control.
"""

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger("hybrid-coordinator.ipm")

@dataclass
class HardwareState:
    temp_cpu_c: Optional[float] = None
    temp_gpu_c: Optional[float] = None
    ram_total_gb: float = 0.0
    ram_free_gb: float = 0.0
    ram_used_pct: float = 0.0
    mtp_acceptance_rate: Optional[float] = None
    thermal_tier: str = "unknown"
    n_gpu_layers_current: Optional[int] = None
    updated_at: float = 0.0

class InferenceParamManager:
    def __init__(self):
        self._state = HardwareState()
        self._polling_task: Optional[asyncio.Task] = None
        self._poll_interval = float(os.getenv("THERMAL_POLL_MS", "500")) / 1000.0
        self._llama_url = os.getenv("LLAMA_CPP_URL", "http://localhost:8080")
        self._hwmon_paths: Dict[str, Path] = {}
        self._find_hwmon_sensors()

    def _find_hwmon_sensors(self):
        """Locate k10temp and amdgpu sensors in /sys/class/hwmon."""
        hwmon_root = Path("/sys/class/hwmon")
        if not hwmon_root.exists():
            return

        for hwmon_dir in hwmon_root.iterdir():
            try:
                name_file = hwmon_dir / "name"
                if not name_file.exists():
                    continue
                name = name_file.read_text().strip()
                if name == "k10temp":
                    self._hwmon_paths["cpu"] = hwmon_dir
                elif name == "amdgpu":
                    self._hwmon_paths["gpu"] = hwmon_dir
            except Exception as e:
                logger.debug(f"Failed to read hwmon at {hwmon_dir}: {e}")

    async def start(self):
        if self._polling_task is None:
            self._polling_task = asyncio.create_task(self._poll_loop())
            logger.info("InferenceParamManager started")

    async def stop(self):
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
            logger.info("InferenceParamManager stopped")

    async def hardware_state(self) -> HardwareState:
        return self._state

    async def _poll_loop(self):
        while True:
            try:
                start_time = time.perf_counter()
                
                # Perform I/O in threads
                thermal_data = await asyncio.to_thread(self._read_thermal_sync)
                mem_data = await asyncio.to_thread(self._read_meminfo_sync)
                n_gpu_layers = await asyncio.to_thread(self._read_n_gpu_layers_sync)
                
                # Async I/O for MTP rate
                mtp_rate = await self._fetch_mtp_rate()

                # Update state
                self._state.temp_cpu_c = thermal_data.get("cpu")
                self._state.temp_gpu_c = thermal_data.get("gpu")
                self._state.ram_total_gb = mem_data.get("total", 0.0)
                self._state.ram_free_gb = mem_data.get("free", 0.0)
                self._state.ram_used_pct = mem_data.get("used_pct", 0.0)
                self._state.mtp_acceptance_rate = mtp_rate
                self._state.n_gpu_layers_current = n_gpu_layers
                self._state.updated_at = time.time()
                
                # Determine thermal tier
                self._state.thermal_tier = self._determine_thermal_tier()

                # AM-G3: propagate thermal tier to MLFQ scheduler
                try:
                    from mlfq_scheduler import get_scheduler
                    await get_scheduler().set_thermal_tier(self._state.thermal_tier)
                except Exception:
                    pass  # scheduler may not be running yet

                elapsed = time.perf_counter() - start_time
                await asyncio.sleep(max(0, self._poll_interval - elapsed))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in IPM poll loop: {e}")
                await asyncio.sleep(self._poll_interval)

    def _determine_thermal_tier(self) -> str:
        temps = [t for t in [self._state.temp_cpu_c, self._state.temp_gpu_c] if t is not None]
        if not temps:
            return "unknown"
        
        max_t = max(temps)
        if max_t >= 88:
            return "shutdown"
        if max_t >= 80:
            return "critical"
        if max_t >= 70:
            return "warn"
        return "optimal"

    def _read_thermal_sync(self) -> dict:
        data = {}
        # CPU (k10temp)
        if "cpu" in self._hwmon_paths:
            path = self._hwmon_paths["cpu"]
            # Try Tctl or Tdie
            for i in range(1, 10):
                label_path = path / f"temp{i}_label"
                if label_path.exists():
                    label = label_path.read_text().strip()
                    if label in ("Tctl", "Tdie"):
                        input_path = path / f"temp{i}_input"
                        if input_path.exists():
                            data["cpu"] = float(input_path.read_text().strip()) / 1000.0
                            break
            # Fallback to first temp if no label match
            if "cpu" not in data:
                input_path = path / "temp1_input"
                if input_path.exists():
                    data["cpu"] = float(input_path.read_text().strip()) / 1000.0

        # GPU (amdgpu)
        if "gpu" in self._hwmon_paths:
            path = self._hwmon_paths["gpu"]
            # Try junction or edge
            for i in range(1, 10):
                label_path = path / f"temp{i}_label"
                if label_path.exists():
                    label = label_path.read_text().strip()
                    if label in ("junction", "edge"):
                        input_path = path / f"temp{i}_input"
                        if input_path.exists():
                            data["gpu"] = float(input_path.read_text().strip()) / 1000.0
                            break
            # Fallback to first temp if no label match
            if "gpu" not in data:
                input_path = path / "temp1_input"
                if input_path.exists():
                    data["gpu"] = float(input_path.read_text().strip()) / 1000.0
        
        return data

    def _read_meminfo_sync(self) -> dict:
        data = {}
        try:
            meminfo = Path("/proc/meminfo").read_text()
            m = re.search(r"MemTotal:\s+(\d+)\s+kB", meminfo)
            total_kb = int(m.group(1)) if m else 0
            
            m = re.search(r"MemAvailable:\s+(\d+)\s+kB", meminfo)
            if m:
                avail_kb = int(m.group(1))
            else:
                # Fallback for older kernels
                m = re.search(r"MemFree:\s+(\d+)\s+kB", meminfo)
                free_kb = int(m.group(1)) if m else 0
                m = re.search(r"Cached:\s+(\d+)\s+kB", meminfo)
                cached_kb = int(m.group(1)) if m else 0
                avail_kb = free_kb + cached_kb

            data["total"] = total_kb / (1024 * 1024)
            data["free"] = avail_kb / (1024 * 1024)
            if total_kb > 0:
                data["used_pct"] = 100.0 * (total_kb - avail_kb) / total_kb
            else:
                data["used_pct"] = 0.0
        except Exception as e:
            logger.debug(f"Failed to read /proc/meminfo: {e}")
        return data

    def _read_n_gpu_layers_sync(self) -> Optional[int]:
        """Find the chat llama-server process and extract --n-gpu-layers from cmdline.

        Skips embedding servers (--embedding flag) to avoid picking up the embed
        server's cmdline which contains intermediate --n-gpu-layers 99 before the
        final --n-gpu-layers 12, causing the IPM to report 99 instead of 12.
        """
        try:
            for proc_dir in Path("/proc").iterdir():
                if not proc_dir.name.isdigit():
                    continue
                try:
                    cmdline = (proc_dir / "cmdline").read_bytes().split(b"\x00")
                    is_llama = any(b"llama-server" in arg or b"llama.cpp" in arg for arg in cmdline)
                    if not is_llama:
                        continue
                    # Skip embedding servers — they have a separate GPU layer budget
                    if b"--embedding" in cmdline:
                        continue
                    # Use the LAST occurrence of --n-gpu-layers (cmdline may repeat the flag)
                    result = None
                    for i, arg in enumerate(cmdline):
                        if arg == b"-ngl" or arg == b"--n-gpu-layers":
                            if i + 1 < len(cmdline):
                                try:
                                    result = int(cmdline[i+1])
                                except ValueError:
                                    pass
                        elif arg.startswith(b"--n-gpu-layers="):
                            try:
                                result = int(arg.split(b"=")[1])
                            except ValueError:
                                pass
                    if result is not None:
                        return result
                except (OSError, ValueError, IndexError):
                    continue
        except Exception as e:
            logger.debug(f"Failed to read /proc for n_gpu_layers: {e}")
        return None

    async def _fetch_mtp_rate(self) -> Optional[float]:
        """Derive MTP acceptance rate from llama.cpp Prometheus metrics.

        llama.cpp with --spec-type draft-mtp does NOT expose a dedicated
        acceptance_rate metric. We derive it from the decode efficiency ratio:
            tokens_per_decode = tokens_predicted_total / n_decode_total
            acceptance_rate = (tokens_per_decode - 1) / spec_draft_n_max

        When spec_draft_n_max=2 and all drafts accepted: tokens_per_decode≈3 → rate=1.0
        When no drafts accepted: tokens_per_decode≈1 → rate=0.0
        """
        try:
            async with httpx.AsyncClient(timeout=0.2) as client:
                resp = await client.get(f"{self._llama_url}/metrics")
                if resp.status_code != 200:
                    return None
                metrics: dict = {}
                for line in resp.text.splitlines():
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            metrics[parts[0]] = float(parts[1])
                        except ValueError:
                            pass
                tokens_predicted = metrics.get("llamacpp:tokens_predicted_total", 0.0)
                n_decode = metrics.get("llamacpp:n_decode_total", 0.0)
                if n_decode < 10:
                    # Not enough data for a meaningful estimate
                    return None
                tokens_per_decode = tokens_predicted / n_decode
                if tokens_per_decode <= 1.01:
                    # No speculative gains observed — MTP may not be active
                    return 0.0
                # spec_draft_n_max=2 is our deployed config (options.nix default)
                spec_draft_n_max = int(os.getenv("LLAMA_SPEC_DRAFT_N_MAX", "2"))
                rate = (tokens_per_decode - 1.0) / spec_draft_n_max
                return round(min(1.0, max(0.0, rate)), 4)
        except Exception as e:
            logger.debug(f"Failed to derive MTP rate from {self._llama_url}/metrics: {e}")
        return None

_ipm: Optional[InferenceParamManager] = None

def get_ipm() -> InferenceParamManager:
    global _ipm
    if _ipm is None:
        _ipm = InferenceParamManager()
    return _ipm
