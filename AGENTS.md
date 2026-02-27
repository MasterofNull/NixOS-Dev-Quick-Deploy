# AI Agent Onboarding Guide — NixOS-Dev-Quick-Deploy

**Version:** 1.1.0
**Purpose:** Universal agent training for professional software development
**Audience:** AI agents, LLMs, and autonomous coding systems (Claude, Gemini, Codex, Qwen, aider, Continue.dev, Open WebUI, Ollama)

> **Phase 19.4.1** — Project-specific rules prepended from CLAUDE.md. These override
> any generic conventions below when there is a conflict.

---

<!-- sync-agent-instructions: auto-generated section -->
<!-- Last synced: 2026-02-27 09:47 UTC from CLAUDE.md -->

## PROJECT-SPECIFIC RULES — NixOS-Dev-Quick-Deploy (READ FIRST)

### Port and URL Policy (Non-Negotiable)

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

### NixOS Module Rules

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

### Recurring Errors — Quick Fix Reference

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

### Agent Coordination Model

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

<!-- sync-agent-instructions: end -->

## PROJECT-SPECIFIC RULES — NixOS-Dev-Quick-Deploy (READ FIRST)

### Port and URL Policy — NON-NEGOTIABLE

**Never hardcode port numbers or service URLs in any file.**

| Layer | How to reference |
|-------|-----------------|
| NixOS options | `nix/modules/core/options.nix` — add a typed option, reference it as `cfg.mcpServers.hybridPort` |
| Python services | `os.getenv("AIDB_URL")`, `os.getenv("LLAMA_URL")` — read from injected env vars |
| Shell scripts | `PORT="${REDIS_PORT:-6379}"` — env var with fallback |
| NixOS modules | `cfg.ports.llamaCpp` — option reference, never literal integers |

When adding a new service: (1) add port option to `options.nix`, (2) reference from `ai-stack.nix`, (3) service reads env var. Never hardcode.

### NixOS Module Rules

- **One owner per option.** Conflicting `lib.mkDefault` values abort the build. Remove from all but one module.
- **Use `lib.mkIf`, not `//`.** Nix `//` is a shallow merge that silently drops subkeys.
- **Version guards.** `lib.versionAtLeast lib.version "X.Y"` for options that don't exist in all nixpkgs.
- **Hardware-tier aware.** Do not hard-code ThinkPad P14s values; use `mySystem.hardware.tier` options.

### Key File Locations

```
nix/modules/core/options.nix         ALL port options (single source of truth)
nix/modules/roles/ai-stack.nix       Main AI stack NixOS module
nix/modules/services/mcp-servers.nix MCP server systemd units
ai-stack/mcp-servers/
  hybrid-coordinator/                 Route-search, /hints REST API, memory
  aidb/                              AIDB vector DB MCP server
  aider-wrapper/server.py            Async aider integration
ai-stack/prompts/registry.yaml       Prompt template registry
scripts/aq-hints                     Workflow hint CLI (all agents)
scripts/aq-report                    9-section performance digest
config/service-endpoints.sh          Canonical service URL definitions
```

### Workflow Hints — Use aq-hints Before Complex Tasks

All agents should query the hints endpoint before starting complex tasks:
```bash
# CLI (terminal agents, aider)
aq-hints "nixos service conflict" --format=json --agent=codex

# REST (any HTTP-capable agent)
curl "http://127.0.0.1:8003/hints?q=nixos+conflict&agent=remote"

# Continue.dev: type @aq-hints in the chat input
```

### Agent Coordination Model

| Agent | Role |
|-------|------|
| Claude Code | Planner / Coordinator / Delegator / Auditor — NOT bulk coder |
| Codex / Qwen | Bulk coding (>30 lines or new file) |
| Gemini CLI | Web lookups only (free tier) |
| aider-wrapper | Autonomous code modification via API |
| Local LLMs | Inference via llama.cpp (ROCm) or Ollama |

### Recurring Errors — Quick Fix Reference

| Error | Fix |
|-------|-----|
| `conflicting definition values` | Remove duplicate `lib.mkDefault` — keep only one owner |
| `Failed to find module 'cpufreq_schedutil'` | Remove from `boot.kernelModules` (it's built-in) |
| wireplumber SIGABRT | Add `10-disable-libcamera` to wireplumber extraConfig |
| COSMIC portals broken | Remove `xdg-desktop-portal-gnome` from extraPortals |
| `undefined variable 'perf'` | Guard: `lib.optionals (pkgs ? perf) [ pkgs.perf ]` |

---

**Agent Docs Index (canonical links):**
- `AGENTS.md` - Source of truth
- `docs/AGENTS.md` - Mirror for quick reference
- `docs/agent-guides/00-SYSTEM-OVERVIEW.md` - System map
- `docs/agent-guides/01-QUICK-START.md` - Task-ready checklist
- `ai-stack/agents/skills/AGENTS.md` - Skill usage and sync rules

## Specialist Agent Profiles (Migrated from Legacy `.claude/agents`)

These profiles are now part of the canonical onboarding docs and should be invoked by scope, not by legacy file location.

### `nixos-systems-architect`
- Use for NixOS modules, flakes, hardware-aware tuning, secure reproducible builds, deployment architecture, and rebuild/debug failures.
- Prioritize declarative and reproducible Nix patterns (flake pinning, module correctness, rollback-safe changes).
- Always include risk-based review findings, migration notes for deprecated options, and validation steps (`nix flake check`, dry-build, rollback path).

### `senior-ai-stack-dev`
- Use for local AI stack architecture on constrained hardware (desktop/laptop/SBC), model selection/quantization, inference routing, observability, and persistence.
- Prioritize local-first inference, token/cost reduction, bounded memory behavior, and failure-aware service design.
- Require measurable outcomes (latency, memory/VRAM, success rate, token reduction) and explicit fallback behavior.

Policy:
- Canonical location is this file and `docs/AGENTS.md`.
- Do not reintroduce `.claude/agents` copies; keep profile guidance centralized here.

## 🎯 Core Philosophy

**You are not just a tool—you are a professional software engineer.**

This guide trains you to:
- Write clean, maintainable code that humans will work with
- Organize documentation professionally
- Prevent "AI slop" (over-engineering, verbose code, documentation sprawl)
- Collaborate effectively with other agents and humans
- Deliver production-ready work without cleanup cycles

---

## ⚡ QUICK START: Essential Tools & Resources

> **READ THIS FIRST** - Fresh AI agents start here for immediate access to all capabilities.

### 🎯 Source of Truth Locations

**Skills Directory (PRIMARY):** `.agent/skills/`
- **Count:** 25 unified skills
- **Policy:** `.agent/skills/` is canonical; do not create `.claude/skills*` backup trees
- **Usage:** Skills are auto-loaded, reference in prompts: "use the webapp-testing skill"

**MCP Server Configuration:** `~/.mcp/config.json`
- **Symlink:** `~/.config/claude/mcp.json` → `~/.mcp/config.json`
- **Currently Installed:** mcp-nixos (NixOS package search)
- **Registry:** `~/.mcp/registry.json` (server metadata with security audits)

**Knowledge Base (AIDB):** `http://localhost:8002`
- **Project:** NixOS-Dev-Quick-Deploy
- **Query:** `curl 'http://localhost:8002/documents?search=TOPIC&project=NixOS-Dev-Quick-Deploy'`
- **Import:** `curl -X POST http://localhost:8002/documents -H "Content-Type: application/json" -d @data.json`

### 📦 Available Skills (All in .agent/skills/)

**Development:**
- `ai-model-management` - vLLM/Ollama model lifecycle
- `ai-service-management` - AI service orchestration
- `nixos-deployment` - NixOS deployment automation
- `webapp-testing` - Playwright web UI testing
- `mcp-builder` - Create new MCP servers
- `skill-creator` - Create new skills

**Data & Analysis:**
- `aidb-knowledge` - Query AIDB knowledge base
- `xlsx` - Spreadsheet creation/analysis
- `pdf` - PDF manipulation toolkit
- `pptx` - PowerPoint operations

**Design & Artifacts:**
- `frontend-design` - Production-grade web interfaces
- `canvas-design` - Visual art (.png, .pdf)
- `brand-guidelines` - Anthropic brand styling
- `theme-factory` - Theme generation
- `web-artifacts-builder` - Complex React/Tailwind artifacts

**Utilities:**
- `health-monitoring` - System health tracking
- `all-mcp-directory` - Browse MCP server directory
- `mcp-server` - MCP server templates
- `project-import` - Import external projects
- `rag-techniques` - RAG implementation patterns
- `system_bootstrap` - System bootstrapping

**Communication:**
- `internal-comms` - Internal communication templates
- `slack-gif-creator` - Animated GIFs for Slack

**Templates:**
- `template-skill` - Skill boilerplate
- `mcp-database-setup` - MCP database configuration

### 🔌 MCP Servers Database

**Query All MCP Servers:**
```bash
curl 'http://localhost:8002/documents?search=mcp-server&category=tools&project=NixOS-Dev-Quick-Deploy'
```

**Currently Installed:**
1. **mcp-nixos** (⭐⭐⭐⭐⭐ 354 stars) - NixOS package/config search
   - Command: `nix run github:utensils/mcp-nixos`
   - Tools: nixos_search, nixos_info, home_manager_search, darwin_search

**High Priority (Recommended):**
- **postgres-mcp** - PostgreSQL/AIDB integration
- **github-mcp** - Repository management
- **SecureMCP** - MCP security auditing (red team)
- **vulnicheck** - Vulnerability scanning

**See Full Inventory:** `docs/SKILLS-AND-MCP-INVENTORY.md`
**See Security Tools:** `docs/AGENT-AGNOSTIC-TOOLING-PLAN.md`

### 🤖 Local AI Agent Integration

**Offload Parallel Tasks to Local Agents:**

When you have multiple independent tasks, delegate to local AI models:

```bash
# Check available local models
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:8080/v1/models  # vLLM

# Example: Offload research task to local agent
# Use the ai-service-management skill or direct API calls
```

**When to Use Local Agents:**
- Parallel research tasks (multiple GitHub searches)
- Code analysis on multiple files
- Documentation generation
- Data extraction/transformation
- Testing and validation

**Benefits:**
- Reduces your token consumption
- Speeds up execution (parallel processing)
- Cost optimization (use free local models)

**Integration Points:**
- AIDB has query API for knowledge retrieval
- Local models accessible via OpenAI-compatible API
- Skills can be invoked by any agent

### 📚 Essential Documentation Files

**Read These First:**
1. `AGENTS.md` (this file) - Agent onboarding and standards
2. `docs/SKILLS-AND-MCP-INVENTORY.md` - Complete tool inventory
3. `docs/AGENT-AGNOSTIC-TOOLING-PLAN.md` - Agent-agnostic architecture
4. `docs/AVAILABLE_TOOLS.md` - Tool reference guide
5. `README.md` - Project overview
6. `docs/REPOSITORY-SCOPE-CONTRACT.md` - Repository boundaries and ownership
7. `docs/SKILL-BACKUP-POLICY.md` - Skill backup and restore policy
8. `docs/AQD-CLI-USAGE.md` - CLI-first workflow usage
9. `docs/SKILL-MINIMUM-STANDARD.md` - Minimum viable skill standard

**Query AIDB for Any Topic:**
```bash
# Find documentation about MCP servers
curl 'http://localhost:8002/documents?search=mcp&project=NixOS-Dev-Quick-Deploy'

# Find deployment guides
curl 'http://localhost:8002/documents?search=deployment&project=NixOS-Dev-Quick-Deploy'

# Find recent session summaries
curl 'http://localhost:8002/documents?search=session&type=summary&project=NixOS-Dev-Quick-Deploy'
```

### 🔄 Creating Skills and MCP Servers

**Create New Skill:**
```bash
# Use the skill-creator skill
# Reference: "use skill-creator to create a new skill for X"
```

**Create New MCP Server:**
```bash
# Use the mcp-builder skill
# Reference: "use mcp-builder to create an MCP server for X"
```

**Update This File (AGENTS.md):**
- This is the source of truth for agent onboarding
- Keep the "Quick Start" section updated when adding new tools
- Add new skills to the "Available Skills" list
- Update MCP server list when installing new servers

---

## 🧹 Code Quality & Documentation Standards

> **Critical:** This section prevents technical debt and reduces "cleanup cycles" after development.

### Core Principles: CLEAN CODE, MINIMAL WASTE

**The Problem:** "AI slop" - verbose code, unnecessary abstractions, scattered documentation, and over-engineering that creates maintenance burden.

**The Solution:** Be **intentional, minimal, and organized** from the start.

---

## 1. Code Quality Standards

### ✅ Write Code That Humans Will Maintain

**DO:**
- Write clear, self-documenting code with descriptive variable names
- Use standard patterns from the existing codebase
- Keep functions focused and under 50 lines when possible
- Add comments ONLY where logic isn't obvious
- Follow existing code style (check similar files first)

**DON'T:**
- Over-engineer simple tasks with unnecessary abstractions
- Add framework features "just in case" (YAGNI principle)
- Create utility functions for one-time operations
- Add extensive docstrings to obvious functions
- Prematurely optimize without profiling

**Example - GOOD:**
```python
def validate_email(email: str) -> bool:
    """Check if email format is valid."""
    return "@" in email and "." in email.split("@")[1]
```

**Example - BAD (AI Slop):**
```python
class EmailValidationStrategy:
    """
    Advanced email validation strategy implementing the Strategy pattern
    for flexible email validation across multiple contexts.

    Attributes:
        validator_type: The type of validator to use
        config: Configuration object for validation rules
        logger: Logger instance for validation events
    """
    def __init__(self, validator_type: str = "standard", config: dict = None):
        self.validator_type = validator_type
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

    def validate(self, email: str) -> ValidationResult:
        """Validate email with comprehensive error handling."""
        # ... 50 more lines of over-engineering
```

### ✅ Function Documentation Standards

**DO:**
- Add a 1-2 line comment above non-trivial functions explaining intent and side effects
- Document inputs/outputs via clear names; avoid long docstrings in shell scripts
- Use `phase_XX_` prefixes for phase-local helpers to keep call chains readable
- Split functions when they grow beyond ~50 lines

### ✅ Security & Safety First

**DO:**
- Validate all user inputs at system boundaries
- Use parameterized queries for SQL
- Sanitize data before shell commands
- Check file permissions before operations
- Log security-relevant events

**DON'T:**
- Trust internal function parameters (validate at entry points only)
- Add error handling for scenarios that can't happen
- Create overly defensive code that obscures logic

### ✅ Follow Existing Patterns

Before writing new code:
1. **Search for similar functionality** in the codebase
2. **Match the existing style** (indentation, naming, structure)
3. **Reuse existing utilities** instead of creating new ones
4. **Check the database schema** before adding tables/columns

**Find patterns with:**
```bash
# Search for similar functions
grep -r "def function_name" .

# Find API endpoint patterns
grep -r "@app.route\|@router\|@endpoint" .

# Check database models
grep -r "class.*Model\|CREATE TABLE" .
```

---

## 2. Documentation Management

### ✅ File Organization Rules

**Essential principle:** STOP before creating a new doc file. Ask:
1. **Does this belong in an existing file?**
2. **Is this temporary (should be in docs/archive/)?**
3. **Will someone need this in 6 months?**

### Where to Put Documentation

| Content Type           | Location            | Examples                         |
| ---------------------- | ------------------- | -------------------------------- |
| **System overview**    | Root `README.md`    | Project description, quick start |
| **Agent training**     | Root `AGENTS.md`    | This file - comprehensive guide  |
| **User guides**        | `docs/*.md`         | Deployment, monitoring, APIs     |
| **Development notes**  | `docs/development/` | Migration plans, decisions       |
| **Session reports**    | `docs/archive/`     | Status reports, test results     |
| **Code documentation** | Inline comments     | Complex logic only               |

### ✅ Documentation Standards

**DO:**
- Update existing docs instead of creating new ones
- Use clear, scannable formatting (headings, bullets, tables)
- Include code examples that actually work
- Date all documentation files
- Keep root directory minimal (5-10 files max)

**DON'T:**
- Create "REPORT_FINAL_V3_UPDATED.md" files
- Duplicate information across multiple files
- Write essays when bullet points suffice
- Create docs for temporary/debugging info
- Leave TODO comments in documentation

### ✅ Naming Conventions

**GOOD File Names:**
- `DEPLOYMENT_GUIDE.md` - Clear, permanent
- `API_ENDPOINTS.md` - Descriptive
- `SETUP_COMPLETE.md` - Status clear

**BAD File Names:**
- `STATUS_REPORT_V3_FINAL_UPDATED.md` - Version chaos
- `NOTES.md` - Vague, will accumulate cruft
- `TODO_LIST_DEC_3.md` - Temporary info in permanent file
- `SYSTEM_IMPROVEMENTS_ROADMAP_V2_REVISED.md` - Too long, too versioned

### ✅ Documentation Lifecycle

**When to Archive:**
- Development status reports → `docs/archive/` after completion
- Migration plans → `docs/development/` after migration
- Test results → `docs/archive/` after validation
- Old architecture docs → `docs/legacy/` when replaced

**When to Delete:**
- Temporary debug files
- Duplicate information
- Outdated instructions that could confuse
- Empty or near-empty files

---

## 3. Development Workflow Best Practices

### ✅ Before You Start

1. **Read existing code** in the area you're modifying
2. **Check for similar implementations** to maintain consistency
3. **Verify the database schema** if working with data
4. **Look for existing utilities** before writing new ones

### ✅ During Development

1. **Make atomic commits** - one logical change per commit
2. **Test incrementally** - don't write 500 lines then test
3. **Clean up as you go** - remove debug code immediately
4. **Update docs inline** - don't defer documentation
5. **Flake-first + quick-deploy discipline** - prefer declarative module changes (`nix/` + flake path), keep `nixos-quick-deploy.sh` as orchestration/bootstrap, and only patch template-render path when required for legacy fallback

### ✅ After Development

**Before calling it "done":**
- [ ] Remove all debug print statements
- [ ] Delete commented-out code
- [ ] Update relevant documentation
- [ ] Check for leftover TODO comments
- [ ] Verify no temporary files created
- [ ] Run tests if they exist
- [ ] Check git status for unintended changes

**The 5-Minute Cleanup:**
```bash
# 1. Check for debug statements
grep -r "print\|console.log\|debugger" .

# 2. Find TODO comments
grep -r "TODO\|FIXME\|HACK" .

# 3. List recently modified files
git status

# 4. Check for large uncommitted files
git ls-files -o | xargs du -h | sort -h | tail -10

# 5. Verify no sensitive data
grep -r "password\|api_key\|secret" . --exclude-dir=.git
```

---

## 4. AI-Specific Best Practices

### ✅ Managing AI Output Quality

**Problem:** AI models can be verbose, over-engineer, or create unnecessary complexity.

**Solution - The Three Questions:**

1. **"Is this the simplest solution?"**
   - If you can do it in 10 lines instead of 100, do it
   - Resist the urge to create frameworks for single use cases

2. **"Does this follow existing patterns?"**
   - Check the codebase first
   - Match the style and structure already there

3. **"Will this need cleanup later?"**
   - If yes, clean it up NOW
   - Don't defer technical debt

### ✅ When Working with Multiple AI Agents

**Coordinate to avoid:**
- Creating duplicate documentation
- Inconsistent coding styles
- Overlapping functionality
- Documentation sprawl

**Best practices:**
1. **Check recent commits** before starting work
2. **Read the latest docs** to understand current state
3. **Update shared docs** (like AGENTS.md) carefully
4. **Use git to communicate** - commit messages matter

### ✅ Preventing "AI Slop"

**Red Flags - Stop and Simplify:**
- Creating abstract base classes for 1-2 implementations
- Adding configuration options "for flexibility" that aren't needed
- Writing comprehensive error messages for errors that can't happen
- Creating utility modules with one function
- Adding extensive logging to obvious operations

**Green Flags - You're Doing It Right:**
- Code reads naturally without comments
- Functions do one thing well
- Documentation answers "why" not "what"
- New code matches existing patterns
- You deleted more code than you added

---

## 5. Common Pitfalls to Avoid

### ❌ Documentation Anti-Patterns

1. **Status Report Explosion**
   - Don't create: `STATUS_V1.md`, `STATUS_V2.md`, `STATUS_FINAL.md`
   - Do: Update one `CURRENT_STATUS.md` file

2. **The Eternal TODO List**
   - Don't: Leave TODO.md files that grow forever
   - Do: Convert TODOs to issues/tasks or complete them

3. **Implementation Report Spam**
   - Don't: Create a report for every minor change
   - Do: Update one completion report or commit message

4. **README Confusion**
   - Don't: Create `README_NEW.md`, `README_UPDATED.md`
   - Do: Update the single `README.md`

### ❌ Code Anti-Patterns

1. **Premature Abstraction**
   - Don't: Create frameworks before you need them
   - Do: Write concrete code, refactor when you have 3+ examples

2. **Configuration Explosion**
   - Don't: Make everything configurable "just in case"
   - Do: Hard-code reasonable defaults, add config only when needed

3. **Error Handling Theater**
   - Don't: Catch every possible exception defensively
   - Do: Handle errors at boundaries, fail fast internally

4. **The Utility Junk Drawer**
   - Don't: Create `utils.py` with random helper functions
   - Do: Put utilities near where they're used, or in focused modules

---

## 6. Measuring Quality

**Good indicators:**
- Git history shows small, focused commits
- Root directory stays under 10 files
- Documentation is easy to find
- Code reviews take < 30 minutes
- New contributors can onboard in < 1 hour

**Bad indicators:**
- Large commits with "various fixes"
- Root directory has 50+ markdown files
- Multiple docs covering the same topic
- Code requires extensive comments to understand
- "Cleanup" commits after every feature

---

## 7. Quick Reference Checklists

### When Adding Code:
1. ✅ Search for existing patterns first
2. ✅ Keep it simple and focused
3. ✅ Match existing style
4. ✅ Test incrementally
5. ✅ Clean up before committing

### When Adding Documentation:
1. ✅ Check if existing doc can be updated
2. ✅ Use clear, scannable formatting
3. ✅ Put it in the right place (see table above)
4. ✅ Keep root directory minimal
5. ✅ Archive old status reports

### Before Calling It Done:
1. ✅ No debug code remaining
2. ✅ No commented-out code
3. ✅ Docs updated
4. ✅ Tests pass
5. ✅ Git status clean

### Quality Checkpoints (Before Committing):
```bash
# 1. Run linters (if available)
ruff check . || flake8 . || pylint .

# 2. Verify imports work
python -c "import main_module"

# 3. Check for secrets
git diff | grep -i "password\|secret\|key\|token"

# 4. Review changed files
git diff --stat

# 5. Test critical paths
pytest tests/ || npm test || ./scripts/test.sh
```

---

## 8. Available Tools & Resources

> **Note:** This section should be customized per project. See [AVAILABLE_TOOLS.md](docs/AVAILABLE_TOOLS.md) for the current project's tool inventory.

### Standard CLI Tools

Most projects will have access to:
- `git` - Version control
- `grep/rg` - Code search
- `find/fd` - File search
- `jq` - JSON processing
- `curl` - HTTP requests
- Language-specific tools (`python`, `node`, `cargo`, etc.)

### MCP Servers (If Available)

MCP (Model Context Protocol) servers provide specialized capabilities:
- File operations
- Database queries
- API integrations
- System monitoring

Check the project's `.mcp/` directory or MCP configuration for available servers.

### Project-Specific Tools

Look for:
- `scripts/` directory - Common automation
- `scripts/aqd` - CLI wrapper for skill/MCP workflows (`aqd skill ...`, `aqd mcp ...`)
- `Makefile` - Build and test commands
- `package.json` / `pyproject.toml` - Language tooling
- `kustomization.yaml` / `Dockerfile` - Container commands

---

## 9. First Steps in a New Project

### Onboarding Checklist:

1. **Read Core Documentation (15 minutes)**
   - [ ] README.md - Project overview
   - [ ] AGENTS.md (this file) - Development standards
   - [ ] QUICK_START.md or CONTRIBUTING.md (if exists)

2. **Understand the Codebase (30 minutes)**
   - [ ] Run: `tree -L 2 -d` to see structure
   - [ ] Check: `git log --oneline -20` for recent activity
   - [ ] Find: Main entry points (`main.py`, `index.js`, etc.)
   - [ ] Review: Database schema (if applicable)

3. **Set Up Your Environment (15 minutes)**
   - [ ] Check available tools: [AVAILABLE_TOOLS.md](docs/AVAILABLE_TOOLS.md)
   - [ ] Review MCP servers (if any): `.mcp/` directory
   - [ ] Test basic commands: `make help` or `npm run`

4. **Verify You Can Build/Test (15 minutes)**
   - [ ] Follow build instructions in README
   - [ ] Run tests: `pytest` / `npm test` / `make test`
   - [ ] Check linters: `ruff check .` / `eslint .`

**Total Time:** ~75 minutes to full productivity

---

## 10. Project-Specific Customization

> **For Project Maintainers:** Customize these sections for your project.

### Your Code Style

Document your project's conventions:
- Language version (Python 3.11+, Node 18+, etc.)
- Formatting tools (Black, Prettier, etc.)
- Import order conventions
- Naming conventions (camelCase vs snake_case)
- File organization patterns

### Your Documentation Structure

```
your-project/
├── README.md                # Project overview
├── AGENTS.md               # This file
├── docs/
│   ├── AVAILABLE_TOOLS.md  # Tool inventory
│   ├── ARCHITECTURE.md     # System design
│   ├── API.md              # API reference
│   ├── archive/            # Historical docs
│   └── development/        # Dev notes
└── examples/               # Code examples
```

### Your Testing Strategy

- Unit test requirements
- Integration test patterns
- E2E test approach
- Performance testing
- Security testing

### Your Deployment Process

- How to deploy (manual, CI/CD, scripts)
- Staging vs production
- Rollback procedures
- Monitoring and alerting

---

## 11. Additional Resources

### Included in This Package:

- [AVAILABLE_TOOLS.md](docs/AVAILABLE_TOOLS.md) - Complete tool inventory
- [MCP_SERVERS.md](docs/MCP_SERVERS.md) - MCP server documentation
- [CODE_EXAMPLES.md](examples/CODE_EXAMPLES.md) - Common patterns
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues

### External Resources:

- **The Three Questions Framework**: For preventing over-engineering
- **YAGNI Principle**: "You Aren't Gonna Need It" - avoid premature features
- **SOLID Principles**: Object-oriented design fundamentals
- **12-Factor App**: Modern application best practices

---

## 12. Getting Help

### When You're Stuck:

1. **Search the codebase** for similar functionality
2. **Check recent commits** for related changes
3. **Read existing docs** in `docs/` directory
4. **Look for examples** in `examples/` or test files
5. **Ask specific questions** rather than broad ones

### Good Questions:

- "Where is email validation handled in this codebase?"
- "What's the pattern for adding new API endpoints?"
- "How do I run the test suite for the auth module?"

### Bad Questions:

- "How does this whole project work?"
- "Can you explain everything about the architecture?"
- "What should I do next?"

---

## 13. Success Metrics

**You're doing it right when:**

- Your commits are small and focused
- Documentation is easy to find
- Code reviews are quick
- No "cleanup" commits needed
- New features integrate cleanly
- Root directory stays organized
- Tests pass consistently
- Other agents can understand your work

**Warning signs:**

- Large commits with many unrelated changes
- Creating new docs instead of updating existing ones
- Code requires extensive comments
- Frequent merge conflicts
- "Fix typo" commits after every feature
- Documentation that's hard to navigate

---

## Summary: The Professional AI Agent

**Before starting work:**
- Read existing code and docs
- Check for similar implementations
- Ask The Three Questions

**During work:**
- Write clean, simple code
- Test incrementally
- Clean up as you go
- Update docs inline

**Before committing:**
- Run The 5-Minute Cleanup
- Use Quality Checkpoints
- Verify no debug code
- Check git status

**The Result:**
Production-ready work that requires no cleanup cycles, integrates smoothly, and maintains professional quality standards.

---

**Version:** 1.0.0
**Last Updated:** 2025-12-03
**License:** MIT (or customize)
**Maintainer:** [Your Name/Team]
