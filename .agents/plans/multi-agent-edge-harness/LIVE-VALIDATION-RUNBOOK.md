---
doc_type: reference
title: "MAEAH Live Validation Runbook"
id: maeah-live-validation-runbook
status: active
owner: AI Stack Maintainers
last_updated: "2026-06-02"
---

# MAEAH Live Validation Runbook

This runbook defines the step-by-step live validation sequence that must pass
before MAEAH readiness is asserted. Do not promote MAEAH readiness on repo-static evidence alone.

## Phase 0 — Repo-static contract gate

Run all static contract checks against the repo. Must pass with zero failures.

```bash
edgeai contracts check --json
bash scripts/testing/test-edgeai-cli-contract.sh
python3 scripts/testing/test-maeah-api-surface-contract.py
python3 scripts/testing/test-maeah-contract-artifacts.py
python3 scripts/testing/test-maeah-model-registry-schema.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

**Gate**: All commands exit 0 and `edgeai contracts check --json` reports `"ok": true`.

## Phase 1 — Surface health

Verify all services are up and the harness surfaces are reachable.

```bash
edgeai doctor --json
edgeai models list --json
edgeai a2a card validate --json
edgeai mcp tools list --json
```

**Expected**: `edgeai doctor --json` shows all services green. Model list returns
valid JSON. A2A card is present. MCP tool list is non-empty.

**Note**: Do **not** run `download`, `promote`, or `rollback` in this phase.
Those are destructive/heavy model lifecycle actions reserved for Phase 3+.

## Phase 2 — Responses compatibility smoke

Validate the `POST /v1/responses` compatibility shim routes correctly.

```bash
edgeai traces tail --last 1 --json
edgeai chat --json "ping"
```

**Expected**: Chat returns a valid JSON envelope. Traces show the route went
through `chat/completions`. The `X-OpenAI-Responses-Compat` header is present
in the response.

## Phase 3 — User-defined model lifecycle smoke

Validate `POST /admin/v1/models` and `DELETE /admin/v1/models/{id}` auth rules.
Confirm that unauthenticated `/admin/v1/models` mutations are rejected with 403,
and that internal dashboard requests are admitted.

```bash
scripts/testing/maeah-live-auth-smoke.sh --plan
scripts/testing/maeah-live-auth-smoke.sh --run
edgeai models add --id local-smoke --name "Smoke Test" --repo org/repo --file model.gguf
edgeai models delete local-smoke
```

**Expected**: Unauthenticated add/delete returns 403. Authenticated (internal
header or API key) add returns 200 or 409. Delete succeeds with 200 or 404.

## Phase 4 — Full MAEAH acceptance

Run the full acceptance test suite and memory recall benchmark.

```bash
bash scripts/testing/maeah-acceptance-tests.sh --verbose
scripts/ai/aq-memory-recall-benchmark --json
```

**Expected**: All acceptance tests pass. Memory recall benchmark shows non-zero
hit rate on the `error-solutions`, `best-practices`, and `skills-patterns`
collections.

## Promotion criteria

Promote MAEAH readiness only when **all** of the following are true:

1. Phase 0 static gate: `edgeai contracts check --json` reports `"ok": true`.
2. Phase 1 surface health: all services green in `edgeai doctor --json`.
3. Phase 2 responses shim: `edgeai chat --json` returns valid JSON envelope.
4. Phase 3 auth smoke: `scripts/testing/maeah-live-auth-smoke.sh --run` passes.
5. Phase 4 acceptance: `maeah-acceptance-tests.sh --verbose` exits 0.

Document the commit hash and timestamp in `PARITY-INTEGRATION-PLAN.md` under the
relevant milestone.

## Failure handling

- **Phase 0 failure**: Fix the static contract before proceeding. Do not skip.
- **Phase 1 failure (service down)**: Restart the failing service via systemctl
  and re-run. If it persists, escalate to the issues backlog before proceeding.
- **Phase 2 failure**: Inspect coordinator logs for routing errors. The shim may
  need a `chat_template_kwargs` or endpoint config update.
- **Phase 3 auth failure**: Verify `_check_auth(request)` is called in the
  mutating route. Check that `X-Dashboard-Internal` header logic is intact.
- **Phase 4 acceptance failure**: Treat each failing test as a blocking regression.
  File an issue in `memory/issues-backlog.md` before promoting.
