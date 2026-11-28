Verdict: REVISE
Reviewed-DESIGN-sha256: a6aa55bb4484841f8700c1334ed8555ea1579a2f67fe3f54dfacb3c7c5563029
P1 Offline journeys / acceptance J6-J8 - Failing on “any DNS or socket attempt” also rejects coordinator→switchboard→llama.cpp loopback communication required by J6 - Permit declared loopback/Unix IPC; fail external connections, external DNS and network fetches; update runbook, acceptance and risk wording consistently.
P2 Execution order / tracker.json - S1d still requires zero Node in “each supported profile,” including lite, which arrives in dependent S13; the round-1 cycle fix is incomplete in the tracker - Restrict S1d validation explicitly to add-on-OFF ai-dev; assign lite closure validation to S13.
P2 Execution order / tracker.json - Prose requires S1c before S13, but the enumerated graph and tracker omit that dependency - Add S1c to S13 dependencies or explicitly remove the prerequisite from prose.
P3 Brief coverage - D-R5-1..6 and the substantive brief requirements have implementation or named deferral coverage; acceptance contradictions above prevent unconditional buy-in - Preserve this coverage when correcting the gates.
P3 Buy-in round 1: privileged RCE - Fixed by trusted-base checking, separate unprivileged candidate execution and N8 - Retain these requirements.
P3 Buy-in round 1: DAG cycle - DESIGN separates S1d and S13 exits correctly; tracker wording remains inconsistent as identified above - Complete the tracker correction.
P3 Buy-in round 1: C2 target and supported-set shrinkage - Fixed by checking the built profile plus build dependencies and requiring an explicit owner decision before dropping ai-dev - Retain both constraints.
P3 Buy-in round 1: GitHub-dependent waiver - Fixed by local-no-github identity, nullable GitHub fields and cross-mode refusal - Retain candidate binding and explicit assurance deficit.
P3 Buy-in round 1: provenance - Fixed at document level through explicit verification revisions and carried-claim tags; this review does not independently attest underlying runtime facts - Preserve [V]/[C] distinctions.
P3 Buy-in round 1: owner key and D21 - Fixed by S2 provisioning prerequisite and contingent S13b activation or dated owner deferral before S12 - Retain those exit gates.
P3 REVIEW-R5 disagreement resolutions - Accept the resolutions; none rejected - Synchronize their execution claims with the corrected tracker.
P3 C1-C5 / local waiver - Supported-install C2 scope, build/runtime coverage, unresolved C3/C5 failures and local-only waiver restrictions follow the approved decisions - Keep owner-host exemption distinct from supported-install compliance.
D11 AGREE - Check current per-slice grants; use an eligible non-author binding reviewer and record exact grant IDs.
D12 AGREE - Owner-confirmed unmodified binary invocation default; linking, vendoring or modification requires the specified owner waiver.
D13 AGREE - Owner-host add-on ON is exempt from C2; lite and add-on-OFF ai-dev retain C1-C5 obligations.
D14 AGREE - Designate actual 16 GB hardware and a pinned model ≤4 GiB; ratify budgets at S0 and require owner approval for measured revisions.
Top risk I see: Contradictory offline gates and residual tracker dependencies could stall execution despite apparent plan readiness.
