# Flagship Design Review — AQ-OS Installer & Quick-Deploy Experience Consolidated PRD

**Reviewer:** Antigravity (Independent Flagship Product, Architecture, Adversarial-Concurrency & SRE Reviewer)  
**Date:** 2026-09-01  
**Candidate Document:** `.agent/AQOS-INSTALLER-EXPERIENCE-PRD-CONSOLIDATED.md`  
**Candidate Hash (Verified):** `bfd870d7f4ae06ce193ec67c7b3847a24cc72e40ad9580c8d7c335993b1550ca`  
**Verdict:** **PASS (ADOPT WITH ARCHITECTURAL & OPERATIONAL ENHANCEMENTS)**

---

## Executive Summary

The Consolidated PRD (`v1`) successfully unifies the product framing from Claude and the engineering/config contract constraints from Codex into a single, cohesive design. The decision to establish **ONE Golden Path** ("AQ-OS Workstation": Pro Dev + Gaming + Optional Local AI) while preserving the underlying `mySystem.*` modular engine for power users is architecturally sound and directly addresses user decision fatigue. Crucially, decoupling the installation execution path from running AI models guarantees deterministic, offline, and fail-closed deployment.

This review validates the candidate hash `bfd870d7f4ae06ce193ec67c7b3847a24cc72e40ad9580c8d7c335993b1550ca` and provides formal adjudication across all five requested design domains.

---

## 1. Adjudication of Golden-Path, Hardware-Tuned AI & Deterministic Install

### Architecture & Design Evaluation: **SOUND**

1. **Golden Path Primacy**: The "Omarchy-style" opinionated golden path eliminates menu complexity for 90%+ of deployments. By treating the golden path as a pre-resolved, curated configuration over `mySystem.*`, power users retain 100% composability via standard Nix options without introducing split execution logic.
2. **Deterministic Installation (AI-Decoupled)**: Hard-gating installation on static schema resolution rather than runtime model outputs is a mandatory reliability requirement. A bare machine during first install has no local model; executing install scripts via LLM inference introduces non-deterministic failure modes and network dependencies. Positioning the AI assistant strictly as an optional post-install proposal adapter (untrusted frontend) maintains fail-closed safety.
3. **Hardware-Adaptive AI Selection**: Dynamically tuning local LLM parameters (quantization level, VRAM allocation, GPU layer offload, context length) to detected hardware prevents out-of-memory (OOM) kernel panics and unusable inferencing latency.

### Identified Edge Cases & Required Mitigations

- **Live ISO Driver Detection Gap**: Hardware discovery during live USB boot may fail to initialize proprietary GPU drivers (e.g. Nvidia discrete GPUs running under generic `nouveau` or Fallback VESA).  
  *Mitigation*: The hardware detector must query PCI IDs via `lspci -nn` / `/sys/bus/pci` directly rather than relying on active kernel module loading (`lsmod` / DRM driver state) to size AI models and driver packages accurately.
- **AI Proposal Timeout & Failure Boundaries**: Local inference during post-install setup can stall or leak memory.  
  *Mitigation*: AI proposals MUST execute under strict process isolation with hard token ceilings and execution timeouts (e.g., 15s MAX). If the AI adapter fails or times out, the system must gracefully fall back to default guided prompts without blocking user workflow.

---

## 2. Cross-Distro Comparative Analysis

| Installer / Framework | Key Strengths & Patterns to Borrow | Weaknesses & Deliberate Differences |
| :--- | :--- | :--- |
| **archinstall** | Lightweight scriptable JSON schema approach. Clean separation between user profile definitions and installation runners. | Fragile terminal menu handling and loose schema enforcement. **AQ-OS Differs**: Enforces strict Draft 2020-12 JSON Schema validation (`additionalProperties: false`) and 4-layer parity. |
| **Calamares** | Clear, unambiguous visual disk partitioning UI with explicit target disk warnings and non-reversible confirmation gates. | Heavy Qt GUI dependencies; difficult to integrate into headless or low-resource TUI deployments. **AQ-OS Borrow**: Unambiguous disk identification and explicit typed confirmation gates. |
| **Omarchy** | Opinionated, ready-to-work developer desktop experience ("OS for the age of agents") with zero post-install setup friction. | Imperative dotfile symlinking and shell script mutations. **AQ-OS Differs**: Backs the golden path with 100% declarative NixOS options (`mySystem.*`) and flake-locked evaluations. |
| **Universal Blue (Bluefin / Bazzite)** | Automatic hardware detection for Nvidia/Mesa drivers, dedicated gaming (Steam/Lutris) & developer container workflows. | Relies on OCI image layering (rpm-ostree). **AQ-OS Differs**: Native Nix package management, atomic NixOS generation switches, and local source composability. |
| **NixOS Installer (`nixos-install`)** | Evaluates native Nix expressions directly; guarantees exact system derivation generation. | Intimidating to non-experts; lacks guided hardware-adaptive tuning and normalized configuration contracts. **AQ-OS Differs**: Wraps native Nix evaluation behind a friendly guided TUI and JSON config contract. |

---

## 3. Config Contract & 4-Layer Parity Design Evaluation

### Parity Architecture Evaluation: **SOUND**

The 4-layer parity model proposed in Section 6 of the Consolidated PRD provides a provable guarantee that guided TUI, AI proposal, manual JSON, and legacy CLI flags execute through the exact same underlying compiler:

1. **Layer 1 (Adapter Parity)**: All input sources produce byte-identical canonical resolved-plan JSON (`aqos-install-plan-v1.json`).
2. **Layer 2 (Projection Parity)**: Canonical JSON resolves to identical Nix evaluation parameters, mutation receipts, and execution steps.
3. **Layer 3 (Nix Evaluation Parity)**: Identical plan lock + identical `flake.lock` produce identical NixOS derivation paths (`drvPath`).
4. **Layer 4 (Expert Boundary)**: Direct hand-edited Nix files remain supported but are explicitly segregated outside adapter parity.

### Potential Failure Modes & Operational Hardening

- **Canonical JSON Serialization Drift**: Subtle differences in JSON serializers across languages (e.g. float vs integer representations or key sorting) can break byte-identical hash equality.  
  *Requirement*: The resolver specification MUST mandate RFC 8785 (JSON Canonicalization Scheme / JCS) for hashing resolved plans.
- **Flake Lock Pinning**: Evaluation parity (Layer 3) breaks if the live installer uses a different nixpkgs flake lock than the target configuration.  
  *Requirement*: The resolved plan lock MUST explicitly embed the exact `flake.lock` commit digest alongside system configuration options.

---

## 4. Golden Profile Contents & Hardware Threshold Specifications

### A. Golden Profile ("AQ-OS Workstation") Recommended Stack

- **Developer Toolchains**: Rust (`rustup` / `rust-bin`), Python 3.12 (`uv`), Node.js (`pnpm`), C/C++ (`clang`, `gcc`, `gdb`), Containers (`podman` / `docker` via `mySystem.roles.containers`), Neovim / VS Code / Helix, Git + SOPS secret tooling.
- **Gaming & Media Stack**: Steam, Lutris, Wine-GE, Gamemode (`mySystem.roles.gaming`), MangoHud, Pipewire low-latency audio.
- **Desktop & UX Layer**: Hyprland Wayland compositor (or KDE Plasma fallback for multi-monitor Nvidia edge cases), Kitty terminal, Rofi/Fuzzel launcher, Waybar status bar.

### B. Hardware Sizing Thresholds for Optional Local AI

To prevent poor user experience and system instability, local AI deployment must adhere to strict hardware boundaries:

| Sizing Tier | Hardware Criteria (System RAM / VRAM / CPU) | Recommended Model & Allocation | System Status Indicator |
| :--- | :--- | :--- | :--- |
| **Not Advised** | System RAM < 16 GB **OR** CPU-only with < 8 cores | Local AI Disabled (Use optional remote API adapter) | `Not Advised (Insufficient RAM/VRAM)` |
| **Limited / Entry** | System RAM 16–32 GB **AND** VRAM 6–8 GB (e.g., RTX 3060 / 4060) | **Qwen2.5-Coder-7B** (4-bit quant, 4K context), max 4–6 GB VRAM budget | `Limited (Light assistance enabled)` |
| **Recommended** | System RAM ≥ 32 GB **AND** VRAM ≥ 12 GB (e.g., RTX 3080 / 4070+) | **Qwen2.5-Coder-14B / 32B** (4-bit quant, 16K context, full GPU offload) | `Recommended (Full local AI active)` |

---

## 5. Beginner Onboarding & Accessibility Specifications

### A. First-Run Onboarding (`aqos-welcome`)

Post-installation, the system should launch a lightweight first-run utility providing:
1. **Hardware Verification**: Live test for display scaling, audio output (Pipewire), and GPU acceleration.
2. **AI Endpoint Check**: If local AI was selected, verify local model responsiveness (`:8080` / `:8003`) with a 1-click test prompt.
3. **Quick Tour & Keybindings**: Display essential desktop shortcuts (Super+Enter terminal, Super+R runner, Super+Q close).

### B. Accessibility Commitments

- **Screen Reader & TUI Compatibility**: The TUI installer MUST respect `NO_COLOR=1` and disable raw ANSI animations when speech synthesis or screen reader tools (e.g. Orca) are detected.
- **Font & Display Scaling**: Support high-contrast color themes and dynamic font scaling via standard TUI keyboard shortcuts (`Ctrl++` / `Ctrl+-`).
- **Keyboard-Only Navigation**: 100% of installer options navigable using standard Arrow keys, Tab, Space, and Enter.

---

## Conclusion & Next Steps

The Consolidated PRD is **APPROVED**. The team is authorized to proceed with Phase P0 (Authoring `aqos-install-plan-v1.schema.json` schema and resolver RFC).
