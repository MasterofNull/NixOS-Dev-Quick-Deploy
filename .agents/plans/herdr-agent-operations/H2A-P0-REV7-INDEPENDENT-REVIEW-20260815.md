---
doc_type: design-review
id: herdr-h2a-p0-rev7-independent-review-20260815
title: HERDR H2A-P0 revision 7 independent review
status: complete
reviewed_at: 2026-08-15T19:20:40Z
reviewer: Gibbs
reviewer_role: independent-reviewer
verdict: REQUEST_REVISION
runtime_authority: false
---

# HERDR H2A-P0 revision 7 independent review

## Exact reviewed subject

- `config/schemas/operator-context.schema.json`: `1f5df849c9ab09ea7218967147d8f5c43c42d817c7c8cf4ef6d72c5ffe23ec87`
- `config/operator-context-source-to-field-ledger.v1.json`: `1d5fb88d024709ed308017e1ad1e563b431adba1fa2d0f0fca7c7f6c4919e65c`
- `scripts/ai/lib/operator_context_projection.py`: `4a4ac79fc7ecdc785856f7f65ce88ae465fdbb310d7524a4842ada4f7c020b4d`
- `scripts/testing/fixtures/operator-context-golden.json`: `71b6358a825d9accf4b1f374988221ff0021c04d866e25a2db5764fb12e13b10`
- `scripts/testing/test-operator-context-projection.py`: `bbcc78a11cdce0c2ae6c7f5fabf4d6d6cee35bb169e251fbda28b3c7f7eab967`

The submitted hashes matched the reviewed bytes.

## Blocking finding

The allowed-character shell/control boundary remains a narrow denylist. Independent permitted-field probes `rm -rf tmp`, `python -c payload`, `sudo reboot`, and `systemctl restart service` were accepted and emitted unchanged. The literal oracle covers only `$(x)` and `x;curl`, so it does not establish a general normalized command-fragment boundary.

## Verified gates

The reviewer confirmed truthful `mission.workflow_phase` and `work[].progress_age` provenance; the hermetic oracle; Draft 2020-12 validation; 71-leaf ledger parity; canonical insertion-order stability; literal bytes and digests; count pairing; sampling/skew and complete-input binding; lifecycle, expiry, issuer, subject, supersession, cycle, array, and chain checks; credential/path/control-character rejection; unknown preservation; empty controls; and pure no-I/O operation.

The reviewer made no repository modification and performed no staging, commit, activation, runtime, or HERDR operation.

VERDICT: REQUEST_REVISION — implement a general normalized shell/control-fragment boundary and literal bounded non-echo probes for allowed-character command forms.
