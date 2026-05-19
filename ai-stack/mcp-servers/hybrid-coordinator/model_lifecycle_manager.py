"""model_lifecycle_manager.py — Download, verify, stage, and hot-swap models.

Implements the Phase A lifecycle operations defined in SYSTEM-COMPARISON-PLAN.md.
All blocking I/O runs in asyncio.to_thread to avoid blocking the event loop.

Hot-swap strategy for Renoir APU (CPU-only path):
  1. Verify target model is in VERIFIED state.
  2. Transition current ACTIVE → RETIRING.
  3. Update active.gguf symlink atomically (os.replace).
  4. Attempt `sudo systemctl restart llama-cpp.service` (may fail if sudo not available).
  5. Poll llama-cpp health endpoint until UP or timeout.
  6. If UP within budget: CANDIDATE → ACTIVE, RETIRING → ARCHIVED.
  7. If timeout: revert symlink → ACTIVE restored, new model → FAILED.

SLA tiers (Gemini AM-G1):
  - gpu_fast: <5s budget
  - cpu_fallback: <30s budget (Renoir APU default)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import AsyncIterator, Callable, Dict, Optional

import aiohttp

from .model_registry import MODEL_DIR, ModelRegistry, ModelState, get_registry

logger = logging.getLogger(__name__)

# HuggingFace base URL — no hardcoded tokens; reads HF_TOKEN env var
HF_BASE_URL = "https://huggingface.co"
LLAMA_HEALTH_URL = os.getenv("LLAMA_CPP_HEALTH_URL", "http://127.0.0.1:8080/health")
ACTIVE_SYMLINK = MODEL_DIR / "active.gguf"

# SLA budgets in seconds
SLA_BUDGETS = {"gpu_fast": 5.0, "cpu_fallback": 30.0}

# Download chunk size
CHUNK_SIZE = 1 * 1024 * 1024  # 1 MB


def _hf_url(repo: str, filename: str) -> str:
    return f"{HF_BASE_URL}/{repo}/resolve/main/{filename}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_symlink(target: Path, link: Path) -> None:
    """Atomically replace a symlink using a temp link + os.replace."""
    tmp_link = link.with_suffix(".swap.tmp")
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()
    os.symlink(target, tmp_link)
    os.replace(tmp_link, link)


async def _poll_llama_health(timeout_s: float) -> bool:
    """Return True if llama-cpp health responds OK within timeout."""
    deadline = time.monotonic() + timeout_s
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=3.0)
    ) as session:
        while time.monotonic() < deadline:
            try:
                async with session.get(LLAMA_HEALTH_URL) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass
            await asyncio.sleep(1.5)
    return False


async def _restart_llama_service() -> tuple[bool, str]:
    """Attempt to restart llama-cpp.service. Returns (success, message)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-n", "systemctl", "restart", "llama-cpp.service",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        if proc.returncode == 0:
            return True, "restarted"
        return False, stderr.decode().strip() or f"exit {proc.returncode}"
    except asyncio.TimeoutError:
        return False, "systemctl restart timed out"
    except Exception as exc:
        return False, str(exc)


class ModelLifecycleManager:
    """Manages the full lifecycle of local GGUF models."""

    def __init__(self, registry: Optional[ModelRegistry] = None) -> None:
        self._registry = registry or get_registry()
        # Active download tasks: model_id → asyncio.Task
        self._download_tasks: Dict[str, asyncio.Task] = {}
        # Progress callbacks: model_id → callable(bytes_done, total, pct)
        self._progress_cbs: Dict[str, list] = {}

    # ── Download ─────────────────────────────────────────────────────────────

    def subscribe_progress(self, model_id: str, cb: Callable) -> None:
        self._progress_cbs.setdefault(model_id, []).append(cb)

    def unsubscribe_progress(self, model_id: str, cb: Callable) -> None:
        if model_id in self._progress_cbs:
            try:
                self._progress_cbs[model_id].remove(cb)
            except ValueError:
                pass

    def _notify_progress(self, model_id: str, done: int, total: int, pct: float) -> None:
        for cb in list(self._progress_cbs.get(model_id, [])):
            try:
                cb(done, total, pct)
            except Exception:
                pass

    async def start_download(self, model_id: str) -> None:
        """Begin background download for model_id. Idempotent if already downloading."""
        entry = await self._registry.get_model(model_id)
        if entry is None:
            raise KeyError(f"Model {model_id!r} not in registry")

        state = ModelState(entry["state"])
        if state == ModelState.DOWNLOADING:
            return  # already running

        # Allow re-download from FAILED or AVAILABLE
        if state not in (ModelState.AVAILABLE, ModelState.FAILED):
            raise ValueError(f"Cannot download model in state {state.value}")

        await self._registry.transition(model_id, ModelState.DOWNLOADING)
        task = asyncio.create_task(self._download_task(model_id, entry))
        self._download_tasks[model_id] = task
        task.add_done_callback(lambda t: self._download_tasks.pop(model_id, None))

    async def _download_task(self, model_id: str, entry: Dict) -> None:
        repo = entry["repo"]
        filename = entry["file"]
        url = _hf_url(repo, filename)
        dest = MODEL_DIR / filename
        tmp = MODEL_DIR / f".dl-{model_id}.tmp"

        headers: Dict[str, str] = {}
        hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=7200, connect=30)
            ) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 404:
                        raise RuntimeError(f"Model file not found on HuggingFace: {url}")
                    resp.raise_for_status()
                    total = int(resp.headers.get("Content-Length", 0))
                    done = 0
                    with open(tmp, "wb") as fh:
                        async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                            fh.write(chunk)
                            done += len(chunk)
                            pct = (done / total * 100) if total else 0.0
                            self._notify_progress(model_id, done, total, pct)
                            await self._registry.update_fields(model_id, {
                                "download_bytes": done,
                                "download_total": total,
                                "download_progress": round(pct, 1),
                            })

            # Move completed file
            await asyncio.to_thread(lambda: tmp.rename(dest))
            await self._registry.transition(
                model_id, ModelState.DOWNLOADED,
                update={"local_path": str(dest), "download_bytes": done, "download_total": total, "download_progress": 100.0}
            )
            # Auto-verify
            await self.verify_model(model_id)

        except Exception as exc:
            logger.error("model_lifecycle: download failed %s: %s", model_id, exc)
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            await self._registry.transition(
                model_id, ModelState.FAILED, error=str(exc)[:400]
            )

    # ── Verify ───────────────────────────────────────────────────────────────

    async def verify_model(self, model_id: str) -> None:
        """SHA256-verify the downloaded file. Updates state → VERIFIED or FAILED."""
        entry = await self._registry.get_model(model_id)
        if entry is None:
            raise KeyError(model_id)

        local_path = entry.get("local_path")
        if not local_path:
            raise ValueError(f"No local_path for {model_id}")

        expected_sha = entry.get("sha256")
        try:
            actual_sha = await asyncio.to_thread(_sha256_file, Path(local_path))
            if expected_sha and expected_sha != actual_sha:
                raise ValueError(
                    f"SHA256 mismatch: expected {expected_sha[:16]}… got {actual_sha[:16]}…"
                )
            await self._registry.transition(
                model_id, ModelState.VERIFIED,
                update={"sha256": actual_sha}
            )
        except Exception as exc:
            logger.error("model_lifecycle: verify failed %s: %s", model_id, exc)
            await self._registry.transition(model_id, ModelState.FAILED, error=str(exc)[:400])
            raise

    # ── Promote / Hot-Swap ───────────────────────────────────────────────────

    async def promote_model(self, model_id: str) -> Dict:
        """Promote a VERIFIED model to ACTIVE via hot-swap.

        Returns a result dict with: success, duration_s, sla_tier, sla_met, message.
        """
        entry = await self._registry.get_model(model_id)
        if entry is None:
            raise KeyError(model_id)

        state = ModelState(entry["state"])
        if state != ModelState.VERIFIED:
            raise ValueError(f"Model must be in VERIFIED state to promote (current: {state.value})")

        sla_tier = entry.get("swap_sla_tier", "cpu_fallback")
        sla_budget = SLA_BUDGETS.get(sla_tier, 30.0)
        local_path = entry.get("local_path")
        if not local_path:
            raise ValueError(f"No local_path for {model_id}")

        swap_start = time.monotonic()

        # 1. Transition to WARMING
        await self._registry.transition(model_id, ModelState.WARMING, update={"swap_started_at": time.time()})

        # 2. Retire current active model if any
        current_active = await self._registry.get_active_model()
        prev_symlink_target: Optional[Path] = None
        if current_active:
            prev_id = current_active["id"]
            # Capture current symlink for rollback
            if ACTIVE_SYMLINK.is_symlink():
                try:
                    prev_symlink_target = ACTIVE_SYMLINK.resolve()
                except OSError:
                    pass
            await self._registry.transition(prev_id, ModelState.RETIRING)

        # 3. Update symlink atomically
        try:
            await asyncio.to_thread(_atomic_symlink, Path(local_path), ACTIVE_SYMLINK)
        except Exception as exc:
            logger.error("model_lifecycle: symlink update failed: %s", exc)
            await self._registry.transition(model_id, ModelState.FAILED, error=f"symlink: {exc}")
            if current_active:
                try:
                    await self._registry.transition(current_active["id"], ModelState.ACTIVE)
                except Exception:
                    pass
            return {"success": False, "message": f"symlink update failed: {exc}"}

        # 4. Transition new model to CANDIDATE
        await self._registry.transition(model_id, ModelState.CANDIDATE)

        # 5. Restart service and poll health
        restart_ok, restart_msg = await _restart_llama_service()
        if not restart_ok:
            logger.warning("model_lifecycle: service restart failed (%s) — polling anyway", restart_msg)

        health_ok = await _poll_llama_health(sla_budget)
        duration_s = time.monotonic() - swap_start
        sla_met = health_ok and duration_s <= sla_budget

        if health_ok:
            # 6a. Success path
            await self._registry.transition(
                model_id, ModelState.ACTIVE,
                update={
                    "promoted_at": time.time(),
                    "swap_finished_at": time.time(),
                    "swap_duration_s": round(duration_s, 2),
                }
            )
            if current_active:
                try:
                    await self._registry.transition(current_active["id"], ModelState.ARCHIVED)
                except Exception:
                    pass
            logger.info(
                "model_lifecycle: promoted %s in %.1fs (SLA %s, budget %.0fs)",
                model_id, duration_s, "MET" if sla_met else "MISSED", sla_budget
            )
            return {
                "success": True,
                "duration_s": round(duration_s, 2),
                "sla_tier": sla_tier,
                "sla_met": sla_met,
                "message": f"promoted in {duration_s:.1f}s",
            }
        else:
            # 6b. Rollback path
            logger.error("model_lifecycle: health check failed after %.1fs — rolling back", duration_s)
            if prev_symlink_target and prev_symlink_target.exists():
                try:
                    await asyncio.to_thread(_atomic_symlink, prev_symlink_target, ACTIVE_SYMLINK)
                    await _restart_llama_service()
                except Exception as rollback_exc:
                    logger.error("model_lifecycle: rollback symlink failed: %s", rollback_exc)

            await self._registry.transition(
                model_id, ModelState.FAILED,
                error=f"health timeout after {duration_s:.1f}s"
            )
            if current_active:
                try:
                    await self._registry.transition(current_active["id"], ModelState.ACTIVE)
                except Exception:
                    pass
            return {
                "success": False,
                "duration_s": round(duration_s, 2),
                "sla_tier": sla_tier,
                "sla_met": False,
                "message": f"health check failed after {duration_s:.1f}s; rolled back",
            }

    # ── Rollback ─────────────────────────────────────────────────────────────

    async def rollback_to(self, model_id: str) -> Dict:
        """Manually promote an ARCHIVED model back to ACTIVE."""
        entry = await self._registry.get_model(model_id)
        if entry is None:
            raise KeyError(model_id)

        state = ModelState(entry["state"])
        # Allow rollback from archived or verified
        if state not in (ModelState.ARCHIVED, ModelState.VERIFIED):
            raise ValueError(f"Rollback requires ARCHIVED or VERIFIED state (current: {state.value})")

        local_path = entry.get("local_path")
        if not local_path or not Path(local_path).exists():
            raise ValueError(f"Model file missing for rollback: {local_path}")

        # Put back in VERIFIED so promote_model can handle it
        if state == ModelState.ARCHIVED:
            await self._registry.transition(model_id, ModelState.AVAILABLE)
            await self._registry.transition(model_id, ModelState.DOWNLOADING)
            await self._registry.transition(model_id, ModelState.DOWNLOADED)
            await self._registry.transition(model_id, ModelState.VERIFIED)

        return await self.promote_model(model_id)

    # ── Cancel ───────────────────────────────────────────────────────────────

    async def cancel_download(self, model_id: str) -> bool:
        task = self._download_tasks.get(model_id)
        if task and not task.done():
            task.cancel()
            return True
        return False


# Module-level singleton
_manager: Optional[ModelLifecycleManager] = None


def get_lifecycle_manager() -> ModelLifecycleManager:
    global _manager
    if _manager is None:
        _manager = ModelLifecycleManager()
    return _manager
