# AQ-OS Installer & Quick-Deploy Experience — CONSOLIDATED PRD

Status: CONSOLIDATED v2 FROZEN (folds claude + codex drafts, the freshness-verified Antigravity review, an adjudicated local-model inventory, and independent Codex review; owner golden-path direction 2026-08-31).
Authors/sources: claude-opus-4.8 (product/architecture framing), codex-cli (engineering constraints, config contract, parity design), Antigravity (independent design review, verified and selectively adopted), local Qwen (bounded inventory suggestions, source-checked and selectively adopted). Exemplar: omarchy (opinionated, curated, "OS for the age of agents").
Source drafts: `AQOS-INSTALLER-EXPERIENCE-PRD-claude.md`, `AQOS-INSTALLER-EXPERIENCE-PRD-codex.md`.

---

## 1. Decision summary (owner-steered 2026-08-31)

Ship **ONE golden path**: a super-tuned, hardware-adaptive setup for **professional development + gaming + (optional) local AI**. It is opinionated and ready-to-go (omarchy-style), NOT an infinite pick-and-choose menu. The proven **modular `mySystem.*` engine stays underneath** for experts, but the golden path is the blessed default.

Three reconciled decisions that shape everything below:
- **Golden path first.** Most users pick the golden path and go. Fewer decisions, expertly tuned. Modularity remains available, not mandatory.
- **Local AI is OPTIONAL and hardware-tuned.** A prominent yes/no. If yes, the AI stack (model + settings) is selected to fit the *detected hardware* (RAM/GPU/CPU) — automating the exact tuning we do by hand (resident model, GPU layers, RAM budget). If the hardware can't run it well, the installer says so honestly.
- **The install itself is DETERMINISTIC — no running AI required.** A fresh/wiped machine has no local model yet (codex correction #4), so AI is never on the install critical path. AI is an *optional untrusted proposal adapter* that, post-install, becomes the ongoing "vibe your way through" assistant.

## 2. Current state (source-backed; codex findings)

- **Active engine = the monolithic `nixos-quick-deploy.sh` (~4755 lines).** The `phases/phase-*.sh` directory is legacy inventory, NOT the active executor. Any PRD claim about "the phase engine" must target the real active path.
- **Useful declarative layers exist:** `nix/modules/profiles/` (ai-dev, gaming, minimal = template-like bundles), `roles/` (composable features via `mySystem.roles.*`), `host-classes/`, `hardware/{cpu,gpu}`, and `mySystem.*` options (`core/options.nix`).
- **The input surface is NOT yet a contract:** flags + env vars with implicit, front-end-duplicated defaults. No normalized plan, no single resolver. This is the central thing to fix.
- **Disk provisioning is not beginner-safe today** and disk erasure is NOT reversible via NixOS generations.

## 3. Goals / Non-goals

**Goals**
1. One recommended **golden path**, plain-language, from bare machine to a working, tuned pro-dev/gaming(/AI) workstation with no NixOS knowledge required.
2. **Nothing lost for experts** — all current flags + direct-Nix workflows preserved during and after migration.
3. **Guided, AI, and manual inputs converge on ONE normalized contract** (provable one-engine).
4. **Hardware-adaptive tuning** — detect specs; tune the golden path (and, if enabled, the AI model/settings) to the machine.
5. **Local-only AI, optional, off the install critical path** — full install works offline with no model/coordinator/network/account.
6. **Safe & honest** — fail closed on unknown fields, conflicts, unsafe devices, stale plans, drift; show the exact planned mutations before authorization; durable progress + recovery receipts.

**Non-goals for P1**
- no disk repartition/format/bare-metal install (deferred to a hardened later phase with a resumable mutation journal);
- no AI-generated arbitrary Nix; no dependence on a running model/coordinator/network/account during install;
- no new profile names, DE, theme gallery, or ISO yet; no removal of legacy flags or direct host-Nix customization;
- no automatic rollback of destructive storage operations (backups/recovery media ≠ rollback).

## 4. The Golden Path (the primary experience)

A single blessed path: **"AQ-OS Workstation"** — tuned for professional dev + gaming, with the **local AI stack as an optional, hardware-fit add-on**. Built as a curated `mySystem.*` selection (a new golden profile), it is:
- **Opinionated + ready** — sane, tested defaults for dev toolchains, GPU/gaming, desktop, monitoring; the user accepts and goes, or tweaks a few clearly-surfaced knobs.
- **Hardware-adaptive** — a deterministic hardware detector produces a redacted capability summary; the resolver tunes the plan to it (CPU/GPU/RAM; and IF AI enabled: which model, GPU layers, RAM budget, whether AI is even advisable on this box).
- **AI = one honest choice** — "Include the local AI assistant? (needs ≥ X GB RAM / a capable GPU; on this machine: recommended/limited/not advised)." If enabled, installed + tuned; if not, a clean pro-dev/gaming system.
- **Reproducible** — the chosen system is a resolved-plan lock (below); saveable, shareable, re-appliable.

The golden path is itself a resolved plan over the modular engine — experts can start from it and compose further; beginners never see the composition.

## 5. Canonical configuration contract (codex; the SSOT that makes it one engine)

SSOT is a PAIR:
- `config/schemas/aqos-install-plan-v1.schema.json` — Draft 2020-12, `additionalProperties:false` at every boundary;
- a single **resolver/compiler** command — validates input, applies defaults + cross-field invariants, emits canonical JSON, and produces the executor + Nix projections. Front ends MUST NOT re-implement defaults or map choices straight to shell vars.

The resolved lock is serialized with **RFC 8785 (JCS)**. Its semantic digest is over those exact canonical UTF-8 bytes, not a language-specific "sorted keys" approximation. The lock binds at least `schema_version`, a versioned hardware summary, a digest-pinned policy/model catalog, and a closed `source_identity`. For P0, `source_identity` means the full immutable Git commit object ID, its exact tree object ID, a required-clean-worktree assertion, `flake_lock_sha256` (SHA-256 of the exact `flake.lock` bytes), the Nix `system` value, and the exact flake installable/host target. Branch and tag names are provenance only and never authority. The resolver and executor independently verify every bound value and fail closed before projection or execution when the checkout is dirty, an object is missing, the checked-out tree/lock differs, the target is unavailable, or any source fact cannot be verified. Non-Git source bundles are unsupported in v1 rather than weakly identified. Provenance stays in a sidecar and cannot change semantic bytes or hashes.

Three distinct artifacts:
- **request plan** — user/AI-supplied values, defaultable fields may be omitted;
- **resolved plan lock** — all defaults explicit, canonical, immutable, **secret-free**;
- **execution authorization receipt** — short-lived approval bound to the resolved-plan hash + current hardware identity; never part of reusable config.

Everything (golden-path choices, hardware tuning, AI proposals, expert flags) targets the `mySystem.*` field set through this contract.

## 6. Parity guarantee (codex; 4 layers)

"One engine" is proven, not asserted:
1. **Adapter parity** — guided answers, AI JSON, manual manifest, and equivalent legacy flags produce **byte-identical RFC 8785 canonical resolved-plan JSON** (explicit defaults, no timestamps/IDs/UI text; provenance in a sidecar so it can't change semantic hashes).
2. **Projection parity** — same resolved-plan digest → byte-identical Nix projections, argv+env, flake targets, planned mutation list, validation checklist (each hashed into the preview receipt).
3. **Nix evaluation parity** — same verified Git commit+tree, clean worktree, Nix `system`, exact flake installable/host target, and exact `flake_lock_sha256` → equal `config.mySystem` (installer-owned fields), NixOS system `drvPath`, Home-Manager activation `drvPath`, disko JSON (when that later path is on). An unavailable or unverifiable source fact, dirty tree, or source/lock/target mismatch fails before execution.
4. **Expert-Nix boundary** — direct hand-edited Nix stays supported but is OUTSIDE adapter parity; its correctness is evaluated by Nix, never silently conflated with schema-controlled choices.

## 7. Safety, secrets, recovery (codex corrections folded in)

- **Disk = the only irreversible step**, hard-gated: plain-language target ("erases Disk 1, a 500GB drive; nothing else touched"), typed confirmation, and — because it's NOT rollback-able — a required backup/recovery-media acknowledgement. First-install recovery ≠ upgrade recovery (no prior generations exist after a fresh wipe).
- **Resumable mutation journal** — durable state + explicit recovery behavior for power loss between partitioning and bootloader (deferred with the bare-metal phase, but designed now).
- **Secrets never serialized** — disk passphrases, auth phrases, tokens never enter the plan, logs, telemetry, or any AI prompt.
- **Rollback front-and-center** for the non-destructive (rebuild/switch) path — a headline feature.

## 8. AI contract (local-only, optional, untrusted adapter)

AI is an **untrusted proposal adapter**, never an authority:
1. receives a redacted hardware capability summary + the schema-supported choice catalog;
2. returns strict JSON constrained to the request-plan schema — no raw Nix/shell/paths/secrets/disk-auth;
3. the trusted resolver applies defaults + policy;
4. UI shows a semantic diff (current → proposed resolved plan);
5. the user approves the **trusted plan**, not the model response.

AI explanation text has zero execution authority. **Local inference only** (own hardware); remote is an opt-in enhancement (own OAuth, no keys). AI is **not on the install critical path** — it's optional during install and the primary assistant *after* install.

Model selection is a **versioned, digest-pinned policy/model catalog with its own P0 artifact, schema, owner, and validation**, not a hard-coded model-name table embedded in the install-plan schema or detector. The policy evaluator consumes the versioned hardware summary and records the evidence, reserved system RAM/VRAM margins, eligible acceleration backend, GPU-layer/offload cap, context cap, and downgrade reason, then emits `recommended`, `limited`, or `not_advised`. Unknown VRAM or insufficient evidence resolves conservatively and can never authorize unsafe full offload. CPU-only operation remains an honest `limited` path when the pinned catalog supports it. Concrete thresholds and timeout budgets must be measured and versioned; review examples such as a fixed 15-second timeout are not requirements without AQ-OS evidence.

### 8.1 Hardware identity and capability evidence

Presence and identity are driver-independent. The detector enumerates `/sys/bus/pci/devices/*` first and preserves PCI BDF, class, vendor ID, and device ID in deterministic order. `lspci -nn` is enrichment or fallback. DRM, loaded modules, `nvidia-smi`, `rocm-smi`, and similar runtime probes are optional evidence for driver readiness or memory capacity; they never decide whether a device exists. The detector supports multiple GPUs and emits an explicit `unknown` / `insufficient_evidence` outcome rather than guessing. Capability summaries are redacted and secret-free.

Existing `scripts/ai/lib/hw_probe.py`, `scripts/governance/discover-system-facts.sh`, `config/hardware-capability-matrix.json`, and `ai-stack/models/registry.json` are reusable inputs, not yet the P0 contract. The current probes partially use `lspci -nn` and DRM sysfs but do not provide a complete driver-independent PCI inventory or one coherent sizing policy.

## 9. Modular engine underneath (experts)

The golden path is a curated resolved plan; the full `mySystem.*` toggle library (profiles/roles/host-classes/options) remains for experts to compose, and for a possible future "advanced/custom" door. Expanding the template + module library (Everyday/Data-ML/Creative/Server/Hardened…) is a later, separate product+module workstream — not P1.

### 9.1 Source-backed P0 module inventory

The current reusable surface is concrete: profiles `ai-dev`, `gaming`, and `minimal`; roles `ai-stack`, `cpp-dev`, `desktop`, `gaming`, `kernel-dev`, `server`, and `virtualization`; CPU/GPU modules plus storage, RAM tuning, zram, network, mobile, and recovery under `nix/modules/hardware/`. The golden path is a **new resolved composition** over these real modules; it is not a reference to a fictional `profiles/desktop.nix`, and it does not assume that existing `ai-dev` or `gaming` alone already represents the product.

The installer owns high-level, schema-supported intent: golden profile, supported role toggles, detected hardware evidence, safe kernel/boot posture, and optional AI recommendation. Expert-only Nix retains low-level driver flags, kernel parameters, raw model/quantization/offload arguments, arbitrary packages/services, secrets, and options outside the declared field set. Detected device identity is evidence, not a user-selectable preference. Disk fields remain schema-designed but non-executable until P4.

Every installer-visible catalog entry has a stable ID, plain label/description, support predicate, dependency and conflict expressions, estimated resource-cost structure, projected `mySystem.*` fields, and source-module reference. Catalog validation proves completeness against actual imports, dependency closure, deterministic ordering, and fail-closed unknown metadata. Multi-GPU is first-class: NVIDIA plus Intel/AMD integrated graphics is not a schema conflict merely because more than one vendor is present.

Local inventory task `local-20260901-112905-8h5np7` supported the need for explicit `label` / `cost` / `deps` / `conflicts` metadata and the installer-owned versus expert-only boundary. Its invented path, fixed `Q5_K_M` rule, `<4 GB` threshold, and blanket NVIDIA-plus-Intel-Arc exclusion were rejected because they conflict with the repository and verified policy. Local output is advisory until source-checked.

## 10. Roadmap (golden-path framed)

- **P0 — Contract + inventory.** Author `aqos-install-plan-v1.schema.json` + the resolver/compiler; formalize `mySystem.*` as the installer-owned field set; catalog modules with label/cost/deps/conflicts metadata; build the deterministic, driver-independent hardware detector → redacted capability summary; author and validate the separate versioned AI-fit policy/model catalog; pin both catalogs and the exact source/lock/target identity used by every resolved plan.
- **P1 — Golden-path guided flow over the ACTIVE engine, non-destructive only.** Author the "AQ-OS Workstation" golden profile; guided TUI: welcome → confirm hardware-tuned golden defaults → optional-AI yes/no (hardware-honest) → preview exact mutations → authorize → rebuild/switch with durable progress. Adapter+projection+eval parity tests green. No disk ops.
- **P2 — Local AI-assist (optional, post-install-primary).** Untrusted proposal adapter → resolver → semantic-diff approve; offline. Hardware-fit model tuning automated.
- **P3 — First-run welcome + rollback-forward + locally-AI-answered manual.**
- **P4 — Hardened bare-metal path** with disko + the resumable mutation journal + recovery media.
- **P5 — Aesthetic layer, ISO, `--recommended` one-command, expanded template library, shareable/community configs.**

## 11. Success metrics

- A first-time-Linux user reaches a working, tuned golden-path desktop with zero terminal, zero jargon, and one honest AI yes/no.
- Guided / AI / manual / legacy-flag paths produce byte-identical resolved plans and equal Nix derivations (parity suite green).
- Zero "wiped the wrong disk" foot-guns; every irreversible step confirmed + backup-acknowledged.
- Full install completes offline with no model/network/account.
- 100% of expert flags/phases + direct-Nix workflows preserved (regression suite).
- PCI-only, `lspci`-only, DRM-only, hybrid/multi-GPU, no-GPU, unknown-VRAM, and missing-probe fixtures resolve deterministically and conservatively.
- Cross-adapter golden fixtures produce identical RFC 8785 bytes/digests; a dirty tree, missing/unverifiable Git object, or commit/tree/lock/system/installable drift fails before execution.

## 12. Open questions and deferred product decisions

1. Golden profile contents: exact dev toolchains, DE choice, and gaming stack are P1 product decisions. Antigravity's Hyprland/KDE and tool list is advisory, not a frozen P0 requirement.
2. Hardware policy: establish measured RAM/VRAM reserves, performance floors, and catalog-backed thresholds for the AI `recommended` / `limited` / `not_advised` call. Do not copy a fixed model table into the schema.
3. Where the resolver lives (language/ownership) and how it invokes the active `nixos-quick-deploy.sh` without a logic fork.
4. TUI stack for P1 (gum/whiptail vs a small Textual/Ratatui app).
5. Minimal viable module metadata (label/cost/deps/conflicts) format + location.
6. Migration: how the current flags become thin projections of the resolved plan without breaking existing operators.
