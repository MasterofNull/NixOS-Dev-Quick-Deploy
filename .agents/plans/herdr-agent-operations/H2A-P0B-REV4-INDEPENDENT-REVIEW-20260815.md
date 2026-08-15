---
doc_type: design-review
id: herdr-h2a-p0b-rev4-independent-review-20260815
title: HERDR H2A-P0B revision 4 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_5_sha256: a000bac50fb663c4477227694a9632f5add52f0feb28565358062fad9e4f3cf8
---

# HERDR H2A-P0B revision 4 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| schema | `1de831f46eb0336c84e12e0f0616f6a9ba1a4b9f34ed3e3c4cc3663214ede5c3` |
| ledger | `2146cb869555aa118aa41d9ba251435daf47856b33ebf000f24ae010aa1c098a` |
| resolver | `07ce5cf6d398508d4d6f8718379309802dec67a1bba0c5804151b8ca9ed56bfe` |
| fixture | `19bcd2a92ee3d42086997f9355dc99e19dce525288a5a71130f52a380fcb4c6b` |
| test | `d91e0ef59e767009606a7f185422108c6e9628a739c8fed10a6f145886e400ef` |

The 82-leaf profile, static-input closure, expected/coverage input rejection, duplicate session/pane refs,
version/protocol/layout truth, sampling, literal replay, Draft 2020-12 checks, and purity passed. Acceptance
still requires:

1. enforce bounded issuer/expiry/revoked/superseded lifecycle against every projected reference, reject
   exact duplicates, resolve active replacements cycle-safely, and retain a full-strength binding digest;
2. bind unauthorized observer revision/digest and every accepted payload into output identity;
3. correct session/pane expected ledger provenance and derive coverage from actual known/unknown dimensions;
4. reject pane `match` without non-null expected/observed equality;
5. reject realistic credential-shaped values in accepted token fields.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — close lifecycle enforcement, complete-input binding, provenance/coverage,
pane truth, and credential privacy.
