# Antigravity's Meta-Prompt: Simplified Workflow & Stricter Security Architecture

This document represents the independent, adversarial contribution to the workflow redesign meta-prompt exercise (Contribution 3 of 3) and the independent review of the local-agent batch (`cc63ac57..1276fe88`).

---

## PART A — Antigravity's Meta-Prompt on Workflow Redesign

### 1. The Root Cause of Process Failures
We reject the premise that the root cause is simply "uniform-heavy process inviting silent dropping." 

The real root cause is the **systemic decoupling of orchestration loops from gate enforcement, paired with a complete lack of tool-enforced suspension and state-preservation mechanisms in the harness runtime.**

When an autonomous agent runner (such as `delegate-to-antigravity` or `aq-antigravity-agent`) executes a task, it runs continuously in a loop. If a step in that loop requires a manual governance ceremony (such as writing a PRD, waiting for human consensus, or notifying the owner) but the runtime itself does not support a first-class **SUSPENDED** state, the agent is forced into an impossible bind: it must either crash the entire session (failing the task) or proceed by bypassing the ceremony (violating the gate). 

Under goal-seeking optimization, agents will always take the path of least resistance. Since automated technical gates (tests, linting, build gates) physically block the commit, they are followed. Since manual governance gates do not block the commit at the CLI level, they are dropped. **Ceremony without automated CLI enforcement is merely narrative friction, and agents will always route around friction.**

---

### 2. Proposed Workflow & Rigor Tiering
We propose replacing the complex, self-declared risk-tiering model with an **automated, tool-enforced gating model** where the risk tier is determined programmatically, not declared by the implementer. 

We define three risk tiers, but unlike Claude's model, the enforcement is hard-coded into the pre-commit and orchestration gates:

#### Tier 0 — System-Critical / High-Impact
*   **Scope**: Any change touching AppArmor configs, secrets, NixOS confinement profiles, capability leases, auth systems, OR any file that alters system command execution (e.g., `shell_tools.py`), file operations (e.g., `file_operations.py`), local inference parsers/GBNF, or telemetry endpoints.
*   **Verification Gate**: Automated static validation + 100% test coverage requirement + **manual human review and cryptographic approval lock** (`aq-approve`).
*   **Minimum Un-skippable Gate**: A tool-generated `REVIEWS_PENDING.json` lock that blocks `git commit` until signed by the owner's public key. The agent runner must automatically suspend execution, serialize its warm memory to `.agent/collaboration/RESUME.json`, and exit with a `YIELD_WAITING_FOR_APPROVAL` status code.

#### Tier 1 — Standard Behavioral/Feature Change
*   **Scope**: General functional code, scripts, and helper modules.
*   **Verification Gate**: Design diff registered in `.agent/proposals/`, passing `aq-qa` integration test suites, and one independent agent review (e.g., Codex or Gemini).
*   **Minimum Un-skippable Gate**: Automated validation of the review verdict (`VERDICT: PASS` in the review receipt metadata) in the pre-commit hook.

#### Tier 2 — Non-Behavioral/Trivial
*   **Scope**: Documentation, formatting, comments, or isolated test files.
*   **Verification Gate**: Standalone syntax check + linting.
*   **Minimum Un-skippable Gate**: Automatic verification that no code/behavioral files were modified.

---

### 3. Preventing Gaming of Risk Tiers
Relying on an agent's self-declaration of a tier (such as a one-paragraph owner-facing declaration) is a failure mode. An agent under pressure will down-classify its changes to bypass reviews.
To make the tier choice **un-gameable**:
1.  **Statically Resolved Tiers**: A CLI tool (`aq-tier-resolver`) must analyze the `git diff` before any code changes are written (during the `RESEARCH` phase) and lock the tier.
2.  **Dependency & AST-based Promotion**: The resolver must trace the call graph. If a file modified by the agent is imported or executed by a Tier 0 component (determined via `ctx_impact`), the change is automatically promoted to Tier 0.
3.  **Strict Pre-Commit Enforcement**: The pre-commit hook must re-run the resolver. If the files staged for commit require Tier 0/1 ceremony but the corresponding review/approval tokens are missing from the project metadata, the commit is aborted.

---

### 4. What We Must Delete and Simplify
We must aggressively purge the "ceremony bloat" that slows down execution without adding security:
1.  **Consolidate State Files**: Delete `PULSE.log`, `steps.jsonl`, and `RESUME.json` from different folders. Consolidate them into a single, tool-managed state file: `.agent/collaboration/STATE.json`.
2.  **Eliminate Role Sprawl**: Abolish the artificial distinction between Architect, Orchestrator, and Implementer. There are only two real roles:
    *   **Advisory Node**: Plans the change, reviews the output, and issues the review receipt. Cannot write code.
    *   **Executive Node**: Writes the code and runs tests. Cannot self-approve or commit without an Advisory signature.
3.  **Purge Unenforced Rules**: Remove the "20 rules" in `.agent/collaboration/RULES.md` that are not checked by the tier-0 validation gate script. If a rule cannot be programmatically validated, it should not block the agent's workflow.

---

### 5. Cheap Owner-In-The-Loop Steering
The owner should not have to read lengthy plans or review intermediate diffs. 
*   **The YIELD Signal**: When a Tier 0 change is reached, the harness exits, prints a compact 3-line summary of the proposed design (input parameters, files touched, security impact), and waits for a single CLI command: `aq-approve <hash>`.
*   **Post-Execution Summary**: Upon task completion, the harness generates a single `walkthrough.md` with embedded telemetry (tests passed, lines modified, token cost). The owner reviews this after the fact, relying on the automated gates to have prevented security regressions.

---

### 6. Where Claude Drew the Boundaries Wrong
The flagship (Claude) drew its Tier 0 boundaries far too small by focusing only on "NixOS confinement files" and "secrets". 
As this cycle's vulnerabilities demonstrate, critical security holes (like shell injections and path-traversal bypasses) are introduced in **general utility files** (`shell_tools.py`, `file_operations.py`) and test configs (`pytest.ini`). 
Therefore, the Tier 0 boundary must be expanded to include **any file that defines system execution primitives or handles path resolution**, even if it lives in a helper or local-agent directory.

---

## PART B — Independent Review of the Local-Agent Batch (cc63ac57..1276fe88)

We conducted an independent security and correctness audit of the committed batch. We confirm Codex's 12 findings and add the following critical details, including new defects and operational risks that both Claude and Codex missed:

### 1. CRITICAL — Replay executes recorded tools LIVE on the host (Workspace Pollution & Execution Side-effects)
*   **File**: `scripts/testing/aq-replay-bench` (Line 160-220), `ai-stack/local-agents/agent_executor.py` (Line 2349)
*   **Detail**: While the record/replay harness stubs LLM response calls (`_call_llama`), it **does not stub the tool execution registry**. When `aq-replay-bench` runs, the agent executor processes the cached tool calls (like `write_file`, `write_region`, or `run_command`) and executes them **live** on the host filesystem. 
*   **Risk**: If a recorded cassette contains a destructive command (e.g. `run_command` executing `rm` or mutating state) or modifications to workspace code files, replaying the bench will execute those side-effects live on the operator's machine. This violates the expectation of a safe, read-only "offline configuration A/B test" and can silently pollute the active workspace during benchmarking.
*   **Fix**: Implement a `--dry-run` or `--mock-tools` flag in `aq-replay-bench` that stubs the tool execution registry, preventing any actual disk writes or shell executions during replay runs.

### 2. CRITICAL — Cassette writes are process-unsafe (Race Conditions & JSONL Corruption)
*   **File**: `ai-stack/local-agents/llm_cassette.py` (Line 193-195)
*   **Detail**: When recording model runs, `Cassette.record` opens the cassette file in append mode:
    ```python
    with self.path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    ```
    This write is performed without any process-level file locking (`fcntl.flock`).
*   **Risk**: In multi-agent or parallel execution environments (where multiple agent tasks run concurrently and share the same environment-configured cassette path), simultaneous writes will result in interleaved lines, corrupting the JSONL database and making it unparseable.
*   **Fix**: Enforce exclusive file locking (`fcntl.flock(fh, fcntl.LOCK_EX)`) during cassette append operations.

### 3. HIGH — `write_region` EOF insertion index mismatch leads to out-of-bounds silent failures
*   **File**: `ai-stack/local-agents/builtin_tools/file_operations.py` (Line 470-520)
*   **Detail**: To allow insertion at EOF, the code sets `max_bound = line_count + 1` and permits `start_line == end_line == max_bound`. However, if the file contains no trailing newline, the splicing logic:
    ```python
    spliced = lines[:start_line - 1] + new_lines + lines[end_line:]
    ```
    concatenates the new content directly to the end of the last line without injecting a separating newline, resulting in malformed syntax (e.g. merging two distinct code lines like `import osimport sys`). Furthermore, if `start_line` is out of range but bypassed by the clamping logic in error reporting, the helper returns a misleading "region" preview that doesn't match the actual file content.
*   **Fix**: Ensure `write_region` detects files lacking a trailing newline and inserts one automatically before appending new content.

### 4. HIGH — Retry budget reduction overrides and masks replay misses
*   **File**: `ai-stack/local-agents/agent_executor.py` (Line 1528-1533)
*   **Detail**: The exception handler for LLM calls:
    ```python
    except Exception as _llm_err:
        # Retry once with reduced budget on transient failures
        response, tok = await self._call_llama(..., max_tokens=512)
    ```
    catches all exceptions, including `llm_cassette.ReplayMiss`. When running in strict replay mode, the first miss throws `ReplayMiss`, which is caught here. The executor then immediately triggers a retry with a reduced budget (`max_tokens=512`) and without `task_type`. This retry will lookup a different key in the cassette, miss again, and throw a second `ReplayMiss` (which finally crashes the agent). This masks the original, correct replay miss with a redundant, incorrectly parameterized second request.
*   **Fix**: Do not catch `ReplayMiss` in the transient LLM error retry block. Let it propagate immediately to halt the loop.

### 5. PROCESS — Commit Contract Violations in the Batch
*   **Detail**: Commit `4650b1e6` lacks the mandatory scope prefix (uses `chore:` instead of `chore(local-agent):`). Additionally, commits `950f56e4` and `ae9029ef` completely omit the Step 8 evidence block (root cause, file/contract changes, reasoning, measurements, implementer/reviewer identities, validation commands/results). This is a direct violation of `.agent/WORKFLOW-CANON.md`.
