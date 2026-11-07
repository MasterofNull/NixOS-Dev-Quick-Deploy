# 2026-11-06 sweep-lanes

## Objective
Recovery sweep P2.6 (system-integrity-recovery): each MCP server connects and each agent lane (Claude, Codex, Gemini, local) dispatches, judged from live state. Report only; no config, tracker or backlog was changed.

## Workflow/Session IDs
Branch feat/sweep-lanes, date 2026-11-06, live host.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet (Rule 17, bounded single-script slice with fixtures).

## Commands Executed
- `scripts/governance/sweep-lanes.py --probe --date 2026-11-06 --dump-fixture /tmp/claude-1000/-home-hyperd-Documents-NixOS-Dev-Quick-Deploy/06eebc53-2284-45b0-b12f-5fbdefb7d0e9/scratchpad/live-probe.json --report /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/worktrees/p26-lanes-sweep/docs/harness-first/evidence/2026-11-06-sweep-lanes.md`
- `scripts/ai/delegate-to-codex|claude --budget-check-only --role review` (no model call)
- Registry read: `.agents/delegation/registry.jsonl`; local `GET /health`, `GET /slots`
- MCP: one `initialize` + `tools/list` per unique server, own process group, killed and verified; no tool called
- Probes (only with --probe): one tiny prompt per lane, 60 s remote / 120 s local hard timeout

## Validation Evidence

Counts per class:

| Class | Count |
|---|---|
| LANE_DOWN | 0 |
| QUOTA_MODEL | 0 |
| HANG | 0 |
| PROBE_SLOW | 0 |
| NO_RECENT_SUCCESS | 1 |
| BUDGET_EXHAUSTED | 1 |
| RETIRED_REF | 7 |
| MCP_CONNECT_FAIL | 1 |
| MCP_TIMEOUT | 0 |
| MCP_CONFIG_MISSING_BINARY | 0 |
| MCP_NO_TOOLS | 0 |
| MCP_DRIFT | 1 |
| MCP_LEFTOVER_PROCESS | 0 |

Total findings: 11. Unknown (not counted as pass): 4. Probe run: yes.

Lane status:

| Lane | Wrapper | CLI | Auth | Budget | Registry | Probe / health |
|---|---|---|---|---|---|---|
| claude | ok | /home/hyperd/.local/bin/claude | present (0d old file) | headroom | 0 done/24h, last ok 11d ago; last failure 2026-08-01T16:24:25Z (failed): reason not recorded | haiku: OK in 6.5s |
| codex | ok | /home/hyperd/.npm-global/bin/codex | present (5d old file) | EXHAUSTED | 4 done/24h, last ok 11h ago; last failure 2026-10-31T23:06:04Z (failed): ERROR: You’ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), visit https://chatgpt.com/settings/usage to purchase more credits or try a | cli-default: OK in 15.3s, 22139 tok |
| gemini | ok | /home/hyperd/.local/bin/gemini | present (25d old file) | n/a | 11 done/24h, last ok 18m ago; last failure 2026-11-06T19:45:45Z (failed): error: interrupted | cli-default: OK in 12.7s; gemini-3.8-flash: OK in 44.3s |
| local | ok | n/a | n/a | n/a | 14 done/24h, last ok 8h ago; last failure 2026-11-03T20:19:25.605006Z (failed): Error: timed out | /health ok, slots 1 (0 busy); llama.cpp: OK in 8.8s, 21 tok |

Probes:

| Lane | Model | Verdict | Time | Tokens | Detail |
|---|---|---|---|---|---|
| claude | haiku | OK | 6.5s | unknown | [{"type":"system","subtype":"init","cwd":"/tmp/sweep-lanes-p |
| codex | cli-default | OK | 15.3s | 22139 | OK |
| gemini | cli-default | OK | 12.7s | unknown | OK |
| gemini | gemini-3.8-flash | OK | 44.3s | unknown | OK |
| local | llama.cpp | OK | 8.8s | 21 | OK |

MCP servers (one handshake per unique server; env values never printed):

| Server | Configured for | Result | Protocol | Tools | Config names |
|---|---|---|---|---|---|
| `lean-ctx` | antigravity-shared,claude,codex,gemini | ok | 2025-06-18 | 47 | lean-ctx |
| `mcp-bridge-hybrid.py` | antigravity-shared,claude,codex,gemini | ok | 2025-06-18 | 46 | Harness MCP, ai-stack-harness, hybrid-coordinator |
| `mcp-github-server` | claude | unknown | - | - | github |
| `mcp-playwright-sandboxed` | claude,gemini | unknown | - | - | Playwright MCP, playwright |
| `mcp-rea-sandboxed` | claude,codex,gemini | CONNECT FAIL | - | - | REA MCP, rea |
| `osint-tools` | claude,codex | ok | 2025-06-18 | 3 | osint-tools |
| `semgrep` | antigravity-shared,claude,gemini | ok | 2025-06-18 | 7 | Semgrep MCP, semgrep |
| `url:developers.openai.com/mcp` | codex | ok | 2025-06-18 | 5 | openaiDeveloperDocs |

Config files read: `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/worktrees/p26-lanes-sweep/.mcp.json`, `/home/hyperd/.claude.json`, `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/worktrees/p26-lanes-sweep/.claude/settings.json`, `/home/hyperd/.claude/settings.json`, `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/worktrees/p26-lanes-sweep/.gemini/settings.json`, `/home/hyperd/.gemini/settings.json`, `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/worktrees/p26-lanes-sweep/.agents/mcp_config.json`, `/home/hyperd/.codex/config.toml`
Config files absent: none

Findings:

| # | Sev | Class | Subject | Evidence |
|---|---|---|---|---|
| 1 | high | BUDGET_EXHAUSTED | `codex` | delegate-to-codex --budget-check-only refused (exit 3): [delegate-to-codex] Token budget: 325593/250000 (24h rolling headless) \| used: 325593/250000 tokens (24h window) \| implement headroom: 0 (limit 150000, 40% reserved for review) \| review headroom: 0 \|  |
| 2 | high | MCP_CONNECT_FAIL | `mcp-rea-sandboxed` | closed (exit 1); stderr: bwrap: execvp rea: No such file or directory {"argv_sha256":"<redacted>","duration_s":0.12544496401096694,"egress":null,"exit_code":1,"limits":{"as":4294967296,"core":0,"cpu":300,"fsize":1073741824}," |
| 3 | medium | NO_RECENT_SUCCESS | `claude` | no successful dispatch in the last 1d; last success 11d ago; 0 failures in window |
| 4 | medium | RETIRED_REF | `.agents/hooks.json` | 1 antigravity reference(s) at line(s) 8; first: "command": "python3 /home/hyperd/.gemini/hooks/lean-ctx-rewrite-antigravity.py" |
| 5 | medium | RETIRED_REF | `config/lane-eligibility-registry.json` | 1 antigravity reference(s) at line(s) 5; first: "antigravity": { |
| 6 | medium | RETIRED_REF | `config/model-coordinator.json` | 1 antigravity reference(s) at line(s) 21; first: "_comment": "Google Gemini direct (generativelanguage.googleapis.com/v1beta/openai) via the antigravity wrappe |
| 7 | medium | RETIRED_REF | `config/remote-lane-egress.json` | 1 antigravity reference(s) at line(s) 31; first: "antigravity": { |
| 8 | medium | RETIRED_REF | `registry` | 10 antigravity dispatch rows in the last 30 days; newest 2026-11-02T00:54:46.471002Z (status timeout) |
| 9 | medium | MCP_DRIFT | `semgrep@codex` | repo .mcp.json defines `semgrep` but no codex config (user or repo level) has it |
| 10 | low | RETIRED_REF | `scripts/ai/delegate-to-codex` | 1 antigravity reference(s) at line(s) 487; first: # so codex receives the SAME facts as local/antigravity, then the codex-specific |
| 11 | low | RETIRED_REF | `scripts/ai/delegate-to-gemini` | 4 antigravity reference(s) at line(s) 171, 196, 368, 463; first: "^Warning:\|^YOLO mode\|^Attempt [0-9]+ failed\.\|An unexpected critical\|FetchError\|ETIMED\|EAI_AGAIN\|ENOTFOUND\|re |

Unknown / not determinable:

- `gemini`: wrapper has no budget check; quota is only observable by a probe
- `local`: wrapper has no budget check; quota is only observable by a probe
- `mcp-github-server`: not started: wrapper mcp-github-server contains `aq-event` (network or event-log side effect at start)
- `mcp-playwright-sandboxed`: not started: wrapper mcp-playwright-sandboxed contains `npx` (network or event-log side effect at start)

Notes:

- Probes call the CLIs and the llama.cpp HTTP API directly, not the delegate-to-* wrappers, so they add no registry rows.
- Gemini quota is per model: the CLI default and the Flash model named in config/model-coordinator.json are probed separately.
- Auth is checked by file existence and age only; a present file does not prove the token is still valid (that is what --probe shows).
- Registry `success` means status `done`; the wrappers do not record a failure reason, so the reason is the last error-like line of the failed task's log.
- MCP drift compares the repo `.mcp.json` against the merged user+repo config of each agent; claude.ai cloud connectors are not file-configured and are out of scope.
- A server whose launcher may have side effects at start is reported unknown and not started.
- This run's probe spend (measured where the CLI reports it): codex 22139 tokens, local 21 tokens; Claude (haiku) and both Gemini probes are unmeasured (Claude's JSON output was an event array the first version of the parser did not read; fixed afterwards in `claude_tokens`, covered by the test; Gemini's CLI prints no usage in text mode). Each probe sent the 6-word prompt "Reply with the single word OK." from an empty temp directory.
- Gemini probes, default and `gemini-3.8-flash`, both answered at the time of the run: the 2026-11-06 default-model 429 was not reproducible. Flash took 44.3 s against 12.7 s for the default, so a 60 s hard timeout leaves little margin on Flash.
- `mcp-rea-sandboxed` fails because the wrapper runs `rea` inside bwrap and no `rea` executable exists on its PATH (`bwrap: execvp rea: No such file or directory`); the config and wrapper exist, the REA binary does not.
- Retired-lane hits: 5 are comments or error-text matches in wrappers/JSON `_comment` (low), the `.agents/hooks.json` hit is a hook script file name, and `config/lane-eligibility-registry.json` and `config/remote-lane-egress.json` still carry live `antigravity` lane entries. The registry shows 10 antigravity dispatch rows in 30 days, newest 2026-11-02 (before the 2026-11-05 retirement).
- `NO_RECENT_SUCCESS` for claude is expected-by-design signal, not a fault: Claude work here runs through the Agent tool, and `delegate-to-claude` has had no successful row for 11 days.
- Equivalent mutant noted in the test: disabling the `group_alive` check alone is not detected because the env-marker scan covers the same processes; killing the group and the marker scan are each guarded by their own mutation.

## Rollback Plan
Delete this report and the sweep script; nothing else was changed.
