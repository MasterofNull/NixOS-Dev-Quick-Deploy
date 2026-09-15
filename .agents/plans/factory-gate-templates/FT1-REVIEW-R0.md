# FT-1 independent acceptance — REQUEST_REVISION

Reviewer: fresh non-author Codex acceptance lane (`ft1_independent_acceptance`).
Subject, unchanged before/after review:
`a507cdac41fd07f06266a6b1bcd4b2cf47b8a530c3c50bf464be85f5adc6eb02`.

Three critical correctness findings, dispatched as the bounded NEXT slice FT-1-R1:

1. Unconfigured command placeholders exit zero and count as PASS; a pre-deploy
   run falsely reported all seven checks passing. Required checks must fail
   closed; deliberate not-applicable and unconfigured must be typed distinctly.
2. Manifest installation moves self-test dependencies away from its assumed
   sibling paths. The declared installed layout must be self-testable. Generated
   Python bytecode must not invalidate source inventory.
3. PM projector permits SHIPPED/100 from editorial acceptance alone, accepts
   schema-invalid input, and allows authoritative progress over 100%. Enforce
   schema/bounds and git-evidence-backed completion.

Evidence: shellcheck + bash syntax PASS over 13 programs; basic missing-review,
wrong-hash, self-review rejection and independent bound acceptance PASS. Reviewer
self-test encountered generated ignored pycache inventory failure; implementer
reported PASS before that artifact existed. No source/live gate was modified.

No final PASS, authorship credit as acceptance, integration or activation follows
from this review. One bounded exact-subject acceptance follows corrective slice;
FT-2/6/7 requirements are not retroactive FT-1 blockers.
