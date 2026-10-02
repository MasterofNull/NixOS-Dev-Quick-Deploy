## Recursive Self-Improvement (RSI) Closed-Loop SOP (Canonical — all agents)

- Run the loop every slice: Detect/Measure -> Diagnose/Register -> Seed/Dogfood -> Synthesize Guards -> Reuse. Never discard or silently work around findings; instrument the unobservable.
- Run tier0 via its wrapper (it takes `aq-gate-checkout` itself; never nest a second checkout).
- Log every error/friction/limitation (fixed or deferred) in `.agent/memory/issues-backlog.md` ([STATUS] SCOPE — desc — root cause; Severity; Action; File ~line); register interim mitigations in `.agent/WORKAROUND-REGISTER.md`.
- Seed MemoryBroker (`POST :8003/api/memory/facts`) + AIDB `error-solutions`/`best-practices`/`skills-patterns` (`scripts/data/seed-rag-knowledge.py`); write `.agent/memory/<topic>.md`. Add a regression test or tier0.d check.
- Owner decisions: show `aq-approve` (numbered; needs-approval + deferred); owner replies "approve 1 3"; run `aq-approve approve 1 3 --tag T --door chat` (always prompts). Agents never self-approve.
- Closeout: root cause, backlog/register, facts+RAG, guard, evidence in `HANDOFF.md` + `PULSE.log`.
- Full text: `canon/blocks/recursive-self-improvement-sop.md`
