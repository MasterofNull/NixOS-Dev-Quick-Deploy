# Gemini lane model roster (2026-11-19)

Date: 2026-11-19
Task ID: HF-20261119-001 (PR #799, branch chore/model-ids-refresh)
Session: Simurg@claude/sonnet, orchestrator Simurg@claude/opus-5.5#da0ef470. Review by a different lane (no self-review).

## Objective
Owner request: update the Gemini lane model list with capabilities and best roles, from the live `gemini models` output (Gemini CLI 1.5.12, OAuth, no API keys). Defaults stay as chosen (Argon primary, automatic Hydrogen fallback on quota). The lane refuses non-Gemini ids.

## Sources (every capability claim in config cites one)
- [G] Google blog, Introducing Gemini 4 Hydrogen: https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-hydrogen/ . Hydrogen is "built to stand on its own as a model for everyday work"; standalone upgrade from Gemini 3.8 Flash; 4 levels low/medium/high(default)/xhigh; 1M context; $1.50/$7.50 per 1M in/out; best for coding, agentic workflows, web prototyping, multimodal work. Carbon and Argon are frontier models for deep long-horizon reasoning. Orchestrator switches models in one session; near-Carbon success with ~24% less quota and 19% faster on Terminal-Bench 4.0; Carbon can coordinate while Hydrogen runs worker/verifier agents.
- [N] 9to5Google quoting Google, Gemini 4 Neon: https://9to5google.com/2026/11/18/gemini-4-neon-announcement/ . Neon sits between Hydrogen and Carbon, "balances depth and efficiency", replaces Argon in the app, comparable to Carbon (sometimes better) at Flash speeds and lower cost; 4 levels low/medium/high/extra high; 1M context; "built for complex coding, analytical reasoning, and production-grade enterprise workflows". Secondary outlet: Google's own Neon post was not fetched.
- [D] Google DeepMind models page: https://deepmind.google/models/gemini/ . Argon "built to solve your hardest problems", resilient to indirect prompt injection; Neon/Hydrogen listed with no description text. No model-card text on levels.
- [A] Antigravity CLI releases: https://github.com/google-antigravity/antigravity-cli/releases . 1.5.10: Orchestrator plans with Gemini 4 Carbon (High) and hands execution to Gemini 4 Hydrogen (High); Carbon/Argon rows merged into one `Orchestrator` row with a planner choice. 1.5.12 changelog (`gemini changelog`): Neon levels added to `--model`; Hydrogen medium thinking for Auto mode review.
- Local: `gemini --help`, `gemini models`, `gemini changelog` (CLI 1.5.12). `gemini models` has no verbose or JSON flag (`--output-format` is rejected), so the list is ids and labels only.

UNVERIFIED (docs silent or third-party only): Argon thinking levels and context window beyond the CLI list (third-party sites say 1,048,576 tokens, low/medium/high); which executor the `gemini-pro-orchestrator-neon` id pairs with (docs describe Carbon/Argon planner + Hydrogen executor; the CLI labels it "Orchestrator (Neon)"); relative speed of Neon-low vs Hydrogen-low; quota-pool sharing between model families; Google's own Neon post.

## Probe (synthetic item, no repo or personal data)
Prompt: evaluate `sum(x for x in xs if x % 3 == 0) * 2` on `[1,3,6,7,9,10]` (answer 36), one-sentence edge-case remark, required final line `ANSWER: <number>`. Run sequentially via `scripts/ai/delegate-to-gemini --role review --mode plan --wait --model <id> --prompt-file <synthetic.md>`. Latency is wall clock for the whole wrapper call (includes CLI start-up and prompt preamble), not a model-speed benchmark.

| Model id | Result | Latency | Correct (36 + final line) |
|---|---|---|---|
| gemini-4-argon-low | QUOTA_EXHAUSTED (Argon); wrapper fell back once to gemini-4-hydrogen, which answered | n/a | fallback answered 36 |
| gemini-4-argon-medium | NOT PROBED (Argon family stop rule) | | |
| gemini-4-argon-high | NOT PROBED (Argon family stop rule) | | |
| gemini-4-hydrogen-low | success | 18s | yes |
| gemini-4-hydrogen-medium | success | 13s | yes |
| gemini-4-hydrogen-high | success | 18s | yes |
| gemini-4-hydrogen-xhigh | success | 40s | yes |
| gemini-4-neon-low | success | 19s | yes |
| gemini-4-neon-medium | success | 19s | yes |
| gemini-4-neon-high | success | 25s | yes |
| gemini-4-neon-xhigh | success | 32s | yes |
| gemini-pro-orchestrator-neon | success (re-run; first run was invalidated because an edit to the fallback script landed mid-run) | 33s | yes |
| gemini-pro-orchestrator-g1-pro | QUOTA_EXHAUSTED rc=3, "Resets in 137h19m6s" (Argon pool) | 19s | n/a |
| gemini-3.8-flash-low | success | 14s | yes |
| gemini-3.8-flash-medium | success | 22s | yes |
| gemini-3.8-flash-high | success | 26s | yes |

Third-party ids (claude-*, gpt-oss) were not probed, per instruction. The probe also showed the bare fallback id `gemini-4-hydrogen` is accepted by the CLI. Finding: one tiny item cannot separate quality between models; roles below rest on the cited positioning plus probe availability, not on measured quality.

## Final role mapping (SSOT: config/model-coordinator.json tiers.google.gemini_lane)
| Role | Model | Basis |
|---|---|---|
| default / primary | gemini-4-argon (CLI default) | owner choice; quota-exhausted at probe time, resets about 137h |
| fallback on quota | gemini-4-hydrogen | owner choice; served and probed OK |
| flagship | gemini-4-argon-high | owner primary; not probed (quota) |
| reviewer | gemini-4-neon-high | [N] complex coding/analysis; probed OK; use while Argon is exhausted |
| deep | gemini-4-neon-xhigh | [N] top level; probed OK |
| balanced | gemini-4-neon-medium | [N]; probed OK |
| implementer | gemini-4-hydrogen-high | [G] default level, everyday coding/agentic; probed OK |
| fast | gemini-4-hydrogen-low | [G]; probed OK |
| orchestrator | gemini-pro-orchestrator-neon | [G][A] plan/execute split; probed OK |
| baseline fallback | gemini-3.8-flash-medium | still served by the CLI |

Stale ids: `gemini-3.5-flash-lite` and `gemini-3.1-pro-preview` are not served by the CLI, but they are direct-API ids (switchboard / Nix `remoteModelAliases`) that Google's model page still lists (see 2026-11-18-model-ids-refresh.md), so they are kept in `tiers.google`; the CLI lane has its own `gemini_lane` block and a served baseline.

## Independence guard
`scripts/ai/lib/gemini-model-guard.sh` (sourced by `delegate-to-gemini` and `gemini-quota-fallback.sh`) rejects any `--model` not starting with `gemini_lane.required_id_prefix` (case-insensitive) with `GEMINI_LANE_NON_GEMINI_MODEL`, exit 2, before any CLI call. The fallback id is now read from the coordinator (env `GEMINI_FALLBACK_MODEL` still overrides). Test: `scripts/testing/test-gemini-model-guard.py` (claude-opus/sonnet, gpt-oss, mixed-case refused with the CLI never invoked; gemini ids pass; roster/default/fallback consistency).

## Validation
- `python3 scripts/testing/test-gemini-model-guard.py` (3 tests) and `test-gemini-quota-fallback.py` (6 tests) pass.
- tier0: see the PR/commit body.
