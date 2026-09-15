# FT-3 independent review R0

Reviewer: Codex `/root/ft1_independent_acceptance`, non-author.
Verdict: REQUEST_REVISION, 2026-09-15. Not accepted or activated.
Whole staged subject unchanged before/after:
`0e5b2fa8f342ee3b2a2a82045431f64d445e1ace6fed72dbc73971bdf051be04`.

Blocking invariants, reproduced in disposable targets only:

1. Relative `BUNDLE_DESTINATION` compared with absolute destination parents
   never matches; preserved README/manifest/self-test are re-rendered. Actual
   installed preserved self-test fails on unrendered protected-branch setup.
   Compare actual containment, assert preserved bytes and run that self-test.
2. Active default `.git/hooks/pre-commit` is bypassed by changing hooksPath
   when no explicit setting exists. Refuse before bootstrap writes; composition
   stays confirm-gated FT-4.
3. Symlinked `.git` redirects local configuration writes into another repo.
   Reject redirected metadata before writes; prove outside configuration unchanged.

Corrective FT-3-R1 owns only installer/aqd/focused tests/implementation docs.
One replay per invariant; recurrence escalates, not another review loop.
No redesign or brownfield implementation added to this corrective slice.

Passed: four-marker focused fixture, source bundle self-test, QA marker probes,
dashboard label states, Python/Bash/JS syntax, whitespace, mixed-stack blocking
and installed starter tracker discovery. Source-only self-test was insufficient
to prove the preserved installed artifact and is not credited as that proof.

Nonblocking FT-4 descriptors: direct-helper greenfield eligibility clarity and
explicit layout/configuration prerequisites. No reviewer source/index/HEAD edits,
production activation or user-project tests. The limited local wording proposal
and zero-output Claude dispatch are not binding reviews.
