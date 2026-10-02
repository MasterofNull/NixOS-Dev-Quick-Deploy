# Freeze — tiered auto-update (2026-10-01)

Status: PLAN_READY_WITH_FOLLOWUPS
Lanes: codex PLAN_READY_WITH_FOLLOWUPS; claude PLAN_READY_WITH_FOLLOWUPS; local NEEDS_DECISION (resolved below); antigravity unavailable (inbox unconsumed; queued for catch-up).

## Decisions
1. Scope (owner): frontier = agent CLIs, IDE, toolchains, DB client langs, SOPS CLI, kernel, perf tools; core = everything else. Mechanism (codex): one attr promoted per run, after attr resolution + build + consumer test.
2. Kernel (owner 2026-10-01, superseding an earlier LTS answer): NEWEST STABLE kernel always (`linuxPackages_latest`, = existing `mySystem.kernel.track = "latest-stable"` policy), promoted from unstable whenever it is newer. Rationale (research 2026-10-01): AI-assisted discovery drives 400+ kernel CVEs/day, CISA KEV deadlines as short as 2 days, AI-assisted exploits weeks after fixes; fixes land in newest stable first. Patched != running: switch staged, `pending_reboot_since` recorded, U4 escalates past a reboot SLA; previous generations remain bootable; post-boot audio/GPU/inference probes.
3. Gates (codex): exact-closure activation; 300s readiness, 3 consecutive passes; rollback to the recorded previous closure under an independent watchdog; no retry loop; no auto-reboot.
4. Cadence (codex): daily notify-only checks; frontier window weekly Sun 02-04 UTC; stable monthly; admission lease = zero active agent jobs for 15 min (unknown = defer).
5. Memory (local's finding, reconciled with codex's "never evict inference"): llama.cpp holds ~24 GB of 27 GB, so builds cannot coexist with it. Inside the admission lease ONLY (inference provably idle), the pipeline stops llama-cpp before the build and the switch + health gate restarts it; if the lease cannot be proven, defer. Never evict an active inference.
6. MVP cuts: no broad category promotion, no automatic kernel switch, no model updates, no major tool-authority bumps (aq-pin-watch routes to sign-off), no GC, no standalone home-manager switch. Feature stays behind mySystem.autoUpdate.enable (default off).

## Slices
- U1 aq-pin-watch — DONE (689efe1b).
- U2 config/update-tiers.json + per-attr promotion with build check (feeds nix/overlays/fast-lane-manifest.nix).
- U3 unattended pipeline (systemd timer behind mySystem.autoUpdate.enable, default off) with decisions 3-5.
- U4 observability: last-run status, versions moved, rollbacks via aq-rsi status + dashboard card; failures -> RSI incident.

## Follow-ups before activation
Measure build/probe budgets; prove admission lease + watchdog survival; one real switch and one injected-failure recovery drill; antigravity confirmatory review on return.
