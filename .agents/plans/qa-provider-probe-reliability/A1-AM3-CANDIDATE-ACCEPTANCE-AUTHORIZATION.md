# QPPR A1-AM3 candidate-acceptance authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-a1-am3-acceptance-20260719`
**Status:** PREPARED_ONLY until owner activation (standing authorization applies)
**Prepared:** 2026-07-19 UTC, Fable 5 orchestrator session
**Required reviewer:** `claude-subagent-qppr-a1-am3-acceptance-reviewer` — flagship tier, fresh
session; must not be the Sonnet implementer, the Opus design/rebind reviewer, the C1C-AM3
acceptance reviewer session, or the orchestrator
**Single use; ≤24h window on activation**

## Frozen candidate subject (four MODIFY)

| Path | Required SHA-256 |
|---|---|
| `scripts/testing/qa-provider-probe.py` | `3894064065607ac4e8437c404aec81285b7ab3d9c2087a83f7f9e59bd6747e84` |
| `scripts/testing/harness_qa/core/result.py` | `37821dcffa3ec98ddfc1cb82ed965d518b7f0bf0fa9088fb369be9cfe1b0d550` |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `15dbe32592a2a4994c357c76921fac92ec9866bcf25b5f67010a098e1b42fa4a` |
| `scripts/testing/verify-flake-first-roadmap-completion.sh` | `4f5ce42ed1f6163d82c1b6c4c913cc4b2dc800e4723591a4ea302e8063529be4` |

Five frozen paths must remain at the final-rebind hashes (`98a1c8f2…`, `b01edf13…`, `ef299307…`,
`2137974e…`, `7d62ff15…`). Lineage: implementation authorization `bedd3eec…` (consumed), final
rebind `711c8c6f…`, rebind review PASS, owner activation PULSE of 2026-07-19T08:45Z window.

## Acceptance criteria (all mandatory)

1. All nine hashes match exactly; predecessor deltas confined to the four MODIFY paths.
2. **4.1 barrier integration (crux A):** the candidate uses EXCLUSIVELY the accepted C1C
   `publication_barrier` (`process_lifecycle.py` at committed `c7407ea4…` — read its contract);
   verify in the bytes that `publication_fd` wiring is correct per that contract, that the
   implementer's reading — barrier activates only on mid-run signal; ordinary return path drives the
   same `try_commit` synchronously — matches AM2 section 4.1's requirement, that `completed` is
   acknowledged only after terminal projection commit + full reader/ticker join, `cancelled` only
   after synchronous disable + join, absolute deadline respected, no post-return continuation, and
   that a `_PublicationContractViolation` fail-stops the aggregate without retry or lock-release.
3. **Verifier recovery (crux B, anti-gaming):** the rewritten check at the former line 597 must
   verify architecture (positive `exec python3 … --machine` delegation + Phase-0 direct-call
   assertion + negative legacy-pattern rejections) rather than gaming the old grep; confirm it
   passes against the frozen smoke candidate `98a1c8f2…` unmodified and would FAIL against a
   reintroduced legacy loop (reason through the assertions; fixture proof exists in the new
   adoption tests). The disclosed 611-vs-609 count deviation is spec-driven; adjudicate it.
4. AM2 sections 4.2–4.5 verified in the bytes: terminal-record validation before join commit;
   canonical-mode fail-closed on missing/invalid `qa_invocation_id` before lock/policy access;
   `O_CREAT|O_EXCL` lock-inode semantics (new=0600-verified, pre-existing=validated-never-chmod);
   self-contained `details` validation in `CheckResult.to_dict()` — adjudicate the implementer's
   no-new-dependency choice (self-contained validator instead of `jsonschema` in production path).
5. Fresh re-run of the full validation set: adoption tests (18/18 expected), frozen C1C lifecycle
   suite (39/39, must be unaffected), `verify-flake-first-roadmap-completion.sh` (611/0 expected),
   `py_compile`/`bash -n`/`git diff --check`, secret scan (no matches in diff), no new
   daemon-publication thread pattern.
6. Governance trail complete via canonical writers, in correct order this time (resume/intent
   BEFORE edits); no prohibited action (no fifth file, no frozen-path edit, no provider/network/
   live action, no A2 work, nothing staged, no self-acceptance).

## Reviewer allowance

Bounded reads of subject + lineage; `sha256sum`; the criterion-5 commands; path-limited
`git status/diff`; `rg -n` in subject paths. Writes: one verdict artifact
`.agents/plans/qa-provider-probe-reliability/A1-AM3-CANDIDATE-ACCEPTANCE.md` (identity/model,
recomputed hashes, per-criterion evidence, deviation adjudications, terminal `VERDICT: PASS` or
`VERDICT: REQUEST_REVISION — <reason>`) and one closing pulse as the reviewer identity, emitted
BEFORE the final report. PASS authorizes only the orchestrator to run Tier-0, stage, and commit.
A2 remains blocked pending its own adjacency rebind and activation.

`RECORD: single use. Activation under the owner's standing authorization must name this document's
exact SHA-256, the reviewer identity, and a ≤24h window.`
