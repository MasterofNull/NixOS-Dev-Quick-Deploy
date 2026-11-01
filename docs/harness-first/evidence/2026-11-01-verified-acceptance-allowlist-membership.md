# Verified owner acceptance: allowlist set-membership alert (round 3) (2026-11-01)

## Objective

Close the round-2 Codex HIGH on the unbacked-owner-acceptance probe in `scripts/ai/aq-health-spider` (`_owner_acceptance_check`): any agent-writable floor is gameable. With the allowlist pinned at 131 and 121 live, a saved floor of 120 alerted, but overwriting it to 131 silenced the alert. The decision must not depend on mutable state.

## Workflow/Session IDs

Branch `feat/verified-owner-acceptance`, worktree `.agents/delegation/worktrees/verified-acceptance`. Bounded Sonnet-tier implementer slice (Rule 17); Codex session codex-20261101-110920-c8qdfq raised the finding. Left uncommitted.

## Delegation Decision

Implementation delegated per Rule 17; independent reviewer (Codex) re-reviews this round.

## Design

- `scripts/ai/aq-pm-tracker` `project_all()` adds `unbacked_key = [plan_dir.name, item id, acceptance_sha256]` to each item whose `acceptance_assurance` is `unverified`.
- `_owner_acceptance_check` compares every live `unbacked_key` with the entries of the tracked remove-only `config/pm-tracker-unbacked-owner-acceptances.json`. Any key not listed raises `owner_acceptance_unbacked_rising`. No count is compared with any stored value.
- The state file `.agents/telemetry/owner-acceptance-unbacked.json` is written each cycle for trend display only and is never read. Its content (missing, corrupt, any value) cannot change the alert decision.
- Failure modes: unreadable/malformed allowlist or missing keys give `owner_acceptance_probe_failed`; a live-key count that disagrees with `unbacked_owner_acceptances` alerts; a failed state write gives `owner_acceptance_state_unwritable`.

## Alert names and operator surface

`owner_acceptance_unbacked_rising` (high), `owner_acceptance_probe_failed` (warning), `owner_acceptance_state_unwritable` (high). Path: `HealthSpider.run_once` calls `_owner_acceptance_check` (`scripts/ai/aq-health-spider`, harness-level block "owner-acceptance") then `handle_anomaly`, which emits a `health_spider_<type>` telemetry event for all three and, for `unbacked_rising`, `push()`es a `human_gate` high-severity item (dedup key `owner-acceptance-unbacked-rising`) into the attention queue with proposed action and next step. This round added `owner_acceptance_state_unwritable` to the same handler branch so it is logged and counted as unresolved; no separate dashboard allowlist exists for these names. The counters themselves are published as the `owner_acceptance_assurance` event.

## Tests

`python3 scripts/testing/test-pm-tracker-owner-acceptance.py`: Ran 51 tests, OK. `HealthSpiderProbe` covers: listed set is quiet; a swapped unlisted acceptance alerts at the same count; removing an entry from allowlist and reality is quiet and re-adding alerts; state file missing/corrupt/0/131/99999/-1 yields the same decision; an upward overwrite within range cannot suppress; count/key mismatch alerts; unreadable projection or allowlist gives probe_failed; state write failure is reported; the real projection against the real allowlist is quiet.

## Residual risks

- An agent can still edit the committed allowlist or tracker `acceptance` blocks; the remove-only checks in `aq-pm-tracker --check-owner-acceptance` (baseline, merge-base, tip) guard that, not the spider.
- The spider trusts the output of `aq-pm-tracker --all-json`; a tampered tracker script defeats it.
- `project_all` skips plans whose manifest fails to parse, so their acceptances are not checked (pre-existing).
- Verified in tests with a stubbed runner and the real projection; not yet observed in a deployed spider cycle (spider restart/rebuild required).
