# Phase 148 Agentic Mind Research Pass

Date: 2026-06-07
Scope: research only. No Nix activation, service restart, or implementation change was performed in this pass because the previous system build produced desktop input instability.

## Executive Findings

1. `scripts/ai/aq-chat` is a high-confidence local model degradation source. It injects `enable_thinking=true` in the system prompt and sends `chat_template_kwargs: {"enable_thinking": True}` for both direct local and switchboard local-tool calls. This contradicts the current local model contract, which requires Qwen thinking to be disabled for stable tool/final-answer behavior.
2. The switchboard protects local requests only when the caller has not already supplied `chat_template_kwargs`. Because `aq-chat` explicitly supplies `enable_thinking=True`, switchboard does not override it.
3. `config/local-agent-config.yaml` is a multi-document YAML file. Any code path using `yaml.safe_load()` against it will fail with `expected a single document ... but found another document`; code must use `safe_load_all()` or split base config from environment overlays.
4. The current golden eval set is too thin to detect agentic workflow degradation. `data/harness-golden-evals.json` contains only two checks and cannot validate canonical workflow adherence, output envelope shape, role behavior, or cross-provider interchangeability.
5. Several authority docs are stale relative to live config. `docs/architecture/agent-behavior-parity-index.md` references parity plan files that now live under archive paths, and `docs/architecture/routing-profile-inventory.md` still reports some alias/profile gaps that current `config/route-aliases.json` has already closed.
6. The desktop input incident is not currently explained by an obvious synthetic-input process. Current process inventory found no active `ydotool`, `xdotool`, `wtype`, `kmonad`, `keyd`, `warpd`, `dotool`, or `xte` process. Logs do show COSMIC compositor/session config errors around login, including missing input-related keys and invalid shortcut action parsing. VSCodium's Gemini Code Assist A2A server is active, but that is only a suspect context, not a root cause.

## Authority And Workflow Pass

Canonical workflow remains `.agent/WORKFLOW-CANON.md`:

`ORIENT -> RESEARCH -> PRD/PLAN -> MEMORY-CHECKPOINT -> EXECUTE(slice) -> VALIDATE -> DOC-UPDATE -> COMMIT`

The live role authority is `docs/architecture/role-matrix.md`. It requires role injection through `shared/llm_config.py` and role-specific system prompts. Runtime review found that local delegate execution constructs its own `SYSTEM_PROMPT` and uses `build_llama_payload()`, but the direct payload builder does not pass a `role=` argument. That means role behavior may depend on ad hoc prompt text rather than the role injection contract.

## Config And Routing Pass

Live profile inventory from `config/switchboard-profiles.yaml`:

- `continue-local`
- `coordinator-internal`
- `default`
- `embedded-assist`
- `embedding-local`
- `local-agent`
- `local-coding`
- `local-tool-calling`
- `remote-coding`
- `remote-default`
- `remote-free`
- `remote-gemini`
- `remote-reasoning`
- `remote-tool-calling`

Live alias notes from `config/route-aliases.json`:

- `Reasoning` still resolves to `local-tool-calling` for backward compatibility.
- `RemoteReasoning` resolves to `remote-reasoning`.
- `RemoteDefault` resolves to `remote-default`.
- `local` resolves to `default`.

Risk: `config/intent-routing-map.json` still contains direct `profile: "local"` and `fallback: "local"` entries. That may be fine if all callers pass through alias resolution, but it is a drift risk if any route code treats profile strings as already canonical.

`config/model-profile.json` is stale for active behavior decisions:

- `last_updated`: 2026-05-20
- `probed_at`: 2026-05-07T17:41:53.741214Z
- `has_thinking_mode`: true
- `can_disable_thinking`: true

Phase 148 should add a freshness gate before trusting model capability and token-budget assumptions.

## Runtime Adapter Pass

Confirmed direct contradiction:

- `scripts/ai/aq-chat` line 127 advertises `enable_thinking=true` in the prompt contract.
- `scripts/ai/aq-chat` lines 193 and 196 send `chat_template_kwargs: {"enable_thinking": True}`.
- `ai-stack/mcp-servers/shared/llm_config.py` sets `chat_template_kwargs: {"enable_thinking": False}` as the shared local payload contract.
- `ai-stack/switchboard/switchboard.py` only injects the safe default when the caller has not already provided `chat_template_kwargs`.

Static search shows most core paths already use `enable_thinking=False`, including `scripts/ai/lib/dispatch.py`, local-agent runtime tests, hybrid route handler helpers, and `smoke-local-model.sh`. The gap is not global absence of the contract; it is inconsistent enforcement and direct-bypass call sites.

Direct local inference call sites needing follow-up audit include:

- `scripts/ai/claude-local-wrapper.py`
- `scripts/ai/lib/model-client.py`
- `scripts/deploy/fix-llama-hang.sh`
- `ai-stack/meta-optimization/meta_optimizer.py`
- `ai-stack/autonomous-improvement/research_phase.py`
- `ai-stack/autonomous-improvement/trigger_engine.py`
- `ai-stack/self-improvement/llm_code_reviewer.py`
- `ai-stack/autoresearch/local_model_optimizer.py`
- `ai-stack/local-orchestrator/mcp_client.py`
- `ai-stack/mcp-servers/aidb/*parallel*` and `llama_cpp_tool_agent.py`

The right implementation move is a static aq-qa check that fails new direct local chat payloads unless they use `build_llama_payload()` or explicitly set `chat_template_kwargs.enable_thinking=false`.

## Eval And Observability Pass

Current checks detect transport health better than behavioral parity:

- `scripts/testing/smoke-agent-harness-parity.sh` verifies model endpoint availability, profile responses, headers, workflow endpoint shape, and review/acceptance endpoint shape.
- `scripts/automation/run-harness-regression-gate.sh` can run online golden evals, but offline mode only validates JSON structure.
- `data/harness-golden-evals.json` has only `headers-presence` and `workflow-plan`.
- `scripts/testing/test-delegated-prompt-failure-trend.py` confirms reporting/hints for prompt-contract failure trends, but does not gate model output quality directly.

Required Phase 148 additions:

1. Agent task envelope schema used by all lanes.
2. Workflow adherence golden corpus covering orientation, research, plan, memory checkpoint, execution boundary, validation, docs, and commit handoff.
3. First-pass contract evaluator that records whether the first model output followed the envelope without fallback repair.
4. Dashboard and `aq-report` interop scorecard: by model/profile/provider, show first-pass validity, role adherence, identity emission, tool-call validity, and workflow-step coverage.

## Desktop Input Incident Pass

User report: the previous system build had to be reverted because OS cursor and text input became erratic.

Read-only checks performed:

- Current `/run/current-system` points to generation 677 path `/nix/store/c1pa0arysxgivrnlb1ppxsk67v4qbf48-nixos-system-hyperd-25.11.20260522.b77b3de`.
- Generation 676 exists at `/nix/store/2p1491zhjsbi58l43g0znf49fspjhnl4-nixos-system-hyperd-25.11.20260522.b77b3de`.
- Generation 678 exists at `/nix/store/6xgmbzni7jjwahkklmvxp9s11si6yjdi-nixos-system-hyperd-25.11.20260522.b77b3de`.
- No active obvious synthetic-input daemon was found in process inventory.
- COSMIC user logs show compositor/session config errors involving missing `input_default`, `input_touchpad_override`, `input_devices`, `keyboard_config`, `cursor_follows_focus`, `focus_follows_cursor_delay`, and `xwayland_eavesdropping` keys.
- COSMIC logs also show invalid `SystemAction(Suspend)` shortcut parsing.
- VSCodium is running under X11-on-COSMIC with `google.geminicodeassist` A2A server active.

Do not run another rebuild until the input incident has a rollback-safe diagnostic checklist. The next diagnostic pass should compare generations 677 and 678, inspect COSMIC config declarations, and capture focused journal slices immediately before and after activation.

## Implementation Prerequisites

1. Fix the `aq-chat` thinking-mode contradiction first. This is likely repo-only and should not require Nix activation if the CLI script is invoked from the checkout, but validate before assuming.
2. Add a static qa gate for local inference payload discipline: no explicit `enable_thinking=true`; direct llama calls must use the shared payload builder or prove safe kwargs.
3. Normalize `local-agent-config.yaml` parsing, or split environment overrides into a separate file.
4. Refresh `docs/architecture/agent-behavior-parity-index.md` and `docs/architecture/routing-profile-inventory.md` before treating them as active implementation authorities.
5. Expand golden evals and add first-pass behavioral scoring before comparing providers.
6. Add a desktop-input health probe or operational checklist before the next `nixos-rebuild switch`.
