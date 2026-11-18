# Remote model ID refresh (2026-11-18)

Date: 2026-11-18
Task ID: HF-20261118-001

## Objective
Owner directive 2026-11-18: refresh pinned REMOTE model IDs to current provider releases. Local llama.cpp model is out of scope. IDs only, no credentials.

Verified against official lists (fetched 2026-11-18):
- Anthropic: https://platform.claude.com/docs/en/about-claude/models/overview (redirected from docs.anthropic.com). Current: `claude-fable-5-2` (Fable 5.2, confirmed, retirement not before 2027-11-09), `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. Older but listed: Fable 5.1, Fable 5, Opus 5, Opus 4.8/4.7/4.6/4.5, Sonnet 5, Sonnet 4.6/4.5, Haiku 4.5 (still served, superseded). Retired: Opus 4.1, Opus 4, Sonnet 4.
- Google: https://aistudio.google.com/docs/models (redirected from ai.google.dev). Current stable: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`; preview: `gemini-3.1-pro-preview`; new family `gemini-4-carbon|argon|hydrogen` (tiering not stated, not wired). Deprecated: `gemini-2.5-flash` (routes to 3.5-flash-lite 2026-12-01), `gemini-2.5-pro` (routes to 3.8-flash 2026-12-01). Shut down: `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-3-pro-preview`. `gemini-3.5-flash` and `gemini-3.1-pro` (no -preview) are NOT on the list.
- OpenAI: https://developers.openai.com/api/docs/models (redirected from platform.openai.com). Flagship: `gpt-6.2-astra`, `gpt-6.2-sol`, `gpt-6.1-terra`, `gpt-6-luna`; specialized `gpt-6-cyber`, `gpt-5.6-cyber`. No codex/mini IDs listed; the page lists no deprecations (separate deprecations page not fetched). `gpt-5.5`, `gpt-5-mini`, `gpt-4o`, `gpt-4-turbo-preview`, `gpt-6-astra`, `gpt-6-sol` are absent from the current list.

Delivered: runtime configs moved to current IDs in the same tier (below).

## Workflow/Session IDs
- Workflow ID: none (bounded implementer slice)
- Session ID: Simurg@claude/sonnet, orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
Delegated by the orchestrator to a bounded Claude Sonnet implementer (Rule 17). Review is by a different lane (no self-review).

## Commands Executed
```bash
rg (claude-*|gpt-*|gemini-*|o-series) over the worktree at origin/main 4cbcdf63d
WebFetch of the three official model pages above
sed/python edits to the files in the table; json.load check on config/model-coordinator.json
pytest hybrid-coordinator tests; scripts/testing/test-*.py listed under Validation Evidence
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

Inventory and changes (file, old -> new, provider, role):

| File:line | Old | New | Provider | Role |
|---|---|---|---|---|
| config/model-coordinator.json:14,18 | claude-fable-5-1 | UNCHANGED: claude-fable-5-2 is current per docs but probe blocked by usage credits (see Probes) | Anthropic | flagship + creative (tier SSOT) |
| config/model-coordinator.json:15 | claude-opus-5-5 | unchanged (current) | Anthropic | flagship_fallback |
| config/model-coordinator.json:16 | claude-sonnet-5-5 | unchanged (current) | Anthropic | balanced = Rule 17 implementer default |
| config/model-coordinator.json:17 | claude-haiku-4-5-20251001 | claude-haiku-5-5 | Anthropic | fast |
| config/model-coordinator.json (google.baseline_fallback) | gemini-3.5-flash | UNCHANGED (3.5-flash is absent from the official list; gemini-3.6-flash is the candidate but is not probed, CLI does not offer it) | Google | fallback |
| config/model-coordinator.json (google flagship/balanced/fast/deep) | gemini-3.8-flash / 3.5-flash-lite / 3.1-pro-preview | unchanged (current) | Google | default |
| config/model-coordinator.json (openai) | gpt-6-astra / gpt-6-sol | gpt-6.2-astra / gpt-6.2-sol | OpenAI | flagship / balanced |
| config/model-coordinator.json (openai.fast) | gpt-6-luna | unchanged (current) | OpenAI | fast |
| config/workflow-automation.yaml:12 | claude-fable-5-1 | unchanged (Fable probe blocked) | Anthropic | default |
| config/multi-agent-collaboration.yaml:341 | claude-fable-5-1 | unchanged (Fable probe blocked) | Anthropic | default |
| ai-stack/local-orchestrator/remote_agents.py:71 | claude-opus-4-8 | claude-opus-5-5 | Anthropic | default (pricing/context updated to official 4/20, 1M) |
| remote_agents.py:87 | claude-sonnet-4-6 | claude-sonnet-5-5 | Anthropic | default (2/10, 1M) |
| remote_agents.py:103 | claude-haiku-4-5-20251001 | claude-haiku-5-5 | Anthropic | default (0.1/0.5, 1M) |
| remote_agents.py:119 | claude-fable-5 | unchanged id; price/context corrected to official Fable 5 10/50, 1M | Anthropic | default |
| remote_agents.py:135 | gpt-5.5 | gpt-6.2-astra | OpenAI | default |
| remote_agents.py:151 | gpt-5-mini | gpt-6-luna | OpenAI | default (fast tier) |
| scripts/ai/aq-agent-window:87,96 | claude-fable-5-1 / gpt-6-astra | claude-fable-5-1 (unchanged) / gpt-6.2-astra | Anthropic/OpenAI | default |
| scripts/ai/aq-coordinator-repl:109 | claude-fable-5 | unchanged | Anthropic | default |
| scripts/ai/aq-tui-dashboard:931 | gpt-5.5 | gpt-6.2-astra | OpenAI | display label for codex lane |
| scripts/ai/aq-role-route:91-93 | alias set lacks haiku-5-5 | added claude-haiku-5-5 (legacy kept) | Anthropic | alias matcher |
| dashboard/backend/api/routes/aistack.py:6767 | claude-fable-5 | unchanged | Anthropic | root-agent model label |
| hybrid-coordinator core/config.py:403-436 | claude-opus-4-5, gpt-4o, gemini-2.0-flash-thinking | claude-opus-5-5, gpt-6.2-sol, gemini-3.8-flash | all | advisor default + fallback chains |
| hybrid-coordinator knowledge/llm_router.py:1135,1185 | same | same | all | advisor fallback defaults |
| hybrid-coordinator core/routing_contract.py:132-143 | gemini-2.0-flash, claude-sonnet-4-6 | gemini-3.8-flash, claude-sonnet-5-5 | Google/Anthropic | env-fallback aliases |
| routing_contract.py:287 | gemini-2.0-flash key | added gemini-3.8-flash key; legacy key kept | Google | explicit profile map |
| nix/hosts/hyperd/deploy-options.nix:17-29 | gemini-3.1-pro, gemini-3.5-flash | gemini-3.1-pro-preview, gemini-3.8-flash (3.1-flash-lite kept) | Google | remoteModelAliases defaults |
| nix/modules/core/options.nix:1971-1977 | gemini-2.5-flash/2.0-flash/2.5-pro examples | gemini-3.8-flash/3.5-flash-lite/3.1-pro-preview | Google | option examples/docs |
| config/env-contract.yaml:613 | gemini-2.5-pro | gemini-3.8-flash | Google | description example |
| tests: test_advisor_fallback_chains.py:25,37 | opus-4-5, gpt-4o | new defaults | - | assertions of the runtime default (not legacy-ID handling) |

Left unchanged:
- `"owner": "claude-sonnet-4-6"` / `claude-opus-4-8` in `_meta` of ~60 config/*.json|yaml files: authorship metadata, not a runtime model ID.
- scripts/ai/aq-role-route legacy alias entries, routing_contract.py `claude-sonnet`/`claude-opus` family prefixes, aq-chat:474 Co-Authored-By trailer text, llm_code_reviewer/ query-router.sh generic `claude-sonnet|opus` family names: family keys not pinned versions.
- hybrid-coordinator extensions/model_fleet_manager.py (OpenRouter slugs: claude-opus-4-6/4-7, sonnet-4-6, gpt-4o, o1, gemini-2.0-flash(-exp), gemini-2.5-pro, header says slugs are verified against OpenRouter): not verifiable from official provider lists; needs the OpenRouter catalog. Follow-up.
- core/llm_client.py:224 `gpt-4-turbo-preview` default and its test: OpenAI-compatible client default for generic endpoints (follow-up; tests assert it).
- aider/gpt-4o-mini in templates/home.nix, nix/hosts/nixos/home.nix, ai-stack/mcp-servers/aider-wrapper/server.py:510; recommended OpenRouter lists in templates/home.nix:104-109 and config/variables.sh:706-710; agentic_memory_journal.py docstring examples; ai-stack/platform/agent_marketplace.py claude-opus-4; observability/integrate_monitoring.py: user-facing templates/docs/examples keyed to OpenRouter or aider slugs, follow-up.
- Test fixtures (test-aq-land.py gemini-3.8-flash-*, test-security-audit-gate.sh o1/o3/o4, test-round-contribution.py gpt-5-codex, test_llm_client.py gpt-4-turbo-preview, test_advisor_fallback_chains.py fixture rows, test-pi-agent-streaming-ui.py claude-fable-5): fixtures, intentionally untouched.
- Codex CLI and Gemini CLI model selection: set by their own CLIs/config, not repo-pinned beyond config/model-coordinator.json tier ids and the display labels above. Reported only.
- gemini-4-carbon/argon/hydrogen: official page gives no tier mapping; not wired in repo tiers (see Probes). Follow-up for the Gemini tier decision.
- gpt-6.1-terra: available as a "fast and efficient" flagship-family model; gpt-6-luna kept as the fast tier.

SSOT note: config/model-coordinator.json `tiers` is the alias SSOT and its comment tells pools to read from it, but remote_agents.py, aq-agent-window, aq-coordinator-repl, aistack.py, config.py and routing_contract.py still hardcode literals. Follow-up: have them read the tiers instead (not refactored here).

## Validation Evidence
- hybrid-coordinator: `pytest tests/test_advisor_fallback_chains.py tests/test_ai_coordinator_model_awareness.py tests/test_llm_router.py tests/test_orchestrate_routing.py tests/test_route_aliases.py tests/test_router_health.py tests/test_routing_decisions_producer.py` -> 112 passed.
- scripts/testing: test-claude-dispatch-payload-safety (2 OK), test-delegate-claude-model-routing (4 OK), test-model-tiering-health (PASS), test-model-catalog-freshness (PASS), test-maeah-model-registry-schema (PASS), test-delegate-codex-shared-writable (all passed). test-model-tier.py printed no output.
- config/model-coordinator.json parses as JSON.
- Static gates and tier0: see the report summary.

### Probes (synthetic prompt "Reply with the single word OK", OAuth CLI sessions, one call each, 2026-11-18)
| Lane | Model | Command shape | Result |
|---|---|---|---|
| Claude | claude-opus-5-5 | `claude -p --model M --tools "" --no-session-persistence` | OK |
| Claude | claude-sonnet-5-5 | same | OK |
| Claude | claude-haiku-5-5 | same | OK (SSOT fast tier updated) |
| Claude | claude-fable-5-2 | same | model accepted, refused: "Fable 5.2 requires usage credits"; NOT a pass, default not changed |
| Claude | claude-fable-5-1 (current SSOT) | same | same usage-credits refusal; unprobed |
| Codex | gpt-6.2-astra | `codex exec -m M -s read-only` | OK (codex-cli 0.169.0) |
| Codex | gpt-6.2-sol | same | OK |
| Codex | gpt-6-luna | same | OK |
| Codex | gpt-6.1-sol (~/.codex/config.toml today) | same | OK, but not on OpenAI's current list |
| Gemini CLI (agy-based, 1.5.10) | gemini-3.8-flash | `gemini --model M -p` | OK |
| Gemini CLI | gemini-4-hydrogen | same | OK |
| Gemini CLI | gemini-4-argon | same | model accepted, 429 RESOURCE_EXHAUSTED (individual quota, resets in ~152h); NOT a pass |
| Gemini CLI | gemini-4-carbon, gemini-3.6-flash | same | rejected: not in the CLI model list |

Gemini CLI valid names: Gemini 4 Argon/Hydrogen (Low..XHigh), Orchestrator (Argon), Gemini 3.8 Flash (Low/Medium/High), Claude Opus 5.5, Claude Sonnet 5.5, GPT-OSS 120B.

### Lane CLI model selection (inventory)
- Codex: `~/.codex/config.toml` has `model = "gpt-6.1-sol"`, a mutable user file. nix/home/base.nix (~line 2009) already merges that file with yq on activation but does not set `.model`. delegate-to-codex only passes `-m` when `--model` is given (line 779); its usage text still cites o3/o4-mini (follow-up).
- Gemini: `~/.gemini/antigravity-cli/settings.json` has `"model": "Gemini 4 Argon (Medium)"`; mutable, no Nix declaration found. delegate-to-gemini passes `--model` only when given.
- Claude: delegate-to-claude resolves tiers from config/model-coordinator.json (tested). `~/.claude/settings.json` sets no model.
- Proposed declarative ownership (not applied): add `| .model = "gpt-6.2-sol"` to the existing yq pipeline in nix/home/base.nix (codex), and a sibling activation merge in the cpp-dev.nix `cppDevLeanCtxMcp` style (python json merge, only when key absent) for `~/.gemini/antigravity-cli/settings.json` `model`. Left to the owner because it overwrites a personal choice.

## Rollback Plan
`git revert <commit>`; the change is IDs only. Trigger: a provider returns model-not-found for one of the new IDs on a live call.

## Residual Risk
- New IDs are verified against doc listings, not live API calls (no credentials by owner rule).
- gemini-3.6-flash as baseline fallback is taken from the Google list; confirm on a live call.
- remote_agents.py cost figures for the OpenAI entries were not changed (no pricing on the official page fetched).
- Deployed switchboard/coordinator pick up the Nix alias changes only on rebuild (owner act).

## Hint Feedback
- No aq-hints used for this slice.
