# P2 — Recoverable delegation and execution boundaries

**DRAFT — pending independent design review, 2026-11-12 UTC.** Requirements R01, R04–R06. Parent [DESIGN](DESIGN.md); sources CF-01/02/08/09/12–15, RT-03/06 and L02 in the source ledgers. Reuse `agent-agnostic-factory`, `coordination-safety-worktree-isolation` and existing claim/dispatch records. Do not add a second scheduler or durable-execution platform.

## Outcome and bounded scope

After a worker or coordinator interruption, an operator sees the original task, bounded lease, actual process/worktree state, last durable evidence and a safe next action. Reconciliation can resume, retry or quarantine without accepting stale results or repeating unauthorized external effects. A git worktree separates repository edits; it does not establish kernel isolation. The known guard resolves paths but malformed/OSError handling was reported fail-open. Inspect the current exact source before assuming this historical finding persists.

Dependencies: P1 identity/outcome envelope; existing coordination safety acceptance; legitimate factory hook installation/composition before gated implementation. Approved rollout defers hook-manager composition: its proposed opt-in design is a separate DRAFT dependency, not an available workaround. Security activation and deployment remain owner-gated.

## Three slices and ownership

1. **P2a reconcile existing claims.** Make the existing `aq-claim` claim-before-edit contract and `aq-lease` records consistently mandatory before adding any lease behavior. Economical implementer adds only missing attempt identity and restart reconciliation to those existing dispatch records. Define expiry, stale-result rejection, maximum retry count and terminal unknown/quarantine. On restart compare durable claim, process, branch, workspace and evidence before deciding. Lost replies must not imply an operation never occurred.
2. **P2b close write-scope ambiguity.** Fix the existing guard producer if the fail-open finding reproduces. Reject malformed scope/path input, unresolved errors and escapes. Cover symlinks, alternate cwd, deleted paths and read-only review tasks. Record whether the enforcement point is cooperative routing, tool permission or actual OS confinement. Required untrusted execution uses an existing declarative sandbox with independently tested network/secret boundaries; otherwise explicitly defer that task class.
3. **P2c prove handback and merge isolation.** Reuse the existing branch/PR queue and test environment. Bind result to attempt and exact subject; repeated handback is idempotent. Keep worker artifacts and test mutations isolated; reject stale or foreign-branch evidence. External actions have scoped idempotency keys or an explicit human reconciliation state. No claim of universal exactly-once effects.

Accountable owner: coordination lead. Cheapest measured-capable local worker can prepare fixtures and inventory; economical Codex owns cross-component implementation. Independent runtime/security reviewer owns fault-injection expectations and verifies authority boundaries. Operator owns admission pause and owner-gated rollback. P2a precedes shared recovery writes; scope fixtures can be prepared in parallel. No new service without registered aq-qa integration check and live dashboard coverage in the delivery cycle.

## Executable acceptance

Freeze fixture hashes and expected outcomes before evaluation. Run two concurrent workers on distinct branches with conflicting file names and separate test artifacts. Each must produce only its own changes; one independent reviewer must remain read-only. A shared dependency failure must classify as infrastructure, not an agent defect. A reviewed old tree followed by a changed file must fail subject validation.

Interrupt at least: after durable claim/before launch; after launch/before result; after result/before acknowledgement; during test execution; and during merge handback. Restart the real coordinator in an isolated test deployment, reconcile, then inspect processes, claim records, branches, PRs and evidence. Across each fixture: at most one accepted final result, no duplicate external mutation, no lost raw evidence, no indefinite claim, and an explicit next action within a timeout frozen from the baseline. Repeat delivery of the same result three times and verify one accepted handback. Simulated effects test semantics; final acceptance must include a real isolated git/PR/test journey.

Malformed JSON, unreadable scope, symlink escape, cwd mismatch and guard exceptions must deny writes and expose a diagnostic. A legitimate in-scope edit must still succeed. For any claimed OS boundary, demonstrate denial of an unauthorized file, secret and network destination using harmless probes; no assertion from a worktree path alone. Unsupported runtime/provider must show unknown/deferred rather than inherit another adapter's pass.

Record all attempts/retries, human actions, actual routing and measured token/time costs including failed/replayed work. Dashboard/aq-qa shows running, stale, quarantined and unknown states from real records. Operator pauses admission, cancels one attempt without affecting another, and resumes only the intended subject. Independent reviewer verifies receipts and logs against fixture truth; no timestamp or test-expectation edits after results.

## Rollback, deferral and next session

Rollback owner pauses dispatch, preserves claims/artifacts, then uses the approved deployment/revert procedure. Reconcile before replaying any outstanding effect. Do not delete worktrees or raw evidence to make recovery appear clean. Older record versions become explicit unknown when authority cannot be reconstructed.

**Dated activation deferral, 2026-11-12:** no P2 runtime change, OS containment claim or restart proof is delivered by these documents. Coordination lead must attach live integration, enabled-state, E2E, observability, operator-control and projected-PM evidence before activation; security/rollback actions require the applicable owner grant. Tracker detection must reference exact future commit/review/activation subjects rather than hand-entered completion.

Next-session prompt: “Read DESIGN/P2 and the existing coordination-safety plan; pin current source and accepted subjects. Reproduce only the listed guard/recovery gaps. After P1 contract and independent scope freeze, implement the smallest missing producer behavior. Run isolated restart/duplicate handback and two-worker git/PR/test journeys. Return exact hashes, receipts, actual cost, operator controls and dated activation deferrals.”
