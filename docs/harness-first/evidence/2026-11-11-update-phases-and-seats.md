# aq-update split into prepare/deploy phases; RSI convene seat fixes

Date: 2026-11-11

Backlog entries: AQ-UPDATE-SUDO, RSI-SEATS, KNOWLEDGE-SYNC (`.agent/memory/issues-backlog.md`).

## 1. aq-update (AQ-UPDATE-SUDO)

Root cause: the sudo prompt for the deploy came at the end of a 30-60 minute unattended landing wait, so it timed out twice.

- `aq-update` (phase 1, prepare): refresh, verify, land through aq-land, sync. Never calls sudo. Records a `ready` ledger
  entry (`rev`, `cmd`) and prints exactly one `aq-update: READY ... run: aq-update --deploy` line. The run stays open.
- `aq-update --deploy` (phase 2): refuses unless the ledger has an open run with `ready`/`verify`/`land`/`sync` done, checkout
  HEAD equals the ready revision, and that revision's tree equals the verified tree. Then `sudo -v` once, aq-deploy-current,
  MCP baseline refresh, validate. Nothing is kept alive across the wait and no credential is stored.
- Manual deploy: if the running revision already equals the prepared one, `--deploy` says so, skips the rebuild and runs only
  baseline refresh and validation (the case that raised the route_handler.py integrity alert).
- `--deploy` does not re-check origin/main: it deploys exactly the verified, landed revision even if main moved since.
- `--resume` continues phase 1 only and never starts phase 2. `--dry-run` (also with `--deploy`) and the no-delta path are unchanged.
- Baseline failure hint now points at `aq-update --deploy`, which skips stages already done.

Tests: `scripts/testing/test-aq-update.py` (33 pass). New: one READY line + ledger record, deploy refusals (no prepared run, finished
run, HEAD moved), sudo -v once up front then baseline, sudo -v failure deploys nothing, manual-deploy path, deploy dry-run,
resume never deploys, flag combinations. Kill/resume cases now cover both phases. Against the previous aq-update 20 of them fail.

## 2. RSI convene seats (RSI-SEATS)

- Local seat (reworked): the slot queue's state, lock and lease-reservation dir now live in ONE shared subdirectory,
  `<main checkout>/.agents/delegation/scheduler/`, resolved by `scripts/ai/lib/scheduler_paths.py` (dependency-free; a linked
  worktree resolves to its main checkout; `AQ_DELEGATION_DIR` no longer affects it). `slot_queue`, the dashboard
  `/scheduler/queue` route and `aq-local-training-loop` all use that module, so the unit and shell jobs contend on the same
  flock and every reader sees the same state. One-time migration: under the lock, `scheduler-state.json` from the old location is
  copied in when the new file is absent (never overwrites); readers fall back to the old file until then. Lease-reservation markers
  are transient and are not migrated. Nix: exactly `.agents/delegation/scheduler` added to the unit's ReadWritePaths (not all of
  `.agents/delegation`), created by a tmpfiles rule next to the capability-audit ones. `.gitignore` covers the new dir.
- Gemini seat: `~/.local/bin/gemini` -> `agy`. Strings in the binary show an embedded ripgrep that is extracted to the user
  cache and a lookup of `~/.local/bin/vendor/...`, with `ANTIGRAVITY_DISABLE_EMBEDDED_RIPGREP` as the switch. Unit now sets
  `ANTIGRAVITY_DISABLE_EMBEDDED_RIPGREP=1` and has `pkgs.ripgrep` on PATH. NOT verified: the exact write that failed was not
  reproduced (the unit's journal is not readable without root, and running the CLI was out of scope); confirm with
  `aq-rsi convene probe` after the rebuild.
- `aq-rsi status` reads the unit's setting (`systemctl show -p Environment -p LoadState ai-prsi-rsi-dispatch.service`, no root)
  and prints `unknown` when it cannot; the caller's shell env is ignored. It also prints per-reason queue drops.
- Queue bound (`rsi_convene._prune_queue`, every tick): dedupe by incident (first wins); expire entries older than 3 days
  (at 2 rounds/day a 10-deep queue is already 5 days); drop entries whose incident is gone or no longer triggers (only when the
  incident ledger is non-empty); cap at 10 keeping the newest. Counts accumulate in `state["dropped"]`.

Tests: `test-slot-queue-wiring.py` (unit-style vs shell-style processes exclude each other; legacy migration; readers agree incl. worktree; Nix RW path + tmpfiles), `test-rsi-convene-rounds.py` (QueueBound x5, UnitSetting x3, unit
declares the env var and ripgrep; 33 pass). Against the previous code the slot tests fail and 8 convene tests fail.

## 3. Knowledge sync (KNOWLEDGE-SYNC)

Already fixed on main by #739 (2026-11-10, after the 2026-11-09 failure): `fetch_url` retries URLError/timeout/HTTP 429/5xx with
backoff (1,2,4s, 3 retries; `KNOWLEDGE_FETCH_MAX_RETRIES`), 4xx fails at once, and per-source failures are isolated.
`test-sync-knowledge-sources-retry.py` passes (8). No change made here. Residual: total backoff is about 7s, so a DNS outage
longer than that still fails the weekly run; raise `KNOWLEDGE_FETCH_MAX_RETRIES` if the next failure shows that.

## Validation run

test-aq-update 33/33; test-aq-update-tiers 8; test-slot-queue-wiring ALL PASS; test-rsi-convene-rounds 33; test-aq-rsi 9;
test-rsi-requeue, test-prsi-rsi-intake, test-eval-contention-guard, test-dashboard-no-false-values, test-api-client-gen, test-scheduler-lease-gate (7, paths updated), test-local-delegation-artifact (23),
test-aq-deploy-current-rev, test-sync-knowledge-sources-retry pass; `check-ci-test-coverage.sh` PASS.

Activation: aq-update change is live on the next owner run. Nix unit change (env var, ripgrep on PATH) needs a rebuild; the
convene seat fixes are unverified in the unit until then. Not run: tier0, full CI, real deploy, sudo.
