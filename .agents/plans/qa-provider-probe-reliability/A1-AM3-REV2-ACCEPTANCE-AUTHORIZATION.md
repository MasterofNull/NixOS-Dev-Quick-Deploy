# QPPR A1-AM3 rev2 candidate-acceptance authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-a1-am3-rev2-acceptance-20260719`
**Status:** PREPARED_ONLY until owner activation (standing authorization applies)
**Required reviewer:** `claude-subagent-qppr-a1-am3-rev2-acceptance-reviewer` — flagship tier,
FRESH session; excluded: the Sonnet implementer, the first acceptance reviewer session (whose
REQUEST_REVISION `A1-AM3-CANDIDATE-ACCEPTANCE.md` is retained lineage), the Opus design/rebind
reviewer, the orchestrator. **Single use; ≤24h window.**

## Frozen revised-candidate subject

| Path | Required SHA-256 |
|---|---|
| `scripts/testing/qa-provider-probe.py` | `f8280792a9ffa23acbb333ed22922c26899fe794879290d715db784826041308` |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `f4ca8241583575bf3e079f15194168b98926df340cddf2465c3733e4d7594781` |

Seven frozen paths must match the revision authorization (`224447ad…`): `result.py` `37821dcf…`,
verifier `4f5ce42e…`, plus the five original frozen paths incl. smoke `98a1c8f2…`. Lineage: first
acceptance REQUEST_REVISION with findings A/B and required revisions R-A1/R-A2/R-A3; revision
authorization `224447ad…` (consumed); owner activation + window amendment PULSE entries.

## Acceptance criteria

1. All nine hashes exact; deltas confined to the two MODIFY paths (diff the two revision
   predecessors `38940640…`/`15dbe325…` → current to confirm revision scope only).
2. **R-A1 verified in the bytes against finding A**: the publication callback now drives the join
   to COMMITTED or synchronously CANCELLED inside the callback window (`_finalize_join` idempotent,
   shared with a post-return no-op path); `completed` acknowledgement reachable only after the
   terminal projection is committed; default-disposition redelivery can no longer kill ahead of the
   terminal write; custom/ignored dispositions cannot observe a late write (AM2 §5.2 ordering).
   Re-read the first acceptance verdict's finding A and confirm each element is actually closed.
3. **R-A2 verified**: no terminal-heartbeat write reachable on a cancelled join (the former
   `qa-provider-probe.py:597-605` path); cancelled joins emit no terminal projection.
4. **R-A3 verified**: the six new `SignalPathAdversarialTests` genuinely prove the adversarial
   cases (real-SIGTERM subprocess proofs for default/custom/ignored dispositions, duplicates,
   write-spy no-late-write) — deterministic via marker-file event barriers, no sleep-only
   assertions; adjudicate the implementer's two disclosed debugging deviations (flaky sleep
   replaced by event barrier; PATH-scoped pure-Python fixture avoiding real agent CLI collision).
5. Fresh re-run: adoption 24/24, frozen lifecycle 39/39, verifier 611/0, py_compile/bash -n/
   diff-check/secret scan clean, no daemon-publication pattern.
6. Governance trail correct order via canonical writers (incl. the implementer's pre-window
   refusal and the owner window amendment); no prohibited action; nothing staged.

## Allowance

As the prior acceptance grants: bounded reads, `sha256sum`, criterion-5 commands, path-limited
git/`rg`. Writes: one verdict artifact
`.agents/plans/qa-provider-probe-reliability/A1-AM3-REV2-ACCEPTANCE.md` (identity/model, hashes,
per-criterion evidence, terminal `VERDICT: PASS` or `VERDICT: REQUEST_REVISION — <reason>`) and
one closing pulse (emitted BEFORE the final report). PASS authorizes only the orchestrator to run
Tier-0, stage, and commit; A2 remains blocked pending its own rebind.

`RECORD: single use. Activation must name this document's exact SHA-256, the reviewer identity,
and a ≤24h window.`
