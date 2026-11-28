# Revision 4 review and lane grant proposal

The original revision 4 freeze candidate consists of the two files below. Their SHA-256 digests identify the material reviewed by Gemini.

| File | SHA-256 |
| --- | --- |
| [Design](DESIGN.md) | `3b344fdf57ab61f9f65ce0cf24836f7d187fd70def437646172103bbab5a1fea` |
| [Slice tracker](tracker.json) | `75a3acbb464d8dc75978bbd5646dbd53577313435e2f092280c94c6568c1f9ae` |

## Round-two findings

| Finding | Resolution in revision 4 |
| --- | --- |
| Reviewer identity and review reuse | GitHub numeric reviewer identity is bound to an enrolled principal through a formal review. Signed author provenance supplies the independence check. Review reuse requires the identical candidate tuple. A changed base or head requires fresh review even when the Git tree matches. |
| Resume, merge races and replay | S2 defines one candidate and one queue admission grant. S1b uses that same verifier and operation record. Recovery checks authoritative GitHub state before retrying. Fences and expiry or revocation prevent stale workers and grants from authorizing new requests. |
| Enforcement | The guard table assigns the blocking point for each proposed guard. QA, dashboard and supporting evidence remain observational. The slice criteria require actual refusals at the named enforcement points. |

The shared checkout's `.agent/memory/issues-backlog.md` contains all five cited incidents. The line numbers below refer to that checkout as verified on 2026-11-23.

| Verified backlog ID | Line |
| --- | --- |
| `LAND-RUNNER-NOT-DURABLE` | 10713 |
| `LANE-AVAILABILITY-NOT-PER-MODEL` | 10887 |
| `AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR` | 10936 |
| `EMBEDDER-STICKY-DEVICE-LOST` | 10942 |
| `DEPENDABOT-REBASE-NOOP-AFTER-FOREIGN-PUSH` | 10954 and 11063 |

Codex confirmed both digests and returned advisory **PASS**. The follow-up verified the lease-enforcement wording, the scope of the embedder incident evidence, the count of expiring grants, and the retry contract. Codex co-authored revision 4.

The independent Gemini lane matched both digests and returned **PASS** on the written design in run `gemini-20261123-101011-wsnk42`. It confirmed the three round-two resolutions, the shared S1b/S2 contract, and all five backlog references. The CLI reported provider-side model resolution, so the exact serving model is unverified.

The independent review covered the design and tracker. The D0 proposal below scopes the reviewer's renewal note to the six existing entries the MVP needs. The landing safety guarantees still require the live GitHub tests specified in S2 before activation.

## Tier0 editorial corrections

The continuation corrected repository-relative path references, marked S9's shim map as a planned artifact, removed a withdrawn registry filename, and removed stale tracker percentage hints. A separate Codex reviewer confirmed **PASS** on the amended pair after checking that the authority, enforcement, and replay contracts retained the reviewed behavior. The candidate for implementation is the pair below.

| File | SHA-256 |
| --- | --- |
| [Design](DESIGN.md) | `290911f40484267560d103b51d89df26607ef5c85a30dfb6b0cb29e2513b9a8f` |
| [Slice tracker](tracker.json) | `eb0433e15bbb1d552e03b757e4ca325e09ef9a5ec25f0738147c922cc586b7f1` |

## D0 · Lane grant renewal due 2026-11-26

The registry records 25 grants expiring at **2026-11-26 00:00 UTC**. The proposed renewal covers six existing entries needed for the MVP. Each proposed entry needs fresh evidence for its exact role before issuance. See the [lane registry](../../../config/lane-eligibility-registry.json), [renewal command](../../../scripts/ai/aq-lane-eligibility), and [October owner ratification](../unified-program/LANE-GRANT-RENEWAL-OWNER-RATIFICATION-20261014.md).

| Registry key | Scope |
| --- | --- |
| `lanes.codex.eligible.orchestrator` | Coordinate the approved MVP slices. |
| `lanes.codex.eligible.implementer` | Implement bounded slices where eligible. |
| `lanes.gemini.eligible.reviewer` | Independently review candidates authored by other lanes. |
| `lanes.gemini.eligible.binding-acceptance` | Provide binding acceptance when separate from the author and, where required, the reviewer. |
| `lanes.sonnet.eligible.reviewer` | Supply a second independent reviewer after a fresh healthy review and role evidence. The current quota failure remains open until verified recovery. |
| `lanes.local.eligible.implementer` | Implement bounded slices covered by local role evidence. |

Use the registry's 45-day term from actual issuance. For issuance at 2026-11-25 12:00 UTC, the proposed expiry is **2027-01-09 12:00 UTC**. Leave any proposed entry with missing evidence unissued. If independent coverage cannot be staffed, hold the affected slice and put a scoped alternate in front of the owner. The other 19 entries are outside this renewal proposal.

Approval of D0 authorizes the scoped renewal once the evidence is verified. The design freeze and implementation have their own decisions.

### Owner decision

On 2026-11-23, the owner approved the proposal in chat with “I approve D0 as proposed.” This authorizes the six entries above for 45 days from issuance, subject to fresh role evidence for each entry.

Issuance is pending. The exact revision 4 confirmation is evidence for Gemini's reviewer role. Codex's merged audit fix (#847) is an implementation evidence lead. Separate evidence is still required for Codex orchestration, Gemini binding acceptance, Sonnet's post-quota review and local implementation. No grants were changed.

The portable factory-kit preflight returned `FOREIGN_HOOK_MANAGER` when run in the native harness checkout with its existing pre-commit configuration. Native repository work follows Tier0 and the GitHub checks. The D0 issuance requirements are the role evidence and registry checks described above.

## D1 · Umbrella PRD and control-plane scope

On 2026-11-23, the owner approved D1 in chat with “I approve D1 as proposed.” Revision 4 is the umbrella PRD. Adopt the five contexts (K1–K5) and nine aggregates (A1–A9), fold in the three related PRDs, and hold experience capture until revised. Design freeze and implementation are separate decisions.

## D2–D4 · Adoption decisions

On 2026-11-23, the owner approved D2, D3, and D4 in chat with “I approve D2, D3, and D4 as proposed.”

- D2. Run the time-limited, flagged `nh` experiment in `aq-update` during post-MVP S5 after a non-Gemini lane verifies the upstream claims, license interpretation, and sudo behavior.
- D3. Defer LangGraph until live coordinator tests demonstrate a replay or interrupt gap. If reopened, evaluate core only and retain one authoritative store.
- D4. Keep the current components for MVP. Refresh the OpenClaw, LiteLLM, devenv, deploy-rs, and colmena evaluations in S12. Revisit deploy-rs versus colmena if a real U8 remote deployment requirement emerges.

## D5–D8 · Intake, authority, landing and remediation

On 2026-11-23, the owner approved D5, D6, D7, and D8 in chat with “I approve D5, D6, D7, and D8 as proposed.”

- D5. Use a Markdown disposition, an `aq-collab-round` link, and the three-line PRD header in the existing intake workflow.
- D6. Extend `config/system-state-authorities.yaml` and its existing checker for decision ownership.
- D7. Adopt the [shared S2 and S1b admission contract](DESIGN.md#shared-s2-and-s1b-admission-contract), including authenticated GitHub review identity, fresh review for any change to the bound candidate, protected merge verification, and one-use, replay-protected queue admission with an authoritative recovery check.
- D8. Use the health-spider fix pipeline as the provisional default. Select the single remediator in S6 using measured behavior.

## D9–D10 · Execution order and independent review

On 2026-11-23, the owner approved D9 and D10 in chat with “I approve D9 and D10 as proposed.”

- D9. Execute S0 → S1 → S2 → S1b → S4 → S3 → S12 under the MVP feature freeze. Begin S5 (`aq-update-unified`) after the freeze exits.
- D10. Preserve Claude’s draft and Codex’s continuation. Use an eligible non-author lane for independent confirmation. The Codex follow-up and any Qwen input are advisory. Verify each adoption claim through a lane independent of the claimant.

## S0 freeze disposition · 2026-11-23

**PLAN_READY_WITH_FOLLOWUPS.** D0–D10 are recorded. Gemini independently confirmed the original revision 4, and a separate Codex reviewer confirmed the editorial corrections against that baseline. This disposition supersedes the pending-freeze wording in the design snapshot.

Execution remains gated on the W2–W4 PR queue clearing, completion of the W9 rebuild, evidence-backed renewal of the required role grants, and capture of the post-rebuild boot ID and live baseline. The S2 live GitHub acceptance tests and the independent D2 adoption-claim verification remain due in their respective slices.
