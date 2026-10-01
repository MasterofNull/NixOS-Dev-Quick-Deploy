## Design, Build, and MVP Audit (owner directive 2026-09-27)

- Design/freeze: full independent expert teams for PRD/plan; freeze MVP scope, contracts, owners, acceptance tests, rollback limits as PLAN_READY[_WITH_FOLLOWUPS]; reuse approved plans; record unavailable lanes honestly, never manufacture consensus.
- Build: bounded slices, cheapest eligible implementers; NO fresh full expert round per slice/commit; keep atomic commits, evidence, gates, activation boundaries; reopen a decision only for material scope change or critical correctness/data-loss/authority/security defects.
- Declare MVP only when frozen E2E journeys pass with real dependencies and reproducible evidence; syntax/staged/simulated success is not readiness; record limitations; never inflate progress.
- At the MVP boundary restore full audit (independent code+runtime review, adversarial, UX, perf, observability, consensus) on one exact subject; only that supports release acceptance; security/containment activation needs its own evidence + owner decision.
- Full text: `canon/blocks/mvp-delivery-sop.md`
