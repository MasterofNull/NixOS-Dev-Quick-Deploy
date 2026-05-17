# Phase 57 — Hardware Capability Matrix + ROCm Promotion Pipeline

## Summary

Establish a formal hardware capability model so GPU backend selection is
driven by evidence rather than GPU vendor alone.  ROCm transitions from a
deprecated flag to a gated promotion lane that is safe on validated hardware
and explicitly blocked on hardware where it causes instability.

## Problem

| Root cause | Effect |
|---|---|
| `acceleration = auto` mapped AMD → ROCm (was reverted) | GPU hangs, ErrorDeviceLost on Renoir APU |
| No hardware capability registry | No machine-readable reason for why a backend is safe or blocked |
| No promotion pipeline | ROCm vs Vulkan choice is ad-hoc; no evidence chain |
| No benchmark harness | Can't prove ROCm is faster before promoting it |
| No canary path | Backend changes affect all hosts simultaneously |

## Goals

1. **Hardware capability matrix** — SSOT JSON mapping hardware classes to
   backend eligibility (default / fallback / candidate), promotion status, and
   promotion criteria.
2. **ROCm promotion gate** — 6-stage script that must pass before any host
   promotes ROCm from `candidate` to `production`.
3. **Backend benchmark harness** — reproducible measurement of startup time,
   tokens/sec, memory, GPU reset events for each available backend.
4. **Nix wiring** — new `mySystem.hardware.accelerationClass` option + updated
   `ai-stack.nix` comments that reference the capability matrix as authority.
5. **aq-qa Phase 57** — 8 new checks covering the pipeline artifacts.

## Non-goals

- Automated backend promotion (manual review required before setting
  `promotion_status = "production"` in the matrix).
- ROCm compilation support (handled by `nix/lib/overlays/llama-cpp-latest.nix`
  + `nix/modules/hardware/gpu/amd.nix`).

---

## Agent Roles

| Role | Agent | Scope |
|---|---|---|
| Orchestrator / Reviewer | Claude (Sonnet 4.6) | Architecture decisions, acceptance gate, this PRD |
| Architecture / Risk | Gemini | Risk review of promotion pipeline design, compatibility matrix completeness |
| Implementer | Qwen (local, via aq-agent-loop) | Script bodies, benchmark runner details |
| Codebase fit | Codex | Confirm pattern conformance to existing scripts/governance/ conventions |

---

## Deliverables

### Phase A — Capability Matrix SSOT

**A.1** `config/hardware-capability-matrix.json`

Top-level sections:
- `hardware_classes` — keyed by class ID, each with `default_backend`,
  `fallback_backend`, `candidate_backend`, `promotion_status`,
  `promotion_blocked_reason` (if blocked), `rocm_compat_key`, `max_gpu_layers`,
  `detection_hints`.
- `rocm_compatibility_matrix` — keyed by GFX target (e.g. `gfx1030`), each
  with `family`, `supported_rocm_versions`, `promotion_eligible`, `notes`.
- `promotion_pipeline` — stage list and valid status transitions.
- `backend_definitions` — canonical backend IDs, descriptions, fallback chain.

**A.2** Update `config/ai-stack-hardware-profiles.json`

- Remove `"status": "deprecated"` from ROCm entry.
- Add `"promotion_gated": true` and reference to capability matrix.

**A.3** `mySystem.hardware.accelerationClass` option in `options.nix`

Type: `nullOr str`, default: `null`.
Written by `discover-system-facts.sh` when class can be determined;
override-able per host.

### Phase B — Promotion Gate + Benchmark

**B.1** `scripts/governance/rocm-promotion-gate.sh`

Six stages run in sequence; any failure exits non-zero with a structured
reason:

| Stage | Name | Pass criterion |
|---|---|---|
| 1 | hardware_identify | Class found in capability matrix AND `promotion_eligible: true` in ROCm compat matrix |
| 2 | compatibility_check | `rocm_compat_key` maps to a non-blocked entry |
| 3 | cold_start | llama.cpp starts with `--n-gpu-layers 99` and reaches `/health` within 120 s, 3 consecutive runs |
| 4 | hang_check | No `amdgpu` GPU reset / ErrorDeviceLost in journal since cold_start |
| 5 | benchmark | ROCm tokens/sec ≥ Vulkan tokens/sec × (1 + threshold%) |
| 6 | soak | Promotion state file records ≥ soak_hours of clean operation |

Outputs: `config/rocm-promotion-state.json` (per-host, gitignored) recording
stage results and timestamps.

**B.2** `scripts/testing/benchmark-acceleration-backends.sh`

- Accepts `--backends vulkan,rocm,cpu` (defaults to auto-detected available).
- For each backend: starts a temporary llama-server subprocess, runs a fixed
  3-shot prompt set, measures startup time, tok/s, peak RSS, GPU reset count.
- Outputs `config/backend-benchmark-results.json`.
- Designed to be invoked by Stage 5 of the promotion gate.

### Phase C — Nix Wiring

**C.1** `options.nix` — add `mySystem.hardware.accelerationClass`

**C.2** `ai-stack.nix` — update the `resolvedAccel` comment block to reference
the capability matrix as the authoritative source; remove the word "deprecated"
from the ROCm description (it is now promotion-gated, not deprecated).

**C.3** `discover-system-facts.sh` — add `detect_acceleration_class()`

Maps (gpu_vendor, igpu_vendor, is_mobile, nixosHardwareModule, rocm_gpu_target)
→ a hardware class ID from the capability matrix.  Writes
`hardware.accelerationClass` into the generated facts.nix.

### Phase D — aq-qa Phase 57

Eight checks:

| ID | Layer | Description |
|---|---|---|
| 1.3.1 | 7 | capability matrix file present and valid JSON |
| 1.3.2 | 7 | all required top-level keys present in matrix |
| 1.3.3 | 7 | promotion-gate script present and executable |
| 1.3.4 | 7 | benchmark harness present and executable |
| 1.3.5 | 7 | current host class recognized in capability matrix |
| 1.3.6 | 7 | current host promotion_status is not unknown |
| 1.3.7 | 7 | ai-stack-hardware-profiles.json ROCm entry is promotion-gated |
| 1.3.8 | 7 | promotion pipeline stages list has ≥ 6 entries |

---

## Acceptance Criteria

- [ ] `config/hardware-capability-matrix.json` validates against its own
  `$schema` via `jq`.
- [ ] `rocm-promotion-gate.sh --dry-run` exits 0 on this host (blocked path
  is explicitly documented, not an error).
- [ ] `benchmark-acceleration-backends.sh --backends vulkan` completes and
  writes valid JSON.
- [ ] `nix flake check --no-build` passes after options.nix / ai-stack.nix
  changes.
- [ ] `scripts/governance/tier0-validation-gate.sh --pre-commit` passes.
- [ ] `aq-qa 57` reports 8/8 PASS.

---

## Risk Register

| Risk | Mitigation |
|---|---|
| Renoir ROCm hang re-introduced | `promotion_status: "blocked"` in matrix; gate Stage 1 rejects it |
| Benchmark variance makes Stage 5 flaky | Configurable threshold + 3-run median |
| facts.nix accelerationClass adds new required field | Option is `nullOr str` with `null` default — no rebuild required for existing hosts |
| ROCm compat matrix becomes stale | Versioned with `last_verified` timestamp per entry; aq-qa check 1.3.2 validates structure |
