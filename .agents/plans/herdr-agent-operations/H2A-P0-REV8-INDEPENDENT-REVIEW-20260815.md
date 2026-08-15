---
doc_type: design-review
id: herdr-h2a-p0-rev8-independent-review-20260815
title: HERDR H2A-P0 revision 8 independent review
status: complete
reviewed_at: 2026-08-15T19:23:52Z
reviewer: Gibbs
reviewer_role: independent-reviewer
verdict: REQUEST_REVISION
runtime_authority: false
---

# HERDR H2A-P0 revision 8 independent review

## Exact reviewed subject

- `config/schemas/operator-context.schema.json`: `1f5df849c9ab09ea7218967147d8f5c43c42d817c7c8cf4ef6d72c5ffe23ec87`
- `config/operator-context-source-to-field-ledger.v1.json`: `1d5fb88d024709ed308017e1ad1e563b431adba1fa2d0f0fca7c7f6c4919e65c`
- `scripts/ai/lib/operator_context_projection.py`: `04d49c1860e42ec4f37cd3f2d97b271b7239249f192e39e084fd0ab304e87081`
- `scripts/testing/fixtures/operator-context-golden.json`: `95e6dddeb9f7264a4564299f02efea1fd718fc9aebb4a79ba327fb320d0f269a`
- `scripts/testing/test-operator-context-projection.py`: `fb84b78919a989744ff3cef86613a9e99cd39411e98d2a20a753f349c63af5b4`

The submitted hashes matched the reviewed bytes.

## Blocking findings

1. The command-head boundary remains denylist-dependent. Unseen command categories `make install`, `cargo test`, `terraform apply`, and `kill -9 process` were accepted and emitted unchanged.
2. The regex matches command-family words anywhere after whitespace, so benign objectives `Review git workflow`, `Document Python API`, and `Improve service health` were rejected. No positive ordinary-prose oracle covers command-related nouns.

## Verified gates

The reviewer confirmed bounded non-echo for recorded negatives; correct mission and progress provenance; the hermetic oracle; Draft 2020-12 validation; 71-leaf ledger parity; canonical ordering; literal bytes and hashes; count and unknown semantics; sampling and complete-input binding; lifecycle, expiry, issuer, subject, supersession, cycle, array, and chain enforcement; credential/path/control rejection; empty controls; and pure no-I/O operation.

The reviewer made no repository modification and performed no staging, commit, activation, runtime, or HERDR operation.

VERDICT: REQUEST_REVISION — use a category-independent command-shaped-head boundary that preserves benign sentence-style prose, with negative unseen-category and positive ordinary-prose vectors.
