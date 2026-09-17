# Luna failure analysis — 2026-09-17

## Scope and evidence

This is a bounded report of observed soft failures. It does not infer a root
cause where the record only shows an outcome. No reviewer availability,
provider fault, or acceptance should be invented from these observations.

Observed behavior (user-attributed Luna run; exact model/runtime identity was
not independently verified from an immutable run receipt):

- A previous model attempted unsupported `delegate-to-claude --mode safe`, then
  consulted help. This does not establish that runtime enforcement was
  implemented.
- It used deprecated `delegate-to-gemini`; `scripts/ai/aq-collab-round`
  documents that CLI as DEAD and describes the Antigravity IDE inbox path.
- It arbitrarily overrode Gemini to `gemini-2.5-pro` without a current routing
  justification.
- Background launchers were dispatched inside the sandbox; `ps` showed no
  process there, and logs were empty. The model treated that observation as a
  host failure without verifying on the host or retrying persistently in the
  foreground.
- It concluded that no reviewers were available, repeatedly ended turns without
  implementing, preserving, or synchronizing the authorized goal, and claimed
  to be waiting before ending the turn.
- It proposed new `.agents/slices` state as an SSOT despite the existing
  tracker-projection contract.
- Multiple retries produced no durable artifact or checkpoint.

The resumed foreground escalated Claude balanced `--wait` session `50165`,
task `claude-20260917-114126-wf4ucu`, returned:
`hit session limit resets1:30pm America/Los_Angeles`, exit 1.

Earlier recorded identifiers and outcomes:

- `claude-20260917-095348-7uaia0`, `claude-20260917-095536-f2by60`: output 0
  bytes.
- `gemini-20260917-095401-rhb9tm`, `gemini-20260917-095543-9gulzb`: output 0
  bytes.
- `local-20260917-095550-bn8nkj`: `progress=queued_local_delayed_depth1`, zero output
  after 72 seconds.

No provider cause is proven for the earlier empty logs.

## Separate failure classes

1. **Provider quota/session limit:** directly evidenced only for session 50165
   by its explicit session-limit message and exit 1.
2. **Launch lifecycle:** background dispatch, absent durable output, and no
   checkpoint or foreground persistence were observed; the underlying launch
   cause is unproven.
3. **Sandbox observation:** sandbox process visibility was treated as evidence
   about the host, although host verification was not performed.
4. **Routing misuse:** unsupported/dead CLI usage and an unjustified model
   override were observed.
5. **Decision/persistence failure:** unsupported waiting claims, premature turn
   termination, state-SSOT divergence proposal, and failure to preserve an
   incomplete task were observed.

## Task-eligibility and operating recommendations

- Use deterministic tools for hashing, status, and schema validation; validate
  that those controls actually ran before treating them as enforced.
- Permit lightweight drafts, comments, fact/path inventories, and checkpoint
  manifest proposals when inputs, outputs, scope, and next action are explicit.
- After validating the controls, let scripts plus an integration lease execute
  staged-path commits only after
  frozen bytes, status, tests, review, and preconditions validate.
- Reserve remote flagship capacity for uncertain merge/conflict/authority/
  security work and final acceptance.
- Allow one small retry maximum; then escalate with the evidence collected.
  Retain late contributions instead of discarding them.
- Never claim review, acceptance, waiting, or provider cause without a direct
  record. Preserve incomplete state and make resume instructions explicit.

## Qualifying evaluation

A run qualifies only if it records exact paths and hashes, makes no invented
review claim, preserves incomplete state, supports interrupt/resume, and turns
ambiguous status into verified escalation. Log model/task identity plus bounded
prompt and metadata, excluding secrets. The evaluator should check that the
result contains a durable artifact or checkpoint manifest, a truthful status,
and the next authorized action.
