# Claude session handoff — 2026-10-02 (Opus 5.5, closing near weekly limit)

Branch `fix/rsi-takeover-20261002`. PR #366 MERGED (18:48Z). **PR #367 OPEN** with all later commits. Read this file, then `aq-resume`; do not hydrate the full HANDOFF/backlog.

## TOP PRIORITY (owner directive, end of session): agent/model-agnostic routing everywhere
The owner reiterated: "all actions and tasks should be able to be routed to the most appropriate agent/model, not just one" (Rule 18).
- Concrete violation: `prsi-orchestrator.py cmd_rsi_dispatch` accepts only lane codex|local, and `config/runtime-prsi-policy.json` has `rsi.repair_lane="codex"`. While Codex is out of quota, owner-approved repairs just wait (cooldown) instead of rerouting.
- Spec: replace the single `repair_lane` with an ordered, capability-tagged `repair_lanes` list (e.g. codex, claude, local) resolved at dispatch time via `config/model-coordinator.json` tiers. Skip lanes with an active cooldown/quota marker (generalize `_lane_cooldown_until` per lane; delegate-to-claude and delegate-to-local need equivalent quota/outage markers). Route to the next eligible lane and record the substitution in the receipt and in AGENT-CATCHUP-QUEUE.md. Never self-review: the repairing lane cannot be the acceptance lane. Prove it on a remote lane first (remote-first proofing), keep local as the floor.
- Audit the other single-lane hardcodes the same way: `delegate_*` defaults, `aq-loop` lanes, and the PRSI policy `rsi.repair_lane` consumers (rg `repair_lane|lane ==|--lane`).

## CVE triage result (`.agents/plans/cve-triage-20261002/TRIAGE.md`, sonnet analyst; not build-tested)
- All 269 are Grype CPE-only matches. No alerted CVE id appears in a nixpkgs patch name, so the false-positive calls are reasoned, not proven. Root nixpkgs is already the newest stable, so a lock refresh gains little; only nixpkgs-unstable is newer.
- Many alerts come from an OLD second copy of a package that sits beside a fixed one (gstreamer, ffmpeg 8.1.2 via wireshark-qt/qtmultimedia, libxml2, libjxl, alsa-lib, perl).
- Levers by package count: dismiss 21 (49 alerts); unstable low-effort 5 (14); fast-lane 5 (75); leaf 4 (35); no fix 19 (78); gnutls mixed (16); busybox low-priority (2).
- Batch 1:
  1. Promote pipewire (`services.pipewire.package`) and xdg-desktop-portal from unstable. Clears gstreamer, gst-plugins-good and alsa-lib, about 53 alerts. Needs an aq-qa audio smoke test.
  2. Resolve the ffmpeg 8.1.2 copy pulled in by wireshark-qt (global promote vs consumer leaf).
  3. Promote pgvector 0.8.6.
  4. Leaf-install perl 5.42.3.
- Later: playwright bundle; grouped dismissals or a `.grype.yaml` with reasons; libpng 1.2.59 (appimage-run) documented as accepted. Each batch = test + rebuild + rescan. Route implementation per Rule 17/18 (cheapest eligible lane), not Claude-only.

## Committed + pushed (PR #367)
- `d121c5a2` aq-approve inbox and `376dff4d` approval SOP + forced-prompt hook (owner-adopted: numbered list, owner says "approve 1 3" in chat, harness prompt = confirmation; ask rules alone do NOT prompt in auto mode).
- `ff124421` health-monitor evidence-lock ReadWritePaths.
- PRSI->RSI merge (`.agents/plans/prsi-rsi-merge-20261002/PLAN.md` + tracker): M1 `1cd5b206` single queue writer; M3 `2aa475c8` coordinator canonical queue, MCP list-only; M2+M5a `9b637768` Ralph PRSI retired, hint paths; M7 `0785d235` (Codex) execute endpoint dry-run-only.
- `584da7e4` rsi-dispatch: delegates honor AQ_DELEGATION_DIR, ~/.codex writable, infra failures refund attempts, `rsi-requeue` (owner-prompted).
- `c9315952` flake.lock chore (deployed lock).
- Owner rebuilt at ~15:1x PDT: all of the above is ACTIVE except what needs live validation below.

## UNCOMMITTED — finish first (status at write time; a commit was in progress)
1. Codex-quota containment (live already: the orchestrator runs from repoPath):
   - `scripts/ai/delegate-to-codex`: apostrophe-agnostic "hit your usage limit" detector (Codex prints U+2019).
   - `scripts/automation/prsi-orchestrator.py`: `_is_lane_unavailable` (refund attempt, stop run), `_lane_cooldown_until`, dispatch skips while `.codex-quota-cooldown` is active.
   - A Haiku agent is writing `scripts/testing/test-rsi-lane-quota.py`; check it exists and passes. Then tier0 and commit `fix(rsi-dispatch): codex quota cooldown...`. The backlog entry `codex-quota-limit-burns-rsi-attempts` is already appended.
2. Backlog appends (uncommitted): codex-quota entry, qa-0162 flake, etc. Commit with item 1.
3. Codex's own uncommitted docs: AGENT-CATCHUP-QUEUE.md, ai-stack/agent-memory/MEMORY.md, `.agent/memory/security-checks-20261002.md`, `rsi-session-handoff-20261002.md`. Preserve; Codex owns them.

## Live state to verify
- Cooldown file `/var/lib/nixos-ai-stack/optimizer/prsi/delegation/.codex-quota-cooldown` = `2026-10-03T02:25:00Z` (7:25 PM PDT reset, from the 15:16 receipt). Dispatch should report `skipped: lane_cooldown` until then.
- 4 owner-approved RSI repairs requeued at 15:15 (cf74048a, b1631709, 946f97d0, a05cfd88). cf74048a used 1 attempt on the quota error (2 left); the others are rsi_pending. After 7:25 PM, watch the first live repair end to end (`journalctl -u ai-prsi-rsi-dispatch`; queue row status). This is the first real proof of the repair lane.
- Health monitor: confirm the next run is error-free, then clear attention `attn-c6442c73` via the inbox (owner prompt).

## CVE work (owner: "massive uptick")
- 269 open code-scanning alerts, ALL Grype, all created 2026-10-02 against flake.lock. This is the first full NixOS-closure scan after Trivy was replaced (7a5bb5fc), not a wave of new vulns. 56 packages: 23 critical / 131 high. Worst: gnutls, libpng, perl, redis, libmad, openssh; volume: gstreamer, ffmpeg, libxml2.
- Snapshot: `.agents/plans/cve-triage-20261002/grype-alerts-20261002.tsv`.
- A Sonnet triage agent is writing `.agents/plans/cve-triage-20261002/TRIAGE.md`: per package, live version, patched-by-nixpkgs (false positive), lock refresh, fast-lane promote (nix/overlays/fast-lane*.nix, incl. leaf mode), no fix yet, or not in live closure. If missing, re-run that analysis.
- Next: after the c9315952 push the CI scan should drop the alerts fixed by the lock. Then batch 1 = criticals via fast lane, dismiss verified false positives with reasons, and feed residuals to RSI grouped per package (never 269 inbox items; rsi_sweep has no timer).
- Dependabot is disabled for the repo; Codex's security-checks doc lists the CI gaps (CodeQL, history secret scan, enforcement).

## Open plan slices
M4 (override reload: the approved routing change only reached the coordinator via a restart), M5b (archive legacy `/var/lib/nixos-ai-stack/prsi/*` and Ralph prsi-queue.json), M6 (read-only dashboard inbox). Producer bug noted by Codex: prsi_handlers.py repo_root derivations (~142, ~235) resolve ai-stack/.

## Pending owner items
- Rotate `hybrid_coordinator_api_key` via sops (partially exposed in the transcript this morning).
- Rule 18 fallback lane for RSI repairs while codex is out of quota (policy repair_lane=codex only).

## Lessons (also in memory)
- lean-ctx rewrite hook mangles `$(cat f)` and multi-line `python3 -c`: use heredocs.
- Append to backlog with a single trailing newline (the commit hook rejects a blank line at EOF).
- Timers run scripts from the working checkout: in-progress edits are live; keep the orchestrator importable at every save.
