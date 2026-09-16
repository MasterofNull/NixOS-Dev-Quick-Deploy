# Local final-answer containment

Status: implementation frozen after P0-A `d4d299e6`; final disposition is bound
to the exact subject in commit review evidence, not assumed here.
Date: 2026-09-16
Parent: PROJECT-LOCAL-DELEGATION-RELIABILITY-PRD.md

## Measured defect

`local-20260916-093529-0vprsd` recorded `done`, 256 output tokens and an
existing zero-byte output artifact. The direct dispatcher accepts stream
completion without checking whether it captured a final answer. It discards
finish-reason and reasoning fields, so neither truncation nor reasoning-only
output is proven. This task earns no review credit.

## Frozen scope and ownership

Use existing registry and wrapper mechanisms, with no new dependency:

- `scripts/ai/lib/task_registry.py`
- `scripts/ai/delegate-to-local`
- `scripts/testing/test-local-delegation-artifact.py`

Do not edit the frozen `scripts/ai/lib/dispatch.py`, change inference budgets,
retry inference, extract hidden reasoning, or rewrite historical registry rows.
Other agents may work in this tree; preserve their changes and claim these
paths before editing. Do not stage, commit or switch branches as implementer.

## Required behavior

1. For **local-direct only**, a persisted terminal `done`/`completed` row with
   an observed existing whitespace-empty answer artifact has read-only observed
   status `failed`, reason `missing_final_answer`, stage `response_contract`.
   Preserve the persisted source status and existing token metadata.
2. Never apply this inference to agent/edit tasks, running tasks, nonempty
   answers, missing historical artifacts, symlinks or unreadable artifacts.
   Reuse safe output-path resolution and bounded regular-file inspection;
   artifact uncertainty is not proof of an empty final answer.
   Gate using the existing registry `agent == "local-direct"` field. A
   whitespace-only prefix of an oversized file does not prove an empty answer.
3. Foreground direct delegation must not audit success or return zero after an
   empty answer. Emit a bounded metadata-only diagnostic and audit failure;
   preserve session saving and consult cleanup on both terminal paths.
   This foreground change applies to explicit `--mode direct`; automatic-mode
   resolution still receives the registry overlay without a wrapper redesign.
4. No prompt, answer content, secrets, reasoning or exception values in diagnostics.
   A token count does not establish response content or finish reason.

## Acceptance and existing observability

Hermetic tests cover empty/whitespace answers, nonempty answers, missing and
unreadable artifacts, non-direct task compatibility, terminal-state filtering,
unchanged registry bytes, bounded artifact reads and foreground cleanup/error
versus success. Run the existing delegation-artifact fixture and syntax checks.
Existing QA 0.10.9 already runs this fixture in both QA registrations. The
existing dashboard local-agent monitor consumes `TaskRegistry.monitor_payload`;
verify that its observed status and typed reason reach that surface. Do not
claim a new dashboard service is needed or that an untouched deployed process
has reloaded source.

Root integration runs live machine monitoring, focused QA and Tier-0, obtains
one independent terminal review, and commits this slice separately. Nonblocking
findings become the next slice. Full transport receipt/finish-reason diagnosis
requires a separately authorized frozen-manifest change; containment does not
claim to fix local model answer quality.

## Planning contribution

Claude foreground task `claude-20260916-115916-r2mnky` returned
PLAN_READY_WITH_FOLLOWUPS: safe read-success detection, bounded inspection, exact
agent discriminator, monitor stage projection and explicit foreground-mode scope.
These are in-scope implementation requirements, not a new planning cycle.
Root corrected its prefix-read suggestion: classify only a complete safely
inspected artifact within the bound; oversized/uncertain artifacts stay unchanged.
Background task `claude-20260916-115842-od01y1` exited without an artifact and
earns no review credit. Source preflight was by the independent inventory lane.

## Implementation and validation checkpoint

Implementer: Codex `/root/ft3_greenfield`; root owns integration and this brief.
The shared inspector uses a regular-file/no-symlink descriptor, inode identity,
complete reads within 64 KiB and pre/post file-stat checks. Uncertainty remains
unclassified. Only exact terminal local-direct entries get the read-only overlay;
monitor tasks project `stage`, and existing nonempty/failure inference is unchanged.
Explicit foreground direct delegation audits error, saves session, releases the
consult and exits nonzero for a confirmed empty answer. Dispatcher stays frozen.

Implementer measurements: artifact fixture 20/20 PASS, 13 documented pre-existing
reverted lifecycle skips; Python/Bash syntax and whitespace checks PASS. Live
read-only `delegate-to-local --status local-20260916-093529-0vprsd` reports
`failed`, persisted `registry_status=done`, `missing_final_answer`, and
`stage=response_contract`. No historical row was rewritten.

QA identifiers are check IDs, not CLI phase arguments: `aq-qa 0.10.9 --machine`
returned unknown phase and is not PASS evidence. Registered integration runs
through supported `aq-qa 0 --machine` during the final Tier-0 gate. The recent
monitor window omitted the original task, so targeted status was used; fixtures
verify the same projected metadata in monitor_payload. Deployed dashboard module
reload remains unperformed. Final review and gate results belong in commit evidence.
