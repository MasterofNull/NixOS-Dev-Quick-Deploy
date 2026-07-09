# Slice E1 — Hardware Capability Probe (WS-EDGE Phase 1 keystone)

**From**: claude-fable-5 (orchestrator) · **Assigned lane**: codex · **Date**: 2026-07-09
**Context**: `.agents/plans/aqos-v1/HORIZON-UNKNOWNS.md` §A1 — the harness is hand-carved to one machine (Renoir constants). This probe makes hardware a *generated* profile.

## Deliverables (bounded — exactly these files)
1. `scripts/ai/lib/hw_probe.py` — pure-stdlib module + CLI:
   - Detect: CPU model/cores/threads + ISA flags (avx2/avx512/neon from /proc/cpuinfo), total/available RAM (/proc/meminfo), GPU + VRAM (/sys/class/drm + lspci fallback; AMD APU UMA case: report shared), NPU hints (lspci patterns), thermal zones present (/sys/class/thermal), battery present (/sys/class/power_supply), free disk at repo root, OS/kernel.
   - Derive: `hardware_class` (embedded <4GB / laptop <16GB / desktop <64GB / server >=64GB usable RAM), `model_size_class` (max local model B-params + suggested quant ladder step), `suggested_n_gpu_layers` (0 when no GPU; conservative UMA heuristic otherwise), `suggested_ctx_size`, `suggested_max_tokens`, `tok_per_sec_estimate: null` (measured later by bench, never guessed).
   - Every detection degrades gracefully: missing source → field null + entry in `"undetected": [...]`. No exceptions escape.
   - CLI: `python3 hw_probe.py` prints JSON; `--write` saves to `config/hardware-profile.generated.json` (never overwrites a hand-authored file without `--force`).
2. `scripts/testing/test-hw-probe.py` — asserts: runs cleanly on this host, required keys present, degradation path (probe with a bogus /proc root via parameter → nulls not crashes), derivation boundaries (4/16/64GB class edges).

## Rules
- PRD gate: append one plan line to `.agent/collaboration/PULSE.log` before editing.
- Do NOT commit — orchestrator reviews and commits (activation gate applies).
- Do NOT modify existing files except adding nothing — this slice is purely additive.
- No hardcoded ports/paths beyond the /proc//sys sources being probed.
- Validate: `python3 -m py_compile` + run the test file; paste results at the end of your output.

## Acceptance
Probe JSON on this host must correctly report: Renoir APU (shared VRAM), ~27-31GB RAM, desktop class, and suggest n_gpu_layers ≤ 12 territory via the UMA heuristic. The existing constants in `.agent/INFRASTRUCTURE-CONSTRAINTS.md` are the ground truth to sanity-check against.
