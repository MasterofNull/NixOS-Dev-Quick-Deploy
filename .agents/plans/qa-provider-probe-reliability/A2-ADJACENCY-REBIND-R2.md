# QPPR-A2 adjacency rebind — revision 2 (runtime-surface adjacency)

**Status:** PREPARED_ONLY / awaiting independent review
**Prepared:** 2026-07-20, Fable 5 orchestrator/architect session
**Supersedes:** `A2-ADJACENCY-REBIND.md` (R1, `b6c93ff5bf0a5638168229842876f94ed72be6b4aae9fec68361f8a49026e594`) — retained as lineage; its independent review `A2-ADJACENCY-REBIND-REVIEW.md` returned REQUEST_REVISION on two defects, both corrected here.
**Satisfies:** `A1-AM3-PREREQUISITE-REBIND.md` §5 (A2's required adjacency rebind after accepted+committed A1-AM3).

## 0. Why R2 exists — the two R1 defects, corrected

R1's independent review (Opus) returned REQUEST_REVISION on exactly two points; items 1, 2, 4, 5 and all twelve subject/target hashes PASSED and are carried forward unchanged (§2–§6):

1. **Adjacency proof stale (crux #1).** R1 §1 claimed HEAD equals A1-AM3 (`3396f9df`) with `git log 3396f9df..HEAD` empty. That is false: two governance-doc commits have since landed (`28bff4a4` Rule 17, `30f3f70b` the R1 rebind docs themselves), and under the owner's staged-for-codex operating model (PULSE `[owner] [operating-model-directive]` 2026-07-19) A2 will not commit until codex returns 2026-07-25, so further governance commits will intervene. The literal design-packet §5.4 rule ("no unrelated commit may intervene between A1 and A2 / land consecutively") is therefore unsatisfiable. **Resolved by the owner's structured waiver** (PULSE `[owner] [design-rule-waiver]` 2026-07-19) reinterpreting §5.4 as runtime-surface adjacency — see §1.
2. **Malformed C1C hash (crux #2).** R1 §1 line 28 wrote the C1C full hash as `1cca8c57a4f58b4f1b1aa1eae509cf6d800e65a` (39 chars, dropped one digit), making its `git merge-base --is-ancestor` command non-reproducible. Corrected here to the true `1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a` (`git rev-parse 1cca8c57`).

## 1. Runtime-surface adjacency (owner-waived reinterpretation of §5.4)

**Owner waiver, verbatim intent** (PULSE `[owner] [design-rule-waiver]` 2026-07-19): design-packet §5.4 is reinterpreted as **runtime-surface adjacency** — A2 commits *after* A1-AM3 (`3396f9df`), and **no commit between `3396f9df` and the eventual A2 commit modifies A1's heartbeat runtime surface or any of A2's five target files**; governance/design/doc-only commits are exempt. This preserves §5.4's actual intent (no drift between the probe that produces `qa.provider-probe-active.v1` and the dashboard card that projects it) while being satisfiable under the staged-for-codex model.

**Definitions (concretely checkable at A2-commit time):**
- *A1 heartbeat runtime surface* = every file committed as an A1-AM3 (`3396f9df`) or C1C (`1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a`) runtime candidate: `scripts/testing/qa-provider-probe.py`, `scripts/testing/harness_qa/core/result.py`, `scripts/testing/harness_qa/core/process_lifecycle.py`, `scripts/testing/test-qa-provider-probe-lifecycle.py`, and the five frozen A1 candidate paths (`smoke-flagship-cli-surfaces.sh`, `phase0.py`, `context.py`, `main.py`, `json_out.py`), plus the schema `qa.provider-probe-active.v1`.
- *A2 target files* = the five in §3.1.

**Intervening commits observed so far, verified governance-only:**

| Commit | Files touched | Intersects A1 runtime surface or A2 targets? |
|---|---|---|
| `28bff4a4` | `.agent/{CODEX,GEMINI,LOCAL-AGENT,WORKFLOW-CANON}.md`, `.claude/CLAUDE.md` | No — all agent instruction docs |
| `30f3f70b` | `.agent/memory/issues-backlog.md`, `A2-ADJACENCY-REBIND.md`, `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md`, `C1C-IMPLEMENTATION-AUTHORIZATION.md`, `C1C-PUBLICATION-ACK-DESIGN-PACKET.md` | No — issue log + governance docs |

Both are disjoint from the A1 runtime surface and A2's five targets (`git show --stat` on each). **The runtime-surface adjacency invariant holds.** It must be **re-verified at A2-commit time** against the then-current commit range `3396f9df..HEAD` — any commit in that range that touches an A1-runtime-surface file or an A2 target file breaks adjacency and requires a fresh reviewed rebind before the A2 commit. Governance/doc commits (this R2, its review, the acceptance authorization, the eventual acceptance verdict) do not.

C1C (`1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a`) is A1-AM3's ancestor (`git merge-base --is-ancestor` returns 0), consistent with the accepted C1C → A1-AM3 chain.

## 2–6. Carried forward from R1 (verified PASS, unchanged)

The following R1 sections are unchanged and were independently confirmed correct; they are incorporated by reference and reproduced in substance:

- **A2's slice** (R1 §2): existing-card visibility slice — one pure bounded reader for the C1A-validated `.agent/qa/provider-probe-active.json` heartbeat in `qa_runner.py`; a validated `projection_only=true` early-return branch on `/aq-qa/run/0` in `aistack.py`; six accessible rows on the existing QA Phase 0 Status card in `dashboard.html`; a 1s-active/2s-idle single-flight cancellable poller with `setText`-only rendering in `assets/dashboard.js`; one new focused offline test. Five files exactly. Projection is never pass/fail authority.
- **Recomputed hashes** (R1 §3): every referenced governance/prerequisite hash byte-exact (design packet `44b600bf…`, rebind amendment `51200b64…`, PRD `7f4bf98c…`, original A2 authorization `7a4a2cf4…`, C1A acceptance `73808146…`, C1B-AM1 acceptance `1373f508…`); C1A commit `52b0a071…` and C1B-AM1 commit `f54cd8c8…` confirmed ancestors of HEAD.
- **A2's five-path ceiling** (R1 §3.1): `qa_runner.py` `abc105fc…`, `aistack.py` `8ae69185…`, `dashboard.html` `801a50b2…`, `assets/dashboard.js` `4e3b44cb…` all byte-unchanged; `scripts/testing/test-dashboard-qa-provider-probe.py` absent (no symlink). Zero byte changes required on A2's own ceiling; `git status --short` clean on all five.
- **Stale→current mapping** (R1 §4): only two UNRESOLVED placeholders, both in `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` §1 — A1 accepted commit → `3396f9df0493796e56c9f7ba34895c9b00667f01`; A1 acceptance → `A1-AM3-REV2-ACCEPTANCE.md` (`d308e3ba1fb66d28ac4cf6ab833524e24ad36b0c31dd0a0a26eda90f26607ea2`, VERDICT: PASS).
- **Technical-requirement impact** (R1 §5): none. A2 binds exclusively to the C1A wire contract `qa.provider-probe-active.v1` (schema `1acaa61d…`, unchanged) and the JSON artifact by path — never to `qa-provider-probe.py` internals, the C1B observer, or the publication barrier. A1-AM3's two behavioral changes (terminal write gated behind `COMMITTED`; join driven to COMMITTED/CANCELLED inside the barrier callback) make *fewer, more trustworthy* writes and alter no JSON shape/field/freshness semantics; A2 already treats missing/stale/malformed/unbound heartbeats as non-healthy, so it has zero coupling to the legacy daemon path or old verifier. Net-positive; no design revision.
- **Disposition** (R1 §6): REBIND-ONLY plus the in-place `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` revision (its §0). `A2-IMPLEMENTATION-AUTHORIZATION.md` needs no edit (superseded for activation by the AM1 document).

## 7. What must still happen before A2 can activate

1. Independent flagship review of **this R2 rebind** and the revised `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` (a different reviewer than any prior A2 preparer/reviewer; exact-hash verification incl. the runtime-surface adjacency verification of §1).
2. After that `PASS`, owner activation naming the exact revised authorization hash, implementer `claude-subagent-qppr-a2-am1-implementer` (balanced/Sonnet, Rule-17 rationale in authorization §0), and a ≤24h window.
3. A bounded implementer performs the exact five-file candidate; under the staged-for-codex operating model the candidate is **staged (uncommitted)** and queued in `.agent/collaboration/CODEX-REVIEW-QUEUE.md` for **codex binding acceptance** on its 2026-07-25 return; only after codex `PASS` does the orchestrator run Tier-0 and commit — at which point §1's runtime-surface adjacency is re-verified against the then-current `3396f9df..HEAD` range.
4. No real provider run, live API/browser vetting, deployment, traffic, or rollback is authorized by this rebind or the resulting A2 commit — those remain behind the separate paired live-vetting grant.

## 8. Stops (unchanged)

Every stop in `A2-IMPLEMENTATION-AUTHORIZATION.md` §4, `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` §4, and `A1-A2-ADOPTION-DESIGN-PACKET.md` §6–7 remains in force. This record authorizes no implementation, staging, commit, provider/network/live action, heartbeat/evidence write, dashboard/API mutation, deployment, or rollback; performs no product-code edit; issues no verdict.

`RECORD: PREPARED_ONLY. Supersedes R1. Awaiting independent flagship PASS over this R2 rebind and the revised A2-AM1-IMPLEMENTATION-AUTHORIZATION.md; until that PASS and owner activation, A2 and all live actions remain unauthorized.`
