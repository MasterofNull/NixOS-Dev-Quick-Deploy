## Recursive Self-Improvement (RSI) Closed-Loop SOP (Canonical — all agents)

- Run the loop every slice: Detect/Measure -> Diagnose/Register -> Seed/Dogfood -> Synthesize Guards -> Reuse. Never discard or silently work around findings; instrument the unobservable.
- Run tier0 via its wrapper (it takes `aq-gate-checkout` itself; never nest a second checkout).
- Log every error/friction/limitation (fixed or deferred) in `.agent/memory/issues-backlog.md` ([STATUS] SCOPE — desc — root cause; Severity; Action; File ~line); register interim mitigations in `.agent/WORKAROUND-REGISTER.md`.
- Seed MemoryBroker (`POST :8003/api/memory/facts`) + AIDB `error-solutions`/`best-practices`/`skills-patterns` (`scripts/data/seed-rag-knowledge.py`); write `.agent/memory/<topic>.md`. Add a regression test or tier0.d check.
- Owner decisions: the agent asks the owner a plain numbered question in the CLI with a recommended default, then acts on the reply. Never self-approve; reserved owner acts (sudo/rebuild/systemctl, irreversible/outward-facing) gate on that answer. No inbox/queue/approval command.
- Closeout: root cause, backlog/register, facts+RAG, guard, evidence in `HANDOFF.md` + `PULSE.log`.
- Full text: `canon/blocks/recursive-self-improvement-sop.md`
