# QA Provider Probe Reliability C1 — Independent Authorization Review

**Verdict:** **PASS**  
**Reviewed:** 2026-07-18  
**Review role:** independent authorization, architecture, security, SRE, and process-lifecycle reviewer  
**Implementation authority:** **None — owner activation remains required**

## Exact reviewed subjects

| Subject | Verified SHA-256 |
|---|---|
| `.agents/plans/qa-provider-probe-reliability/C1-IMPLEMENTATION-AUTHORIZATION.md` | `d4c574ddecd21c5f88e501806cde7593bb3fb1b4c59c003d3479d1527b035743` |
| `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| `.agents/plans/qa-provider-probe-reliability/D0-DESIGN-PACKET.md` | `041951b9afbb6173e15cc176329f3ae228930199fb67799ad1fb59b32980394f` |
| `.agents/plans/qa-provider-probe-reliability/D0-DESIGN-REVIEW.md` | `9ca904808a903f98398ec9c98113a7f039ef9bb11b4076bfbe4c8a1a133310fb` |

All four on-disk hashes match the authorization and requested review subjects. The five candidate
paths were also verified absent at review time. Existing unrelated dirty files are outside this
subject and confer no authority to touch them.

## Boundary adjudication

### Five-file ceiling and closed contract

The authorization grants exactly five **NEW** files: one pure standard-library lifecycle module,
one Draft 2020-12 schema, one immutable policy, one golden-vector fixture, and one focused test. It
hard-stops on a sixth file, any existing-file edit, substitution, pre-existing candidate path,
bound-hash drift, or shared-file conflict. Every schema object boundary is required to reject
unknown fields, and all versions, providers, profiles, lifecycle states, results, failure classes,
dispositions, actions, and reason codes are closed.

The policy is frozen to 45-second provider deadline, 2-second TERM grace, 1-second KILL/reap,
200-second four-provider aggregate, one attempt, 4,096-byte sanitized stderr retention, and
65,536-byte stdout validation retention. Its only profiles are the four fixed `exit_only` help
profiles for `codex`, `qwen`, `claude`, and `pi`; environment, CLI, fixture, model-output, retry, and
fallback overrides are forbidden. C1 may validate those declarations but may not resolve or execute
any real provider.

### Process identity, cleanup, and Revision-3 signals

The process contract preserves the accepted D0 invariants: argv-only spawn, `DEVNULL` stdin, fresh
session, continuous bounded drains, monotonic deadlines, pidfd plus start-time/PGID/SID identity,
`waitid(...WNOWAIT)` leader anchoring, temporary subreaper ownership with exact restoration, and two
consecutive all-return quiescence passes before leader reap. All returns, including direct exit
zero, pass through membership checks. Numeric group signals remain legal only while the unreaped
leader identity is valid; `ESRCH` is not proof, and no numeric signal is permitted after reap. An
escaped-session fixture fails `cleanup_failed` without an arbitrary kill.

The frozen cleanup order is `SIGCONT -> SIGTERM -> 2-second grace -> SIGKILL -> 1-second reap ->
two-pass quiescence -> owned-descendant reap -> leader reap`. Interruption uses that same idempotent
path. Revision 3 is retained precisely: SIGTERM/SIGINT are blocked during ownership and wakeup-pipe
installation; the first signal is recorded, later signals coalesce, child cleanup is bounded to
four seconds, prior mask and handlers are restored, and the first signal is redelivered exactly
once within the five-second cleanup/restoration/redelivery SLO. Only a restored default disposition
must terminate nonzero; custom and ignored post-redelivery behavior is preserved and never replaced
by a forced exit.

### Evidence, normalization, and adversarial coverage

Results prohibit prompts, credentials, HOME data, environment, terminal data, raw argv, arbitrary
paths, PIDs/PGIDs/SIDs, and full output. Stderr must be replacement-decoded, control-cleaned,
credential-redacted, path-tokenized, and capped; both streams continue draining after caps and
overflow cannot pass. Golden vectors require exact lifecycle-first normalization for `exit_only`
and `machine_json_v1`, including missing, malformed, multiple, invalid, reported-failure, nonzero,
truncated, and pass branches. Every vector asserts one spawn and no retry.

The mandatory fixtures cover clean/nonzero/spawn/deadline outcomes, self-stop action order,
timeout and leader-exit-zero forks, flood and redaction boundaries, each interruption phase,
`probe_busy`, real SIGTERM/SIGINT across default/returning-custom/non-returning-custom/ignored
dispositions, second-signal coalescing, pidfd and direct-child races, `ESRCH`, subreaper restoration,
two-pass quiescence, escaped session, every closed enum/rejection, secret/path/control canaries, and
one-spawn normalization. Tests are offline and may spawn only deterministic local fixtures.

## Authority and integration decision

The exclusions are explicit and complete: no provider or inference execution, network, Phase-0 or
shell adoption, dashboard/runtime/API changes, service/Nix/deployment work, traffic, store, broker,
cgroup, A1-A3 action, cleanup, rollback, staging, or commit is granted. Exactly one bounded
implementer must own all five files without delegation or self-acceptance. A separate agent/session
must review the exact completed hashes; any byte it changes recuses that reviewer. Only the
orchestrator may stage and commit after independent exact-subject PASS and all frozen validation
gates pass.

This authorization is therefore sufficiently hash-bound, closed, single-use, and fail-closed for
owner activation. It remains **PREPARED_ONLY**. Activation must explicitly name authorization SHA
`d4c574ddecd21c5f88e501806cde7593bb3fb1b4c59c003d3479d1527b035743`, exactly one implementer,
an activation timestamp, and an expiry no more than 24 hours later, while affirming that the exact
five-file ceiling and stop conditions are unchanged. A design PASS, this review PASS, silence, or
broad preauthorization does not activate C1.

`VERDICT: PASS`

