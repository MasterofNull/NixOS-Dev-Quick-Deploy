## Delivery Workflow (Canonical — all agents)

- One branch + worktree per slice from `origin/main`; never edit/commit tracked files in the main checkout (append-only PULSE/backlog excepted); sub-agents stay in their worktree.
- Commit only as `tier0-validation-gate.sh --pre-commit && git commit`; never `--no-verify`; graph/wiki are generated, not committed.
- Land via PR only (`gh pr create --body-file`), never push `main`; evidence doc `docs/harness-first/evidence/<date>-<slug>.md`.
- Resumable trail for any lane: RESUME.json + PULSE.log + HANDOFF.md; down lanes catch up via AGENT-CATCHUP-QUEUE.md.
- sudo/nrs/systemctl = owner acts: give exact copy-paste commands; no rebuild during DB jobs.
- Enabled != done; no derelict capabilities; archive only with a parity equivalent.
- Discover first: CAPABILITY-INDEX.md, `aq-graph-query`, `aq-wiki --section`, `aq-hints`; friction -> `aq-rsi report`.
- Full text: `canon/blocks/delivery-workflow.md`
