# AI Agent Surface Matrix
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-13 (validated)

Purpose:
- keep agent CLI, IDE, harness, and remote-provider surfaces explicit
- distinguish declarative delivery from external-but-integrated and scaffold-only states
- make future packaging and harness work measurable instead of ad hoc

## Current State

| Surface | Delivery Mode | Current State | Harness Integration | Validation Target |
| --- | --- | --- | --- | --- |
| Continue CLI (`cn`) | Declarative Nix package | Active | switchboard / OpenAI-compatible proxy, hybrid-coordinator, Continue IDE extension | `nix-build nix/pkgs/continue-cli.nix`, `cn --help` |
| Continue IDE extension | Declarative VSIX wiring | Active | VSCodium settings, switchboard base URL, MCP config path | Home Manager switch, VSCodium settings audit |
| Codex VS Code extension | Declarative VSIX wiring | Active | switchboard base URL, shared env, local harness paths | Home Manager switch, extension presence |
| Codex CLI (`codex`) | npm-global install | Installed at `~/.npm-global/bin/codex`, needs PATH wiring | switchboard/OpenAI-compatible path, VSCodium executable wiring | `~/.npm-global/bin/codex --help` |
| Claude Code extension | Declarative extension wiring | Active | local harness env injection, executable path wiring | Home Manager switch, extension presence |
| Claude CLI (`claude`) | Native upstream install on PATH | Integrated, host help smoke green, not yet declaratively packaged in-repo | VSCodium executable wiring, local harness env injection | `claude --help` |
| Gemini Code Assist / companion | Declarative VSIX wiring | Active | VSCodium extension layer, local env wiring | Home Manager switch, extension presence |
| Gemini CLI (`gemini`) | npm-global install | Installed at `~/.npm-global/bin/gemini`, needs PATH wiring | switchboard/OpenAI-compatible path via shared shell env | `~/.npm-global/bin/gemini --help` |
| Qwen IDE companion | Declarative VSIX wiring | Active | VSCodium extension layer, `.qwen/` session rules | Home Manager switch, extension presence |
| Qwen CLI (`qwen`) | npm-global install | Installed at `~/.npm-global/bin/qwen`, needs PATH wiring | local shell path, shared harness workflow contracts | `~/.npm-global/bin/qwen --help` |
| pi agent (`pi`) | Scaffolded package + shell alias fallback | Partially integrated, host help smoke green | switchboard/OpenAI-compatible alias path | declarative package build, `pi --help` |
| Aider | Declarative package via nixpkgs when available | Active | host home package, local model defaults, aider wrapper service | `aider --help` or package presence |
| OpenRouter remote profiles | Declarative Nix config + SOPS secret | Active | switchboard routing profiles, hybrid-coordinator remote fallback | deploy verification, `/query`, `/workflow/plan` |
| Hybrid-coordinator local harness | Declarative system service | Active | workflow plan, hints, query, qa, learning/export | `aq-qa 0`, deploy capability verification |

## Required Next Steps

1. Keep all declarative agent surfaces green under real build validation, not parse-only checks.
2. Move CLI surfaces from “external binary on PATH” to “declarative package” where upstream distribution allows clean packaging.
3. Keep unsupported installer-only surfaces explicitly marked as external, with local harness wiring and smoke validation still present.
4. Prevent partially integrated surfaces from being treated as complete until they have:
   - declarative or explicit external classification
   - harness wiring
   - validation commands
   - deploy/runtime reporting

## Priority Order

1. Continue CLI and Continue/editor runtime
2. Codex/Qwen/Gemini CLI declarative packaging or explicit external classification
3. Claude native/external classification with stronger validation
4. pi agent declarative packaging or scaffold downgrade until hashes/runtime are fixed
5. OpenRouter multi-agent/tool-calling profile validation through the local harness
