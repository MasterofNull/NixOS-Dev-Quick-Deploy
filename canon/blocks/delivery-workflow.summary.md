## Delivery Workflow (Canonical — all agents)

- One branch + worktree per slice from `origin/main`; never edit tracked files in the main checkout (append-only PULSE/backlog excepted); sub-agents stay in their worktree.
- Commit only as `tier0-validation-gate.sh --pre-commit && git commit`; never `--no-verify`; graph/wiki generated, not committed.
- Land via PR only (`gh pr create --body-file`; body Details then What/How/Why, CI-checked), never push `main`; evidence `docs/harness-first/evidence/<date>-<slug>.md`.
- Resumable trail: RESUME.json + PULSE.log + HANDOFF.md; down lanes catch up via AGENT-CATCHUP-QUEUE.md.
- sudo/nrs/systemctl = owner acts: give exact copy-paste cmds; no rebuild during DB jobs.
- Done = enable -> rebuild (`aq-deploy-current`) -> validate live -> peer review -> owner grant; no derelict capabilities; archive only with parity.
- Discover first: CAPABILITY-INDEX.md, `aq-graph-query`, `aq-wiki --section`, `aq-hints`; friction -> `aq-rsi report`.
- Full text: `canon/blocks/delivery-workflow.md`
