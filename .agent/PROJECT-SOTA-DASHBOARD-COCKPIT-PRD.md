# PROJECT-PRD: SOTA Command Center Cockpit Revamp & Universal Bootable Installer

**Author**: MasterofNull & Antigravity (Orchestrator)
**Date**: 2026-10-25
**Status**: PLAN_READY / RATIFIED
**Governing Canon**: `canon/blocks/mvp-delivery-sop.md` & `canon/blocks/behavioral-rules.md` (Rule 8)

---

## 1. Executive Summary & Problem Statement

### 1.1 The Operational Defect
Prior iterations of the NixOS AI Command Center Dashboard delivered fragmented, inconsistent panels with high visual clutter, non-functional mock stubs, and latent HTTP 500 / timeout errors on core aggregation routes (e.g. `/api/aistack/advanced/runtime-summary`). Concurrently, hardware deployment of this sovereign AI stack onto bare-metal machines, virtual hypervisors (Proxmox/KVM), and edge devices was gated on ad-hoc scripts rather than a single, declarative, universal installation engine with verified TPM2/LUKS disk encryption options.

### 1.2 Core Architecture Direction (Anthropic Paradigm Alignment)
In accordance with Anthropic's verified research (*"One AI agent beats many subagents now that models can handle complexity alone"*), this system shifts away from fragmented, shallow subagent churn. A **single lead agent** maintains persistent context across the whole architectural surface, orchestrating durable background execution without losing the broader system picture.

---

## 2. Component Topology & System Architecture

```
                       +-----------------------------------------------+
                       |           Operator Browser Cockpit            |
                       |    (OKLCH Dark Canvas · Impeccable Theme)     |
                       +-----------------------+-----------------------+
                                               |
                     WebSocket (/ws/metrics)   |   HTTP REST (:8889)
                     SSE (/ws/agent-state)     |   (FastAPI Engine)
                                               v
                       +-----------------------------------------------+
                       |       Command Center Dashboard Backend        |
                       |             (Port 8889 · Systemd)             |
                       +-------+---------------+---------------+-------+
                               |               |               |
                 +-------------+               |               +-------------+
                 v                             v                             v
     +-----------------------+     +-----------------------+     +-----------------------+
     |   Hybrid Coordinator  |     |   AIDB Knowledge DB   |     | System 1 Stream Triage|
     |  (:8003 · UDS Auth)   |     |  (:8002 · Qdrant RAG) |     | (WAL SQLite · <150ms) |
     +-----------+-----------+     +-----------+-----------+     +-----------+-----------+
                 |                             |                             |
                 +-----------------------------+-----------------------------+
                                               |
                                               v
                       +-----------------------------------------------+
                       |      Hardware Fact & Confinement Layer        |
                       |    - Landlock LSM Loopback Pins               |
                       |    - AppArmor / Bubblewrap Cells              |
                       |    - Declarative Disko (Plain vs. LUKS/TPM2)  |
                       +-----------------------------------------------+
```

---

## 3. High-Depth Specifications

### 3.1 SOTA Command Center Cockpit (Frontend & UX)
1. **Design System & Visual Ergonomics (Impeccable Standard)**:
   - **Color Engine**: Strict OKLCH color space avoiding dead black (`#000000`) and blinding pure white (`#ffffff`). Surface levels: `var(--bg)` (dark neutral slate), `var(--bg2)` (elevated panel), `var(--cyan)` (telemetry / active action), `var(--grn)` (verified healthy), `var(--yel)` (attention / degraded), and `var(--magenta)` (adversarial / security block).
   - **Typography**: Fluid type scale with strict >= 1.25 hierarchy ratio. Tabular figures (`font-variant-numeric: tabular-nums`) on all latency and token metrics.
   - **Zero Decorative Code (Rule 23)**: Every badge, graph, and metric links directly to live non-gamified telemetry. No static or hardcoded "100% OK" cards.

2. **Thought Stream & Intent HUD**:
   - Real-time SSE stream displaying the active lead agent's intent, current step, and reasoning traces.
   - Visual distinction between System 1 fast heuristics (<200ms) and System 2 deliberate verification turns.

3. **Human Steering & Intervention Dock**:
   - Single-click operator actions: `PAUSE AGENT`, `STEER PROMPT`, `FORCE LOCAL FALLBACK`, and `RELEASE CANARY LOCK`.
   - Interventions are cryptographically recorded in the operator audit trail (`/var/lib/nixos-system-dashboard/telemetry/operator-audit.jsonl`).

### 3.2 Backend Route Resiliency (`dashboard/backend/api/routes/aistack.py`)
1. **Concurrency & Locking Isolation**:
   - SQLite databases (`oncall.db`, `triage_state.sqlite`) operate in Write-Ahead Logging (`PRAGMA journal_mode=WAL`) with busy timeouts set to `2.0s`.
   - SQLite connection exceptions are gracefully intercepted to yield structured `degraded` health status rather than unhandled HTTP 500 crashes.
2. **Parallelized Telemetry Aggregation**:
   - Replaces sequential blocking HTTP calls in `/advanced/runtime-summary` with asynchronous parallel fan-out via `asyncio.gather(*[...], return_exceptions=True)`.
   - Total route latency capped strictly under **3.0 seconds** (down from >30s timeouts).

### 3.3 Universal SOTA Bootable USB Installer
1. **Declarative Image Generation**:
   - Flake target: `nix build .#nixosConfigurations.aqos-install-vm-plain.config.system.build.isoImage`.
   - Boots natively on UEFI Secure Boot systems, legacy BIOS, and virtual hypervisors (Proxmox, KVM, VirtualBox).
2. **Autonomous Hardware Fact Probing**:
   - `scripts/governance/discover-system-facts.sh` dynamically probes CPU architecture (x86_64, aarch64), GPU memory / layer offload limits, RAM constraints, and disk controllers.
   - Generates tailored `hardware-configuration.nix` and `facts.nix` in `/mnt/etc/nixos`.
3. **Partitioning & Encryption Contract**:
   - Full disk encryption via LUKS + TPM2 auto-unlock with a mandatory human recovery passphrase.
   - Plain ext4/ZFS layout option for non-volatile cloud VPS or disposable lab environments.
4. **First-Boot Zero-Secret Ignition**:
   - Sops-nix age key auto-provisioning flips secure services (firewall bouncer, switchboard signer, AIDB API keys) on at initial boot without manual key injection.

---

## 4. Adversarial & Failure Scenarios

| Scenario | Impact | System Defensive Behavior |
| :--- | :--- | :--- |
| **Concurrent DB Write Collision** | Multiple agents logging intent simultaneously to `oncall.db` | WAL mode enables concurrent readers while writers queue; timeout catches fallback to volatile `:memory:` without thread crash. |
| **Model Serving Exhaustion (OOM)** | `llama.cpp` APU offload exceeds available RAM | Dashboard telemetry signals degraded layer offload; Switchboard auto-routes to remote fallback lane; alerts trigger in Cockpit. |
| **Untrusted Input via Thought Stream** | Malicious command injection via agent prompt / thought line | HTML entity escaping + CSP strict policy (`script-src 'self'`); no `eval()` or unescaped innerHTML in `assets/dashboard.js`. |
| **Storage Failure / Degraded Disk** | Real hardware partition failure during boot | Installer performs rootless VM dogfooding and partition check before any real-disk touch. |

---

## 5. Definition of Done & 6-Dimensional Attestation

No slice under this plan is marked done until attested against:
1. **Integrated**: Dashboard routes and installer scripts wired directly into NixOS flake and systemd units.
2. **Turned ON**: Enabled and active in the running system (`command-center-dashboard-api.service` active).
3. **Functionally Validated Real-World**:
   - `verify-dashboard-apis.py` passes 97/97 endpoints HTTP 200.
   - `harness_qa/main.py 0` passes 207/207 checks (100% green across L1-L7).
4. **Observable**: Cockpit displays live Thought Stream, Intervention Dock, and System 1 P95 latency.
5. **Intervenable**: Operator can pause, steer, or resume active agent sessions directly from the UI.
6. **PM-Tracked**: Plan tracking accurately projected from git commits and live test output.
