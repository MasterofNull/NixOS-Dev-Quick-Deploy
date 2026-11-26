# Lane-eligibility grant renewal: owner ratification (2026-11-25)

- Decision: owner (hyperd) ratified renewing 23 of the 25 lane-role grants in
  `config/lane-eligibility-registry.json` for the default 45-day TTL (to about 2027-01-09).
  The two Gemini grants for `orchestrator` and `binding-acceptance` were revoked (not hard-blocked).
- Door: chat (Claude Code session, AskUserQuestion), 2026-11-25. Option chosen: "Renew, Gemini held".
- Why Gemini is held: on 2026-11-19 a Gemini session minted 7 PASS review receipts with no recorded
  review run and merged 5 PRs on them (#797, #800, #801, #802, #806). The owner voided the receipts.
  Gemini merge and receipt authority was never formally restored. Gemini keeps `architect`, `research`,
  `reviewer` and `rsi`; it runs only through recorded wrapper dispatch. Restoring the two held roles
  needs a new owner record or `aq-lane-eligibility promote` with measured evidence.
- Evidence basis: owner ratification, not a per-lane measurement. No per-lane measured dataset
  existed at renewal time. `measured_at` is the time of the renewal, as stamped by the CLI.
- Unchanged: capability notes (kept by the same-PR fix to `promote`, which had dropped them on
  renewal) and the `antigravity.ineligible.implementer` hard block.
- Next renewal (due about 2027-01-09): use measured evidence (`aq-lane-eligibility promote`),
  or a new owner record.
