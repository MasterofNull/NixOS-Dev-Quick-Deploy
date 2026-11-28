# C1, C2, C4 audit of origin/main (2026-11-27)

All paths on `origin/main` via `git show` / `git grep` unless stated. No tracked file was modified.

## C1: is a remote or paid model lane REQUIRED anywhere in the core path?

Verdict: PARTIAL. Inference, routing and memory run local-only. Two things are not local-only: (1) the trust-critical landing/review gate, (2) the harness narrative and owner workflow assume subscription lanes.

Evidence, runs local-only:
- `config/model-coordinator.json`: `models.llama-cpp-local` has `is_local: true`, endpoint `http://127.0.0.1:8080`, `cost_per_1k_tokens: 0.0`; `routing_policy` has `prefer_local_for_simple: true`, `prefer_free_tier: true`, `default_fast_model: llama-cpp-local`, but `default_reasoning_model: "claude-reasoning"` and `default_coding_model: "qwen-coder"`. The reasoning default is a remote lane, so a local-only install must override it (no schema check ensures this; the schema file is also absent, rev4 A1).
- `tiers` carry anthropic, google, openai and local blocks; the local block is `coding`/`chat` (`tiers.local`). Remote tiers are optional data; nothing else in the file requires a key.
- `nix/modules/roles/ai-stack.nix:503,516`: the Open WebUI / llama-server wiring uses `OPENAI_API_KEYS = "dummy"` (llama-server ignores it), so the local stack does not need a key.
- `nix/modules/core/options.nix:1301-1320`: `mySystem.aiStack.llamaCpp.enable` default `true`, local GGUF path; `vectorDb.enable` default `false` (`:1753`); embedding server local (`embeddingServer`, bge-m3 catalog entry).
- Local lanes in the delegation tools: `scripts/ai/delegate-to-local`; `scripts/ai/aq-gap-import` / `aq-knowledge-import.sh` are local-first (#875).

Evidence, NOT local-only:
- `scripts/ai/aq-land` (the only path to land a PR): review lanes `LANES = gemini, codex, local(+ opus, sonnet)`. `local` is skipped when `self.trust_critical` (paths starting `.github/workflows/review-disposition.yml`, `scripts/governance/`, `.githooks/`, ...: `aq-land:56,407,636-637`: "local: change touches gates/trunk/review authority; needs codex or gemini") and when the diff exceeds `AQ_LAND_LOCAL_MAX_DIFF` (default 30000 bytes, `:638`). Dependency-bump PRs use only `gemini,codex` ("local cannot read release notes", `:17`, `:621`). A local-only install can therefore not land governance changes or large diffs through aq-land. The independent-review requirement (non-author `Reviewed-by`) is by design; with only one model family there is no independent reviewer lane. Rev4 D10 says Qwen input is "advisory" for exactly this reason.
- Remote-lane health is part of the landing path: backlog notes two Codex outages froze every gate landing (commit body of #874).
- Hosted dependency that is not a model API: GitHub (PRs, branch protection, merge queue, required checks) is mandatory for rev4 S2. A fully offline makerspace has no GitHub (C4).
- `nix/home/base.nix` installs/wires Claude, Codex, Gemini, Qwen Code CLIs (`~/.npm-global/bin` comment at `:891`, "codex, qwen, gemini, pi CLI agents"); `config/npm-packages.sh` documents native installers for Claude Code, Gemini CLI, Qwen Code, Codex CLI. These are optional lanes, not boot dependencies (not verified by a local-only boot test: UNVERIFIED).

Rev5 actions:
1. Define the local-only profile: set `default_reasoning_model` to a local key; contract test (`config/model-coordinator.json` schema, rev4 S3) that fails if the local-only profile references any remote key.
2. aq-land needs a declared single-family mode: either a second local model as reviewer with an explicit "reduced-assurance" label, or owner self-review with a recorded waiver. Today the code simply refuses. Owner decision D-R5-1.
3. CI check "no paid-API requirement": fail when a module under the default profile reads `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` without a local fallback, or when a non-optional systemd unit lists a remote endpoint. (`git grep` of those key names under `nix/modules` and `ai-stack/switchboard` found only the two `dummy` values above, so the check can start green.)

## C2: npm / Node dependencies

Command: `git grep -n -I -E 'nodejs|nodePackages|buildNpmPackage|npmDeps|node_modules|package\.json|npm|npx|pnpm|yarn' origin/main -- nix flake.nix flake.lock`, plus `git ls-tree -r` for lock/package files. Verdict: FAIL (many). Each item with purpose:

| Item | Path (origin/main) | Purpose | Required? |
|---|---|---|---|
| `nodejs` in base system packages | `nix/modules/core/base.nix:47`; `nix/data/profile-system-packages.nix:7,96,112,128` (every profile list incl. ai-dev) | general Node runtime on every host | Not needed by core services; needed by npm CLIs and extensions |
| `nodejs` in Home Manager | `nix/home/base.nix:392,535` ("required by AI extension language servers") | VSCodium extensions | Optional (desktop) |
| npm-global agent CLIs | `nix/home/base.nix:101-107,300-304,716,868-869,891`; `config/npm-packages.sh` (`@openai/codex`, `openai` fallbacks; Gemini, Qwen via native installers or npm) | Codex/Gemini/Qwen/pi CLIs, `NPM_CONFIG_PREFIX=~/.npm-global` | Optional lanes |
| `continue-cli` | `nix/pkgs/continue-cli.nix` (prebuilt npm tarball `dist/cn.js`, wrapped with node) | Continue CLI | Optional |
| `pi-agent` | `nix/pkgs/pi-agent.nix` (`buildNpmPackage`, `hash = lib.fakeHash`: never built); nixpkgs now ships `pi-coding-agent` 0.75.4 | pi agent | Optional; retire in favor of nixpkgs |
| `opencode` + `models-dev` | `nix/pkgs/by-name/opencode/package.nix` (bun, nodejs), `nix/lib/overlays/opencode.nix` | opencode CLI | Optional; nixpkgs has `opencode` 1.15.10 |
| llama.cpp web UI npm deps | `nix/lib/overlays/llama-cpp-latest.nix:64-116` (`npmDeps` FOD hash from `nix/pins/llama-cpp.json`, or `npm-config-hook` removed when `LLAMA_BUILD_UI=OFF`) | web UI of the inference server | Build-time only; can be disabled (`LLAMA_BUILD_UI=OFF` path exists) |
| playwright via `npx` | `nix/home/base.nix:1616-1634` (`npx --yes --package @playwright/cli`), MCP `command == "npx"` at `:1956,2155` | browser automation wrappers | Optional; downloads from npm at run time (not offline-safe) |
| dev shells | `flake.nix:585-603,710,827` (`nodejs_22`, bun, typescript, tailwind, comment "install -g lighthouse") | mobile-web/frontend dev shells | Optional dev shells |
| harness SDK | `ai-stack/mcp-servers/hybrid-coordinator/package.json` + `package-lock.json` (`@nixos-ai/harness-sdk`, TS/JS SDK) | client SDK for coordinator | Optional |
| theme extension | `templates/vscode/max-ss.cyberpunk-1.2.14-universal/package.json` + lock | VSCodium theme | Cosmetic |
| MCP seed list | `ai-stack/data/tool-recommendations-seed.yaml` (`npx -y @modelcontextprotocol/server-*`, `npm install ...`) | recommendation data, not executed by default | Data |
| npm supply-chain monitor | `nix/modules/core/options.nix:621-678`, `config/security/npm-threat-intel.json` | monitors npm installs | Exists BECAUSE npm is present |
| skill helper | `.agent/skills/web-artifacts-builder/scripts/init-artifact.sh` (pnpm) | artifact builder skill | Optional |

Rev5 actions: (a) a CI check that fails when a new `buildNpmPackage`, `package.json`, `npx`, or `nodejs` appears outside an allowlist (`config/npm-exceptions.yaml`, dated, each with owner and removal trigger; same shape as the upstream register). (b) Owner decision D-R5-2: the agent CLIs (Codex, Gemini, Qwen Code, Claude Code) are Node/npm programs by upstream choice, so "no Node" and "use those lanes" conflict; C2 can hold for the CORE harness only, with agent CLIs declared out-of-core user-installed tools. UNVERIFIED: whether each of those CLIs is a Node program today (README/`config/npm-packages.sh` implies npm packaging; native installers may bundle a runtime).

## C4: footprint on the default profile vs a modest makerspace machine

Measured sources are limited: static Nix declarations; no live `systemctl`/`free` run (read-only discovery on a shared checkout). Live figures UNVERIFIED.

Hard facts:
- Default for this host: profile `ai-dev` (`nix/modules/profiles/ai-dev.nix`, 206 lines) enables `roles.aiStack`, `roles.cppDev`, `roles.virtualization`, `roles.desktop`, `roles.agenticToolchain`, `mcpServers`, `monitoring` + `commandCenter`, `localhostIsolation`, `switchboard`, `aqDecide` (shadow), `executionCellRunner`, `leaseSigningAuthority`, `c2SchedulerContextIssuer`, `revocationEpochAuthority`, `activation.signing`, `secureboot`, `identityKernel`, `agentMesh`, `affectiveEngine`, `worldModel`, `metaOptimization` (lines 13-188). Host adds `services.aiOncalld` and audit logging (`nix/hosts/hyperd/default.nix:49-55`).
- AI stack minimum RAM: assertion `cfg.hardware.systemRamGb >= 12` (`nix/modules/roles/ai-stack.nix:1010-1011`, "minimum 12 GB RAM required"); a 14B/13B model warns under 16 GB (`:1025-1028`). Hardware tiers `nano|micro|small|medium|large` exist (`:1017`, `options.nix:38`); `mcpTimeoutScale` doubles on nano/micro (`options.nix:1201`).
- Context cap by RAM tier: <=24 GB 8192, <=32 GB 16384, <=48 GB 32768, else 65536 (`ai-stack.nix:223-232`).
- Model catalog includes small models: `qwen3-4b` "~2.5 GB Q4", `gemma4-e4b` (marked `recommended = true`, `ai-stack.nix:534`), `qwen3-8b`, plus embedding `bge-m3`, `bge-small-aqdecide`. The owner's host runs a 22.5 GB Qwen3.6-35B (`CLAUDE.md`, `.agent/INFRASTRUCTURE-CONSTRAINTS.md`: ~27 GB usable RAM, GPU layers <= 12, 1 concurrent request, ~1-5 tok/s). So the model is a per-host choice, not hard-wired.
- Per-service memory ceilings in Nix: dozens of `MemoryMax` entries (128M to 2G) in `nix/modules/roles/ai-stack.nix:2196-2878` and `nix/modules/services/mcp-servers.nix` (1G/768M; "tier-aware MemoryMax ceiling sized to the detected hardware tier", `:55`), oncalld 2G (`oncalld.nix:83`). A rough sum is not computed here: many services; UNVERIFIED total.
- Mandatory vs profile-gated: `minimal` profile (`nix/modules/profiles/minimal.nix`) sets `roles.aiStack.enable = false`, i.e. the harness is OFF; there is no profile that is "AI stack on, small". Postgres, Redis, Qdrant: `vectorDb.enable` default false; Postgres/Redis options exist (`options.nix:1088-1097, 3578-3584`) but their default enablement was not traced: UNVERIFIED. Secure boot, localhostIsolation, activation signing, identity-kernel/lease/epoch services are enabled by the ai-dev profile with `mkDefault`/`mkForce` mixed (several `= true` without `mkDefault`: executionCellRunner, leaseSigningAuthority, c2SchedulerContextIssuer, revocationEpochAuthority, lines 54-71), so a downstream profile cannot easily turn them off.
- Offline tolerance: Nix builds need a binary cache or full local build; model GGUFs are fetched from Hugging Face (`huggingFaceRepo`/`huggingFaceFile`, `sha256`), `playwright` via npx fetches from npm at run time; rev4 S2 needs GitHub. Local-only inference itself works offline once models are present. No offline-install path documented for students: UNVERIFIED.
- Simplicity: 30 `tier0.d` checks, ~150 `config/*.json` data files, 19 modules declaring timers, 31 service modules in `nix/modules/services/`, six loop families (rev4). Not "simple to operate".
- Disk: not measured (no `nix path-info -S`). UNVERIFIED; a 4B Q4 GGUF is about 2.5 GB per catalog `ramEstimate`, the owner model 22.5 GB.

Rev5 actions: (1) define `profile = "lite"` (or a `hardwareTier = nano|micro` bundle): local 4B-8B model + switchboard + coordinator + MemoryBroker only; no desktop/virtualization/secureboot/identity-kernel/world-model/affective/meta-optimization. (2) Measure with `systemd-cgtop`/`nix path-info -Sh` on a 16 GB laptop and record numbers in the architecture summary. (3) State explicitly which rev4 enforcement (merge queue, signed provenance) is "developer-fleet only" and not part of a student install. Owner decision D-R5-6.
