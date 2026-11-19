# PRD: Agent work durability across reboots, restarts and crashes

Status: MVP FROZEN, PLAN_READY_WITH_FOLLOWUPS (2026-11-19). Gemini round 1 gave REVISE (gemini.out); round 2 resolved all 17 findings (gemini-r2.out), and its 1 new P1 is closed in Revision 2. Lanes not available for this gate, recorded honestly: Codex (local daily cap reached) and local Qwen (power gate: on battery). Both are queued as catch-up reviews; per Rule 18 they are advisory unless they find a real defect. Owner: hyperd. Author: Simurg@claude/opus-5.5#da0ef470.
Tracker: `tracker.json` in this directory.

## Problem

Agent work that has cost tokens is lost or re-run after a reboot, a service restart or a crash.

Evidence from 2026-11-19:
- `/tmp` is tmpfs (`findmnt -no FSTYPE /tmp` = `tmpfs`). Claude Code keeps subagent transcripts, task outputs and the session scratchpad under `/tmp/claude-1000` (161 MB at the time of writing). Everything there is wiped on reboot.
- The orchestrator put a delegation brief in the scratchpad under `/tmp`. That broke the existing rule that briefs and outputs belong in `.agents/delegation/`. Nothing enforced the rule.
- The land runner and detached Gemini/local workers run as `setsid nohup` processes. They survive a closed terminal, but not a reboot, and nothing restarts them.
- User services do not start before login (`loginctl show-user hyperd -p Linger` = `Linger=no`).
- Claude subagents have no on-disk record of what they were doing. A subagent that is mid-task loses all its findings, and the orchestrator only knows it existed from its own context.
- Recorded Gemini runs (`.agents/sessions/*.json`) store `sessionId`, `title`, `agent` and `history`, but no task status or step, so they cannot be resumed from.

Already durable, and to be reused rather than replaced:
- worktrees under `.agents/delegation/worktrees/`, including uncommitted edits;
- `aq-land` per-PR checkpoints, which resume mid-PR (land log: "resuming PR #803: pushed, reviewed and receipted");
- the land queue directory;
- delegation outputs and receipts;
- RESUME.json, PULSE.log, AGENT-CATCHUP-QUEUE.md;
- the main Claude session transcript (`~/.claude/projects/...`).

## Goals

1. No agent work artifact that cost tokens lives only in tmpfs or only in process memory.
2. After a reboot, every unfinished dispatch is listed from disk alone, with enough state to continue from its last checkpoint rather than from scratch.
3. Long-running coordinators (the land runner, and resume itself) come back on their own after a reboot.
4. Before a planned reboot, one command says go or no-go and why.

## Non-goals

- Resuming a Claude subagent's live model context. The provider does not support this. Instead we persist the findings it produced, so a re-dispatch starts from them.
- Changing review, receipt or merge authority. Resume never merges, never mints receipts and never re-runs a step marked done.
- Replacing RESUME.json, PULSE.log or `aq-land` checkpoints. The ledger points at them.

## Design (MVP)

### S0: move Claude Code's temp root off tmpfs
- Claude Code reads `CLAUDE_CODE_TMPDIR` (verified in the 2.1.325 binary: `function ff(){let e=i.CLAUDE_CODE_TMPDIR;if(e)return e;return m()}`).
- Set it declaratively in `nix/home/base.nix` `home.sessionVariables` to `${config.home.homeDirectory}/.local/state/claude-code/tmp`. Create the directory with mode 0700, owned by the user.
- Retention: a user tmpfiles age rule, with the age set by an option (default 30d, no hardwired limit). Before the age rule removes a session directory, it is archived (Rule 12) as a compressed tarball under `~/.local/state/claude-code/archive/`.
- Takes effect for sessions started after the owner's home-manager switch. The running session keeps `/tmp`.
- Interim (done 2026-11-19): one-off copy of this session's directory to `~/.local/state/claude-code/snapshots/20261119T0912`.

### S1: work ledger
- One JSON file per dispatch: `.agents/delegation/ledger/<dispatch-id>.json`. Fields:
  - `id`, `lane`, `model`, `role`, `parent` (orchestrator session), `task` (one line);
  - `brief_path` (must be under `.agents/delegation/`), `worktree`, `branch`, `pr`;
  - `status`: queued, running, checkpointed, done, failed or abandoned;
  - `steps[]`: name, status, at, artifact path;
  - `findings_path`, `last_heartbeat`, `resume_policy`: auto, confirm or never.
- One small writer library (Bash plus Python bindings, sharing one schema file) does atomic write-then-rename. It is used by:
  - `delegate-to-codex`, `delegate-to-gemini`, `delegate-to-local`;
  - `aq-land` (pointing at its existing checkpoint, not duplicating it);
  - the land runner;
  - the orchestrator's Claude subagent dispatch. The orchestrator writes the entry on spawn, and the brief tells the subagent its ledger path.
- The ledger is runtime state and is gitignored. A tier0 check validates the schema and flags entries that have stayed `running` past their heartbeat window.

### S2: findings checkpoints
- Every dispatched agent appends its findings, as it works, to `findings_path`:
  - root cause found;
  - fix made, with commit sha;
  - tests run, with the pass/fail line.
- This is where the token cost actually lives. A re-dispatch after a crash gets the prior findings in its brief and is told to verify them, not re-derive them.
- The brief template (`slice-authoring`) gains the ledger and findings paths and the "append as you go" contract. The wrappers inject them automatically.

### S3: boot-time resume
- `aq-work-resume` lists unfinished ledger entries and acts on each according to its `resume_policy`:
  - `auto`: review and land steps re-enter `aq-land`, which already resumes from its checkpoint;
  - `confirm`: implementer work is printed as a re-dispatch command with its findings, for the orchestrator or owner;
  - `never`: left for the owner.
- Systemd user services, declared in home-manager:
  - `aq-land-runner.service` (Restart=on-failure);
  - `aq-work-resume.service` (oneshot, at boot).
- `users.users.hyperd.linger = true` lets them start before login. This needs the owner's rebuild.
- Guard: resume refuses to run while `aq-reboot-ready` reports a reboot in progress, and never resumes an entry whose worktree is missing. It reports such entries instead.

### S4: `aq-reboot-ready`
- Lists and gives a go or no-go:
  - `running` ledger entries;
  - unpushed commits in the delegation worktrees;
  - reviews that are in flight;
  - DB jobs (the existing "no rebuild during DB jobs" rule);
  - the land runner's state.
- `--checkpoint` asks running wrapper workers to flush their findings, then waits a bounded time.
- Its output feeds the in-cycle commands printed for the owner. Post-reboot commands still go only in the RESUME.json notes.

### S5: no-tmpfs guard for work artifacts
- The wrappers refuse `--prompt-file` and output paths outside `.agents/delegation/` (or the S0 Claude temp root), with an error message that names the right place.
- The inventory (see "Inventory" below) lists every tool that writes work state to tmp. Each is moved, or registered in WORKAROUND-REGISTER with a reason.

## Acceptance (frozen MVP journeys)

1. **J1:** start a Claude session after the switch, dispatch a subagent, then reboot. The transcript and task output still exist under `~/.local/state/claude-code/tmp`.
2. **J2:** dispatch a Codex or Gemini review through `aq-land`, then kill the land runner mid-review. After reboot, `aq-land-runner.service` is active and the PR continues from its checkpoint without re-running the finished steps. Evidence is the land log.
3. **J3:** a Sonnet implementer writes two findings, then is killed. `aq-work-resume` lists the entry as `confirm` and prints a re-dispatch brief that contains both findings.
4. **J4:** `aq-reboot-ready` says NO-GO while a ledger entry is `running` or a worktree has unpushed commits, and GO when neither is true.
5. **J5:** `delegate-to-codex --prompt-file /tmp/x.md` is refused with a pointer to `.agents/delegation/`.

## Risks and mitigations

- **Disk growth on persistent storage:** mitigated by the age rule plus archive-before-remove, the archive size reported by `aq-reboot-ready`, and an option-driven age.
- **Secrets in transcripts on persistent disk:** the directory is 0700 and outside the repo. It is never committed, and gitleaks already scans the repo, not this directory. The ledger holds paths, not prompt bodies.
- **Resume storms after boot:** resume runs entries one at a time through the existing land lock and load check (`load_ok` in the land runner). It does not start everything at once.
- **Stale or wrong resumes:** resume never touches review authority, never re-runs a `done` step, and refuses entries whose worktree HEAD moved since the checkpoint unless the step is idempotent.
- **Lean-ctx and hooks:** none of this changes lean-ctx policy.

## Rollback

- S0: remove the session variable; Claude falls back to `os.tmpdir()`.
- S3: disable the two user services. Linger can stay.
- The ledger is additive. Deleting the directory (archived per Rule 12) returns behavior to today's.

## Owner decisions needed

1. Linger plus user services in the next home-manager/NixOS switch. Recommended: yes.
2. Retention age for the Claude temp root. Recommended: 30 days, then archive.
3. Should `auto` resume cover review and land steps only, with implementer re-dispatch staying `confirm`? Recommended: yes.

## Inventory findings (read-only sweep, 2026-11-19; worker PID/queue handling unverified because one grep was hook-blocked)

Already durable:
- the delegation wrappers write to `$DELEGATION_DIR` = `.agents/delegation` (delegate-to-codex:62-71, delegate-to-gemini:41-44, delegate-to-local:70-72);
- `scripts/ai/lib/delegation-dir.sh:11` and `delegation_dir.py:8-16` refuse /tmp, /var/tmp and /dev/shm (so S5 extends an existing guard rather than adding one);
- `aq-land:134` has the same guard, plus the only true resume-from-checkpoint (aq-land:5,144,208,647).

Record-only, with no resume:
- `aq-collab-round` `round.json` (81-105);
- `aq-loop` `update_resume` into RESUME.json (518-646); `aq-resume` only prints it (24-29);
- the wrapper `registry.jsonl`; `dispatch.py repair-stale/status` reconciles but never relaunches;
- coordinator workflow sessions (`$DATA_DIR/workflow-sessions.json`, workflow_session_handlers.py:160-167,708-740) and graph runs (`/var/lib/ai-stack/hybrid/orchestration-graph-runs.json`, orchestration_graph_runner.py:32-62).

On tmpfs or in memory only:
- `hybrid-coordinator/workflow/agents_task_handlers.py:185-186`: spawned-agent state in `/tmp/agent-spawner/agent-<id>.json`;
- `workflow/runtime_manager.py:355,361`: run workspace root `/tmp/agent-runs` (options.nix:2418,2436 already declares `/var/lib/nixos-ai-stack/mutable/program/agent-runs`, so the code ignores its own SSOT);
- `config/workflow-automation.yaml` (lines 68,120,145,180,285-287): templates, success model, workflow state, workflow-store.db and logs all under `/tmp`;
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/consensus_engine.py` (line 41): `_sessions` only in memory;
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_executor.py` (line 106): `running_sessions` only in memory;
- `aq-session-start:349-356` and `scripts/ai/lib/triage_engine.py` (line 182): partial (temp copy or fallback);
- `aqd:677-679,721-723` and `safety_control_layer.py:122`: fixed-name `/tmp` scratch files (a collision risk, not a durability one; move to mktemp).

To verify: whether the hybrid-coordinator unit has `PrivateTmp` (if so, `/tmp/agent-spawner` is lost on every service restart, not only on reboot), and whether `/tmp` is written by the PrivateTmp units in mcp-servers.nix (1747, 1825, 2165, 2232, 2293), agent-reap, llama-router, workflow-deviation-broker, switchboard, command-center-dashboard, headroom-proxy and execution-cell-runner.

### S6: coordinator state off tmpfs
- Move the agent-spawner state, the run workspace root and the workflow-automation paths to the coordinator's `StateDirectory`/`DATA_DIR` under `/var/lib/ai-stack/`. Paths come from options.nix (the SSOT) via env, never hardcoded.
- Consensus sessions persist to `$DATA_DIR/consensus-sessions.json` with atomic writes.
- Fixed-name scratch files switch to `mktemp`.

### S7: coordinator restart reconcile
- On start, scan the persisted workflow sessions, graph runs and spawned-agent records.
- Mark records that say `running` but have no live task as `interrupted`, with a timestamp. Write a ledger entry for each (resume_policy `confirm`) and surface them in `aq-work-resume`.
- Never silently re-run a workflow step.
- Acceptance J6: start a workflow run, restart the coordinator, and the run shows `interrupted` in the API and in `aq-work-resume`, not `running`.

### S8: compressed archives and worktree retirement (owner request 2026-11-19: "compress the files and folders we are archiving")
Measured 2026-11-19 (disk 908G, 48% used):
- `.agents/delegation/worktrees` 45G across 304 worktrees, untracked;
- `.agents/delegation/outputs` 3.3G, untracked;
- `.agents/archive` plus `.agent/archive` 416M, 411 tracked files;
- git pack 66M.

Plan:
- One archiver, `aq-archive <path>`, for untracked work state. It replaces bare `mv` for Rule 12. It writes `<archive-dir>/<YYYYMMDD>-<name>.tar.zst` (zstd, reproducible `--sort=name --mtime`) plus a `.sha256` and a one-line index row (`archive-index.jsonl`: original path, size before and after, file count, date, reason). It verifies by listing the tarball before moving the original aside. Restore is `aq-archive --restore <row>`.
- Worktree retirement: a worktree whose branch is merged into origin/main or has a closed PR, has no uncommitted or unpushed changes, and has no running ledger entry is retired. Its diff summary goes into the archive index (the branch stays on origin), and then `git worktree remove` runs.
  - Removal never happens with dirty state or unpushed commits; those are listed for the owner instead.
  - This is the 45G item; most of it is rebuildable checkout content, not unique work.
- Outputs: delegation outputs older than the retention option (default 30d) and not referenced by an open ledger entry or PR are tarred per day.
- Tracked repo archives (`.agent/archive`, `.agents/archive`) stay uncompressed text. git already zlib-compresses them (the whole history is 66M). Binary tarballs would lose `rg`/diff and would not shrink history. New large untracked dumps never enter tracked archive dirs; a tier0 size guard flags any tracked archive file over a size option.
- Acceptance J7: `aq-archive` round-trips a directory (archive, restore, byte-identical by sha256). Worktree retirement retires only clean, merged worktrees in a dry run on today's set and lists every dirty one.


## Revision 1: changes adopted from review (Gemini, 2026-11-19)

The text below overrides the sections above wherever they conflict.

### MVP scope (phase D1)
MVP is S0, S1, S2, S3, S4 (read-only form) and S5. Phase D2 follows:
- S6 and S7: the coordinator's system-service privilege domain, which needs the PrivateTmp audit first.
- S8: archives and worktree retirement, delivered as its own housekeeping PR, because the owner asked for it.

All three stay in this plan as D2 and are not dropped.

### Changes, keyed by finding
- **F3 (P1), the age rule deletes without archiving:** S0 uses tmpfiles only to create `~/.local/state/claude-code/{,tmp,archive}` at 0700, with no age rule. Retention is a user timer plus a oneshot that calls the archiver, verifies the tarball (`tar -tf` plus sha256), and only then moves the source aside. The archiver lands in D1 as a minimal S0 helper and grows in S8.
- **F4 (P1), secret exposure on persistent disk:**
  - The parent, `tmp/` and `archive/` are all 0700, and the archiver runs with umask 0077.
  - `~/.local/state/claude-code/` is excluded from AIDB/RAG indexing and from any knowledge-sync path.
  - Archive retention is option-driven (age plus disk cap). Optional pre-archive redaction is deferred to D2.
- **F5 (P1), ledger races and pre-reboot entries:**
  - The ledger is append-only `<dispatch-id>.jsonl` event files, reduced on read, and written by one Python helper (`aq-ledger`) under `flock`. This also covers F16: there is no Bash writer.
  - Every event carries `boot_id`, `pid` and `pid_start_ticks`. An entry whose last `boot_id` differs from the current boot is deterministically `interrupted`.
  - Subagents only append to `findings_path`; they never mutate the ledger.
- **F6 (P1), boot race between the services:**
  - `aq-work-resume.service` is reconcile-only and fast. It marks prior-boot entries `interrupted`, idempotently enqueues `auto` items into the land queue, and writes a summary for `confirm` and `never` items.
  - `aq-land-runner.service` is the only executor, ordered `After=network-online.target`, with option-driven `RestartSec` and `StartLimitBurst`. A readiness check (gh auth, network, the review lanes) pauses the runner rather than failing PRs.
- **F7 (P1), Rule 14:** in D2 the coordinator never writes into the user's repo. Its reconciled `interrupted` state stays in its own `$DATA_DIR` and is exposed through its HTTP API, which `aq-work-resume` reads.
- **F8 (P1), no flush protocol:** `--checkpoint` is cut.
  - `aq-reboot-ready` is read-only plus a drain flag at `/run/user/$UID/aq-drain`. The flag is on tmpfs, so it clears on reboot, which also covers F11 (it cannot wedge resume).
  - The drain flag stops the runner from starting new steps and waits, for a time set by an option, for the active step to finish.
  - Interactive or external workers are listed as NO-GO until they exit.
- **F10 (P2), `CLAUDE_CODE_TMPDIR` not reaching every launch path:** set it via `home.sessionVariables` and also `systemd.user.sessionVariables` (environment.d), so GUI terminals and user units inherit it.
  - J1 is extended: verify from a new terminal and from the IDE terminal (`ls ~/.local/state/claude-code/tmp` after a subagent run).
  - Unverified: whether Claude Code also honours the variable from `~/.claude/settings.json` `env`. It is not relied on.
- **F15 (P2), command sprawl:** there are no new top-level commands beyond `aq-ledger` (internal).
  - Boot reconcile is `aq-resume --work` (the existing command, extended) and runs as the service's ExecStart.
  - The reboot check is `aq-resume --reboot-check`.
- **F16 (P2), conflicting SSOT paths in S6:** S6 paths come only from the `options.nix` agent-runs option already declared (`/var/lib/nixos-ai-stack/mutable/program/agent-runs`). The `/var/lib/ai-stack/...` suggestions above are superseded.
- **F17 (P3), hardwired windows:**
  - Every window becomes a declared option: heartbeat, drain wait, retention age and cap, worktree idle age (default 24h), `max_flood_prs`.
  - S8 worktree retirement defaults to `--dry-run` and adds the idle-age grace period.

## Revision 2 (Gemini round 2, 2026-11-19)
- **F3 clarification:** once the `.tar.zst` and `.sha256` are verified (`tar -tf` succeeds and the checksum matches), the uncompressed source is removed, so retention actually reclaims space. The verified tarball is the archived form (Rule 12 via a compressed move). If verification fails, the source stays.
- **Owner decision 4:** confirm this reading of Rule 12 (archive = verified compressed copy, then remove the original). Recommended: yes. Until it is confirmed, the archiver moves the original into `archive/` alongside the tarball, which reclaims no space.
- **D1 build order:** S0a (the `CLAUDE_CODE_TMPDIR` variable and 0700 directories) ships first, with these PRDs. Then S0b (retention timer and archiver), S1, S2, S5, S3, S4.
