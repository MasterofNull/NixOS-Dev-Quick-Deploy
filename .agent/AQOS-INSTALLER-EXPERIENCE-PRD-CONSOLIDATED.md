# AQ-OS Installer & Quick-Deploy Experience — CONSOLIDATED PRD

Status: CONSOLIDATED v1 (folds claude + codex drafts; owner golden-path direction 2026-08-31). Pending: local(qwen) + antigravity perspectives.
Authors/sources: claude-opus-4.8 (product/architecture framing), codex-cli (engineering constraints, config contract, parity design). Exemplar: omarchy (opinionated, curated, "OS for the age of agents").
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

Three distinct artifacts:
- **request plan** — user/AI-supplied values, defaultable fields may be omitted;
- **resolved plan lock** — all defaults explicit, canonical, immutable, **secret-free**;
- **execution authorization receipt** — short-lived approval bound to the resolved-plan hash + current hardware identity; never part of reusable config.

Everything (golden-path choices, hardware tuning, AI proposals, expert flags) targets the `mySystem.*` field set through this contract.

## 6. Parity guarantee (codex; 4 layers)

"One engine" is proven, not asserted:
1. **Adapter parity** — guided answers, AI JSON, manual manifest, and equivalent legacy flags produce **byte-identical canonical resolved-plan JSON** (sorted keys, explicit defaults, no timestamps/IDs/UI text; provenance in a sidecar so it can't change semantic hashes).
2. **Projection parity** — same resolved-plan digest → byte-identical Nix projections, argv+env, flake targets, planned mutation list, validation checklist (each hashed into the preview receipt).
3. **Nix evaluation parity** — same commit + `flake.lock` → equal `config.mySystem` (installer-owned fields), NixOS system `drvPath`, Home-Manager activation `drvPath`, disko JSON (when that later path is on).
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

## 9. Modular engine underneath (experts)

The golden path is a curated resolved plan; the full `mySystem.*` toggle library (profiles/roles/host-classes/options) remains for experts to compose, and for a possible future "advanced/custom" door. Expanding the template + module library (Everyday/Data-ML/Creative/Server/Hardened…) is a later, separate product+module workstream — not P1.

## 10. Roadmap (golden-path framed)

- **P0 — Contract + inventory.** Author `aqos-install-plan-v1.schema.json` + the resolver/compiler; formalize `mySystem.*` as the installer-owned field set; catalog modules with label/cost/deps/conflicts metadata; build the deterministic hardware detector → redacted capability summary.
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

## 12. Open questions (for local + antigravity to fold in)

1. Golden profile contents: exact dev toolchains, DE choice, gaming stack, and the hardware thresholds for the AI "recommended/limited/not-advised" call.
2. Hardware detector: reuse existing `hardware/{cpu,gpu}` + facts.nix discovery, or a new probe? What's the redacted capability summary schema?
3. Where the resolver lives (language/ownership) and how it invokes the active `nixos-quick-deploy.sh` without a logic fork.
4. TUI stack for P1 (gum/whiptail vs a small Textual/Ratatui app).
5. Minimal viable module metadata (label/cost/deps/conflicts) format + location.
6. Migration: how the current flags become thin projections of the resolved plan without breaking existing operators.
