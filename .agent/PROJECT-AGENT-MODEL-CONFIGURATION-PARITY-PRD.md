---
doc_type: prd
id: agent-model-configuration-parity
title: Agent and Model Configuration Parity PRD
status: draft
owner: hyperd
---

# Agent and Model Configuration Parity PRD

## Authority and intent

This PRD projects `docs/architecture/role-matrix.md`, the AQ-OS reference
architecture, the Service Coverage contract, and the agent-connection
reliability program into one deployment contract for Codex, Claude,
Antigravity/Gemini, local agent/coding, local logic/direct, and embedded
retrieval lanes.

Provider projections must also conform to their current upstream configuration
contracts. For Codex, the authoritative reference is
`https://learn.chatgpt.com/docs/config-file/config-reference`: project overrides
load only for trusted projects, custom roles require
`agents.<name>.description` plus `agents.<name>.config_file`, and
`features.codex_hooks` is only a deprecated alias for `features.hooks`.

Roles remain model-agnostic. Provider and hardware differences may change model,
modality, context, phase budgets, tools, concurrency, and fallback, but never
authority, identity, monitoring, evidence, independence, or review truth.

## Problem

Configuration is split across declarative Nix, user and project Codex TOML,
provider wrappers, `config/model-coordinator.json`, local dispatch code, role
documents, and tests. Current evidence shows:

- the live Codex config reintroduced deprecated `features.codex_hooks` because
  tests checked a transform but not the effective merged configuration;
- project Codex role files exist but are not declared through
  `agents.<name>.config_file`;
- `config/model-coordinator.json` still advertises stale or contradictory model,
  endpoint, and fallback metadata instead of matching effective native Codex
  and provider routes;
- Antigravity loop mode bypasses registry/PENDING/audit lifecycle, ignores
  declared timeout/token inputs, duplicates model IDs, and lacks typed reviews;
- Claude lacks bounded timeout/retry/fallback and shares an unsafe registry
  writer pattern;
- local embedded prefetch is generative rather than retrieval-only, `aq-chat`
  self-assigns authority roles, eligibility is not enforced, payload SSOT is
  bypassed, and lifecycle evidence omits effective deployment lineage.

## Canonical deployment contract

Every dispatch resolves one immutable `AgentDeployment` record before launch:

| Group | Required fields |
|---|---|
| identity | task, attempt, parent, lane, provider, effective model artifact |
| authority | assigned role, authorization/subject hashes, reviewer eligibility, recusal |
| modality | agent loop, planner, chat/logic, embedded retrieval |
| payload | system/developer/user prompt hashes, schema/version, tool manifest hash |
| resources | context, output, prefill/generation/tool/deadline budgets, concurrency/queue |
| isolation | filesystem, network, environment allowlist, cwd, nested-delegation policy |
| lifecycle | queued, admitted, running, parked, terminal state, retry/fallback lineage |
| evidence | receipt, validation, finding disposition, monitoring and dashboard state |

The provider-neutral record is the SSOT. Provider adapters may translate it but
may not invent authority, model IDs, budgets, or terminal truth.

## Requirements

1. A closed versioned schema and pure resolver produce `AgentDeployment`.
2. Model IDs and tier mappings resolve from one admitted coordinator SSOT.
3. Provider projections have golden vectors for roles, payloads, tools,
   budgets, schemas, timeouts, retries, parking, fallback, and recusal.
4. Effective merged configuration is fingerprinted from source layers and
   compared with the live client view. Deprecated keys, undeclared roles,
   unsafe overrides, stale generations, and missing tool policy fail health.
5. All launches register before execution through one lifecycle writer. No
   wrapper or loop may bypass registry, audit, PENDING/RESUME, or receipts.
6. Reviewer payloads bind subject hash, criteria evidence, identity/model
   lineage, independence, and `PASS|FAIL|REQUEST_REVISION`.
7. Local modalities share common authority/evidence contracts while consuming
   measured hardware-specific phase budgets. Embedded retrieval never receives
   role prompts or emits verdicts.
8. Configuration health ships with an `aq-qa` integration check, dashboard
   panel, low-cardinality metrics, alerts, and committed regression fixtures.
9. Raw agent feedback cannot mutate trusted configuration. Findings enter the
   typed recursive feedback/eval/promotion loop.

## Threat model

Fail closed on stale config projections, hidden user overrides, deprecated
aliases, role self-promotion, self-review, model substitution without lineage,
unbounded retries, quota storms, local slot starvation, false terminal state,
PID/attempt replay, prompt/tool drift, fallback misattribution, embedded
instruction injection, and monitoring bypass.

## Delivery and acceptance

Delivery is contract-first: inventory/effective-config doctor, pure schema and
resolver, provider shadows, monitored canaries, adoption, then legacy cleanup.
No live cutover occurs in a contract or shadow slice.

A lane is not complete until its focused tests, live integration check,
dashboard health, exact config fingerprint, typed receipt, and independent
review pass together. Unavailable lanes are capacity-parked and queued for
catch-up; they are never credited early.
