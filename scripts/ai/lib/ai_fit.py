#!/usr/bin/env python3
"""Deterministic AI-fit evaluator for the AQ-OS installer golden path.

Maps a versioned hardware-evidence summary (scripts/ai/lib/hw_probe.py output,
schema_version 2) + the digest-pinned AI-fit policy catalog
(config/aqos-ai-fit-policy-catalog-v1.json) to an honest recommended / limited /
not_advised verdict, an eligible-model list, the selected acceleration backend,
and explicit reserves, offload caps, context caps, and downgrade reasons.

Contract (PRD v2 section 92):
- The catalog carries measured DATA only; the verdict LOGIC lives here.
- Unknown VRAM or insufficient evidence resolves conservatively and can NEVER
  authorize unsafe full offload.
- CPU-only operation is an honest `limited` path, never `recommended`.
- The catalog's exact file bytes are hashed (sha256); that digest is what a
  resolved install-plan lock binds as catalog_digests.ai_fit_policy_catalog_sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CATALOG_PATH = Path("config/aqos-ai-fit-policy-catalog-v1.json")
GIB = 1024**3

# PCI vendor IDs (lowercase, 0x-prefixed, matching hw_probe evidence).
VENDOR_NVIDIA = "0x10de"
VENDOR_AMD = "0x1002"
VENDOR_INTEL = "0x8086"


def load_catalog(path: Path | str = CATALOG_PATH) -> tuple[dict[str, Any], str]:
    """Return (catalog, sha256-of-exact-file-bytes). The digest is the binding value."""
    raw = Path(path).read_bytes()
    catalog = json.loads(raw)
    return catalog, hashlib.sha256(raw).hexdigest()


def _extract_evidence(hw: dict[str, Any] | None) -> dict[str, Any]:
    """Pull the fields the policy needs from a hw_probe result, tolerant of gaps."""
    hw = hw or {}
    ram = hw.get("ram") or {}
    gpu = hw.get("gpu") or {}
    primary = gpu.get("primary") or {}
    return {
        "input_schema_version": hw.get("schema_version"),
        "ram_total_bytes": ram.get("total_bytes"),
        "gpu_present": bool(gpu.get("present")),
        "gpu_outcome": gpu.get("outcome"),
        "gpu_count": len(gpu.get("devices") or []),
        "memory_type": primary.get("memory_type"),
        "vendor_id": (primary.get("vendor_id") or "").lower() or None,
        "vram_total_bytes": primary.get("vram_total_bytes"),
    }


def _evidence_status(ev: dict[str, Any]) -> str:
    if ev["ram_total_bytes"] is None:
        return "unknown"
    if ev["gpu_outcome"] == "insufficient_evidence":
        return "insufficient_evidence"
    return "sufficient"


def _select_backend(ev: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    """Pick only a stable, auto-selectable, vendor-eligible catalog backend."""
    backends = catalog.get("backends", {})

    def eligible(backend_id: str) -> bool:
        backend = backends.get(backend_id) or {}
        vendor_ids = backend.get("vendor_ids") or []
        if not backend.get("stable") or not backend.get("auto_select"):
            return False
        if vendor_ids and ev["vendor_id"] not in vendor_ids:
            return False
        if backend.get("requires_discrete_vram"):
            return ev["memory_type"] == "dedicated" and bool(ev["vram_total_bytes"])
        return True

    def selected(backend_id: str) -> dict[str, Any]:
        backend = backends[backend_id]
        return {
            "id": backend_id,
            "offload": backend["offload"],
            "gpu_layer_cap": backend.get("apu_gpu_layer_cap"),
            "reason": f"{backend_id} is the highest-priority eligible catalog backend",
        }

    cpu = {"id": "cpu", "offload": "none", "gpu_layer_cap": 0,
           "reason": "no stable auto-selectable catalog backend is eligible -> CPU-only"}

    # No usable GPU evidence -> CPU-only.
    if not ev["gpu_present"] or ev["gpu_outcome"] != "detected":
        cpu["reason"] = "no GPU detected (or GPU evidence insufficient) -> CPU-only"
        return cpu

    # Full-offload backends are preferred, then bounded partial offload. The
    # explicit order is policy-engine behavior; every eligibility fact remains
    # catalog-owned and is checked above.
    for backend_id in ("cuda", "rocm", "vulkan"):
        if eligible(backend_id):
            return selected(backend_id)
    return cpu


def _model_offload(model: dict[str, Any], backend: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any]:
    """Per-model offload decision; unknown capacity always fails closed."""
    if backend["offload"] == "none":
        return {"offload": "none", "gpu_layer_cap": 0, "downgrade_reason": "cpu-only (no GPU offload)"}
    vram = ev["vram_total_bytes"]
    need = model.get("vram_required_bytes") or 0
    if backend["offload"] == "full":
        if not need:
            return {"offload": "none", "gpu_layer_cap": 0,
                    "downgrade_reason": "model VRAM requirement unknown -> CPU-only, no full offload"}
        if not vram or vram < need:
            return {"offload": "none", "gpu_layer_cap": 0,
                    "downgrade_reason": f"VRAM {vram} cannot prove model requirement {need} -> CPU-only"}
        return {"offload": "full", "gpu_layer_cap": None, "downgrade_reason": None}
    # partial
    return {"offload": "partial", "gpu_layer_cap": backend.get("gpu_layer_cap"),
            "downgrade_reason": "capped partial offload"}


def _fit_one(model: dict[str, Any], available_ram: int, headroom_margin: int,
             backend: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any]:
    need = model.get("ram_required_bytes") or 0
    off = _model_offload(model, backend, ev)
    if need > available_ram:
        return {
            "model_id": model["id"], "params_b": model.get("params_b"),
            "fit": "not_advised", "ram_required_bytes": need,
            "ram_headroom_bytes": available_ram - need, "context_cap": model.get("context_max"),
            "offload": off["offload"], "gpu_layer_cap": off["gpu_layer_cap"],
            "downgrade_reason": f"insufficient RAM: needs {need}, {available_ram} available after reserves",
        }
    headroom = available_ram - need
    fit = "recommended" if headroom >= headroom_margin else "limited"
    reason = off["downgrade_reason"]
    if fit == "limited" and not reason:
        reason = "fits but RAM headroom below recommended margin"
    return {
        "model_id": model["id"], "params_b": model.get("params_b"),
        "fit": fit, "ram_required_bytes": need,
        "ram_headroom_bytes": headroom, "context_cap": model.get("context_max"),
        "offload": off["offload"], "gpu_layer_cap": off["gpu_layer_cap"],
        "downgrade_reason": reason,
    }


def evaluate_fit(hw: dict[str, Any] | None, catalog: dict[str, Any],
                 catalog_sha256: str | None = None) -> dict[str, Any]:
    """Deterministic verdict from hardware evidence + the pinned catalog."""
    ev = _extract_evidence(hw)
    status = _evidence_status(ev)
    reserves = catalog.get("reserves", {})
    os_reserve = reserves.get("os_reserve_bytes", 0)
    kv_floor = reserves.get("kv_cache_floor_bytes", 0)
    headroom_margin = reserves.get("recommended_headroom_bytes", 0)

    out: dict[str, Any] = {
        "catalog_version": catalog.get("catalog_version"),
        "policy_version": catalog.get("policy_version"),
        "ai_fit_policy_catalog_sha256": catalog_sha256,
        "input_schema_version": ev["input_schema_version"],
        "evidence_status": status,
        "gpu_count": ev["gpu_count"],
        "os_reserve_bytes": os_reserve,
        "kv_cache_reserved_bytes": kv_floor,
    }

    # RAM unknown -> cannot size anything honestly.
    if status == "unknown":
        out.update({
            "verdict": "not_advised",
            "reason": "insufficient hardware evidence: total RAM unknown",
            "usable_ram_bytes": None,
            "backend": {"id": "cpu", "offload": "none", "gpu_layer_cap": 0,
                        "reason": "RAM unknown -> conservative CPU-only"},
            "eligible_models": [],
            "recommended_model": None,
            "downgrade_reasons": ["ram-unknown"],
        })
        return out

    total_ram = ev["ram_total_bytes"]
    available_ram = max(0, total_ram - os_reserve - kv_floor)
    backend = _select_backend(ev, catalog)

    models = sorted(catalog.get("models", []), key=lambda m: (m.get("params_b") or 0, m.get("id")))
    evaluated = [_fit_one(m, available_ram, headroom_margin, backend, ev) for m in models]

    downgrades: list[str] = []
    if status == "insufficient_evidence":
        downgrades.append("gpu-evidence-insufficient")
    if backend["offload"] == "none":
        downgrades.append("cpu-only")
    elif backend["offload"] == "partial":
        downgrades.append("partial-offload")

    fitting = [m for m in evaluated if m["fit"] in ("recommended", "limited")]
    has_gpu_offload = backend["offload"] in ("partial", "full")
    any_recommended = any(m["fit"] == "recommended" for m in evaluated)

    if not fitting:
        smallest = models[0]["ram_required_bytes"] if models else None
        verdict = "not_advised"
        reason = (f"even the smallest catalog model needs {smallest} bytes RAM; "
                  f"only {available_ram} available after reserves")
        recommended_model = None
        downgrades.append("ram-too-small")
    elif has_gpu_offload and any_recommended:
        verdict = "recommended"
        reason = "a catalog model fits with recommended headroom and GPU offload is available"
        recommended_model = max((m for m in fitting if m["fit"] == "recommended"),
                                key=lambda m: (m["params_b"] or 0))["model_id"]
    else:
        verdict = "limited"
        if not has_gpu_offload:
            reason = "CPU-only honest path: a model fits in RAM but no GPU offload is available"
        else:
            reason = "GPU offload available but every fitting model is RAM-tight"
        recommended_model = max(fitting, key=lambda m: (m["params_b"] or 0))["model_id"]

    out.update({
        "verdict": verdict,
        "reason": reason,
        "usable_ram_bytes": available_ram,
        "backend": backend,
        "eligible_models": evaluated,
        "recommended_model": recommended_model,
        "downgrade_reasons": sorted(set(downgrades)),
    })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate AI-fit from a hardware profile + pinned catalog.")
    parser.add_argument("--hardware", type=Path, default=None,
                        help="path to a hw_probe JSON profile; omit to probe live hardware")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH,
                        help=f"path to the AI-fit policy catalog (default {CATALOG_PATH})")
    parser.add_argument("--digest", action="store_true", help="print only the catalog sha256 and exit")
    args = parser.parse_args(argv)

    catalog, digest = load_catalog(args.catalog)
    if args.digest:
        print(digest)
        return 0

    if args.hardware is not None:
        hw = json.loads(args.hardware.read_text())
    else:
        # Import lazily so --digest / --hardware paths do not require the probe.
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "hw_probe", Path(__file__).with_name("hw_probe.py"))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        hw = mod.probe_hardware()

    print(json.dumps(evaluate_fit(hw, catalog, digest), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
