# B3-C1 candidate — Codex acceptance authorization

**Status:** PREPARED — Codex binding acceptance (Codex is back online 2026-07-22; the designated
implementation-acceptance lane per the operating model). Prepared by Fable 5 orchestrator.
**Required reviewer:** Codex (headless), a session distinct from the Sonnet implementer.

## Frozen candidate (staged, uncommitted)

| Op | Path | SHA-256 |
|---|---|---|
| NEW | `scripts/governance/aq-canon-compiler.py` | `72d21a996a0056e78ef7b99f9e3335597e436a2d26c36da7e52ea9b5ca9675ac` |
| NEW | `config/schemas/aq-canon-spec-v1.json` | `43903df84f040cef8c7d0aca383711dca52f086e6523758c91aa6721d4fd64fc` |
| NEW | `scripts/testing/test-aq-canon-compiler.py` | `087b6642dd6890fd1cf28ca740224596a606ac80cdc35795aea9d9c3d7c464b9` |
| MODIFY | `scripts/governance/tier0-validation-gate.sh` | `5517cbf8540802c2970786a2ac6b7e5761e9506f27fc2b76588c393aa09954d7` |

Authority: `B3-C1-CANON-COMPILER-AUTHORIZATION.md` — now **ACTIVATED** (§6 Owner Activation Record,
2026-07-22), current hash `faad68dd8d93b1da9521336ae378cf5081ae7da84d61c762ba9c4c555f289461`; its
contract (§§1–4) was Opus-re-reviewed sound against pre-activation hash `d6676252…`
(`.agents/plans/stream-auth-rereview/claude.md`). 5-file ceiling (4 touched; the FLAGSHIP-REVIEW.md
is the 5th, pre-existing). Predecessor `tier0-validation-gate.sh` = `da91d135…`.

**Note to reviewer:** the controlling authorization is now ACTIVATED (implementation_authorized=TRUE
in its §6). This is a fix to an earlier Codex REQUEST_REVISION that correctly flagged the doc still
read PREPARED_ONLY. Proceed with binding acceptance of the candidate below.

## Acceptance criteria for Codex

1. All 4 hashes match exactly; only these 4 changed; no 5th/6th file touched (the review doc is
   pre-existing, not part of this candidate's diff).
2. `aq-canon-compiler.py` is a pure read-only generator: no `os.system`/`subprocess`/socket/network/
   DB/exec; stdlib + `jsonschema` only; writes only to stdout or an explicit `--out-dir`; fail-closed
   (invalid spec/schema → non-zero exit + error).
3. **Determinism (the core invariant):** same input → byte-identical output. Re-verify by running the
   compiler twice on a real repo schema and confirming identical SHA-256 (the implementer reports
   `c372770a…` across two runs — reproduce).
4. The `tier0-validation-gate.sh` edit is a MINIMAL additive registration
   (`gate_canon_compiler_determinism`) that does not alter any other gate; run that check in
   isolation and confirm it passes.
5. `python3 scripts/testing/test-aq-canon-compiler.py` passes (implementer reports 13/13); py_compile
   clean; `git diff --check` clean; no secret/credential added.
6. No prohibited action (no runtime authority granted to the compiler; nothing staged beyond these 4
   plus B3-C1 governance docs; the L2B-B/VF-7 files are separate slices — do not conflate).

Return a terminal line: `VERDICT: PASS` or `VERDICT: REQUEST_REVISION — <reason>`. On PASS the
orchestrator runs Tier-0 (which now includes the new canon-compiler determinism gate) and commits.

`RECORD: PREPARED. Codex binding acceptance; commit only after PASS.`
