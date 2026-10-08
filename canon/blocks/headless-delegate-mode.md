## Headless Delegate Mode (Canonical — all agents)

Applies to any agent dispatched non-interactively (`delegate-to-*`, `codex exec`, Agent-tool sub-agents) with a bounded slice.

**Primary Agents (current & future orchestrators):**
- Enforce all agentic system features: the 8-step canonical workflow (`ORIENT → RESEARCH → PRD/PLAN → MEMORY-CHECKPOINT → EXECUTE → VALIDATE → DOC-UPDATE → COMMIT`), Behavioral Rules 1–22, harness-first memory/AIDB checkpoints, and 6-dimension activation gate (Definition of Done).
- Dispatch sub-agents with slimmed-down, token-efficient payloads: bounded objective (1–2 sentences), exact file paths and line ranges (by reference), constraints, and acceptance criteria. Never pass full conversation transcripts, multi-MB histories, or unreferenced document dumps.
- Ensure dependencies needed by the slice are committed (or explicitly named), deliverable paths are visible (shared worktree/absolute path), and quota headroom exists (Rule 18). Persistent sub-orchestrators use `aq-worktree new --name <n> --base <branch>`.
- Gate once upon integration: primary orchestrator runs `tier0-validation-gate.sh` and verifies live functionality.

**Sub-Agents (delegates receiving prompts):**
- Operate with slim, token-efficient baseline tools (`lean-ctx`, `agrep`, `acat`, `als`, `asum`, targeted edit tools, syntax checks).
- **On-demand tool & capability reachability:** Sub-agents retain full access to any system tool or package when needed. Reach any package in pinned nixpkgs live via `aq-tool <pkg> [args...]` (`scripts/ai/aq-tool`) without restart, rebuild, or permission barrier. Query AIDB (`error-solutions`) or `aq-hints` on-demand if contextual ambiguity arises.
- Work from the bounded prompt only; read only named files/line ranges. Do not forward or reconstruct conversation history.
- Skip session-start hydration (`aq-resume`, `aq-prime`, `aq-session-start`); the orchestrator already supplied the context.
- Never run `tier0-validation-gate.sh` or `aq-qa`; run only the focused test named in the prompt.
- If blocked (missing dependency, unreadable path, ambiguity, quota/rate limit), STOP and report the exact blocker in <=3 lines. Do not widen scope or retry beyond Rule 6.
- Do not commit, stage, or push unless the prompt says so.
- **Validation output required:** Paste actual command output (tail) for every validation step in your hand-back report; claimed-but-unshown validation is treated as not run, and the orchestrator re-validates.
- **Worktree isolation:** Never run `git stash`, `git switch/checkout <branch>`, `git branch -m/-D`, or `git pull` outside your assigned worktree; verify `git rev-parse --show-toplevel` equals your worktree before any git write, and run repo tools (generators, gates) via your worktree's own path — a main-checkout copy writes to the main checkout.
- **Fixture secrets at runtime:** Tests build fake secrets at runtime (string concatenation), never as token-shaped literals (github_pat_…, PEM blocks).
- **Bridge-managed handoff:** For bridge-managed delegates (delegate-to-codex/local/antigravity), leave changes staged and uncommitted unless the prompt explicitly says to commit.
