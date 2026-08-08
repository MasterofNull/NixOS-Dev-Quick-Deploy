---
doc_type: prd
id: herdr-agent-operations
title: Herdr Agent Operations Presentation and PTY Fabric
status: draft
owner: hyperd
date: 2026-08-08
priority: P0-high
---

# Herdr Agent Operations PRD

## Intent

Replace the never-adopted cmux-style terminal concept with a pinned,
declarative Herdr server/window implementation that automatically organizes
and displays AQ-OS orchestrators, expert reasoning teams, reviewers,
implementers, coders, researchers, local inference modalities, validation
runners, and monitoring surfaces.

Herdr supplies persistent real PTYs, workspaces/tabs/panes, remote attach, and
semantic terminal state. AQ-OS remains the authority for task identity,
lifecycle, leases, role/model lineage, review receipts, evidence, acceptance,
and release. A pane title or Herdr working/blocked/done heuristic is an
observation, never proof that a task was admitted, completed, or accepted.

## Architecture

```text
AQ-OS dispatch / TEG / review receipts / TaskRegistry (authority)
                   |
                   v
        allowlisted Herdr presentation adapter
                   |
        pinned local Herdr server + real PTYs
                   |
  control | reasoning | implementation | review | research | local | ops
                   |
      terminal observations -> AQ telemetry/dashboard (projection)
```

The standard workspace is `aq-os`. Tabs are deterministic:

- `control`: owner/orchestrator and current program tracker;
- `reasoning`: flat flagship/expert-team design and adjudication lanes;
- `implementation`: economical bounded coders/implementers by exclusive slice;
- `review`: independent reviewers and acceptance evidence;
- `research`: read-only explorers, OSINT, documentation, and security intake;
- `local`: local agent, logic inference, embedded retrieval, queues, thermals;
- `ops`: `aq-tui-dashboard`, Phase-0, journals, services, broker and GPU state.

Every managed pane label projects `task_id`, role, lane, slice, and worktree
from AQ-OS records. It never stores prompts, secrets, raw provider output, or
acceptance verdicts in pane metadata.

## Security and authority boundary

Herdr's local socket is powerful: it can send terminal input, launch/close
processes, alter layouts, manage plugins, and stop the server. Therefore:

1. The upstream `SKILL.md` and unrestricted socket API are not installed into
   general agent roles.
2. Agents do not receive mutation authority merely because they run in a Herdr
   pane. Confined worker cells scrub `HERDR_*`, hide the socket/config paths,
   and cannot execute the Herdr binary or connect to its control socket.
3. Only the AQ orchestrator/presentation adapter may create, label, focus, or
   close managed panes, and only from already-admitted task records.
4. `pane send`, `agent prompt`, process launch, plugin install/enable,
   integration install, server stop, worktree remove, remote bootstrap, and
   update operations are deny-by-default capabilities requiring separate
   reviewed grants.
5. Herdr automatic version checks and remote agent-manifest checks are disabled.
   The binary and manifests are pinned through Nix; no curl installer is used.
6. Session auto-resume of agents is disabled until the dispatch broker can
   reconcile every restored PTY against canonical task lifecycle and fencing.
7. Terminal scrollback/logs are sensitive local evidence, excluded from commits,
   RAG, ordinary telemetry labels, and remote transport by default.
8. Herdr failure cannot mutate canonical task state. AQ-OS detects presentation
   loss and can reconstruct layout from its own records.

## Delivery slices

- **H0 — intake and contracts:** pinned upstream/source/license/SBOM review,
  proposed capability record, authority matrix, layout contract, threat model,
  and golden projection vectors. No install or runtime.
- **H1 — default-OFF packaging:** pinned Nix flake/package, declarative config,
  user service/session, disabled updates/manifests/plugins/restore, read-only
  status wrapper, rollback. No agent launches.
- **H2 — monitored presentation:** pure TaskRegistry/review/local-state to layout
  projection, allowlisted reconciler, `aq-qa`, dashboard and Agent Ops health,
  stale/orphan/drift detection. Harmless shells/monitors only.
- **H3 — brokered agent panes:** dispatch broker/TEG launches admitted tasks into
  confined Herdr PTYs; worker cannot access Herdr socket; cancellation/fencing,
  receipts, worktree leases, and independent review proven end-to-end.
- **H4 — dogfood and cutover:** soak local/remote lanes, SSH attach, restart and
  reconstruction, then retire cmux-specific naming/code only after reference
  scan and archive procedure.

## Success gates

1. Closing a client leaves Herdr-hosted harmless canary PTYs alive.
2. Every visible managed agent maps to one canonical AQ task; dark tasks and
   orphan panes are visible defects.
3. No agent can use the Herdr socket to prompt another lane, spawn work, close a
   pane, install a plugin, or stop the server without an AQ capability grant.
4. Herdr semantic state is compared with registry/receipt truth; disagreement is
   shown, never silently normalized.
5. Phase-0 and dashboard report package pin, server/socket health, session,
   managed/unmanaged panes, role counts, drift, stale/blocked age, and last
   reconciliation result.
6. Update/manifest network egress, plugins, native session restore, and remote
   bootstrap remain off unless separately activated and observed.
7. Rollback stops the Herdr presentation service without killing canonical task
   records or losing accepted evidence; the existing TUI remains available.

## Non-goals

Herdr is not the task registry, dispatch authority, reviewer, model router,
permission system, worktree lease owner, evidence store, dashboard SSOT, or
replacement for the local inference/switchboard contracts.
