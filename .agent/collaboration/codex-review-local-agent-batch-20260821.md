Reading additional input from stdin...
OpenAI Codex v0.147.0
--------
workdir: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: medium
reasoning summaries: none
session id: 01a026a2-b4a0-7921-b5a8-facb59adf996
--------
user
=== HARNESS GROUNDING (canonical SSOT — applies to codex) ===
# Harness Grounding Supplement (canonical SSOT — all agents)

This file is injected into every agent delegation (codex, claude, gemini, local,
antigravity) as a system-message supplement. It encodes harness-specific facts the
model cannot derive from general training. Keep entries concise — token cost per
delegation is real.

NOTE: sections tagged "[local-inference]" describe llama.cpp / local-model payload
behavior and apply when a lane controls the local inference request (local, aq-chat,
dispatch). They are harmless context for external agents (codex/claude/gemini) but
are not actionable there.

## Scope & Stop Discipline (HARD — every delegated agent, every turn)

You are executing ONE assigned slice, not steering the project. Before writing anything:

1. **Edit only the surfaces the task names.** If the task lists permitted files, those are
   the ONLY files you may modify. A file that seems related is still out of scope. Touching an
   unlisted surface is a stop condition, not initiative.
2. **Never implement a data/config change as a filesystem shortcut.** Do NOT create symlinks,
   bind mounts, mounts, or `chmod`/`chown`/`rm` tracked paths to "unify", "point at", or
   "redirect" state. "Single source of truth" means a resolver in code, never one directory
   replacing another. Filesystem-topology edits to tracked/runtime paths are forbidden unless the
   task names that exact path as a surface.
3. **NO DELETE — archive.** Never `rm`/`rmdir`. Move to a timestamped archive path instead.
4. **Check authorization state before AND after any pause.** If the task references an
   authorization/round, confirm it still reads AUTHORIZED (not SUSPENDED/PREPARED_ONLY/CONSUMED)
   and, where a package root is named, that `aq-package-freeze verify` exits 0 before you write.
   If a slice was suspended, STOP — do not recreate, re-stage, or continue suspended files.
5. **Undeclared dependency discovered → STOP and report.** Do not silently expand scope to
   "make it work". The plan amends; you do not.
6. **Budgets and acceptance criteria are hard facts, not negotiable by narrative.** If a measured
   result violates a stated budget (latency, sample size, size cap), it FAILS. A summary sentence
   asserting it is "acceptable" or "within tolerance" does not make it so — report the real number.
7. **Stage, don't commit, unless the task explicitly says commit.** The orchestrator runs the
   independent review and integration. Self-committing assigned slice work is out of role.

Violating any of the above wastes an entire review round and can suspend your authorization.
When unsure whether something is in scope: it is not — ask or report, do not act.

## Commit Format (mandatory)

Pattern: `type(scope): short description`
Example: `fix(dispatch): set frequency_penalty=0.0 to prevent JSON truncation`
Types: feat|fix|docs|refactor|chore|test|ci|perf|style
Trailer: `Co-Authored-By: claude-sonnet-4-6 <noreply@anthropic.com>`
CRITICAL: `(scope)` is NOT optional. `fix: description` is wrong. Always include it.

## Tool Result Messages [local-inference]

Tool result messages MUST use `role: "tool"`. Using `role: "function"` causes the message to
be silently dropped by the Qwen3 chat template — the model never sees the result and
hallucinates on all subsequent turns. Always: `{"role": "tool", "tool_call_id": "...", "content": "..."}`.

## AppArmor Rules

- SQLite databases: `rwk` (read+write+lock). `c` is INVALID — `rwkc` fails `apparmor_parser`.
- File rules do NOT cover `mkdir()`. Directory creation needs a separate explicit rule.
- `NoNewPrivileges=true` in systemd blocks `Ux`/`Px` transitions → use `ix` only.
- After profile changes: check `journalctl -u apparmor.service` for syntax errors.
- Nix store paths in AppArmor: use `/nix/store/**/rest/of/path` glob, NOT the full hash path.

## Frequency Penalty [local-inference]

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

## Timestamped Monitor Pattern (standard for all long-running agentic tasks)

Every Monitor arm for a long-running multi-step task MUST prefix events with an ISO 8601
UTC timestamp so elapsed time between events is immediately readable.

Standard wrapper (pipe after any grep/filter):
```bash
| while IFS= read -r line; do printf "[%s] %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$line"; done
```

Full example — watch a batch processor log:
```bash
tail -f /tmp/run.log | grep -E --line-buffered "progress|FAIL|done" \
  | while IFS= read -r line; do printf "[%s] %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$line"; done
```

Rules:
- Apply this wrapper to EVERY Monitor command — no exceptions for long-running tasks.
- Long-running scripts (batch processors, training loops, deploy scripts) must also prefix
  their own `print()` / `echo` output with `$(date -u +%Y-%m-%dT%H:%M:%SZ)` at the source.
- When re-arming a monitor (e.g. after a session break), stop the old monitor via TaskStop
  before arming the new one to avoid duplicate untimstamped events.

## Loop Completion Signal (aq-loop outer orchestration)

When a task is dispatched via `aq-loop`, the outer loop expects this exact completion signal
as your FINAL response after store_memory returns success:

  COMPLETED: <what was done in one sentence>

- Output ONLY that line. No JSON, no tool calls, no markdown.
- Omitting this signal causes aq-loop to classify the iteration as incomplete and retry.
- Do NOT output COMPLETED: before the task is actually done (tier0 passed + committed).

## Workflow Phases (ORIENT→COMMIT)

Follow in order. Never skip or reorder:
1. ORIENT   — get_hint(query) first. Read RESUME.json if available.
2. RESEARCH — query_aidb(collection='error-solutions'). Max 4 read_file per slice.
3. PLAN     — one sentence: 'Fixing: <title> — <description>'
4. EXECUTE  — edit_file over write_file. One targeted change per slice.
5. VERIFY   — validate_before_commit; fix failures; re-run tier0 gate.
6. DOC-UPDATE — mark [OPEN]→[DONE] in .agent/memory/issues-backlog.md if applicable.
7. COMMIT   — git_add + git_commit; then store_memory → then COMPLETED: signal.

=== END HARNESS GROUNDING ===

=== HARNESS CONSTRAINTS (NON-NEGOTIABLE) ===
1. SCOPE LOCK: Work ONLY on what the task requests. No unsolicited refactors, cleanups, or
   adjacent features. One slice, one concern. If in doubt about scope, STOP and report.
2. PRD GATE: Write a brief plan (problem/goal/files/validation) to .agent/collaboration/PULSE.log
   BEFORE editing any file. Format: [ISO-timestamp] [codex] [plan]: <scope> — <approach>
3. PORT POLICY: NEVER hardcode ports or URLs. Source of truth: nix/modules/core/options.nix.
   Python reads from env vars; shell uses ${PORT:-default}. Known ports: llama=8080,
   embed=8081, aidb=8002, coordinator=8003, switchboard=8085, dashboard=8889.
4. HARDWARE: GPU layers ceiling = 12 (Renoir APU). enable_thinking: false in ALL llama.cpp
   requests. Never suggest n_gpu_layers > 12.
5. LOGGING: switchboard.py uses print(..., file=sys.stderr) — there is NO logger object.
6. COMMIT DISCIPLINE: After work is done, list all modified files and validate with:
   python3 -m py_compile <py-files> && bash -n <sh-files>
   DO NOT commit — the orchestrator (Claude) reviews and commits.
7. SECURITY: No hardcoded secrets, tokens, or credentials. No injection patterns.
   Run py_compile on every Python file you touch before declaring work complete.
8. ATOMIC PULSE: Append one line to .agent/collaboration/PULSE.log after every file write:
   [ISO-timestamp] [codex] [write]: <file> — <what changed>
9. ATOMIC RESUME: At every phase start and on task completion, update
   .agent/collaboration/RESUME.json with: current_objective, phase, todo_snapshot[],
   uncommitted_changes[], resume_hint. This is the compaction anchor for all agents.
=== END CONSTRAINTS ===

INDEPENDENT REVIEW — local-agent reliability + record/replay harness (you were offline for all of it).

Review these commits (this session's work, all in ai-stack/local-agents/ + scripts/ai/ + scripts/testing/):
  git log --oneline -8   (look for: grammar fix, context supply chain, interventions, write_region,
  run_command artifact-strip, LLM record/replay harness)

CONTEXT: We root-caused why local (Qwen) failed ~95% of bounded edit tasks and fixed a chain of
CONFIG/HARNESS bugs (not model capability): a malformed GBNF tool-call grammar (unquoted keys +
forced-empty arguments in scripts/ai/lib/grammar_cache.py _object_rule), a 256->512 first-call token
budget, a whitespace-mangling context assembler, and a run_command shell-guard rejecting tool-call
JSON-envelope artifacts. Plus loop interventions (re-read, no-action, edit-feedback) and a write_region
line-range edit tool (Aider whole-format tactic), and an LLM record/replay cassette harness.

YOUR REVIEW SCOPE (independent — find what we missed; be adversarial):
1. grammar_cache.py _object_rule fix: is the generated GBNF actually correct/complete for nested
   objects + arrays? Any injection or malformed-JSON edge cases? (it's security-adjacent — it constrains
   model output).
2. shell_tools.py artifact-strip `re.sub(r"[\s}\]\",]+$", "", command)`: does trimming a trailing
   }/]/,/quote/space tail EVER strip a legitimate command's real trailing content (e.g. a command
   legitimately ending in a quote or bracket)? Is the injection guard still sound?
3. llm_cassette.py + agent_executor _call_llama wiring: is default-OFF truly a strict no-op on the hot
   path? Is request_key stable AND not accidentally colliding distinct requests? Any way a replay could
   silently mask a real regression?
4. The interventions in agent_executor: do the one-shot flags/counters actually bound retries, or can
   any loop indefinitely? Fail-safe on every path?
5. Anything HARD-rule-relevant: secrets, fail-closed violations, gates gamed.

OUTPUT: a prioritized findings list (severity + file:line + concrete failure scenario + fix). If a fix
is genuinely wrong or unsafe, say so plainly. Advisory — do NOT commit; the orchestrator integrates.
Report findings only; if nothing is wrong in an area, say "clean" for it.
deprecated: `[features].codex_hooks` is deprecated. Use `[features].hooks` instead.
Enable it with `--enable hooks` or `[features].hooks` in config.toml. See https://developers.openai.com/codex/config-basic#feature-flags for details.
hook: SessionStart
hook: SessionStart Completed
codex
I’ll perform a read-only, adversarial review of the eight commits, concentrating on grammar correctness, shell-command integrity, cassette isolation/keying, and retry termination. I’m using the repository’s lean-context and security-review workflows because this is a security-adjacent code review; I won’t alter or commit implementation files.
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "pwd && sed -n '1,240p' LEAN-CTX.md && sed -n '1,260p' /home/hyperd/.codex/skills/lean-ctx/SKILL.md && sed -n '1,300p' /home/hyperd/.codex/skills/security-audit/SKILL.md" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 58ms:
/home/hyperd/Documents/NixOS-Dev-Quick-Deploy
<!-- lean-ctx-owned: PROJECT-LEAN-CTX.md v1 -->
# lean-ctx — Context Engineering Layer
<!-- lean-ctx-rules-v9 -->

PREFER lean-ctx MCP tools over native equivalents for token savings:

## Tool preference:
| PREFER | OVER | Why |
|--------|------|-----|
| `ctx_read(path, mode)` | `Read` / `cat` | Cached, 10 read modes, re-reads ~13 tokens |
| `ctx_shell(command)` | `Shell` / `bash` | Pattern compression for git/npm/cargo output |
| `ctx_search(pattern, path)` | `Grep` / `rg` | Compact, token-efficient results |
| `ctx_tree(path, depth)` | `ls` / `find` | Compact directory maps |
| `ctx_edit(path, old_string, new_string)` | `Edit` (when Read unavailable) | Search-and-replace without native Read |

## ctx_read modes:
- `auto` — auto-select optimal mode (recommended default)
- `full` — cached read (files you edit)
- `map` — deps + exports (context-only files)
- `signatures` — API surface only
- `diff` — changed lines after edits
- `aggressive` — maximum compression (context only)
- `entropy` — highlight high-entropy fragments
- `task` — IB-filtered (task relevant)
- `reference` — quote-friendly minimal excerpts
- `lines:N-M` — specific range

## File editing:
Use native Edit/StrReplace if available. If Edit requires Read and Read is unavailable, use ctx_edit.
Write, Delete, Glob → use normally. NEVER loop on Edit failures — switch to ctx_edit immediately.

## Proactive (use without being asked):
- `ctx_overview(task)` at session start
- `ctx_compress` when context grows large
<!-- /lean-ctx -->
---
name: lean-ctx
description: Context Runtime for AI Agents — 46 MCP tools, 10 read modes, 90+ shell patterns, tree-sitter AST for 18 languages. Compresses LLM context by up to 99%. Use when reading files, running shell commands, searching code, or exploring directories. Auto-installs if not present.
---

# LeanCTX — Context Runtime for AI Agents

LeanCTX optimizes LLM context through 46 MCP tools, 90+ shell compression patterns, and tree-sitter AST parsing for 18 languages. It provides adaptive file reading, cross-session memory (CCP), task-conditioned relevance scoring, and a feedback loop for learning optimal compression.

## Setup (run first)

Before using lean-ctx, verify it is installed:

```bash
which lean-ctx || bash scripts/install.sh
```

If the install script is not available locally, install manually:

```bash
curl -fsSL https://raw.githubusercontent.com/yvgude/lean-ctx/main/skills/lean-ctx/scripts/install.sh | bash
```

After installation, configure the MCP server:

```bash
lean-ctx init --global
lean-ctx doctor --fix
```

## When to use lean-ctx

Always prefer `lean-ctx -c <command>` over running commands directly when:
- The command produces verbose output (build logs, git diffs, dependency trees, test results)
- You are reading files and only need the structure or API surface
- You want to check token savings for the current session

## Shell commands (use instead of raw exec)

```bash
lean-ctx -c git status          # Compressed git output
lean-ctx -c git diff            # Only meaningful diff lines
lean-ctx -c git log --oneline -10
lean-ctx -c npm install         # Strips progress bars, noise
lean-ctx -c cargo build
lean-ctx -c cargo test
lean-ctx -c docker ps
lean-ctx -c kubectl get pods
lean-ctx -c aws ec2 describe-instances
lean-ctx -c helm list
lean-ctx -c prisma migrate dev
lean-ctx -c curl -s <url>       # JSON schema extraction
lean-ctx -c ls -la <dir>        # Grouped directory listing
```

Supported: git, npm, pnpm, yarn, bun, deno, cargo, docker, kubectl, helm, gh, pip, ruff, go, eslint, prettier, tsc, aws, psql, mysql, prisma, swift, zig, cmake, ansible, composer, mix, bazel, systemd, terraform, make, maven, dotnet, flutter, poetry, rubocop, playwright, curl, wget, and more.

## File reading (compressed modes)

```bash
lean-ctx read <file>                    # Full content with structured header
lean-ctx read <file> -m map             # Dependency graph + exports + API (~5-15% tokens)
lean-ctx read <file> -m signatures      # Function/class signatures only (~10-20% tokens)
lean-ctx read <file> -m aggressive      # Syntax-stripped (~30-50% tokens)
lean-ctx read <file> -m entropy         # Shannon entropy filtered (~20-40% tokens)
lean-ctx read <file> -m diff            # Only changed lines since last read
```

Use `map` mode when you need to understand what a file does without reading every line.
Use `signatures` mode when you need the API surface of a module (tree-sitter for 18 languages).
Use `full` mode only when you will edit the file.

## AI Tool Integration

```bash
lean-ctx init --global          # Install shell aliases
lean-ctx init --agent claude    # Claude Code PreToolUse hook
lean-ctx init --agent cursor    # Cursor hooks.json
lean-ctx init --agent gemini    # Gemini CLI BeforeTool hook
lean-ctx init --agent codex     # Codex AGENTS.md
lean-ctx init --agent windsurf  # .windsurfrules
lean-ctx init --agent cline     # .clinerules
lean-ctx init --agent crush     # Crush MCP config
lean-ctx init --agent copilot   # VS Code / Copilot .vscode/mcp.json
```

## Multi-Agent & Knowledge (v2.7.0+)

MCP tools:
- `ctx_knowledge(action="remember", category, key, value)` — persistent cross-session project knowledge store
- `ctx_knowledge(action="recall", query)` — search stored facts by text or category
- `ctx_knowledge(action="consolidate")` — extract session findings into permanent knowledge
- `ctx_agent(action="register", agent_type, role)` — multi-agent context sharing with scratchpad messaging
- `ctx_agent(action="post", message, tags)` — share findings/warnings between concurrent agents
- `ctx_agent(action="read")` — read messages from other agents
- `ctx_agent(action="handoff", to_agent, message)` — transfer task to another agent
- `ctx_agent(action="sync")` — multi-agent sync status (active agents, pending messages, shared contexts)
- `ctx_share(action="push", paths, to_agent, message)` — push cached file contexts to another agent
- `ctx_share(action="pull")` — pull shared contexts from other agents
- `ctx_share(action="list")` — list all shared contexts
- `ctx_share(action="clear")` — remove contexts shared by this agent

## Additional Intelligence Tools (v2.19.0)

- `ctx_edit(path, old_string, new_string)` — search-and-replace file editing without native Read/Edit
- `ctx_overview(task)` — task-relevant project map at session start
- `ctx_preload(task)` — proactive context loader, caches task-relevant files
- `ctx_semantic_search(query)` — BM25 code search by meaning across the project
- `ctx_intent` now supports multi-intent detection and complexity classification
- Semantic cache: TF-IDF + cosine similarity for finding similar files across reads

## Session Continuity (CCP)

```bash
lean-ctx sessions list          # List all CCP sessions
lean-ctx sessions show          # Show latest session state
lean-ctx wrapped                # Weekly savings report card
lean-ctx wrapped --month        # Monthly savings report card
lean-ctx benchmark run          # Real project benchmark (terminal output)
lean-ctx benchmark run --json   # Machine-readable JSON output
lean-ctx benchmark report       # Shareable Markdown report
```

MCP tools for CCP:
- `ctx_session status` — show current session state (~400 tokens)
- `ctx_session load` — restore previous session (cross-chat memory)
- `ctx_session task "description"` — set current task
- `ctx_session finding "file:line — summary"` — record key finding
- `ctx_session decision "summary"` — record architectural decision
- `ctx_session save` — force persist session to disk
- `ctx_wrapped` — generate savings report card in chat

## Analytics

```bash
lean-ctx gain                   # Visual token savings dashboard
lean-ctx dashboard              # Web dashboard at localhost:3333
lean-ctx session                # Adoption statistics
lean-ctx discover               # Find uncompressed commands in shell history
```

## Tips

- The output suffix `[lean-ctx: 5029→197 tok, -96%]` shows original vs compressed token count
- For large outputs, lean-ctx automatically truncates while preserving relevant context
- JSON responses from curl/wget are reduced to schema outlines
- Build errors are grouped by type with counts
- Test results show only failures with summary counts
- Cached re-reads cost only ~13 tokens
---
name: security-audit
description: "Skill: security-audit"
---

# Skill: security-audit

- **Purpose**: Automate the identification of security vulnerabilities, insecure coding patterns, and compliance regressions in the codebase.
- **Variables**:
  - `target_path`: The file or directory path to scan.
- **Instructions**:
  - Rule 1: Use `scripts/security/security-audit.sh` for comprehensive scans.
  - Rule 2: Prioritize High/Critical CVEs and AppArmor policy violations.
  - Rule 3: Only suggest actionable fixes; do not just report vulnerabilities.
- **Workflow**:
  1. Initialize target environment.
  2. Run security scanner.
  3. Analyze report for High/Critical findings.
  4. Compare findings against known allowlist in `.gitleaks.toml`.
  5. Generate remediation plan.
- **Report**: A JSON security report and a list of actionable remediation steps or JIRA/task tickets.

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx -c 'which lean-ctx' && aq-session-start --task \"independent review local-agent reliability and record replay harness\" && aq-skill-auto \"independent security-adjacent review of local-agent grammar shell tools cassette replay and retry termination\" --agent codex --json --test" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 11572ms:
/run/current-system/sw/bin/lean-ctx
=== aq-session-start: independent review local-agent reliability and record replay harness ===

[1/3] Context bootstrap...
[2/3] Ranked hints...
[3/4] Hierarchical context...
[4/5] Lesson registry...
[5/5] System state snapshot...
[6/6] Collaborator awareness...

Context written to: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/scratchpad/session-context-20260821.md

--- Session Brief ---
Task : independent review local-agent reliability and record replay harness
Date : 2026-08-21T23:23:33Z
Collab: running=[codex, gemini, opencode] uncommitted=0
Lessons: 0 promoted, 0 pending review
--------------------
{
  "agent": "codex",
  "agent_instruction": "At task start, load selected local SKILL.md files. For sub-agents, pass reference_skills by name only. Treat validation security_issues as warnings for already-local skills; use capability-intake before importing external skills.",
  "reference_checks": {
    "checks": [
      {
        "command": "scripts/testing/check-skill-source-of-truth.sh",
        "ok": true,
        "returncode": 0,
        "stderr": "",
        "stdout": "PASS: skill files are confined to approved roots."
      },
      {
        "command": "scripts/testing/validate-skill-references.sh",
        "ok": true,
        "returncode": 0,
        "stderr": "",
        "stdout": "PASS: all relative skill references resolve."
      }
    ],
    "ok": true
  },
  "reference_skills": [
    "capability-intake",
    "agent-tool-map",
    "multi-agent-collab"
  ],
  "selected_skills": [
    {
      "description": "Security-gated intake workflow for external plugins, skills, MCP servers, and agent tools.",
      "name": "capability-intake",
      "path": ".agent/skills/capability-intake/SKILL.md",
      "score": 62,
      "sections": [
        "Capability Intake",
        "Description",
        "Tags",
        "When to Use",
        "Workflow",
        "Usage",
        "Files",
        "Delegation Rule"
      ],
      "tags": [
        "plugins",
        "skills",
        "tools",
        "mcp",
        "security",
        "admission",
        "supply-chain",
        "allowlist",
        "import"
      ],
      "when_to_use": "Use this skill before adding, enabling, updating, or delegating review of any external plugin, skill, MCP server, agent connector, or CLI capability. Use it for: Comparing candidate tools before installation. Auditing MCP/tool metadata and declared permissions. Producing reviewer-ready admission reports. Fan-out delegation for deeper source, security, and integration review."
    },
    {
      "description": "Agent Tool Map Skill",
      "name": "agent-tool-map",
      "path": ".agent/skills/agent-tool-map/SKILL.md",
      "score": 38,
      "sections": [
        "Agent Tool Map Skill",
        "Description",
        "Tags",
        "When to Use",
        "1. Tool Name Mapping by Agent",
        "Critical: Gemini `run_shell_command` Does Not Exist",
        "2. Gemini CLI Modes and Tool Availability",
        "3. Codex CLI Notes",
        "4. Local Agent (Qwen3) Tool Notes",
        "5. Prompt Design by Agent",
        "For Gemini (auto_edit)",
        "For Codex",
        "For Local (direct mode)",
        "For Claude (this agent)"
      ],
      "tags": [
        "gemini",
        "codex",
        "claude",
        "tools",
        "tool-names",
        "grep_search",
        "run_shell_command",
        "read_file",
        "replace"
      ],
      "when_to_use": "Writing prompts for Gemini or Codex; tool call failing with \"Tool not found\"; unsure which tool name to use in a delegation prompt for a specific agent. --"
    },
    {
      "description": "Multi-Agent Collaboration Skill",
      "name": "multi-agent-collab",
      "path": ".agent/skills/multi-agent-collab/SKILL.md",
      "score": 23,
      "sections": [
        "Multi-Agent Collaboration Skill",
        "Tags",
        "When to Use",
        "1. Role Matrix (summary)",
        "2. Canonical 2-3 Agent Review Cycle",
        "2b. Multi-Agent Expert-Team Debate (STANDARD for PRD / plan / decision creation)",
        "Engage ALL available agents (standing requirement)",
        "3. RESUME.json Schema (exact format)",
        "4. Handoff Protocol",
        "5. File Drop Protocol (.agents/drops/)",
        ".agents/drops/<id>.drop.yaml",
        "6. Context Slicing for Sub-Agents",
        "7. Conflict Resolution",
        "Terminal disposition SSOT"
      ],
      "tags": [
        "orchestrator",
        "multi-agent",
        "review",
        "handoff",
        "delegation",
        "RESUME",
        "PULSE",
        "role",
        "slice"
      ],
      "when_to_use": "Designing a review cycle; handing off between architect/implementer/reviewer; coordinating parallel agents; signaling task completion; structuring RESUME.json for cross-agent continuity. --"
    }
  ],
  "status": "ok",
  "task": "independent security-adjacent review of local-agent grammar shell tools cassette replay and retry termination",
  "validation": [
    {
      "detected_sections": [
        "Capability Intake",
        "Description",
        "Tags",
        "When to Use",
        "Workflow",
        "Usage",
        "Files",
        "Delegation Rule"
      ],
      "errors": [],
      "name": "capability-intake",
      "path": ".agent/skills/capability-intake/SKILL.md",
      "quality_score": 75.0,
      "security_issues": [],
      "suggestions": [],
      "valid": true,
      "warnings": [
        "Missing recommended sections: examples, notes"
      ]
    },
    {
      "detected_sections": [
        "Agent Tool Map Skill",
        "Description",
        "Tags",
        "When to Use",
        "1. Tool Name Mapping by Agent",
        "Critical: Gemini `run_shell_command` Does Not Exist",
        "2. Gemini CLI Modes and Tool Availability",
        "3. Codex CLI Notes",
        "4. Local Agent (Qwen3) Tool Notes",
        "5. Prompt Design by Agent",
        "For Gemini (auto_edit)",
        "For Codex",
        "For Local (direct mode)",
        "For Claude (this agent)"
      ],
      "errors": [],
      "name": "agent-tool-map",
      "path": ".agent/skills/agent-tool-map/SKILL.md",
      "quality_score": 70.0,
      "security_issues": [],
      "suggestions": [
        "Add a 'Usage' section with examples"
      ],
      "valid": true,
      "warnings": [
        "Missing recommended sections: usage, examples"
      ]
    },
    {
      "detected_sections": [
        "Multi-Agent Collaboration Skill",
        "Tags",
        "When to Use",
        "1. Role Matrix (summary)",
        "2. Canonical 2-3 Agent Review Cycle",
        "2b. Multi-Agent Expert-Team Debate (STANDARD for PRD / plan / decision creation)",
        "Engage ALL available agents (standing requirement)",
        "3. RESUME.json Schema (exact format)",
        "4. Handoff Protocol",
        "5. File Drop Protocol (.agents/drops/)",
        ".agents/drops/<id>.drop.yaml",
        "6. Context Slicing for Sub-Agents",
        "7. Conflict Resolution",
        "Terminal disposition SSOT"
      ],
      "errors": [
        "Missing required sections: description"
      ],
      "name": "multi-agent-collab",
      "path": ".agent/skills/multi-agent-collab/SKILL.md",
      "quality_score": 55.0,
      "security_issues": [],
      "suggestions": [
        "Consider adding more detail to improve quality score",
        "Add a 'Usage' section with examples"
      ],
      "valid": false,
      "warnings": [
        "Missing recommended sections: usage, examples, notes"
      ]
    }
  ]
}

codex
The mandatory session bootstrap is still running. Once it finishes, I’ll resolve the exact commit set and inspect both the changes and their tests, including negative cases that could expose unsafe trimming or replay collisions.
codex
The repository’s automatic skill router selected capability-intake, tool-mapping, and collaboration references. They do not authorize any broader work; I’m loading them only to satisfy the project workflow, and I’ll keep this review strictly within the named commits and surfaces.
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx read .agent/skills/capability-intake/SKILL.md && lean-ctx read .agent/skills/agent-tool-map/SKILL.md && lean-ctx read .agent/skills/multi-agent-collab/SKILL.md && lean-ctx -c 'git log --oneline -8' && lean-ctx -c 'git status --short'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 2462ms:
SKILL.md [57L]
---
name: capability-intake
description: Security-gated intake workflow for external plugins, skills, MCP servers, and agent tools.
---

# Capability Intake

## Description

Run the deny-by-default review workflow for external capabilities before agents enable plugins, skills, MCP servers, connectors, or CLIs.

## Tags
plugins, skills, tools, mcp, security, admission, supply-chain, allowlist, import

## When to Use
Use this skill before adding, enabling, updating, or delegating review of any external plugin, skill, MCP server, agent connector, or CLI capability.

Use it for:
- Comparing candidate tools before installation.
- Auditing MCP/tool metadata and declared permissions.
- Producing reviewer-ready admission reports.
- Fan-out delegation for deeper source, security, and integration review.

## Workflow
1. List candidates:
   ```bash
   scripts/ai/aq-capability-intake list
   ```
2. Audit all candidates:
   ```bash
   scripts/ai/aq-capability-intake audit --all --json
   ```
3. For a specific candidate:
   ```bash
   scripts/ai/aq-capability-intake audit <candidate-id> --json
   ```
4. Do not enable a candidate unless its report is `low-risk` or a reviewer explicitly accepts `needs-review` with mitigation.
5. If a candidate has network, secret, write, shell, package-manager, or browser permissions, require a follow-up slice with:
   - pinned version or digest
   - tool allowlist
   - SBOM/dependency scan
   - sandbox/permission boundary
   - dashboard or `aq-report` visibility
   - rollback path

## Usage

Start with `scripts/ai/aq-capability-intake audit <candidate-id> --json`, review admission status and mitigations, and only promote candidates that are `low-risk` or `accepted-with-mitigations`.

## Files
- Candidate registry: `config/agent-capability-intake-candidates.json`
- CLI: `scripts/ai/aq-capability-intake`
- PRD: `.agent/PROJECT-CAPABILITY-INTAKE-PRD.md`
- Test: `scripts/testing/test-capability-intake.py`

## Delegation Rule
When delegating review, pass only candidate id and this skill name. The receiving agent should load this skill, run the audit CLI, inspect upstream source, then report PASS/FAIL/REQUEST_REVISION with evidence.

SKILL.md [114L]
---
name: agent-tool-map
description: "Agent Tool Map Skill"
---

# Agent Tool Map Skill
## Description
Maps common operations to the correct tool names for Claude, Gemini, Codex, and the local agent so delegated prompts do not ask an agent to call unavailable tools.

## Tags
gemini, codex, claude, tools, tool-names, grep_search, run_shell_command, read_file, replace
## When to Use
Writing prompts for Gemini or Codex; tool call failing with "Tool not found"; unsure which
tool name to use in a delegation prompt for a specific agent.

---

## 1. Tool Name Mapping by Agent

Each agent has different tool names for the same operation. Use the correct name when writing prompts or delegation instructions.

- Read file: Claude Code `Read`; Gemini CLI `read_file`; Codex CLI `read_file`; local agent `read_file` / `Read`.
- Search content: Claude Code `Grep`; Gemini CLI `grep_search`; Codex CLI `grep_search`; local agent `grep_search`.
- Find files: Claude Code `Glob`; Gemini CLI `find_files`; Codex CLI `find_files`; local agent `find_files`.
- Edit file: Claude Code `Edit`; Gemini CLI `replace`; Codex CLI `apply_patch`; local agent `replace`.
- Write new file: Claude Code `Write`; Gemini CLI `write_file`; Codex CLI `write_file`; local agent `write_file`.
- Terminal command: Claude Code `Bash`; Gemini CLI unavailable in `auto_edit`; Codex CLI terminal tool; local agent `run_command`.
- Web fetch: Claude Code `WebFetch`; Gemini CLI `web_fetch`; Codex CLI n/a; local agent n/a.

### Critical: Gemini `run_shell_command` Does Not Exist
In Gemini CLI `auto_edit` mode, `run_shell_command` is NOT available. Any attempt returns
"Tool not found" and wastes a turn.

**When writing Gemini delegation prompts:**
```
WRONG: "Run `python3 -m py_compile file.py` to validate"
RIGHT: "Validate by reading file.py and checking for obvious syntax errors with grep_search"

WRONG: "Execute the tier0 validation gate"
RIGHT: "Read the gate script and verify the conditions it checks are met in the files"
```

For validation in Gemini prompts, rely on:
- `read_file` to verify file contents
- `grep_search` to find patterns
- `replace` + re-read to confirm edits took effect

---

## 2. Gemini CLI Modes and Tool Availability

| Mode | Tools available | Use for |
|------|----------------|---------|
| `auto_edit` | read_file, write_file, grep_search, find_files, replace, web_fetch | Code editing, review, analysis |
| `default` | read_file, grep_search, find_files, web_fetch | Read-only research |
| `yolo` | ALL tools, auto-approved | Full autonomous operation |

**Current harness usage**: Gemini is primarily `auto_edit` mode. Design delegation prompts
that do not rely on shell execution.

---

## 3. Codex CLI Notes

Codex requires stdin from `/dev/null`:
```bash
scripts/ai/delegate-to-codex --prompt "..." < /dev/null
```

Large prompts must go in a file:
```bash
scripts/ai/delegate-to-codex --prompt-file /tmp/prompt.txt < /dev/null
```

Codex uses `apply_patch` for edits (unified diff format). When writing Codex prompts for
code changes, describe the change and let Codex generate the patch — don't ask for `replace`.

---

## 4. Local Agent (Qwen3) Tool Notes

Local agent running via `--mode agent` has access to the coordinator's MCP tools:
- `hybrid_search` — searches AIDB collections
- `recall_agent_memory` — retrieves from memory broker
- `store_agent_memory` — writes to memory broker
- `get_hints` — gets contextual hints
- `ai_coordinator_delegate` — delegates to sub-agent (recursive)

Local agent in `--mode direct` has NO tool access — it receives only the prompt and produces
text. Do not ask it to "check the service status" or "run the QA" in direct mode.

---

## 5. Prompt Design by Agent

### For Gemini (auto_edit)
- Be explicit about which files to read and edit
- Include acceptance criteria as readable conditions ("the file should contain X")
- Avoid asking for shell validation — use file verification instead
- Keep prompts under 2000 tokens to avoid routing classifier failure (429)

### For Codex
- Always include the full edit scope in a separate file (`--prompt-file`)
- Specify exact file paths
- Request a specific output format ("output a commit message at the end")

### For Local (direct mode)
- Use focused prompts under 512 tokens for best results
- No tool calls — analysis/reasoning only
- Ask for structured output (JSON/YAML) for programmatic use

### For Claude (this agent)
- Full tool access — use Grep/Glob/Read/Edit/Bash freely
- Can run any validation commands directly

SKILL.md [195L]
---
name: multi-agent-collab
description: "Multi-Agent Collaboration Skill"
---

# Multi-Agent Collaboration Skill
## Tags
orchestrator, multi-agent, review, handoff, delegation, RESUME, PULSE, role, slice
## When to Use
Designing a review cycle; handing off between architect/implementer/reviewer; coordinating
parallel agents; signaling task completion; structuring RESUME.json for cross-agent continuity.

---

## 1. Role Matrix (summary)

| Role | Can do | Cannot do |
|------|--------|-----------|
| `orchestrator` | Assign slices, accept work, commit integration, open/close sessions | Implement code itself without reviewer |
| `architect` | Draft architecture, write PRDs, flag risks | Commit without orchestrator review |
| `implementer` | Edit files within assigned slice, validate, propose commit | Self-promote to reviewer, re-scope |
| `reviewer` | Issue pass/fail verdict against slice criteria | Review own work |

**Sub-agent non-orchestrator rule**: sub-agents execute only assigned slices. Do not re-scope,
do not route other agents, do not finalize acceptance.

---

## 2. Canonical 2-3 Agent Review Cycle

```
Orchestrator (Claude)
  ├─ 1. Write PRD + assign slice to implementer
  ├─ 2. delegate-to-gemini --role implementer --prompt-file /tmp/slice.txt
  ├─ 3. delegate-to-gemini --role reviewer --prompt "Review commit X per criteria Y"
  └─ 4. Record terminal disposition; issue a next scoped slice if needed

Single-agent multi-role (when team not needed):
  └─ Single agent handles all roles sequentially, marks each role switch explicitly
```

Planning uses one parallel batch review, one synthesis, then freeze as `PLAN_READY`,
`PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, or `PLAN_REJECTED`. Completed implementation uses
`ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`, `ACTIVATION_BLOCKED`, or `REJECTED`; no same-slice replay.

Pass implementer exactly the slice context. Do NOT pass full HANDOFF.md — pass only:
- The slice objectives
- Relevant file paths (not content)
- Acceptance criteria
- RESUME.json checkpoint

---

## 2b. Multi-Agent Expert-Team Debate (STANDARD for PRD / plan / decision creation)

CORRECT pattern (supersedes assigning a DIFFERENT role per agent — that conflates
angle-diversity with model-diversity and under-covers each angle):

**Every agent plays the SAME expert-team baseline per PASS. Run MULTIPLE passes to
cover the different angles.**

- **angle-diversity → passes.** Each pass = ONE expert-team baseline chosen for the
  goal/task/domain (kernel roles from role-matrix + domain expertise), e.g.
  pass1=[architect+security], pass2=[implementer+systems], pass3=[reviewer+product].
- **model-diversity → agents.** Within a pass, Claude + local(Qwen) + Codex + Gemini
  ALL reason through the SAME baseline, so disagreement reflects genuine model
  reasoning, not role framing.
- Multiple same-baseline passes cover EVERY angle with EVERY model — which is what the
  old AgentType→one-role SSOT tried to approximate with per-agent roles, but couldn't.

Mechanism (per pass, via aq-collaborate):
1. orchestrator picks the pass's expert-team baseline.
2. each agent votes: `aq-collaborate review <angle-item> --agent <model>-<baseline> --verdict approve|reject --score S --feedback "..."`
3. `aq-collaborate decide <angle-item>` → weighted consensus for that angle.
4. next pass = next baseline; aggregate the passes' consensuses into the final call.

ANTI-PATTERN (do NOT): one pass where each agent gets a different role. You then
cannot tell a role artifact from a real disagreement, and only one model sees each angle.

### Engage ALL available agents (standing requirement)

Every phase — grounding, research, PRD, plans, collaborations, integrations,
validations — engages ALL available agents, not just the orchestrator. The roster is
dynamic (the local model changes; currently Qwen). Invocation paths:
- **claude** — orchestrator + participant (direct).
- **local** (currently Qwen) — `delegate-to-local --mode agent` (headless, live).
- **codex** — `delegate-to-codex --prompt` (headless CLI, live).
- **gemini** — NO headless lane (switchboard remote credential unavailable under
  current constraints); engages via file/git A2A: post the pass to `aq-collaborate` +
  PULSE.log, the Antigravity IDE agent reads + submits its vote/contribution async.

Aggregation point = `aq-collaborate` (each agent submits a `review` per pass; `decide`
computes consensus once all available agents have voted). Do not proceed on a partial
roster unless an agent is genuinely unavailable — record which agents participated.

---

## 3. RESUME.json Schema (exact format)

```json
{
  "current_objective": "One sentence: what are we building right now",
  "phase": "Phase 86",
  "todo_snapshot": [
    "done: slice 1 — attention_queue.py",
    "in-progress: slice 2 — aq-alerts CLI",
    "pending: slice 3 — dashboard endpoint",
    "pending: slice 4 — NixOS shell hook"
  ],
  "uncommitted_changes": [
    "scripts/ai/lib/attention_queue.py",
    "scripts/ai/aq-alerts"
  ],
  "resume_hint": "Next: implement dashboard /api/aistack/alerts/status route in aistack.py"
}
```

**Write RESUME.json**: when starting a new user task AND after each completed todo item.
This is the compaction anchor — it must survive a 401 summarization failure.

---

## 4. Handoff Protocol

When transferring work to another agent:
```
1. Update RESUME.json with current state
2. Append to PULSE.log: [ISO-timestamp] [agent] [handoff]: scope — target agent + objective
3. Write HANDOFF.md entry with:
   - What was completed (with commit hash)
   - What's in-progress (file + line)
   - What's pending (next slice)
   - Any blockers discovered
4. Pass HANDOFF.md path to receiving agent (not content — they read it)
```

Task completion signal (from sub-agent to orchestrator):
```
1. Update PULSE.log: [timestamp] [agent] [complete]: slice-name — outcome
2. Update RESUME.json: mark todo item as done, update resume_hint
3. If committing: run tier0 gate first
4. Output summary: "VERDICT: PASS|FAIL — [brief outcome]" as last line
```

---

## 5. File Drop Protocol (.agents/drops/)

Drop file format for async task queuing:
```yaml
# .agents/drops/<id>.drop.yaml
title: "Task title (no injection chars)"
body: "Task description — no $(), backticks, or && allowed"
severity: medium           # critical|high|medium|low
agent: gemini              # optional: preferred agent
human_gate: false          # true = require human approval before execution
rebuild_required: false    # true = task requires nixos-rebuild after completion
```

Security: DropSpec rejects `$(`, `` ` ``, `&&` in title/body. Use plain text only.

---

## 6. Context Slicing for Sub-Agents

**Rule**: Sub-agents get slice-relevant context only. Never pass full session history.

What to include per slice:
```
- slice_objective (1-2 sentences)
- relevant_files (paths only, not content — agent reads them)
- acceptance_criteria (explicit pass/fail conditions)
- constraints (ports, security rules, existing patterns to follow)
- reference_skills (list skill names to load, e.g., ["apparmor-rules", "nixos-system"])
```

What NOT to include:
- Full HANDOFF.md (link to it, don't inline it)
- Previous agent outputs
- Unrelated file contents
- Full AGENTS.md (reference specific sections)

---

## 7. Conflict Resolution

When parallel implementers produce conflicting output:
1. Orchestrator reviews both against acceptance criteria
2. Winning implementation is selected (not merged — one wins)
3. Losing agent's patterns/insights are captured in HANDOFF.md
4. Conflict fact is logged to memory/facts: `fact_type: "conflict_resolution"`

## Terminal disposition SSOT

Planning: `PLAN_READY`, `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, `PLAN_REJECTED`. Implementation: `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`, `ACTIVATION_BLOCKED`, `REJECTED`. Frozen criteria are stable except critical defects. Safe inert-at-rest bytes may commit with `ACTIVATION_BLOCKED` but cannot activate; unsafe-at-rest bytes are `REJECTED`.

4650b1e6 chore: gitignore LLM cassette run-artifacts dir
950f56e4 feat(local-agent): LLM record/replay harness — deterministic offline validation
ae9029ef fix(local-agent): strip tool-call JSON-envelope artifact from run_command args
47e03ea9 feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis
7f00d1b2 docs(research)+chore: harness parity research + worklog + gitignore churn

hook: PreToolUse
2026-08-21T23:24:06.113905Z ERROR codex_core::tools::router: error=Command blocked by PreToolUse hook: Command should run via lean-ctx for compact output. Do not retry the original command. Re-run with: /run/current-system/sw/bin/lean-ctx -c 'git log -8 --format='\''%H%x09%s'\''' && /run/current-system/sw/bin/lean-ctx -c 'git status --short' && /run/current-system/sw/bin/lean-ctx -c 'git show --stat --oneline --decorate --no-renames HEAD~8..HEAD'. Command: git log -8 --format='%H%x09%s' && git status --short && git show --stat --oneline --decorate --no-renames HEAD~8..HEAD
hook: PreToolUse Blocked
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "/run/current-system/sw/bin/lean-ctx -c 'git log -8 --format='\\''%H%x09%s'\\''' && /run/current-system/sw/bin/lean-ctx -c 'git status --short' && /run/current-system/sw/bin/lean-ctx -c 'git show --stat --oneline --decorate --no-renames HEAD~8..HEAD'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 exited 128 in 901ms:
4650b1e656c5305fa1ec6a842158d9488fc671aa	chore: gitignore LLM cassette run-artifacts dir
950f56e4deecba5d42d986b240f306eb30e03ad2	feat(local-agent): LLM record/replay harness — deterministic offline validation
ae9029ef4a96beb69cb1dd879ac271acd165992b	fix(local-agent): strip tool-call JSON-envelope artifact from run_command args
47e03ea9891fcfac63de090328ac11555ffd4546	feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis
7f00d1b2afbff98f273ec9d653ff9af859357f83	docs(research)+chore: harness parity research + worklog + gitignore churn
fatal: ambiguous argument 'HEAD~8..HEAD': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'
[lean-ctx: full output -> /home/hyperd/.lean-ctx/tee/2026-08-21_162410_git_show_--stat_--oneline_--decorate_--n.log (redacted, 24h TTL)]

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx -c 'git rev-list --count HEAD' && lean-ctx -c 'git log --all --oneline --decorate --grep=grammar --grep=context --grep=intervention --grep=write_region --grep=artifact --grep=cassette' && lean-ctx -c 'git show --stat --oneline --decorate --no-renames 7f00d1b2"'^..HEAD'"'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 exited 128 in 2066ms:
5
4650b1e6 (HEAD -> main) chore: gitignore LLM cassette run-artifacts dir
950f56e4 (origin/main, origin/HEAD) feat(local-agent): LLM record/replay harness — deterministic offline validation
ae9029ef fix(local-agent): strip tool-call JSON-envelope artifact from run_command args
47e03ea9 feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis
7f00d1b2 (grafted) docs(research)+chore: harness parity research + worklog + gitignore churn
3d45e03c fix(foundation-c): repair ALA to C2 signed lease contract
0579c579 docs(foundation-c): Codex Rule-18 catch-up audit — 2 real C2-SCI defects logged (activation-gated)
36a5e2c4 feat(foundation-c): C6-B3 (amended) — fail-closed epoch reader + slot_queue revocation fence (default-OFF)
5f12ad5c feat(governance): Rule 20 PROGRESS-PROJECTED + MINIMAL-CODE + tier0 check-pm-tracker gate (agent parity)
1a555b38 docs(foundation-c): C6 rev3 — re-anchor after C2-SCI + C6-P0 (both blockers resolved)
2f89cf32 docs(foundation-c): C6 reconciliation — both pre-freeze blockers RESOLVED, C6 unblocked
7cbfa3b7 docs(foundation-c): C2 scheduler-context issuer BUILD COMPLETE (default-OFF) + queue confirmatory reviews
2c36e7d3 feat(foundation-c): C2 issuer B4 — Service Coverage + dashboard (default-OFF, C2-SCI build complete)
ad5d95dd feat(foundation-c): C2 issuer B3 — gate outbound-client + dispatch ingress (flag-gated CAPABILITY_SCHEDULER_CONTEXT_ISSUER, default-OFF byte-parity)
600a9eb6 docs(foundation-c): C2 B2 + B2.5 independent reviews — PASS, durable ledger validated
0bd67174 feat(foundation-c): C2 issuer B2.5 — durable atomic single-use ledger (closes fail-open-across-restarts)
03a3eb6c feat(foundation-c): C2 scheduler-context issuer B2 — confined service + verifier allowlist + schema (default-OFF)
5f3a8eb1 docs(foundation-c): C2 B1 independent code review PASS + fold observations
e01d48a7 feat(foundation-c): C2 scheduler-context issuer B1 — issuer + transport + tests (default-OFF, unwired)
f55d13fa docs(foundation-c): FREEZE C2 scheduler-context issuer rev4 (binding review PASS) — build gated on owner grant
9d765391 docs(foundation-c): C2 scheduler-context issuer rev4 — re-anchor baseline after ALA activation
5bf66edc docs(foundation-c): draft enforce-asymmetric-verify design — the real CAPABILITY_ASYMMETRIC_LEASE flag blocker
88cb1431 docs(foundation-c): draft enforce-asymmetric-verify design — the real CAPABILITY_ASYMMETRIC_LEASE flag blocker
48d92962 fix(foundation-c): ALA Phase 1b — grant switchboard socket access (prevents Phase-2 outage)
5b396cce feat(foundation-c): ALA activation Phase 1 — provision key + enable confined signer (flag still 0)
539ec969 docs(foundation-c): C2 scheduler-context issuer rev3 — realizes the trust model on the BUILT ALA
8bcfd393 feat(foundation-c): C6-P0 trust-anchors build (owner-activated, verified, tier0-green)
8ca60fa2 docs(foundation-c): asymmetric confined lease-signing authority design (owner-chosen fix for the rev2 FAIL)
33ef5ab3 docs(foundation-c): rev2 binding re-review = FAIL — issuer depends on asymmetric lease crypto that doesn't exist
f6188cd1 chore(collab): archive foundation-c-rev2-depth task and add review artifact
6a3952dc chore(collab): complete stream-auth-rereview and collect pending round manifests
6db86035 docs(foundation-c): fold advisory review lanes into the binding-review record
d8702e4c docs(foundation-c): C2 issuer rev2 closes binding-review HIGH defect (peer-uid was not authority)
c11d45ce docs(foundation-c): C6-P0 trust-anchors rev3 (narrowed) + C2 scheduler-context issuer slice
5f94cc06 docs(foundation-c): C6 activation-readiness reconciliation — Q-C6-1 (missing C2 issuer) is the critical path
aabd7073 docs(foundation-c): C4 activation-readiness reconciliation — C6 is the gating blocker
31c766e6 feat(governance): WR-3 deploy-context preflight for the execution-cell runner (T2)
b51875df docs(parity): Super Simple Software Factory parity analysis — 4 incorporation items
b42ba4a4 docs(collab): queue R7 provisioning design for codex binding review
97b5b056 docs(foundation-c): R7 provisioning design — trusted-repo mirror + durable reservation (GREEN round-trip)
e7bf91de docs(foundation-c): record antigravity advisory PASS on C5/C6/C3a-2 (not gate-clearing)
817b3112 docs(foundation-c): consolidated activation-ready batch packet for Aug-4 codex return
6d17f9e6 feat(foundation-c): C3b R5 switchboard adapter + Ed25519 grant signing (owner-activated, flag DEFAULT-OFF)
6b61c662 feat(foundation-c): ACTIVATE C5 span observability (CAPABILITY_SPAN_TRUTH=1)
ea89b86e feat(foundation-c): C5 spans-as-truth build (non-enforcement, flag CAPABILITY_SPAN_TRUTH default-OFF)
42271fea docs(foundation-c): C5 (OTel spans as truth) + C6 (epoch control + scheduler seam) designs
7eaa4620 feat(tooling): dashboard data-viz + progress bars + plans-index tests
927b4bfb feat(plans): plan lifecycle + supersession — retire what the AQ-OS refactor replaces
292ecba8 feat(tooling): aq-plans-index — master SSOT dashboard of every plan
3b66e152 feat(capability-intake): playwright-mcp version-integrity + sandbox-confinement (declared)
... (548 more commits, use git log --max-count=N to see all)
[lean-ctx: 18874→1419 tok, -92%]
fatal: ambiguous argument '7f00d1b2^..HEAD': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx -c 'git log --all --format=\"%H %s\" -30 --regexp-ignore-case --grep=\"grammar fix\\|context supply chain\\|interventions\\|write_region\\|artifact-strip\\|record/replay\"' && lean-ctx -c 'git show --stat --oneline 7f00d1b2' && lean-ctx -c 'git show --stat --oneline 47e03ea9' && lean-ctx -c 'git show --stat --oneline ae9029ef' && lean-ctx -c 'git show --stat --oneline 950f56e4' && lean-ctx -c 'git show --stat --oneline 4650b1e6'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 5014ms:
950f56e4deecba5d42d986b240f306eb30e03ad2 feat(local-agent): LLM record/replay harness — deterministic offline validation
47e03ea9891fcfac63de090328ac11555ffd4546 feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis
24059beb91ddcc829917ec63d2ca0e403a427e8a feat: implement generator-critic pattern for quality gating (Batch 9.2)
[lean-ctx] WARNING: compression removed >95% of content, returning original
7f00d1b2 docs(research)+chore: harness parity research + worklog + gitignore churn
 .agent/ACTIVATION-AUDIT.md                         |   510 +
 .agent/AQ-CHAT-PHASE-A-COMPLETE.md                 |    82 +
 .agent/AQ-CHAT-PHASE-E-COMPLETE.md                 |    62 +
 .agent/AQ-CHAT-ROUTING-KNOWLEDGE-SUMMARY.md        |    33 +
 .agent/AQ-CHAT-ROUTING-PLAN-CONSOLIDATED.md        |   996 +
 .agent/AQ-CHAT-ROUTING-PRD-CONSOLIDATED.md         |   597 +
 .agent/AQ-CHAT-ROUTING-PRD-claude.md               |   366 +
 .agent/AQ-CHAT-ROUTING-PRD-codex.md                |   795 +
 .agent/AQ-CHAT-ROUTING-PRD-gemini.md               |   635 +
 .agent/CLOUD-OPERATIONS-INSTRUCTIONS.md            |    20 +
 .agent/CODEX.md                                    |   422 +
 .agent/CYBER-SECURITY-INSTRUCTIONS.md              |    20 +
 .agent/DATA-ENGINEERING-INSTRUCTIONS.md            |    20 +
 .agent/DEFINITION-OF-DONE.md                       |    55 +
 .agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md           |   148 +
 .agent/FABLE-5-ANALYSIS-CHARTER.md                 |    90 +
 .agent/FABLE-PARITY-CONTRACT.md                    |    61 +
 .agent/FRONTEND-UIUX-INSTRUCTIONS.md               |    20 +
 .agent/FUTURE-AGENTIC-SURFACES.md                  |    52 +
 .agent/GEMINI.md                                   |   479 +
 .agent/GIS-SYSTEMS-INSTRUCTIONS.md                 |    80 +
 .agent/INDYDEVDAN-RESEARCH-SUMMARY.md              |    83 +
 .agent/INFRASTRUCTURE-CONSTRAINTS.md               |   167 +
 .agent/LOCAL-AGENT.md                              |   670 +
 .agent/ML-AI-INSTRUCTIONS.md                       |    20 +
 .agent/MLOPS-ENGINEERING-INSTRUCTIONS.md           |    20 +
 .agent/MOBILE-WEB-INSTRUCTIONS.md                  |    71 +
 .agent/OSINT-SYSTEMS-INSTRUCTIONS.md               |    85 +
 .agent/PRD-closed-local-improvement-loop.md        |   148 +
 .agent/PRD-slice2-slice3-zero-trust-inference.md   |   179 +
 .agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md |   214 +
 ...PROJECT-AGENT-MODEL-CONFIGURATION-PARITY-PRD.md |   107 +
 .agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md      |   119 +
 .agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md       |   119 +
 .agent/PROJECT-AGENTIC-MIND-STANDARDIZATION-PRD.md |   245 +
 .agent/PROJECT-AI-CAPABILITY-BACKLOG-PRD.md        |    35 +
 .agent/PROJECT-AI-REPO-DISCOVERY-PRD.md            |    30 +
 .agent/PROJECT-APPROVAL-CONTROL-PLANE-PRD.md       |   123 +
 .agent/PROJECT-AQ-EVAL-PRD.md                      |    35 +
 .agent/PROJECT-AQ-INFERENCE-BENCH-PRD.md           |    53 +
 .agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md            |   324 +
 .../PROJECT-AQOS-DEFENSIVE-SECURITY-FACTORY-PRD.md |   210 +
 .agent/PROJECT-AQOS-PRD.md                         |   209 +
 .agent/PROJECT-CAPABILITY-INTAKE-PLAN.md           |    39 +
 .agent/PROJECT-CAPABILITY-INTAKE-PRD.md            |    43 +
 .agent/PROJECT-CHECK-KERNEL-PRD.md                 |   278 +
 .agent/PROJECT-CODEX-SUBAGENT-CONFIGURATION-PRD.md |    55 +
 .agent/PROJECT-CONTEXT-SANDBOX-PARITY-PRD.md       |    34 +
 ...ROJECT-DECLARATIVE-SANDBOX-HOST-OBSERVER-PRD.md |    20 +
 .agent/PROJECT-EMBEDDED-HARDWARE-PLAN.md           |    34 +
 .agent/PROJECT-EMBEDDED-HARDWARE-PRD.md            |    28 +
 .agent/PROJECT-GIS-SYSTEMS-PLAN.md                 |    30 +
 .agent/PROJECT-GIS-SYSTEMS-PRD.md                  |    28 +
 .agent/PROJECT-HERDR-AGENT-OPERATIONS-PRD.md       |   120 +
 .agent/PROJECT-HERDR-H1-CORRECTION-PRD.md          |    70 +
 ...OJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md |   300 +
 ...-LOCAL-AI-FACTORY-REFERENCE-ARCHITECTURE-PRD.md |   647 +
 .../PROJECT-LOCAL-DELEGATION-RELIABILITY-PLAN.md   |   150 +
 .agent/PROJECT-LOCAL-DELEGATION-RELIABILITY-PRD.md |   266 +
 .agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md     |   560 +
 .agent/PROJECT-LOCAL-INFERENCE-L1A-PLAN.md         |    95 +
 .agent/PROJECT-LOCAL-INFERENCE-L2A-PLAN.md         |   157 +
 .agent/PROJECT-LOCAL-INFERENCE-L2B-A-PLAN.md       |   262 +
 ...LOCAL-INFERENCE-L2B-A1-DASHBOARD-PARITY-PLAN.md |    48 +
 .agent/PROJECT-MOBILE-WEB-PLAN.md                  |    37 +
 .agent/PROJECT-MOBILE-WEB-PRD.md                   |    28 +
 ...PROJECT-NETWORK-PROFILE-INTEROPERABILITY-PRD.md |   344 +
 .agent/PROJECT-OSINT-SYSTEMS-PLAN.md               |    42 +
 .agent/PROJECT-OSINT-SYSTEMS-PRD.md                |    51 +
 .agent/PROJECT-PRECOMMIT-SUBJECT-BOUNDARY-PRD.md   |   218 +
 .agent/PROJECT-PROGRAM-PROGRESS-TRACKER-PRD.md     |   125 +
 .../PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md   |   388 +
 .agent/PROJECT-REVIEW-CONVERGENCE-PRD.md           |    60 +
 .agent/PROJECT-ROOT-CAUSE-DISCIPLINE-PRD.md        |    96 +
 .agent/PROJECT-RSI-READINESS-PRD.md                |   210 +
 .agent/PROJECT-RULE-19-RATIFICATION.md             |    88 +
 .agent/PROJECT-SCIENTIFIC-RESEARCH-PLAN.md         |    30 +
 .agent/PROJECT-SCIENTIFIC-RESEARCH-PRD.md          |    28 +
 .agent/PROJECT-SECURITY-SYSTEMS-PRD.md             |    55 +
 .agent/PROJECT-SYSTEM-CAPABILITY-CATALOG-PRD.md    |    62 +
 .agent/PROJECT-SYSTEMS-SOFTWARE-PRD.md             |    48 +
 .agent/PROJECT-T3MP3ST-CAPABILITY-INTAKE-PRD.md    |    57 +
 .agent/PROJECT-TERMINAL-REVIEW-DISPOSITIONS-PRD.md |    75 +
 .agent/PROJECT-TRUSTED-EXECUTION-GATEWAY-PRD.md    |   152 +
 .agent/PROJECT-USABILITY-PARITY-PRD.md             |   260 +
 .agent/PROJECT-VERIFIED-FACTORY-PRD.md             |   297 +
 .agent/PROJECT-WORKFLOW-DEVIATION-RECOVERY-PRD.md  |    92 +
 .agent/PROMOTED-BUG-PATTERNS.md                    |   207 +
 .agent/QA-AUTOMATION-INSTRUCTIONS.md               |    20 +
 .agent/QWEN.md                                     |     9 +
 .agent/RUST-ENGINEERING-INSTRUCTIONS.md            |    32 +
 .agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md         |    81 +
 .agent/SECURITY-SYSTEMS-INSTRUCTIONS.md            |   129 +
 .agent/SKILL_INDEX.md                              |   166 +
 .agent/SYSTEM-AUDIT-2026-06-14.md                  |   202 +
 .agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md            |   149 +
 .agent/TRADING-AGENTS-INSTRUCTIONS.md              |    20 +
 .agent/WORKAROUND-REGISTER.md                      |    70 +
 .agent/WORKFLOW-CANON.md                           |   751 +
 .agent/agent.md                                    |     0
 .agent/analysis/2026-07-09-full-system-analysis.md |    92 +
 .../DEEP-TECHNICAL-ANALYSIS-REPORT.md              |    66 +
 .agent/archive/20260531-docs/DOMAIN-ROLE-MATRIX.md |   134 +
 .../archive/20260531-docs/IMPLEMENTATION-REPORT.md |   528 +
 .../20260531-docs/LOCAL-AGENT-HARNESS-PRIMER.md    |   514 +
 .../20260531-docs/MASTER-DEVELOPMENT-PROMPT.md     |   427 +
 .../20260531-docs/PHASE-3-3-IMPLEMENTATION.md      |   402 +
 .../20260531-docs/PHASE-3-3-VALIDATION-EXAMPLES.md |   375 +
 .../PHASE-4.1-IMPLEMENTATION-SUMMARY.md            |   463 +
 .../PHASE-5-2-OPTIMIZATION-CHANGES.md              |   301 +
 .agent/archive/20260531-docs/PHASE-86-PRD.md       |   120 +
 .../PHASE-LOCAL-ASYNC-IMPLEMENTATION-REPORT.md     |    34 +
 .../PHASE-OSINT-IMPLEMENTATION-SUMMARY.md          |    49 +
 .../PRODUCTION-FINALIZATION-INVOKE.md              |   104 +
 .../20260531-docs/PROJECT-ACCELERATE-PRD.md        |    52 +
 .../20260531-docs/PROJECT-AGENT-CLI-TOOLS-PRD.md   |    63 +
 .../PROJECT-AGENT-ROLE-STANDARDIZATION-PRD.md      |   115 +
 .../PROJECT-AGENT-TOOL-CONTRACT-PRD.md             |    79 +
 .../PROJECT-AGENTIC-FIRST-ELEVATION-PRD.md         |   306 +
 .../PROJECT-APPARMOR-ACTIVATION-RELIABILITY-PRD.md |    27 +
 .../PROJECT-CAPABILITY-EXPANSION-CODEX-PRD.md      |   179 +
 .../PROJECT-CAPABILITY-EXPANSION-MASTER-PRD.md     |   318 +
 .../PROJECT-CLI-TOOL-ACCESS-ENABLING-PRD.md        |    31 +
 .../PROJECT-COMMAND-CENTER-DASHBOARD-REVAMP-PRD.md |    72 +
 .../PROJECT-CONFIG-CENTRALIZATION-PRD.md           |   492 +
 .../PROJECT-CONTINUE-EDITOR-RESCUE-PRD.md          |    33 +
 .../PROJECT-CORE-INPUT-REFRESH-PRD.md              |    30 +
 .../PROJECT-DEPLOY-TIME-MEMORY-RELIEF-PRD.md       |    27 +
 .../20260531-docs/PROJECT-DISPATCH-REFACTOR-PRD.md |   144 +
 .../20260531-docs/PROJECT-EMBEDDED-HARDWARE-PRD.md |   163 +
 .../PROJECT-FAILED-UNIT-HYGIENE-PRD.md             |    22 +
 .../PROJECT-GEMINI-QUALITY-HARDENING-PRD.md        |    36 +
 .../20260531-docs/PROJECT-GIS-SYSTEMS-PRD.md       |   161 +
 ...T-HARNESS-OPERATION-ROUTING-CONTINUATION-PRD.md |    37 +
 .../20260531-docs/PROJECT-HEALTH-SPIDER-PRD.md     |    42 +
 .../PROJECT-HW-CAPABILITY-MATRIX-PRD.md            |   160 +
 .../PROJECT-INTEGRITY-SCAN-DEBT-PRD.md             |    33 +
 .../PROJECT-KERNEL-TRACK-MIGRATION-PRD.md          |    37 +
 .../PROJECT-LOCAL-AGENT-CODING-PRD.md              |    76 +
 .../PROJECT-LOCAL-ASYNC-OPTIMIZATION-PRD.md        |    58 +
 .../PROJECT-LOGICAL-ORPHAN-BASELINE-PRD.md         |    48 +
 .../PROJECT-MAEAH-EDGE-HARNESS-PRD.md              |    32 +
 .../20260531-docs/PROJECT-MLOPS-ENGINEERING-PRD.md |    45 +
 .../20260531-docs/PROJECT-MOBILE-WEB-PRD.md        |   153 +
 .../20260531-docs/PROJECT-OSINT-SYSTEMS-PRD.md     |   113 +
 .../archive/20260531-docs/PROJECT-PAEA-PRD-V2.md   |    69 +
 .../archive/20260531-docs/PROJECT-PAEA-PRD-V3-1.md |    91 +
 .../archive/20260531-docs/PROJECT-PAEA-PRD-V3.md   |   101 +
 .agent/archive/20260531-docs/PROJECT-PAEA-PRD.md   |    67 +
 ...ROJECT-PHASE55-COORDINATOR-STABILIZATION-PRD.md |    31 +
 .../archive/20260531-docs/PROJECT-PHASE83-PRD.md   |    85 +
 .../archive/20260531-docs/PROJECT-PHASE85-PRD.md   |   195 +
 .../PROJECT-PROGRESSIVE-DISCLOSURE-DOCS-PRD.md     |    50 +
 .../20260531-docs/PROJECT-QA-AUTOMATION-PRD.md     |    19 +
 .../PROJECT-REPO-PARITY-TOOLING-PRD.md             |    45 +
 .../PROJECT-ROCM-TARGET-AUTOMATION-PRD.md          |    20 +
 .../20260531-docs/PROJECT-RUNTIME-NARROWING-PRD.md |    34 +
 .../PROJECT-SCIENTIFIC-RESEARCH-PRD.md             |   159 +
 .../20260531-docs/PROJECT-SECURITY-SYSTEMS-PRD.md  |   138 +
 .../PROJECT-SYSTEM-STABILITY-RECOVERY-PRD.md       |    38 +
 .../20260531-docs/PROJECT-SYSTEMS-SOFTWARE-PRD.md  |   176 +
 .../20260531-docs/PROJECT-TOKENMAXXING-PRD.md      |    72 +
 .../PROJECT-TOOL-WORKING-SET-GC-PRD.md             |    33 +
 .../20260531-docs/PROJECT-TOOLBOX-FACTORY-PRD.md   |    21 +
 .../20260531-docs/PROJECT-TRADING-AGENTS-PRD.md    |    19 +
 .../20260531-docs/PROJECT-WORKFLOW-PARITY-PRD.md   |    99 +
 .../20260531-docs/REASONING-PROFILES-COMPLETE.md   |   495 +
 .../20260531-docs/SYSTEM-EXECUTIVE-SUMMARY.md      |    96 +
 .../UNIVERSAL-VALIDATION-FRAMEWORK-PRD.md          |   184 +
 .../20260531-docs/phase73-expert-panel-response.md |   129 +
 .../SKILL.md                                       |    32 +
 .../20260531-stub-strict-json-output/SKILL.md      |    32 +
 .agent/archive/20260615-1necho-artifact            |    36 +
 .../archive/20260618-quirky-wondering-hollerith.md |   208 +
 .agent/archive/20260629-stale-loop-dry-run.json    |    10 +
 .agent/archive/20260701-1necho-root-junk           |     6 +
 .agent/archive/20260701-aq-loop-overnight          |   121 +
 .agent/archive/20260701-loop-1782774058.json       |    10 +
 .agent/archive/20260729-stray-junk/1nwc            |     2 +
 .agent/archive/20260730-tracker-wip/README.md      |    11 +
 .../tracker-refresh-slice.patch                    |   677 +
 .agent/archive/20260807-shell-debris/1nwc          |     2 +
 .../dogfood-01-validate.patch                      |     0
 .../20260818-dogfood-falserun/dogfood-02.patch     |     0
 .../20260818-dogfood-falserun/dogfood-03.patch     |     0
 .../20260818-dogfood-falserun/dogfood-04.patch     |     0
 .../20260818-dogfood-falserun/dogfood-05.patch     |     0
 .../20260818-dogfood-falserun/dogfood-06.patch     |     0
 .../dogfood-overnight-summary.md                   |    16 +
 .../summary-grammar-only-21pct.md                  |    29 +
 .../summary-pre-grammar.md                         |    13 +
 .../summary-pre-verbatim.md                        |    30 +
 .agent/archive/ARCHIVED-GIT-REFS.md                |     3 +
 .../BOUNDARY-usability-parity.md                   |    21 +
 .../archive/antigravity-inbox-20260709/aqos-v1.md  |    38 +
 .../f1-plan-consensus.md                           |   148 +
 .../f1-round-state-machine.md                      |    12 +
 .../f2-local-scheduler.md                          |    12 +
 .../f2-plan-consensus.md                           |   107 +
 .../antigravity-inbox-20260709/f2-session-mode.md  |    57 +
 .../f3-capability-otel.md                          |    12 +
 .../antigravity-inbox-20260709/factory-critique.md |    12 +
 .../antigravity-inbox-20260709/reentry-intent.md   |    75 +
 .../usability-parity-expert-team.md                |    31 +
 .../usability-parity-v2.md                         |   201 +
 .../ws-edge-privacy-wasm.md                        |    23 +
 .../aqos-cycle0-findings-review.md                 |    57 +
 .../build-package-freeze-tool.md                   |    58 +
 .../aqos-refoundation-cycle0.md                    |    12 +
 .../gemini-fresh-approve-cycle0.md                 |    42 +
 .../implement-c02-slice.md                         |    60 +
 .../repin-c02-recovery-review.md                   |    24 +
 .../review-c02-recovery-root-v2.md                 |    21 +
 .../review-c02-recovery-root.md                    |    22 +
 .../antigravity-inbox-20260711/review-e2f1b8c6.md  |    34 +
 .../00-review-c0.3-opus-implementation.md          |    14 +
 .../review-local-inference-contract.md             |    18 +
 .../agent-ops-traceability-m0-acceptance.md        |    33 +
 .../agent-ops-traceability-m1-acceptance.md        |    42 +
 .../agent-ops-traceability-m1-design-review.md     |    30 +
 .../agent-ops-traceability-m2-design-review.md     |    37 +
 .../agent-ops-traceability-m2-rev3-review.md       |    19 +
 .../agent-ops-traceability-r0m-design-review.md    |    32 +
 ...ocal-delegation-reliability-r0-acceptance-v2.md |    39 +
 .../local-delegation-reliability-r0-review.md      |    38 +
 .../local-inference-l2b-a-acceptance-v2.md         |    39 +
 .../local-inference-l2b-a1-acceptance.md           |    33 +
 .../local-inference-l2b-a1-dashboard-review.md     |    32 +
 .../m2-fable-routing-bootstrap-acceptance.md       |    23 +
 .../m2-fable-routing-bootstrap-hash-refresh.md     |    14 +
 .../m2a-am1-candidate-acceptance.md                |    36 +
 .../m2a-inventory-amendment-1-review.md            |    15 +
 .../unified-program-required-revisions-review.md   |    30 +
 .../unified-program-revision-review.md             |    37 +
 .../antigravity-inbox-20260715/unified-program.md  |    27 +
 .../agent-connection-reliability-c0-acceptance.md  |    48 +
 ...gent-connection-reliability-c0-design-review.md |    34 +
 .../agent-ops-traceability-m2b-design-review.md    |    31 +
 .../agent-ops-traceability-m2b-rev4-review.md      |    25 +
 .../c05-design-review.md                           |    33 +
 .../c05-tiered-policy-architecture.md              |    26 +
 .../antigravity-inbox-20260716/c05a-acceptance.md  |    30 +
 .../m2a-read-only-show-hotfix-acceptance.md        |    27 +
 ...ent-connection-reliability-c06-design-review.md |    39 +
 .../antigravity-routing-honesty-accept.md          |    26 +
 .../.claimed-dispatch-integration-review           |    26 +
 .../stream-auth-rereview.md                        |    26 +
 .../.claimed-test-harness-verification             |     3 +
 .../b1-parity-design-review.md                     |   141 +
 .../track-s-architecture-review.md                 |    40 +
 ...ty-autonomous-bridge-a0-am5-review-3e2e17b3090d |    33 +
 .../agent-model-config-c1a-acceptance.md           |    32 +
 .../agent-model-config-parity-design-input.md      |    75 +
 .../reactivation-review-20260729.md                |    50 +
 ...progress-tracker-am1-design-review-aef829c9f595 |    23 +
 .../.claimed-c3b-r1-review-3d0bd81a3e68            |    70 +
 .../.claimed-c3b-r2-review-2800286b11dd            |    66 +
 .../.claimed-c3b-r3-review-f8b01eff83a7            |    71 +
 .../.claimed-c3b-r4-review-2a6e0a2f7942            |    44 +
 .../.claimed-c3b-r5-review-c428774d454d            |    52 +
 .../.claimed-c4-review-6658e35ff46f                |    49 +
 .../.claimed-c3a2-review-eb1d918dbc41              |    42 +
 .../.claimed-c5-review-cff52c881624                |    37 +
 .../.claimed-c6-review-84f55b64044d                |    40 +
 ...d-foundation-c-rev2-depth-20260801-ca6cfdf4b18e |    76 +
 ...d-enforce-asymmetric-verify-review-e65014a7626e |    47 +
 ...ala-c2-c6-b3r-advisory-20260808.md-052aa2d5a04b |    21 +
 ...uler-context-issuer-rev4-review.md-04e88fb9a7fa |    27 +
 ...org-friction-consensus-20260808.md-bbedbee4915f |    34 +
 .../acp-prd-advisory-20260815.md-2ca10497228f      |    26 +
 .../rsi-readiness.md                               |    50 +
 .../GEMINI-C0.3-OPUS-IMPLEMENTATION-REVIEW.md      |    53 +
 .../GEMINI-LOCAL-INFERENCE-CONTRACT-REVIEW.md      |    64 +
 .../GEMINI-RAG-SEED-REVIEW.md                      |   138 +
 .../pulse-artifacts-20260709/PULSE.lognecho        |     4 +
 .../pulse-artifacts-20260709/PULSE.lognprintf      |     4 +
 .agent/archive/usability-parity-v1-antigravity.md  |   171 +
 .agent/collaboration/AGENT-CATCHUP-QUEUE.md        |   253 +
 .agent/collaboration/CODEX-PHASE-65-REVIEW.md      |   101 +
 .agent/collaboration/CODEX-PHASE-68-REVIEW.md      |   120 +
 .agent/collaboration/CODEX-REVIEW-QUEUE.md         |    45 +
 .agent/collaboration/FINAL-SUMMARY.md              |    23 +
 .agent/collaboration/GEMINI-ARCH-REVIEW-PH74.md    |    47 +
 .agent/collaboration/GEMINI-PHASE-65-REVIEW.md     |   135 +
 .agent/collaboration/GEMINI-PHASE-68-REVIEW.md     |    83 +
 .agent/collaboration/GEMINI-VISUAL-REVIEW.md       |    61 +
 .agent/collaboration/HANDOFF.template.md           |    13 +
 .agent/collaboration/INFRASTRUCTURE-REPORT.md      |    14 +
 .agent/collaboration/LOCAL_DELEGATION_STRATEGY.md  |    47 +
 .agent/collaboration/LOOP_STATE.json               |    44 +
 .agent/collaboration/PENDING.template.json         |     4 +
 .agent/collaboration/PHASE-65-67-TEAM-BRIEF.md     |   126 +
 .agent/collaboration/PHASE-68-TEAM-BRIEF.md        |    47 +
 .agent/collaboration/README.md                     |    29 +
 .agent/collaboration/RESUME.template.json          |     7 +
 .agent/collaboration/RULES.md                      |    50 +
 .agent/collaboration/STATUS-2026-07-07.md          |    50 +
 .agent/collaboration/SUPPORT_BROADCAST.md          |    36 +
 .../antigravity-inbox/.supervisor.lock             |     0
 .../acp-p1-design-review-20260816.md               |    21 +
 .../acp-p1b-design-review-20260817.md              |    22 +
 .../acp-p2-design-review-20260816.md               |    23 +
 .../acp-p3-design-review-20260816.md               |    24 +
 .../acp-p4-design-review-20260817.md               |    22 +
 .../flat-org-friction-consensus-20260808.md        |    34 +
 .../herdr-escalation-adjudication-20260816.md      |    28 +
 .../receipts/acp-p1-design-review-20260816.json    |     1 +
 .../receipts/acp-p1b-design-review-20260817.json   |     1 +
 .../receipts/acp-p2-design-review-20260816.json    |     1 +
 .../receipts/acp-p3-design-review-20260816.json    |     1 +
 .../receipts/acp-p4-design-review-20260817.json    |     1 +
 .../receipts/acp-prd-advisory-20260815.json        |     1 +
 ...t-connection-reliability-c06-design-review.json |    12 +
 .../agent-model-config-c1a-acceptance.json         |    12 +
 .../agent-model-config-parity-design-input.json    |    12 +
 .../receipts/ala-c2-c6-b3r-advisory-20260808.json  |     1 +
 ...ntigravity-autonomous-bridge-a0-am5-review.json |     1 +
 ...ntigravity-autonomous-bridge-a0-am5-review.lock |     0
 .../antigravity-routing-honesty-accept.json        |    21 +
 .../aqos-progress-tracker-am1-design-review.json   |     1 +
 .../aqos-progress-tracker-am1-design-review.lock   |     0
 .../receipts/b1-parity-design-review.json          |    31 +
 ...-issuer-rev4-review.adoption-normalization.json |     9 +
 .../c2-scheduler-context-issuer-rev4-review.json   |     1 +
 .../antigravity-inbox/receipts/c3a2-review.json    |     1 +
 .../antigravity-inbox/receipts/c3a2-review.lock    |     0
 .../antigravity-inbox/receipts/c3b-r1-review.json  |     1 +
 .../antigravity-inbox/receipts/c3b-r1-review.lock  |     0
 .../antigravity-inbox/receipts/c3b-r2-review.json  |     1 +
 .../antigravity-inbox/receipts/c3b-r2-review.lock  |     0
 .../antigravity-inbox/receipts/c3b-r3-review.json  |     1 +
 .../antigravity-inbox/receipts/c3b-r3-review.lock  |     0
 .../antigravity-inbox/receipts/c3b-r4-review.json  |     1 +
 .../antigravity-inbox/receipts/c3b-r4-review.lock  |     0
 .../antigravity-inbox/receipts/c3b-r5-review.json  |     1 +
 .../antigravity-inbox/receipts/c3b-r5-review.lock  |     0
 .../antigravity-inbox/receipts/c4-review.json      |     1 +
 .../antigravity-inbox/receipts/c4-review.lock      |     0
 .../antigravity-inbox/receipts/c5-review.json      |     1 +
 .../antigravity-inbox/receipts/c5-review.lock      |     0
 .../antigravity-inbox/receipts/c6-review.json      |     1 +
 .../antigravity-inbox/receipts/c6-review.lock      |     0
 .../receipts/dispatch-integration-review.json      |    69 +
 .../receipts/enforce-asymmetric-verify-review.json |     1 +
 .../receipts/enforce-asymmetric-verify-review.lock |     0
 ...ion-consensus-20260808.adoption-completion.json |    11 +
 .../flat-org-friction-consensus-20260808.json      |     1 +
 .../receipts/foundation-c-rev2-depth-20260801.json |     1 +
 .../receipts/foundation-c-rev2-depth-20260801.lock |     0
 .../herdr-escalation-adjudication-20260816.json    |     1 +
 .../receipts/reactivation-review-20260729.json     |    38 +
 .../teg-c1-sliceone-advisory-20260815.json         |     1 +
 .../receipts/test-harness-verification.json        |    20 +
 .../antigravity-inbox/receipts/test-round.json     |    22 +
 .../receipts/track-s-architecture-review.json      |    22 +
 .../teg-c1-sliceone-advisory-20260815.md           |    21 +
 .../aq-collaborate-contributions.jsonl             |     2 +
 .../collaboration/dashboard-revamp-screenshot.png  |   Bin 0 -> 177925 bytes
 .../integration-contracts/173-A--173-E.md          |    51 +
 .../herdr-h2-canonical-aq--operator-context.md     |   234 +
 ...dr-h2-herdr-observation--presentation-health.md |   201 +
 .../herdr-h2-human-controls--audited-aq-actions.md |   160 +
 ...dr-h2-operator-context--herdr-layout-planner.md |   141 +
 .../herdr-h2-operator-context--web-dashboard.md    |   151 +
 .../collaboration/tasks/seed-rag-execute-local.md  |    75 +
 .../collaboration/tasks/seed-rag-review-gemini.md  |    45 +
 .agent/comms/harness.py                            |     0
 .agent/comms/local-harness-proxy.py                |     0
 .agent/memory/issues-backlog.md                    |  3265 +++
 .agent/memory/local-insights-20260604.md           |    23 +
 .agent/memory/local-insights-20260607.md           |    23 +
 .agent/memory/qwen-insights-20260523.md            |    23 +
 .agent/phase173-PLAN-CONSOLIDATED.md               |   238 +
 .agent/phase173-PLAN-claude.md                     |   273 +
 .agent/phase173-PLAN-gemini.md                     |    87 +
 .agent/phase173-PRD-CONSOLIDATED.md                |   394 +
 .agent/phase173-PRD-claude.md                      |   245 +
 .agent/phase173-PRD-gemini.md                      |   109 +
 .agent/phase173-PRD-qwen3-proxy.md                 |   248 +
 .agent/phase175-PLAN-CONSOLIDATED.md               |   194 +
 .agent/phase175-PRD-CONSOLIDATED.md                |   236 +
 .agent/phase175-PRD-claude.md                      |   182 +
 .agent/phase175-PRD-gemini.md                      |    67 +
 .agent/phase175-PRD-qwen3.md                       |   101 +
 .../phase175-expert-review-agent-coordination.md   |   336 +
 .agent/phase175-expert-review-ai-research.md       |   468 +
 .agent/phase175-expert-review-cli-ux.md            |   409 +
 .agent/phase175-expert-review-inference.md         |   347 +
 .agent/phase175-switchboard-run-id-fix.md          |    55 +
 .agent/phase175a-implementation.md                 |    57 +
 .agent/phase175b-implementation.md                 |    49 +
 .agent/phase175c-implementation.md                 |    60 +
 .agent/proposals/proposal_0001.json                |    12 +
 .agent/proposals/proposals.json                    |    12 +
 .agent/python_skills/check_service_health/SKILL.md |    21 +
 .agent/python_skills/get_ai_service_logs/SKILL.md  |    17 +
 .agent/python_skills/get_ai_stack_status/SKILL.md  |    24 +
 .agent/python_skills/start_ai_service/SKILL.md     |    21 +
 .agent/python_skills/stop_ai_service/SKILL.md      |    21 +
 .agent/research/deepseek-harness-parity-2026-08.md |   144 +
 .agent/research/harness-parity-research-roadmap.md |    69 +
 .agent/roles/agent-roles.yaml                      |    93 +
 .agent/roles/architect.md                          |    15 +
 .agent/roles/implementer.md                        |    15 +
 .agent/roles/orchestrator.md                       |    39 +
 .agent/roles/reviewer.md                           |    15 +
 .agent/roles/sdet.md                               |    15 +
 .agent/roles/sre.md                                |    15 +
 .agent/security-scope-receipts/.gitignore          |     2 +
 .agent/skills/agent-tool-map/SKILL.md              |   114 +
 .agent/skills/ai-stack-qa/SKILL.md                 |   180 +
 .agent/skills/aidb-knowledge/SKILL.md              |   129 +
 .agent/skills/all-mcp-directory/SKILL.md           |   147 +
 .agent/skills/apparmor-rules/SKILL.md              |   214 +
 .agent/skills/aq-workflow/SKILL.md                 |   267 +
 .agent/skills/async-delegation/SKILL.md            |    24 +
 .../SKILL.md                                       |    34 +
 .../SKILL.md                                       |    34 +
 .agent/skills/brand-guidelines/LICENSE.txt         |   202 +
 .agent/skills/brand-guidelines/SKILL.md            |    77 +
 .agent/skills/canvas-design/LICENSE.txt            |   202 +
 .agent/skills/canvas-design/SKILL.md               |   140 +
 .../canvas-design/canvas-fonts/ArsenalSC-OFL.txt   |    93 +
 .../canvas-fonts/ArsenalSC-Regular.ttf             |   Bin 0 -> 165848 bytes
 .../canvas-fonts/BigShoulders-Bold.ttf             |   Bin 0 -> 94528 bytes
 .../canvas-fonts/BigShoulders-OFL.txt              |    93 +
 .../canvas-fonts/BigShoulders-Regular.ttf          |   Bin 0 -> 94396 bytes
 .../canvas-design/canvas-fonts/Boldonse-OFL.txt    |    93 +
 .../canvas-fonts/Boldonse-Regular.ttf              |   Bin 0 -> 77168 bytes
 .../canvas-fonts/BricolageGrotesque-Bold.ttf       |   Bin 0 -> 90952 bytes
 .../canvas-fonts/BricolageGrotesque-OFL.txt        |    93 +
 .../canvas-fonts/BricolageGrotesque-Regular.ttf    |   Bin 0 -> 90920 bytes
 .../canvas-design/canvas-fonts/CrimsonPro-Bold.ttf |   Bin 0 -> 107352 bytes
 .../canvas-fonts/CrimsonPro-Italic.ttf             |   Bin 0 -> 108828 bytes
 .../canvas-design/canvas-fonts/CrimsonPro-OFL.txt  |    93 +
 .../canvas-fonts/CrimsonPro-Regular.ttf            |   Bin 0 -> 106696 bytes
 .../canvas-design/canvas-fonts/DMMono-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/DMMono-Regular.ttf  |   Bin 0 -> 48852 bytes
 .../canvas-design/canvas-fonts/EricaOne-OFL.txt    |    94 +
 .../canvas-fonts/EricaOne-Regular.ttf              |   Bin 0 -> 24872 bytes
 .../canvas-design/canvas-fonts/GeistMono-Bold.ttf  |   Bin 0 -> 78304 bytes
 .../canvas-design/canvas-fonts/GeistMono-OFL.txt   |    93 +
 .../canvas-fonts/GeistMono-Regular.ttf             |   Bin 0 -> 78232 bytes
 .../canvas-design/canvas-fonts/Gloock-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Gloock-Regular.ttf  |   Bin 0 -> 95156 bytes
 .../canvas-fonts/IBMPlexMono-Bold.ttf              |   Bin 0 -> 136008 bytes
 .../canvas-design/canvas-fonts/IBMPlexMono-OFL.txt |    93 +
 .../canvas-fonts/IBMPlexMono-Regular.ttf           |   Bin 0 -> 133796 bytes
 .../canvas-fonts/IBMPlexSerif-Bold.ttf             |   Bin 0 -> 161000 bytes
 .../canvas-fonts/IBMPlexSerif-BoldItalic.ttf       |   Bin 0 -> 169840 bytes
 .../canvas-fonts/IBMPlexSerif-Italic.ttf           |   Bin 0 -> 170004 bytes
 .../canvas-fonts/IBMPlexSerif-Regular.ttf          |   Bin 0 -> 160380 bytes
 .../canvas-fonts/InstrumentSans-Bold.ttf           |   Bin 0 -> 68084 bytes
 .../canvas-fonts/InstrumentSans-BoldItalic.ttf     |   Bin 0 -> 70004 bytes
 .../canvas-fonts/InstrumentSans-Italic.ttf         |   Bin 0 -> 69900 bytes
 .../canvas-fonts/InstrumentSans-OFL.txt            |    93 +
 .../canvas-fonts/InstrumentSans-Regular.ttf        |   Bin 0 -> 68028 bytes
 .../canvas-fonts/InstrumentSerif-Italic.ttf        |   Bin 0 -> 70868 bytes
 .../canvas-fonts/InstrumentSerif-Regular.ttf       |   Bin 0 -> 69312 bytes
 .../canvas-design/canvas-fonts/Italiana-OFL.txt    |    93 +
 .../canvas-fonts/Italiana-Regular.ttf              |   Bin 0 -> 27184 bytes
 .../canvas-fonts/JetBrainsMono-Bold.ttf            |   Bin 0 -> 114828 bytes
 .../canvas-fonts/JetBrainsMono-OFL.txt             |    93 +
 .../canvas-fonts/JetBrainsMono-Regular.ttf         |   Bin 0 -> 114904 bytes
 .../canvas-design/canvas-fonts/Jura-Light.ttf      |   Bin 0 -> 154308 bytes
 .../canvas-design/canvas-fonts/Jura-Medium.ttf     |   Bin 0 -> 154488 bytes
 .../skills/canvas-design/canvas-fonts/Jura-OFL.txt |    93 +
 .../canvas-fonts/LibreBaskerville-OFL.txt          |    93 +
 .../canvas-fonts/LibreBaskerville-Regular.ttf      |   Bin 0 -> 147584 bytes
 .../canvas-design/canvas-fonts/Lora-Bold.ttf       |   Bin 0 -> 133828 bytes
 .../canvas-design/canvas-fonts/Lora-BoldItalic.ttf |   Bin 0 -> 140332 bytes
 .../canvas-design/canvas-fonts/Lora-Italic.ttf     |   Bin 0 -> 139328 bytes
 .../skills/canvas-design/canvas-fonts/Lora-OFL.txt |    93 +
 .../canvas-design/canvas-fonts/Lora-Regular.ttf    |   Bin 0 -> 133888 bytes
 .../canvas-fonts/NationalPark-Bold.ttf             |   Bin 0 -> 79208 bytes
 .../canvas-fonts/NationalPark-OFL.txt              |    93 +
 .../canvas-fonts/NationalPark-Regular.ttf          |   Bin 0 -> 76424 bytes
 .../canvas-fonts/NothingYouCouldDo-OFL.txt         |    93 +
 .../canvas-fonts/NothingYouCouldDo-Regular.ttf     |   Bin 0 -> 32020 bytes
 .../canvas-design/canvas-fonts/Outfit-Bold.ttf     |   Bin 0 -> 55392 bytes
 .../canvas-design/canvas-fonts/Outfit-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Outfit-Regular.ttf  |   Bin 0 -> 54912 bytes
 .../canvas-fonts/PixelifySans-Medium.ttf           |   Bin 0 -> 51072 bytes
 .../canvas-fonts/PixelifySans-OFL.txt              |    93 +
 .../canvas-design/canvas-fonts/PoiretOne-OFL.txt   |    93 +
 .../canvas-fonts/PoiretOne-Regular.ttf             |   Bin 0 -> 45244 bytes
 .../canvas-design/canvas-fonts/RedHatMono-Bold.ttf |   Bin 0 -> 34420 bytes
 .../canvas-design/canvas-fonts/RedHatMono-OFL.txt  |    93 +
 .../canvas-fonts/RedHatMono-Regular.ttf            |   Bin 0 -> 34488 bytes
 .../canvas-design/canvas-fonts/Silkscreen-OFL.txt  |    93 +
 .../canvas-fonts/Silkscreen-Regular.ttf            |   Bin 0 -> 31960 bytes
 .../canvas-fonts/SmoochSans-Medium.ttf             |   Bin 0 -> 59704 bytes
 .../canvas-design/canvas-fonts/SmoochSans-OFL.txt  |    93 +
 .../canvas-design/canvas-fonts/Tektur-Medium.ttf   |   Bin 0 -> 76248 bytes
 .../canvas-design/canvas-fonts/Tektur-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Tektur-Regular.ttf  |   Bin 0 -> 75604 bytes
 .../canvas-design/canvas-fonts/WorkSans-Bold.ttf   |   Bin 0 -> 191304 bytes
 .../canvas-fonts/WorkSans-BoldItalic.ttf           |   Bin 0 -> 175772 bytes
 .../canvas-design/canvas-fonts/WorkSans-Italic.ttf |   Bin 0 -> 174280 bytes
 .../canvas-design/canvas-fonts/WorkSans-OFL.txt    |    93 +
 .../canvas-fonts/WorkSans-Regular.ttf              |   Bin 0 -> 188916 bytes
 .../canvas-design/canvas-fonts/YoungSerif-OFL.txt  |    93 +
 .../canvas-fonts/YoungSerif-Regular.ttf            |   Bin 0 -> 105136 bytes
 .agent/skills/capability-intake/SKILL.md           |    57 +
 .agent/skills/context-efficiency/SKILL.md          |   177 +
 .agent/skills/coordinator-api/SKILL.md             |   169 +
 .agent/skills/debug-workflow/SKILL.md              |   156 +
 .agent/skills/domain-shells/SKILL.md               |   149 +
 .agent/skills/escalation-protocol/SKILL.md         |   143 +
 .agent/skills/finding-freshness/SKILL.md           |    51 +
 .agent/skills/flake-review/SKILL.md                |    22 +
 .agent/skills/frontend-design/LICENSE.txt          |   177 +
 .agent/skills/frontend-design/SKILL.md             |    56 +
 .agent/skills/health-monitoring/SKILL.md           |   107 +
 .agent/skills/impeccable/SKILL.md                  |   109 +
 .agent/skills/internal-comms/LICENSE.txt           |   202 +
 .agent/skills/internal-comms/SKILL.md              |    36 +
 .../skills/internal-comms/examples/3p-updates.md   |    47 +
 .../internal-comms/examples/company-newsletter.md  |    65 +
 .../skills/internal-comms/examples/faq-answers.md  |    30 +
 .../internal-comms/examples/general-comms.md       |    16 +
 .agent/skills/lean-ctx/SKILL.md                    |   149 +
 .agent/skills/lean-ctx/scripts/install.sh          |    95 +
 .agent/skills/llm-config/SKILL.md                  |   150 +
 .agent/skills/mcp-builder/LICENSE.txt              |   202 +
 .agent/skills/mcp-builder/SKILL.md                 |   258 +
 .agent/skills/mcp-builder/reference/evaluation.md  |   602 +
 .../mcp-builder/reference/mcp_best_practices.md    |   249 +
 .../mcp-builder/reference/node_mcp_server.md       |   970 +
 .../mcp-builder/reference/python_mcp_server.md     |   719 +
 .agent/skills/mcp-builder/scripts/connections.py   |   151 +
 .agent/skills/mcp-builder/scripts/evaluation.py    |   373 +
 .../mcp-builder/scripts/example_evaluation.xml     |    22 +
 .agent/skills/mcp-builder/scripts/requirements.txt |     2 +
 .agent/skills/mcp-server/SKILL.md                  |    88 +
 .agent/skills/minimal-code/SKILL.md                |    47 +
 .agent/skills/multi-agent-collab/SKILL.md          |   195 +
 .agent/skills/nixos-deployment/SKILL.md            |   549 +
 .agent/skills/nixos-system/SKILL.md                |   282 +
 .agent/skills/osint-systems/SKILL.md               |    58 +
 .agent/skills/pdf/LICENSE.txt                      |    30 +
 .agent/skills/pdf/SKILL.md                         |   298 +
 .agent/skills/pdf/forms.md                         |   205 +
 .agent/skills/pdf/reference.md                     |   612 +
 .agent/skills/pdf/scripts/check_bounding_boxes.py  |    70 +
 .../pdf/scripts/check_bounding_boxes_test.py       |   226 +
 .agent/skills/pdf/scripts/check_fillable_fields.py |    12 +
 .agent/skills/pdf/scripts/convert_pdf_to_images.py |    35 +
 .../skills/pdf/scripts/create_validation_image.py  |    41 +
 .../skills/pdf/scripts/extract_form_field_info.py  |   152 +
 .agent/skills/pdf/scripts/fill_fillable_fields.py  |   114 +
 .../pdf/scripts/fill_pdf_form_with_annotations.py  |   108 +
 .agent/skills/performance-profiler/SKILL.md        |   160 +
 .agent/skills/pptx/LICENSE.txt                     |    30 +
 .agent/skills/pptx/SKILL.md                        |   484 +
 .agent/skills/pptx/html2pptx.md                    |   625 +
 .agent/skills/pptx/ooxml.md                        |   427 +
 .../schemas/ISO-IEC29500-4_2016/dml-chart.xsd      |  1499 ++
 .../ISO-IEC29500-4_2016/dml-chartDrawing.xsd       |   146 +
 .../schemas/ISO-IEC29500-4_2016/dml-diagram.xsd    |  1085 +
 .../ISO-IEC29500-4_2016/dml-lockedCanvas.xsd       |    11 +
 .../ooxml/schemas/ISO-IEC29500-4_2016/dml-main.xsd |  3081 +++
 .../schemas/ISO-IEC29500-4_2016/dml-picture.xsd    |    23 +
 .../ISO-IEC29500-4_2016/dml-spreadsheetDrawing.xsd |   185 +
 .../dml-wordprocessingDrawing.xsd                  |   287 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/pml.xsd |  1676 ++
 .../shared-additionalCharacteristics.xsd           |    28 +
 .../ISO-IEC29500-4_2016/shared-bibliography.xsd    |   144 +
 .../shared-commonSimpleTypes.xsd                   |   174 +
 .../shared-customXmlDataProperties.xsd             |    25 +
 .../shared-customXmlSchemaProperties.xsd           |    18 +
 .../shared-documentPropertiesCustom.xsd            |    59 +
 .../shared-documentPropertiesExtended.xsd          |    56 +
 .../shared-documentPropertiesVariantTypes.xsd      |   195 +
 .../schemas/ISO-IEC29500-4_2016/shared-math.xsd    |   582 +
 .../shared-relationshipReference.xsd               |    25 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/sml.xsd |  4439 ++++
 .../ooxml/schemas/ISO-IEC29500-4_2016/vml-main.xsd |   570 +
 .../ISO-IEC29500-4_2016/vml-officeDrawing.xsd      |   509 +
 .../vml-presentationDrawing.xsd                    |    12 +
 .../ISO-IEC29500-4_2016/vml-spreadsheetDrawing.xsd |   108 +
 .../vml-wordprocessingDrawing.xsd                  |    96 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/wml.xsd |  3646 +++
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/xml.xsd |   116 +
 .../ecma/fouth-edition/opc-contentTypes.xsd        |    42 +
 .../ecma/fouth-edition/opc-coreProperties.xsd      |    50 +
 .../schemas/ecma/fouth-edition/opc-digSig.xsd      |    49 +
 .../ecma/fouth-edition/opc-relationships.xsd       |    33 +
 .agent/skills/pptx/ooxml/schemas/mce/mc.xsd        |    75 +
 .../pptx/ooxml/schemas/microsoft/wml-2010.xsd      |   560 +
 .../pptx/ooxml/schemas/microsoft/wml-2012.xsd      |    67 +
 .../pptx/ooxml/schemas/microsoft/wml-2018.xsd      |    14 +
 .../pptx/ooxml/schemas/microsoft/wml-cex-2018.xsd  |    20 +
 .../pptx/ooxml/schemas/microsoft/wml-cid-2016.xsd  |    13 +
 .../schemas/microsoft/wml-sdtdatahash-2020.xsd     |     4 +
 .../ooxml/schemas/microsoft/wml-symex-2015.xsd     |     8 +
 .agent/skills/pptx/ooxml/scripts/pack.py           |   159 +
 .agent/skills/pptx/ooxml/scripts/unpack.py         |    29 +
 .agent/skills/pptx/ooxml/scripts/validate.py       |    69 +
 .../pptx/ooxml/scripts/validation/__init__.py      |    15 +
 .../skills/pptx/ooxml/scripts/validation/base.py   |   951 +
 .../skills/pptx/ooxml/scripts/validation/docx.py   |   274 +
 .../skills/pptx/ooxml/scripts/validation/pptx.py   |   315 +
 .../pptx/ooxml/scripts/validation/redlining.py     |   279 +
 .agent/skills/pptx/scripts/html2pptx.js            |   979 +
 .agent/skills/pptx/scripts/inventory.py            |  1020 +
 .agent/skills/pptx/scripts/rearrange.py            |   231 +
 .agent/skills/pptx/scripts/replace.py              |   385 +
 .agent/skills/pptx/scripts/thumbnail.py            |   450 +
 .agent/skills/project-import/SKILL.md              |    66 +
 .../provider-request-error-recovery/SKILL.md       |    71 +
 .agent/skills/prsi-review/SKILL.md                 |    23 +
 .agent/skills/python-async/SKILL.md                |   174 +
 .agent/skills/rag-operations/SKILL.md              |   151 +
 .agent/skills/rag-techniques/SKILL.md              |    91 +
 .agent/skills/reviewer-gate/SKILL.md               |   174 +
 .agent/skills/role-contracts/SKILL.md              |   126 +
 .agent/skills/rust-ecosystem/SKILL.md              |    50 +
 .agent/skills/security-audit/SKILL.md              |    21 +
 .agent/skills/security-scanner/SKILL.md            |   180 +
 .agent/skills/self-improvement/SKILL.md            |   175 +
 .agent/skills/skill-creator/LICENSE.txt            |   202 +
 .agent/skills/skill-creator/SKILL.md               |   373 +
 .../skill-creator/references/output-patterns.md    |    82 +
 .../skills/skill-creator/references/workflows.md   |    28 +
 .agent/skills/skill-creator/scripts/init_skill.py  |   303 +
 .../skills/skill-creator/scripts/package_skill.py  |   110 +
 .../skills/skill-creator/scripts/quick_validate.py |    95 +
 .agent/skills/slack-gif-creator/LICENSE.txt        |   202 +
 .agent/skills/slack-gif-creator/SKILL.md           |   254 +
 .../slack-gif-creator/core/color_palettes.py       |   302 +
 .agent/skills/slack-gif-creator/core/easing.py     |   234 +
 .../slack-gif-creator/core/frame_composer.py       |   176 +
 .../skills/slack-gif-creator/core/gif_builder.py   |   269 +
 .agent/skills/slack-gif-creator/core/typography.py |   357 +
 .agent/skills/slack-gif-creator/core/validators.py |   136 +
 .../slack-gif-creator/core/visual_effects.py       |   494 +
 .agent/skills/slack-gif-creator/requirements.txt   |     4 +
 .../skills/slack-gif-creator/templates/bounce.py   |   106 +
 .../skills/slack-gif-creator/templates/explode.py  |   331 +
 .agent/skills/slack-gif-creator/templates/fade.py  |   329 +
 .agent/skills/slack-gif-creator/templates/flip.py  |   291 +
 .../slack-gif-creator/templates/kaleidoscope.py    |   211 +
 .agent/skills/slack-gif-creator/templates/morph.py |   329 +
 .agent/skills/slack-gif-creator/templates/move.py  |   293 +
 .agent/skills/slack-gif-creator/templates/pulse.py |   268 +
 .agent/skills/slack-gif-creator/templates/shake.py |   127 +
 .agent/skills/slack-gif-creator/templates/slide.py |   291 +
 .agent/skills/slack-gif-creator/templates/spin.py  |   269 +
 .../skills/slack-gif-creator/templates/wiggle.py   |   300 +
 .agent/skills/slack-gif-creator/templates/zoom.py  |   312 +
 .agent/skills/slice-authoring/SKILL.md             |   161 +
 .agent/skills/strict-json-output-contract/SKILL.md |   104 +
 .agent/skills/system-dev/SKILL.md                  |   233 +
 .agent/skills/system-recovery/SKILL.md             |    23 +
 .agent/skills/system_bootstrap/SKILL.md            |    54 +
 .agent/skills/t3mp3st-intake/SKILL.md              |    50 +
 .agent/skills/task-eligibility/SKILL.md            |   149 +
 .agent/skills/template-skill/SKILL.md              |    10 +
 .agent/skills/test-remediation/SKILL.md            |    24 +
 .agent/skills/testing-patterns/SKILL.md            |   216 +
 .agent/skills/theme-factory/LICENSE.txt            |   202 +
 .agent/skills/theme-factory/SKILL.md               |    63 +
 .agent/skills/theme-factory/theme-showcase.pdf     |   Bin 0 -> 124310 bytes
 .agent/skills/theme-factory/themes/arctic-frost.md |    19 +
 .../theme-factory/themes/botanical-garden.md       |    19 +
 .agent/skills/theme-factory/themes/desert-rose.md  |    19 +
 .../skills/theme-factory/themes/forest-canopy.md   |    19 +
 .agent/skills/theme-factory/themes/golden-hour.md  |    19 +
 .../skills/theme-factory/themes/midnight-galaxy.md |    19 +
 .../theme-factory/themes/modern-minimalist.md      |    19 +
 .agent/skills/theme-factory/themes/ocean-depths.md |    19 +
 .../theme-factory/themes/sunset-boulevard.md       |    19 +
 .../skills/theme-factory/themes/tech-innovation.md |    19 +
 .agent/skills/tradingagents/SKILL.md               |   139 +
 .agent/skills/understand-anything/SKILL.md         |    97 +
 .agent/skills/web-artifacts-builder/LICENSE.txt    |   202 +
 .agent/skills/web-artifacts-builder/SKILL.md       |    74 +
 .../scripts/bundle-artifact.sh                     |    54 +
 .../web-artifacts-builder/scripts/init-artifact.sh |   322 +
 .../scripts/shadcn-components.tar.gz               |   Bin 0 -> 19967 bytes
 .agent/skills/webapp-testing/LICENSE.txt           |   202 +
 .agent/skills/webapp-testing/SKILL.md              |   116 +
 .../webapp-testing/examples/console_logging.py     |    35 +
 .../webapp-testing/examples/dashboard_smoke.py     |    68 +
 .../webapp-testing/examples/element_discovery.py   |    40 +
 .../examples/static_html_automation.py             |    33 +
 .../skills/webapp-testing/scripts/with_server.py   |   106 +
 .agent/skills/wiki-navigation/SKILL.md             |   117 +
 .agent/skills/xlsx/LICENSE.txt                     |    30 +
 .agent/skills/xlsx/SKILL.md                        |   292 +
 .agent/skills/xlsx/recalc.py                       |   178 +
 .agent/tool-parity-contract.json                   |    23 +
 .../workflows/IMPLEMENTATION-STATUS-2026-04-09.md  |   427 +
 .agent/workflows/PHASE-3-COMPLETION-2026-04-14.md  |   263 +
 .agent/workflows/ROADMAP-PROGRESS-2026-04-11.md    |   395 +
 .agent/workflows/advisor-strategy-design.md        |   383 +
 ...harness-comprehensive-analysis-v2-2026-04-09.md |   905 +
 .../ai-harness-parity-analysis-2026-04-09.md       |   980 +
 .agent/workflows/aq-collaborate-api-fix.md         |    39 +
 .agent/workflows/brownfield-PDR-20260309-002320.md |    51 +
 .agent/workflows/brownfield-PDR-20260406-221711.md |    51 +
 .agent/workflows/brownfield-PDR-20260407-034035.md |    51 +
 .agent/workflows/brownfield-PDR-20260419-021048.md |    51 +
 .agent/workflows/brownfield-PDR-20260419-024534.md |    51 +
 .agent/workflows/brownfield-PDR-20260419-030703.md |   107 +
 .agent/workflows/brownfield-PDR-20260419-160730.md |    51 +
 .agent/workflows/brownfield-PDR-20260419-190535.md |    51 +
 .agent/workflows/brownfield-PDR-20260424-212610.md |    51 +
 .../harness-optimization-prompt-2026-04-09.md      |   152 +
 .../openrouter-config-status-2026-04-09.md         |   101 +
 .../baseline_20260409_215323.json                  |  1036 +
 .../baseline_20260409_215323.txt                   |   193 +
 .../baseline_20260409_215600.json                  |  1036 +
 .../baseline_20260409_215600.txt                   |   193 +
 .../baseline_20260409_215726.json                  |  1036 +
 .../baseline_20260409_215726.txt                   |   193 +
 .../optimized_20260409_215903.json                 |   982 +
 .../optimized_20260409_215903.txt                  |   186 +
 .../performance-optimization-2026-04-18.md         |   197 +
 .agent/workflows/phase-12-delegation-diagnosis.md  |   194 +
 .../phase-2-completion-report-2026-04-16.md        |   553 +
 .../phase-2-status-assessment-2026-04-14.md        |   321 +
 .agent/workflows/session-primer-summary.json       |    22 +
 .agent/workflows/session-summary-2026-04-09.md     |   329 +
 .../ui-ux-completeness-analysis-2026-04-09.md      |   690 +
 .agents/AUTONOMOUS-AGENT-HANDOFF-PROMPT.md         |   486 +
 .agents/AUTONOMOUS-AGENT-SECURITY-POLICY.md        |   273 +
 .agents/AUTONOMOUS-WORKFLOW-COORDINATOR-PROMPT.md  |   582 +
 .agents/LOCAL-AGENT-CLI-COORDINATOR-PROMPT.md      |   627 +
 .agents/README.md                                  |    21 +
 .../2026-05-13-layer-aware-validation.md           |    32 +
 .../20260531-plans/ARCH-REVAMP-IMPL-CONTRACT.md    |   256 +
 .agents/archive/20260531-plans/ARCH-REVAMP-PRD.md  |   771 +
 .../PHASE-60-ECOSYSTEM-INTEGRATION-PRD.md          |   359 +
 .../PHASE-64-67-AIOS-ELEVATION-PRD.md              |   139 +
 .../PHASE-68-70-AIOS-CONTINUITY-PRD.md             |   134 +
 .../archive/20260531-plans/PHASE-86-HITL-DESIGN.md |    98 +
 .agents/archive/20260531-plans/PHASE-B2-FILEMAP.md |   186 +
 .../PROJECT-AI-HARNESS-EVOLUTION-PRD.md            |   254 +
 .../20260531-plans/PROJECT-PAEA-UPDATE-PLAN-V2.md  |    51 +
 .../PROJECT-PAEA-UPDATE-PLAN-V3-1.md               |    51 +
 .../20260531-plans/PROJECT-PAEA-UPDATE-PLAN-V3.md  |    51 +
 .../20260531-plans/PROJECT-PAEA-UPDATE-PLAN.md     |    52 +
 .../PROJECT-PHASE87-88-STABILIZATION-PRD.md        |   137 +
 .../PROJECT-PHASE89-LEARNING-LOOP-MATURITY-PRD.md  |   115 +
 ...PROJECT-PHASE90-DELEGATION-OBSERVABILITY-PRD.md |    67 +
 .../20260531-plans/SYSTEM-ASSESSMENT-FIX-PRD.md    |   230 +
 .../20260531-plans/arch-review-codex-findings.md   |   331 +
 .../20260531-plans/config-centralization/PLAN.md   |   290 +
 .../local-model-ops-improvement/SHARED-BRIEF.md    |   108 +
 .../AGENT-PARITY-REVIEW.md                         |   115 +
 .../multi-agent-edge-harness/COMBINED-PRD.md       |   618 +
 .../EXTERNAL-PARITY-AMENDMENTS.md                  |   228 +
 .../LIVE-VALIDATION-RUNBOOK.md                     |   152 +
 .../MAEAH-SECURITY-CONTRACT-GATES.md               |   149 +
 .../PARITY-INTEGRATION-PLAN.md                     |   158 +
 .../PHASE-A-ACCEPTANCE-CRITERIA.md                 |   108 +
 .../multi-agent-edge-harness/PLAN-SIGNOFF.md       |   160 +
 .../multi-agent-edge-harness/PRD-CTO-CLAUDE.md     |   403 +
 .../multi-agent-edge-harness/PRD-EDGE-AI-QWEN.md   |   490 +
 .../PRD-STAFF-ENG-CODEX.md                         |  1048 +
 .../multi-agent-edge-harness/PRD-VP-ENG-GEMINI.md  |   117 +
 .../QWEN-ITEMS-CODEX-FINDINGS.md                   |    34 +
 .../QWEN-ITEMS-GEMINI-FINDINGS.md                  |    39 +
 .../multi-agent-edge-harness/RESEARCH-FINDINGS.md  |   413 +
 .../multi-agent-edge-harness/SHARED-GOALS-BRIEF.md |   145 +
 .../multi-agent-edge-harness/SIGNOFF-CODEX.md      |    54 +
 .../multi-agent-edge-harness/SIGNOFF-GEMINI.md     |    31 +
 .../SYSTEM-COMPARISON-PLAN.md                      |   563 +
 .../phase-08-delegation-memory-latency.md          |   175 +
 ...hase-09-intent-contract-openrouter-hardening.md |   154 +
 .../20260531-plans/phase-1-systemd-env-quoting.md  |    23 +
 ...e-10-post-rebuild-validation-gap-remediation.md |   137 +
 ...se-11-http-server-decomposition-remote-burst.md |   327 +
 .../20260531-plans/phase-12-reliability-first.md   |   235 +
 .../phase-13-memory-systems-maturity.md            |   281 +
 .../20260531-plans/phase-16-identity-kernel.md     |   252 +
 .../phase-17-closed-loop-improver.md               |   245 +
 .../phase-18-agent-mesh-collective-memory.md       |   217 +
 .../20260531-plans/phase-19-values-signals.md      |   279 +
 .../phase-20-world-model-predictive.md             |   256 +
 .../phase-21-operational-hardening.md              |   194 +
 .../phase-22-eval-recovery-fleet-resilience.md     |   190 +
 .../phase-23-system-polish-and-coverage.md         |   120 +
 .../phase-24-external-framework-integration.md     |   230 +
 .../phase-25-system-hardening-brainstem.md         |   265 +
 .../phase-26-unified-orchestration-gateway.md      |   168 +
 .../phase-27-ide-agent-state-stability.md          |    93 +
 .../phase-28-guarded-execution-safety-gating.md    |   157 +
 .../phase-29-feedback-driven-agent-loop.md         |    66 +
 ...-operational-introspection-and-cli-execution.md |   114 +
 .../phase-31-agent-workflow-parity.md              |    61 +
 .../phase-32-local-agent-coding-loop.md            |    69 +
 .../phase-34-dashboard-eval-recovery.md            |    79 +
 .../20260531-plans/phase-36-audit-integrity.md     |    37 +
 .../phase-37-cli-tool-access-restoration.md        |    37 +
 .../phase-52-logic-error-discovery-and-diagrams.md |   122 +
 .../phase-53-command-center-card-inventory.md      |   268 +
 .../phase-53-command-center-dashboard-revamp.md    |    72 +
 .../phase-54-agentic-first-elevation.md            |   255 +
 ...hase-55-temporal-memory-crystalline-agentops.md |   201 +
 .../phase-56-harness-integration-loop.md           |   449 +
 .../phase-58-capability-expansion-foundation.md    |    86 +
 .../20260531-plans/phase-58-remediation-2.md       |    24 +
 .../phase-58a-agent-tool-contract.md               |    56 +
 .../phase-58a-architecture-review-brief.md         |   127 +
 .../phase-58a-canonical-kernel-declaration.md      |    60 +
 .../phase-58a-capability-expansion-team-plan.md    |   213 +
 .../phase-58a-capability-lifecycle.md              |    36 +
 .../phase-58a-codex-foundation-plan.md             |   105 +
 .../20260531-plans/phase-58a-domain-activation.md  |    26 +
 .../20260531-plans/phase-58a-gemini-review-gate.md |    31 +
 .../phase-58a-instruction-projections.md           |    49 +
 .../20260531-plans/phase-58a-qwen-eligibility.md   |    28 +
 .../20260531-plans/phase-58a-role-matrix.md        |    63 +
 .../phase-58a-routing-profile-inventory.md         |    58 +
 .../20260531-plans/phase-58b-candidate-soak-log.md |    44 +
 .../phase-58b-default-routing-decision.md          |    40 +
 .../phase-58b-domain-prd-reconciliation.md         |    33 +
 .../phase-58b-domain-validation-evidence.md        |    50 +
 .../phase-58b-domain-validation-workflows.md       |    59 +
 .../phase-58b-post-rebuild-soak-log.md             |    24 +
 .../phase-58b-real-use-adoption-log.md             |    66 +
 .../20260531-plans/phase-58b-review-package.md     |    80 +
 .../phase-58b-routing-and-mobile-web-hardening.md  |    40 +
 .../phase-59-logical-orphan-triage.md              |    39 +
 .../phase-59-progressive-disclosure-docs.md        |    43 +
 .../phase-60-aq-chat-local-tool-profile.md         |    20 +
 .../phase-60-capability-expansion.md               |    32 +
 .../phase-60-context-warmer-local-slot.md          |    34 +
 .../phase-60-local-agent-analysis-completion.md    |    31 +
 .../phase-60-osint-tools-activation.md             |    28 +
 .../20260531-plans/phase-60-tool-lease-broker.md   |    23 +
 .../20260531-plans/phase-83-dag-context-wiring.md  |    81 +
 .../archive/20260531-plans/phase-b-accelerate.md   |    68 +
 .../phase-b2-duplicate-resolution.md               |   235 +
 .../20260531-plans/phase-b3-migration-plan.md      |    51 +
 .../phase-system-stability-recovery-slice-1.md     |    34 +
 .../phase-system-stability-recovery-slice-2.md     |    29 +
 .../phase-system-stability-recovery-slice-3.md     |    28 +
 .../phase-system-stability-recovery-slice-4.md     |    27 +
 .../phase-system-stability-recovery-slice-5.md     |    26 +
 .agents/archive/20260531-plans/phase-template.md   |    29 +
 .../20260531-plans/system-reset-plan-2026-05.md    |   119 +
 ...lice-103-cross-agent-contradiction-detection.md |    35 +
 .../slice-93-15-dashboard-agent-observability.md   |    33 +
 .../slice-93-5-useful-token-instrumentation.md     |    34 +
 .agents/archive/20260707-zero-research             |     1 +
 .agents/archive/c02-recovery-20260711/README.md    |    11 +
 .../evidence_algebra.rejected.py.txt               |   229 +
 .../qa_evidence_store.rejected.py.txt              |   278 +
 .../rejected-implementation.patch                  |  1266 ++
 .../telemetry-symlink.metadata.json                |    18 +
 .../c02-recovery-20260711/test-evidence-algebra.py |   206 +
 .../test-evidence-algebra.rejected-v2.py.txt       |   142 +
 .../test-qa-evidence-store.py                      |   200 +
 .../test-qa-evidence-store.rejected-v2.py.txt      |   147 +
 .../prd-consensus-local.md                         |    22 +
 .agents/bench/llama/PROMOTED                       |     9 +
 .agents/delegation/streams/aq-1783464775.txt       |     1 +
 .agents/delegation/streams/aq-1783468502.txt       |     3 +
 .agents/delegation/streams/aq-1783470479.txt       |     6 +
 .agents/delegation/streams/aq-1783482520.txt       |     3 +
 .agents/delegation/streams/aq-1783490813.txt       |     5 +
 .agents/delegation/streams/aq-1783493023.txt       |     1 +
 .agents/delegation/streams/aq-1783573820.txt       |     1 +
 .agents/delegation/streams/aq-1783577799.txt       |     1 +
 .agents/delegation/streams/aq-1783580040.txt       |     1 +
 .agents/delegation/streams/aq-1783581271.txt       |     3 +
 .agents/delegation/streams/aq-1783597361.txt       |     1 +
 .../designs/MODEL-INTEGRITY-CAPABILITY-GUARD.md    |   273 +
 .agents/designs/OPERATOR-INTELLIGENCE-BRIDGE.md    |   315 +
 .agents/drops/.gitkeep                             |     0
 .agents/drops/archive/.gitkeep                     |     0
 .agents/drops/failed/.gitkeep                      |     0
 .agents/fine-tuning/dataset.jsonl                  |     6 +
 .agents/governance/evidence-failed-qa-report.json  |    60 +
 .agents/governance/evidence-invalid-round.json     |    78 +
 .../planning/designs/context-mode-integration.md   |   382 +
 .../planning/designs/intelligent-agent-routing.md  |   577 +
 .../designs/unified-deploy-cli-architecture.md     |   546 +
 .../high-value-improvements-plan-2026-04-19.md     |   594 +
 .../plans/AI-STACK-SELF-IMPROVEMENT-ROADMAP.md     |   400 +
 .../plans/ALERT-NOTIFICATION-SYSTEM-DESIGN.md      |  1097 +
 .../AUTONOMOUS-AGENTIC-ORCHESTRATION-DESIGN.md     |   730 +
 .../plans/CONTEXT-ROT-AND-RECALL-DESIGN.md         |   390 +
 .agents/planning/plans/DELEGATION-QUEUE.md         |   100 +
 ...PLOYMENT-OPTIMIZATION-IMPLEMENTATION-SUMMARY.md |   389 +
 .../LOCAL-AGENT-AGENTIC-CAPABILITIES-DESIGN.md     |   476 +
 .../planning/plans/MASTER-ROADMAP-2026-04-09.md    |   894 +
 .../plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md      |  1092 +
 .../plans/PARALLEL-EXECUTION-PLAN-2026-03.md       |   367 +
 .../planning/plans/PHASE-1-BATCH-1.2-COMPLETION.md |   255 +
 .../plans/PHASE-1-MONITORING-IMPLEMENTATION.md     |   735 +
 .../plans/PHASE-11-BATCH-11.1-COMPLETION.md        |   318 +
 .../plans/PHASE-11-BATCH-11.2-COMPLETION.md        |   251 +
 .../plans/PHASE-11-BATCH-11.3-COMPLETION.md        |   292 +
 .../plans/PHASE-11-BATCH-11.4-COMPLETION.md        |    83 +
 .../plans/PHASE-11-BATCH-11.5-COMPLETION.md        |   231 +
 .../plans/PHASE-11-BATCH-11.6-COMPLETION.md        |   432 +
 .../PHASE-4-5-COMPLETION-ROADMAP-2026-03-30.md     |   257 +
 .../planning/plans/PHASE-4.2-DELIVERY-MANIFEST.md  |   507 +
 .../plans/PHASE-4.2-IMPLEMENTATION-SUMMARY.md      |   483 +
 .../planning/plans/PHASE-4.2-QUICK-REFERENCE.md    |   416 +
 .../plans/PHASE-5.2-IMPLEMENTATION-SUMMARY.md      |   595 +
 .../plans/PRE-DEPLOY-SUMMARY-2026-03-31.md         |   118 +
 .../plans/PROJECT-CLEANUP-EXECUTION-PASS.md        |   429 +
 .agents/planning/plans/README.md                   |    18 +
 .../plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md     |   990 +
 .../planning/plans/SYSTEM-FINALIZATION-ROADMAP.md  |   671 +
 .../plans/SYSTEM-IMPROVEMENT-ROADMAP-2026-03.md    |  1198 +
 .../plans/ai-harness-enhancement-roadmap.md        |  1629 ++
 .../deployment-performance-optimization-2026-03.md |  1300 ++
 .../plans/phase-1-slice-1.5-benchmark-harness.md   |   330 +
 .../plans/phase-1-slice-1.6-documentation.md       |   414 +
 .../plans/phase-2-slice-2.1-workflow-dsl-design.md |   634 +
 ...hase-2-slice-2.2-parser-validator-delegation.md |   621 +
 .../plans/phase-2-slice-2.3-executor-delegation.md |   963 +
 .../phase-2-slice-2.4-coordinator-delegation.md    |   704 +
 .../phase-2-slice-2.5-templates-delegation.md      |   568 +
 .agents/planning/plans/phase-2-workflow-engine.md  |   517 +
 .../plans/phase-2.4-coordinator-integration.md     |   427 +
 .../plans/phase-4.5-implementation-complete.md     |   531 +
 .agents/planning/plans/phase-template.md           |    29 +
 .../plans/test-coverage-expansion-2026-03.md       |   995 +
 .../plans/test-specifications-phase-6.3.md         |  1296 ++
 .agents/planning/qwen-36-switch-recovery-plan.md   |   237 +
 .../research/mcp-signed-components-2026-03.md      |    96 +
 .agents/planning/system-maintenance-2026-04-19.md  |   341 +
 ...FFECTIVENESS-CENTERED-SYSTEM-IMPROVEMENT-PRD.md |   425 +
 .../plans/OBSERVABILITY-PARITY-CONSENSUS-REVIEW.md |    86 +
 .agents/plans/OBSERVABILITY-PARITY-PLAN.md         |    46 +
 .agents/plans/PHASE-150-IMPLEMENTATION-PLAN.md     |    70 +
 .agents/plans/README.md                            |    54 +
 .agents/plans/RUST-REFACTOR-TEAM-COLAB.md          |    52 +
 .agents/plans/TECHNICAL-ANALYSIS-PRD.md            |   170 +
 .agents/plans/UNIFIED-PROGRAM-PLAN.md              |   171 +
 ...LD_CLASS_SOFTWARE_FACTORY_READINESS_RESEARCH.md |   225 +
 .agents/plans/agent-agnostic-factory/DESIGN.md     |    76 +
 .../DISPATCH-INTEGRATION-ACCEPTANCE.md             |    68 +
 .../DISPATCH-INTEGRATION-DESIGN.md                 |   139 +
 .../DISPATCH-INTEGRATION-REVIEW-BRIEF.md           |    80 +
 .../Q5-LANE-ELIGIBILITY-REGISTRY-DESIGN.md         |    81 +
 .../RECLAIM-TOCTOU-ACCEPTANCE.md                   |    56 +
 .../ROUTER-CORE-ACCEPTANCE.md                      |   157 +
 .../C0-DESIGN-PACKET.md                            |    76 +
 .../C0.5-DESIGN-PACKET.md                          |   202 +
 .../C0.5B-DESIGN-PACKET.md                         |   304 +
 .../C0.6-CODEX-DESIGN-REVIEW.md                    |    67 +
 .../C0.6-LOCAL-DIRECT-DEADLINE-DESIGN-PACKET.md    |   481 +
 .../C0.6-T-AM2-AUTHORIZATION-REVISION-REVIEW.md    |    98 +
 .../C0.6-T-AM3-AUTHORIZATION-REVIEW.md             |    98 +
 .../C0.6-T-AM3-CANDIDATE-ACCEPTANCE.md             |   116 +
 .../C0.6-T-AM4-AUTHORIZATION-REVIEW.md             |   107 +
 .../C0.6-T-AM4-CANDIDATE-REVISION.md               |   180 +
 .../C0.6-T-AM5-AUTHORIZATION-REVIEW.md             |   112 +
 .../C0.6-T-AM5-CANDIDATE-ACCEPTANCE.md             |   124 +
 .../C0.6-T-AM5-CANDIDATE-REVISION.md               |   160 +
 .../C0.6-T-AM6-AUTHORIZATION-REVIEW.md             |   107 +
 .../C0.6-T-AM6-CANDIDATE-REVISION.md               |   224 +
 .../C0.6-T-AM7-CANDIDATE-ACCEPTANCE.md             |    39 +
 .../C0.6-T-AM7-CANDIDATE-REVISION.md               |   237 +
 .../C0.6-T-AM8-ACTIVATION.md                       |    17 +
 .../C0.6-T-AM8-CANDIDATE-ACCEPTANCE.md             |    30 +
 .../C0.6-T-AM8-CANDIDATE-REVISION.md               |    52 +
 .../C0.6-T-AM9-CANDIDATE-REVISION.md               |    58 +
 .../C0.6-T-AUTHORIZATION-REVIEW.md                 |    83 +
 .../C0.6-T-AUTHORIZATION-REVISION-REVIEW.md        |    89 +
 .../C0.6-T-IMPLEMENTATION-AUTHORIZATION-AM3.md     |   100 +
 .../C0.6-T-IMPLEMENTATION-AUTHORIZATION-AM4.md     |   156 +
 .../C0.6-T-IMPLEMENTATION-AUTHORIZATION-AM5.md     |   105 +
 .../C0.6-T-IMPLEMENTATION-AUTHORIZATION-AM6.md     |   141 +
 .../C0.6-T-IMPLEMENTATION-AUTHORIZATION-AM7.md     |   180 +
 .../C0.6-T-IMPLEMENTATION-AUTHORIZATION-AM8.md     |    31 +
 ...TION-AUTHORIZATION-AM9-REACTIVATION-20260729.md |    50 +
 .../C0.6-T-IMPLEMENTATION-AUTHORIZATION-AM9.md     |    21 +
 .../C0.6-T-IMPLEMENTATION-AUTHORIZATION.md         |   181 +
 .../C0.6-T-TELEMETRY-DESIGN-PACKET.md              |   332 +
 .../IMPLEMENTATION-AUTHORIZATION-C0-AMENDMENT-1.md |    39 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.5A-AM1.md      |    28 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.5A-AM2.md      |    36 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.5A.md          |    82 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.5B-AM1.md      |    21 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.5B.md          |    33 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.md             |    77 +
 .../IMPLEMENTATION-AUTHORIZATION-R0.1-AM1.md       |    84 +
 .../IMPLEMENTATION-AUTHORIZATION-R0.1-AM2.md       |    78 +
 .../IMPLEMENTATION-AUTHORIZATION-R0.1-AM3.md       |    62 +
 .../IMPLEMENTATION-AUTHORIZATION-R0.1-AM4.md       |    55 +
 .../IMPLEMENTATION-AUTHORIZATION-R0.1.md           |    60 +
 .../agent-connection-reliability/PROGRAM-PLAN.md   |   122 +
 .../R0.1-AM1-AUTHORIZATION-REVIEW.md               |    93 +
 .../R0.1-AM2-AUTHORIZATION-REVIEW.md               |   126 +
 .../R0.1-AM3-AUTHORIZATION-REVIEW.md               |    23 +
 .../R0.1-AM4-ACCEPTANCE.md                         |    43 +
 .../R0.1-AM4-AUTHORIZATION-REVIEW.md               |    22 +
 .../R0.1-DESIGN-REVIEW.md                          |    27 +
 ...-LEGACY-REGISTRY-LOOKUP-COMPAT-DESIGN-PACKET.md |   334 +
 .../R0.1-PARTIAL-CANDIDATE-AUDIT.md                |    71 +
 .../R0.1-WEB-VISIBILITY-AMENDMENT-DESIGN-PACKET.md |   282 +
 .../R0.1-WEB-VISIBILITY-DESIGN-REVIEW.md           |    36 +
 ...IER0-STAGED-ISOLATION-AM3-BINDING-ACCEPTANCE.md |    96 +
 .../antigravity-c0-acceptance.md                   |    54 +
 .../antigravity-c0-design-review.md                |    43 +
 .../antigravity-c0.5-design-review.md              |    58 +
 .../antigravity-c0.5a-acceptance.md                |    36 +
 .../antigravity-c0.6-design-review.md              |    57 +
 .../codex-c0.5b-acceptance-am1.md                  |    23 +
 .../codex-c0.5b-acceptance-r1.md                   |    29 +
 .../codex-c0.6-design-review-r1.md                 |    18 +
 .../codex-c0.6-design-review-r2.md                 |    25 +
 .../fable-c0.5-design-review.md                    |    29 +
 .../sonnet-c0.5b-design-review.md                  |    27 +
 .../sonnet-c0.6-design-review-unavailable.md       |    10 +
 .../C1A-CANDIDATE-ACCEPTANCE.md                    |    50 +
 .../agent-model-config-parity/C1B-DESIGN-PACKET.md |    71 +
 .../agent-model-config-parity/PROGRAM-PLAN.md      |    51 +
 .../antigravity-c1a-acceptance.md                  |    40 +
 .../antigravity-design-input.md                    |   121 +
 .../.plan-lifecycle.json                           |     8 +
 .../FABLE-ROUTING-BOOTSTRAP-AUTHORIZATION.md       |    34 +
 .../IMPLEMENTATION-AUTHORIZATION-M1.md             |    83 +
 .../IMPLEMENTATION-AUTHORIZATION-M2A-AM1.md        |    71 +
 ...-AUTHORIZATION-M2A-READ-ONLY-SHOW-HOTFIX-AM1.md |    19 +
 ...TION-AUTHORIZATION-M2A-READ-ONLY-SHOW-HOTFIX.md |    12 +
 .../IMPLEMENTATION-AUTHORIZATION-M2A.md            |    86 +
 .../M1-IMPLEMENTATION-PACKET.md                    |    73 +
 .../agent-ops-traceability-r0m/M2-DESIGN-PACKET.md |   207 +
 .../M2A-INVENTORY-AMENDMENT-1.md                   |    67 +
 .../M2A-READ-ONLY-SHOW-HOTFIX-DESIGN.md            |    34 +
 .../M2B-DESIGN-PACKET.md                           |   225 +
 .../M2B-DESIGN-REVIEW-AGGREGATE.md                 |    43 +
 ...tigravity-fable-routing-bootstrap-acceptance.md |    53 +
 ...gravity-fable-routing-bootstrap-hash-refresh.md |    31 +
 .../antigravity-m0-acceptance.md                   |    69 +
 .../antigravity-m1-acceptance.md                   |    61 +
 .../antigravity-m1-design-review.md                |    57 +
 .../antigravity-m2-design-review.md                |    77 +
 .../antigravity-m2-rev3-review.md                  |    43 +
 .../antigravity-m2a-am1-acceptance.md              |    63 +
 ...antigravity-m2a-inventory-amendment-1-review.md |    51 +
 .../antigravity-m2b-design-review.md               |    49 +
 .../antigravity-m2b-rev4-review.md                 |    40 +
 .../agent-ops-traceability-r0m/antigravity.md      |    54 +
 .../claude-fable-m2-rev3-review.md                 |    29 +
 .../codex-m2b-design-review.md                     |    58 +
 .../sonnet-m2a-read-only-show-hotfix-acceptance.md |    30 +
 .agents/plans/ai-capability-backlog.md             |    21 +
 .agents/plans/ai-repo-discovery-catalog.md         |    20 +
 .../A0-DESIGN-PACKET.md                            |   175 +
 .../A1-SERVICE-COVERAGE-DESIGN.md                  |    97 +
 .../plans/antigravity-lane-restoration/DESIGN.md   |   313 +
 .../ROUTING-CONSOLIDATION-SPEC.md                  |    56 +
 .../ROUTING-FIX-PROPOSAL.md                        |    71 +
 .../antigravity-routing-honesty-accept/README.md   |    14 +
 .../antigravity.md                                 |    42 +
 .../antigravity-routing-honesty-accept/round.json  |    73 +
 .../approval-control-plane/ACP-DEPLOY-20260817.md  |    33 +
 .../ACP-P0-DESIGN-20260816.md                      |   152 +
 .../ACP-P1-BUILD-20260816.md                       |    48 +
 .../ACP-P1-DESIGN-20260816.md                      |   164 +
 .../ACP-P1b-BUILD-20260817.md                      |    79 +
 .../ACP-P1b-DESIGN-20260816.md                     |    85 +
 .../ACP-P2-BUILD-20260817.md                       |    99 +
 .../ACP-P2-DESIGN-20260816.md                      |   131 +
 .../ACP-P3-BUILD-20260817.md                       |    47 +
 .../ACP-P3-DESIGN-20260816.md                      |   120 +
 .../ACP-P4-BUILD-20260817.md                       |   126 +
 .../ACP-P4-DESIGN-20260816.md                      |    82 +
 .../ACP-PREP-COPY-20260816.md                      |   108 +
 .../ANTIGRAVITY-ACP-P1-DESIGN-ADVISORY-20260816.md |    70 +
 .../ANTIGRAVITY-ACP-P2-DESIGN-ADVISORY-20260816.md |    64 +
 .../ANTIGRAVITY-ACP-P3-DESIGN-ADVISORY-20260816.md |    70 +
 ...IGRAVITY-AGENT-PROMPTING-COMPARISON-20260817.md |    88 +
 ...IGRAVITY-PROMPTING-AUDIT-ASSESSMENT-20260817.md |    56 +
 .agents/plans/approval-control-plane/tracker.json  |   302 +
 .agents/plans/aq-eval-harness.md                   |    22 +
 .agents/plans/aq-inference-bench.md                |    25 +
 .../plans/aqos-capabilities-inventory/tracker.json |    32 +
 .../plans/aqos-defensive-security/PROGRAM-PLAN.md  |   138 +
 .../S0-A-ACTIVATION-RECEIPTS.md                    |    25 +
 .../aqos-defensive-security/S0-A-AM1-ACTIVATION.md |    15 +
 .../S0-A-AM1-CANDIDATE-REVISION.md                 |   123 +
 .../S0-A-CANDIDATE-ACCEPTANCE.md                   |    50 +
 .../S0-A-CLAUDE-CONFIRMATORY-REVIEW.md             |   171 +
 .../aqos-defensive-security/S0-A-DESIGN-PACKET.md  |   175 +
 .../S0-A-IMPLEMENTATION-AUTHORIZATION-AM1.md       |    68 +
 .../S0-A-IMPLEMENTATION-AUTHORIZATION.md           |   163 +
 .../S0-A-RELEASE-AUTHORIZATION-20260729.md         |    59 +
 .../S0-A-RELEASE-AUTHORIZATION-AM1-20260729.md     |    67 +
 .../S0-A-RELEASE-AUTHORIZATION-AM2-20260729.md     |   122 +
 .../S0-A-RELEASE-AUTHORIZATION-AM3-20260729.md     |   165 +
 .../antigravity-track-s-review.md                  |    55 +
 .../B2-C1-AUTHORIZATION-REVIEW.md                  |   120 +
 .../B2-C1-IMPLEMENTATION-ACCEPTANCE.md             |    97 +
 .../B2-C1-IMPLEMENTATION-AUTHORIZATION.md          |   254 +
 .../aqos-foundation-b2/B2-D0-DESIGN-PACKET.md      |   211 +
 .../aqos-foundation-b2/B2-D0-DESIGN-REVIEW.md      |   101 +
 .../B2-M1-DESIGN-AUTHORIZATION-REVIEW-R2.md        |   127 +
 .../B2-M1-DESIGN-AUTHORIZATION-REVIEW-R3.md        |   102 +
 .../B2-M1-DESIGN-AUTHORIZATION-REVIEW-R4.md        |    74 +
 .../B2-M1-DESIGN-AUTHORIZATION-REVIEW.md           |   127 +
 .../aqos-foundation-b2/B2-M1-DESIGN-PACKET.md      |   349 +
 .../B2-M1-IMPLEMENTATION-AUTHORIZATION.md          |   328 +
 ...-ACCEPTANCE-RECOVERY-AUTHORIZATION-REVIEW-R2.md |    92 +
 ...M1A-ACCEPTANCE-RECOVERY-AUTHORIZATION-REVIEW.md |    78 +
 .../B2-M1A-ACCEPTANCE-RECOVERY-AUTHORIZATION.md    |   147 +
 .../B2-M1A-AM1-AUTHORIZATION-REVIEW.md             |    99 +
 .../aqos-foundation-b2/B2-M1A-AM1-DESIGN-PACKET.md |   166 +
 .../B2-M1A-AM1-IMPLEMENTATION-AUTHORIZATION.md     |   173 +
 .../B2-M1A-AM1-WORKFLOW-CONFLICT-INCIDENT.md       |    73 +
 .../B2-M1A-AM2-AUTHORIZATION-REVIEW-R2.md          |    78 +
 .../B2-M1A-AM2-AUTHORIZATION-REVIEW.md             |    80 +
 .../aqos-foundation-b2/B2-M1A-AM2-DESIGN-PACKET.md |   171 +
 .../B2-M1A-AM2-IMPLEMENTATION-AUTHORIZATION.md     |   249 +
 .../B2-M1A-AM2-STATIC-ACCEPTANCE-AUTHORIZATION.md  |   143 +
 .../B2-M1A-AM2-STATIC-ACCEPTANCE.md                |   183 +
 .../B2-M1A-IMPLEMENTATION-ACCEPTANCE.md            |   101 +
 .../B2-M1A-RECOVERY-ACCEPTANCE.md                  |   121 +
 .../aqos-foundation-b2/WORKFLOW-SHADOW-ADR.md      |   250 +
 .../aqos-foundation-b2/WORKFLOW-SHADOW-PRD.md      |   396 +
 .../B3-C1-ACTIVATION-REBIND-REVIEW.md              |    77 +
 .../B3-C1-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md    |    47 +
 .../B3-C1-CANON-COMPILER-AUTHORIZATION.md          |    90 +
 .../aqos-foundation-b3/B3-C1-CODEX-ACCEPTANCE.md   |   110 +
 .../aqos-foundation-b3/B3-C1-FLAGSHIP-REVIEW.md    |    42 +
 .../aqos-foundation-c/ACTIVATION-READY-BATCH.md    |    78 +
 ...E-SELF-BIND-AMENDMENT-AUTHORIZATION-20260802.md |    28 +
 ...COVERAGE-SELF-BIND-AMENDMENT-DESIGN-20260802.md |    46 +
 ...LA-C2-CONTRACT-REPAIR-AUTHORIZATION-20260808.md |    47 +
 .../ALA-C2-CONTRACT-REPAIR-DESIGN-20260808.md      |   160 +
 ...LA-C2-CONTRACT-REPAIR-DESIGN-REVIEW-20260808.md |    61 +
 ...CT-REPAIR-IMPLEMENTATION-ACCEPTANCE-20260808.md |    53 +
 ...NTRACT-REPAIR-RELEASE-AUTHORIZATION-20260808.md |    75 +
 ...CT-REPAIR-RELEASE-AUTHORIZATION-AM1-20260808.md |    76 +
 .../ANTIGRAVITY-ALA-C2-C6-B3R-ADVISORY-20260808.md |    59 +
 ...NTIGRAVITY-TEG-C1-SLICEONE-ADVISORY-20260815.md |    68 +
 ...-LEASE-AUTHORITY-ACTIVATION-RUNBOOK-20260806.md |    58 +
 ...SYMMETRIC-LEASE-AUTHORITY-BUILD-LOG-20260806.md |   168 +
 .../ASYMMETRIC-LEASE-AUTHORITY-DESIGN-20260806.md  |   230 +
 .../ASYMMETRIC-LEASE-AUTHORITY-FREEZE-20260806.md  |    46 +
 .../aqos-foundation-c/C0-IMPLEMENTATION-SPEC.md    |    81 +
 .agents/plans/aqos-foundation-c/C0-REVIEW-OPUS.md  |   186 +
 .../aqos-foundation-c/C1-IMPLEMENTATION-SPEC.md    |    97 +
 .agents/plans/aqos-foundation-c/C1-REVIEW-OPUS.md  |    75 +
 .../C2-AMENDMENT-BUILTIN-TOOLS.md                  |   105 +
 .../C2-AMENDMENT-REREVIEW-OPUS.md                  |   169 +
 .../aqos-foundation-c/C2-AMENDMENT-REVIEW-CODEX.md |   382 +
 .../C2-DESIGN-AND-AUTHORIZATION.md                 |   165 +
 .../C2-ENFORCEMENT-ACTIVATION-20260730.md          |    51 +
 .../aqos-foundation-c/C2-FREEZE-AND-ACTIVATION.md  |    57 +
 .../aqos-foundation-c/C2-REREVIEW-CODEX-ROUND2.md  |    53 +
 .../plans/aqos-foundation-c/C2-REREVIEW-OPUS.md    |   147 +
 .agents/plans/aqos-foundation-c/C2-REVIEW-OPUS.md  |   160 +
 ...-SCHEDULER-CONTEXT-ISSUER-BUILD-LOG-20260807.md |    50 +
 .../C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md |   231 +
 .../C2-SCHEDULER-CONTEXT-ISSUER-FREEZE-20260807.md |    60 +
 .../C2-SCI-ACTIVATION-20260815.md                  |    64 +
 .../C3A-1-DESIGN-AND-AUTHORIZATION.md              |   166 +
 .../C3A-2-CODEX-DEPTH-REVIEW-20260801.md           |   130 +
 .../C3A-2-DESIGN-AND-AUTHORIZATION.md              |   213 +
 .../C3A-2-DESIGN-FORWARD-SCOPE.md                  |    49 +
 .../C3A-DESIGN-AND-AUTHORIZATION.md                |   215 +
 .../C3B-DESIGN-AND-AUTHORIZATION.md                |   368 +
 .../plans/aqos-foundation-c/C3B-R0-REVIEW-OPUS.md  |    89 +
 .../C3B-R1-DESIGN-AND-AUTHORIZATION.md             |   205 +
 .../C3B-R2-DESIGN-AND-AUTHORIZATION.md             |   157 +
 .../C3B-R3-DESIGN-AND-AUTHORIZATION.md             |   185 +
 .../C3B-R3-FREEZE-AND-ACTIVATION.md                |    73 +
 .../C3B-R4-ACCEPTANCE-REPORT-20260730.md           |    48 +
 .../C3B-R4-DESIGN-AND-AUTHORIZATION.md             |   134 +
 .../C3B-R5-DESIGN-AND-AUTHORIZATION.md             |   153 +
 .../C3B-R5-FREEZE-AND-ACTIVATION.md                |    67 +
 .../C3B-REV3-INDEPENDENT-REVIEW-20260730.md        |   136 +
 .../C4-ACTIVATION-READINESS-20260806.md            |    82 +
 .../C4-CODEX-DEPTH-REVIEW-20260801.md              |   217 +
 .../C4-DESIGN-AND-AUTHORIZATION.md                 |   283 +
 .../C5-DESIGN-AND-AUTHORIZATION.md                 |   132 +
 .../aqos-foundation-c/C6-ACTIVATION-20260815.md    |    58 +
 .../C6-ACTIVATION-READINESS-20260806.md            |    91 +
 .../C6-B1-CODE-REVIEW-20260807.md                  |    57 +
 .../C6-B3-AMENDMENT-REVIEW-20260808.md             |   126 +
 .../C6-B3-CODE-REVIEW-20260808.md                  |   158 +
 .../C6-B3-EPOCH-READER-AMENDMENT-20260808.md       |    59 +
 .../C6-B3-LIVE-SEAM-RECONCILIATION-20260808.md     |   151 +
 .../C6-CODEX-DEPTH-REVIEW-20260801.md              |   142 +
 .../C6-DESIGN-AND-AUTHORIZATION.md                 |   344 +
 .../plans/aqos-foundation-c/C6-FREEZE-20260807.md  |    72 +
 .../C6-P0-AND-C2-ISSUER-BINDING-REVIEW-20260806.md |   189 +
 .../C6-P0-FREEZE-AND-ACTIVATION-20260806.md        |    35 +
 .../C6-P0-INDEPENDENT-REVIEW-20260801.md           |    57 +
 .../C6-P0-REV2-INDEPENDENT-REVIEW-20260801.md      |    37 +
 .../C6-P0-TRUST-ANCHORS-DESIGN-20260801.md         |   138 +
 .../C6-P0-TRUST-ANCHORS-REV3-20260806.md           |    80 +
 .../C6-RECONCILIATION-POST-C2SCI-20260807.md       |    63 +
 .../C6-REV3-BINDING-REVIEW-20260807.md             |   124 +
 .../CATCHUP-CODEX-CONFIRMATORY-AUDIT-20260808.md   |   170 +
 .../CODEX-DEPTH-REVISION-BRIEF-20260801.md         |   137 +
 .../CODEX-RETURN-CATCHUP-AUDIT-20260814.md         |   193 +
 .agents/plans/aqos-foundation-c/DESIGN-PACKET.md   |   239 +
 .../plans/aqos-foundation-c/DESIGN-REVIEW-OPUS.md  |   162 +
 ...ENFORCE-ASYMMETRIC-VERIFY-BUILD-LOG-20260807.md |    62 +
 .../ENFORCE-ASYMMETRIC-VERIFY-DESIGN-20260807.md   |   170 +
 .../ENFORCE-ASYMMETRIC-VERIFY-FREEZE-20260807.md   |    60 +
 .../FOUNDATION-C-REV2-CODEX-ACCEPTANCE-20260801.md |   224 +
 .../FOUNDATION-C-REV3-CODEX-ACCEPTANCE-20260801.md |    50 +
 .../R5-SHADOW-ACTIVATION-20260731.md               |    49 +
 .../plans/aqos-foundation-c/R7-FREEZE-20260803.md  |    48 +
 .../R7-PROVISIONING-DESIGN-20260803.md             |   164 +
 .../REV2-COLLABORATIVE-REVIEW-PACKET-20260801.md   |    45 +
 ...OYMENT-HARDENING-CODEX-DEPTH-REVIEW-20260801.md |   119 +
 .../RUNNER-DEPLOYMENT-HARDENING-FREEZE.md          |    89 +
 ...DENING-IMPLEMENTATION-AUTHORIZATION-20260801.md |    35 +
 .../RUNNER-DEPLOYMENT-HARDENING.md                 |   211 +
 ...NNER-HARDENING-AUTHORIZATION-REVIEW-20260801.md |    57 +
 ...-HARDENING-AUTHORIZATION-REVIEW-AM1-20260801.md |    58 +
 ...-HARDENING-BYTE-RECOVERY-ACCEPTANCE-20260802.md |    39 +
 ...RDENING-BYTE-RECOVERY-AUTHORIZATION-20260801.md |    29 +
 ...NNER-HARDENING-BYTE-RECOVERY-DESIGN-20260801.md |    47 +
 ...HARDENING-IMPLEMENTATION-ACCEPTANCE-20260801.md |    62 +
 .../TEG-C1-DESIGN-PACKET-20260808.md               |   178 +
 .../TEG-C1-DESIGN-REVIEW-20260808.md               |   292 +
 .../aqos-foundation-c/TEG-C1-FREEZE-20260814.md    |    47 +
 .../TEG-C1-ORCHESTRATOR-REVIEW-20260808.md         |    65 +
 .../TEG-C1-R2-REREVIEW-20260808.md                 |    70 +
 .../aqos-foundation-c/r4-acceptance-20260730.json  |    79 +
 .../aqos-foundation-c/r4-acceptance-20260730.jsonl |   240 +
 .../r4-acceptance-revocation-20260730-cap1.json    |    83 +
 .../r4-acceptance-revocation-20260730-cap1.jsonl   |   120 +
 .../r4-acceptance-revocation-20260730-cap2.json    |    83 +
 .../r4-acceptance-revocation-20260730-cap2.jsonl   |   120 +
 .agents/plans/aqos-foundation-c/tracker.json       |   306 +
 ...-SEMANTIC-REBUILD-WIP-INCOMPLETE-20260802.patch |  2003 ++
 .../DESIGN-PACKET-AM1-20260729.md                  |   157 +
 .../DESIGN-PACKET-AM2-20260730.md                  |   189 +
 ...ESIGN-PACKET-AM2-INDEPENDENT-REVIEW-20260730.md |   115 +
 .../DESIGN-PACKET-AM3-20260801.md                  |    76 +
 .../DESIGN-PACKET-AM3-BYTE-RECOVERY-R1-20260801.md |   152 +
 ...SIGN-PACKET-AM3-SEMANTIC-REBUILD-R1-20260802.md |    84 +
 .../DESIGN-PACKET-AM4-20260801.md                  |   109 +
 .../DESIGN-PACKET-AM4-REV1-20260801.md             |   120 +
 .../plans/aqos-progress-tracker/DESIGN-PACKET.md   |    49 +
 .../IMPLEMENTATION-AUTHORIZATION-AM1-20260729.md   |    61 +
 .../IMPLEMENTATION-AUTHORIZATION-AM2-20260730.md   |    97 +
 ...UTHORIZATION-AM2-INDEPENDENT-REVIEW-20260730.md |   107 +
 .../IMPLEMENTATION-AUTHORIZATION-AM3-20260801.md   |    57 +
 ...-AUTHORIZATION-AM3-BYTE-RECOVERY-R1-20260801.md |    73 +
 ...THORIZATION-AM3-SEMANTIC-REBUILD-R1-20260802.md |    97 +
 ...PLEMENTATION-AUTHORIZATION-AM4-REV1-20260801.md |   102 +
 ...ENTATION-AUTHORIZATION-REACTIVATION-20260729.md |    51 +
 .../IMPLEMENTATION-AUTHORIZATION.md                |    38 +
 .../antigravity-am1-design-review.md               |    76 +
 .agents/plans/aqos-refactor-status/SPEC.md         |    64 +
 .../aqos-refoundation-cycle0/.round-dispatch.json  |     8 +
 .../aqos-refoundation-cycle0/.round-prompt.txt     |     6 +
 .../ACTIVATION-C0.2-RECOVERY.md                    |    74 +
 .../plans/aqos-refoundation-cycle0/AGGREGATE.md    |   107 +
 .../aqos-refoundation-cycle0/C0.2-BASELINES.json   |   130 +
 .../aqos-refoundation-cycle0/C0.2-BASELINES.md     |    32 +
 .../C0.2-IMPLEMENTATION-REPORT.md                  |    86 +
 .../aqos-refoundation-cycle0/C0.2-POST-CHANGE.json |    62 +
 .../C0.2-PRESERVED-DIFF-DISPOSITION.md             |    36 +
 .../C0.2-REWORK-POST-CHANGE.json                   |    45 +
 .../aqos-refoundation-cycle0/C0.2-REWORK-REPORT.md |    30 +
 .../C0.2-SURFACE-INVENTORY.md                      |    61 +
 .../C0.3-AUTHORIZATION-AMENDMENT-1.md              |   146 +
 .../C0.3-AUTHORIZATION-CONSUMPTION.md              |    74 +
 .../C0.3-BATCH-INTEGRATION-INCIDENT-20260801.md    |    52 +
 .../C0.3-CLAUDE-EVIDENCE-INCIDENT-20260713.md      |    48 +
 .../C0.3-CURRENT-SUBJECT-ACCEPTANCE-CANDIDATE.md   |   120 +
 .../C0.3-CURRENT-SUBJECT-ACCEPTANCE.md             |   143 +
 .../C0.3-EVIDENCE-RECOVERY-AUTHORIZATION.md        |   122 +
 .../C0.3-EVIDENCE-RECOVERY-V2-AUTHORIZATION.md     |   106 +
 .../C0.3-IMPLEMENTATION-REPORT.md                  |   313 +
 .../C0.3-POST-BATCH-SETTLEMENT-DESIGN-20260801.md  |    83 +
 ...C0.3-PROVENANCE-RECONCILIATION-AUTHORIZATION.md |   288 +
 .../C0.3-PROVENANCE-RECONCILIATION-DESIGN.md       |   321 +
 ...ECOVERY-EVIDENCE-OVERWRITE-INCIDENT-20260713.md |    84 +
 .../C0.3-STAGE2-RECOVERY-AUTHORIZATION-20260730.md |   150 +
 ...TAGE2-RECOVERY-AUTHORIZATION-REVIEW-20260730.md |    98 +
 .../aqos-refoundation-cycle0/CONSOLIDATED-PLAN.md  |   342 +
 .../CURRENT-AUTHORITY-INVENTORY.md                 |    41 +
 .../plans/aqos-refoundation-cycle0/DECISION-LOG.md |    67 +
 .../aqos-refoundation-cycle0/EVIDENCE-ALGEBRA.md   |    59 +
 .../EVIDENCE-MANIFEST.json                         |   195 +
 .../aqos-refoundation-cycle0/EVIDENCE-MANIFEST.md  |    68 +
 ...ATION-A-ADJUDICATION-CONTRACT-AM1-ACCEPTANCE.md |    43 +
 ...JUDICATION-CONTRACT-AM1-AUTHORIZATION-REVIEW.md |    23 +
 ...ON-A-ADJUDICATION-CONTRACT-AM1-AUTHORIZATION.md |    60 +
 ...A-ADJUDICATION-CONTRACT-AUTHORIZATION-REVIEW.md |    85 +
 ...DATION-A-ADJUDICATION-CONTRACT-AUTHORIZATION.md |    59 +
 ...DATION-A-ADJUDICATION-CONTRACT-DESIGN-REVIEW.md |   113 +
 .../FOUNDATION-A-ADJUDICATION-CONTRACT-DESIGN.md   |   328 +
 .../FOUNDATION-A-OWNER-ADJUDICATION-20260718.md    |    78 +
 ...NDATION-A-OWNER-ADJUDICATION-REVIEW-20260718.md |    35 +
 ...REGISTRY-PROJECTION-AM1-AUTHORIZATION-REVIEW.md |    22 +
 ...TION-A-REGISTRY-PROJECTION-AM1-AUTHORIZATION.md |    57 +
 ...REGISTRY-PROJECTION-AM2-AUTHORIZATION-REVIEW.md |    19 +
 ...TION-A-REGISTRY-PROJECTION-AM2-AUTHORIZATION.md |    47 +
 ...NDATION-A-REGISTRY-PROJECTION-AM3-ACCEPTANCE.md |    36 +
 ...REGISTRY-PROJECTION-AM3-AUTHORIZATION-REVIEW.md |    20 +
 ...TION-A-REGISTRY-PROJECTION-AM3-AUTHORIZATION.md |    49 +
 ...N-A-REGISTRY-PROJECTION-AUTHORIZATION-REVIEW.md |    24 +
 ...UNDATION-A-REGISTRY-PROJECTION-AUTHORIZATION.md |    60 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.1.md           |    81 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.2-RECOVERY.md  |    53 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.2.md           |    84 +
 .../IMPLEMENTATION-AUTHORIZATION-C0.3.md           |    69 +
 .../OWNER-POLICY-RATIFICATION.md                   |   124 +
 .../aqos-refoundation-cycle0/PACKAGE-ROOT.json     |   149 +
 .../aqos-refoundation-cycle0/PACKAGE-ROOT.sha256   |     1 +
 .agents/plans/aqos-refoundation-cycle0/README.md   |    14 +
 .../REFERENCE-AND-MIGRATION-COMPARISON.md          |    68 +
 .../REVIEW-FABLE5-C02-RECOVERY.md                  |    72 +
 .../REVIEW-FABLE5-FINAL.md                         |    61 +
 .../aqos-refoundation-cycle0/REVIEW-FABLE5.md      |   160 +
 .../aqos-refoundation-cycle0/REVIEW-FINDINGS.md    |    68 +
 .../REVIEW-GEMINI-C0.2-RECOVERY-V2.md              |    48 +
 .../REVIEW-GEMINI-C0.2-RECOVERY.md                 |    45 +
 .../REVIEW-GEMINI-FINAL.md                         |    53 +
 .../REVIEW-GEMINI-e2f1b8c6.md                      |    42 +
 .../aqos-refoundation-cycle0/STATE-CONTRACT.md     |   160 +
 .../aqos-refoundation-cycle0/THREAT-REGISTER.md    |    66 +
 .../antigravity-findings-review.md                 |    72 +
 .../plans/aqos-refoundation-cycle0/antigravity.md  |   222 +
 .agents/plans/aqos-refoundation-cycle0/claude.md   |   200 +
 .agents/plans/aqos-refoundation-cycle0/codex.md    |   137 +
 ...ab379ed4421c78272beb58090e55d178c15def4649.json |     1 +
 .../evidence/rejected/DISPOSITION.md               |    21 +
 ...ntigravity-unauthorized-overwrite-20260713.json |  2493 +++
 ...source-evidence-claude-invented-singletons.json |  2593 +++
 .../local-findings-review.md                       |    36 +
 .agents/plans/aqos-refoundation-cycle0/round.json  |    77 +
 .../plans/aqos-requirements-inventory/tracker.json |    39 +
 .agents/plans/aqos-services-inventory/tracker.json |    48 +
 .agents/plans/aqos-tools-inventory/tracker.json    |    39 +
 .agents/plans/aqos-v1/.plan-lifecycle.json         |     8 +
 .agents/plans/aqos-v1/.round-dispatch.json         |     8 +
 .agents/plans/aqos-v1/.round-prompt.txt            |    37 +
 .agents/plans/aqos-v1/AGGREGATE.md                 |    38 +
 .agents/plans/aqos-v1/DELEGATION.md                |    31 +
 .agents/plans/aqos-v1/GOD-TIER-PROMPTS.md          |    30 +
 .agents/plans/aqos-v1/HORIZON-UNKNOWNS.md          |    80 +
 .agents/plans/aqos-v1/PLAN.md                      |    90 +
 .agents/plans/aqos-v1/README.md                    |    45 +
 .agents/plans/aqos-v1/ROUND-PROMPT.md              |    32 +
 .agents/plans/aqos-v1/STACKING-AUDIT.md            |    33 +
 .agents/plans/aqos-v1/antigravity.md               |    39 +
 .agents/plans/aqos-v1/claude.md                    |    35 +
 .agents/plans/aqos-v1/codex.md                     |    45 +
 .agents/plans/aqos-v1/local-bounded-prompt.md      |    35 +
 .agents/plans/aqos-v1/local.md                     |     5 +
 .agents/plans/aqos-v1/round.json                   |    77 +
 .agents/plans/aqos-v1/ws-edge/E1-hw-probe-spec.md  |    22 +
 .agents/plans/aqos-v1/ws-edge/draft-tune-bench.md  |    49 +
 .agents/plans/aqos-v1/ws-edge/rebudget-analysis.md |    81 +
 .../plans/aqos-v1/ws6-command-center-roadmap.md    |    52 +
 .agents/plans/b1-parity-design-review/README.md    |    14 +
 .../plans/b1-parity-design-review/antigravity.md   |    46 +
 .agents/plans/b1-parity-design-review/round.json   |    73 +
 .../.plan-lifecycle.json                           |     8 +
 .../.round-dispatch.json                           |    36 +
 .../.round-prompt.txt                              |     5 +
 .../c05-tiered-policy-architecture/AGGREGATE.md    |    47 +
 .../plans/c05-tiered-policy-architecture/README.md |    53 +
 .../c05-tiered-policy-architecture/antigravity.md  |    45 +
 .../plans/c05-tiered-policy-architecture/claude.md |    23 +
 .../plans/c05-tiered-policy-architecture/local.md  |    65 +
 .../c05-tiered-policy-architecture/round.json      |    88 +
 .../antigravity.md                                 |    45 +
 .../b1-code-review.md                              |    65 +
 .../b2-code-review.md                              |    53 +
 .../b25-b3-b4-code-review.md                       |    61 +
 .../fresh-flagship.md                              |   115 +
 .agents/plans/c3a2-review/README.md                |    28 +
 .agents/plans/c3a2-review/antigravity.md           |    21 +
 .agents/plans/c3a2-review/claude.md                |     2 +
 .agents/plans/c3a2-review/round.json               |    73 +
 .agents/plans/c3b-r1-review/README.md              |    57 +
 .agents/plans/c3b-r1-review/antigravity.md         |    49 +
 .agents/plans/c3b-r1-review/claude.md              |    37 +
 .agents/plans/c3b-r1-review/round.json             |    73 +
 .agents/plans/c3b-r2-review/README.md              |    53 +
 .agents/plans/c3b-r2-review/antigravity.md         |    52 +
 .agents/plans/c3b-r2-review/claude.md              |    32 +
 .agents/plans/c3b-r2-review/round.json             |    73 +
 .agents/plans/c3b-r3-review/README.md              |    58 +
 .agents/plans/c3b-r3-review/antigravity.md         |    55 +
 .agents/plans/c3b-r3-review/claude.md              |    32 +
 .agents/plans/c3b-r3-review/round.json             |    73 +
 .agents/plans/c3b-r4-review/README.md              |    31 +
 .agents/plans/c3b-r4-review/antigravity.md         |    35 +
 .agents/plans/c3b-r4-review/claude.md              |     9 +
 .agents/plans/c3b-r4-review/round.json             |    73 +
 .agents/plans/c3b-r5-review/README.md              |    39 +
 .agents/plans/c3b-r5-review/antigravity.md         |    38 +
 .agents/plans/c3b-r5-review/claude.md              |    14 +
 .agents/plans/c3b-r5-review/round.json             |    73 +
 .agents/plans/c4-review/README.md                  |    35 +
 .agents/plans/c4-review/antigravity.md             |    39 +
 .agents/plans/c4-review/claude.md                  |     2 +
 .agents/plans/c4-review/round.json                 |    73 +
 .agents/plans/c5-review/README.md                  |    23 +
 .agents/plans/c5-review/antigravity.md             |    21 +
 .agents/plans/c5-review/claude.md                  |     2 +
 .agents/plans/c5-review/round.json                 |    73 +
 .agents/plans/c6-review/README.md                  |    26 +
 .agents/plans/c6-review/antigravity.md             |    22 +
 .agents/plans/c6-review/claude.md                  |     2 +
 .agents/plans/c6-review/round.json                 |    73 +
 .../ANTIGRAVITY-CANDIDATE-REVIEW.md                |   222 +
 .../plans/codex-subagent-configuration/C0-PLAN.md  |    41 +
 .agents/plans/context-sandbox-parity-routing.md    |    19 +
 .../CANDIDATE-ACCEPTANCE.md                        |   137 +
 .../CODEX-ACCEPTANCE-AUTHORIZATION.md              |    53 +
 .../REVISED-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md  |    47 +
 .../REVISED-CANDIDATE-ACCEPTANCE.md                |   108 +
 .../REVISION-AUTHORIZATION.md                      |    60 +
 .../SLICE-DESIGN-AND-AUTHORIZATION.md              |    89 +
 .../plans/dev-cycle-candidate-slate-2026-07-06.md  |   135 +
 .../.round-dispatch.json                           |     8 +
 .../dispatch-integration-review/.round-prompt.txt  |     5 +
 .../plans/dispatch-integration-review/README.md    |    14 +
 .../dispatch-integration-review/antigravity.md     |    50 +
 .agents/plans/dispatch-integration-review/local.md |     7 +
 .../plans/dispatch-integration-review/round.json   |    73 +
 .../antigravity.md                                 |    62 +
 .../code-review-a4c496ec.md                        |    17 +
 .../fresh-flagship-rev2.md                         |    66 +
 .../fresh-flagship.md                              |   204 +
 .agents/plans/epic-flat-collaborative-factory.md   |    76 +
 .agents/plans/f1-brief.md                          |    42 +
 .agents/plans/f1-impl-plan.md                      |   203 +
 .../plans/f1-plan-consensus/.plan-lifecycle.json   |     8 +
 .../plans/f1-plan-consensus/.round-dispatch.json   |     8 +
 .agents/plans/f1-plan-consensus/.round-prompt.txt  |   142 +
 .agents/plans/f1-plan-consensus/AGGREGATE.md       |    56 +
 .agents/plans/f1-plan-consensus/README.md          |    14 +
 .agents/plans/f1-plan-consensus/antigravity.md     |    40 +
 .agents/plans/f1-plan-consensus/claude.md          |    41 +
 .agents/plans/f1-plan-consensus/codex.md           |    43 +
 .agents/plans/f1-plan-consensus/local.md           |    10 +
 .../f1-round-state-machine/.plan-lifecycle.json    |     8 +
 .../f1-round-state-machine/.round-dispatch.json    |     8 +
 .../plans/f1-round-state-machine/.round-prompt.txt |     6 +
 .agents/plans/f1-round-state-machine/AGGREGATE.md  |    50 +
 .agents/plans/f1-round-state-machine/README.md     |    14 +
 .../plans/f1-round-state-machine/antigravity.md    |   148 +
 .agents/plans/f1-round-state-machine/claude.md     |    79 +
 .agents/plans/f1-round-state-machine/codex.md      |   282 +
 .agents/plans/f1-round-state-machine/local.md      |    15 +
 .agents/plans/f2-brief.md                          |    42 +
 .agents/plans/f2-impl-plan.md                      |   145 +
 .../plans/f2-local-scheduler/.plan-lifecycle.json  |     8 +
 .../plans/f2-local-scheduler/.round-dispatch.json  |     8 +
 .agents/plans/f2-local-scheduler/.round-prompt.txt |     6 +
 .agents/plans/f2-local-scheduler/AGGREGATE.md      |    48 +
 .agents/plans/f2-local-scheduler/README.md         |    14 +
 .agents/plans/f2-local-scheduler/antigravity.md    |    71 +
 .agents/plans/f2-local-scheduler/claude.md         |    45 +
 .agents/plans/f2-local-scheduler/codex.md          |   112 +
 .agents/plans/f2-local-scheduler/local.md          |    10 +
 .../plans/f2-plan-consensus/.plan-lifecycle.json   |     8 +
 .../plans/f2-plan-consensus/.round-dispatch.json   |     8 +
 .agents/plans/f2-plan-consensus/.round-prompt.txt  |   101 +
 .agents/plans/f2-plan-consensus/AGGREGATE.md       |    51 +
 .agents/plans/f2-plan-consensus/README.md          |    14 +
 .agents/plans/f2-plan-consensus/antigravity.md     |    32 +
 .agents/plans/f2-plan-consensus/claude.md          |    41 +
 .agents/plans/f2-plan-consensus/codex.md           |    31 +
 .agents/plans/f2-plan-consensus/local.md           |     7 +
 .agents/plans/f2-plan-consensus/round.json         |    77 +
 .agents/plans/f2-session-mode/.plan-lifecycle.json |     8 +
 .agents/plans/f2-session-mode/.round-dispatch.json |     8 +
 .agents/plans/f2-session-mode/.round-prompt.txt    |    51 +
 .agents/plans/f2-session-mode/AGGREGATE.md         |    94 +
 .agents/plans/f2-session-mode/BRIEF.md             |    42 +
 .agents/plans/f2-session-mode/README.md            |    14 +
 .agents/plans/f2-session-mode/antigravity.md       |    52 +
 .agents/plans/f2-session-mode/claude.md            |    58 +
 .agents/plans/f2-session-mode/codex.md             |   146 +
 .agents/plans/f2-session-mode/local.md             |     9 +
 .agents/plans/f2-session-mode/round.json           |    77 +
 .agents/plans/f3-brief.md                          |    38 +
 .../plans/f3-capability-otel/.plan-lifecycle.json  |     8 +
 .../plans/f3-capability-otel/.round-dispatch.json  |     8 +
 .agents/plans/f3-capability-otel/.round-prompt.txt |     6 +
 .agents/plans/f3-capability-otel/AGGREGATE.md      |   104 +
 .agents/plans/f3-capability-otel/README.md         |    14 +
 .agents/plans/f3-capability-otel/antigravity.md    |    83 +
 .agents/plans/f3-capability-otel/claude.md         |    49 +
 .agents/plans/f3-capability-otel/codex.md          |   191 +
 .agents/plans/f3-capability-otel/local.md          |     7 +
 .agents/plans/factory-critique-brief.md            |    46 +
 .../plans/factory-critique/.plan-lifecycle.json    |     8 +
 .../plans/factory-critique/.round-dispatch.json    |     8 +
 .agents/plans/factory-critique/.round-prompt.txt   |     6 +
 .agents/plans/factory-critique/AGGREGATE.md        |    74 +
 .agents/plans/factory-critique/README.md           |    14 +
 .agents/plans/factory-critique/antigravity.md      |    27 +
 .agents/plans/factory-critique/claude.md           |    62 +
 .agents/plans/factory-critique/codex.md            |   128 +
 .agents/plans/factory-critique/local.md            |     5 +
 .agents/plans/flat-collaboration-enablement-prd.md |    31 +
 .agents/plans/flat-collaboration-enablement.md     |    29 +
 .../foundation-c-rev2-depth-20260801/README.md     |    14 +
 .../antigravity.md                                 |    87 +
 .../foundation-c-rev2-depth-20260801/local.md      |    11 +
 .../foundation-c-rev2-depth-20260801/round.json    |    73 +
 .../plans/generic-flake-baseline/AM1-ACCEPTANCE.md |    37 +
 .../plans/generic-flake-baseline/AM2-ACCEPTANCE.md |    31 +
 .../CLOSURE-DESIGN-REVIEW.md                       |    29 +
 .../plans/generic-flake-baseline/CLOSURE-DESIGN.md |   153 +
 .../IMPLEMENTATION-AUTHORIZATION-AM1-REVIEW.md     |    19 +
 .../IMPLEMENTATION-AUTHORIZATION-AM1.md            |    50 +
 .../IMPLEMENTATION-AUTHORIZATION-AM2-REVIEW.md     |    19 +
 .../IMPLEMENTATION-AUTHORIZATION-AM2.md            |    50 +
 .../IMPLEMENTATION-AUTHORIZATION-REVIEW.md         |    20 +
 .../IMPLEMENTATION-AUTHORIZATION.md                |    56 +
 .agents/plans/gitlawb-zero-gap-analysis.md         |    57 +
 .../ANTIGRAVITY-ACP-PRD-ADVISORY-20260815.md       |    34 +
 .../ANTIGRAVITY-FLAT-ORG-FRICTION-20260808.md      |    50 +
 ...TIGRAVITY-HERDR-ESCALATION-ADVISORY-20260816.md |    37 +
 .../herdr-agent-operations/H0-INTAKE-REPORT.md     |    56 +
 .../H1-ACCEPTANCE-20260815.md                      |    48 +
 .../H1-CORRECTION-DESIGN-20260815.md               |   101 +
 .../H1-CORRECTION-INDEPENDENT-REVIEW-20260815.md   |    51 +
 ...-CORRECTION-REV1-INDEPENDENT-REVIEW-20260815.md |    39 +
 .../herdr-agent-operations/H1-DESIGN-PACKET.md     |   206 +
 .../H1-SUPPLY-CHAIN-REPORT.md                      |   106 +
 .../H2-CLAUDE-CODEX-COLLABORATION-BRIEF.md         |   245 +
 .../H2-CODEX-PRODUCT-UX-REVIEW.md                  |   128 +
 .../herdr-agent-operations/H2-DESIGN-PACKET.md     |   320 +
 .../H2A-IMPLEMENTATION-INVENTORY-20260808.md       |   414 +
 .../H2A-INVENTORY-CODEX-REVIEW.md                  |   168 +
 .../H2A-INVENTORY-ORCHESTRATOR-REVIEW-20260808.md  |    45 +
 .../H2A-P0-REV1-INDEPENDENT-REVIEW-20260815.md     |    40 +
 .../H2A-P0-REV2-INDEPENDENT-REVIEW-20260815.md     |    40 +
 .../H2A-P0-REV3-INDEPENDENT-REVIEW-20260815.md     |    39 +
 .../H2A-P0-REV4-INDEPENDENT-REVIEW-20260815.md     |    37 +
 .../H2A-P0-REV5-INDEPENDENT-REVIEW-20260815.md     |    31 +
 .../H2A-P0-REV6-INDEPENDENT-REVIEW-20260815.md     |    36 +
 .../H2A-P0-REV7-INDEPENDENT-REVIEW-20260815.md     |    35 +
 .../H2A-P0-REV8-INDEPENDENT-REVIEW-20260815.md     |    36 +
 .../H2A-P0-REV9-INDEPENDENT-REVIEW-20260815.md     |    29 +
 .../H2A-P0B-REV1-INDEPENDENT-REVIEW-20260815.md    |    38 +
 .../H2A-P0B-REV2-INDEPENDENT-REVIEW-20260815.md    |    37 +
 .../H2A-P0B-REV3-INDEPENDENT-REVIEW-20260815.md    |    38 +
 .../H2A-P0B-REV4-INDEPENDENT-REVIEW-20260815.md    |    40 +
 .../H2A-P0B-REV5-INDEPENDENT-REVIEW-20260815.md    |    37 +
 .../H2A-P0B-REV6-INDEPENDENT-REVIEW-20260815.md    |    31 +
 .../H2A-P0B-REV7-INDEPENDENT-REVIEW-20260815.md    |    38 +
 .../H2A-P0B-REV8-INDEPENDENT-REVIEW-20260815.md    |    31 +
 .../H2A-P0B-REV9-INDEPENDENT-REVIEW-20260815.md    |    29 +
 .../H2A-REV1-INDEPENDENT-REVIEW-20260809.md        |    61 +
 .../H2A-REV2-INDEPENDENT-REVIEW-20260814.md        |    56 +
 .../H2A-REV3-INDEPENDENT-REVIEW-20260814.md        |    41 +
 .../H2A-REV4-INDEPENDENT-REVIEW-20260814.md        |    53 +
 .../H2A-REV5-INDEPENDENT-REVIEW-20260815.md        |    91 +
 .../HERDR-ESCALATION-ADJUDICATION-20260816.md      |    56 +
 .../plans/herdr-agent-operations/PROGRAM-PLAN.md   |    91 +
 ...CONVERGENCE-REV1-INDEPENDENT-REVIEW-20260815.md |    26 +
 ...CONVERGENCE-REV2-INDEPENDENT-REVIEW-20260815.md |    23 +
 .../evidence/H1-SBOM.spdx.json                     | 22300 +++++++++++++++++++
 .agents/plans/herdr-agent-operations/tracker.json  |   182 +
 .../html-learning-docs-requirements-2026-07-06.md  |    73 +
 .../2026-07-24-llama-cpp-resume-latch.md           |    35 +
 .../C0-DESIGN-REVIEW.md                            |    33 +
 .../plans/lean-ctx-workspace-identity/C0-DESIGN.md |   340 +
 .agents/plans/local-context-supply-chain/DESIGN.md |    88 +
 .../plans/local-context-supply-chain/tracker.json  |    19 +
 .../antigravity-acceptance-v2.md                   |    93 +
 .../local-delegation-reliability-r0/antigravity.md |    84 +
 .agents/plans/local-embed-context/DESIGN.md        |    93 +
 .agents/plans/local-embed-context/SLICE1-NOTES.md  |    86 +
 .../SLICE2-LOCAL-DECOMPOSITION.md                  |    74 +
 .agents/plans/local-embed-context/SLICE2A-NOTES.md |    32 +
 .../local-embed-context/SLICE2B-ACCEPTANCE.md      |   130 +
 .agents/plans/local-embed-context/SLICE3-DESIGN.md |    60 +
 .../B1-PARITY-ACCEPTANCE.md                        |    44 +
 .../B1-PARITY-IMPLEMENTATION-AUTHORIZATION.md      |   106 +
 .../CHAT-BATCH-PARITY-DESIGN-PACKET.md             |   151 +
 .../CHAT-BATCH-PARITY-DESIGN-REVIEW.md             |   215 +
 .../DASHBOARD-PARITY-AUTHORIZATION.md              |    19 +
 .../antigravity-acceptance-v2.md                   |    55 +
 .../antigravity-dashboard-acceptance.md            |    54 +
 .../antigravity-dashboard-review.md                |    53 +
 .../L2B-B-AM2-AUTHORIZATION-REVIEW.md              |   100 +
 .../L2B-B-AM4-AUTHORIZATION-REVIEW.md              |   109 +
 .../L2B-B-AM4-RECONCILIATION.md                    |    61 +
 ...-AM5-DRIFT-RECOVERY-ACCEPTANCE-AUTHORIZATION.md |   167 +
 .../L2B-B-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md    |    46 +
 .../L2B-B-CANDIDATE-REVISION-AM2.md                |   129 +
 .../L2B-B-CANDIDATE-REVISION-AM3.md                |   113 +
 .../L2B-B-CANDIDATE-REVISION-AM4.md                |    83 +
 .../L2B-B-CODEX-ACCEPTANCE.md                      |    22 +
 .../L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md            |   115 +
 .../local-inference-l2b-b/L2B-B-FLAGSHIP-REVIEW.md |    44 +
 .../L2B-B-IMPLEMENTATION-AUTHORIZATION-AM1.md      |   169 +
 .../L2B-B-IMPLEMENTATION-AUTHORIZATION-AM2.md      |   164 +
 .../L2B-B-IMPLEMENTATION-AUTHORIZATION-AM3.md      |   176 +
 .../L2B-B-IMPLEMENTATION-AUTHORIZATION-AM4.md      |   149 +
 .../L2B-B-IMPLEMENTATION-AUTHORIZATION.md          |    93 +
 .../L2B-B-NARROW-REVISION-CODEX-ACCEPTANCE.md      |   110 +
 .../L2B-B-RECOVERY-REFREEZE-AM1.md                 |   118 +
 .../L2B-B-REVISION-AUTHORIZATION.md                |    58 +
 .../L3-G0-ADOPTION-BOUNDARY-DESIGN.md              |   335 +
 .../L3-G0-INDEPENDENT-REVIEW-20260730.md           |    99 +
 .../L3-P0-AM1-CORRECTION-DESIGN-20260801.md        |    83 +
 ...P0-AM1-IMPLEMENTATION-AUTHORIZATION-20260801.md |    78 +
 ...P0-AM2-IMPLEMENTATION-AUTHORIZATION-20260801.md |    68 +
 ...L3-P0-AM3-IMPLEMENTATION-ACCEPTANCE-20260802.md |    55 +
 ...P0-AM3-IMPLEMENTATION-AUTHORIZATION-20260801.md |    75 +
 .../L3-P0-AUTHORIZATION-REVIEW-20260801.md         |    55 +
 .../L3-P0-IMPLEMENTATION-AUTHORIZATION-20260801.md |    48 +
 .../L3-P0-INDEPENDENT-REVIEW-20260801.md           |    91 +
 ...-P0-PROVENANCE-SHADOW-KERNEL-DESIGN-20260801.md |   262 +
 .../L3-P0-REV2-INDEPENDENT-REVIEW-20260801.md      |    50 +
 .../L3-P0-REV3-INDEPENDENT-REVIEW-20260801.md      |    28 +
 ...3-P1-COMPLETION-AND-PROGRESS-DESIGN-20260801.md |   142 +
 .../local-lane-performance/BASELINE-20260817.md    |    53 +
 .../DECOMPOSE-LOOP-BUILD-20260817.md               |    24 +
 .agents/plans/local-scaling-adaptive-offload.md    |   157 +
 .../plans/multi-agent-edge-harness/COMBINED-PRD.md |    88 +
 .../LIVE-VALIDATION-RUNBOOK.md                     |   112 +
 .../PARITY-INTEGRATION-PLAN.md                     |    77 +
 .../PROGRAM-PLAN.md                                |   289 +
 .agents/plans/osint-active-recon-gate-prd.md       |    38 +
 .agents/plans/osint-active-recon-gate.md           |    27 +
 .agents/plans/parity-gitlawb-zero-2026-07-08.md    |   241 +
 .../ANALYSIS-20260805.md                           |   100 +
 .agents/plans/phase-115-consolidated-plan.md       |   224 +
 .../plans/phase-115-system-intelligence-hub-prd.md |   260 +
 .agents/plans/phase-148-agentic-mind-research.md   |   125 +
 ...tion-reduce-delegated-prompt-failure-json-co.md |    40 +
 ...tion-reduce-delegated-prompt-failure-provide.md |    40 +
 .agents/plans/phase-171-inference-prd.md           |   366 +
 .agents/plans/phase-171A-inference-architecture.md |   109 +
 .../plans/phase-172-coordination-delegation-prd.md |   497 +
 .agents/plans/phase-173/.plan-lifecycle.json       |     7 +
 .agents/plans/phase-template.md                    |    29 +
 .agents/plans/phase0-keystone-zero-trust-plan.md   |   119 +
 .agents/plans/phase184A-delegation-fix-prd.md      |   568 +
 .agents/plans/phase184B-training-pipeline-prd.md   |   662 +
 .../plans/phase184C-dashboard-observability-prd.md |   577 +
 .agents/plans/phase185A-workflow-engine-prd.md     |   631 +
 .agents/plans/phase185B-autonomy-prsi-prd.md       |   706 +
 .agents/plans/plan-consensus/.plan-lifecycle.json  |     8 +
 .agents/plans/plan-consensus/AGGREGATE.md          |    80 +
 .agents/plans/plan-consensus/README.md             |    32 +
 .agents/plans/plan-consensus/antigravity.md        |    17 +
 .agents/plans/plan-consensus/claude.md             |    39 +
 .agents/plans/plan-consensus/codex.md              |    21 +
 .agents/plans/plan-consensus/local.md              |    21 +
 .agents/plans/pm-tracker-standard/DESIGN.md        |   111 +
 .../plans/pm-tracker-standard/SUPERSESSION-MAP.md  |    78 +
 .agents/plans/prd-consensus/.plan-lifecycle.json   |     8 +
 .agents/plans/prd-consensus/AGGREGATE.md           |    85 +
 .agents/plans/prd-consensus/README.md              |    23 +
 .agents/plans/prd-consensus/antigravity.md         |    22 +
 .agents/plans/prd-consensus/claude.md              |    38 +
 .agents/plans/prd-consensus/codex.md               |    18 +
 .agents/plans/prd-consensus/gemini.md              |    22 +
 .../precommit-subject-boundary/H0-DESIGN-PACKET.md |   243 +
 .../program-progress-tracker/.plan-lifecycle.json  |     8 +
 .../DASHBOARD-MONITOR-APPARMOR-ACCEPTANCE.md       |    39 +
 ...HBOARD-MONITOR-APPARMOR-AUTHORIZATION-REVIEW.md |    45 +
 .../DASHBOARD-MONITOR-APPARMOR-AUTHORIZATION.md    |    57 +
 .../program-progress-tracker/DESIGN-REVIEW.md      |    31 +
 .../IMPLEMENTATION-ACCEPTANCE-AM4.md               |    73 +
 .../IMPLEMENTATION-ACCEPTANCE.md                   |   356 +
 .../IMPLEMENTATION-AUTHORIZATION-AM1-REVIEW.md     |    64 +
 .../IMPLEMENTATION-AUTHORIZATION-AM1.md            |    81 +
 .../IMPLEMENTATION-AUTHORIZATION-AM2-REVIEW.md     |    61 +
 .../IMPLEMENTATION-AUTHORIZATION-AM2.md            |    76 +
 .../IMPLEMENTATION-AUTHORIZATION-AM3-REVIEW.md     |    70 +
 .../IMPLEMENTATION-AUTHORIZATION-AM3.md            |    81 +
 .../IMPLEMENTATION-AUTHORIZATION-AM4-REVIEW.md     |    57 +
 .../IMPLEMENTATION-AUTHORIZATION-AM4.md            |    84 +
 .../IMPLEMENTATION-AUTHORIZATION-REVIEW.md         |   109 +
 .../IMPLEMENTATION-AUTHORIZATION.md                |    74 +
 .../IMPLEMENTATION-PLAN.md                         |    44 +
 .../PM-DASHBOARD-LIVE-BUILD-20260817.md            |   106 +
 .../PRIOR-LEASE-RELEASE-AUDIT.md                   |    59 +
 .../A1-A2-ADOPTION-DESIGN-PACKET.md                |   356 +
 .../A1-A2-ADOPTION-REBIND-AMENDMENT.md             |    94 +
 .../A1-A2-ADOPTION-REBIND-REVIEW-R2.md             |    75 +
 .../A1-A2-ADOPTION-REBIND-REVIEW.md                |   126 +
 .../A1-AM1-IMPLEMENTATION-ACCEPTANCE.md            |   101 +
 .../A1-AM1-IMPLEMENTATION-AUTHORIZATION.md         |    78 +
 .../A1-AM2-AUTHORIZATION-REVIEW.md                 |   127 +
 .../A1-AM2-DESIGN-AMENDMENT.md                     |   182 +
 .../A1-AM2-IMPLEMENTATION-AUTHORIZATION.md         |    79 +
 .../A1-AM3-AM1-REPRODUCIBLE-REBIND.md              |    38 +
 .../A1-AM3-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md   |    65 +
 .../A1-AM3-CANDIDATE-ACCEPTANCE.md                 |   241 +
 .../A1-AM3-FINAL-REBIND-REVIEW.md                  |   106 +
 .../A1-AM3-FINAL-REBIND.md                         |   183 +
 .../A1-AM3-IMPLEMENTATION-AUTHORIZATION.md         |   147 +
 .../A1-AM3-PREREQUISITE-REBIND.md                  |    82 +
 .../A1-AM3-REV2-ACCEPTANCE-AUTHORIZATION.md        |    54 +
 .../A1-AM3-REV2-ACCEPTANCE.md                      |   218 +
 .../A1-AM3-REVISION-AUTHORIZATION.md               |    60 +
 .../A1-AM3-ROADMAP-RECOVERY-AUTHORIZATION.md       |    63 +
 .../A1-AM3-ROADMAP-VERIFIER-RECOVERY.md            |    93 +
 .../A1-IMPLEMENTATION-AUTHORIZATION.md             |    86 +
 .../A2-ADJACENCY-REBIND-R2-REVIEW.md               |   136 +
 .../A2-ADJACENCY-REBIND-R2.md                      |    56 +
 .../A2-ADJACENCY-REBIND-REVIEW.md                  |   140 +
 .../A2-ADJACENCY-REBIND.md                         |   186 +
 .../A2-AM1-IMPLEMENTATION-AUTHORIZATION.md         |   147 +
 .../A2-CANDIDATE-ACCEPTANCE.md                     |   129 +
 .../A2-CANDIDATE-CODEX-ACCEPTANCE-AUTHORIZATION.md |    64 +
 .../A2-CANDIDATE-REVISION-AUTHORIZATION.md         |    56 +
 .../A2-IMPLEMENTATION-AUTHORIZATION.md             |    78 +
 ...2-REVISED-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md |    54 +
 .../A2-REVISED-CANDIDATE-ACCEPTANCE.md             |    84 +
 .../C1-AUTHORIZATION-REVIEW.md                     |    92 +
 .../C1-IMPLEMENTATION-ACCEPTANCE.md                |    90 +
 .../C1-IMPLEMENTATION-AUTHORIZATION.md             |   300 +
 .../C1A-CONTRACT-AMENDMENT-DESIGN-PACKET.md        |   104 +
 .../C1A-IMPLEMENTATION-ACCEPTANCE.md               |    79 +
 .../C1A-IMPLEMENTATION-AUTHORIZATION.md            |    60 +
 .../C1B-AM1-AUTHORIZATION-REVIEW-R2.md             |    76 +
 .../C1B-AM1-AUTHORIZATION-REVIEW.md                |    81 +
 .../C1B-AM1-IMPLEMENTATION-ACCEPTANCE.md           |    85 +
 .../C1B-AM1-IMPLEMENTATION-AUTHORIZATION.md        |    67 +
 .../C1B-AM1-LIFECYCLE-ORDERING-DESIGN-PACKET.md    |    93 +
 .../C1B-IMPLEMENTATION-ACCEPTANCE.md               |    85 +
 .../C1B-IMPLEMENTATION-AUTHORIZATION.md            |    59 +
 .../C1B-OBSERVER-INTERFACE-DESIGN-PACKET.md        |   147 +
 .../C1C-A1-AM3-AUTHORIZATION-REVIEW.md             |   106 +
 .../C1C-AM1-AUTHORIZATION-REVIEW.md                |    68 +
 .../C1C-AM1-FAIL-STOP-SRE-AMENDMENT.md             |    97 +
 .../C1C-AM1-IMPLEMENTATION-AUTHORIZATION.md        |    51 +
 .../C1C-AM2-AUTHORIZATION-REVIEW.md                |    64 +
 .../C1C-AM2-CANDIDATE-REJECTION.md                 |    66 +
 .../C1C-AM2-IMPLEMENTATION-AUTHORIZATION.md        |    66 +
 .../C1C-AM2-OBSERVABLE-FAIL-STOP-AMENDMENT.md      |    87 +
 .../C1C-AM3-AUTHORIZATION-REVIEW-R2.md             |    73 +
 .../C1C-AM3-AUTHORIZATION-REVIEW.md                |    90 +
 .../C1C-AM3-CANDIDATE-ACCEPTANCE-AUTHORIZATION.md  |    67 +
 .../C1C-AM3-CANDIDATE-ACCEPTANCE.md                |   190 +
 .../C1C-AM3-IMPLEMENTATION-AUTHORIZATION.md        |   108 +
 .../C1C-AM3-SYNCHRONOUS-FAIL-STOP-AMENDMENT.md     |   137 +
 .../C1C-IMPLEMENTATION-AUTHORIZATION.md            |    52 +
 .../C1C-PUBLICATION-ACK-DESIGN-PACKET.md           |    98 +
 .../D0-DESIGN-PACKET.md                            |   264 +
 .../D0-DESIGN-REVIEW.md                            |   116 +
 .../QPPR-A1-A2-PREPARATION-REVIEW-R2.md            |   139 +
 .../QPPR-A1-A2-PREPARATION-REVIEW-R3.md            |   137 +
 .../QPPR-A1-A2-PREPARATION-REVIEW-R4.md            |    88 +
 .../QPPR-A1-A2-PREPARATION-REVIEW-R5.md            |   114 +
 .../QPPR-A1-A2-PREPARATION-REVIEW.md               |   139 +
 .../rejected/c1c-am2-haiku-process_lifecycle.py    |  1351 ++
 ...c-am2-haiku-test-qa-provider-probe-lifecycle.py |  1051 +
 .../reactivation-review-20260729/antigravity.md    |    47 +
 .agents/plans/reentry-intent/.round-dispatch.json  |     8 +
 .agents/plans/reentry-intent/.round-prompt.txt     |    69 +
 .agents/plans/reentry-intent/AGGREGATE.md          |    93 +
 .agents/plans/reentry-intent/INTENT.md             |    60 +
 .agents/plans/reentry-intent/README.md             |    14 +
 .agents/plans/reentry-intent/antigravity.md        |    60 +
 .agents/plans/reentry-intent/claude.md             |    76 +
 .agents/plans/reentry-intent/codex.md              |   136 +
 .agents/plans/reentry-intent/local.md              |    19 +
 .agents/plans/reentry-intent/round.json            |    77 +
 .agents/plans/round-slice2-slice3-2026-07-06.md    |   258 +
 .agents/plans/rsi-readiness/.round-dispatch.json   |     8 +
 .agents/plans/rsi-readiness/.round-prompt.txt      |    44 +
 .agents/plans/rsi-readiness/AGGREGATE.md           |    53 +
 .agents/plans/rsi-readiness/DELEGATION.md          |    41 +
 .agents/plans/rsi-readiness/README.md              |    52 +
 .agents/plans/rsi-readiness/ROUND-PROMPT.md        |    39 +
 .agents/plans/rsi-readiness/antigravity.md         |    43 +
 .agents/plans/rsi-readiness/attestations/R1.2.json |    30 +
 .agents/plans/rsi-readiness/attestations/R1.3.json |    32 +
 .agents/plans/rsi-readiness/attestations/R5.1.json |    31 +
 .agents/plans/rsi-readiness/claude.md              |    36 +
 .agents/plans/rsi-readiness/codex.md               |    43 +
 .agents/plans/rsi-readiness/local.json             |    21 +
 .agents/plans/rsi-readiness/local.md               |    31 +
 .agents/plans/rsi-readiness/round.json             |    77 +
 .../CODEX-DESIGN-REVIEW.md                         |    30 +
 ...ECURITY-VALIDATION-RELIABILITY-DESIGN-PACKET.md |   372 +
 .../TEMPORAL-GUARD-ACCEPTANCE.md                   |    50 +
 .agents/plans/slice0-bringup-runbook-2026-07-06.md |    81 +
 .agents/plans/stream-auth-rereview/README.md       |    14 +
 .agents/plans/stream-auth-rereview/antigravity.md  |    38 +
 .agents/plans/stream-auth-rereview/claude.md       |   122 +
 .agents/plans/stream-auth-rereview/round.json      |    73 +
 .agents/plans/system-capability-catalog.md         |    19 +
 .../plans/tiered-agent-memory/.plan-lifecycle.json |     7 +
 .agents/plans/unified-program/.round-dispatch.json |     8 +
 .agents/plans/unified-program/.round-prompt.txt    |     6 +
 .../ACTIVATION-AND-CLOSEOUT-WORKLIST.md            |   106 +
 .agents/plans/unified-program/AGGREGATE.md         |   107 +
 .agents/plans/unified-program/AMENDMENTS-A1-A6.md  |    42 +
 .../C03-TRACKER-AM3-INDEPENDENT-REVIEW-20260801.md |   104 +
 .../unified-program/EXECUTION-READINESS-QUEUE.md   |   111 +
 .../unified-program/LANE-ELIGIBILITY-MATRIX.md     |    34 +
 .../unified-program/OWNER-ACTIVATION-RECORDS.md    |    57 +
 .../plans/unified-program/OWNER-DECISION-SHEET.md  |    49 +
 .../Q1-Q2-OWNER-RATIFICATION-20260718.md           |    57 +
 .../Q1-Q2-OWNER-RATIFICATION-REVIEW-20260718.md    |    67 +
 .../Q10-INFERENCE-BASELINE-20260725.md             |    63 +
 .../Q3-Q10-OWNER-RATIFICATION-20260723.md          |    73 +
 .agents/plans/unified-program/README.md            |    14 +
 .../TRACK-V-REVISION-REVIEW-PACKET.md              |    75 +
 .../antigravity-required-revisions-review.md       |    42 +
 .../plans/unified-program/antigravity-revision.md  |    55 +
 .agents/plans/unified-program/antigravity.md       |    98 +
 .agents/plans/unified-program/claude.md            |    93 +
 .agents/plans/unified-program/codex.md             |   133 +
 .agents/plans/unified-program/local.md             |    20 +
 .agents/plans/unified-program/round.json           |    73 +
 .../.local-direct-retry-full-prompt.txt            |    34 +
 .../.local-direct-retry-prompt.txt                 |    32 +
 .../usability-parity-v2/.local-retry-prompt.txt    |    19 +
 .../plans/usability-parity-v2/.round-dispatch.json |     8 +
 .../plans/usability-parity-v2/.round-prompt.txt    |   195 +
 .agents/plans/usability-parity-v2/AGGREGATE.md     |    90 +
 .agents/plans/usability-parity-v2/README.md        |   203 +
 .agents/plans/usability-parity-v2/antigravity.md   |   191 +
 .agents/plans/usability-parity-v2/claude.md        |   120 +
 .agents/plans/usability-parity-v2/codex.md         |   137 +
 .agents/plans/usability-parity-v2/local.md         |    32 +
 .agents/plans/usability-parity-v2/round.json       |    77 +
 .../plans/usability-parity/.plan-lifecycle.json    |     8 +
 .../plans/usability-parity/CONSOLIDATED-PLAN.md    |   121 +
 .agents/plans/usability-parity/antigravity.md      |   171 +
 .agents/plans/usability-parity/codex.md            |   150 +
 .../verified-factory/VF-7-CODEX-ACCEPTANCE.md      |    35 +
 .../VF-7-EVIDENCE-PATH-AUTHORIZATION.md            |    91 +
 .../plans/verified-factory/VF-7-FLAGSHIP-REVIEW.md |    43 +
 .../C0-DESIGN-PACKET-20260808.md                   |    52 +
 .../C1A-DESIGN-PACKET-20260808.md                  |    31 +
 .../C1B-DESIGN-PACKET-20260808.md                  |   239 +
 ..._HARNESS_USABILITY_PARITY_EXPERT_TEAM_PROMPT.md |   189 +
 .../prompts/AQOS_OWNER_NEXT_CYCLE_META_PROMPT.md   |   372 +
 .../prompts/CLOUDFLARE_SOFTWARE_FACTORY_PARITY.md  |    32 +
 .agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md    |   212 +
 .../prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md |   241 +
 .../LOCAL-AI-FACTORY-NEXT-CYCLE-META-PROMPT.md     |   208 +
 .agents/prompts/TOKENOMICS_PARITY_TEAM_HANDOFF.md  |   172 +
 .../prompts/VERIFIED-FACTORY-CYCLE-META-PROMPT.md  |   132 +
 .../phase30-6-bootstrap-injection-gemini.md        |   103 +
 .agents/prompts/phase30-6-bootstrap-injection.md   |   120 +
 .agents/prompts/phase30-research.md                |    28 +
 .agents/prompts/phase30-status-review.md           |    27 +
 .agents/prompts/phase33-1-skill-schema.md          |    50 +
 .agents/prompts/phase33-4-output-compression.md    |    72 +
 .agents/scripts/telemetry_audit.py                 |    13 +
 .../summary/FINAL-SESSION-SUMMARY-2026-03-20.md    |   483 +
 .../summary/FINAL-SESSION-SUMMARY-2026-03-21.md    |   685 +
 .../summary/IMPLEMENTATION-STATUS-2026-04-09.md    |   427 +
 .agents/summary/PHASE-11-VALIDATION-REPORT.md      |   670 +
 .agents/summary/PHASE-3-COMPLETION-2026-04-14.md   |   263 +
 .agents/summary/PHASE-4-COLLABORATION-SUMMARY.md   |   425 +
 .agents/summary/PHASE-4-FINAL-VALIDATION.md        |   309 +
 .agents/summary/ROADMAP-PROGRESS-2026-04-11.md     |   395 +
 ...SSION-COMPLETION-REPORT-2026-03-20-CONTINUED.md |   559 +
 .../SESSION-COMPLETION-REPORT-2026-03-20.md        |   511 +
 .agents/summary/advisor-strategy-design.md         |   383 +
 ...harness-comprehensive-analysis-v2-2026-04-09.md |   905 +
 .../ai-harness-parity-analysis-2026-04-09.md       |   980 +
 .../audits/bolt-on-features-audit-2026-03.md       |   770 +
 .../audits/deployment-scripts-audit-2026-03.md     |   165 +
 .agents/summary/brownfield-PDR-20260309-002320.md  |    51 +
 .agents/summary/brownfield-PDR-20260406-221711.md  |    51 +
 .agents/summary/brownfield-PDR-20260407-034035.md  |    51 +
 .agents/summary/brownfield-PDR-20260419-021048.md  |    51 +
 .agents/summary/brownfield-PDR-20260419-024534.md  |    51 +
 .agents/summary/brownfield-PDR-20260419-030703.md  |   107 +
 .agents/summary/consolidation-status-20260419.md   |   107 +
 .../harness-optimization-prompt-2026-04-09.md      |   152 +
 .../summary/openrouter-config-status-2026-04-09.md |   101 +
 .../baseline_20260409_215323.json                  |  1036 +
 .../baseline_20260409_215323.txt                   |   193 +
 .../baseline_20260409_215600.json                  |  1036 +
 .../baseline_20260409_215600.txt                   |   193 +
 .../baseline_20260409_215726.json                  |  1036 +
 .../baseline_20260409_215726.txt                   |   193 +
 .../optimized_20260409_215903.json                 |   982 +
 .../optimized_20260409_215903.txt                  |   186 +
 .../summary/performance-optimization-2026-04-18.md |   197 +
 .../phase-2-completion-report-2026-04-16.md        |   553 +
 .../phase-2-status-assessment-2026-04-14.md        |   321 +
 .agents/summary/session-primer-summary.json        |    22 +
 .agents/summary/session-summary-2026-04-09.md      |   329 +
 .agents/summary/strands-integration-complete.md    |   124 +
 .../token-spending-assessment-2026-06-01.md        |    38 +
 .../ui-ux-completeness-analysis-2026-04-09.md      |   690 +
 .agents/tasks/systemd-env-quoting-issue.md         |    78 +
 .agents/telemetry/training-loop-progress.json      |    10 +
 .aider.md                                          |    35 +
 .aiexclude                                         |    37 +
 .claude/CLAUDE.md                                  |   279 +
 .claude/README.md                                  |    49 +
 .claude/commands/brownfield.md                     |    17 +
 .claude/commands/commit.md                         |    17 +
 .claude/commands/create-prd.md                     |    26 +
 .claude/commands/execute.md                        |    22 +
 .claude/commands/explore-harness.md                |    22 +
 .claude/commands/impeccable.md                     |   108 +
 .claude/commands/plan-feature.md                   |    21 +
 .claude/commands/prime.md                          |    52 +
 .claude/commands/primer.md                         |    17 +
 .claude/commands/project-init.md                   |    18 +
 .claude/commands/trading-analysis.md               |    99 +
 .claude/rules/lean-ctx.md                          |    34 +
 .env.example                                       |     4 +
 .gemini/context.md                                 |    87 +
 .gemini/primer-summary.md                          |    49 +
 .gemini/settings.json                              |    56 +
 .githooks/README.md                                |    93 +
 .githooks/pre-commit                               |   258 +
 .githooks/pre-push                                 |   112 +
 .github/CODEOWNERS                                 |    25 +
 .github/FUNDING.yml                                |    12 +
 .github/workflows/gitleaks.yml                     |    46 +
 .github/workflows/harness-sdk-release.yml          |   146 +
 .github/workflows/memory-benchmarks.yml            |    40 +
 .github/workflows/nix-build.yml                    |    40 +
 .github/workflows/rust-tests.yml.disabled          |    72 +
 .github/workflows/security.yml                     |   305 +
 .github/workflows/shellcheck.yml                   |    48 +
 .github/workflows/test-coverage.yml                |    41 +
 .github/workflows/test.yml                         |   880 +
 .github/workflows/tests-legacy.yml                 |    84 +
 .github/workflows/tests.yml                        |    90 +
 .github/workflows/validate-shell-scripts.yml       |    75 +
 .gitignore                                         |   336 +
 .gitleaks.toml                                     |    28 +
 .pre-commit-config.yaml                            |    24 +
 .qwen/SESSION-RULES.md                             |   144 +
 .qwen/settings.json                                |    73 +
 .qwen/settings.json.orig                           |    73 +
 .sops.yaml                                         |     9 +
 .trivyignore                                       |    15 +
 .understand-anything/.understandignore             |   187 +
 .understand-anything/knowledge-graph.json          |     1 +
 .understand-anything/wiki/.wiki-meta.json          |    57 +
 .understand-anything/wiki/README.md                |    58 +
 .understand-anything/wiki/agent-runtimes.md        |    33 +
 .understand-anything/wiki/ai-scripts.md            |    91 +
 .understand-anything/wiki/aidb.md                  |    97 +
 .understand-anything/wiki/configuration.md         |    37 +
 .understand-anything/wiki/governance.md            |    51 +
 .understand-anything/wiki/hybrid-coordinator.md    |   103 +
 .understand-anything/wiki/local-agent.md           |   101 +
 .understand-anything/wiki/nix-hosts.md             |    40 +
 .understand-anything/wiki/nix-modules.md           |    55 +
 .understand-anything/wiki/switchboard.md           |    32 +
 .understand-anything/wiki/testing.md               |    83 +
 .vscode.configs.import.cspell.config.json          |     6 +
 AGENTS.md                                          |   318 +
 CLAUDE.md                                          |     1 +
 Cargo.lock                                         |     7 +
 Cargo.toml                                         |     3 +
 LICENSE                                            |    21 +
 Makefile                                           |    43 +
 README.md                                          |   642 +
 ai-knowledge-base/HYBRID-LEARNING-ARCHITECTURE.md  |   689 +
 ai-knowledge-base/README.md                        |    90 +
 .../mcp-servers/ai-llm-development.json            |   277 +
 ai-knowledge-base/mcp-servers/coding-agents.json   |   305 +
 .../mcp-servers/nixos-development.json             |   171 +
 .../mcp-servers/vm-qemu-development.json           |   228 +
 ai-knowledge-base/reference/llama-cpp-api.md       |    41 +
 .../reference/nixpkgs-25.05-release-notes.md       |   242 +
 .../reference/nixpkgs-25.11-release-notes.md       |   226 +
 .../reference/nixpkgs-26.05-release-notes.md       |    25 +
 .../reference/postgresql-release-notes-17.5.md     |    67 +
 .../reference/postgresql-release-notes-17.6.md     |    77 +
 .../reference/postgresql-release-notes-17.7.md     |    71 +
 .../reference/postgresql-release-notes-18.0.md     |   224 +
 .../reference/postgresql-release-notes-18.1.md     |    59 +
 .../reference/prsi/prsi-research-fallback-notes.md |    19 +
 .../reference/prsi/prsi-research-index-2026-03.md  |    53 +
 ai-stack/AUTO-START-GUIDE.md                       |     5 +
 ai-stack/__init__.py                               |     0
 ai-stack/affective-engine/__init__.py              |     0
 ai-stack/affective-engine/output_modulator.py      |    42 +
 ai-stack/affective-engine/reciprocity_tracker.py   |    83 +
 ai-stack/affective-engine/signal_detectors.py      |   109 +
 ai-stack/affective-engine/state_model.py           |    63 +
 ai-stack/agent-memory/MEMORY.md                    |   190 +
 ai-stack/agent-memory/__init__.py                  |     6 +
 ai-stack/agent-memory/dag_manager.py               |   174 +
 ai-stack/agents/README.md                          |   573 +
 ai-stack/agents/orchestrator/README.md             |   147 +
 ai-stack/agents/runtimes/local_agent_runtime.py    |  1481 ++
 .../agents/runtimes/test_local_agent_runtime.py    |   383 +
 ai-stack/agents/shared/README.md                   |   282 +
 ai-stack/agents/skills/AGENTS.md                   |   184 +
 .../agents/skills/ai-service-management/SKILL.md   |    67 +
 ai-stack/agents/skills/aidb-knowledge/SKILL.md     |   140 +
 ai-stack/agents/skills/all-mcp-directory/SKILL.md  |   147 +
 .../agents/skills/brand-guidelines/LICENSE.txt     |   202 +
 ai-stack/agents/skills/brand-guidelines/SKILL.md   |    77 +
 ai-stack/agents/skills/canvas-design/LICENSE.txt   |   202 +
 ai-stack/agents/skills/canvas-design/SKILL.md      |   130 +
 .../canvas-design/canvas-fonts/ArsenalSC-OFL.txt   |    93 +
 .../canvas-fonts/ArsenalSC-Regular.ttf             |   Bin 0 -> 165848 bytes
 .../canvas-fonts/BigShoulders-Bold.ttf             |   Bin 0 -> 94528 bytes
 .../canvas-fonts/BigShoulders-OFL.txt              |    93 +
 .../canvas-fonts/BigShoulders-Regular.ttf          |   Bin 0 -> 94396 bytes
 .../canvas-design/canvas-fonts/Boldonse-OFL.txt    |    93 +
 .../canvas-fonts/Boldonse-Regular.ttf              |   Bin 0 -> 77168 bytes
 .../canvas-fonts/BricolageGrotesque-Bold.ttf       |   Bin 0 -> 90952 bytes
 .../canvas-fonts/BricolageGrotesque-OFL.txt        |    93 +
 .../canvas-fonts/BricolageGrotesque-Regular.ttf    |   Bin 0 -> 90920 bytes
 .../canvas-design/canvas-fonts/CrimsonPro-Bold.ttf |   Bin 0 -> 107352 bytes
 .../canvas-fonts/CrimsonPro-Italic.ttf             |   Bin 0 -> 108828 bytes
 .../canvas-design/canvas-fonts/CrimsonPro-OFL.txt  |    93 +
 .../canvas-fonts/CrimsonPro-Regular.ttf            |   Bin 0 -> 106696 bytes
 .../canvas-design/canvas-fonts/DMMono-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/DMMono-Regular.ttf  |   Bin 0 -> 48852 bytes
 .../canvas-design/canvas-fonts/EricaOne-OFL.txt    |    94 +
 .../canvas-fonts/EricaOne-Regular.ttf              |   Bin 0 -> 24872 bytes
 .../canvas-design/canvas-fonts/GeistMono-Bold.ttf  |   Bin 0 -> 78304 bytes
 .../canvas-design/canvas-fonts/GeistMono-OFL.txt   |    93 +
 .../canvas-fonts/GeistMono-Regular.ttf             |   Bin 0 -> 78232 bytes
 .../canvas-design/canvas-fonts/Gloock-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Gloock-Regular.ttf  |   Bin 0 -> 95156 bytes
 .../canvas-fonts/IBMPlexMono-Bold.ttf              |   Bin 0 -> 136008 bytes
 .../canvas-design/canvas-fonts/IBMPlexMono-OFL.txt |    93 +
 .../canvas-fonts/IBMPlexMono-Regular.ttf           |   Bin 0 -> 133796 bytes
 .../canvas-fonts/IBMPlexSerif-Bold.ttf             |   Bin 0 -> 161000 bytes
 .../canvas-fonts/IBMPlexSerif-BoldItalic.ttf       |   Bin 0 -> 169840 bytes
 .../canvas-fonts/IBMPlexSerif-Italic.ttf           |   Bin 0 -> 170004 bytes
 .../canvas-fonts/IBMPlexSerif-Regular.ttf          |   Bin 0 -> 160380 bytes
 .../canvas-fonts/InstrumentSans-Bold.ttf           |   Bin 0 -> 68084 bytes
 .../canvas-fonts/InstrumentSans-BoldItalic.ttf     |   Bin 0 -> 70004 bytes
 .../canvas-fonts/InstrumentSans-Italic.ttf         |   Bin 0 -> 69900 bytes
 .../canvas-fonts/InstrumentSans-OFL.txt            |    93 +
 .../canvas-fonts/InstrumentSans-Regular.ttf        |   Bin 0 -> 68028 bytes
 .../canvas-fonts/InstrumentSerif-Italic.ttf        |   Bin 0 -> 70868 bytes
 .../canvas-fonts/InstrumentSerif-Regular.ttf       |   Bin 0 -> 69312 bytes
 .../canvas-design/canvas-fonts/Italiana-OFL.txt    |    93 +
 .../canvas-fonts/Italiana-Regular.ttf              |   Bin 0 -> 27184 bytes
 .../canvas-fonts/JetBrainsMono-Bold.ttf            |   Bin 0 -> 114828 bytes
 .../canvas-fonts/JetBrainsMono-OFL.txt             |    93 +
 .../canvas-fonts/JetBrainsMono-Regular.ttf         |   Bin 0 -> 114904 bytes
 .../canvas-design/canvas-fonts/Jura-Light.ttf      |   Bin 0 -> 154308 bytes
 .../canvas-design/canvas-fonts/Jura-Medium.ttf     |   Bin 0 -> 154488 bytes
 .../skills/canvas-design/canvas-fonts/Jura-OFL.txt |    93 +
 .../canvas-fonts/LibreBaskerville-OFL.txt          |    93 +
 .../canvas-fonts/LibreBaskerville-Regular.ttf      |   Bin 0 -> 147584 bytes
 .../canvas-design/canvas-fonts/Lora-Bold.ttf       |   Bin 0 -> 133828 bytes
 .../canvas-design/canvas-fonts/Lora-BoldItalic.ttf |   Bin 0 -> 140332 bytes
 .../canvas-design/canvas-fonts/Lora-Italic.ttf     |   Bin 0 -> 139328 bytes
 .../skills/canvas-design/canvas-fonts/Lora-OFL.txt |    93 +
 .../canvas-design/canvas-fonts/Lora-Regular.ttf    |   Bin 0 -> 133888 bytes
 .../canvas-fonts/NationalPark-Bold.ttf             |   Bin 0 -> 79208 bytes
 .../canvas-fonts/NationalPark-OFL.txt              |    93 +
 .../canvas-fonts/NationalPark-Regular.ttf          |   Bin 0 -> 76424 bytes
 .../canvas-fonts/NothingYouCouldDo-OFL.txt         |    93 +
 .../canvas-fonts/NothingYouCouldDo-Regular.ttf     |   Bin 0 -> 32020 bytes
 .../canvas-design/canvas-fonts/Outfit-Bold.ttf     |   Bin 0 -> 55392 bytes
 .../canvas-design/canvas-fonts/Outfit-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Outfit-Regular.ttf  |   Bin 0 -> 54912 bytes
 .../canvas-fonts/PixelifySans-Medium.ttf           |   Bin 0 -> 51072 bytes
 .../canvas-fonts/PixelifySans-OFL.txt              |    93 +
 .../canvas-design/canvas-fonts/PoiretOne-OFL.txt   |    93 +
 .../canvas-fonts/PoiretOne-Regular.ttf             |   Bin 0 -> 45244 bytes
 .../canvas-design/canvas-fonts/RedHatMono-Bold.ttf |   Bin 0 -> 34420 bytes
 .../canvas-design/canvas-fonts/RedHatMono-OFL.txt  |    93 +
 .../canvas-fonts/RedHatMono-Regular.ttf            |   Bin 0 -> 34488 bytes
 .../canvas-design/canvas-fonts/Silkscreen-OFL.txt  |    93 +
 .../canvas-fonts/Silkscreen-Regular.ttf            |   Bin 0 -> 31960 bytes
 .../canvas-fonts/SmoochSans-Medium.ttf             |   Bin 0 -> 59704 bytes
 .../canvas-design/canvas-fonts/SmoochSans-OFL.txt  |    93 +
 .../canvas-design/canvas-fonts/Tektur-Medium.ttf   |   Bin 0 -> 76248 bytes
 .../canvas-design/canvas-fonts/Tektur-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Tektur-Regular.ttf  |   Bin 0 -> 75604 bytes
 .../canvas-design/canvas-fonts/WorkSans-Bold.ttf   |   Bin 0 -> 191304 bytes
 .../canvas-fonts/WorkSans-BoldItalic.ttf           |   Bin 0 -> 175772 bytes
 .../canvas-design/canvas-fonts/WorkSans-Italic.ttf |   Bin 0 -> 174280 bytes
 .../canvas-design/canvas-fonts/WorkSans-OFL.txt    |    93 +
 .../canvas-fonts/WorkSans-Regular.ttf              |   Bin 0 -> 188916 bytes
 .../canvas-design/canvas-fonts/YoungSerif-OFL.txt  |    93 +
 .../canvas-fonts/YoungSerif-Regular.ttf            |   Bin 0 -> 105136 bytes
 ai-stack/agents/skills/example_market_analysis.py  |   199 +
 ai-stack/agents/skills/example_rf_monitoring.py    |   276 +
 ai-stack/agents/skills/frontend-design/LICENSE.txt |   177 +
 ai-stack/agents/skills/frontend-design/SKILL.md    |    46 +
 ai-stack/agents/skills/health-monitoring/SKILL.md  |   107 +
 ai-stack/agents/skills/internal-comms/LICENSE.txt  |   202 +
 ai-stack/agents/skills/internal-comms/SKILL.md     |    36 +
 .../skills/internal-comms/examples/3p-updates.md   |    47 +
 .../internal-comms/examples/company-newsletter.md  |    65 +
 .../skills/internal-comms/examples/faq-answers.md  |    30 +
 .../internal-comms/examples/general-comms.md       |    16 +
 ai-stack/agents/skills/mcp-builder/LICENSE.txt     |   202 +
 ai-stack/agents/skills/mcp-builder/SKILL.md        |   246 +
 .../skills/mcp-builder/reference/evaluation.md     |   602 +
 .../mcp-builder/reference/mcp_best_practices.md    |   249 +
 .../mcp-builder/reference/node_mcp_server.md       |   970 +
 .../mcp-builder/reference/python_mcp_server.md     |   719 +
 .../skills/mcp-builder/scripts/connections.py      |   151 +
 .../skills/mcp-builder/scripts/evaluation.py       |   373 +
 .../mcp-builder/scripts/example_evaluation.xml     |    22 +
 .../skills/mcp-builder/scripts/requirements.txt    |     2 +
 ai-stack/agents/skills/mcp-server/SKILL.md         |    97 +
 ai-stack/agents/skills/memory-diagnostics/SKILL.md |    17 +
 .../agents/skills/memory-diagnostics/__init__.py   |     2 +
 ai-stack/agents/skills/memory-diagnostics/test.py  |     4 +
 ai-stack/agents/skills/nixos-deployment/SKILL.md   |   549 +
 ai-stack/agents/skills/pdf/LICENSE.txt             |    30 +
 ai-stack/agents/skills/pdf/SKILL.md                |   298 +
 ai-stack/agents/skills/pdf/forms.md                |   205 +
 ai-stack/agents/skills/pdf/reference.md            |   612 +
 .../skills/pdf/scripts/check_bounding_boxes.py     |    70 +
 .../skills/pdf/scripts/check_fillable_fields.py    |    12 +
 .../skills/pdf/scripts/convert_pdf_to_images.py    |    35 +
 .../skills/pdf/scripts/create_validation_image.py  |    41 +
 .../skills/pdf/scripts/extract_form_field_info.py  |   152 +
 .../skills/pdf/scripts/fill_fillable_fields.py     |   114 +
 .../pdf/scripts/fill_pdf_form_with_annotations.py  |   108 +
 ai-stack/agents/skills/pptx/LICENSE.txt            |    30 +
 ai-stack/agents/skills/pptx/SKILL.md               |   484 +
 ai-stack/agents/skills/pptx/html2pptx.md           |   625 +
 ai-stack/agents/skills/pptx/ooxml.md               |   427 +
 .../schemas/ISO-IEC29500-4_2016/dml-chart.xsd      |  1499 ++
 .../ISO-IEC29500-4_2016/dml-chartDrawing.xsd       |   146 +
 .../schemas/ISO-IEC29500-4_2016/dml-diagram.xsd    |  1085 +
 .../ISO-IEC29500-4_2016/dml-lockedCanvas.xsd       |    11 +
 .../ooxml/schemas/ISO-IEC29500-4_2016/dml-main.xsd |  3081 +++
 .../schemas/ISO-IEC29500-4_2016/dml-picture.xsd    |    23 +
 .../ISO-IEC29500-4_2016/dml-spreadsheetDrawing.xsd |   185 +
 .../dml-wordprocessingDrawing.xsd                  |   287 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/pml.xsd |  1676 ++
 .../shared-additionalCharacteristics.xsd           |    28 +
 .../ISO-IEC29500-4_2016/shared-bibliography.xsd    |   144 +
 .../shared-commonSimpleTypes.xsd                   |   174 +
 .../shared-customXmlDataProperties.xsd             |    25 +
 .../shared-customXmlSchemaProperties.xsd           |    18 +
 .../shared-documentPropertiesCustom.xsd            |    59 +
 .../shared-documentPropertiesExtended.xsd          |    56 +
 .../shared-documentPropertiesVariantTypes.xsd      |   195 +
 .../schemas/ISO-IEC29500-4_2016/shared-math.xsd    |   582 +
 .../shared-relationshipReference.xsd               |    25 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/sml.xsd |  4439 ++++
 .../ooxml/schemas/ISO-IEC29500-4_2016/vml-main.xsd |   570 +
 .../ISO-IEC29500-4_2016/vml-officeDrawing.xsd      |   509 +
 .../vml-presentationDrawing.xsd                    |    12 +
 .../ISO-IEC29500-4_2016/vml-spreadsheetDrawing.xsd |   108 +
 .../vml-wordprocessingDrawing.xsd                  |    96 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/wml.xsd |  3646 +++
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/xml.xsd |   116 +
 .../ecma/fouth-edition/opc-contentTypes.xsd        |    42 +
 .../ecma/fouth-edition/opc-coreProperties.xsd      |    50 +
 .../schemas/ecma/fouth-edition/opc-digSig.xsd      |    49 +
 .../ecma/fouth-edition/opc-relationships.xsd       |    33 +
 .../agents/skills/pptx/ooxml/schemas/mce/mc.xsd    |    75 +
 .../pptx/ooxml/schemas/microsoft/wml-2010.xsd      |   560 +
 .../pptx/ooxml/schemas/microsoft/wml-2012.xsd      |    67 +
 .../pptx/ooxml/schemas/microsoft/wml-2018.xsd      |    14 +
 .../pptx/ooxml/schemas/microsoft/wml-cex-2018.xsd  |    20 +
 .../pptx/ooxml/schemas/microsoft/wml-cid-2016.xsd  |    13 +
 .../schemas/microsoft/wml-sdtdatahash-2020.xsd     |     4 +
 .../ooxml/schemas/microsoft/wml-symex-2015.xsd     |     8 +
 ai-stack/agents/skills/pptx/ooxml/scripts/pack.py  |   159 +
 .../agents/skills/pptx/ooxml/scripts/unpack.py     |    29 +
 .../agents/skills/pptx/ooxml/scripts/validate.py   |    69 +
 .../pptx/ooxml/scripts/validation/__init__.py      |    15 +
 .../skills/pptx/ooxml/scripts/validation/base.py   |   951 +
 .../skills/pptx/ooxml/scripts/validation/docx.py   |   274 +
 .../skills/pptx/ooxml/scripts/validation/pptx.py   |   315 +
 .../pptx/ooxml/scripts/validation/redlining.py     |   279 +
 ai-stack/agents/skills/pptx/scripts/html2pptx.js   |   979 +
 ai-stack/agents/skills/pptx/scripts/inventory.py   |  1020 +
 ai-stack/agents/skills/pptx/scripts/rearrange.py   |   231 +
 ai-stack/agents/skills/pptx/scripts/replace.py     |   385 +
 ai-stack/agents/skills/pptx/scripts/thumbnail.py   |   450 +
 ai-stack/agents/skills/project-import/SKILL.md     |    66 +
 ai-stack/agents/skills/rag-techniques/SKILL.md     |    91 +
 ai-stack/agents/skills/ralph-wiggum.md             |   395 +
 ai-stack/agents/skills/skill-creator/LICENSE.txt   |   202 +
 ai-stack/agents/skills/skill-creator/SKILL.md      |   366 +
 .../skill-creator/references/output-patterns.md    |    82 +
 .../skills/skill-creator/references/workflows.md   |    28 +
 .../skills/skill-creator/scripts/init_skill.py     |   303 +
 .../skills/skill-creator/scripts/package_skill.py  |   110 +
 .../skills/skill-creator/scripts/quick_validate.py |    95 +
 .../agents/skills/slack-gif-creator/LICENSE.txt    |   202 +
 ai-stack/agents/skills/slack-gif-creator/SKILL.md  |   254 +
 .../slack-gif-creator/core/color_palettes.py       |   302 +
 .../agents/skills/slack-gif-creator/core/easing.py |   234 +
 .../slack-gif-creator/core/frame_composer.py       |   176 +
 .../skills/slack-gif-creator/core/gif_builder.py   |   269 +
 .../skills/slack-gif-creator/core/typography.py    |   357 +
 .../skills/slack-gif-creator/core/validators.py    |   136 +
 .../slack-gif-creator/core/visual_effects.py       |   494 +
 .../skills/slack-gif-creator/requirements.txt      |     4 +
 .../skills/slack-gif-creator/templates/bounce.py   |   106 +
 .../skills/slack-gif-creator/templates/explode.py  |   331 +
 .../skills/slack-gif-creator/templates/fade.py     |   329 +
 .../skills/slack-gif-creator/templates/flip.py     |   291 +
 .../slack-gif-creator/templates/kaleidoscope.py    |   211 +
 .../skills/slack-gif-creator/templates/morph.py    |   329 +
 .../skills/slack-gif-creator/templates/move.py     |   293 +
 .../skills/slack-gif-creator/templates/pulse.py    |   268 +
 .../skills/slack-gif-creator/templates/shake.py    |   127 +
 .../skills/slack-gif-creator/templates/slide.py    |   291 +
 .../skills/slack-gif-creator/templates/spin.py     |   269 +
 .../skills/slack-gif-creator/templates/wiggle.py   |   300 +
 .../skills/slack-gif-creator/templates/zoom.py     |   312 +
 ai-stack/agents/skills/system_bootstrap/SKILL.md   |    54 +
 ai-stack/agents/skills/template-skill/SKILL.md     |    10 +
 ai-stack/agents/skills/theme-factory/LICENSE.txt   |   202 +
 ai-stack/agents/skills/theme-factory/SKILL.md      |    63 +
 .../agents/skills/theme-factory/theme-showcase.pdf |   Bin 0 -> 124310 bytes
 .../skills/theme-factory/themes/arctic-frost.md    |    19 +
 .../theme-factory/themes/botanical-garden.md       |    19 +
 .../skills/theme-factory/themes/desert-rose.md     |    19 +
 .../skills/theme-factory/themes/forest-canopy.md   |    19 +
 .../skills/theme-factory/themes/golden-hour.md     |    19 +
 .../skills/theme-factory/themes/midnight-galaxy.md |    19 +
 .../theme-factory/themes/modern-minimalist.md      |    19 +
 .../skills/theme-factory/themes/ocean-depths.md    |    19 +
 .../theme-factory/themes/sunset-boulevard.md       |    19 +
 .../skills/theme-factory/themes/tech-innovation.md |    19 +
 .../skills/web-artifacts-builder/LICENSE.txt       |   202 +
 .../agents/skills/web-artifacts-builder/SKILL.md   |    74 +
 .../scripts/bundle-artifact.sh                     |    54 +
 .../web-artifacts-builder/scripts/init-artifact.sh |   322 +
 .../scripts/shadcn-components.tar.gz               |   Bin 0 -> 19967 bytes
 ai-stack/agents/skills/webapp-testing/LICENSE.txt  |   202 +
 ai-stack/agents/skills/webapp-testing/SKILL.md     |   102 +
 .../webapp-testing/examples/console_logging.py     |    35 +
 .../webapp-testing/examples/element_discovery.py   |    44 +
 .../examples/static_html_automation.py             |    33 +
 .../skills/webapp-testing/scripts/with_server.py   |   106 +
 ai-stack/agents/skills/xlsx/LICENSE.txt            |    30 +
 ai-stack/agents/skills/xlsx/SKILL.md               |   292 +
 ai-stack/agents/skills/xlsx/recalc.py              |   178 +
 ai-stack/aidb/__init__.py                          |     0
 ai-stack/aidb/agent_diary.py                       |   448 +
 ai-stack/aidb/benchmarks/BASELINE-METRICS.md       |   453 +
 ai-stack/aidb/benchmarks/aq-benchmark              |   530 +
 .../aidb/benchmarks/memory-benchmark-corpus.json   |  1250 ++
 ai-stack/aidb/benchmarks/performance_bench.py      |   544 +
 ai-stack/aidb/benchmarks/recall_accuracy.py        |   626 +
 ai-stack/aidb/code_change_indexer.py               |   806 +
 ai-stack/aidb/identity_manager.py                  |   267 +
 ai-stack/aidb/interaction_indexer.py               |   488 +
 ai-stack/aidb/layered_loading.py                   |   531 +
 ai-stack/aidb/schema/interaction-history-v1.sql    |    76 +
 .../aidb/schema/migrations/001_temporal_facts.sql  |   403 +
 ai-stack/aidb/schema/temporal-facts-v2.sql         |   250 +
 ai-stack/aidb/temporal_facts.py                    |   353 +
 ai-stack/aidb/temporal_query.py                    |   494 +
 .../test_code_change_indexer_keyword_hints.py      |   118 +
 ai-stack/aidb/tests/test_layered_loading.py        |   401 +
 ai-stack/aidb/tests/test_temporal_facts.py         |   511 +
 ai-stack/aidb/tests/test_temporal_query.py         |   515 +
 ai-stack/aidb/tests/test_vector_indexing.py        |   247 +
 .../autonomous-improvement/ACTIVATION-STATUS.md    |   277 +
 ai-stack/autonomous-improvement/DEPLOYMENT.md      |   348 +
 ai-stack/autonomous-improvement/README.md          |   319 +
 ai-stack/autonomous-improvement/autonomous_loop.py |   548 +
 .../autonomous-improvement/experiment_executor.py  |   292 +
 ai-stack/autonomous-improvement/requirements.txt   |     2 +
 ai-stack/autonomous-improvement/research_phase.py  |   511 +
 .../autonomous-improvement/sandbox_validator.py    |   243 +
 ai-stack/autonomous-improvement/trend_database.py  |   607 +
 ai-stack/autonomous-improvement/trigger_engine.py  |   389 +
 ai-stack/autoresearch/autoresearch.py              |   570 +
 ai-stack/autoresearch/experiments.sqlite           |   Bin 0 -> 24576 bytes
 ai-stack/autoresearch/local_model_optimizer.py     |   371 +
 .../capability-gap/failure_pattern_analysis.py     |  1161 +
 ai-stack/capability-gap/gap_detection.py           |   513 +
 ai-stack/capability-gap/gap_remediation.py         |   782 +
 ai-stack/capability-gap/remediation_learning.py    |   642 +
 ai-stack/conftest.py                               |    64 +
 ai-stack/context_memory/context_manager.py         |   574 +
 ai-stack/continue/config.json                      |   228 +
 ai-stack/cron/tls-cert-monitoring                  |    13 +
 ai-stack/data/knowledge-sources.yaml               |  1174 +
 ai-stack/data/tool-recommendations-seed.yaml       |  1312 ++
 .../migrations/V20__world_model_query_patterns.sql |    19 +
 ai-stack/database/postgres/migrations/env.py       |    60 +
 .../versions/0001_create_tool_registry.py          |    24 +
 .../migrations/versions/0002_imported_documents.py |    44 +
 .../migrations/versions/0003_open_skills.py        |    32 +
 .../versions/0004_open_skills_source_url.py        |    20 +
 .../versions/0005_pgvector_embeddings.py           |    50 +
 .../versions/0006_codemachine_workflows.py         |    70 +
 .../migrations/versions/0007_status_flags.py       |    45 +
 .../versions/0008_create_system_registry_table.py  |    59 +
 .../versions/0009_populate_system_registry.py      |    70 +
 .../database/postgres/schemas/context-scan.json    |    15 +
 ai-stack/database/postgres/schemas/draft-plan.json |    11 +
 .../postgres/schemas/final-aggregation.json        |    15 +
 ai-stack/database/postgres/schemas/web-brief.json  |    14 +
 ai-stack/deployment/auto_deployer.py               |   570 +
 ai-stack/docs/tooling-registry.md                  |   163 +
 ai-stack/efficiency/context_management.py          |   573 +
 ai-stack/efficiency/prompt_compression.py          |   548 +
 ai-stack/efficiency/semantic_compression.py        |   994 +
 ai-stack/embedding-cache/embedding_cache.py        |   359 +
 ai-stack/eval/promptfoo-config.yaml                |   216 +
 ai-stack/eval/results/eval-20260224T092035Z.json   |  1328 ++
 ai-stack/eval/results/eval-20260224T094733Z.json   |  1310 ++
 ai-stack/eval/results/eval-20260224T094847Z.json   |  1310 ++
 .../eval/results/eval-20260224T094940Z-summary.txt |     4 +
 ai-stack/eval/results/eval-20260224T094940Z.json   |  1310 ++
 .../eval/results/eval-20260224T095010Z-summary.txt |     4 +
 ai-stack/eval/results/eval-20260224T095010Z.json   |  1310 ++
 .../eval/results/eval-20260224T234702Z-summary.txt |     4 +
 ai-stack/eval/results/eval-20260224T234702Z.json   |  1310 ++
 .../eval/results/eval-20260226T231049Z-summary.txt |     4 +
 ai-stack/eval/results/eval-20260226T231049Z.json   |  1892 ++
 .../eval/results/eval-20260227T232322Z-summary.txt |     4 +
 ai-stack/eval/results/eval-20260227T232322Z.json   |  1892 ++
 .../eval/results/eval-20260228T000138Z-summary.txt |     4 +
 ai-stack/eval/results/eval-20260228T000138Z.json   |  1892 ++
 ai-stack/eval/results/perf-baseline.json           |     6 +
 ai-stack/eval/results/scores.csv                   |     4 +
 ai-stack/identity-kernel/checkpoint_service.py     |   149 +
 ai-stack/identity-kernel/narrative_engine.py       |   186 +
 ai-stack/identity-kernel/value_constitution.py     |   113 +
 ai-stack/local-agents/__init__.py                  |   169 +
 ai-stack/local-agents/agent_executor.py            |  3062 +++
 ai-stack/local-agents/agent_spawner.py             |   718 +
 .../local-agents/builtin_tools/ai_coordination.py  |  1850 ++
 .../local-agents/builtin_tools/code_execution.py   |   355 +
 .../local-agents/builtin_tools/computer_use.py     |   604 +
 .../local-agents/builtin_tools/file_operations.py  |   667 +
 ai-stack/local-agents/builtin_tools/git_tools.py   |   385 +
 .../local-agents/builtin_tools/github_tools.py     |   274 +
 ai-stack/local-agents/builtin_tools/shell_tools.py |   478 +
 .../local-agents/builtin_tools/testing_tools.py    |   291 +
 ai-stack/local-agents/candidate_lifecycle.py       |   145 +
 ai-stack/local-agents/code_executor.py             |   563 +
 ai-stack/local-agents/collective_memory.py         |   281 +
 ai-stack/local-agents/context_assembler.py         |   546 +
 ai-stack/local-agents/context_cache.py             |   173 +
 ai-stack/local-agents/control_channel.py           |    84 +
 ai-stack/local-agents/cross_model_critique.py      |   244 +
 ai-stack/local-agents/decompose_loop.py            |   479 +
 ai-stack/local-agents/discovery_agent.py           |   397 +
 ai-stack/local-agents/eval_sandbox.py              |   134 +
 ai-stack/local-agents/experience_replay.py         |   155 +
 ai-stack/local-agents/failure_correction.py        |    78 +
 ai-stack/local-agents/harness_paths.py             |   189 +
 ai-stack/local-agents/loop_state.py                |   207 +
 ai-stack/local-agents/monitoring_agent.py          |   589 +
 ai-stack/local-agents/remediator_agent.py          |    26 +
 ai-stack/local-agents/self_improvement.py          |   572 +
 ai-stack/local-agents/tool_grammar.py              |    62 +
 ai-stack/local-agents/tool_registry.py             |   816 +
 ai-stack/local-agents/training_capture.py          |   115 +
 ai-stack/local-agents/training_ingest.py           |   805 +
 ai-stack/local-agents/trust_scoring.py             |   117 +
 ai-stack/local-orchestrator/TOOL_DECORATORS.md     |   217 +
 ai-stack/local-orchestrator/__init__.py            |    44 +
 ai-stack/local-orchestrator/agent_interface.py     |   341 +
 ai-stack/local-orchestrator/example_tools.py       |   194 +
 ai-stack/local-orchestrator/mcp_client.py          |   624 +
 ai-stack/local-orchestrator/orchestrator.py        |   585 +
 ai-stack/local-orchestrator/remote_agents.py       |   540 +
 ai-stack/local-orchestrator/router.py              |   446 +
 ai-stack/local-orchestrator/sop_engine.py          |   427 +
 .../local-orchestrator/system-prompt-evaluation.md |   361 +
 .../system-prompt-v2-optimized.md                  |   103 +
 ai-stack/local-orchestrator/system-prompt.md       |    72 +
 .../local-orchestrator/test_agent_interface.py     |   129 +
 ai-stack/local-orchestrator/test_sop_engine.py     |   117 +
 .../local-orchestrator/test_strands_integration.py |   272 +
 ai-stack/local-orchestrator/test_workflow_graph.py |   202 +
 ai-stack/local-orchestrator/tool_decorators.py     |   369 +
 ai-stack/local-orchestrator/workflow_graph.py      |   471 +
 ai-stack/mcp-servers/aidb/Dockerfile               |    64 +
 ai-stack/mcp-servers/aidb/README.md                |   495 +
 ai-stack/mcp-servers/aidb/SECURITY-NOTES.md        |   272 +
 ai-stack/mcp-servers/aidb/__init__.py              |     1 +
 ai-stack/mcp-servers/aidb/circuit_breaker.py       |   191 +
 ai-stack/mcp-servers/aidb/codemachine_client.py    |   362 +
 ai-stack/mcp-servers/aidb/cve_endpoints.py         |   430 +
 ai-stack/mcp-servers/aidb/discovery_api.py         |   458 +
 ai-stack/mcp-servers/aidb/discovery_endpoints.py   |   332 +
 ai-stack/mcp-servers/aidb/document_importer.py     |   579 +
 ai-stack/mcp-servers/aidb/garbage_collector.py     |   448 +
 ai-stack/mcp-servers/aidb/gc_worker.py             |    81 +
 ai-stack/mcp-servers/aidb/health_check.py          |   567 +
 ai-stack/mcp-servers/aidb/interaction_history.py   |   116 +
 ai-stack/mcp-servers/aidb/issue_tracker.py         |   611 +
 ai-stack/mcp-servers/aidb/kernelorg_client.py      |   330 +
 ai-stack/mcp-servers/aidb/llama_cpp_tool_agent.py  |   474 +
 ai-stack/mcp-servers/aidb/llm_parallel.py          |    56 +
 ai-stack/mcp-servers/aidb/middleware/__init__.py   |     0
 ai-stack/mcp-servers/aidb/middleware/cache.py      |   133 +
 ai-stack/mcp-servers/aidb/mindsdb_client.py        |   584 +
 ai-stack/mcp-servers/aidb/ml_engine.py             |   445 +
 ai-stack/mcp-servers/aidb/nvd_client.py            |   443 +
 ai-stack/mcp-servers/aidb/parallel_inference.py    |   285 +
 ai-stack/mcp-servers/aidb/query_validator.py       |   427 +
 ai-stack/mcp-servers/aidb/rag/__init__.py          |     5 +
 ai-stack/mcp-servers/aidb/rag/pipeline.py          |   149 +
 ai-stack/mcp-servers/aidb/registry_api.py          |   121 +
 ai-stack/mcp-servers/aidb/requirements.lock        |  3856 ++++
 ai-stack/mcp-servers/aidb/requirements.txt         |    60 +
 ai-stack/mcp-servers/aidb/schema.py                |   326 +
 ai-stack/mcp-servers/aidb/server.py                |  3892 ++++
 ai-stack/mcp-servers/aidb/settings_loader.py       |   405 +
 ai-stack/mcp-servers/aidb/skills_loader.py         |    85 +
 ai-stack/mcp-servers/aidb/start_with_discovery.sh  |    34 +
 ai-stack/mcp-servers/aidb/tool_discovery.py        |   536 +
 ai-stack/mcp-servers/aidb/tool_discovery_daemon.py |   114 +
 ai-stack/mcp-servers/aidb/vscode_telemetry.py      |   384 +
 ai-stack/mcp-servers/aider-wrapper/Dockerfile      |    41 +
 .../mcp-servers/aider-wrapper/requirements.lock    |   541 +
 .../mcp-servers/aider-wrapper/requirements.txt     |    18 +
 ai-stack/mcp-servers/aider-wrapper/server.py       |  1275 ++
 ai-stack/mcp-servers/config/config.dev.yaml        |     5 +
 ai-stack/mcp-servers/config/config.prod.yaml       |     8 +
 ai-stack/mcp-servers/config/config.staging.yaml    |     6 +
 ai-stack/mcp-servers/config/config.yaml            |   151 +
 ai-stack/mcp-servers/container-engine/Dockerfile   |    25 +
 .../mcp-servers/container-engine/requirements.lock |   558 +
 .../mcp-servers/container-engine/requirements.txt  |     5 +
 ai-stack/mcp-servers/container-engine/server.py    |   652 +
 ai-stack/mcp-servers/embeddings-service/Dockerfile |    36 +
 ai-stack/mcp-servers/embeddings-service/server.py  |   589 +
 ai-stack/mcp-servers/github/README.md              |   191 +
 ai-stack/mcp-servers/health-monitor/Dockerfile     |    52 +
 ai-stack/mcp-servers/health-monitor/README.md      |   362 +
 .../mcp-servers/health-monitor/requirements.lock   |  1365 ++
 .../mcp-servers/health-monitor/requirements.txt    |    23 +
 .../mcp-servers/health-monitor/self_healing.py     |   513 +
 .../health-monitor/self_healing_daemon.py          |    90 +
 ai-stack/mcp-servers/health-monitor/server.py      |   351 +
 .../hybrid-coordinator/BEFORE-AFTER-COMPARISON.md  |   450 +
 ai-stack/mcp-servers/hybrid-coordinator/Dockerfile |    95 +
 .../hybrid-coordinator/OPTIMIZATION-SUMMARY.md     |   363 +
 .../QUALITY_CACHE_INTEGRATION.md                   |   136 +
 ai-stack/mcp-servers/hybrid-coordinator/README.md  |   538 +
 .../mcp-servers/hybrid-coordinator/README.sdk.md   |   168 +
 .../hybrid-coordinator/advanced_features.py        |     1 +
 .../hybrid-coordinator/advisor_detector.py         |     1 +
 .../hybrid-coordinator/affective_handlers.py       |     2 +
 .../hybrid-coordinator/agent/__init__.py           |     0
 .../hybrid-coordinator/agent/agent_service.py      |   351 +
 .../agent_capability_registry.py                   |    33 +
 .../hybrid-coordinator/agent_registry.py           |     2 +
 .../hybrid-coordinator/agentic_memory_journal.py   |     1 +
 .../hybrid-coordinator/agents_task_handlers.py     |     1 +
 .../hybrid-coordinator/ai_coordinator.py           |     2 +
 .../hybrid-coordinator/ai_coordinator_handlers.py  |     8 +
 .../hybrid-coordinator/auth_middleware.py          |     1 +
 .../hybrid-coordinator/auto_quality_improver.py    |     1 +
 .../auto_tool_select_handlers.py                   |     1 +
 .../hybrid-coordinator/blast_radius_classifier.py  |    39 +
 .../hybrid-coordinator/browser_research.py         |     1 +
 .../hybrid-coordinator/capability_discovery.py     |     1 +
 .../hybrid-coordinator/circuit_breaker.py          |     1 +
 .../hybrid-coordinator/collections_config.py       |     1 +
 ai-stack/mcp-servers/hybrid-coordinator/config.py  |     2 +
 .../hybrid-coordinator/consensus_arbiter.py        |   198 +
 .../hybrid-coordinator/consensus_manager.py        |   121 +
 .../hybrid-coordinator/context_compression.py      |     1 +
 .../hybrid-coordinator/context_summary_handlers.py |     1 +
 .../hybrid-coordinator/continuous_learning.py      |     5 +
 .../continuous_learning_daemon.py                  |     1 +
 .../hybrid-coordinator/control/__init__.py         |     0
 .../hybrid-coordinator/control/control_service.py  |    80 +
 .../mcp-servers/hybrid-coordinator/coordinator.py  |     1 +
 .../hybrid-coordinator/core/__init__.py            |     0
 .../hybrid-coordinator/core/auth_middleware.py     |    17 +
 .../hybrid-coordinator/core/circuit_breaker.py     |   204 +
 .../mcp-servers/hybrid-coordinator/core/config.py  |   937 +
 .../hybrid-coordinator/core/domain_router.py       |   299 +
 .../hybrid-coordinator/core/llm_client.py          |   707 +
 .../mcp-servers/hybrid-coordinator/core/metrics.py |   347 +
 .../hybrid-coordinator/core/route_aliases.py       |   299 +
 .../hybrid-coordinator/core/route_handler.py       |  2209 ++
 .../hybrid-coordinator/core/routing_contract.py    |   357 +
 .../hybrid-coordinator/core/session_builders.py    |   480 +
 .../hybrid-coordinator/core/status_service.py      |   322 +
 .../hybrid-coordinator/core/task_classifier.py     |   207 +
 .../hybrid-coordinator/delegation_feedback.py      |     1 +
 .../hybrid-coordinator/delegation_handlers.py      |     2 +
 .../hybrid-coordinator/domain_router.py            |    42 +
 .../hybrid-coordinator/drift_analyzer.py           |   206 +
 .../mcp-servers/hybrid-coordinator/embedder.py     |     1 +
 .../hybrid-coordinator/embedding_cache.py          |     1 +
 .../mcp-servers/hybrid-coordinator/eval_runner.py  |   615 +
 .../hybrid-coordinator/evidence_safety_handlers.py |     1 +
 .../hybrid-coordinator/extensions/__init__.py      |     0
 .../extensions/advanced_features.py                |  2186 ++
 .../extensions/advisor_detector.py                 |   320 +
 .../extensions/affective_handlers.py               |    91 +
 .../extensions/ai_coordinator.py                   |  1235 +
 .../extensions/ai_coordinator_handlers.py          |  2816 +++
 .../extensions/auto_quality_improver.py            |   326 +
 .../extensions/auto_tool_select_handlers.py        |   691 +
 .../extensions/blast_radius_classifier.py          |   159 +
 .../extensions/browser_research.py                 |   274 +
 .../extensions/continuous_learning.py              |  1511 ++
 .../extensions/continuous_learning_daemon.py       |   173 +
 .../extensions/drift_analyzer.py                   |     3 +
 .../extensions/federated_integration.py            |   447 +
 .../extensions/federated_mcp_handlers.py           |   318 +
 .../extensions/federation_sync.py                  |   648 +
 .../extensions/garbage_collector.py                |   475 +
 .../extensions/generator_critic.py                 |   538 +
 .../hybrid-coordinator/extensions/harness_eval.py  |   471 +
 .../hybrid-coordinator/extensions/harness_sdk.py   |   718 +
 .../extensions/identity_handlers.py                |   185 +
 .../extensions/interaction_tracker.py              |   651 +
 .../extensions/learning_lifecycle.py               |   116 +
 .../extensions/lesson_effectiveness_tracker.py     |   291 +
 .../hybrid-coordinator/extensions/mcp_handlers.py  |  2249 ++
 .../extensions/mcp_jsonrpc_adapter.py              |   176 +
 .../extensions/memory_crystallizer.py              |     3 +
 .../extensions/memory_superseder.py                |     3 +
 .../extensions/model_coordinator.py                |   653 +
 .../extensions/model_fleet_manager.py              |   719 +
 .../hybrid-coordinator/extensions/model_loader.py  |   143 +
 .../extensions/model_opt_handlers.py               |   248 +
 .../extensions/model_optimization.py               |  1077 +
 .../hybrid-coordinator/extensions/model_probe.py   |   313 +
 .../extensions/openai_a2a_handlers.py              |  1548 ++
 .../extensions/operator_intelligence.py            |   527 +
 .../extensions/pattern_integration.py              |   432 +
 .../extensions/prompt_injection.py                 |   197 +
 .../hybrid-coordinator/extensions/quality_cache.py |   364 +
 .../extensions/quality_monitor.py                  |   372 +
 .../extensions/real_time_learning_engine.py        |   328 +
 .../extensions/remediation_tracker.py              |   306 +
 .../extensions/remote_llm_feedback.py              |   482 +
 .../extensions/research_workflows.py               |   374 +
 .../extensions/skill_usage_tracker.py              |   274 +
 .../extensions/skill_validator.py                  |   320 +
 .../extensions/system_state_tool.py                |   172 +
 .../extensions/trading_handlers.py                 |   351 +
 .../hybrid-coordinator/extensions/web_research.py  |   428 +
 .../hybrid-coordinator/federated_integration.py    |     1 +
 .../hybrid-coordinator/federated_mcp_handlers.py   |     1 +
 .../hybrid-coordinator/federation_sync.py          |     1 +
 .../hybrid-coordinator/garbage_collector.py        |     1 +
 .../hybrid-coordinator/generator_critic.py         |     1 +
 .../mcp-servers/hybrid-coordinator/harness_eval.py |     2 +
 .../hybrid-coordinator/harness_sdk.d.ts            |   166 +
 .../mcp-servers/hybrid-coordinator/harness_sdk.js  |   504 +
 .../mcp-servers/hybrid-coordinator/harness_sdk.py  |     1 +
 .../mcp-servers/hybrid-coordinator/harness_sdk.ts  |   552 +
 .../mcp-servers/hybrid-coordinator/hints_engine.py |     3 +
 .../hybrid-coordinator/hints_handlers.py           |     1 +
 .../hybrid-coordinator/homeostasis_manager.py      |   111 +
 .../hybrid-coordinator/http_server_impl.py         |  2909 +++
 .../hybrid-coordinator/identity_handlers.py        |     1 +
 .../hybrid-coordinator/inference_param_manager.py  |   361 +
 .../hybrid-coordinator/intake_gateway.py           |   216 +
 .../hybrid-coordinator/intent_classifier.py        |   640 +
 .../hybrid-coordinator/interaction_tracker.py      |     2 +
 .../hybrid-coordinator/knowledge/__init__.py       |     0
 .../knowledge/agentic_memory_journal.py            |   387 +
 .../knowledge/capability_discovery.py              |   303 +
 .../knowledge/collections_config.py                |   333 +
 .../knowledge/context_compression.py               |   391 +
 .../knowledge/context_lifecycle_manager.py         |   527 +
 .../knowledge/context_summary_handlers.py          |   218 +
 .../hybrid-coordinator/knowledge/embedder.py       |   136 +
 .../knowledge/embedding_cache.py                   |   329 +
 .../hybrid-coordinator/knowledge/gap_analyzer.py   |   145 +
 .../hybrid-coordinator/knowledge/graph_search.py   |   173 +
 .../hybrid-coordinator/knowledge/hints_engine.py   |    53 +
 .../knowledge/hints_engine_impl.py                 |  2793 +++
 .../hybrid-coordinator/knowledge/hints_handlers.py |   355 +
 .../hybrid-coordinator/knowledge/llm_router.py     |  1159 +
 .../knowledge/llm_router_handlers.py               |   246 +
 .../knowledge/memory_context_handlers.py           |   467 +
 .../hybrid-coordinator/knowledge/memory_manager.py |   619 +
 .../hybrid-coordinator/knowledge/models.py         |    25 +
 .../knowledge/multi_turn_context.py                |   592 +
 .../knowledge/progressive_disclosure.py            |   631 +
 .../knowledge/query_expansion.py                   |   517 +
 .../hybrid-coordinator/knowledge/rag_reflection.py |   348 +
 .../hybrid-coordinator/knowledge/search_router.py  |  1054 +
 .../hybrid-coordinator/knowledge/semantic_cache.py |   284 +
 .../hybrid-coordinator/knowledge/static_rules.py   |   316 +
 .../hybrid-coordinator/knowledge/temporal_graph.py |   360 +
 .../hybrid-coordinator/knowledge/token_manager.py  |   313 +
 .../knowledge/tooling_manifest.py                  |   715 +
 .../hybrid-coordinator/learning_lifecycle.py       |     1 +
 .../lesson_effectiveness_tracker.py                |     1 +
 .../hybrid-coordinator/lifecycle_fsm.py            |    23 +
 .../mcp-servers/hybrid-coordinator/llm_client.py   |     1 +
 .../mcp-servers/hybrid-coordinator/llm_router.py   |     1 +
 .../hybrid-coordinator/llm_router_handlers.py      |     1 +
 .../mcp-servers/hybrid-coordinator/mcp_handlers.py |     2 +
 .../hybrid-coordinator/memory/__init__.py          |     0
 .../hybrid-coordinator/memory/memory_service.py    |   198 +
 .../hybrid-coordinator/memory_broker.py            |   512 +
 .../hybrid-coordinator/memory_context_handlers.py  |     1 +
 .../hybrid-coordinator/memory_crystallizer.py      |   278 +
 .../hybrid-coordinator/memory_manager.py           |     2 +
 .../hybrid-coordinator/memory_superseder.py        |   226 +
 ai-stack/mcp-servers/hybrid-coordinator/metrics.py |     1 +
 .../hybrid-coordinator/middleware/__init__.py      |     0
 .../hybrid-coordinator/middleware/auth.py          |   329 +
 .../hybrid-coordinator/mlfq_scheduler.py           |   474 +
 .../hybrid-coordinator/model_coordinator.py        |     1 +
 .../hybrid-coordinator/model_fleet_manager.py      |     1 +
 .../hybrid-coordinator/model_lifecycle_manager.py  |   577 +
 .../mcp-servers/hybrid-coordinator/model_loader.py |     2 +
 .../hybrid-coordinator/model_opt_handlers.py       |     1 +
 .../hybrid-coordinator/model_optimization.py       |     1 +
 .../mcp-servers/hybrid-coordinator/model_probe.py  |     1 +
 .../hybrid-coordinator/model_registry.py           |   624 +
 .../hybrid-coordinator/multi_turn_context.py       |     1 +
 .../hybrid-coordinator/openai_a2a_handlers.py      |     1 +
 .../operator_intelligence_handlers.py              |    93 +
 .../mcp-servers/hybrid-coordinator/ops_handlers.py |     1 +
 .../orchestration_graph_runner.py                  |    13 +
 .../hybrid-coordinator/orchestration_handlers.py   |     1 +
 .../hybrid-coordinator/orchestration_utils.py      |     2 +
 .../mcp-servers/hybrid-coordinator/package.json    |    33 +
 .../hybrid-coordinator/pattern_integration.py      |     1 +
 .../hybrid-coordinator/progressive_disclosure.py   |     1 +
 .../hybrid-coordinator/prompt_injection.py         |     1 +
 .../hybrid-coordinator/prsi_handlers.py            |     1 +
 .../mcp-servers/hybrid-coordinator/pyproject.toml  |    25 +
 .../hybrid-coordinator/quality_cache.py            |     1 +
 .../hybrid-coordinator/quality_monitor.py          |     1 +
 .../hybrid-coordinator/query/__init__.py           |     0
 .../hybrid-coordinator/query/query_service.py      |    62 +
 .../hybrid-coordinator/query_expansion.py          |     1 +
 .../hybrid-coordinator/rag_augmentor.py            |   326 +
 .../hybrid-coordinator/rag_reflection.py           |     1 +
 .../real_time_learning_engine.py                   |     2 +
 .../hybrid-coordinator/remediation_tracker.py      |     1 +
 .../hybrid-coordinator/remote_llm_feedback.py      |     1 +
 .../hybrid-coordinator/requirements.lock           |  2775 +++
 .../hybrid-coordinator/requirements.txt            |    49 +
 .../hybrid-coordinator/research_workflows.py       |     1 +
 .../hybrid-coordinator/route_aliases.py            |     1 +
 .../hybrid-coordinator/route_handler.py            |     2 +
 ai-stack/mcp-servers/hybrid-coordinator/router.py  |   313 +
 .../hybrid-coordinator/routing_contract.py         |     1 +
 .../hybrid-coordinator/runtime_control_handlers.py |     1 +
 .../hybrid-coordinator/runtime_manager.py          |     2 +
 .../hybrid-coordinator/safe_command_executor.py    |     1 +
 .../hybrid-coordinator/search_router.py            |     2 +
 .../hybrid-coordinator/semantic_cache.py           |     1 +
 ai-stack/mcp-servers/hybrid-coordinator/server.py  |  1067 +
 .../hybrid-coordinator/session_builders.py         |     2 +
 .../hybrid-coordinator/skill_usage_tracker.py      |     1 +
 .../hybrid-coordinator/start_with_learning.sh      |    42 +
 .../hybrid-coordinator/task_classifier.py          |     1 +
 .../hybrid-coordinator/telemetry/__init__.py       |     0
 .../telemetry/health_spider_handlers.py            |    21 +
 .../telemetry/insights_service.py                  |    42 +
 .../hybrid-coordinator/tests/__init__.py           |     1 +
 .../tests/test_advisor_detector.py                 |   333 +
 .../tests/test_advisor_fallback_chains.py          |   217 +
 .../tests/test_ai_coordinator_model_awareness.py   |   530 +
 .../tests/test_cognitive_intelligence_l5_l6.py     |   263 +
 .../tests/test_config_local_system_prompt.py       |    95 +
 .../tests/test_domain_role_enforcement.py          |    78 +
 .../tests/test_drift_analyzer.py                   |    33 +
 .../tests/test_harness_eval_scorecard.py           |   117 +
 .../tests/test_http_query_runtime_optimization.py  |    94 +
 ...t_http_server_delegated_message_optimization.py |   141 +
 .../tests/test_learning_lifecycle.py               |    75 +
 .../hybrid-coordinator/tests/test_llm_client.py    |   261 +
 .../hybrid-coordinator/tests/test_llm_router.py    |   104 +
 .../tests/test_mcp_handlers_dispatch.py            |   326 +
 .../hybrid-coordinator/tests/test_memory_broker.py |    20 +
 .../tests/test_memory_crystallizer.py              |    55 +
 .../tests/test_memory_superseder.py                |    50 +
 .../tests/test_multi_agent_consensus_l7.py         |    71 +
 .../tests/test_optimizations_simple.py             |   247 +
 .../tests/test_orchestrate_routing.py              |   142 +
 .../hybrid-coordinator/tests/test_route_aliases.py |   316 +
 .../tests/test_workflow_executor.py                |   248 +
 .../tests/test_workflow_plan_optimization_watch.py |   190 +
 .../test_workflow_run_blueprint_auto_selection.py  |    78 +
 .../hybrid-coordinator/tooling_manifest.py         |     1 +
 .../hybrid-coordinator/trace_collector.py          |   499 +
 .../hybrid-coordinator/trading_handlers.py         |     1 +
 .../mcp-servers/hybrid-coordinator/web_research.py |     2 +
 .../hybrid-coordinator/workflow/__init__.py        |     0
 .../workflow/agent_capability_registry.py          |   247 +
 .../hybrid-coordinator/workflow/agent_registry.py  |   737 +
 .../workflow/agents_task_handlers.py               |   776 +
 .../workflow/consensus_engine.py                   |   269 +
 .../hybrid-coordinator/workflow/coordinator.py     |   366 +
 .../workflow/delegation_feedback.py                |   516 +
 .../workflow/delegation_handlers.py                |   845 +
 .../workflow/evidence_safety_handlers.py           |   665 +
 .../hybrid-coordinator/workflow/intake_gateway.py  |   405 +
 .../hybrid-coordinator/workflow/lifecycle_fsm.py   |   458 +
 .../hybrid-coordinator/workflow/ops_handlers.py    |   868 +
 .../workflow/orchestration_graph_runner.py         |   392 +
 .../workflow/orchestration_handlers.py             |   637 +
 .../workflow/orchestration_service.py              |    60 +
 .../workflow/orchestration_utils.py                |   789 +
 .../hybrid-coordinator/workflow/prsi_handlers.py   |   238 +
 .../workflow/runtime_control_handlers.py           |   742 +
 .../hybrid-coordinator/workflow/runtime_manager.py |   750 +
 .../workflow/safe_command_executor.py              |   146 +
 .../workflow/safety_control_layer.py               |   142 +
 .../hybrid-coordinator/workflow/safety_gate.py     |   126 +
 .../workflow/workflow_checkpointer.py              |   529 +
 .../workflow/workflow_executor.py                  |   706 +
 .../workflow/workflow_planning.py                  |   741 +
 .../workflow/workflow_session_handlers.py          |  1441 ++
 .../workflow/yaml_workflow_handlers.py             |   314 +
 .../hybrid-coordinator/workflow_executor.py        |     1 +
 .../hybrid-coordinator/workflow_planning.py        |     2 +
 .../workflow_session_handlers.py                   |     2 +
 .../hybrid-coordinator/yaml_workflow_handlers.py   |     1 +
 .../mcp-servers/mlops-tools/context_compressor.py  |    38 +
 ai-stack/mcp-servers/mlops-tools/context_weaver.py |    45 +
 ai-stack/mcp-servers/mlops-tools/server.py         |   126 +
 ai-stack/mcp-servers/nixos-docs/Dockerfile         |    69 +
 ai-stack/mcp-servers/nixos-docs/README.md          |   454 +
 ai-stack/mcp-servers/nixos-docs/requirements.lock  |  3406 +++
 ai-stack/mcp-servers/nixos-docs/requirements.txt   |    56 +
 ai-stack/mcp-servers/nixos-docs/server.py          |   721 +
 ai-stack/mcp-servers/nixos-docs/start_server.sh    |    27 +
 ai-stack/mcp-servers/nixos/README.md               |   102 +
 ai-stack/mcp-servers/osint-tools/server.py         |   193 +
 ai-stack/mcp-servers/qa-tools/server.py            |   126 +
 ai-stack/mcp-servers/qdrant-populator/Dockerfile   |    13 +
 ai-stack/mcp-servers/qdrant-populator/populate.py  |   180 +
 ai-stack/mcp-servers/ralph-wiggum/Dockerfile       |    67 +
 ai-stack/mcp-servers/ralph-wiggum/README.md        |   534 +
 .../mcp-servers/ralph-wiggum/circuit_breaker.py    |   190 +
 .../mcp-servers/ralph-wiggum/config/default.yaml   |    64 +
 ai-stack/mcp-servers/ralph-wiggum/hooks.py         |   264 +
 ai-stack/mcp-servers/ralph-wiggum/loop_engine.py   |   804 +
 ai-stack/mcp-servers/ralph-wiggum/orchestrator.py  |   211 +
 .../mcp-servers/ralph-wiggum/requirements.lock     |  1469 ++
 ai-stack/mcp-servers/ralph-wiggum/requirements.txt |    39 +
 ai-stack/mcp-servers/ralph-wiggum/server.py        |   781 +
 ai-stack/mcp-servers/ralph-wiggum/state_manager.py |   194 +
 ai-stack/mcp-servers/shared/__init__.py            |     1 +
 ai-stack/mcp-servers/shared/ab_testing.py          |   564 +
 ai-stack/mcp-servers/shared/audit_sidecar.py       |   130 +
 ai-stack/mcp-servers/shared/auth_http_client.py    |   245 +
 ai-stack/mcp-servers/shared/auth_middleware.py     |   288 +
 ai-stack/mcp-servers/shared/circuit_breaker.py     |   493 +
 .../shared/config/reasoning-profiles.json          |    70 +
 ai-stack/mcp-servers/shared/config_loader.py       |    38 +
 ai-stack/mcp-servers/shared/health_check.py        |   853 +
 ai-stack/mcp-servers/shared/hybrid_client.py       |   844 +
 ai-stack/mcp-servers/shared/inference_telemetry.py |   645 +
 ai-stack/mcp-servers/shared/llm_config.py          |   373 +
 ai-stack/mcp-servers/shared/model_catalog.py       |   632 +
 ai-stack/mcp-servers/shared/model_monitoring.py    |   618 +
 ai-stack/mcp-servers/shared/path_validation.py     |   195 +
 ai-stack/mcp-servers/shared/podman_api_client.py   |   612 +
 ai-stack/mcp-servers/shared/postgres_client.py     |    84 +
 ai-stack/mcp-servers/shared/rate_limiter.py        |   229 +
 ai-stack/mcp-servers/shared/retry_backoff.py       |   442 +
 ai-stack/mcp-servers/shared/secrets_loader.py      |   169 +
 ai-stack/mcp-servers/shared/ssrf_protection.py     |   191 +
 ai-stack/mcp-servers/shared/stack_settings.py      |    77 +
 ai-stack/mcp-servers/shared/telemetry_privacy.py   |    91 +
 ai-stack/mcp-servers/shared/tool_audit.py          |   110 +
 .../mcp-servers/shared/tool_security_auditor.py    |   388 +
 ai-stack/mcp-servers/trading-tools/server.py       |   134 +
 .../meta-optimization/harness_evolution_tracker.py |   506 +
 ai-stack/meta-optimization/meta_optimizer.py       |   657 +
 ai-stack/migrations/alembic.ini                    |    37 +
 ai-stack/migrations/env.py                         |   105 +
 ai-stack/migrations/script.py.mako                 |    23 +
 ai-stack/migrations/test-migrations.sh             |     8 +
 .../versions/20260109_01_baseline_schema.py        |   136 +
 .../versions/20260109_02_pgvector_hnsw_index.py    |    28 +
 .../versions/20260125_01_add_llm_used_column.py    |    24 +
 .../versions/20260718_01_b2_workflow_shadow.py     |   350 +
 ai-stack/model-optimization/active_learning.py     |   747 +
 .../model-optimization/continuous_finetuning.py    |   440 +
 ai-stack/model-optimization/data_curator.py        |   563 +
 ai-stack/model-optimization/distillation.py        |   814 +
 ai-stack/model-optimization/synthetic_data.py      |   761 +
 ai-stack/models/registry.json                      |   422 +
 ai-stack/models/registry.json.bak                  |    59 +
 .../comprehensive-system-monitoring.json           |   623 +
 .../grafana/dashboards/p1-security-monitoring.json |   364 +
 ai-stack/monitoring/local_llm_monitor.py           |   558 +
 ai-stack/monitoring/prometheus/rules/p1-alerts.yml |   228 +
 ai-stack/observability/alert_engine.py             |   518 +
 .../observability/anomaly_alert_integration.py     |   327 +
 ai-stack/observability/baseline_profiler.py        |   563 +
 .../grafana-dashboards/ai-stack-overview.json      |   104 +
 .../orchestration-framework.json                   |   523 +
 ai-stack/observability/integrate_monitoring.py     |   229 +
 ai-stack/observability/metrics_middleware.py       |   232 +
 ai-stack/observability/notification_handlers.py    |   423 +
 ai-stack/observability/opentelemetry_config.py     |   429 +
 ai-stack/observability/performance_profiler.py     |   465 +
 ai-stack/observability/prometheus_config.yml       |    95 +
 ai-stack/observability/remediation_workflows.py    |   464 +
 ai-stack/offloading/__init__.py                    |     0
 ai-stack/offloading/agent_pool_manager.py          |   495 +
 ai-stack/offloading/agent_quality_profiler.py      |   790 +
 ai-stack/offloading/quality_assurance.py           |   651 +
 ai-stack/offloading/work_classifier.py             |   528 +
 ai-stack/orchestration/__init__.py                 |    75 +
 ai-stack/orchestration/agent_hq.py                 |   754 +
 ai-stack/orchestration/delegation_api.py           |   596 +
 ai-stack/orchestration/mcp_tool_invoker.py         |   692 +
 ai-stack/orchestration/workspace_isolation.py      |   587 +
 ai-stack/platform/agent_marketplace.py             |   663 +
 ai-stack/platform/federation_protocol.py           |   539 +
 ai-stack/platform/harness_sdk_v2.py                |   905 +
 ai-stack/platform/production_hardening.py          |   601 +
 ai-stack/postgres/init-schema.sql                  |   568 +
 .../migrations/006_autonomous_improvement.sql      |   417 +
 .../postgres/migrations/007_federated_learning.sql |   361 +
 .../postgres/migrations/008_meta_optimization.sql  |   356 +
 .../migrations/009_multi_agent_collaboration.sql   |   333 +
 .../postgres/migrations/010_platform_maturity.sql  |   398 +
 ai-stack/progressive-disclosure/lazy_context.py    |   341 +
 .../progressive-disclosure/multi_tier_loading.py   |   522 +
 .../progressive-disclosure/relevance_prediction.py |   307 +
 ai-stack/prompts/registry.yaml                     |   599 +
 .../real-time-learning/feedback_acceleration.py    |   584 +
 ai-stack/real-time-learning/meta_learning.py       |   671 +
 ai-stack/real-time-learning/online_learning.py     |   593 +
 ai-stack/security/adapter_audit.py                 |   420 +
 ai-stack/security/capability_guard.py              |   404 +
 ai-stack/security/context_sanitizer.py             |   261 +
 ai-stack/security/zero_trust.py                    |   653 +
 ai-stack/self-improvement/improvement_detector.py  |   517 +
 ai-stack/self-improvement/llm_code_reviewer.py     |   416 +
 ai-stack/snapshots/hint-adoption-summary.json      |     1 +
 ai-stack/snapshots/imported-documents-meta.jsonl   |   175 +
 ai-stack/snapshots/query-gaps.jsonl                |   127 +
 ai-stack/sop-templates/codebase-analysis.sop.md    |    93 +
 ai-stack/sop-templates/deployment-check.sop.md     |   128 +
 ai-stack/sop-templates/test-validation.sop.md      |   169 +
 ai-stack/sql/add_ralph_repos_metadata.sql          |   145 +
 ai-stack/sql/comprehensive_update_jan2026.sql      |   130 +
 ai-stack/sql/package_versions_schema.sql           |   130 +
 ai-stack/sql/update_package_versions_jan2026.sql   |    91 +
 ai-stack/switchboard/capability_lease_gate.py      |   888 +
 ai-stack/switchboard/execution_cell_adapter.py     |   598 +
 ai-stack/switchboard/execution_cell_runner.py      |  1252 ++
 ai-stack/switchboard/execution_cell_validator.py   |   383 +
 ai-stack/switchboard/switchboard.py                |  3641 +++
 ai-stack/systemd/letsencrypt-renewal.timer         |    17 +
 ai-stack/testing/chaos_engineering.py              |   399 +
 ai-stack/testing/performance_benchmarks.py         |   347 +
 ai-stack/testing/property_based_tests.py           |   223 +
 ai-stack/tests/unit/test_workspace_isolation.py    |    13 +
 ai-stack/trading-agents/__init__.py                |     0
 ai-stack/trading-agents/analysts/__init__.py       |     0
 .../analysts/fundamentals_analyst.py               |    97 +
 ai-stack/trading-agents/analysts/market_analyst.py |   112 +
 ai-stack/trading-agents/analysts/news_analyst.py   |    82 +
 .../trading-agents/analysts/sentiment_analyst.py   |    74 +
 ai-stack/trading-agents/config.py                  |    60 +
 ai-stack/trading-agents/dataflows/__init__.py      |     0
 ai-stack/trading-agents/dataflows/interface.py     |   294 +
 ai-stack/trading-agents/graph/__init__.py          |     0
 ai-stack/trading-agents/graph/state.py             |    79 +
 ai-stack/trading-agents/graph/trading_graph.py     |   155 +
 ai-stack/trading-agents/portfolio/__init__.py      |     0
 .../trading-agents/portfolio/portfolio_manager.py  |   106 +
 ai-stack/trading-agents/researchers/__init__.py    |     0
 .../trading-agents/researchers/bear_researcher.py  |    93 +
 .../trading-agents/researchers/bull_researcher.py  |    97 +
 ai-stack/trading-agents/risk_mgmt/__init__.py      |     0
 ai-stack/trading-agents/risk_mgmt/risk_manager.py  |    87 +
 ai-stack/trading-agents/trader/__init__.py         |     0
 ai-stack/trading-agents/trader/trader_agent.py     |    94 +
 ai-stack/workflows/__init__.py                     |    39 +
 ai-stack/workflows/coordinator.py                  |   419 +
 ai-stack/workflows/examples/conditional-flow.yaml  |    83 +
 ai-stack/workflows/examples/error-handling.yaml    |   116 +
 .../workflows/examples/feature-implementation.yaml |   121 +
 ai-stack/workflows/examples/loop-until-done.yaml   |    85 +
 ai-stack/workflows/examples/parallel-tasks.yaml    |    95 +
 ai-stack/workflows/examples/simple-sequential.yaml |    48 +
 ai-stack/workflows/examples/sub-workflow.yaml      |    96 +
 .../workflows/examples/test-agent-routing.yaml     |   130 +
 .../examples/test-memory-integration.yaml          |   117 +
 ai-stack/workflows/graph.py                        |   377 +
 ai-stack/workflows/models.py                       |   273 +
 ai-stack/workflows/node_dispatcher.py              |   187 +
 ai-stack/workflows/parser.py                       |   286 +
 ai-stack/workflows/persistence.py                  |   273 +
 ai-stack/workflows/schema/workflow-v1.yaml         |   239 +
 ai-stack/workflows/templates/bug-fix.yaml          |   150 +
 ai-stack/workflows/templates/ci-cd-setup.yaml      |   230 +
 ai-stack/workflows/templates/code-review.yaml      |   139 +
 .../workflows/templates/dependency-update.yaml     |   201 +
 ai-stack/workflows/templates/documentation.yaml    |   148 +
 .../templates/performance-optimization.yaml        |   177 +
 ai-stack/workflows/templates/refactoring.yaml      |   160 +
 ai-stack/workflows/templates/security-audit.yaml   |   177 +
 ai-stack/workflows/templates/testing.yaml          |   158 +
 ai-stack/workflows/tests/test_e2e_integration.py   |   430 +
 ai-stack/workflows/validator.py                    |   520 +
 ai-stack/world-model/__init__.py                   |     0
 ai-stack/world-model/context_warmer.py             |   114 +
 ai-stack/world-model/intent_forecaster.py          |   104 +
 ai-stack/world-model/pattern_index.py              |   169 +
 archive/AGENTS.md.backup-20251203                  |   769 +
 archive/agent-onboarding-package-v1.0.0.tar.gz     |   Bin 0 -> 25478 bytes
 archive/agent-onboarding-package-v2.0.0.tar.gz     |   Bin 0 -> 3348892 bytes
 .../.agent/skills/ai-service-management/SKILL.md   |   431 +
 .../.agent/skills/aidb-knowledge/SKILL.md          |   122 +
 .../.agent/skills/all-mcp-directory/SKILL.md       |   138 +
 .../.agent/skills/brand-guidelines/LICENSE.txt     |   202 +
 .../.agent/skills/brand-guidelines/SKILL.md        |    73 +
 .../.agent/skills/canvas-design/LICENSE.txt        |   202 +
 .../.agent/skills/canvas-design/SKILL.md           |   130 +
 .../canvas-design/canvas-fonts/ArsenalSC-OFL.txt   |    93 +
 .../canvas-fonts/ArsenalSC-Regular.ttf             |   Bin 0 -> 165848 bytes
 .../canvas-fonts/BigShoulders-Bold.ttf             |   Bin 0 -> 94528 bytes
 .../canvas-fonts/BigShoulders-OFL.txt              |    93 +
 .../canvas-fonts/BigShoulders-Regular.ttf          |   Bin 0 -> 94396 bytes
 .../canvas-design/canvas-fonts/Boldonse-OFL.txt    |    93 +
 .../canvas-fonts/Boldonse-Regular.ttf              |   Bin 0 -> 77168 bytes
 .../canvas-fonts/BricolageGrotesque-Bold.ttf       |   Bin 0 -> 90952 bytes
 .../canvas-fonts/BricolageGrotesque-OFL.txt        |    93 +
 .../canvas-fonts/BricolageGrotesque-Regular.ttf    |   Bin 0 -> 90920 bytes
 .../canvas-design/canvas-fonts/CrimsonPro-Bold.ttf |   Bin 0 -> 107352 bytes
 .../canvas-fonts/CrimsonPro-Italic.ttf             |   Bin 0 -> 108828 bytes
 .../canvas-design/canvas-fonts/CrimsonPro-OFL.txt  |    93 +
 .../canvas-fonts/CrimsonPro-Regular.ttf            |   Bin 0 -> 106696 bytes
 .../canvas-design/canvas-fonts/DMMono-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/DMMono-Regular.ttf  |   Bin 0 -> 48852 bytes
 .../canvas-design/canvas-fonts/EricaOne-OFL.txt    |    94 +
 .../canvas-fonts/EricaOne-Regular.ttf              |   Bin 0 -> 24872 bytes
 .../canvas-design/canvas-fonts/GeistMono-Bold.ttf  |   Bin 0 -> 78304 bytes
 .../canvas-design/canvas-fonts/GeistMono-OFL.txt   |    93 +
 .../canvas-fonts/GeistMono-Regular.ttf             |   Bin 0 -> 78232 bytes
 .../canvas-design/canvas-fonts/Gloock-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Gloock-Regular.ttf  |   Bin 0 -> 95156 bytes
 .../canvas-fonts/IBMPlexMono-Bold.ttf              |   Bin 0 -> 136008 bytes
 .../canvas-design/canvas-fonts/IBMPlexMono-OFL.txt |    93 +
 .../canvas-fonts/IBMPlexMono-Regular.ttf           |   Bin 0 -> 133796 bytes
 .../canvas-fonts/IBMPlexSerif-Bold.ttf             |   Bin 0 -> 161000 bytes
 .../canvas-fonts/IBMPlexSerif-BoldItalic.ttf       |   Bin 0 -> 169840 bytes
 .../canvas-fonts/IBMPlexSerif-Italic.ttf           |   Bin 0 -> 170004 bytes
 .../canvas-fonts/IBMPlexSerif-Regular.ttf          |   Bin 0 -> 160380 bytes
 .../canvas-fonts/InstrumentSans-Bold.ttf           |   Bin 0 -> 68084 bytes
 .../canvas-fonts/InstrumentSans-BoldItalic.ttf     |   Bin 0 -> 70004 bytes
 .../canvas-fonts/InstrumentSans-Italic.ttf         |   Bin 0 -> 69900 bytes
 .../canvas-fonts/InstrumentSans-OFL.txt            |    93 +
 .../canvas-fonts/InstrumentSans-Regular.ttf        |   Bin 0 -> 68028 bytes
 .../canvas-fonts/InstrumentSerif-Italic.ttf        |   Bin 0 -> 70868 bytes
 .../canvas-fonts/InstrumentSerif-Regular.ttf       |   Bin 0 -> 69312 bytes
 .../canvas-design/canvas-fonts/Italiana-OFL.txt    |    93 +
 .../canvas-fonts/Italiana-Regular.ttf              |   Bin 0 -> 27184 bytes
 .../canvas-fonts/JetBrainsMono-Bold.ttf            |   Bin 0 -> 114828 bytes
 .../canvas-fonts/JetBrainsMono-OFL.txt             |    93 +
 .../canvas-fonts/JetBrainsMono-Regular.ttf         |   Bin 0 -> 114904 bytes
 .../canvas-design/canvas-fonts/Jura-Light.ttf      |   Bin 0 -> 154308 bytes
 .../canvas-design/canvas-fonts/Jura-Medium.ttf     |   Bin 0 -> 154488 bytes
 .../skills/canvas-design/canvas-fonts/Jura-OFL.txt |    93 +
 .../canvas-fonts/LibreBaskerville-OFL.txt          |    93 +
 .../canvas-fonts/LibreBaskerville-Regular.ttf      |   Bin 0 -> 147584 bytes
 .../canvas-design/canvas-fonts/Lora-Bold.ttf       |   Bin 0 -> 133828 bytes
 .../canvas-design/canvas-fonts/Lora-BoldItalic.ttf |   Bin 0 -> 140332 bytes
 .../canvas-design/canvas-fonts/Lora-Italic.ttf     |   Bin 0 -> 139328 bytes
 .../skills/canvas-design/canvas-fonts/Lora-OFL.txt |    93 +
 .../canvas-design/canvas-fonts/Lora-Regular.ttf    |   Bin 0 -> 133888 bytes
 .../canvas-fonts/NationalPark-Bold.ttf             |   Bin 0 -> 79208 bytes
 .../canvas-fonts/NationalPark-OFL.txt              |    93 +
 .../canvas-fonts/NationalPark-Regular.ttf          |   Bin 0 -> 76424 bytes
 .../canvas-fonts/NothingYouCouldDo-OFL.txt         |    93 +
 .../canvas-fonts/NothingYouCouldDo-Regular.ttf     |   Bin 0 -> 32020 bytes
 .../canvas-design/canvas-fonts/Outfit-Bold.ttf     |   Bin 0 -> 55392 bytes
 .../canvas-design/canvas-fonts/Outfit-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Outfit-Regular.ttf  |   Bin 0 -> 54912 bytes
 .../canvas-fonts/PixelifySans-Medium.ttf           |   Bin 0 -> 51072 bytes
 .../canvas-fonts/PixelifySans-OFL.txt              |    93 +
 .../canvas-design/canvas-fonts/PoiretOne-OFL.txt   |    93 +
 .../canvas-fonts/PoiretOne-Regular.ttf             |   Bin 0 -> 45244 bytes
 .../canvas-design/canvas-fonts/RedHatMono-Bold.ttf |   Bin 0 -> 34420 bytes
 .../canvas-design/canvas-fonts/RedHatMono-OFL.txt  |    93 +
 .../canvas-fonts/RedHatMono-Regular.ttf            |   Bin 0 -> 34488 bytes
 .../canvas-design/canvas-fonts/Silkscreen-OFL.txt  |    93 +
 .../canvas-fonts/Silkscreen-Regular.ttf            |   Bin 0 -> 31960 bytes
 .../canvas-fonts/SmoochSans-Medium.ttf             |   Bin 0 -> 59704 bytes
 .../canvas-design/canvas-fonts/SmoochSans-OFL.txt  |    93 +
 .../canvas-design/canvas-fonts/Tektur-Medium.ttf   |   Bin 0 -> 76248 bytes
 .../canvas-design/canvas-fonts/Tektur-OFL.txt      |    93 +
 .../canvas-design/canvas-fonts/Tektur-Regular.ttf  |   Bin 0 -> 75604 bytes
 .../canvas-design/canvas-fonts/WorkSans-Bold.ttf   |   Bin 0 -> 191304 bytes
 .../canvas-fonts/WorkSans-BoldItalic.ttf           |   Bin 0 -> 175772 bytes
 .../canvas-design/canvas-fonts/WorkSans-Italic.ttf |   Bin 0 -> 174280 bytes
 .../canvas-design/canvas-fonts/WorkSans-OFL.txt    |    93 +
 .../canvas-fonts/WorkSans-Regular.ttf              |   Bin 0 -> 188916 bytes
 .../canvas-design/canvas-fonts/YoungSerif-OFL.txt  |    93 +
 .../canvas-fonts/YoungSerif-Regular.ttf            |   Bin 0 -> 105136 bytes
 .../.agent/skills/frontend-design/LICENSE.txt      |   177 +
 .../.agent/skills/frontend-design/SKILL.md         |    42 +
 .../.agent/skills/health-monitoring/SKILL.md       |   102 +
 .../.agent/skills/internal-comms/LICENSE.txt       |   202 +
 .../.agent/skills/internal-comms/SKILL.md          |    32 +
 .../skills/internal-comms/examples/3p-updates.md   |    47 +
 .../internal-comms/examples/company-newsletter.md  |    65 +
 .../skills/internal-comms/examples/faq-answers.md  |    30 +
 .../internal-comms/examples/general-comms.md       |    16 +
 .../.agent/skills/mcp-builder/LICENSE.txt          |   202 +
 .../.agent/skills/mcp-builder/SKILL.md             |   236 +
 .../skills/mcp-builder/reference/evaluation.md     |   602 +
 .../mcp-builder/reference/mcp_best_practices.md    |   249 +
 .../mcp-builder/reference/node_mcp_server.md       |   970 +
 .../mcp-builder/reference/python_mcp_server.md     |   719 +
 .../skills/mcp-builder/scripts/connections.py      |   151 +
 .../skills/mcp-builder/scripts/evaluation.py       |   373 +
 .../mcp-builder/scripts/example_evaluation.xml     |    22 +
 .../skills/mcp-builder/scripts/requirements.txt    |     2 +
 .../.agent/skills/mcp-server/SKILL.md              |    79 +
 .../.agent/skills/nixos-deployment/SKILL.md        |   544 +
 .../.agent/skills/pdf/LICENSE.txt                  |    30 +
 .../.agent/skills/pdf/SKILL.md                     |   294 +
 .../.agent/skills/pdf/forms.md                     |   205 +
 .../.agent/skills/pdf/reference.md                 |   612 +
 .../skills/pdf/scripts/check_bounding_boxes.py     |    70 +
 .../pdf/scripts/check_bounding_boxes_test.py       |   226 +
 .../skills/pdf/scripts/check_fillable_fields.py    |    12 +
 .../skills/pdf/scripts/convert_pdf_to_images.py    |    35 +
 .../skills/pdf/scripts/create_validation_image.py  |    41 +
 .../skills/pdf/scripts/extract_form_field_info.py  |   152 +
 .../skills/pdf/scripts/fill_fillable_fields.py     |   114 +
 .../pdf/scripts/fill_pdf_form_with_annotations.py  |   108 +
 .../.agent/skills/pptx/LICENSE.txt                 |    30 +
 .../.agent/skills/pptx/SKILL.md                    |   484 +
 .../.agent/skills/pptx/html2pptx.md                |   625 +
 .../.agent/skills/pptx/ooxml.md                    |   427 +
 .../schemas/ISO-IEC29500-4_2016/dml-chart.xsd      |  1499 ++
 .../ISO-IEC29500-4_2016/dml-chartDrawing.xsd       |   146 +
 .../schemas/ISO-IEC29500-4_2016/dml-diagram.xsd    |  1085 +
 .../ISO-IEC29500-4_2016/dml-lockedCanvas.xsd       |    11 +
 .../ooxml/schemas/ISO-IEC29500-4_2016/dml-main.xsd |  3081 +++
 .../schemas/ISO-IEC29500-4_2016/dml-picture.xsd    |    23 +
 .../ISO-IEC29500-4_2016/dml-spreadsheetDrawing.xsd |   185 +
 .../dml-wordprocessingDrawing.xsd                  |   287 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/pml.xsd |  1676 ++
 .../shared-additionalCharacteristics.xsd           |    28 +
 .../ISO-IEC29500-4_2016/shared-bibliography.xsd    |   144 +
 .../shared-commonSimpleTypes.xsd                   |   174 +
 .../shared-customXmlDataProperties.xsd             |    25 +
 .../shared-customXmlSchemaProperties.xsd           |    18 +
 .../shared-documentPropertiesCustom.xsd            |    59 +
 .../shared-documentPropertiesExtended.xsd          |    56 +
 .../shared-documentPropertiesVariantTypes.xsd      |   195 +
 .../schemas/ISO-IEC29500-4_2016/shared-math.xsd    |   582 +
 .../shared-relationshipReference.xsd               |    25 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/sml.xsd |  4439 ++++
 .../ooxml/schemas/ISO-IEC29500-4_2016/vml-main.xsd |   570 +
 .../ISO-IEC29500-4_2016/vml-officeDrawing.xsd      |   509 +
 .../vml-presentationDrawing.xsd                    |    12 +
 .../ISO-IEC29500-4_2016/vml-spreadsheetDrawing.xsd |   108 +
 .../vml-wordprocessingDrawing.xsd                  |    96 +
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/wml.xsd |  3646 +++
 .../pptx/ooxml/schemas/ISO-IEC29500-4_2016/xml.xsd |   116 +
 .../ecma/fouth-edition/opc-contentTypes.xsd        |    42 +
 .../ecma/fouth-edition/opc-coreProperties.xsd      |    50 +
 .../schemas/ecma/fouth-edition/opc-digSig.xsd      |    49 +
 .../ecma/fouth-edition/opc-relationships.xsd       |    33 +
 .../.agent/skills/pptx/ooxml/schemas/mce/mc.xsd    |    75 +
 .../pptx/ooxml/schemas/microsoft/wml-2010.xsd      |   560 +
 .../pptx/ooxml/schemas/microsoft/wml-2012.xsd      |    67 +
 .../pptx/ooxml/schemas/microsoft/wml-2018.xsd      |    14 +
 .../pptx/ooxml/schemas/microsoft/wml-cex-2018.xsd  |    20 +
 .../pptx/ooxml/schemas/microsoft/wml-cid-2016.xsd  |    13 +
 .../schemas/microsoft/wml-sdtdatahash-2020.xsd     |     4 +
 .../ooxml/schemas/microsoft/wml-symex-2015.xsd     |     8 +
 .../.agent/skills/pptx/ooxml/scripts/pack.py       |   159 +
 .../.agent/skills/pptx/ooxml/scripts/unpack.py     |    29 +
 .../.agent/skills/pptx/ooxml/scripts/validate.py   |    69 +
 .../pptx/ooxml/scripts/validation/__init__.py      |    15 +
 .../skills/pptx/ooxml/scripts/validation/base.py   |   951 +
 .../skills/pptx/ooxml/scripts/validation/docx.py   |   274 +
 .../skills/pptx/ooxml/scripts/validation/pptx.py   |   315 +
 .../pptx/ooxml/scripts/validation/redlining.py     |   279 +
 .../.agent/skills/pptx/scripts/html2pptx.js        |   979 +
 .../.agent/skills/pptx/scripts/inventory.py        |  1020 +
 .../.agent/skills/pptx/scripts/rearrange.py        |   231 +
 .../.agent/skills/pptx/scripts/replace.py          |   385 +
 .../.agent/skills/pptx/scripts/thumbnail.py        |   450 +
 .../.agent/skills/project-import/SKILL.md          |    57 +
 .../.agent/skills/rag-techniques/SKILL.md          |    82 +
 .../.agent/skills/skill-creator/LICENSE.txt        |   202 +
 .../.agent/skills/skill-creator/SKILL.md           |   356 +
 .../skill-creator/references/output-patterns.md    |    82 +
 .../skills/skill-creator/references/workflows.md   |    28 +
 .../skills/skill-creator/scripts/init_skill.py     |   303 +
 .../skills/skill-creator/scripts/package_skill.py  |   110 +
 .../skills/skill-creator/scripts/quick_validate.py |    95 +
 .../.agent/skills/slack-gif-creator/LICENSE.txt    |   202 +
 .../.agent/skills/slack-gif-creator/SKILL.md       |   254 +
 .../slack-gif-creator/core/color_palettes.py       |   302 +
 .../.agent/skills/slack-gif-creator/core/easing.py |   234 +
 .../slack-gif-creator/core/frame_composer.py       |   176 +
 .../skills/slack-gif-creator/core/gif_builder.py   |   269 +
 .../skills/slack-gif-creator/core/typography.py    |   357 +
 .../skills/slack-gif-creator/core/validators.py    |   136 +
 .../slack-gif-creator/core/visual_effects.py       |   494 +
 .../skills/slack-gif-creator/requirements.txt      |     4 +
 .../skills/slack-gif-creator/templates/bounce.py   |   106 +
 .../skills/slack-gif-creator/templates/explode.py  |   331 +
 .../skills/slack-gif-creator/templates/fade.py     |   329 +
 .../skills/slack-gif-creator/templates/flip.py     |   291 +
 .../slack-gif-creator/templates/kaleidoscope.py    |   211 +
 .../skills/slack-gif-creator/templates/morph.py    |   329 +
 .../skills/slack-gif-creator/templates/move.py     |   293 +
 .../skills/slack-gif-creator/templates/pulse.py    |   268 +
 .../skills/slack-gif-creator/templates/shake.py    |   127 +
 .../skills/slack-gif-creator/templates/slide.py    |   291 +
 .../skills/slack-gif-creator/templates/spin.py     |   269 +
 .../skills/slack-gif-creator/templates/wiggle.py   |   300 +
 .../skills/slack-gif-creator/templates/zoom.py     |   312 +
 .../.agent/skills/system_bootstrap/SKILL.md        |    45 +
 .../.agent/skills/template-skill/SKILL.md          |     6 +
 .../.agent/skills/theme-factory/LICENSE.txt        |   202 +
 .../.agent/skills/theme-factory/SKILL.md           |    59 +
 .../.agent/skills/theme-factory/theme-showcase.pdf |   Bin 0 -> 124310 bytes
 .../skills/theme-factory/themes/arctic-frost.md    |    19 +
 .../theme-factory/themes/botanical-garden.md       |    19 +
 .../skills/theme-factory/themes/desert-rose.md     |    19 +
 .../skills/theme-factory/themes/forest-canopy.md   |    19 +
 .../skills/theme-factory/themes/golden-hour.md     |    19 +
 .../skills/theme-factory/themes/midnight-galaxy.md |    19 +
 .../theme-factory/themes/modern-minimalist.md      |    19 +
 .../skills/theme-factory/themes/ocean-depths.md    |    19 +
 .../theme-factory/themes/sunset-boulevard.md       |    19 +
 .../skills/theme-factory/themes/tech-innovation.md |    19 +
 .../skills/web-artifacts-builder/LICENSE.txt       |   202 +
 .../.agent/skills/web-artifacts-builder/SKILL.md   |    74 +
 .../scripts/bundle-artifact.sh                     |    54 +
 .../web-artifacts-builder/scripts/init-artifact.sh |   322 +
 .../scripts/shadcn-components.tar.gz               |   Bin 0 -> 19967 bytes
 .../.agent/skills/webapp-testing/LICENSE.txt       |   202 +
 .../.agent/skills/webapp-testing/SKILL.md          |    96 +
 .../webapp-testing/examples/console_logging.py     |    35 +
 .../webapp-testing/examples/element_discovery.py   |    40 +
 .../examples/static_html_automation.py             |    33 +
 .../skills/webapp-testing/scripts/with_server.py   |   106 +
 .../.agent/skills/xlsx/LICENSE.txt                 |    30 +
 .../.agent/skills/xlsx/SKILL.md                    |   289 +
 .../.agent/skills/xlsx/recalc.py                   |   178 +
 archive/agent-onboarding-package-v2.0.0/AGENTS.md  |   742 +
 .../docs/AGENT-AGNOSTIC-TOOLING-PLAN.md            |   650 +
 .../docs/AGENT-ONBOARDING-README.md                |    58 +
 .../docs/RED-TEAM-MCP-SERVERS.md                   |   325 +
 .../docs/SKILLS-AND-MCP-INVENTORY.md               |   544 +
 .../home/hyperd/.mcp/config.json                   |    52 +
 .../agent_communication_protocol.py                |   467 +
 .../agentic-patterns/chain_of_verification.py      |    97 +
 .../agentic-patterns/collaborative_planning.py     |   497 +
 .../agentic-patterns/debate_pattern.py             |    81 +
 .../agentic-patterns/multi_agent_orchestration.py  |   621 +
 .../agentic-patterns/pipeline_orchestration.py     |   945 +
 .../agentic-patterns/plan_and_solve.py             |    94 +
 .../agentic-patterns/quality_consensus.py          |   486 +
 .../agentic-patterns/react_pattern.py              |   369 +
 .../agentic-patterns/reflexion_pattern.py          |   454 +
 .../agentic-patterns/self_consistency.py           |   109 +
 .../agentic-patterns/tree_of_thoughts.py           |   406 +
 .../agentic-patterns/workflow_automation.py        |   575 +
 .../autonomous-orchestrator/__init__.py            |    93 +
 .../autonomous-orchestrator/approval.py            |   534 +
 .../autonomous-orchestrator/delegation_protocol.py |   662 +
 .../autonomous-orchestrator/orchestrator.py        |   315 +
 .../autonomous-orchestrator/security_enforcer.py   |   335 +
 .../autonomous-orchestrator/security_policy.json   |   185 +
 .../autonomous-orchestrator/verification.py        |   550 +
 .../agent_learning_aggregator.py                   |   499 +
 .../federated_pattern_synthesis.py                 |   461 +
 .../01-containerize-dashboard-api.json             |   101 +
 .../ai-stack-ralph-tasks/02-fix-critical-bugs.json |   215 +
 .../03-p3-perf-001-query-cache-real.json           |   106 +
 .../04-p3-perf-002-connection-pool-real.json       |   135 +
 .../05-fix-dashboard-aidb-section.json             |   114 +
 .../06-fix-resource-leak-bug.json                  |    24 +
 .../07-implement-query-cache-with-aidb.json        |    26 +
 .../08-implement-connection-pooling.json           |    27 +
 .../09-fix-websocket-race-condition.json           |    22 +
 .../10-fix-event-loop-blocking.json                |    23 +
 .../complete-production-hardening.json             |   255 +
 .../completion-workflow/01-api-contract-tests.json |    12 +
 .../02-adaptive-iteration-logic.json               |    12 +
 .../completion-workflow/03-dashboard-controls.json |    11 +
 .../04-learning-optimization-proposals.json        |    12 +
 .../fix-dashboard-integration.json                 |   145 +
 .../p3-perf-001-query-caching.json                 |    76 +
 .../p3-perf-002-connection-pooling.json            |    93 +
 archive/ai-stack-ralph-tasks/remaining-tasks.json  |   281 +
 archive/ai-stack-ralph-tasks/test-simple-fix.json  |    12 +
 archive/ai-stack-ralph-tasks/test-simple-task.json |    21 +
 archive/ai-stack-tests/docker-compose.test.yml     |   122 +
 archive/deprecated-scripts/ai-stack-full-test.sh   |     6 +
 archive/deprecated-scripts/ai-stack-manage.sh      |     6 +
 archive/deprecated-scripts/ai-stack-monitor.sh     |     6 +
 archive/deprecated-scripts/ai-stack-startup.sh     |     6 +
 archive/deprecated-scripts/container-lifecycle.sh  |     6 +
 .../deploy-jan2026-updates-optionA.sh              |     6 +
 .../deprecated-scripts/enable-podman-containers.sh |     6 +
 archive/deprecated-scripts/enable-podman-tcp.sh    |     6 +
 archive/deprecated-scripts/hybrid-ai-stack.sh      |     6 +
 archive/deprecated-scripts/initialize-ai-stack.sh  |     6 +
 archive/deprecated-scripts/local-ai-starter.sh     |     6 +
 .../deprecated-scripts/podman-ai-stack-monitor.sh  |     6 +
 archive/deprecated-scripts/podman-ai-stack.sh      |     6 +
 archive/deprecated-scripts/reset-ai-volumes.sh     |     6 +
 archive/deprecated-scripts/setup-podman-api.sh     |     6 +
 .../deprecated-scripts/swap-embeddings-model.sh    |     6 +
 archive/deprecated-scripts/swap-llama-cpp-model.sh |     6 +
 archive/deprecated-scripts/verify-nixos-docs.sh    |     6 +
 archive/deprecated-scripts/verify-upgrades.sh      |     6 +
 archive/deprecated/README.md                       |    42 +
 .../lib/runtime-superseded/ai-stack-containers.sh  |    96 +
 .../deprecated/lib/runtime-superseded/common.sh    |  3474 +++
 .../deprecated/lib/runtime-superseded/config.sh    |  4728 ++++
 .../deprecated/lib/runtime-superseded/reporting.sh |  1164 +
 .../service-conflict-resolution.sh                 |   359 +
 archive/deprecated/lib/runtime-superseded/tools.sh |  3691 +++
 .../lib/runtime-superseded/validation.sh           |   627 +
 .../nix/modules/services/mcp-servers-oci.nix       |   341 +
 archive/deprecated/nixos-quick-deploy-v3.0.0.old   |  7698 +++++++
 .../deprecated/nixos-quick-deploy.sh.backup-v3.0.0 |  7698 +++++++
 archive/deprecated/requirements.txt                |    22 +
 .../generate-dashboard-data-lite.sh                |    11 +
 .../run-dashboard-collector-full.sh                |    12 +
 .../run-dashboard-collector-lite.sh                |    12 +
 .../deprecated/systemd/telemetry-rotation.service  |    26 +
 .../deprecated/systemd/telemetry-rotation.timer    |    17 +
 archive/patches/enable-cosmic-power-profiles.patch |    20 +
 archive/podman-legacy-2026-01/compose/.env.example |    81 +
 .../compose/docker-compose.dev.yml                 |    10 +
 .../compose/docker-compose.yml                     |  1143 +
 .../compose/docker-compose.yml.bak                 |  1040 +
 .../grafana/provisioning/dashboards/ai-stack.json  |    89 +
 .../grafana/provisioning/dashboards/default.yml    |    11 +
 .../provisioning/datasources/prometheus.yml        |     8 +
 .../compose/nginx/certs/.gitkeep                   |     0
 .../compose/nginx/certs/localhost.crt              |    34 +
 .../compose/nginx/certs/localhost.key              |    18 +
 .../podman-legacy-2026-01/compose/nginx/nginx.conf |   120 +
 .../compose/prometheus/alerts/ai-stack-alerts.yml  |   144 +
 .../compose/prometheus/prometheus.yml              |    17 +
 .../podman-legacy-2026-01/compose/secrets/.gitkeep |     0
 .../compose/secrets/aidb_api_key                   |     1 +
 .../compose/secrets/aider_wrapper_api_key          |     1 +
 .../compose/secrets/container_engine_api_key       |     1 +
 .../compose/secrets/dashboard_api_key              |     1 +
 .../compose/secrets/embeddings_api_key             |     1 +
 .../compose/secrets/grafana_admin_password         |     1 +
 .../compose/secrets/hybrid_coordinator_api_key     |     1 +
 .../compose/secrets/nixos_docs_api_key             |     1 +
 .../compose/secrets/postgres_password              |     1 +
 .../compose/secrets/ralph_wiggum_api_key           |     1 +
 .../compose/secrets/redis_password                 |     1 +
 .../compose/secrets/stack_api_key                  |     1 +
 .../local-ai-stack/.env.example                    |   105 +
 .../local-ai-stack/docker-compose.yml              |  1002 +
 archive/podman-legacy-2026-01/podman.nix           |    71 +
 .../podman-legacy-2026-01/reset-podman-runtime.sh  |    81 +
 archive/podman-legacy-2026-01/test-podman-api.sh   |   379 +
 archive/scripts/cleanup-hanging-compose.sh         |    74 +
 archive/scripts/test-password-migration.sh         |   497 +
 archive/temp-artifacts/output.txt                  |     1 +
 .../temp-docs-20251120/AI-MODELS-PRUNING-GUIDE.md  |   201 +
 .../CONFLICT-RESOLUTION-INTEGRATION-SUMMARY.md     |   350 +
 .../temp-docs-20251120/DECLARATIVE-SERVICE-FIX.md  |   344 +
 .../DUPLICATE-PODMAN-FIX-COMPLETE.md               |   387 +
 .../DUPLICATE-PODMAN-RESOLUTION.md                 |   201 +
 archive/temp-docs-20251120/FIX-VERIFIED-WORKING.md |   218 +
 .../NIXOS-SERVICE-CONFLICT-FIX.md                  |   300 +
 .../temp-docs-20251120/PODMAN-AI-STACK-OVERVIEW.md |   498 +
 .../PODMAN-AI-STACK-TIMEOUT-FIX.md                 |   210 +
 .../temp-docs-20251120/PORT-CONFLICT-SOLUTION.md   |   313 +
 .../temp-docs-20251120/RECOVERY-INSTRUCTIONS.md    |   110 +
 .../temp-docs-20251120/TGI-PODMAN-ARCHITECTURE.md  |   397 +
 .../ai-stack-port-conflict-solutions.md            |   214 +
 archive/temp-docs-20251120/fix-stuck-rebuild.sh    |   102 +
 .../migrate-to-user-level-ai-stack.sh              |   125 +
 .../temp-docs-20251120/test-aidb-integration.sh    |   272 +
 .../test-conflict-resolution-simple.sh             |   207 +
 .../temp-docs-20251120/test-conflict-resolution.sh |   147 +
 archive/temp-docs-20251120/test-tgi-services.sh    |   155 +
 archive/templates/systemd-legacy/README.md         |    16 +
 .../systemd-legacy/ai-stack-cleanup.service        |    29 +
 .../systemd-legacy/ai-stack-resume-recovery.sh     |    12 +
 .../ai-stack-runtime-recovery.service              |    23 +
 .../systemd-legacy/claude-api-proxy.service        |    26 +
 .../skill-reference-lint/broken-skill/SKILL.md     |     8 +
 .../skill-reference-lint/valid-skill/SKILL.md      |     8 +
 .../skill-reference-lint/valid-skill/reference.md  |     1 +
 archive/test_llama.py                              |    25 +
 archive/tests-deprecated/README.md                 |    36 +
 .../tests-deprecated/check-ai-stack-health-v2.py   |    47 +
 archive/tests-deprecated/check-ai-stack-health.sh  |    44 +
 .../check-capability-catalog-append.sh             |    41 +
 archive/tests-deprecated/check-capability-gap.sh   |   225 +
 .../check-capability-patch-apply.sh                |    55 +
 .../check-capability-patch-prep.sh                 |    38 +
 .../tests-deprecated/check-capability-promotion.sh |    48 +
 .../check-capability-remediation.sh                |    70 +
 archive/tests-deprecated/check-capability-stub.sh  |    64 +
 .../check-failed-units-classification.sh           |    64 +
 .../check-harness-sdk-version-parity.sh            |    33 +
 .../tests-deprecated/check-prsi-phase7-program.sh  |    47 +
 .../tests-deprecated/check-runtime-act-wrapper.sh  |   103 +
 .../check-runtime-diagnose-classifications.sh      |   233 +
 .../check-runtime-incident-tooling.sh              |    21 +
 .../check-runtime-loop-integration.sh              |    57 +
 .../tests-deprecated/check-runtime-plan-catalog.sh |   252 +
 .../check-runtime-remediation-runner.sh            |   174 +
 archive/tests-deprecated/check-system-act.sh       |   163 +
 archive/tests-deprecated/check-tls-log-warnings.sh |    76 +
 archive/tests-deprecated/demo-local-ai-usage.py    |   178 +
 archive/tests-deprecated/generated-code.py         |     7 +
 archive/tests-deprecated/generated_code.py         |     5 +
 archive/tests-deprecated/rag-smoke-test.sh         |   125 +
 .../tests-deprecated/smoke-cross-client-compat.sh  |    95 +
 .../smoke-skill-bundle-distribution.sh             |    67 +
 archive/tests-deprecated/telemetry-smoke-test.sh   |    49 +
 archive/tests-deprecated/test-ai-stack-health.sh   |    22 +
 .../tests-deprecated/test-container-recovery.sh    |    49 +
 .../test-context-compression-validation.py         |    74 +
 .../test-continuous-learning-demo.py               |   174 +
 .../tests-deprecated/test-continuous-learning.py   |   529 +
 archive/tests-deprecated/test-learning-simple.sh   |    31 +
 archive/tests-deprecated/test-rag-workflow.py      |   414 +
 archive/tests-deprecated/test-services.sh          |   128 +
 archive/tests-deprecated/test-vim-yank.py          |   140 +
 .../tests-deprecated/test_real_world_workflows.sh  |     3 +
 archive/tests-deprecated/test_services.sh          |     3 +
 archive/tests-deprecated/test_vim_yank.py          |     5 +
 .../validate-agent-capability-contract.sh          |    79 +
 .../tests-deprecated/validate-config-settings.bats |    24 +
 .../tests-deprecated/validate-config-settings.sh   |    83 +
 .../tests-deprecated/validate-deploy-doc-flags.sh  |    56 +
 archive/tests-deprecated/validate-flake-inputs.sh  |   444 +
 .../validate-skill-references.bats                 |    22 +
 .../validate-tool-execution-policy.sh              |    52 +
 .../validate-tool-management-policy.sh             |    80 +
 .../tests-deprecated/verify-local-llm-feedback.sh  |    93 +
 archive/tests-deprecated/verify-model-safety.sh    |   220 +
 archive/tests-deprecated/verify-skill-registry.sh  |    35 +
 .../tests-deprecated/vim-yank-implementation.py    |   226 +
 .../tests-deprecated/vim_yank_implementation.py    |     5 +
 .../test_qdrant_client_compat.py                   |    90 +
 .../hybrid-coordinator/test_reasoning_profiles.py  |   156 +
 .../test_route_handler_optimizations.py            |  1501 ++
 .../test_search_router_reranking.py                |   836 +
 .../hybrid-coordinator/test_task_classifier.py     |   278 +
 archive/tests-python-stale/workflows/__init__.py   |     1 +
 .../workflows/test_coordinator.py                  |   294 +
 archive/tests-python-stale/workflows/test_graph.py |   402 +
 .../workflows/test_integration.py                  |   396 +
 .../tests-python-stale/workflows/test_parser.py    |   321 +
 .../tests-python-stale/workflows/test_validator.py |   425 +
 archive/tests-stale/check_bounding_boxes_test.py   |   226 +
 archive/tests-stale/test_agent_executor.py         |   117 +
 .../test_document_importer_route_stack.py          |    92 +
 assets/aqos-progress-tracker.html                  |   572 +
 assets/dashboard.js                                |  8570 +++++++
 assets/education/context-engineering.html          |   303 +
 assets/education/hardware-limits.html              |   335 +
 assets/education/nixos-contracts.html              |   305 +
 assets/modules/affective-engine-module.html        |   502 +
 assets/modules/aidb-rag-stores.html                |   510 +
 assets/modules/aq-eval-harness.html                |   509 +
 assets/modules/aq-inference-bench.html             |   507 +
 assets/modules/auto-skill-selection.html           |   503 +
 assets/modules/capability-intake.html              |   504 +
 assets/modules/dashboard-observability.html        |   504 +
 assets/modules/github-mcp-readonly.html            |   501 +
 assets/modules/identity-kernel-service.html        |   503 +
 assets/modules/local-agent-delegation.html         |   505 +
 assets/modules/nixos-static-analysis.html          |   502 +
 assets/modules/osint-research-store.html           |   502 +
 assets/modules/playwright-mcp.html                 |   503 +
 assets/modules/semgrep-mcp.html                    |   501 +
 assets/modules/t3mp3st-intake.html                 |   505 +
 assets/modules/tooling-manifest.html               |   503 +
 assets/modules/understand-anything.html            |   502 +
 assets/modules/workflow-blueprints.html            |   503 +
 assets/readme/command-center-demo.gif              |   Bin 0 -> 260862 bytes
 assets/readme/command-center-hero.png              |   Bin 0 -> 263712 bytes
 assets/readme/command-center-overview.png          |   Bin 0 -> 263712 bytes
 assets/readme/command-center-screenshot.png        |   Bin 0 -> 592599 bytes
 assets/readme/command-center-services.png          |   Bin 0 -> 379620 bytes
 assets/readme/operator-flow.svg                    |    35 +
 assets/readme/system-overview.svg                  |    64 +
 assets/vendor/chart.umd.min.js                     |    20 +
 assets/vendor/d3.v7.min.js                         |     2 +
 assets/vendor/mermaid.min.js                       |  3405 +++
 canon/blocks/fable-parity.md                       |    16 +
 canon/canon.yaml                                   |    20 +
 config/.gitignore                                  |     5 +
 config/README.md                                   |    27 +
 config/ablation-reasoning-profiles.json            |   100 +
 config/agent-action-policy.json                    |    34 +
 config/agent-capability-contract.json              |    53 +
 config/agent-capability-intake-candidates.json     |   557 +
 config/agent-context-cards.json                    |   658 +
 config/agent-dispatch-budget.json                  |    22 +
 config/agent-dispatch-policy.json                  |    26 +
 config/agent-memory-surface-registry.json          |   150 +
 config/agent-ops-profile.json                      |    14 +
 config/agent-routing-policy.json                   |   141 +
 config/ai-capability-implementation-backlog.json   |   547 +
 config/ai-harness-slice-registry.json              |  4002 ++++
 config/ai-harness-slice-registry.schema.json       |   506 +
 config/ai-slo-thresholds.json                      |    17 +
 config/ai-stack-agent-discovery.json               |   257 +
 config/ai-stack-hardware-profiles.json             |   283 +
 config/alert-rules.yaml                            |   168 +
 config/anomaly-detection.yaml                      |   152 +
 config/approved-skill-sources.json                 |    20 +
 config/aq-eval-suites.json                         |   110 +
 config/aq-inference-benchmarks.json                |   101 +
 config/aq-integrity-logical-orphans.json           |   696 +
 config/aqos/c6-owner-public-keys.json              |    13 +
 config/aqos/c6-scheduler-signer-keys.json          |    12 +
 config/aqos/lease-signer-keys.json                 |    12 +
 config/autonomous-coordinator-security-policy.json |   200 +
 config/backend-benchmark-results.json              |    27 +
 config/bench-promotion-criteria.json               |    62 +
 config/capability-gap-catalog.json                 |   280 +
 config/capability-lease-epoch                      |     1 +
 config/capability-lifecycle-registry.json          |   526 +
 config/capability-package-resolvers.json           |   591 +
 config/capability-remediation-policy.json          |    21 +
 config/capability-stack-hints.json                 |   335 +
 config/clm-compaction-prompt.yaml                  |    38 +
 config/curated-web-research-sources.json           |   347 +
 config/defaults.sh                                 |   131 +
 config/delegation-prompt-contracts.json            |   133 +
 config/deploy.yaml                                 |    44 +
 config/doc-frontmatter-schema.yaml                 |   229 +
 config/domain-knowledge-seeds.json                 |    73 +
 config/drops.yaml                                  |    49 +
 config/edge-model-registry.json                    |    83 +
 config/env-contract.yaml                           |  1357 ++
 config/feature-defaults.yaml                       |   438 +
 config/first-party-tools.json                      |   283 +
 config/grant-signing-public-key                    |     1 +
 config/hardware-capability-matrix.json             |   663 +
 config/harness-first-high-impact-paths.txt         |    14 +
 config/harness-first-platform-owners.txt           |     4 +
 config/harness-first-policy.json                   |    39 +
 config/harness-prompt-extensions.json              |   115 +
 config/harness-prompt-extensions.yaml              |   100 +
 ...rdr-presentation-source-to-field-ledger.v1.json |   432 +
 config/hospital-gate-hostnetwork-allowlist.txt     |     4 +
 config/identity-values.yaml                        |    21 +
 config/improvement-sources.json                    |   354 +
 config/intent-routing-map.json                     |   181 +
 config/keys/skill-registry-trust-roots.json        |    11 +
 config/lane-eligibility-registry.json              |   150 +
 config/legacy-root-script-aliases.txt              |    47 +
 config/lessons/agentic-slice-lessons.json          |    99 +
 config/llama-cpp-models.sha256                     |    12 +
 config/local-agent-config.yaml                     |   345 +
 config/local-agent-grounding-micro.md              |    24 +
 config/local-agent-grounding.md                    |   143 +
 config/local-delegation-runtime-policy.json        |    38 +
 config/local-inference-policy.json                 |    41 +
 config/local-inference-transport-policy.json       |    40 +
 config/local-model-config.yaml                     |    94 +
 config/local-model-requirements.md                 |    75 +
 config/memory-recall-benchmark-seeds.json          |    34 +
 config/model-cache.yaml                            |   173 +
 config/model-catalog.yaml                          |   233 +
 config/model-coordinator.json                      |   358 +
 config/model-profile.json                          |    31 +
 config/multi-agent-collaboration.yaml              |   351 +
 config/notifications.yaml                          |   148 +
 config/npm-packages.sh                             |    45 +
 ...operator-context-source-to-field-ledger.v1.json |   361 +
 config/orchestration-graph-templates.json          |   208 +
 config/package-count-baseline.json                 |    35 +
 config/parity-scorecard.json                       |   120 +
 config/progressive-disclosure-domains.json         |   598 +
 config/provider-fallback-policy.json               |   141 +
 config/prsi/confidence-calibration-policy.json     |    30 +
 config/prsi/edge-brownout-policy.json              |    20 +
 config/prsi/eval-pinning-policy.json               |    18 +
 config/prsi/high-risk-approval-rubric.json         |    15 +
 config/prsi/quarantine-workflow.json               |    23 +
 config/prsi/validation-matrix.json                 |    41 +
 config/python-tooling-policy-allowlist.txt         |    12 +
 config/qa-provider-probe-contract.schema.json      |   415 +
 config/qa-provider-probe-policy.json               |    42 +
 config/qa-xfail.yaml                               |    16 +
 config/query-performance.yaml                      |   244 +
 config/reasoning-profiles.json                     |   155 +
 config/refactor-milestones.json                    |   388 +
 config/repo-structure-allowlist.txt                |   333 +
 config/review-feedback-policy.json                 |    11 +
 config/root-file-allowlist.txt                     |    26 +
 config/root-script-shim-allowlist.txt              |     3 +
 config/route-aliases.json                          |    62 +
 config/routing-policy.yaml                         |    47 +
 config/runtime-budget-policy.json                  |    45 +
 config/runtime-isolation-profiles.json             |    57 +
 config/runtime-prsi-policy.json                    |    95 +
 config/runtime-remediation-catalog.json            |   209 +
 config/runtime-remediation-policy.json             |    23 +
 config/runtime-safety-policy.json                  |   110 +
 config/runtime-scheduler-policy.json               |    30 +
 config/runtime-tool-security-policy.json           |    52 +
 config/safety-rails.yaml                           |    51 +
 .../agent-capability-intake-candidates.schema.json |    96 +
 config/schemas/agent-dispatch-envelope.schema.json |   125 +
 config/schemas/agent-dispatch-policy.schema.json   |    30 +
 .../agent-ops-local-direct-health.schema.json      |   152 +
 config/schemas/agent-ops-projection.schema.json    |   261 +
 ...i-capability-implementation-backlog.schema.json |    66 +
 config/schemas/aq-canon-spec-v1.json               |    42 +
 config/schemas/aq-eval-suites.schema.json          |    80 +
 config/schemas/aq-evidence-record-v1.json          |   113 +
 config/schemas/aq-inference-benchmarks.schema.json |    60 +
 .../capability-lease-gate-decision.schema.json     |    56 +
 .../capability-lease-shadow-record.schema.json     |    54 +
 config/schemas/capability-lease.schema.json        |   119 +
 config/schemas/delegation-task-record.schema.json  |   115 +
 .../execution-cell-adapter-receipt.schema.json     |    33 +
 .../execution-cell-runner-decision.schema.json     |    86 +
 config/schemas/harness-first/policy.schema.json    |    44 +
 .../harness/remote-task-contract.schema.json       |    43 +
 config/schemas/herdr-presentation.schema.json      |    24 +
 config/schemas/learning-candidate.schema.json      |    59 +
 .../local-delegation-runtime-policy.schema.json    |   107 +
 config/schemas/local-inference-error.schema.json   |    19 +
 config/schemas/local-inference-event.schema.json   |    22 +
 config/schemas/local-inference-payload-v1.json     |    37 +
 config/schemas/local-inference-policy.schema.json  |   117 +
 ...-inference-producer-revision-set-v1.schema.json |    21 +
 config/schemas/local-inference-request.schema.json |   121 +
 ...l-inference-resolved-shadow-plan-v1.schema.json |    31 +
 config/schemas/local-inference-result.schema.json  |    79 +
 ...ence-shadow-observation-metadata-v1.schema.json |    14 +
 ...cal-inference-shadow-observation-v1.schema.json |    36 +
 ...erence-shadow-request-projection-v1.schema.json |    13 +
 .../local-inference-transport-policy.schema.json   |    66 +
 .../schemas/local-inference-transport.schema.json  |   408 +
 ...-inference-trusted-fact-envelope-v1.schema.json |    17 +
 ...ference-trusted-fact-unavailable-v1.schema.json |    14 +
 config/schemas/maeah/agent-run-event.schema.json   |   205 +
 config/schemas/maeah/lifecycle-event.schema.json   |    25 +
 config/schemas/maeah/model-entry.schema.json       |    71 +
 config/schemas/maeah/spec-variant-pack.schema.json |    93 +
 config/schemas/operator-context.schema.json        |   605 +
 config/schemas/prsi/cycle-outcome.schema.json      |    53 +
 config/schemas/prsi/cycle-plan.schema.json         |   101 +
 config/schemas/prsi/validation-report.schema.json  |    55 +
 config/schemas/review-feedback-policy.schema.json  |    17 +
 config/schemas/review-round-receipt.schema.json    |    45 +
 config/schemas/revocation-epoch-bump.schema.json   |    71 +
 config/schemas/scheduler-lease-context.schema.json |    28 +
 .../scheduler-lease-gate-decision.schema.json      |    65 +
 config/schemas/span-taxonomy.schema.json           |   130 +
 .../suggested-ai-repo-candidates.schema.json       |    71 +
 .../schemas/system-capability-catalog.schema.json  |    63 +
 .../schemas/system-state-authorities.schema.json   |   288 +
 config/schemas/workflow-deviation.schema.json      |    48 +
 config/schemas/workflow-dsl.schema.json            |   298 +
 .../schemas/workflow-shadow-contracts.schema.json  |   126 +
 config/script-header-waivers.txt                   |   121 +
 config/security/npm-threat-intel.json              |    28 +
 config/service-endpoints.sh                        |   116 +
 config/settings.sh                                 |   142 +
 config/stale-trim-keep.txt                         |    25 +
 config/suggested-ai-repo-candidates.json           |   763 +
 config/switchboard-profiles.yaml                   |   369 +
 config/system-capability-catalog.json              |   732 +
 config/system-state-authorities.yaml               |   508 +
 config/template-placeholder-baseline.tsv           |    12 +
 config/training-manifest.yaml                      |   128 +
 config/validation-check-registry.json              |  1838 ++
 config/variables.sh                                |   849 +
 config/workflow-automation.yaml                    |   329 +
 config/workflow-blueprints.json                    |  1011 +
 config/workflow-shadow-db-privileges.json          |   226 +
 config/workflow-shadow-phase-tokens.json           |    25 +
 contracts/__init__.py                              |     8 +
 contracts/config/__init__.py                       |    37 +
 contracts/config/switchboard_profiles.py           |    72 +
 contracts/events/__init__.py                       |     8 +
 contracts/events/envelope.py                       |   110 +
 crates/contract-validator/Cargo.toml               |     7 +
 crates/contract-validator/src/main.rs              |   567 +
 dashboard.html                                     |  2880 +++
 dashboard/README.md                                |    58 +
 dashboard/VIRTUAL-LAYOUT.json                      |    38 +
 dashboard/backend/.env.example                     |    19 +
 dashboard/backend/Dockerfile                       |    19 +
 dashboard/backend/api/__init__.py                  |     1 +
 dashboard/backend/api/config/__init__.py           |     0
 dashboard/backend/api/config/service_endpoints.py  |    78 +
 dashboard/backend/api/main.py                      |   503 +
 dashboard/backend/api/routes/__init__.py           |     1 +
 dashboard/backend/api/routes/actions.py            |   168 +
 dashboard/backend/api/routes/adk.py                |   469 +
 dashboard/backend/api/routes/aistack.py            |  8295 +++++++
 dashboard/backend/api/routes/approvals.py          |   504 +
 dashboard/backend/api/routes/audit.py              |   165 +
 dashboard/backend/api/routes/collaboration.py      |   793 +
 dashboard/backend/api/routes/config.py             |   780 +
 dashboard/backend/api/routes/containers.py         |    98 +
 dashboard/backend/api/routes/deployments.py        |  1019 +
 dashboard/backend/api/routes/firewall.py           |   820 +
 dashboard/backend/api/routes/health.py             |   556 +
 dashboard/backend/api/routes/insights.py           |   353 +
 dashboard/backend/api/routes/metrics.py            |    49 +
 dashboard/backend/api/routes/models.py             |   552 +
 dashboard/backend/api/routes/pm.py                 |    94 +
 dashboard/backend/api/routes/search_performance.py |   325 +
 dashboard/backend/api/routes/security.py           |   507 +
 dashboard/backend/api/routes/services.py           |    87 +
 dashboard/backend/api/routes/testing.py            |   245 +
 dashboard/backend/api/routes/topology.py           |   208 +
 dashboard/backend/api/routes/websockets.py         |     7 +
 dashboard/backend/api/routes/workflows.py          |  1224 +
 dashboard/backend/api/services/__init__.py         |     1 +
 dashboard/backend/api/services/ai_insights.py      |  2014 ++
 .../backend/api/services/ai_service_health.py      |   384 +
 .../backend/api/services/container_manager.py      |   103 +
 dashboard/backend/api/services/context_store.py    |  2618 +++
 .../backend/api/services/metrics_collector.py      |   523 +
 dashboard/backend/api/services/qa_runner.py        |   476 +
 dashboard/backend/api/services/runtime_controls.py |   337 +
 dashboard/backend/api/services/service_manager.py  |   171 +
 dashboard/backend/api/services/systemd_units.py    |   106 +
 dashboard/backend/requirements.txt                 |     9 +
 dashboard/backend/static/approve.html              |   636 +
 data/.gitkeep                                      |     0
 data/README.md                                     |   133 +
 data/ai-research-scorecard.json                    |     7 +
 data/github-focused-agent-repos-2026-03-03.json    |   919 +
 data/github-focused-agent-repos-2026-03-03.md      |    42 +
 data/github-keyword-repos-2026-03-03.json          |   718 +
 data/github-keyword-repos-2026-03-03.md            |    59 +
 data/github-semantic-keyword-repos-2026-03-03.json |  1969 ++
 data/github-semantic-keyword-repos-2026-03-03.md   |   238 +
 data/golden/.agent-no-read                         |    10 +
 data/golden/tasks.json                             |    27 +
 data/harness-gap-eval-pack-optimized.json          |    25 +
 data/harness-gap-eval-pack.json                    |   151 +
 data/harness-golden-evals.json                     |   201 +
 data/harness-holdout-evals.json                    |    25 +
 data/improvement-crawler-state.json                |    65 +
 data/parity/repo-parity-db.json                    |   604 +
 data/prsi-artifacts/examples/cycle_outcome.json    |    25 +
 data/prsi-artifacts/examples/cycle_plan.json       |    52 +
 .../prsi-artifacts/examples/validation_report.json |    48 +
 .../high-risk-approval-template.json               |    14 +
 data/prsi-artifacts/quarantine-template.json       |    10 +
 data/prsi-negative-control-canary.json             |    25 +
 deploy                                             |   343 +
 docs/AGENT-INTEGRATION-WORKFLOW.md                 |     6 +
 docs/AGENT-ONBOARDING-README.md                    |     6 +
 docs/AGENT-PARITY-MATRIX.md                        |   860 +
 docs/AGENTS.md                                     |  1211 +
 docs/AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md     |    14 +
 docs/AI-STACK-FULL-INTEGRATION.md                  |    10 +
 docs/AI-STACK-V3-AGENTIC-ERA-GUIDE.md              |    10 +
 docs/AQD-CLI-USAGE.md                              |    67 +
 docs/AVAILABLE_TOOLS.md                            |    16 +
 docs/BOOT-FS-RESILIENCE-GUARDRAILS.md              |    70 +
 docs/BUILD_OPTIMIZATION.md                         |     6 +
 docs/CLAUDE-CODE-ERROR-ANALYSIS.md                 |   412 +
 docs/CLEAN-SETUP.md                                |   107 +
 docs/CODE_EXAMPLES.md                              |    10 +
 docs/COMPREHENSIVE-SYSTEM-ANALYSIS.md              |    10 +
 docs/CONFIGURATION-REFERENCE.md                    |    85 +
 docs/CONTEXT-OPTIMIZATION-STRATEGIES-2026.md       |     6 +
 docs/DASHBOARD-DEPLOYMENT-INTEGRATION.md           |   337 +
 docs/DASHBOARD-VISUAL-GUIDE.md                     |    10 +
 docs/DEPLOYMENT-PERSISTENCE-VERIFIED.md            |    10 +
 docs/DEPLOYMENT-SUCCESS-V5.md                      |    10 +
 docs/DEVELOPMENT-ROADMAP.md                        |    10 +
 docs/DOCUMENTATION-INDEX.md                        |   143 +
 docs/ERROR_HANDLING_PATTERNS.md                    |   406 +
 docs/FEDERATED-DATA-STRATEGY.md                    |    10 +
 docs/FINETUNING.md                                 |    80 +
 docs/FLAKE-MANAGEMENT.md                           |   103 +
 docs/GLF_OS_REFERENCE.md                           |     6 +
 docs/HAND-IN-GLOVE-INTEGRATION.md                  |    10 +
 docs/HYBRID-AI-SYSTEM-GUIDE.md                     |    10 +
 docs/IMPLEMENTATION-CHECKLIST.md                   |    10 +
 docs/IMPROVEMENTS_IMPLEMENTED.md                   |   223 +
 docs/LOCAL-AI-STARTER.md                           |    10 +
 docs/MCP_SERVERS.md                                |     6 +
 docs/MCP_SETUP.md                                  |   173 +
 docs/NIXOS-25.11-RELEASE-RESEARCH.md               |    10 +
 docs/NIXOS-DEPLOY-SCRIPT-UPDATES.md                |    10 +
 docs/OPENSKILLS-INTEGRATION-PLAN.md                |    10 +
 docs/OPTIONAL_ENHANCEMENTS.md                      |     6 +
 docs/P1-HARDENING-ROADMAP.md                       |    10 +
 docs/PARITY-ADVANCED-TOOLING.md                    |    58 +
 docs/PRODUCTION-HARDENING-ROADMAP.md               |    10 +
 docs/PROGRESSIVE-DISCLOSURE-GUIDE.md               |     9 +
 docs/QUICK-DASHBOARD-REFERENCE.md                  |   109 +
 docs/QUICK_START.md                                |    78 +
 docs/RACE_CONDITIONS_ANALYSIS.md                   |   220 +
 docs/README.md                                     |     6 +
 docs/RED-TEAM-MCP-SERVERS.md                       |     6 +
 docs/REPOSITORY-SCOPE-CONTRACT.md                  |    42 +
 docs/RLM-RAG-SELF-HEALING-IMPLEMENTATION-PLAN.md   |    10 +
 docs/SECURITY-EXCEPTIONS.md                        |    48 +
 docs/SILENT-FAILURES-ANALYSIS.md                   |   255 +
 docs/SKILL-BACKUP-POLICY.md                        |    33 +
 docs/SKILL-MINIMUM-STANDARD.md                     |    42 +
 docs/SKILLS-AND-MCP-INVENTORY.md                   |    35 +
 docs/SOPS-NIX-INTEGRATION.md                       |    10 +
 docs/STRUCTURAL_ISSUES_AND_IMPROVEMENTS.md         |   409 +
 docs/SYNTAX_REFERENCE.md                           |   582 +
 docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md            |  1346 ++
 docs/SYSTEM-IMPROVEMENTS-V5.md                     |    10 +
 docs/SYSTEM-READY-FOR-AIDB.md                      |    10 +
 docs/SYSTEM_PROJECT_DESIGN.md                      |    10 +
 docs/TROUBLESHOOTING.md                            |    20 +
 docs/VIBE-CODING-SYSTEM-ARCHITECTURE.md            |    10 +
 docs/VIRTUALIZATION-SETUP.md                       |     6 +
 docs/VLLM-MIGRATION.md                             |    10 +
 docs/VLLM-MODEL-SELECTION.md                       |    10 +
 docs/agent-guides/00-SYSTEM-OVERVIEW.md            |   185 +
 docs/agent-guides/01-QUICK-START.md                |   124 +
 docs/agent-guides/02-SERVICE-STATUS.md             |    48 +
 docs/agent-guides/10-NIXOS-CONFIG.md               |    91 +
 docs/agent-guides/12-DEBUGGING.md                  |   331 +
 docs/agent-guides/20-LOCAL-LLM-USAGE.md            |   209 +
 docs/agent-guides/21-RAG-CONTEXT.md                |     6 +
 docs/agent-guides/22-CONTINUOUS-LEARNING.md        |   558 +
 docs/agent-guides/30-QDRANT-OPERATIONS.md          |     6 +
 docs/agent-guides/31-POSTGRES-OPS.md               |    29 +
 docs/agent-guides/32-ERROR-LOGGING.md              |     6 +
 docs/agent-guides/40-HYBRID-WORKFLOW.md            |   205 +
 docs/agent-guides/41-VALUE-SCORING.md              |     6 +
 docs/agent-guides/42-PATTERN-EXTRACTION.md         |     6 +
 docs/agent-guides/44-FEDERATION-AUTOMATION.md      |    10 +
 docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md     |   127 +
 docs/agent-guides/46-SWITCHBOARD-PROFILES.md       |   162 +
 docs/agent-guides/47-AGENT-TOOL-CONTRACT.md        |    78 +
 docs/agent-guides/48-WIKI-MAINTENANCE.md           |   180 +
 docs/agent-guides/50-STRANDS-INTEGRATION.md        |    72 +
 docs/agent-guides/50-TOOL-SELECTION-MATRIX.md      |   226 +
 .../51-LOCAL-AGENT-CAPABILITY-ENVELOPE.md          |    46 +
 docs/agent-guides/60-CODE-QUALITY.md               |   112 +
 docs/agent-guides/61-WORKFLOW-PRACTICES.md         |   138 +
 docs/agent-guides/62-MEMORY-SYSTEM.md              |   291 +
 docs/agent-guides/90-COMPREHENSIVE-ANALYSIS.md     |    10 +
 docs/agent-guides/99-CLAUDE-DETAILS-LEGACY.md      |   410 +
 docs/api/README.md                                 |     6 +
 docs/api/aidb-openapi.json                         |     1 +
 docs/api/embeddings-openapi.yaml                   |   136 +
 docs/api/hybrid-openapi.yaml                       |   822 +
 docs/api/maeah-openapi.yaml                        |   261 +
 docs/api/nixos-docs-openapi.yaml                   |    94 +
 docs/api/orchestration-visibility.md               |   297 +
 .../AI-HARNESS-SLICE-REGISTRY-DESIGN.md            |   511 +
 docs/architecture/AI-STACK-ARCHITECTURE.md         |   350 +
 .../GOOGLE-ADK-PARITY-MATRIX-2026-03.md            |   228 +
 docs/architecture/OSI-LAYER-MAPPING.md             |    62 +
 .../PHASE-8-ARCHITECTURE-ASSESSMENT.md             |   185 +
 docs/architecture/RELATIONAL-GRAPH.md              |   255 +
 docs/architecture/REQUEST-ROUTING-FLOW.md          |   221 +
 docs/architecture/ROUTING-ARCHITECTURE-DESIGN.md   |   282 +
 docs/architecture/SYSTEM-RESET-PDR-2026-05.md      |   389 +
 docs/architecture/adk-discovery-log.jsonl          |    27 +
 docs/architecture/agent-behavior-parity-index.md   |    91 +
 docs/architecture/agent-sandbox-parity-analysis.md |   146 +
 docs/architecture/aqos-cycle1-state-spine-adr.md   |    91 +
 docs/architecture/architecture-decisions.md        |   641 +
 docs/architecture/canonical-kernel-declaration.md  |   192 +
 docs/architecture/capability-lifecycle.md          |   190 +
 docs/architecture/cross-surface-change-contract.md |    20 +
 docs/architecture/domain-activation-template.md    |   184 +
 docs/architecture/front-door-routing.md            |   117 +
 docs/architecture/gemini-review-gate.md            |   121 +
 docs/architecture/hybrid-coordinator-module-map.md |   180 +
 docs/architecture/integration-model.md             |   642 +
 .../local-agent-agentic-capabilities.md            |  1083 +
 docs/architecture/local-agent-task-eligibility.md  |   165 +
 docs/architecture/memory-system-design.md          |  1006 +
 .../phase-3-agentic-storage-completion.md          |   351 +
 .../2026-06-29-ai-harness-layer-concept-gemini.md  |   176 +
 ...2026-06-29-ai-harness-memory-systems-roadmap.md |    34 +
 .../research/2026-06-29-ai-repo-discovery-seeds.md |     9 +
 .../2026-06-29-critical-pessimistic-assessment.md  |    62 +
 ...-system-assessment-agi-scaffold-architecture.md |   250 +
 docs/architecture/role-matrix.md                   |   248 +
 docs/architecture/routing-profile-inventory.md     |   233 +
 .../runtime-auth-profile-enforcement.md            |    62 +
 .../system-centric-ai-repos-recommendations.md     |   123 +
 docs/architecture/workflow-dsl-design.md           |   634 +
 docs/architecture/workflow-dsl-reference.md        |  1108 +
 docs/architecture/workflow-executor-integration.md |   603 +
 docs/architecture/workflow-executor-security.md    |   452 +
 docs/archive/03-PROGRESSIVE-DISCLOSURE.md          |     1 +
 .../AGENTIC-WORKFLOW-100-PERCENT-2026-01-05.md     |   412 +
 .../AGENTIC-WORKFLOW-COMPLETE-2026-01-05.md        |   400 +
 docs/archive/AI-AGENT-CLI-TOOL-TRAINING-SUMMARY.md |   648 +
 docs/archive/AI-OPTIMIZER-INTEGRATION-COMPLETE.md  |   763 +
 .../AI-STACK-AGENTIC-WORKFLOW-FIXES-2026-01-05.md  |   444 +
 .../archive/AI-STACK-COMPLETE-STATUS-2026-01-05.md |   457 +
 .../AI-STACK-FEATURE-TEST-RESULTS-2026-01-02.md    |   327 +
 docs/archive/AI-STACK-FIXES-2025-12-31.md          |   262 +
 docs/archive/AI-STACK-FIXES-APPLIED-2025-12-31.md  |   148 +
 docs/archive/AI-STACK-P1-SEC-003-COMPLETION.md     |   199 +
 docs/archive/AI-STACK-UPGRADES-2025.md             |   366 +
 docs/archive/AI-STACK-V3-UPDATE-SUMMARY.md         |   616 +
 .../AI-STACK-VALIDATION-COMPLETE-2026-01-02.md     |   420 +
 docs/archive/AI-SYSTEM-TEST-REPORT-2025-12-22.md   |   526 +
 docs/archive/ALL-FIXES-SUMMARY.md                  |   397 +
 docs/archive/ALL_IMPROVEMENTS_COMPLETE.md          |   391 +
 docs/archive/BOOT-ERRORS-FIXED-2025-12-31.md       |   262 +
 docs/archive/CACHING-IMPLEMENTATION-COMPLETE.md    |   358 +
 docs/archive/CACHING-STRATEGY-2026-01-01.md        |   459 +
 docs/archive/CHANGES-SUMMARY-2025-12-31.md         |   422 +
 docs/archive/CLAUDE-LOCAL-ENFORCEMENT-COMPLETE.md  |   611 +
 docs/archive/COMPLETE-FIX-SUMMARY-2025-12-31.md    |   338 +
 docs/archive/COMPLETE_IMPROVEMENTS_SUMMARY.md      |    65 +
 docs/archive/CONTAINER-DATA-LOSS-FIX.md            |   174 +
 .../archive/CONTAINER-DEPLOYMENT-FIX-2025-12-31.md |   319 +
 docs/archive/CONTAINER-IMAGE-FIX.md                |   326 +
 .../COSMIC-POWER-MANAGEMENT-FIX-2025-12-31.md      |   252 +
 docs/archive/CUDA-PREVENTION-FIX-2026-01-01.md     |   169 +
 .../DASHBOARD-AND-RALPH-COMPLETION-SUMMARY.md      |   545 +
 .../DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md  |   217 +
 .../DASHBOARD-COMPLETE-SUMMARY-2026-01-02.md       |   363 +
 docs/archive/DASHBOARD-CONSOLIDATION-2026-01-02.md |   483 +
 .../DASHBOARD-CONSOLIDATION-SUMMARY-2026-01-02.md  |   391 +
 docs/archive/DASHBOARD-ENHANCEMENTS-2025-12-21.md  |   443 +
 docs/archive/DASHBOARD-FINAL-REPORT-2026-01-02.md  |   449 +
 docs/archive/DASHBOARD-FIX-2026-01-02.md           |   206 +
 docs/archive/DASHBOARD-FIX-REPORT-2025-12-31.md    |   374 +
 docs/archive/DASHBOARD-IMPLEMENTATION-COMPLETE.md  |   501 +
 docs/archive/DASHBOARD-INTEGRATION-COMPLETE.md     |   393 +
 docs/archive/DASHBOARD-INTEGRATION-SUMMARY.md      |   515 +
 .../DASHBOARD-METRICS-INTEGRATION-2026-01-06.md    |   706 +
 .../DASHBOARD-REALTIME-METRICS-2026-01-02.md       |   476 +
 docs/archive/DAY1-TOKEN-OPTIMIZATION-RESULTS.md    |   361 +
 docs/archive/DAY2-PROGRESS-SUMMARY.md              |   445 +
 .../DAY2-SECURE-CONTAINER-MANAGEMENT-COMPLETE.md   |   498 +
 docs/archive/DAY5-DEFAULT-PASSWORDS-ELIMINATED.md  |   593 +
 docs/archive/DAY5-INTEGRATION-TESTING-RESULTS.md   |   558 +
 .../DEPLOYMENT-FIXES-COMPLETE-2026-01-01.md        |   304 +
 docs/archive/DEPLOYMENT-SCRIPT-UPDATES-SUMMARY.md  |   458 +
 docs/archive/DEPLOYMENT-SESSION-REPORT.md          |   364 +
 docs/archive/DEPLOYMENT-STATUS-IN-PROGRESS.md      |   136 +
 docs/archive/DEPLOYMENT-STATUS-SUMMARY.md          |   481 +
 docs/archive/DEPLOYMENT-STATUS.md                  |   141 +
 docs/archive/DEPLOYMENT-SUCCESS-JAN2026.md         |   337 +
 docs/archive/DISCOVERY-QUICK-FIX.md                |   175 +
 docs/archive/DISCOVERY-REVIEW-SUMMARY.md           |   278 +
 docs/archive/DNS-FIX.md                            |   264 +
 docs/archive/DNS-RESOLUTION-FIX.md                 |   286 +
 docs/archive/EMBEDDINGS-FIX-COMPLETE-2026-01-05.md |   503 +
 .../EMBEDDINGS-INTEGRATION-COMPLETE-2026-01-05.md  |   395 +
 docs/archive/ERROR-ISSUE-LOG-2026-01-05.md         |   495 +
 .../archive/FAST-BUILD-OPTIMIZATIONS-2026-01-01.md |   381 +
 docs/archive/FEDERATION-IMPLEMENTATION-COMPLETE.md |   579 +
 ...FINAL-EMBEDDINGS-AND-IMPROVEMENTS-2026-01-05.md |   511 +
 docs/archive/FINAL-INTEGRATION-STATUS.md           |   393 +
 docs/archive/FINAL-STATUS-2026-01-05.md            |   266 +
 docs/archive/FINAL_IMPLEMENTATION_SUMMARY.md       |   257 +
 docs/archive/FIXES-APPLIED-SUMMARY.md              |   276 +
 docs/archive/FIXES-CONTAINER-HANGING-2026-01-02.md |   212 +
 docs/archive/FULL-STACK-DEPLOYMENT-IN-PROGRESS.md  |   553 +
 docs/archive/FUNCTIONAL-TEST-REPORT.md             |   287 +
 docs/archive/FUNCTIONAL-TEST-SUMMARY.md            |   174 +
 docs/archive/GRAFANA-MINDSDB-VERIFICATION.md       |   295 +
 docs/archive/HYBRID-COORDINATOR-FIX-2026-01-02.md  |   218 +
 docs/archive/IMMEDIATE-ACTION-PLAN-2026-01-05.md   |   325 +
 docs/archive/IMPLEMENTATION-COMPLETE-DEC-4-2025.md |   530 +
 docs/archive/IMPLEMENTATION-PROGRESS.md            |   481 +
 docs/archive/IMPLEMENTATION-SUMMARY-DEC-2025.md    |   416 +
 docs/archive/IMPLEMENTATION-SUMMARY.md             |   226 +
 .../archive/KNOWLEDGE-BASE-POPULATED-2026-01-05.md |   342 +
 ...LEGACY-DOCUMENT-RETENTION-SUMMARY-2026-03-05.md |   102 +
 docs/archive/MANGOHUD_FIX.md                       |   214 +
 docs/archive/MODULAR-AI-SYSTEM-SUMMARY.md          |   503 +
 docs/archive/ORCHESTRATOR-ANALYSIS.md              |   658 +
 docs/archive/ORCHESTRATOR-DEPLOYMENT-STATUS.md     |   455 +
 docs/archive/OVERLAY_MIGRATION.md                  |     8 +
 docs/archive/P1-IMPLEMENTATION-COMPLETE.md         |   592 +
 docs/archive/P2-DASHBOARD-INTEGRATION-COMPLETE.md  |   415 +
 docs/archive/PACKAGE-VERSION-REPORT-JAN2026.md     |   305 +
 docs/archive/PHASE-1-COMPLETE.md                   |   263 +
 docs/archive/PHASE-1-PROGRESS.md                   |   258 +
 docs/archive/PHASE-9-MODEL-SELECTION-FIX.md        |   307 +
 docs/archive/PODMAN-AI-STACK-START.md              |     9 +
 docs/archive/PODMAN-CONTAINERS-FIX.md              |   172 +
 docs/archive/PODMAN-SYSTEMD-FIX-2026-01-06.md      |   379 +
 docs/archive/POSTGRES-INITIALIZATION-2026-01-01.md |   391 +
 docs/archive/PRODUCTION-FIXES-APPLIED.md           |   420 +
 docs/archive/PRODUCTION-HARDENING-COMPLETE.md      |   359 +
 docs/archive/PRODUCTION-HARDENING-ROADMAP.md       |  1905 ++
 .../PRODUCTION-HARDENING-SESSION-2026-01-06.md     |   424 +
 .../PRODUCTION-HARDENING-SESSION-2026-01-07.md     |   220 +
 .../PRODUCTION-HARDENING-SESSION-2026-01-08.md     |   162 +
 .../PRODUCTION-HARDENING-SESSION-2026-01-09.md     |   178 +
 .../PRODUCTION-HARDENING-STATUS-2026-01-09.md      |   746 +
 docs/archive/PROGRESSIVE-DISCLOSURE-COMPLETE.md    |   261 +
 .../PROGRESSIVE-DISCLOSURE-IMPLEMENTATION.md       |   601 +
 docs/archive/PROJECT-STATUS-JAN23-2026.md          |   561 +
 docs/archive/PYTORCH-CPU-ONLY-FIX-RESEARCHED.md    |   223 +
 docs/archive/PYTORCH-DOWNLOAD-FIX-2025-12-31.md    |   242 +
 docs/archive/REPORTS-IN-DATABASE.md                |   437 +
 docs/archive/RLM-API-IMPLEMENTATION-2026-01-05.md  |   658 +
 docs/archive/RLM-FINAL-SUMMARY-2026-01-05.md       |   469 +
 .../RLM-IMPLEMENTATION-STATUS-2026-01-05.md        |   512 +
 docs/archive/ROOTLESS_PODMAN.md                    |     8 +
 docs/archive/SECRETS-ENCRYPTION-FIX.md             |   473 +
 docs/archive/SECRETS-ERRORS-FIXED.md               |   179 +
 docs/archive/SECURITY-FIXES-APPLIED.md             |   335 +
 docs/archive/SENIOR-DEV-CODE-REVIEW.md             |  1134 +
 docs/archive/SESSION-COMPLETE-2025-12-22.md        |   535 +
 docs/archive/SESSION-COMPLETE.md                   |   363 +
 docs/archive/SESSION-CONTINUATION-JAN24.md         |   418 +
 docs/archive/SESSION-PROGRESS-2026-01-10.md        |   617 +
 docs/archive/SESSION-SUMMARY-2025-12-21.md         |   523 +
 docs/archive/SESSION-SUMMARY-2026-01-09.md         |   312 +
 .../SESSION-SUMMARY-RLM-RAG-SETUP-2026-01-05.md    |   461 +
 docs/archive/SYSTEM-ANALYSIS-2026-01-05.md         |   904 +
 docs/archive/SYSTEM-ERRORS-FIXED-2025-12-31.md     |   225 +
 docs/archive/SYSTEM-HEALTH-REPORT-2025-12-31.md    |   234 +
 docs/archive/SYSTEM-IMPROVEMENTS-2025-12-21.md     |   487 +
 docs/archive/SYSTEM-RECOVERY-REPORT-2025-12-31.md  |   286 +
 docs/archive/SYSTEM-TEST-RESULTS.md                |   445 +
 docs/archive/TERMINAL-ERROR-LOG-2026-01-05.md      |   359 +
 docs/archive/TESTING-READINESS-STATUS.md           |   473 +
 docs/archive/TOKEN-OPTIMIZATION-ANALYSIS.md        |   531 +
 docs/archive/UNDEFINED-VARIABLES-FIX.md            |   183 +
 docs/archive/UPGRADE-SUMMARY-2025-12-31.md         |   310 +
 docs/archive/VALIDATION-REPORT-2026-01-09.md       |   430 +
 docs/archive/VIBE-CODING-COMPLETE.md               |   530 +
 .../VIBE-CODING-DEMONSTRATION-2025-12-31.md        |   535 +
 docs/archive/VIBE-CODING-IMPLEMENTATION-SUMMARY.md |   597 +
 docs/archive/VIBE-CODING-INTEGRATION-COMPLETE.md   |   403 +
 .../VSCODE-AI-INTEGRATION-PROGRESS-2025-12-31.md   |   494 +
 ...SCODE-AI-INTEGRATION-TEST-RESULTS-2025-12-31.md |   463 +
 docs/archive/WARNING-MESSAGES-FIXED-2026-01-01.md  |   178 +
 docs/archive/WEEK1-PROGRESS-SUMMARY.md             |   469 +
 docs/archive/deprecated/CODE_REVIEW.md             |   726 +
 docs/archive/deprecated/CODE_REVIEW_FINDINGS.md    |   253 +
 docs/archive/deprecated/DEPENDENCY_CHART.md        |   648 +
 docs/archive/deprecated/FIXES_AND_IMPROVEMENTS.md  |   576 +
 docs/archive/deprecated/IMPROVEMENT_SUGGESTIONS.md |   677 +
 .../deprecated/MODULAR_ARCHITECTURE_PROPOSAL.md    |  1039 +
 .../deprecated/README-ORPHANED-PROCESS-CLEANUP.md  |   271 +
 docs/archive/deprecated/SAFE_IMPROVEMENTS.md       |   634 +
 docs/archive/deprecated/WORKFLOW_CHART.md          |   676 +
 docs/archive/legacy-2025/11-CONTAINER-MGMT.md      |     6 +
 .../archive/legacy-2025/43-FEDERATED-DEPLOYMENT.md |   805 +
 .../legacy-2025/AGENT-AGNOSTIC-TOOLING-PLAN.md     |   658 +
 .../legacy-2025/AI-STACK-CONTAINER-SPINOFF.md      |   260 +
 .../legacy-2025/AI-STACK-RAG-IMPLEMENTATION.md     |   390 +
 ...STACK-WORKFLOW-CONSOLIDATION-PLAN-2025-12-22.md |    90 +
 .../legacy-2025/AUTO-START-IMPLEMENTATION.md       |   508 +
 .../legacy-2025/CONTAINER-VERSIONS-UPDATE.md       |    10 +
 .../legacy-2025/DASHBOARD-COLLECTORS-GUIDE.md      |   267 +
 .../legacy-2025/DASHBOARD-INTEGRATION-PLAN.md      |   417 +
 docs/archive/legacy-2025/DASHBOARD-READY.md        |   135 +
 .../legacy-2025/DASHBOARD-UPDATE-OPTIMIZATION.md   |   212 +
 docs/archive/legacy-2025/DASHBOARD-V2-UPGRADE.md   |   301 +
 .../legacy-2025/DEPLOYMENT-GUIDE-IMPROVEMENTS.md   |   430 +
 .../legacy-2025/DISCOVERY-PIPELINE-REVIEW.md       |   817 +
 .../legacy-2025/DISTRIBUTED-LEARNING-GUIDE.md      |   888 +
 docs/archive/legacy-2025/ENFORCE-LOCAL-AI-USAGE.md |   333 +
 .../archive/legacy-2025/ENGINEERING-ENVIRONMENT.md |   117 +
 .../legacy-2025/FEDERATED-DEPLOYMENT-GUIDE.md      |    47 +
 .../FINAL-PRODUCTION-HARDENING-SUMMARY.md          |   497 +
 docs/archive/legacy-2025/GITHUB-TOKEN-SETUP.md     |   290 +
 .../legacy-2025/HEALTH-CHECK-UPDATES-DEC-2025.md   |   376 +
 docs/archive/legacy-2025/P1-DEPLOYMENT-GUIDE.md    |   650 +
 .../legacy-2025/P1-P2-DEPLOYMENT-SUCCESS.md        |   382 +
 .../QUICK-START-LOCAL-AI-ENFORCEMENT.md            |   363 +
 .../SECURE-CONTAINER-MANAGEMENT-PLAN.md            |   448 +
 .../archive/legacy-2025/SECURITY-AUDIT-DEC-2025.md |   763 +
 .../archive/legacy-2025/SESSION-ACCOMPLISHMENTS.md |   327 +
 .../legacy-2025/SESSION-CONTINUATION-DEC-4-2025.md |   321 +
 .../SYSTEM-AUDIT-AND-IMPROVEMENTS-DEC-2025.md      |    10 +
 docs/archive/legacy-2025/SYSTEM-STATUS-SUMMARY.md  |   228 +
 .../archive/legacy-2025/SYSTEMATIC-IMPROVEMENTS.md |   586 +
 docs/archive/legacy-2025/TESTING_PLAN.md           |    69 +
 docs/archive/legacy-sequence/00-QUICK-START.md     |     1 +
 docs/archive/legacy-sequence/01-SYSTEM-OVERVIEW.md |     1 +
 .../legacy-sequence/02-AGENT-INTEGRATION.md        |     1 +
 .../03-PROGRESSIVE-DISCLOSURE-LEGACY.md            |   731 +
 .../legacy-sequence/03-PROGRESSIVE-DISCLOSURE.md   |     1 +
 .../legacy-sequence/04-AGENT-CONTEXT-PD-LEGACY.md  |   122 +
 .../legacy-sequence/04-CONTINUOUS-LEARNING.md      |     1 +
 docs/archive/legacy-sequence/05-API-REFERENCE.md   |     1 +
 docs/archive/legacy-sequence/06-TROUBLESHOOTING.md |     1 +
 .../legacy-sequence/07-DOCUMENTATION-INDEX.md      |     1 +
 docs/archive/legacy-sequence/08-SECURITY.md        |     1 +
 docs/archive/legacy-sequence/09-DEPLOYMENT.md      |     1 +
 docs/archive/legacy-sequence/10-OPERATIONS.md      |     1 +
 docs/archive/legacy-sequence/11-TOOLS.md           |     1 +
 docs/archive/legacy-sequence/12-SKILLS-MCP.md      |     1 +
 docs/archive/legacy-sequence/13-MCP-SERVERS.md     |     1 +
 docs/archive/legacy-sequence/14-PODMAN-ROOTLESS.md |     1 +
 docs/archive/legacy-sequence/15-ARCHITECTURE.md    |     1 +
 docs/archive/legacy-sequence/16-AGENT-START.md     |     1 +
 docs/archive/legacy-sequence/17-AGENT-REFERENCE.md |     1 +
 docs/archive/legacy-sequence/18-AGENT-SETUP.md     |     1 +
 .../19-PROGRESSIVE-DISCLOSURE-README.md            |     1 +
 docs/archive/legacy-sequence/20-SYSTEM-USAGE.md    |     1 +
 docs/archive/legacy-sequence/21-HYBRID-SYSTEM.md   |     1 +
 .../legacy-sequence/22-RAG-IMPLEMENTATION.md       |     1 +
 docs/archive/legacy-sequence/23-AI-STACK-GUIDE.md  |     1 +
 .../archive/legacy-sequence/24-MODEL-QUICKSTART.md |     1 +
 docs/archive/legacy-sequence/25-MODEL-MODULAR.md   |     1 +
 docs/archive/legacy-sequence/26-ENGINEERING-ENV.md |     1 +
 docs/archive/legacy-sequence/27-PODMAN-START.md    |     1 +
 docs/archive/legacy-sequence/28-PODMAN-ROOTLESS.md |     1 +
 docs/archive/legacy-sequence/29-DASHBOARD-GUIDE.md |     1 +
 .../archive/legacy-sequence/30-DASHBOARD-README.md |     1 +
 docs/archive/legacy-sequence/31-PACKAGE-GUIDE.md   |     1 +
 docs/archive/legacy-sequence/32-QUICK-REFERENCE.md |     1 +
 .../legacy-sequence/33-QUICK-REFERENCE-CARD.md     |     1 +
 docs/archive/legacy-sequence/34-RUN-FIRST.md       |     1 +
 .../archive/legacy-sequence/35-LOCAL-AI-STARTER.md |     1 +
 docs/archive/root-docs/AGENT_BOOTSTRAP_COMMAND.md  |   268 +
 .../archive/root-docs/AI-STACK-IMPROVEMENT-PLAN.md |  1595 ++
 docs/archive/root-docs/AI-STACK-QA-PLAN.md         |  1282 ++
 docs/archive/root-docs/AI-STACK-STATUS-REPORT.md   |   149 +
 docs/archive/root-docs/AIDB_SCHEMA_GUARANTEES.md   |   286 +
 .../root-docs/CONTINUE-EXTENSION-HANG-FIX.md       |   244 +
 docs/archive/root-docs/DEPLOY-OPTIMIZATIONS.md     |   196 +
 docs/archive/root-docs/DEPLOYMENT-FIXES-SUMMARY.md |   205 +
 docs/archive/root-docs/FIXES-EXECUTION-SUMMARY.md  |   148 +
 docs/archive/root-docs/HEALTH-CHECK-FIXES.md       |   196 +
 .../root-docs/KNOWN_ISSUES_TROUBLESHOOTING.md      |    32 +
 .../root-docs/LLAMA-CPP-OPTIMIZATION-CHANGES.md    |   196 +
 docs/archive/root-docs/MCP.md                      |    17 +
 docs/archive/root-docs/MCP_SERVICE_CONTRACTS.md    |   263 +
 docs/archive/root-docs/PROMETHEUS_SLO_RULES.md     |   375 +
 docs/archive/root-docs/REMOTE-AGENT-SETUP.md       |   171 +
 .../root-docs/SECURITY-INCIDENT-2026-03-02.md      |   297 +
 docs/archive/root-docs/SKILLS.md                   |    16 +
 docs/archive/root-docs/SYSTEM-RECOVERY-PLAN.md     |   239 +
 docs/archive/root-docs/TESTING-MANDATE.md          |   495 +
 .../stale/2026-03/AGENT-INTEGRATION-WORKFLOW.md    |   537 +
 .../stale/2026-03/AGENT-ONBOARDING-README.md       |    10 +
 docs/archive/stale/2026-03/BUILD_OPTIMIZATION.md   |   463 +
 .../CONTEXT-OPTIMIZATION-STRATEGIES-2026.md        |   803 +
 docs/archive/stale/2026-03/GLF_OS_REFERENCE.md     |    29 +
 docs/archive/stale/2026-03/MCP_SERVERS.md          |   748 +
 .../archive/stale/2026-03/OPTIONAL_ENHANCEMENTS.md |   202 +
 docs/archive/stale/2026-03/README.md               |    24 +
 docs/archive/stale/2026-03/RED-TEAM-MCP-SERVERS.md |   334 +
 docs/archive/stale/2026-03/VIRTUALIZATION-SETUP.md |   221 +
 .../2026-03/agent-guides/11-CONTAINER-MGMT.md      |   207 +
 .../stale/2026-03/agent-guides/21-RAG-CONTEXT.md   |   323 +
 .../2026-03/agent-guides/30-QDRANT-OPERATIONS.md   |   631 +
 .../stale/2026-03/agent-guides/32-ERROR-LOGGING.md |   486 +
 .../2026-03/agent-guides/40-HYBRID-WORKFLOW.md     |   560 +
 .../stale/2026-03/agent-guides/41-VALUE-SCORING.md |   528 +
 .../2026-03/agent-guides/42-PATTERN-EXTRACTION.md  |   580 +
 docs/archive/stale/2026-03/api/README.md           |    14 +
 .../development/IMPROVEMENT-PROPOSAL-TEMPLATE.md   |    44 +
 docs/archive/stale/2026-03/initial-passwords.md    |    41 +
 docs/archive/stubs/AI-SYSTEM-USAGE-GUIDE.md        |     6 +
 docs/archive/stubs/DASHBOARD-QUICKSTART.md         |     5 +
 docs/archive/stubs/ISSUE-TRACKING-GUIDE.md         |     5 +
 .../stubs/PROGRESSIVE-DISCLOSURE-IMPLEMENTATION.md |     5 +
 docs/archive/stubs/SYSTEM-DASHBOARD-GUIDE.md       |     6 +
 docs/archive/stubs/SYSTEM-DASHBOARD-README.md      |     6 +
 .../2025-12-22-ai-stack-release-updates.md         |    11 +
 .../AGENTIC-WORKFLOW-BOOTSTRAP-2026-03-05.md       |   190 +
 .../AI_STACK_RELIABILITY_IMPLEMENTATION.md         |   234 +
 docs/development/ARCHITECTURE_DIAGRAMS.md          |   110 +
 docs/development/BATCH-4.3-SUMMARY.md              |   436 +
 docs/development/CI_CD_INTEGRATION_PLAN.md         |    54 +
 docs/development/COMPLETION-ROADMAP.md             |   307 +
 docs/development/CONTINUOUS-LEARNING-DEEP-DIVE.md  |  1054 +
 docs/development/DASHBOARD_HEALTH_MONITORING.md    |   315 +
 .../DAY4-INTER-SERVICE-AUTH-PROGRESS.md            |   407 +
 docs/development/FINAL-SESSION-SUMMARY.md          |    32 +
 ...T-DECLARATIVE-MIGRATION-CHECKLIST-2026-02-24.md |   153 +
 .../HOSPITAL-CLASSIFIED-SECURITY-BASELINE.md       |    79 +
 docs/development/HOSPITAL-DEPLOYMENT-STATUS.md     |   333 +
 .../IDE-AGENT-STATE-STABILITY-PDR-2026-05-08.md    |   182 +
 .../IMPROVEMENT-DISCOVERY-REPORT-2025-12-22.md     |    11 +
 .../IMPROVEMENT-DISCOVERY-REPORT-2026-02-24.md     |   240 +
 .../IMPROVEMENT-DISCOVERY-REPORT-2026-03-13.md     |   238 +
 .../IMPROVEMENT-DISCOVERY-REPORT-2026-04-29.md     |   468 +
 .../IMPROVEMENT-DISCOVERY-REPORT-2026-06-06.md     |   355 +
 docs/development/IMPROVEMENT-PROPOSAL-TEMPLATE.md  |    10 +
 ...AL-AGENT-FEEDBACK-EXECUTION-LOOP-PRD-2026-05.md |   110 +
 ...AL-PERSPECTIVE-AND-CLI-EXECUTION-PRD-2026-05.md |   265 +
 docs/development/MISSION-COMPLETE-2026-01-09.md    |   496 +
 docs/development/NEXT-STEPS-RECOMMENDATIONS.md     |    20 +
 .../NIXOS-WRITABLE-STATE-REQUIREMENTS.md           |   100 +
 docs/development/ORCHESTRATION-VISUAL-SUMMARY.md   |    16 +
 docs/development/P1-INTEGRATION-COMPLETE.md        |   392 +
 docs/development/PHASE-11-DOCUMENTATION-SUMMARY.md |   443 +
 docs/development/PRODUCTION-HARDENING-STATUS.md    |   369 +
 docs/development/PYTHON-TOOLING-POLICY.md          |    52 +
 ...K-DEPLOY-MARKET-READINESS-ROADMAP-2026-01-09.md |    12 +
 .../ROADMAP_ANALYSIS_AND_IMPROVEMENTS.md           |   139 +
 docs/development/ROADMAP_ENHANCEMENT_COMPLETE.md   |    50 +
 docs/development/SECRETS-MANAGEMENT-GUIDE.md       |   226 +
 docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md |  2600 +++
 docs/development/SYSTEM-UPGRADE-ROADMAP.md         |  5827 +++++
 .../development/SYSTEM_UPGRADE_COMPLETE_SUMMARY.md |    17 +
 docs/development/VALIDATION-CHECKPOINT.md          |    15 +
 docs/development/VIM_YANK_IMPLEMENTATION.md        |    67 +
 docs/development/WORKFLOW-AUTOMATION-QUICK-REF.md  |   173 +
 docs/development/WORKFLOW-INTEGRATION.md           |   476 +
 docs/development/adk/adk-parity-scorecard.md       |   386 +
 .../adk/implementation-discovery-guide.md          |   631 +
 docs/development/agentic-workflow-automation.md    |   958 +
 .../ai-stack-advisor-ranked-fallbacks.md           |   288 +
 docs/development/ai-stack-advisor-strategy.md      |    58 +
 docs/development/cli-reference.md                  |   767 +
 docs/development/local-agent-recipes.md            |   662 +
 docs/development/local-agent-tool-reference.md     |   580 +
 docs/development/multi-agent-collaboration.md      |   706 +
 .../nixos-quick-deploy-analysis-2026-04-17.md      |   245 +
 docs/generated/HARNESS-SDK-API.md                  |   119 +
 .../HARNESS-FIRST-EVIDENCE-TEMPLATE.md             |    37 +
 docs/harness-first/HARNESS-FIRST-RUNBOOK.md        |    96 +
 docs/harness-first/evidence/.gitkeep               |     0
 .../2026-03-04-harness-first-owner-approval.md     |    42 +
 docs/initial-passwords.md                          |     6 +
 docs/memory-system/API-REFERENCE.md                |  1230 +
 docs/memory-system/INTEGRATION-EXAMPLES.md         |  1607 ++
 docs/memory-system/QUICK-REFERENCE.md              |   412 +
 docs/memory-system/USER-GUIDE.md                   |   626 +
 docs/operations/AI-AGENT-SURFACE-MATRIX.md         |   127 +
 docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md    |    93 +
 .../CLOSEOUT-READINESS-CHECKLIST-2026-03-05.md     |    45 +
 docs/operations/CONTEXT-LIMIT-HANDLING.md          |   377 +
 .../operations/DASHBOARD-ARCHITECTURE-REFERENCE.md |   109 +
 .../DASHBOARD_PERFORMANCE_OPTIMIZATION.md          |   773 +
 docs/operations/DEPLOYMENT-PERFORMANCE-TUNING.md   |   663 +
 docs/operations/EDITOR-STATE-RECOVERY-RUNBOOK.md   |   273 +
 .../NAMING-LABEL-CONSISTENCY-REPORT-2026-03-05.md  |   162 +
 docs/operations/NAMING-LABEL-CONVENTIONS.md        |    34 +
 docs/operations/OPERATOR-RUNBOOK.md                |   118 +
 docs/operations/QUICK-DEPLOY-REFERENCE-TREE.md     |    37 +
 docs/operations/REPO-CLEANUP-INVENTORY-PASS1.csv   |   121 +
 docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv   |   121 +
 docs/operations/REPO-CLEANUP-PASS1-PLAN.md         |    66 +
 docs/operations/REPO-STRUCTURE-POLICY.md           |    80 +
 docs/operations/SAFETY-GATE-GUIDE.md               |   165 +
 docs/operations/SKILL-DISTRIBUTION-MANIFEST.md     |   192 +
 docs/operations/STALE-ASSET-TRIM-REPORT.md         |    16 +
 docs/operations/ZERO-BOLT-ON-QUICK-REF.md          |   321 +
 .../agent-artifact-distribution-policy.md          |    69 +
 docs/operations/agent-artifact-gc-policy.md        |    71 +
 docs/operations/agent-capability-gap-loop.md       |   100 +
 docs/operations/agent-context-bootstrap.md         |   116 +
 .../agent-context-progressive-disclosure.md        |    13 +
 docs/operations/agent-feedback-loop.md             |    75 +
 docs/operations/agent-memory-state-standard.md     |   112 +
 docs/operations/agent-operational-perspective.md   |    51 +
 docs/operations/agent-ops-window.md                |    99 +
 .../ai-harness-routing-and-editor-surfaces.md      |   216 +
 docs/operations/ai-stack-runtime-diagnosis-loop.md |   414 +
 docs/operations/ai-stack-tooling-exposure.md       |   448 +
 docs/operations/ai-stack-vulkan-debug-loop.md      |   101 +
 docs/operations/antigravity-drain-verification.md  |    52 +
 docs/operations/aq-switchboard.md                  |   274 +
 .../autonomous-improvement-metric-sync.md          |    50 +
 docs/operations/battery-charge-thresholds.md       |   263 +
 docs/operations/beginner-operator-guide.md         |   142 +
 docs/operations/collab-workflow-exposure.md        |   235 +
 docs/operations/collaboration-guide.md             |   308 +
 docs/operations/command-center-graph-workspace.md  |    94 +
 .../dashboard-performance-implementation.md        |   514 +
 .../dashboard-performance-quick-reference.md       |   329 +
 .../deployment-monitoring-alerting-integration.md  |   600 +
 docs/operations/deprecated-script-audit.json       |   182 +
 docs/operations/deprecated-script-audit.md         |    48 +
 docs/operations/document-lifecycle-hygiene.md      |    96 +
 docs/operations/embedding-cache.md                 |   466 +
 docs/operations/herdr-agent-operations.md          |   131 +
 docs/operations/local-agent-operations-guide.md    |  1202 +
 docs/operations/openrouter-free-setup.md           |   176 +
 docs/operations/orchestration-visibility-guide.md  |   375 +
 docs/operations/performance-optimization.md        |   354 +
 docs/operations/procedures/AI-STACK-RUNBOOK.md     |   336 +
 .../procedures/AUTONOMOUS-SUDOERS-SETUP.md         |   150 +
 .../procedures/CONFIG-VALIDATION-PROCEDURES.md     |    41 +
 .../procedures/CREDENTIAL-MANAGEMENT-PROCEDURES.md |    35 +
 .../procedures/PERFORMANCE-TESTING-PROCEDURES.md   |    38 +
 .../procedures/PHASE3-VISUAL-CHECKLIST.md          |    38 +
 .../procedures/PORT-MANAGEMENT-PROCEDURES.md       |    31 +
 .../procedures/SECURITY-TESTING-PROCEDURES.md      |    31 +
 .../procedures/gemini-cli-state-repair.md          |    60 +
 docs/operations/production-deployment-guide.md     |   883 +
 .../query-agent-storage-learning-integration.md    |   554 +
 docs/operations/query-performance-tuning.md        |   500 +
 docs/operations/query-retrieval-optimization.md    |   514 +
 docs/operations/reasoning-profiles-checklist.md    |   275 +
 .../reasoning-profiles-implementation-summary.md   |   336 +
 docs/operations/reasoning-profiles-quickstart.md   |   327 +
 .../reasoning-profiles-reference-card.md           |   282 +
 docs/operations/reasoning-profiles.md              |   300 +
 .../reference/COSMIC-KEYBOARD-SHORTCUTS.md         |    98 +
 docs/operations/reference/QUICK-REFERENCE-CARD.md  |    91 +
 docs/operations/reference/QUICK-REFERENCE.md       |    96 +
 .../reference/SYSTEM-CAPABILITY-CATALOG.md         |   292 +
 .../reliability/AI-STACK-RUNTIME-RELIABILITY.md    |    93 +
 .../security-audit-compliance-integration.md       |   741 +
 docs/operations/signer-key-provisioning.md         |    78 +
 docs/operations/standards/LOGGING-STANDARDS.md     |    41 +
 docs/operations/troubleshooting-runbooks.md        |   150 +
 docs/operations/workflow-automation-guide.md       |   665 +
 docs/prsi/PRSI-HIGH-RISK-APPROVAL-RUBRIC.md        |    21 +
 docs/prsi/PRSI-OPERATIONS-RUNBOOK.md               |    47 +
 docs/prsi/PRSI-QUARANTINE-RUNBOOK.md               |    26 +
 .../AI-HARNESS-IMPLEMENTATION-ROADMAP-2026-03.md   |   735 +
 .../AI-HARNESS-NEXT-IMPROVEMENTS-2026-03.md        |   160 +
 docs/roadmap/REPO-LIBRARY.md                       |   197 +
 docs/runbooks/staged-rollout-and-rollback.md       |   185 +
 docs/security/AUDIT-2026-06-14-RATE-LIMITING.md    |    35 +
 docs/security/SECURITY-REMEDIATION-PROGRAM.md      |   359 +
 docs/security/security-hardening-guide.md          |   800 +
 docs/skill-dependency-lock.md                      |    47 +
 docs/sql/aidb-timeseries-schema.sql                |    40 +
 docs/testing/A2A-TCK-RUNBOOK.md                    |    44 +
 docs/testing/A2A-TCK-STATUS.md                     |    41 +
 docs/testing/memory-system-performance.md          |    65 +
 docs/user-guides/execution-history-browser.md      |   309 +
 docs/user-guides/keyboard-shortcuts.md             |   346 +
 docs/user-guides/quick-start.md                    |   290 +
 docs/workflows/BEST-PRACTICES.md                   |   546 +
 docs/workflows/TEMPLATE-CATALOG.md                 |   668 +
 docs/workflows/USER-GUIDE.md                       |   601 +
 flake.lock                                         |   431 +
 flake.nix                                          |   741 +
 lib/cross-cutting/colors.sh                        |   107 +
 lib/cross-cutting/common.sh                        |     5 +
 lib/cross-cutting/config.sh                        |     5 +
 lib/cross-cutting/error-codes.sh                   |   103 +
 lib/cross-cutting/error-handling.sh                |   378 +
 lib/cross-cutting/harness.sh                       |     0
 lib/cross-cutting/retry-backoff.sh                 |    84 +
 lib/cross-cutting/retry.sh                         |   208 +
 lib/cross-cutting/security/README.md               |   212 +
 lib/cross-cutting/security/audit-logger.py         |   708 +
 lib/cross-cutting/security/compliance-checker.sh   |   999 +
 lib/cross-cutting/security/scanner.sh              |  1057 +
 .../security/security-workflow-validator.sh        |   724 +
 lib/cross-cutting/timeout.sh                       |     5 +
 lib/l1-infra/deploy/alert-config.sh                |   461 +
 lib/l1-infra/deploy/auto-enable-features.sh        |   351 +
 lib/l1-infra/deploy/auto-remediation.sh            |   547 +
 lib/l1-infra/deploy/background-tasks.sh            |   319 +
 lib/l1-infra/deploy/commands/ai-stack.sh           |   443 +
 lib/l1-infra/deploy/commands/config.sh             |   479 +
 lib/l1-infra/deploy/commands/dashboard.sh          |   488 +
 lib/l1-infra/deploy/commands/health.sh             |   475 +
 lib/l1-infra/deploy/commands/recover.sh            |   534 +
 lib/l1-infra/deploy/commands/search.sh             |   337 +
 lib/l1-infra/deploy/commands/security.sh           |   621 +
 lib/l1-infra/deploy/commands/test.sh               |   539 +
 lib/l1-infra/deploy/commands/upstream.sh           |   220 +
 lib/l1-infra/deploy/core.sh                        |   400 +
 lib/l1-infra/deploy/dashboard-notify.sh            |   214 +
 lib/l1-infra/deploy/deployment-hooks.sh            |   585 +
 lib/l1-infra/deploy/monitoring-integration.sh      |   405 +
 lib/l1-infra/deploy/nix-caching.sh                 |   304 +
 lib/l1-infra/deploy/optimize-model-downloads.sh    |   370 +
 lib/l1-infra/deploy/parallel-health-checks.sh      |   288 +
 lib/l1-infra/deploy/parallel-service-start.sh      |   354 +
 lib/l1-infra/deploy/profiling.sh                   |   204 +
 lib/l1-infra/dry-run.sh                            |   287 +
 lib/l1-infra/gpu-detection.sh                      |   259 +
 lib/l1-infra/hardware-detect.sh                    |     5 +
 lib/l1-infra/home-manager.sh                       |   166 +
 lib/l1-infra/nixos.sh                              |   711 +
 lib/l1-infra/packages.sh                           |   572 +
 lib/l1-infra/secrets-sops.sh                       |   322 +
 lib/l1-infra/secrets.sh                            |   518 +
 lib/l2-runtime/ai-stack-containers.sh              |     5 +
 lib/l2-runtime/flatpak.sh                          |   111 +
 lib/l2-runtime/python.sh                           |   173 +
 lib/l2-runtime/tools.sh                            |    38 +
 lib/l3-conn/service-conflict-resolution.sh         |     5 +
 lib/l3-conn/service-registry.sh                    |   231 +
 lib/l4-coord/adk/declarative-wiring-spec.nix       |   445 +
 lib/l4-coord/adk/implementation-discovery.sh       |   756 +
 lib/l4-coord/adk/parity-tracker.py                 |   604 +
 lib/l4-coord/adk/wiring-validator.sh               |   489 +
 lib/l4-coord/agents/__init__.py                    |   182 +
 .../agents/agent_communication_protocol.py         |   565 +
 lib/l4-coord/agents/collaboration_patterns.py      |   588 +
 lib/l4-coord/agents/collaborative_planning.py      |   637 +
 lib/l4-coord/agents/dynamic_team_formation.py      |   661 +
 lib/l4-coord/agents/improvement-tracker.sh         |   331 +
 lib/l4-coord/agents/interaction-storage.py         |   419 +
 lib/l4-coord/agents/learning-loop.py               |   462 +
 lib/l4-coord/agents/pattern-extractor.py           |   485 +
 lib/l4-coord/agents/quality_consensus.py           |   668 +
 lib/l4-coord/agents/query-router.sh                |   413 +
 lib/l4-coord/agents/team_performance_metrics.py    |   549 +
 lib/l4-coord/ai-optimizer.sh                       |     5 +
 lib/l4-coord/workflows/__init__.py                 |   146 +
 lib/l4-coord/workflows/success_predictor.py        |   556 +
 lib/l4-coord/workflows/template_manager.py         |   652 +
 .../workflows/tests/test_workflow_store_logs.py    |   215 +
 lib/l4-coord/workflows/workflow_adapter.py         |   654 +
 lib/l4-coord/workflows/workflow_executor.py        |   670 +
 lib/l4-coord/workflows/workflow_generator.py       |   617 +
 lib/l4-coord/workflows/workflow_optimizer.py       |   692 +
 lib/l4-coord/workflows/workflow_store.py           |   740 +
 lib/l5-state/backup.sh                             |   679 +
 lib/l5-state/state-management.sh                   |   783 +
 lib/l6-cog/ai-optimizer-hooks.sh                   |     5 +
 lib/l6-cog/search/__init__.py                      |    23 +
 lib/l6-cog/search/embedding_optimizer.py           |   203 +
 lib/l6-cog/search/lazy_loader.py                   |   112 +
 lib/l6-cog/search/query_batcher.py                 |   481 +
 lib/l6-cog/search/query_cache.py                   |   551 +
 lib/l6-cog/search/query_profiler.py                |   197 +
 lib/l6-cog/search/vector_search_optimizer.py       |   519 +
 lib/l7-interaction/dashboard.sh                    |    17 +
 lib/l7-interaction/finalization.sh                 |     5 +
 lib/l7-interaction/logging-structured.sh           |    67 +
 lib/l7-interaction/logging.sh                      |   406 +
 lib/l7-interaction/main-refactoring-demo.sh        |   243 +
 lib/l7-interaction/progress.sh                     |   193 +
 lib/l7-interaction/reporting.sh                    |     5 +
 lib/l7-interaction/user-interaction.sh             |   442 +
 lib/l7-interaction/user.sh                         |   677 +
 lib/l7-interaction/validation-input.sh             |   376 +
 lib/l7-interaction/validation.sh                   |     5 +
 nix/data/flatpak-profiles.nix                      |    66 +
 nix/data/profile-system-packages.nix               |   104 +
 nix/home/base.nix                                  |  2106 ++
 nix/home/deploy-common.nix                         |    10 +
 nix/home/herdr.nix                                 |    65 +
 nix/hosts/_example/default.nix.sample              |    72 +
 nix/hosts/_example/facts.nix.sample                |    54 +
 nix/hosts/_example/home.nix.sample                 |    45 +
 nix/hosts/hyperd/default.nix                       |    39 +
 nix/hosts/hyperd/deploy-options.nix                |    34 +
 nix/hosts/hyperd/facts.nix                         |   110 +
 nix/hosts/hyperd/hardware-configuration.nix        |    42 +
 nix/hosts/hyperd/home-deploy-options.nix           |    12 +
 nix/hosts/hyperd/home.nix                          |    19 +
 nix/hosts/nixos/default.nix                        |    17 +
 nix/hosts/nixos/deploy-options.nix                 |    19 +
 nix/hosts/nixos/hardware-configuration.nix         |    46 +
 nix/hosts/nixos/home-deploy-options.nix            |     3 +
 nix/hosts/nixos/home.nix                           |    87 +
 nix/hosts/sbc-minimal/default.nix                  |    24 +
 nix/hosts/sbc-minimal/hardware-configuration.nix   |    12 +
 nix/lib/ai-stack-hardware.nix                      |   355 +
 nix/lib/hardened-service.nix                       |    87 +
 nix/lib/hardware-tier.nix                          |    70 +
 nix/lib/kernel-patches.nix                         |   215 +
 nix/lib/overlays/llama-cpp-aarch64.nix             |    35 +
 nix/lib/overlays/llama-cpp-latest.nix              |   160 +
 nix/lib/overlays/opencode.nix                      |    17 +
 nix/lib/overlays/osint-tools.nix                   |    10 +
 nix/modules/core/base.nix                          |   526 +
 nix/modules/core/custom-kernel.nix                 |   451 +
 nix/modules/core/disk-health-monitor.nix           |   113 +
 nix/modules/core/fs-integrity-monitor.nix          |    88 +
 nix/modules/core/guardrail-alerts.nix              |    61 +
 nix/modules/core/hospital-classified.nix           |    53 +
 nix/modules/core/localhost-isolation.nix           |    49 +
 nix/modules/core/logging.nix                       |   241 +
 nix/modules/core/network.nix                       |   104 +
 nix/modules/core/options.nix                       |  3531 +++
 nix/modules/core/secrets.nix                       |   187 +
 nix/modules/core/users.nix                         |    93 +
 nix/modules/disk/default.nix                       |    19 +
 nix/modules/disk/gpt-efi-btrfs.nix                 |    48 +
 nix/modules/disk/gpt-efi-ext4.nix                  |    38 +
 nix/modules/disk/gpt-luks-ext4.nix                 |    45 +
 nix/modules/hardware/cpu/amd.nix                   |    59 +
 nix/modules/hardware/cpu/apple-silicon.nix         |    95 +
 nix/modules/hardware/cpu/arm.nix                   |    62 +
 nix/modules/hardware/cpu/intel.nix                 |    24 +
 nix/modules/hardware/cpu/qualcomm.nix              |    69 +
 nix/modules/hardware/cpu/riscv64.nix               |    79 +
 nix/modules/hardware/default.nix                   |    67 +
 nix/modules/hardware/gpu/adreno.nix                |    80 +
 nix/modules/hardware/gpu/amd.nix                   |    93 +
 nix/modules/hardware/gpu/apple.nix                 |   101 +
 nix/modules/hardware/gpu/intel-arc.nix             |   113 +
 nix/modules/hardware/gpu/intel.nix                 |    40 +
 nix/modules/hardware/gpu/mali.nix                  |    82 +
 nix/modules/hardware/gpu/nvidia.nix                |    48 +
 nix/modules/hardware/mobile.nix                    |   141 +
 nix/modules/hardware/network.nix                   |    24 +
 nix/modules/hardware/ram-tuning.nix                |    66 +
 nix/modules/hardware/recovery.nix                  |    20 +
 nix/modules/hardware/storage.nix                   |    68 +
 nix/modules/hardware/zram.nix                      |    22 +
 .../host-classes/p14s-amd-ai-workstation.nix       |   169 +
 nix/modules/profiles/ai-dev.nix                    |   169 +
 nix/modules/profiles/gaming.nix                    |    19 +
 nix/modules/profiles/minimal.nix                   |    17 +
 nix/modules/roles/ai-stack.nix                     |  2490 +++
 nix/modules/roles/antigravity.nix                  |    52 +
 nix/modules/roles/cpp-dev.nix                      |   208 +
 nix/modules/roles/default.nix                      |    11 +
 nix/modules/roles/desktop.nix                      |   310 +
 nix/modules/roles/gaming.nix                       |    60 +
 nix/modules/roles/kernel-dev.nix                   |   280 +
 nix/modules/roles/server.nix                       |    71 +
 nix/modules/roles/virtualization.nix               |    80 +
 nix/modules/secureboot.nix                         |    15 +
 nix/modules/services/affective-engine.nix          |    36 +
 nix/modules/services/agent-mesh.nix                |    36 +
 nix/modules/services/agent-reap.nix                |   117 +
 nix/modules/services/ai-stack.nix                  |     6 +
 nix/modules/services/antigravity-auto-wake.nix     |   149 +
 nix/modules/services/autonomous-improvement.nix    |   224 +
 .../services/c2-scheduler-context-issuer.nix       |   178 +
 nix/modules/services/capability-registry.nix       |    45 +
 nix/modules/services/command-center-dashboard.nix  |   266 +
 nix/modules/services/crowdsec.nix                  |   205 +
 nix/modules/services/data-retention.nix            |   208 +
 nix/modules/services/default.nix                   |    29 +
 nix/modules/services/execution-cell-runner.nix     |   334 +
 nix/modules/services/headroom-proxy.nix            |   107 +
 nix/modules/services/identity-kernel.nix           |    68 +
 nix/modules/services/ingress.nix                   |   106 +
 nix/modules/services/lease-signing-authority.nix   |   132 +
 nix/modules/services/llama-router.nix              |   149 +
 nix/modules/services/lore-sync.nix                 |   207 +
 nix/modules/services/mcp-servers.nix               |  2852 +++
 nix/modules/services/meta-optimization.nix         |   274 +
 nix/modules/services/monitoring.nix                |   862 +
 nix/modules/services/nvd-sync.nix                  |   135 +
 .../services/revocation-epoch-authority.nix        |   175 +
 nix/modules/services/switchboard.nix               |   587 +
 nix/modules/services/workflow-deviation-broker.nix |    74 +
 nix/modules/services/world-model.nix               |    34 +
 .../llama-cpp/allow-vulkan-igpu-offload.patch      |   152 +
 nix/pins/llama-cpp.json                            |    24 +
 nix/pkgs/agentic-tools.nix                         |    35 +
 nix/pkgs/by-name/models-dev/package.nix            |   117 +
 nix/pkgs/by-name/opencode/package.nix              |   196 +
 nix/pkgs/continue-cli.nix                          |    46 +
 nix/pkgs/herdr.nix                                 |    27 +
 nix/pkgs/lean-ctx.nix                              |    54 +
 nix/pkgs/maigret.nix                               |    94 +
 nix/pkgs/mosaic.nix                                |    44 +
 nix/pkgs/pi-agent.nix                              |    42 +
 nix/pkgs/rtk.nix                                   |    55 +
 nixos-quick-deploy.sh                              |  4755 ++++
 phases/phase-01-system-initialization.sh           |     6 +
 phases/phase-02-system-backup.sh                   |   246 +
 phases/phase-03-configuration-generation.sh        |     6 +
 phases/phase-04-pre-deployment-validation.sh       |   238 +
 phases/phase-05-declarative-deployment.sh          |     6 +
 phases/phase-06-additional-tooling.sh              |   398 +
 phases/phase-07-post-deployment-validation.sh      |     6 +
 phases/phase-08-finalization-and-report.sh         |     6 +
 phases/phase-09-ai-model-deployment.sh             |     6 +
 phases/phase-09-ai-optimizer-prep.sh               |     6 +
 phases/phase-09-ai-stack-deployment.sh             |     6 +
 pyrightconfig.json                                 |    59 +
 pytest.ini                                         |     7 +
 scripts/agent-tools/README.md                      |    69 +
 scripts/agent-tools/acat                           |    78 +
 scripts/agent-tools/adiff                          |    77 +
 scripts/agent-tools/aenv                           |    53 +
 scripts/agent-tools/agrep                          |   171 +
 scripts/agent-tools/ahist                          |    45 +
 scripts/agent-tools/alog                           |    84 +
 scripts/agent-tools/als                            |   131 +
 scripts/agent-tools/aproc                          |    71 +
 scripts/agent-tools/asum                           |   105 +
 scripts/agent-tools/atest                          |    76 +
 scripts/agent-tools/install.sh                     |    21 +
 scripts/agent-tools/test-tools.sh                  |    37 +
 scripts/ai/_aq-qa-bash                             |  3248 +++
 scripts/ai/acat                                    |    20 +
 scripts/ai/adk-discovery-workflow.sh               |   314 +
 scripts/ai/agrep                                   |     3 +
 scripts/ai/ai-commit-simple                        |   159 +
 scripts/ai/ai-env-summary.sh                       |    45 +
 scripts/ai/ai-metrics-auto-updater.sh              |    50 +
 scripts/ai/ai-model-manager.sh                     |    71 +
 scripts/ai/ai-model-setup.sh                       |    53 +
 scripts/ai/ai-stack-e2e-test.sh                    |    49 +
 scripts/ai/ai-stack-feature-scenario.sh            |    70 +
 scripts/ai/ai-stack-health.sh                      |    68 +
 scripts/ai/ai-stack-resume-recovery.sh             |    65 +
 scripts/ai/ai-stack-troubleshoot.sh                |    39 +
 scripts/ai/ai-validate-and-commit                  |   205 +
 scripts/ai/als                                     |     3 +
 scripts/ai/aq                                      |   334 +
 scripts/ai/aq-a2a-audit                            |   188 +
 scripts/ai/aq-adopt-workflow                       |   144 +
 scripts/ai/aq-agent-loop                           |   587 +
 scripts/ai/aq-agent-reap                           |   270 +
 scripts/ai/aq-agent-send                           |    40 +
 scripts/ai/aq-alerts                               |   127 +
 scripts/ai/aq-antigravity-agent                    |   173 +
 scripts/ai/aq-antigravity-inbox                    |   402 +
 scripts/ai/aq-approve                              |   195 +
 scripts/ai/aq-approve-headless                     |   563 +
 scripts/ai/aq-architect                            |    13 +
 scripts/ai/aq-auto-remediate.py                    |   585 +
 scripts/ai/aq-autonomous-improve                   |   194 +
 scripts/ai/aq-autoresearch                         |   177 +
 scripts/ai/aq-bitnet-benchmark.py                  |   370 +
 scripts/ai/aq-bitnet-compare.py                    |   147 +
 scripts/ai/aq-bitnet-feasibility.py                |   296 +
 scripts/ai/aq-cache-prewarm                        |    51 +
 scripts/ai/aq-cache-warm                           |   342 +
 scripts/ai/aq-capability-catalog                   |   211 +
 scripts/ai/aq-capability-catalog-append            |    88 +
 scripts/ai/aq-capability-flush                     |   298 +
 scripts/ai/aq-capability-gap                       |   698 +
 scripts/ai/aq-capability-intake                    |   408 +
 scripts/ai/aq-capability-patch-apply               |   109 +
 scripts/ai/aq-capability-patch-prep                |    88 +
 scripts/ai/aq-capability-plan                      |   184 +
 scripts/ai/aq-capability-promote                   |   116 +
 scripts/ai/aq-capability-remediate                 |   162 +
 scripts/ai/aq-capability-shadow                    |   254 +
 scripts/ai/aq-capability-stub                      |   154 +
 scripts/ai/aq-cascade                              |   119 +
 scripts/ai/aq-chat                                 |  1626 ++
 scripts/ai/aq-coder                                |    18 +
 scripts/ai/aq-collab-round                         |   729 +
 scripts/ai/aq-collaborate                          |   521 +
 scripts/ai/aq-collective                           |    75 +
 scripts/ai/aq-commit-agent                         |    17 +
 scripts/ai/aq-commit-facts                         |   102 +
 scripts/ai/aq-completions.sh                       |   146 +
 scripts/ai/aq-context-bootstrap                    |   463 +
 scripts/ai/aq-context-card                         |   342 +
 scripts/ai/aq-context-manage                       |   613 +
 scripts/ai/aq-context-sandbox                      |    91 +
 scripts/ai/aq-context-warm                         |    53 +
 scripts/ai/aq-correct-failures                     |   228 +
 scripts/ai/aq-crystallize                          |    52 +
 scripts/ai/aq-defer                                |    51 +
 scripts/ai/aq-delegate                             |   348 +
 scripts/ai/aq-delegation-registry                  |   229 +
 scripts/ai/aq-drop                                 |   103 +
 scripts/ai/aq-drop-daemon                          |   249 +
 scripts/ai/aq-editor-rescue                        |   419 +
 scripts/ai/aq-editor-trim-sessions                 |   181 +
 scripts/ai/aq-enrich-plans                         |   173 +
 scripts/ai/aq-epoch-bump                           |   277 +
 scripts/ai/aq-eval                                 |   294 +
 scripts/ai/aq-event                                |   161 +
 scripts/ai/aq-factory                              |    30 +
 scripts/ai/aq-federated-learning                   |   375 +
 scripts/ai/aq-feedback-loop                        |   296 +
 scripts/ai/aq-flat-prd-gate                        |   171 +
 scripts/ai/aq-gap-auto-remediate                   |   275 +
 scripts/ai/aq-gap-import                           |   105 +
 scripts/ai/aq-gaps                                 |   118 +
 scripts/ai/aq-git-status-agent                     |     9 +
 scripts/ai/aq-health-spider                        |  1289 ++
 scripts/ai/aq-herdr                                |   107 +
 scripts/ai/aq-hints                                |   566 +
 scripts/ai/aq-index                                |   395 +
 scripts/ai/aq-index-knowledge-graph                |   324 +
 scripts/ai/aq-index-logic-patterns                 |   275 +
 scripts/ai/aq-inference-bench                      |   381 +
 scripts/ai/aq-insights                             |   318 +
 scripts/ai/aq-integrity-scan                       |   515 +
 scripts/ai/aq-introspection-validate               |   149 +
 scripts/ai/aq-knowledge-import.sh                  |   125 +
 scripts/ai/aq-lane-eligibility                     |   348 +
 scripts/ai/aq-lease                                |   175 +
 scripts/ai/aq-lesson-promote                       |    94 +
 scripts/ai/aq-llama-benchmark-observe.py           |   220 +
 scripts/ai/aq-llama-benchmark.py                   |   586 +
 scripts/ai/aq-llama-debug                          |     7 +
 scripts/ai/aq-llama-staging-status.py              |   164 +
 scripts/ai/aq-llm-monitor                          |   396 +
 scripts/ai/aq-local-dogfood-run                    |   337 +
 scripts/ai/aq-local-review                         |   410 +
 scripts/ai/aq-local-surface-scan                   |   130 +
 scripts/ai/aq-local-training-loop                  |  1249 ++
 scripts/ai/aq-loop                                 |   735 +
 scripts/ai/aq-loop-queue                           |   128 +
 scripts/ai/aq-memory                               |   511 +
 scripts/ai/aq-memory-recall-benchmark              |   115 +
 scripts/ai/aq-meta-optimize                        |   278 +
 scripts/ai/aq-mine                                 |   345 +
 scripts/ai/aq-model                                |   238 +
 scripts/ai/aq-model-eval                           |    99 +
 scripts/ai/aq-model-switch                         |   386 +
 scripts/ai/aq-operational-perspective              |   307 +
 scripts/ai/aq-optimizer                            |   423 +
 scripts/ai/aq-patterns                             |   282 +
 scripts/ai/aq-plans-index                          |   525 +
 scripts/ai/aq-pm-tracker                           |   361 +
 scripts/ai/aq-prime                                |   610 +
 scripts/ai/aq-prompt-eval                          |   691 +
 scripts/ai/aq-propose                              |   121 +
 scripts/ai/aq-provision-signer-key                 |   261 +
 scripts/ai/aq-prsi-review                          |   251 +
 scripts/ai/aq-push-intelligence                    |    47 +
 scripts/ai/aq-qa                                   |    62 +
 scripts/ai/aq-qa-agent                             |    13 +
 scripts/ai/aq-quickstart                           |   189 +
 scripts/ai/aq-rag-prewarm                          |   243 +
 scripts/ai/aq-ralph-task                           |    62 +
 scripts/ai/aq-rate                                 |    82 +
 scripts/ai/aq-refactor-status                      |   145 +
 scripts/ai/aq-refine                               |   176 +
 scripts/ai/aq-reject                               |    47 +
 scripts/ai/aq-report                               |  8739 ++++++++
 scripts/ai/aq-report-agent                         |    22 +
 scripts/ai/aq-resume                               |   102 +
 scripts/ai/aq-review                               |   185 +
 scripts/ai/aq-review-repairs                       |   189 +
 scripts/ai/aq-role-route                           |   449 +
 scripts/ai/aq-runtime                              |    55 +
 scripts/ai/aq-runtime-act                          |   209 +
 scripts/ai/aq-runtime-diagnose                     |   402 +
 scripts/ai/aq-runtime-plan                         |   660 +
 scripts/ai/aq-runtime-remediate                    |   350 +
 scripts/ai/aq-screenshot                           |   144 +
 scripts/ai/aq-sequential-edit                      |   140 +
 scripts/ai/aq-session-start                        |   341 +
 scripts/ai/aq-session-zero                         |   147 +
 scripts/ai/aq-setup                                |   244 +
 scripts/ai/aq-skill-auto                           |   222 +
 scripts/ai/aq-skill-factory                        |   199 +
 scripts/ai/aq-skill-suggest                        |   260 +
 scripts/ai/aq-slice-claim                          |   490 +
 scripts/ai/aq-slice-helper                         |   292 +
 scripts/ai/aq-sync-shared-skills.py                |   350 +
 scripts/ai/aq-system-act                           |   242 +
 scripts/ai/aq-system-state                         |   734 +
 scripts/ai/aq-tempest                              |   289 +
 scripts/ai/aq-throttler                            |    80 +
 scripts/ai/aq-top                                  |   194 +
 scripts/ai/aq-trading                              |   207 +
 scripts/ai/aq-tui-dashboard                        |  1115 +
 scripts/ai/aq-understand-anything                  |   265 +
 scripts/ai/aq-verify-committed                     |    76 +
 scripts/ai/aq-wiki                                 |   718 +
 scripts/ai/aq-workflow                             |   358 +
 scripts/ai/aq-workflow-deviation                   |    44 +
 scripts/ai/aqd                                     |  1968 ++
 scripts/ai/asum                                    |     6 +
 scripts/ai/autonomous-coordinator-local.sh         |   300 +
 scripts/ai/autonomous-coordinator-simple.sh        |   254 +
 scripts/ai/autonomous-coordinator.sh               |   207 +
 scripts/ai/backfill-interaction-history-qdrant.py  |   197 +
 scripts/ai/bash-completion.sh                      |   227 +
 scripts/ai/claude-api-proxy.py                     |   441 +
 scripts/ai/claude-local-wrapper.py                 |   183 +
 scripts/ai/cli-enhanced.sh                         |   309 +
 scripts/ai/cli-utils.py                            |   315 +
 scripts/ai/complete-via-ralph.sh                   |   164 +
 scripts/ai/delegate-fanout                         |   243 +
 scripts/ai/delegate-to-antigravity                 |   715 +
 scripts/ai/delegate-to-claude                      |   420 +
 scripts/ai/delegate-to-codex                       |   531 +
 scripts/ai/delegate-to-gemini                      |   599 +
 scripts/ai/delegate-to-local                       |   312 +
 scripts/ai/edgeai                                  |   371 +
 scripts/ai/export-container-config                 |   478 +
 scripts/ai/gen-api-client.py                       |   138 +
 scripts/ai/generate-module-dashboard.py            |   902 +
 scripts/ai/harness-rpc.js                          |   891 +
 scripts/ai/ingest-impeccable-references.sh         |   146 +
 scripts/ai/ingest-trading-knowledge.sh             |   137 +
 scripts/ai/lib/__init__.py                         |     0
 scripts/ai/lib/a2a_guard.py                        |   116 +
 scripts/ai/lib/agent_action_policy.py              |   124 +
 scripts/ai/lib/agent_dispatch_budget.py            |   152 +
 scripts/ai/lib/agent_dispatch_contract.py          |   188 +
 scripts/ai/lib/agent_ops_projection.py             |   859 +
 scripts/ai/lib/agent_run_events.py                 |   378 +
 scripts/ai/lib/approval_executor.py                |   195 +
 scripts/ai/lib/approval_recovery.py                |   650 +
 scripts/ai/lib/approval_request.py                 |   720 +
 scripts/ai/lib/approval_runbook_engine.py          |   646 +
 scripts/ai/lib/approval_signer.py                  |   742 +
 scripts/ai/lib/aq-shim.sh                          |    30 +
 scripts/ai/lib/aq_dashboard_client.py              |  1299 ++
 scripts/ai/lib/attention_queue.py                  |   420 +
 scripts/ai/lib/audit-post.sh                       |    76 +
 scripts/ai/lib/audit-write.sh                      |    95 +
 scripts/ai/lib/auto_assign.py                      |   175 +
 scripts/ai/lib/backpressure.py                     |    46 +
 scripts/ai/lib/capability_lease.py                 |   605 +
 scripts/ai/lib/capability_lease_issuance.py        |   223 +
 scripts/ai/lib/cascade.py                          |   255 +
 scripts/ai/lib/chat_intent.py                      |   206 +
 scripts/ai/lib/config_loader.py                    |   197 +
 scripts/ai/lib/context-merger.py                   |    63 +
 scripts/ai/lib/context_merger.py                   |     1 +
 scripts/ai/lib/context_risk.py                     |   136 +
 scripts/ai/lib/dispatch.py                         |  1728 ++
 scripts/ai/lib/dispatch_consult.py                 |   454 +
 scripts/ai/lib/drop_spec.py                        |   128 +
 scripts/ai/lib/durable_reservation.py              |   164 +
 scripts/ai/lib/eval_integrity.py                   |   201 +
 scripts/ai/lib/event_log.py                        |   161 +
 scripts/ai/lib/execution_cell_clone.py             |   856 +
 scripts/ai/lib/execution_grant.py                  |   782 +
 scripts/ai/lib/grammar_cache.py                    |   192 +
 scripts/ai/lib/harness-grounding.sh                |    31 +
 scripts/ai/lib/harness_runner.py                   |    27 +
 scripts/ai/lib/herdr_presentation_projection.py    |   342 +
 scripts/ai/lib/hw_probe.py                         |   348 +
 scripts/ai/lib/lease_signing_authority.py          |   322 +
 scripts/ai/lib/local_delegation_reliability.py     |   598 +
 scripts/ai/lib/local_inference_context.py          |   254 +
 scripts/ai/lib/local_inference_contract.py         |   440 +
 scripts/ai/lib/local_inference_policy.py           |   396 +
 scripts/ai/lib/local_inference_provenance.py       |   253 +
 scripts/ai/lib/local_inference_transport.py        |  1712 ++
 scripts/ai/lib/model-client.py                     |    78 +
 scripts/ai/lib/model_budget.py                     |   146 +
 scripts/ai/lib/model_tier.py                       |    94 +
 scripts/ai/lib/model_tiering.py                    |    44 +
 scripts/ai/lib/operator_context_projection.py      |   257 +
 scripts/ai/lib/pending-update                      |   152 +
 scripts/ai/lib/qa_evidence_store.py                |   372 +
 scripts/ai/lib/quality_check.py                    |   211 +
 scripts/ai/lib/refactor_status.py                  |   323 +
 scripts/ai/lib/resume_projector.py                 |   145 +
 scripts/ai/lib/review_feedback_contract.py         |   528 +
 scripts/ai/lib/revocation_epoch.py                 |   692 +
 scripts/ai/lib/revocation_epoch_transport.py       |   309 +
 scripts/ai/lib/round_aggregate.py                  |   405 +
 scripts/ai/lib/round_contribution.py               |   416 +
 scripts/ai/lib/round_state.py                      |   374 +
 scripts/ai/lib/scheduler.py                        |   163 +
 scripts/ai/lib/scheduler_context_issuer.py         |   464 +
 scripts/ai/lib/scheduler_context_transport.py      |   316 +
 scripts/ai/lib/slot_queue.py                       |   492 +
 scripts/ai/lib/slot_scheduler.py                   |    40 +
 scripts/ai/lib/span_projector.py                   |   420 +
 scripts/ai/lib/span_taxonomy.py                    |   273 +
 scripts/ai/lib/spec_variant_packs.py               |   198 +
 scripts/ai/lib/task_config.py                      |   146 +
 scripts/ai/lib/task_registry.py                    |  1419 ++
 scripts/ai/lib/trace-seed.sh                       |    18 +
 scripts/ai/lib/trace.py                            |   217 +
 scripts/ai/lib/workflow_deviation.py               |   187 +
 scripts/ai/lib/workflow_deviation_io.py            |   223 +
 scripts/ai/lib/workflow_deviation_transport.py     |   368 +
 scripts/ai/lib/workflow_shadow_contract.py         |   419 +
 scripts/ai/llama-model-cli.sh                      |    57 +
 scripts/ai/local-harness-proxy.py                  |   162 +
 scripts/ai/local-orchestrator                      |   344 +
 scripts/ai/mcp-bridge-hybrid.py                    |  1667 ++
 scripts/ai/mcp-db-setup                            |     5 +
 scripts/ai/mcp-db-validate                         |   226 +
 scripts/ai/mcp-github-server                       |    83 +
 scripts/ai/mcp-playwright-sandboxed                |    94 +
 scripts/ai/mcp-server                              |   307 +
 scripts/ai/optimize-and-validate.sh                |   352 +
 scripts/ai/p3-qa-001-dashboard-layered-health.json |    15 +
 scripts/ai/prime-local-agent                       |   110 +
 scripts/ai/race-harness                            |   515 +
 scripts/ai/ralph-orchestrator.sh                   |   298 +
 scripts/ai/rebuild-qdrant-collections.sh           |    12 +
 scripts/ai/render-continue-config.sh               |    73 +
 scripts/ai/resume-model-download.sh                |    76 +
 scripts/ai/route-reasoning-mode.py                 |    48 +
 scripts/ai/skills/aq-delegate.skill.md             |    53 +
 scripts/ai/skills/aq-hints.skill.md                |    52 +
 scripts/ai/skills/aq-memory.skill.md               |    61 +
 scripts/ai/skills/aq-qa.skill.md                   |    56 +
 scripts/ai/skills/aq-report.skill.md               |    53 +
 scripts/ai/skills/aq-runtime-diagnose.skill.md     |    63 +
 scripts/ai/skills/impeccable.skill.md              |   106 +
 scripts/ai/skills/tradingagents.skill.md           |   106 +
 scripts/ai/sync-workflow-sessions.py               |    76 +
 scripts/ai/test-ux-improvements.sh                 |   466 +
 scripts/ai/update-llama-cpp.sh                     |   237 +
 scripts/ai/workflow-deviation-broker               |     7 +
 scripts/apply-tls-certificates.sh                  |     3 +
 scripts/archive-project-knowledge.sh               |     3 +
 scripts/automation/adk/schedule-discovery.sh       |   369 +
 scripts/automation/aidb-reindex.sh                 |   159 +
 scripts/automation/apparmor-fix-agent.py           |   629 +
 scripts/automation/auto-remediate.sh               |    82 +
 scripts/automation/cron-templates.sh               |     8 +
 scripts/automation/post-deploy-converge.sh         |   328 +
 scripts/automation/prime-ai-tooling-defaults.sh    |   111 +
 scripts/automation/prsi-orchestrator.py            |   891 +
 scripts/automation/publish-eval-trend.py           |   143 +
 scripts/automation/repo-parity-check.py            |   107 +
 scripts/automation/repo-parity-update.service      |    15 +
 scripts/automation/repo-parity-update.timer        |    10 +
 scripts/automation/run-acceptance-checks.sh        |   203 +
 scripts/automation/run-advanced-parity-suite.sh    |    70 +
 scripts/automation/run-ai-harness-phase-plan.sh    |    27 +
 scripts/automation/run-all-checks.sh               |   172 +
 scripts/automation/run-eval.sh                     |   221 +
 scripts/automation/run-gap-eval-pack.py            |   312 +
 scripts/automation/run-harness-improvement-pass.sh |   160 +
 scripts/automation/run-harness-regression-gate.sh  |    55 +
 .../run-hint-adoption-remediation-bounded.sh       |   221 +
 .../automation/run-intent-remediation-bounded.sh   |    54 +
 scripts/automation/run-prsi-canary-suite.sh        |    54 +
 scripts/automation/run-prsi-cycle-evidence.sh      |   251 +
 scripts/automation/run-prsi-discovery-slice.sh     |    62 +
 scripts/automation/run-prsi-eval-integrity-gate.sh |    78 +
 .../automation/run-prsi-stop-condition-drill.sh    |    41 +
 scripts/automation/run-qa-suite.sh                 |    36 +
 scripts/automation/run-tc3-checks.sh               |   311 +
 scripts/automation/update-repo-parity.py           |   341 +
 scripts/cleanup-migrated-reports.sh                |     3 +
 scripts/collect-ai-metrics.sh                      |     3 +
 scripts/compare-installed-vs-intended.sh           |     3 +
 scripts/configure-podman-tcp.sh                    |     3 +
 scripts/count-packages-accurately.sh               |     3 +
 scripts/count-packages-simple.sh                   |     3 +
 scripts/cron-templates.sh                          |     3 +
 scripts/curate-residual-gaps.sh                    |     3 +
 .../data/apply-autonomous-improvement-migration.sh |    77 +
 scripts/data/archive-project-knowledge.sh          |   287 +
 scripts/data/backfill-workflow-intent-contract.py  |   138 +
 scripts/data/backup-postgresql.sh                  |   396 +
 scripts/data/backup-qdrant.sh                      |   433 +
 scripts/data/bootstrap-aidb-data.sh                |    57 +
 scripts/data/bootstrap-prsi-confidence-samples.sh  |    45 +
 scripts/data/bootstrap_aidb_data.sh                |     3 +
 scripts/data/cleanup-migrated-reports.sh           |    96 +
 scripts/data/curate-residual-gaps.sh               |   190 +
 scripts/data/download-embeddings-model.sh          |    55 +
 scripts/data/download-llama-cpp-models.sh          |     6 +
 scripts/data/export-ai-behavior-snapshot.sh        |   164 +
 scripts/data/export-collections.sh                 |     6 +
 scripts/data/fix-all-embedding-dimensions.sql      |    39 +
 scripts/data/fix-embedding-dimensions.sh           |   118 +
 scripts/data/fix-postgres-embedding-dimensions.sql |    45 +
 scripts/data/generate-api-key.sh                   |    79 +
 scripts/data/generate-api-secrets.sh               |    13 +
 scripts/data/generate-dashboard-data-lite.sh       |    21 +
 scripts/data/generate-dashboard-data.sh            |    42 +
 scripts/data/generate-harness-sdk-api-docs.sh      |   176 +
 scripts/data/generate-harness-sdk-provenance.sh    |    74 +
 scripts/data/generate-package-counts.sh            |   287 +
 scripts/data/generate-passwords.sh                 |    50 +
 scripts/data/import-agent-instructions.sh          |   206 +
 scripts/data/import-ai-behavior-snapshot.sh        |   199 +
 scripts/data/import-collections.sh                 |     6 +
 scripts/data/import-documents.py                   |   296 +
 scripts/data/import-project-knowledge.sh           |   101 +
 scripts/data/import-tool-recommendations.py        |   376 +
 scripts/data/index-codebase.py                     |   279 +
 scripts/data/ingest-project-knowledge.py           |   385 +
 scripts/data/migrate-hc-domains.py                 |   252 +
 scripts/data/migrate-reports-to-database.sh        |   134 +
 scripts/data/populate-qdrant-directly.py           |   277 +
 scripts/data/provision-solved-issues.py            |    58 +
 scripts/data/provision_solved_issues.py            |    14 +
 scripts/data/rag-system-complete.py                |   627 +
 scripts/data/rebuild-qdrant-collections.sh         |   162 +
 scripts/data/rotate-telemetry.sh                   |     6 +
 scripts/data/seed-domain-knowledge.py              |   150 +
 scripts/data/seed-fresh-deploy.sh                  |   103 +
 scripts/data/seed-memory-recall-benchmark.py       |   109 +
 scripts/data/seed-rag-knowledge.py                 |  2036 ++
 scripts/data/seed-routing-traffic.sh               |   199 +
 scripts/data/seed-tool-audit-traffic.sh            |    69 +
 scripts/data/seed-tooling-plan-telemetry.sh        |    77 +
 scripts/data/semantic-rank-repo-corpus.py          |   210 +
 scripts/data/sync-agent-instructions               |   346 +
 scripts/data/sync-ai-research-knowledge.sh         |    78 +
 scripts/data/sync-aidb-library-catalog.sh          |   371 +
 scripts/data/sync-configs-to-templates.sh          |   180 +
 scripts/data/sync-docs-to-ai.sh                    |   136 +
 scripts/data/sync-flatpak-profile.sh               |   272 +
 scripts/data/sync-hint-feedback-db.py              |   456 +
 scripts/data/sync-knowledge-sources                |   290 +
 scripts/data/sync-learning-data.sh                 |   190 +
 scripts/data/trim-ai-logs.sh                       |   288 +
 scripts/data/trim-snapshots.sh                     |    98 +
 scripts/data/trim-temporal-facts.sh                |    91 +
 scripts/data/update-ai-research-now.sh             |    12 +
 scripts/data/update-aidb-library-catalog-now.sh    |    30 +
 scripts/demo-local-ai-usage.py                     |     5 +
 scripts/deploy/configure-podman-tcp.sh             |     7 +
 scripts/deploy/deploy-aidb-mcp-server.sh           |    13 +
 scripts/deploy/deploy-clean.sh                     |     8 +
 scripts/deploy/enable-cosmic-power-profiles.sh     |    61 +
 scripts/deploy/enable-progressive-disclosure.sh    |     7 +
 scripts/deploy/enhance-dashboard-with-controls.sh  |   217 +
 scripts/deploy/fix-llama-hang.sh                   |    79 +
 scripts/deploy/fix-mangohud-config.sh              |   212 +
 scripts/deploy/install-ai-research-sync-timer.sh   |    30 +
 scripts/deploy/install-backup-timers.sh            |    76 +
 scripts/deploy/install-git-hooks.sh                |    17 +
 scripts/deploy/install-library-catalog-timer.sh    |    64 +
 scripts/deploy/launch-dashboard.sh                 |     8 +
 scripts/deploy/mangohud-profile.sh                 |   125 +
 scripts/deploy/p10k-setup-wizard.sh                |   274 +
 scripts/deploy/publish-local-registry.sh           |     7 +
 scripts/deploy/quick-deploy-fast-verify.sh         |    31 +
 scripts/deploy/recovery-iso-disk-fix.sh            |   188 +
 scripts/deploy/recovery-iso-unlock-user.sh         |   144 +
 scripts/deploy/recovery-offline-fsck-guide.sh      |    44 +
 scripts/deploy/restore-drill.sh                    |   165 +
 scripts/deploy/serve-dashboard-api.sh              |    42 +
 scripts/deploy/serve-dashboard.sh                  |    94 +
 scripts/deploy/setup-claude-proxy.sh               |   167 +
 scripts/deploy/setup-dashboard.sh                  |     7 +
 scripts/deploy/setup-mcp-databases.sh              |     7 +
 scripts/deploy/start-ai-stack-and-dashboard.sh     |     7 +
 scripts/deploy/start-ai-stack.sh                   |     4 +
 scripts/deploy/start-unified-dashboard.sh          |    22 +
 scripts/deploy/stop-ai-stack.sh                    |     4 +
 scripts/edge-model-registry-validate.sh            |     3 +
 scripts/enable-cosmic-power-profiles.sh            |     3 +
 scripts/enable-progressive-disclosure.sh           |     3 +
 scripts/enhance-dashboard-with-controls.sh         |     3 +
 scripts/evaluate-agent-policy.py                   |     5 +
 scripts/firewall-audit.sh                          |     3 +
 scripts/fix-mangohud-config.sh                     |     3 +
 scripts/fix-secrets-encryption.sh                  |     3 +
 scripts/fs-integrity-check.sh                      |     3 +
 scripts/governance/_check_env_contract.py          |    56 +
 scripts/governance/ai-harness-slice-scorecard.py   |   778 +
 scripts/governance/ai-stack-manager.py             |    25 +
 scripts/governance/ai_stack_manager.py             |     5 +
 .../governance/analyze-clean-deploy-readiness.sh   |   336 +
 scripts/governance/analyze-issues.py               |   161 +
 scripts/governance/apply-doc-metadata-blocks.py    |    69 +
 scripts/governance/apply-project-root.sh           |   119 +
 .../governance/apply-readme-ai-stack-updates.py    |   201 +
 scripts/governance/aq-canon-compiler.py            |   277 +
 scripts/governance/aq-evidence-collector.py        |   303 +
 scripts/governance/aq-package-freeze               |   151 +
 scripts/governance/audit-agent-artifact-debt.py    |   354 +
 scripts/governance/audit-deploy-feature-toggles.sh |    60 +
 .../governance/audit-deprecated-script-usage.py    |   270 +
 scripts/governance/audit-hardcoded-paths.sh        |    47 +
 scripts/governance/audit-service-endpoints.sh      |    61 +
 .../build-quick-deploy-reference-tree.sh           |    84 +
 scripts/governance/canon-compile.py                |   134 +
 .../governance/check-archive-path-consistency.sh   |    21 +
 scripts/governance/check-cross-surface-contract.py |   151 +
 .../governance/check-deprecated-docs-location.sh   |    20 +
 scripts/governance/check-doc-frontmatter.py        |   206 +
 scripts/governance/check-doc-lifecycle-hygiene.py  |   124 +
 scripts/governance/check-doc-links.sh              |   119 +
 scripts/governance/check-doc-metadata-standards.sh |    47 +
 .../governance/check-doc-script-path-migration.sh  |    96 +
 scripts/governance/check-flake-age.sh              |   132 +
 .../governance/check-generated-artifact-hygiene.sh |    38 +
 scripts/governance/check-legacy-deprecated-root.sh |    20 +
 .../governance/check-naming-label-consistency.sh   |   207 +
 scripts/governance/check-python-tooling-policy.sh  |    63 +
 .../governance/check-repo-allowlist-integrity.sh   |    43 +
 scripts/governance/check-root-file-hygiene.sh      |    45 +
 scripts/governance/check-root-script-shim-only.sh  |    47 +
 .../governance/check-script-header-standards.sh    |   157 +
 .../governance/check-script-shim-consistency.sh    |    92 +
 scripts/governance/check-state-authorities.py      |   667 +
 .../governance/check-unattended-sudo-readiness.sh  |    56 +
 scripts/governance/config-directory-lint.sh        |   102 +
 scripts/governance/count-packages-accurately.sh    |     8 +
 scripts/governance/count-packages-simple.sh        |     8 +
 scripts/governance/discover-focused-agent-repos.py |   216 +
 scripts/governance/discover-improvements.py        |   392 +
 scripts/governance/discover-improvements.sh        |    16 +
 .../governance/discover-semantic-github-repos.py   |   278 +
 scripts/governance/discover-system-facts.sh        |   882 +
 scripts/governance/edge-model-registry-validate.sh |    72 +
 scripts/governance/evaluate-agent-policy.py        |    78 +
 .../governance/generate-repo-cleanup-inventory.sh  |    58 +
 scripts/governance/git-safe.sh                     |    14 +
 scripts/governance/integration-audit.sh            |   522 +
 scripts/governance/lint-color-echo-usage.sh        |    77 +
 scripts/governance/lint-skill-external-deps.sh     |    52 +
 scripts/governance/lint-skill-template.sh          |   123 +
 scripts/governance/lint-template-placeholders.sh   |    62 +
 scripts/governance/list-issues.py                  |   285 +
 scripts/governance/manage-dashboard-collectors.sh  |   110 +
 scripts/governance/manage-secrets.py               |  1060 +
 scripts/governance/manage-secrets.sh               |    16 +
 scripts/governance/new-improvement-proposal.sh     |    28 +
 scripts/governance/nix-static-analysis.sh          |   139 +
 scripts/governance/normalize-repo-allowlist.sh     |    60 +
 scripts/governance/pre-archive-scan-hook.sh        |    43 +
 scripts/governance/pre-archive-scan.sh             |   123 +
 scripts/governance/pre-rebuild-preflight.sh        |   114 +
 scripts/governance/preflight-auto-remediate.sh     |    35 +
 scripts/governance/quick-deploy-lint.sh            |   209 +
 scripts/governance/record-claude-code-errors.sh    |    86 +
 scripts/governance/record-issue.py                 |   337 +
 .../remediate-unattended-sudo-readiness.sh         |    58 +
 scripts/governance/repo-structure-lint.sh          |   181 +
 scripts/governance/resolve-issue.py                |   174 +
 scripts/governance/rocm-promotion-gate.sh          |   533 +
 scripts/governance/run-focused-ci-checks.sh        |   233 +
 scripts/governance/skill-bundle-registry.py        |   318 +
 scripts/governance/tier0-validation-gate.sh        |  1015 +
 scripts/governance/tier0.d/README.md               |    35 +
 scripts/governance/tier0.d/check-canon-drift.sh    |    17 +
 scripts/governance/tier0.d/check-color-echo.sh     |    53 +
 .../governance/tier0.d/check-config-contracts.sh   |    41 +
 scripts/governance/tier0.d/check-deleted-links.sh  |   109 +
 scripts/governance/tier0.d/check-pm-tracker.sh     |    56 +
 scripts/governance/tier0.d/check-sops-sync.sh      |   151 +
 scripts/governance/trim-stale-assets.sh            |   335 +
 scripts/governance/update-readme-ai-stack.py       |   149 +
 scripts/governance/verify-profile-cleanup.sh       |    71 +
 scripts/health/ai-stack-health-monitor.py          |   183 +
 scripts/health/antigravity-health.sh               |   194 +
 scripts/health/fs-integrity-check.sh               |    49 +
 scripts/health/gemini-cli-health.sh                |   233 +
 scripts/health/system-health-check.sh              |   101 +
 scripts/kernel/kdev                                |   652 +
 scripts/kernel/ktest                               |   554 +
 scripts/lib/download-cache.sh                      |   195 +
 scripts/lib/report-to-database.sh                  |   341 +
 scripts/maintenance/system-update-full.sh          |   189 +
 scripts/mangohud-profile.sh                        |     3 +
 scripts/nix-static-analysis.sh                     |     3 +
 scripts/npm-security-monitor.sh                    |     3 +
 scripts/observability/collect-ai-metrics.sh        |    55 +
 scripts/observability/parse-structured-logs.py     |    56 +
 scripts/p10k-setup-wizard.sh                       |     3 +
 .../performance/run-performance-benchmark-suite.sh |    81 +
 scripts/post-deploy-converge.sh                    |     3 +
 scripts/publish-local-registry.sh                  |     3 +
 scripts/quick-deploy-lint.sh                       |     3 +
 scripts/rag_system_complete.py                     |     5 +
 scripts/reliability/check-runtime-reliability.sh   |    72 +
 scripts/security/apply-tls-certificates.sh         |    27 +
 scripts/security/check-audit-integrity.sh          |    71 +
 .../cleanup-stale-code-scanning-analyses.sh        |   149 +
 .../compare-github-code-scanning-alerts.sh         |   156 +
 scripts/security/dashboard-security-scan.sh        |   173 +
 .../security/export-github-code-scanning-alerts.sh |   219 +
 scripts/security/firewall-audit.sh                 |    56 +
 scripts/security/fix-secrets-encryption.sh         |   389 +
 scripts/security/hospital-classified-gate.sh       |   177 +
 scripts/security/npm-security-monitor.sh           |   554 +
 scripts/security/reconcile-github-code-scanning.sh |   155 +
 scripts/security/refresh-hosted-code-scanning.sh   |   186 +
 scripts/security/renew-tls-certificate.sh          |   129 +
 .../report-github-code-scanning-residuals.sh       |   163 +
 scripts/security/rotate-api-key.sh                 |    72 +
 scripts/security/rotate-skill-registry-key.sh      |   173 +
 scripts/security/run-security-penetration-suite.sh |    78 +
 scripts/security/secrets-rotation-plan.sh          |   128 +
 scripts/security/security-audit.sh                 |   335 +
 scripts/security/security-manager.sh               |   233 +
 scripts/security/security-scan.sh                  |    45 +
 scripts/security/sign-skill-registry.sh            |    30 +
 .../summarize-github-code-scanning-alerts.sh       |   244 +
 scripts/security/update-mcp-integrity-baseline.sh  |    24 +
 scripts/security/verify-python-lock-runtime.py     |   149 +
 scripts/semantic-rank-repo-corpus.py               |     5 +
 scripts/services/cosmic-battery-bridge-dbus.conf   |    16 +
 scripts/services/cosmic-battery-bridge.py          |   322 +
 scripts/sign-skill-registry.sh                     |     3 +
 scripts/skill-bundle-registry.py                   |     5 +
 scripts/sync_docs_to_ai.sh                         |     3 +
 scripts/testing/_mock_config.py                    |    42 +
 scripts/testing/bench-local-agent.py               |   820 +
 scripts/testing/benchmark-acceleration-backends.sh |   450 +
 scripts/testing/benchmark-collaboration.sh         |   341 +
 scripts/testing/benchmark-llama-latency.sh         |   177 +
 scripts/testing/benchmark-quality-performance.py   |   273 +
 scripts/testing/benchmark-query-performance.sh     |   306 +
 scripts/testing/benchmark-workflow-automation.sh   |   340 +
 scripts/testing/cell-submit.py                     |    66 +
 scripts/testing/chaos-harness-smoke.sh             |    49 +
 scripts/testing/check-agent-context-tooling.sh     |   120 +
 .../testing/check-ai-coordinator-delegate-smoke.sh |    76 +
 scripts/testing/check-ai-stack-health-v2.py        |    19 +
 scripts/testing/check-ai-stack-health.sh           |     9 +
 scripts/testing/check-api-auth-hardening.sh        |    67 +
 .../testing/check-aq-integrity-logical-baseline.py |   102 +
 scripts/testing/check-aq-report-contract.sh        |    89 +
 scripts/testing/check-aq-report-metric-smoke.sh    |   179 +
 .../testing/check-aq-report-runtime-sections.sh    |    59 +
 scripts/testing/check-boot-shutdown-integration.sh |    56 +
 scripts/testing/check-context-bootstrap.sh         |   203 +
 scripts/testing/check-dashboard-managed-service.sh |    48 +
 scripts/testing/check-dryrun-failure-modes.sh      |   120 +
 scripts/testing/check-feedback-loop.sh             |    90 +
 .../check-harness-first-evidence-template.sh       |    49 +
 .../check-harness-first-platform-owner-approval.py |   150 +
 .../check-harness-first-pr-evidence-gate.sh        |   110 +
 scripts/testing/check-harness-first-runbook.sh     |    87 +
 .../testing/check-harness-first-static-gates.sh    |    15 +
 scripts/testing/check-knowledge-base-breadth.sh    |    67 +
 scripts/testing/check-mcp-health.sh                |   166 +
 scripts/testing/check-mcp-integrity.sh             |    61 +
 scripts/testing/check-mcp-processes.sh             |    91 +
 .../testing/check-npm-security-monitor-smoke.sh    |    29 +
 scripts/testing/check-package-count-drift.sh       |   104 +
 scripts/testing/check-prsi-bootstrap-integrity.sh  |   146 +
 scripts/testing/check-prsi-budget-discipline.sh    |    33 +
 .../testing/check-prsi-confidence-calibration.sh   |   115 +
 scripts/testing/check-prsi-cycle-contract.sh       |   163 +
 scripts/testing/check-prsi-eval-pinning.sh         |    54 +
 .../check-prsi-high-risk-approval-rubric.sh        |    28 +
 scripts/testing/check-prsi-phase7-static-gates.sh  |    24 +
 scripts/testing/check-prsi-quarantine-workflow.sh  |    28 +
 scripts/testing/check-prsi-validation-matrix.sh    |    50 +
 scripts/testing/check-remote-profiles.sh           |    38 +
 scripts/testing/check-routing-fallback.sh          |   117 +
 scripts/testing/check-skill-source-of-truth.sh     |    29 +
 scripts/testing/check-tls-log-warnings.sh          |    17 +
 scripts/testing/command.sh                         |     5 +
 scripts/testing/compare-installed-vs-intended.sh   |   176 +
 scripts/testing/coverage/.coveragerc               |    22 +
 scripts/testing/drill-rollback.sh                  |   225 +
 .../fixtures/agent-dispatch-contract-golden.json   |    38 +
 .../fixtures/agent-ops-projection-golden.json      |    39 +
 .../testing/fixtures/capability-lease-golden.json  |   170 +
 .../testing/fixtures/execution-grant-golden.json   |  2117 ++
 .../fixtures/herdr-presentation-golden.json        |   868 +
 .../testing/fixtures/l2b_b_golden_payloads.json    |   252 +
 .../local-delegation-reliability-golden.json       |   338 +
 .../local-inference-chat-batch-parity-golden.json  |   322 +
 .../local-inference-contract-v1-golden.json        |    48 +
 .../fixtures/local-inference-l2a-golden.json       |    28 +
 .../local-inference-l2b-payload-golden.json        |    53 +
 .../local-inference-l2b-stream-golden.json         |    10 +
 .../fixtures/local-inference-l3-p0-golden.json     |    22 +
 .../testing/fixtures/operator-context-golden.json  |  2477 ++
 .../fixtures/qa-provider-probe-vectors.json        |   289 +
 .../fixtures/review-feedback-contract-golden.json  |    58 +
 .../fixtures/workflow-deviation-golden.json        |    26 +
 .../workflow-shadow-contract-v1-golden.json        |   158 +
 scripts/testing/gate-local-payload-discipline.sh   |    28 +
 scripts/testing/harness-runner.sh                  |   186 +
 scripts/testing/harness_qa/__init__.py             |     2 +
 scripts/testing/harness_qa/core/__init__.py        |     9 +
 scripts/testing/harness_qa/core/context.py         |   154 +
 scripts/testing/harness_qa/core/helpers.py         |   236 +
 .../testing/harness_qa/core/process_lifecycle.py   |  1445 ++
 scripts/testing/harness_qa/core/result.py          |   229 +
 scripts/testing/harness_qa/main.py                 |   354 +
 scripts/testing/harness_qa/phases/__init__.py      |    59 +
 scripts/testing/harness_qa/phases/phase0.py        |  3650 +++
 scripts/testing/harness_qa/phases/phase1.py        |    39 +
 scripts/testing/harness_qa/phases/phase10.py       |    39 +
 scripts/testing/harness_qa/phases/phase2.py        |    39 +
 scripts/testing/harness_qa/phases/phase3.py        |    39 +
 scripts/testing/harness_qa/phases/phase4.py        |    39 +
 scripts/testing/harness_qa/phases/phase5.py        |    39 +
 scripts/testing/harness_qa/phases/phase54.py       |    39 +
 scripts/testing/harness_qa/phases/phase55.py       |    39 +
 scripts/testing/harness_qa/phases/phase56.py       |    39 +
 scripts/testing/harness_qa/phases/phase57.py       |    39 +
 scripts/testing/harness_qa/phases/phase58.py       |    39 +
 scripts/testing/harness_qa/phases/phase59.py       |    39 +
 scripts/testing/harness_qa/phases/phase6.py        |    39 +
 scripts/testing/harness_qa/phases/phase68.py       |   343 +
 scripts/testing/harness_qa/phases/phase69.py       |   180 +
 scripts/testing/harness_qa/phases/phase7.py        |    39 +
 scripts/testing/harness_qa/phases/phase70.py       |   143 +
 scripts/testing/harness_qa/phases/phase71.py       |   343 +
 scripts/testing/harness_qa/phases/phase72.py       |   229 +
 scripts/testing/harness_qa/phases/phase73.py       |   280 +
 scripts/testing/harness_qa/phases/phase8.py        |    39 +
 scripts/testing/harness_qa/phases/phase9.py        |    39 +
 scripts/testing/harness_qa/reporters/__init__.py   |     4 +
 scripts/testing/harness_qa/reporters/console.py    |    68 +
 scripts/testing/harness_qa/reporters/json_out.py   |    38 +
 scripts/testing/maeah-acceptance-tests.sh          |   277 +
 scripts/testing/maeah-live-auth-smoke.sh           |   138 +
 scripts/testing/memory-regression-tests.py         |    88 +
 scripts/testing/mobile-web-masa-harness.py         |   250 +
 .../testing/perf/execution-cell-perf-harness.py    |  1394 ++
 .../perf/execution-cell-perf-report.schema.json    |   261 +
 scripts/testing/phase58b-routing-audit.py          |    68 +
 scripts/testing/qa-provider-probe.py               |   669 +
 scripts/testing/run-a2a-tck.sh                     |   146 +
 scripts/testing/run-benchmark-gate.sh              |   107 +
 scripts/testing/run-targeted-coverage.sh           |   150 +
 scripts/testing/smoke-a2a-compat.sh                |   159 +
 scripts/testing/smoke-agent-harness-parity.sh      |   210 +
 .../testing/smoke-augment-research-lesson-refs.sh  |   135 +
 ...smoke-context-cache-learning-ops-lesson-refs.sh |    99 +
 .../testing/smoke-continue-coordinator-ingress.sh  |   154 +
 scripts/testing/smoke-continue-editor-flow.sh      |   120 +
 scripts/testing/smoke-delegate-lesson-refs.sh      |    47 +
 .../smoke-deployment-monitoring-alerting.sh        |   160 +
 scripts/testing/smoke-discovery-lesson-refs.sh     |    48 +
 scripts/testing/smoke-feedback-lesson-refs.sh      |    46 +
 scripts/testing/smoke-flagship-cli-surfaces.sh     |    22 +
 scripts/testing/smoke-focused-parity.sh            |   126 +
 scripts/testing/smoke-harness-sdk-packaging.sh     |    90 +
 .../smoke-health-memory-learning-lesson-refs.sh    |   128 +
 scripts/testing/smoke-hints-lesson-refs.sh         |    32 +
 scripts/testing/smoke-ide-adapter-compat.sh        |   258 +
 scripts/testing/smoke-integration-complete.sh      |   227 +
 scripts/testing/smoke-lessons-lesson-refs.sh       |    31 +
 scripts/testing/smoke-lessons-review-refs.sh       |    53 +
 scripts/testing/smoke-local-model.sh               |   312 +
 scripts/testing/smoke-mcp-health-pings.sh          |    47 +
 .../testing/smoke-phase-4-integrated-workflows.sh  |   127 +
 .../testing/smoke-query-agent-storage-learning.sh  |   176 +
 scripts/testing/smoke-query-lesson-refs.sh         |    45 +
 scripts/testing/smoke-query-task-classes.sh        |   221 +
 scripts/testing/smoke-remote-delegation-lanes.sh   |    67 +
 .../testing/smoke-review-acceptance-lesson-refs.sh |    84 +
 scripts/testing/smoke-security-audit-compliance.sh |   156 +
 scripts/testing/smoke-security-audit-producer.sh   |    47 +
 scripts/testing/smoke-session-lesson-refs.sh       |    47 +
 scripts/testing/smoke-skills-lesson-refs.sh        |    31 +
 scripts/testing/smoke-status-lesson-refs.sh        |    31 +
 scripts/testing/smoke-status-report-summary.sh     |    62 +
 .../testing/smoke-status-runtime-lesson-refs.sh    |   110 +
 scripts/testing/smoke-test-local-agents.sh         |   193 +
 .../testing/smoke-test-orchestration-visibility.sh |    61 +
 scripts/testing/smoke-wasmtime.sh                  |    73 +
 .../smoke-workflow-isolation-lesson-refs.sh        |    71 +
 .../smoke-workflow-orchestrate-lesson-refs.sh      |    55 +
 scripts/testing/smoke-workflow-plan-lesson-refs.sh |    33 +
 scripts/testing/smoke-workflow-review-contract.sh  |   561 +
 scripts/testing/smoke-workflow-run-lesson-refs.sh  |    52 +
 .../testing/smoke-workflow-runtime-lesson-refs.sh  |    83 +
 .../testing/smoke-workflow-start-lesson-refs.sh    |    43 +
 .../testing/smoke-workflow-tooling-lesson-refs.sh  |    35 +
 scripts/testing/smoke-workflow-tree-lesson-refs.sh |    82 +
 scripts/testing/telemetry-smoke-test.sh            |     9 +
 scripts/testing/test-a2a-compat.py                 |    52 +
 scripts/testing/test-a2a-guard.py                  |    88 +
 scripts/testing/test-adk-declarative-wiring.sh     |    14 +
 scripts/testing/test-adk-integration.py            |   498 +
 scripts/testing/test-adk-protocol-compliance.py    |   454 +
 .../testing/test-adk-reviewer-gate-checklist.sh    |    59 +
 .../test-advanced-features-control-plane.py        |    70 +
 .../test-advanced-features-implementation.py       |   120 +
 .../testing/test-advanced-reasoning-patterns.py    |   115 +
 .../testing/test-affective-reciprocity-wiring.py   |    41 +
 scripts/testing/test-agent-action-policy.py        |   107 +
 scripts/testing/test-agent-agnostic-router.py      |   459 +
 scripts/testing/test-agent-artifact-policy.py      |   104 +
 scripts/testing/test-agent-dispatch-budget.py      |   122 +
 scripts/testing/test-agent-dispatch-contract.py    |   160 +
 scripts/testing/test-agent-evaluation-bias.py      |   133 +
 .../test-agent-executor-analysis-finalization.py   |    30 +
 scripts/testing/test-agent-executor-reviewer-id.py |   135 +
 .../test-agent-executor-role-eligibility.py        |   128 +
 scripts/testing/test-agent-identity-envelope.py    |   101 +
 scripts/testing/test-agent-lesson-registry.py      |    71 +
 scripts/testing/test-agent-lesson-schema.py        |    79 +
 scripts/testing/test-agent-loop-event-streaming.py |    59 +
 scripts/testing/test-agent-loop-result-quality.py  |    62 +
 .../testing/test-agent-mcp-client-projection.py    |   174 +
 .../testing/test-agent-memory-surface-registry.py  |    31 +
 .../test-agent-ops-local-direct-health-web.py      |   444 +
 scripts/testing/test-agent-ops-projection.py       |  1732 ++
 scripts/testing/test-agent-pool-integration.py     |    57 +
 scripts/testing/test-agent-quality-profiler.py     |   122 +
 scripts/testing/test-agent-registry.py             |    40 +
 scripts/testing/test-agent-run-event-envelope.py   |   176 +
 scripts/testing/test-agent-safety.sh               |   171 +
 scripts/testing/test-agent-status-integration.py   |   251 +
 scripts/testing/test-agent-status-reporting.py     |   185 +
 scripts/testing/test-agent-unbacked-write-guard.py |    96 +
 scripts/testing/test-agentic-workflow-parity.py    |   146 +
 .../test-ai-capability-implementation-backlog.py   |   121 +
 scripts/testing/test-ai-coordinator.py             |   220 +
 scripts/testing/test-ai-insights-ai-metrics.py     |    99 +
 scripts/testing/test-ai-insights-dashboard.py      |   417 +
 .../testing/test-ai-insights-ranking-algorithms.py |   520 +
 .../testing/test-ai-insights-roadmap-surfaces.py   |   374 +
 scripts/testing/test-ai-metrics-instrumentation.py |    65 +
 .../testing/test-ai-service-health-monitoring.py   |   342 +
 .../test-ai-service-health-switchboard-details.py  |    89 +
 .../testing/test-ai-stack-acceleration-policy.py   |    57 +
 scripts/testing/test-ai-stack-health-monitor.py    |    83 +
 scripts/testing/test-ai-stack-health.sh            |     8 +
 scripts/testing/test-aidb-last-accessed-sql.py     |    20 +
 scripts/testing/test-aidb-reindex-exit-policy.sh   |    19 +
 scripts/testing/test-ala-service-coverage.py       |    78 +
 scripts/testing/test-alert-engine-builtins.py      |    43 +
 .../testing/test-analysis-only-stagnation-mode.py  |    84 +
 scripts/testing/test-antigravity-claim-receipt.py  |   222 +
 scripts/testing/test-antigravity-inbox.py          |    69 +
 scripts/testing/test-antigravity-liveness.py       |   102 +
 .../testing/test-antigravity-routing-honesty.py    |   258 +
 scripts/testing/test-api-auth-hardening-smoke.py   |    61 +
 scripts/testing/test-api-client-gen.py             |    62 +
 scripts/testing/test-approval-recovery.py          |   593 +
 scripts/testing/test-approval-request.py           |   542 +
 scripts/testing/test-approval-runbook-engine.py    |   549 +
 scripts/testing/test-approval-signer.py            |   797 +
 scripts/testing/test-approval-surface.py           |   442 +
 scripts/testing/test-aq-a2a-audit.py               |    95 +
 scripts/testing/test-aq-agent-reap.py              |   136 +
 scripts/testing/test-aq-alerts-json.py             |    37 +
 scripts/testing/test-aq-approve-headless.py        |   628 +
 scripts/testing/test-aq-canon-compiler.py          |   197 +
 scripts/testing/test-aq-chat-local-tool-profile.py |   136 +
 scripts/testing/test-aq-completions.sh             |    39 +
 .../testing/test-aq-context-manage-checkpoint.py   |    67 +
 scripts/testing/test-aq-context-sandbox.py         |    52 +
 scripts/testing/test-aq-editor-rescue.py           |   190 +
 scripts/testing/test-aq-eval.py                    |    82 +
 scripts/testing/test-aq-evidence-collector.py      |   411 +
 scripts/testing/test-aq-index-knowledge-graph.py   |    41 +
 scripts/testing/test-aq-inference-bench.py         |   176 +
 scripts/testing/test-aq-integrity-scan-contract.py |   128 +
 scripts/testing/test-aq-local-review.py            |   218 +
 .../testing/test-aq-loop-review-repair-guard.py    |    64 +
 .../testing/test-aq-optimizer-gap-remediation.py   |    37 +
 scripts/testing/test-aq-optimizer-lesson-review.py |    37 +
 scripts/testing/test-aq-qa-continue-config.py      |   109 +
 scripts/testing/test-aq-qa-delegate-window.py      |    56 +
 scripts/testing/test-aq-qa-progress-heartbeat.py   |    70 +
 scripts/testing/test-aq-rag-prewarm-selection.sh   |   136 +
 .../testing/test-aq-report-attention-contention.py |   143 +
 .../test-aq-report-continuation-downshift.py       |   169 +
 .../test-aq-report-editor-rescue-telemetry.py      |   126 +
 .../testing/test-aq-report-editor-state-budgets.py |   130 +
 .../test-aq-report-effectiveness-scorecard.py      |   171 +
 scripts/testing/test-aq-report-llama-benchmarks.py |    74 +
 .../test-aq-report-prompt-cache-fallback.py        |    91 +
 .../test-aq-report-prompt-registry-fallback.py     |    56 +
 scripts/testing/test-aq-report-ragas-panel.py      |   197 +
 .../test-aq-report-reliability-interpretation.py   |   151 +
 scripts/testing/test-aq-report-route-telemetry.py  |    84 +
 scripts/testing/test-aq-report-runtime-actions.py  |   215 +
 .../testing/test-aq-report-tool-audit-sources.py   |   122 +
 scripts/testing/test-aq-router.sh                  |    74 +
 scripts/testing/test-aq-screenshot-contract.sh     |    36 +
 scripts/testing/test-aq-sequential-edit.py         |    92 +
 scripts/testing/test-aq-slice-helper-contract.sh   |    20 +
 scripts/testing/test-aq-tempest.py                 |   103 +
 scripts/testing/test-asymmetric-lease-authority.py |   300 +
 .../testing/test-attention-queue-env-override.py   |   125 +
 scripts/testing/test-audit-defaults.py             |    43 +
 scripts/testing/test-auto-assign.py                |    89 +
 .../testing/test-auto-deployer-error-threshold.py  |    75 +
 .../testing/test-auto-deployer-strategy-stages.py  |    67 +
 .../testing/test-auto-tool-select-skill-routes.py  |    46 +
 .../test-autonomous-capability-discovery.sh        |    88 +
 scripts/testing/test-backend-selection-caching.py  |   537 +
 scripts/testing/test-backpressure.py               |   160 +
 .../testing/test-behavioral-contract-read-limit.py |    20 +
 scripts/testing/test-bitnet-benchmark.py           |    35 +
 scripts/testing/test-bitnet-compare.py             |    31 +
 scripts/testing/test-bitnet-feasibility.py         |    73 +
 scripts/testing/test-blast-radius-classifier.py    |    35 +
 scripts/testing/test-boot-stability-regressions.py |   274 +
 scripts/testing/test-browser-research.py           |    95 +
 scripts/testing/test-c2-gate-dispatch-wiring.py    |   646 +
 scripts/testing/test-c2-sci-live-mint.py           |   102 +
 scripts/testing/test-c2-sci-service-coverage.py    |   111 +
 scripts/testing/test-c6-p0-trust-anchors.py        |   150 +
 .../testing/test-cache-prewarm-effectiveness.py    |   590 +
 scripts/testing/test-candidate-lifecycle.py        |   124 +
 .../testing/test-capability-enforcement-card.py    |   322 +
 .../testing/test-capability-enforcement-check.py   |   163 +
 scripts/testing/test-capability-flush.py           |   104 +
 scripts/testing/test-capability-gap-integration.py |    65 +
 scripts/testing/test-capability-intake.py          |   531 +
 scripts/testing/test-capability-lease-gate.py      |   768 +
 scripts/testing/test-capability-lease-issuance.py  |   466 +
 scripts/testing/test-capability-lease.py           |   565 +
 scripts/testing/test-cascade.py                    |   122 +
 scripts/testing/test-chat-intent.py                |   279 +
 scripts/testing/test-check-flake-age.sh            |   179 +
 scripts/testing/test-check-mcp-health-defaults.sh  |    42 +
 .../testing/test-codex-subagent-configuration.py   |   199 +
 .../testing/test-collaborative-plan-persistence.py |    63 +
 scripts/testing/test-complexity-lane-routing.py    |    57 +
 scripts/testing/test-config-loader.py              |   146 +
 scripts/testing/test-consensus-persistence.py      |    64 +
 scripts/testing/test-container-recovery.sh         |    12 +
 scripts/testing/test-context-assembler.py          |   441 +
 scripts/testing/test-context-cache.py              |   222 +
 .../testing/test-context-compaction-sandwich.py    |    82 +
 scripts/testing/test-context-manage-summary.py     |   106 +
 scripts/testing/test-context-sanitizer-wiring.py   |    21 +
 .../testing/test-context-store-causality-edges.py  |   466 +
 .../testing/test-context-store-deployment-deps.py  |   508 +
 .../test-context-store-deployment-lifecycle.py     |   242 +
 scripts/testing/test-context-store-performance.py  |   406 +
 .../testing/test-context-store-query-context.py    |   332 +
 .../testing/test-context-store-service-state.py    |   399 +
 .../test-context-warmer-python-resolution.py       |    44 +
 .../test-context-warmer-service-python-env.py      |    61 +
 .../testing/test-continue-coordinator-ingress.py   |    93 +
 .../test-continue-editor-failure-categories.py     |    99 +
 scripts/testing/test-continue-editor-history.py    |    77 +
 .../test-continuous-learning-checkpoint-resume.py  |    78 +
 .../testing/test-continuous-learning-embeddings.py |    89 +
 .../testing/test-continuous-learning-proposals.py  |    73 +
 .../test-continuous-learning-qdrant-upsert.py      |   162 +
 ...test-continuous-learning-watchfiles-throttle.py |   100 +
 scripts/testing/test-control-channel.py            |    95 +
 .../test-coordinator-strangler-route-ownership.py  |   130 +
 .../test-cross-agent-contradiction-detection.py    |   150 +
 scripts/testing/test-curated-web-research.py       |   168 +
 scripts/testing/test-dashboard-a2a-insights-ui.py  |    36 +
 .../test-dashboard-advanced-runtime-summary.py     |   128 +
 scripts/testing/test-dashboard-agent-replay.py     |   236 +
 scripts/testing/test-dashboard-ai-insights-ui.py   |    48 +
 ...shboard-ai-metrics-switchboard-local-runtime.py |   150 +
 .../test-dashboard-aidb-health-live-mode.py        |    36 +
 ...test-dashboard-command-center-graph-payloads.py |    42 +
 .../test-dashboard-command-center-graph-ui.py      |    53 +
 .../test-dashboard-command-center-graphs.py        |    61 +
 .../testing/test-dashboard-command-lenses-ui.py    |    74 +
 scripts/testing/test-dashboard-compat-routes.py    |    80 +
 .../testing/test-dashboard-config-control-plane.py |   134 +
 scripts/testing/test-dashboard-config-ui.py        |    49 +
 scripts/testing/test-dashboard-context-store-ui.py |   427 +
 .../testing/test-dashboard-deployment-execution.py |   279 +
 scripts/testing/test-dashboard-deployment-ui.py    |   106 +
 .../test-dashboard-governance-projection.py        |   359 +
 .../testing/test-dashboard-graph-visualization.py  |   475 +
 .../test-dashboard-insights-report-cache.py        |   283 +
 .../testing/test-dashboard-loop-status-fallback.py |   142 +
 .../test-dashboard-operator-links-api-base.py      |    35 +
 .../test-dashboard-orchestration-api-base.py       |    45 +
 .../testing/test-dashboard-orchestration-events.py |   144 +
 .../test-dashboard-orchestration-sessions.py       |   140 +
 .../testing/test-dashboard-phase5-7-integration.py |   124 +
 scripts/testing/test-dashboard-program-progress.py |   232 +
 .../testing/test-dashboard-qa-provider-probe.py    |   385 +
 .../test-dashboard-qa-runner-runtime-env.py        |    73 +
 scripts/testing/test-dashboard-qa-singleflight.py  |    50 +
 .../testing/test-dashboard-routing-posture-ui.py   |    39 +
 scripts/testing/test-dashboard-runtime-controls.py |   194 +
 .../testing/test-dashboard-search-filter-logic.py  |   436 +
 scripts/testing/test-dashboard-security-headers.py |    60 +
 .../test-dashboard-security-scan-automation.py     |   182 +
 .../testing/test-dashboard-testing-execution.py    |   208 +
 scripts/testing/test-dashboard-testing-ui.py       |    54 +
 scripts/testing/test-dashboard-visual.sh           |    98 +
 scripts/testing/test-dashboard-workflow-graphs.py  |   118 +
 scripts/testing/test-decompose-loop.py             |   313 +
 scripts/testing/test-delegate-agent-mapping.py     |    13 +
 .../test-delegate-antigravity-background-stdio.py  |    48 +
 .../test-delegate-attention-queue-wiring.py        |    75 +
 .../testing/test-delegate-claude-model-routing.py  |   121 +
 .../testing/test-delegate-codex-quota-precheck.sh  |   320 +
 scripts/testing/test-delegate-coding.py            |    13 +
 scripts/testing/test-delegate-local-agent.py       |    13 +
 .../test-delegate-response-budget-wiring.py        |    80 +
 .../test-delegate-routing-profile-honoring.py      |    44 +
 scripts/testing/test-delegate-timeout-config.py    |    64 +
 scripts/testing/test-delegate-to-local-argparse.sh |    18 +
 scripts/testing/test-delegate.py                   |    13 +
 ...test-delegated-prompt-efficiency-integration.py |    49 +
 .../test-delegated-prompt-failure-history.py       |   127 +
 .../testing/test-delegated-prompt-failure-trend.py |    97 +
 .../testing/test-delegated-quality-integration.py  |    77 +
 scripts/testing/test-delegation-failover.py        |   360 +
 .../testing/test-delegation-feedback-contract.py   |    92 +
 scripts/testing/test-delegation-feedback.py        |   216 +
 scripts/testing/test-delegation-local-gemini.py    |    22 +
 .../test-deployment-causality-clustering.py        |   771 +
 scripts/testing/test-deployment-dashboard.py       |   307 +
 scripts/testing/test-deployment-graph-queries.py   |   571 +
 .../test-deployment-monitoring-alerting-e2e.py     |   631 +
 .../testing/test-deployment-operations-rollback.py |   556 +
 .../testing/test-desktop-cosmic-greeter-config.py  |    66 +
 .../testing/test-discovery-agent-opportunities.py  |   121 +
 scripts/testing/test-discovery-system.py           |   394 +
 scripts/testing/test-dispatch-consult.py           |   547 +
 .../testing/test-doc-frontmatter-staged-files.py   |   214 +
 scripts/testing/test-domain-router.py              |    28 +
 scripts/testing/test-durable-reservation.py        |   159 +
 scripts/testing/test-edgeai-cli-contract.sh        |    24 +
 scripts/testing/test-edit-feedback.py              |   305 +
 .../test-embedding-generation-performance.py       |   528 +
 .../test-enabled-external-mcp-candidates.py        |   119 +
 scripts/testing/test-enforce-asymmetric-verify.py  |   637 +
 scripts/testing/test-eval-contention-guard.py      |    94 +
 scripts/testing/test-eval-integrity.py             |    90 +
 scripts/testing/test-eval-sandbox.py               |    81 +
 scripts/testing/test-event-bus-a2a.py              |   195 +
 scripts/testing/test-evidence-algebra.py           |    81 +
 scripts/testing/test-execution-cell-adapter.py     |   613 +
 scripts/testing/test-execution-cell-clone.py       |   646 +
 .../testing/test-execution-cell-perf-harness.py    |   510 +
 .../test-execution-cell-runner-deploy-context.py   |   109 +
 scripts/testing/test-execution-cell-runner.py      |   877 +
 scripts/testing/test-execution-grant.py            |   415 +
 .../testing/test-exploration-stagnation-guard.py   |    48 +
 scripts/testing/test-failure-correction.py         |    57 +
 scripts/testing/test-failure-pattern-analysis.py   |   108 +
 scripts/testing/test-flat-prd-gate.py              |   136 +
 scripts/testing/test-focused-ci-diagnostic-json.py |   227 +
 scripts/testing/test-frontdoor-routing-contract.py |    44 +
 scripts/testing/test-grammar-cache.py              |    98 +
 scripts/testing/test-harness-delegation-live.py    |   313 +
 scripts/testing/test-harness-workflow-controls.py  |    64 +
 .../testing/test-health-spider-loop-regression.py  |    99 +
 .../test-health-spider-osi-layered-probe.py        |    52 +
 scripts/testing/test-herdr-h1-contract.py          |   239 +
 scripts/testing/test-herdr-intake-contract.py      |    69 +
 .../testing/test-herdr-presentation-projection.py  |   242 +
 scripts/testing/test-hints-agent-lessons.py        |    75 +
 scripts/testing/test-hints-route-selection.py      |   123 +
 scripts/testing/test-hints-runtime-batch.py        |   284 +
 scripts/testing/test-host-observer-contract.py     |   121 +
 scripts/testing/test-http-query-audit-metadata.py  |    65 +
 scripts/testing/test-hw-probe.py                   |   127 +
 scripts/testing/test-hybrid-auth-profile-policy.py |    70 +
 scripts/testing/test-hybrid-routing-config.py      |    47 +
 .../test-hyperd-unattended-sudo-wildcards.py       |    36 +
 .../testing/test-insights-performance-hotspots.py  |   154 +
 scripts/testing/test-insights-phase4-acceptance.py |    88 +
 .../testing/test-insights-security-compliance.py   |    78 +
 scripts/testing/test-intake-gateway.py             |    51 +
 scripts/testing/test-integration-completeness.py   |   477 +
 scripts/testing/test-intent-classifier-coverage.py |   181 +
 scripts/testing/test-introspection-validate.py     |    67 +
 scripts/testing/test-ipm-thermal-thresholds.py     |   113 +
 scripts/testing/test-json-sanitizer.py             |    36 +
 scripts/testing/test-knowledge-graph-search.py     |    60 +
 scripts/testing/test-lane-eligibility.py           |   388 +
 scripts/testing/test-lazy-loading-large-results.py |   380 +
 scripts/testing/test-lease-signing-authority.py    |   167 +
 scripts/testing/test-llama-benchmark-observe.py    |    59 +
 scripts/testing/test-llama-benchmark.py            |    49 +
 scripts/testing/test-llama-staging-status.py       |    56 +
 scripts/testing/test-llm-router-integration.py     |   115 +
 scripts/testing/test-local-agent-config.py         |   140 +
 .../test-local-agent-first-token-timeout.py        |    34 +
 .../testing/test-local-agent-monitor-visibility.py |    96 +
 .../testing/test-local-agent-offline-resilience.py |   118 +
 .../test-local-agent-progress-guarded-tools.py     |    69 +
 .../test-local-agent-store-memory-contract.py      |   113 +
 scripts/testing/test-local-delegation-artifact.py  |   491 +
 .../testing/test-local-delegation-reliability.py   |   315 +
 scripts/testing/test-local-inference-budget.py     |   419 +
 .../test-local-inference-chat-batch-parity.py      |   546 +
 scripts/testing/test-local-inference-contract.py   |   309 +
 scripts/testing/test-local-inference-l2a.py        |   368 +
 scripts/testing/test-local-inference-l2b.py        |  1336 ++
 scripts/testing/test-local-inference-l3-p0.py      |   219 +
 scripts/testing/test-local-inference-throughput.py |    81 +
 .../testing/test-local-orchestrator-frontdoor.sh   |    16 +
 scripts/testing/test-local-shell-sandbox.py        |    48 +
 scripts/testing/test-local-slot-busy-fast-fail.py  |   147 +
 .../test-local-subprocess-discipline-smoke.py      |   138 +
 scripts/testing/test-local-surface-scan.py         |    38 +
 .../test-local-system-prompt-env-sanitization.py   |    36 +
 .../test-local-training-loop-timeout-task-id.py    |    92 +
 scripts/testing/test-loop-scorer-certified.py      |    61 +
 scripts/testing/test-maeah-api-surface-contract.py |    71 +
 scripts/testing/test-maeah-contract-artifacts.py   |    62 +
 .../testing/test-maeah-live-runbook-contract.py    |    76 +
 .../testing/test-maeah-model-registry-schema.py    |    57 +
 scripts/testing/test-mcp-bridge-aidb-query.py      |    74 +
 scripts/testing/test-mcp-tool-attention-queue.py   |    60 +
 .../testing/test-memory-recall-broker-contract.py  |   301 +
 scripts/testing/test-meta-learning-integration.py  |    49 +
 .../testing/test-metrics-cache-effectiveness.py    |   461 +
 scripts/testing/test-modal-task-profiles.py        |   306 +
 scripts/testing/test-model-budget.py               |    84 +
 scripts/testing/test-model-catalog-freshness.py    |    73 +
 .../test-model-optimization-advanced-runtime.py    |    87 +
 .../test-model-optimization-implementation.py      |   174 +
 .../testing/test-model-optimization-mcp-tools.py   |    52 +
 .../test-model-optimization-runtime-integration.py |   109 +
 scripts/testing/test-model-symlink-verification.sh |    37 +
 scripts/testing/test-model-tier.py                 |    73 +
 scripts/testing/test-multi-agent-collaboration.py  |   630 +
 scripts/testing/test-multi-agent-coordination.py   |   438 +
 .../testing/test-multi-modal-retrieval-ranking.py  |   558 +
 .../testing/test-nixos-writable-state-policy.py    |    31 +
 scripts/testing/test-noaction-intervention.py      |   285 +
 ...ffloading-context-remediation-implementation.py |   182 +
 scripts/testing/test-operational-perspective.py    |   126 +
 .../testing/test-operator-context-projection.py    |   191 +
 .../testing/test-operator-retrieval-guidance.py    |   643 +
 scripts/testing/test-ops-handler-extraction.py     |    44 +
 .../test-optional-performance-completion.py        |    79 +
 .../testing/test-orchestration-comprehensive.py    |   600 +
 scripts/testing/test-orchestration-framework.py    |   240 +
 scripts/testing/test-orchestration-primitives.py   |   124 +
 .../test-orchestration-runtime-integration.py      |    74 +
 scripts/testing/test-orchestration-visibility.py   |   187 +
 scripts/testing/test-osint-active-recon-gate.py    |   118 +
 scripts/testing/test-osint-research-ingest.py      |   188 +
 scripts/testing/test-osint-tools-mcp-contract.py   |    72 +
 scripts/testing/test-package-freeze.py             |    97 +
 scripts/testing/test-phase59-expert-mode-wiring.py |    58 +
 scripts/testing/test-pipeline-orchestration.py     |   198 +
 scripts/testing/test-plans-index.py                |   266 +
 scripts/testing/test-postflight-health-policy.py   |    36 +
 .../test-progressive-context-integration.py        |    57 +
 .../test-progressive-disclosure-implementation.py  |   136 +
 scripts/testing/test-prompt-effectiveness.py       |   584 +
 .../testing/test-prompt-eval-transport-guard.py    |    67 +
 .../testing/test-prompt-injection-resilience.sh    |    90 +
 scripts/testing/test-qa-evidence-store.py          |   103 +
 scripts/testing/test-qa-provider-probe-adoption.py |   681 +
 .../testing/test-qa-provider-probe-lifecycle.py    |  1465 ++
 scripts/testing/test-qa-provider-probe-observer.py |   527 +
 scripts/testing/test-quality-cache.py              |   245 +
 scripts/testing/test-quality-system-health.py      |   343 +
 .../test-query-agent-storage-learning-loop.py      |   683 +
 .../testing/test-query-handler-attention-queue.py  |    56 +
 scripts/testing/test-query-performance.py          |   379 +
 scripts/testing/test-query-result-caching.py       |   555 +
 scripts/testing/test-quickstart.py                 |    75 +
 scripts/testing/test-race-harness.py               |   178 +
 scripts/testing/test-rag-posture-diagnosis.py      |   171 +
 scripts/testing/test-ragas-autoscoring-wiring.py   |   170 +
 scripts/testing/test-ragas-faithfulness-guard.py   |   166 +
 .../testing/test-ralph-orchestrator-delegation.py  |    81 +
 scripts/testing/test-ralph-task-systemd-wiring.sh  |    23 +
 scripts/testing/test-read-file-gate.py             |   288 +
 .../testing/test-real-time-learning-integration.py |    49 +
 scripts/testing/test-real-world-workflows.sh       |   125 +
 scripts/testing/test-refactor-status.py            |   465 +
 scripts/testing/test-remote-profile-utilization.py |   211 +
 scripts/testing/test-remote-task-contract.py       |    67 +
 scripts/testing/test-reread-intervention.py        |   225 +
 scripts/testing/test-retrieval-breadth-history.py  |    79 +
 scripts/testing/test-review-feedback-contract.py   |   289 +
 scripts/testing/test-revocation-epoch-authority.py |   363 +
 scripts/testing/test-revocation-epoch.py           |   494 +
 scripts/testing/test-round-aggregate.py            |   314 +
 scripts/testing/test-round-contribution.py         |   154 +
 .../testing/test-round-decision-authorization.py   |   191 +
 scripts/testing/test-round-golden.py               |   310 +
 scripts/testing/test-round-state-machine.py        |   119 +
 .../test-route-handler-adaptive-timeouts.py        |   144 +
 .../testing/test-route-handler-backend-audit.py    |   151 +
 .../test-route-handler-classifier-context-cap.py   |   283 +
 .../test-route-handler-collection-policy.py        |   226 +
 .../testing/test-route-handler-context-budget.py   |   193 +
 .../testing/test-route-handler-discovery-gating.py |   213 +
 .../test-route-handler-local-synthesis-budget.py   |   201 +
 .../testing/test-route-search-parallelization.py   |   462 +
 .../test-route-search-pressure-diagnosis.py        |   134 +
 scripts/testing/test-routing-history.py            |    66 +
 scripts/testing/test-routing-profile-registry.py   |    31 +
 scripts/testing/test-safety-gate.py                |   137 +
 scripts/testing/test-safety-layer.py               |    48 +
 scripts/testing/test-scheduler-context-issuer.py   |   582 +
 scripts/testing/test-scheduler-context-ledger.py   |   342 +
 scripts/testing/test-scheduler-lease-gate.py       |   326 +
 scripts/testing/test-scheduler.py                  |   143 +
 .../test-search-router-collection-timeouts.py      |   104 +
 scripts/testing/test-secrets-rotation-plan.py      |    85 +
 .../testing/test-security-audit-compliance-flow.py |   683 +
 scripts/testing/test-security-contract-gates.py    |   111 +
 .../testing/test-security-workflow-integration.py  |   387 +
 scripts/testing/test-semantic-compression.py       |   140 +
 scripts/testing/test-shared-skill-sync.py          |    69 +
 scripts/testing/test-skill-auto.py                 |    69 +
 scripts/testing/test-slot-queue-wiring.py          |   122 +
 scripts/testing/test-span-truth.py                 |   587 +
 scripts/testing/test-spec-variant-packs.py         |    85 +
 scripts/testing/test-state-authorities.py          |   626 +
 scripts/testing/test-stateful-downgrade-policy.py  |    37 +
 .../testing/test-suggested-ai-repo-candidates.py   |   113 +
 .../test-switchboard-adaptive-local-budget.py      |    64 +
 .../testing/test-switchboard-context-output-gc.py  |    70 +
 .../test-switchboard-continue-context-window.sh    |    70 +
 .../test-switchboard-local-runtime-health.py       |   133 +
 .../testing/test-switchboard-local-tool-calling.sh |    95 +
 .../test-switchboard-local-tool-finalization.py    |    60 +
 ...st-switchboard-no-silent-openrouter-fallback.py |    43 +
 .../test-switchboard-profile-catalog-contract.py   |   105 +
 scripts/testing/test-switchboard-profile-policy.py |    61 +
 .../testing/test-switchboard-strict-reply-trim.py  |   104 +
 .../test-switchboard-tool-working-set-gc.py        |   123 +
 scripts/testing/test-switchboard-useful-ratio.py   |    33 +
 scripts/testing/test-synthesis-guard.py            |    21 +
 scripts/testing/test-system-capability-catalog.py  |    72 +
 .../test-task-classifier-local-continuation.py     |   116 +
 scripts/testing/test-task-registry-heartbeat-ts.py |    60 +
 scripts/testing/test-telemetry-root-boundary.py    |    83 +
 scripts/testing/test-telemetry-thought-event.sh    |    72 +
 scripts/testing/test-testing-artifact-paths.py     |    55 +
 scripts/testing/test-tier0-color-echo-extension.sh |    48 +
 scripts/testing/test-tier0-staged-isolation.sh     |   202 +
 scripts/testing/test-timeout-guard-behavior.py     |   626 +
 scripts/testing/test-token-usage-coverage.py       |    68 +
 scripts/testing/test-tool-call-grammar.py          |   391 +
 scripts/testing/test-tool-grammar.py               |    96 +
 .../test-tool-registry-security-metadata.py        |    88 +
 scripts/testing/test-tool-security-auditor.py      |    88 +
 scripts/testing/test-tooling-manifest.py           |   170 +
 scripts/testing/test-trace-seed.py                 |    68 +
 scripts/testing/test-trace.py                      |   116 +
 scripts/testing/test-trading-handlers-imports.py   |    39 +
 scripts/testing/test-training-capture.py           |    75 +
 scripts/testing/test-training-ingest-failure.py    |   155 +
 scripts/testing/test-training-loop-trust-gates.py  |    47 +
 .../test-understand-anything-batch-validation.py   |    28 +
 scripts/testing/test-useful-token-metrics.py       |   158 +
 .../testing/test-vector-similarity-search-perf.py  |   409 +
 .../testing/test-vectorization-visualization.py    |    48 +
 scripts/testing/test-verify-python-lock-runtime.py |    94 +
 .../test-vscodium-extension-runtime-guards.py      |    60 +
 scripts/testing/test-vscodium-gpu-mitigation.py    |    34 +
 scripts/testing/test-web-research-lane.py          |   102 +
 scripts/testing/test-workflow-automation.py        |   581 +
 scripts/testing/test-workflow-blueprints.py        |    68 +
 scripts/testing/test-workflow-deviation-broker.py  |   280 +
 scripts/testing/test-workflow-deviation-c1a.py     |   222 +
 .../testing/test-workflow-deviation-contract.py    |   126 +
 .../test-workflow-orchestration-defaults.py        |    69 +
 .../testing/test-workflow-orchestration-policy.py  |   434 +
 scripts/testing/test-workflow-pattern-adoption.py  |    81 +
 scripts/testing/test-workflow-review-gate.py       |   353 +
 .../testing/test-workflow-run-policy-overrides.py  |    43 +
 .../testing/test-workflow-runtime-integration.py   |   422 +
 scripts/testing/test-workflow-shadow-contract.py   |   257 +
 scripts/testing/test-workflow-shadow-migration.py  |   564 +
 scripts/testing/validate-ai-slo-runtime.sh         |   102 +
 scripts/testing/validate-autonomous-loop-gates.sh  |    83 +
 scripts/testing/validate-deploy-doc-flags.sh       |    24 +
 .../validate-deployment-monitoring-alerting.sh     |   527 +
 scripts/testing/validate-echo-colors.sh            |   120 +
 scripts/testing/validate-genai-observability.sh    |    48 +
 scripts/testing/validate-phase-5.2.sh              |    91 +
 .../validate-query-agent-storage-learning.sh       |   343 +
 scripts/testing/validate-runtime-declarative.sh    |   159 +
 scripts/testing/validate-skill-references.sh       |    99 +
 scripts/testing/verify-dashboard-apis.py           |   161 +
 .../verify-flake-first-roadmap-completion.sh       |   724 +
 scripts/testing/verify-self-consistency.py         |    76 +
 scripts/testing/verify-skill-registry.sh           |   120 +
 scripts/upstream/dev                               |   643 +
 scripts/upstream/track                             |   588 +
 scripts/utils/battery-toggle.sh                    |   188 +
 systemd/ai-research-sync.service                   |    13 +
 systemd/ai-research-sync.timer                     |    11 +
 systemd/aidb-backup-postgresql.service             |    34 +
 systemd/aidb-backup-postgresql.timer               |    21 +
 systemd/aidb-backup-qdrant.service                 |    34 +
 systemd/aidb-backup-qdrant.timer                   |    21 +
 systemd/aidb-library-catalog-sync.service          |    28 +
 systemd/aidb-library-catalog-sync.timer            |    13 +
 .../capability-intake-admission-controller.md      |    47 +
 .../capability-intake-github-mcp-readonly.md       |    39 +
 tasks_inbox/capability-intake-local-packs.md       |    20 +
 tasks_inbox/capability-intake-playwright-mcp.md    |    70 +
 tasks_inbox/capability-intake-semgrep-osv-trivy.md |    20 +
 templates/.sops.yaml                               |    28 +
 .../ChatGPT Image Feb 21, 2026, 02_05_57 PM.png    |   Bin 0 -> 3405363 bytes
 templates/Royal Wine-inner.ron                     |   195 +
 templates/Royal Wine.ron                           |   264 +
 .../agentic-workflow/.agent/GLOBAL-RULES.md.tmpl   |    36 +
 .../agentic-workflow/.agent/PROJECT-PRD.md.tmpl    |    47 +
 .../.agent/commands/start-workflow.sh.tmpl         |    65 +
 .../.agent/workflows/intent-contract.json.tmpl     |    15 +
 .../.agent/workflows/phase-01-foundation.md.tmpl   |    29 +
 templates/agentic-workflow/.agents/README.md.tmpl  |    21 +
 .../agentic-workflow/.agents/plans/README.md.tmpl  |    18 +
 .../.agents/plans/phase-template.md.tmpl           |    29 +
 templates/agentic-workflow/.claude/CLAUDE.md.tmpl  |    84 +
 .../.claude/commands/brownfield.md.tmpl            |    10 +
 .../.claude/commands/commit.md.tmpl                |    10 +
 .../.claude/commands/create-prd.md.tmpl            |    19 +
 .../.claude/commands/execute.md.tmpl               |    15 +
 .../.claude/commands/explore-harness.md.tmpl       |    15 +
 .../.claude/commands/plan-feature.md.tmpl          |    14 +
 .../.claude/commands/prime.md.tmpl                 |    45 +
 .../.claude/commands/primer.md.tmpl                |    10 +
 .../.claude/commands/project-init.md.tmpl          |    11 +
 .../agentic-workflow/.claude/settings.json.tmpl    |    40 +
 templates/agentic-workflow/README.md               |    24 +
 .../autonomous-ops-sudoers.example                 |    21 +
 templates/configuration.nix                        |  1282 ++
 templates/flake.lock                               |   188 +
 templates/flake.nix                                |   218 +
 templates/home.nix                                 |  4352 ++++
 templates/mcp-config-template.json                 |    62 +
 templates/mcp-server-template.py                   |   449 +
 templates/mcp-server-template.ts                   |   352 +
 .../mcp-servers/embeddings-service/Dockerfile      |    20 +
 templates/mcp-servers/embeddings-service/server.py |   124 +
 templates/nixos-improvements/README.md             |   484 +
 templates/nixos-improvements/ai-agents.nix         |   339 +
 templates/nixos-improvements/ai-env.nix            |    59 +
 templates/nixos-improvements/hybrid-learning.nix   |   524 +
 .../nixos-improvements/mobile-workstation.nix      |   377 +
 templates/nixos-improvements/networking.nix        |    71 +
 templates/nixos-improvements/optimizations.nix     |   326 +
 templates/nixos-improvements/testing.nix           |   392 +
 templates/nixos-improvements/virtualization.nix    |   274 +
 templates/python-overrides.nix                     |   333 +
 templates/secrets.yaml                             |    59 +
 templates/systemd/ai-stack-startup.service         |    24 +
 templates/vscode/claude-code/mcp_servers.json      |   190 +
 templates/vscode/continue/config.json              |    32 +
 .../.vsixmanifest                                  |    44 +
 .../max-ss.cyberpunk-1.2.14-universal/CHANGELOG.md |   164 +
 .../vscode/max-ss.cyberpunk-1.2.14-universal/CNAME |     1 +
 .../max-ss.cyberpunk-1.2.14-universal/LICENSE.txt  |   674 +
 .../max-ss.cyberpunk-1.2.14-universal/README.md    |   104 +
 .../max-ss.cyberpunk-1.2.14-universal/_config.yml  |     1 +
 .../assets/banner.png                              |   Bin 0 -> 361268 bytes
 .../assets/boost/culture.png                       |   Bin 0 -> 75980 bytes
 .../assets/boost/friendly.png                      |   Bin 0 -> 74515 bytes
 .../assets/boost/levels.png                        |   Bin 0 -> 81913 bytes
 .../assets/boost/lovely.png                        |   Bin 0 -> 90661 bytes
 .../assets/boost/monster.png                       |   Bin 0 -> 85900 bytes
 .../assets/boost/robo-cat.png                      |   Bin 0 -> 87746 bytes
 .../assets/boost/super-star.png                    |   Bin 0 -> 88532 bytes
 .../assets/contributor/avatar_1.png                |   Bin 0 -> 85458 bytes
 .../assets/contributor/avatar_2.png                |   Bin 0 -> 74169 bytes
 .../assets/contributor/avatar_5.png                |   Bin 0 -> 34372 bytes
 .../assets/cyberpunk_banner_2021.png               |   Bin 0 -> 226179 bytes
 ...yberPunk2077-umbra-WindowsTerminal-spin_off.png |   Bin 0 -> 162847 bytes
 ...rpunk-SCARLET-for-Windows-Terminal-spin_off.png |   Bin 0 -> 109587 bytes
 .../assets/hall-of-the-fame/angus_creator.png      |   Bin 0 -> 63691 bytes
 .../hall-of-the-fame/chrysillala_contributor.png   |   Bin 0 -> 56906 bytes
 .../assets/hall-of-the-fame/culture.png            |   Bin 0 -> 75980 bytes
 .../assets/hall-of-the-fame/fin.png                |   Bin 0 -> 70801 bytes
 .../assets/hall-of-the-fame/friendly.png           |   Bin 0 -> 74515 bytes
 .../assets/hall-of-the-fame/hasparus_creator.png   |   Bin 0 -> 65392 bytes
 .../hall-of-the-fame/kleinfreund_contributor.png   |   Bin 0 -> 67659 bytes
 .../assets/hall-of-the-fame/kuerme_contributor.png |   Bin 0 -> 54603 bytes
 .../assets/hall-of-the-fame/levels.png             |   Bin 0 -> 81913 bytes
 .../assets/hall-of-the-fame/lovely.png             |   Bin 0 -> 90661 bytes
 .../assets/hall-of-the-fame/max-ss_creator.png     |   Bin 0 -> 76771 bytes
 .../assets/hall-of-the-fame/mikevromen_creator.png |   Bin 0 -> 67951 bytes
 .../hall-of-the-fame/mkoppmann_contributor.png     |   Bin 0 -> 66442 bytes
 .../assets/hall-of-the-fame/monster.png            |   Bin 0 -> 85900 bytes
 .../assets/hall-of-the-fame/murderlon_creator.png  |   Bin 0 -> 66434 bytes
 .../assets/hall-of-the-fame/robo-cat.png           |   Bin 0 -> 87746 bytes
 .../assets/hall-of-the-fame/super-star.png         |   Bin 0 -> 88532 bytes
 .../assets/hall-of-the-fame/szul_creator.png       |   Bin 0 -> 67248 bytes
 .../assets/image/Reminders.png                     |   Bin 0 -> 4544 bytes
 .../assets/image/bonus.png                         |   Bin 0 -> 4247 bytes
 .../assets/image/fin.png                           |   Bin 0 -> 70801 bytes
 .../assets/image/hall_of_the_fame.png              |   Bin 0 -> 7394 bytes
 .../assets/image/spin_off.png                      |   Bin 0 -> 3903 bytes
 .../assets/image/stars.png                         |   Bin 0 -> 12675 bytes
 .../assets/image/why_cyberpunk.png                 |   Bin 0 -> 6900 bytes
 .../assets/preview-scarlet.png                     |   Bin 0 -> 192677 bytes
 .../assets/preview-umbra.png                       |   Bin 0 -> 189758 bytes
 .../assets/preview.png                             |   Bin 0 -> 194150 bytes
 ...yberPunk2077-umbra-WindowsTerminal-spin_off.png |   Bin 0 -> 162847 bytes
 ...rpunk-SCARLET-for-Windows-Terminal-spin_off.png |   Bin 0 -> 109587 bytes
 .../assets/spin-off/chrome-theme.png               |   Bin 0 -> 67251 bytes
 .../assets/spin-off/hyper-cyberpunk-spin_off.png   |   Bin 0 -> 277818 bytes
 .../assets/spin-off/iterm-preview.png              |   Bin 0 -> 700135 bytes
 .../assets/spin-off/iterm-theme.png                |   Bin 0 -> 427636 bytes
 .../assets/version-0-0-2/after.png                 |   Bin 0 -> 43059 bytes
 .../assets/version-0-0-2/before.png                |   Bin 0 -> 43153 bytes
 .../assets/version-0-1-0/after.png                 |   Bin 0 -> 54486 bytes
 .../assets/version-0-1-0/before.png                |   Bin 0 -> 39835 bytes
 .../assets/version-0-1-0/peekView.png              |   Bin 0 -> 226813 bytes
 .../cyberpunk_logo_2021.png                        |   Bin 0 -> 99925 bytes
 .../max-ss.cyberpunk-1.2.14-universal/icon.png     |   Bin 0 -> 133529 bytes
 .../max-ss.cyberpunk-1.2.14-universal/index.html   |   123 +
 .../max-ss.cyberpunk-1.2.14-universal/package.json |    51 +
 .../styles.scssc                                   |   Bin 0 -> 54691 bytes
 .../_mixins.scssc                                  |   Bin 0 -> 10265 bytes
 .../_variables.scssc                               |   Bin 0 -> 3543 bytes
 .../flex-layout.scssc                              |   Bin 0 -> 50894 bytes
 .../fonts.scssc                                    |   Bin 0 -> 4615 bytes
 .../page/common/_mixins.scss                       |    34 +
 .../page/common/_variables.scss                    |    16 +
 .../page/common/flex-layout.scss                   |   207 +
 .../page/common/fonts.scss                         |    18 +
 .../page/common/fonts/blender_bold.woff            |   Bin 0 -> 29632 bytes
 .../page/common/fonts/blender_bold_italic.woff     |   Bin 0 -> 29604 bytes
 .../page/common/fonts/blender_book.woff            |   Bin 0 -> 30028 bytes
 .../page/common/fonts/blender_book_italic.woff     |   Bin 0 -> 31384 bytes
 .../page/common/fonts/blender_heavy.woff           |   Bin 0 -> 23816 bytes
 .../page/common/fonts/blender_medium.woff          |   Bin 0 -> 29088 bytes
 .../page/common/fonts/blender_medium_italic.woff   |   Bin 0 -> 30232 bytes
 .../page/common/fonts/blender_thin.woff            |   Bin 0 -> 29080 bytes
 .../page/common/images/Github.svg                  |     1 +
 .../page/common/images/Spotify.svg                 |     1 +
 .../page/common/images/Twitter.svg                 |     1 +
 .../page/common/images/bg_decoration.svg           |     1 +
 .../page/common/images/logo.svg                    |     1 +
 .../page/common/images/preview.png                 |   Bin 0 -> 191995 bytes
 .../page/common/images/quotes.svg                  |     1 +
 .../page/common/outsiders.scss                     |     0
 .../page/index.css                                 |   499 +
 .../page/index.css.map                             |     7 +
 .../page/styles.scss                               |   215 +
 .../themes/cyberpunk-color-theme.json              |   943 +
 .../themes/cyberpunk-scarlet-color-theme.json      |   855 +
 .../themes/cyberpunk-umbra-color-theme.json        |   831 +
 .../wiki/boost.md                                  |    79 +
 templates/vscode/settings.json                     |   242 +
 .../test-api-key-security.sh                       |   250 +
 .../test-connection-pool-exhaustion.sh             |   303 +
 .../test-agent-progressive-disclosure.sh           |   342 +
 tests/chaos-engineering/README.md                  |   408 +
 tests/chaos-engineering/run-all-chaos-tests.sh     |   310 +
 tests/failure-scenario-tests.sh                    |   231 +
 .../capability-plan/missing-external-cli.json      |    50 +
 .../capability-plan/missing-repo-tool.json         |    50 +
 .../runtime-diagnose/apparmor-healthy.json         |     5 +
 .../fixtures/runtime-diagnose/llama-unhealthy.json |     5 +
 tests/fixtures/runtime-plan/diagnoses-healthy.json |    15 +
 .../runtime-plan/diagnoses-suppression.json        |    14 +
 .../fixtures/runtime-plan/diagnoses-unhealthy.json |    15 +
 tests/fixtures/runtime-plan/qa-healthy.json        |    11 +
 tests/fixtures/runtime-plan/qa-unhealthy.json      |    11 +
 .../runtime-plan/remediation-blocked-plan.json     |    12 +
 .../remediation-command-metadata-plan.json         |    31 +
 .../runtime-plan/remediation-safe-plan.json        |    73 +
 .../runtime-plan/remediation-unsafe-live-plan.json |    15 +
 .../integration/phase-35-harness-integration.bats  |    66 +
 tests/integration/test-interaction-history.py      |    96 +
 tests/integration/test-phase1-dag-context.py       |    89 +
 tests/integration/test-phase2-drop-zones.py        |    76 +
 tests/integration/test-phase3-arbitrage.py         |    56 +
 tests/integration/test-phase4-observability.py     |    46 +
 .../test-phase5-production-hardening.py            |    33 +
 tests/integration/test_cli.bats                    |    16 +
 tests/integration/test_mcp_contracts.py            |   247 +
 tests/integration/test_rag_retrieval.py            |   242 +
 tests/integration/test_routing.py                  |   270 +
 tests/progressive-disclosure-validation.py         |   560 +
 tests/run-integration-tests.sh                     |    29 +
 tests/run-unit-tests.sh                            |    22 +
 tests/test_progressive_disclosure.py               |    35 +
 tests/test_unified_health_tool.py                  |    29 +
 tests/unit/ai-stack-troubleshoot.bats              |    17 +
 tests/unit/aqd-parity.bats                         |    48 +
 tests/unit/concurrent-lock.bats                    |   175 +
 tests/unit/discover-system-facts.bats              |   103 +
 tests/unit/error-codes.bats                        |   113 +
 tests/unit/fs-integrity-helpers.bats               |    43 +
 tests/unit/retry-backoff.bats                      |   102 +
 tests/unit/secrets-sops.bats                       |    70 +
 tests/unit/test_dashboard_service_health_config.py |    25 +
 tests/unit/test_helper.bash                        |    23 +
 .../test_phase_3_3_service_config_retrieval.py     |   357 +
 tests/unit/test_phase_4_1_alerting_flow.py         |    83 +
 tests/unit/test_phase_4_2_learning_flow.py         |    29 +
 ...est_phase_4_3_security_audit_compliance_flow.py |    94 +
 .../test_phase_4_integrated_acceptance_runner.py   |    19 +
 tests/unit/test_route_handler_collection_policy.py |   116 +
 tests/unit/validation-input.bats                   |   298 +
 5948 files changed, 1304704 insertions(+)
47e03ea9 feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis
 .agent/research/maturity-gap-analysis-2026-08.md   | 106 +++++++
 ai-stack/local-agents/agent_executor.py            |  10 +-
 .../local-agents/builtin_tools/file_operations.py  | 136 ++++++++-
 scripts/testing/test-write-region.py               | 331 +++++++++++++++++++++
 4 files changed, 578 insertions(+), 5 deletions(-)
ae9029ef fix(local-agent): strip tool-call JSON-envelope artifact from run_command args
 .agent/memory/issues-backlog.md                    |  5 +++++
 ai-stack/local-agents/builtin_tools/shell_tools.py | 10 ++++++++++
 2 files changed, 15 insertions(+)
950f56e4 feat(local-agent): LLM record/replay harness — deterministic offline validation
 .agents/plans/record-replay-harness/DESIGN.md |  87 ++++
 ai-stack/local-agents/agent_executor.py       |  61 ++-
 ai-stack/local-agents/llm_cassette.py         | 347 ++++++++++++++++
 scripts/testing/aq-replay-bench               | 332 +++++++++++++++
 scripts/testing/test-llm-cassette.py          | 575 ++++++++++++++++++++++++++
 5 files changed, 1400 insertions(+), 2 deletions(-)
4650b1e6 chore: gitignore LLM cassette run-artifacts dir
 .gitignore | 3 +++
 1 file changed, 3 insertions(+)

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx -c 'rg -n \"def _object_rule|_object_rule\\(|frequency_penalty|first_call|512|intervention|no_action|edit_feedback|write_region|_call_llama|cassette|replay|request_key|artifact|re\\.sub|MAX_|max_iterations|while |for .*range\" scripts/ai/lib/grammar_cache.py ai-stack/local-agents/builtin_tools/shell_tools.py ai-stack/local-agents/llm_cassette.py ai-stack/local-agents/agent_executor.py scripts/testing/test-tool-call-grammar.py scripts/testing/test-llm-cassette.py scripts/testing/test-write-region.py'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 813ms:
338 matches in 7F:

scripts/testing/test-llm-cassette.py (125):
  3: Tests for the LLM record/replay cassette harness.
  6: ai-stack/local-agents/llm_cassette.py   — request_key, Cassette, mode/path/on_miss
  7: ai-stack/local-agents/agent_executor.py — the two _call_llama wiring points
  9: Design doc (authoritative): .agents/plans/record-replay-harness/DESIGN.md
  12: (a) request_key is stable + excludes volatile fields
  15: (d) replay mode returns recorded content WITHOUT touching the network, in BOTH
  16: the streaming and legacy (non-streaming) _call_llama branches
  18: (f) mode=off is a strict no-op — live HTTP path taken, cassette file never written
  24: Bonus (DoD payoff demonstration, not just a unit check): a synthetic cassette row
  26: `\\n},\\n` artifact this session hit live (the local model's streaming/GBNF tool-call
  ... +115 more
ai-stack/local-agents/agent_executor.py (109):
  29: # Operator intervention channel (first cut) — lazily loaded, fails open so a missing/broken
  68: from shared.llm_config import build_llama_payload, AGENT_TOOL_CALL_MAX_TOKENS, AGENT_TASK_MAX_TOKENS  # noqa: E402
  83: # Record/replay harness (velocity multiplier — deterministic offline replay of local
  84: # inference; see .agents/plans/record-replay-harness/DESIGN.md). Default-OFF
  85: # (AQ_LLM_CASSETTE_MODE unset -> "off") is a strict no-op in _call_llama; wrapped in
  88: import llm_cassette  # noqa: E402  (same dir: ai-stack/local-agents/)
  90: llm_cassette = None  # type: ignore
  268: # spans (~1200 tok) + a whole 17KB (~4.3K tok) file blew LLAMA_MAX_PROMPT_CHARS=24000.
  273: # edit-forcing intervention (delivered as the read_file tool result, role:"tool") instead
  276: # complete. A SECOND breach (re-read after the intervention) still aborts as before.
  ... +99 more
ai-stack/local-agents/llm_cassette.py (55):
  3: LLM record/replay cassette — deterministic, instant replay of local-agent inference.
  7: exhaustion, etc). This module lets `_call_llama` in agent_executor.py record real model
  8: outputs once, then replay them deterministically and offline — so harness fixes and
  9: config A/Bs (grammar on/off, write_region, PTC) validate in seconds, not tens of minutes.
  11: Design doc (authoritative): .agents/plans/record-replay-harness/DESIGN.md
  16: cassette at AQ_LLM_CASSETTE.
  17: replay         — NO network. Returns the cassette's recorded content for the
  20: replay-record  — replay on hit; live + record on miss (grows a cassette
  24: internal error (corrupt cassette line, unwritable path, etc) is logged and swallowed,
  27: AQ_LLM_CASSETTE_ON_MISS=error (the default in `replay` mode) — that is a signal, not a
  ... +45 more
scripts/testing/test-write-region.py (31):
  3: Regression test for the write_region line-range rewrite tool (2026-08-20).
  16: Fix under test: `write_region(file_path, start_line, end_line, new_text)`
  32: (d) a successful write_region call counts as an edit for the no-action
  105: result = await file_operations.write_region_handler(
  130: result = await file_operations.write_region_handler(
  146: result = await file_operations.write_region_handler(
  155: result2 = await file_operations.write_region_handler(
  162: result3 = await file_operations.write_region_handler(
  169: result4 = await file_operations.write_region_handler(
  180: result = await file_operations.write_region_handler(
  ... +21 more
scripts/testing/test-tool-call-grammar.py (12):
  87: while self.i < self.n:
  99: while self.i < self.n:
  104: while self.i < self.n and self.text[self.i] != "\n":
  114: while self.i < self.n and (self.text[self.i].isalnum() or self.text[self.i] in "_-"):
  134: while self._peek() == "|":
  143: while True:
  162: while self.i < self.n and self.text[self.i].isdigit():
  193: while self.i < self.n and self.text[self.i] != '"':
  215: while self.i < self.n and self.text[self.i] != "]":
  246: in_range = any(lo <= c <= hi for lo, hi in expr.ranges)
  ... +2 more
ai-stack/local-agents/builtin_tools/shell_tools.py (3):
  139: # Strip trailing tool-call JSON artifacts before ANY check. The local model's
  146: # cleanup, not a security relaxation. Root cause: local-agent-tool-call-json-artifact-leak.
  147: command = re.sub(r"[\s}\]\",]+$", "", command)
scripts/ai/lib/grammar_cache.py (3):
  64: while len(self._entries) > self.config.max_size:
  143: return _object_rule(schema)
  158: def _object_rule(schema: Mapping[str, Any]) -> str:
[lean-ctx: 9982→1287 tok, -87%]

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx -c 'nl -ba scripts/ai/lib/grammar_cache.py | sed -n \"120,230p\"' && lean-ctx -c 'nl -ba ai-stack/local-agents/builtin_tools/shell_tools.py | sed -n \"1,230p\"' && lean-ctx -c 'nl -ba ai-stack/local-agents/llm_cassette.py | sed -n \"1,390p\"' && lean-ctx -c 'nl -ba ai-stack/local-agents/agent_executor.py | sed -n \"1,390p\"'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 2577ms:
73 lines → 73 unique
last 15 unique lines:
178	    `text` is the exact raw output text desired (e.g. a JSON-encoded key/value
179	    like `"function"`, quote characters included). Backslashes and double quotes
180	    in `text` are backslash-escaped so they survive as literal characters inside
181	    the GBNF string rather than terminating it early — the fix for the bug where
182	    `json.dumps(name)[1:-1]` stripped the JSON quotes and produced an unquoted
183	    GBNF literal (matching bare `arguments` instead of `"arguments"`).
184	    """
185	    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
186	    return f'"{escaped}"'
187
188
189	def _schema_mapping(value: Any) -> Mapping[str, Any]:
190	    if isinstance(value, Mapping):
191	        return value
192	    return {}
[lean-ctx: 993→197 tok, -80%]
230 lines → 230 unique
7 errors:
  136	            "error": str (if failed)
  152	        return {"success": False, "error": "Empty command"}
  159	            "error": "Command rejected: shell control/metacharacter sequences are not allowed",
  167	            "error": f"Command '{base_cmd}' not in safe list: {', '.join(sorted(SAFE_COMMANDS))}",
  187	            except Exception as nsjail_exc:
  ... +2 more errors
last 15 unique lines:
216	        if _RTK_ENABLED:
217	            try:
218	                rtk_argv = [_RTK_BIN] + shlex.split(command)
219	                result = subprocess.run(
220	                    rtk_argv,
221	                    capture_output=True,
222	                    text=True,
223	                    timeout=timeout_seconds,
224	                )
225	                return {
226	                    "success": result.returncode == 0,
227	                    "stdout": result.stdout,
228	                    "stderr": result.stderr,
229	                    "returncode": result.returncode,
230	                    "compressed": True,
[lean-ctx: 2779→229 tok, -92%]
347 lines → 347 unique
26 errors:
  19	                     (error [default] | passthrough | empty).
  24	internal error (corrupt cassette line, unwritable path, etc) is logged and swallowed,
  25	never propagated into the caller's live inference path. The one deliberate exception
  27	AQ_LLM_CASSETTE_ON_MISS=error (the default in `replay` mode) — that is a signal, not a
  58	class ReplayMiss(Exception):
  ... +21 more errors
last 15 unique lines:
333	    modes. No-op in off/replay. Never raises."""
334	    m = mode()
335	    if m not in ("record", "replay-record"):
336	        return
337	    try:
338	        cass = get_cassette()
339	        if cass is None:
340	            logger.warning(
341	                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — not recording", m
342	            )
343	            return
344	        key = request_key(payload, task_type)
345	        cass.record(key, payload, content, tokens, meta)
346	    except Exception:
347	        logger.exception("llm_cassette: maybe_record internal error — continuing without recording")
[lean-ctx: 4276→272 tok, -94%]
[lean-ctx] WARNING: compression removed >95% of content, returning original
     1	#!/usr/bin/env python3
     2	"""
     3	Local Agent Executor - Workflow Integration
     4	
     5	Enables local llama.cpp agents to execute tasks with tool use:
     6	- Tool-augmented inference
     7	- Multi-step task execution
     8	- Result validation
     9	- Performance tracking
    10	- Automatic failover to remote agents
    11	
    12	Part of Phase 11 Batch 11.3: Workflow Integration
    13	"""
    14	
    15	import asyncio
    16	import difflib
    17	import json
    18	import logging
    19	import os
    20	import re
    21	import sys
    22	import time
    23	from dataclasses import dataclass, field
    24	from datetime import datetime, timezone
    25	from enum import Enum
    26	from pathlib import Path
    27	from typing import Any, Dict, List, Optional, Tuple
    28	
    29	# Operator intervention channel (first cut) — lazily loaded, fails open so a missing/broken
    30	# control module never disrupts the agent loop.
    31	_CONTROL_MOD: Any = None
    32	
    33	
    34	def _control_channel():
    35	    global _CONTROL_MOD
    36	    if _CONTROL_MOD is None:
    37	        try:
    38	            from importlib.machinery import SourceFileLoader
    39	            _CONTROL_MOD = SourceFileLoader(
    40	                "control_channel", str(Path(__file__).with_name("control_channel.py"))
    41	            ).load_module()
    42	        except Exception:
    43	            _CONTROL_MOD = False
    44	    return _CONTROL_MOD or None
    45	
    46	import httpx
    47	
    48	# shared/ lives at ai-stack/mcp-servers/shared/ — add parent to path once.
    49	_MCP_SERVERS_PATH = str(Path(__file__).resolve().parents[1] / "mcp-servers")
    50	if _MCP_SERVERS_PATH not in sys.path:
    51	    sys.path.insert(0, _MCP_SERVERS_PATH)
    52	_AI_LIB_PATH = str(Path(__file__).resolve().parents[2] / "scripts" / "ai" / "lib")
    53	if _AI_LIB_PATH not in sys.path:
    54	    sys.path.insert(0, _AI_LIB_PATH)
    55	
    56	# Phase 184: Antigravity Collective Integration
    57	# lib/l4-coord uses a hyphen — not importable via dotted path. Add the agents
    58	# subdir directly so imports work without renaming the on-disk directory.
    59	_L4_COORD_AGENTS = str(Path(__file__).resolve().parents[2] / "lib" / "l4-coord" / "agents")
    60	if _L4_COORD_AGENTS not in sys.path:
    61	    sys.path.insert(0, _L4_COORD_AGENTS)
    62	
    63	from collaborative_planning import (  # noqa: E402
    64	    CollaborativePlanning, PlanningMode, PhaseType
    65	)
    66	from collective_memory import CollectiveMemory  # noqa: E402
    67	
    68	from shared.llm_config import build_llama_payload, AGENT_TOOL_CALL_MAX_TOKENS, AGENT_TASK_MAX_TOKENS  # noqa: E402
    69	from tool_registry import ToolCall, ToolRegistry, get_registry
    70	from context_risk import compact_context_if_needed
    71	
    72	# P2 (closed-local-improvement-loop): GBNF-constrained tool-call decoding. AQ_LOCAL_GBNF remains
    73	# DEFAULT OFF. Values true/1/on keep the original all-turn grammar plumbing for benchmarking; value
    74	# "repair" constrains only a malformed tool-call retry so final-answer turns are unaffected.
    75	try:
    76	    import tool_grammar  # noqa: E402  (same dir: ai-stack/local-agents/)
    77	except Exception:  # noqa: BLE001 — never let an optional import break the executor
    78	    tool_grammar = None  # type: ignore
    79	_LOCAL_GBNF_MODE = os.environ.get("AQ_LOCAL_GBNF", "").strip().lower()
    80	_LOCAL_GBNF_ALWAYS_ENABLED = _LOCAL_GBNF_MODE in ("1", "true", "yes", "on")
    81	_LOCAL_GBNF_REPAIR_ENABLED = _LOCAL_GBNF_ALWAYS_ENABLED or _LOCAL_GBNF_MODE in ("repair", "retry")
    82	
    83	# Record/replay harness (velocity multiplier — deterministic offline replay of local
    84	# inference; see .agents/plans/record-replay-harness/DESIGN.md). Default-OFF
    85	# (AQ_LLM_CASSETTE_MODE unset -> "off") is a strict no-op in _call_llama; wrapped in
    86	# try/except so a broken/missing module never disrupts live inference.
    87	try:
    88	    import llm_cassette  # noqa: E402  (same dir: ai-stack/local-agents/)
    89	except Exception:  # noqa: BLE001 — never let an optional import break the executor
    90	    llm_cassette = None  # type: ignore
    91	
    92	# P1 (closed-local-improvement-loop): capture local failures as labeled training samples.
    93	try:
    94	    import training_capture  # noqa: E402
    95	except Exception:  # noqa: BLE001
    96	    training_capture = None  # type: ignore
    97	
    98	# Slice 2b (local-embed-context): embed-backed semantic context cache for the prune
    99	# path — best-effort, fail-open. Lives at ai-stack/local-agents/context_cache.py
   100	# (same dir as this module; see F5 in SLICE2-LOCAL-DECOMPOSITION.md).
   101	try:
   102	    import context_cache  # noqa: E402  (same dir: ai-stack/local-agents/)
   103	except Exception:  # noqa: BLE001 — never let an optional import break the executor
   104	    context_cache = None  # type: ignore
   105	
   106	# Slice 0.2 (local-context-supply-chain): the read_file gate reuses context_assembler's
   107	# Tier-0 file-chunking helpers (line-aware chunk + '[path:start-end]' citation framing)
   108	# rather than reimplementing them — same embed/Qdrant round-trip pattern, no new code
   109	# path. Best-effort import; the gate fails closed (bounded head, never raw oversized
   110	# file) when this is unavailable — see _gate_large_file_content.
   111	try:
   112	    from context_assembler import (  # noqa: E402  (same dir: ai-stack/local-agents/)
   113	        _chunk_file as _rf_chunk_file,
   114	        _parse_chunk_citation as _rf_parse_chunk_citation,
   115	    )
   116	except Exception:  # noqa: BLE001
   117	    _rf_chunk_file = None  # type: ignore
   118	    _rf_parse_chunk_citation = None  # type: ignore
   119	
   120	# Phase 164B — MIC-G context sanitizer: scrub prompt-injection patterns from tool results
   121	# before they are injected into the LLM context window.  Import is best-effort; if the
   122	# security module is unavailable (e.g. minimal install) the agent continues without it.
   123	try:
   124	    _SECURITY_PATH = str(Path(__file__).resolve().parents[1] / "security")
   125	    if _SECURITY_PATH not in sys.path:
   126	        sys.path.insert(0, _SECURITY_PATH)
   127	    from context_sanitizer import sanitize_tool_result as _sanitize_tool_result
   128	    _CONTEXT_SANITIZER_AVAILABLE = True
   129	except ImportError:
   130	    _CONTEXT_SANITIZER_AVAILABLE = False
   131	    _sanitize_tool_result = None  # type: ignore[assignment]
   132	
   133	logger = logging.getLogger(__name__)
   134	
   135	_TELEMETRY_DIR = Path(os.getenv("TELEMETRY_DIR", "/var/lib/ai-stack/hybrid/telemetry"))
   136	# Agent events are written to the user-spool path (.agents/telemetry/hybrid-events.jsonl)
   137	# rather than the service-owned /var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl.
   138	# Reason: hybrid-events.jsonl is owned by ai-hybrid:ai-stack with 0640 permissions —
   139	# aq-agent-loop runs as hyperd (ai-stack group, read-only) so every direct write
   140	# silently fails with PermissionError. training_ingest.py reads BOTH paths via
   141	# USER_EVENTS_SPOOL, so agent telemetry lands in training data without privilege issues.
   142	_REPO_ROOT_PATH = Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parents[2]))
   143	_HYBRID_EVENTS = _REPO_ROOT_PATH / ".agents" / "telemetry" / "hybrid-events.jsonl"
   144	_HYBRID_EVENTS.parent.mkdir(parents=True, exist_ok=True)
   145	
   146	# Phase E — agent-run-events.jsonl path: prefer harness_paths SSOT; fall back to absolute path.
   147	# Never use a relative path — agent_executor.py may run from Nix store (EROFS).
   148	try:
   149	    _HP_PATH = str(Path(__file__).resolve().parent)
   150	    if _HP_PATH not in sys.path:
   151	        sys.path.insert(0, _HP_PATH)
   152	    from harness_paths import AGENT_RUN_EVENTS as _AGENT_RUN_EVENTS_PATH
   153	except ImportError:
   154	    _AGENT_RUN_EVENTS_PATH = Path(os.environ.get(  # type: ignore[assignment]
   155	        "AQ_AGENT_RUN_EVENTS_PATH",
   156	        "/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl",
   157	    ))
   158	
   159	# Per-task monotonic sequence counter for agent-run-events.jsonl.
   160	# Keyed by task_id. Cleaned up on agent_complete/agent_failed to prevent unbounded growth.
   161	_agent_event_seq: dict[str, int] = {}
   162	
   163	_CODE_TASK_RE = re.compile(
   164	    r"\b(implement|write|code|script|function|class|patch|refactor|debug|fix|test)\b",
   165	    re.IGNORECASE,
   166	)
   167	
   168	# ── Phase A.6: keyword sets for per-iteration tool hot-swap ──────────────────
   169	# Mirror the sets in local_agent_runtime.py so both runtimes share the same
   170	# signal vocabulary.  Tools described as text in the system prompt are refreshed
   171	# by rebuilding messages[0] after each tool call result.
   172	_AEXEC_MEMORY_KW = frozenset(["remember", "store", "save", "record", "note", "memorize", "persist"])
   173	_AEXEC_WORKFLOW_KW = frozenset(["workflow", "pipeline", "prsi", "self-improve", "optimization"])
   174	_AEXEC_DELEGATE_KW = frozenset(["delegate", "remote", "escalate", "assign", "handoff", "codex", "claude", "opencode"])
   175	_AEXEC_HEALTH_KW = frozenset(["health", "status", "check", "verify", "diagnose", "monitor", "running", "alive"])
   176	_AEXEC_MESH_KW = frozenset(["mesh", "agents", "team", "capabilities", "federated", "who can"])
   177	_AEXEC_OBJECTIVE_KW = frozenset(["objective", "what to work", "no task", "need direction", "what should", "propose", "suggest work"])
   178	
   179	# Tool names that are always present (never hot-swapped in/out).
   180	# Slice 0.2 (local-context-supply-chain): git_add/git_commit removed — local NEVER
   181	# commits (structural, not prompt-hoped). See _AEXEC_COMMIT_TOOLS + AQ_LOCAL_ALLOW_COMMIT.
   182	_AEXEC_ALWAYS_TOOLS: frozenset[str] = frozenset(["read_file", "write_file", "edit_file", "run_command"])
   183	
   184	# Commit tools — excluded from the model-visible tool schema AND blocked at the point
   185	# of execution (belt-and-suspenders: the SI-slice system prompt names them by name, so
   186	# a schema-only filter would not stop a call the model emits anyway). Gated behind
   187	# AQ_LOCAL_ALLOW_COMMIT (default off) rather than deleted — the handlers/registration
   188	# in builtin_tools/git_tools.py are untouched.
   189	_AEXEC_COMMIT_TOOLS: frozenset[str] = frozenset(["git_add", "git_commit"])
   190	# Tools eligible for hot-swap injection keyed by the keyword set that triggers them.
   191	_AEXEC_HOTSWAP_MAP: list[tuple[frozenset[str], list[str]]] = [
   192	    (_AEXEC_MEMORY_KW,    ["store_memory"]),
   193	    (_AEXEC_WORKFLOW_KW,  ["get_workflow_status", "execute_workflow"]),
   194	    (_AEXEC_DELEGATE_KW,  ["delegate_to_remote"]),
   195	    (_AEXEC_HEALTH_KW,    ["harness_health"]),
   196	    (_AEXEC_MESH_KW,      ["mesh_discovery"]),
   197	    (_AEXEC_OBJECTIVE_KW, ["discover_objectives"]),
   198	]
   199	
   200	# Tools that gate the loop: after one of these returns, inject a synthesis nudge
   201	# and return immediately instead of continuing the tool call loop.
   202	# This prevents the agent from taking action before the user approves a proposal.
   203	_TERMINAL_TOOLS: frozenset[str] = frozenset({"discover_objectives"})
   204	
   205	
   206	def _refresh_active_tools(
   207	    tool_name: str,
   208	    result_text: str,
   209	    current_tools: List[Dict],
   210	    all_tools: List[Dict],
   211	    max_tools: int = 8,
   212	) -> List[Dict]:
   213	    """Hot-swap active tool set for agent_executor based on tool result content.
   214	
   215	    Monotonic expansion: never removes already-active tools.
   216	    all_tools is the full registry snapshot — source of new schemas.
   217	    max_tools is generous (8) here because tool descriptions are text, not JSON schemas.
   218	    """
   219	    current_names = {t["name"] for t in current_tools}
   220	    result_lower = result_text.lower()
   221	    additions: list[str] = []
   222	
   223	    for kw_set, candidates in _AEXEC_HOTSWAP_MAP:
   224	        if any(k in result_lower for k in kw_set):
   225	            for candidate in candidates:
   226	                if candidate not in current_names:
   227	                    additions.append(candidate)
   228	
   229	    if not additions:
   230	        return current_tools
   231	
   232	    # Build lookup from full registry
   233	    all_by_name = {t["name"]: t for t in all_tools}
   234	    result_tools = list(current_tools)
   235	    for name in additions:
   236	        if len(result_tools) >= max_tools:
   237	            break
   238	        if name in all_by_name and name not in current_names:
   239	            result_tools.append(all_by_name[name])
   240	            current_names.add(name)
   241	    return result_tools
   242	
   243	
   244	def _env_flag(name: str, default: bool) -> bool:
   245	    """Parse a boolean environment flag."""
   246	    value = os.getenv(name)
   247	    if value is None:
   248	        return default
   249	    return value.strip().lower() in {"1", "true", "yes", "on"}
   250	
   251	
   252	def _env_float(name: str, default: float) -> float:
   253	    """Parse a float environment setting with fallback."""
   254	    value = os.getenv(name)
   255	    if value is None:
   256	        return default
   257	    try:
   258	        return float(value)
   259	    except ValueError:
   260	        logger.warning("Invalid %s=%r, using default %.2f", name, value, default)
   261	        return default
   262	
   263	
   264	# ── Slice 0.2 (local-context-supply-chain) — enforcement flags ──────────────────
   265	# read_file gate: kill switch AQ_READ_FILE_GATE=0 restores pre-0.2 whole-file behavior.
   266	_READ_FILE_GATE_ENABLED: bool = _env_flag("AQ_READ_FILE_GATE", True)
   267	# ~1500 tok at ~4 chars/tok — matches the DESIGN.md AFTER-run-1 finding: front-loaded
   268	# spans (~1200 tok) + a whole 17KB (~4.3K tok) file blew LLAMA_MAX_PROMPT_CHARS=24000.
   269	_READ_FILE_GATE_CHAR_BUDGET: int = int(os.getenv("AQ_READ_FILE_GATE_CHARS", "6000"))
   270	# Structural no-commit: local NEVER commits by default. Escape hatch, not deletion.
   271	_LOCAL_ALLOW_COMMIT: bool = _env_flag("AQ_LOCAL_ALLOW_COMMIT", False)
   272	# Repeated-read stagnation: on the FIRST threshold breach for a file, inject a one-shot
   273	# edit-forcing intervention (delivered as the read_file tool result, role:"tool") instead
   274	# of aborting immediately. The relevant code is already front-loaded verbatim in context
   275	# under "## Relevant prior knowledge" — the abort was throwing away tasks local could
   276	# complete. A SECOND breach (re-read after the intervention) still aborts as before.
   277	# Kill switch AQ_REREAD_INTERVENTION=0 restores the plain-abort behavior.
   278	_REREAD_INTERVENTION_ENABLED: bool = _env_flag("AQ_REREAD_INTERVENTION", True)
   279	
   280	# No-action stagnation: on implementer/edit tasks, the model sometimes returns a
   281	# prose PLAN with no parseable tool call at all ("Thought: I would change X so
   282	# that...") and the loop — finding no tool call — treats that as the final
   283	# answer and completes with zero edits. The task's whole point was to EDIT a
   284	# file, so accepting narration as completion is a silent failure. On the FIRST
   285	# such prose-only response (implementer task, zero successful edits so far,
   286	# not a refusal), inject a one-shot corrective nudge instead of completing. A
   287	# SECOND prose-only response still completes as before (never loop forever).
   288	# Kill switch AQ_NOACTION_INTERVENTION=0 restores the plain-completion behavior.
   289	_NOACTION_INTERVENTION_ENABLED: bool = _env_flag("AQ_NOACTION_INTERVENTION", True)
   290	
   291	# Edit-failure feedback: now that the tool-call grammar is fixed, the dominant
   292	# local-agent failure mode is edit_file failing on an old_string byte-mismatch
   293	# (the model paraphrases, or reconstructs old_string from a partial view) and
   294	# then blindly retrying the same mismatch until the task hits its time cap
   295	# (measured: a 12-task dogfood run with grammar ON — ~80% of tasks failed this
   296	# way; example: 1 edit_file attempt, 3 mismatch failures, no edit landed). On
   297	# the FIRST such mismatch failure for a given target file, inject the file's
   298	# EXACT current text for the region the model was trying to edit as the tool
   299	# result (instead of the bare failure) so the model can copy a byte-matching
   300	# old_string on retry. Bounded to _EDIT_FEEDBACK_MAX_PER_FILE fires per file so
   301	# a persistently-failing edit still eventually ends rather than looping
   302	# forever. Kill switch AQ_EDIT_FEEDBACK=0 restores the plain-failure behavior.
   303	_EDIT_FEEDBACK_ENABLED: bool = _env_flag("AQ_EDIT_FEEDBACK", True)
   304	_EDIT_FEEDBACK_MAX_PER_FILE: int = int(os.getenv("AQ_EDIT_FEEDBACK_MAX_PER_FILE", "2"))
   305	_EDIT_FEEDBACK_CHAR_BUDGET: int = int(
   306	    os.getenv("AQ_EDIT_FEEDBACK_CHARS", str(_READ_FILE_GATE_CHAR_BUDGET))
   307	)
   308	
   309	# Substrings the edit_file/write_file handlers use to signal an old_string
   310	# byte-mismatch specifically (vs. a different failure class — file-not-found,
   311	# permission, path-validation, OSError — none of which are fixable by showing
   312	# the model more of the file, so those fall through to the plain failure).
   313	_EDIT_MISMATCH_SIGNAL_PHRASES: tuple[str, ...] = (
   314	    "old_string not found", "not found in", "no replacement made",
   315	    "does not match", "did not match",
   316	)
   317	
   318	# Heuristic substrings indicating the model is explicitly declining/stopping
   319	# rather than narrating a plan it forgot to execute. Kept conservative and
   320	# lowercase-matched — false negatives (treated as a plan) just cost one nudge
   321	# turn; false positives (treated as a refusal) would let a real stall through,
   322	# so favor recognizing genuine refusal language.
   323	_REFUSAL_SIGNAL_PHRASES: tuple[str, ...] = (
   324	    "cannot safely", "can't safely", "unable to safely", "not safe to",
   325	    "unsafe to make", "under-specified", "underspecified", "under specified",
   326	    "insufficient information", "not enough information", "requires clarification",
   327	    "need clarification", "too ambiguous", "out of scope", "cannot determine",
   328	    "cannot proceed safely", "i cannot complete this", "i'm unable to complete",
   329	    "will not make this change", "refuse to make", "decline to make",
   330	    "no changes were made because", "cannot make this change",
   331	)
   332	
   333	
   334	def _looks_like_refusal(text: str) -> bool:
   335	    """True if prose reads as an explicit stop/refusal rather than a forgotten-action plan."""
   336	    lowered = text.lower()
   337	    return any(phrase in lowered for phrase in _REFUSAL_SIGNAL_PHRASES)
   338	
   339	
   340	def _looks_like_edit_mismatch(error_text: str) -> bool:
   341	    """True if an edit_file failure message signals an old_string byte-mismatch."""
   342	    lowered = (error_text or "").lower()
   343	    return any(phrase in lowered for phrase in _EDIT_MISMATCH_SIGNAL_PHRASES)
   344	
   345	
   346	def _build_edit_mismatch_feedback(
   347	    file_path: str,
   348	    attempted_old_string: str,
   349	    char_budget: int = _READ_FILE_GATE_CHAR_BUDGET,
   350	    context_lines: int = 12,
   351	) -> Optional[str]:
   352	    """One-shot edit-mismatch feedback body: the file's EXACT current text for
   353	    the region the model was trying to edit, bounded to char_budget.
   354	
   355	    Anchors on the first non-blank line of the model's attempted old_string
   356	    (exact substring match first, difflib fuzzy match as fallback) and slices
   357	    +/- context_lines around it. Falls back to a bounded head-of-file slice if
   358	    no anchor can be found. Fail-safe: returns None (never raises) on any
   359	    error — the caller falls through to the plain failure result.
   360	    """
   361	    try:
   362	        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
   363	        if not path.exists() or not path.is_file():
   364	            return None
   365	        content = path.read_text(encoding="utf-8")
   366	        lines = content.splitlines()
   367	
   368	        anchor_line_no: Optional[int] = None
   369	        attempted_lines = [ln.strip() for ln in (attempted_old_string or "").splitlines() if ln.strip()]
   370	        if attempted_lines:
   371	            anchor = attempted_lines[0]
   372	            for i, line in enumerate(lines):
   373	                if anchor in line:
   374	                    anchor_line_no = i
   375	                    break
   376	            if anchor_line_no is None:
   377	                best_ratio = 0.0
   378	                best_i: Optional[int] = None
   379	                for i, line in enumerate(lines):
   380	                    ratio = difflib.SequenceMatcher(None, anchor, line.strip()).ratio()
   381	                    if ratio > best_ratio:
   382	                        best_ratio = ratio
   383	                        best_i = i
   384	                if best_ratio >= 0.4:
   385	                    anchor_line_no = best_i
   386	
   387	        if anchor_line_no is not None:
   388	            start = max(0, anchor_line_no - context_lines)
   389	            end = min(len(lines), anchor_line_no + context_lines + 1)
   390	            region = "\n".join(lines[start:end])

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "sed -n '120,210p' scripts/ai/lib/grammar_cache.py
sed -n '120,225p' ai-stack/local-agents/builtin_tools/shell_tools.py
sed -n '1,220p' ai-stack/local-agents/llm_cassette.py
sed -n '220,380p' ai-stack/local-agents/llm_cassette.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 53ms:


def _parse_json_value(value: Any) -> Any:
    if isinstance(value, bytes | bytearray):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value


def _rule_for_schema(schema: Mapping[str, Any]) -> str:
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        # Constrain to the exact enumerated literals (e.g. the leased tool-name set)
        # instead of falling through to an unconstrained `string`/`number` rule.
        # Parenthesized: GBNF `|` has lower precedence than sequencing, so an
        # unparenthesized alternation embedded inline (e.g. inside _object_rule's
        # "key" ws ":" ws <this> sequence) would leak across the whole enclosing
        # rule instead of binding to just this property's value.
        alternatives = " | ".join(_gbnf_literal(json.dumps(v, separators=(",", ":"))) for v in enum_values)
        return f"({alternatives})"
    schema_type = schema.get("type")
    if schema_type == "object":
        return _object_rule(schema)
    if schema_type == "array":
        item_rule = _rule_for_schema(_schema_mapping(schema.get("items", {})))
        return f'"[" ws ({item_rule} (ws "," ws {item_rule})*)? ws "]"'
    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    return "string | number | boolean | null"


def _object_rule(schema: Mapping[str, Any]) -> str:
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping) or not properties:
        # Free-form object (schema is `{"type": "object"}` with no declared
        # `properties`, e.g. a tool-call's `arguments` payload): allow zero-or-more
        # arbitrary JSON members instead of forcing an empty "{}" body, which made
        # every tool call emit useless empty arguments.
        return "object"

    parts: list[str] = []
    for name in sorted(properties):
        prop_schema = _schema_mapping(properties[name])
        key_literal = _gbnf_literal(json.dumps(name, separators=(",", ":")))
        parts.append(f'{key_literal} ws ":" ws {_rule_for_schema(prop_schema)}')
    return '"{" ws ' + ' ws "," ws '.join(parts) + ' ws "}"'


def _gbnf_literal(text: str) -> str:
    """Return a GBNF double-quoted literal that generates `text` verbatim.

    `text` is the exact raw output text desired (e.g. a JSON-encoded key/value
    like `"function"`, quote characters included). Backslashes and double quotes
    in `text` are backslash-escaped so they survive as literal characters inside
    the GBNF string rather than terminating it early — the fix for the bug where
    `json.dumps(name)[1:-1]` stripped the JSON quotes and produced an unquoted
    GBNF literal (matching bare `arguments` instead of `"arguments"`).
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _schema_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
    command: str,
    timeout_seconds: int = 10,
) -> Dict:
    """
    Execute a safe shell command.

    Args:
        command: Shell command to execute
        timeout_seconds: Timeout in seconds (default: 10)

    Returns:
        {
            "success": bool,
            "stdout": str,
            "stderr": str,
            "returncode": int,
            "error": str (if failed)
        }
    """
    # Strip trailing tool-call JSON artifacts before ANY check. The local model's
    # GBNF/streaming tool-call parser can leak the envelope's closing punctuation
    # into the command argument (e.g. "grep ... file\n},\n"), which the shell-control
    # guard below then rejects as a newline/metachar — the model retries verbatim and
    # stagnates. This trims ONLY trailing whitespace + a dangling "}"/"]"/"," /quote
    # tail; it never removes anything from the middle of a command, so a genuine
    # injection ("; rm -rf" / "cmd\ncmd2") is still caught by the guard. Producer-side
    # cleanup, not a security relaxation. Root cause: local-agent-tool-call-json-artifact-leak.
    command = re.sub(r"[\s}\]\",]+$", "", command)

    # Parse first word as command
    cmd_parts = command.split()
    if not cmd_parts:
        return {"success": False, "error": "Empty command"}

    base_cmd = cmd_parts[0]

    if _SHELL_CONTROL_PATTERN.search(command):
        return {
            "success": False,
            "error": "Command rejected: shell control/metacharacter sequences are not allowed",
            "safety_reason": "shell_injection_guard",
        }

    # Check if command is safe
    if base_cmd not in SAFE_COMMANDS:
        return {
            "success": False,
            "error": f"Command '{base_cmd}' not in safe list: {', '.join(sorted(SAFE_COMMANDS))}",
        }

    try:
        if _nsjail.available:
            try:
                nsjail_argv = _nsjail.build_argv(command, timeout_seconds)
                result = subprocess.run(
                    nsjail_argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds + 2,
                )
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "sandbox": "nsjail",
                }
            except Exception as nsjail_exc:
                logger.warning(
                    "NsjailSandbox: isolation failure: %s",
                    nsjail_exc,
                )
                if _nsjail.required:
                    return {
                        "success": False,
                        "error": f"Sandbox required but nsjail failed: {nsjail_exc}",
                        "sandbox": "nsjail",
                        "safety_reason": "sandbox_required_failed",
                    }

        if _nsjail.required and not _nsjail.available:
            return {
                "success": False,
                "error": "Sandbox required but nsjail is unavailable",
                "sandbox": "unavailable",
                "safety_reason": "sandbox_required_unavailable",
            }

        # Plain subprocess compatibility path. This is only used when nsjail is
        # not configured as required; the shell injection guard above still
        # applies before reaching this path.
        #
        # Phase 164 Stage B: when RTK is available, wrap the command so output
        # is compressed before it enters the LLM context window. RTK handles
        # git, grep, ls, pytest, cargo, docker, kubectl, and 100+ other commands.
        # Falls back to uncompressed execution if RTK fails.
        if _RTK_ENABLED:
            try:
                rtk_argv = [_RTK_BIN] + shlex.split(command)
                result = subprocess.run(
                    rtk_argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                return {
#!/usr/bin/env python3
"""
LLM record/replay cassette — deterministic, instant replay of local-agent inference.

Problem: every dogfood validation of the local-agent loop is a 30-40 min LIVE run on
the APU, subject to transient variance (silent-server-timeout, grammar drift, budget
exhaustion, etc). This module lets `_call_llama` in agent_executor.py record real model
outputs once, then replay them deterministically and offline — so harness fixes and
config A/Bs (grammar on/off, write_region, PTC) validate in seconds, not tens of minutes.

Design doc (authoritative): .agents/plans/record-replay-harness/DESIGN.md

Modes (env AQ_LLM_CASSETTE_MODE, default "off"):
    off            — no-op. Zero behavior change (the sacrosanct default).
    record         — live call happens; (key -> content, tokens) is appended to the
                     cassette at AQ_LLM_CASSETTE.
    replay         — NO network. Returns the cassette's recorded content for the
                     request's key. Miss behavior is AQ_LLM_CASSETTE_ON_MISS
                     (error [default] | passthrough | empty).
    replay-record  — replay on hit; live + record on miss (grows a cassette
                     incrementally).

Everything in this module is stdlib-only (hashlib/json/os) and fails SAFE: any
internal error (corrupt cassette line, unwritable path, etc) is logged and swallowed,
never propagated into the caller's live inference path. The one deliberate exception
is `ReplayMiss`, raised only when the operator has explicitly asked for
AQ_LLM_CASSETTE_ON_MISS=error (the default in `replay` mode) — that is a signal, not a
bug.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Fields considered part of the SEMANTIC request identity. Everything else in a
# build_llama_payload() dict (chat_template_kwargs, repeat_penalty, repeat_last_n,
# cache_prompt, stream_options, ...) is volatile/derived and deliberately excluded so
# the key is stable across runs that only differ in those knobs.
_SEMANTIC_FIELDS: Tuple[str, ...] = (
    "messages",
    "max_tokens",
    "temperature",
    "grammar",
    "task_type",
    "tools",
    "stream",
)


class ReplayMiss(Exception):
    """Raised in replay mode (AQ_LLM_CASSETTE_ON_MISS=error, the default) when no
    recorded row exists for the computed request key. Carries the key and a short
    payload summary so the failure is immediately actionable."""

    def __init__(self, key: str, payload: Optional[Dict[str, Any]] = None):
        self.key = key
        self.payload_summary = _summarize_payload(payload) if payload else ""
        super().__init__(
            f"llm_cassette: REPLAY MISS for key={key} — no recorded row. "
            f"payload={self.payload_summary}"
        )


def _summarize_payload(payload: Dict[str, Any]) -> str:
    try:
        messages = payload.get("messages") or []
        last = messages[-1] if messages else {}
        preview = str(last.get("content", ""))[:120].replace("\n", "\\n")
        return (
            f"max_tokens={payload.get('max_tokens')} "
            f"temperature={payload.get('temperature')} "
            f"n_messages={len(messages)} last='{preview}'"
        )
    except Exception:
        return "<unavailable>"


def _normalize_messages(messages: Any) -> List[Dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append({"role": m.get("role"), "content": m.get("content")})
    return out


def request_key(payload: Dict[str, Any], task_type: Optional[str] = None) -> str:
    """Stable sha256 over the SEMANTIC request only.

    Includes: messages (role+content), max_tokens, temperature, grammar, task_type,
    tools, stream. Excludes volatile fields (timestamps, request ids, cache flags,
    chat_template_kwargs, repeat_penalty/repeat_last_n, frequency_penalty, ...) so the
    same logical request hashes identically across runs and machines.

    `task_type` is accepted as a separate optional arg because build_llama_payload()
    consumes it as a keyword-only builder argument and does NOT carry it into the
    resulting payload dict — callers that have task_type as a local variable should
    pass it explicitly. If the payload dict already carries a "task_type" key (e.g. a
    cassette row payload_digest reconstruction), that value wins.
    """
    try:
        semantic: Dict[str, Any] = {
            "messages": _normalize_messages(payload.get("messages")),
            "max_tokens": payload.get("max_tokens"),
            "temperature": payload.get("temperature"),
            "grammar": payload.get("grammar"),
            "task_type": payload.get("task_type", task_type),
            "tools": payload.get("tools"),
            "stream": bool(payload.get("stream", False)),
        }
        blob = json.dumps(semantic, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
    except Exception:
        logger.exception("llm_cassette: request_key failed — this is a bug, not a miss")
        raise


class Cassette:
    """A JSONL-backed store of recorded (key -> content, tokens) rows.

    Multiple rows may share a key (the same request issued more than once in a run,
    e.g. a retry or a repeated planning step with identical semantic content). Rows are
    consumed in APPEND order per key via a per-instance cursor: the Nth lookup for a
    given key returns the Nth recorded row for that key, so a two-call sequence with an
    identical key replays its 1st call's output, then its 2nd.
    """

    def __init__(self, cassette_path: str):
        self.path = Path(cassette_path)
        self._rows: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._cursor: Dict[str, int] = {}

    def _load(self) -> None:
        if self._rows is not None:
            return
        rows: Dict[str, List[Dict[str, Any]]] = {}
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as fh:
                    for line_no, line in enumerate(fh, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning(
                                "llm_cassette: skipping corrupt row %s:%d", self.path, line_no
                            )
                            continue
                        key = row.get("key")
                        if not key:
                            continue
                        rows.setdefault(key, []).append(row)
            except OSError as e:
                logger.warning("llm_cassette: failed to read %s: %s", self.path, e)
        self._rows = rows

    def record(
        self,
        key: str,
        payload: Dict[str, Any],
        content: str,
        tokens: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append one row. Never raises — logs and no-ops on any IO/serialization error."""
        try:
            payload_digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
        except Exception:
            payload_digest = ""
        row = {
            "key": key,
            "payload_digest": payload_digest,
            "content": content,
            "tokens": tokens,
            "meta": meta or {},
            "ts": time.time(),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("llm_cassette: failed to write %s: %s", self.path, e)
            return
        # Keep the in-memory index in sync so a record()-then-lookup() in the same
        # process (replay-record mode, or a test) sees the row immediately without
        # re-reading the file.
        if self._rows is not None:
            self._rows.setdefault(key, []).append(row)

    def lookup(self, key: str) -> Optional[Tuple[str, int]]:
        """Return (content, tokens) for the next unconsumed row at this key, in
        call order, or None if no (further) row exists. Never raises."""
        try:
            self._load()
            assert self._rows is not None
            rows = self._rows.get(key)
            if not rows:
                return None
            idx = self._cursor.get(key, 0)
            if idx >= len(rows):
                return None
            row = rows[idx]
            self._cursor[key] = idx + 1
            return row.get("content", ""), int(row.get("tokens", 0) or 0)
        except Exception:
            logger.exception("llm_cassette: lookup failed for key=%s — treating as miss", key)
            logger.exception("llm_cassette: lookup failed for key=%s — treating as miss", key)
            return None

    def reset_cursor(self) -> None:
        """Rewind consumption cursors to the start (useful for re-running the same
        cassette against a second config in aq-replay-bench)."""
        self._cursor = {}


# ---------------------------------------------------------------------------
# Module-level env readers + a small per-path cassette cache so the consumption
# cursor persists across the many _call_llama invocations of a single task loop.
# ---------------------------------------------------------------------------

_VALID_MODES = ("off", "record", "replay", "replay-record")
_VALID_ON_MISS = ("error", "passthrough", "empty")

_cassette_cache: Dict[str, Cassette] = {}


def mode() -> str:
    m = os.environ.get("AQ_LLM_CASSETTE_MODE", "off").strip().lower()
    return m if m in _VALID_MODES else "off"


def path() -> Optional[str]:
    p = os.environ.get("AQ_LLM_CASSETTE")
    return p.strip() if p and p.strip() else None


def on_miss() -> str:
    o = os.environ.get("AQ_LLM_CASSETTE_ON_MISS", "error").strip().lower()
    return o if o in _VALID_ON_MISS else "error"


def get_cassette(cassette_path: Optional[str] = None) -> Optional[Cassette]:
    """Return the process-wide Cassette for `cassette_path` (or AQ_LLM_CASSETTE if
    omitted), creating it on first use. Returns None if no path is configured."""
    p = cassette_path if cassette_path is not None else path()
    if not p:
        return None
    resolved = str(Path(p).expanduser())
    cass = _cassette_cache.get(resolved)
    if cass is None:
        cass = Cassette(resolved)
        _cassette_cache[resolved] = cass
    return cass


def reset_cache() -> None:
    """Test/bench helper: drop all cached Cassette instances (and their cursors)."""
    _cassette_cache.clear()


# ---------------------------------------------------------------------------
# Orchestration helpers — the thin surface agent_executor._call_llama wires into.
# Both are pure no-ops in mode "off" and fail safe (fall through to live) on any
# internal error, per the design's guardrail.
# ---------------------------------------------------------------------------

def replay_lookup(
    payload: Dict[str, Any], task_type: Optional[str] = None
) -> Optional[Tuple[str, int]]:
    """Consult the cassette in replay/replay-record modes.

    Returns:
        (content, tokens) on a cassette hit, or on-miss "empty" policy.
        None — proceed with the live call — in mode "off"/"record", on a
              replay-record miss, or on-miss "passthrough".
    Raises:
        ReplayMiss — mode "replay", on-miss "error" (the default), and no row exists.
    """
    m = mode()
    if m not in ("replay", "replay-record"):
        return None
    try:
        cass = get_cassette()
        if cass is None:
            logger.warning(
                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — proceeding live", m
            )
            return None
        key = request_key(payload, task_type)
        hit = cass.lookup(key)
    except ReplayMiss:
        raise
    except Exception:
        logger.exception("llm_cassette: replay_lookup internal error — falling back to live")
        return None

    if hit is not None:
        return hit

    if m == "replay-record":
        return None  # fall through to live; caller records after

    policy = on_miss()
    if policy == "passthrough":
        return None
    if policy == "empty":
        return "", 0
    # policy == "error" (default): a miss in strict replay mode is a test failure.
    raise ReplayMiss(key, payload)


def maybe_record(
    payload: Dict[str, Any],
    task_type: Optional[str],
    content: str,
    tokens: int,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Tee a live (content, tokens) result into the cassette in record/replay-record
    modes. No-op in off/replay. Never raises."""
    m = mode()
    if m not in ("record", "replay-record"):
        return
    try:
        cass = get_cassette()
        if cass is None:
            logger.warning(
                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — not recording", m
            )
            return
        key = request_key(payload, task_type)
        cass.record(key, payload, content, tokens, meta)
    except Exception:
        logger.exception("llm_cassette: maybe_record internal error — continuing without recording")

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc 'rg -n "def _call_llama|replay_lookup|maybe_record|while |for .*range|reread|noaction|edit_feedback|successful_edit|iteration|max_iterations|tool_iterations|tool_call_count|intervention" ai-stack/local-agents/agent_executor.py' in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 54ms:
29:# Operator intervention channel (first cut) — lazily loaded, fails open so a missing/broken
168:# ── Phase A.6: keyword sets for per-iteration tool hot-swap ──────────────────
273:# edit-forcing intervention (delivered as the read_file tool result, role:"tool") instead
276:# complete. A SECOND breach (re-read after the intervention) still aborts as before.
1188:        tool_call_count = 0
1275:        # Repeated-read stagnation: fires the edit-forcing intervention exactly once per
1276:        # task. Set True the moment the intervention message is queued (not only on full
1278:        # straight through to the plain abort rather than looping interventions forever.
1279:        _reread_intervention_sent = False
1281:        # whether the one-shot no-action intervention has already fired. See the
1284:        _no_action_intervention_sent = False
1288:        _edit_feedback_counts: dict = {}  # file_path → feedback-fire count
1382:                        "tool_call_count": call_number,
1411:        while True:
1412:            # Phase E — agent_step_start: emitted at the top of every iteration before the LLM call.
1415:                {"tool_call_count": tool_call_count},
1419:            # Operator intervention channel — poll the per-task control queue between turns
1518:            call_max_tokens = AGENT_TASK_MAX_TOKENS if tool_call_count > 0 else AGENT_TOOL_CALL_MAX_TOKENS
1526:                    call_number=tool_call_count + 1,
1532:                    tool_call_count + 1, str(_llm_err)[:120],
1539:                    call_number=tool_call_count + 1,
1549:                    tool_call_count + 1, _ctx_chars_at_fail,
1560:                    call_number=tool_call_count + 1,
1567:                        f"LLM returned empty response at call {tool_call_count + 1} "
1579:                # Fire on ANY turn — tool_call_count > 0 was too narrow; the model can output
1602:                                call_number=tool_call_count + 1,
1610:                                    tool_call_count + 1,
1617:                                tool_call_count + 1,
1624:                            tool_call_count,
1639:                                model_provenance={"lane": "local", "call_number": tool_call_count},
1655:                            call_number=tool_call_count + 1,
1674:                        and not _no_action_intervention_sent
1679:                                _no_action_intervention_sent = True
1680:                                intervention_msg = (
1692:                                    "content": intervention_msg,
1695:                                    "no-action intervention: prose-only response with 0 "
1698:                                    tool_call_count,
1701:                                    task.id, "noaction_intervention",
1702:                                    {"tool_call_count": tool_call_count},
1706:                        except Exception as _noaction_err:
1708:                                "no-action-intervention construction failed (%s) — "
1709:                                "falling through to normal completion", _noaction_err,
1712:                            # never let a broken intervention crash or hang the loop).
1714:                    if tool_call_count > 0:
1717:                            {"tool_call_count": tool_call_count},
1761:            tool_call_count += 1
1884:                    result.tool_name, threshold, tool_call_count,
1902:                            f"Aborting loop at call {tool_call_count} to prevent runaway search."
1906:                            _fp, _FAILED_READ_LIMIT, tool_call_count,
1931:                        f"not fixable by the agent. Aborting at call {tool_call_count}."
1935:                        result.tool_name, _tool_failure_counts[result.tool_name], tool_call_count,
1949:                        # First breach: inject a one-shot edit-forcing intervention instead
1955:                        if _REREAD_INTERVENTION_ENABLED and not _reread_intervention_sent:
1957:                                _reread_intervention_sent = True
1964:                                intervention_msg = (
1980:                                    "content": intervention_msg,
1983:                                    "repeated-read intervention: path=%r reads=%d call=%d — "
1985:                                    read_path, _read_path_counts[read_path], tool_call_count,
1988:                                    task.id, "reread_intervention",
1992:                                        "tool_call_count": tool_call_count,
1999:                                    "reread-intervention construction failed (%s) — "
2003:                                # let a broken intervention crash or hang the loop).
2007:                            f"Aborting at tool call {tool_call_count}."
2011:                            read_path, _read_path_counts[read_path], tool_call_count,
2034:                    _ef_fires = _edit_feedback_counts.get(_ef_path, 0)
2048:                                _edit_feedback_counts[_ef_path] = _ef_fires + 1
2071:                                    _ef_path, _edit_feedback_counts[_ef_path], tool_call_count,
2074:                                    task.id, "edit_feedback_intervention",
2077:                                        "attempt": _edit_feedback_counts[_ef_path],
2078:                                        "tool_call_count": tool_call_count,
2112:                        f"in analysis phase. Aborting at tool call {tool_call_count}."
2118:                        f"Aborting at tool call {tool_call_count}."
2122:                    _reads_without_edit, task.task_type, tool_call_count,
2132:                    f"Aborting at tool call {tool_call_count}."
2136:                    _observations_without_action, tool_call_count,
2156:            _emit_step_telemetry(result, tool_call_count, prose_before)
2205:                    call_number=tool_call_count + 1,
2237:                    call_number=tool_call_count + 1,
2257:                    _observations_without_action, tool_call_count,
2269:                        "Do not keep rereading the same files."
2293:                    _reads_without_edit, tool_call_count,
2310:                    _validation_passes_without_commit, tool_call_count,
2351:        return llm_cassette.replay_lookup(payload, task_type)
2365:        llm_cassette.maybe_record(payload, task_type, content, tokens, meta)
2367:    async def _call_llama(
2495:                    "tool_call_count": call_number,
2549:                        # CONTENT token; fires even while keep-alives arrive. Measured: this
2916:                        f"\n\n[LOOP STATE — iter {_ls.get('iteration')}/{_ls.get('max_iterations')} "

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "sed -n '1160,1805p' ai-stack/local-agents/agent_executor.py
sed -n '1840,2340p' ai-stack/local-agents/agent_executor.py
sed -n '2335,2645p' ai-stack/local-agents/agent_executor.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 56ms:
                "content": f"Context: {json.dumps(task.context)}",
            })

        # F.3 — working-memory auto-prefetch: inject prior-task scratch notes into the
        # system prompt so the model starts with relevant prior findings without needing
        # to call get_working_memory explicitly. 3 s hard timeout — skip on any error.
        if self.fallback_endpoint:
            try:
                async with httpx.AsyncClient(timeout=3.0) as _wm_client:
                    _wm_resp = await _wm_client.post(
                        f"{self.fallback_endpoint.rstrip('/')}/memory/recall",
                        json={"query": task.objective[:200], "memory_types": ["semantic"], "limit": 3},
                    )
                    if _wm_resp.status_code == 200:
                        _wm_results = _wm_resp.json().get("results", [])[:3]
                        _wm_lines = [
                            f"- {r['content'][:200]}"
                            for r in _wm_results if r.get("content")
                        ]
                        if _wm_lines:
                            messages[0]["content"] += (
                                "\n\nPRIOR WORKING MEMORY:\n" + "\n".join(_wm_lines)
                            )
                            logger.debug("working_memory_prefetch: injected %d entries", len(_wm_lines))
            except Exception:
                pass

        # Tool use loop
        tool_call_count = 0
        total_tokens = 0
        _loop_start = time.time()

        # Phase E — stall watchdog: fire advisory event if no activity for STALL_TIMEOUT seconds.
        # STALL_TIMEOUT_OVERRIDE env var enables short timeouts for CI testing (e.g. 5s).
        # Watchdog is advisory only — never aborts the loop.
        STALL_TIMEOUT = int(os.environ.get("STALL_TIMEOUT_OVERRIDE", "300"))
        _watchdog_last_activity: list[float] = [time.time()]
        _loop = asyncio.get_running_loop()
        _watchdog_handle: asyncio.TimerHandle

        def _cancel_watchdog() -> None:
            if not _watchdog_handle.cancelled():
                _watchdog_handle.cancel()

        def _fire_stall() -> None:
            if task.status != TaskStatus.RUNNING:
                _cancel_watchdog()
                return
            elapsed = time.time() - _watchdog_last_activity[0]
            if elapsed >= STALL_TIMEOUT - 1:
                asyncio.create_task(self._emit_agent_event(
                    task.id, "agent_stall",
                    {"elapsed_s": round(elapsed, 1), "advisory": True},
                    _watchdog_last_activity,
                ))
            # Reschedule for the next interval
            nonlocal _watchdog_handle
            _watchdog_handle = _loop.call_later(STALL_TIMEOUT, _fire_stall)

        _watchdog_handle = _loop.call_later(STALL_TIMEOUT, _fire_stall)

        # Stagnation guard: track (tool_name, result_prefix) for recent calls.
        # Thresholds: 3 for read_file (pure observation, no state change expected after 3
        # identical reads); 5 for run_command and others (allows brief polling loops).
        # If the threshold is exceeded, abort with a degraded result rather than burning
        # the full budget on a runaway loop.
        _recent_tools: list = []
        _STAGNATION_THRESHOLD_READ = 3   # read_file: identical result = definitely stuck
        _STAGNATION_THRESHOLD_OTHER = 5  # run_command etc: allow polling for state change

        # File-not-found stagnation: track paths that returned ok=False.
        # If the same path fails 3 times, the file genuinely does not exist and
        # the model is stuck in a search loop — abort rather than burn the budget.
        _failed_reads: dict = {}  # path → failure count
        _FAILED_READ_LIMIT = 3

        # Per-tool failure stagnation: tracks how many times any single tool has returned
        # success=False (or a non-zero exit_code). If the same tool keeps failing regardless
        # of intervening calls (e.g. harness_health → store_memory → harness_health loop),
        # the observation stagnation guard won't fire because action calls reset the counter.
        # This guard catches persistent infra failures the model cannot fix.
        _tool_failure_counts: dict = {}  # tool_name → failure count
        _TOOL_FAILURE_HARD_LIMIT = 5

        # Exploration stagnation: tracks reads since the last edit/write tool call.
        # Implementation tasks abort early on over-exploration. Analysis-only work may
        # read much more, but must checkpoint through store_memory/write_file and may
        # not spin on the same file path.
        _reads_without_edit = 0
        _read_path_counts: dict = {}
        _ANALYSIS_ONLY_TASK_TYPES = frozenset({
            "research", "analysis", "analysis_only", "research_only",
            "planning", "prd", "deep_reasoning",
        })
        _is_analysis_only_task = (task.task_type or "").lower() in _ANALYSIS_ONLY_TASK_TYPES
        # Stagnation thresholds are env-tunable so we can empirically probe where the
        # boundary is the GUARD vs the model (capability-envelope experiments). Defaults
        # unchanged — set AI_AGENT_* only for controlled runs. Large-file multi-edit
        # tasks legitimately re-read to locate several edit sites; too-tight limits abort
        # a capable model prematurely.
        _env_int = lambda name, default: max(1, int(os.environ.get(name, str(default))))
        _IMPLEMENTATION_MAX_READS_WITHOUT_EDIT = _env_int("AI_AGENT_IMPL_MAX_READS_WITHOUT_EDIT", 8)
        _IMPLEMENTATION_READS_HARD_LIMIT = _env_int("AI_AGENT_IMPL_READS_HARD_LIMIT", 12)
        _ANALYSIS_MAX_READS_WITHOUT_CHECKPOINT = _env_int("AI_AGENT_ANALYSIS_MAX_READS", 24)
        _ANALYSIS_READS_HARD_LIMIT = _env_int("AI_AGENT_ANALYSIS_READS_HARD_LIMIT", 80)
        _REPEATED_READ_PATH_LIMIT = _env_int("AI_AGENT_REPEATED_READ_PATH_LIMIT", 4)
        _MAX_READS_WITHOUT_EDIT = (
            _ANALYSIS_MAX_READS_WITHOUT_CHECKPOINT
            if _is_analysis_only_task else _IMPLEMENTATION_MAX_READS_WITHOUT_EDIT
        )
        _READS_HARD_LIMIT = (
            _ANALYSIS_READS_HARD_LIMIT
            if _is_analysis_only_task else _IMPLEMENTATION_READS_HARD_LIMIT
        )
        _exploration_nudge_sent = False
        # Repeated-read stagnation: fires the edit-forcing intervention exactly once per
        # task. Set True the moment the intervention message is queued (not only on full
        # success) so a second breach — with or without a mid-construction error — falls
        # straight through to the plain abort rather than looping interventions forever.
        _reread_intervention_sent = False
        # No-action guard: counts successful edit_file/write_file calls this run, and
        # whether the one-shot no-action intervention has already fired. See the
        # _NOACTION_INTERVENTION_ENABLED block above for the full rationale.
        _edits_made = 0
        _no_action_intervention_sent = False
        # Edit-failure feedback: fires per target file (a task may edit several
        # files), bounded to _EDIT_FEEDBACK_MAX_PER_FILE per path. See the
        # _EDIT_FEEDBACK_ENABLED block above for the full rationale.
        _edit_feedback_counts: dict = {}  # file_path → feedback-fire count
        _validation_passes_without_commit = 0
        _VALIDATION_STALL_NUDGE = 3

        # Observation stagnation: harness query tools (get_hint, query_aidb, etc.) called
        # repeatedly without taking any action. Distinguishable from exploration stagnation
        # (which tracks read_file). Research tasks legitimately query multiple sources, so
        # threshold is higher than read_file's 3. Soft nudge at 6; hard abort at 10.
        _OBSERVATION_QUERY_TOOLS = frozenset({
            "get_hint", "query_aidb", "get_prsi_pending", "get_working_memory",
            "mesh_discovery", "harness_health", "query_context", "get_context",
            "collective_memory_search",
        })
        _OBSERVATION_ACTION_TOOLS = frozenset({
            "store_memory", "run_command", "run_harness_cli", "delegate_to_remote",
            "edit_file", "write_file", "write_region", "git_add", "git_commit",
        })
        _observations_without_action = 0
        _MAX_OBSERVATIONS_WITHOUT_ACTION = 6
        _OBSERVATIONS_HARD_LIMIT = 10
        _observation_nudge_sent = False

        # Observability: progress sidecar path (set by aq-agent-loop via env var).
        # Updated after every tool call so dashboards and `dispatch.py watch` can
        # read current state without waiting for the final JSON output.
        _progress_file = os.getenv("AGENT_PROGRESS_FILE")
        _steps_file = os.getenv("AGENT_STEPS_FILE")

        def _emit_step_telemetry(tc_result, call_number: int, prose_before: str) -> None:
            """Write per-tool-call telemetry to all three observability surfaces."""
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
            elapsed = time.time() - _loop_start

            # 1. hybrid-events.jsonl — feeds dashboard + training_ingest
            if _HYBRID_EVENTS.parent.exists():
                try:
                    events = []
                    if prose_before.strip():
                        events.append(json.dumps({
                            "event_type": "agent_thinking",
                            "timestamp": ts,
                            "task_id": task.id,
                            "session_id": task.id,
                            "tool_call_number": call_number,
                            "thinking": prose_before[:500],
                            "model": os.getenv("LLAMA_MODEL_NAME", "local"),
                        }))
                    events.append(json.dumps({
                        "event_type": "agent_tool_call",
                        "timestamp": ts,
                        "task_id": task.id,
                        "session_id": task.id,
                        "tool_name": tc_result.tool_name,
                        "tool_call_number": call_number,
                        "success": tc_result.status == "completed",
                        "execution_time_ms": tc_result.execution_time_ms,
                        "error": tc_result.error,
                        "elapsed_s": round(elapsed, 1),
                        "objective_preview": task.objective[:120],
                        "model": os.getenv("LLAMA_MODEL_NAME", "local"),
                    }))
                    # tool_result event: successful tool calls → training pairs.
                    # query = task objective + tool invocation context.
                    # response = the actual tool output (training signal for tool-use).
                    if tc_result.status == "completed" and tc_result.result is not None:
                        _args_str = json.dumps(tc_result.arguments)[:200] if hasattr(tc_result, "arguments") else ""
                        try:
                            _res_str = json.dumps(tc_result.result)[:1500]
                        except (TypeError, ValueError):
                            _res_str = str(tc_result.result)[:1500]
                        events.append(json.dumps({
                            "event_type": "tool_result",
                            "timestamp": ts,
                            "task_id": task.id,
                            "session_id": task.id,
                            "tool_name": tc_result.tool_name,
                            "query": f"Task: {task.objective[:200]} | Tool: {tc_result.tool_name}({_args_str})",
                            "response": _res_str,
                            "success": True,
                            "execution_time_ms": tc_result.execution_time_ms,
                            "elapsed_s": round(elapsed, 1),
                            "model": os.getenv("LLAMA_MODEL_NAME", "local"),
                        }))
                    with open(_HYBRID_EVENTS, "a", encoding="utf-8") as _hef:
                        _hef.write("\n".join(events) + "\n")
                except Exception:
                    pass

            # 2. Progress sidecar — single JSON, overwritten each step
            if _progress_file:
                try:
                    Path(_progress_file).write_text(json.dumps({
                        "task_id": task.id,
                        "status": "running",
                        "tool_call_count": call_number,
                        "last_tool": tc_result.tool_name,
                        "last_tool_success": tc_result.status == "completed",
                        "last_tool_ms": round(tc_result.execution_time_ms or 0, 1),
                        "last_error": tc_result.error,
                        "elapsed_s": round(elapsed, 1),
                        "objective_preview": task.objective[:120],
                        "timestamp": ts,
                    }, indent=2))
                except Exception:
                    pass

            # 3. Steps JSONL — append-only, one line per step, for streaming tail
            if _steps_file:
                try:
                    with open(_steps_file, "a", encoding="utf-8") as _sf:
                        _sf.write(json.dumps({
                            "step": call_number,
                            "tool": tc_result.tool_name,
                            "ok": tc_result.status == "completed",
                            "ms": round(tc_result.execution_time_ms or 0),
                            "elapsed_s": round(elapsed, 1),
                            "ts": ts,
                            "error": tc_result.error,
                        }) + "\n")
                except Exception:
                    pass

        _ctrl_cursor = 0  # operator control-channel read cursor (messages consumed)
        while True:
            # Phase E — agent_step_start: emitted at the top of every iteration before the LLM call.
            await self._emit_agent_event(
                task.id, "agent_step_start",
                {"tool_call_count": tool_call_count},
                _watchdog_last_activity,
            )

            # Operator intervention channel — poll the per-task control queue between turns
            # and inject any operator messages into the conversation (or a soft-stop on
            # cancel). Fails open: the loop is never disrupted by a control-channel error.
            try:
                _cc = _control_channel()
                if _cc is not None:
                    _new_ctrl, _ctrl_cursor = _cc.poll(task.id, _ctrl_cursor)
                    for _cm in _new_ctrl:
                        _txt = (_cm.get("text") or "").strip()
                        if _cm.get("kind") == "cancel":
                            messages.append({"role": "user", "content":
                                "[OPERATOR INTERVENTION — STOP] Finalize now and stop. " + _txt})
                        elif _txt:
                            messages.append({"role": "user", "content":
                                "[OPERATOR INTERVENTION] " + _txt})
                    if _new_ctrl:
                        await self._emit_agent_event(
                            task.id, "operator_inject",
                            {"count": len(_new_ctrl)}, _watchdog_last_activity,
                        )
            except Exception:
                pass

            # Context guard — Pinned + Sliding strategy:
            # Qwen3-35B SWA forces full re-prefill on every call (no KV cache reuse
            # across turns). At 10 tok/s prefill on Renoir APU, 7k tokens = ~12 min/call.
            # Target: keep context under ~3000 tokens (~12000 chars at 4 chars/tok).
            #
            # Strategy (avoids the "last-N-pairs" failure mode where the model loses
            # its initial discovery — e.g. which issue to fix — by step 5-6):
            #   PINNED  = messages[0:4]  — system + user + first call + first result
            #             These hold the task objective and initial grep/discovery output.
            #   SLIDING = messages[-4:]  — last 2 assistant+tool pairs (most recent work)
            #   Combined = PINNED + SLIDING when len(messages) > 8.
            #   When len ≤ 8, all messages fit; no pruning needed.
            _CTX_CHAR_BUDGET = 12000  # ~3000 tokens (4 chars/tok)
            _ctx_chars = sum(len((m.get("content") or "")) for m in messages)
            if _ctx_chars > _CTX_CHAR_BUDGET and len(messages) > 8:
                pinned = messages[:4]   # system + user + first_assistant + first_tool
                sliding = messages[-4:]  # last 2 assistant+tool pairs
                # When len > 8, pinned ends at index 3 and sliding starts at len-4.
                # The minimum gap between them is (len-4) - 3 = len-7 ≥ 2, so overlap
                # is never possible here. Simple concatenation is correct.
                # F.2 — prune checkpoint: compact the about-to-be-dropped middle messages
                # into working memory before evicting them, so prior findings remain
                # recoverable via get_working_memory. Fire-and-forget.
                if self.fallback_endpoint:
                    _dropped = messages[4:-4]
                    _prune_text = " | ".join(
                        (m.get("content") or "")[:120]
                        for m in _dropped
                        if m.get("role") in {"assistant", "tool"} and m.get("content")
                    )[:600]
                    if _prune_text:
                        asyncio.create_task(
                            _store_prune_checkpoint(self.fallback_endpoint, task.id, _prune_text)
                        )
                # Slice 2b — semantic scratchpad: recover the evicted middle by relevance
                # to the current objective, inserted AFTER the pinned prefix (index 4,
                # never spliced into it) so llama.cpp prefix-cache reuse is preserved.
                # context_cache is sync (httpx.Client) — offload via asyncio.to_thread so
                # the event loop never blocks. Fail-open: any error → no scratchpad, same
                # as today's pinned+sliding behavior.
                _scratch = None
                if context_cache is not None:
                    try:
                        _dropped_texts = [m.get("content") or "" for m in messages[4:-4]
                                          if m.get("role") in {"assistant", "tool"} and m.get("content")]
                        if _dropped_texts:
                            _coll = await asyncio.to_thread(context_cache.cache_evicted, str(task.id), _dropped_texts)
                            if _coll:
                                _retr = await asyncio.to_thread(context_cache.retrieve_ctx, _coll, str(task.objective), 6)
                                _scratch = context_cache.scratchpad_message(_retr)  # pure, no I/O
                    except Exception:
                        _scratch = None
                messages = pinned + ([_scratch] if _scratch else []) + sliding
                logger.debug(
                    "context_prune(pinned+sliding): pinned=%d sliding=%d total=%d chars_before=%d scratch=%s",
                    len(pinned), len(sliding), len(messages), _ctx_chars, bool(_scratch),
                )
            elif _ctx_chars > _CTX_CHAR_BUDGET and len(messages) > 6:
                # Fallback for 6 < len ≤ 8: can't do full pinned+sliding, just shed oldest pair.
                # Verify messages[2:4] form a valid (assistant, tool) pair before dropping —
                # a dangling role:tool without its role:assistant corrupts the conversation graph.
                _m2_role = messages[2].get("role") if len(messages) > 2 else None
                _m3_role = messages[3].get("role") if len(messages) > 3 else None
                if _m2_role == "assistant" and _m3_role == "tool":
                    messages = messages[:2] + messages[4:]
                    logger.debug("context_prune(shed-oldest-pair): messages now %d", len(messages))
                else:
                    logger.debug(
                        "context_prune(shed-oldest-pair): SKIP — messages[2:4] roles=%s/%s not assistant/tool pair",
                        _m2_role, _m3_role,
                    )

            # Call model — use larger budget once tools have been used so that
            # the final synthesis turn (no tool_call in response) isn't capped at
            # the tool-call budget (512).  First call keeps 512 since the model
            # almost always emits a tool call there (short JSON, EOS quick).
            call_max_tokens = AGENT_TASK_MAX_TOKENS if tool_call_count > 0 else AGENT_TOOL_CALL_MAX_TOKENS
            try:
                response, tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=call_max_tokens,
                    task_type=task.task_type,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
            except Exception as _llm_err:
                # Retry once with reduced budget on transient failures (timeout, connection drop).
                logger.warning(
                    "LLM call %d failed (%r), retrying with 512 tokens",
                    tool_call_count + 1, str(_llm_err)[:120],
                )
                response, tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=512,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
            total_tokens += tok
            if not response.strip():
                # Retry once with a nudge before failing the task. Empty responses happen
                # when the server is cold or the model stalls — a single retry recovers most
                # transient cases without burning the full budget.
                _ctx_chars_at_fail = sum(len((m.get("content") or "")) for m in messages)
                logger.warning(
                    "empty response at call %d (ctx ~%d chars) — retrying once with nudge",
                    tool_call_count + 1, _ctx_chars_at_fail,
                )
                _nudge_messages = messages + [{
                    "role": "user",
                    "content": "Your previous response was empty. Please provide a JSON tool call or a plain-text final answer now.",
                }]
                response, _retry_tok = await self._call_llama(
                    _nudge_messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += _retry_tok
                if response.strip():
                    messages = _nudge_messages
                else:
                    raise RuntimeError(
                        f"LLM returned empty response at call {tool_call_count + 1} "
                        f"(context ~{_ctx_chars_at_fail} chars)"
                    )

            # Parse tool call
            tool_call = self.tool_registry.parse_tool_call_from_llama(response)

            if not tool_call:
                # No tool call — could be prose synthesis (correct) or a truncated/malformed
                # tool-call JSON (model tried to call a tool but got cut off at max_tokens, or
                # the parser rejected it due to embedded newlines in string values).
                # Detect the latter by checking for the {"function" prefix that Qwen3 uses.
                # Fire on ANY turn — tool_call_count > 0 was too narrow; the model can output
                # a JSON tool call as its very first response if the parse failed (e.g. embedded
                # bare newlines in old_string/new_string values).
                if response.lstrip().startswith('{"function"'):
                    if _LOCAL_GBNF_REPAIR_ENABLED:
                        repair_messages = messages + [
                            {"role": "assistant", "content": response},
                            {
                                "role": "user",
                                "content": (
                                    "The previous output was malformed tool-call JSON. "
                                    "Return exactly one valid JSON tool call matching the available tool schema. "
                                    "No prose."
                                ),
                            },
                        ]
                        try:
                            repaired_response, repair_tokens = await self._call_llama(
                                repair_messages,
                                role=role,
                                max_tokens=AGENT_TOOL_CALL_MAX_TOKENS,
                                task_type=task.task_type,
                                task_id=task.id,
                                call_number=tool_call_count + 1,
                                force_tool_grammar=True,
                            )
                            total_tokens += repair_tokens
                            repaired_tool_call = self.tool_registry.parse_tool_call_from_llama(repaired_response)
                            if repaired_tool_call:
                                logger.info(
                                    "gbnf-repair: recovered malformed tool call at call %d",
                                    tool_call_count + 1,
                                )
                                response = repaired_response
                                tool_call = repaired_tool_call
                        except Exception as _repair_err:
                            logger.warning(
                                "gbnf-repair: constrained retry failed at call %d: %s",
                                tool_call_count + 1,
                                str(_repair_err)[:120],
                            )
                    if not tool_call:
                        logger.warning(
                            "final-response-is-tool-call: response looks like truncated tool call at "
                            "call %d — requesting prose synthesis (max_tokens=256)",
                            tool_call_count,
                        )
                        # P1: this is an unambiguous local failure — the model emitted a tool-call JSON
                        # the parser rejected (truncated/malformed). Capture it as a labeled training
                        # sample so the loop can learn from it. Best-effort; never breaks the turn.
                        if training_capture is not None:
                            last_user = next((m.get("content", "") for m in reversed(messages)
                                              if m.get("role") == "user"), "")
                            training_capture.capture_failure(
                                prompt=last_user,
                                bad_output=response,
                                failure_class="invalid_tool_json",
                                tools_available=[t.name for t in self.tool_registry.tools.values()
                                                 if getattr(t, "enabled", True)],
                                source="agent_executor.parse_failed",
                                model_provenance={"lane": "local", "call_number": tool_call_count},
                            )
                        messages.append({"role": "assistant", "content": response})
                        messages.append({
                            "role": "user",
                            "content": (
                                "The previous output was incomplete. "
                                "Write ONE prose sentence starting with 'COMPLETED:' summarising what was done. "
                                "No JSON. No tool calls."
                            ),
                        })
                        prose, syn_tokens = await self._call_llama(
                            messages,
                            role=role,
                            max_tokens=256,
                            task_id=task.id,
                            call_number=tool_call_count + 1,
                        )
                        total_tokens += syn_tokens
                        _cancel_watchdog()
                        return prose.strip() if prose.strip() else response, total_tokens
                if not tool_call:
                    # No-action guard: an implementer/edit task with zero successful
                    # edits so far that returns non-empty prose with no tool call is a
                    # narrated PLAN ("Thought: I would change X..."), not completion —
                    # accepting it silently ends the task having changed nothing. Refuse
                    # it ONCE and force an edit_file call instead. A genuine refusal
                    # ("cannot safely...", "under-specified...") still completes normally,
                    # and a second prose-only response completes too (no infinite loop).
                    # Fail-safe: any error here falls through to the existing completion
                    # path below rather than crashing the turn.
                    if (
                        _NOACTION_INTERVENTION_ENABLED
                        and not _is_analysis_only_task
                        and _edits_made == 0
                        and not _no_action_intervention_sent
                        and response.strip()
                    ):
                        try:
                            if not _looks_like_refusal(response):
                                _no_action_intervention_sent = True
                                intervention_msg = (
                                    "You described the change but did NOT make it — no "
                                    "file has been edited yet. Do NOT answer in prose. "
                                    "Call edit_file NOW: use the exact code from the "
                                    "'## Relevant prior knowledge' block above as "
                                    "old_string and your changed version as new_string. "
                                    "The task is only complete once edit_file has "
                                    "changed the file."
                                )
                                messages.append({"role": "assistant", "content": response})
                                messages.append({
                                    "role": "user",
                                    "content": intervention_msg,
                                })
                                logger.warning(
                                    "no-action intervention: prose-only response with 0 "
                                    "edits made at call %d — injecting one-shot "
                                    "edit-forcing nudge instead of completing",
                                    tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "noaction_intervention",
                                    {"tool_call_count": tool_call_count},
                                    _watchdog_last_activity,
                                )
                                continue
                        except Exception as _noaction_err:
                            logger.warning(
                                "no-action-intervention construction failed (%s) — "
                                "falling through to normal completion", _noaction_err,
                            )
                            # Fall through to the plain completion below (fail-safe:
                            # never let a broken intervention crash or hang the loop).
                    # Phase E — agent_synthesis_start: no tool call in response after ≥1 tool calls.
                    if tool_call_count > 0:
                        await self._emit_agent_event(
                            task.id, "agent_synthesis_start",
                            {"tool_call_count": tool_call_count},
                            _watchdog_last_activity,
                        )
                    _cancel_watchdog()
                    return response, total_tokens

            # Phase E — agent_tool_intent: emitted after parsing, before dispatch.
            await self._emit_agent_event(
                task.id, "agent_tool_intent",
                {
                    "tool_name": tool_call.tool_name,
                    "tool_args_preview": json.dumps(
                        tool_call.arguments,
                        sort_keys=True,
                        default=str,
                    )[:200],
                },
                _watchdog_last_activity,
            )

            # Execute tool call
            tool_call.model_id = f"local-{agent_type.value}"
            tool_call.session_id = task.id

            # Slice 0.2 — structural no-commit: block execution at the point of the call
            # itself, not just the advertised schema. The SI-slice system prompt still
            # names git_add/git_commit by name (STEP 6), so a schema-only filter would
            # not stop a call the model emits anyway — this is what makes "local CANNOT
            # commit" structural rather than prompt-hoped. AQ_LOCAL_ALLOW_COMMIT=1 is the
            # explicit escape hatch; the handlers in builtin_tools/git_tools.py are
            # untouched, only this call site refuses to reach them.
            if tool_call.tool_name in _AEXEC_COMMIT_TOOLS and not _LOCAL_ALLOW_COMMIT:
                tool_call.status = "blocked"
                tool_call.error = (
                    f"{tool_call.tool_name} is disabled for local agents (structural "
                    "no-commit gate). Local NEVER commits — finish validation and STOP; "
                    "the orchestrator commits after remote review. Override: "
                    "AQ_LOCAL_ALLOW_COMMIT=1 (not recommended)."
                )
                tool_call.result = {"success": False, "error": tool_call.error, "blocked": True}
                result = tool_call
            else:
                result = await self.tool_registry.execute_tool_call(tool_call)
            task.tool_calls_made.append(result)
            tool_call_count += 1

            # Slice 0.2 — read_file gate (the load-bearing fix): an oversized whole-file
            # read on top of front-loaded context blows the prompt-char budget (DESIGN.md
            # AFTER-run-1: 25920 > 24000 LLAMA_MAX_PROMPT_CHARS). Skip when an explicit
            # line range was requested — that's already a bounded, caller-chosen span.
            if (
                _READ_FILE_GATE_ENABLED
                and result.tool_name == "read_file"
                and result.status == "completed"
                and isinstance(result.result, dict)
                and result.result.get("success")
                and isinstance(result.result.get("content"), str)
                and tool_call.arguments.get("start_line") is None
                and tool_call.arguments.get("end_line") is None
            ):
                _rf_path = str(
                    tool_call.arguments.get("file_path")
                    or (result.result.get("metadata") or {}).get("path")
                    or ""
                )
                _gated_content, _rf_gated = _gate_large_file_content(
                    result.result["content"], _rf_path, task.objective, task.id,
                )
                if _rf_gated:
                    result.result["content"] = _gated_content
                    _rf_meta = result.result.setdefault("metadata", {})
                    _rf_meta["read_file_gate"] = True

            # P1.4: a valid tool call that executed cleanly is a POSITIVE sample — capture it directly
            # here (the reliable source) rather than mining hybrid-events (only ~0.03% of which are
            # inference completions — the root cause of the ingest's samples_added:0). Best-effort;
            # ingest dedupes by content hash. Guarded so it never affects the turn.
            if training_capture is not None and not getattr(result, "error", None):
                _last_user = next((m.get("content", "") for m in reversed(messages)
                                   if m.get("role") == "user"), "")
                if _last_user and response:
                    training_capture.capture_success(
                        prompt=_last_user,
                        good_output=response,
                        source="agent_executor.tool_success",
                        model_provenance={"lane": "local", "tool": getattr(result, "tool_name", "")},
                    )

            # Phase E — agent_tool_result: emitted after dispatch returns.
                if _context_risk.get("context_risk"):
                    await self._emit_agent_event(
                        task.id, "context_compaction",
                        {
                            "tool_name": result.tool_name,
                            "artifact_path": _context_risk.get("artifact_path"),
                            "raw_chars": _context_risk.get("raw_chars"),
                            "risk_reasons": _context_risk.get("risk_reasons", []),
                            "context_route": _context_risk.get("context_route"),
                        },
                        _watchdog_last_activity,
                    )
                    formatted_result = compacted_result
            except Exception as _compact_err:
                logger.debug("context compaction error (non-fatal): %s", _compact_err)

            # Stagnation detection: same (tool_name, result_prefix) repeated beyond
            # threshold → model is looping without state change. Abort early via a
            # progress guard. There is intentionally no hard max-tool-call ceiling:
            # context pruning + working-memory checkpoints keep prior findings
            # reachable across long implementation loops.
            # Thresholds are tool-specific:
            #   read_file  → 3: pure observation; identical result 3× = definitely stuck.
            #   run_command → 5: polling loops (e.g. tail, systemctl) legitimately repeat.
            threshold = (
                _STAGNATION_THRESHOLD_READ
                if result.tool_name == "read_file"
                else _STAGNATION_THRESHOLD_OTHER
            )
            _recent_tools.append((result.tool_name, formatted_result[:200]))
            if len(_recent_tools) > threshold:
                _recent_tools.pop(0)
            if (
                len(_recent_tools) == threshold
                and len({t for t, _ in _recent_tools}) == 1   # same tool name
                and len({r for _, r in _recent_tools}) == 1   # same result prefix
            ):
                stagnation_msg = (
                    f"Stagnation detected: '{result.tool_name}' called {threshold} consecutive "
                    f"times with identical result — loop aborted to prevent runaway. "
                    f"Last result prefix: {formatted_result[:300]}"
                )
                logger.warning(
                    "stagnation: tool=%r threshold=%d — aborting loop at call %d",
                    result.tool_name, threshold, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            # File-not-found stagnation: if the same path keeps returning an error
            # (file not found), the model is stuck in a search loop. Abort early.
            if result.tool_name == "read_file" and (
                result.status == "failed"
                or (result.result is not None and not result.result.get("success", True))
            ):
                _fp = (result.arguments or {}).get("file_path", "")
                if _fp:
                    _failed_reads[_fp] = _failed_reads.get(_fp, 0) + 1
                    if _failed_reads[_fp] >= _FAILED_READ_LIMIT:
                        stagnation_msg = (
                            f"File-not-found stagnation: '{_fp}' has returned an error "
                            f"{_FAILED_READ_LIMIT} times — file does not exist or is inaccessible. "
                            f"Aborting loop at call {tool_call_count} to prevent runaway search."
                        )
                        logger.warning(
                            "file-not-found stagnation: path=%r failed %d times — aborting at call %d",
                            _fp, _FAILED_READ_LIMIT, tool_call_count,
                        )
                        _cancel_watchdog()
                        return stagnation_msg, total_tokens

            # Per-tool failure stagnation: track tools that persistently return errors.
            # Catches loops like harness_health(fail)→store_memory(ok)→harness_health(fail)
            # that reset the observation counter but never make forward progress.
            _is_tool_failure = (
                result.status == "failed"
                or (
                    result.result is not None
                    and (
                        not result.result.get("success", True)
                        or result.result.get("exit_code", 0) not in (None, 0)
                        or result.result.get("error") is not None
                    )
                )
            )
            if _is_tool_failure:
                _tool_failure_counts[result.tool_name] = _tool_failure_counts.get(result.tool_name, 0) + 1
                if _tool_failure_counts[result.tool_name] >= _TOOL_FAILURE_HARD_LIMIT:
                    stagnation_msg = (
                        f"Tool-failure stagnation: '{result.tool_name}' has failed "
                        f"{_tool_failure_counts[result.tool_name]} times — persistent infra error, "
                        f"not fixable by the agent. Aborting at call {tool_call_count}."
                    )
                    logger.warning(
                        "tool-failure stagnation: tool=%r failed %d times — aborting at call %d",
                        result.tool_name, _tool_failure_counts[result.tool_name], tool_call_count,
                    )
                    _cancel_watchdog()
                    return stagnation_msg, total_tokens

            # Exploration stagnation: count reads vs edits/writes.
            # Reset counter on any write action; abort if model reads too many files
            # without acting (prevents over-exploration in self-improvement tasks).
            if result.tool_name == "read_file":
                _reads_without_edit += 1
                read_path = str(result.arguments.get("file_path") or result.arguments.get("path") or "")
                if read_path:
                    _read_path_counts[read_path] = _read_path_counts.get(read_path, 0) + 1
                    if _read_path_counts[read_path] >= _REPEATED_READ_PATH_LIMIT:
                        # First breach: inject a one-shot edit-forcing intervention instead
                        # of aborting. The relevant code is already front-loaded verbatim
                        # under "## Relevant prior knowledge" — the plain abort discarded
                        # tasks local could complete once nudged off the read->edit stall.
                        # Delivered as the read_file tool result (role:"tool") so the model
                        # actually sees it as the outcome of ITS OWN last tool call next turn.
                        if _REREAD_INTERVENTION_ENABLED and not _reread_intervention_sent:
                            try:
                                _reread_intervention_sent = True
                                _iv_brace = response.rfind('{"function"')
                                if _iv_brace == -1:
                                    _iv_brace = response.rfind("{")
                                _iv_clean_call = (
                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
                                )
                                intervention_msg = (
                                    f"You have read {read_path!r} "
                                    f"{_read_path_counts[read_path]} times and it keeps returning "
                                    "the same content — reading it again will not help. STOP "
                                    "reading. The relevant code for this task is ALREADY in your "
                                    "context above under '## Relevant prior knowledge' as exact "
                                    "fenced code blocks (byte-identical to the file). Call "
                                    "edit_file NOW: use the exact text from one of those code "
                                    "blocks as old_string (it will match), and provide your "
                                    "changed version as new_string. Do not call read_file on "
                                    "this file again."
                                )
                                messages.append({"role": "assistant", "content": _iv_clean_call})
                                messages.append({
                                    "role": "tool",
                                    "name": result.tool_name,
                                    "content": intervention_msg,
                                })
                                logger.warning(
                                    "repeated-read intervention: path=%r reads=%d call=%d — "
                                    "injecting one-shot edit-forcing nudge instead of aborting",
                                    read_path, _read_path_counts[read_path], tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "reread_intervention",
                                    {
                                        "file_path": read_path,
                                        "reads": _read_path_counts[read_path],
                                        "tool_call_count": tool_call_count,
                                    },
                                    _watchdog_last_activity,
                                )
                                continue
                            except Exception as _interv_err:
                                logger.warning(
                                    "reread-intervention construction failed (%s) — "
                                    "falling back to plain abort", _interv_err,
                                )
                                # Fall through to the plain abort below (fail-safe: never
                                # let a broken intervention crash or hang the loop).
                        stagnation_msg = (
                            f"Repeated-read stagnation: {read_path!r} was read "
                            f"{_read_path_counts[read_path]} times without progress. "
                            f"Aborting at tool call {tool_call_count}."
                        )
                        logger.warning(
                            "repeated-read stagnation: path=%r reads=%d call=%d",
                            read_path, _read_path_counts[read_path], tool_call_count,
                        )
                        _cancel_watchdog()
                        return stagnation_msg, total_tokens
            elif result.tool_name in ("edit_file", "write_file", "write_region"):
                _reads_without_edit = 0
                _read_path_counts.clear()
                if not _is_tool_failure:
                    _edits_made += 1
                elif result.tool_name == "edit_file":
                    # Edit-failure feedback: old_string byte-mismatch is now the
                    # dominant local-agent failure mode (see _EDIT_FEEDBACK_ENABLED
                    # above). On the FIRST such mismatch failure for this file
                    # (bounded to _EDIT_FEEDBACK_MAX_PER_FILE), inject the file's
                    # EXACT current text for the attempted region as the tool
                    # result instead of the bare failure, then let the loop
                    # continue — never crash or hang on a broken feedback build.
                    _ef_err = str((result.result or {}).get("error", "")) if result.result else ""
                    _ef_path = str(
                        (result.arguments or {}).get("file_path")
                        or (result.arguments or {}).get("path")
                        or ""
                    )
                    _ef_fires = _edit_feedback_counts.get(_ef_path, 0)
                    if (
                        _EDIT_FEEDBACK_ENABLED
                        and _ef_path
                        and _looks_like_edit_mismatch(_ef_err)
                        and _ef_fires < _EDIT_FEEDBACK_MAX_PER_FILE
                    ):
                        try:
                            _ef_region = _build_edit_mismatch_feedback(
                                _ef_path,
                                str((result.arguments or {}).get("old_string") or ""),
                                char_budget=_EDIT_FEEDBACK_CHAR_BUDGET,
                            )
                            if _ef_region:
                                _edit_feedback_counts[_ef_path] = _ef_fires + 1
                                _iv_brace = response.rfind('{"function"')
                                if _iv_brace == -1:
                                    _iv_brace = response.rfind("{")
                                _iv_clean_call = (
                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
                                )
                                feedback_msg = (
                                    "edit_file FAILED: your old_string did not match the "
                                    "file. The file's EXACT current text for that region is "
                                    "below — copy an exact substring of THIS as your "
                                    "old_string (character-for-character, including "
                                    "indentation) and retry edit_file.\n\n" + _ef_region
                                )
                                messages.append({"role": "assistant", "content": _iv_clean_call})
                                messages.append({
                                    "role": "tool",
                                    "name": result.tool_name,
                                    "content": feedback_msg,
                                })
                                logger.warning(
                                    "edit-mismatch feedback: path=%r attempt=%d call=%d — "
                                    "injecting exact-region feedback instead of plain failure",
                                    _ef_path, _edit_feedback_counts[_ef_path], tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "edit_feedback_intervention",
                                    {
                                        "file_path": _ef_path,
                                        "attempt": _edit_feedback_counts[_ef_path],
                                        "tool_call_count": tool_call_count,
                                    },
                                    _watchdog_last_activity,
                                )
                                continue
                        except Exception as _ef_err_exc:
                            logger.warning(
                                "edit-feedback construction failed (%s) — "
                                "falling through to plain failure", _ef_err_exc,
                            )
                            # Fall through to the normal failure-result append below.
            elif _is_analysis_only_task and result.tool_name == "store_memory":
                _reads_without_edit = 0
                _read_path_counts.clear()

            # Validation stall: detect repeated validate_before_commit/run_command
            # without any intervening commit. Model validated the code is ready but
            # won't pull the trigger. Nudge it to git_add → git_commit immediately.
            if result.tool_name in ("validate_before_commit", "run_command") and result.status == "completed":
                _validation_passes_without_commit += 1
            elif result.tool_name in ("write_file", "edit_file", "write_region", "git_add", "git_commit"):
                _validation_passes_without_commit = 0

            # Observation stagnation: track harness query calls vs action calls.
            if result.tool_name in _OBSERVATION_QUERY_TOOLS:
                _observations_without_action += 1
            elif result.tool_name in _OBSERVATION_ACTION_TOOLS:
                _observations_without_action = 0

            if _reads_without_edit >= _READS_HARD_LIMIT:
                if _is_analysis_only_task:
                    stagnation_msg = (
                        f"Analysis checkpoint stagnation: {_reads_without_edit} consecutive "
                        f"reads without store_memory or write_file checkpoint — model stuck "
                        f"in analysis phase. Aborting at tool call {tool_call_count}."
                    )
                else:
                    stagnation_msg = (
                        f"Exploration stagnation: {_reads_without_edit} consecutive reads without "
                        f"any edit_file or write_file — model stuck in exploration phase. "
                        f"Aborting at tool call {tool_call_count}."
                    )
                logger.warning(
                    "exploration/checkpoint stagnation: %d reads task_type=%r call=%d",
                    _reads_without_edit, task.task_type, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            if _observations_without_action >= _OBSERVATIONS_HARD_LIMIT:
                stagnation_msg = (
                    f"Observation stagnation: {_observations_without_action} consecutive "
                    f"harness query calls (get_hint/query_aidb/etc.) without any action — "
                    f"model is stuck in an observation loop. "
                    f"Aborting at tool call {tool_call_count}."
                )
                logger.warning(
                    "observation stagnation: %d queries without action — aborting at call %d",
                    _observations_without_action, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            # Extract the clean JSON from the response so the assistant turn
            # contains only the tool call object, not any leading prose.
            # Qwen3's chat template strips unknown roles — "function" is not
            # in its vocabulary; "tool" is the correct role for tool results.
            brace = response.rfind('{"function"')
            if brace == -1:
                brace = response.rfind("{")
            clean_call = response[brace:].strip() if brace != -1 else response.strip()

            # Capture prose before the tool call JSON (model's reasoning/thinking).
            # This is the text the model emitted BEFORE the structured tool call —
            # the "thinking aloud" surface that would otherwise be invisible.
            prose_before = response[:brace].strip() if brace > 0 else ""

            # Emit per-step telemetry to all observability surfaces (non-blocking).
            _emit_step_telemetry(result, tool_call_count, prose_before)

            messages.append({
                "role": "assistant",
                "content": clean_call,
            })
            messages.append({
                "role": "tool",
                "name": result.tool_name,
                "content": formatted_result,
            })

            # A.6 — hot-swap: expand active tool set based on what the result reveals.
            # Monotonic expansion only (never shrinks). Rebuilds messages[0] (system prompt)
            # when new tools are added so the model sees the expanded surface next call.
            _prev_tool_count = len(_active_tools)
            _active_tools = _refresh_active_tools(
                result.tool_name, formatted_result, _active_tools, _all_tools,
            )
            if len(_active_tools) > _prev_tool_count:
                messages[0] = {
                    "role": "system",
                    "content": self._get_system_prompt(agent_type, _active_tools, task.objective),
                }
                logger.debug(
                    "tool_hotswap: +%d tools after %s (total=%d)",
                    len(_active_tools) - _prev_tool_count, result.tool_name, len(_active_tools),
                )

            # Terminal tool gate: discover_objectives (and any future proposal tools) must
            # not be followed by action — the user must approve first. Inject a synthesis
            # nudge and return immediately so the agent produces a human-readable proposal
            # instead of continuing the tool loop.
            if result.tool_name in _TERMINAL_TOOLS:
                _cancel_watchdog()
                messages.append({
                    "role": "user",
                    "content": (
                        "Present the proposed objectives above as a numbered list. "
                        "For each include: rank, source, priority, and reasoning. "
                        "End with: 'Please reply with a number to select, or describe a different goal.' "
                        "Do NOT call any tools. Do NOT take any action."
                    ),
                })
                synthesis, syn_tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += syn_tok
                logger.info("terminal_tool_gate: %s → synthesis returned", result.tool_name)
                return synthesis.strip() if synthesis.strip() else formatted_result, total_tokens

            # Observation stall nudge: too many harness query calls without any action.
            # Analysis-only tasks should finalize into a report at this point; asking
            # them to "act" can send the model back into planning/tool loops.
            if (
                _is_analysis_only_task
                and _observations_without_action == _MAX_OBSERVATIONS_WITHOUT_ACTION
                and not _observation_nudge_sent
            ):
                _observation_nudge_sent = True
                _cancel_watchdog()
                messages.append({
                    "role": "user",
                    "content": (
                        "FINALIZE NOW. Do not call another tool. Do not continue planning. "
                        "Use the tool results already in context to answer the original task. "
                        "Start with 'COMPLETED:' and include concrete findings, ranked items "
                        "or decisions when requested, security/validation notes, and next safe "
                        "repo-local slice recommendations."
                    ),
                })
                synthesis, syn_tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_type=task.task_type,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += syn_tok
                return synthesis.strip(), total_tokens

            if _observations_without_action == _MAX_OBSERVATIONS_WITHOUT_ACTION and not _observation_nudge_sent:
                _observation_nudge_sent = True
                messages.append({
                    "role": "user",
                    "content": (
                        f"OBSERVATION STALL: You have called harness query tools "
                        f"({_observations_without_action} times: get_hint, query_aidb, etc.) "
                        "without taking any action. You have enough context. Now act: "
                        "call store_memory with your findings, OR call run_harness_cli, "
                        "OR write/edit a file. Do NOT call get_hint or query_aidb again "
                        "until after you have taken at least one action."
                    ),
                })
                logger.info(
                    "observation-stall nudge injected after %d queries without action at call %d",
                    _observations_without_action, tool_call_count,
                )

            # Soft nudge: inject a user message when reads-without-edit reaches the soft limit.
            # Appears before the next LLM call so the model can course-correct without aborting.
            if _reads_without_edit == _MAX_READS_WITHOUT_EDIT and not _exploration_nudge_sent:
                _exploration_nudge_sent = True
                if _is_analysis_only_task:
                    nudge_content = (
                        f"ANALYSIS TASK: You have read {_reads_without_edit} files. "
                        f"Continue gathering context as needed, but checkpoint before "
                        f"{_READS_HARD_LIMIT} reads with store_memory or write_file. "
                        "Do not keep rereading the same files."
                    )
                else:
                    # Single-edit-first nudge (converged on independently by codex, 578bc847,
                    # + this session). Measured basis: the local model read-loops on
                    # multi-site edit tasks but succeeds at ONE edit (EXP3), so reframing to
                    # "make exactly ONE edit now, others later" targets the stuck read->edit
                    # transition. EFFECTIVENESS INCONCLUSIVE: the one validation run
                    # (reference-local-agent-capability-envelope EXP5) read-looped to call 17
                    # with 0 edits but was cut off by a first-token wedge, not a clean finish
                    # — needs a clean non-wedged run to confirm. Low-risk (only fires when the
                    # agent is already stuck). The proven multi-edit path remains the external
                    # decomposer (scripts/ai/aq-sequential-edit).
                    nudge_content = (
                        f"STOP READING — you have read {_reads_without_edit} times without "
                        "editing. Do NOT read again. Make exactly ONE edit now: pick the "
                        "single most concrete change from the BEHAVIORAL CONTRACT and emit "
                        "ONE edit_file call for it (exact old_string anchor + new_string). "
                        "Ignore every other change this turn — you will make them one at a "
                        "time in the following turns. One edit_file call, now."
                    )
                messages.append({"role": "user", "content": nudge_content})
                logger.info(
                    "exploration-nudge injected after %d reads without edit at call %d",
                    _reads_without_edit, tool_call_count,
                )

            # Validation stall nudge: code passed validation N times but model won't commit.
            if _validation_passes_without_commit >= _VALIDATION_STALL_NUDGE:
                messages.append({
                    "role": "user",
                    "content": (
                        f"COMMIT STALL: validate_before_commit or run_command has passed "
                        f"{_validation_passes_without_commit} times without a git_commit. "
                        "The code is ready. If edit_file for the [DONE] marker is failing, "
                        "call git_add now with only the changed code files, then git_commit "
                        "immediately. Do NOT validate again."
                    ),
                })
                logger.info(
                    "validation-stall nudge injected after %d passes without commit at call %d",
                    _validation_passes_without_commit, tool_call_count,
                )
                _validation_passes_without_commit = 0

    def _tool_call_grammar(self, *, force_repair: bool = False) -> Optional[str]:
        """P2: GBNF constraining output to the tool-call envelope over the ENABLED tools. Returns None
        unless AQ_LOCAL_GBNF is set (default OFF) or a repair-only retry explicitly requests it.
        Cached on the instance keyed by the enabled-tool set (the lease can hot-swap mid-run)."""
        if tool_grammar is None:
            return None
        if force_repair:
            if not _LOCAL_GBNF_REPAIR_ENABLED:
                return None
        elif not _LOCAL_GBNF_ALWAYS_ENABLED:
            return None
        try:
            names = sorted(t.name for t in self.tool_registry.tools.values() if getattr(t, "enabled", True))
            cache_key = tuple(names)
            cached = getattr(self, "_gbnf_cache", None)
            if cached and cached[0] == cache_key:
                return cached[1]
            grammar, _hit = tool_grammar.tool_call_grammar(names)
            self._gbnf_cache = (cache_key, grammar)
            return grammar
        except Exception:  # noqa: BLE001 — grammar is an optimization; never break the call on it
            return None

    def _cassette_replay(
        self, payload: Dict[str, Any], task_type: Optional[str]
    ) -> Optional[Tuple[str, int]]:
        """Record/replay harness hook — consult the cassette before the HTTP call.
            return None

    def _cassette_replay(
        self, payload: Dict[str, Any], task_type: Optional[str]
    ) -> Optional[Tuple[str, int]]:
        """Record/replay harness hook — consult the cassette before the HTTP call.

        Returns (content, tokens) on a replay hit (caller must return it immediately,
        skipping the network entirely); None means "proceed live" (default-off mode,
        record mode, replay-record miss, or on-miss=passthrough). Raises
        llm_cassette.ReplayMiss only when the operator explicitly asked for strict
        replay (AQ_LLM_CASSETTE_ON_MISS=error, the default in replay mode) — that is a
        deliberate test-failure signal, not swallowed here.
        """
        if llm_cassette is None:
            return None
        return llm_cassette.replay_lookup(payload, task_type)

    def _cassette_record(
        self,
        payload: Dict[str, Any],
        task_type: Optional[str],
        content: str,
        tokens: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record/replay harness hook — tee a live result into the cassette. No-op
        unless AQ_LLM_CASSETTE_MODE is record/replay-record; never raises."""
        if llm_cassette is None:
            return
        llm_cassette.maybe_record(payload, task_type, content, tokens, meta)

    async def _call_llama(
        self,
        messages: List[Dict],
        role: Optional[str] = None,
        max_tokens: int = AGENT_TOOL_CALL_MAX_TOKENS,
        task_type: Optional[str] = None,
        task_id: Optional[str] = None,
        call_number: int = 0,
        force_tool_grammar: bool = False,
    ) -> Tuple[str, int]:
        """
        Call local llama.cpp server using SSE streaming.

        Uses per-chunk read timeout (LLAMA_CHUNK_TIMEOUT env, default 120s) instead of a
        wall-clock total timeout so long-reasoning tasks never time out as long as tokens
        flow.  Falls back to a non-streaming POST if streaming is explicitly disabled via
        LLAMA_USE_STREAMING=false.

        Args:
            messages: Conversation messages
            task_type: Optional llm_config profile name. When set, profile drives
                temperature, frequency_penalty, thinking_budget, and enable_thinking.
                When None, hardcoded temperature=0.2, frequency_penalty=0.05 (legacy).

        Returns:
            (response_text, tokens_used) — tokens_used is total_tokens from the usage chunk.
        """
        use_streaming = _env_flag("LLAMA_USE_STREAMING", default=True)
        chunk_timeout = _env_float("LLAMA_CHUNK_TIMEOUT", default=120.0)
        first_token_timeout = _env_float(
            "LLAMA_FIRST_TOKEN_TIMEOUT",
            default=min(chunk_timeout, 600.0),
        )

        # Agent tool calls: 512 tokens (50-100 for JSON + 400 for summary).
        # At 1-2 tok/s on Renoir APU, 512 tokens = 256-512s max generation.
        # 4096 would risk 68-minute slot locks when clients disconnect.
        # When task_type is set the profile drives temperature; otherwise use 0.2.
        _temperature: Optional[float] = None if task_type else 0.2

        # Prefill-wedge guard (root-cause fix for orphaned-slot cascades): a single oversized prompt
        # — e.g. an un-compacted large-file read that slipped past the >8-message context pruning —
        # causes a prefill longer than first_token_timeout on the single-slot APU. The client gives up
        # but llama.cpp keeps prefilling, ORPHANING the only slot and wedging ALL subsequent local
        # dispatches (a wedged slot then starves unrelated tasks — this is how a victim task fails with
        # 0 tool calls). Fail FAST here with a clean, capturable error instead of sending a request that
        # will wedge the slot. Ceiling ~6000 tok leaves headroom under the 8192 ctx for generation.
        _prompt_chars = sum(len(m.get("content") or "") for m in messages)
        _max_prompt_chars = int(os.getenv("LLAMA_MAX_PROMPT_CHARS", "24000"))
        if _prompt_chars > _max_prompt_chars:
            raise RuntimeError(
                f"prompt too large for single-slot prefill: {_prompt_chars} chars > {_max_prompt_chars} "
                "(LLAMA_MAX_PROMPT_CHARS) — refusing to send; an oversized prefill would orphan/wedge the "
                "llama.cpp slot. Trim context: ranged reads, tool-result compaction, or fewer files."
            )

        if not use_streaming:
            # Legacy non-streaming path — 300s wall-clock limit.
            _payload_kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": role}
            if _temperature is not None:
                _payload_kwargs["temperature"] = _temperature
            if task_type:
                _payload_kwargs["task_type"] = task_type
            _gbnf = self._tool_call_grammar(force_repair=force_tool_grammar)
            if _gbnf:
                _payload_kwargs["grammar"] = _gbnf
            payload = build_llama_payload(messages, **_payload_kwargs)

            # Record/replay harness — replay hit skips the HTTP call entirely (no-op
            # when AQ_LLM_CASSETTE_MODE=off, the default).
            _cassette_hit = self._cassette_replay(payload, task_type)
            if _cassette_hit is not None:
                return _cassette_hit

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.llama_endpoint}/v1/chat/completions",
                    json=payload,
                    timeout=300.0,
                    headers={"x-ai-profile": os.environ.get("AGENT_SWITCHBOARD_PROFILE", "local-agent")},
                )
                if response.status_code != 200:
                    raise Exception(f"llama.cpp error: {response.status_code} {response.text}")
                data = response.json()
                tokens = data.get("usage", {}).get("total_tokens", 0)
                content = data["choices"][0]["message"]["content"]
                self._cassette_record(payload, task_type, content, tokens, {"path": "legacy"})
                return content, tokens

        # Streaming path: collect SSE delta chunks.
        # Pass stream=True so build_llama_payload includes stream_options.include_usage=True,
        # which causes llama.cpp to emit a final usage-only chunk for token tracking.
        # httpx.Timeout(read=chunk_timeout) is per-read-operation (per chunk), not total.
        _stream_kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": role, "stream": True}
        if _temperature is not None:
            _stream_kwargs["temperature"] = _temperature
        if task_type:
            _stream_kwargs["task_type"] = task_type
        _gbnf = self._tool_call_grammar(force_repair=force_tool_grammar)
        if _gbnf:
            _stream_kwargs["grammar"] = _gbnf
        payload = build_llama_payload(messages, **_stream_kwargs)

        # Record/replay harness — replay hit skips SSE streaming entirely (no-op when
        # AQ_LLM_CASSETTE_MODE=off, the default).
        _cassette_hit = self._cassette_replay(payload, task_type)
        if _cassette_hit is not None:
            return _cassette_hit

        read_timeout = min(chunk_timeout, first_token_timeout)
        timeout = httpx.Timeout(connect=10.0, read=read_timeout, write=10.0, pool=5.0)

        collected: List[str] = []
        tokens_used = 0
        progress_file = os.getenv("AGENT_PROGRESS_FILE")
        last_progress_write = 0.0

        def _write_stream_progress(status: str, force: bool = False) -> None:
            nonlocal last_progress_write
            if not progress_file:
                return
            now = time.time()
            if not force and len(collected) % 10 != 0 and now - last_progress_write < 30:
                return
            try:
                Path(progress_file).write_text(json.dumps({
                    "task_id": task_id,
                    "status": status,
                    "tool_call_count": call_number,
                    "llm_stream_chunks": len(collected),
                    "llm_stream_chars": sum(len(part) for part in collected),
                    "max_tokens": max_tokens,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
                }, indent=2))
                last_progress_write = now
            except Exception:
                pass

        # Live stream tail — the raw LLM output/reasoning as it streams, for near-real-time
        # monitoring in aq-tui-dashboard --matrix (reads .agents/delegation/streams/<id>.txt).
        # Throttled ~0.7s; independent of AGENT_PROGRESS_FILE. This is what lets the operator
        # watch a local agent's thoughts/output live, like its native CLI.
        _stream_dir = Path(__file__).resolve().parents[2] / ".agents" / "delegation" / "streams"
        _stream_file = _stream_dir / f"{task_id}.txt"
        _last_stream_write = [0.0]

        def _write_stream_tail(final: bool = False) -> None:
            now = time.time()
            if not final and now - _last_stream_write[0] < 0.7:
                return
            _last_stream_write[0] = now
            try:
                _stream_dir.mkdir(parents=True, exist_ok=True)
                _stream_file.write_text("".join(collected)[-4000:])
            except OSError:
                pass

        try:
            _write_stream_progress("llm_waiting", force=True)
            _stream_start = time.monotonic()
            # x-ai-profile: local-agent -> if the endpoint is the switchboard (:8085),
            # route to the passthrough local-agent lane (no card injection / payload
            # transform) so we gain the switchboard's concurrency + observability without
            # changing agent behavior. Harmless (ignored) when hitting llama.cpp directly.
            _route_headers = {"x-ai-profile": os.environ.get("AGENT_SWITCHBOARD_PROFILE", "local-agent")}
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.llama_endpoint}/v1/chat/completions",
                    json=payload,
                    headers=_route_headers,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise Exception(f"llama.cpp error: {response.status_code} {body.decode()[:200]}")

                    async for raw_line in response.aiter_lines():
                        # Wall-clock first-token watchdog. llama.cpp emits keep-alive/empty
                        # SSE lines during a long single-slot prefill, which reset httpx's
                        # per-read timer — so the per-chunk read timeout never bounds
                        # first-token and a wedged prefill hangs for the full (hours-long)
                        # chunk_timeout. Enforce an explicit wall-clock bound until the first
                        # CONTENT token; fires even while keep-alives arrive. Measured: this
                        # is what let runs wedge 10-23 min with 0 tokens.
                        if not collected and (time.monotonic() - _stream_start) > first_token_timeout:
                            raise RuntimeError(
                                f"LLM first-token timeout: no content within "
                                f"{first_token_timeout:.0f}s of request start "
                                "(single-slot prefill wedge or context too large)."
                            )
                        line = raw_line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            line = line[len("data: "):]
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices", [{}])
                        if not choices:
                            # Usage-only chunk emitted when stream_options.include_usage=True
                            usage = chunk.get("usage", {})
                            if usage:
                                tokens_used = usage.get("total_tokens", 0)
                                _write_stream_progress("llm_usage", force=True)
                            continue
                        delta = choices[0].get("delta", {})
                        token = delta.get("content") or ""
                        if token:
                            collected.append(token)
                            _write_stream_progress("llm_streaming")
                            _write_stream_tail()
        except httpx.ReadTimeout:
            raise RuntimeError(
                f"LLM no-progress timeout: server silent for >{read_timeout:.0f}s "
                f"(first_token_timeout={first_token_timeout:.0f}, chunk_timeout={chunk_timeout:.0f}; "
                "context may be too large or the inference slot may be wedged)"
            )
        except httpx.ConnectError as _ce:
            raise RuntimeError(f"LLM connection refused at {self.llama_endpoint}: {_ce}") from _ce
        except httpx.NetworkError as _ne:
            raise RuntimeError(f"LLM network error: {_ne}") from _ne

        _write_stream_tail(final=True)
        content = "".join(collected)
        self._cassette_record(payload, task_type, content, tokens_used, {"path": "streaming"})
        return content, tokens_used

    async def _fallback_to_remote(self, task: Task) -> Task:
        """
        Fallback to remote agent (hybrid coordinator).

        Gap-pattern fix (44x): on provider 429/503, capture error details and
        retry once with a simplified payload (reduced max_tokens, stripped context).
        This prevents the same large payload from triggering the same rate-limit error.

        Args:
            task: Task to execute remotely

        Returns:
            Updated task with remote result
        """
        start_time = time.time()
        task.status = TaskStatus.FALLBACK
        task.assigned_agent = "remote-fallback"
        task.degraded_reason = None

        _RETRY_STATUSES = {429, 503, 502}

        try:
            async with httpx.AsyncClient() as client:
                profile = self._select_remote_profile(task)
                base_payload = self._build_remote_delegate_payload(task, profile)
                delegate_response = await client.post(
                    f"{self.fallback_endpoint}/control/ai-coordinator/delegate",
                    json=base_payload,
                    timeout=self.remote_timeout_seconds,
                )

                if delegate_response.status_code in _RETRY_STATUSES:
                    # Gap rule: log provider-specific failure, simplify payload, retry once.
                    logger.warning(
                        "remote_delegate_provider_error: status=%d detail=%s — retrying with simplified payload",
                        delegate_response.status_code,
                        delegate_response.text[:120],
                    )
                    await asyncio.sleep(2.0)
                    simplified = {
                        "task": task.objective[:800],
                        "profile": "remote-free",
                        "prefer_local": True,
                        "max_tokens": 400,
                    }
                    delegate_response = await client.post(
                        f"{self.fallback_endpoint}/control/ai-coordinator/delegate",
                        json=simplified,
                        timeout=self.remote_timeout_seconds,
                    )

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "rg -n \"asyncio\\.wait_for|timeout_seconds|max_tool|max_calls|MAX_TOOL|tool_call_count >=|elapsed|_loop_start|execute_task|execute\\(\" ai-stack/local-agents/agent_executor.py | sed -n '1,220p'
sed -n '1500,1740p' ai-stack/local-agents/agent_executor.py
sed -n '1860,2150p' ai-stack/local-agents/agent_executor.py
sed -n '2150,2335p' ai-stack/local-agents/agent_executor.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 70ms:
211:    max_tools: int = 8,
217:    max_tools is generous (8) here because tool descriptions are text, not JSON schemas.
236:        if len(result_tools) >= max_tools:
765:        remote_timeout_seconds: Optional[float] = None,
766:        remote_probe_timeout_seconds: Optional[float] = None,
782:        self.remote_timeout_seconds = (
784:            if remote_timeout_seconds is None
785:            else remote_timeout_seconds
787:        self.remote_probe_timeout_seconds = (
789:            if remote_probe_timeout_seconds is None
790:            else remote_probe_timeout_seconds
904:    async def execute_task(
908:        max_tool_calls: int = 0,
916:            max_tool_calls: Deprecated compatibility parameter. Tool loops are
1011:                max_tool_calls,
1113:        max_tool_calls: int,
1190:        _loop_start = time.time()
1208:            elapsed = time.time() - _watchdog_last_activity[0]
1209:            if elapsed >= STALL_TIMEOUT - 1:
1212:                    {"elapsed_s": round(elapsed, 1), "advisory": True},
1319:            elapsed = time.time() - _loop_start
1345:                        "elapsed_s": round(elapsed, 1),
1368:                            "elapsed_s": round(elapsed, 1),
1387:                        "elapsed_s": round(elapsed, 1),
1403:                            "elapsed_s": round(elapsed, 1),
2624:                    timeout=self.remote_timeout_seconds,
2644:                        timeout=self.remote_timeout_seconds,
2671:                        timeout=self.remote_timeout_seconds,
2991:                response = await client.get(health_url, timeout=self.remote_probe_timeout_seconds)
3048:            result = await self.execute_task(phase_task)
3108:        result = await executor.execute_task(task)
                # Fallback for 6 < len ≤ 8: can't do full pinned+sliding, just shed oldest pair.
                # Verify messages[2:4] form a valid (assistant, tool) pair before dropping —
                # a dangling role:tool without its role:assistant corrupts the conversation graph.
                _m2_role = messages[2].get("role") if len(messages) > 2 else None
                _m3_role = messages[3].get("role") if len(messages) > 3 else None
                if _m2_role == "assistant" and _m3_role == "tool":
                    messages = messages[:2] + messages[4:]
                    logger.debug("context_prune(shed-oldest-pair): messages now %d", len(messages))
                else:
                    logger.debug(
                        "context_prune(shed-oldest-pair): SKIP — messages[2:4] roles=%s/%s not assistant/tool pair",
                        _m2_role, _m3_role,
                    )

            # Call model — use larger budget once tools have been used so that
            # the final synthesis turn (no tool_call in response) isn't capped at
            # the tool-call budget (512).  First call keeps 512 since the model
            # almost always emits a tool call there (short JSON, EOS quick).
            call_max_tokens = AGENT_TASK_MAX_TOKENS if tool_call_count > 0 else AGENT_TOOL_CALL_MAX_TOKENS
            try:
                response, tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=call_max_tokens,
                    task_type=task.task_type,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
            except Exception as _llm_err:
                # Retry once with reduced budget on transient failures (timeout, connection drop).
                logger.warning(
                    "LLM call %d failed (%r), retrying with 512 tokens",
                    tool_call_count + 1, str(_llm_err)[:120],
                )
                response, tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=512,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
            total_tokens += tok
            if not response.strip():
                # Retry once with a nudge before failing the task. Empty responses happen
                # when the server is cold or the model stalls — a single retry recovers most
                # transient cases without burning the full budget.
                _ctx_chars_at_fail = sum(len((m.get("content") or "")) for m in messages)
                logger.warning(
                    "empty response at call %d (ctx ~%d chars) — retrying once with nudge",
                    tool_call_count + 1, _ctx_chars_at_fail,
                )
                _nudge_messages = messages + [{
                    "role": "user",
                    "content": "Your previous response was empty. Please provide a JSON tool call or a plain-text final answer now.",
                }]
                response, _retry_tok = await self._call_llama(
                    _nudge_messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += _retry_tok
                if response.strip():
                    messages = _nudge_messages
                else:
                    raise RuntimeError(
                        f"LLM returned empty response at call {tool_call_count + 1} "
                        f"(context ~{_ctx_chars_at_fail} chars)"
                    )

            # Parse tool call
            tool_call = self.tool_registry.parse_tool_call_from_llama(response)

            if not tool_call:
                # No tool call — could be prose synthesis (correct) or a truncated/malformed
                # tool-call JSON (model tried to call a tool but got cut off at max_tokens, or
                # the parser rejected it due to embedded newlines in string values).
                # Detect the latter by checking for the {"function" prefix that Qwen3 uses.
                # Fire on ANY turn — tool_call_count > 0 was too narrow; the model can output
                # a JSON tool call as its very first response if the parse failed (e.g. embedded
                # bare newlines in old_string/new_string values).
                if response.lstrip().startswith('{"function"'):
                    if _LOCAL_GBNF_REPAIR_ENABLED:
                        repair_messages = messages + [
                            {"role": "assistant", "content": response},
                            {
                                "role": "user",
                                "content": (
                                    "The previous output was malformed tool-call JSON. "
                                    "Return exactly one valid JSON tool call matching the available tool schema. "
                                    "No prose."
                                ),
                            },
                        ]
                        try:
                            repaired_response, repair_tokens = await self._call_llama(
                                repair_messages,
                                role=role,
                                max_tokens=AGENT_TOOL_CALL_MAX_TOKENS,
                                task_type=task.task_type,
                                task_id=task.id,
                                call_number=tool_call_count + 1,
                                force_tool_grammar=True,
                            )
                            total_tokens += repair_tokens
                            repaired_tool_call = self.tool_registry.parse_tool_call_from_llama(repaired_response)
                            if repaired_tool_call:
                                logger.info(
                                    "gbnf-repair: recovered malformed tool call at call %d",
                                    tool_call_count + 1,
                                )
                                response = repaired_response
                                tool_call = repaired_tool_call
                        except Exception as _repair_err:
                            logger.warning(
                                "gbnf-repair: constrained retry failed at call %d: %s",
                                tool_call_count + 1,
                                str(_repair_err)[:120],
                            )
                    if not tool_call:
                        logger.warning(
                            "final-response-is-tool-call: response looks like truncated tool call at "
                            "call %d — requesting prose synthesis (max_tokens=256)",
                            tool_call_count,
                        )
                        # P1: this is an unambiguous local failure — the model emitted a tool-call JSON
                        # the parser rejected (truncated/malformed). Capture it as a labeled training
                        # sample so the loop can learn from it. Best-effort; never breaks the turn.
                        if training_capture is not None:
                            last_user = next((m.get("content", "") for m in reversed(messages)
                                              if m.get("role") == "user"), "")
                            training_capture.capture_failure(
                                prompt=last_user,
                                bad_output=response,
                                failure_class="invalid_tool_json",
                                tools_available=[t.name for t in self.tool_registry.tools.values()
                                                 if getattr(t, "enabled", True)],
                                source="agent_executor.parse_failed",
                                model_provenance={"lane": "local", "call_number": tool_call_count},
                            )
                        messages.append({"role": "assistant", "content": response})
                        messages.append({
                            "role": "user",
                            "content": (
                                "The previous output was incomplete. "
                                "Write ONE prose sentence starting with 'COMPLETED:' summarising what was done. "
                                "No JSON. No tool calls."
                            ),
                        })
                        prose, syn_tokens = await self._call_llama(
                            messages,
                            role=role,
                            max_tokens=256,
                            task_id=task.id,
                            call_number=tool_call_count + 1,
                        )
                        total_tokens += syn_tokens
                        _cancel_watchdog()
                        return prose.strip() if prose.strip() else response, total_tokens
                if not tool_call:
                    # No-action guard: an implementer/edit task with zero successful
                    # edits so far that returns non-empty prose with no tool call is a
                    # narrated PLAN ("Thought: I would change X..."), not completion —
                    # accepting it silently ends the task having changed nothing. Refuse
                    # it ONCE and force an edit_file call instead. A genuine refusal
                    # ("cannot safely...", "under-specified...") still completes normally,
                    # and a second prose-only response completes too (no infinite loop).
                    # Fail-safe: any error here falls through to the existing completion
                    # path below rather than crashing the turn.
                    if (
                        _NOACTION_INTERVENTION_ENABLED
                        and not _is_analysis_only_task
                        and _edits_made == 0
                        and not _no_action_intervention_sent
                        and response.strip()
                    ):
                        try:
                            if not _looks_like_refusal(response):
                                _no_action_intervention_sent = True
                                intervention_msg = (
                                    "You described the change but did NOT make it — no "
                                    "file has been edited yet. Do NOT answer in prose. "
                                    "Call edit_file NOW: use the exact code from the "
                                    "'## Relevant prior knowledge' block above as "
                                    "old_string and your changed version as new_string. "
                                    "The task is only complete once edit_file has "
                                    "changed the file."
                                )
                                messages.append({"role": "assistant", "content": response})
                                messages.append({
                                    "role": "user",
                                    "content": intervention_msg,
                                })
                                logger.warning(
                                    "no-action intervention: prose-only response with 0 "
                                    "edits made at call %d — injecting one-shot "
                                    "edit-forcing nudge instead of completing",
                                    tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "noaction_intervention",
                                    {"tool_call_count": tool_call_count},
                                    _watchdog_last_activity,
                                )
                                continue
                        except Exception as _noaction_err:
                            logger.warning(
                                "no-action-intervention construction failed (%s) — "
                                "falling through to normal completion", _noaction_err,
                            )
                            # Fall through to the plain completion below (fail-safe:
                            # never let a broken intervention crash or hang the loop).
                    # Phase E — agent_synthesis_start: no tool call in response after ≥1 tool calls.
                    if tool_call_count > 0:
                        await self._emit_agent_event(
                            task.id, "agent_synthesis_start",
                            {"tool_call_count": tool_call_count},
                            _watchdog_last_activity,
                        )
                    _cancel_watchdog()
                    return response, total_tokens

            # Phase E — agent_tool_intent: emitted after parsing, before dispatch.
            await self._emit_agent_event(
                task.id, "agent_tool_intent",
                {
                    "tool_name": tool_call.tool_name,
                    "tool_args_preview": json.dumps(
                        tool_call.arguments,
                        sort_keys=True,
                        default=str,
                    )[:200],
                },
                _watchdog_last_activity,
            )

            # Execute tool call
            tool_call.model_id = f"local-{agent_type.value}"
            tool_call.session_id = task.id

            # reachable across long implementation loops.
            # Thresholds are tool-specific:
            #   read_file  → 3: pure observation; identical result 3× = definitely stuck.
            #   run_command → 5: polling loops (e.g. tail, systemctl) legitimately repeat.
            threshold = (
                _STAGNATION_THRESHOLD_READ
                if result.tool_name == "read_file"
                else _STAGNATION_THRESHOLD_OTHER
            )
            _recent_tools.append((result.tool_name, formatted_result[:200]))
            if len(_recent_tools) > threshold:
                _recent_tools.pop(0)
            if (
                len(_recent_tools) == threshold
                and len({t for t, _ in _recent_tools}) == 1   # same tool name
                and len({r for _, r in _recent_tools}) == 1   # same result prefix
            ):
                stagnation_msg = (
                    f"Stagnation detected: '{result.tool_name}' called {threshold} consecutive "
                    f"times with identical result — loop aborted to prevent runaway. "
                    f"Last result prefix: {formatted_result[:300]}"
                )
                logger.warning(
                    "stagnation: tool=%r threshold=%d — aborting loop at call %d",
                    result.tool_name, threshold, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            # File-not-found stagnation: if the same path keeps returning an error
            # (file not found), the model is stuck in a search loop. Abort early.
            if result.tool_name == "read_file" and (
                result.status == "failed"
                or (result.result is not None and not result.result.get("success", True))
            ):
                _fp = (result.arguments or {}).get("file_path", "")
                if _fp:
                    _failed_reads[_fp] = _failed_reads.get(_fp, 0) + 1
                    if _failed_reads[_fp] >= _FAILED_READ_LIMIT:
                        stagnation_msg = (
                            f"File-not-found stagnation: '{_fp}' has returned an error "
                            f"{_FAILED_READ_LIMIT} times — file does not exist or is inaccessible. "
                            f"Aborting loop at call {tool_call_count} to prevent runaway search."
                        )
                        logger.warning(
                            "file-not-found stagnation: path=%r failed %d times — aborting at call %d",
                            _fp, _FAILED_READ_LIMIT, tool_call_count,
                        )
                        _cancel_watchdog()
                        return stagnation_msg, total_tokens

            # Per-tool failure stagnation: track tools that persistently return errors.
            # Catches loops like harness_health(fail)→store_memory(ok)→harness_health(fail)
            # that reset the observation counter but never make forward progress.
            _is_tool_failure = (
                result.status == "failed"
                or (
                    result.result is not None
                    and (
                        not result.result.get("success", True)
                        or result.result.get("exit_code", 0) not in (None, 0)
                        or result.result.get("error") is not None
                    )
                )
            )
            if _is_tool_failure:
                _tool_failure_counts[result.tool_name] = _tool_failure_counts.get(result.tool_name, 0) + 1
                if _tool_failure_counts[result.tool_name] >= _TOOL_FAILURE_HARD_LIMIT:
                    stagnation_msg = (
                        f"Tool-failure stagnation: '{result.tool_name}' has failed "
                        f"{_tool_failure_counts[result.tool_name]} times — persistent infra error, "
                        f"not fixable by the agent. Aborting at call {tool_call_count}."
                    )
                    logger.warning(
                        "tool-failure stagnation: tool=%r failed %d times — aborting at call %d",
                        result.tool_name, _tool_failure_counts[result.tool_name], tool_call_count,
                    )
                    _cancel_watchdog()
                    return stagnation_msg, total_tokens

            # Exploration stagnation: count reads vs edits/writes.
            # Reset counter on any write action; abort if model reads too many files
            # without acting (prevents over-exploration in self-improvement tasks).
            if result.tool_name == "read_file":
                _reads_without_edit += 1
                read_path = str(result.arguments.get("file_path") or result.arguments.get("path") or "")
                if read_path:
                    _read_path_counts[read_path] = _read_path_counts.get(read_path, 0) + 1
                    if _read_path_counts[read_path] >= _REPEATED_READ_PATH_LIMIT:
                        # First breach: inject a one-shot edit-forcing intervention instead
                        # of aborting. The relevant code is already front-loaded verbatim
                        # under "## Relevant prior knowledge" — the plain abort discarded
                        # tasks local could complete once nudged off the read->edit stall.
                        # Delivered as the read_file tool result (role:"tool") so the model
                        # actually sees it as the outcome of ITS OWN last tool call next turn.
                        if _REREAD_INTERVENTION_ENABLED and not _reread_intervention_sent:
                            try:
                                _reread_intervention_sent = True
                                _iv_brace = response.rfind('{"function"')
                                if _iv_brace == -1:
                                    _iv_brace = response.rfind("{")
                                _iv_clean_call = (
                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
                                )
                                intervention_msg = (
                                    f"You have read {read_path!r} "
                                    f"{_read_path_counts[read_path]} times and it keeps returning "
                                    "the same content — reading it again will not help. STOP "
                                    "reading. The relevant code for this task is ALREADY in your "
                                    "context above under '## Relevant prior knowledge' as exact "
                                    "fenced code blocks (byte-identical to the file). Call "
                                    "edit_file NOW: use the exact text from one of those code "
                                    "blocks as old_string (it will match), and provide your "
                                    "changed version as new_string. Do not call read_file on "
                                    "this file again."
                                )
                                messages.append({"role": "assistant", "content": _iv_clean_call})
                                messages.append({
                                    "role": "tool",
                                    "name": result.tool_name,
                                    "content": intervention_msg,
                                })
                                logger.warning(
                                    "repeated-read intervention: path=%r reads=%d call=%d — "
                                    "injecting one-shot edit-forcing nudge instead of aborting",
                                    read_path, _read_path_counts[read_path], tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "reread_intervention",
                                    {
                                        "file_path": read_path,
                                        "reads": _read_path_counts[read_path],
                                        "tool_call_count": tool_call_count,
                                    },
                                    _watchdog_last_activity,
                                )
                                continue
                            except Exception as _interv_err:
                                logger.warning(
                                    "reread-intervention construction failed (%s) — "
                                    "falling back to plain abort", _interv_err,
                                )
                                # Fall through to the plain abort below (fail-safe: never
                                # let a broken intervention crash or hang the loop).
                        stagnation_msg = (
                            f"Repeated-read stagnation: {read_path!r} was read "
                            f"{_read_path_counts[read_path]} times without progress. "
                            f"Aborting at tool call {tool_call_count}."
                        )
                        logger.warning(
                            "repeated-read stagnation: path=%r reads=%d call=%d",
                            read_path, _read_path_counts[read_path], tool_call_count,
                        )
                        _cancel_watchdog()
                        return stagnation_msg, total_tokens
            elif result.tool_name in ("edit_file", "write_file", "write_region"):
                _reads_without_edit = 0
                _read_path_counts.clear()
                if not _is_tool_failure:
                    _edits_made += 1
                elif result.tool_name == "edit_file":
                    # Edit-failure feedback: old_string byte-mismatch is now the
                    # dominant local-agent failure mode (see _EDIT_FEEDBACK_ENABLED
                    # above). On the FIRST such mismatch failure for this file
                    # (bounded to _EDIT_FEEDBACK_MAX_PER_FILE), inject the file's
                    # EXACT current text for the attempted region as the tool
                    # result instead of the bare failure, then let the loop
                    # continue — never crash or hang on a broken feedback build.
                    _ef_err = str((result.result or {}).get("error", "")) if result.result else ""
                    _ef_path = str(
                        (result.arguments or {}).get("file_path")
                        or (result.arguments or {}).get("path")
                        or ""
                    )
                    _ef_fires = _edit_feedback_counts.get(_ef_path, 0)
                    if (
                        _EDIT_FEEDBACK_ENABLED
                        and _ef_path
                        and _looks_like_edit_mismatch(_ef_err)
                        and _ef_fires < _EDIT_FEEDBACK_MAX_PER_FILE
                    ):
                        try:
                            _ef_region = _build_edit_mismatch_feedback(
                                _ef_path,
                                str((result.arguments or {}).get("old_string") or ""),
                                char_budget=_EDIT_FEEDBACK_CHAR_BUDGET,
                            )
                            if _ef_region:
                                _edit_feedback_counts[_ef_path] = _ef_fires + 1
                                _iv_brace = response.rfind('{"function"')
                                if _iv_brace == -1:
                                    _iv_brace = response.rfind("{")
                                _iv_clean_call = (
                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
                                )
                                feedback_msg = (
                                    "edit_file FAILED: your old_string did not match the "
                                    "file. The file's EXACT current text for that region is "
                                    "below — copy an exact substring of THIS as your "
                                    "old_string (character-for-character, including "
                                    "indentation) and retry edit_file.\n\n" + _ef_region
                                )
                                messages.append({"role": "assistant", "content": _iv_clean_call})
                                messages.append({
                                    "role": "tool",
                                    "name": result.tool_name,
                                    "content": feedback_msg,
                                })
                                logger.warning(
                                    "edit-mismatch feedback: path=%r attempt=%d call=%d — "
                                    "injecting exact-region feedback instead of plain failure",
                                    _ef_path, _edit_feedback_counts[_ef_path], tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "edit_feedback_intervention",
                                    {
                                        "file_path": _ef_path,
                                        "attempt": _edit_feedback_counts[_ef_path],
                                        "tool_call_count": tool_call_count,
                                    },
                                    _watchdog_last_activity,
                                )
                                continue
                        except Exception as _ef_err_exc:
                            logger.warning(
                                "edit-feedback construction failed (%s) — "
                                "falling through to plain failure", _ef_err_exc,
                            )
                            # Fall through to the normal failure-result append below.
            elif _is_analysis_only_task and result.tool_name == "store_memory":
                _reads_without_edit = 0
                _read_path_counts.clear()

            # Validation stall: detect repeated validate_before_commit/run_command
            # without any intervening commit. Model validated the code is ready but
            # won't pull the trigger. Nudge it to git_add → git_commit immediately.
            if result.tool_name in ("validate_before_commit", "run_command") and result.status == "completed":
                _validation_passes_without_commit += 1
            elif result.tool_name in ("write_file", "edit_file", "write_region", "git_add", "git_commit"):
                _validation_passes_without_commit = 0

            # Observation stagnation: track harness query calls vs action calls.
            if result.tool_name in _OBSERVATION_QUERY_TOOLS:
                _observations_without_action += 1
            elif result.tool_name in _OBSERVATION_ACTION_TOOLS:
                _observations_without_action = 0

            if _reads_without_edit >= _READS_HARD_LIMIT:
                if _is_analysis_only_task:
                    stagnation_msg = (
                        f"Analysis checkpoint stagnation: {_reads_without_edit} consecutive "
                        f"reads without store_memory or write_file checkpoint — model stuck "
                        f"in analysis phase. Aborting at tool call {tool_call_count}."
                    )
                else:
                    stagnation_msg = (
                        f"Exploration stagnation: {_reads_without_edit} consecutive reads without "
                        f"any edit_file or write_file — model stuck in exploration phase. "
                        f"Aborting at tool call {tool_call_count}."
                    )
                logger.warning(
                    "exploration/checkpoint stagnation: %d reads task_type=%r call=%d",
                    _reads_without_edit, task.task_type, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            if _observations_without_action >= _OBSERVATIONS_HARD_LIMIT:
                stagnation_msg = (
                    f"Observation stagnation: {_observations_without_action} consecutive "
                    f"harness query calls (get_hint/query_aidb/etc.) without any action — "
                    f"model is stuck in an observation loop. "
                    f"Aborting at tool call {tool_call_count}."
                )
                logger.warning(
                    "observation stagnation: %d queries without action — aborting at call %d",
                    _observations_without_action, tool_call_count,
                )
                _cancel_watchdog()
                return stagnation_msg, total_tokens

            # Extract the clean JSON from the response so the assistant turn
            # contains only the tool call object, not any leading prose.
            # Qwen3's chat template strips unknown roles — "function" is not
            # in its vocabulary; "tool" is the correct role for tool results.
            brace = response.rfind('{"function"')
            if brace == -1:
                brace = response.rfind("{")
            clean_call = response[brace:].strip() if brace != -1 else response.strip()

            # Capture prose before the tool call JSON (model's reasoning/thinking).
            # Capture prose before the tool call JSON (model's reasoning/thinking).
            # This is the text the model emitted BEFORE the structured tool call —
            # the "thinking aloud" surface that would otherwise be invisible.
            prose_before = response[:brace].strip() if brace > 0 else ""

            # Emit per-step telemetry to all observability surfaces (non-blocking).
            _emit_step_telemetry(result, tool_call_count, prose_before)

            messages.append({
                "role": "assistant",
                "content": clean_call,
            })
            messages.append({
                "role": "tool",
                "name": result.tool_name,
                "content": formatted_result,
            })

            # A.6 — hot-swap: expand active tool set based on what the result reveals.
            # Monotonic expansion only (never shrinks). Rebuilds messages[0] (system prompt)
            # when new tools are added so the model sees the expanded surface next call.
            _prev_tool_count = len(_active_tools)
            _active_tools = _refresh_active_tools(
                result.tool_name, formatted_result, _active_tools, _all_tools,
            )
            if len(_active_tools) > _prev_tool_count:
                messages[0] = {
                    "role": "system",
                    "content": self._get_system_prompt(agent_type, _active_tools, task.objective),
                }
                logger.debug(
                    "tool_hotswap: +%d tools after %s (total=%d)",
                    len(_active_tools) - _prev_tool_count, result.tool_name, len(_active_tools),
                )

            # Terminal tool gate: discover_objectives (and any future proposal tools) must
            # not be followed by action — the user must approve first. Inject a synthesis
            # nudge and return immediately so the agent produces a human-readable proposal
            # instead of continuing the tool loop.
            if result.tool_name in _TERMINAL_TOOLS:
                _cancel_watchdog()
                messages.append({
                    "role": "user",
                    "content": (
                        "Present the proposed objectives above as a numbered list. "
                        "For each include: rank, source, priority, and reasoning. "
                        "End with: 'Please reply with a number to select, or describe a different goal.' "
                        "Do NOT call any tools. Do NOT take any action."
                    ),
                })
                synthesis, syn_tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += syn_tok
                logger.info("terminal_tool_gate: %s → synthesis returned", result.tool_name)
                return synthesis.strip() if synthesis.strip() else formatted_result, total_tokens

            # Observation stall nudge: too many harness query calls without any action.
            # Analysis-only tasks should finalize into a report at this point; asking
            # them to "act" can send the model back into planning/tool loops.
            if (
                _is_analysis_only_task
                and _observations_without_action == _MAX_OBSERVATIONS_WITHOUT_ACTION
                and not _observation_nudge_sent
            ):
                _observation_nudge_sent = True
                _cancel_watchdog()
                messages.append({
                    "role": "user",
                    "content": (
                        "FINALIZE NOW. Do not call another tool. Do not continue planning. "
                        "Use the tool results already in context to answer the original task. "
                        "Start with 'COMPLETED:' and include concrete findings, ranked items "
                        "or decisions when requested, security/validation notes, and next safe "
                        "repo-local slice recommendations."
                    ),
                })
                synthesis, syn_tok = await self._call_llama(
                    messages,
                    role=role,
                    max_tokens=AGENT_TASK_MAX_TOKENS,
                    task_type=task.task_type,
                    task_id=task.id,
                    call_number=tool_call_count + 1,
                )
                total_tokens += syn_tok
                return synthesis.strip(), total_tokens

            if _observations_without_action == _MAX_OBSERVATIONS_WITHOUT_ACTION and not _observation_nudge_sent:
                _observation_nudge_sent = True
                messages.append({
                    "role": "user",
                    "content": (
                        f"OBSERVATION STALL: You have called harness query tools "
                        f"({_observations_without_action} times: get_hint, query_aidb, etc.) "
                        "without taking any action. You have enough context. Now act: "
                        "call store_memory with your findings, OR call run_harness_cli, "
                        "OR write/edit a file. Do NOT call get_hint or query_aidb again "
                        "until after you have taken at least one action."
                    ),
                })
                logger.info(
                    "observation-stall nudge injected after %d queries without action at call %d",
                    _observations_without_action, tool_call_count,
                )

            # Soft nudge: inject a user message when reads-without-edit reaches the soft limit.
            # Appears before the next LLM call so the model can course-correct without aborting.
            if _reads_without_edit == _MAX_READS_WITHOUT_EDIT and not _exploration_nudge_sent:
                _exploration_nudge_sent = True
                if _is_analysis_only_task:
                    nudge_content = (
                        f"ANALYSIS TASK: You have read {_reads_without_edit} files. "
                        f"Continue gathering context as needed, but checkpoint before "
                        f"{_READS_HARD_LIMIT} reads with store_memory or write_file. "
                        "Do not keep rereading the same files."
                    )
                else:
                    # Single-edit-first nudge (converged on independently by codex, 578bc847,
                    # + this session). Measured basis: the local model read-loops on
                    # multi-site edit tasks but succeeds at ONE edit (EXP3), so reframing to
                    # "make exactly ONE edit now, others later" targets the stuck read->edit
                    # transition. EFFECTIVENESS INCONCLUSIVE: the one validation run
                    # (reference-local-agent-capability-envelope EXP5) read-looped to call 17
                    # with 0 edits but was cut off by a first-token wedge, not a clean finish
                    # — needs a clean non-wedged run to confirm. Low-risk (only fires when the
                    # agent is already stuck). The proven multi-edit path remains the external
                    # decomposer (scripts/ai/aq-sequential-edit).
                    nudge_content = (
                        f"STOP READING — you have read {_reads_without_edit} times without "
                        "editing. Do NOT read again. Make exactly ONE edit now: pick the "
                        "single most concrete change from the BEHAVIORAL CONTRACT and emit "
                        "ONE edit_file call for it (exact old_string anchor + new_string). "
                        "Ignore every other change this turn — you will make them one at a "
                        "time in the following turns. One edit_file call, now."
                    )
                messages.append({"role": "user", "content": nudge_content})
                logger.info(
                    "exploration-nudge injected after %d reads without edit at call %d",
                    _reads_without_edit, tool_call_count,
                )

            # Validation stall nudge: code passed validation N times but model won't commit.
            if _validation_passes_without_commit >= _VALIDATION_STALL_NUDGE:
                messages.append({
                    "role": "user",
                    "content": (
                        f"COMMIT STALL: validate_before_commit or run_command has passed "
                        f"{_validation_passes_without_commit} times without a git_commit. "
                        "The code is ready. If edit_file for the [DONE] marker is failing, "
                        "call git_add now with only the changed code files, then git_commit "
                        "immediately. Do NOT validate again."
                    ),
                })
                logger.info(
                    "validation-stall nudge injected after %d passes without commit at call %d",
                    _validation_passes_without_commit, tool_call_count,
                )
                _validation_passes_without_commit = 0

    def _tool_call_grammar(self, *, force_repair: bool = False) -> Optional[str]:
        """P2: GBNF constraining output to the tool-call envelope over the ENABLED tools. Returns None
        unless AQ_LOCAL_GBNF is set (default OFF) or a repair-only retry explicitly requests it.
        Cached on the instance keyed by the enabled-tool set (the lease can hot-swap mid-run)."""
        if tool_grammar is None:
            return None
        if force_repair:
            if not _LOCAL_GBNF_REPAIR_ENABLED:
                return None
        elif not _LOCAL_GBNF_ALWAYS_ENABLED:
            return None
        try:
            names = sorted(t.name for t in self.tool_registry.tools.values() if getattr(t, "enabled", True))
            cache_key = tuple(names)
            cached = getattr(self, "_gbnf_cache", None)
            if cached and cached[0] == cache_key:
                return cached[1]
            grammar, _hit = tool_grammar.tool_call_grammar(names)
            self._gbnf_cache = (cache_key, grammar)
            return grammar
        except Exception:  # noqa: BLE001 — grammar is an optimization; never break the call on it
            return None

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "sed -n '880,1045p' ai-stack/local-agents/agent_executor.py
sed -n '1090,1140p' ai-stack/local-agents/agent_executor.py
sed -n '1740,1885p' ai-stack/local-agents/agent_executor.py
sed -n '1935,2020p' ai-stack/local-agents/agent_executor.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 56ms:
        # Use local for latency-critical tasks
        if task.latency_critical:
            return True, "Latency critical, local preferred"

        # Use remote for quality-critical tasks
        if task.quality_critical:
            if not remote_routing_available and self.allow_degraded_local_execution:
                return True, "Quality critical task degraded to local because remote routing is unavailable"
            return False, "Quality critical, remote preferred"

        # Check local agent performance
        agent_perf = self.performance[AgentType.AGENT]
        if agent_perf.total_tasks > 10:
            success_rate = agent_perf.get_success_rate()

            # Fallback to remote if local success rate too low
            if success_rate < 0.7:
                if not remote_routing_available and self.allow_degraded_local_execution:
                    return True, f"Local success rate low ({success_rate:.1%}) but remote routing unavailable"
                return False, f"Local success rate low ({success_rate:.1%})"

        # Default to local
        return True, "Default to local (cost-efficient)"

    async def execute_task(
        self,
        task: Task,
        agent_type: AgentType = AgentType.AGENT,
        max_tool_calls: int = 0,
    ) -> Task:
        """
        Execute a task using local agent with tool use.

        Args:
            task: Task to execute
            agent_type: Type of agent to use
            max_tool_calls: Deprecated compatibility parameter. Tool loops are
                governed by stagnation/progress guards, context pruning, and the
                stall watchdog, not by a fixed tool-call ceiling.

        Returns:
            Updated task with result or error
        """
        start_time = time.time()
        task.status = TaskStatus.RUNNING
        task.assigned_agent = f"local-{agent_type.value}"

        # Auto-assign role from capability→default mapping if not explicitly set.
        # EMBEDDED agents never get a role (no text generation to guide).
        if task.role is None:
            task.role = AGENT_TYPE_DEFAULT_ROLE.get(agent_type)

        # Phase 58A.5: validate role eligibility — clamp ineligible assignments to default.
        eligible_roles = AGENT_TYPE_ELIGIBLE_ROLES.get(agent_type)
        if task.role is not None and eligible_roles is not None and task.role not in eligible_roles:
            logger.warning(
                "Task %s: agent_type=%s is not eligible for role=%s (eligible: %s); clamping to default",
                task.id, agent_type.value, task.role, eligible_roles,
            )
            task.role = AGENT_TYPE_DEFAULT_ROLE.get(agent_type)

        # Phase 104: self-review guard — role-matrix.md §8 prohibits reviewing own work.
        # reviewer_id holds the assigned_agent of the original implementation task.
        # This is advisory (warning, not block) — blocking is the orchestrator's responsibility.
        if task.role == "reviewer" and task.reviewer_id is not None:
            if task.reviewer_id == task.assigned_agent:
                logger.warning(
                    "Task %s: self-review detected — reviewer_id=%r matches assigned_agent=%r. "
                    "Role matrix §8: a reviewer may not review their own work. "
                    "Proceeding — orchestrator should reassign to a different agent.",
                    task.id, task.reviewer_id, task.assigned_agent,
                )

        # Route task
        use_local, route_reason = self.route_task(task)

        if not use_local:
            if self.enable_fallback:
                if not await self._remote_fallback_available():
                    if self.allow_degraded_local_execution:
                        use_local = True
                        task.degraded_reason = (
                            f"{route_reason}; remote fallback unavailable, executing locally"
                        )
                        logger.warning("Task %s degraded to local execution: %s", task.id, task.degraded_reason)
                    else:
                        task.status = TaskStatus.FAILED
                        task.error = f"{route_reason}; remote fallback unavailable"
                        task.execution_time_ms = (time.time() - start_time) * 1000
                        await self._emit_terminal_agent_event(
                            task,
                            "agent_failed",
                            {
                                "error": task.error,
                                "run_attempt": len(task.tool_calls_made),
                            },
                        )
                        self.performance[agent_type].update(task)
                        return task
                else:
                    logger.info(f"Task {task.id} routed to remote: {route_reason}")
                    return await self._fallback_to_remote(task)
            elif self.allow_degraded_local_execution:
                use_local = True
                task.degraded_reason = f"{route_reason}; remote fallback disabled, executing locally"
            else:
                task.status = TaskStatus.FAILED
                task.error = f"{route_reason}; remote fallback disabled"
                task.execution_time_ms = (time.time() - start_time) * 1000
                await self._emit_terminal_agent_event(
                    task,
                    "agent_failed",
                    {
                        "error": task.error,
                        "run_attempt": len(task.tool_calls_made),
                    },
                )
                self.performance[agent_type].update(task)
                return task

        if task.degraded_reason is None and "degrading to local" in route_reason.lower():
            task.degraded_reason = route_reason

        logger.info(f"Task {task.id} executing locally: {route_reason}")

        # Execute with tool use loop
        _task_tokens_used = 0
        try:
            result, _task_tokens_used = await self._execute_with_tools(
                task,
                agent_type,
                max_tool_calls,
                role=task.role,
            )

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.execution_time_ms = (time.time() - start_time) * 1000

            # Write completed task fact to MemoryBroker
            if self.fallback_endpoint:
                try:
                    async with httpx.AsyncClient() as _mb_client:
                        await _mb_client.post(
                            f"{self.fallback_endpoint.rstrip('/')}/api/memory/facts",
                            json={
                                "fact": f"Task {task.id} completed: {task.objective[:200]}",
                                "source": "agent-executor",
                                "session_id": task.id,
                                "confidence": 0.8,
                                "role": task.role,
                            },
                            timeout=5.0,
                        )
                except Exception:
                    pass

            # Emit agent_step_complete event for training ingest pipeline
            if task.result and _HYBRID_EVENTS.parent.exists():
                try:
                    _event = json.dumps({
                        "event_type": "agent_step_complete",
                        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                        "query": task.objective,
                        "response": task.result if isinstance(task.result, str) else json.dumps(task.result),
                        "latency_ms": task.execution_time_ms,
            if self.enable_fallback and await self._remote_fallback_available():
                logger.info(f"Falling back to remote for task {task.id}")
                return await self._fallback_to_remote(task)
            if self.enable_fallback and task.error:
                task.error = f"{task.error}; remote fallback unavailable"
            await self._emit_terminal_agent_event(
                task,
                "agent_failed",
                {
                    "error": task.error or str(e),
                    "run_attempt": len(task.tool_calls_made),
                },
            )

        # Update performance tracking
        self.performance[agent_type].update(task)

        return task

    async def _execute_with_tools(
        self,
        task: Task,
        agent_type: AgentType,
        max_tool_calls: int,
        role: Optional[str] = None,
    ) -> Tuple[Any, int]:
        """
        Execute task with tool use loop.

        Tool use loop:
        1. Send prompt + tools to model
        2. Parse response for tool calls
        3. Execute tool calls
        4. Append results to context
        5. Repeat until no more tool calls or max reached
        """
        # Get tools for model.
        # A.6 — _all_tools is the full registry snapshot (hot-swap source, never depleted).
        # _active_tools starts as the full set and may expand mid-loop via _refresh_active_tools.
        # The system prompt is rebuilt whenever _active_tools changes so the model always
        # sees the current tool surface without a full context reload.
        _all_tools = self.tool_registry.get_tools_for_model()
        # Slice 0.2 — structural no-commit: exclude git_add/git_commit from the
        # model-visible schema by default. Filtering here (the hot-swap source) also
        # keeps them out of _refresh_active_tools' candidate pool, so no later
        # keyword-triggered hot-swap can reintroduce them either.
        if not _LOCAL_ALLOW_COMMIT:
            _all_tools = [t for t in _all_tools if t.get("name") not in _AEXEC_COMMIT_TOOLS]
        _active_tools = list(_all_tools)

        # Build initial prompt

            # Slice 0.2 — structural no-commit: block execution at the point of the call
            # itself, not just the advertised schema. The SI-slice system prompt still
            # names git_add/git_commit by name (STEP 6), so a schema-only filter would
            # not stop a call the model emits anyway — this is what makes "local CANNOT
            # commit" structural rather than prompt-hoped. AQ_LOCAL_ALLOW_COMMIT=1 is the
            # explicit escape hatch; the handlers in builtin_tools/git_tools.py are
            # untouched, only this call site refuses to reach them.
            if tool_call.tool_name in _AEXEC_COMMIT_TOOLS and not _LOCAL_ALLOW_COMMIT:
                tool_call.status = "blocked"
                tool_call.error = (
                    f"{tool_call.tool_name} is disabled for local agents (structural "
                    "no-commit gate). Local NEVER commits — finish validation and STOP; "
                    "the orchestrator commits after remote review. Override: "
                    "AQ_LOCAL_ALLOW_COMMIT=1 (not recommended)."
                )
                tool_call.result = {"success": False, "error": tool_call.error, "blocked": True}
                result = tool_call
            else:
                result = await self.tool_registry.execute_tool_call(tool_call)
            task.tool_calls_made.append(result)
            tool_call_count += 1

            # Slice 0.2 — read_file gate (the load-bearing fix): an oversized whole-file
            # read on top of front-loaded context blows the prompt-char budget (DESIGN.md
            # AFTER-run-1: 25920 > 24000 LLAMA_MAX_PROMPT_CHARS). Skip when an explicit
            # line range was requested — that's already a bounded, caller-chosen span.
            if (
                _READ_FILE_GATE_ENABLED
                and result.tool_name == "read_file"
                and result.status == "completed"
                and isinstance(result.result, dict)
                and result.result.get("success")
                and isinstance(result.result.get("content"), str)
                and tool_call.arguments.get("start_line") is None
                and tool_call.arguments.get("end_line") is None
            ):
                _rf_path = str(
                    tool_call.arguments.get("file_path")
                    or (result.result.get("metadata") or {}).get("path")
                    or ""
                )
                _gated_content, _rf_gated = _gate_large_file_content(
                    result.result["content"], _rf_path, task.objective, task.id,
                )
                if _rf_gated:
                    result.result["content"] = _gated_content
                    _rf_meta = result.result.setdefault("metadata", {})
                    _rf_meta["read_file_gate"] = True

            # P1.4: a valid tool call that executed cleanly is a POSITIVE sample — capture it directly
            # here (the reliable source) rather than mining hybrid-events (only ~0.03% of which are
            # inference completions — the root cause of the ingest's samples_added:0). Best-effort;
            # ingest dedupes by content hash. Guarded so it never affects the turn.
            if training_capture is not None and not getattr(result, "error", None):
                _last_user = next((m.get("content", "") for m in reversed(messages)
                                   if m.get("role") == "user"), "")
                if _last_user and response:
                    training_capture.capture_success(
                        prompt=_last_user,
                        good_output=response,
                        source="agent_executor.tool_success",
                        model_provenance={"lane": "local", "tool": getattr(result, "tool_name", "")},
                    )

            # Phase E — agent_tool_result: emitted after dispatch returns.
            await self._emit_agent_event(
                task.id, "agent_tool_result",
                {
                    "tool_name": result.tool_name,
                    "result_preview": str(result.result)[:200] if result.result is not None else "",
                },
                _watchdog_last_activity,
            )

            # Format result for model, then sanitize for prompt-injection patterns.
            # context_sanitizer scrubs IGNORE/SYSTEM/OVERRIDE patterns from tool output
            # before it reaches the model context (MIC-G P2 — External Content Injection).
            formatted_result = self.tool_registry.format_tool_result(result)
            if _CONTEXT_SANITIZER_AVAILABLE and _sanitize_tool_result is not None:
                try:
                    formatted_result, _violations = _sanitize_tool_result(
                        formatted_result, source=result.tool_name,
                    )
                    if _violations:
                        logger.warning(
                            "context_sanitizer: %d violation(s) in %s result: %s",
                            len(_violations), result.tool_name, _violations[:3],
                        )
                except Exception as _san_err:
                    logger.debug("context_sanitizer error (non-fatal): %s", _san_err)
            try:
                compacted_result, _context_risk = compact_context_if_needed(
                    formatted_result,
                    source=result.tool_name,
                    label=f"{task.id}-{result.tool_name}",
                    kind="agent-tool-result",
                    min_chars=int(os.getenv("SWB_CONTEXT_OUTPUT_GC_MIN_CHARS", "2400")),
                    summary_chars=int(os.getenv("SWB_CONTEXT_OUTPUT_GC_SUMMARY_CHARS", "900")),
                )
                if _context_risk.get("context_risk"):
                    await self._emit_agent_event(
                        task.id, "context_compaction",
                        {
                            "tool_name": result.tool_name,
                            "artifact_path": _context_risk.get("artifact_path"),
                            "raw_chars": _context_risk.get("raw_chars"),
                            "risk_reasons": _context_risk.get("risk_reasons", []),
                            "context_route": _context_risk.get("context_route"),
                        },
                        _watchdog_last_activity,
                    )
                    formatted_result = compacted_result
            except Exception as _compact_err:
                logger.debug("context compaction error (non-fatal): %s", _compact_err)

            # Stagnation detection: same (tool_name, result_prefix) repeated beyond
            # threshold → model is looping without state change. Abort early via a
            # progress guard. There is intentionally no hard max-tool-call ceiling:
            # context pruning + working-memory checkpoints keep prior findings
            # reachable across long implementation loops.
            # Thresholds are tool-specific:
            #   read_file  → 3: pure observation; identical result 3× = definitely stuck.
            #   run_command → 5: polling loops (e.g. tail, systemctl) legitimately repeat.
            threshold = (
                _STAGNATION_THRESHOLD_READ
                if result.tool_name == "read_file"
                else _STAGNATION_THRESHOLD_OTHER
            )
            _recent_tools.append((result.tool_name, formatted_result[:200]))
            if len(_recent_tools) > threshold:
                _recent_tools.pop(0)
            if (
                len(_recent_tools) == threshold
                and len({t for t, _ in _recent_tools}) == 1   # same tool name
                and len({r for _, r in _recent_tools}) == 1   # same result prefix
            ):
                stagnation_msg = (
                    f"Stagnation detected: '{result.tool_name}' called {threshold} consecutive "
                    f"times with identical result — loop aborted to prevent runaway. "
                    f"Last result prefix: {formatted_result[:300]}"
                )
                logger.warning(
                    "stagnation: tool=%r threshold=%d — aborting loop at call %d",
                    result.tool_name, threshold, tool_call_count,
                )
                        result.tool_name, _tool_failure_counts[result.tool_name], tool_call_count,
                    )
                    _cancel_watchdog()
                    return stagnation_msg, total_tokens

            # Exploration stagnation: count reads vs edits/writes.
            # Reset counter on any write action; abort if model reads too many files
            # without acting (prevents over-exploration in self-improvement tasks).
            if result.tool_name == "read_file":
                _reads_without_edit += 1
                read_path = str(result.arguments.get("file_path") or result.arguments.get("path") or "")
                if read_path:
                    _read_path_counts[read_path] = _read_path_counts.get(read_path, 0) + 1
                    if _read_path_counts[read_path] >= _REPEATED_READ_PATH_LIMIT:
                        # First breach: inject a one-shot edit-forcing intervention instead
                        # of aborting. The relevant code is already front-loaded verbatim
                        # under "## Relevant prior knowledge" — the plain abort discarded
                        # tasks local could complete once nudged off the read->edit stall.
                        # Delivered as the read_file tool result (role:"tool") so the model
                        # actually sees it as the outcome of ITS OWN last tool call next turn.
                        if _REREAD_INTERVENTION_ENABLED and not _reread_intervention_sent:
                            try:
                                _reread_intervention_sent = True
                                _iv_brace = response.rfind('{"function"')
                                if _iv_brace == -1:
                                    _iv_brace = response.rfind("{")
                                _iv_clean_call = (
                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
                                )
                                intervention_msg = (
                                    f"You have read {read_path!r} "
                                    f"{_read_path_counts[read_path]} times and it keeps returning "
                                    "the same content — reading it again will not help. STOP "
                                    "reading. The relevant code for this task is ALREADY in your "
                                    "context above under '## Relevant prior knowledge' as exact "
                                    "fenced code blocks (byte-identical to the file). Call "
                                    "edit_file NOW: use the exact text from one of those code "
                                    "blocks as old_string (it will match), and provide your "
                                    "changed version as new_string. Do not call read_file on "
                                    "this file again."
                                )
                                messages.append({"role": "assistant", "content": _iv_clean_call})
                                messages.append({
                                    "role": "tool",
                                    "name": result.tool_name,
                                    "content": intervention_msg,
                                })
                                logger.warning(
                                    "repeated-read intervention: path=%r reads=%d call=%d — "
                                    "injecting one-shot edit-forcing nudge instead of aborting",
                                    read_path, _read_path_counts[read_path], tool_call_count,
                                )
                                await self._emit_agent_event(
                                    task.id, "reread_intervention",
                                    {
                                        "file_path": read_path,
                                        "reads": _read_path_counts[read_path],
                                        "tool_call_count": tool_call_count,
                                    },
                                    _watchdog_last_activity,
                                )
                                continue
                            except Exception as _interv_err:
                                logger.warning(
                                    "reread-intervention construction failed (%s) — "
                                    "falling back to plain abort", _interv_err,
                                )
                                # Fall through to the plain abort below (fail-safe: never
                                # let a broken intervention crash or hang the loop).
                        stagnation_msg = (
                            f"Repeated-read stagnation: {read_path!r} was read "
                            f"{_read_path_counts[read_path]} times without progress. "
                            f"Aborting at tool call {tool_call_count}."
                        )
                        logger.warning(
                            "repeated-read stagnation: path=%r reads=%d call=%d",
                            read_path, _read_path_counts[read_path], tool_call_count,
                        )
                        _cancel_watchdog()
                        return stagnation_msg, total_tokens
            elif result.tool_name in ("edit_file", "write_file", "write_region"):
                _reads_without_edit = 0
                _read_path_counts.clear()
                if not _is_tool_failure:
                    _edits_made += 1
                elif result.tool_name == "edit_file":

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "sed -n '1,130p' scripts/ai/lib/grammar_cache.py
sed -n '1,260p' ai-stack/local-agents/tool_grammar.py
rg -n \"grammar_cache|tool_call_grammar|properties|required|additionalProperties|nested|array|object\" scripts/testing/test-tool-call-grammar.py ai-stack/local-agents/tool_grammar.py scripts/ai/lib/grammar_cache.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 58ms:
#!/usr/bin/env python3
"""Pure in-memory GBNF grammar cache keyed by schema and zero-trust policy."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, Field, PositiveInt


Builder = Callable[[Any, Any], str]


class GrammarCacheConfig(BaseModel):
    """Runtime-independent cache sizing."""

    max_size: PositiveInt = Field(default=128)


def cache_key(schema_json: Any, zero_trust_state: Any) -> str:
    """Return the canonical versioned key for a schema and zero-trust state."""

    key_material = (
        b"gbnf:v1\0"
        + _canonical_bytes(schema_json)
        + b"\0zt:"
        + _canonical_zt_digest(zero_trust_state).encode("utf-8")
    )
    return hashlib.sha256(key_material).hexdigest()


class GrammarCache:
    """Bounded LRU cache for deterministic schema-to-grammar builders."""

    def __init__(
        self,
        builder: Builder | None = None,
        max_size: int = 128,
    ) -> None:
        self.config = GrammarCacheConfig(max_size=max_size)
        self._builder = builder or default_json_schema_to_gbnf
        self._entries: OrderedDict[str, str] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_or_build(self, schema_json: Any, zero_trust_state: Any) -> tuple[str, bool]:
        """Return a cached grammar or build and store a new one."""

        key = cache_key(schema_json, zero_trust_state)
        if key in self._entries:
            self._hits += 1
            self._entries.move_to_end(key)
            return self._entries[key], True

        self._misses += 1
        grammar = self._builder(schema_json, zero_trust_state)
        self._entries[key] = grammar
        self._entries.move_to_end(key)
        while len(self._entries) > self.config.max_size:
            self._entries.popitem(last=False)
            self._evictions += 1
        return grammar, False

    def stats(self) -> dict[str, int]:
        """Return cache counters without exposing mutable state."""

        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._entries),
            "evictions": self._evictions,
        }


def default_json_schema_to_gbnf(schema_json: Any, zero_trust_state: Any) -> str:
    """Build a small deterministic GBNF grammar for common JSON schema types."""

    schema = _parse_json_value(schema_json)
    if not isinstance(schema, Mapping):
        raise ValueError("schema_json must describe a JSON object schema")

    root = _rule_for_schema(schema)
    return "\n".join(
        [
            f"root ::= {root}",
            'string ::= "\\"" ([^"\\\\] | "\\\\" (["\\\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\\""',
            'number ::= "-"? ([0-9] | [1-9][0-9]*) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?',
            'boolean ::= "true" | "false"',
            'null ::= "null"',
            "ws ::= [ \\t\\n\\r]*",
            # Generic JSON object/array/value rules, used by _object_rule for schemas
            # that declare `"type": "object"` with NO `properties` (free-form objects,
            # e.g. a tool-call's `arguments` payload). These allow zero-or-more members
            # of arbitrary JSON value type instead of forcing an empty "{}" body.
            'member ::= string ws ":" ws value',
            "value ::= string | number | boolean | null | object | array",
            'object ::= "{" ws (member (ws "," ws member)*)? ws "}"',
            'array ::= "[" ws (value (ws "," ws value)*)? ws "]"',
        ]
    )


def _canonical_zt_digest(zero_trust_state: Any) -> str:
    if isinstance(zero_trust_state, str):
        digest = zero_trust_state.strip()
        if not digest:
            raise ValueError("zero_trust_state digest must not be empty")
        return digest
    return hashlib.sha256(_canonical_bytes(zero_trust_state)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    parsed = _parse_json_value(value)
    return json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_json_value(value: Any) -> Any:
    if isinstance(value, bytes | bytearray):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value


def _rule_for_schema(schema: Mapping[str, Any]) -> str:
#!/usr/bin/env python3
"""P2 — tool-call GBNF construction for the local agent lane.

The local 35B intermittently emits a tool call as PROSE ("I will call write_file...") instead of the
required JSON envelope, and ~15% of its tool-JSON is malformed. GBNF-constrained decoding forces the
output to a valid tool-call shape at generation time — the FAST producer-fix (no retrain) from the
closed-local-improvement-loop PRD (Phase 2).

This module is PURE: it builds the tool-call envelope JSON schema and hands it to F2.2's grammar_cache
(scripts/ai/lib/grammar_cache.py) to produce + cache the GBNF. Wiring the resulting grammar into the
live request (agent_executor -> build_llama_payload(grammar=...)) is flag-gated (AQ_LOCAL_GBNF) and
must be validated by a bench before default-on, so a too-strict grammar can never silently break
tool-calling.

The local tool-call envelope observed in the live stream is: {"function": "<name>", "arguments": {...}}.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# grammar_cache lives in scripts/ai/lib (F2.2).
_LIB = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
import grammar_cache  # noqa: E402


def tool_call_schema(tool_names: list[str]) -> dict[str, Any]:
    """JSON schema for the local tool-call envelope, constraining `function` to the AVAILABLE tools.

    {"function": <enum of tool_names>, "arguments": <object>}. Constraining the function name to the
    leased tool set (not free text) is what kills 'call a tool that doesn't exist' + prose-as-tool-call.
    """
    fn: dict[str, Any] = {"type": "string"}
    if tool_names:
        fn = {"type": "string", "enum": sorted(set(tool_names))}
    return {
        "type": "object",
        "properties": {
            "function": fn,
            "arguments": {"type": "object"},
        },
        "required": ["function", "arguments"],
        "additionalProperties": False,
    }


def tool_call_grammar(
    tool_names: list[str],
    zero_trust_state: Any = None,
    cache: "grammar_cache.GrammarCache | None" = None,
) -> tuple[str, bool]:
    """Build (or cache-hit) the GBNF for the tool-call envelope over `tool_names`.

    Returns (gbnf, was_cache_hit). `zero_trust_state` shares F2.2/F3's namespaced key so the grammar
    cache and the capability policy stay in one namespace. Pass a shared GrammarCache to persist across
    turns; a fresh one is created if None (still deterministic)."""
    c = cache if cache is not None else grammar_cache.GrammarCache()
    schema = tool_call_schema(tool_names)
    return c.get_or_build(schema, zero_trust_state)
scripts/ai/lib/grammar_cache.py:85:        raise ValueError("schema_json must describe a JSON object schema")
scripts/ai/lib/grammar_cache.py:96:            # Generic JSON object/array/value rules, used by _object_rule for schemas
scripts/ai/lib/grammar_cache.py:97:            # that declare `"type": "object"` with NO `properties` (free-form objects,
scripts/ai/lib/grammar_cache.py:101:            "value ::= string | number | boolean | null | object | array",
scripts/ai/lib/grammar_cache.py:102:            'object ::= "{" ws (member (ws "," ws member)*)? ws "}"',
scripts/ai/lib/grammar_cache.py:103:            'array ::= "[" ws (value (ws "," ws value)*)? ws "]"',
scripts/ai/lib/grammar_cache.py:123:    if isinstance(value, bytes | bytearray):
scripts/ai/lib/grammar_cache.py:136:        # unparenthesized alternation embedded inline (e.g. inside _object_rule's
scripts/ai/lib/grammar_cache.py:142:    if schema_type == "object":
scripts/ai/lib/grammar_cache.py:143:        return _object_rule(schema)
scripts/ai/lib/grammar_cache.py:144:    if schema_type == "array":
scripts/ai/lib/grammar_cache.py:158:def _object_rule(schema: Mapping[str, Any]) -> str:
scripts/ai/lib/grammar_cache.py:159:    properties = schema.get("properties", {})
scripts/ai/lib/grammar_cache.py:160:    if not isinstance(properties, Mapping) or not properties:
scripts/ai/lib/grammar_cache.py:161:        # Free-form object (schema is `{"type": "object"}` with no declared
scripts/ai/lib/grammar_cache.py:162:        # `properties`, e.g. a tool-call's `arguments` payload): allow zero-or-more
scripts/ai/lib/grammar_cache.py:165:        return "object"
scripts/ai/lib/grammar_cache.py:168:    for name in sorted(properties):
scripts/ai/lib/grammar_cache.py:169:        prop_schema = _schema_mapping(properties[name])
ai-stack/local-agents/tool_grammar.py:5:required JSON envelope, and ~15% of its tool-JSON is malformed. GBNF-constrained decoding forces the
ai-stack/local-agents/tool_grammar.py:9:This module is PURE: it builds the tool-call envelope JSON schema and hands it to F2.2's grammar_cache
ai-stack/local-agents/tool_grammar.py:10:(scripts/ai/lib/grammar_cache.py) to produce + cache the GBNF. Wiring the resulting grammar into the
ai-stack/local-agents/tool_grammar.py:23:# grammar_cache lives in scripts/ai/lib (F2.2).
ai-stack/local-agents/tool_grammar.py:27:import grammar_cache  # noqa: E402
ai-stack/local-agents/tool_grammar.py:33:    {"function": <enum of tool_names>, "arguments": <object>}. Constraining the function name to the
ai-stack/local-agents/tool_grammar.py:40:        "type": "object",
ai-stack/local-agents/tool_grammar.py:41:        "properties": {
ai-stack/local-agents/tool_grammar.py:43:            "arguments": {"type": "object"},
ai-stack/local-agents/tool_grammar.py:45:        "required": ["function", "arguments"],
ai-stack/local-agents/tool_grammar.py:46:        "additionalProperties": False,
ai-stack/local-agents/tool_grammar.py:50:def tool_call_grammar(
ai-stack/local-agents/tool_grammar.py:53:    cache: "grammar_cache.GrammarCache | None" = None,
ai-stack/local-agents/tool_grammar.py:60:    c = cache if cache is not None else grammar_cache.GrammarCache()
scripts/testing/test-tool-call-grammar.py:2:"""Regression test for the F2.2 GBNF `_object_rule` fix (grammar_cache.py).
scripts/testing/test-tool-call-grammar.py:4:Root cause verified live (2026-08-18): `tool_call_grammar(['read_file', 'edit_file',
scripts/testing/test-tool-call-grammar.py:6:because `_object_rule`:
scripts/testing/test-tool-call-grammar.py:9:  2. returned the empty-only rule `'"{" ws "}"'` for a free-form object (a schema
scripts/testing/test-tool-call-grammar.py:10:     with `"type": "object"` and no `properties`, e.g. the tool-call `arguments`
scripts/testing/test-tool-call-grammar.py:14:non-empty free-form `arguments` object, and (c) actually ACCEPTS a hand-written
scripts/testing/test-tool-call-grammar.py:61:    items: tuple[object, ...]
scripts/testing/test-tool-call-grammar.py:66:    options: tuple[object, ...]
scripts/testing/test-tool-call-grammar.py:71:    expr: object
scripts/testing/test-tool-call-grammar.py:72:    kind: object  # '*' | '+' | '?' | ('exact', n)
scripts/testing/test-tool-call-grammar.py:84:    def parse_rules(self) -> dict[str, object]:
scripts/testing/test-tool-call-grammar.py:85:        rules: dict[str, object] = {}
scripts/testing/test-tool-call-grammar.py:131:    def _parse_alternation(self) -> object:
scripts/testing/test-tool-call-grammar.py:141:    def _parse_sequence(self) -> object:
scripts/testing/test-tool-call-grammar.py:142:        items: list[object] = []
scripts/testing/test-tool-call-grammar.py:153:    def _parse_term(self) -> object:
scripts/testing/test-tool-call-grammar.py:171:    def _parse_atom(self) -> object:
scripts/testing/test-tool-call-grammar.py:239:def _positions_after(expr: object, rules: dict[str, object], text: str, pos: int) -> set[int]:
scripts/testing/test-tool-call-grammar.py:312:    gbnf, _hit = tool_grammar.tool_call_grammar(["read_file", "edit_file", "write_file"])
scripts/testing/test-tool-call-grammar.py:318:    # produces a non-empty rule set including root + the new generic object/array rules.
scripts/testing/test-tool-call-grammar.py:320:    for expected in ("root", "string", "number", "boolean", "null", "ws", "member", "value", "object", "array"):
scripts/testing/test-tool-call-grammar.py:335:def test_arguments_uses_generic_nonempty_capable_object_not_empty_only():
scripts/testing/test-tool-call-grammar.py:338:    # grammar must route arguments through the free-form `object` rule instead.
scripts/testing/test-tool-call-grammar.py:339:    assert '"\\"arguments\\"" ws ":" ws object' in gbnf, gbnf
scripts/testing/test-tool-call-grammar.py:356:def test_grammar_accepts_multi_key_nested_arguments():
scripts/testing/test-tool-call-grammar.py:370:    assert gbnf_matches(gbnf, envelope), "free-form object must still permit {}"

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "sed -n '300,400p' scripts/testing/test-tool-call-grammar.py
sed -n '1,220p' scripts/testing/test-llm-cassette.py
sed -n '220,500p' scripts/testing/test-llm-cassette.py
sed -n '500,640p' scripts/testing/test-llm-cassette.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 61ms:

    rules = _GbnfParser(gbnf_text).parse_rules()
    ends = _positions_after(rules[root], rules, candidate, 0)
    return len(candidate) in ends


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def _grammar() -> str:
    gbnf, _hit = tool_grammar.tool_call_grammar(["read_file", "edit_file", "write_file"])
    return gbnf


def test_grammar_parses_as_valid_gbnf():
    # "compiles": the parser above accepts the emitted grammar without error and
    # produces a non-empty rule set including root + the new generic object/array rules.
    rules = _GbnfParser(_grammar()).parse_rules()
    for expected in ("root", "string", "number", "boolean", "null", "ws", "member", "value", "object", "array"):
        assert expected in rules, f"missing rule {expected!r}"


def test_property_keys_are_quoted_in_grammar_source():
    gbnf = _grammar()
    # Bug #1: keys must be emitted as the GBNF literal for `"arguments"` / `"function"`
    # (quote characters included in the generated text), not the bare word.
    assert '"\\"arguments\\""' in gbnf, gbnf
    assert '"\\"function\\""' in gbnf, gbnf
    # and NOT the old quote-stripped form (a literal that matches the bare word).
    assert '"arguments" ws' not in gbnf
    assert '"function" ws' not in gbnf


def test_arguments_uses_generic_nonempty_capable_object_not_empty_only():
    gbnf = _grammar()
    # Bug #2: the old code forced arguments to `'"{" ws "}"'` (empty only). The fixed
    # grammar must route arguments through the free-form `object` rule instead.
    assert '"\\"arguments\\"" ws ":" ws object' in gbnf, gbnf
    assert '"{" ws "}"' not in gbnf, gbnf


def test_function_is_constrained_to_the_enum_of_tool_names():
    gbnf = _grammar()
    for name in ("read_file", "edit_file", "write_file"):
        assert json.dumps(name) in gbnf.replace("\\", "")


def test_grammar_accepts_a_real_valid_envelope_with_nonempty_arguments():
    gbnf = _grammar()
    envelope = '{"arguments":{"file_path":"a.py"},"function":"read_file"}'
    assert json.loads(envelope) == {"arguments": {"file_path": "a.py"}, "function": "read_file"}
    assert gbnf_matches(gbnf, envelope), "grammar must accept a valid multi-arg tool-call envelope"


def test_grammar_accepts_multi_key_nested_arguments():
    gbnf = _grammar()
    envelope = (
        '{"arguments":{"file_path":"a.py","old_string":"x","new_string":"y"},'
        '"function":"edit_file"}'
    )
    assert json.loads(envelope)  # sanity: real JSON
    assert gbnf_matches(gbnf, envelope)


def test_grammar_accepts_empty_arguments_too():
    gbnf = _grammar()
    envelope = '{"arguments":{},"function":"write_file"}'
    assert json.loads(envelope)
    assert gbnf_matches(gbnf, envelope), "free-form object must still permit {}"


def test_grammar_rejects_unquoted_keys_the_old_bug_shape():
    gbnf = _grammar()
    # The exact invalid shape reported live before the fix.
    old_bug_output = '{arguments:{},function:"read_file"}'
    with_ws = '{ arguments: {} , function: "read_file" }'
    assert not gbnf_matches(gbnf, old_bug_output)
    assert not gbnf_matches(gbnf, with_ws)


def test_grammar_rejects_unknown_function_name():
    gbnf = _grammar()
    envelope = '{"arguments":{},"function":"delete_everything"}'
    assert not gbnf_matches(gbnf, envelope)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
#!/usr/bin/env python3
"""
Tests for the LLM record/replay cassette harness.

Modules under test:
  ai-stack/local-agents/llm_cassette.py   — request_key, Cassette, mode/path/on_miss
  ai-stack/local-agents/agent_executor.py — the two _call_llama wiring points

Design doc (authoritative): .agents/plans/record-replay-harness/DESIGN.md

Covers:
  (a) request_key is stable + excludes volatile fields
  (b) record -> lookup round trip (same instance + a freshly-loaded instance)
  (c) multi-row-per-key consumed in call order
  (d) replay mode returns recorded content WITHOUT touching the network, in BOTH
      the streaming and legacy (non-streaming) _call_llama branches
  (e) on_miss error/passthrough/empty behaviors
  (f) mode=off is a strict no-op — live HTTP path taken, cassette file never written
  (g) golden end-to-end: record a stubbed run of _execute_with_tools (network
      stubbed with canned turns, not a live APU call), then REPLAY the identical
      task through the real _execute_with_tools fully offline and confirm identical
      loop behavior (same final answer, same tool-call outcomes, zero network I/O).

Bonus (DoD payoff demonstration, not just a unit check): a synthetic cassette row
carrying a run_command tool call whose "command" argument ends in the literal
`\\n},\\n` artifact this session hit live (the local model's streaming/GBNF tool-call
parser leaking the JSON envelope's closing punctuation into the argument value) is
recorded, then replayed fully offline through the real parse + execute path, proving
the already-committed strip fix in builtin_tools/shell_tools.py:147 resolves it
deterministically — no 30-40 min live APU run required.

Run: python3 scripts/testing/test-llm-cassette.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "local-agents"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))

import httpx  # noqa: E402
import llm_cassette  # noqa: E402
from agent_executor import AgentType, LocalAgentExecutor, Task  # noqa: E402
from shared.llm_config import build_llama_payload  # noqa: E402
from tool_registry import ToolRegistry  # noqa: E402
from builtin_tools.shell_tools import register_shell_tools  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# Shared test fixtures / fakes
# ---------------------------------------------------------------------------

_CASSETTE_ENV_VARS = ("AQ_LLM_CASSETTE_MODE", "AQ_LLM_CASSETTE", "AQ_LLM_CASSETTE_ON_MISS")


@contextlib.contextmanager
def cassette_env(mode: Optional[str] = None, path: Optional[str] = None, on_miss: Optional[str] = None):
    """Save/restore the cassette env vars around a test and reset llm_cassette's
    process-wide Cassette cache so a prior test's cursor/path never leaks in."""
    saved = {k: os.environ.get(k) for k in _CASSETTE_ENV_VARS}
    try:
        for var, val in (("AQ_LLM_CASSETTE_MODE", mode), ("AQ_LLM_CASSETTE", path), ("AQ_LLM_CASSETTE_ON_MISS", on_miss)):
            if val is not None:
                os.environ[var] = val
            else:
                os.environ.pop(var, None)
        llm_cassette.reset_cache()
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        llm_cassette.reset_cache()


@contextlib.contextmanager
def env_var(name: str, value: Optional[str]):
    saved = os.environ.get(name)
    try:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
        yield
    finally:
        if saved is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = saved


class _ExplodingAsyncClient:
    """Any attempt to construct httpx.AsyncClient explodes. Proves a replay hit (or
    mode=replay generally) never touches the network."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("network touched — httpx.AsyncClient must not be constructed on a replay hit")


class _FakeResponse:
    def __init__(self, status_code: int, json_data: Dict[str, Any]):
        self.status_code = status_code
        self._json = json_data
        self.text = json.dumps(json_data)

    def json(self) -> Dict[str, Any]:
        return self._json


def _make_single_response_client(response: _FakeResponse):
    """A fake httpx.AsyncClient whose .post() always returns the same canned
    response — used to prove the LIVE path executes (mode=off)."""

    class _Ctx:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, timeout=None, headers=None):
            return response

    return _Ctx


def _make_scripted_client(turns: List[str]):
    """A fake httpx.AsyncClient that returns each of `turns` in order, one per POST
    call — used to drive a multi-turn _execute_with_tools loop deterministically
    without a live APU."""
    turns_iter = iter(turns)

    class _Ctx:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, timeout=None, headers=None):
            try:
                content = next(turns_iter)
            except StopIteration:
                raise AssertionError(
                    "scripted client ran out of canned turns — the loop made more LLM "
                    "calls than the test expected"
                )
            return _FakeResponse(200, {
                "choices": [{"message": {"content": content}}],
                "usage": {"total_tokens": 10},
            })

    return _Ctx


# ---------------------------------------------------------------------------
# (a) request_key: stable + excludes volatile fields
# ---------------------------------------------------------------------------

def test_request_key_stable_and_excludes_volatile() -> None:
    base = {
        "messages": [
            {"role": "system", "content": "sys prompt"},
            {"role": "user", "content": "do the thing"},
        ],
        "max_tokens": 256,
        "temperature": 0.2,
        "chat_template_kwargs": {"enable_thinking": False},
        "repeat_penalty": 1.08,
        "repeat_last_n": 64,
        "frequency_penalty": 0.05,
        "cache_prompt": True,
    }
    k1 = llm_cassette.request_key(base)
    k1_again = llm_cassette.request_key(json.loads(json.dumps(base)))
    assert_true(k1 == k1_again, "request_key must be deterministic across repeated calls")

    volatile_changed = dict(base)
    volatile_changed["cache_prompt"] = False
    volatile_changed["repeat_penalty"] = 1.5
    volatile_changed["repeat_last_n"] = 32
    volatile_changed["chat_template_kwargs"] = {"enable_thinking": True}
    k2 = llm_cassette.request_key(volatile_changed)
    assert_true(
        k1 == k2,
        "request_key must exclude volatile fields (cache_prompt/repeat_penalty/"
        "repeat_last_n/chat_template_kwargs)",
    )

    semantic_changed = dict(base)
    semantic_changed["messages"] = [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "do a DIFFERENT thing"},
    ]
    k3 = llm_cassette.request_key(semantic_changed)
    assert_true(k1 != k3, "request_key must change when message content changes")


    grammar_changed = dict(base)
    grammar_changed["grammar"] = "root ::= object"
    k4 = llm_cassette.request_key(grammar_changed)
    assert_true(k1 != k4, "request_key must change when grammar changes")

    kt1 = llm_cassette.request_key(base, task_type="agent")
    kt2 = llm_cassette.request_key(base, task_type="research")
    assert_true(kt1 != kt2, "request_key must vary with task_type")
    assert_true(kt1 != k1, "request_key with an explicit task_type must differ from without")
    print("PASS (a): request_key stability + volatile-field exclusion")


# ---------------------------------------------------------------------------
# (b) record -> lookup round trip
# ---------------------------------------------------------------------------

def test_record_lookup_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "cassette.jsonl")
        cass = llm_cassette.Cassette(cpath)
        payload = {"messages": [{"role": "user", "content": "hello"}], "max_tokens": 10}
        key = llm_cassette.request_key(payload)
        cass.record(key, payload, "hello back", 7, {"note": "unit-test"})

        hit = cass.lookup(key)
        assert_true(hit == ("hello back", 7), f"same-instance lookup must round-trip, got {hit}")

        # A freshly-constructed instance must read the same row back from disk.
        cass2 = llm_cassette.Cassette(cpath)
        hit2 = cass2.lookup(key)
        assert_true(hit2 == ("hello back", 7), f"fresh-instance lookup must round-trip from disk, got {hit2}")
        assert_true(cass2.lookup(key) is None, "a 2nd lookup with only one recorded row must miss")
    print("PASS (b): record -> lookup round trip (same instance + fresh reload)")


# ---------------------------------------------------------------------------
# (c) multi-row-per-key consumed in call order
# ---------------------------------------------------------------------------

def test_multi_row_per_key_call_order() -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "cassette.jsonl")
        cass = llm_cassette.Cassette(cpath)
        payload = {"messages": [{"role": "user", "content": "same request twice"}]}
        key = llm_cassette.request_key(payload)
        cass.record(key, payload, "first call output", 10)
        cass.record(key, payload, "second call output", 20)

        h1 = cass.lookup(key)
        h2 = cass.lookup(key)
        h3 = cass.lookup(key)
        assert_true(h1 == ("first call output", 10), f"1st lookup must return the 1st recorded row, got {h1}")
        assert_true(h2 == ("second call output", 20), f"2nd lookup must return the 2nd recorded row, got {h2}")
        assert_true(h3 is None, "3rd lookup with only 2 recorded rows must miss")
    print("PASS (c): multi-row-per-key consumed in call order")


# ---------------------------------------------------------------------------
# (d) replay mode returns recorded content WITHOUT touching the network —
#     both the streaming and legacy _call_llama branches.
# ---------------------------------------------------------------------------

async def _run_replay_no_network(streaming: bool) -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "cassette.jsonl")
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "replay-no-network probe"},
        ]
        max_tokens = 128
        task_type = "agent"

        # Build the SAME payload _call_llama would build for this branch (GBNF is off
        # by default in this test env, so no "grammar" key) to derive a matching key.
        kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": None, "task_type": task_type}
        if streaming:
            kwargs["stream"] = True
        payload = build_llama_payload(messages, **kwargs)
        key = llm_cassette.request_key(payload, task_type)

        cass = llm_cassette.Cassette(cpath)
        cass.record(key, payload, "replayed content, no network involved", 99)

        with cassette_env(mode="replay", path=cpath), env_var("LLAMA_USE_STREAMING", "true" if streaming else "false"):
            saved_client = httpx.AsyncClient
            httpx.AsyncClient = _ExplodingAsyncClient  # type: ignore[assignment]
            try:
                executor = LocalAgentExecutor(fallback_endpoint="")
                content, tokens = await executor._call_llama(
                    messages, max_tokens=max_tokens, task_type=task_type,
                )
            finally:
                httpx.AsyncClient = saved_client

        branch = "streaming" if streaming else "legacy"
        assert_true(
            (content, tokens) == ("replayed content, no network involved", 99),
            f"replay ({branch} branch) must return the recorded row, got {(content, tokens)}",
        )


def test_replay_returns_recorded_content_without_network() -> None:
    asyncio.run(_run_replay_no_network(streaming=True))
    asyncio.run(_run_replay_no_network(streaming=False))
    print("PASS (d): replay returns recorded content with zero network I/O (streaming + legacy branches)")


# ---------------------------------------------------------------------------
# (e) on_miss policies
# ---------------------------------------------------------------------------

def test_on_miss_policies() -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "empty_cassette.jsonl")
        Path(cpath).write_text("")  # cassette exists but has no matching row
        payload = {"messages": [{"role": "user", "content": "never recorded"}], "max_tokens": 5}

        with cassette_env(mode="replay", path=cpath, on_miss="error"):
            try:
                llm_cassette.replay_lookup(payload)
                raise AssertionError("expected ReplayMiss for on_miss=error")
            except llm_cassette.ReplayMiss as e:
                assert_true(bool(e.key), "ReplayMiss must carry the computed key")

        with cassette_env(mode="replay", path=cpath, on_miss="passthrough"):
            result = llm_cassette.replay_lookup(payload)
            assert_true(result is None, "on_miss=passthrough must return None (fall through to live)")

        with cassette_env(mode="replay", path=cpath, on_miss="empty"):
            result = llm_cassette.replay_lookup(payload)
            assert_true(result == ("", 0), f"on_miss=empty must return ('', 0), got {result}")
    print("PASS (e): on_miss policies (error raises ReplayMiss / passthrough -> None / empty -> ('',0))")


# ---------------------------------------------------------------------------
# (f) mode=off is a strict no-op
# ---------------------------------------------------------------------------

async def _run_mode_off_is_noop() -> None:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "unused_cassette.jsonl")
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "off-mode probe"}]

        live_response = _FakeResponse(200, {
            "choices": [{"message": {"content": "LIVE-PATH-TAKEN"}}],
            "usage": {"total_tokens": 11},
        })

        # mode omitted entirely -> "off" (the sacrosanct default).
        with cassette_env(mode=None, path=cpath), env_var("LLAMA_USE_STREAMING", "false"):
            saved_client = httpx.AsyncClient
            httpx.AsyncClient = _make_single_response_client(live_response)  # type: ignore[assignment]
            try:
                executor = LocalAgentExecutor(fallback_endpoint="")
                content, tokens = await executor._call_llama(messages, max_tokens=64, task_type="agent")
            finally:
                httpx.AsyncClient = saved_client

        assert_true(
            (content, tokens) == ("LIVE-PATH-TAKEN", 11),
            f"mode=off must take the live path unmodified, got {(content, tokens)}",
        )
        assert_true(not Path(cpath).exists(), "mode=off must never write to a cassette file")


def test_mode_off_is_noop() -> None:
    asyncio.run(_run_mode_off_is_noop())
    print("PASS (f): mode=off is a strict no-op — live path taken, zero cassette I/O")


# ---------------------------------------------------------------------------
# (g) golden end-to-end: record (stubbed) -> replay through the real
#     _execute_with_tools, offline, identical loop behavior.
# ---------------------------------------------------------------------------

def _golden_task() -> Task:
    return Task(
        id="golden-e2e",
        objective="Run the probe command with run_command and report the result.",
        # "research" is an analysis-only task_type — avoids the no-action edit-forcing
        # intervention (agent_executor.py ~L1672) so the loop terminates in exactly
        # 2 LLM turns: one tool call, one prose final answer.
        task_type="research",
    )


async def _run_golden_e2e() -> Dict[str, Any]:
    turn1 = '{"function": "run_command", "arguments": {"command": "echo golden-e2e-probe"}}'
    turn2 = "Command executed successfully. Task complete."

    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "golden.jsonl")
        saved_client = httpx.AsyncClient
        try:
            # --- Pass 1: record. Network is STUBBED with canned turns (not a live APU
            # call) — this is the harness's own record path, exercised end-to-end. ---
            with cassette_env(mode="record", path=cpath), env_var("LLAMA_USE_STREAMING", "false"):
                httpx.AsyncClient = _make_scripted_client([turn1, turn2])  # type: ignore[assignment]
                registry1 = ToolRegistry(db_path=Path(td) / "audit_record.db")
                register_shell_tools(registry1)
                executor1 = LocalAgentExecutor(tool_registry=registry1, fallback_endpoint="")
                task1 = _golden_task()
                record_response, _record_tokens = await executor1._execute_with_tools(
                    task1, AgentType.AGENT, max_tool_calls=5,
                )

            assert_true(Path(cpath).exists(), "record pass must create the cassette file")
            recorded_rows = sum(1 for line in Path(cpath).read_text().splitlines() if line.strip())
            assert_true(
                recorded_rows == 2,
                f"record pass must write exactly 2 rows (2 distinct LLM turns), got {recorded_rows}",
            )

            # --- Pass 2: replay. Network EXPLODES if touched — proves it's offline. ---
            with cassette_env(mode="replay", path=cpath), env_var("LLAMA_USE_STREAMING", "false"):
                httpx.AsyncClient = _ExplodingAsyncClient  # type: ignore[assignment]
                registry2 = ToolRegistry(db_path=Path(td) / "audit_replay.db")
                register_shell_tools(registry2)
                executor2 = LocalAgentExecutor(tool_registry=registry2, fallback_endpoint="")
                task2 = _golden_task()
                task2.id = "golden-e2e-replay"
                replay_response, _replay_tokens = await executor2._execute_with_tools(
                    task2, AgentType.AGENT, max_tool_calls=5,
                )
        finally:
            httpx.AsyncClient = saved_client

        return {
            "record_response": record_response,
            "replay_response": replay_response,
            "record_tool_calls": [(tc.tool_name, tc.status, tc.result) for tc in task1.tool_calls_made],
            "replay_tool_calls": [(tc.tool_name, tc.status, tc.result) for tc in task2.tool_calls_made],
        }


def test_golden_e2e_record_then_replay_through_execute_with_tools() -> None:
    outcome = asyncio.run(_run_golden_e2e())
    assert_true(
        outcome["record_response"] == outcome["replay_response"] == "Command executed successfully. Task complete.",
        f"replay must reproduce the identical final answer, got {outcome}",
    )
    assert_true(
        outcome["record_tool_calls"] == outcome["replay_tool_calls"],
        f"replay must reproduce identical tool-call outcomes, got {outcome}",
    )
    assert_true(
        len(outcome["replay_tool_calls"]) == 1 and outcome["replay_tool_calls"][0][0] == "run_command",
        f"replay must reproduce exactly the one run_command call, got {outcome['replay_tool_calls']}",
    )
    assert_true(
        outcome["replay_tool_calls"][0][1] == "completed" and outcome["replay_tool_calls"][0][2].get("success") is True,
        f"replay must reproduce a successful run_command execution, got {outcome['replay_tool_calls']}",
    )
    print(
        "PASS (g): golden end-to-end — record (stubbed) -> replay through the real "
        "_execute_with_tools, fully offline, identical loop behavior"
    )


# ---------------------------------------------------------------------------
# DoD payoff demonstration: record + replay a synthetic run_command call carrying
# this session's live tool-call-JSON-artifact tail ("...\n},\n"), proving the
# committed strip fix (builtin_tools/shell_tools.py:147) resolves it offline.
# ---------------------------------------------------------------------------

async def _run_artifact_strip_replay_demo() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        cpath = str(Path(td) / "artifact_demo_cassette.jsonl")
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "grep the codebase for a pattern"},
        ]
        max_tokens = 128
        task_type = "agent"

        # The malformed content this session actually produced live: the model's
        # streaming/GBNF tool-call parser leaked the JSON envelope's closing
        # punctuation into the "command" string's value.
        artifact_content = (
            '{"function": "run_command", "arguments": '
            '{"function": "run_command", "arguments": '
            '{"command": "echo artifact-strip-fix-works\n},\n"}}'
        )

        kwargs: Dict[str, Any] = {"max_tokens": max_tokens, "role": None, "task_type": task_type}
        payload = build_llama_payload(messages, **kwargs)
        key = llm_cassette.request_key(payload, task_type)
        cass = llm_cassette.Cassette(cpath)
        cass.record(key, payload, artifact_content, 37, {"demo": "run_command-artifact-tail"})

        with cassette_env(mode="replay", path=cpath), env_var("LLAMA_USE_STREAMING", "false"):
            saved_client = httpx.AsyncClient
            httpx.AsyncClient = _ExplodingAsyncClient  # type: ignore[assignment]
            try:
                registry = ToolRegistry(db_path=Path(td) / "artifact_audit.db")
                register_shell_tools(registry)
                executor = LocalAgentExecutor(tool_registry=registry, fallback_endpoint="")
                content, tokens = await executor._call_llama(
                    messages, max_tokens=max_tokens, task_type=task_type,
                )
            finally:
                httpx.AsyncClient = saved_client

        assert_true(content == artifact_content, "replay must return the exact recorded artifact-tailed content, offline")
        assert_true(tokens == 37, "replay must return the recorded token count")

        # Run the REPLAYED content through the real loop-side handling: parse the tool
        # call, then execute it via the already-committed artifact-strip fix.
        tool_call = registry.parse_tool_call_from_llama(content)
        assert_true(tool_call is not None, "parse_tool_call_from_llama must parse the artifact-tailed JSON")
        assert_true(tool_call.tool_name == "run_command", f"expected run_command, got {tool_call.tool_name}")
        raw_command = tool_call.arguments.get("command", "")
        assert_true(
            raw_command.endswith("\n},\n"),
            f"parsed command must still carry the raw artifact tail (the fix strips it downstream, "
            f"in run_command_handler, not in parsing) — got {raw_command!r}",
        )

        result = await registry.execute_tool_call(tool_call)
        return {"raw_command": raw_command, "status": result.status, "result": result.result}


def test_artifact_strip_fix_resolves_via_offline_replay() -> None:
    outcome = asyncio.run(_run_artifact_strip_replay_demo())
    assert_true(
        outcome["status"] == "completed"
        and isinstance(outcome["result"], dict)
        and outcome["result"].get("success") is True
        and "artifact-strip-fix-works" in (outcome["result"].get("stdout") or ""),
        f"the committed artifact-strip fix (shell_tools.py:147) must make the "
        f"\\n}},\\n-tailed run_command call succeed on replay, got {outcome}",
    )
    print(
        "PASS (DoD demo): run_command call with the live '\\n},\\n' artifact tail, "
        "recorded once and replayed fully offline, resolves via the committed "
        "shell_tools.py strip fix — outcome=" + json.dumps(outcome)
    )


# ---------------------------------------------------------------------------

def main() -> int:
    test_request_key_stable_and_excludes_volatile()
    test_record_lookup_roundtrip()
    test_multi_row_per_key_call_order()
    test_replay_returns_recorded_content_without_network()
    test_on_miss_policies()
    test_mode_off_is_noop()
    test_golden_e2e_record_then_replay_through_execute_with_tools()
    test_artifact_strip_fix_resolves_via_offline_replay()
    print("PASS: llm-cassette record/replay harness — all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "sed -n '1,125p' ai-stack/local-agents/builtin_tools/shell_tools.py
sed -n '210,330p' ai-stack/local-agents/builtin_tools/shell_tools.py
rg -n \"def build_argv|class Nsjail|shell=True|/bin/(ba)?sh|-c\" ai-stack/local-agents/builtin_tools scripts/ai | head -100" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 66ms:
#!/usr/bin/env python3
"""
Built-in Shell Command Tools for Local Agents

Provides safe shell command execution with sandboxing:
- run_command: Execute shell commands (sandboxed)
- get_system_info: Get CPU, memory, disk stats
- check_service: Check systemd service health

Part of Phase 11 Batch 11.1: Tool Calling Infrastructure
"""

import asyncio
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
from typing import Dict

from tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)

# Phase 164 Stage B: RTK (Rust Token Killer) shell output compression.
# When rtk is in PATH (installed as a NixOS system package), run_command wraps
# the command with `rtk <cmd>` so output is compressed before entering LLM context.
# Disable via SWB_RTK_ENABLED=0 or RTK_BIN="".
_RTK_BIN: str = os.environ.get("RTK_BIN", "") or shutil.which("rtk") or ""
_RTK_ENABLED: bool = bool(_RTK_BIN) and os.environ.get("SWB_RTK_ENABLED", "1").strip() not in ("0", "false", "no")


# Whitelist of safe commands
# Extended (2026-05-18) to include aq-* harness tools and common analysis tools
# that agents legitimately need. run_shell_command is an alias registered below
# to handle models that emit the wrong tool name.
class NsjailSandbox:
    """Linux namespace sandbox for SAFE_COMMANDS execution (Phase 62.2, AM-G6).

    Uses nsjail to run commands in a minimal read-only Linux namespace:
    - No network (iface_no_lo)
    - No /proc access (disable_proc)
    - Read-only bind of /nix/store and /run/current-system
    - Writable /tmp (tmpfs, 16 MiB)

    If nsjail is configured as required, startup failures fail closed instead of
    silently downgrading to host subprocess execution.
    """

    def __init__(self) -> None:
        bin_path = os.environ.get("NSJAIL_BIN") or shutil.which("nsjail")
        self.available: bool = bool(bin_path and os.path.isfile(bin_path))
        self.bin: str = bin_path or ""
        self.required: bool = os.environ.get("NSJAIL_REQUIRED", "0").strip().lower() in {"1", "true", "yes"}

    def build_argv(self, command: str, timeout_seconds: int) -> list:
        """Build nsjail argv wrapping the given shell command string."""
        return [
            self.bin,
            "--mode", "once",
            "--time_limit", str(timeout_seconds),
            "--max_cpus", "1",
            "--rlimit_nofile", "64",
            "--disable_proc",
            "--iface_no_lo",
            "--bindmount_ro", "/nix/store",
            "--bindmount_ro", "/run/current-system",
            "--tmpfs", "/tmp:size=16m",
            "--cwd", "/tmp",
            "--",
            "/run/current-system/sw/bin/sh", "-c", command,
        ]


_nsjail = NsjailSandbox()

_SHELL_CONTROL_PATTERN = re.compile(r"(?:;|&&|\|\||`|\$\(|\$\{|\n|\r)")


SAFE_COMMANDS = {
    # System inspection (read-only)
    "ls", "pwd", "echo", "cat", "head", "tail", "wc", "grep", "rg",
    "find", "which", "whoami", "hostname", "date", "uptime",
    "free", "df", "du", "ps", "top", "systemctl", "journalctl",
    # Git (read-only ops)
    "git",
    # HTTP — coordinator/RAG/memory API calls (coordinator at :8003 only; :8002 blocked by safe_command_executor.py)
    "curl",
    # Code analysis / validation
    "bash", "python3", "python", "nix-instantiate", "nix",
    "shellcheck", "statix", "deadnix",
    # Harness tools (full suite from LOCAL-AGENT.md)
    "agrep", "als", "acat", "asum",
    "aq-qa", "aq-hints", "aq-report", "aq-session-start",
    "aq-commit-facts", "aq-lesson-promote", "aq-crystallize",
    "aq-agent-loop", "aqd",
    # understand-anything mapping: agents consult subsystem wiki + graph on demand
    # (aq-wiki --section/--list/--status). Without this the agent cannot benefit
    # from the codebase mapping during autonomous runs.
    "aq-wiki",
    # OpenCode CLI (Phase 60 Integration)
    "opencode",
    # JSON/YAML inspection
    "jq", "yq",
    # File utilities
    "fd", "sort", "uniq", "cut", "awk", "sed", "tr", "printf", "tee",
    # Browser / Javascript execution
    "chromium", "playwright", "node", "lighthouse",
}


async def run_command_handler(
    command: str,
    timeout_seconds: int = 10,
) -> Dict:
    """
    Execute a safe shell command.

        # applies before reaching this path.
        #
        # Phase 164 Stage B: when RTK is available, wrap the command so output
        # is compressed before it enters the LLM context window. RTK handles
        # git, grep, ls, pytest, cargo, docker, kubectl, and 100+ other commands.
        # Falls back to uncompressed execution if RTK fails.
        if _RTK_ENABLED:
            try:
                rtk_argv = [_RTK_BIN] + shlex.split(command)
                result = subprocess.run(
                    rtk_argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "compressed": True,
                }
            except Exception as rtk_exc:
                logger.debug("RTK compression failed (%s), falling back to plain subprocess", rtk_exc)

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout_seconds}s",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Command failed: {e}",
        }


async def get_system_info_handler() -> Dict:
    """
    Get system information (CPU, memory, disk).

    Returns:
        {
            "cpu": {...},
            "memory": {...},
            "disk": {...}
        }
    """
    info = {}

    # CPU info
    try:
        result = subprocess.run(
            ["nproc"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        info["cpu"] = {
            "cores": int(result.stdout.strip()) if result.returncode == 0 else None,
        }
    except:
        info["cpu"] = {"error": "Failed to get CPU info"}

    # Memory info
    try:
        result = subprocess.run(
            ["free", "-m"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            if len(lines) >= 2:
                mem_line = lines[1].split()
                info["memory"] = {
                    "total_mb": int(mem_line[1]),
                    "used_mb": int(mem_line[2]),
                    "free_mb": int(mem_line[3]),
                }
    except:
        info["memory"] = {"error": "Failed to get memory info"}

    # Disk info
    try:
        result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            if len(lines) >= 2:
                disk_line = lines[1].split()
                info["disk"] = {
                    "total": disk_line[1],
                    "used": disk_line[2],
                    "available": disk_line[3],
                    "use_percent": disk_line[4],
                }
    except:
        info["disk"] = {"error": "Failed to get disk info"}

    return info
scripts/ai/aq-patterns:269:        extract_hint_patterns | python3 -c "
ai-stack/local-agents/builtin_tools/file_operations.py:402:    if old_string is not found so the model can self-correct.
ai-stack/local-agents/builtin_tools/file_operations.py:419:            # Provide a snippet of the file to help the model self-correct its old_string
scripts/ai/aq-drop:79:DROP_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
scripts/ai/aq-understand-anything:16:  aq-understand-anything dashboard-command [project-dir]
scripts/ai/aq-understand-anything:246:    dashboard-command)
scripts/ai/aq-capability-patch-prep:3:aq-capability-patch-prep — prepare a bounded patch artifact for capability catalog changes.
scripts/ai/aq-capability-patch-prep:14:CATALOG_PATH = REPO_ROOT / "config" / "capability-gap-catalog.json"
scripts/ai/aq-capability-patch-prep:19:    parser.add_argument("--updated-catalog-file", required=True, help="Updated catalog artifact from aq-capability-catalog-append.")
scripts/ai/aq-capability-patch-prep:20:    parser.add_argument("--catalog", default=str(CATALOG_PATH), help="Base capability catalog path.")
scripts/ai/aq-rag-prewarm:11:CURL_BIN="${AQ_PREWARM_CURL_BIN:-curl}"
scripts/ai/aq-rag-prewarm:171:      --max-time 30 --connect-timeout 5 \
scripts/ai/aq-rag-prewarm:239:    "${MAX_JOBS}" "$(printf '%s' "${SELECTED_PROMPT_IDS[*]}" | python3 -c 'import json, sys; data=sys.stdin.read().split(); print(json.dumps(data if data else []))')"
scripts/ai/autonomous-coordinator-local.sh:20:    local policy_file="config/autonomous-coordinator-security-policy.json"
scripts/ai/autonomous-coordinator-local.sh:52:        --compact \
scripts/ai/autonomous-coordinator-local.sh:66:                "ai-stack/mcp-servers/hybrid-coordinator/http_server.py"
scripts/ai/autonomous-coordinator-local.sh:103:                "Review existing implementation in ${relevant_files[0]:-codebase}"
scripts/ai/aq-sync-shared-skills.py:37:        "--check",
ai-stack/local-agents/builtin_tools/shell_tools.py:44:class NsjailSandbox:
ai-stack/local-agents/builtin_tools/shell_tools.py:63:    def build_argv(self, command: str, timeout_seconds: int) -> list:
ai-stack/local-agents/builtin_tools/shell_tools.py:76:            "--cwd", "/tmp",
ai-stack/local-agents/builtin_tools/shell_tools.py:78:            "/run/current-system/sw/bin/sh", "-c", command,
ai-stack/local-agents/builtin_tools/shell_tools.py:102:    "aq-commit-facts", "aq-lesson-promote", "aq-crystallize",
ai-stack/local-agents/builtin_tools/shell_tools.py:139:    # Strip trailing tool-call JSON artifacts before ANY check. The local model's
ai-stack/local-agents/builtin_tools/shell_tools.py:140:    # GBNF/streaming tool-call parser can leak the envelope's closing punctuation
ai-stack/local-agents/builtin_tools/shell_tools.py:141:    # into the command argument (e.g. "grep ... file\n},\n"), which the shell-control
ai-stack/local-agents/builtin_tools/shell_tools.py:146:    # cleanup, not a security relaxation. Root cause: local-agent-tool-call-json-artifact-leak.
ai-stack/local-agents/builtin_tools/shell_tools.py:237:            shell=True,
scripts/ai/aq-capability-gap:3:aq-capability-gap — classify missing tools, workflows, and skills.
scripts/ai/aq-capability-gap:19:CATALOG_PATH = REPO_ROOT / "config" / "capability-gap-catalog.json"
scripts/ai/aq-capability-gap:31:    parser.add_argument("--context-language", dest="context_language", help="Optional implementation language hint, for example nix, python, shell.")
scripts/ai/aq-capability-gap:32:    parser.add_argument("--context-application", dest="context_application", help="Optional application/domain hint, for example nixos, ai-stack, prsi.")
scripts/ai/aq-capability-gap:33:    parser.add_argument("--context-file", dest="context_file", help="Optional current file path hint.")
scripts/ai/aq-capability-gap:35:    parser.add_argument("--catalog", default=str(CATALOG_PATH), help="Capability gap catalog path.")
scripts/ai/aq-capability-gap:465:    hints.append("config/capability-gap-catalog.json")
scripts/ai/aq-capability-gap:576:        context_flags.extend(["--context-language", context["language"]])
scripts/ai/aq-capability-gap:578:        context_flags.extend(["--context-application", context["application"]])
scripts/ai/aq-capability-gap:580:        context_flags.extend(["--context-file", context["file"]])
scripts/ai/aq-capability-gap:584:            f"python3 scripts/ai/aq-capability-stub --tool {capability_id}{context_suffix}" if not capability_id.startswith(("workflow:", "skill:")) else (
scripts/ai/aq-capability-gap:585:                f"python3 scripts/ai/aq-capability-stub --workflow {capability_id.split('workflow:',1)[1]}{context_suffix}"
scripts/ai/aq-capability-gap:587:                f"python3 scripts/ai/aq-capability-stub --skill {capability_id.split('skill:',1)[1]}{context_suffix}"
scripts/ai/aq-capability-gap:591:            f"python3 scripts/ai/aq-capability-promote --tool {capability_id}{context_suffix}" if capability_type == "tool" else (
scripts/ai/aq-capability-gap:592:                f"python3 scripts/ai/aq-capability-promote --workflow {capability_id.split('workflow:',1)[1]}{context_suffix}"
scripts/ai/aq-capability-gap:594:                f"python3 scripts/ai/aq-capability-promote --skill {capability_id.split('skill:',1)[1]}{context_suffix}"
scripts/ai/aq-capability-gap:599:            f"aq-context-bootstrap --task \"add remediation path for missing capability {capability_id}\" --scope harness-first --format json"
scripts/ai/aq-capability-gap:608:                "config/capability-gap-catalog.json"
scripts/ai/aq-index:11:    aq-index stats [--collection NAME]
scripts/ai/aq-index:28:    aq-index stats --collection interaction-history
scripts/ai/aq-index:213:        "codebase-context",
scripts/ai/aq-index:351:        "--collection",
scripts/ai/aq-tempest:17:REGISTRY_PATH = REPO_ROOT / "config" / "agent-capability-intake-candidates.json"
scripts/ai/aq-tempest:19:INTAKE_CMD = REPO_ROOT / "scripts" / "ai" / "aq-capability-intake"
scripts/ai/aq-tempest:190:        f"Create one with `aq-tempest scope-create --name <name> --targets <cidr-or-host> --approved-by <operator> --purpose <reason>`. See {PRD_PATH.relative_to(REPO_ROOT)}.",
scripts/ai/aq-tempest:255:    scope_create = sub.add_parser("scope-create", help="Create a local self red-team scope receipt")
scripts/ai/aq-tempest:269:    scope_check = sub.add_parser("scope-check", help="Validate one local T3MP3ST scope receipt")
scripts/ai/aqd:39:  aqd workflows brownfield [--target <dir>] [--objective <text>] [--constraints <text>] [--out-of-scope <text>] [--acceptance <text>] [--force]
scripts/ai/aqd:54:  aqd parity cross-client-smoke
scripts/ai/aqd:100:    nix --extra-experimental-features "nix-command flakes" shell nixpkgs#python3 --command python3 "${args[@]}"
scripts/ai/aqd:131:    nix --extra-experimental-features "nix-command flakes" shell \
scripts/ai/aqd:133:      --command python3 "${args[@]}"
scripts/ai/aqd:532:- `phase-02-core-feature.md`
scripts/ai/aqd:646:  cat > "$hooks_dir/pre-commit" <<'EOF'
scripts/ai/aqd:650:files="$(git diff --cached --name-only --diff-filter=ACM)"
scripts/ai/aqd:710:    patch="$(git show --format= --no-color "$commit" 2>/dev/null || true)"
scripts/ai/aqd:729:  chmod +x "$hooks_dir/pre-commit" "$hooks_dir/pre-push"
scripts/ai/aqd:795:- git secret guards installed (.git/hooks/pre-commit, .git/hooks/pre-push)
scripts/ai/aqd:951:      --constraints) constraints="${2:-}"; shift 2 ;;
scripts/ai/aqd:1065:22. parity cross-client-smoke
scripts/ai/aqd:1122:  local contract_file="$target_dir/.agent/workflows/intent-contract.json"
scripts/ai/aqd:1138:    render_template_file "$template_root/.agent/workflows/intent-contract.json.tmpl" "$contract_file" "$project_name" "$goal" "$stack" "$owner"
scripts/ai/aqd:1149:  - .agent/workflows/intent-contract.json
scripts/ai/aqd:1302:CONTRACT_PATH="${2:-.agent/workflows/intent-contract.json}"
scripts/ai/aqd:1326:  payload="$(jq -c --arg query "$QUERY" '{query:$query,safety_mode:"plan-readonly",token_limit:8000,tool_call_limit:40,intent_contract:.}' "$CONTRACT_PATH")"
scripts/ai/aqd:1387:  - .agent/workflows/intent-contract.json
scripts/ai/aqd:1403:  run_python_with_yaml "${REPO_ROOT}/.agent/skills/skill-creator/scripts/quick_validate.py" "$skill_path"
scripts/ai/aqd:1410:  run_python "${REPO_ROOT}/.agent/skills/skill-creator/scripts/init_skill.py" "$name" "$@"
scripts/ai/aqd:1418:    run_python_with_yaml "${REPO_ROOT}/.agent/skills/skill-creator/scripts/package_skill.py" "$skill_path" "$output_dir"
scripts/ai/aqd:1420:    run_python_with_yaml "${REPO_ROOT}/.agent/skills/skill-creator/scripts/package_skill.py" "$skill_path"
scripts/ai/aqd:1474:  curl -sf "${url}/control/reasoning/profiles" | python3 -c "
scripts/ai/aqd:1482:" 2>/dev/null || { echo "[WARN] coordinator not reachable — showing local profile file"; python3 -c "
scripts/ai/aqd:1509:    "${url}/control/reasoning/profile/apply" | python3 -c "
scripts/ai/aqd:1525:    -d "{\"query\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$query"),\"top_k\":${top_k}}" \
scripts/ai/aqd:1526:    "${dash_url}/api/logic/search" | python3 -c "
scripts/ai/aqd:1551:  curl -sf "${dash_url}/api/topology" | python3 -c "
scripts/ai/aqd:1605:  "${REPO_ROOT}/scripts/testing/smoke-cross-client-compat.sh"
scripts/ai/aqd:1684:  echo "$resp" | python3 -c "
scripts/ai/aqd:1701:  echo "$resp" | python3 -c "
scripts/ai/aqd:1730:    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('default_safety_mode','execute-mutating'))" 2>/dev/null \
scripts/ai/aqd:1735:  local payload; payload=$(python3 -c "
scripts/ai/aqd:1766:  local payload; payload=$(python3 -c "import json,sys; print(json.dumps({'query': sys.argv[1], 'mode': 'plan-readonly', 'prefer_local': True}))" "$task")
scripts/ai/aqd:1784:  local payload; payload=$(python3 -c "import json,sys; print(json.dumps({'query': sys.argv[1], 'mode': sys.argv[2], 'prefer_local': True}))" "$task" "$mode")
scripts/ai/aqd:1811:  status=$(echo "$resp"  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "?")
scripts/ai/aqd:1812:  phase=$(echo "$resp"   | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('current_phase_index','?'))" 2>/dev/null || echo "?")
scripts/ai/aqd:1813:  updated=$(echo "$resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('updated_at','?'))" 2>/dev/null || echo "?")
scripts/ai/aqd:1821:  _aqd_http_get "$url" | python3 -c "
scripts/ai/aqd:1854:    payload=$(python3 -c "import json,sys; print(json.dumps({'task': sys.argv[1], 'template_id': sys.argv[2]}))" "$task" "$template")
scripts/ai/aqd:1856:    payload=$(python3 -c "import json,sys; print(json.dumps({'task': sys.argv[1], 'template_id': 'coding-staged'}))" "$task")
scripts/ai/aqd:1862:  local run_id; run_id=$(echo "$resp" | python3 -c "import json,sys; print(json.load(sys.stdin).get('run_id',''))" 2>/dev/null)
scripts/ai/aqd:1871:  _aqd_http_get "$url" | python3 -c "
scripts/ai/aqd:1932:    parity:cross-client-smoke) cmd_parity_cross_client_smoke "$@" ;;

codex
Two substantive issues are already emerging: the shell cleanup mutates legitimate quoted commands, and the surrounding shell guard still allows single-pipe/redirection-style shell syntax. I’m now validating those with harmless probes and checking whether cassette keying ignores parameters that materially change generation.
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "python3 - <<'PY'
import asyncio, importlib.util
from pathlib import Path
p=Path('ai-stack/local-agents/builtin_tools/shell_tools.py')
spec=importlib.util.spec_from_file_location('shell_tools_review', p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
async def main():
    for cmd in ['printf \"%s\" \"]\"', 'echo SAFE | printf PIPED', 'echo SAFE > harmless-output']:
        cleaned=m.re.sub(r'[\\s}\\]\",]+"'$'"', '', cmd)
        print(repr(cmd), '=>', repr(cleaned), 'guard=', bool(m._SHELL_CONTROL_PATTERN.search(cleaned)))
        if cmd "'!= '"'echo SAFE > harmless-output':
            print(await m.run_command_handler(cmd))
asyncio.run(main())
PY
rg -n \"frequency_penalty|repeat_penalty|repeat_last_n|chat_template_kwargs|enable_thinking|def build_llama_payload|temperature\" ai-stack/mcp-servers/shared/llm_config.py config/llm-config.yaml config 2>/dev/null | head -220" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 270ms:
Traceback (most recent call last):
  File "<stdin>", line 5, in <module>
  File "<frozen importlib._bootstrap_external>", line 1023, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/shell_tools.py", line 23, in <module>
    from tool_registry import (
    ...<4 lines>...
    )
ModuleNotFoundError: No module named 'tool_registry'
ai-stack/mcp-servers/shared/llm_config.py:9:  - chat_template_kwargs: {"enable_thinking": False}
ai-stack/mcp-servers/shared/llm_config.py:11:    Top-level enable_thinking is silently ignored — it MUST be nested here.
ai-stack/mcp-servers/shared/llm_config.py:14:  - chat_template_kwargs: {"enable_thinking": True, "thinking_budget": N}
ai-stack/mcp-servers/shared/llm_config.py:29:  Profiles set temperature, frequency_penalty, enable_thinking, and thinking_budget.
ai-stack/mcp-servers/shared/llm_config.py:37:    payload = build_llama_payload(messages, max_tokens=8, temperature=0.0, model="local")
ai-stack/mcp-servers/shared/llm_config.py:154:    enable_thinking defaults to False for most profiles (Renoir APU 1 tok/s —
ai-stack/mcp-servers/shared/llm_config.py:170:    temperature: float
ai-stack/mcp-servers/shared/llm_config.py:171:    frequency_penalty: float
ai-stack/mcp-servers/shared/llm_config.py:172:    enable_thinking: bool
ai-stack/mcp-servers/shared/llm_config.py:181:    # frequency_penalty=0.0: cumulative penalty causes early EOS on dense
ai-stack/mcp-servers/shared/llm_config.py:185:        temperature=0.0,
ai-stack/mcp-servers/shared/llm_config.py:186:        frequency_penalty=0.0,
ai-stack/mcp-servers/shared/llm_config.py:187:        enable_thinking=False,
ai-stack/mcp-servers/shared/llm_config.py:195:        temperature=0.1,
ai-stack/mcp-servers/shared/llm_config.py:196:        frequency_penalty=0.0,
ai-stack/mcp-servers/shared/llm_config.py:197:        enable_thinking=False,
ai-stack/mcp-servers/shared/llm_config.py:202:    # Code generation and debugging. frequency_penalty=0.0 avoids truncation
ai-stack/mcp-servers/shared/llm_config.py:206:        temperature=0.15,
ai-stack/mcp-servers/shared/llm_config.py:207:        frequency_penalty=0.0,
ai-stack/mcp-servers/shared/llm_config.py:208:        enable_thinking=False,
ai-stack/mcp-servers/shared/llm_config.py:213:    # Architecture, analysis, design decisions. Higher temperature for more
ai-stack/mcp-servers/shared/llm_config.py:214:    # exploratory prose. Mild frequency_penalty is safe for natural language.
ai-stack/mcp-servers/shared/llm_config.py:215:    # enable_thinking=False until hardware supports larger budgets without timeout.
ai-stack/mcp-servers/shared/llm_config.py:218:        temperature=0.5,
ai-stack/mcp-servers/shared/llm_config.py:219:        frequency_penalty=0.05,
ai-stack/mcp-servers/shared/llm_config.py:220:        enable_thinking=False,
ai-stack/mcp-servers/shared/llm_config.py:228:        temperature=0.3,
ai-stack/mcp-servers/shared/llm_config.py:229:        frequency_penalty=0.0,
ai-stack/mcp-servers/shared/llm_config.py:230:        enable_thinking=False,
ai-stack/mcp-servers/shared/llm_config.py:241:        temperature=0.4,
ai-stack/mcp-servers/shared/llm_config.py:242:        frequency_penalty=0.0,
ai-stack/mcp-servers/shared/llm_config.py:243:        enable_thinking=True,
ai-stack/mcp-servers/shared/llm_config.py:255:        temperature=0.5,
ai-stack/mcp-servers/shared/llm_config.py:256:        frequency_penalty=0.05,
ai-stack/mcp-servers/shared/llm_config.py:257:        enable_thinking=True,
ai-stack/mcp-servers/shared/llm_config.py:275:def build_llama_payload(
ai-stack/mcp-servers/shared/llm_config.py:279:    temperature: float | None = None,
ai-stack/mcp-servers/shared/llm_config.py:294:        temperature: Sampling temperature. If None, defers to task_type profile
ai-stack/mcp-servers/shared/llm_config.py:302:              When set, activates profile-specific temperature, frequency_penalty,
ai-stack/mcp-servers/shared/llm_config.py:303:              enable_thinking, and thinking_budget. Explicit keyword args override the profile.
ai-stack/mcp-servers/shared/llm_config.py:307:                 frequency_penalty in **extra overrides the profile value.
ai-stack/mcp-servers/shared/llm_config.py:319:    # temperature: explicit arg > profile > legacy default 0.3
ai-stack/mcp-servers/shared/llm_config.py:320:    _temperature = temperature if temperature is not None else (
ai-stack/mcp-servers/shared/llm_config.py:321:        profile.temperature if profile else 0.3
ai-stack/mcp-servers/shared/llm_config.py:323:    # frequency_penalty: **extra override > profile > legacy default 0.05
ai-stack/mcp-servers/shared/llm_config.py:324:    _freq_penalty = extra.pop("frequency_penalty", profile.frequency_penalty if profile else 0.05)
ai-stack/mcp-servers/shared/llm_config.py:325:    # enable_thinking + thinking_budget: profile-driven.
ai-stack/mcp-servers/shared/llm_config.py:328:    _enable_thinking = profile.enable_thinking if profile else False
ai-stack/mcp-servers/shared/llm_config.py:331:    # ARCH CONSTRAINT: enable_thinking is a Jinja2 chat-template variable.
ai-stack/mcp-servers/shared/llm_config.py:332:    # It MUST be in chat_template_kwargs — top-level is silently ignored by
ai-stack/mcp-servers/shared/llm_config.py:334:    _ctk: dict[str, Any] = {"enable_thinking": _enable_thinking}
ai-stack/mcp-servers/shared/llm_config.py:335:    if _enable_thinking and _thinking_budget is not None:
ai-stack/mcp-servers/shared/llm_config.py:349:        "temperature": _temperature,
ai-stack/mcp-servers/shared/llm_config.py:351:        "chat_template_kwargs": _ctk,
ai-stack/mcp-servers/shared/llm_config.py:353:        # repeat_penalty=1.08 + repeat_last_n=64 guard the sliding window.
ai-stack/mcp-servers/shared/llm_config.py:354:        # frequency_penalty is profile-driven: 0.0 for structured/code (cumulative
ai-stack/mcp-servers/shared/llm_config.py:356:        "repeat_penalty": 1.08,
ai-stack/mcp-servers/shared/llm_config.py:357:        "repeat_last_n": 64,
ai-stack/mcp-servers/shared/llm_config.py:358:        "frequency_penalty": _freq_penalty,
ai-stack/mcp-servers/shared/llm_config.py:371:    # are forwarded without modification. frequency_penalty was already popped above.
config/local-inference-transport-policy.json:12:    "repeat_penalty": 1.08,
config/local-inference-transport-policy.json:13:    "repeat_last_n": 64,
config/local-inference-transport-policy.json:20:      "body_allowlist": ["cache_prompt", "chat_template_kwargs", "frequency_penalty", "max_tokens", "messages", "model", "repeat_last_n", "repeat_penalty", "response_format", "stop", "stream", "stream_options", "temperature", "tool_choice", "tools"]
config/local-inference-transport-policy.json:25:      "body_allowlist": ["cache_prompt", "chat_template_kwargs", "frequency_penalty", "max_tokens", "messages", "model", "repeat_last_n", "repeat_penalty", "response_format", "stop", "stream", "stream_options", "temperature", "tool_choice", "tools"]
config/local-inference-transport-policy.json:30:      "body_allowlist": ["cache_prompt", "chat_template_kwargs", "frequency_penalty", "max_tokens", "messages", "model", "repeat_last_n", "repeat_penalty", "response_format", "stop", "stream", "stream_options", "temperature", "tool_choice", "tools"]
config/local-inference-transport-policy.json:35:      "body_allowlist": ["cache_prompt", "chat_template_kwargs", "frequency_penalty", "max_tokens", "messages", "model", "repeat_last_n", "repeat_penalty", "response_format", "stop", "stream", "stream_options", "temperature", "tool_choice", "tools"]
config/validation-check-registry.json:1540:      "description": "Modal task profiles: TASK_PROFILES in llm_config.py, classify_task_type() in dispatch.py, TaskConfig.task_type field. 5 profiles (structured/lookup/code/reasoning/agent) each with temperature, frequency_penalty, enable_thinking, suggested_remote_profile.",
config/model-coordinator.json:21:      "_comment": "Google Gemini direct (generativelanguage.googleapis.com/v1beta/openai) via the antigravity wrapper -> switchboard -> Gemini backend; NOT OpenRouter (unused). LATEST ids: gemini-3.1-pro (advanced reasoning, complex science/coding), gemini-3.5-flash (high-efficiency, multimodal, speed, agentic loops), gemini-3.1-flash-lite (ultra-efficient, cost-sensitive high-volume). Baseline fallback ids: gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.0-flash (Vertex AI adds -001 suffix). EFFORT (OPTIONAL, remote-native): the *_thinking_level values below are Google's native reasoning-depth control (thinking_level preset minimal|low|medium|high, or thinking_config.thinking_budget int; Vertex thinkingConfig.thinkingBudget). They tune remote reasoning DEPTH only — they are NOT defensive throttles. The remote lane scales to native API ceilings (large context, high concurrency, fast gen); do NOT apply the local Qwen ceilings (enable_thinking=false / thinking_budget~200) here. /v1beta/openai does NOT support OpenAI reasoning_effort. Default lane = gemini-3.5-flash; complex/critical = gemini-3.1-pro. gemini-3.5-flash ships in THREE reasoning-effort levels (low|medium|high via thinking_level) — see `gemini_3_5_flash_efforts` below for per-level capabilities + best-uses (low=fast agentic/IDE loops, medium=balanced default, high=cheaper deep-reasoning pass below the 3.1-pro architect tier).",
config/model-coordinator.json:61:      "_comment": "Local Qwen (single slot, SWB_LOCAL_CONCURRENCY=1, ~1-3.45 tok/s on Renoir APU / 27GB RAM). DEFENSIVE CEILINGS APPLY HERE ONLY: switchboard injects enable_thinking=false (in chat_template_kwargs) and a small local thinking_budget (~200) to prevent a single unbounded thinking loop from locking the harness ~40min or ballooning the KV cache into a GPU OOM. These ceilings must NEVER be applied to remote lanes.",
config/local-model-config.yaml:46:  enable_thinking: false   # CRITICAL: Qwen3 emits reasoning_content (thinking tokens).
config/local-model-config.yaml:48:                           # Applied via: chat_template_kwargs: {"enable_thinking": false}
config/local-model-config.yaml:50:  temperature: 0.7
config/local-model-config.yaml:53:  repeat_penalty: 1.0
config/reasoning-profiles.json:26:        "temperature": 0.3,
config/reasoning-profiles.json:57:        "temperature": 0.5,
config/reasoning-profiles.json:89:        "temperature": 0.7,
config/switchboard-profiles.yaml:349:      - frequency_penalty=0.0 ALWAYS for any structured/JSON/code output (penalty causes premature EOS)
config/local-agent-grounding.md:44:Example: `fix(dispatch): set frequency_penalty=0.0 to prevent JSON truncation`
config/local-agent-grounding.md:65:`frequency_penalty != 0.0` applies cumulative logit penalties. In dense JSON where `"`
config/local-agent-grounding.md:67:at ~line 59-61. ALWAYS use `frequency_penalty=0.0` for structured/code output.
config/local-agent-grounding.md:68:Loop protection: use `repeat_penalty=1.08` + `repeat_last_n=64` (sliding window) instead.
config/local-agent-grounding.md:80:- `enable_thinking` must be in `chat_template_kwargs`, NOT top-level — top-level is silently ignored.
config/clm-compaction-prompt.yaml:9:# Output constraints: max_tokens=512, temperature=0.1, stream=false
config/local-model-requirements.md:29:0.3 **Toggleable thinking via `chat_template_kwargs`.** Reasoning ON for LARGE_SESSION, OFF for the SMALL
config/local-model-requirements.md:30:    fast-lane — without empty responses (we hit thinking-tokens→empty-output). GATE: `enable_thinking:false`
config/local-model-requirements.md:32:0.4 **Structured-output discipline under our decode params.** No JSON truncation under `frequency_penalty=0.0`
config/local-model-requirements.md:33:    + `repeat_penalty≈1.08`; survives GBNF constraint (F2.2 grammar cache) without quality collapse. GATE:
config/ablation-reasoning-profiles.json:18:      "temperature_hint": 0.6,
config/ablation-reasoning-profiles.json:29:      "temperature_hint": 0.6,
config/ablation-reasoning-profiles.json:40:      "temperature_hint": 0.6,
config/ablation-reasoning-profiles.json:51:      "temperature_hint": 0.4,
config/ablation-reasoning-profiles.json:63:      "temperature_hint": 0.3,
config/ablation-reasoning-profiles.json:74:      "temperature_hint": 0.5,
config/ablation-reasoning-profiles.json:85:      "temperature_hint": 0.7,
config/ablation-reasoning-profiles.json:89:      "name": "high-temperature",
config/ablation-reasoning-profiles.json:90:      "description": "Ablation: raises temperature to 0.9 to test stochastic vs deterministic reasoning quality delta.",
config/ablation-reasoning-profiles.json:96:      "temperature_hint": 0.9,
config/ablation-reasoning-profiles.json:97:      "tags": ["ablation", "temperature"]
config/schemas/local-inference-transport.schema.json:53:          "required": ["system_message_sha256", "chat_template_kwargs"],
config/schemas/local-inference-transport.schema.json:56:            "chat_template_kwargs": {"$ref": "#/$defs/chatTemplateKwargs"}
config/schemas/local-inference-transport.schema.json:246:      "required": ["enable_thinking"],
config/schemas/local-inference-transport.schema.json:248:        "enable_thinking": {"type": "boolean"},
config/schemas/local-inference-transport.schema.json:252:      "then": {"properties": {"enable_thinking": {"const": true}}}
config/schemas/local-inference-transport.schema.json:256:      "required": ["messages", "temperature", "max_tokens", "chat_template_kwargs", "repeat_penalty", "repeat_last_n", "frequency_penalty", "cache_prompt", "model"],
config/schemas/local-inference-transport.schema.json:258:        "messages": {"type": "array", "items": {"$ref": "#/$defs/message"}}, "temperature": {"type": "number"},
config/schemas/local-inference-transport.schema.json:260:        "stream": {"type": "boolean"}, "stream_options": {"$ref": "#/$defs/streamOptions"}, "chat_template_kwargs": {"$ref": "#/$defs/chatTemplateKwargs"},
config/schemas/local-inference-transport.schema.json:261:        "frequency_penalty": {"type": "number"}, "repeat_penalty": {"type": "number", "exclusiveMinimum": 0},
config/schemas/local-inference-transport.schema.json:262:        "repeat_last_n": {"type": "integer", "minimum": 0}, "cache_prompt": {"type": "boolean"},
config/schemas/local-inference-transport-policy.schema.json:23:      "required": ["repeat_penalty", "repeat_last_n", "cache_prompt"],
config/schemas/local-inference-transport-policy.schema.json:25:        "repeat_penalty": {"type": "number", "exclusiveMinimum": 0},
config/schemas/local-inference-transport-policy.schema.json:26:        "repeat_last_n": {"type": "integer", "minimum": 0},

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "python3 - <<'PY'
import asyncio, sys
sys.path.insert(0, 'ai-stack/local-agents')
from builtin_tools import shell_tools as m
async def main():
    for cmd in ['printf \"%s\" \"]\"', 'echo SAFE | printf PIPED', 'echo SAFE > harmless-output']:
        cleaned=m.re.sub(r'[\\s}\\]\",]+"'$'"', '', cmd)
        print(repr(cmd), '=>', repr(cleaned), 'guard=', bool(m._SHELL_CONTROL_PATTERN.search(cleaned)))
        if '>' not in cmd:
            print(await m.run_command_handler(cmd))
asyncio.run(main())
PY
sed -n '275,380p' ai-stack/mcp-servers/shared/llm_config.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 392ms:
'printf "%s" "]"' => 'printf "%s' guard= False
{'success': False, 'stdout': '', 'stderr': '/nix/store/zh1ijdhb6gng1509b1zrilb6xlzx60j6-bash-5.3p9/bin/sh: -c: line 1: unexpected EOF while looking for matching `"\'\n', 'returncode': 2}
'echo SAFE | printf PIPED' => 'echo SAFE | printf PIPED' guard= False
{'success': True, 'stdout': 'SAFE | printf PIPED\n', 'stderr': '', 'returncode': 0, 'compressed': True}
'echo SAFE > harmless-output' => 'echo SAFE > harmless-output' guard= False
def build_llama_payload(
    messages: list,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    stream: bool = False,
    role: str | None = None,
    task_type: str | None = None,
    **extra: Any,
) -> dict:
    """Build a llama.cpp-compatible chat completion payload.

    This is the single source of truth for all local model request payloads.
    Never build inline dicts for llama.cpp calls — always use this function.

    Args:
        messages: Chat messages list (OpenAI format).
        max_tokens: Token budget. If None, reads LLAMA_MAX_TOKENS env var,
                    falling back to AGENT_TASK_MAX_TOKENS (1200).
        temperature: Sampling temperature. If None, defers to task_type profile
                     or falls back to 0.3. Explicit value always wins.
        stream: Set True to request SSE streaming.
        role: Authority role (orchestrator/architect/implementer/reviewer).
              Injects a compact role block into the system prompt (~25-35 tokens).
              None = no injection. Never set for EMBEDDED agents.
        task_type: Modal task profile name
              (structured/lookup/code/reasoning/agent/research/deep_reasoning).
              When set, activates profile-specific temperature, frequency_penalty,
              enable_thinking, and thinking_budget. Explicit keyword args override the profile.
              "research" and "deep_reasoning" enable safe thinking with a hard token ceiling.
        **extra: Additional payload fields forwarded verbatim
                 (e.g. stop=[...], tools=[...], cache_prompt=True).
                 frequency_penalty in **extra overrides the profile value.

    Returns:
        dict ready to POST to /v1/chat/completions.
    """
    profile = get_task_profile(task_type)

    _max_tokens = (
        max_tokens
        if max_tokens is not None
        else int(os.environ.get("LLAMA_MAX_TOKENS", str(AGENT_TASK_MAX_TOKENS)))
    )
    # temperature: explicit arg > profile > legacy default 0.3
    _temperature = temperature if temperature is not None else (
        profile.temperature if profile else 0.3
    )
    # frequency_penalty: **extra override > profile > legacy default 0.05
    _freq_penalty = extra.pop("frequency_penalty", profile.frequency_penalty if profile else 0.05)
    # enable_thinking + thinking_budget: profile-driven.
    # Safe thinking: only enabled when thinking_budget is set in the profile,
    # capping the thinking phase so content tokens are never crowded out.
    _enable_thinking = profile.enable_thinking if profile else False
    _thinking_budget: Optional[int] = profile.thinking_budget if profile else None

    # ARCH CONSTRAINT: enable_thinking is a Jinja2 chat-template variable.
    # It MUST be in chat_template_kwargs — top-level is silently ignored by
    # llama.cpp, causing Qwen3-35B to fill all tokens with reasoning_content.
    _ctk: dict[str, Any] = {"enable_thinking": _enable_thinking}
    if _enable_thinking and _thinking_budget is not None:
        _ctk["thinking_budget"] = _thinking_budget

    _messages = _inject_role(messages, role) if role else messages
    # Fable-parity behavioral injection (modal). Skipped for probe-sized budgets,
    # strict-JSON lanes, or FABLE_PARITY=0. SSOT: .agent/FABLE-PARITY-CONTRACT.md.
    if (
        os.environ.get("FABLE_PARITY", "1") != "0"
        and _max_tokens > _FABLE_PARITY_MIN_BUDGET
        and task_type not in _FABLE_PARITY_SKIP_TASK_TYPES
    ):
        _messages = _inject_fable_parity(_messages)
    payload: dict[str, Any] = {
        "messages": _messages,
        "temperature": _temperature,
        "max_tokens": _max_tokens,
        "chat_template_kwargs": _ctk,
        # Anti-loop guardrails.
        # repeat_penalty=1.08 + repeat_last_n=64 guard the sliding window.
        # frequency_penalty is profile-driven: 0.0 for structured/code (cumulative
        # penalty causes early EOS on dense tokens), 0.05 for reasoning (prose).
        "repeat_penalty": 1.08,
        "repeat_last_n": 64,
        "frequency_penalty": _freq_penalty,
        # Phase 173: enable llama.cpp KV-cache prefix reuse for multi-turn sessions.
        # cache_prompt=True tells llama.cpp to cache this prompt's KV state and reuse
        # it on subsequent requests sharing the same prefix (system prompt + history).
        # Improves cache_hit_rate metric (target ≥50%; PRSI found 17.2% without this).
        # Callers may override to False via **extra if needed.
        "cache_prompt": True,
    }
    if stream:
        payload["stream"] = True
        # Request usage stats in the final SSE chunk so callers can track token spend.
        payload["stream_options"] = {"include_usage": True}
    # Extra fields (stop sequences, tool schemas, cache flags, model name, etc.)
    # are forwarded without modification. frequency_penalty was already popped above.
    payload.update(extra)
    return payload

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "python3 - <<'PY'
import asyncio, sys
sys.path.insert(0, 'ai-stack/local-agents')
from builtin_tools import shell_tools as m
m._RTK_ENABLED=False
m._nsjail.available=False
m._nsjail.required=False
async def main():
    for cmd in ['echo SAFE | printf PIPED', 'echo FIRST & echo SECOND']:
        print(repr(cmd), await m.run_command_handler(cmd))
asyncio.run(main())
PY" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 300ms:
'echo SAFE | printf PIPED' {'success': True, 'stdout': 'PIPED', 'stderr': '', 'returncode': 0}
'echo FIRST & echo SECOND' {'success': True, 'stdout': 'SECOND\nFIRST\n', 'stderr': '', 'returncode': 0}

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc 'rg -n "query_aidb|error-solutions" scripts/ai/aq-* ai-stack/local-agents | head -100
scripts/security/security-audit.sh --help 2>&1 | head -80' in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 71ms:
scripts/ai/aq-health-spider:15:  http_failure     → emit event + seed RAG error-solutions
scripts/ai/aq-health-spider:18:  Novel issues seeded to Qdrant error-solutions via llama-embed + Qdrant PUT.
scripts/ai/aq-health-spider:402:    """Seed one entry to Qdrant error-solutions via llama-embed. Returns True on success."""
scripts/ai/aq-health-spider:417:            f"{QDRANT_URL}/collections/error-solutions/points",
scripts/ai/aq-agent-loop:108:    "get_hint", "query_aidb",
scripts/ai/aq-agent-loop:119:                           store_memory, validate_before_commit, get_hint, query_aidb.
scripts/ai/aq-agent-loop:121:                           on Renoir APU (10 tok/s prefill). get_hint/query_aidb enable ORIENT/RESEARCH phases.
scripts/ai/aq-agent-loop:534:            "'self-improvement' = 10 tools (adds get_hint/query_aidb for ORIENT/RESEARCH phases); "
scripts/ai/aq-loop:326:2. RESEARCH — call get_hint(query) and query_aidb(collection='error-solutions')
ai-stack/local-agents/agent_executor.py:1292:        # Observation stagnation: harness query tools (get_hint, query_aidb, etc.) called
ai-stack/local-agents/agent_executor.py:1297:            "get_hint", "query_aidb", "get_prsi_pending", "get_working_memory",
ai-stack/local-agents/agent_executor.py:2130:                    f"harness query calls (get_hint/query_aidb/etc.) without any action — "
ai-stack/local-agents/agent_executor.py:2248:                        f"({_observations_without_action} times: get_hint, query_aidb, etc.) "
ai-stack/local-agents/agent_executor.py:2251:                        "OR write/edit a file. Do NOT call get_hint or query_aidb again "
ai-stack/local-agents/agent_executor.py:2816:            "  it via read_file/query_aidb/get_hint — only fetch more if that block is insufficient.\n"
ai-stack/local-agents/agent_executor.py:2830:            "  query_aidb(query='<issue-title>')                 → known fix patterns (63+ seeded)\n"
ai-stack/local-agents/agent_executor.py:2856:            "STEP 7: store_memory('<fix-pattern-in-one-sentence>', context_type='error-solutions', importance=0.8)\n"
ai-stack/local-agents/agent_executor.py:2870:                "and harness coordination (get_hint, query_aidb, store_memory, get_working_memory). "
ai-stack/local-agents/agent_executor.py:2872:                "get_hint + query_aidb(collection='error-solutions') + get_working_memory "
ai-stack/local-agents/builtin_tools/ai_coordination.py:449:    # 3. AIDB error-solutions — known patterns needing attention
ai-stack/local-agents/builtin_tools/ai_coordination.py:455:                "collection": "error-solutions",
ai-stack/local-agents/builtin_tools/ai_coordination.py:471:                        "source": "aidb:error-solutions",
ai-stack/local-agents/builtin_tools/ai_coordination.py:728:    Primary path for harness-seeded collections (error-solutions, skills-patterns, etc.).
ai-stack/local-agents/builtin_tools/ai_coordination.py:779:    "error-solutions", "skills-patterns", "best-practices", "codebase-context",
ai-stack/local-agents/builtin_tools/ai_coordination.py:786:async def query_aidb_handler(query: str, collection: str = "error-solutions", limit: int = 5) -> Dict:
ai-stack/local-agents/builtin_tools/ai_coordination.py:787:    """Search harness pattern collections. Default 'error-solutions' has 66 seeded fix patterns.
ai-stack/local-agents/builtin_tools/ai_coordination.py:1528:    # query_aidb
ai-stack/local-agents/builtin_tools/ai_coordination.py:1530:        name="query_aidb",
ai-stack/local-agents/builtin_tools/ai_coordination.py:1542:        handler=query_aidb_handler,
ai-stack/local-agents/context_assembler.py:7:discovering fixes/patterns via in-loop tool calls (query_aidb, get_hint) pays
ai-stack/local-agents/context_assembler.py:14:error-solutions, best-practices, skills-patterns, wiki-sections, agent
ai-stack/local-agents/context_assembler.py:44:  Tier 1 — prior fixes (error-solutions, skills-patterns, best-practices):
ai-stack/local-agents/context_assembler.py:81:    ("error-solutions", 3),
ai-stack/local-agents/context_assembler.py:187:        elif collection in ("error-solutions", "best-practices"):
zsh:2: permission denied: scripts/security/security-audit.sh

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "bash scripts/security/security-audit.sh --help 2>&1 | head -100
sed -n '760,840p' ai-stack/local-agents/builtin_tools/ai_coordination.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 67ms:
Usage: scripts/security/security-audit.sh [--repo-root PATH] [--output-dir PATH] [--notify-user USER]

Runs pip-audit on requirements.lock files and npm audit on package.json roots.
Writes JSON report: audit-YYYY-MM-DD.json and latest-security-audit.json.
                    "score": h.get("score", 0.0),
                    "source": f"qdrant:{collection}",
                    "payload": p,
                })
            return {
                "success": True,
                "results": deduped,
                "count": len(deduped),
                "fallback": "qdrant-direct",
            }
    except Exception as e:
        return {"success": False, "error": f"qdrant-direct: {e}"}


# Collections seeded directly to Qdrant (port 6333) by seed-rag-knowledge.py and training pipeline.
# These are separate from AIDB's pgvector store (port 8002) which holds document chunks.
# Phase 175: AIDB pgvector returns wrong content for these names (MCP registry entries, not
# harness patterns) — always go direct to Qdrant for harness pattern collections.
_QDRANT_COLLECTIONS: frozenset = frozenset({
    "error-solutions", "skills-patterns", "best-practices", "codebase-context",
    "knowledge", "interaction-history", "agent-memory-episodic", "agent-memory-semantic",
    "agent-memory-procedural", "learning-feedback", "trading-patterns", "mlops-patterns",
    "qa-patterns", "osint-intelligence",
})


async def query_aidb_handler(query: str, collection: str = "error-solutions", limit: int = 5) -> Dict:
    """Search harness pattern collections. Default 'error-solutions' has 66 seeded fix patterns.

    Routes to Qdrant-direct (embed via llama-embed:8081 + search Qdrant:6333) for all
    harness-seeded collections. AIDB pgvector (port 8002) is a separate document store
    with different content — not used for harness pattern queries.
    """
    if collection in _QDRANT_COLLECTIONS:
        return await _query_qdrant_direct(query, collection, limit)
    # Non-harness collections: try AIDB pgvector
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{AIDB_URL}/vector/search",
                json={"query": query, "collection": collection, "limit": limit},
            )
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_working_memory_handler() -> Dict:
    """Proxy for recall_agent_memory (get_working_memory)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/memory/recall", json={"query": "working memory summary", "memory_types": ["semantic"]})
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def mesh_discovery_handler() -> Dict:
    """Get active agents, teams, and capabilities from the mesh."""
    try:
        from collective_memory import CollectiveMemory
        mem = CollectiveMemory()
        active_teams = mem.get_active_teams()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{HYBRID_COORDINATOR_URL}/discovery/capabilities")
            capabilities = resp.json() if resp.status_code == 200 else {}
            
        return {
            "success": True,
            "active_teams": active_teams,
            "team_count": len(active_teams),
            "capabilities": capabilities.get("capabilities", []),
            "redis_connected": mem.is_redis_connected(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def collective_memory_search_handler(query: str, limit: int = 5) -> Dict:
    """Search historical collaboration records in the collective memory (Qdrant).

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "for term in 'tool-call grammar' 'context supply' 'intervention' 'write_region' 'artifact' 'record/replay'; do lean-ctx -c \"git log --all --format='%H %s' -10 --regexp-ignore-case --grep='"'$term'"'\"; done" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 3740ms:
3cff973b01d96d0e515ebd690a8396ff86204a87 feat(p1,p2): integrate codex's GBNF repair-retry (P2.3) + training-loop reactivation (P1.5)
950f56e4deecba5d42d986b240f306eb30e03ad2 feat(local-agent): LLM record/replay harness — deterministic offline validation
47e03ea9891fcfac63de090328ac11555ffd4546 feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis
2f89cf32f893e75828c69b75ea61493c5db6972c docs(foundation-c): C6 reconciliation — both pre-freeze blockers RESOLVED, C6 unblocked
aabd707309e415917e4b7fca8130d3d075e79e29 docs(foundation-c): C4 activation-readiness reconciliation — C6 is the gating blocker
97b5b05620da6aeb3a8a00e7b9fe297939473b86 docs(foundation-c): R7 provisioning design — trusted-repo mirror + durable reservation (GREEN round-trip)
817b3112e598ff636df0cd36c58f3ec103f0330d docs(foundation-c): consolidated activation-ready batch packet for Aug-4 codex return
0ad2b5211e5da00ed9ceb9bca60fde38a43b9bcc feat(loop): HITL approve/reject-repair-pair gate — dataset poison guard
303e3a374c5eca0eea9bd7edee3bf96a3aa161b3 feat(observability): health-spider probe for the closed local-improvement loop
e7998f3079cf6dfcbcc3ac893e86ab5dbaaf2a73 docs(prd): Slice 2/3 PRD from ratified consensus; close Slice 1b
418f409056650b15371e54e765e374ac48617b46 feat(ops): polling control channel — operator injects responses into a live agent
47e03ea9891fcfac63de090328ac11555ffd4546 feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis
4650b1e656c5305fa1ec6a842158d9488fc671aa chore: gitignore LLM cassette run-artifacts dir
950f56e4deecba5d42d986b240f306eb30e03ad2 feat(local-agent): LLM record/replay harness — deterministic offline validation
ae9029ef4a96beb69cb1dd879ac271acd165992b fix(local-agent): strip tool-call JSON-envelope artifact from run_command args
7f00d1b2afbff98f273ec9d653ff9af859357f83 docs(research)+chore: harness parity research + worklog + gitignore churn
3d45e03ccea880ee22ab6022cdd730f98b0513d1 fix(foundation-c): repair ALA to C2 signed lease contract
5f12ad5c179f65570d4a620a988eaa35c55df87f feat(governance): Rule 20 PROGRESS-PROJECTED + MINIMAL-CODE + tier0 check-pm-tracker gate (agent parity)
600a9eb6f6d3ffd52c3f72534946cb0ac759a984 docs(foundation-c): C2 B2 + B2.5 independent reviews — PASS, durable ledger validated
f6188cd1ffe481c905376672ea23e82e2f8490ed chore(collab): archive foundation-c-rev2-depth task and add review artifact
6a3952dc69142276a5ab44d5df3e2aa6d6946b3c chore(collab): complete stream-auth-rereview and collect pending round manifests
e7bf91deb4693a6667cd3c3ed10b0988b4143ef6 docs(foundation-c): record antigravity advisory PASS on C5/C6/C3a-2 (not gate-clearing)
950f56e4deecba5d42d986b240f306eb30e03ad2 feat(local-agent): LLM record/replay harness — deterministic offline validation
47e03ea9891fcfac63de090328ac11555ffd4546 feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "sed -n '1,230p' ai-stack/local-agents/builtin_tools/file_operations.py
sed -n '230,470p' ai-stack/local-agents/builtin_tools/file_operations.py
sed -n '1,380p' scripts/testing/test-write-region.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 50ms:
#!/usr/bin/env python3
"""
Built-in File Operation Tools for Local Agents

Provides safe file operation tools with sandboxing and validation:
- read_file: Read file contents
- write_file: Write file contents
- list_files: Glob file search
- search_files: Content search (grep)
- file_exists: Check file existence

All tools follow safety policies and include audit logging.

Part of Phase 11 Batch 11.1: Tool Calling Infrastructure
"""

import asyncio
import glob
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)


# File path validation
ALLOWED_BASE_PATHS = [
    Path.home() / ".local/share/nixos-ai-stack",
    Path.home() / "Documents",
    Path("/tmp"),
]

FORBIDDEN_PATHS = [
    Path.home() / ".ssh",
    Path.home() / ".gnupg",
    Path("/etc/shadow"),
    Path("/etc/passwd"),
]


def validate_file_path(file_path: str, allow_write: bool = False) -> tuple[bool, str]:
    """
    Validate file path for safety.

    Args:
        file_path: Path to validate
        allow_write: Whether write access is needed

    Returns:
        (is_valid, reason)
    """
    try:
        path = Path(file_path).resolve()
    except Exception as e:
        return False, f"Invalid path: {e}"

    # Check forbidden paths
    for forbidden in FORBIDDEN_PATHS:
        if path == forbidden or forbidden in path.parents:
            return False, f"Access to {forbidden} is forbidden"

    # Check allowed base paths
    if allow_write:
        allowed = False
        for base in ALLOWED_BASE_PATHS:
            if path == base or base in path.parents:
                allowed = True
                break

        if not allowed:
            return False, f"Write access not allowed outside: {', '.join(str(p) for p in ALLOWED_BASE_PATHS)}"

    return True, "OK"


# Tool handlers

async def read_file_handler(
    file_path: str,
    max_size_kb: int = 1024,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> Dict:
    """
    Read contents of a file with optional line-range chunking.

    Args:
        file_path: Absolute path to file
        max_size_kb: Maximum file size in KB (default: 1MB)
        start_line: 1-based start line (optional)
        end_line: 1-based end line (optional)

    Returns:
        {
            "success": bool,
            "content": str (if success),
            "error": str (if failed),
            "metadata": {size_bytes, lines, start_line, end_line}
        }
    """
    # Validate path
    is_valid, reason = validate_file_path(file_path, allow_write=False)
    if not is_valid:
        return {"success": False, "error": f"Path validation failed: {reason}"}

    path = Path(file_path)

    # Check file exists
    if not path.exists():
        return {"success": False, "error": f"File does not exist: {file_path}"}

    if not path.is_file():
        return {"success": False, "error": f"Path is not a file: {file_path}"}

    # Check file size (only if reading the whole file)
    size_bytes = path.stat().st_size
    if start_line is None and end_line is None:
        if size_bytes > max_size_kb * 1024:
            return {
                "success": False,
                "error": f"File too large: {size_bytes / 1024:.1f}KB > {max_size_kb}KB. Use start_line/end_line for chunking.",
            }

    # Read file
    try:
        if start_line is not None or end_line is not None:
            # Chunked read
            lines_content = []
            s = (start_line or 1) - 1
            e = end_line or 1000000 # default to "rest of file"
            
            with path.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= s and i < e:
                        lines_content.append(line)
                    if i >= e:
                        break
            
            content = "".join(lines_content)
            actual_lines = len(lines_content)
        else:
            # Full read
            content = path.read_text(encoding="utf-8")
            actual_lines = content.count("\n") + 1

        return {
            "success": True,
            "content": content,
            "metadata": {
                "size_bytes": size_bytes,
                "lines": actual_lines,
                "path": str(path),
                "start_line": start_line,
                "end_line": end_line,
            },
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to read file: {e}"}


async def write_file_handler(
    file_path: str,
    content: str,
    mode: str = "w",
    create_dirs: bool = True,
) -> Dict:
    """
    Write contents to a file.

    Args:
        file_path: Absolute path to file
        content: Content to write
        mode: Write mode ('w' or 'a')
        create_dirs: Create parent directories if needed

    Returns:
        {
            "success": bool,
            "bytes_written": int,
            "error": str (if failed)
        }
    """
    # Validate path (write access)
    is_valid, reason = validate_file_path(file_path, allow_write=True)
    if not is_valid:
        return {"success": False, "error": f"Path validation failed: {reason}"}

    if mode not in ("w", "a"):
        return {"success": False, "error": f"Invalid mode: {mode} (must be 'w' or 'a')"}

    path = Path(file_path)

    # Create parent directories if needed
    if create_dirs:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"success": False, "error": f"Failed to create directories: {e}"}

    # Write file
    import hashlib as _hashlib
    try:
        encoded = content.encode("utf-8")
        if mode == "w":
            path.write_bytes(encoded)
        else:  # append
            with path.open("ab") as f:
                f.write(encoded)

        sha256 = _hashlib.sha256(encoded).hexdigest()[:16]

        return {
            "success": True,
            "bytes_written": len(encoded),
            "sha256_prefix": sha256,  # audit trail: non-repudiation without re-reading
            "path": str(path),
        }


    except Exception as e:
        return {"success": False, "error": f"Failed to write file: {e}"}


async def list_files_handler(
    pattern: str,
    recursive: bool = True,
    max_results: int = 1000,
) -> Dict:
    """
    List files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "*.py", "**/*.md")
        recursive: Enable recursive search
        max_results: Maximum results to return

    Returns:
        {
            "success": bool,
            "files": [str],  # List of matching file paths
            "count": int,
            "truncated": bool
        }
    """
    try:
        # Use glob
        if recursive and "**" not in pattern:
            pattern = f"**/{pattern}"

        matches = glob.glob(pattern, recursive=recursive)

        # Filter out forbidden paths
        safe_matches = []
        for match in matches:
            is_valid, _ = validate_file_path(match, allow_write=False)
            if is_valid:
                safe_matches.append(match)

        # Sort and limit
        safe_matches.sort()
        truncated = len(safe_matches) > max_results
        safe_matches = safe_matches[:max_results]

        return {
            "success": True,
            "files": safe_matches,
            "count": len(safe_matches),
            "truncated": truncated,
        }

    except Exception as e:
        return {"success": False, "error": f"Glob failed: {e}"}


async def search_files_handler(
    pattern: str,
    path: str = ".",
    file_pattern: Optional[str] = None,
    max_results: int = 100,
) -> Dict:
    """
    Search file contents for a pattern (grep).

    Args:
        pattern: Regular expression pattern to search
        path: Directory to search in
        file_pattern: Optional file glob pattern (e.g., "*.py")
        max_results: Maximum results to return

    Returns:
        {
            "success": bool,
            "matches": [
                {"file": str, "line": int, "text": str}
            ],
            "count": int,
            "truncated": bool
        }
    """
    # Validate path
    is_valid, reason = validate_file_path(path, allow_write=False)
    if not is_valid:
        return {"success": False, "error": f"Path validation failed: {reason}"}

    try:
        # Build grep command
        cmd = ["grep", "-rn", pattern, path]

        if file_pattern:
            cmd.extend(["--include", file_pattern])

        # Run grep
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,  # 10 second timeout
        )

        # Parse results
        matches = []
        for line in result.stdout.splitlines():
            # Format: file:line:text
            parts = line.split(":", 2)
            if len(parts) >= 3:
                matches.append({
                    "file": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else 0,
                    "text": parts[2],
                })

        # Limit results
        truncated = len(matches) > max_results
        matches = matches[:max_results]

        return {
            "success": True,
            "matches": matches,
            "count": len(matches),
            "truncated": truncated,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Search timed out (>10s)"}
    except Exception as e:
        return {"success": False, "error": f"Search failed: {e}"}


async def file_exists_handler(file_path: str) -> Dict:
    """
    Check if a file exists.

    Args:
        file_path: Path to check

    Returns:
        {
            "exists": bool,
            "is_file": bool,
            "is_dir": bool,
            "size_bytes": int (if file exists)
        }
    """
    path = Path(file_path)

    exists = path.exists()
    is_file = path.is_file() if exists else False
    is_dir = path.is_dir() if exists else False

    result = {
        "exists": exists,
        "is_file": is_file,
        "is_dir": is_dir,
    }

    if is_file:
        try:
            result["size_bytes"] = path.stat().st_size
        except:
            pass

    return result


async def edit_file_handler(file_path: str, old_string: str, new_string: str) -> Dict:
    """
    Surgically replace old_string with new_string in a file (first occurrence).

    Preferred over write_file for targeted changes — the model only needs to supply
    the strings to change, not regenerate the entire file.  Fails with a clear error
    if old_string is not found so the model can self-correct.

    Args:
        file_path:   Relative or absolute path to the file to edit.
        old_string:  Exact text to replace (must be unique enough to identify the site).
        new_string:  Replacement text.

    Returns:
        {"success": True, "replacements": 1}          on success
        {"success": False, "error": "<reason>"}        on failure
    """
    try:
        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        content = path.read_text(encoding="utf-8")
        if old_string not in content:
            # Provide a snippet of the file to help the model self-correct its old_string
            snippet = content[:400] + ("..." if len(content) > 400 else "")
            return {
                "success": False,
                "error": f"old_string not found in {file_path}. File starts with:\n{snippet}",
            }
        new_content = content.replace(old_string, new_string, 1)
        path.write_text(new_content, encoding="utf-8")
        return {"success": True, "replacements": 1}
    except OSError as exc:
        return {"success": False, "error": str(exc)}


# AQ_WRITE_REGION: kill switch for the write_region tool (default ON). Set to "0"/"false"
# to hide the tool from the registry entirely — falls back to edit_file/write_file only.
def _write_region_enabled() -> bool:
    return os.environ.get("AQ_WRITE_REGION", "1").strip().lower() not in ("0", "false", "no", "off")


async def write_region_handler(
    file_path: str,
    start_line: int,
    end_line: int,
    new_text: str,
) -> Dict:
    """
    Replace lines [start_line, end_line] (1-indexed, inclusive) of file_path with new_text.
    No old_string matching — deterministic line-range rewrite.

    Research motivation (Aider per-model edit-format data): search/replace (edit_file's
    old_string) is the HARDEST edit format for weak/quantized models — they cannot
    reliably reproduce a byte-exact anchor, so they churn on 'old_string not found'.
    Aider defaults local/weak models to whole-unit rewrite instead. We front-load code
    to local WITH line-number citations (e.g. '[file:271-290]'), so a line-range rewrite
    needs no matching at all — just the line numbers already shown.

    Args:
        file_path:   Relative or absolute path to the file to edit.
        start_line:  1-indexed first line to replace (inclusive).
        end_line:    1-indexed last line to replace (inclusive). May equal
                     len(lines)+1 (with start_line == end_line) to insert at EOF
                     without replacing anything.
        new_text:    Replacement text for the region (may be multi-line).

    Returns:
        {"success": True, "start_line": int, "end_line": int, "lines_written": int}
        {"success": False, "error": "<reason>", "current_line_count": int, "region": "<current text at/near the target>"}
    """
    try:
        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
#!/usr/bin/env python3
"""
Regression test for the write_region line-range rewrite tool (2026-08-20).

Root cause this addresses (see .agent/PROMOTED-BUG-PATTERNS.md / Aider's
per-model edit-format research): the local (Qwen) agent's #1 remaining edit
failure is `edit_file` old_string MISMATCH — search/replace requires a
byte-exact old_string, and weak/quantized models cannot reliably reproduce
one from a partial view of a file, so they churn on 'old_string not found'.
Aider's published per-model data is why it DEFAULTS weak/local models to
"whole"-format edits (rewrite the unit, no matching) rather than
search/replace. We already front-load code to local WITH line-number
citations (e.g. '[file:271-290]'), so a line-range rewrite needs NO
old_string at all — just the line numbers already shown.

Fix under test: `write_region(file_path, start_line, end_line, new_text)`
(ai-stack/local-agents/builtin_tools/file_operations.py) replaces lines
[start_line, end_line] (1-indexed, inclusive) with new_text — no fuzzy
matching, deterministic. Registered in the tool registry exactly like
edit_file/write_file (so it reaches the model-visible tool schema AND the
GBNF grammar's function enum, which derives from the registry's enabled
tools — see agent_executor.py `_tool_call_grammar`). Gated behind
AQ_WRITE_REGION (default "1"; "0" hides the tool entirely). A successful
call counts toward `_edits_made` (the no-action guard) exactly like
edit_file/write_file.

Coverage:
  (a) a valid line-range replace produces the exact expected file content
  (b) out-of-range start/end returns a clear error with the current line
      count — no crash, no partial write (file left byte-identical)
  (c) inserting at EOF (start_line == end_line == line_count + 1) works
  (d) a successful write_region call counts as an edit for the no-action
      guard — driven through the REAL `_execute_with_tools` loop
  (e) AQ_WRITE_REGION=0 hides the tool from the registry (and therefore
      from the model-visible schema + GBNF enum, which both derive from
      registry.tools)
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
LOCAL_AGENTS = ROOT / "ai-stack" / "local-agents"
BUILTINS = LOCAL_AGENTS / "builtin_tools"
sys.path.insert(0, str(LOCAL_AGENTS))
sys.path.insert(0, str(BUILTINS))

from tool_registry import ToolRegistry  # noqa: E402
import file_operations  # noqa: E402

spec = importlib.util.spec_from_file_location("agent_executor", LOCAL_AGENTS / "agent_executor.py")
ae = importlib.util.module_from_spec(spec)
sys.modules.setdefault("httpx", MagicMock())
spec.loader.exec_module(ae)

AgentExecutor = ae.LocalAgentExecutor
AgentType = ae.AgentType
Task = ae.Task
TaskStatus = ae.TaskStatus
ToolCall = ae.ToolCall if hasattr(ae, "ToolCall") else None
if ToolCall is None:
    import tool_registry as _tr
    ToolCall = _tr.ToolCall

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}")
        FAIL += 1


ORIGINAL_CONTENT = (
    "line one\n"
    "line two\n"
    "line three\n"
    "line four\n"
    "line five\n"
)


def make_target_file(tmp_dir: Path) -> Path:
    p = tmp_dir / "target.txt"
    p.write_text(ORIGINAL_CONTENT, encoding="utf-8")
    return p


async def test_valid_replace_produces_exact_content():
    """(a) a valid line-range replace produces the exact expected file content."""
    with tempfile.TemporaryDirectory() as td:
        p = make_target_file(Path(td))
        result = await file_operations.write_region_handler(
            file_path=str(p),
            start_line=2,
            end_line=3,
            new_text="line two REPLACED\nline three REPLACED\n",
        )
        check("valid replace reports success", result.get("success") is True)
        check("valid replace reports correct start_line", result.get("start_line") == 2)
        check("valid replace reports correct end_line", result.get("end_line") == 3)

        expected = (
            "line one\n"
            "line two REPLACED\n"
            "line three REPLACED\n"
            "line four\n"
            "line five\n"
        )
        actual = p.read_text(encoding="utf-8")
        check("file content matches exactly after replace", actual == expected)


async def test_single_line_replace():
    """A single-line region (start_line == end_line) replaces just that line."""
    with tempfile.TemporaryDirectory() as td:
        p = make_target_file(Path(td))
        result = await file_operations.write_region_handler(
            file_path=str(p), start_line=1, end_line=1, new_text="ONLY LINE ONE CHANGED\n",
        )
        check("single-line replace succeeds", result.get("success") is True)
        expected = "ONLY LINE ONE CHANGED\n" + "".join(ORIGINAL_CONTENT.splitlines(keepends=True)[1:])
        check("single-line replace content exact", p.read_text(encoding="utf-8") == expected)


async def test_out_of_range_returns_error_no_crash_no_partial_write():
    """(b) out-of-range start/end returns an error with the current line count
    (no crash, no partial write — file left byte-identical)."""
    with tempfile.TemporaryDirectory() as td:
        p = make_target_file(Path(td))
        before = p.read_text(encoding="utf-8")

        # end_line way past EOF
        result = await file_operations.write_region_handler(
            file_path=str(p), start_line=2, end_line=999, new_text="X\n",
        )
        check("out-of-range end_line reports failure", result.get("success") is False)
        check("out-of-range error includes current_line_count", result.get("current_line_count") == 5)
        check("out-of-range error message is descriptive", "5 lines" in result.get("error", ""))
        check("out-of-range: file unchanged (no partial write)", p.read_text(encoding="utf-8") == before)

        # start_line < 1
        result2 = await file_operations.write_region_handler(
            file_path=str(p), start_line=0, end_line=1, new_text="X\n",
        )
        check("start_line < 1 reports failure", result2.get("success") is False)
        check("start_line < 1: file unchanged", p.read_text(encoding="utf-8") == before)

        # start_line > end_line
        result3 = await file_operations.write_region_handler(
            file_path=str(p), start_line=3, end_line=2, new_text="X\n",
        )
        check("start_line > end_line reports failure", result3.get("success") is False)
        check("start_line > end_line: file unchanged", p.read_text(encoding="utf-8") == before)

        # missing file — no crash
        result4 = await file_operations.write_region_handler(
            file_path=str(Path(td) / "does-not-exist.txt"), start_line=1, end_line=1, new_text="X\n",
        )
        check("missing file reports failure (no crash)", result4.get("success") is False)
        check("missing file error is descriptive", "not found" in result4.get("error", "").lower())


async def test_insert_at_eof():
    """(c) inserting at EOF (start_line == end_line == line_count + 1) works."""
    with tempfile.TemporaryDirectory() as td:
        p = make_target_file(Path(td))
        result = await file_operations.write_region_handler(
            file_path=str(p), start_line=6, end_line=6, new_text="line six APPENDED\n",
        )
        check("EOF insert reports success", result.get("success") is True)
        expected = ORIGINAL_CONTENT + "line six APPENDED\n"
        check("EOF insert appends without disturbing existing lines", p.read_text(encoding="utf-8") == expected)


def make_executor() -> AgentExecutor:
    ex = AgentExecutor.__new__(AgentExecutor)
    ex.llama_endpoint = "http://localhost:8080"
    ex.enable_fallback = False
    ex.allow_degraded_local_execution = True
    ex.fallback_endpoint = None
    ex.remote_probe_timeout_seconds = 5
    ex._prompt_extensions_cache = None

    reg = MagicMock()
    reg.get_tools_for_model.return_value = [
        {"name": "write_region", "description": "line-range rewrite"},
    ]
    reg.tools = {}

    def _fake_format(tool_call) -> str:
        import json as _json
        return _json.dumps({"tool": tool_call.tool_name, "status": "success", "result": tool_call.result})

    reg.format_tool_result.side_effect = _fake_format
    ex.tool_registry = reg
    ex.performance = {at: MagicMock() for at in AgentType}
    return ex


async def test_counts_as_edit_for_noaction_guard():
    """(d) a successful write_region call counts toward `_edits_made`, so a
    prose-only completion AFTER it does NOT trigger the no-action
    intervention (mirrors test-noaction-intervention.py's pattern for
    edit_file/write_file)."""
    with tempfile.TemporaryDirectory() as td:
        target_path = str(make_target_file(Path(td)))
        ex = make_executor()
        task = Task(id="t-write-region-noaction", objective="rewrite lines 2-3", status=TaskStatus.RUNNING)

        _call_seq = {"n": 0}

        def _fake_parse(_response: str):
            _call_seq["n"] += 1
            if _call_seq["n"] == 1:
                return ToolCall(
                    id="call-1", tool_name="write_region",
                    arguments={
                        "file_path": target_path,
                        "start_line": 2,
                        "end_line": 3,
                        "new_text": "REPLACED TWO\nREPLACED THREE\n",
                    },
                )
            return None  # turn 2: prose-only completion, no tool call

        async def _fake_execute(tool_call):
            tool_call.status = "completed"
            result = await file_operations.write_region_handler(**tool_call.arguments)
            tool_call.result = result
            return tool_call

        call_log = []

        async def _fake_call_llama(messages, **kwargs):
            call_log.append(list(messages))
            n = _call_seq["n"] + 1
            if n <= 1:
                return (
                    f'{{"function": "write_region", "arguments": '
                    f'{{"file_path": "{target_path}", "start_line": 2, "end_line": 3, '
                    f'"new_text": "REPLACED TWO\\nREPLACED THREE\\n"}}}}',
                    10,
                )
            return "COMPLETED: rewrote lines 2-3 with write_region.", 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=_fake_execute)
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        noaction_msgs = [
            m for m in (call_log[-1] if call_log else [])
            if m.get("role") == "user" and "Call edit_file NOW" in (m.get("content") or "")
        ]
        check(
            "no-action intervention NOT injected after a successful write_region "
            "(it already counted as an edit)",
            len(noaction_msgs) == 0,
        )
        check(
            "task completes normally (no stagnation/abort)",
            "Aborting" not in final_msg and "stagnation" not in final_msg.lower(),
        )
        check("completion reflects the write_region fix", "COMPLETED" in final_msg)

        actual = Path(target_path).read_text(encoding="utf-8")
        check(
            "the write_region edit actually landed on disk",
            "REPLACED TWO" in actual and "REPLACED THREE" in actual,
        )


def test_env_flag_hides_tool():
    """(e) AQ_WRITE_REGION=0 hides the tool from the registry entirely — and
    therefore from get_tools_for_model()'s output, which is the same source
    the GBNF grammar enum (agent_executor._tool_call_grammar) derives from."""
    with patch.dict(os.environ, {"AQ_WRITE_REGION": "0"}):
        registry_off = ToolRegistry(db_path=Path(tempfile.mktemp(suffix=".db")))
        file_operations.register_file_tools(registry_off)
        check("AQ_WRITE_REGION=0: write_region absent from registry.tools",
              "write_region" not in registry_off.tools)
        model_tool_names_off = {t["name"] for t in registry_off.get_tools_for_model()}
        check("AQ_WRITE_REGION=0: write_region absent from model-visible schema",
              "write_region" not in model_tool_names_off)

    with patch.dict(os.environ, {"AQ_WRITE_REGION": "1"}):
        registry_on = ToolRegistry(db_path=Path(tempfile.mktemp(suffix=".db")))
        file_operations.register_file_tools(registry_on)
        check("AQ_WRITE_REGION=1: write_region present in registry.tools",
              "write_region" in registry_on.tools)
        model_tool_names_on = {t["name"] for t in registry_on.get_tools_for_model()}
        check("AQ_WRITE_REGION=1: write_region present in model-visible schema",
              "write_region" in model_tool_names_on)

    # Default (env var unset) is ON.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AQ_WRITE_REGION", None)
        registry_default = ToolRegistry(db_path=Path(tempfile.mktemp(suffix=".db")))
        file_operations.register_file_tools(registry_default)
        check("AQ_WRITE_REGION unset: defaults to ON",
              "write_region" in registry_default.tools)


async def main():
    await test_valid_replace_produces_exact_content()
    await test_single_line_replace()
    await test_out_of_range_returns_error_no_crash_no_partial_write()
    await test_insert_at_eof()
    await test_counts_as_edit_for_noaction_guard()
    test_env_flag_hides_tool()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "nl -ba ai-stack/local-agents/builtin_tools/file_operations.py | sed -n '320,445p'
nl -ba ai-stack/local-agents/builtin_tools/file_operations.py | sed -n '445,600p'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 57ms:
   320	        if file_pattern:
   321	            cmd.extend(["--include", file_pattern])
   322	
   323	        # Run grep
   324	        result = subprocess.run(
   325	            cmd,
   326	            capture_output=True,
   327	            text=True,
   328	            timeout=10,  # 10 second timeout
   329	        )
   330	
   331	        # Parse results
   332	        matches = []
   333	        for line in result.stdout.splitlines():
   334	            # Format: file:line:text
   335	            parts = line.split(":", 2)
   336	            if len(parts) >= 3:
   337	                matches.append({
   338	                    "file": parts[0],
   339	                    "line": int(parts[1]) if parts[1].isdigit() else 0,
   340	                    "text": parts[2],
   341	                })
   342	
   343	        # Limit results
   344	        truncated = len(matches) > max_results
   345	        matches = matches[:max_results]
   346	
   347	        return {
   348	            "success": True,
   349	            "matches": matches,
   350	            "count": len(matches),
   351	            "truncated": truncated,
   352	        }
   353	
   354	    except subprocess.TimeoutExpired:
   355	        return {"success": False, "error": "Search timed out (>10s)"}
   356	    except Exception as e:
   357	        return {"success": False, "error": f"Search failed: {e}"}
   358	
   359	
   360	async def file_exists_handler(file_path: str) -> Dict:
   361	    """
   362	    Check if a file exists.
   363	
   364	    Args:
   365	        file_path: Path to check
   366	
   367	    Returns:
   368	        {
   369	            "exists": bool,
   370	            "is_file": bool,
   371	            "is_dir": bool,
   372	            "size_bytes": int (if file exists)
   373	        }
   374	    """
   375	    path = Path(file_path)
   376	
   377	    exists = path.exists()
   378	    is_file = path.is_file() if exists else False
   379	    is_dir = path.is_dir() if exists else False
   380	
   381	    result = {
   382	        "exists": exists,
   383	        "is_file": is_file,
   384	        "is_dir": is_dir,
   385	    }
   386	
   387	    if is_file:
   388	        try:
   389	            result["size_bytes"] = path.stat().st_size
   390	        except:
   391	            pass
   392	
   393	    return result
   394	
   395	
   396	async def edit_file_handler(file_path: str, old_string: str, new_string: str) -> Dict:
   397	    """
   398	    Surgically replace old_string with new_string in a file (first occurrence).
   399	
   400	    Preferred over write_file for targeted changes — the model only needs to supply
   401	    the strings to change, not regenerate the entire file.  Fails with a clear error
   402	    if old_string is not found so the model can self-correct.
   403	
   404	    Args:
   405	        file_path:   Relative or absolute path to the file to edit.
   406	        old_string:  Exact text to replace (must be unique enough to identify the site).
   407	        new_string:  Replacement text.
   408	
   409	    Returns:
   410	        {"success": True, "replacements": 1}          on success
   411	        {"success": False, "error": "<reason>"}        on failure
   412	    """
   413	    try:
   414	        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
   415	        if not path.exists():
   416	            return {"success": False, "error": f"File not found: {file_path}"}
   417	        content = path.read_text(encoding="utf-8")
   418	        if old_string not in content:
   419	            # Provide a snippet of the file to help the model self-correct its old_string
   420	            snippet = content[:400] + ("..." if len(content) > 400 else "")
   421	            return {
   422	                "success": False,
   423	                "error": f"old_string not found in {file_path}. File starts with:\n{snippet}",
   424	            }
   425	        new_content = content.replace(old_string, new_string, 1)
   426	        path.write_text(new_content, encoding="utf-8")
   427	        return {"success": True, "replacements": 1}
   428	    except OSError as exc:
   429	        return {"success": False, "error": str(exc)}
   430	
   431	
   432	# AQ_WRITE_REGION: kill switch for the write_region tool (default ON). Set to "0"/"false"
   433	# to hide the tool from the registry entirely — falls back to edit_file/write_file only.
   434	def _write_region_enabled() -> bool:
   435	    return os.environ.get("AQ_WRITE_REGION", "1").strip().lower() not in ("0", "false", "no", "off")
   436	
   437	
   438	async def write_region_handler(
   439	    file_path: str,
   440	    start_line: int,
   441	    end_line: int,
   442	    new_text: str,
   443	) -> Dict:
   444	    """
   445	    Replace lines [start_line, end_line] (1-indexed, inclusive) of file_path with new_text.
   445	    Replace lines [start_line, end_line] (1-indexed, inclusive) of file_path with new_text.
   446	    No old_string matching — deterministic line-range rewrite.
   447	
   448	    Research motivation (Aider per-model edit-format data): search/replace (edit_file's
   449	    old_string) is the HARDEST edit format for weak/quantized models — they cannot
   450	    reliably reproduce a byte-exact anchor, so they churn on 'old_string not found'.
   451	    Aider defaults local/weak models to whole-unit rewrite instead. We front-load code
   452	    to local WITH line-number citations (e.g. '[file:271-290]'), so a line-range rewrite
   453	    needs no matching at all — just the line numbers already shown.
   454	
   455	    Args:
   456	        file_path:   Relative or absolute path to the file to edit.
   457	        start_line:  1-indexed first line to replace (inclusive).
   458	        end_line:    1-indexed last line to replace (inclusive). May equal
   459	                     len(lines)+1 (with start_line == end_line) to insert at EOF
   460	                     without replacing anything.
   461	        new_text:    Replacement text for the region (may be multi-line).
   462	
   463	    Returns:
   464	        {"success": True, "start_line": int, "end_line": int, "lines_written": int}
   465	        {"success": False, "error": "<reason>", "current_line_count": int, "region": "<current text at/near the target>"}
   466	    """
   467	    try:
   468	        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
   469	        if not path.exists():
   470	            return {"success": False, "error": f"File not found: {file_path}"}
   471	        if not path.is_file():
   472	            return {"success": False, "error": f"Path is not a file: {file_path}"}
   473	
   474	        content = path.read_text(encoding="utf-8")
   475	        lines = content.splitlines(keepends=True)
   476	        line_count = len(lines)
   477	        max_bound = line_count + 1  # +1 slot allows a pure EOF insert
   478	
   479	        try:
   480	            start_line = int(start_line)
   481	            end_line = int(end_line)
   482	        except (TypeError, ValueError):
   483	            return {
   484	                "success": False,
   485	                "error": f"start_line/end_line must be integers (got {start_line!r}, {end_line!r})",
   486	                "current_line_count": line_count,
   487	            }
   488	
   489	        if not (1 <= start_line <= end_line <= max_bound):
   490	            clamp_start = max(1, min(start_line, max(line_count, 1)))
   491	            clamp_end = max(1, min(end_line, max(line_count, 1)))
   492	            region_text = "".join(lines[clamp_start - 1:clamp_end]) if line_count else ""
   493	            return {
   494	                "success": False,
   495	                "error": (
   496	                    f"Out-of-range region [start_line={start_line}, end_line={end_line}] for "
   497	                    f"{file_path} — file currently has {line_count} lines. Valid range is "
   498	                    f"1 <= start_line <= end_line <= {max_bound} ({max_bound} = insert-at-EOF)."
   499	                ),
   500	                "current_line_count": line_count,
   501	                "region": region_text,
   502	            }
   503	
   504	        if new_text and not new_text.endswith("\n"):
   505	            new_text = new_text + "\n"
   506	        new_lines = new_text.splitlines(keepends=True) if new_text else []
   507	
   508	        spliced = lines[:start_line - 1] + new_lines + lines[end_line:]
   509	        path.write_text("".join(spliced), encoding="utf-8")
   510	
   511	        return {
   512	            "success": True,
   513	            "start_line": start_line,
   514	            "end_line": start_line + len(new_lines) - 1 if new_lines else start_line - 1,
   515	            "lines_written": len(new_lines),
   516	        }
   517	    except OSError as exc:
   518	        return {"success": False, "error": str(exc)}
   519	
   520	
   521	def register_file_tools(registry: ToolRegistry):
   522	    """Register all file operation tools in the registry"""
   523	
   524	    # read_file
   525	    registry.register(ToolDefinition(
   526	        name="read_file",
   527	        description="Read the contents of a file with optional line-range chunking.",
   528	        parameters={
   529	            "type": "object",
   530	            "properties": {
   531	                "file_path": {
   532	                    "type": "string",
   533	                    "description": "Absolute path to the file to read",
   534	                },
   535	                "max_size_kb": {
   536	                    "type": "integer",
   537	                    "description": "Maximum file size in KB (default: 1024)",
   538	                    "default": 1024,
   539	                },
   540	                "start_line": {
   541	                    "type": "integer",
   542	                    "description": "1-based start line (optional)",
   543	                },
   544	                "end_line": {
   545	                    "type": "integer",
   546	                    "description": "1-based end line (optional)",
   547	                },
   548	            },
   549	            "required": ["file_path"],
   550	        },
   551	        category=ToolCategory.FILE_OPS,
   552	        safety_policy=SafetyPolicy.READ_ONLY,
   553	        handler=read_file_handler,
   554	    ))
   555	
   556	    # write_file
   557	    registry.register(ToolDefinition(
   558	        name="write_file",
   559	        description="Write content to a file",
   560	        parameters={
   561	            "type": "object",
   562	            "properties": {
   563	                "file_path": {
   564	                    "type": "string",
   565	                    "description": "Absolute path to the file to write",
   566	                },
   567	                "content": {
   568	                    "type": "string",
   569	                    "description": "Content to write to the file",
   570	                },
   571	                "mode": {
   572	                    "type": "string",
   573	                    "description": "Write mode: 'w' (overwrite) or 'a' (append)",
   574	                    "enum": ["w", "a"],
   575	                    "default": "w",
   576	                },
   577	                "create_dirs": {
   578	                    "type": "boolean",
   579	                    "description": "Create parent directories if they don't exist",
   580	                    "default": True,
   581	                },
   582	            },
   583	            "required": ["file_path", "content"],
   584	        },
   585	        category=ToolCategory.FILE_OPS,
   586	        safety_policy=SafetyPolicy.WRITE_SAFE,
   587	        handler=write_file_handler,
   588	        requires_confirmation=False,  # Agent loop is autonomous; git review is the safety gate
   589	    ))
   590	
   591	    # list_files
   592	    registry.register(ToolDefinition(
   593	        name="list_files",
   594	        description="List files matching a glob pattern",
   595	        parameters={
   596	            "type": "object",
   597	            "properties": {
   598	                "pattern": {
   599	                    "type": "string",
   600	                    "description": "Glob pattern (e.g., '*.py', '**/*.md')",

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx -c 'python3 -m pytest -q scripts/testing/test-tool-call-grammar.py scripts/testing/test-llm-cassette.py scripts/testing/test-write-region.py'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "python3 - <<'PY'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0,'scripts/ai/lib'); sys.path.insert(0,'ai-stack/local-agents')
import grammar_cache, llm_cassette
spec=importlib.util.spec_from_file_location('grammar_tests', Path('scripts/testing/test-tool-call-grammar.py'))
t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
g=grammar_cache.default_json_schema_to_gbnf({'type':'object','properties':{'optional':{'type':'string'}},'required':[]}, 'review')
print('optional empty object accepted:', t.gbnf_matches(g, '{}'))
g2=grammar_cache.default_json_schema_to_gbnf({'type':'object','properties':{'s':{'type':'string'}},'required':['s']}, 'review')
candidate='{\"s\":\"line1\\nline2\"}'
print('bare-newline candidate json-valid:', end=' ')
import json
try: json.loads(candidate); print(True)
except json.JSONDecodeError: print(False)
print('bare-newline accepted by grammar:', t.gbnf_matches(g2,candidate))
p1={'messages':[{'role':'tool','name':'read_file','content':'ok'}], 'frequency_penalty':0.0, 'chat_template_kwargs':{'enable_thinking':False}, 'model':'A'}
p2={'messages':[{'role':'tool','name':'run_command','content':'ok'}], 'frequency_penalty':0.9, 'chat_template_kwargs':{'enable_thinking':True}, 'model':'B'}
print('distinct behavioral payload keys collide:', llm_cassette.request_key(p1)==llm_cassette.request_key(p2))
PY" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 exited 1 in 393ms:
Traceback (most recent call last):
  File "<stdin>", line 6, in <module>
  File "<frozen importlib._bootstrap_external>", line 1023, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/test-tool-call-grammar.py", line 43, in <module>
    @dataclass(frozen=True)
     ~~~~~~~~~^^^^^^^^^^^^^
  File "/nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/dataclasses.py", line 1295, in wrap
    return _process_class(cls, init, repr, eq, order, unsafe_hash,
                          frozen, match_args, kw_only, slots,
                          weakref_slot)
  File "/nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/dataclasses.py", line 997, in _process_class
    and _is_type(type, cls, dataclasses, dataclasses.KW_ONLY,
        ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                 _is_kw_only))):
                 ^^^^^^^^^^^^
  File "/nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/dataclasses.py", line 757, in _is_type
    ns = sys.modules.get(cls.__module__).__dict__
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute '__dict__'. Did you mean: '__dir__'?

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "python3 - <<'PY'
import importlib.util, sys, json
from pathlib import Path
sys.path.insert(0,'scripts/ai/lib'); sys.path.insert(0,'ai-stack/local-agents')
import grammar_cache, llm_cassette
spec=importlib.util.spec_from_file_location('grammar_tests_review', Path('scripts/testing/test-tool-call-grammar.py'))
t=importlib.util.module_from_spec(spec); sys.modules[spec.name]=t; spec.loader.exec_module(t)
g=grammar_cache.default_json_schema_to_gbnf({'type':'object','properties':{'optional':{'type':'string'}},'required':[]}, 'review')
print('optional empty object accepted:', t.gbnf_matches(g, '{}'))
g2=grammar_cache.default_json_schema_to_gbnf({'type':'object','properties':{'s':{'type':'string'}},'required':['s']}, 'review')
candidate='{\"s\":\"line1\\nline2\"}'
try: json.loads(candidate); valid=True
except json.JSONDecodeError: valid=False
print('bare-newline candidate json-valid:', valid)
print('bare-newline accepted by grammar:', t.gbnf_matches(g2,candidate))
p1={'messages':[{'role':'tool','name':'read_file','content':'ok'}], 'frequency_penalty':0.0, 'chat_template_kwargs':{'enable_thinking':False}, 'model':'A'}
p2={'messages':[{'role':'tool','name':'run_command','content':'ok'}], 'frequency_penalty':0.9, 'chat_template_kwargs':{'enable_thinking':True}, 'model':'B'}
print('distinct behavioral payload keys collide:', llm_cassette.request_key(p1)==llm_cassette.request_key(p2))
PY" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 420ms:
optional empty object accepted: False
bare-newline candidate json-valid: False
bare-newline accepted by grammar: True
distinct behavioral payload keys collide: True

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "python3 - <<'PY'
import importlib.util, sys
from pathlib import Path
sys.path.insert(0,'scripts/ai/lib')
import grammar_cache
spec=importlib.util.spec_from_file_location('gt', Path('scripts/testing/test-tool-call-grammar.py')); t=importlib.util.module_from_spec(spec); sys.modules[spec.name]=t; spec.loader.exec_module(t)
for schema,candidates in [
 ({'type':'array','items':{}}, ['[]','[\"x\"]','[1]','[true]','[null]','[\"x\",1]']),
 ({'type':'object','properties':{'x':{}},'required':['x']}, ['{\"x\":\"s\"}','{\"x\":1}','{\"x\":true}','{\"x\":null}'])]:
 g=grammar_cache.default_json_schema_to_gbnf(schema,'r')
 print(schema)
 for c in candidates: print(c,t.gbnf_matches(g,c))
PY" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 409ms:
{'type': 'array', 'items': {}}
[] True
["x"] True
[1] True
[true] True
[null] True
["x",1] False
{'type': 'object', 'properties': {'x': {}}, 'required': ['x']}
{"x":"s"} False
{"x":1} False
{"x":true} False
{"x":null} False

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "nl -ba scripts/ai/lib/grammar_cache.py | sed -n '80,190p'
nl -ba ai-stack/local-agents/builtin_tools/shell_tools.py | sed -n '55,165p;225,245p'
nl -ba ai-stack/local-agents/llm_cassette.py | sed -n '35,125p;135,240p;260,350p'
nl -ba ai-stack/local-agents/agent_executor.py | sed -n '900,930p;1270,1308p;1405,1420p;1510,1570p;1660,1720p;1938,2090p'
" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 60ms:
    80	def default_json_schema_to_gbnf(schema_json: Any, zero_trust_state: Any) -> str:
    81	    """Build a small deterministic GBNF grammar for common JSON schema types."""
    82	
    83	    schema = _parse_json_value(schema_json)
    84	    if not isinstance(schema, Mapping):
    85	        raise ValueError("schema_json must describe a JSON object schema")
    86	
    87	    root = _rule_for_schema(schema)
    88	    return "\n".join(
    89	        [
    90	            f"root ::= {root}",
    91	            'string ::= "\\"" ([^"\\\\] | "\\\\" (["\\\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\\""',
    92	            'number ::= "-"? ([0-9] | [1-9][0-9]*) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?',
    93	            'boolean ::= "true" | "false"',
    94	            'null ::= "null"',
    95	            "ws ::= [ \\t\\n\\r]*",
    96	            # Generic JSON object/array/value rules, used by _object_rule for schemas
    97	            # that declare `"type": "object"` with NO `properties` (free-form objects,
    98	            # e.g. a tool-call's `arguments` payload). These allow zero-or-more members
    99	            # of arbitrary JSON value type instead of forcing an empty "{}" body.
   100	            'member ::= string ws ":" ws value',
   101	            "value ::= string | number | boolean | null | object | array",
   102	            'object ::= "{" ws (member (ws "," ws member)*)? ws "}"',
   103	            'array ::= "[" ws (value (ws "," ws value)*)? ws "]"',
   104	        ]
   105	    )
   106	
   107	
   108	def _canonical_zt_digest(zero_trust_state: Any) -> str:
   109	    if isinstance(zero_trust_state, str):
   110	        digest = zero_trust_state.strip()
   111	        if not digest:
   112	            raise ValueError("zero_trust_state digest must not be empty")
   113	        return digest
   114	    return hashlib.sha256(_canonical_bytes(zero_trust_state)).hexdigest()
   115	
   116	
   117	def _canonical_bytes(value: Any) -> bytes:
   118	    parsed = _parse_json_value(value)
   119	    return json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")
   120	
   121	
   122	def _parse_json_value(value: Any) -> Any:
   123	    if isinstance(value, bytes | bytearray):
   124	        value = value.decode("utf-8")
   125	    if isinstance(value, str):
   126	        return json.loads(value)
   127	    return value
   128	
   129	
   130	def _rule_for_schema(schema: Mapping[str, Any]) -> str:
   131	    enum_values = schema.get("enum")
   132	    if isinstance(enum_values, list) and enum_values:
   133	        # Constrain to the exact enumerated literals (e.g. the leased tool-name set)
   134	        # instead of falling through to an unconstrained `string`/`number` rule.
   135	        # Parenthesized: GBNF `|` has lower precedence than sequencing, so an
   136	        # unparenthesized alternation embedded inline (e.g. inside _object_rule's
   137	        # "key" ws ":" ws <this> sequence) would leak across the whole enclosing
   138	        # rule instead of binding to just this property's value.
   139	        alternatives = " | ".join(_gbnf_literal(json.dumps(v, separators=(",", ":"))) for v in enum_values)
   140	        return f"({alternatives})"
   141	    schema_type = schema.get("type")
   142	    if schema_type == "object":
   143	        return _object_rule(schema)
   144	    if schema_type == "array":
   145	        item_rule = _rule_for_schema(_schema_mapping(schema.get("items", {})))
   146	        return f'"[" ws ({item_rule} (ws "," ws {item_rule})*)? ws "]"'
   147	    if schema_type == "string":
   148	        return "string"
   149	    if schema_type in {"integer", "number"}:
   150	        return "number"
   151	    if schema_type == "boolean":
   152	        return "boolean"
   153	    if schema_type == "null":
   154	        return "null"
   155	    return "string | number | boolean | null"
   156	
   157	
   158	def _object_rule(schema: Mapping[str, Any]) -> str:
   159	    properties = schema.get("properties", {})
   160	    if not isinstance(properties, Mapping) or not properties:
   161	        # Free-form object (schema is `{"type": "object"}` with no declared
   162	        # `properties`, e.g. a tool-call's `arguments` payload): allow zero-or-more
   163	        # arbitrary JSON members instead of forcing an empty "{}" body, which made
   164	        # every tool call emit useless empty arguments.
   165	        return "object"
   166	
   167	    parts: list[str] = []
   168	    for name in sorted(properties):
   169	        prop_schema = _schema_mapping(properties[name])
   170	        key_literal = _gbnf_literal(json.dumps(name, separators=(",", ":")))
   171	        parts.append(f'{key_literal} ws ":" ws {_rule_for_schema(prop_schema)}')
   172	    return '"{" ws ' + ' ws "," ws '.join(parts) + ' ws "}"'
   173	
   174	
   175	def _gbnf_literal(text: str) -> str:
   176	    """Return a GBNF double-quoted literal that generates `text` verbatim.
   177	
   178	    `text` is the exact raw output text desired (e.g. a JSON-encoded key/value
   179	    like `"function"`, quote characters included). Backslashes and double quotes
   180	    in `text` are backslash-escaped so they survive as literal characters inside
   181	    the GBNF string rather than terminating it early — the fix for the bug where
   182	    `json.dumps(name)[1:-1]` stripped the JSON quotes and produced an unquoted
   183	    GBNF literal (matching bare `arguments` instead of `"arguments"`).
   184	    """
   185	    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
   186	    return f'"{escaped}"'
   187	
   188	
   189	def _schema_mapping(value: Any) -> Mapping[str, Any]:
   190	    if isinstance(value, Mapping):
    55	    """
    56	
    57	    def __init__(self) -> None:
    58	        bin_path = os.environ.get("NSJAIL_BIN") or shutil.which("nsjail")
    59	        self.available: bool = bool(bin_path and os.path.isfile(bin_path))
    60	        self.bin: str = bin_path or ""
    61	        self.required: bool = os.environ.get("NSJAIL_REQUIRED", "0").strip().lower() in {"1", "true", "yes"}
    62	
    63	    def build_argv(self, command: str, timeout_seconds: int) -> list:
    64	        """Build nsjail argv wrapping the given shell command string."""
    65	        return [
    66	            self.bin,
    67	            "--mode", "once",
    68	            "--time_limit", str(timeout_seconds),
    69	            "--max_cpus", "1",
    70	            "--rlimit_nofile", "64",
    71	            "--disable_proc",
    72	            "--iface_no_lo",
    73	            "--bindmount_ro", "/nix/store",
    74	            "--bindmount_ro", "/run/current-system",
    75	            "--tmpfs", "/tmp:size=16m",
    76	            "--cwd", "/tmp",
    77	            "--",
    78	            "/run/current-system/sw/bin/sh", "-c", command,
    79	        ]
    80	
    81	
    82	_nsjail = NsjailSandbox()
    83	
    84	_SHELL_CONTROL_PATTERN = re.compile(r"(?:;|&&|\|\||`|\$\(|\$\{|\n|\r)")
    85	
    86	
    87	SAFE_COMMANDS = {
    88	    # System inspection (read-only)
    89	    "ls", "pwd", "echo", "cat", "head", "tail", "wc", "grep", "rg",
    90	    "find", "which", "whoami", "hostname", "date", "uptime",
    91	    "free", "df", "du", "ps", "top", "systemctl", "journalctl",
    92	    # Git (read-only ops)
    93	    "git",
    94	    # HTTP — coordinator/RAG/memory API calls (coordinator at :8003 only; :8002 blocked by safe_command_executor.py)
    95	    "curl",
    96	    # Code analysis / validation
    97	    "bash", "python3", "python", "nix-instantiate", "nix",
    98	    "shellcheck", "statix", "deadnix",
    99	    # Harness tools (full suite from LOCAL-AGENT.md)
   100	    "agrep", "als", "acat", "asum",
   101	    "aq-qa", "aq-hints", "aq-report", "aq-session-start",
   102	    "aq-commit-facts", "aq-lesson-promote", "aq-crystallize",
   103	    "aq-agent-loop", "aqd",
   104	    # understand-anything mapping: agents consult subsystem wiki + graph on demand
   105	    # (aq-wiki --section/--list/--status). Without this the agent cannot benefit
   106	    # from the codebase mapping during autonomous runs.
   107	    "aq-wiki",
   108	    # OpenCode CLI (Phase 60 Integration)
   109	    "opencode",
   110	    # JSON/YAML inspection
   111	    "jq", "yq",
   112	    # File utilities
   113	    "fd", "sort", "uniq", "cut", "awk", "sed", "tr", "printf", "tee",
   114	    # Browser / Javascript execution
   115	    "chromium", "playwright", "node", "lighthouse",
   116	}
   117	
   118	
   119	async def run_command_handler(
   120	    command: str,
   121	    timeout_seconds: int = 10,
   122	) -> Dict:
   123	    """
   124	    Execute a safe shell command.
   125	
   126	    Args:
   127	        command: Shell command to execute
   128	        timeout_seconds: Timeout in seconds (default: 10)
   129	
   130	    Returns:
   131	        {
   132	            "success": bool,
   133	            "stdout": str,
   134	            "stderr": str,
   135	            "returncode": int,
   136	            "error": str (if failed)
   137	        }
   138	    """
   139	    # Strip trailing tool-call JSON artifacts before ANY check. The local model's
   140	    # GBNF/streaming tool-call parser can leak the envelope's closing punctuation
   141	    # into the command argument (e.g. "grep ... file\n},\n"), which the shell-control
   142	    # guard below then rejects as a newline/metachar — the model retries verbatim and
   143	    # stagnates. This trims ONLY trailing whitespace + a dangling "}"/"]"/"," /quote
   144	    # tail; it never removes anything from the middle of a command, so a genuine
   145	    # injection ("; rm -rf" / "cmd\ncmd2") is still caught by the guard. Producer-side
   146	    # cleanup, not a security relaxation. Root cause: local-agent-tool-call-json-artifact-leak.
   147	    command = re.sub(r"[\s}\]\",]+$", "", command)
   148	
   149	    # Parse first word as command
   150	    cmd_parts = command.split()
   151	    if not cmd_parts:
   152	        return {"success": False, "error": "Empty command"}
   153	
   154	    base_cmd = cmd_parts[0]
   155	
   156	    if _SHELL_CONTROL_PATTERN.search(command):
   157	        return {
   158	            "success": False,
   159	            "error": "Command rejected: shell control/metacharacter sequences are not allowed",
   160	            "safety_reason": "shell_injection_guard",
   161	        }
   162	
   163	    # Check if command is safe
   164	    if base_cmd not in SAFE_COMMANDS:
   165	        return {
   225	                return {
   226	                    "success": result.returncode == 0,
   227	                    "stdout": result.stdout,
   228	                    "stderr": result.stderr,
   229	                    "returncode": result.returncode,
   230	                    "compressed": True,
   231	                }
   232	            except Exception as rtk_exc:
   233	                logger.debug("RTK compression failed (%s), falling back to plain subprocess", rtk_exc)
   234	
   235	        result = subprocess.run(
   236	            command,
   237	            shell=True,
   238	            capture_output=True,
   239	            text=True,
   240	            timeout=timeout_seconds,
   241	        )
   242	
   243	        return {
   244	            "success": result.returncode == 0,
   245	            "stdout": result.stdout,
    35	import logging
    36	import os
    37	import time
    38	from pathlib import Path
    39	from typing import Any, Dict, List, Optional, Tuple
    40	
    41	logger = logging.getLogger(__name__)
    42	
    43	# Fields considered part of the SEMANTIC request identity. Everything else in a
    44	# build_llama_payload() dict (chat_template_kwargs, repeat_penalty, repeat_last_n,
    45	# cache_prompt, stream_options, ...) is volatile/derived and deliberately excluded so
    46	# the key is stable across runs that only differ in those knobs.
    47	_SEMANTIC_FIELDS: Tuple[str, ...] = (
    48	    "messages",
    49	    "max_tokens",
    50	    "temperature",
    51	    "grammar",
    52	    "task_type",
    53	    "tools",
    54	    "stream",
    55	)
    56	
    57	
    58	class ReplayMiss(Exception):
    59	    """Raised in replay mode (AQ_LLM_CASSETTE_ON_MISS=error, the default) when no
    60	    recorded row exists for the computed request key. Carries the key and a short
    61	    payload summary so the failure is immediately actionable."""
    62	
    63	    def __init__(self, key: str, payload: Optional[Dict[str, Any]] = None):
    64	        self.key = key
    65	        self.payload_summary = _summarize_payload(payload) if payload else ""
    66	        super().__init__(
    67	            f"llm_cassette: REPLAY MISS for key={key} — no recorded row. "
    68	            f"payload={self.payload_summary}"
    69	        )
    70	
    71	
    72	def _summarize_payload(payload: Dict[str, Any]) -> str:
    73	    try:
    74	        messages = payload.get("messages") or []
    75	        last = messages[-1] if messages else {}
    76	        preview = str(last.get("content", ""))[:120].replace("\n", "\\n")
    77	        return (
    78	            f"max_tokens={payload.get('max_tokens')} "
    79	            f"temperature={payload.get('temperature')} "
    80	            f"n_messages={len(messages)} last='{preview}'"
    81	        )
    82	    except Exception:
    83	        return "<unavailable>"
    84	
    85	
    86	def _normalize_messages(messages: Any) -> List[Dict[str, Any]]:
    87	    if not isinstance(messages, list):
    88	        return []
    89	    out = []
    90	    for m in messages:
    91	        if isinstance(m, dict):
    92	            out.append({"role": m.get("role"), "content": m.get("content")})
    93	    return out
    94	
    95	
    96	def request_key(payload: Dict[str, Any], task_type: Optional[str] = None) -> str:
    97	    """Stable sha256 over the SEMANTIC request only.
    98	
    99	    Includes: messages (role+content), max_tokens, temperature, grammar, task_type,
   100	    tools, stream. Excludes volatile fields (timestamps, request ids, cache flags,
   101	    chat_template_kwargs, repeat_penalty/repeat_last_n, frequency_penalty, ...) so the
   102	    same logical request hashes identically across runs and machines.
   103	
   104	    `task_type` is accepted as a separate optional arg because build_llama_payload()
   105	    consumes it as a keyword-only builder argument and does NOT carry it into the
   106	    resulting payload dict — callers that have task_type as a local variable should
   107	    pass it explicitly. If the payload dict already carries a "task_type" key (e.g. a
   108	    cassette row payload_digest reconstruction), that value wins.
   109	    """
   110	    try:
   111	        semantic: Dict[str, Any] = {
   112	            "messages": _normalize_messages(payload.get("messages")),
   113	            "max_tokens": payload.get("max_tokens"),
   114	            "temperature": payload.get("temperature"),
   115	            "grammar": payload.get("grammar"),
   116	            "task_type": payload.get("task_type", task_type),
   117	            "tools": payload.get("tools"),
   118	            "stream": bool(payload.get("stream", False)),
   119	        }
   120	        blob = json.dumps(semantic, sort_keys=True, default=str, ensure_ascii=False)
   121	        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
   122	    except Exception:
   123	        logger.exception("llm_cassette: request_key failed — this is a bug, not a miss")
   124	        raise
   125	
   135	    """
   136	
   137	    def __init__(self, cassette_path: str):
   138	        self.path = Path(cassette_path)
   139	        self._rows: Optional[Dict[str, List[Dict[str, Any]]]] = None
   140	        self._cursor: Dict[str, int] = {}
   141	
   142	    def _load(self) -> None:
   143	        if self._rows is not None:
   144	            return
   145	        rows: Dict[str, List[Dict[str, Any]]] = {}
   146	        if self.path.exists():
   147	            try:
   148	                with self.path.open("r", encoding="utf-8") as fh:
   149	                    for line_no, line in enumerate(fh, start=1):
   150	                        line = line.strip()
   151	                        if not line:
   152	                            continue
   153	                        try:
   154	                            row = json.loads(line)
   155	                        except json.JSONDecodeError:
   156	                            logger.warning(
   157	                                "llm_cassette: skipping corrupt row %s:%d", self.path, line_no
   158	                            )
   159	                            continue
   160	                        key = row.get("key")
   161	                        if not key:
   162	                            continue
   163	                        rows.setdefault(key, []).append(row)
   164	            except OSError as e:
   165	                logger.warning("llm_cassette: failed to read %s: %s", self.path, e)
   166	        self._rows = rows
   167	
   168	    def record(
   169	        self,
   170	        key: str,
   171	        payload: Dict[str, Any],
   172	        content: str,
   173	        tokens: int,
   174	        meta: Optional[Dict[str, Any]] = None,
   175	    ) -> None:
   176	        """Append one row. Never raises — logs and no-ops on any IO/serialization error."""
   177	        try:
   178	            payload_digest = hashlib.sha256(
   179	                json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
   180	            ).hexdigest()
   181	        except Exception:
   182	            payload_digest = ""
   183	        row = {
   184	            "key": key,
   185	            "payload_digest": payload_digest,
   186	            "content": content,
   187	            "tokens": tokens,
   188	            "meta": meta or {},
   189	            "ts": time.time(),
   190	        }
   191	        try:
   192	            self.path.parent.mkdir(parents=True, exist_ok=True)
   193	            with self.path.open("a", encoding="utf-8") as fh:
   194	                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
   195	        except OSError as e:
   196	            logger.warning("llm_cassette: failed to write %s: %s", self.path, e)
   197	            return
   198	        # Keep the in-memory index in sync so a record()-then-lookup() in the same
   199	        # process (replay-record mode, or a test) sees the row immediately without
   200	        # re-reading the file.
   201	        if self._rows is not None:
   202	            self._rows.setdefault(key, []).append(row)
   203	
   204	    def lookup(self, key: str) -> Optional[Tuple[str, int]]:
   205	        """Return (content, tokens) for the next unconsumed row at this key, in
   206	        call order, or None if no (further) row exists. Never raises."""
   207	        try:
   208	            self._load()
   209	            assert self._rows is not None
   210	            rows = self._rows.get(key)
   211	            if not rows:
   212	                return None
   213	            idx = self._cursor.get(key, 0)
   214	            if idx >= len(rows):
   215	                return None
   216	            row = rows[idx]
   217	            self._cursor[key] = idx + 1
   218	            return row.get("content", ""), int(row.get("tokens", 0) or 0)
   219	        except Exception:
   220	            logger.exception("llm_cassette: lookup failed for key=%s — treating as miss", key)
   221	            return None
   222	
   223	    def reset_cursor(self) -> None:
   224	        """Rewind consumption cursors to the start (useful for re-running the same
   225	        cassette against a second config in aq-replay-bench)."""
   226	        self._cursor = {}
   227	
   228	
   229	# ---------------------------------------------------------------------------
   230	# Module-level env readers + a small per-path cassette cache so the consumption
   231	# cursor persists across the many _call_llama invocations of a single task loop.
   232	# ---------------------------------------------------------------------------
   233	
   234	_VALID_MODES = ("off", "record", "replay", "replay-record")
   235	_VALID_ON_MISS = ("error", "passthrough", "empty")
   236	
   237	_cassette_cache: Dict[str, Cassette] = {}
   238	
   239	
   240	def mode() -> str:
   260	        return None
   261	    resolved = str(Path(p).expanduser())
   262	    cass = _cassette_cache.get(resolved)
   263	    if cass is None:
   264	        cass = Cassette(resolved)
   265	        _cassette_cache[resolved] = cass
   266	    return cass
   267	
   268	
   269	def reset_cache() -> None:
   270	    """Test/bench helper: drop all cached Cassette instances (and their cursors)."""
   271	    _cassette_cache.clear()
   272	
   273	
   274	# ---------------------------------------------------------------------------
   275	# Orchestration helpers — the thin surface agent_executor._call_llama wires into.
   276	# Both are pure no-ops in mode "off" and fail safe (fall through to live) on any
   277	# internal error, per the design's guardrail.
   278	# ---------------------------------------------------------------------------
   279	
   280	def replay_lookup(
   281	    payload: Dict[str, Any], task_type: Optional[str] = None
   282	) -> Optional[Tuple[str, int]]:
   283	    """Consult the cassette in replay/replay-record modes.
   284	
   285	    Returns:
   286	        (content, tokens) on a cassette hit, or on-miss "empty" policy.
   287	        None — proceed with the live call — in mode "off"/"record", on a
   288	              replay-record miss, or on-miss "passthrough".
   289	    Raises:
   290	        ReplayMiss — mode "replay", on-miss "error" (the default), and no row exists.
   291	    """
   292	    m = mode()
   293	    if m not in ("replay", "replay-record"):
   294	        return None
   295	    try:
   296	        cass = get_cassette()
   297	        if cass is None:
   298	            logger.warning(
   299	                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — proceeding live", m
   300	            )
   301	            return None
   302	        key = request_key(payload, task_type)
   303	        hit = cass.lookup(key)
   304	    except ReplayMiss:
   305	        raise
   306	    except Exception:
   307	        logger.exception("llm_cassette: replay_lookup internal error — falling back to live")
   308	        return None
   309	
   310	    if hit is not None:
   311	        return hit
   312	
   313	    if m == "replay-record":
   314	        return None  # fall through to live; caller records after
   315	
   316	    policy = on_miss()
   317	    if policy == "passthrough":
   318	        return None
   319	    if policy == "empty":
   320	        return "", 0
   321	    # policy == "error" (default): a miss in strict replay mode is a test failure.
   322	    raise ReplayMiss(key, payload)
   323	
   324	
   325	def maybe_record(
   326	    payload: Dict[str, Any],
   327	    task_type: Optional[str],
   328	    content: str,
   329	    tokens: int,
   330	    meta: Optional[Dict[str, Any]] = None,
   331	) -> None:
   332	    """Tee a live (content, tokens) result into the cassette in record/replay-record
   333	    modes. No-op in off/replay. Never raises."""
   334	    m = mode()
   335	    if m not in ("record", "replay-record"):
   336	        return
   337	    try:
   338	        cass = get_cassette()
   339	        if cass is None:
   340	            logger.warning(
   341	                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — not recording", m
   342	            )
   343	            return
   344	        key = request_key(payload, task_type)
   345	        cass.record(key, payload, content, tokens, meta)
   346	    except Exception:
   347	        logger.exception("llm_cassette: maybe_record internal error — continuing without recording")
   900	
   901	        # Default to local
   902	        return True, "Default to local (cost-efficient)"
   903	
   904	    async def execute_task(
   905	        self,
   906	        task: Task,
   907	        agent_type: AgentType = AgentType.AGENT,
   908	        max_tool_calls: int = 0,
   909	    ) -> Task:
   910	        """
   911	        Execute a task using local agent with tool use.
   912	
   913	        Args:
   914	            task: Task to execute
   915	            agent_type: Type of agent to use
   916	            max_tool_calls: Deprecated compatibility parameter. Tool loops are
   917	                governed by stagnation/progress guards, context pruning, and the
   918	                stall watchdog, not by a fixed tool-call ceiling.
   919	
   920	        Returns:
   921	            Updated task with result or error
   922	        """
   923	        start_time = time.time()
   924	        task.status = TaskStatus.RUNNING
   925	        task.assigned_agent = f"local-{agent_type.value}"
   926	
   927	        # Auto-assign role from capability→default mapping if not explicitly set.
   928	        # EMBEDDED agents never get a role (no text generation to guide).
   929	        if task.role is None:
   930	            task.role = AGENT_TYPE_DEFAULT_ROLE.get(agent_type)
  1270	        _READS_HARD_LIMIT = (
  1271	            _ANALYSIS_READS_HARD_LIMIT
  1272	            if _is_analysis_only_task else _IMPLEMENTATION_READS_HARD_LIMIT
  1273	        )
  1274	        _exploration_nudge_sent = False
  1275	        # Repeated-read stagnation: fires the edit-forcing intervention exactly once per
  1276	        # task. Set True the moment the intervention message is queued (not only on full
  1277	        # success) so a second breach — with or without a mid-construction error — falls
  1278	        # straight through to the plain abort rather than looping interventions forever.
  1279	        _reread_intervention_sent = False
  1280	        # No-action guard: counts successful edit_file/write_file calls this run, and
  1281	        # whether the one-shot no-action intervention has already fired. See the
  1282	        # _NOACTION_INTERVENTION_ENABLED block above for the full rationale.
  1283	        _edits_made = 0
  1284	        _no_action_intervention_sent = False
  1285	        # Edit-failure feedback: fires per target file (a task may edit several
  1286	        # files), bounded to _EDIT_FEEDBACK_MAX_PER_FILE per path. See the
  1287	        # _EDIT_FEEDBACK_ENABLED block above for the full rationale.
  1288	        _edit_feedback_counts: dict = {}  # file_path → feedback-fire count
  1289	        _validation_passes_without_commit = 0
  1290	        _VALIDATION_STALL_NUDGE = 3
  1291	
  1292	        # Observation stagnation: harness query tools (get_hint, query_aidb, etc.) called
  1293	        # repeatedly without taking any action. Distinguishable from exploration stagnation
  1294	        # (which tracks read_file). Research tasks legitimately query multiple sources, so
  1295	        # threshold is higher than read_file's 3. Soft nudge at 6; hard abort at 10.
  1296	        _OBSERVATION_QUERY_TOOLS = frozenset({
  1297	            "get_hint", "query_aidb", "get_prsi_pending", "get_working_memory",
  1298	            "mesh_discovery", "harness_health", "query_context", "get_context",
  1299	            "collective_memory_search",
  1300	        })
  1301	        _OBSERVATION_ACTION_TOOLS = frozenset({
  1302	            "store_memory", "run_command", "run_harness_cli", "delegate_to_remote",
  1303	            "edit_file", "write_file", "write_region", "git_add", "git_commit",
  1304	        })
  1305	        _observations_without_action = 0
  1306	        _MAX_OBSERVATIONS_WITHOUT_ACTION = 6
  1307	        _OBSERVATIONS_HARD_LIMIT = 10
  1308	        _observation_nudge_sent = False
  1405	                            "error": tc_result.error,
  1406	                        }) + "\n")
  1407	                except Exception:
  1408	                    pass
  1409	
  1410	        _ctrl_cursor = 0  # operator control-channel read cursor (messages consumed)
  1411	        while True:
  1412	            # Phase E — agent_step_start: emitted at the top of every iteration before the LLM call.
  1413	            await self._emit_agent_event(
  1414	                task.id, "agent_step_start",
  1415	                {"tool_call_count": tool_call_count},
  1416	                _watchdog_last_activity,
  1417	            )
  1418	
  1419	            # Operator intervention channel — poll the per-task control queue between turns
  1420	            # and inject any operator messages into the conversation (or a soft-stop on
  1510	                        "context_prune(shed-oldest-pair): SKIP — messages[2:4] roles=%s/%s not assistant/tool pair",
  1511	                        _m2_role, _m3_role,
  1512	                    )
  1513	
  1514	            # Call model — use larger budget once tools have been used so that
  1515	            # the final synthesis turn (no tool_call in response) isn't capped at
  1516	            # the tool-call budget (512).  First call keeps 512 since the model
  1517	            # almost always emits a tool call there (short JSON, EOS quick).
  1518	            call_max_tokens = AGENT_TASK_MAX_TOKENS if tool_call_count > 0 else AGENT_TOOL_CALL_MAX_TOKENS
  1519	            try:
  1520	                response, tok = await self._call_llama(
  1521	                    messages,
  1522	                    role=role,
  1523	                    max_tokens=call_max_tokens,
  1524	                    task_type=task.task_type,
  1525	                    task_id=task.id,
  1526	                    call_number=tool_call_count + 1,
  1527	                )
  1528	            except Exception as _llm_err:
  1529	                # Retry once with reduced budget on transient failures (timeout, connection drop).
  1530	                logger.warning(
  1531	                    "LLM call %d failed (%r), retrying with 512 tokens",
  1532	                    tool_call_count + 1, str(_llm_err)[:120],
  1533	                )
  1534	                response, tok = await self._call_llama(
  1535	                    messages,
  1536	                    role=role,
  1537	                    max_tokens=512,
  1538	                    task_id=task.id,
  1539	                    call_number=tool_call_count + 1,
  1540	                )
  1541	            total_tokens += tok
  1542	            if not response.strip():
  1543	                # Retry once with a nudge before failing the task. Empty responses happen
  1544	                # when the server is cold or the model stalls — a single retry recovers most
  1545	                # transient cases without burning the full budget.
  1546	                _ctx_chars_at_fail = sum(len((m.get("content") or "")) for m in messages)
  1547	                logger.warning(
  1548	                    "empty response at call %d (ctx ~%d chars) — retrying once with nudge",
  1549	                    tool_call_count + 1, _ctx_chars_at_fail,
  1550	                )
  1551	                _nudge_messages = messages + [{
  1552	                    "role": "user",
  1553	                    "content": "Your previous response was empty. Please provide a JSON tool call or a plain-text final answer now.",
  1554	                }]
  1555	                response, _retry_tok = await self._call_llama(
  1556	                    _nudge_messages,
  1557	                    role=role,
  1558	                    max_tokens=AGENT_TASK_MAX_TOKENS,
  1559	                    task_id=task.id,
  1560	                    call_number=tool_call_count + 1,
  1561	                )
  1562	                total_tokens += _retry_tok
  1563	                if response.strip():
  1564	                    messages = _nudge_messages
  1565	                else:
  1566	                    raise RuntimeError(
  1567	                        f"LLM returned empty response at call {tool_call_count + 1} "
  1568	                        f"(context ~{_ctx_chars_at_fail} chars)"
  1569	                    )
  1570	
  1660	                if not tool_call:
  1661	                    # No-action guard: an implementer/edit task with zero successful
  1662	                    # edits so far that returns non-empty prose with no tool call is a
  1663	                    # narrated PLAN ("Thought: I would change X..."), not completion —
  1664	                    # accepting it silently ends the task having changed nothing. Refuse
  1665	                    # it ONCE and force an edit_file call instead. A genuine refusal
  1666	                    # ("cannot safely...", "under-specified...") still completes normally,
  1667	                    # and a second prose-only response completes too (no infinite loop).
  1668	                    # Fail-safe: any error here falls through to the existing completion
  1669	                    # path below rather than crashing the turn.
  1670	                    if (
  1671	                        _NOACTION_INTERVENTION_ENABLED
  1672	                        and not _is_analysis_only_task
  1673	                        and _edits_made == 0
  1674	                        and not _no_action_intervention_sent
  1675	                        and response.strip()
  1676	                    ):
  1677	                        try:
  1678	                            if not _looks_like_refusal(response):
  1679	                                _no_action_intervention_sent = True
  1680	                                intervention_msg = (
  1681	                                    "You described the change but did NOT make it — no "
  1682	                                    "file has been edited yet. Do NOT answer in prose. "
  1683	                                    "Call edit_file NOW: use the exact code from the "
  1684	                                    "'## Relevant prior knowledge' block above as "
  1685	                                    "old_string and your changed version as new_string. "
  1686	                                    "The task is only complete once edit_file has "
  1687	                                    "changed the file."
  1688	                                )
  1689	                                messages.append({"role": "assistant", "content": response})
  1690	                                messages.append({
  1691	                                    "role": "user",
  1692	                                    "content": intervention_msg,
  1693	                                })
  1694	                                logger.warning(
  1695	                                    "no-action intervention: prose-only response with 0 "
  1696	                                    "edits made at call %d — injecting one-shot "
  1697	                                    "edit-forcing nudge instead of completing",
  1698	                                    tool_call_count,
  1699	                                )
  1700	                                await self._emit_agent_event(
  1701	                                    task.id, "noaction_intervention",
  1702	                                    {"tool_call_count": tool_call_count},
  1703	                                    _watchdog_last_activity,
  1704	                                )
  1705	                                continue
  1706	                        except Exception as _noaction_err:
  1707	                            logger.warning(
  1708	                                "no-action-intervention construction failed (%s) — "
  1709	                                "falling through to normal completion", _noaction_err,
  1710	                            )
  1711	                            # Fall through to the plain completion below (fail-safe:
  1712	                            # never let a broken intervention crash or hang the loop).
  1713	                    # Phase E — agent_synthesis_start: no tool call in response after ≥1 tool calls.
  1714	                    if tool_call_count > 0:
  1715	                        await self._emit_agent_event(
  1716	                            task.id, "agent_synthesis_start",
  1717	                            {"tool_call_count": tool_call_count},
  1718	                            _watchdog_last_activity,
  1719	                        )
  1720	                    _cancel_watchdog()
  1938	                    return stagnation_msg, total_tokens
  1939	
  1940	            # Exploration stagnation: count reads vs edits/writes.
  1941	            # Reset counter on any write action; abort if model reads too many files
  1942	            # without acting (prevents over-exploration in self-improvement tasks).
  1943	            if result.tool_name == "read_file":
  1944	                _reads_without_edit += 1
  1945	                read_path = str(result.arguments.get("file_path") or result.arguments.get("path") or "")
  1946	                if read_path:
  1947	                    _read_path_counts[read_path] = _read_path_counts.get(read_path, 0) + 1
  1948	                    if _read_path_counts[read_path] >= _REPEATED_READ_PATH_LIMIT:
  1949	                        # First breach: inject a one-shot edit-forcing intervention instead
  1950	                        # of aborting. The relevant code is already front-loaded verbatim
  1951	                        # under "## Relevant prior knowledge" — the plain abort discarded
  1952	                        # tasks local could complete once nudged off the read->edit stall.
  1953	                        # Delivered as the read_file tool result (role:"tool") so the model
  1954	                        # actually sees it as the outcome of ITS OWN last tool call next turn.
  1955	                        if _REREAD_INTERVENTION_ENABLED and not _reread_intervention_sent:
  1956	                            try:
  1957	                                _reread_intervention_sent = True
  1958	                                _iv_brace = response.rfind('{"function"')
  1959	                                if _iv_brace == -1:
  1960	                                    _iv_brace = response.rfind("{")
  1961	                                _iv_clean_call = (
  1962	                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
  1963	                                )
  1964	                                intervention_msg = (
  1965	                                    f"You have read {read_path!r} "
  1966	                                    f"{_read_path_counts[read_path]} times and it keeps returning "
  1967	                                    "the same content — reading it again will not help. STOP "
  1968	                                    "reading. The relevant code for this task is ALREADY in your "
  1969	                                    "context above under '## Relevant prior knowledge' as exact "
  1970	                                    "fenced code blocks (byte-identical to the file). Call "
  1971	                                    "edit_file NOW: use the exact text from one of those code "
  1972	                                    "blocks as old_string (it will match), and provide your "
  1973	                                    "changed version as new_string. Do not call read_file on "
  1974	                                    "this file again."
  1975	                                )
  1976	                                messages.append({"role": "assistant", "content": _iv_clean_call})
  1977	                                messages.append({
  1978	                                    "role": "tool",
  1979	                                    "name": result.tool_name,
  1980	                                    "content": intervention_msg,
  1981	                                })
  1982	                                logger.warning(
  1983	                                    "repeated-read intervention: path=%r reads=%d call=%d — "
  1984	                                    "injecting one-shot edit-forcing nudge instead of aborting",
  1985	                                    read_path, _read_path_counts[read_path], tool_call_count,
  1986	                                )
  1987	                                await self._emit_agent_event(
  1988	                                    task.id, "reread_intervention",
  1989	                                    {
  1990	                                        "file_path": read_path,
  1991	                                        "reads": _read_path_counts[read_path],
  1992	                                        "tool_call_count": tool_call_count,
  1993	                                    },
  1994	                                    _watchdog_last_activity,
  1995	                                )
  1996	                                continue
  1997	                            except Exception as _interv_err:
  1998	                                logger.warning(
  1999	                                    "reread-intervention construction failed (%s) — "
  2000	                                    "falling back to plain abort", _interv_err,
  2001	                                )
  2002	                                # Fall through to the plain abort below (fail-safe: never
  2003	                                # let a broken intervention crash or hang the loop).
  2004	                        stagnation_msg = (
  2005	                            f"Repeated-read stagnation: {read_path!r} was read "
  2006	                            f"{_read_path_counts[read_path]} times without progress. "
  2007	                            f"Aborting at tool call {tool_call_count}."
  2008	                        )
  2009	                        logger.warning(
  2010	                            "repeated-read stagnation: path=%r reads=%d call=%d",
  2011	                            read_path, _read_path_counts[read_path], tool_call_count,
  2012	                        )
  2013	                        _cancel_watchdog()
  2014	                        return stagnation_msg, total_tokens
  2015	            elif result.tool_name in ("edit_file", "write_file", "write_region"):
  2016	                _reads_without_edit = 0
  2017	                _read_path_counts.clear()
  2018	                if not _is_tool_failure:
  2019	                    _edits_made += 1
  2020	                elif result.tool_name == "edit_file":
  2021	                    # Edit-failure feedback: old_string byte-mismatch is now the
  2022	                    # dominant local-agent failure mode (see _EDIT_FEEDBACK_ENABLED
  2023	                    # above). On the FIRST such mismatch failure for this file
  2024	                    # (bounded to _EDIT_FEEDBACK_MAX_PER_FILE), inject the file's
  2025	                    # EXACT current text for the attempted region as the tool
  2026	                    # result instead of the bare failure, then let the loop
  2027	                    # continue — never crash or hang on a broken feedback build.
  2028	                    _ef_err = str((result.result or {}).get("error", "")) if result.result else ""
  2029	                    _ef_path = str(
  2030	                        (result.arguments or {}).get("file_path")
  2031	                        or (result.arguments or {}).get("path")
  2032	                        or ""
  2033	                    )
  2034	                    _ef_fires = _edit_feedback_counts.get(_ef_path, 0)
  2035	                    if (
  2036	                        _EDIT_FEEDBACK_ENABLED
  2037	                        and _ef_path
  2038	                        and _looks_like_edit_mismatch(_ef_err)
  2039	                        and _ef_fires < _EDIT_FEEDBACK_MAX_PER_FILE
  2040	                    ):
  2041	                        try:
  2042	                            _ef_region = _build_edit_mismatch_feedback(
  2043	                                _ef_path,
  2044	                                str((result.arguments or {}).get("old_string") or ""),
  2045	                                char_budget=_EDIT_FEEDBACK_CHAR_BUDGET,
  2046	                            )
  2047	                            if _ef_region:
  2048	                                _edit_feedback_counts[_ef_path] = _ef_fires + 1
  2049	                                _iv_brace = response.rfind('{"function"')
  2050	                                if _iv_brace == -1:
  2051	                                    _iv_brace = response.rfind("{")
  2052	                                _iv_clean_call = (
  2053	                                    response[_iv_brace:].strip() if _iv_brace != -1 else response.strip()
  2054	                                )
  2055	                                feedback_msg = (
  2056	                                    "edit_file FAILED: your old_string did not match the "
  2057	                                    "file. The file's EXACT current text for that region is "
  2058	                                    "below — copy an exact substring of THIS as your "
  2059	                                    "old_string (character-for-character, including "
  2060	                                    "indentation) and retry edit_file.\n\n" + _ef_region
  2061	                                )
  2062	                                messages.append({"role": "assistant", "content": _iv_clean_call})
  2063	                                messages.append({
  2064	                                    "role": "tool",
  2065	                                    "name": result.tool_name,
  2066	                                    "content": feedback_msg,
  2067	                                })
  2068	                                logger.warning(
  2069	                                    "edit-mismatch feedback: path=%r attempt=%d call=%d — "
  2070	                                    "injecting exact-region feedback instead of plain failure",
  2071	                                    _ef_path, _edit_feedback_counts[_ef_path], tool_call_count,
  2072	                                )
  2073	                                await self._emit_agent_event(
  2074	                                    task.id, "edit_feedback_intervention",
  2075	                                    {
  2076	                                        "file_path": _ef_path,
  2077	                                        "attempt": _edit_feedback_counts[_ef_path],
  2078	                                        "tool_call_count": tool_call_count,
  2079	                                    },
  2080	                                    _watchdog_last_activity,
  2081	                                )
  2082	                                continue
  2083	                        except Exception as _ef_err_exc:
  2084	                            logger.warning(
  2085	                                "edit-feedback construction failed (%s) — "
  2086	                                "falling through to plain failure", _ef_err_exc,
  2087	                            )
  2088	                            # Fall through to the normal failure-result append below.
  2089	            elif _is_analysis_only_task and result.tool_name == "store_memory":
  2090	                _reads_without_edit = 0

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "nl -ba ai-stack/local-agents/llm_cassette.py | sed -n '240,355p'
nl -ba ai-stack/local-agents/agent_executor.py | sed -n '900,925p;1180,1225p;1408,1428p;2340,2390p'
nl -ba ai-stack/local-agents/builtin_tools/file_operations.py | sed -n '460,520p'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 62ms:
   240	def mode() -> str:
   241	    m = os.environ.get("AQ_LLM_CASSETTE_MODE", "off").strip().lower()
   242	    return m if m in _VALID_MODES else "off"
   243	
   244	
   245	def path() -> Optional[str]:
   246	    p = os.environ.get("AQ_LLM_CASSETTE")
   247	    return p.strip() if p and p.strip() else None
   248	
   249	
   250	def on_miss() -> str:
   251	    o = os.environ.get("AQ_LLM_CASSETTE_ON_MISS", "error").strip().lower()
   252	    return o if o in _VALID_ON_MISS else "error"
   253	
   254	
   255	def get_cassette(cassette_path: Optional[str] = None) -> Optional[Cassette]:
   256	    """Return the process-wide Cassette for `cassette_path` (or AQ_LLM_CASSETTE if
   257	    omitted), creating it on first use. Returns None if no path is configured."""
   258	    p = cassette_path if cassette_path is not None else path()
   259	    if not p:
   260	        return None
   261	    resolved = str(Path(p).expanduser())
   262	    cass = _cassette_cache.get(resolved)
   263	    if cass is None:
   264	        cass = Cassette(resolved)
   265	        _cassette_cache[resolved] = cass
   266	    return cass
   267	
   268	
   269	def reset_cache() -> None:
   270	    """Test/bench helper: drop all cached Cassette instances (and their cursors)."""
   271	    _cassette_cache.clear()
   272	
   273	
   274	# ---------------------------------------------------------------------------
   275	# Orchestration helpers — the thin surface agent_executor._call_llama wires into.
   276	# Both are pure no-ops in mode "off" and fail safe (fall through to live) on any
   277	# internal error, per the design's guardrail.
   278	# ---------------------------------------------------------------------------
   279	
   280	def replay_lookup(
   281	    payload: Dict[str, Any], task_type: Optional[str] = None
   282	) -> Optional[Tuple[str, int]]:
   283	    """Consult the cassette in replay/replay-record modes.
   284	
   285	    Returns:
   286	        (content, tokens) on a cassette hit, or on-miss "empty" policy.
   287	        None — proceed with the live call — in mode "off"/"record", on a
   288	              replay-record miss, or on-miss "passthrough".
   289	    Raises:
   290	        ReplayMiss — mode "replay", on-miss "error" (the default), and no row exists.
   291	    """
   292	    m = mode()
   293	    if m not in ("replay", "replay-record"):
   294	        return None
   295	    try:
   296	        cass = get_cassette()
   297	        if cass is None:
   298	            logger.warning(
   299	                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — proceeding live", m
   300	            )
   301	            return None
   302	        key = request_key(payload, task_type)
   303	        hit = cass.lookup(key)
   304	    except ReplayMiss:
   305	        raise
   306	    except Exception:
   307	        logger.exception("llm_cassette: replay_lookup internal error — falling back to live")
   308	        return None
   309	
   310	    if hit is not None:
   311	        return hit
   312	
   313	    if m == "replay-record":
   314	        return None  # fall through to live; caller records after
   315	
   316	    policy = on_miss()
   317	    if policy == "passthrough":
   318	        return None
   319	    if policy == "empty":
   320	        return "", 0
   321	    # policy == "error" (default): a miss in strict replay mode is a test failure.
   322	    raise ReplayMiss(key, payload)
   323	
   324	
   325	def maybe_record(
   326	    payload: Dict[str, Any],
   327	    task_type: Optional[str],
   328	    content: str,
   329	    tokens: int,
   330	    meta: Optional[Dict[str, Any]] = None,
   331	) -> None:
   332	    """Tee a live (content, tokens) result into the cassette in record/replay-record
   333	    modes. No-op in off/replay. Never raises."""
   334	    m = mode()
   335	    if m not in ("record", "replay-record"):
   336	        return
   337	    try:
   338	        cass = get_cassette()
   339	        if cass is None:
   340	            logger.warning(
   341	                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — not recording", m
   342	            )
   343	            return
   344	        key = request_key(payload, task_type)
   345	        cass.record(key, payload, content, tokens, meta)
   346	    except Exception:
   347	        logger.exception("llm_cassette: maybe_record internal error — continuing without recording")
   900	
   901	        # Default to local
   902	        return True, "Default to local (cost-efficient)"
   903	
   904	    async def execute_task(
   905	        self,
   906	        task: Task,
   907	        agent_type: AgentType = AgentType.AGENT,
   908	        max_tool_calls: int = 0,
   909	    ) -> Task:
   910	        """
   911	        Execute a task using local agent with tool use.
   912	
   913	        Args:
   914	            task: Task to execute
   915	            agent_type: Type of agent to use
   916	            max_tool_calls: Deprecated compatibility parameter. Tool loops are
   917	                governed by stagnation/progress guards, context pruning, and the
   918	                stall watchdog, not by a fixed tool-call ceiling.
   919	
   920	        Returns:
   921	            Updated task with result or error
   922	        """
   923	        start_time = time.time()
   924	        task.status = TaskStatus.RUNNING
   925	        task.assigned_agent = f"local-{agent_type.value}"
  1180	                            messages[0]["content"] += (
  1181	                                "\n\nPRIOR WORKING MEMORY:\n" + "\n".join(_wm_lines)
  1182	                            )
  1183	                            logger.debug("working_memory_prefetch: injected %d entries", len(_wm_lines))
  1184	            except Exception:
  1185	                pass
  1186	
  1187	        # Tool use loop
  1188	        tool_call_count = 0
  1189	        total_tokens = 0
  1190	        _loop_start = time.time()
  1191	
  1192	        # Phase E — stall watchdog: fire advisory event if no activity for STALL_TIMEOUT seconds.
  1193	        # STALL_TIMEOUT_OVERRIDE env var enables short timeouts for CI testing (e.g. 5s).
  1194	        # Watchdog is advisory only — never aborts the loop.
  1195	        STALL_TIMEOUT = int(os.environ.get("STALL_TIMEOUT_OVERRIDE", "300"))
  1196	        _watchdog_last_activity: list[float] = [time.time()]
  1197	        _loop = asyncio.get_running_loop()
  1198	        _watchdog_handle: asyncio.TimerHandle
  1199	
  1200	        def _cancel_watchdog() -> None:
  1201	            if not _watchdog_handle.cancelled():
  1202	                _watchdog_handle.cancel()
  1203	
  1204	        def _fire_stall() -> None:
  1205	            if task.status != TaskStatus.RUNNING:
  1206	                _cancel_watchdog()
  1207	                return
  1208	            elapsed = time.time() - _watchdog_last_activity[0]
  1209	            if elapsed >= STALL_TIMEOUT - 1:
  1210	                asyncio.create_task(self._emit_agent_event(
  1211	                    task.id, "agent_stall",
  1212	                    {"elapsed_s": round(elapsed, 1), "advisory": True},
  1213	                    _watchdog_last_activity,
  1214	                ))
  1215	            # Reschedule for the next interval
  1216	            nonlocal _watchdog_handle
  1217	            _watchdog_handle = _loop.call_later(STALL_TIMEOUT, _fire_stall)
  1218	
  1219	        _watchdog_handle = _loop.call_later(STALL_TIMEOUT, _fire_stall)
  1220	
  1221	        # Stagnation guard: track (tool_name, result_prefix) for recent calls.
  1222	        # Thresholds: 3 for read_file (pure observation, no state change expected after 3
  1223	        # identical reads); 5 for run_command and others (allows brief polling loops).
  1224	        # If the threshold is exceeded, abort with a degraded result rather than burning
  1225	        # the full budget on a runaway loop.
  1408	                    pass
  1409	
  1410	        _ctrl_cursor = 0  # operator control-channel read cursor (messages consumed)
  1411	        while True:
  1412	            # Phase E — agent_step_start: emitted at the top of every iteration before the LLM call.
  1413	            await self._emit_agent_event(
  1414	                task.id, "agent_step_start",
  1415	                {"tool_call_count": tool_call_count},
  1416	                _watchdog_last_activity,
  1417	            )
  1418	
  1419	            # Operator intervention channel — poll the per-task control queue between turns
  1420	            # and inject any operator messages into the conversation (or a soft-stop on
  1421	            # cancel). Fails open: the loop is never disrupted by a control-channel error.
  1422	            try:
  1423	                _cc = _control_channel()
  1424	                if _cc is not None:
  1425	                    _new_ctrl, _ctrl_cursor = _cc.poll(task.id, _ctrl_cursor)
  1426	                    for _cm in _new_ctrl:
  1427	                        _txt = (_cm.get("text") or "").strip()
  1428	                        if _cm.get("kind") == "cancel":
  2340	        """Record/replay harness hook — consult the cassette before the HTTP call.
  2341	
  2342	        Returns (content, tokens) on a replay hit (caller must return it immediately,
  2343	        skipping the network entirely); None means "proceed live" (default-off mode,
  2344	        record mode, replay-record miss, or on-miss=passthrough). Raises
  2345	        llm_cassette.ReplayMiss only when the operator explicitly asked for strict
  2346	        replay (AQ_LLM_CASSETTE_ON_MISS=error, the default in replay mode) — that is a
  2347	        deliberate test-failure signal, not swallowed here.
  2348	        """
  2349	        if llm_cassette is None:
  2350	            return None
  2351	        return llm_cassette.replay_lookup(payload, task_type)
  2352	
  2353	    def _cassette_record(
  2354	        self,
  2355	        payload: Dict[str, Any],
  2356	        task_type: Optional[str],
  2357	        content: str,
  2358	        tokens: int,
  2359	        meta: Optional[Dict[str, Any]] = None,
  2360	    ) -> None:
  2361	        """Record/replay harness hook — tee a live result into the cassette. No-op
  2362	        unless AQ_LLM_CASSETTE_MODE is record/replay-record; never raises."""
  2363	        if llm_cassette is None:
  2364	            return
  2365	        llm_cassette.maybe_record(payload, task_type, content, tokens, meta)
  2366	
  2367	    async def _call_llama(
  2368	        self,
  2369	        messages: List[Dict],
  2370	        role: Optional[str] = None,
  2371	        max_tokens: int = AGENT_TOOL_CALL_MAX_TOKENS,
  2372	        task_type: Optional[str] = None,
  2373	        task_id: Optional[str] = None,
  2374	        call_number: int = 0,
  2375	        force_tool_grammar: bool = False,
  2376	    ) -> Tuple[str, int]:
  2377	        """
  2378	        Call local llama.cpp server using SSE streaming.
  2379	
  2380	        Uses per-chunk read timeout (LLAMA_CHUNK_TIMEOUT env, default 120s) instead of a
  2381	        wall-clock total timeout so long-reasoning tasks never time out as long as tokens
  2382	        flow.  Falls back to a non-streaming POST if streaming is explicitly disabled via
  2383	        LLAMA_USE_STREAMING=false.
  2384	
  2385	        Args:
  2386	            messages: Conversation messages
  2387	            task_type: Optional llm_config profile name. When set, profile drives
  2388	                temperature, frequency_penalty, thinking_budget, and enable_thinking.
  2389	                When None, hardcoded temperature=0.2, frequency_penalty=0.05 (legacy).
  2390	
   460	                     without replacing anything.
   461	        new_text:    Replacement text for the region (may be multi-line).
   462	
   463	    Returns:
   464	        {"success": True, "start_line": int, "end_line": int, "lines_written": int}
   465	        {"success": False, "error": "<reason>", "current_line_count": int, "region": "<current text at/near the target>"}
   466	    """
   467	    try:
   468	        path = Path(file_path) if Path(file_path).is_absolute() else Path.cwd() / file_path
   469	        if not path.exists():
   470	            return {"success": False, "error": f"File not found: {file_path}"}
   471	        if not path.is_file():
   472	            return {"success": False, "error": f"Path is not a file: {file_path}"}
   473	
   474	        content = path.read_text(encoding="utf-8")
   475	        lines = content.splitlines(keepends=True)
   476	        line_count = len(lines)
   477	        max_bound = line_count + 1  # +1 slot allows a pure EOF insert
   478	
   479	        try:
   480	            start_line = int(start_line)
   481	            end_line = int(end_line)
   482	        except (TypeError, ValueError):
   483	            return {
   484	                "success": False,
   485	                "error": f"start_line/end_line must be integers (got {start_line!r}, {end_line!r})",
   486	                "current_line_count": line_count,
   487	            }
   488	
   489	        if not (1 <= start_line <= end_line <= max_bound):
   490	            clamp_start = max(1, min(start_line, max(line_count, 1)))
   491	            clamp_end = max(1, min(end_line, max(line_count, 1)))
   492	            region_text = "".join(lines[clamp_start - 1:clamp_end]) if line_count else ""
   493	            return {
   494	                "success": False,
   495	                "error": (
   496	                    f"Out-of-range region [start_line={start_line}, end_line={end_line}] for "
   497	                    f"{file_path} — file currently has {line_count} lines. Valid range is "
   498	                    f"1 <= start_line <= end_line <= {max_bound} ({max_bound} = insert-at-EOF)."
   499	                ),
   500	                "current_line_count": line_count,
   501	                "region": region_text,
   502	            }
   503	
   504	        if new_text and not new_text.endswith("\n"):
   505	            new_text = new_text + "\n"
   506	        new_lines = new_text.splitlines(keepends=True) if new_text else []
   507	
   508	        spliced = lines[:start_line - 1] + new_lines + lines[end_line:]
   509	        path.write_text("".join(spliced), encoding="utf-8")
   510	
   511	        return {
   512	            "success": True,
   513	            "start_line": start_line,
   514	            "end_line": start_line + len(new_lines) - 1 if new_lines else start_line - 1,
   515	            "lines_written": len(new_lines),
   516	        }
   517	    except OSError as exc:
   518	        return {"success": False, "error": str(exc)}
   519	
   520	

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "python3 - <<'PY'
import asyncio, sys, json
sys.path.insert(0,'ai-stack/local-agents'); sys.path.insert(0,'ai-stack/mcp-servers')
from builtin_tools.ai_coordination import query_aidb_handler
r=asyncio.run(query_aidb_handler('GBNF JSON grammar cassette replay shell command injection retry loop', 'error-solutions', 3))
print(json.dumps(r, indent=2, default=str)[:6000])
PY
lean-ctx -c 'git status --short'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 1038ms:
{
  "success": false,
  "error": "qdrant-direct: All connection attempts failed"
}

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "rg --files scripts/testing | rg 'intervention|noaction|reread|edit-feedback|context.*assembler|shell.*tool|run-command'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 62ms:
scripts/testing/test-noaction-intervention.py
scripts/testing/test-context-assembler.py
scripts/testing/test-edit-feedback.py
scripts/testing/test-reread-intervention.py

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx -c 'python3 -m pytest -q scripts/testing/test-noaction-intervention.py scripts/testing/test-edit-feedback.py scripts/testing/test-reread-intervention.py scripts/testing/test-context-assembler.py' && python3 -m py_compile scripts/ai/lib/grammar_cache.py ai-stack/local-agents/builtin_tools/shell_tools.py ai-stack/local-agents/builtin_tools/file_operations.py ai-stack/local-agents/llm_cassette.py ai-stack/local-agents/agent_executor.py" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 exited 1 in 2753ms:
97 lines → 93 unique
last 15 unique lines:
../../../../nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/site-packages/_pytest/config/__init__.py:1434
/nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: asyncio_mode
self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED scripts/testing/test-noaction-intervention.py::test_prose_plan_then_edit_completes
FAILED scripts/testing/test-noaction-intervention.py::test_prose_twice_still_completes
FAILED scripts/testing/test-noaction-intervention.py::test_kill_switch_restores_immediate_completion
FAILED scripts/testing/test-noaction-intervention.py::test_refusal_is_never_intervened_on
FAILED scripts/testing/test-edit-feedback.py::test_mismatch_then_match_completes
FAILED scripts/testing/test-edit-feedback.py::test_feedback_bounded_per_file
FAILED scripts/testing/test-edit-feedback.py::test_kill_switch_restores_plain_failure
FAILED scripts/testing/test-reread-intervention.py::test_first_breach_injects_intervention_not_abort
FAILED scripts/testing/test-reread-intervention.py::test_kill_switch_restores_plain_abort
9 failed, 17 passed, 2 warnings in 0.99s
[lean-ctx: 1145→367 tok, -68%]

codex
The intervention regression suite is not green: 9 tests fail (no-action, edit-feedback, and re-read), while context-assembler tests pass. I’m checking whether those failures expose production logic defects or stale test fixtures before assigning severity.
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc 'python3 -m pytest -q scripts/testing/test-noaction-intervention.py::test_prose_plan_then_edit_completes scripts/testing/test-edit-feedback.py::test_mismatch_then_match_completes scripts/testing/test-reread-intervention.py::test_first_breach_injects_intervention_not_abort -vv' in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 exited 1 in 1602ms:
============================= test session starts ==============================
platform linux -- Python 3.13.13, pytest-9.0.3, pluggy-1.6.0 -- /run/current-system/sw/bin/python3
cachedir: .pytest_cache
rootdir: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
configfile: pytest.ini
plugins: anyio-4.13.0
collecting ... collected 3 items

scripts/testing/test-noaction-intervention.py::test_prose_plan_then_edit_completes FAILED [ 33%]
scripts/testing/test-edit-feedback.py::test_mismatch_then_match_completes FAILED [ 66%]
scripts/testing/test-reread-intervention.py::test_first_breach_injects_intervention_not_abort FAILED [100%]

=================================== FAILURES ===================================
_____________________ test_prose_plan_then_edit_completes ______________________
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
______________________ test_mismatch_then_match_completes ______________________
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
_______________ test_first_breach_injects_intervention_not_abort _______________
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
=============================== warnings summary ===============================
../../../../nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/site-packages/_pytest/config/__init__.py:1434
  /nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: asyncio_default_fixture_loop_scope
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

../../../../nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/site-packages/_pytest/config/__init__.py:1434
  /nix/store/5pa7nk70mwmlyr704l44x67da08ygg02-python3-3.13.13-env/lib/python3.13/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED scripts/testing/test-noaction-intervention.py::test_prose_plan_then_edit_completes
FAILED scripts/testing/test-edit-feedback.py::test_mismatch_then_match_completes
FAILED scripts/testing/test-reread-intervention.py::test_first_breach_injects_intervention_not_abort
======================== 3 failed, 2 warnings in 0.49s =========================

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "tail -60 scripts/testing/test-noaction-intervention.py
tail -60 scripts/testing/test-edit-feedback.py
tail -60 scripts/testing/test-reread-intervention.py
sed -n '1,120p' pytest.ini" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 63ms:
    check("(d) exactly 2 LLM calls (prose -> intervention -> prose again -> completes, no 3rd call)",
          ex._call_llama.await_count == 2)
    check("(d) no edit was ever executed", ex.tool_registry.execute_tool_call.await_count == 0)
    check("(d) loop terminated (did not hang) and returned the second prose response",
          final_msg.strip() == responses[1].strip())


async def test_kill_switch_restores_immediate_completion():
    """(e): AQ_NOACTION_INTERVENTION=0 (patched module attribute, same
    pattern test-reread-intervention.py uses for its own kill switch)
    restores the pre-fix behavior: turn-1 prose completes immediately."""
    ex = make_executor()
    task = Task(id="t-noaction-killswitch", objective="fix the retry backoff", status=TaskStatus.RUNNING)
    snapshots: list = []
    responses = [PROSE_PLAN, edit_call_json()]
    ex._call_llama = make_call_llama_mock(responses, snapshots)

    with patch.object(ae, "_NOACTION_INTERVENTION_ENABLED", False):
        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("(e) kill switch: exactly 1 LLM call (prose completes immediately, no intervention turn)",
          ex._call_llama.await_count == 1)
    check("(e) kill switch: final message is the raw prose plan, unmodified",
          final_msg.strip() == PROSE_PLAN.strip())
    check("(e) kill switch: no edit was ever executed",
          ex.tool_registry.execute_tool_call.await_count == 0)


async def test_refusal_is_never_intervened_on():
    """(bonus): an explicit refusal/stop on turn 1 preserves the legitimate
    exit — completes immediately, same as the kill-switch path, even with
    the intervention enabled."""
    ex = make_executor()
    task = Task(id="t-noaction-refusal", objective="fix the retry backoff", status=TaskStatus.RUNNING)
    snapshots: list = []
    responses = [REFUSAL_PROSE, edit_call_json()]
    ex._call_llama = make_call_llama_mock(responses, snapshots)

    final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("(bonus) refusal completes immediately — exactly 1 LLM call",
          ex._call_llama.await_count == 1)
    check("(bonus) refusal message returned unmodified (no forced edit)",
          final_msg.strip() == REFUSAL_PROSE.strip())
    check("(bonus) no edit was ever executed on a genuine refusal",
          ex.tool_registry.execute_tool_call.await_count == 0)


async def main():
    await test_prose_plan_then_edit_completes()
    await test_prose_twice_still_completes()
    await test_kill_switch_restores_immediate_completion()
    await test_refusal_is_never_intervened_on()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
                id="call-mismatch", tool_name="edit_file",
                arguments={
                    "file_path": target_path,
                    "old_string": MISMATCH_OLD_STRING,
                    "new_string": "REPLACED",
                },
            )

        async def _fake_call_llama(messages, **kwargs):
            snapshots.append(list(messages))
            return f'{{"function": "edit_file", "arguments": {{"file_path": "{target_path}"}}}}', 10

        ex.tool_registry.parse_tool_call_from_llama.side_effect = _fake_parse
        ex.tool_registry.execute_tool_call = AsyncMock(side_effect=make_execute_for(target_path))
        ex._call_llama = AsyncMock(side_effect=_fake_call_llama)

        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        feedback_tool_msgs = feedback_msgs_in_final_state(snapshots)
        check(
            f"feedback fires at most {ae._EDIT_FEEDBACK_MAX_PER_FILE} times for a persistently-failing file",
            len(feedback_tool_msgs) <= ae._EDIT_FEEDBACK_MAX_PER_FILE,
        )
        check("feedback fires at least once before the guard takes over", len(feedback_tool_msgs) >= 1)
        check("the loop eventually ends (never loops forever) via the pre-existing failure guard",
              "Aborting" in final_msg or "stagnation" in final_msg.lower())


async def test_kill_switch_restores_plain_failure():
    """(4): AQ_EDIT_FEEDBACK=0 restores plain-failure behavior — no feedback injected."""
    with tempfile.TemporaryDirectory() as td:
        target_path = make_target_file(Path(td))
        ex = make_executor()
        task = Task(id="t-edit-feedback-killswitch", objective="fix the thing", status=TaskStatus.RUNNING)
        snapshots: list = []
        make_mismatch_then_match_mocks(ex, target_path, snapshots)

        with patch.object(ae, "_EDIT_FEEDBACK_ENABLED", False):
            final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

        feedback_tool_msgs = feedback_msgs_in_final_state(snapshots)
        check("kill switch: no exact-region feedback ever injected", len(feedback_tool_msgs) == 0)
        # The mismatch-then-match script still ultimately succeeds (turn 2 matches,
        # turn 3 completes) — the kill switch only removes the FEEDBACK, not the
        # model's own eventual correct retry.
        check("kill switch: task still completes normally on its own matching retry",
              "Aborting" not in final_msg and "stagnation" not in final_msg.lower())


async def main():
    await test_mismatch_then_match_completes()
    await test_feedback_bounded_per_file()
    await test_kill_switch_restores_plain_failure()

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
    check("intervention message mentions edit_file",
          all("edit_file" in m["content"] for m in intervention_tool_msgs))
    check("intervention fires exactly once (single occurrence across the whole run)",
          len(intervention_tool_msgs) == 1)

    # The call AFTER the intervention (call 3) must have seen it in its own
    # message history — proves it reaches the model on the NEXT turn, not
    # just logged.
    check("the LLM call following the breach sees the intervention in its own context",
          any(
              m.get("role") == "tool" and "Relevant prior knowledge" in (m.get("content") or "")
              for m in snapshots[-1]
          ))

    check("final result is still a plain abort (second breach) after the one-shot nudge failed to land an edit",
          "Aborting" in final_msg and "Repeated-read stagnation" in final_msg)


async def test_kill_switch_restores_plain_abort():
    """(4): AQ_REREAD_INTERVENTION=0 restores original abort-on-first-breach.

    _REREAD_INTERVENTION_ENABLED is a module-level constant resolved once at
    import time (same pattern as _READ_FILE_GATE_ENABLED) — the running loop
    reads the module attribute directly, not os.environ, each call. So the
    kill switch is exercised by patching the module attribute, mirroring how
    test-read-file-gate.py patches ae._LOCAL_ALLOW_COMMIT.
    """
    os.environ["AI_AGENT_REPEATED_READ_PATH_LIMIT"] = "2"
    ex = make_executor()
    task = Task(id="t-killswitch", objective="fix the thing", status=TaskStatus.RUNNING)
    snapshots: list = []
    ex._call_llama = make_call_llama_mock(snapshots)

    from unittest.mock import patch as _patch
    with _patch.object(ae, "_REREAD_INTERVENTION_ENABLED", False):
        final_msg, _tokens = await ex._execute_with_tools(task, AgentType.AGENT, max_tool_calls=0)

    check("kill switch: only 2 _call_llama calls (abort fires on the FIRST breach, no intervention turn)",
          ex._call_llama.await_count == 2)
    check("kill switch: final result is the plain abort message",
          "Aborting" in final_msg and "Repeated-read stagnation" in final_msg)
    no_intervention = not any(
        m.get("role") == "tool" and "Relevant prior knowledge" in (m.get("content") or "")
        for snap in snapshots for m in snap
    )
    check("kill switch: no intervention message ever injected", no_intervention)


async def main():
    await test_first_breach_injects_intervention_not_abort()
    await test_kill_switch_restores_plain_abort()

    os.environ.pop("AI_AGENT_REPEATED_READ_PATH_LIMIT", None)

    print(f"\n{PASS}/{PASS + FAIL} tests passed")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
[pytest]
testpaths = ai-stack
markers =
    integration: requires running services
    asyncio: mark test as async
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc 'python3 scripts/testing/test-noaction-intervention.py
python3 scripts/testing/test-edit-feedback.py
python3 scripts/testing/test-reread-intervention.py
python3 scripts/testing/test-context-assembler.py' in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 2774ms:
no-action intervention: prose-only response with 0 edits made at call 0 — injecting one-shot edit-forcing nudge instead of completing
no-action intervention: prose-only response with 0 edits made at call 0 — injecting one-shot edit-forcing nudge instead of completing
  PASS  (a) turn-1 prose did not complete immediately — 3 LLM calls happened (prose -> intervention -> edit -> final synthesis), not 1
  PASS  (b) edit_file was actually executed (tool result landed)
  PASS  (b) the executed tool was edit_file
  PASS  (b) task completed with the edit landed (final message reflects real completion)
  PASS  (c) no-action intervention message present in final context
  PASS  (c) no-action intervention fires exactly once (not duplicated)
  PASS  (d) exactly 2 LLM calls (prose -> intervention -> prose again -> completes, no 3rd call)
  PASS  (d) no edit was ever executed
  PASS  (d) loop terminated (did not hang) and returned the second prose response
  PASS  (e) kill switch: exactly 1 LLM call (prose completes immediately, no intervention turn)
  PASS  (e) kill switch: final message is the raw prose plan, unmodified
  PASS  (e) kill switch: no edit was ever executed
  PASS  (bonus) refusal completes immediately — exactly 1 LLM call
  PASS  (bonus) refusal message returned unmodified (no forced edit)
  PASS  (bonus) no edit was ever executed on a genuine refusal

15/15 tests passed
edit-mismatch feedback: path='/tmp/tmpqshl7bp4/target.py' attempt=1 call=1 — injecting exact-region feedback instead of plain failure
edit-mismatch feedback: path='/tmp/tmpie8bu18m/target.py' attempt=1 call=1 — injecting exact-region feedback instead of plain failure
edit-mismatch feedback: path='/tmp/tmpie8bu18m/target.py' attempt=2 call=2 — injecting exact-region feedback instead of plain failure
stagnation: tool='edit_file' threshold=5 — aborting loop at call 5
  PASS  feedback delivered as role:'tool' message
  PASS  feedback contains the real file's exact current text
  PASS  feedback message instructs a retry
  PASS  feedback fires exactly once for this file
  PASS  task completes (no abort) after the matching retry
  PASS  completion prose reflects the fix
  PASS  the matching-old_string edit actually landed on disk
  PASS  feedback fires at most 2 times for a persistently-failing file
  PASS  feedback fires at least once before the guard takes over
  PASS  the loop eventually ends (never loops forever) via the pre-existing failure guard
  PASS  kill switch: no exact-region feedback ever injected
  PASS  kill switch: task still completes normally on its own matching retry

12/12 tests passed
repeated-read intervention: path='/fake/repeated.py' reads=2 call=2 — injecting one-shot edit-forcing nudge instead of aborting
repeated-read stagnation: path='/fake/repeated.py' reads=3 call=3
repeated-read stagnation: path='/fake/repeated.py' reads=2 call=2
  PASS  exactly 3 _call_llama calls (1 clean read, 1 breach->intervention, 1 breach->abort)
  PASS  intervention delivered as role:'tool' message
  PASS  intervention message mentions edit_file
  PASS  intervention fires exactly once (single occurrence across the whole run)
  PASS  the LLM call following the breach sees the intervention in its own context
  PASS  final result is still a plain abort (second breach) after the one-shot nudge failed to land an edit
  PASS  kill switch: only 2 _call_llama calls (abort fires on the FIRST breach, no intervention turn)
  PASS  kill switch: final result is the plain abort message
  PASS  kill switch: no intervention message ever injected

9/9 tests passed
[test-context-assembler] LIVE backends: False
test_citations_present_per_source (__main__.TestCitations.test_citations_present_per_source) ... ok
test_enabled_prepends_when_assembler_finds_content (__main__.TestDispatchWiring.test_enabled_prepends_when_assembler_finds_content) ... ok
test_kill_switch_returns_prompt_unchanged (__main__.TestDispatchWiring.test_kill_switch_returns_prompt_unchanged) ... ok
test_dead_embed_returns_empty_valid_context (__main__.TestFailOpen.test_dead_embed_returns_empty_valid_context) ... ok
test_dead_qdrant_returns_empty_valid_context (__main__.TestFailOpen.test_dead_qdrant_returns_empty_valid_context) ... ok
test_empty_task_text_returns_empty_valid_context_no_network (__main__.TestFailOpen.test_empty_task_text_returns_empty_valid_context_no_network) ... ok
test_missing_collection_skipped_others_kept (__main__.TestFailOpen.test_missing_collection_skipped_others_kept) ... ok
test_never_raises_on_totally_broken_response_json (__main__.TestFailOpen.test_never_raises_on_totally_broken_response_json) ... ok
test_file_targeted_fail_open_on_cache_evicted_failure (__main__.TestFileTargetedRetrieval.test_file_targeted_fail_open_on_cache_evicted_failure) ... ok
test_file_targeted_gets_budget_priority_over_semantic (__main__.TestFileTargetedRetrieval.test_file_targeted_gets_budget_priority_over_semantic) ... ok
test_named_existing_file_produces_file_targeted_citation (__main__.TestFileTargetedRetrieval.test_named_existing_file_produces_file_targeted_citation) ... ok
test_named_nonexistent_file_falls_back_to_semantic_only (__main__.TestFileTargetedRetrieval.test_named_nonexistent_file_falls_back_to_semantic_only) ... ok
test_rendered_span_body_is_byte_identical_to_source_lines (__main__.TestFileTargetedVerbatim.test_rendered_span_body_is_byte_identical_to_source_lines) ... ok
test_verbatim_helper_preserves_indentation_and_truncates_on_line_boundary (__main__.TestFileTargetedVerbatim.test_verbatim_helper_preserves_indentation_and_truncates_on_line_boundary) ... ok
test_code_task_pulls_multiple_collections (__main__.TestMultiCollectionPull.test_code_task_pulls_multiple_collections) ... ok
test_generous_budget_fits_everything_stub_offers (__main__.TestTokenBudget.test_generous_budget_fits_everything_stub_offers) ... ok
test_tight_budget_yields_small_block (__main__.TestTokenBudget.test_tight_budget_yields_small_block) ... ok

----------------------------------------------------------------------
Ran 17 tests in 0.214s

OK

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc 'rg -n "test-(tool-call-grammar|llm-cassette|write-region|noaction-intervention|edit-feedback|reread-intervention|context-assembler)" scripts/governance scripts/testing config | head -200' in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 87ms:
scripts/testing/test-read-file-gate.py:15:Dual-mode, mirroring test-context-assembler.py's pattern: probe the real embed
scripts/testing/test-read-file-gate.py:48:    """Same proof pattern as test-context-assembler.py's _live_backends_available()."""
scripts/testing/test-write-region.py:216:    intervention (mirrors test-noaction-intervention.py's pattern for
scripts/testing/test-noaction-intervention.py:27:test-reread-intervention.py), so the assertions exercise the actual control
scripts/testing/test-noaction-intervention.py:235:    pattern test-reread-intervention.py uses for its own kill switch)
scripts/testing/aq-replay-bench:30:    # Re-run the exact scenario recorded by scripts/testing/test-llm-cassette.py's
scripts/testing/aq-replay-bench:72:# scripts/testing/test-llm-cassette.py's golden end-to-end). Pass --extra-tools to
scripts/testing/test-context-assembler.py:440:    print(f"[test-context-assembler] LIVE backends: {LIVE}", file=sys.stderr)
scripts/testing/test-edit-feedback.py:25:test-reread-intervention.py / test-noaction-intervention.py) against a REAL
scripts/testing/test-llm-cassette.py:32:Run: python3 scripts/testing/test-llm-cassette.py

hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "python3 scripts/testing/test-tool-call-grammar.py | tail -5
python3 scripts/testing/test-llm-cassette.py | tail -12
python3 scripts/testing/test-write-region.py | tail -8
lean-ctx -c 'git status --short'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "lean-ctx -c 'git show -s --format=full 4650b1e6' && lean-ctx -c 'git show -s --format=full 950f56e4' && lean-ctx -c 'git show -s --format=full ae9029ef' && lean-ctx -c 'git show -s --format=full 47e03ea9'" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 2525ms:
4650b1e Commit: 29788208+MasterofNull@users.noreply.github.com <29788208+MasterofNull@users.noreply.github.com>
[lean-ctx: 129→38 tok, -71%]
950f56e Commit: 29788208+MasterofNull@users.noreply.github.com <29788208+MasterofNull@users.noreply.github.com> +0/-4
[lean-ctx: 652→41 tok, -94%]
ae9029e Commit: 29788208+MasterofNull@users.noreply.github.com <29788208+MasterofNull@users.noreply.github.com>
[lean-ctx: 291→37 tok, -87%]
47e03ea Commit: 29788208+MasterofNull@users.noreply.github.com <29788208+MasterofNull@users.noreply.github.com>
[lean-ctx: 360→37 tok, -90%]

hook: PreToolUse
2026-08-21T23:31:34.025160Z ERROR codex_core::tools::router: error=Command blocked by PreToolUse hook: Command should run via lean-ctx for compact output. Do not retry the original command. Re-run with: /run/current-system/sw/bin/lean-ctx -c 'git cat-file -p 4650b1e6\ngit cat-file -p 950f56e4' | sed -n '1,120p'\ngit cat-file -p ae9029ef | sed -n '1,100p'\ngit cat-file -p 47e03ea9 | sed -n '1,100p'. Command: git cat-file -p 4650b1e6
git cat-file -p 950f56e4 | sed -n '1,120p'
git cat-file -p ae9029ef | sed -n '1,100p'
git cat-file -p 47e03ea9 | sed -n '1,100p'
hook: PreToolUse Blocked
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "for c in 4650b1e6 950f56e4 ae9029ef 47e03ea9; do /run/current-system/sw/bin/lean-ctx -c \"git log -1 --pretty=format:'%s%n%b' "'$c"; done' in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 2519ms:
chore: gitignore LLM cassette run-artifacts dir
Co-Authored-By: claude-opus-4.8 <noreply@anthropic.com>
feat(local-agent): LLM record/replay harness — deterministic offline validation
Velocity multiplier: replaces 30-40min flaky live dogfood runs with instant, deterministic
replay of recorded model outputs. This session hit 4 different failures live (silent-timeout,
run_command artifact, grammar, budget), each costing a full cycle to discover serially; most
are loop/parser/guard bugs (not model bugs), so replay reproduces them EXACTLY offline.

- llm_cassette.py: Cassette (JSONL) keyed by request_key() — a stable sha256 over the SEMANTIC
  request (messages/max_tokens/temperature/grammar/task_type/tools/stream), excluding volatile
  knobs. Modes via AQ_LLM_CASSETTE_MODE (off|record|replay|replay-record, default OFF); path via
  AQ_LLM_CASSETTE; miss policy AQ_LLM_CASSETTE_ON_MISS (error|passthrough|empty). Multi-row-per-key
  consumed in call order. stdlib only.
- agent_executor: _cassette_replay/_cassette_record wrap BOTH _call_llama branches. Replay hit
  returns (content,tokens) before any HTTP/SSE. Optional import fails safe to None. Default-off is
  a STRICT no-op (verified: replay_lookup->None, maybe_record writes nothing, mode()->off) and any
  cassette error falls back to live (fail-safe).
- aq-replay-bench: config-matrix A/B runner — replays a cassette across flag combos in <1s,
  tabulates edit%, correct% (compile/lint the diff -> catches lucky-pass), valid-tool-call%, calls,
  run_command-rejections, failure-mode histogram.
- test-llm-cassette.py 8/8: key stability, record round-trip, multi-row order, zero-network replay
  (patched httpx to blow up), all on_miss policies, mode=off no-op, golden e2e through real
  _execute_with_tools. DoD demo: recorded this session's '\n},\n' run_command artifact failure,
  replayed offline, proved the committed strip fix resolves it (success=true) — deterministically.

Boundary: replay validates the HARNESS (loop/parser/guards/interventions/edit-apply) completely and
instantly; it does NOT re-measure the MODEL's live reliability (that needs periodic live sampling).
No-op regression: test-tool-call-grammar 9/9 unchanged.

Co-Authored-By: claude-opus-4.8 <noreply@anthropic.com>
fix(local-agent): strip tool-call JSON-envelope artifact from run_command args
4th distinct local-agent failure found via dogfood: the streaming/GBNF tool-call
parser leaks the envelope tail (e.g. '\n},\n') into the final argument's value, so
run_command got 'grep ... file\n},\n'. The shell-safety guard correctly rejected the
trailing newline; local retried verbatim -> 5 rejections -> tool-failure-stagnation
abort (calls=13, never edited). Fix: trim a trailing whitespace/brace/bracket/comma/
quote tail before the guard. Surgical + verified — real injection ('; rm', 'a\nb',
'&&') is still rejected; only the dangling envelope tail is removed. Producer-side
cleanup, not a security relaxation.

Co-Authored-By: claude-opus-4.8 <noreply@anthropic.com>
feat(local-agent): write_region line-range rewrite tool (Aider whole-format tactic) + maturity gap analysis
write_region(file_path, start_line, end_line, new_text): deterministic line-range
replace requiring NO old_string match. Targets the measured #1 local edit failure
(byte-exact old_string mismatch on weak/quantized models). Aider's per-model data
shows weak models fail search/replace and defaults them to whole-format rewrites;
local uses the line-number citations already in its front-loaded context. Registered
like edit_file (auto-joins the GBNF function enum), gated AQ_WRITE_REGION (default on),
wired into _edits_made / observation / validation-stall guards + a prompt steering line.
On failure returns the current line count + region text (edit-feedback pattern).
Tests: test-write-region.py 27/27; 49/49 regression across the 4 intervention suites.

Also: .agent/research/maturity-gap-analysis — observability/extensibility/interop/
benchmarking gaps; record/replay + OTel-GenAI observability identified as the
velocity-multipliers to build next.

Co-Authored-By: claude-opus-4.8 <noreply@anthropic.com>

hook: PreToolUse
2026-08-21T23:31:57.387114Z ERROR codex_core::tools::router: error=Command blocked by PreToolUse hook: Command should run via lean-ctx for compact output. Do not retry the original command. Re-run with: /run/current-system/sw/bin/lean-ctx -c 'git show 4650b1e6 --format= -- .gitignore' && rg -n "casset|record-replay|replay" .gitignore. Command: git show 4650b1e6 --format= -- .gitignore && rg -n "casset|record-replay|replay" .gitignore
hook: PreToolUse Blocked
hook: PreToolUse
hook: PreToolUse Completed
exec
/run/current-system/sw/bin/zsh -lc "/run/current-system/sw/bin/lean-ctx -c 'git show 4650b1e6 --format= -- .gitignore' && rg -n \"casset|record-replay|replay\" .gitignore" in /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
 succeeded in 708ms:
diff --git a/.gitignore b/.gitignore
index c4ba869e..c8f7144d 100644
--- a/.gitignore
+++ b/.gitignore
@@ -334,3 +334,6 @@ config/aqos/approval-signer-credentials.json
 .agents/delegation/dogfood-queue.json
 .agents/delegation/dogfood-runner.log
 .agents/delegation/dogfood-overnight-summary.md
+
+# LLM record/replay cassettes (run artifacts; curate goldens explicitly)
... (1 more lines)
338:# LLM record/replay cassettes (run artifacts; curate goldens explicitly)
339:.agents/delegation/cassettes/

codex
Verdict: **REQUEST_REVISION**. Several fixes are genuinely unsafe or incomplete.

1. **CRITICAL — shell injection guard is not sound.**  
   [shell_tools.py:84](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/shell_tools.py:84), [shell_tools.py:235](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/shell_tools.py:235)  
   The guard misses single `|`, single `&`, `>`, and `<`, then executes with `shell=True`. When RTK/nsjail are unavailable or fail, a whitelisted prefix can run chained commands or overwrite files. Harmless probes confirmed both `echo SAFE | printf PIPED` and `echo FIRST & echo SECOND` execute. `bash -c` and `python3 -c` also bypass the command allowlist in substance.  
   **Fix:** eliminate `shell=True`; parse to argv and execute directly. If shell syntax is required, implement an AST-level allowlist and require the sandbox fail-closed.

2. **CRITICAL — `write_region` bypasses the file-write security boundary.**  
   [file_operations.py:467](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/file_operations.py:467)  
   Unlike `write_file`, it never calls `validate_file_path(..., allow_write=True)`. Any existing writable file—including forbidden paths such as `~/.ssh/config`—can be modified. Symlink targets are also followed.  
   **Fix:** resolve and validate against the workspace allowlist, reject forbidden/symlink targets, then write atomically.

3. **HIGH — cassette keys collide across materially different inference requests.**  
   [llm_cassette.py:43](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:43), [llm_cassette.py:86](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:86), [llm_cassette.py:96](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:96)  
   The key excludes `frequency_penalty`, `repeat_penalty`, `chat_template_kwargs.enable_thinking`, model identity, stop sequences, and other behavior-changing fields. Message normalization also drops `name`, `tool_call_id`, and tool-call metadata. I verified that requests differing simultaneously in model, tool name, thinking mode, and frequency penalty produce the same key. The test explicitly codifies this collision as desired behavior.  
   **Fix:** hash the complete canonical behavioral request, excluding only genuinely non-semantic IDs/timestamps. Include model/build identity and complete messages; verify the stored digest during lookup.

4. **HIGH — strict replay can silently become a live call.**  
   [llm_cassette.py:240](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:240), [llm_cassette.py:292](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:292), [agent_executor.py:2349](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:2349)  
   An invalid mode silently becomes `off`; replay with no path proceeds live; internal replay errors fall back live; and a failed optional import disables replay silently. That contradicts “replay — NO network” and can mask regressions.  
   **Fix:** make `replay` strictly fail-closed for invalid configuration, missing files, corrupt rows, imports, and lookup failures. Permit live fallback only under an explicitly named passthrough/replay-record mode.

5. **HIGH — the agent loop has no hard termination bound.**  
   [agent_executor.py:904](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:904), [agent_executor.py:1192](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1192), [agent_executor.py:1411](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1411)  
   `max_tool_calls` is ignored, the watchdog is advisory, and execution uses `while True`. Alternating successful tools with changing outputs can continually reset/avoid every stagnation counter.  
   **Fix:** enforce both a hard tool-call ceiling and wall-clock/token budget, with an explicit bounded override for long jobs.

6. **HIGH — the GBNF still permits malformed JSON and incompletely implements schemas.**  
   [grammar_cache.py:91](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/grammar_cache.py:91), [grammar_cache.py:145](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/grammar_cache.py:145), [grammar_cache.py:155](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/grammar_cache.py:155), [grammar_cache.py:158](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/grammar_cache.py:158)  
   The string rule allows unescaped control characters, including bare newlines. I confirmed the grammar accepts a string that `json.loads` rejects. `_object_rule` ignores `required` and forces every property in sorted order; unknown-type alternations are unparenthesized and break nested objects and heterogeneous arrays.  
   **Fix:** exclude JSON control characters, parenthesize every alternation, and either implement `required`/optional/additional-property semantics or reject unsupported schemas explicitly.

7. **MEDIUM — artifact stripping corrupts legitimate commands.**  
   [shell_tools.py:139](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/shell_tools.py:139)  
   `re.sub(r"[\s}\]\",]+$", "", command)` strips real quotes/brackets, not merely envelopes. `printf "%s" "]"` becomes the unterminated `printf "%s` and fails.  
   **Fix:** repair at the JSON parser boundary. If downstream recovery remains necessary, recognize only the exact observed newline-prefixed envelope suffix; never remove arbitrary quotes or brackets.

8. **MEDIUM — retry paths silently change the inference profile.**  
   [agent_executor.py:1519](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1519), [agent_executor.py:1528](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1528), [agent_executor.py:1555](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1555)  
   The broad `except Exception` treats replay misses and programming errors as transient failures. Both fallback calls omit `task_type`, changing frequency penalty/thinking configuration and cassette identity.  
   **Fix:** catch only transient transport exceptions and preserve `task_type`, grammar mode, and all behavioral parameters on retries.

9. **MEDIUM — line-number edits have no stale-context protection.**  
   [file_operations.py:474](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/file_operations.py:474), [file_operations.py:508](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/file_operations.py:508)  
   If an earlier edit shifts lines, a later `write_region` based on old citations rewrites the wrong block without detecting drift. Writes are also non-atomic, and `new_text` is forcibly newline-terminated.  
   **Fix:** require an expected file/region hash, preserve exact requested bytes, and use atomic replacement.

10. **MEDIUM — new regression tests are not part of the normal gate.**  
    [pytest.ini:2](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/pytest.ini:2)  
    `pytest` only discovers `ai-stack`; the relevant tests live under `scripts/testing`, and no tier0 reference to their filenames exists. The async intervention tests fail when invoked through pytest because the configured asyncio plugin is unavailable, although their standalone runners pass.  
    **Fix:** register the standalone commands in tier0 or make them normal pytest tests with the required plugin pinned.

11. **LOW — cassette output may expose sensitive model content.**  
    [llm_cassette.py:168](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:168)  
    Model output is written to any operator-supplied path with default filesystem permissions and no redaction. Only one conventional cassette directory is ignored by Git.  
    **Fix:** constrain paths, create files as `0600`, redact known secret patterns, and refuse tracked destinations by default.

12. **PROCESS — commit contract violations.**  
    `4650b1e6` uses `chore:` without the mandatory scope, and reviewed commits use a different co-author trailer than the supplied exact contract. These need correction or an explicit contract exception.

Clean areas:

- Property-name escaping and function-enum parenthesization are correct.
- Recursive free-form objects/arrays work apart from the JSON-string defect above.
- Default-off cassette mode causes no cassette I/O or behavioral change, though it still adds hook/env lookups to the hot path.
- The individual re-read, no-action, and edit-feedback interventions are one-shot/bounded and their standalone suites pass: 15/15, 12/12, and 9/9.
- Context assembly whitespace/verbatim coverage passes 17/17.
- No hardcoded secret was found.

Review limitation: this checkout is shallow with only five reachable commits, not eight. I reviewed HEAD `4650b1e6` and the current-tree implementations for the unavailable grammar/context/intervention history. No files were modified or committed.
tokens used
199,707
Verdict: **REQUEST_REVISION**. Several fixes are genuinely unsafe or incomplete.

1. **CRITICAL — shell injection guard is not sound.**  
   [shell_tools.py:84](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/shell_tools.py:84), [shell_tools.py:235](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/shell_tools.py:235)  
   The guard misses single `|`, single `&`, `>`, and `<`, then executes with `shell=True`. When RTK/nsjail are unavailable or fail, a whitelisted prefix can run chained commands or overwrite files. Harmless probes confirmed both `echo SAFE | printf PIPED` and `echo FIRST & echo SECOND` execute. `bash -c` and `python3 -c` also bypass the command allowlist in substance.  
   **Fix:** eliminate `shell=True`; parse to argv and execute directly. If shell syntax is required, implement an AST-level allowlist and require the sandbox fail-closed.

2. **CRITICAL — `write_region` bypasses the file-write security boundary.**  
   [file_operations.py:467](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/file_operations.py:467)  
   Unlike `write_file`, it never calls `validate_file_path(..., allow_write=True)`. Any existing writable file—including forbidden paths such as `~/.ssh/config`—can be modified. Symlink targets are also followed.  
   **Fix:** resolve and validate against the workspace allowlist, reject forbidden/symlink targets, then write atomically.

3. **HIGH — cassette keys collide across materially different inference requests.**  
   [llm_cassette.py:43](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:43), [llm_cassette.py:86](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:86), [llm_cassette.py:96](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:96)  
   The key excludes `frequency_penalty`, `repeat_penalty`, `chat_template_kwargs.enable_thinking`, model identity, stop sequences, and other behavior-changing fields. Message normalization also drops `name`, `tool_call_id`, and tool-call metadata. I verified that requests differing simultaneously in model, tool name, thinking mode, and frequency penalty produce the same key. The test explicitly codifies this collision as desired behavior.  
   **Fix:** hash the complete canonical behavioral request, excluding only genuinely non-semantic IDs/timestamps. Include model/build identity and complete messages; verify the stored digest during lookup.

4. **HIGH — strict replay can silently become a live call.**  
   [llm_cassette.py:240](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:240), [llm_cassette.py:292](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:292), [agent_executor.py:2349](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:2349)  
   An invalid mode silently becomes `off`; replay with no path proceeds live; internal replay errors fall back live; and a failed optional import disables replay silently. That contradicts “replay — NO network” and can mask regressions.  
   **Fix:** make `replay` strictly fail-closed for invalid configuration, missing files, corrupt rows, imports, and lookup failures. Permit live fallback only under an explicitly named passthrough/replay-record mode.

5. **HIGH — the agent loop has no hard termination bound.**  
   [agent_executor.py:904](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:904), [agent_executor.py:1192](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1192), [agent_executor.py:1411](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1411)  
   `max_tool_calls` is ignored, the watchdog is advisory, and execution uses `while True`. Alternating successful tools with changing outputs can continually reset/avoid every stagnation counter.  
   **Fix:** enforce both a hard tool-call ceiling and wall-clock/token budget, with an explicit bounded override for long jobs.

6. **HIGH — the GBNF still permits malformed JSON and incompletely implements schemas.**  
   [grammar_cache.py:91](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/grammar_cache.py:91), [grammar_cache.py:145](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/grammar_cache.py:145), [grammar_cache.py:155](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/grammar_cache.py:155), [grammar_cache.py:158](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/grammar_cache.py:158)  
   The string rule allows unescaped control characters, including bare newlines. I confirmed the grammar accepts a string that `json.loads` rejects. `_object_rule` ignores `required` and forces every property in sorted order; unknown-type alternations are unparenthesized and break nested objects and heterogeneous arrays.  
   **Fix:** exclude JSON control characters, parenthesize every alternation, and either implement `required`/optional/additional-property semantics or reject unsupported schemas explicitly.

7. **MEDIUM — artifact stripping corrupts legitimate commands.**  
   [shell_tools.py:139](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/shell_tools.py:139)  
   `re.sub(r"[\s}\]\",]+$", "", command)` strips real quotes/brackets, not merely envelopes. `printf "%s" "]"` becomes the unterminated `printf "%s` and fails.  
   **Fix:** repair at the JSON parser boundary. If downstream recovery remains necessary, recognize only the exact observed newline-prefixed envelope suffix; never remove arbitrary quotes or brackets.

8. **MEDIUM — retry paths silently change the inference profile.**  
   [agent_executor.py:1519](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1519), [agent_executor.py:1528](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1528), [agent_executor.py:1555](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py:1555)  
   The broad `except Exception` treats replay misses and programming errors as transient failures. Both fallback calls omit `task_type`, changing frequency penalty/thinking configuration and cassette identity.  
   **Fix:** catch only transient transport exceptions and preserve `task_type`, grammar mode, and all behavioral parameters on retries.

9. **MEDIUM — line-number edits have no stale-context protection.**  
   [file_operations.py:474](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/file_operations.py:474), [file_operations.py:508](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/builtin_tools/file_operations.py:508)  
   If an earlier edit shifts lines, a later `write_region` based on old citations rewrites the wrong block without detecting drift. Writes are also non-atomic, and `new_text` is forcibly newline-terminated.  
   **Fix:** require an expected file/region hash, preserve exact requested bytes, and use atomic replacement.

10. **MEDIUM — new regression tests are not part of the normal gate.**  
    [pytest.ini:2](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/pytest.ini:2)  
    `pytest` only discovers `ai-stack`; the relevant tests live under `scripts/testing`, and no tier0 reference to their filenames exists. The async intervention tests fail when invoked through pytest because the configured asyncio plugin is unavailable, although their standalone runners pass.  
    **Fix:** register the standalone commands in tier0 or make them normal pytest tests with the required plugin pinned.

11. **LOW — cassette output may expose sensitive model content.**  
    [llm_cassette.py:168](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/llm_cassette.py:168)  
    Model output is written to any operator-supplied path with default filesystem permissions and no redaction. Only one conventional cassette directory is ignored by Git.  
    **Fix:** constrain paths, create files as `0600`, redact known secret patterns, and refuse tracked destinations by default.

12. **PROCESS — commit contract violations.**  
    `4650b1e6` uses `chore:` without the mandatory scope, and reviewed commits use a different co-author trailer than the supplied exact contract. These need correction or an explicit contract exception.

Clean areas:

- Property-name escaping and function-enum parenthesization are correct.
- Recursive free-form objects/arrays work apart from the JSON-string defect above.
- Default-off cassette mode causes no cassette I/O or behavioral change, though it still adds hook/env lookups to the hot path.
- The individual re-read, no-action, and edit-feedback interventions are one-shot/bounded and their standalone suites pass: 15/15, 12/12, and 9/9.
- Context assembly whitespace/verbatim coverage passes 17/17.
- No hardcoded secret was found.

Review limitation: this checkout is shallow with only five reachable commits, not eight. I reviewed HEAD `4650b1e6` and the current-tree implementations for the unavailable grammar/context/intervention history. No files were modified or committed.
