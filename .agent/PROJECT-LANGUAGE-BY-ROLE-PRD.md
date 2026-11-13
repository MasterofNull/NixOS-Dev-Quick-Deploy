# PRD: Language and tools by role

Status: DRAFT for review (owner decision recorded; matrix and slices open to review)
Owner decision 2026-11-12: "I want to lift the standing order and for us to use the proper language and tools
for the correct uses and roles." Follow-up the same day: add the recommended Python checker that mimics the
Rust and Go compile checks.

## 1. Decision

The "No Rust rewrite / no language migration" standing order (AQOS PRD section 7, UNIFIED-PROGRAM-PLAN
"Rust refactor: DEFERRED INDEFINITELY", 2026-05-30) is lifted. Each component is written in the language whose
strengths match its role. Python is no longer the default for every new component.

## 2. Where we are (measured 2026-11-12)

- Python: 1,927 tracked files, about 540,000 lines. Shell: 651 files. Nix: 153. Rust: 2 files (821 lines, `crates/contract-validator`). Go: none.
- Python's only gate is `py_compile` (syntax). There is no type checking or lint in tier0 or CI.
- The one Rust gate (`tier0.d/check-owned-scope.sh`) compiles the crate on the fly with `cargo run`, and when
  `cargo` is not on PATH it prints a WARN and skips. A trust-critical gate therefore fails open. No Nix package
  and no CI build, clippy, fmt or test exists for it.

## 3. Language-by-role matrix

| Role | Language | Why |
|---|---|---|
| Long-running daemons with concurrency, shared state, locks or queues (attention queue, drop daemon, task registry, claim/lease store) | Rust (tokio) | Memory and data-race safety, real async, one static binary, no interpreter environment per unit |
| Trust-critical gates and validators (scope gate, contract/receipt verification, signature and lease checks) | Rust | The compiler rejects whole classes of agent mistakes; a packaged binary cannot silently skip |
| CLIs invoked very often by agents or hooks, where startup time adds up | Rust | Millisecond startup instead of interpreter import time |
| Factory-kit distributables that must run on another user's machine | Rust | Single binary, no Python dependency closure |
| ML, RAG, embeddings, evaluation, training data, model and SDK glue | Python | The ecosystem lives there; llama.cpp (C++) already does the hot inference work |
| Fast-changing orchestration scripts and tools that activate by checkout sync | Python (typed, see section 4) | No rebuild per change keeps the fix-and-activate loop short |
| Tests | The language of the code under test; cross-language contract tests in Python are fine | |
| System configuration, packaging, services | Nix | Declarative-only (Rule 13) |
| Dashboard frontend | TypeScript | Browser target |
| Glue in shell | Bash, thin wrappers only (about 50 lines, no business logic) | Anything larger moves to Python or Rust |

Go has no default role. Rust is the single compiled systems language: its toolchain is already in the flake,
`.agent/RUST-ENGINEERING-INSTRUCTIONS.md` exists, and one crate is already in the tree. A second compiled
language doubles toolchains, gates and review skill for little gain. Go may be used only where its ecosystem is
the reason (an upstream tool or library that exists only in Go), with that reason written in the slice brief.

## 4. Python held to compile-time-like checks

- **basedpyright** (pyright fork, nixpkgs 1.39.3) is the type checker. Its baseline file records today's errors
  so the gate fails only on errors a change introduces (Rule 19 gate corollary). The ratchet only tightens:
  fixing an error shrinks the baseline, and a regenerated baseline that grows is rejected.
- **ruff** is the linter: undefined names, unused imports and variables, unreachable code, common bug patterns.
  It also ratchets from a baseline.
- tier0 `--pre-commit` checks the staged Python files (fast). CI checks the whole tree against the baseline.
- New Python files are expected to carry type annotations on public functions. Strict mode is opt-in per
  directory and expands as directories reach zero baseline errors.

## 5. Rust held to its own gates

- Every crate is packaged with `rustPlatform.buildRustPackage` in the flake. Gates and units call the packaged
  binary and never `cargo run`.
- A missing binary is a gate FAIL, never a skip.
- CI runs `cargo fmt --check`, `cargo clippy -- -D warnings` and `cargo test` for the workspace.
- Idioms and crate choices follow `.agent/RUST-ENGINEERING-INSTRUCTIONS.md`.

## 6. Migration rules

- New components pick their language from the matrix. Existing code ports only when a trigger fires: a substantial
  rewrite is needed anyway, a defect class the target language prevents has been measured, or a performance or
  startup budget is breached.
- Ports use the strangler pattern: the new binary runs beside the old path with parity tests on the same inputs,
  traffic moves over, and the old path is archived only with parity (Rule 12, archive-only-with-parity).
- Activation cost is explicit: a Rust component activates by rebuild, so batch ports into rebuild cycles and keep
  high-churn logic where checkout-sync activation applies.
- Every port slice follows the delivery workflow (worktree, tier0, aq-land review, evidence, Activation DoD).

## 7. Slices

| # | Slice | Content |
|---|---|---|
| L1 | `feat/language-by-role` | This PRD and canon block `language-by-role` in all agent files; standing-order lines updated. Code: package `harness-contracts` in the flake, add Rust fmt/clippy/test to CI, and make `check-owned-scope.sh` use the packaged binary and fail closed. |
| L2 | `feat/python-type-gate` | basedpyright and ruff in the dev shell and system tooling, baseline files, tier0 staged-file check and CI full-tree check with ratchet. |
| L3 | Port `attention_queue` to Rust | First daemon port, per `.agents/plans/TECHNICAL-ANALYSIS-PRD.md` phase 1, with parity tests. |
| L4 | Port `aq-drop-daemon` | Phase 2 of the same plan. |
| L5 | Port `task_registry` | Phase 3, with a local socket or JSON-RPC for Python callers. |

L3 to L5 each need their own slice brief and are sequenced against the system-integrity-recovery plan.

## 8. Acceptance

- L1: canon drift gate passes with the new block in all six agent files; `nix build .#harness-contracts` works;
  CI runs fmt, clippy and test; removing the binary makes the scope gate FAIL.
- L2: a staged Python file with a new type error or undefined name fails tier0; an unchanged tree passes CI
  against the baseline; the baseline cannot grow without failing.

## 9. Risks

- Rebuild cost per Rust change. Mitigation: section 6 activation rule.
- Baseline noise on 540k lines. Mitigation: ratchet only on new errors, staged-file scope in tier0.
- Two runtimes during ports. Mitigation: parity tests and archive-with-parity.
