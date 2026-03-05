# Claude Code — Project Intelligence for NixOS-Dev-Quick-Deploy

This file is read automatically at session start. It encodes hard-won project
knowledge, efficiency rules, and behavioral standards. Follow them strictly to
minimise remote token consumption while maintaining quality.

---

## 1. Token Efficiency — Non-Negotiable Rules

### Read minimally
- **Grep first, read second.** Never open a full file to find something.
  Use `Grep` with `-n` and `-C 3` to get exact line numbers + context, then
  `Read` with `offset`+`limit` to fetch only those lines.
- **Trust your edits.** After an `Edit` or `Write` call succeeds, do NOT
  re-read the file to confirm. The tool guarantees the change was applied.
- **One verification pass.** Run a single `bash` check at the end of a task,
  not an incremental check after every individual edit.

### Batch everything
- Fire all independent tool calls in a single message (parallel).
- Chain dependent calls with `&&` in one Bash invocation.
- Never use separate Bash calls for things like `git status && git diff` —
  combine them.

### Document surgically
- Update only the section of a roadmap/issue file that changed. Do not
  rewrite surrounding context. Use a targeted `Edit` with the smallest
  possible `old_string` that uniquely identifies the location.
- Do not add explanatory prose to documents that already have it.

### Skip noisy confirmation
- Do not echo "OK" messages or print intermediate results unless the user
  explicitly asked for them.
- Do not use `echo` or `printf` in scripts just to confirm state that can
  be inferred from a zero exit code.

---

## 2. Project Layout (fast reference — do not re-discover)

```
nixos-quick-deploy.sh       Main orchestrator script
lib/
  tools.sh                  AI CLI native installers (Claude, Gemini, Qwen, Codex)
  config.sh                 All config generation logic (3700+ lines)
config/
  variables.sh              User-facing knobs (not committed)
  npm-packages.sh           NPM fallback packages (native installers preferred)
templates/
  configuration.nix         System NixOS module (flat form)
  flake.nix                 Flake template with placeholders
  nixos-improvements/       Imported modules (all use flat form)
    optimizations.nix       Kernel/I-O/memory tuning
    mobile-workstation.nix  ThinkPad-specific power/thermal
    networking.nix          Network stack hardening
    security.nix            Kernel hardening / audit
SYSTEM-UPGRADE-ROADMAP.md  Primary issue tracker (NIX-ISSUE-NNN)
KNOWN_ISSUES_TROUBLESHOOTING.md  Resolved issues with recovery steps
```

---

## 3. NixOS Module System — Rules Learned the Hard Way

### Ownership rule
Each option must have **exactly one owner module**. If two modules set the
same option at the same `lib.mkDefault` priority with different values, NixOS
aborts with "conflicting definition values". Resolve by removing the setting
from all but one module.

| Priority | Operator | Numeric | Use when |
|---|---|---|---|
| Lowest | `lib.mkDefault` | 1000 | "I suggest this, others can override" |
| Normal | (bare value) | 100 | "This is my module's normal setting" |
| Highest | `lib.mkForce` | 50 | "Override everything — no exceptions" |

### Never use `//` for conditional options
Nix `//` is a **shallow merge** — it replaces entire top-level keys. Use
`lib.mkIf condition value` inline inside the module's `{ }` block instead.
The NixOS module system deep-merges `lib.mkIf`-wrapped declarations safely.

```nix
# WRONG — silently drops services.udev.extraRules:
} // lib.optionalAttrs someFlag { services.someOption = true; }

# RIGHT — deep-merged by the module system:
services.someOption = lib.mkIf someFlag true;
```

### Version guards
Use `lib.versionAtLeast lib.version "X.Y"` to guard options that only exist
in newer nixpkgs. Do **not** access `options.*` inside a module — it causes
infinite recursion.

---

## 4. Hardware Context (ThinkPad P14s Gen 2a — AMD Ryzen)

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

## 5. Recurring Errors — Quick Reference

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

## 6. Workflow Standards

### Before touching any file
1. `Grep` for the exact string — get line number.
2. `Read` only the relevant range (offset + limit).
3. Make the targeted `Edit`.
4. Move on — do not re-read.

### When adding a new issue
1. Add `NIX-ISSUE-NNN` entry in the **Agent Review Findings** section of
   `SYSTEM-UPGRADE-ROADMAP.md` (one line, marked `- [x]` if resolved).
2. Add a subsection to the relevant Phase at the bottom of the roadmap.
3. Add a numbered entry to `KNOWN_ISSUES_TROUBLESHOOTING.md` with status,
   symptom, root cause, fix, and tracking reference.
4. Do **not** rewrite the surrounding roadmap prose.

### Placeholder completeness check
Every `@PLACEHOLDER@` token in `templates/configuration.nix` must have a
corresponding `replace_placeholder` call in `lib/config.sh`. Verify with:
```bash
grep -oh '@[A-Z_]*@' templates/configuration.nix | sort -u | while read p; do
  grep -q "replace_placeholder.*$p" lib/config.sh || echo "MISSING: $p"
done
```

### Syntax check
```bash
bash -n lib/config.sh
```
Run once after all changes to a session, not after every individual edit.

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

## 7. Local AI Stack Goal

This project is a stepping stone to a self-hosted AI stack running on this
ThinkPad P14s Gen 2a. When operational, it will replace remote API calls for
routine tasks, making the workflow token-independent for everyday engineering
work. Decisions made in this codebase should optimise for:

- **Reproducibility** — NixOS declarative config must produce the same system
  from a fresh install with no manual steps.
- **Hardware fit** — configurations must match the AMD Ryzen ThinkPad profile,
  not generic Intel assumptions.
- **Forward compatibility** — use version guards rather than hard-coding to
  a single nixpkgs revision.
- **Minimal surface** — do not enable services, packages, or modules that are
  not actively used. Every enabled service is a potential failure point.

---

## 8. Agent Coordination Model — DEFAULT BEHAVIOR (NON-NEGOTIABLE)

Claude's role in this project is **Planner → Coordinator → Delegator → Auditor**.
Claude must NOT consume its own context doing bulk coding work. Token budget is a
shared finite resource; protect it.

### Role definitions

| Role | Claude does | CLI agent does |
|------|-------------|----------------|
| **Planner** | Read plan, identify task scope, break into sub-tasks | — |
| **Coordinator** | Sequence tasks, manage dependencies, track phase gates | — |
| **Delegator** | Write precise prompts for Codex/Qwen, pass files via `@` syntax | Executes the code change |
| **Auditor** | Grep/Read to verify output, run syntax checks, commit | — |

### Hard rules

1. **Codex or Qwen does bulk coding** — any task that modifies >30 lines or
   creates a new file goes to Codex or Qwen via `Bash` tool. Claude writes the
   delegation prompt, not the code.
2. **Gemini is search-only** — free tier, limited quota. Use only for quick web
   lookups (docs, release notes, error messages). Never send full files to Gemini.
3. **Claude writes no bulk code directly** — exception: single-line targeted fixes
   that are faster than writing a delegation prompt.
4. **Verify all delegated output** — after Codex/Qwen finishes, Claude runs
   `Grep`/`Read` spot-checks + `python3 -m py_compile` or `bash -n` before commit.
5. **One delegation prompt per logical sub-task** — do not combine unrelated
   changes into one Codex/Qwen invocation; that makes auditing impossible.

### Binary locations (all in ~/.npm-global/bin — must be in PATH)

```bash
export PATH="$HOME/.npm-global/bin:$PATH"
# versions confirmed: codex 0.104.0, qwen 0.10.5, gemini 0.29.5
```

Always prepend this export to any Bash invocation that calls these tools.

### Delegation template (Codex/Qwen)

```bash
codex "
TASK: <one-sentence description>
FILES: @path/to/file1.py @path/to/file2.py
CONSTRAINT: <any hard rules, port policy, etc.>
CHANGE:
  1. <specific change 1>
  2. <specific change 2>
DO NOT: <list anything that must not be touched>
OUTPUT: confirm each change with a diff-style summary
"
```

### When to use which agent

| Task | Agent |
|------|-------|
| Create new module (<200 lines) | `codex` |
| Multi-file refactor | `qwen` |
| Inline SQL / config extraction | `codex` |
| Security / pattern audit | `codex` |
| Web doc lookup | `gemini -p` |
| Architecture analysis across dirs | `qwen` |
| Targeted single-line fix | Claude directly |
| Test generation | `codex` |

---

## 9. Using Gemini CLI, Qwen CLI, and Codex CLI for Large Codebase Analysis

When analyzing large codebases or multiple files that might exceed context limits, use CLI tools with large context windows. Three primary options are available:

| Tool | Command | Context Strength | Best For |
|------|---------|------------------|----------|
| **Gemini CLI** | `gemini -p` | Small internet searches (free) | Quick web lookups, reference checks |
| **Qwen CLI** | `qwen` | Very Large | Deep code understanding, multi-file analysis, audits |
| **Codex CLI** | `codex` | Large | Pattern detection, security audits, test generation |

### Verification Rule — NON-NEGOTIABLE

**Output from `qwen` and `codex` MUST be verified before implementation.**

These tools can hallucinate file paths, API signatures, or conclusions. Before acting on their output:
1. **Cross-check** every file path and code reference against the actual codebase (`Grep`, `Read`).
2. **Validate** any generated code with `python3 -m py_compile` or `bash -n` before committing.
3. **Do not blindly accept** structural claims (e.g. "X is implemented", "Y does not exist") —
   verify with a targeted `Grep` first.
4. When qwen/codex output is used to *populate data* (e.g. YAML entries, documentation),
   verify each entry is accurate before committing.

### File and Directory Inclusion Syntax

All three tools use the `@` syntax to include files and directories. Paths are relative to where you run the command:

```bash
# Single file
gemini -p "@src/main.py Explain this file's purpose and structure"
qwen "@src/main.py Explain this file's purpose and structure"
codex "@src/main.py Explain this file's purpose and structure"

# Multiple files
gemini -p "@package.json @src/index.js Analyze the dependencies used in the code"
qwen "@package.json @src/index.js Analyze the dependencies used in the code"
codex "@package.json @src/index.js Analyze the dependencies used in the code"

# Entire directory
gemini -p "@src/ Summarize the architecture of this codebase"
qwen "@src/ Summarize the architecture of this codebase"
codex "@src/ Summarize the architecture of this codebase"

# Multiple directories
gemini -p "@src/ @tests/ Analyze test coverage for the source code"
qwen "@src/ @tests/ Analyze test coverage for the source code"
codex "@src/ @tests/ Analyze test coverage for the source code"

# Current directory and subdirectories
gemini -p "@./ Give me an overview of this entire project"
qwen "@./ Give me an overview of this entire project"
codex "@./ Give me an overview of this entire project"

# Or use --all_files flag (Gemini only)
gemini --all_files -p "Analyze the project structure and dependencies"
```

### Implementation Verification Examples

```bash
# Check if a feature is implemented
gemini -p "@src/ @lib/ Has dark mode been implemented? Show relevant files and functions"
qwen "@src/ @lib/ Has dark mode been implemented? Show relevant files and functions"
codex "@src/ @lib/ Has dark mode been implemented? Show relevant files and functions"

# Verify authentication implementation
gemini -p "@src/ @middleware/ Is JWT authentication implemented? List all auth-related endpoints"
qwen "@src/ @middleware/ Is JWT authentication implemented? List all auth-related endpoints"
codex "@src/ @middleware/ Is JWT authentication implemented? List all auth-related endpoints"

# Check for specific patterns
gemini -p "@src/ Are there any React hooks that handle WebSocket connections? List them with file paths"
qwen "@src/ Are there any React hooks that handle WebSocket connections? List them with file paths"
codex "@src/ Are there any React hooks that handle WebSocket connections? List them with file paths"

# Verify error handling
gemini -p "@src/ @api/ Is proper error handling implemented for all API endpoints?"
qwen "@src/ @api/ Is proper error handling implemented for all API endpoints?"
codex "@src/ @api/ Is proper error handling implemented for all API endpoints?"

# Check for rate limiting
gemini -p "@backend/ @middleware/ Is rate limiting implemented? Show the implementation details"
qwen "@backend/ @middleware/ Is rate limiting implemented? Show the implementation details"
codex "@backend/ @middleware/ Is rate limiting implemented? Show the implementation details"

# Verify caching strategy
gemini -p "@src/ @lib/ @services/ Is Redis caching implemented? List all cache-related functions"
qwen "@src/ @lib/ @services/ Is Redis caching implemented? List all cache-related functions"
codex "@src/ @lib/ @services/ Is Redis caching implemented? List all cache-related functions"

# Check for security measures
gemini -p "@src/ @api/ Are SQL injection protections implemented? Show how inputs are sanitized"
qwen "@src/ @api/ Are SQL injection protections implemented? Show how inputs are sanitized"
codex "@src/ @api/ Are SQL injection protections implemented? Show how inputs are sanitized"

# Verify test coverage
gemini -p "@src/payment/ @tests/ Is the payment processing module fully tested? List all test cases"
qwen "@src/payment/ @tests/ Is the payment processing module fully tested? List all test cases"
codex "@src/payment/ @tests/ Is the payment processing module fully tested? List all test cases"
```

### When to Use Each CLI Tool

**Use `gemini -p` when:**
- Analyzing entire codebases or large directories
- Comparing multiple large files
- Need to understand project-wide patterns or architecture
- Working with files totaling more than 100KB
- Maximum context window is required (1M+ tokens)

**Use `qwen` when:**
- Deep code understanding and reasoning is needed
- Multi-file refactoring tasks
- Complex logic analysis across modules
- Code explanation with architectural insights
- When you need nuanced understanding of code intent

**Use `codex` when:**
- Pattern detection across the codebase
- Security audits and vulnerability scanning
- Test generation and coverage analysis
- Code quality assessment
- Finding duplicate code or anti-patterns

### Tool Selection Quick Reference

| Task Type | Primary Tool | Alternative |
|-----------|-------------|-------------|
| Full codebase architecture review | `gemini -p` | `qwen` |
| Security audit | `codex` | `gemini -p` |
| Multi-file refactoring plan | `qwen` | `gemini -p` |
| Test coverage analysis | `codex` | `qwen` |
| Pattern/anti-pattern detection | `codex` | `qwen` |
| Deep code explanation | `qwen` | `gemini -p` |
| Dependency analysis | `gemini -p` | `codex` |
| API endpoint inventory | `codex` | `gemini -p` |

### Important Notes

- Paths in `@` syntax are relative to your current working directory when invoking the CLI
- All CLIs include file contents directly in the context
- No `--yolo` flag needed for read-only analysis
- When checking implementations, be specific about what you're looking for to get accurate results
- For very large codebases, start with `gemini -p` for overview, then use `qwen` or `codex` for deep dives
- Cross-verify critical findings (security, architecture) using multiple tools
