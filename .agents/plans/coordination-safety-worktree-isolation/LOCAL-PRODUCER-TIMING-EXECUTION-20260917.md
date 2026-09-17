# Local producer timing — bounded authorized slice

Status: PLAN_READY_WITH_FOLLOWUPS. Parent: `.agent/PROJECT-LOCAL-LATENCY-OBSERVABILITY-PRD.md`.
Baseline: f9ab7e429874eb32f91c04889aa7189daa213787. Owner: hyperd.

## Authority and objective

Owner explicitly authorized a separately independently reviewed change to the frozen
local dispatcher to record queue wait, request start, first visible response, and
completion timings, metadata only. This does not reopen the accepted pipeline-elapsed
projection or authorize model replacement, budget/admission/timeout changes, or prompt
and hidden-reasoning capture. Root is sole integrator; workers never stage/commit main.

The actual delegation path is dispatch.py DirectRunner or AgentRunner; AgentRunner
spawns aq-agent-loop, which calls agent_executor. The latter can make multiple model
calls. Wrapper elapsed, local slot waiting, model-call time-to-first-visible-content,
and whole-task completion are different observations and must not be conflated.

## Minimal implementation and ownership

Reuse existing progress/output/task identity and bounded monitor read patterns; stdlib
clocks/JSON only, no new service, endpoint, registry, dependency or environment variable.
Prefer existing helpers; a tiny shared timing helper is allowed only for the two real
producers if duplication cannot be avoided. Timing persistence must be best-effort,
bounded and content-free, and must not change inference success/status/control flow.

Terra owns dispatch.py, agent_executor.py, task_registry.py, assets/dashboard.js,
test-local-delegation-artifact.py, test-local-inference-l2b.py, and a focused producer
fixture/helper if needed. Reuse existing QA 0.10.9 and stream regression coverage;
register the focused producer fixture in the existing phase-0 checks if otherwise
unexercised. Root owns this execution packet and evidence/handoff. All edits occur
only in /tmp/aq-local-producer-timing-20260917; preserve concurrent unrelated work.
The protected L2B payload fixture pins dispatch.py source bytes. Necessary re-binding
of changed owned source hashes in local-inference-l2b-payload-golden.json is included
in this explicitly authorized producer change, only after unchanged payload vectors
and stream behavior pass. Preserve builder/settings hashes, vectors and assertions;
record old/new hashes rather than weakening the manifest gate.

## Frozen acceptance

- Record actual request start, first nonempty visible content and request terminal
  success/failure on the producer path. Ignore role-only, keepalive, usage-only and
  reasoning deltas for first-visible content. Do not add or expand stream-content
  capture. Label receipt versus flush semantics precisely; preserve existing writes.
- DirectRunner measures its actual local slot acquisition/poll duration, including
  timeout with no request started. This is local admission wait, NOT server queue or
  prefill time. Agent executor's unobserved local/server queue remains null.
- Per-call agent timing is correlated by existing task ID and call number. The monitor
  labels latest-call timing explicitly; no sum/whole-task TTFT or guessed decode rate.
- Replay has no live request/first-content observations; buffered/nonstreaming output
  does not claim streaming TTFT. Absent, malformed, oversized, symlink, mismatched,
  nonfinite, boolean, negative or unordered metadata fails to explicit unavailable.
- UTC timestamps may communicate event time; durations use one monotonic clock per
  call. Document suspend-excluded monotonic duration if applicable; do not change
  sleep, clock watchdogs or inference deadlines. Never subtract unrelated process
  clocks or historical receipts to fabricate timings.
- Existing monitor projects only allowlisted timing metadata and renders it in the
  current agent monitor card with units, phase labels and unavailable explanations.
  No prompt, response, exception body, arbitrary metadata or hidden reasoning leaks.
- Hermetic direct/SSE, no-content/failure, replay/buffered, multi-call and unsafe-receipt
  fixtures pass. Existing delegation artifact and stream regressions remain green.
  Independent non-author exact-subject PASS and guarded canonical Tier-0 precede
  accepted integration. A compact unchanged-profile read-only live probe measures
  the real producer after source tests; no coding-quality promotion is implied.

## Delivery and exclusions

Source, executable QA and monitor wiring ship together. Live deployed UI exposure is
a separately named activation follow-up; do not call the phase complete before it.
One bounded review batch; any unresolved finding gets a distinct follow-up slice and
truthful safe-at-rest preservation, not a same-slice review loop. No deployment,
restart, cleanup, destructive Git, secrets, model/payload/settings tuning or automatic
retry is included. Existing elapsed receipt compatibility must remain intact.

## Grounding evidence during implementation (not additional gates)

The existing local advisory task local-20260917-124946-uve07l was alive with a
last queued_local_delayed_depth1 receipt (142.3 seconds), subsequently aged while
no output existed. This does not establish its current queue/request phase;
DirectRunner's ten-content-chunk progress cadence can leave a prior queue receipt
visible during request work. Immediate request timing addresses that ambiguity.

aq-agent-loop creates an internal Task.id of aq-<epoch> (line 430), distinct from
the delegation registry local-<dispatch> ID. Agent timing correlation must preserve
that distinction and bind through the established output/delegation identity,
without changing task-ID generation or rejecting genuine producer receipts.

Independent design-only check found no critical gap. Antigravity delivered an
advisory PLAN_READY_WITH_FOLLOWUPS, verified generation8b524d47/outputb2159cd7;
its recommendations remain design input, not code acceptance or live proof.
