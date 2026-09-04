# AQ-OS Installer & Quick-Deploy Experience — PRD (claude draft)

Status: DRAFT for multi-agent consolidation
Author: claude-opus-4.8 (analysis/architecture tier)
Date: 2026-08-30
Exemplar reference: omarchy (github.com/omacom/omarchy, omarchy.org) — "beautiful, modern & opinionated Linux distribution… the malleable OS for the age of agents."

---

## 1. Vision

Make the NixOS system install + quick-deploy **the best, easiest, and most thorough automated setup in Linux** — a single experience that carries an *extreme beginner* (never touched Linux or NixOS) from bare metal to a working, beautiful, AI-augmented workstation **without them needing to understand NixOS**, while giving an *expert* full declarative control and nothing taken away.

Our unfair advantage over every other distro installer, including omarchy: **this system ships local AI agents.** The installer is not just guided — it is **AI-assisted**. The user can describe what they want in plain language ("a machine for Python data work with a clean dark theme") and the local agents translate that into a validated NixOS configuration, explain each step, and stay available after install. omarchy's "vibe your way through every alteration" — we do it *natively*, during install and forever after.

## 2. Current state (honest)

- Entry point: `nixos-quick-deploy.sh` (~4755 lines) + a `phases/phase-*.sh` declarative phase engine + `nix/modules/` + `flake.nix`.
- Strengths: genuinely powerful — phase-based, idempotent, disko partitioning, model selection, secrets bootstrap, GUI-switch handling, live-switch safety, ~22 places with some beginner-oriented prompting.
- Gaps (why it is expert-first today):
  - **No single guided front door.** A newcomer meets a 4755-line script and ~20 flags (`--phase0-disko`, `--skip-model-selection`, `--ai-secrets-bootstrap`…). Decision fatigue, no plain-language framing.
  - **No graphical / rich-TUI experience.** No welcome screen, no visual progress, no "Coming from Mac/Windows" on-ramp.
  - **No AI-assisted path** despite the whole system being AI agents.
  - **No first-run onboarding.** After install, the user is on their own; there is no omarchy-style manual/tour.
  - **Destructive steps under-explained** to a beginner (disko wipes disks).

## 3. Goals

1. **Zero-to-working for a total beginner** with no NixOS knowledge, via a guided flow with safe, opinionated defaults and plain-language choices.
2. **Nothing lost for experts** — the flag/phase CLI stays first-class; the new experience is a *layer over* the same phase engine, never a fork.
3. **LOCAL-ONLY AI assist — remote NEVER required (HARD, owner 2026-08-30).** The install is driven by the machine's OWN local agents/models. Describe intent in words; the LOCAL agent proposes a validated config, explains it, and the user approves (beginner-friendly human control, crypto/keys hidden). Remote agents are an OPTIONAL enhancement a user may opt into (own OAuth, per no-API-keys policy) — the entire install, including AI-assist, MUST work fully offline with only local inference. No install step may hard-depend on network/remote AI.
4. **Modular, template-driven composition (HARD, owner 2026-08-30).** Ship a FULL SUITE of premade system templates + feature/tool modules the user can **pick, combine, configure, and implement**. Built on our existing `mySystem.*` toggle system (profiles = templates, roles = features, host-classes = hardware bases). Users compose their system attribute-by-attribute; they are never forced into one blessed image.
5. **Thorough + safe** — non-destructive by default; every destructive/irreversible step (disk wipe) is explicit, confirmed, and reversible where NixOS allows (generations/rollback front-and-center).
6. **Beautiful, polished first-run** — aesthetic-first, curated defaults, a first-boot welcome + guided tour + living manual.
7. **Beginner-to-power continuum** — the same install can be driven fully-guided, fully-automated (one command), or fully-manual (flags/phases), and the user can graduate between them.

## 4. Non-goals (this PRD)

- Not replacing the phase engine or `nixos-quick-deploy.sh` — we wrap and orchestrate it.
- Not shipping a custom desktop environment from scratch (curate existing, omarchy-style).
- Not an online account / telemetry requirement — local-first, no phone-home.
- Lighter/alternate local model swap is explicitly OUT (owner-decided 2026-08-30).

## 5. Guiding principles (omarchy-derived + AI-native)

- **Opinionated, curated defaults** — one blessed "recommended" path removes decision fatigue; choices are progressive, not upfront.
- **Guided simplicity without sacrificing control** — the beginner never sees a flag; the expert never loses one.
- **AI as the interface, not a gimmick** — plain-language intent → validated Nix; explanations in human terms; agents remain the post-install "vibe your way through" surface.
- **Safe & reversible first** — destructive actions gated behind clear, confirmed, plain-language surfaces; NixOS rollback is a headline feature, not a footnote.
- **Aesthetic-first** — theming, fonts, wallpaper, a welcome experience are P0, not polish-later.
- **Honest & observable** — the install shows real progress and real state; failures explain themselves and offer a next action (dogfooding our own observability culture).

## 5.5 Modularity & the template library (the core mechanism)

We do NOT ship one blessed image. We ship a **library of composable modules + premade templates**, and the installer is a friendly way to **pick → combine → configure → implement**. This is already how our system is built — we expose and expand it, we do not reinvent it.

**The composition layers (all via `mySystem.*` option toggles):**
- **Templates = `nix/modules/profiles/`** — curated, opinionated STARTING POINTS that flip a coherent set of toggles (e.g. `ai-dev` sets `mySystem.roles.aiStack.enable`, `cppDev.enable`, `desktop.enable`, `monitoring.enable`…). Today: `ai-dev`, `gaming`, `minimal`. **We expand this into a full suite** (e.g. Everyday, Developer, Data/ML, Creative, Server/Homelab, Privacy/Hardened, Gaming, Minimal).
- **Features/tools = `nix/modules/roles/`** — composable capability modules the user adds/removes on top of a template (today: `desktop`, `server`, `cppDev`, `kernelDev`, `gaming`, `virtualization`, `aiStack`, `antigravity`). Each is an independent `mySystem.roles.<x>.enable` toggle.
- **Hardware base = `nix/modules/host-classes/`** + `hardware/{cpu,gpu}` — detected/selected machine family.
- **Fine-grained attributes = `mySystem.*` options** (monitoring, mcpServers, localhostIsolation, ports, model selection, disk layout…) — the individual knobs.

**The config contract / SSOT = the `mySystem.*` option set** (`nix/modules/core/options.nix`). Every path — guided flow, AI-assist, and expert flags — targets the SAME `mySystem.*` toggles, which is exactly why guided and manual are provably one engine. A user's chosen system is just a set of toggle values ("a config") that the installer serializes, an agent can read/propose, and the flake evaluates.

**Pick → combine → configure → implement:**
1. **Pick** a template (profile) as the starting point — or "start from scratch / minimal."
2. **Combine** — turn features (roles) on/off; the UI shows what each adds in plain language + its cost (RAM/disk/complexity), with conflict/dependency awareness (e.g. GPU role needs a GPU).
3. **Configure** — set the exposed options for enabled modules (theme, hostname, ports, model, disk).
4. **Implement** — the installer materializes the `mySystem.*` selection into the flake, dry-runs (`nixos-rebuild build`), then applies. Fully reproducible; the chosen "config" can be saved, shared, re-applied, and version-controlled.

**Where AI fits (locally):** the local agent maps plain-language intent to a starting template + a set of role/option toggles ("I want a private machine for Python + light gaming" → `ai-dev`-like base, enable `gaming`, disable `antigravity`, hardened options on), explains each toggle, flags conflicts, and hands the human an approve/tweak surface. It reads and writes the same `mySystem.*` contract — nothing an expert couldn't do by hand, just faster and explained. **No remote call anywhere in this path.**

**Community/extensibility (later):** because a "config" is just toggle values + optional custom modules, users can share templates and third parties can drop in new role/profile modules — a modular ecosystem, not a fixed distro.

## 6. Personas

- **Bea (extreme beginner):** came from Windows/Mac, wants a "computer that just works and looks great," terrified of the terminal and of "wiping my disk." Needs: plain language, safe defaults, visual progress, undo, no jargon, help on tap.
- **Ravi (intermediate/dev):** comfortable in a terminal, new to NixOS, wants a good dev box fast without learning the whole Nix language today. Needs: curated dev presets, AI-assist to write the config, an escape hatch to edit it.
- **Sam (expert):** knows NixOS/flakes, wants full declarative control, reproducibility, and to script the whole thing headless. Needs: the flags/phases untouched, `--unattended`, a machine-readable contract, disko control.

## 7. Experience design

### 7.1 The three doors (one engine)
1. **Guided (default for beginners):** a rich TUI (and/or GUI) welcome → a short interview (plain-language) → AI proposes a config → preview + explain → confirm → install with visual progress → first-boot welcome + tour.
2. **Automated (one command):** `nixos-quick-deploy --recommended` (or an ISO that boots straight into the guided flow) — accept all curated defaults, minimal questions, safe.
3. **Manual (experts):** the existing flag/phase CLI, unchanged, plus a documented machine-mode contract (mirrors the `aq-session-start --machine` pattern we just shipped).

### 7.2 The guided interview (beginner)
Plain-language questions, each with a "Recommended" pre-pick and a one-line "why":
- "What is this computer for?" (everyday / development / creative / server) → drives curated app + module presets.
- "How should it look?" (curated theme gallery, live preview) → theming.
- "Who are you?" (username, human-readable) → user setup, no `/etc/shadow` talk.
- "Disk" — the ONLY scary step — presented with the strongest guardrails: detect disks, plain-language ("this will erase Disk 1 — a 500GB drive; nothing else is touched"), typed confirmation, and a "back" at every step.
- Everything else (bootloader, locale, networking, the entire AI stack) is defaulted and explained, not asked.

### 7.3 AI-assisted config
- A free-text box: "Describe your ideal setup." → local agent drafts the module selection + a human-readable summary + the actual Nix it will write → user approves/tweaks in plain language. This is where we beat every other installer: the config author is an agent, the reviewer is the human, and the record is real Nix (anti-gaming: the shown config IS the applied config).

### 7.4 First-run (post-install)
- Boot into a **welcome app**: "Coming from Mac/Windows" tour, the essentials (how to update, how to roll back, how to ask the local AI for help), theme/wallpaper picker, and a link into a living **manual** (omarchy's 51-chapter model, but ours can be AI-answered: "ask the manual anything").

### 7.5 Architecture (thin over the existing engine)
- The guided front-end (TUI first — `gum`/`whiptail`/a small Textual/Ratatui app; GUI later) **emits the same inputs** the phase engine already consumes (env vars / a config JSON), then invokes the existing `nixos-quick-deploy.sh` phases. No logic fork.
- AI-assist calls the local coordinator to translate intent → module/preset selection → validated Nix (dry-run/`nixos-rebuild build` before switch).
- Every guided choice maps to an existing flag/phase, so guided and manual are provably the same engine (a test asserts parity).

## 8. Roadmap (phased, each phase independently shippable)

- **P0 — Research & design (this PRD + consolidation).** Multi-agent PRDs → CONSOLIDATED; audit the phase engine's input surface; formalize the `mySystem.*` toggle set as the config contract/SSOT; catalog the module inventory (profiles/roles/options) with a plain-language label + cost + dependencies per module; define the guided-interview question set.
- **P0.5 — Expand the template + module library.** Author the full suite of premade templates (profiles) — Everyday, Developer, Data/ML, Creative, Server/Homelab, Privacy/Hardened, Gaming, Minimal — and fill role/feature gaps, each with metadata (label, description, cost, deps, conflicts) the installer consumes. This is the "full suite of premade configs" workstream and runs alongside P1.
- **P1 — Guided TUI MVP over the existing engine (pick→combine→configure→implement).** Welcome → pick a template → toggle features → configure → preview → confirm → install with progress, all emitting `mySystem.*` values into the existing phases. Non-destructive-by-default; disk step hard-gated. Guided/manual parity test.
- **P2 — LOCAL AI-assisted composition.** Plain-language intent → local agent maps to template + toggles → explains + flags conflicts → approve/tweak → validated Nix. Fully offline (local inference only). Dry-run (`nixos-rebuild build`) before switch.
- **P3 — First-run welcome + living manual.** Welcome app, tour, roll-back-front-and-center, locally-AI-answered manual.
- **P4 — Aesthetic layer + theming.** Theme gallery, fonts, wallpaper, live preview.
- **P5 — Bootable ISO + `--recommended` one-command path + full unattended/expert contract + shareable/community templates.**

## 9. Success metrics

- A first-time-Linux user reaches a working, themed desktop **unattended in < N minutes** with **zero terminal use** and **zero jargon** encountered.
- Guided and manual paths produce **byte-identical** system config for the same choices (parity test green).
- Every destructive step is **confirmed + reversible/explained**; zero "I wiped the wrong disk" foot-guns.
- Post-install, a beginner can **update, roll back, and ask the AI for help** from the welcome app without documentation.
- Expert flags/phases: **100% preserved** (regression test).

## 10. Open questions (for consolidation with codex / qwen / antigravity)

1. TUI vs GUI first? (Lean TUI MVP for reach + speed; GUI in P4/P5. Confirm.)
2. Do we ship a bootable ISO (omarchy 4.x did) or stay "run on an existing NixOS/any-Linux" — or both?
3. How much of the AI stack installs by default for a "everyday" (non-dev) beginner? (Curation question.)
4. Curated-defaults ownership: who blesses the "recommended" set per persona, and where is it declared (a `presets/` module)?
5. Where does the config-JSON contract live so guided/AI/manual all target one schema? (SSOT.)
6. Accessibility scope for P1 (dictation/large-text/high-contrast — omarchy treats a11y as first-class).

---

*Next: route to codex, local(qwen), and antigravity for their PRD drafts; consolidate into `AQOS-INSTALLER-EXPERIENCE-PRD-CONSOLIDATED.md`; then a phased plan under `.agents/plans/` with a projected PM tracker.*
