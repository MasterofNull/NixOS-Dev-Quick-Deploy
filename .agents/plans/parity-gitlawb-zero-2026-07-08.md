# Parity Gap Analysis — Gitlawb/zero vs NixOS AI Harness

Date: 2026-07-08
Subject: https://github.com/Gitlawb/zero
Status: analysis only; no external install or enablement performed

## Intake Verdict

`Gitlawb/zero` should be treated as a design-reference candidate, not an enabled runtime dependency yet.
It is an MIT-licensed terminal coding agent with a Go core, native sandbox helpers, stream-JSON headless
I/O, local sessions, provider/model management, plugins, hooks, skills, MCP, specialists, worktrees,
verification, usage, cron, and session search.

Do not install or expose it to agents until it has a normal capability-intake record with:

- pinned release/version or source commit
- supply-chain scan for Go, npm wrapper, install scripts, and helper binaries
- sandbox boundary review for `zero-linux-sandbox`, `zero-seccomp`, and browser/terminal helpers
- explicit tool allowlist
- no secret propagation from harness env into Zero subprocesses
- dashboard or `aq-report` visibility
- rollback path

## High-Value Lessons To Incorporate

### 1. Stream-JSON Agent Protocol

Zero's `zero exec --input-format stream-json --output-format stream-json` is a useful contract model:
every line is schema-versioned JSON, output events carry `runId`, unknown input fields are rejected,
permission requests/decisions are first-class events, and final status is represented by `run_end`.

Parity gap in this harness:

- We have agent-run events, PULSE, audit logs, dashboard replay, and delegation registries, but they are
  not one canonical bidirectional stream protocol for all lanes.
- Our Antigravity/file-A2A and local delegation paths still rely on per-tool conventions and loose files.

Candidate slice:

- Define `aq-agent-stream.v1` JSONL as the canonical lane adapter protocol.
- Map existing `agent_run_events`, PULSE, `delegate-to-local`, `delegate-to-antigravity`, and
  `aq-collab-round` events into it.
- Add strict schema validation and reject unknown fields for inbound automation.

### 2. Permission Events As A UX/API Primitive

Zero makes side effects visible: writes, shell, network, destructive actions, and out-of-workspace writes
are permission-gated, and prompt/deny/allow decisions are events.

Parity gap in this harness:

- We have capability intake, action policy, sandbox profile work, and dashboard controls, but permission
  requests are not uniformly represented as operator-visible objects across tools, models, MCP, and
  A2A lanes.
- Sandbox denials still appear as noisy tool failures in some contexts instead of a structured
  `permission_request` / `permission_denied` lifecycle.

Candidate slice:

- Create `PermissionDecision` records with `action`, `side_effect`, `risk`, `block`, `recoverable`,
  and `operator_decision`.
- Render active/past permission decisions in the dashboard and `aq-report`.
- Feed permission records into the planned CapabilityLease/zero-trust work.

### 3. Sandbox Grants Inspection

Zero exposes `zero sandbox policy` and `zero sandbox grants list`.

Parity gap in this harness:

- Our sandbox state spans NixOS modules, AppArmor, POSIX DAC, systemd `ReadWritePaths`, tool wrappers,
  Codex sandbox policy, and escalation rules.
- We have strong declarations, but no single operator-facing `aq-sandbox policy` and `aq-sandbox grants`
  view that explains the effective grants per lane/tool/session.

Candidate slice:

- Add `aq-sandbox policy --json` and `aq-sandbox grants --json`.
- Inputs: runtime isolation profiles, systemd unit properties, AppArmor profile names, writable roots,
  capability leases, current sandbox mode, escalation policy, and recent denial summaries.
- Dashboard card: "Effective Sandbox Grants" with pass/warn/deny categories.

### 4. Specialists As Scoped Subagents

Zero specialists are markdown manifests with front matter, tool categories, inheritance, optional model
override, and explicit restrictions: child specialists cannot spawn more specialists or author new ones.

Parity gap in this harness:

- We have skills, roles, domain instructions, local/remote lanes, and collaboration rounds, but not one
  compact project-local specialist manifest format that constrains tools per subagent.
- Our current round work is moving toward typed contribution envelopes; specialists would make dispatch
  targets more deterministic.

Candidate slice:

- Add `.agent/specialists/*.md` manifests with `name`, `description`, `extends`, `model`, `tools`,
  `risk_tier`, and `allowed_outputs`.
- Map specialist `tools` to existing tool bundles / CapabilityLease.
- Add tests that specialists cannot delegate recursively unless a policy explicitly grants it.

### 5. Background Task Metadata And Stale PID Handling

Zero background specialist tasks persist `.ndjson` stream output and `.json` metadata, and stale running
tasks are marked error on restart to avoid sending stop signals to recycled PIDs.

Parity gap in this harness:

- We have recently hit stale delegation task issues and parser drift around `delegate-to-local`.
- We have registries and output logs, but not a single durable background-task schema across local,
  Codex, Gemini/Antigravity, and opencode lanes.

Candidate slice:

- Add `background_task.v1` schema with `task_id`, `parent_session`, `pid`, `start_time`, `heartbeat`,
  `status`, `stream_path`, `output_path`, `exit_code`, and `stale_pid_policy`.
- Make `delegate-to-local`, `delegate-to-antigravity`, and `aq-collab-round` use it.
- Add restart reconciliation: stale `running` -> `error_stale_pid` with no blind `kill`.

### 6. Spec-First, Worktree-Isolated Runs

Zero has `zero exec --use-spec`, `--worktree`, `--resume`, and `--fork`.

Parity gap in this harness:

- We have PRD/plan gates, isolated worktree policy in concept, collaboration rounds, and spec variant
  packs, but the end-to-end operator command for "spec-first isolated implementation attempt" is still
  not as simple as Zero's headless interface.

Candidate slice:

- Add `aq-run --spec <path> --worktree --lane <profile> --output-format aq-jsonl`.
- Require validation plan before writes.
- Keep edits uncommitted in the isolated worktree for scoring, matching the eval lesson below.

### 7. Offline Agent Evals With Fixture Workspaces

Zero's offline eval format is especially relevant: tasks define prompts, fixture workspaces, expected
changed files, forbidden files, required trace events, verification commands, and scoring. Bench mode
copies fixtures into isolated workspaces and warns that agents should not commit during scoring because
commits hide changed files from `git status`.

Parity gap in this harness:

- We have `aq-eval`, validation registry, agent-run replay, and many regression scripts, but not enough
  fixture-workspace scoring for full agent behavior.
- Our agents often commit as a success condition; for evals, this should be disabled so changed-file
  scoring can work.

Candidate slice:

- Add `aq-agent-eval` fixture mode: copy workspace, initialize baseline, run lane command, score
  expected/forbidden changed files, required trace events, and verification commands.
- Explicitly forbid commits inside eval runs.
- Store reports under `model-evaluations` and dashboard them by lane/model/task.

### 8. First-Run Doctor / Provider Detection

Zero exposes `setup`, `providers list`, `models list`, and `doctor`.

Parity gap in this harness:

- We have `aq-qa`, `aq-report`, switchboard health, model catalog, and route aliases, but first-run
  and post-rebuild diagnosis still requires knowing multiple commands.
- The current Antigravity/Gemini blocker is exactly a provider doctor issue: switchboard is configured
  for Google Gemini, but the secret is not a valid Google AI Studio key.

Candidate slice:

- Add `aq-doctor providers --json`.
- It should check provider URL, secret file existence, secret type hint, non-empty key, model alias
  compatibility, smoke-call status, fallback behavior, and dashboard visibility.
- Add a dedicated Gemini check that reports "invalid Google API key" without printing the key.

### 9. Repo Map / Repo Info As Deterministic Context

Zero includes `repo-map` and `repo-info`.

Parity gap in this harness:

- We have understand-anything, wiki navigation, lean-ctx maps, and context cards, but the operator-facing
  "deterministic repo map for current task" is distributed across several tools.

Candidate slice:

- Add `aq-repo-map --json --scope <path>` that combines lean-ctx tree/signatures,
  understand-anything graph IDs, validation ownership, and capability surfaces.
- Use it as the first context packet for local/remote delegation.

### 10. Cron / Scheduled Agent Jobs

Zero has `zero cron` for scheduled jobs.

Parity gap in this harness:

- We have systemd timers, PRSI, discovery agents, warmers, and drop-zone daemons, but no single agent-facing
  schedule registry with per-job permission and output contracts.

Candidate slice:

- Add `aq-schedule list|add|disable --json` backed by declarative Nix/systemd timer generation.
- Include CapabilityLease and sandbox profile per scheduled job.

## What We Already Do Better

- Deny-by-default external capability intake is already stricter than Zero's public install path.
- NixOS declarative deployment gives reproducible service, profile, and sandbox wiring.
- Dashboard observability is broader than a terminal-only view: QA, services, routes, agent replay,
  scorecards, model freshness, and metrics are already live surfaces.
- Multi-agent round design is more explicit than Zero's specialist-only delegation model, especially
  after the F1/F2/F3 design rounds.
- Capability catalog + validation registry give strong governance hooks before activation.

## Security / Supply-Chain Notes

- Do not use `curl | bash`, npm `postinstall`, or Bun `trustedDependencies` as an intake path.
- Source-build review must cover Go modules, npm wrapper scripts, release helper code, sandbox helpers,
  local browser/terminal helpers, and any web-fetch provider.
- If Zero is tested locally, run it only in a throwaway worktree with no secrets in the environment and
  no write roots outside that worktree.
- Treat Zero's plugin and hook manifests as executable capability surfaces.

## Recommended Backlog Order

1. `aq-doctor providers --json` with Gemini/Antigravity invalid-key diagnosis.
2. `aq-sandbox policy/grants --json` effective sandbox explainer.
3. `aq-agent-stream.v1` JSONL protocol for lane interoperability.
4. `background_task.v1` registry with stale-PID reconciliation.
5. `.agent/specialists/*.md` scoped subagent manifests backed by CapabilityLease.
6. `aq-agent-eval` fixture-workspace scoring and no-commit eval mode.
7. `aq-run --spec --worktree` scripted spec-first isolated execution.
8. `aq-repo-map --json` deterministic repo map packet.
9. `aq-schedule` declarative scheduled agent jobs.

## Bottom Line

Zero is most useful to us as a compact reference for operator UX and protocol shape, not as a drop-in
replacement. The strongest lessons are: unified stream-JSON events, explicit permission events, sandbox
grant inspection, scoped specialists, durable background-task metadata, fixture-based eval scoring, and
provider doctor workflows. These align directly with our current F1/F2/F3 direction and should be
implemented as native harness slices under NixOS governance rather than by importing Zero wholesale.
