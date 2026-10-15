# Evidence: nixos-docs: Replace diskcache with stdlib sqlite3 TTL Cache

## Context
Date: 2026-10-14
Slice: `fix/nixos-docs-diskcache-no-pickle`
Component: `ai-stack/mcp-servers/nixos-docs/server.py`, `ai-stack/mcp-servers/nixos-docs/requirements.txt`, `nix/modules/services/mcp-servers.nix`, `scripts/testing/test-nixos-docs-diskcache-no-pickle.py`
Author lane: claude; independent reviewer: claude-sonnet (independent reviewer) + orchestrator verification of revision delta

## Problem
Root cause: diskcache (CVE-2025-69872, pickle-based) is unmaintained (no release since 2023-08, Scorecard Maintained 0, open maintenance issue #355); gate-triggered dependency rule.

## Solution
Cache replaced by a stdlib sqlite3 TTL cache (`text-cache.db`, schema check, get() never raises). Review caught a legacy cache.db schema collision, fixed by using a distinct file name.

## Validation Evidence
- `python3 scripts/testing/test-nixos-docs-diskcache-no-pickle.py`: `PASS test-nixos-docs-diskcache-no-pickle (stdlib sqlite3 TextTTLCache)`.
- tier0 `--pre-commit`: see commit/PR.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude | claude-sonnet (independent reviewer) + orchestrator verification of revision delta | PASS_WITH_FOLLOWUPS |

## Follow-ups
- After this lands, remove the diskcache entry from `config/security-exceptions.json` (slice 15 / security gate).
- Owner post-deploy archive command for the legacy cache (runtime, owner-operated):

```
sudo mkdir -p /var/lib/ai-stack/nixos-docs/.archive-20261014-diskcache && sudo sh -c 'cd /var/lib/ai-stack/nixos-docs/cache && mv cache.db* [0-9a-f][0-9a-f] /var/lib/ai-stack/nixos-docs/.archive-20261014-diskcache/'
```

## Rule 15 Activation Attestation
- Integrated: YES - nixos-docs server uses the new cache on its live request path.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; full real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: no tracked plan item; no status hand-set.

## Objective
Clear the failing security gate on diskcache (PYSEC-2026-2447 / CVE-2025-69872) by moving the nixos-docs MCP server off the unmaintained, pickle-based diskcache to a stdlib sqlite3 TTL cache, with no behavior change for callers (cache dir mode tightened to 0700).

## Workflow/Session IDs
- Orchestrator session: eb012479-4564-462f-8e6f-4824d5a77754 (claude-opus-5-5), slice 14 of the 2026-10-14 landing manifest (`.agents/delegation/outputs/landing-manifest-20261014.md`).
- Branch/worktree: `fix/nixos-docs-diskcache-no-pickle` in `/tmp/wt-diskcache`.

## Delegation Decision
Implementer: claude-sonnet sub-agent (Rule 17 balanced tier; bounded single-component change with a checkable test). Reviewer: separate claude-sonnet instance (same-lane; cross-lane confirmatory review queued in AGENT-CATCHUP-QUEUE). Orchestrator verified the revision delta (legacy cache.db schema collision fix).

## Commands Executed
- `python3 scripts/testing/test-nixos-docs-diskcache-no-pickle.py`
- `gitleaks detect --redact --config .gitleaks.toml --source . --no-git --exit-code 1`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Rollback Plan
Revert the PR merge commit (restores diskcache in requirements.txt and mcp-servers.nix). The new cache writes only `text-cache.db`; the legacy diskcache files are left in place until the owner archives them, so a revert finds its old cache intact.

## Residual Risk
- Cache is cold after deploy (new file); first lookups hit upstream docs until warm.
- The diskcache security exception in `config/security-exceptions.json` must be removed after merge (tracked in Follow-ups).
- Same-lane review only until the cross-lane confirmatory review lands.

## Hint Feedback
No aq-hints consulted for this slice; dependency decision followed the owner rule "dependency work only on a failing gate; abandoned -> maintained replacement" (stdlib chosen as smallest maintained replacement).
