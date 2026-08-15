---
doc_type: design-review
id: herdr-h2a-rev3-independent-review-20260814
title: HERDR H2A revision 3 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (independent aq_reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-14
---

# HERDR H2A revision 3 independent review

Read-only review of the five-document H2A `PREPARED_ONLY` candidate. No implementation, staging,
commit, rebuild, HERDR runtime, or activation authority is granted.

## Exact reviewed subjects

| Subject | SHA-256 |
|---|---|
| Inventory | `2220013daef96ec7aaac1b1ce0f6c9d1656d22ad5799f23770ff3d83cd7c883a` |
| Contract #2 | `8074632c4b73dbc37c4da98533a703c12af441ac37f3274e914232563de1ead5` |
| Contract #3 | `f407bafeb12ad85a95a95a88406a5cf2e1a73d68622844aa104d23c9929ac9c7` |
| Contract #4 | `b8cedf3b50e857bb5da028823dc94bc655deb4a4125f867498fc6778c3775f08` |
| Contract #5 | `a46150cf88d24a97dda3ae81d2ae5dd4830ad636238fcd2705703fda0e181f52` |
| Contract zero | `716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48` |

## Sole blocking finding

Contract #5 constrained count state to `known|unknown|unavailable`, but its exact generic `state`
profile also allowed `stale|conflict` and applied that broader enum to all count objects. The closed
schema and golden corpus therefore lacked a deterministic answer for whether those two values were
valid count states. Define a distinct narrow `count_state` or consistently broaden the count rule.

All earlier findings passed: presentation and comparison schemas aligned; comparator ownership was
singular; parent/progress vectors were synthetic-only; layout planning excluded cross-projection
drift; ten paths were correctly counted and absent; the action allowlist remained empty and
fail-closed; and no new implementation, runtime, identity, activation, or sensitive-data authority
was introduced.

VERDICT: REQUEST_REVISION — reconcile contract #5 count-state enums before freeze
