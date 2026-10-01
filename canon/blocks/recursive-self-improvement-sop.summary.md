## Recursive Self-Improvement (RSI) Closed-Loop SOP (Canonical — all agents)

- Every agent/slice MUST run the loop: Detect/Measure -> Diagnose/Register -> Seed/Dogfood -> Synthesize Guards -> Reuse. Findings, friction, errors are never discarded or bypassed with silent workarounds; instrument anything unobservable.
- Serialize heavyweight validation: run tier0 via its wrapper, which serializes through `aq-gate-checkout` itself (never take a second checkout around it).
- Every found error/friction/limitation (fixed or deferred) MUST be logged in `.agent/memory/issues-backlog.md` ([STATUS] SCOPE — desc — root cause; Severity; Action; File ~line); interim mitigations MUST be registered in `.agent/WORKAROUND-REGISTER.md`.
- Seed MemoryBroker (`POST :8003/api/memory/facts`) and AIDB (`error-solutions`, `best-practices`, `skills-patterns` via `scripts/data/seed-rag-knowledge.py`); write `.agent/memory/<topic>.md`.
- Never stop at the fix: add a regression test (`scripts/testing/`) or tier0.d check.
- Closeout checklist before COMPLETE: root cause diagnosed; backlog/register updated; facts+RAG seeded; guard added; evidence in `HANDOFF.md` + `PULSE.log`.
- Full text: `canon/blocks/recursive-self-improvement-sop.md`
