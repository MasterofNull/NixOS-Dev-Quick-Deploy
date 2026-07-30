# Antigravity Design Input: Agent/Model Configuration Parity Architecture

**Author:** Antigravity (Gemini 3.6 Flash / IDE Agent Node)  
**Target:** `agent-model-config-parity`  
**Date:** 2026-07-29  
**Verdict:** `VERDICT: READY_FOR_SYNTHESIS`

---

## 1. Canonical Typed Agent Deployment Specification (`AgentDeploymentSpec`)

```yaml
schema_version: "aq.agent-deployment-spec/1.0"
agent_id: "string"                  # e.g., "antigravity-ide", "codex-orchestrator", "local-coding"
role: "string"                      # orchestrator | implementer | reviewer | architect
authority_level: "string"           # read_only | bounded_edit | full_autorun
model_tier: "string"                # flagship | balanced | fast | deep
provider: "string"                  # google | anthropic | openai | local_apu
model_id: "string"                  # e.g., "gemini-3.6-flash", "claude-fable-5", "qwen3.6-35b"
thinking_level: "string"            # minimal | low | medium | high
context_budget_tokens: 1048576       # token budget limit
prompt_lineage_hash: "sha256"       # SHA-256 of system/developer prompt payload
allowed_tools: ["string"]          # strict tool whitelist
sandbox_policy: "string"            # read_only | restricted_fs | isolated_net
delegation_max_depth: 2             # maximum nested delegation depth
timeout_seconds: 300
retry_budget:
  max_attempts: 3
  backoff_factor: 2.0
reviewer_eligibility:
  can_review_self: false
  can_review_roles: ["implementer"]
fallback_chain: ["string"]           # fallback model/provider tier IDs
```

---

## 2. SSOT vs. Provider-Specific Projections

### Provider-Neutral SSOT (`config/model-coordinator.json` / `config/agent-deployments.yaml`)
- `agent_id`, `role`, `authority_level`, `model_tier`, `allowed_tools`, `context_budget_tokens`, `reviewer_eligibility`, `fallback_chain`.

### Provider-Specific Projections
1. **Google Gemini (`delegate-to-antigravity` / Switchboard)**:
   - Maps `thinking_level` to `thinking_config.thinking_budget` or native Gemini presets (`medium`/`high`).
   - Uses `/v1beta/openai` direct endpoint formatting.
2. **Anthropic Claude (`delegate-to-claude`)**:
   - Maps `anthropic-version` headers and prompt caching markers.
3. **Codex (`.codex/config.toml` & `.codex/agents/*.toml`)**:
   - Project TOML structure for local IDE integration.
4. **Local APU / Qwen (`delegate-to-local`)**:
   - Enforces `enable_thinking=false` and strict APU defensive ceilings (`thinking_budget~200`, `SWB_LOCAL_CONCURRENCY=1`).

---

## 3. Config Precedence, Fingerprinting & Verification

### Precedence Order
1. **Base Defaults** (`config/model-coordinator.json`)
2. **Declarative Nix Configuration** (`nix/home/base.nix` & `nix/modules/roles/ai-stack.nix`)
3. **Environment Contract** (`config/env-contract.yaml`)
4. **Runtime Task Overrides** (explicit CLI parameters `--model`, `--mode`)

### Fingerprinting & Drift Detection
- Every merged spec generates a cryptographic `config_fingerprint` (`sha256(canonical_yaml)`).
- Delegation wrappers inject `config_fingerprint` into request headers and receipt metadata.
- `aq-qa` phase checks compute active fingerprint and compare against the Home Manager generation hash to flag stale overrides instantly.

---

## 4. Lane Differentiation & Zero-Trust Authority Contract

| Deployment Lane | Context Ceiling | Thinking Control | Execution Ceiling | Evidence & Authority |
|---|---|---|---|---|
| **Remote Flagship (Gemini/Claude)** | 200k - 1M+ | Native `high` | API native concurrency | Immutable signed evidence receipt required |
| **Economical Implementer** | 128k | Native `medium` | Bounded file edits | Mandatory Tier0 gate check before commit |
| **Local APU (Qwen3.6-35b)** | 32k | Defensive `~200` | Single slot (`SWB_LOCAL_CONCURRENCY=1`) | Offline execution receipt |
| **Embedded Retrieval (Qdrant)** | 512 | N/A | Vector read-only | Vector search audit trace |

All lanes enforce identical fail-closed security gates, read-before-edit constraints, and reviewer eligibility rules.

---

## 5. Wrapper Schemas & Golden Vectors

- **Envelope Contract**: `aq.agent-delegation-request/1.0` and `aq.agent-delegation-response/1.0`.
- **Golden Vector Test**: `scripts/testing/test-agent-delegation-wrapper-parity.py` validates canonical JSON request serialization across `delegate-to-antigravity`, `delegate-to-claude`, and `delegate-to-local`.

---

## 6. Observability, Receipts & Metrics

- **Lifecycle States**: `CREATED` -> `VALIDATED` -> `RUNNING` -> `COMPLETED` | `FAILED` | `PARKED`.
- **Metrics**:
  - `agent_delegation_requests_total{agent_id, provider, status}`
  - `agent_delegation_latency_seconds{agent_id, provider}`
  - `agent_token_consumption_total{agent_id, model_id, direction}`
- **Dashboard Binding**: Real-time status cards and telemetry ribbons on `:8889`.

---

## 7. Migration Slices

1. **Slice 1 (Contract)**: Define `AgentDeploymentSpec` JSON Schema in `config/schemas/`.
2. **Slice 2 (Shadow)**: Implement `config_fingerprint` injection across delegation scripts in report-only mode.
3. **Slice 3 (Canary)**: Enforce fingerprint verification on `delegate-to-local`.
4. **Slice 4 (Adoption)**: Roll out spec validation to `delegate-to-antigravity` and `delegate-to-claude`.
5. **Slice 5 (Cleanup)**: Deprecate legacy ad-hoc environment variables.

---

## 8. Current Conflicts & Stale Claims

1. **OpenRouter Legacy References in `model-coordinator.json`**:
   - `qwen-coder` points to `openrouter` endpoint while local direct APU runs `qwen3.6-35b`. **Severity: Medium**.
2. **Model Alias Drift in `deploy-options.nix`**:
   - Legacy comments referenced `gemini-3.5-flash` while active IDE uses `gemini-3.6-flash`. **Severity: Low (Resolved)**.

---

VERDICT: READY_FOR_SYNTHESIS
