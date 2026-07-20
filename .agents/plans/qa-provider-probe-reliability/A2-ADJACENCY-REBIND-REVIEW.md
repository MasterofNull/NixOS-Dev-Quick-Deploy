# QPPR-A2 adjacency rebind — independent flagship review

**Reviewer identity:** `claude-subagent-qppr-a2-rebind-reviewer`
**Model:** Claude Opus 4.8 (`claude-opus-4-8`)
**Role:** independent flagship architecture / security / SRE / QA / authorization reviewer — no
authorship stake in the reviewed documents; design / inactive-authorization gate only (a PASS makes
A2 eligible for owner activation under the standing authorization; it is not implementation
acceptance).
**Reviewed:** 2026-07-20
**Subjects:**
- `A2-ADJACENCY-REBIND.md`
- `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md`

## Recomputed hashes (this session, twice — pre- and post-interruption; stable)

### Subjects
| Document | Expected | Recomputed | Result |
|---|---|---|---|
| `A2-ADJACENCY-REBIND.md` | `b6c93ff5bf0a5638168229842876f94ed72be6b4aae9fec68361f8a49026e594` | `b6c93ff5bf0a5638168229842876f94ed72be6b4aae9fec68361f8a49026e594` | **exact** |
| `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `995ed4cb18d3c158ef06bebd094e8c52b0c71dd90480eccf3f0b8d258373bd66` | `995ed4cb18d3c158ef06bebd094e8c52b0c71dd90480eccf3f0b8d258373bd66` | **exact** |

### Referenced governance documents (all recomputed against disk)
| Subject | Recorded | Recomputed | Result |
|---|---|---|---|
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `44b600bf…c79f18` | `44b600bf…c79f18` | exact |
| `A1-A2-ADOPTION-REBIND-AMENDMENT.md` | `51200b64…1477dc` | `51200b64…1477dc` | exact |
| `PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` | `7f4bf98c…bebf0d` | `7f4bf98c…bebf0d` | exact |
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
| 5 | `scripts/testing/test-dashboard-qa-provider-probe.py` (NEW) | absent | absent (confirmed) | unchanged |

### Commit anchors
| Anchor | Expected | Verified |
|---|---|---|
| A1-AM3 accepted commit `3396f9df` | HEAD-adjacent, subject "feat(qa): land A1-AM3…" | commit exists, subject matches; **but NOT HEAD (see Finding 3)** |
| C1A commit `52b0a071` | ancestor of HEAD | YES |
| corrected C1B-AM1 commit `f54cd8c8` | ancestor of HEAD | YES |
| C1C commit `1cca8c57` (short) | A1-AM3 direct parent | YES — real parent = `1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a` |

## Findings

### 1. Subject-hash integrity & coherence — PASS
Both subjects recomputed byte-exact against the required values, twice (pre- and post-interruption).
No concatenation or amendment seams: the AM1 document's §0 "Revision notice" is a clean, explicitly
disclosed in-place revision block, not a spliced seam; the rebind document reads as a single coherent
artifact.

### 2. Disposition correctness ("rebind-only") — PASS (design substantively correct)
A2's five bound targets are byte-identical to their recorded predecessors and the NEW path is absent.
Neither the C1C commit (`1cca8c57`) nor the A1-AM3 commit (`3396f9df`) touches any of the five paths
— verified against both commit file-lists (C1C changed 22 files: A1-AM3 governance docs + harness_qa
core/phase0/main/json_out, `qa-provider-probe.py`, smoke/verify scripts; A1-AM3 changed its 9 accepted
paths) and via an empty `git log 3396f9df..HEAD -- <five A2 paths>`. A2 binds only to the stable
`qa.provider-probe-active.v1` wire contract (schema hash `1acaa61d…` verified unchanged on disk) and
reads the JSON heartbeat artifact by path; it does not import or reason about `qa-provider-probe.py`
internals, the C1C publication barrier, the legacy daemon-publication path, or the old verifier
pattern. A1-AM3's two behavioral changes (terminal heartbeat write gated exclusively behind a
`COMMITTED` join; the join driven to `COMMITTED`/synchronous `CANCELLED` inside the barrier callback)
only make *fewer, more trustworthy* writes reach the file — they do not alter the JSON shape, field
set, or freshness semantics A2 consumes, all of which A2 already treats defensively. **A2's design
requirements are not invalidated by C1C/A1-AM3; the disposition is substantively correct.** (This
finding is about the design; the adjacency/commit-placement claim is adjudicated separately in
Finding 3.)

### 3. Adjacency binding — FAIL
The rebind's central proof is stale and false at review time. The document asserts (§1): "HEAD equals
the A1-AM3 commit itself," "`git log 3396f9df..HEAD` is empty," and a future A2 commit "would land as
the immediate next commit after A1, exactly as required." Recomputed:
- `git rev-parse HEAD` = `30f3f70b7ca2b5cb43c5564134c845dbba7bc4ea` — **not `3396f9df`**.
- `git rev-list --count 3396f9df..HEAD` = **2**. Two commits have landed since A1-AM3:
  - `28bff4a4` docs(governance): add Rule 17 — modifies 5 agent-instruction files; unrelated to the
    A2 code slice.
  - `30f3f70b` docs(qa): A2 adjacency rebind + C1C base governance docs + issue log — the rebind
    documents themselves; governance, not the A2 code commit.

Design packet `A1-A2-ADOPTION-DESIGN-PACKET.md` §1 ("the slices … must land **consecutively on the
same branch**") and §5 item 4 ("A2 must immediately follow … **No unrelated commit may intervene
between A1 and A2**") are now unsatisfiable for a future A2 implementation commit on this branch — at
least two commits already sit between `3396f9df` and any future A2 commit. The authorization's own
self-imposed stop (`A2-AM1…` §2: "**Any unrelated intervening commit** or byte/absence drift is a
hard stop requiring another reviewed rebind") is therefore tripped, and §4/§7.3's activation
precondition ("immediately after `3396f9df` with no unrelated intervening commit") cannot be met.
A2's five *predecessor byte-hashes* remain exact (that sub-claim holds), but the adjacency guarantee
the document exists to provide does not.

### 4. Stale-field closure — PASS
Both previously-`UNRESOLVED` fields are closed to real values: A1 accepted commit =
`3396f9df0493796e56c9f7ba34895c9b00667f01` (real commit) and A1 implementation acceptance =
`A1-AM3-REV2-ACCEPTANCE.md` (`d308e3ba…607ea2`, recomputed exact, VERDICT: PASS confirmed at line
218). A placeholder sweep found no live `UNRESOLVED`/`TBD`/`TODO`/`<pending>` — every remaining
"UNRESOLVED" string is a historical description of the old value now closed.

### 5. Implementer-identity revision — PASS
AM1 §0 discloses the change as an in-place revision of a never-activated PREPARED_ONLY authorization
(legitimate on that basis). Rule-17 rationale recorded: Codex CLI quota-exhausted until 2026-07-25;
the local-Qwen envelope is measured as bounded single-command/single-edit only and cannot cover a
coordinated four-file-plus-new-test multi-site candidate; balanced (Sonnet) tier
`claude-subagent-qppr-a2-am1-implementer` is the cheapest capable tier under current constraints —
recorded as a deviation, not a preference. Technical content (five-file ceiling §2, frozen future
grant §3, stops §4) is preserved. Activation still requires an independent PASS plus explicit owner
activation naming the exact authorization hash, the implementer identity, and a ≤24h window. Consistent
with Rule 17 as committed at `28bff4a4`.

### 6. Fabrication sweep — FAIL (one defect)
Every hash in both documents corresponds to real on-disk bytes **except one**: the C1C full hash in
`A2-ADJACENCY-REBIND.md` §1 line 28, `1cca8c57a4f58b4f1b1aa1eae509cf6d800e65a`, is **39 characters**
— a "`8`" is dropped after `1cca8c57`. The real parent of `3396f9df` is
`1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a` (40 chars). The recorded command
`git merge-base --is-ancestor 1cca8c57a4f58b4f1b1aa1eae509cf6d800e65a HEAD` does **not** execute — it
errors `fatal: Not a valid object name` (reproduced this session), so the stated "confirms C1C is
A1-AM3's direct parent" output could not have been produced as written. The underlying *claim* is true
(the short form `1cca8c57` on lines 29/84 is correct and C1C genuinely is A1-AM3's parent), but a
recorded verification command is non-reproducible and a cited hash resolves to no object. All other
hashes (12 subjects/targets + schema + acceptance) are real.

## Summary
Items 1, 2, 4, 5 PASS; items 3 and 6 FAIL. The substance of the disposition (rebind-only; A2's five
files byte-unchanged and its design uncoupled from what C1C/A1-AM3 changed) is correct. But the
document's defining guarantee — exact commit adjacency — is false at review time (two unrelated
governance commits now sit between A1 and HEAD, tripping the packet's consecutive-commit rule and the
authorization's own hard-stop), and one recorded C1C hash/command is malformed and non-reproducible. A
PASS would let the owner activate an authorization whose own adjacency precondition is already
violated. Both defects are fixable by a fresh rebind cut against the true current HEAD (`30f3f70b`)
that (a) re-establishes or, with explicit owner waiver, formally reinterprets the §5.4
"no-unrelated-intervening-commit" requirement in light of the unavoidable governance commits, and
(b) corrects the C1C full hash to `1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a` and re-verifies the
merge-base command.

VERDICT: REQUEST_REVISION — (3) adjacency proof stale/false: HEAD is `30f3f70b`, not `3396f9df`; two unrelated commits (`28bff4a4` Rule 17, `30f3f70b` the rebind docs) now sit between A1 and HEAD, making the design-packet §5.4 consecutive-commit requirement and the authorization's own §2 hard-stop unsatisfiable for a future A2 commit; (6) C1C full hash on §1 line 28 is 39 chars (dropped "8"), non-resolvable, and its recorded merge-base command errors — must be corrected to `1cca8c578a4f58b4f1b1aa1eae509cf6d800e65a`. Items 1, 2, 4, 5 and all other hashes PASS.
