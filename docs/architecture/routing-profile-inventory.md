# Routing and Profile Inventory — Drift Report

**Status:** Accepted — Phase 58A.2 (2026-05-18)
**Upstream authority:** `docs/architecture/canonical-kernel-declaration.md`, `docs/architecture/role-matrix.md`
**Sources inspected:**
- `config/route-aliases.json` — human-facing alias → profile map
- `config/intent-routing-map.json` — intent classifier → profile map
- `ai-stack/mcp-servers/hybrid-coordinator/core/routing_contract.py` — profile registry
- `nix/modules/services/switchboard.nix` — profile-card definitions
- `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` — profile documentation

---

## Canonical object model applied to routing

Per the kernel declaration (58A.0), the routing layer should distinguish four levels:

| Level | What it is | Where it lives |
|---|---|---|
| **Human-facing intent alias** | What a caller writes (e.g. `Explore`, `Plan`) | `config/route-aliases.json` |
| **Semantic intent** | Classifier-resolved task type (e.g. `planning`, `code_generation`) | `config/intent-routing-map.json` |
| **Canonical profile** | Execution-policy name with stable semantics | `routing_contract.py` PROFILE_REGISTRY + switchboard.nix profile-cards |
| **Provider / model realization** | Actual model loaded for a profile | `SWITCHBOARD_REMOTE_ALIAS_*` env vars (injected by Nix) |

Adapters (route-aliases resolver, intent classifier) should be distinct from the canonical profile. Currently they are — but there are drift gaps between them.

---

## Full profile inventory

### Local tier (LOCAL)

| Profile | Tier | Model alias | Alias-reachable | Intent-routed | SWB card | Doc |
|---|---|---|---|---|---|---|
| `default` | LOCAL | llama-cpp-local | yes | — | yes | yes |
| `continue-local` | LOCAL | llama-cpp-local | no | — | yes | yes |
| `local-agent` | LOCAL | llama-cpp-local | yes | — | yes | yes |
| `embedded-assist` | LOCAL | llama-cpp-local | yes | — | yes | yes |
| `local-tool-calling` | LOCAL | llama-cpp-local | yes | code_gen / code_review / tool_exec | yes | yes |
| `embedding-local` | LOCAL | embeddings-local | no | — | yes | yes |
| `local` | LOCAL | llama-cpp-local | no | knowledge / math / delegation | **no** | no |
| `local-chat` | LOCAL | llama-cpp-local | no | — | **no** | no |

### Edge tier (EDGE — local specialist models, unprovisioned on this hardware)

| Profile | Tier | Model alias | Alias-reachable | Intent-routed | SWB card | Doc |
|---|---|---|---|---|---|---|
| `local-coding` | EDGE | llama-cpp-coder | no | — | **no** | no |
| `local-reasoning` | EDGE | llama-cpp-reasoning | no | — | **no** | no |

### Remote-free tier (REMOTE_FREE)

| Profile | Tier | Model alias | Alias-reachable | Intent-routed | SWB card | Doc |
|---|---|---|---|---|---|---|
| `remote-default` | REMOTE_FREE | alias_gemini | **no** | — | yes | yes (table only) |
| `remote-free` | REMOTE_FREE | alias_free | yes | — | yes | yes |
| `remote-gemini` | REMOTE_FREE | alias_gemini | yes | — | yes | yes |

### Remote-paid tier (REMOTE_PAID)

| Profile | Tier | Model alias | Alias-reachable | Intent-routed | SWB card | Doc |
|---|---|---|---|---|---|---|
| `remote-coding` | REMOTE_PAID | alias_coding | yes | — | yes | yes |
| `remote-reasoning` | REMOTE_PAID | alias_reasoning | troubleshooting / planning | yes | yes | yes |
| `remote-tool-calling` | REMOTE_PAID | alias_tool | yes | — | yes | yes |

---

## Human-facing alias inventory

Source: `config/route-aliases.json`

| Alias | Resolved profile | Notes |
|---|---|---|
| `default` | `default` | identity |
| `Explore` | `default` | |
| `Plan` | `default` | |
| `Continuation` | `default` | |
| `Implementation` | `local-tool-calling` | |
| `Reasoning` | `local-tool-calling` | misnamed: sends to local, not remote-reasoning |
| `ToolCalling` | `local-tool-calling` | |
| `Agent`, `LocalAgent`, `local-agent` | `local-agent` | 3 aliases → 1 profile |
| `EmbeddedAssist`, `embedded-assist` | `embedded-assist` | |
| `RemoteFree` | `remote-free` | |
| `RemoteGemini` | `remote-gemini` | |
| `RemoteCoding` | `remote-coding` | |
| `RemoteReasoning` | `remote-reasoning` | |
| `RemoteToolCalling` | `remote-tool-calling` | |

---

## Intent classifier → profile map

Source: `config/intent-routing-map.json` (hot-reloadable, Phase 54)

| Intent class | Primary profile | Fallback profile | Memory recall |
|---|---|---|---|
| `code_generation` | `local-tool-calling` | `local` | no |
| `code_review` | `local-tool-calling` | `local` | no |
| `knowledge_lookup` | `local` | `local` | yes |
| `planning` | `remote-reasoning` | `local` | yes |
| `math_reasoning` | `local` | `local` | no |
| `tool_execution` | `local-tool-calling` | `local` | no |
| `troubleshooting` | `remote-reasoning` | `remote-free` | yes |
| `delegation` | `local` | `local` | yes |

---

## Drift findings

### D-1: `local` profile is intent-routed but alias-unreachable and undocumented

**Severity: Medium**

`config/intent-routing-map.json` routes `knowledge_lookup`, `math_reasoning`, and `delegation` to the `local` profile. The `local` profile exists in `routing_contract.py` (tier=LOCAL, model=llama-cpp-local) but:
- It is NOT in `route-aliases.json` `allowed_profiles` — the alias resolver would reject it.
- It has no switchboard profile-card.
- It is not documented in `46-SWITCHBOARD-PROFILES.md`.

The intent classifier therefore uses a profile that bypasses the alias resolver's validation gate. In practice, `local` and `default` both resolve to the same llama.cpp endpoint, so the current behavior is functionally equivalent — but the conceptual split is confusing and the `local` profile has no documented semantics distinct from `default`.

**Recommendation:** Either (a) make `local` an explicit alias for `default` in route-aliases.json and document it, or (b) change intent-routing-map.json to use `default` instead and retire the `local` profile name.

---

### D-2: `Reasoning` alias routes to `local-tool-calling`, not `remote-reasoning`

**Severity: Low (naming confusion, not a runtime bug)**

The alias `Reasoning` in route-aliases.json resolves to `local-tool-calling` (LOCAL tier). A caller expecting reasoning capabilities (architecture/planning) would expect `remote-reasoning` (REMOTE_PAID, claude-sonnet level). The alias name is misleading.

**Recommendation:** Rename alias `Reasoning` → `LocalReasoning` or `LocalTool` and add a new alias `Reasoning` → `remote-reasoning`. Consider a migration note.

---

### D-3: `remote-default` profile — in registry and SWB but not alias-reachable and partially documented

**Severity: Low**

`remote-default` exists in `routing_contract.py` (REMOTE_FREE, alias_gemini) and switchboard.nix has a profile-card for it, and it appears in the `46-SWITCHBOARD-PROFILES.md` profile matrix table. However:
- It is NOT in `route-aliases.json` allowed_profiles or aliases.
- The 46-SWITCHBOARD-PROFILES.md decision tree does not mention it.

It appears to be a fallback convenience profile that was added to the registry but never fully wired into the front-door alias system.

**Recommendation:** Either add `RemoteDefault → remote-default` alias and document the use case, or deprecate it in routing_contract.py.

---

### D-4: EDGE-tier profiles (`local-coding`, `local-reasoning`) are phantom entries

**Severity: Low (hardware-blocked)**

`routing_contract.py` defines `local-coding` (EDGE) and `local-reasoning` (EDGE) targeting `LLAMA_CPP_CODER_URL` / `LLAMA_CPP_REASONING_URL`. These URLs are not provisioned on this hardware (Renoir APU, single llama.cpp instance). There are no switchboard profile-cards for them.

They are aspirational entries that pre-declare the EDGE tier for when a second specialised model is available.

**Recommendation:** Mark them clearly as `# aspirational — unprovisioned` in routing_contract.py and do not route anything to them until the hardware or remote model fills the slot.

---

### D-5: `local-chat` is an orphan profile

**Severity: Low**

`local-chat` exists only in routing_contract.py (LOCAL, llama-cpp-local, "Chat-optimised local inference"). No switchboard card, no alias, no documentation, no intent routing. Semantically identical to `default` for this hardware.

**Recommendation:** Remove `local-chat` from routing_contract.py in a cleanup slice, or document and wire it if there is a real use case.

---

### D-6: Dashboard port stale value in switchboard.nix profile-card

**Severity: Low (cosmetic)**

The `local-agent` profile-card in `switchboard.nix` contains:
```
dash:8006
```
The canonical dashboard port is **8889** per `nix/modules/core/options.nix`. The profile-card hard-codes an old value.

**Recommendation:** Fix the injected profile-card text in switchboard.nix to use the Nix option value rather than a hard-coded port.

---

### D-7: Two parallel routing paths with no explicit priority rule

**Severity: Medium**

Incoming requests to `POST /query` can be routed via:
1. **Alias path** — `route` field in request body → `route_aliases.resolve_route_alias()` → canonical profile.
2. **Intent path** — `IntentClassifier` classifies the query text → `intent-routing-map.json` lookup → profile (bypasses alias resolver).

There is no documented rule for when each path is taken, which takes precedence, or how conflicts are resolved. The intent path can target profiles (`local`) that the alias path's validator would reject.

**Recommendation:** Document the priority rule in `docs/architecture/front-door-routing.md`. The likely correct rule is: explicit `route` field in request → alias path; no `route` field → intent classification path. This should be stated explicitly and enforced.

---

## No-drift confirmations

- Provider/model env vars are correctly not hardcoded: routing_contract.py reads `SWITCHBOARD_REMOTE_ALIAS_*` at runtime.
- Profile tier hierarchy (LOCAL → EDGE → REMOTE_FREE → REMOTE_PAID → REMOTE_FLAGSHIP) is correctly defined and used.
- `config/route-aliases.json` validation.allowed_profiles correctly excludes unprovisioned EDGE profiles.
- Budget/fallback behavior: `SWB_REMOTE_DAILY_TOKEN_CAP` fallback is documented and runtime-controlled.
- Port options: all service ports in switchboard.nix come from `nix/modules/core/options.nix` (except the D-6 local-agent card).

---

## Consequences for later Phase 58A slices

### 58A.3 — instruction projections
Instruction surfaces that mention profiles (e.g., `local-agent`, `remote-reasoning`) should use the canonical profile names from this inventory. The `Reasoning` alias naming confusion (D-2) should be noted so projections don't repeat it.

### 58A.4 — Gemini review gate
Gemini's review gate should specify which profiles it may invoke. Per this inventory, Gemini work typically flows via `remote-gemini` (REMOTE_FREE). The review gate contract must state whether Gemini may self-route to `remote-reasoning` (REMOTE_PAID).

### 58A.5 — Qwen bounded-task eligibility
Qwen's task eligibility should map to specific profiles. Per this inventory, bounded Qwen tasks should target `local` or `local-tool-calling` (LOCAL tier) and must not escalate to remote tiers without orchestrator assignment.

---

## Recommended remediation priority

| Finding | Priority | Effort | Blocks |
|---|---|---|---|
| D-7: dual routing paths, no priority rule | P1 | small doc fix | correctness understanding |
| D-1: `local` profile not in allowed_profiles | P2 | config change | alias validation consistency |
| D-2: `Reasoning` alias misnaming | P2 | config change | caller expectations |
| D-6: dashboard port stale in SWB card | P2 | one-line nix fix | accuracy |
| D-3: `remote-default` not alias-reachable | P3 | config or doc change | completeness |
| D-4: EDGE phantom profiles | P3 | comment-only fix | clarity |
| D-5: `local-chat` orphan | P3 | delete one entry | cleanliness |
