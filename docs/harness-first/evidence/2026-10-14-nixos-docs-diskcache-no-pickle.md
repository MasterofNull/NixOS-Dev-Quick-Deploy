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
