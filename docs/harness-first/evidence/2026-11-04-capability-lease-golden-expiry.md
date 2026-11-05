## Objective
Stop the capability-lease test from failing on wall-clock time. The assertion "attenuation: golden child verifies ok under DEV key" in scripts/testing/test-capability-lease.py failed because the golden child lease has expires_at 2026-11-01T00:00:00Z and today (2026-11-04) is past it. The library had not regressed.

## Workflow/Session IDs
Branch fix/capability-lease-golden-expiry, worktree .agents/delegation/worktrees/cap-lease-expiry. No session ID was recorded for this slice.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Haiku (Rule 17, mechanical bounded edit with checkable results). Date: 2026-11-04. Scope is limited to scripts/ai/lib/capability_lease.py, scripts/testing/test-capability-lease.py and this evidence doc. The golden fixture JSON was not edited or re-signed.

## Commands Executed
- rg for verify( and capability_lease callers across scripts/
- python3 scripts/testing/test-capability-lease.py
- python3 scripts/testing/test-capability-lease-gate.py
- python3 scripts/testing/test-capability-lease-issuance.py
- python3 scripts/testing/run-test-group.py tests-capability

## Validation Evidence
Root cause: a fixture with an absolute expiry date was verified against wall-clock time. verify() had no time parameter, so every golden VERIFY_OK assertion would fail once the fixture's expires_at passed.

Fix:
- capability_lease.verify() gains a keyword-only `now: Optional[datetime] = None`, passed to is_expired(). The default keeps wall-clock behaviour. No other signature changed.
- test-capability-lease.py defines GOLDEN_NOW = 2026-08-01T00:00:00Z. Golden VERIFY_OK assertions pass it. This instant lies inside [issued_at, expires_at) for the valid, parent, tampered and child golden leases (all issued 2026-07-24; expires 2026-12-31, 2026-12-31, 2026-12-31 and 2026-11-01).
- One assertion added: the golden child verifies as VERIFY_EXPIRED when now is 2026-11-02.
- Expiry assertions on the golden expired lease are unchanged.
- rg shows all other verify() callers pass positional or keyword arguments that the keyword-only addition does not affect.

Test results:
- test-capability-lease.py: 55 passed, 0 failed (of 55 assertions), exit 0
- test-capability-lease-gate.py: 83/83 passed, exit 0
- test-capability-lease-issuance.py: 57 passed, 0 failed (of 57 assertions), exit 0
- run-test-group.py tests-capability: 13/13 passed, exit 0

## Rollback Plan
Revert the changes to scripts/ai/lib/capability_lease.py and scripts/testing/test-capability-lease.py, and remove this evidence doc. No data or config migration is involved.

## Residual Risk
- The CLI assertion "dev-key: CLI verify of golden 'valid' lease -> ok" still uses wall-clock time through a subprocess. It will fail after 2026-12-31T00:00:00Z.
- The fresh_child attenuation assertion, which is not a golden fixture, also uses wall-clock time and inherits the parent's 2026-12-31 expiry. It will fail after that date.
- Both are the same class of time bomb and are left for a follow-up slice. They are not fixed here because the slice scope was limited to golden VERIFY_OK assertions.

## Hint Feedback
No hints were consulted for this slice. The existing is_expired(now=) signature and the GOLDEN_PATH comments were the useful context.
