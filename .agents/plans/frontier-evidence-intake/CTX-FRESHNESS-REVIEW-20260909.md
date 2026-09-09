# ctx-freshness + shallow-heal — independent review

**Author:** Codex (implemented aq-ctx-freshness + hooks + session-start edit + shallow-heal).
**Reviewer:** Claude Opus 4.8 (orchestrator, NON-AUTHOR — independent verification). Per Rule 18:
the preferred cross-lane reviewers were unavailable (Codex is the author; the fresh-Claude/sonnet
lane is session-limited until 12:30am PT), so the next eligible independent lane (non-author
flagship) reviewed; a cross-lane confirmatory is QUEUED for the sonnet lane's return.

Verified:
- syntax clean (bash -n) on aq-ctx-freshness + both hooks; test-aq-ctx-freshness.sh PASS.
- --check reports FRESH (exit 0) on the rebuilt graph; --heal-shallow exit 0 and LIVE-PROVEN:
  running it unshallowed the repo in the background (is-shallow-repository true -> false).
- SAFETY: hooks are post-merge/post-checkout (NOT pre-commit) + fail-safe -> cannot block a
  commit or a git op; session-start additions are || true -> cannot block hydration; all modes
  fail-safe on missing tool/remote (exit 0). Additive only; no existing behavior changed.
- Consensus-aligned (Graft round table): staleness signal surfaced; refresh demand-driven/background
  (not per-commit); AQ_UNSHALLOW_DEPTH gives the lighter deepen option.

**Verdict: PASS.** Confirmatory audit queued for the sonnet lane (advisory).
