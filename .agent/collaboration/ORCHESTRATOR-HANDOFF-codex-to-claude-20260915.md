# Codex → Claude orchestrator handoff — 2026-09-15

Owner requested the coordinator seat return to the now-available Claude. Codex is
pausing new implementation after this handoff. No Codex-owned background shell
or local dogfood job was started or remains running. The three collaborators
used this turn have completed. Shared checkout remains on `main`; no branch
switch, reset, deletion, rollback, or new deployment was performed for SR-3.

## Landed work

- `7547e8c4`: Claude's five-file db-4 F2 Qdrant scratch-GC slice independently
  reviewed by Codex and committed. Exact staged binary/full-index subject:
  `c051d59ceec78e27dd62d61388d3c0ea2faf1ba68c1222176b66d0054325b87b`.
  Commit hooks passed. It preserves the `agent-ctx-` prefix safety fence,
  unknown-age skip, dry-run, per-collection isolation and weekly declarative GC.
  The corrected document says 17 pruned + 1 skipped-unknown, not 18 pruned.
- `main` is `7547e8c4`, eight commits ahead of `origin/main` at last check.
  F2 is committed, not pushed or activated by this turn. Do not repeat it.
- Earlier `45efc6a0` Antigravity binary alias fix was accepted, pushed and
  deployed. Both `antigravity` and `antigravity-ide` exist live.
- Signed Lenovo firmware update succeeded: BIOS `R1MET64W (1.34)`,
  EC `R1MHT64W`; fwupd reports success. Both fans ramp and settle normally.
  Firmware anchor: `.agents/scratchpad/firmware-resume-20260914.md`.

## Crash evidence — do not overclaim causality

Two unclean boot endings today: Sep14 08:57:30 and 20:17:36 PDT. Neither
journal tail shows orderly shutdown, kernel panic, OOM kill, thermal trip,
MCE, NVMe reset or storage I/O failure. Services were answering successfully
immediately before the abrupt stops. pstore contains no surviving crash record.

The morning crash followed a long s2idle interval, resuming at 08:48:15
(~9 minutes before the stop). The evening crash followed resumes at 12:15:22
and 18:51:23 (~86 minutes before the stop). Every inspected resume emits AMD
DMCUB diagnostics and four Lenovo ACPI missing-symbol errors involving
`\\_SB.PCI0.LPC0.EC0.HKEY.MSCB`. This is the strongest correlation, not a
proven hard-reset root cause. The evening failure was AFTER the firmware
reboot/update; do not repeat the explorer's mistaken “all failures pre-update”
claim. Firmware efficacy still requires a measured lid-cycle soak.

Current kernel is 7.2.0; first crashed boot used 7.2.4. Locked project target
evaluates to 7.2, latest-stable. Current sleep is `[s2idle]`; kernel explicitly
uses the P14s Gen2 AMD s2idle firmware quirk. Keep lid sleep enabled.

Do NOT blindly restore `amdgpu.dcdebugmask=0x10`: it disables PSR but commit
`684733da` deliberately removed it and added a regression assertion forbidding
the default. No evidence justifies overriding that policy yet. Existing
`amdgpu.gpu_recovery=1`, disabled overdrive/HDR, TSC and SD PIO safeguards remain.

Antigravity 2.5.5 had three Electron NodeService SIGSEGVs today; older stable
1.23.2 also had four on Sep9–11. Auto-wake did not run around the crashes.
No useful coredump stack proves host-crash causality. Do not blindly downgrade
or disable auto-wake. Keep critical routing on healthy lanes; Antigravity is
already honestly degraded/advisory due stale exhausted quota + undrained claim.

## Prepared SR-3 slice — UNSTAGED, NOT ACCEPTED, NOT ACTIVATED

Codex-owned changed files:

- `.agent/PROJECT-SUSPEND-RESUME-RESILIENCE-PRD.md`
- `config/suspend-resume-workloads.json`
- `nix/modules/roles/ai-stack.nix`
- `dashboard/backend/api/routes/aistack.py`
- `assets/dashboard.js`
- `scripts/testing/harness_qa/phases/phase0.py`
- `scripts/testing/test-suspend-resume-contract.py`
- NEW `scripts/health/aq-resume-reconciler.py` (worker authored; Codex integration edits)
- NEW `scripts/testing/test-resume-reconciler.py` (same authorship)

Concrete finding: the old `llama-cpp-resume` oneshot was wanted by and ordered
after `sleep.target`, an entry-side transaction, not a reliable wake-side hook.
Prepared replacement holds `aq-suspend-resume-marker` active during sleep;
`StopWhenUnneeded`/`ExecStop` dispatches asynchronous
`aq-resume-reconcile.service` on wake. Reconciler triggers nonblocking llama
restart, bounds readiness to 180 seconds, and writes typed low-cardinality
telemetry to `/var/lib/ai-stack/telemetry/suspend-resume-health.json`.
Hardware State card and QA 0.14.1/0.14.2 project it. No raw journals/prompts/secrets
are persisted. Registry remains PARTIAL pending review/live validation.

Validation performed:

- Python compile + `test-resume-reconciler.py`: PASS.
- `test-suspend-resume-contract.py` + `--self-test`: PASS (four adversarial cases).
- `node --check assets/dashboard.js`: PASS.
- `git diff --check`: PASS.
- Initial Nix evaluation failed on undefined `repoSource`, then parse found
  undefined `aiGroup`; both corrected by store-materializing the script with
  `pkgs.writeText` and root-owned 0755 telemetry directory.
- `nix-instantiate --parse nix/modules/roles/ai-stack.nix`: PASS after fixes.
- Full Nix module evaluation has NOT been rerun after these fixes.
- `test-boot-stability-regressions.py` has a baseline failure at line ~187:
  missing health-spider `osi-layered` assertion. Not introduced by SR-3;
  do not silently credit this test as passing.
- No SR-3 Tier-0, exact-subject independent review, commit or live lid test yet.

Claude's next bounded actions:

1. Independently inspect the nine-file SR-3 subject; particularly prove systemd
   wake-side semantics and ensure failed restart cannot report stale-server
   readiness. Check journal-read failure is not misrepresented as zero errors,
   SIGTERM interruption persistence, hard deadline/input bounds, and final
   timestamp accuracy. These are review asks, not proven findings yet.
2. Run full Nix evaluation; fix only named critical correctness defects, then
   one bound acceptance + Tier-0. Keep unrelated staged/index changes out.
3. Commit with truthful implementer/reviewer identities; batch push/rebuild
   when safe. Activate and verify dashboard/QA before claiming compliant.
4. Three owner-coordinated lid cycles + normal-use soak; do not suspend the
   laptop without coordinating with the owner. If another hard stop occurs,
   use a separately reviewed single-variable display/kernel experiment.
5. Continue owner Phase-1 Foundations B/C + database F3; packaging/portability
   remains owner-paused to Phase 4. Do not restart the older fp-3 roadmap.

## Preserve unrelated work

Existing dirty files include issues-backlog F3 diagnosis, hot memory, prompt
registry, env-contract packaging residue, Antigravity receipts/claims, factory
restore plan/script/tests, archives and VM artifact. Do not revert or bundle
them into SR-3. Index was empty after F2 commit and remains intentionally
unstaged for this prepared slice.

## Separate durable config-parity worktree

`.codex/worktrees/agent-config-parity`, branch `fix/agent-config-parity`, holds
uncommitted coordinator/model/hook parity work. Initial independent review was
REQUEST_REVISION; fixes began but are not accepted. Need inspect actual status,
finish schema/SSOT tests and consumer compatibility, update live
`~/.codex/config.toml` deprecated `codex_hooks` with proper write authority,
then fresh strict-config doctor, one re-review and Tier-0. Do not merge it
without that. It is separate from the crash slice and should stay isolated.

Also retain the deployment model-readiness race: the earlier deployment
activated successfully but its readiness probe returned rc4 during cold model
load; automatic systemd recovery succeeded. Do not issue competing manual
restarts while the remediator is active.
