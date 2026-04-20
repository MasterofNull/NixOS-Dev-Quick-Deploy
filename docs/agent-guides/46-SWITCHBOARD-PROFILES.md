# Switchboard Profile Selection Guide

The switchboard (`:8085`) routes requests to local or remote LLMs.
Select the right profile via the `x-ai-profile: <name>` request header
or by targeting the right endpoint in your client config.

## Profile Matrix

| Profile | Provider | Max Input | Max Output | Max Msgs | Use When |
|---------|----------|-----------|------------|----------|----------|
| `default` | auto | unlimited | 768 tok | unlimited | General-purpose; hints injected |
| `continue-local` | local | 1200 tok | 768 tok | 8 | Continue.dev inline chat; quick edits |
| `embedded-assist` | local | 1800 tok | 512 tok | 10 | Embedded agent assist; low-token queries |
| `local-tool-calling` | local | 2400 tok | 768 tok | 12 | Built-in tool execution on local host |
| `embedding-local` | local (embed) | 512 tok | 256 tok | 8 | Embeddings only — `/v1/embeddings` |
| `remote-default` | remote | 3500 tok | 1024 tok | 16 | General remote tasks; remote fallback |
| `remote-free` | remote | 3500 tok | 1200 tok | 16 | Low-cost probing; discovery queries |
| `remote-coding` | remote (coder) | 5000 tok | 1800 tok | 20 | Implementation, refactoring, code review |
| `remote-reasoning` | remote (large) | 6000 tok | 1800 tok | 20 | Architecture, policy, tradeoff analysis |
| `remote-tool-calling` | remote (coder) | 3500 tok | 900 tok | 16 | Strict tool-schema execution via remote |
| `remote-gemini` | remote (free) | 3500 tok | 1400 tok | 16 | Discovery, planning, synthesis front-door |

## Decision Tree

```
Need embeddings?
  └─ embedding-local

Need tool execution?
  ├─ Tools are local built-ins → local-tool-calling
  └─ Tools are remote API calls → remote-tool-calling

Local inference (CPU only, fast, private)?
  ├─ Continue.dev / IDE chat → continue-local
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

## Budget & Fallback

- `SWB_REMOTE_DAILY_TOKEN_CAP` — hard daily remote token cap (0 = unlimited).
- When cap is hit, `remote-*` profiles fall back to local unless `forceProvider=remote`.
- Local profiles never fall back to remote.

## Loop Detection (added 2026-04-20)

The switchboard detects degenerate self-correction loops in local model output:
- Scans last `SWB_LOOP_DETECT_WINDOW` (default 3) assistant turns
- Injects `[loop-guard]` system message when similarity ≥ `SWB_LOOP_DETECT_THRESHOLD` (0.72)
- Events logged to `/var/log/nixos-ai-stack/loop-events.jsonl`
