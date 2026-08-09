---
doc_type: plan
id: herdr-agent-operations-h1
title: Herdr H1 Default-OFF Package and Operator Surface
status: draft
owner: codex-orchestrator
date: 2026-08-08
parent_prd: herdr-agent-operations
---

# Herdr H1 design packet

## Outcome

H1 makes a source-pinned Herdr binary and an AQ-owned read-only operator facade
available on NixOS without starting a server, opening a socket, creating a pane,
restoring a session, or launching an agent. Runtime activation remains a later,
separately reviewed action.

Upstream subject:

- release: `v0.7.5`;
- revision: `ef4c23f5775bb8cfec05f05d0844226ff959a07a`;
- source: `https://github.com/herdrdev/herdr`;
- license: AGPL-3.0-or-later, or a separately obtained commercial license;
- metadata retrieval: `nix flake metadata github:herdrdev/herdr/v0.7.5`;
- the final source and Cargo dependency hashes must be frozen by the H1 package
  review. A null metadata `narHash` is not accepted as a package hash.
- H1 implementation is blocked until the owner accepts AGPL-3.0-or-later
  obligations for the intended internal deployment or binds a commercial
  license record. The harness must not relabel the source as permissive.

## Authority boundary

Herdr is a persistent PTY and presentation fabric. It is not authorized to
admit work, mint leases, assign roles, select models, declare completion, accept
reviews, mutate Git, or release changes. AQ TaskRegistry, dispatch/TEG,
capability leases, review receipts, and commit gates remain authoritative.

The upstream CLI talks to a mutation-capable same-user socket. General workers
therefore receive neither the Herdr binary nor socket/config paths. H1 exposes
only AQ-owned, read-only status and configuration checks. Raw `herdr pane run`,
`send-text`, `send-keys`, `agent prompt`, `workspace close`, `server stop`,
plugins, integrations, updates, restore, worktrees, and remote bootstrap remain
denied.

## Declarative boundary

Use a dedicated Home Manager module, not a privileged NixOS system service:

```text
programs.aqHerdr.enable        = false  # package + immutable config + facade
programs.aqHerdr.runtimeEnable = false  # later activation; structurally inert in H1
```

H1 requirements:

1. `enable = false` and `runtimeEnable = false` are defaults.
2. The Home Manager module asserts `runtimeEnable == false`; evaluating
   `runtimeEnable = true` must fail with a typed H1 boundary message. A focused
   negative evaluation test is mandatory. A later activation slice must amend
   this assertion before it can implement runtime semantics.
3. `enable = true` installs the locally packaged pinned binary, an immutable
   XDG config, and `aq-herdr`; it does not start Herdr.
4. Any user unit has no `WantedBy`, socket activation, login activation,
   restart trigger, or pane/process launch in H1.
5. Generated config sets `onboarding = false`,
   `update.version_check = false`, and `update.manifest_check = false`.
6. No plugin, integration, native agent restore, remote bootstrap, update, or
   channel mutation is installed or invoked.
7. State/config directories are private to the primary user. No new environment
   variable is introduced merely to carry a path.
8. Rollback is declarative disablement. It never deletes Herdr state, AQ task
   state, evidence, or terminal records.

## Operator facade

H1 owns these commands only:

```text
aq-herdr status [--json]   configured/effective/runtime/package state
aq-herdr doctor [--json]   immutable-config, version, ownership and policy checks
aq-herdr version           pinned package identity
aq-herdr attach            H2 activation gate; H1 returns typed `not-activated`
```

The facade must not connect to the Herdr control socket in H1. JSON uses a
closed versioned object and distinguishes `disabled`, `configured-not-running`,
`unavailable`, `degraded`, and `running`; zero is never substituted for unknown.

## H2 operator experience frozen by H1

The named session and workspace are both `aq-os`. The workspace has seven tabs
in stable order:

```text
┌ AQ-OS / ATTENTION ───────────────────────────────────────────────────────┐
│ 1 CONTROL  2 REASONING  3 IMPLEMENT  4 REVIEW  5 RESEARCH  6 LOCAL  7 OPS│
├──────────────────────────────────────────────────────────────────────────┤
│ CONTROL                                                                  │
│ ┌ program / owner decisions ┐ ┌ authority + lifecycle mismatches ┐      │
│ │ tracker, gates, next slice │ │ blocked · stale · unmanaged      │      │
│ └────────────────────────────┘ └───────────────────────────────────┘      │
│ ┌ event timeline / accepted evidence / release queue ─────────────┐      │
│ └──────────────────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────────────┘
```

Tab responsibilities:

| Tab | Visible purpose | Canonical source |
|---|---|---|
| `control` | program tracker, owner decisions, attention queue | plan tracker + authority records |
| `reasoning` | equal flagship/expert lanes, dissent and unavailability | collaboration round/receipts |
| `implementation` | one bounded pane group per exclusive slice/lease | dispatch registry + lease |
| `review` | authors separated from independent reviewers | review receipts/subject hashes |
| `research` | read-only explorers, evidence intake, security research | admitted research tasks |
| `local` | agent/logic/embedding modalities, queue, thermals, progress | local inference contracts |
| `ops` | existing `aq-tui-dashboard`, Phase-0, services and hardware | sanitized operational projection |

Pane labels are projections only:

```text
<attention glyph> <role>/<lane> · <short slice> · r<record_revision>
```

They contain no prompt, raw output, secret, path, model reasoning, acceptance
claim, or unbounded task identifier. Text and color both convey state. Narrow
terminals abbreviate labels and use an overflow picker rather than compressing
all seven tabs into unreadable columns.

## H2 safe controls

After H2 implementation acceptance, and only after a separate owner-authorized
runtime canary/activation, the operator surface may add:

```text
aq-herdr plan --json
aq-herdr layout --check [--json]
aq-herdr reconcile --layout-only --expected-revision N --dry-run
aq-herdr open-monitor <allowlisted-monitor-id>
aq-herdr focus --task <canonical-task-id>
```

Before that activation, `attach`, non-dry-run reconciliation, and any socket
mutation return typed `not-activated`. Reconciliation is expected-revision
bound, dry-run by default, and can create or
label only the deterministic workspace, tabs, and allowlisted harmless monitor
panes. Unmanaged panes are visibly marked and never killed automatically.

## Observability and Service Coverage

Before runtime activation, one closed projection must supply:

- schema/version and freshness;
- configured, effective, runtime and package state;
- source revision, package version and protocol version;
- session state and redacted socket owner/mode/peer facts (never socket path);
- unit state/restart count;
- desired/applied layout revision and digest;
- reconcile result/reason and age;
- expected/present tabs;
- managed, unmanaged, orphan, missing and drift counts;
- role/modality counts and lifecycle mismatch count;
- terminal-exposure violations;
- effective booleans proving updates, manifests, plugins, integrations,
  restore and remote bootstrap remain disabled.

H2 is incomplete until the same projection is exercised by `aq-qa`, displayed
in `aq-tui-dashboard`, and visible in the web command center. High-cardinality
identifiers, prompts, output, argv, paths and secrets are prohibited metrics.

## H1 implementation ceiling

Freeze no more than these nine paths after independent design review:

1. `nix/pkgs/herdr.nix` (new);
2. `nix/home/herdr.nix` (new);
3. `flake.nix` (Home Manager module composition only);
4. `scripts/ai/aq-herdr` (new, H1 read-only surface);
5. `.agents/plans/herdr-agent-operations/H1-SUPPLY-CHAIN-REPORT.md` (new);
6. `.agents/plans/herdr-agent-operations/H1-DESIGN-PACKET.md`;
7. `.agents/plans/herdr-agent-operations/tracker.json`;
8. `docs/operations/herdr-agent-operations.md`;
9. `scripts/testing/test-herdr-h1-contract.py` (new).

Do not edit `flake.lock`, `config/env-contract.yaml`, system services, dashboard,
Phase-0, wrappers, dispatch, providers, or agent integrations in H1. If local
packaging cannot be made reproducible without another file, stop and amend the
reviewed ceiling rather than expanding it silently.

## Acceptance

- exact release/revision/source/Cargo hashes and license/SBOM evidence freeze;
- eval proves both options default false;
- eval rejects `runtimeEnable = true` throughout H1;
- `enable=true,runtimeEnable=false` builds package/config/facade with no unit
  activation and no socket/process/pane creation;
- config parser or exact generated-config oracle proves update and manifest
  checks disabled;
- `aq-herdr status --json` is closed, redacted and truthful with no server;
- negative tests prove mutation commands are absent from the facade;
- focused tests, Nix evaluation, package build and Tier-0 pass;
- an independent reviewer issues PASS over the exact candidate;
- no deployment, service start, live socket, provider, agent launch or network
  use is credited as H1 acceptance.
