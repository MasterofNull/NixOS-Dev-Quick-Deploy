# Harness Grounding Supplement — Qwen3-35B

This file is injected into every direct/agent delegation as a system message supplement.
It encodes harness-specific facts the model cannot derive from general training.
Keep entries concise — token cost per delegation is real.

## Commit Format (mandatory)

Pattern: `type(scope): short description`
Example: `fix(dispatch): set frequency_penalty=0.0 to prevent JSON truncation`
Types: feat|fix|docs|refactor|chore|test|ci|perf|style
Trailer: `Co-Authored-By: claude-sonnet-4-6 <noreply@anthropic.com>`
CRITICAL: `(scope)` is NOT optional. `fix: description` is wrong. Always include it.

## Tool Result Messages

Tool result messages MUST use `role: "tool"`. Using `role: "function"` causes the message to
be silently dropped by the Qwen3 chat template — the model never sees the result and
hallucinates on all subsequent turns. Always: `{"role": "tool", "tool_call_id": "...", "content": "..."}`.

## AppArmor Rules

- SQLite databases: `rwk` (read+write+lock). `c` is INVALID — `rwkc` fails `apparmor_parser`.
- File rules do NOT cover `mkdir()`. Directory creation needs a separate explicit rule.
- `NoNewPrivileges=true` in systemd blocks `Ux`/`Px` transitions → use `ix` only.
- After profile changes: check `journalctl -u apparmor.service` for syntax errors.
- Nix store paths in AppArmor: use `/nix/store/**/rest/of/path` glob, NOT the full hash path.

## Frequency Penalty

`frequency_penalty != 0.0` applies cumulative logit penalties. In dense JSON where `"`
appears 300+ times, the penalty reaches 15.0 → `"` becomes unprintable → early EOS
at ~line 59-61. ALWAYS use `frequency_penalty=0.0` for structured/code output.
Loop protection: use `repeat_penalty=1.08` + `repeat_last_n=64` (sliding window) instead.

## Ports and Service URLs

ALL service ports come from `nix/modules/core/options.nix` — never hardcode.
Current defaults: llama.cpp=8080, embed=8081, AIDB=8002, coordinator=8003,
switchboard=8085, cli-bridge=8089, dashboard=8889.
Python reads from env vars; shell scripts use `${PORT:-default}`.

## NixOS Constraints

- GPU layers ceiling: `--n-gpu-layers 12` (Renoir APU, 4 GB shared VRAM). Never suggest >12.
- `enable_thinking` must be in `chat_template_kwargs`, NOT top-level — top-level is silently ignored.
- `sops.secrets.*` entries MUST be immediately followed by `sops <file>` to add the matching key.
  Mismatch = `setupSecrets failed (1)` at boot = `/run/secrets/` absent = full stack down.
- Secrets/API keys NEVER go in tracked Nix files. Only `deploy-options.local.nix` is gitignored.

## AIDB Collections (real names — NOT stale training data)

Valid collections: `error-solutions`, `best-practices`, `skills-patterns`, `codebase-context`,
`agent-interactions`, `training-data`, `task-history`, `model-evaluations`,
`harness-patterns`, `system-telemetry`, `performance-metrics`, `code-patterns`,
`nixos-patterns`, `agent-memory`.
For bug patterns and fixes: use `error-solutions`. NOT `solved_issues` (stale, does not exist).

## Python Async Pattern

File I/O inside `async def` aiohttp/FastAPI handlers MUST be non-blocking:
- `aiofiles.open(path)` for async file reads
- `asyncio.to_thread(sync_fn, ...)` for wrapping sync I/O
- NEVER `open(path).read()` directly inside `async def` — blocks the event loop.
