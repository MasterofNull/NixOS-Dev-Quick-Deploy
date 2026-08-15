# AQ-OS Herdr operator workspace

Status: H1 implementation candidate; the raw Herdr CLI is not exposed or activated.
Owner: AI Stack Maintainers
Last Updated: 2026-08-08

Herdr will be the persistent terminal presentation layer for AQ-OS. It keeps
operator windows and harmless monitors alive across terminal disconnects while
AQ-OS remains authoritative for task admission, roles, leases, reviews,
completion, and releases.

## The planned daily workflow

The controls in this section are provisional until H2 acceptance and a separate
owner-authorized runtime canary/activation validate them against the pinned
binary. H1 exposes inspection only; `attach` returns `not-activated`.

After that separate activation, the normal entrypoint is expected to be:

```bash
aq-herdr doctor
aq-herdr status
aq-herdr attach
```

`attach` is designed to open the named `aq-os` session and workspace. Persistent
detach/reattach behavior must pass a live canary before this becomes an
operational guarantee.

Do not use `herdr server stop` as a routine detach operation. Do not use raw
`herdr pane run`, `agent prompt`, plugins, integrations, worktrees, restore,
updates, or remote bootstrap for AQ-managed work. Those bypass AQ admission and
evidence controls.

## Provisional navigation

These upstream defaults are a usability target, not yet an AQ-OS acceptance
claim. The H2 live canary must verify each binding, mouse behavior, narrow
terminal behavior, and detach semantics before the guide is promoted to active.

| Action | Control |
|---|---|
| choose a tab | `ctrl+b`, then `1`…`7` |
| next / previous tab | `ctrl+b`, then `n` / `p` |
| workspace and pane navigator | `ctrl+b`, then `w` |
| detach safely | `ctrl+b`, then `q` |
| show Herdr key help | `ctrl+b`, then `?` |
| mouse navigation | click tabs/panes; drag split borders |

The seven tabs are stable: `control`, `reasoning`, `implementation`, `review`,
`research`, `local`, and `ops`. The `control` tab answers “what needs attention
next?”; `ops` hosts the existing `aq-tui-dashboard`, which remains the detailed
Agent Ops monitoring authority.

## Reading state correctly

Herdr may infer that a terminal looks `working`, `blocked`, `done`, or `idle`.
That is a visual observation. AQ-OS task records and review receipts decide the
actual lifecycle state. If they disagree, the pane is marked as drift; the
system never silently treats the visual state as truth.

Expected attention semantics:

| Marker | Meaning | Operator response |
|---|---|---|
| healthy | AQ record and presentation agree | no action |
| needs-review | implementation ended; independent receipt absent | inspect Review tab |
| blocked | canonical task declares a blocker | inspect evidence, do not infer from shell |
| stale | progress age exceeds lane-specific budget | inspect task progress before canceling |
| drift | registry and presentation disagree | run `aq-herdr layout --check` |
| unmanaged | pane was not created from an AQ projection | keep visible; reconcile manually |
| unavailable | source cannot be read | treat as unknown, never healthy zero |

For slow local inference, inspect step progress before intervening. A 30–40
minute local-agent task can be healthy on the current APU; elapsed wall time
alone is not a cancellation signal.

## Safe inspection commands

After `programs.aqHerdr.enable = true` is separately applied through Home
Manager, H1 exposes only the read-only `aq-herdr` facade. The raw `herdr`
binary is deliberately absent from the shared user PATH. These commands do not
invoke Herdr or connect to its control socket; they report the sealed H1
build/config boundary:

```bash
aq-herdr status
aq-herdr status --json
aq-herdr doctor
aq-herdr version
```

`aq-herdr attach` is present only to return the typed `not-activated` result
with exit status 3. It does not attach, start, restore, or mutate a session.

H2 implementation may add projection and layout inspection. Attach and
non-dry-run mutation remain unavailable until the separate runtime activation:

```bash
aq-herdr plan --json
aq-herdr layout --check
aq-herdr reconcile --layout-only --expected-revision <n> --dry-run
aq-herdr focus --task <task-id>
aq-herdr open-monitor agent-ops
```

The initial reconciliation is always a dry run. Managed layout changes require
an expected AQ record revision. Unknown panes are reported, not killed.

## Existing monitoring remains available

Herdr does not replace these commands:

```bash
aq-tui-dashboard
aq-tui-dashboard --matrix
aq-tui-dashboard --focus <task-id>
aq-tui-dashboard --json
aq-qa 0 --machine
```

The default Herdr sidebar and default AQ dashboard are redacted. Prompt/output
inspection remains an explicit operator drill-in through `--matrix` or
`--focus`; it is not copied into pane labels, metrics, RAG, or normal logs.

## Recovery

If the Herdr presentation layer is unavailable, continue with
`aq-tui-dashboard` and the ordinary AQ CLIs. AQ records, leases, evidence and
accepted work do not depend on Herdr. Declaratively disabling Herdr must not
delete state or terminate canonical tasks.
