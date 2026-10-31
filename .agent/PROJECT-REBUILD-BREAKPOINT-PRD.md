# Authorized rebuild breakpoint
Owner directive 2026-10-31 authorizes existing rebuild blocker fixes.
Wave 1: PR672 generated baseline; live QA diagnosis; preserve lock.
Wave 2: lock admission and system/HM evaluation; bounded producer fix, no sandbox widening.
Wave 3: independent review, tier0, PR updates; clean source reconciliation; dry-build and owner activation commands; Claude handoff.
Architecture: canonical deploy and generated baselines. Failure modes: stale receipt, dirty lock, obsolete producer dependency. Security: no timestamp/policy bypass or signer activation. UX: exact breakpoint and commands.
Acceptance: PR checks pass; admitted lock; system/HM validation; live QA or dated blocker; preserve unrelated work.
