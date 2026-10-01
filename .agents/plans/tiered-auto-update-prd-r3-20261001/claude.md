# Claude (orchestrator) — tiered-auto-update-prd-r3-20261001

Scope: reconcile the owner directive (2026-10-01) with codex's review; recommendations for the freeze.

1. Tiers. Owner scope wins: frontier categories = agent CLIs (claude-code, codex, antigravity), IDE (vscodium), language toolchains, database client languages, SOPS CLI, kernel, performance tools. Codex's sequencing is adopted as the mechanism, not a narrower scope: promote each attr individually onto the fast lane only after attr resolution against pinned inputs + a build + its consumer test; one promotion per run. Core = everything else (systemd, nix, glibc, openssl/openssh, postgres/redis/qdrant servers, llama-cpp, mesa/firmware, sops-nix activation).
2. Kernel. Owner wants kernel on frontier; codex flags Renoir audio/GPU skew. Proposal: frontier kernel = newest *supported* line tracked by the pipeline (not blind `linuxPackages_latest` every run), staged build-only with owner-scheduled reboot and post-boot audio/GPU/inference probes; pending-reboot recorded separately. OWNER DECISION 2026-10-01: newest LTS series.
3. Health/rollback: adopt codex's gate set verbatim (exact-closure activation, 300s readiness, 3 consecutive passes, rollback to the recorded previous closure not blind --rollback, independent watchdog, no retry loop, no auto-reboot).
4. Cadence: adopt daily check, weekly frontier window, monthly stable window, admission lease with 15 min idle. Map "zero active agent jobs" onto existing signals (aq-loop LOOP_STATE, delegate registry running rows, llama /slots is_processing) — unknown = defer.
5. MVP cut agreed: no auto kernel switch, no model updates, no major tool-authority bumps (aq-pin-watch already routes majors to sign-off), no GC, no standalone home-manager switch.
6. aq-pin-watch (U1, committed 689efe1b) is the pin step inside U3; its validate-and-restore contract already matches codex's "verify, never disable checks".

VERDICT: PLAN_READY_WITH_FOLLOWUPS (kernel line decided by owner: newest LTS)
