# CS-3 independent review and preservation receipt

Reviewer: native cold `/root/cs3_final_review`, non-author aq_reviewer lane.
Reviewed baseline: 161e321bcec824e5d88b23f53276ede962376887.
Exact staged subject: c5506ed015c5917b33f16b5f654a90e7d484d20fa4480b21c38c44026a8f9cf1.
Length: 50,258 raw binary/full-index diff bytes, independently checked twice.
Actual verdict: REQUEST_REVISION. This receipt does not award PASS trailers.

## One returned finding batch

1. Index-based ls-files validation rejects already-staged exact tracked deletion
   and rename sources. Reproduced declared tracked.txt to renamed.txt failure.
2. Published diff-tree default rename semantics differ from staged git-diff.
   A valid rename can create a commit and then report verification failure.
   Reviewer's staged ec71f576... versus published 187e216e... were shorthand
   evidence prefixes, not complete SHA256 receipts or production commit hashes.

Required arguments, flock/common-directory exclusion, ancestry/temporary index,
preservation, no TTL, bounded lock reads and escaped source Fleet wiring passed
inspected criteria; the passing focused fixture missed positive owned cases.
Nonblocking: real HEAD-object drift test and deployed CS4 route/Fleet exposure.
No production Tier-0, deployment, index or source mutation by the reviewer.

## Durable next step

Candidate preserved with normal hooks as ACTIVATION_BLOCKED commit
1a9a056713e6f686693fd215082d704d2ea45a89 on
factory/cs3-integration-guard-20260917; local/origin matched after 22 push checks.
No merge to main or completion claim. CS3-F1 is the named bounded corrective:
exact frozen-HEAD blob validation, equivalent diff hashing and positive owned
deletion/rename regression plus actual HEAD-object drift. One final independent
confirmation is required on the corrected bytes. Further recurrence escalates.

CS4 deployed dashboard exposure remains an activation gate; source tests are
not proof that a running dashboard has loaded the new status field.
