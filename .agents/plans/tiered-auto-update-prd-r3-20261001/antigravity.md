# Antigravity — tiered-auto-update-prd-r3-20261001

Scope: Architecture & PRD review for unattended tiered auto-update on 27GB APU host.

1. Initial Package Tiers:
   - Frontier: Fast-lane agent CLIs (`antigravity-ide`, `claude-code`, `codex`), IDE (`vscodium`), and developer toolchains (`rustc`, `cargo`, `go`, `nodejs`, `python3`). Promoted individually only after attr resolution against pinned inputs, isolated build, and consumer test pass.
   - Core: Infrastructure and service daemons (`nix`, `systemd`, `glibc`, `openssl`, `openssh`, `sops-nix`, `postgresql`, `redis`, `qdrant`, `llama-cpp`, `mesa`, `linux-firmware`).
   - Excluded: LLM weights (digest-pinned models, not nixpkgs packages).
2. Kernel Strategy:
   - Adopt latest-stable policy per Owner Directive 2026-10-01, but strictly staged as build/boot-stage candidate.
   - Unattended reboot is forbidden; pending-reboot recorded separately for operator-scheduled maintenance with post-boot Renoir GPU/audio and llama.cpp inference validation.
3. Post-Switch Health Gate & Rollback Triggers:
   - Target exact built closure (no mutable source rebuilds during switch).
   - Readiness window: <=300s, requiring 3 consecutive passes 20s apart across `aq-qa phase 0`, coordinator->llama inference probe, AIDB vector retrieval, switchboard routing, and service-UID secret readability.
   - Rollback: Instant rollback to recorded previous closure hash (never blind `--rollback`) on activation failure, probe timeout, or missing secrets. Monitored via independent local watchdog; zero automatic retry loops.
4. Cadence & Agent-Activity Guard:
   - Daily metadata/staleness checks; weekly frontier window (Sunday 02:00–04:00 UTC); monthly core window.
   - Authoritative admission lease: require >=15 minutes of verified zero agent activity (`aq-loop` idle, delegate registry empty, llama.cpp `/slots` inactive). Any unknown/stale activity signal defers the window.
5. Top Failure Modes & Host Guards:
   - RAM Pressure / Swap Thrash (24GB llama.cpp resident on 27GB RAM): Restrict builds to 1 job / 2 cores; require binary cache hits for heavy packages (no uncached compilation beside resident LLM); require MemAvailable >= 8 GiB or defer.
   - SOPS Decryption Failure: Pre-switch validation of key declarations and post-switch non-root UID readability probe without logging plaintext.
   - Renoir GPU/Audio Driver Skew: Keep graphics/kernel as atomic compatibility unit; enforce offline probe before release.
   - Filesystem Exhaustion: Preflight check for >=10 GiB free in `/nix/store` and >=500 MiB in `/boot`; forbid update-path GC.
6. MVP Cuts:
   - Cut automatic kernel switch/reboot, model weight updates, standalone home-manager switches, major tool-authority bumps, and automatic garbage collection.

VERDICT: PLAN_READY_WITH_FOLLOWUPS
