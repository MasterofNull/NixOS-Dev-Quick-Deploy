# Language and Tools by Role (Canonical — all agents)

<!-- SSOT: .agent/PROJECT-LANGUAGE-BY-ROLE-PRD.md (owner decision 2026-11-12 lifted the no-Rust/no-migration order) -->

Pick each component's language from its role, not from habit. Python is not the default for new components.

| Role | Language |
|---|---|
| Long-running concurrent daemons (queues, locks, shared state); trust-critical gates and validators; hot CLIs where startup adds up; factory-kit distributables | Rust |
| ML, RAG, embeddings, evaluation, training data, model/SDK glue; fast-changing scripts that activate by checkout sync | Python (typed) |
| System config, packaging, services | Nix |
| Dashboard frontend | TypeScript |
| Thin glue (about 50 lines, no business logic) | Bash |

- Go has no default role; use it only when its ecosystem is the reason, stated in the slice brief.
- Rust: packaged with `buildRustPackage`; gates call the packaged binary, never `cargo run`; a missing binary is a FAIL, never a skip; `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test` in CI; idioms per `.agent/RUST-ENGINEERING-INSTRUCTIONS.md`.
- Python: basedpyright (types) and ruff (lint) gate staged files in tier0 and the full tree in CI against a baseline that only shrinks; annotate public functions in new files.
- Existing code ports only on a trigger (substantial rewrite anyway, measured defect class the target language prevents, perf/startup budget breach), by strangler pattern with parity tests, archiving the old path only with parity.
- Rust components activate by rebuild: batch ports into rebuild cycles; keep high-churn logic where checkout-sync activation applies.
