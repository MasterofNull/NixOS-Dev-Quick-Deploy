# Project Context — NixOS-Dev-Quick-Deploy

<!-- Phase 19.4.3 — <!-- sync-agent-instructions: auto-generated section --> -->
<!-- Last synced: 2026-02-27 19:46 UTC from CLAUDE.md -->
<!-- Auto-loaded by Gemini CLI from .gemini/context.md -->

## What This Project Is

A NixOS-first, fully declarative AI development stack on an AMD ThinkPad P14s Gen 2a.
Provides: local LLM inference (llama.cpp/ROCm + Ollama), hybrid query routing,
vector database (AIDB + Qdrant), MCP servers, workflow hints (aq-hints), and
Continue.dev integration.

## Port Policy (NON-NEGOTIABLE)

### Port and service URL policy — NON-NEGOTIABLE
**Never hardcode port numbers or service URLs in any file.**
This project has a single source of truth for all network settings:
- **NixOS side:** `nix/modules/core/options.nix` — all ports defined as typed NixOS options here.
- **Python services:** read URLs exclusively from environment variables injected by the systemd unit (e.g. `LLAMA_CPP_BASE_URL`, `AIDB_URL`, `REDIS_URL`). Fallback default values in `os.getenv("...", "default")` are only acceptable for local development; when `AI_STRICT_ENV=true` all URLs must be present.
- **Shell scripts:** use env var overrides with sensible fallbacks (e.g. `REDIS_PORT="${REDIS_PORT:-6379}"`).
- **NixOS modules:** use option references (e.g. `cfg.ports.llamaCpp`) — never literal integers.

When adding a new service:
1. Add its port option to `options.nix`.
2. Reference that option from `ai-stack.nix` to inject the env var.
3. Have the service read the env var. Do NOT hardcode the value.

---

## Key Service URLs (from config/service-endpoints.sh)

Source this file before any script that needs URLs:
```bash
source config/service-endpoints.sh
curl "$HINTS_URL?q=nixos+conflict"
```

## Hardware

| Component | Detail |
|---|---|
| CPU | AMD Ryzen (AuthenticAMD) — `k10temp` driver |
| Thermal daemon | `thermald` is Intel-only — **disabled on this machine** |
| Fans | ACPI-controlled; `thinkpad-isa-0000` hwmon shows fan1/fan2 |
| GPU | AMD integrated (`amdgpu`) + discrete (`/dev/dri/card1`) |
| NVMe | `nvme0n1` — BFQ scheduler, state `live` |
| Boot | systemd-boot, EFI partition `/dev/nvme0n1p1` (UUID `8D2E-EF0C`) |
| Root | `/dev/nvme0n1p2` (UUID `b386ce56`, ext4) |
| Swap | `/dev/nvme0n1p3` (UUID `dac1f455`) + zram |

### Known-good settings for this machine
- `services.thermald.enable = lib.mkDefault (config.hardware.cpu.intel.updateMicrocode or false)`
  — evaluates `false` on AMD; Intel systems get thermald automatically.
- `boot.loader.systemd-boot.graceful = lib.mkDefault true`
  — prevents dirty-ESP dirty bit from aborting bootloader install.
- `powerManagement.cpuFreqGovernor = lib.mkDefault "schedutil"` — fine for
  AMD; `schedutil` is built into the kernel (not a loadable module).

---

## Recurring Errors

| Error | Root Cause | Fix location |
|---|---|---|
| `services.gnome.gcr-ssh-agent does not exist` | nixos-25.11 doesn't have it | `lib.optionalAttrs (lib.versionAtLeast lib.version "26.05")` guard |
| `conflicting definition values` for `thermald` | Two `lib.mkDefault` owners | Remove from `mobile-workstation.nix`; keep in `configuration.nix` |
| `Failed to find module 'cpufreq_schedutil'` | Built-in governor, not loadable | Do not add to `boot.kernelModules` |
| wireplumber SIGABRT / core dump | libcamera UVC `LOG(Fatal)` | `wireplumber.extraConfig."10-disable-libcamera"` |
| COSMIC portals broken | `xdg-desktop-portal-gnome` requires gnome-shell | Remove from `extraPortals`; use `-cosmic` and `-hyprland` |
| `services.lact.enable = "auto"` | String for boolean option | Use `true` |
| `undefined variable 'perf'` | `perf` not in all nixpkgs | `lib.optionals (pkgs ? perf) [ pkgs.perf ]` |

---

## Using Gemini CLI Here

Gemini is for **web lookups and large-context analysis only** (free tier, limited quota).
Do NOT send full files unless the analysis task is >100KB.

```bash
# Good: doc lookup
gemini -p "NixOS 25.11 xdg-desktop-portal-gnome missing gnome-shell workaround"

# Good: large codebase analysis
gemini -p "@ai-stack/mcp-servers/ Summarize the MCP server architecture"

# Bad: small targeted task (use direct file read instead)
# gemini -p "@scripts/aq-hints show me the first 20 lines"
```
