# Switchboard Profile Selection Guide

The switchboard (`:8085`) routes requests to local or remote LLMs.
Select the right profile via the `x-ai-profile: <name>` request header
or by targeting the right endpoint in your client config.

## Profile Matrix

| Profile | Provider | Max Input | Max Output | Max Msgs | Hints | Use When |
|---------|----------|-----------|------------|----------|-------|----------|
| `default` | auto | unlimited | 768 tok | unlimited | yes | General-purpose; hints injected |
| `continue-local` | local | 1200 tok | 768 tok | 8 | no | Continue.dev inline chat; quick edits |
| `local-agent` | local | 3500 tok | 1024 tok | 16 | **yes** | Agent tasks: PRSI, harness ops, fixes |
| `embedded-assist` | local | 1800 tok | 512 tok | 10 | no | Embedded agent assist; low-token queries |
| `local-tool-calling` | local | 2400 tok | 768 tok | 12 | no | Built-in tool execution on local host |
| `embedding-local` | local (embed) | 512 tok | 256 tok | 8 | no | Embeddings only — `/v1/embeddings` |
| `remote-default` | remote | 3500 tok | 1024 tok | 16 | no | General remote tasks; remote fallback |
| `remote-free` | remote | 3500 tok | 1200 tok | 16 | no | Low-cost probing; discovery queries |
| `remote-coding` | remote (coder) | 5000 tok | 1800 tok | 20 | no | Implementation, refactoring, code review |
| `remote-reasoning` | remote (large) | 6000 tok | 1800 tok | 20 | no | Architecture, policy, tradeoff analysis |
| `remote-tool-calling` | remote (coder) | 3500 tok | 900 tok | 16 | no | Strict tool-schema execution via remote |
| `remote-gemini` | remote (free) | 3500 tok | 1400 tok | 16 | no | Discovery, planning, synthesis front-door |

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

**Continue.dev** — set `apiBase` to `http://localhost:8085/v1` and the profile
is selected automatically from the `continue-local` profile card injected at
startup.

**qwen CLI:**
```bash
qwen --provider openai --base-url http://localhost:8085/v1 \
  -H "x-ai-profile: local-tool-calling" "..."
```

## local-agent Profile (Agent Tasks on Local Model)

Use `local-agent` when you want the local model to perform real agent work — PRSI triage,
harness diagnostics, system fixes, or multi-step operations — rather than quick IDE chat.

**What it provides that `continue-local` does not:**
- `injectHints = true` — ranked workflow hints from hybrid-coordinator are prepended to every turn
- 3× higher token budget (3500 input, 16 messages) — room for context + multi-turn reasoning
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
Ports: llama:8080 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dashboard:8006
```

> Note: until the next `nixos-rebuild switch`, `local-agent` falls back to the `default`
> profile (which also has `injectHints = true` and the PRSI queue path). Functional
> from the first Continue.dev reload — no rebuild required for basic operation.

## Budget & Fallback

- `SWB_REMOTE_DAILY_TOKEN_CAP` — hard daily remote token cap (0 = unlimited).
- When cap is hit, `remote-*` profiles fall back to local unless `forceProvider=remote`.
- Local profiles never fall back to remote.

## Loop Detection (added 2026-04-20)

The switchboard detects degenerate self-correction loops in local model output:
- Scans last `SWB_LOOP_DETECT_WINDOW` (default 3) assistant turns
- Injects `[loop-guard]` system message when similarity ≥ `SWB_LOOP_DETECT_THRESHOLD` (0.72)
- Events logged to `/var/log/nixos-ai-stack/loop-events.jsonl`
