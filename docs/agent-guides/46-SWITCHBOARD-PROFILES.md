# Switchboard Profile Selection Guide

The switchboard (`:8085`) routes requests to local or remote LLMs.
Select the right profile via the `x-ai-profile: <name>` request header
or by targeting the right endpoint in your client config.

## Profile Matrix

| Profile | Provider | Max Input | Default Max Output | Max Msgs | Hints | Use When |
|---------|----------|-----------|------------|----------|-------|----------|
| `default` | auto | unlimited | 768 tok | unlimited | yes | General-purpose; hints injected |
| `continue-local` | local | 4000 tok | 768 tok | 12 | no | Continue.dev inline chat; quick edits |
| `local-agent` | local | 5500 tok | 1500 tok | 16 | **yes** | Agent tasks: PRSI, harness ops, fixes |
| `embedded-assist` | local | 1800 tok | 512 tok | 10 | no | Embedded agent assist; low-token queries |
| `local-tool-calling` | local | 5200 tok | 1500 tok | 20 | no | Built-in tool execution on local host |
| `embedding-local` | local (embed) | 512 tok | 256 tok | 8 | no | Embeddings only — `/v1/embeddings` |
| `remote-default` | remote | 3500 tok | 2048 tok | 16 | no | General remote tasks; remote fallback |
| `remote-free` | remote | 3500 tok | 1200 tok | 16 | no | Low-cost probing; discovery queries |
| `remote-coding` | remote (coder) | 5000 tok | 1800 tok | 20 | no | Implementation, refactoring, code review |
| `remote-reasoning` | remote (large) | 6000 tok | 1800 tok | 20 | no | Architecture, policy, tradeoff analysis |
| `remote-tool-calling` | remote (coder) | 3500 tok | 900 tok | 16 | no | Strict tool-schema execution via remote |
| `remote-gemini` | remote (free) | 3500 tok | 1400 tok | 16 | no | Discovery, planning, synthesis front-door |

Important:
- `Default Max Output` values are switchboard profile defaults, not a universal
  cap for every interactive client.
- User-facing editor clients can request larger reply budgets when the client
  surface is intentionally configured for interactive work.
- Agent-to-agent traffic should be controlled primarily by workflow/session
  `token_limit`, tool-call limits, and blueprint policy.

## Decision Tree

```
Need embeddings?
  └─ embedding-local

Need tool execution?
  ├─ Tools are local built-ins → local-tool-calling
  └─ Tools are remote API calls → remote-tool-calling

Local inference (CPU only, fast, private)?
  ├─ Continue.dev / IDE chat → continue-local
  ├─ Agent tasks (PRSI, harness, fixes) → local-agent  ← HINTS INJECTED
  ├─ Short bounded Q&A       → embedded-assist
  └─ Everything else         → default (hints injected)

Remote inference needed?
  ├─ Code / implementation   → remote-coding
  ├─ Architecture / planning → remote-reasoning
  ├─ Discovery / synthesis   → remote-gemini
  ├─ Low-cost probing        → remote-free
  └─ General                 → remote-default
```

## How to Select a Profile

**HTTP header (any client):**
```
x-ai-profile: remote-coding
```

**curl example:**
```bash
curl -s http://localhost:8085/v1/chat/completions \
  -H "x-ai-profile: remote-coding" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Refactor this function..."}]}'
```

**Continue.dev** — set `apiBase` to `http://localhost:8085/v1` and select the
intended model lane from the generated model list. The profile is chosen by the
`X-AI-Profile` header associated with that model entry.

**qwen CLI:**
```bash
qwen --provider openai --base-url http://localhost:8085/v1 \
  -H "x-ai-profile: local-tool-calling" "..."
```

## local-tool-calling Profile (Local Built-in Tool Execution)

Use `local-tool-calling` when the local model should inspect files, run bounded
health checks, query harness context, or validate a small slice through the
server-side built-in tool registry. `aq-chat --profile local` selects this lane
by default; pass `--no-tools` to `aq-chat` only for raw llama.cpp behavior.

Operational guardrails:
- Keep tool loops bounded (`max_tool_calls` is capped by the caller/profile).
- Live smoke tests must set explicit curl timeouts; killed clients can leave the
  local lane busy until the server-side request completes.
- If a requested tool is unsupported, surface the exact rejection instead of
  pretending the local model can execute arbitrary commands.

Focused validation:
```bash
SWB_TOOL_CALL_TIMEOUT_SECONDS=120 scripts/testing/test-switchboard-local-tool-calling.sh
```

## local-agent Profile (Agent Tasks on Local Model)

Use `local-agent` when you want the local model to perform real agent work — PRSI triage,
harness diagnostics, system fixes, or multi-step operations — rather than quick IDE chat.

**What it provides that `continue-local` does not:**
- `injectHints = true` — ranked workflow hints from hybrid-coordinator are prepended to every turn
- 5500-token input budget with 16 messages — room for context + multi-turn reasoning while staying under local context headroom
- Rich profile card with PRSI queue path, orchestrator commands, all service ports, harness CLIs

**Select in Continue.dev:** switch to the **"Local Agent (Harness-Aware)"** model in the IDE model
picker before sending any harness/PRSI/diagnostic request.

**HTTP header:**
```
x-ai-profile: local-agent
```

**Key card content injected:**
```
PRSI queue: /var/lib/nixos-ai-stack/prsi/action-queue.json
PRSI cmds: python3 scripts/automation/prsi-orchestrator.py [sync|list|verify|approve|execute]
Health: aq-qa 0 | aq-report | journalctl -u ai-*.service -n 30
Ports: llama:8080 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dashboard:8889
```

> Note: the deployed Nix catalog, YAML catalog, and Python fallback should stay aligned.
> Run `python3 scripts/testing/test-switchboard-profile-policy.py` and
> `python3 scripts/testing/test-switchboard-profile-catalog-contract.py` after profile edits.

## Budget & Fallback

- `SWB_REMOTE_DAILY_TOKEN_CAP` — hard daily remote token cap (0 = unlimited).
- When cap is hit, `remote-*` profiles fall back to local unless `forceProvider=remote`.
- Local profiles never fall back to remote.
- For workflow runs and delegated sub-agents, treat switchboard profile budgets
  as defaults only. The authoritative internal-traffic budget should come from
  workflow/session policy such as `token_limit`.

## Compact Guidance Contract (`[compact-guidance]`)

The `[compact-guidance]` system message is injected by the switchboard to instruct the model
to produce concise, token-efficient responses suited for agent-to-agent traffic.

**This contract applies ONLY to:**
- `continue-local` — IDE inline chat; brief completions expected
- `embedded-assist` — compact Q&A; low-token bounded queries

**This contract does NOT apply to:**
- `local-agent` — agent tasks require full reasoning depth; compact guidance would degrade quality
- Any `remote-*` profile — remote models are not token-constrained at the switchboard level
- `default` — general-purpose profile; not subject to compact guidance override

If you observe unexpectedly terse responses on `local-agent`, verify you are not inadvertently
sending `x-ai-profile: continue-local` or `embedded-assist` headers.

## Loop Detection (added 2026-04-20)

The switchboard detects degenerate self-correction loops in local model output:
- Scans last `SWB_LOOP_DETECT_WINDOW` (default 3) assistant turns
- Injects `[loop-guard]` system message when similarity ≥ `SWB_LOOP_DETECT_THRESHOLD` (0.72)
- On the **2nd+ consecutive trigger** for the same conversation, returns HTTP 503 `{"error":"loop_detected"}`
- Events logged to `/var/log/nixos-ai-stack/loop-events.jsonl`
