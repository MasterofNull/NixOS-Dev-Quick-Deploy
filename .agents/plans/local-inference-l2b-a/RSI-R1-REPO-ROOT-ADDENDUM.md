# L2B-A addendum — RSI R1 Ralph repo-root source rebind (2026-10-02)

Scope: evidence reconciliation only. Historical acceptance (`antigravity-acceptance-v2.md`) is retained unchanged.

## Change covered
`ai-stack/mcp-servers/ralph-wiggum/server.py` — the two existing `scripts/ai/aq-optimizer` subprocess calls
(`--dry-run` in `sync_prsi_queue`, guarded `--apply` in `execute_prsi_actions`) change only
`cwd="/home/hyperd/Documents/NixOS-Dev-Quick-Deploy"` → `cwd=os.environ["REPO_ROOT"]`.
`REPO_ROOT` comes from `mcp.repoPath` in `nix/modules/services/mcp-servers.nix`.

| | sha256 |
|---|---|
| prior pin (HEAD 6c341d28) | `4ce2dda70c9a9e506f03b1b4f334173486b672202b351c0d261566af1fda714a` |
| rebound pin | `dc3a4b21b09c8ad0beb47ccc18472fdf6fc9794428de095b431b33e43beb95ba` |

## Boundary statement
- No import, call, or adoption of `local_inference_transport` (the fixture's `ralph-unavailable` absent-predicate still holds).
- No change to dispatch/execution semantics, routes, auth, or the R1–R4 live run-loop slices; the `--apply` path keeps its existing guard and is reached only as before.
- Authority: owner RSI repair request (PRD `.agent/PROJECT-RSI-TAKEOVER-20261002-PRD.md`, slice R1). The hash is rebound together with this addendum, not alone.

## Evidence
- `python3 scripts/testing/test-local-inference-l2b.py` → `PASS: 16 local-inference L2B checks` after rebind (FAIL on live source drift before).
- Independent review: see PULSE.log entry for this addendum (Claude sonnet reviewer, author lane Codex).

## Amendment 1 — atomic PRSI queue write (2026-10-02)
`_save_prsi_queue` replaces the in-place `write_text` with temp-file + `os.replace` (plus `import tempfile`).
Cause: a legacy `hyperd:users 0644` queue file inside the `ai-ralph`-owned dir blocked writes (Errno 13), and a
tmpfiles `z` re-own was refused by systemd-tmpfiles as an unsafe path transition.

| | sha256 |
|---|---|
| prior pin (e9ccc8f4) | `dc3a4b21b09c8ad0beb47ccc18472fdf6fc9794428de095b431b33e43beb95ba` |
| rebound pin | `a2ee122dc4c21e2e8aaf8099ab54cbfe6e865cc7033403491b96ce11cb7b3110` |

Boundary unchanged: queue persistence only; no `local_inference_transport`, no route/auth/dispatch/execution change.
Evidence: `test-local-inference-l2b.py` 16 PASS; `test-ralph-prsi-repo-root.py` PASS (0444 pre-existing file replaced, mode 0640, no temp leftovers).
