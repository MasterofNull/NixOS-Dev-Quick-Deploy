# QPPR-A2 adjacency rebind R2 — independent flagship review

**Reviewer identity:** `claude-subagent-qppr-a2-rebind-r2-reviewer`
**Model:** Claude Opus 4.8 (`claude-opus-4-8`)
**Role:** independent flagship architecture / security / SRE / QA / authorization reviewer — no
authorship stake in the reviewed documents (R2 drafted by the Fable orchestrator; R1 by a Sonnet
architect; R1 reviewed by a prior Opus session). Design / inactive-authorization gate only. A PASS
makes A2 eligible for owner activation; it is **not** implementation acceptance.
**Reviewed:** 2026-07-20
**Subjects:**
- `A2-ADJACENCY-REBIND-R2.md`
- `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md`

## Recomputed hashes (this session)

### Subjects
| Document | Expected | Recomputed | Result |
|---|---|---|---|
| `A2-ADJACENCY-REBIND-R2.md` | `1156b3fd9cd4ec30360212ae93923661ee47b5022c687f6dec7739726279ca5d` | identical | **exact** |
| `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `76b22fb5015452c1b336e3945c31377e09f6c2c6d51f0bc360d89ded7dbe9f82` | identical | **exact** |

### Referenced governance / prerequisite artifacts (recomputed against disk)
| Subject | Recorded | Recomputed | Result |
|---|---|---|---|
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `44b600bf…c79f18` | `44b600bf…c79f18` | exact |
| `A1-A2-ADOPTION-REBIND-AMENDMENT.md` | `51200b64…1477dc` | `51200b64…1477dc` | exact |
| `PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` (`.agent/`) | `7f4bf98c…bebf0d` | `7f4bf98c…bebf0d` | exact |
| `A2-IMPLEMENTATION-AUTHORIZATION.md` | `7a4a2cf4…f1d68e` | `7a4a2cf4…f1d68e` | exact |
| `C1A-IMPLEMENTATION-ACCEPTANCE.md` | `73808146…1d1987` | `73808146…1d1987` | exact |
| `C1B-AM1-IMPLEMENTATION-ACCEPTANCE.md` | `1373f508…b270c868` | `1373f508…b270c868` | exact |
| `A1-AM3-REV2-ACCEPTANCE.md` | `d308e3ba…607ea2` | `d308e3ba…607ea2` (VERDICT: PASS, line 218) | exact |
| `qa.provider-probe-active.v1` schema (`config/qa-provider-probe-contract.schema.json`) | `1acaa61d…16b7ac4` | `1acaa61d…16b7ac4` | exact |

### A2 five-file ceiling (recomputed against live working tree)
| # | Path | Recorded predecessor | Recomputed | Result |
|---:|---|---|---|---|
| 1 | `dashboard/backend/api/services/qa_runner.py` | `abc105fc…6ec0e0` | `abc105fc…6ec0e0` | unchanged |
| 2 | `dashboard/backend/api/routes/aistack.py` | `8ae69185…b48db` | `8ae69185…b48db` | unchanged |
| 3 | `dashboard.html` | `801a50b2…d93323` | `801a50b2…d93323` | unchanged |
| 4 | `assets/dashboard.js` | `4e3b44cb…90c8b6` | `4e3b44cb…90c8b6` | unchanged |
| 5 | `scripts/testing/test-dashboard-qa-provider-probe.py` (NEW) | absent | absent (no symlink) | unchanged |

### Git anchors
| Anchor | Check | Result |
|---|---|---|
| C1C full hash | `git rev-parse 1cca8c57` = `1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a` | exact (40 chars) |
| C1C → A1-AM3 ancestry | `git merge-base --is-ancestor 1cca8c578…65a 3396f9df` | exit 0 (ancestor) |
| C1C = A1-AM3 parent | `git rev-parse 3396f9df^` = `1cca8c578…65a` | confirmed |
| HEAD | `git rev-parse HEAD` = `30f3f70b7ca2…` | R2 docs are uncommitted working-tree changes |
| Range `3396f9df..HEAD` | exactly `28bff4a4`, `30f3f70b` | two governance commits |
| C1A commit `52b0a071` | ancestor of HEAD | exit 0 |
| C1B-AM1 commit `f54cd8c8` | ancestor of HEAD | exit 0 |

## Findings

### 1. Subject-hash integrity & coherence — PASS
Both subjects recomputed byte-exact against the required values. No concatenation/amendment seams:
the AM1 §0 revision block is a clean, explicitly disclosed in-place re-revision of a
never-activated PREPARED_ONLY authorization (§0 discloses both the 2026-07-19 and 2026-07-20 edits
and preserves technical content). R2 reads as a single coherent artifact; its §0 correctly names the
two R1 defects and carries R1 items 1,2,4,5 forward by reference.

### 2. Crux #1 — runtime-surface adjacency — PASS
(a) **Owner waiver exists and says this.** PULSE.log line 323 `[owner] [design-rule-waiver]` and
line 321 `[owner] [operating-model-directive]` are present. The waiver verbatim reinterprets
design-packet §5.4 as RUNTIME-SURFACE ADJACENCY — "A2 commits after A1-AM3 (3396f9df) and no commit
between 3396f9df and the eventual A2 commit modifies A1's heartbeat runtime surface … or any of A2's
five target files; governance/design/doc-only commits are exempt," citing the same two commits
(`28bff4a4`, `30f3f70b`) and directing the R2 draft + C1C fix + mandatory independent review. R2 §1
faithfully mirrors the waiver text and intent.
(b) **Intervening commits governance/doc-only and disjoint.** `git show --stat`: `28bff4a4` touches
only agent-instruction docs (`.agent/{CODEX,GEMINI,LOCAL-AGENT,WORKFLOW-CANON}.md`, `.claude/CLAUDE.md`)
— Rule 17; `30f3f70b` touches `issues-backlog.md` + five governance docs (the R1 rebind pair + two
C1C base docs). Neither intersects the A1 heartbeat runtime surface (`qa-provider-probe.py`,
`result.py`, `process_lifecycle.py`, `test-qa-provider-probe-lifecycle.py`, the five frozen A1
candidate paths, the schema) nor A2's five targets. R2 §1's table is accurate.
(c) **Faithful to §5.4 intent, not evasive.** Design-packet line 25 ("land consecutively") and lines
278-280 (§5 item 4: "No unrelated commit may intervene between A1 and A2") exist to prevent drift
between the A1 probe that produces `qa.provider-probe-active.v1` and the A2 card that projects it.
The reinterpretation still hard-stops on any commit touching the A1 runtime surface or A2's targets,
permitting only governance/doc commits — so a commit that could cause probe→dashboard drift breaks
adjacency and forces a fresh reviewed rebind. Intent preserved.
(d) **Concretely checkable at A2-commit time.** The invariant is expressed as a decidable predicate
over `3396f9df..HEAD` against two enumerated file sets, re-verified at commit time (R2 §1; AM1
§2/§4). Checkable as written.

### 3. Crux #2 — C1C hash — PASS
R2 corrects the C1C full hash to `1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a`. `git rev-parse 1cca8c57`
returns exactly that (40 chars); `git merge-base --is-ancestor 1cca8c578…65a 3396f9df` returns 0;
C1C is also A1-AM3's direct parent. The malformed 39-char R1 hash appears only in R2 §0's explicit
"defect being corrected" description, never in an operative clause.

### 4. Carried-forward content still valid — PASS
Five-path ceiling byte-unchanged on the live tree (all four MODIFY hashes exact, NEW path absent incl.
no symlink). Both formerly-UNRESOLVED fields closed to real values: A1 accepted commit
`3396f9df0493796e56c9f7ba34895c9b00667f01` and acceptance `A1-AM3-REV2-ACCEPTANCE.md`
(`d308e3ba…607ea2`, VERDICT: PASS at line 218). Rebind-only disposition sound: A2 binds only to the
stable `qa.provider-probe-active.v1` wire contract (schema `1acaa61d…` unchanged) and reads the JSON
heartbeat by path; C1C/A1-AM3 changed only how reliably the file is written, not its shape/fields/
freshness. Sonnet implementer identity `claude-subagent-qppr-a2-am1-implementer` with Rule-17
rationale (Codex quota-exhausted to 2026-07-25; local-Qwen envelope too narrow for multi-site work;
balanced tier cheapest capable — recorded deviation) intact; consistent with Rule 17 as committed at
`28bff4a4`.

### 5. Auth-document consistency — PASS
Every activation-gating reference in the revised authorization points to R2: §1 prerequisites table
("Adjacency rebind (this cycle) | A2-ADJACENCY-REBIND-R2.md"), §1 activation precondition, §2 stop
clause, §4 activation gate ("this document and A2-ADJACENCY-REBIND-R2.md together"), and §0. The two
`A2-ADJACENCY-REBIND.md` (R1) mentions (§0 items 3 and 5) are lineage/evidence pointers to
retained-superseded analysis whose substance R2 §2-6 incorporates by reference — not activation
gates. No stale literal-adjacency language ("immediately after / no unrelated intervening commit /
land consecutively") remains in any operative clause of either document (the only occurrences are
R2 §0's quoted description of the corrected R1 defect); the §2 and §4 hard-stops now read in
runtime-surface terms. The staged-for-codex acceptance path is correctly reflected: candidate staged
(uncommitted), queued for codex binding acceptance on 2026-07-25, orchestrator commits only after
codex PASS with runtime-surface adjacency re-verified at that time (§4, §7.3, R2 §7.3).

### 6. Fabrication sweep — PASS
Every hash in both documents corresponds to real on-disk/git bytes: 2 subjects, C1C full hash + its
ancestry/parent, five-file ceiling (4 hashes + 1 confirmed absence), and 8 referenced governance/
prerequisite artifacts (design packet, rebind amendment, PRD, original A2 auth, C1A acceptance,
C1B-AM1 acceptance, A1-AM3-REV2 acceptance, schema). C1A and C1B-AM1 commits confirmed HEAD ancestors.
No non-resolvable object, no non-reproducible verification command.

## Summary
All six adjudicated items PASS. R2 corrects exactly the two R1 REQUEST_REVISION defects: the stale/
false literal-adjacency proof is replaced by an owner-waived runtime-surface adjacency invariant that
is present in PULSE.log, faithful to §5.4's anti-drift intent, verified against the two disjoint
governance commits, and decidably re-checkable at A2-commit time; and the malformed 39-char C1C hash
is corrected to the true 40-char `1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a` with a reproducible
merge-base. All carried-forward R1 PASS content re-verified exact on the live tree. Both documents
remain PREPARED_ONLY. This PASS makes A2 eligible for owner activation naming the exact revised
authorization hash `76b22fb5015452c1b336e3945c31377e09f6c2c6d51f0bc360d89ded7dbe9f82`; it is not
implementation acceptance, and no provider/network/live/deploy/commit action is authorized.

VERDICT: PASS
