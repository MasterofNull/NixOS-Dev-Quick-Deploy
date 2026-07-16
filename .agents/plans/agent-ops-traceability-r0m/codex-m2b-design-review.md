# Codex architecture review — Agent Ops Traceability M2B

Reviewed packet SHA-256: `cce83b39c147423756c0d3187b2ad2f5db353645e73660625b27d448f01d11ce`
Base: `57b87e2d`
Date: 2026-07-16
Verdict: **REQUEST_REVISION**

## Blocking findings

1. **The receipt boundary is not implementable across the proposed Bash/CLI topology.** The packet
   requires an opaque process-local attachment receipt that is invalid after serialization, while
   the Bash wrappers necessarily invoke `aq-delegation-registry attach-process` as a separate
   process and receive its result through stdout. Either the receipt becomes serialized and
   replayable, or the wrapper cannot pass it to `ExecBarrier.release()`. PID/start-time arguments
   must not be reintroduced as an ersatz receipt.

   Revise the design around one in-process launch broker operation that owns begin, projection
   preflight, fork/barrier descriptors, PID/start-time observation, transactional attachment, receipt
   validation, release, wait, and terminal transition. Shell wrappers may supply provider argv and
   bounded metadata to that broker, but they must never receive or transport the receipt. The broker
   must not invoke through a shell string.

2. **A commit is not an activation boundary for directly executed worktree wrappers.** An implementer
   editing four live wrapper paths sequentially creates a partial cutover before staging or commit.
   “One reviewed commit” therefore does not satisfy the packet's own atomic-adoption invariant.

   Split delivery into a dormant M2B foundation and a separately reviewed one-switch activation, or
   introduce one atomic activation manifest/pointer that all wrappers already consult while retaining
   legacy behavior until flipped. The activation mechanism itself must fail closed on unknown,
   malformed, or version-mismatched states. Do not claim atomicity from git history alone.

3. **Provider ownership and cancellation semantics are underspecified for a central broker.** The
   broker must define which PID remains stable across exec, how signals and timeouts propagate, how
   stdout/stderr and exit status are preserved, how wait-mode differs from background mode, and how
   it transitions when the caller dies. It may terminate only the child/process group it created and
   must prove descriptor closure and terminal convergence for each wrapper language.

4. **The exact inventory cannot yet be ratified.** A true activation manifest or shared launch module
   may require an additional file, while reusing `aq-delegation-registry` as both lifecycle CLI and
   provider broker materially expands that surface. Choose and review the component boundary first,
   then bind the inventory. Do not force the architecture to fit the current nineteen-file ceiling.

## Non-blocking amendments

- Define stable machine error codes and exit codes for begin, preflight, attach, release, provider,
  transition, and retirement failures.
- Make the fake-provider smoke prove prompt/argv canaries are absent from records and telemetry while
  still reaching the provider unchanged.
- Treat a failed terminal transition after provider exit as contract-health failure requiring
  explicit reconciliation evidence; do not overwrite the provider exit code silently.
- Require a static and dynamic proof that all supported wrapper launch branches traverse the broker,
  including `--wait`, background, cancellation, and Antigravity loop-mode decisions.

## Preserved boundaries

M2B remains unauthorized. M2A remains dormant. M3, local reliability R1–R4, inference R1–R4, new
stores, owner Q8 decisions, network/inference routing changes, unrelated process termination, and
internal-platform/subagent adoption remain unauthorized.
