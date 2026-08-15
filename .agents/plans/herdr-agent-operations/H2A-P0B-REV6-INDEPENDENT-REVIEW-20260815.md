---
doc_type: design-review
id: herdr-h2a-p0b-rev6-independent-review-20260815
title: HERDR H2A-P0B revision 6 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_5_sha256: a000bac50fb663c4477227694a9632f5add52f0feb28565358062fad9e4f3cf8
---

# HERDR H2A-P0B revision 6 independent review

All exact schema/ledger/replay/input-binding/provenance/replacement/pane/privacy/purity gates passed except:

1. active emitted references accept semantically past expiry buckets;
2. coverage omits explicit known categories such as enabled/disabled, compatible/incompatible,
   match/mismatch, degraded/stale/failed;
3. fixture lifecycle labels still exercise generic shape rejection instead of literal reference-binding
   expiry and genuine cycle graphs.

Reviewed hashes: `1de831f46eb0336c84e12e0f0616f6a9ba1a4b9f34ed3e3c4cc3663214ede5c3` /
`89e358a6284bda789db5571ab105a5b8040b487a0b56486d954ac409624813d8` /
`e61a3897a8cd1377c997428213665613622564455fefbb5e766801865d3c7188` /
`a912e9ee7b91066ab5173f76ce2cc38bd06c28bd3a5b8518cd5deeb2d673dc0f` /
`e18ccb4284c4fa5fbaa9f486226fbfeb57bd42a13e7d4cd69532334094ac6de1`.

VERDICT: REQUEST_REVISION — enforce semantic expiry, exhaustive coverage-state classification, and literal
reference lifecycle vectors.
