---
doc_type: design-review
id: herdr-h2a-p0-rev5-independent-review-20260815
title: HERDR H2A-P0 revision 5 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
---

# HERDR H2A-P0 revision 5 independent review

All exact hashes and every prior sampling, lifecycle, replacement-chain, superseded-authority, overflow,
privacy, replay, count, unknown-state, and purity gate passed except two findings:

1. `work[].progress_age` ledger provenance still names `program_workflow_facts` instead of
   `agent_progress_facts` used by the resolver;
2. the shell-fragment fixture targets a forbidden root key rather than an allowed normalized text field.

Reviewed hashes: `1f5df849c9ab09ea7218967147d8f5c43c42d817c7c8cf4ef6d72c5ffe23ec87` /
`75850b2c56f3025b4161a94d79d1b45676acdbcefcfe549d8a89e9c1b3b47622` /
`e61cbf882d6b3e315d477e97c644e7b5d09fed0ff76805d392c42de58a732124` /
`8ab3a4295daeba90b551d488c39564a28b2098bdae76eb2820c88fa1b5296cd3` /
`a4892e396809bdb9e95a85581e6f97cb66a9fb6394daf716c8a959d9dc4181b8`.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — correct one ledger source and add one allowed-field literal shell vector.
