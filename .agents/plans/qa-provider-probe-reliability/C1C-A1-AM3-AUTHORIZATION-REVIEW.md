# QPPR-C1C / A1-AM3 authorization review

**Reviewer:** `codex-subagent-qppr-c1c-am3-auth-reviewer`
**Role:** independent flagship architecture / security / SRE / QA reviewer
**Reviewed:** 2026-07-19
**Verdict:** REQUEST_REVISION

## Exact reviewed subjects

| Subject | Required SHA-256 | Observed SHA-256 | Result |
|---|---|---|---|
| C1C publication-ack design | `2a04262e0b278eeaeff271475f003e13883615aff906a132a9ee2e8c2f470974` | `2a04262e0b278eeaeff271475f003e13883615aff906a132a9ee2e8c2f470974` | exact |
| C1C implementation authorization | `c9460d0b7468defb0807ca4d51ff2ae615e6d0764b9b836fe0c58bdade237c23` | `c9460d0b7468defb0807ca4d51ff2ae615e6d0764b9b836fe0c58bdade237c23` | exact |
| A1-AM3 prerequisite rebind | `41ca28a2d0d4960ec6849d93cc013912ecaa545dfe0b6b645f76a14cc7c5f0b2` | `41ca28a2d0d4960ec6849d93cc013912ecaa545dfe0b6b645f76a14cc7c5f0b2` | exact |
| A1-AM3 conditional authorization | `63f28c168b0b2a6547d72b00df9122cc8ef5c6e02443a78b5b5d271b5920f621` | `63f28c168b0b2a6547d72b00df9122cc8ef5c6e02443a78b5b5d271b5920f621` | exact |
| A1-AM3 roadmap-verifier recovery | `0d16fa8e96413e6368aa0dfb4331f5dbfa79e652187eb9d4a98405c33ab0c1a4` | `0d16fa8e96413e6368aa0dfb4331f5dbfa79e652187eb9d4a98405c33ab0c1a4` | exact |
| A1-AM3 roadmap-recovery authorization | `6590176eb70ec09296f87bad1a2d4c58220086aa21fe09cc4058d77c35d359ac` | `6590176eb70ec09296f87bad1a2d4c58220086aa21fe09cc4058d77c35d359ac` | exact |

The two C1C predecessor hashes and frozen observer-test hash also match the current bytes:

- `process_lifecycle.py`: `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e`
- `test-qa-provider-probe-lifecycle.py`: `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7`
- `test-qa-provider-probe-observer.py`: `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b`

## Criteria adjudication

### C1C boundary and ordering

The two-file ceiling is structurally sufficient for the proposed opt-in interface and its lifecycle
fixtures. The design preserves the accepted legacy callback and observer bytes, rejects dual-interface
admission before spawn, places the synchronous barrier after result normalization and terminal-event
attempt, and restores/redelivers only after the barrier returns. Therefore a returning barrier has no
barrier worker that can continue after redelivery. The required implementer identity is exact, the
candidate/reviewer roles are separated, and provider, network, evidence, Phase-0, Nix, deployment,
staging, commit, deletion, and self-acceptance remain excluded.

One SRE claim is not yet enforceable. An absolute deadline passed to an in-process callback is
cooperative: a callback that blocks or ignores the deadline cannot be cancelled by the lifecycle owner,
which is itself blocked in the callback. The design can guarantee no post-redelivery continuation by
delaying redelivery indefinitely, but it cannot simultaneously prove that the existing four/five-second
restoration/redelivery budget remains unchanged. The current deterministic evidence covers an already
expired deadline and acknowledged returns, not a barrier that overruns or never returns. The amended
design must either add an enforceable isolation/cancellation boundary with deterministic overrun proof,
or narrow the invariant and explicitly accept the fail-stopped redelivery risk through the applicable
SRE authority. Merely adding a sleep-based test or trusting a callback to self-police is insufficient.

The C1C authorization also requests “exact deterministic focused-test results” but does not freeze the
exact commands that produce them. The revised authorization must name the focused lifecycle command,
the unchanged observer regression command/hash check, and the proportionate syntax/security checks so
activation and acceptance cannot substitute a weaker invocation.

### A1-AM3 prerequisite and ceiling

The conditional documents correctly keep A1-AM3 NON-ACTIVATABLE until C1C is independently accepted,
committed, and bound by final exact bytes. They retain the exact three-file AM3 implementation ceiling,
freeze the other five A1 candidate paths, require the C1C barrier instead of legacy publication, and
keep A2 blocked. No current owner wording can activate these bytes.

The referenced A1-AM2 evidence is not presently reproducible from the named workspace paths. The
conditional package names design SHA
`6992c98f3c2e00d91cf5c5893b6116e23b484f16a3121a9f32899e3f4ab77f6d` and review SHA
`6827864ccdcae765b47f0c4daf32416199270a8ef825f1e3efb0e3395ede2d14`, while the currently observed
files hash to `2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` and
`214a3a99fbadf9895311c7142e63fc4787e1b7fb3fe10c115fbfaac305cc89c6`, respectively. The rebind notes
the discrepancy, but final review cannot inherit requirements from unavailable bytes. Preserve the
intended historical subjects as immutable evidence or rebind to independently reviewed observable
bytes before any later activation package is prepared.

### Mandatory Tier-0 compatibility recovery

The frozen A1 smoke candidate at
`98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` correctly delegates to the
canonical `qa-provider-probe.py --machine` compatibility entrypoint and intentionally removes the old
inline command array. However,
`scripts/testing/verify-flake-first-roadmap-completion.sh:597` still requires the legacy
`commands=(cn codex qwen gemini claude pi)` or inline `--help` pattern. The orchestrator's mandatory
Tier-0 run consequently produced 22 PASS / 1 FAIL at “Flagship CLI smoke covers declared agent CLI
surfaces.” The original three-file conditional authorization was therefore incomplete.

The exact roadmap-recovery subjects reviewed above resolve this adjacency at the design level. They
expand the future AM3 correction ceiling to exactly four files by adding the matching verifier
predecessor `c8602060565decdeef229042d2e15bf4b875f78f5a71eb4422cfcc3dd074a9d9`, while preserving the
five frozen A1 paths. Their positive requirements bind exact canonical `exec python3 ... --machine`
and direct Phase-0 `0.6.1` adoption; their negative requirements reject missing exec, missing Phase-0
call, and reintroduced legacy loops. This is architecture-aware coverage rather than dead `--help`
text added to game the old pattern.

The recovery remains correctly NON-ACTIVATABLE pending C1C acceptance/commit and final byte rebind.
The final rebind must supersede the three-file authorization with these exact recovery subjects, bind
all four correction and five frozen hashes, and require the focused negative fixtures plus mandatory
Tier-0. Subject to that sequence, the roadmap failure is no longer a package blocker.

## Required revisions

1. Resolve the C1C cooperative-deadline/SRE invariant with an enforceable bounded cancellation design
   or an explicit authority-approved narrowing, plus deterministic overrun evidence.
2. Freeze exact focused, regression, syntax, and security commands in the C1C authorization.
3. Preserve or rebind the unavailable A1-AM2 design/review subjects so inherited requirements are
   independently auditable.
4. Carry the exact reviewed roadmap-recovery subjects into the post-C1C final A1-AM3 rebind and retain
   their four-file ceiling, negative fixtures, and mandatory Tier-0 gate.

Residual risk after these revisions remains the correctness of the eventual A1 join implementation;
that risk belongs to exact-candidate acceptance and cannot be waived by this design review.

VERDICT: REQUEST_REVISION — enforce or explicitly adjudicate the cooperative callback deadline, freeze exact C1C validation commands, reconcile unavailable A1-AM2 subjects, and carry the accepted four-file roadmap recovery into the final non-activatable A1-AM3 rebind
