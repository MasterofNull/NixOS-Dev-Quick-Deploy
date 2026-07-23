# QPPR A1-AM3 revision authorization (post-acceptance REQUEST_REVISION)

**Authorization ID:** `auth-qa-provider-probe-reliability-a1-am3-rev2-20260719`
**Status:** PREPARED_ONLY until owner activation (standing authorization applies)
**Required implementer:** `claude-subagent-qppr-a1-am3-implementer` (same identity/tier as the
consumed grant; the acceptance verdict supplies exact corrective direction, so implementer
continuity is retained deliberately)
**Single use; ≤24h window on activation**

## Basis

Acceptance review `A1-AM3-CANDIDATE-ACCEPTANCE.md` returned `REQUEST_REVISION` with two findings
against an otherwise-passing candidate: (A) the C1C publication callback returns after only filling
the result slot — commit is deferred past `run_owned_process` return, so a default-disposition
signal redelivery kills the process with zero terminal heartbeat behind an already-recorded
`completed` acknowledgement, and custom/ignored dispositions write after handler return contrary to
AM2 §5.2; (B) canonical mode writes a terminal heartbeat even when the join cancels
(`qa-provider-probe.py:597-605`), contrary to AM2's cancel-without-writing requirement. Crux B
(verifier rewrite), criteria 4.3–4.5, all validations, and governance ordering PASSED and their
artifacts are retained unchanged.

## Ceiling: exactly two MODIFY, seven frozen

| Path | Predecessor (accepted-candidate) SHA-256 | Disposition |
|---|---|---|
| `scripts/testing/qa-provider-probe.py` | `3894064065607ac4e8437c404aec81285b7ab3d9c2087a83f7f9e59bd6747e84` | MODIFY |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `15dbe32592a2a4994c357c76921fac92ec9866bcf25b5f67010a098e1b42fa4a` | MODIFY |
| `scripts/testing/harness_qa/core/result.py` | `37821dcffa3ec98ddfc1cb82ed965d518b7f0bf0fa9088fb369be9cfe1b0d550` | FROZEN |
| `scripts/testing/verify-flake-first-roadmap-completion.sh` | `4f5ce42ed1f6163d82c1b6c4c913cc4b2dc800e4723591a4ea302e8063529be4` | FROZEN |
| five original frozen paths | per `A1-AM3-FINAL-REBIND.md` | FROZEN |

## Required revisions (from the verdict artifact, binding)

- **R-A1**: drive the join to COMMITTED or synchronously CANCELLED *inside* the publication
  callback window, with an idempotent post-return join for the ordinary path; the `completed`
  acknowledgement may be recorded only after the terminal projection is committed; `cancelled`
  only after synchronous disable + join. No post-return continuation; absolute deadline respected;
  the C1C interface (committed `c7407ea4…`) is NOT modified — the reviewer confirmed a bounded
  callback-internal commit is feasible within it.
- **R-A2**: remove the commit-independent canonical terminal-heartbeat write on cancelled joins —
  a cancelled join emits no terminal projection.
- **R-A3**: add the AM2 §5 items 1–3 signal-path adversarial tests (default-disposition kill with
  zero-heartbeat proof, custom/ignored disposition ordering, no-late-write), deterministic per the
  established fixture standards (event barriers, no sleep-only assertions).

All prior validations must still pass (adoption suite grows with R-A3; frozen lifecycle 39/39
unaffected; verifier 611/0; compile/diff/secret checks). Governance events per the established
canonical-writer sequence, resume/intent BEFORE edits. All stop conditions of the consumed
authorization remain, including the A2 block and no-fifth-file.

A revised candidate requires fresh hash binding and a NEW independent acceptance review by a fresh
reviewer session. Tier-0/staging/commit remain orchestrator-only after that PASS.

`RECORD: single use. Activation under the owner's standing authorization must name this document's
exact SHA-256, the implementer identity, and a ≤24h window.`


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `auth-qa-provider-probe-reliability-a1-am3-rev2-20260719`, event_id `2f37d479a954456ab281daa1ef5a0ba4`, ts `2026-07-19T19:08:32Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
