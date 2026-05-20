# MAEAH Live Validation Runbook

**Date:** 2026-05-20
**Owner:** Codex
**Scope:** Post-recovery validation for the Multi-Agent Edge AI Harness after `llama.cpp`, the local model, dashboard, and coordinator services are back online.

## Purpose

During the llama/local-model outage, the team advanced repo-only MAEAH contract work:

- normalized OpenAI-compatible `/v1/responses` and admin model lifecycle APIs,
- model lifecycle schema/OpenAPI artifacts,
- `edgeai` CLI facade,
- `edgeai chat`,
- `edgeai models add/delete`,
- `edgeai contracts check`.

This runbook defines the live validation sequence needed before promoting the dev cycle from repo-static parity to runtime-validated readiness.

## Preconditions

Confirm the services are expected to be up before running this sequence:

```bash
systemctl is-active llama-cpp
systemctl is-active hybrid-coordinator 2>/dev/null || true
systemctl is-active command-center-dashboard 2>/dev/null || true
```

If service names differ on the host, use the service names declared in the local NixOS/Home Manager profile rather than changing this runbook.

## Phase 0 — Repo-static contract gate

Run this first. It does not require live services.

```bash
edgeai contracts check --json | jq .
scripts/testing/test-edgeai-cli-contract.sh
python3 scripts/testing/test-maeah-api-surface-contract.py
python3 scripts/testing/test-maeah-contract-artifacts.py
python3 scripts/testing/test-maeah-model-registry-schema.py
```

Expected result: every command exits `0` and reports `ok: true` or `PASS`.

## Phase 1 — Surface health

```bash
edgeai doctor --json | jq .
edgeai models list --json | jq .
edgeai a2a card validate --json | jq .
edgeai mcp tools list --json | jq .
edgeai traces tail --last 1 --json | jq .
```

Expected result:

- coordinator health is reachable,
- dashboard health is reachable,
- agent card validates required A2A fields,
- MCP tool catalog returns structured JSON,
- traces endpoint returns JSON even if no recent trace exists.

## Phase 2 — Responses compatibility smoke

```bash
edgeai chat --json "Say pong" | jq .
edgeai chat --model local "Say pong"
```

Expected result:

- `/v1/responses` returns JSON with `output_text` or an equivalent normalized response body,
- non-JSON mode prints model text rather than a raw stack trace,
- failures are explicit JSON/service errors, not shell errors.

## Phase 3 — User-defined model lifecycle smoke

Use a disposable model entry that points at a known safe test fixture or a real small GGUF only if the operator intends to test download behavior.

Catalog-only add/delete smoke:

```bash
edgeai models add \
  --id local-smoke \
  --name "Local Smoke" \
  --repo org/repo \
  --file model.gguf \
  --params smoke \
  --context-size 4096 \
  --ram-gb 1 \
  --hardware-targets cpu_only

edgeai models list --json | jq '.models[] | select(.id == "local-smoke")'
edgeai models delete local-smoke
```

Expected result:

- add returns `status: added`,
- list shows `user_defined: true`,
- delete returns `status: deleted`,
- built-in and active models remain protected from deletion.

Do **not** run `download`, `promote`, or `rollback` during this smoke unless the model path, expected disk usage, and operator intent are confirmed.

## Phase 4 — Full MAEAH acceptance

Run only after Phases 0–3 pass:

```bash
bash scripts/testing/maeah-acceptance-tests.sh --verbose
scripts/ai/aq-memory-recall-benchmark --json
```

If the broader gate is required:

```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
```

Expected result: Tier 0 passes without QA phase 0 timeout. During the outage window, this gate was only partially runnable because `aq-qa 0` waits on local services.

## Promotion criteria

Runtime validation can be marked complete when:

1. Phase 0 static contracts pass.
2. Phase 1 live surfaces are reachable and structured.
3. Phase 2 `/v1/responses` smoke passes.
4. Phase 3 catalog add/delete smoke passes without touching built-ins or active model state.
5. Phase 4 MAEAH acceptance passes, or failures are documented as unrelated known infrastructure issues.

## Failure handling

Record failures in `.agent/collaboration/PENDING.json` and append `.agent/collaboration/HANDOFF.md` with:

- command run,
- exit code,
- last 50 lines or structured error body,
- whether the failure is service availability, API contract drift, auth, or model runtime behavior.

Do not promote MAEAH readiness on repo-static evidence alone.
