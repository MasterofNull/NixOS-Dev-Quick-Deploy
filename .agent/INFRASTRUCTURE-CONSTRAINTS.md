# INFRASTRUCTURE-CONSTRAINTS.md
# Shared across ALL agents (Claude, Gemini, Codex, Local/Qwen3)
# SSOT: this file. Port SSOT: nix/modules/core/options.nix (never hardcode ports in code).

**When to use:** Load before any Nix/system change, service config, model config, or API work.
**Related:** `.agent/PROMOTED-BUG-PATTERNS.md` for runtime failure patterns.

---

## Hardware (AMD Ryzen 7 PRO 5850U — Renoir APU, ThinkPad P14s Gen 2a)

| Resource | Hard Limit | Notes |
|----------|-----------|-------|
| Usable RAM | ~27 GB | 4 GB reserved as shared VRAM |
| GPU layers | **12 max** | 4 GB VRAM ceiling — `--n-gpu-layers 12` |
| KV cache budget | 1.0 GB | q8_0 requires `--flash-attn on` (bare flag eats next arg) |
| UMBM total | 22.5 GB model / 1.0 GB KV / 3.0 GB OS | Never exceed without explicit math |
| Concurrent requests | 1 (thermal L1) | MLFQ scheduler enforces |
| Max quant | Q4_K_XL | T0/T1 quants will not fit in RAM |
| Inference speed | ~1 tok/s floor | 300s+ timeout for all local LLM calls |

**GPU:** AMD Radeon iGPU (RDNA1/Renoir), Vulkan only — NO ROCm (blocked class).
**llama.cpp flags:** `--flash-attn on --cache-type-k q8_0 --cache-type-v q8_0` (Phase 66.1). Bare `--flash-attn` eats next arg.

### Thermal Gates (automatic enforcement, be aware)

| Tier | Temp | Effect |
|------|------|--------|
| `optimal` | ≤70°C | Full operation |
| `warm` | ≤85°C | Monitor; keep tasks short |
| `critical` | ≥85°C | CLM compaction off; MLFQ concurrency=1; defer heavy jobs |
| `shutdown` | ≥95°C | All inference suspended; notify orchestrator |

**Hard rules (always, any model):**
- Never suggest `n_gpu_layers` > 12 in any config or code
- Never add model quants larger than Q4_K_XL
- Never set context > 8192 without explicit KV budget math
- Service baseline ~4 GB — account for it in memory sizing

---

## Service Port Map (SSOT: `nix/modules/core/options.nix`)

| Service | Port | Auth |
|---------|------|------|
| llama.cpp | 8080 | none |
| llama-embed | 8081 | none |
| AIDB | 8002 | X-API-Key header |
| hybrid-coordinator | 8003 | `/run/secrets/hybrid_coordinator_api_key` |
| ralph-wiggum | 8004 | aidb_api_key (shared) |
| switchboard | 8085 | none |
| dashboard | 8889 | none |
| Grafana | 3000 | none |
| Open WebUI | 3001 | none |

**Auth notes:**
- API key field: `cat /run/secrets/hybrid_coordinator_api_key` (not `API_KEY` or `HYBRID_API_KEY`)
- ralph-wiggum TaskRequest field: `prompt` (not `task`)
- `/run/secrets/aidb_api_key` has leading newlines — strip: `${KEY//[$'\t\r\n ']/}`
- `/api/traces` is loopback-exempt (no API key needed from 127.0.0.1)
- AIDB vector search: `POST /vector/search` (returns `distance`, not `score`)

**NEVER hardcode ports in Python or shell.** Python reads from env vars; shell uses `${PORT:-default}`.

---

## Delegation / Remote Backend

| Path | Current Status |
|------|---------------|
| `delegate-to-antigravity` | **Active** — routes through switchboard HTTP POST (0ccb644f). x-ai-profile header selects profile. |
| Current backend | `remote-free` → `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter. Works in normal use; burst testing → 429 rate limit → circuit breaker trip. |
| `delegate-to-local` | Active — `--mode agent` for tool-using tasks; `--mode direct` for reasoning/analysis only (model cannot execute shell). |
| `delegate-to-gemini` (npm) | **RETIRED** (2026-06-20). |
| gemini-cli oauth-personal | onboardUser 429 persistent (Google backend structural issue). Wait or add OpenRouter credits. |
| gemini-cli path | BLOCKED — not the delegation path. For delegate-to-antigravity only. |

**delegate-to-antigravity valid flags:** `--prompt`, `--role`, `--mode`, `--check <id>`, `--list`, `--status <id>`, `--wait`, `--loop`.

---

## Current Local Model Config (update on model swap)

**Model:** Qwen3-35B (unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_XL)
**Capability:** PROMOTED to primary dev agent (2026-06-22). Benchmark: 82%/85% on 2 consecutive runs (tool_use 92%, coherence 100%).
**Re-bench on model swap:** `bench-local-agent --no-attention` (~8 min)

**Critical config:**
- `enable_thinking: false` MUST be in `chat_template_kwargs`, NOT top-level. Top-level is silently ignored — thinking tokens fill all output, returning empty content.
- Speculative decoding: `--spec-type draft-mtp --spec-draft-n-max 2`
- Context window: 4096 (8192 max with KV budget math)

**Agent executor token budget (Phase 159):**
- tool_call_count == 0: 512 tokens (tool call detection phase)
- tool_call_count > 0: 1200 tokens (synthesis phase)
- Hard ceiling: `_LOCAL_MAX_TOKENS_HARD_CEILING=180` (180s budget headroom at 1 tok/s)

---

## NixOS Architecture Rules

1. **NixOS-first, flake-based** — no bare `pip install`, no manual `systemctl`
2. **NEVER hardcode ports/URLs** — source of truth: `nix/modules/core/options.nix`
3. **Python reads URLs from env vars**; shell scripts use `${PORT:-default}`
4. **Feature flags are profile-driven:** `nix/modules/profiles/ai-dev.nix`
5. **`deploy-options.local.nix` is gitignored** — secrets wiring only, no eval-time policy
6. **Flake target:** `.#hyperd-ai-dev` (`.#hyperd` does NOT exist)
7. **Rebuild commands:**
   ```bash
   sudo nixos-rebuild switch --flake .#hyperd-ai-dev   # system changes
   home-manager switch --flake .#hyperd                # user/home changes only
   ```
8. **Most Python services run from Nix store** — `systemctl restart` doesn't pick up new code. Exception: dashboard backend (WorkingDirectory=repo/dashboard/backend). Coordinator/llama-cpp: require nixos-rebuild.

### NixOS Error Patterns

| Error | Root Cause | Fix |
|-------|-----------|-----|
| Infinite recursion in `nixpkgs.overlays` | `pkgs.stdenv.hostPlatform.*` inside overlay | Use `config.nixpkgs.hostPlatform.*` |
| `DynamicUser` can't read `/home/<user>` | Ephemeral UID, 0700 dir | Use `User = svcUser; Group = svcGroup;` |
| systemd `Environment=` splits on spaces | Unquoted tokens | Escape: `"KEY=\"val1 val2\""` |
| Port conflict OWU/Grafana on 3000 | Grafana default | `ports.openWebui = 3001` in options.nix |
| llama-cpp crash on startup | KV quant needs flash-attn | `--flash-attn on` before cache-type flags |

### SOPS / Secrets Pattern (SECURITY HARD)

Never add secrets/API keys to tracked Nix files (options, modules, home.nix, hosts/*/home.nix etc.) — they go into the Nix store and the public repo.
Always use **SOPS → `/run/secrets/`**. Only `nix/hosts/*/deploy-options.local.nix` is gitignored.

**Adding a new secret (mandatory sequence):**
1. Add entry to `secrets.nix`
2. Run `sops <secrets-file>` immediately to add the matching key to the SOPS manifest
3. Reference via `/run/secrets/<name>` in service config

Manifest/SOPS file mismatch = `setupSecrets failed (1)` = `/run/secrets/` absent = full AI stack cascade.

---

## Key File Locations

| File | Purpose |
|------|---------|
| `nix/modules/core/options.nix` | Port/URL SSOT + all stack options |
| `nix/modules/roles/ai-stack.nix` | Main AI stack NixOS module |
| `nix/modules/services/mcp-servers.nix` | MCP server service declarations |
| `nix/hosts/hyperd/facts.nix` | Per-host overrides (extraArgs, model paths) |
| `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` | Coordinator entry point |
| `scripts/governance/tier0-validation-gate.sh` | Pre-commit gate (17 checks) |
| `scripts/ai/aq-qa` | Health checker |
| `config/intent-routing-map.json` | Intent routing (hot-reload via POST /control/intent/reload) |

---

## API Corrections (coordinator :8003)

- AIDB ingest: `POST /documents` — fields: content, project, relative_path, title
- Hybrid query: `POST /query` — fields: query, mode, prefer_local, limit (no `force_remote`)
- `cache_hit` in /query response is inside `capability_discovery` sub-object, NOT top-level
- Missing query → HTTP 400 (aiohttp — not 422)
- AIDB secrets scanner blocks docs with `/run/secrets/` paths (expected)
- `/world/forecast` is GET-only (405 on POST)
- AIDB vector search: `POST /vector/search` (returns `distance`, not `score`)
- Qdrant collections: `curl http://127.0.0.1:6333/collections` to verify names before assuming search works. Use `error-solutions` not `solved_issues`.

---

*Last updated: 2026-06-26 | Maintained by all agents*
