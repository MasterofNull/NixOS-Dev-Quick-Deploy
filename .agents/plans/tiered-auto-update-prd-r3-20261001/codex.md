# Codex — tiered-auto-update-prd-r3-20261001
Scope: read-only architecture review of the four named files; recommendations, not runtime attestation.
Plan: assess tier boundaries, activation/recovery, resource budgets and scheduling; write only this verdict; verify <=40 lines.
1. Initial tiers: frontier = `antigravity` (unstable resolver `antigravity-ide`); retain the only individually approved promotion.
Core = all other attrs by default, explicitly `nix`, `systemd`, `glibc`, `openssl`, `openssh`, `sops`, `age`, `linuxPackages`, `mesa`, `linux-firmware`, `llama-cpp`.
Keep `vscode`, `nodejs`, `python3`, `rustc`, `cargo`, `go`, `postgresql`, `sqlite`, `ollama` on their existing pins initially; this is a proposed policy list, not a verified installed inventory.
Follow-ups: promote installed IDE/toolchain/agent CLI attrs one at a time after attr resolution, build and consumer integration tests; package-scoped environments avoid overriding system Python/Node globally.
Models are digest-pinned artifacts, not package attrs; exclude automatic model replacement. Keep SOPS activation integration stable even if the CLI later gains frontier eligibility.
2. Kernel: retain the current known-good kernel for MVP; follow up with a pinned supported LTS kernel package set, never automatic `linuxPackages_latest` promotion.
Treat kernel, modules, firmware and graphics as a compatibility unit; kernel-changing candidates are build/boot-stage only, with an owner-scheduled reboot and post-boot audio/GPU/inference checks.
No live-switch success can attest a new kernel; record pending-reboot separately from accepted deployment.
3. Health: require a healthy baseline, then test the exact built closure; do not rebuild from mutable source at activation time.
After switch allow at most 300 seconds for readiness; require three consecutive passes 20 seconds apart, with bounded individual probe timeouts.
Gate on aq-qa phase 0 PLUS authenticated coordinator→inference response, embedding→AIDB retrieval, switchboard routing, dashboard state, service-UID secret readability and operator access.
Require zero new failed units against baseline and no failure of any required unit; essential unhealthy baseline defers activation.
Rollback immediately on switch/activation error, missing required secrets, critical unit failure or lost operator-access probe; transient readiness/probe errors trigger rollback at the deadline.
Record and root the exact previous system closure/profile generation before switch; restore that target, not an assumed previous generation via blind `--rollback`.
Run recovery under an independent local watchdog; validate the recovered system with the same gates, stop further updates and alert if recovery fails. No retry loop or automatic reboot.
4. Cadence: daily metadata/pin checks; frontier activation weekly Sunday 02:00–04:00 UTC, stable-input updates monthly in that window; checks remain notify-only outside it.
Use a single update/deploy lock plus an authoritative agent-job admission lease; require zero active jobs for 15 minutes and recheck atomically before activation while blocking new admissions.
Unknown/stale activity state defers; process-name matching alone is insufficient. Recheck quiet hours on persistent-timer catch-up; never start a switch after the window closes.
Top failure modes and guards:
- OOM/swap thrash beside resident llama.cpp on 27 GB RAM: one build job, two build cores, cache-first; require >=8 GiB MemAvailable and >=4 GiB headroom above measured build peak; otherwise defer.
- Nix daemon builders escaping timer cgroups: enforce measured limits at the builder/daemon boundary; reject uncached heavy builds in MVP; never evict inference to satisfy the update budget.
- Store/boot exhaustion: preflight both filesystems against candidate closure/download/boot sizes plus reserve; retain previous closure and boot generation; no update-path garbage collection.
- SOPS key/config mismatch or permissions regression: validate declarations against encrypted key names, then bounded runtime readability checks as actual service UIDs without logging plaintext.
- GPU/audio kernel skew or incompatible llama.cpp: freeze that stack initially; later require Renoir inference/audio probes and <=12 GPU layers, with thinking disabled in inference tests.
- Partial activation/network loss/self-restart: durable transaction journal and independent watchdog; bounded activation, pinned recovery target, operator-access probe and persistent incident state.
- Concurrent edits or changed pins after review/build: isolated candidate checkout, immutable lock/pin digest, deployment lock, exact closure activation; preserve developer worktrees.
- Database migration or separate home-manager activation: generation rollback does not undo data/user state; exclude irreversible migrations and standalone home-manager switch from MVP.
- Supply-chain/hash drift: allowlisted input changes and intake tests; preserve existing artifact hashes unless an explicitly validated artifact version changes; verify new hashes, never disable checks.
- Existing script falsely reporting success: replace interactive unattended branches, make dry-build failure fatal and report health evidence; Chromium/version output is not a deployment gate.
MVP cuts: broad category promotion, automatic kernel/GPU/SOPS/inference/model updates, major tool-authority bumps, automatic reboot, GC and separate home-manager deployment.
Keep: default-off opt-in, one frontier attr, deterministic isolated candidate, baseline/resource gates, admission lock, exact-closure recovery drill, dashboard/run status and failure incidents.
Follow-ups before activation: resolve proposed attrs against pinned inputs; measure build/probe budgets; prove admission authority and watchdog survival; demonstrate one real switch and injected-failure recovery.
The existing notify-only staleness timer must remain notify-only; use its findings without silently granting it deployment authority.
VERDICT: PLAN_READY_WITH_FOLLOWUPS
