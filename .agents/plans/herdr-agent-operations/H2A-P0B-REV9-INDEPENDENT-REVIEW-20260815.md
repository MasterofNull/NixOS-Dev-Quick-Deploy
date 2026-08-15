---
doc_type: design-review
id: herdr-h2a-p0b-rev9-independent-review-20260815
title: HERDR H2A-P0B revision 9 convergence review
status: escalated
reviewed_at: 2026-08-15T19:50:15Z
reviewer: Gibbs
reviewer_role: independent-reviewer
verdict: ESCALATION
runtime_authority: false
---

# HERDR H2A-P0B revision 9 convergence review

## Exact subject

- schema: `1de831f46eb0336c84e12e0f0616f6a9ba1a4b9f34ed3e3c4cc3663214ede5c3`
- ledger: `89e358a6284bda789db5571ab105a5b8040b487a0b56486d954ac409624813d8`
- resolver: `ebfc5e338c9cf768e325982f46f1f27a28f9fb8cb3cb3d180f3b8ef1fd74fa4c`
- fixture: `06d8a19905ba8e0a2bb8241b54d90e6e2978f6de194e71ce9199dc3725b6290f`
- test: `151f4a801f4cb29055080d239ce6444673bf55e33e38004e9b37c9bfaab10f66`

`coverage_totality` passed: the sole reducer covers every return class, the independent branch oracle matches, and all 27 emitted state dimensions reconcile. Canonical order, cycle-specific rejection, schema/ledger/literal/lifecycle/bounds/purity gates remain green.

A distinct `unauthorized_input_validation` equivalence class remains. Unauthorized observations return before nested validation, allowing credential-shaped or over-bound content to affect the observation revision. `reference_bindings[].issuer_revision` directly uses the token regex and bypasses credential rejection. Existing privacy tests do not cover either ingress bypass.

No repository or runtime mutation occurred.

ESCALATION: the P0B review budget is exhausted. Do not automatically revise/re-review this candidate. Issue one new bounded ingress-validation remediation slice; P0B remains unaccepted and unstaged.
