# AQ-OS Progress Tracker AM2 — Implementation Authorization

Authorization ID: `auth-aqos-progress-tracker-am2-20260730`  
Idempotency key: `aqos-progress-tracker:am2:97131faa:20260730`  
Status: **PREPARED_ONLY — OWNER ACTIVATION REQUIRED**  
Prepared: 2026-07-30 UTC

## Exact binding

- Base HEAD:
  `97131faac372e89273f14372edbfa5e52b816d64`
- Governing design:
  `.agents/plans/aqos-progress-tracker/DESIGN-PACKET-AM2-20260730.md`
- Governing design SHA-256:
  `48284994e49491bf09374e59032e93155dcf27ec34ac07f8dcecaba17c1394f0`
- Independent design review:
  `.agents/plans/aqos-progress-tracker/DESIGN-PACKET-AM2-INDEPENDENT-REVIEW-20260730.md`
- Independent design review SHA-256:
  `42b8ce2704a9ff781a3d47217da8d668d0272a240e01a34fac95cdadca5562df`
- Implementer: `codex-subagent-tracker-am2-implementer`
- Independent acceptance reviewer:
  `codex-subagent-tracker-am2-acceptance-reviewer`

The implementer cannot accept its own work. This authorization is inert until
the owner activates its exact SHA-256, both assignees, the exact base HEAD, and
a UTC window no longer than 24 hours.

## Exact four-file ceiling

After activation, the implementer may modify only:

1. `config/refactor-milestones.json`
2. `assets/aqos-progress-tracker.html`
3. `scripts/testing/test-dashboard-program-progress.py`
4. `scripts/testing/harness_qa/phases/phase0.py`

The primary-worktree and clean-HEAD hashes, frozen provenance inputs, required
current-state projection, negative vectors, and expected counts are exactly
those in the governing design. The Phase-0 release subject is clean HEAD plus
only the `0.10.40` replacement and must hash to:

`7bfc9119822c72493911d29d85c69d9ef1826974195c45e327a73f87152ed182`

All unrelated primary-worktree bytes, including checks `0.10.42` and `0.10.43`,
must remain byte-identical and outside the candidate projection and index.

## Authorized work after activation

The assigned implementer may:

1. materialize an isolated single-ref candidate from the exact base HEAD;
2. project Track S S0-A as commit-derived shipped truth while keeping Track S
   active;
3. project Foundation C2 as shipped/done/default-OFF at `97131faa`, preserve
   the named High residual issue, and make no activation claim;
4. update the focused hermetic oracle and all required negative vectors;
5. apply only the frozen Phase-0 `0.10.40` replacement;
6. compute and bind the final normalized projection digest;
7. run the governing design's offline validation commands; and
8. freeze exact candidate hashes for independent acceptance.

## Acceptance and release boundary

Implementation acceptance is offline and may not deploy. The exact four-file
candidate must pass its focused static suites, compile checks, diff checks, and
ordinary pre-commit hook inside the isolated projection. Pre-deployment Tier-0
may truthfully retain only the already-known live `0.10.40` failure; it may not
be reported as a full PASS and may not gain a new failure.

No staging or commit is authorized here. A later release authorization must
bind the independently accepted candidate hashes and exact index projection.
A separate deployment authorization owns runtime mutation. After deployment,
both commands must exit `0` before operational closeout:

```text
python3 scripts/testing/test-dashboard-program-progress.py
aq-qa 0 --machine
```

The live full Tier-0 PASS is also a prerequisite for the separately reviewed
C0.3 Stage-2 recovery. No waiver, differential substitution, skip, static
substitute, or relabeling is permitted for that C0.3 gate.

## Consumption, drift, and stop conditions

Activation is single-use and is consumed when implementation begins. Stop
without mutation on any HEAD, design, review, source, projector, inventory,
overlap, or hash drift; a fifth implementation path; a dashboard JavaScript
edit; a Phase-0 edit outside `0.10.40`; loss of unrelated dirty bytes; an
incorrect Track S/C2/count projection; a missing residual issue; a flag-on,
Nix, live-traffic, or cutover implication; a failed negative vector; or a need
for runtime/network/deployment access.

This authorization never permits staging, commit, push, deployment, service or
process mutation, provider/network/database access, Nix changes, C2 flag
activation, C0.3 settlement, or later-slice authority.

