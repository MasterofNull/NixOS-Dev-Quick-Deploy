Verdict: PLAN_READY_WITH_FOLLOWUPS
Reviewed-DESIGN-sha256: 8428a855ddefeb7c2c4c518a0ec932d4b49982260f6568142d2d536dfcc64b76
P2 Decision ownership / REVIEW resolution 3 - The 7–16 overlap range counts rows, while the defined metric sums excess independent writers; 16 is not an established upper bound - Separate overlapping-row counts from writer totals; leave writer totals unknown until S1 computes them, including in ARCHITECTURE-SUMMARY.md.
P3 Round-2 closure - All findings are fixed: required local IPC is allowed; S1d targets add-on-OFF ai-dev; S13 depends on S1c; earlier safeguards remain; D9 includes S13b and tracker records both owner-key prerequisites - Retain these corrections.
P3 Consolidation - Brief requirements and binding D-R5-1..6 are covered or assigned named slices; MVP ordering and acceptance are executable; C2 and local-waiver boundaries hold; runtime uncertainty remains explicit - Accept disagreement resolutions except resolution 3’s numerical presentation above.
D11: AGREE — Check current per-slice grants; use an eligible non-author binding reviewer and record grant IDs.
D12: AGREE — Retain the unmodified-binary invocation default and owner-waiver boundary for linking, vendoring or modification; unresolved licence evidence blocks adoption.
D13: AGREE — Owner-host add-on ON is exempt from C2; lite and add-on-OFF ai-dev retain supported-install compliance requirements.
D14: AGREE — Designate real 16 GB hardware and a pinned model ≤4 GiB; ratify budgets at S0 and require owner approval for revisions.
Top risk I see: Declared boundaries and static checks could appear complete before runtime admission and recovery are proven; S12 must require real refusal, crash and replay evidence.
