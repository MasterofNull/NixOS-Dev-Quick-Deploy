# AQ-OS Horizon Map — Unknown Unknowns for a Local-First Edge AI OS

**Date**: 2026-07-09 · **Author**: claude-fable-5 · **Status**: input to round `aqos-v1` (lanes: weigh these when scoring/amending the PRD)
**Question answered**: what has NOT been developed, researched, or considered for a harness/OS that excels on any reasonable hardware — embedded through servers — and how do we systematically expose remaining blind spots?

The PRD (WS1-WS10) professionalizes what exists. This document maps what does not exist yet. Organized by dimension; each item notes current state (NONE / STUB / PARTIAL) and the workstream it would extend.

---

## A. Hardware-portability dimension (the biggest structural gap)

The harness today is **hand-carved to one machine** (Renoir APU constants: gpu-layers 12, LOCAL_TOK_PER_SEC, 27GB budgets). Nothing generalizes it.

| # | Capability | State | Note |
|---|-----------|-------|------|
| A1 | **Hardware Abstraction & Capability Probe** — detect RAM/VRAM/NPU/iGPU/AVX-NEON/thermal envelope/battery at install; auto-derive model choice, quant, ctx size, token budgets, timeouts. The Renoir constants become one *generated* profile, not the codebase's physics. | STUB (`ai-stack-hardware-profiles.json` is static) | new WS-EDGE, feeds WS1 contracts |
| A2 | **Model portfolio ladder per hardware class** — embedded 0.5-4B / laptop 7-14B / desktop 30B+ / server 70B+-MoE, with a quantization ladder (Q2→Q8) and LoRA-adapter swapping instead of full-model swaps on small devices | NONE (single Qwen3-35B) | extends WS8 |
| A3 | **Alternative runtimes beyond llama.cpp** — NPU/accelerator paths: OpenVINO, QNN, CoreML, Vulkan backend, ExecuTorch/MLC for phones+embedded. Runtime becomes a leased capability, not an assumption | NONE | extends WS3 capability model |
| A4 | **Speculative decoding / draft models** — small resident model drafts for the big model; biggest single tok/s win available on weak hardware | NONE (SMALL_RESIDENT tier exists on paper in model_tier.py) | extends F2.5 just wired |
| A5 | **Power & thermal aware scheduling** — battery-state bands, thermal-throttle detection feeding backpressure, duty-cycling on embedded; **energy-per-token** as a first-class metric next to tok/s | NONE | extends WS5 metrics + slot_queue |
| A6 | **Storage tiering & model residency** — mmap strategy, model eviction/warm-up policy, disk-budget contracts for 32GB-eMMC-class devices | NONE | extends WS7 |
| A7 | **Heterogeneous fleet as one harness** — laptop+desktop+Pi federate: mDNS discovery, capability gossip, job placement by measured envelope (the multi-node path in WS2/WS3, made concrete) | STUB (`federation_protocol.py`, `federated_integration.py` unwired) | extends WS2/WS3 |

## B. Systems/OS dimension

| # | Capability | State | Note |
|---|-----------|-------|------|
| B1 | **Offline-first formalized** — declared degraded modes when remote lanes vanish; sync/reconcile on reconnect; **CRDT merge for memory/state across devices** (two devices learning independently must merge without clobber — today even two agents on one host clobber RESUME.json) | PARTIAL (local-only works; no reconcile) | extends WS2 |
| B2 | **Latency classes & ambient compute** — interactive voice/UI needs <500ms first token → a small model always resident (never evicted); wake-word patterns; the P1 band gets a real-time contract, not just priority | NONE | extends F2.5/WS3 |
| B3 | **OTA/update story for edge** — Nix generations + flake pinning IS an A/B-partition OTA story better than most commercial edge stacks — but it's never been packaged/documented as one; non-NixOS targets need a plan (nix-portable? OCI?) | PARTIAL (NixOS-only, undocumented as a feature) | extends WS10 |
| B4 | **Portable sandboxing** — AppArmor profiles assume NixOS; embedded/other-distro targets need an alternative. **WASM component model for skills/plugins** (portable, capability-scoped, language-agnostic) is the strategic bet worth researching | NONE | extends WS3/WS9 |
| B5 | **Crash-safety on power-loss** — SQLite-WAL/fsync discipline for every state file; today's json-file writes (even with os.replace) have never been power-loss tested; embedded devices lose power routinely | NONE | extends WS7 |

## C. AI/UX dimension

| # | Capability | State | Note |
|---|-----------|-------|------|
| C1 | **Multimodal edge loop** — whisper.cpp STT + local TTS + camera/vision (LLaVA-class) + sensor ingestion; a voice-first local assistant is the killer edge app and it's 100% absent | NONE | new WS |
| C2 | **Personal data vault & privacy boundary** — ingest email/files/browser/calendar with on-device embeddings; formal egress ledger (every byte leaving the device is logged and attributable); PII redaction before any remote lane; a *written privacy contract* is what makes "local-first" a claim instead of a vibe | NONE | extends WS7/WS9 |
| C3 | **Personal adapters / continual learning** — per-user LoRA trained on-device from the closed loop; federated aggregation across own devices without raw-data movement | NONE (closed loop trains base behaviors, not personalization) | extends WS8 |
| C4 | **Non-expert operator UX** — recovery-from-bad-state by someone who cannot read a traceback; guided setup; accessibility. Today's operator IS the developer; an OS has users | NONE | extends WS6 |

## D. Reliability & economics

| # | Capability | State | Note |
|---|-----------|-------|------|
| D1 | **Failure taxonomy + fault injection on edge** — OOM, thermal, disk-full, power-loss mid-write, clock skew; chaos suite exists for services but not for edge physics | PARTIAL (`tests/chaos-engineering/`) | extends WS10 |
| D2 | **Local-vs-remote economics engine** — cost/energy/latency/quality per task class, measured, driving the router; plus the ROI dashboard that proves the local-first thesis with numbers | PARTIAL (routing_policy has static costs) | extends WS5 |
| D3 | **Benchmark suite as a product artifact** — standardized per-hardware-class benchmark (TTFT, tok/s, RAG recall, task success, energy) so any adopter knows what their device will do before installing; doubles as marketing | STUB (`aq-inference-bench` plan exists) | extends WS8 |

## E. Ecosystem & product

| # | Capability | State | Note |
|---|-----------|-------|------|
| E1 | **Protocol-native interop** — MCP served AND consumed everywhere; OpenAI-compat surface (exists in switchboard); **Google A2A / open agent-interchange protocols**; an OS wins by being the best citizen, not a silo | PARTIAL (MCP yes; A2A protocol no) | extends WS2 |
| E2 | **Capability marketplace + trust model** — signed third-party skills/plugins with the intake gate as the trust root | STUB (`agent_marketplace.py`, sign-skill-registry) | extends WS3/WS9 |
| E3 | **Model supply-chain security** — GGUF provenance/hash pinning, malicious-model detection (tokenizer attacks, embedded jailbreak weights); nobody in the local-AI space does this well — differentiator | NONE | extends WS9 |
| E4 | **Compliance & licensing posture** — model license terms for redistribution (Qwen etc.), EU AI Act edge implications, telemetry opt-in policy | NONE | extends WS10 |
| E5 | **Community/distribution strategy** — what is open, what is the product, who contributes; flake as the install channel | NONE | product decision |

## F. Security unknowns specific to local models

- **F1 Injection blast radius**: weaker local models follow injected instructions more readily than frontier models — the tool sandbox and egress ledger must assume the model IS compromised (zero-trust extends to the model itself). Extends WS9.
- **F2 Physical attack surface** on embedded: UART/debug ports, evil-maid, model extraction from disk (at-rest encryption for adapters/memory). NONE.

---

## How to expose blind spots systematically (the meta-answer)

Blind spots persist because every review shares the builder's frame. Break the frame seven ways, institutionalized as recurring harness workflows — each maps to an existing mechanism, so these are wiring tasks, not inventions:

1. **Adversarial premortem round** (quarterly, aq-collab-round): every lane answers "It is 2027 and AQ-OS failed/was breached/was abandoned — write the post-mortem." Failure narratives surface assumptions no forward-looking review finds.
2. **Comparative teardown program** (autoresearch loop): systematically diff capability lists against adjacent systems — Home Assistant (the most successful local-first OS analog: study its config/UX/community model), k3s/fleet (edge orchestration), Ollama/LM Studio (DX bar), Tailscale (mesh identity), ExecuTorch/MLC (embedded inference), smolagents/LangGraph (agent runtimes). Every capability they have and we lack is a decision, not an accident — make each one explicit accept/reject.
3. **Standards scan** (scheduled): MCP, A2A, OpenTelemetry, WASI/component-model, SLSA, C2PA — a standard the harness can't speak is a blind spot with a deadline attached.
4. **Persona-simulation rounds**: agents role-play adopter personas (Pi hobbyist, privacy journalist, SMB sysadmin, robotics lab) attempting install→first-value using only the docs; their friction logs become requirements. Cheap with existing fan-out infra.
5. **Metric inversion audit**: for every dashboard metric ask "what failure is invisible to this?" (success-rate hides quality drift → need eval-drift detection; uptime hides silent staleness → need freshness probes). Formalize as a WS5 review gate.
6. **Hardware matrix CI**: qemu-ARM emulation + a small physical farm (a Pi, an old laptop, a phone) exercising the benchmark suite per release — portability claims validated by machines, not intentions.
7. **External red-team + user contact**: eventually, eyes that never saw the code. Until then, the T3MP3ST/security-audit skills run against the harness itself on a schedule.

**Sequencing recommendation**: A1 (hardware probe) is the keystone — every other edge item depends on knowing the device. C2 (privacy boundary/egress ledger) is the identity-defining feature: it converts "local-first" from architecture into product promise. B4 (WASM skills) is the highest-leverage research bet. D2 (economics engine) proves the thesis. Propose these four as WS-EDGE Phase 1 in the ratified plan.
