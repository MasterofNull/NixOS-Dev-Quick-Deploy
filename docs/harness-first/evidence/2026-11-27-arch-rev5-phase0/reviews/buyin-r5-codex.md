Verdict: PLAN_READY_WITH_FOLLOWUPS
Reviewed-DESIGN-sha256: c759dbda5250205e7784e641fbad095364bf48f1c5873ea7052fb788604e3694
P3 - Changes stay within F1/F3/F4/F5 and citation hygiene; no unrelated scope, slice, acceptance, or decision changes found - No fix required.
P3 - F1 correctly separates overlapping-row counts from excess-writer totals, leaves the total UNKNOWN, and removes the invented upper bound - No fix required.
P3 - Changed citations identify the intended files; reviewer outputs resolve in the shared checkout but remain untracked and absent from the reviewed worktree - Preserve those outputs with durable evidence.
Top risk I see: Reviewer-output citations depend on local untracked artifacts and may become unavailable in another checkout.
