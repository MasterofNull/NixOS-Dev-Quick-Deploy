"""model_registry.py — Durable model catalog + lifecycle state machine.

State machine (Codex AM-C4):
  available → downloading → downloaded → verified → warming
  → candidate → active → retiring → archived
  any state → failed (on error)

Registry is persisted to REGISTRY_PATH as JSON. Concurrent access is
serialized via an asyncio Lock so no file-level locking is needed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import os
logger = logging.getLogger(__name__)

# Paths — override via env vars so dashboard (running as hyperd) can use writable locations.
# After nixos-rebuild these point to the system paths owned by ai-hybrid / llama.
_DEFAULT_REGISTRY = os.getenv(
    "MODEL_REGISTRY_PATH",
    str(Path.home() / ".local/share/nixos-ai-stack/model-registry.json")
)
_DEFAULT_MODEL_DIR = os.getenv(
    "MODEL_DIR",
    "/var/lib/llama-cpp/models"
)
REGISTRY_PATH = Path(_DEFAULT_REGISTRY)
MODEL_DIR = Path(_DEFAULT_MODEL_DIR)

# Registry schema version — bump when structure changes
REGISTRY_VERSION = 2


class ModelState(str, Enum):
    AVAILABLE = "available"       # in catalog, not downloaded
    DOWNLOADING = "downloading"   # download in progress
    DOWNLOADED = "downloaded"     # file on disk, not yet verified
    VERIFIED = "verified"         # SHA256 OK
    WARMING = "warming"           # being loaded into memory
    CANDIDATE = "candidate"       # loaded, traffic not yet routed
    ACTIVE = "active"             # serving live traffic
    RETIRING = "retiring"         # draining connections, being replaced
    ARCHIVED = "archived"         # no longer used, file may be retained
    FAILED = "failed"             # error state

    def can_transition_to(self, target: "ModelState") -> bool:
        _ALLOWED: Dict[ModelState, set] = {
            ModelState.AVAILABLE:    {ModelState.DOWNLOADING},
            ModelState.DOWNLOADING:  {ModelState.DOWNLOADED, ModelState.FAILED},
            ModelState.DOWNLOADED:   {ModelState.VERIFIED, ModelState.FAILED},
            ModelState.VERIFIED:     {ModelState.WARMING, ModelState.AVAILABLE},
            ModelState.WARMING:      {ModelState.CANDIDATE, ModelState.FAILED},
            ModelState.CANDIDATE:    {ModelState.ACTIVE, ModelState.FAILED, ModelState.AVAILABLE},
            ModelState.ACTIVE:       {ModelState.RETIRING},
            ModelState.RETIRING:     {ModelState.ARCHIVED, ModelState.ACTIVE},  # rollback path
            ModelState.ARCHIVED:     set(),
            ModelState.FAILED:       {ModelState.AVAILABLE, ModelState.DOWNLOADING},
        }
        return target in _ALLOWED.get(self, set())


# Quant tier ladder (T0–T5, Qwen PRD §3.2)
QUANT_TIERS = {
    "T0": {"label": "Q2_K",   "desc": "ultra-low RAM",      "ram_factor": 0.55},
    "T1": {"label": "Q3_K_M", "desc": "low RAM",            "ram_factor": 0.70},
    "T2": {"label": "Q4_K_M", "desc": "default",            "ram_factor": 1.00},
    "T3": {"label": "Q4_K_XL","desc": "coding/reasoning",   "ram_factor": 1.05},
    "T4": {"label": "Q5_K_M", "desc": "quality-critical",   "ram_factor": 1.30},
    "T5": {"label": "Q8_0",   "desc": "near-lossless",      "ram_factor": 1.75},
}

# Built-in catalog seeded from defaultModelCatalog in ai-stack.nix
# These are the AVAILABLE (not-yet-downloaded) entries.
_BUILTIN_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "qwen3.6-35b-mtp",
        # llama-server flags that are SPECIFIC to this model (merged with base service args)
        "llama_args": {
            "ctx_size": 16384,
            "n_gpu_layers": 12,
            "spec_type": "draft-mtp",
            "spec_draft_n_max": 2,
            "parallel": 1,
            "flash_attn": "off",
            "mlock": True,
            "jinja": True,
            "batch_size": 512,
            "ubatch_size": 256,
            "threads": 8,
            "threads_batch": 8,
        },
        "name": "Qwen3.6 35B A3B MTP",
        "repo": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF",
        "file": "Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
        "sha256": None,
        "params": "35B (3B active MoE) + MTP heads",
        "context_size": 262144,
        "ram_estimate_gb": 22.5,
        "quant_tier": "T3",
        "type": "moe",
        "hardware_targets": ["apu_renoir", "igpu_rdna2"],
        "mtp_sibling": None,
        "swap_sla_tier": "cpu_fallback",
        "recommended": True,
        "description": "Primary Renoir APU model with MTP speculation",
    },
    {
        "id": "qwen3.6-35b",
        "llama_args": {
            "ctx_size": 16384,
            "n_gpu_layers": 12,
            "parallel": 1,
            "flash_attn": "off",
            "mlock": True,
            "jinja": True,
            "batch_size": 512,
            "ubatch_size": 256,
            "threads": 8,
            "threads_batch": 8,
        },
        "name": "Qwen3.6 35B A3B",
        "repo": "unsloth/Qwen3.6-35B-A3B-GGUF",
        "file": "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf",
        "sha256": None,
        "params": "35B (3B active MoE)",
        "context_size": 262144,
        "ram_estimate_gb": 22.1,
        "quant_tier": "T2",
        "type": "moe",
        "hardware_targets": ["apu_renoir", "igpu_rdna2"],
        "mtp_sibling": "qwen3.6-35b-mtp",
        "swap_sla_tier": "cpu_fallback",
        "recommended": False,
        "description": "Qwen3.6 35B default quant tier fallback",
    },
    {
        "id": "qwen3-8b",
        "llama_args": {
            "ctx_size": 8192,
            "n_gpu_layers": 12,
            "parallel": 2,
            "mlock": True,
            "jinja": True,
            "batch_size": 512,
            "ubatch_size": 256,
            "threads": 8,
            "threads_batch": 8,
        },
        "name": "Qwen3 8B Instruct",
        "repo": "unsloth/Qwen3-8B-Instruct-GGUF",
        "file": "Qwen3-8B-Instruct-Q4_K_M.gguf",
        "sha256": None,
        "params": "8B",
        "context_size": 40960,
        "ram_estimate_gb": 5.0,
        "quant_tier": "T2",
        "type": "dense",
        "hardware_targets": ["apu_renoir", "igpu_rdna2", "cpu_only"],
        "mtp_sibling": None,
        "swap_sla_tier": "gpu_fast",
        "recommended": False,
        "description": "Lightweight dense model for low-RAM scenarios",
    },
    {
        "id": "qwen3-4b",
        "llama_args": {
            "ctx_size": 32768,
            "n_gpu_layers": 12,
            "parallel": 4,
            "mlock": True,
            "jinja": True,
            "batch_size": 512,
            "ubatch_size": 256,
            "threads": 8,
            "threads_batch": 8,
        },
        "name": "Qwen3 4B Instruct 2507",
        "repo": "unsloth/Qwen3-4B-Instruct-2507-GGUF",
        "file": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "sha256": None,
        "params": "4B",
        "context_size": 262144,
        "ram_estimate_gb": 2.5,
        "quant_tier": "T2",
        "type": "dense",
        "hardware_targets": ["cpu_only", "apu_renoir"],
        "mtp_sibling": None,
        "swap_sla_tier": "gpu_fast",
        "recommended": False,
        "description": "Ultra-lightweight 4B for testing and fallback",
    },
    {
        "id": "phi4-mini",
        "llama_args": {
            "ctx_size": 32768,
            "n_gpu_layers": 12,
            "parallel": 4,
            "mlock": True,
            "batch_size": 512,
            "ubatch_size": 256,
            "threads": 8,
            "threads_batch": 8,
        },
        "name": "Phi-4 Mini Instruct",
        "repo": "unsloth/phi-4-mini-instruct-GGUF",
        "file": "phi-4-mini-instruct-Q4_K_M.gguf",
        "sha256": None,
        "params": "3.8B",
        "context_size": 131072,
        "ram_estimate_gb": 2.5,
        "quant_tier": "T2",
        "type": "dense",
        "hardware_targets": ["cpu_only", "apu_renoir"],
        "mtp_sibling": None,
        "swap_sla_tier": "gpu_fast",
        "recommended": False,
        "description": "Phi-4 Mini for fast iterative testing",
    },
    {
        "id": "gemma4-e4b",
        "llama_args": {
            "ctx_size": 16384,
            "n_gpu_layers": 12,
            "parallel": 2,
            "mlock": True,
            "batch_size": 512,
            "ubatch_size": 256,
            "threads": 8,
            "threads_batch": 8,
        },
        "name": "Gemma 4 E4B Instruct",
        "repo": "bartowski/google_gemma-4-E4B-it-GGUF",
        "file": "google_gemma-4-E4B-it-Q4_K_M.gguf",
        "sha256": None,
        "params": "4.5B active / 8B total",
        "context_size": 131072,
        "ram_estimate_gb": 5.2,
        "quant_tier": "T2",
        "type": "dense",
        "hardware_targets": ["apu_renoir", "cpu_only"],
        "mtp_sibling": None,
        "swap_sla_tier": "gpu_fast",
        "recommended": False,
        "description": "Gemma 4 E4B for alternative benchmarking",
    },
]


def _default_entry(base: Dict[str, Any]) -> Dict[str, Any]:
    """Return a fully-populated registry entry with runtime fields."""
    now = time.time()
    return {
        **base,
        "state": ModelState.AVAILABLE.value,
        "version": 1,
        "local_path": None,
        "staged_path": None,
        "download_bytes": 0,
        "download_total": 0,
        "download_progress": 0.0,
        "error": None,
        "swap_started_at": None,
        "swap_finished_at": None,
        "swap_duration_s": None,
        "promoted_at": None,
        "created_at": now,
        "updated_at": now,
        "audit_log": [],
    }


def _reconcile_disk_state(models: Dict[str, Dict[str, Any]]) -> None:
    """Promote registry entries whose files already exist on disk.

    Called during first load when no persisted registry exists.
    - available + file on disk → verified (local_path set)
    - matches active.gguf symlink target → active (promoted_at set)
    Entries already in a non-available state are left unchanged.
    """
    try:
        active_target: Optional[str] = None
        active_sym = MODEL_DIR / "active.gguf"
        if active_sym.is_symlink():
            active_target = str(active_sym.resolve())
    except Exception:
        active_target = None

    now = time.time()
    for entry in models.values():
        if entry.get("state") != ModelState.AVAILABLE.value:
            continue
        fname = entry.get("file")
        if not fname:
            continue
        candidate = MODEL_DIR / fname
        if not candidate.exists():
            continue
        local_path = str(candidate)
        entry["local_path"] = local_path
        entry["updated_at"] = now
        if active_target and local_path == active_target:
            entry["state"] = ModelState.ACTIVE.value
            entry["promoted_at"] = entry.get("promoted_at") or now
            entry["audit_log"].append({
                "ts": now, "event": "auto_discovered_active",
                "note": "file matched active.gguf symlink on startup"
            })
        else:
            entry["state"] = ModelState.VERIFIED.value
            entry["audit_log"].append({
                "ts": now, "event": "auto_discovered_verified",
                "note": "file found on disk during registry init"
            })



class ModelRegistry:
    """Thread-safe model catalog with durable JSON persistence."""

    def __init__(self, registry_path: Path = REGISTRY_PATH) -> None:
        self._path = registry_path
        self._lock = asyncio.Lock()
        self._models: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    # ── I/O helpers ──────────────────────────────────────────────────────────

    def _load_sync(self) -> None:
        """Synchronous load (call once at startup from async context via to_thread)."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                stored = {e["id"]: e for e in data.get("models", [])}
            except Exception as exc:
                logger.warning("model_registry: failed to load %s: %s — using builtin catalog", self._path, exc)
                stored = {}
        else:
            stored = {}

        # Merge builtin catalog; stored entries win on overlap for runtime fields,
        # but static metadata fields (llama_args, hardware_targets, etc.) are always
        # refreshed from the builtin catalog so new catalog additions take effect
        # without clearing the registry file.
        _STATIC_FIELDS = {"llama_args", "hardware_targets", "swap_sla_tier", "mtp_sibling",
                          "context_size", "ram_estimate_gb", "quant_tier", "type",
                          "recommended", "description", "params", "repo", "file"}
        merged: Dict[str, Dict[str, Any]] = {}
        for base in _BUILTIN_CATALOG:
            key = base["id"]
            if key in stored:
                entry = dict(stored[key])
                # Always refresh static metadata from builtin catalog
                for field in _STATIC_FIELDS:
                    if field in base:
                        entry[field] = base[field]
                merged[key] = entry
            else:
                merged[key] = _default_entry(base)

        # Carry over any stored entries not in builtin catalog.
        for key, entry in stored.items():
            if key not in merged:
                merged[key] = entry

        # Auto-discover existing files on disk and promote state accordingly.
        _reconcile_disk_state(merged)
        self._models = merged
        self._loaded = True

    def _save_sync(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": REGISTRY_VERSION,
            "updated_at": time.time(),
            "models": list(self._models.values()),
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.rename(self._path)

    # ── Async API ─────────────────────────────────────────────────────────────

    async def ensure_loaded(self) -> None:
        if not self._loaded:
            async with self._lock:
                if not self._loaded:
                    await asyncio.to_thread(self._load_sync)

    async def list_models(self) -> List[Dict[str, Any]]:
        await self.ensure_loaded()
        async with self._lock:
            return list(self._models.values())

    async def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        await self.ensure_loaded()
        async with self._lock:
            return self._models.get(model_id)

    async def get_active_model(self) -> Optional[Dict[str, Any]]:
        await self.ensure_loaded()
        async with self._lock:
            for entry in self._models.values():
                if entry.get("state") == ModelState.ACTIVE.value:
                    return entry
            return None

    async def transition(
        self,
        model_id: str,
        target_state: ModelState,
        update: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transition model to target_state with optional field updates."""
        await self.ensure_loaded()
        async with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                raise KeyError(f"Model {model_id!r} not found in registry")

            current = ModelState(entry["state"])
            if not current.can_transition_to(target_state):
                raise ValueError(
                    f"Invalid transition {current.value} → {target_state.value} for {model_id}"
                )

            now = time.time()
            entry["state"] = target_state.value
            entry["updated_at"] = now
            if error is not None:
                entry["error"] = error
            elif target_state != ModelState.FAILED:
                entry["error"] = None
            if update:
                for k, v in update.items():
                    entry[k] = v

            # Append to audit_log (cap at 50 entries)
            audit_entry = {
                "ts": now,
                "from": current.value,
                "to": target_state.value,
            }
            if error:
                audit_entry["error"] = error[:200]
            entry.setdefault("audit_log", []).append(audit_entry)
            if len(entry["audit_log"]) > 50:
                entry["audit_log"] = entry["audit_log"][-50:]

            await asyncio.to_thread(self._save_sync)
            return dict(entry)

    async def update_fields(self, model_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Update arbitrary fields without state transition (for progress updates)."""
        await self.ensure_loaded()
        async with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                raise KeyError(f"Model {model_id!r} not found")
            entry.update(fields)
            entry["updated_at"] = time.time()
            # Don't persist on every progress tick — caller can persist when done.
            return dict(entry)

    async def upsert(self, model_id: str, base: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new model entry or replace an existing one."""
        await self.ensure_loaded()
        async with self._lock:
            if model_id not in self._models:
                self._models[model_id] = _default_entry({**base, "id": model_id})
            else:
                self._models[model_id].update(base)
                self._models[model_id]["updated_at"] = time.time()
            await asyncio.to_thread(self._save_sync)
            return dict(self._models[model_id])

    async def save(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._save_sync)


# Module-level singleton
_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
