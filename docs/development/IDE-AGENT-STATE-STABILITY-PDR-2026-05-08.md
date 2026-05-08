# IDE Agent State Stability PDR
Status: Proposed
Owner: AI Stack Maintainers
Last Updated: 2026-05-08

## Objective
- Stop VSCodium agent surfaces from freezing due to oversized local session/state corpora.
- Move long-lived orchestration context out of editor-local persistence and into harness memory.
- Define a permanent operating model so Continue, Claude, Codex, Gemini, Qwen, and Git surfaces remain usable during long-running development work.

## Scope Lock
- In scope:
  - Continue session growth
  - Gemini and Qwen extension-host state growth
  - Codex extension local state-db health
  - VSCodium extension registry churn (`.obsolete`, version drift, mutable vs immutable installs)
  - Harness/editor coordination rules that affect client-side persistence volume
- Out of scope:
  - Replacing VSCodium
  - Removing all AI extensions
  - Re-architecting the hybrid coordinator from scratch
- Constraints:
  - Preserve declarative-first configuration
  - Preserve required Continue routing and CLI bridge entries
  - Avoid hardcoded secrets or provider credentials in editor config
  - Keep remote/paid models out of autonomous background loops

## Problem Statement
The current editor-facing multi-agent workflow stores too much raw execution history inside local editor clients. Large Continue session JSON files, Gemini/Qwen extension global state, stale extension registry markers, and broken local state databases combine to freeze or stall VSCodium extension startup and interactive IDE work.

This is not a single-extension problem. The freeze pattern comes from the interaction of:
- long chat/session transcripts
- repeated agent retries and failed resumes
- agent-mode file snapshots and inline context capture
- editor-local persistence of orchestration artifacts
- stale extension lifecycle state
- broken extension-private state stores

## Evidence Snapshot
- Continue active session corpus previously reached roughly `252 MB` under `~/.continue/sessions`.
- One active Continue session contained `210` history entries and about `6.35M` JSON characters.
- Gemini VSCodium global state previously reached about `2.39 MB`; about `1.65 MB` was `workspaceChange` payload and about `0.36 MB` was `ideContext`.
- Qwen VSCodium global state previously held `59` conversations, including `46` empty sessions before pruning.
- Codex extension logs showed a hard failure opening `~/.codex/state_5.sqlite` because `migration 19` was already applied but missing from the current resolved migration set.
- VSCodium `.obsolete` contained stale versioned entries for Gemini, OpenAI ChatGPT/Codex, and Qwen, matching immutable/mutable version drift.

## Root Cause Analysis
### Primary Causes
1. Editor clients are being used as durable orchestration journals instead of thin interactive fronts.
2. Agent-mode extensions persist raw file snapshots and large context blobs that are useful transiently but expensive at restart.
3. Failed or repeated sessions create duplicate local artifacts faster than cleanup paths remove them.
4. Extension state retention is largely unbounded by size, recency, or failure count.

### Secondary Causes
1. Immutable declarative extension pins and mutable runtime installs can drift and create stale registry markers.
2. Broken local state DBs can stall extension initialization even when chat history volume is otherwise acceptable.
3. Temporary workspace paths and failed delegated runs can leave editor extensions retrying repo/introspection work that no longer resolves.

## Decision
Adopt a **thin-editor / thick-harness** operating model.

### Decision Details
1. The editor must stop being the primary long-term store for orchestration history.
2. The harness memory layer becomes the authoritative store for:
   - decisions
   - slice state
   - resumable context
   - multi-agent coordination notes
3. Editor-local state must be explicitly bounded by:
   - size
   - recency
   - session count
   - retry count
4. Runtime repair and pruning must be treated as first-class product behavior, not ad hoc cleanup.

## Design Principles
- Summaries over transcripts: persist structured working memory, not raw replay whenever possible.
- Phase boundaries over endless sessions: long tasks should checkpoint at slice boundaries and start fresh editor sessions when needed.
- Fail fast on broken local state: migrate or archive state DBs instead of repeatedly retrying corrupted lineages.
- Mutable where required: extensions that self-mutate at runtime should not also be pinned immutably in conflicting ways.
- Editor clients are interactive surfaces, not workflow ledgers.

## Remediation Strategy
### Track A: Immediate Containment
- Keep automated repair for stale `.obsolete` entries.
- Keep pruning Gemini `workspaceChange` and `ideContext`.
- Keep pruning empty and excess Qwen conversations.
- Archive oversized Continue session JSON files out of the hot path.
- Back up and reset broken Codex local state DBs when migration lineages diverge.

### Track B: Productized Retention Controls
- Add explicit retention budgets for editor-local corpora:
  - max Continue session size
  - max retained Continue sessions
  - max Gemini/Qwen global-state payload
  - max retries per resumed session
- Surface those budgets in docs and validation.

### Initial Budget Baseline
- Continue active session corpus: `16 MiB` total hot-path budget
- Continue largest hot session file: `8 MiB`
- Continue active hot sessions: `12`
- Gemini VSCodium global state payload: `1 MiB`
- Qwen VSCodium global state payload: `768 KiB`
- Stale AI `.obsolete` markers: `0`
- These are surfaced by:
  - `python3 scripts/ai/aq-report --format json`
  - `aq-qa 0 --json` via check `0.5.7`

### Track C: Workflow Contract Changes
- Require harness working-memory checkpointing after major slices.
- Prefer `summarize_context` plus memory save/recall over replaying full session history.
- Stop injecting full bootstrap banners, repo maps, and long tool output into editor transcripts when a compact reference will do.
- Treat repeated failed resumes as a signal to fork a fresh session from memory, not continue the same transcript.

### Track D: Observability
- Add health/reporting for editor-local corpus size and extension-state drift.
- Expose top offenders by extension and path in `aq-report` or `aq-qa`.
- Persist compact rescue telemetry so repeated freeze/retry loops are measurable in `aq-report`.
- Add detection for:
  - oversized Continue sessions
  - Gemini/Qwen state growth
  - stale versioned extension markers
  - broken Codex local state migrations
  - repeated rescue attempts that end with the same QA failures

### Track E: Rescue Workflow
- Provide a single bounded rescue entrypoint that:
  - checkpoints the current slice into harness memory
  - captures `aq-report` editor-state budget health
  - captures `aq-qa 0` editor/runtime health
  - optionally runs `vscodium-repair`
  - prints fresh-session resume commands
- Make checkpoint-and-fresh-session recovery the default after repeated editor retries or context-limit transport failures.

## Acceptance Criteria
- VSCodium launches without extension-host freeze on the standard development workspace.
- Continue active session directory remains within bounded size after sustained use.
- Gemini and Qwen global-state payloads remain below agreed thresholds after repeated agent interactions.
- Codex extension no longer fails on a stale migration lineage after repair.
- Repeated orchestration/retry flows checkpoint to harness memory instead of growing editor-local transcripts indefinitely.
- `aq-qa` or equivalent reports editor-local corpus health explicitly.
- `aq-report` exposes recent rescue frequency, repair/regeneration success, and top repeated QA failures.

## Risks
- Over-aggressive pruning may remove user-visible chat history that is still wanted.
- Fresh-session discipline may feel less convenient unless resume-from-memory is smooth.
- Extension behavior may change upstream and reintroduce new state-growth paths.
- Some failures may still originate in third-party extension bugs outside repo control.

## Mitigations
- Archive before delete for user session history.
- Keep repair operations reversible with timestamped backups.
- Validate on real workspaces, not only synthetic tests.
- Document when to use memory checkpoint + fresh session as the default recovery path.

## Alternatives Considered
### Keep current behavior and only raise context budgets
- Rejected: it increases persistence volume and postpones freezes rather than preventing them.

### Remove most AI extensions
- Rejected: it reduces capability but does not fix the underlying state-management problem.

### Treat this as only a VSCodium GPU/rendering issue
- Rejected: logs and state inspection show corpus/state persistence is a material contributor beyond rendering stability.

### Move all state to remote providers
- Rejected: conflicts with the local-first and quota-protection operating model.

## Implementation Notes
- Current repo guardrails already cover:
  - loopback host normalization
  - mutable runtime handling for Qwen
  - extension alias reconciliation
  - stale marker cleanup
  - Gemini/Qwen pruning
  - Continue session archiving
  - Codex DB backup/reset
- The next gap is governance and observability, not just more one-off cleanup.

## Linked Plan
- [.agents/plans/phase-27-ide-agent-state-stability.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/plans/phase-27-ide-agent-state-stability.md)
