# PROJECT-AQ-WORKSPACE-AGY-NATIVE-CLI-PRD

**Status**: IN_PROGRESS
**Owner**: AI Stack Maintainers / Operator
**Date**: 2026-10-12
**Slice**: `launcher-native-agy-cli`

---

## 1. Objective & Problem Statement

The operator wishes to conduct all human-to-agent and multi-agent interaction entirely inside the centralized terminal workspace (`aq-workspace` / `aq-agent-launcher`), utilizing their personal Google subscription without ever having to open or run the Google Antigravity IDE GUI package.

Previously:
1. `aq-agent-launcher` inspected the environment for `claude` (Claude Code CLI) and `codex` (Codex CLI), launching them directly as native processes.
2. For `gemini|antigravity`, `aq-agent-launcher` fell back to `python3 aq-agent-window --lane gemini`, routing through Switchboard HTTP endpoints rather than running the user's native subscription CLI directly in the pane.
3. Google deprecated the old `@google/gemini-cli` npm package, replacing it with the official native binary `agy` (`~/.local/bin/agy`), which supports browser-based OAuth with Google subscriptions (Google One AI Premium / Google AI Pro / Code Assist).

---

## 2. Technical Architecture & Changes

1. **`scripts/ai/aq-agent-launcher`**:
   - Update `gemini|antigravity` case to detect `agy` or `gemini` executable via `command -v agy 2>/dev/null || command -v gemini 2>/dev/null || echo "$HOME/.local/bin/agy"`.
   - Wire `NEW_CMD=("$AGENT_BIN")` and `RESUME_CMD=("$AGENT_BIN" "--continue")`.
   - Update `get_auth_status()` to report Google Subscription Native CLI (`agy`) status.
   - Update `launch_agent("login")` to invoke `agy` or `gemini` directly to trigger the browser OAuth subscription flow.
2. **`config/zellij/aq-agentic-workspace.kdl`**:
   - Update pane labels from `Google Antigravity / Gemini 3.8-Flash (Gemini CLI)` to `Google Gemini (Subscription CLI)` for terminal clarity.
3. **`scripts/ai/aq-workspace`**:
   - Clarify help messages indicating that `aq-workspace gemini` launches the native subscription CLI.
4. **`scripts/testing/test-aq-agent-launcher.py`**:
   - Add unit test verifying that `gemini` lane selects the native CLI binary with `--continue` for resume and direct execution for fresh sessions.

---

## 3. Definition of Done & Activation Gate

- **Integrated**: Called directly from `aq-workspace` and `aq-agent-launcher`.
- **Turned ON**: Active whenever `gemini` or `agy` is launched in the terminal.
- **Functionally Validated Real-World**: Verified with mock and live binary checks; `bash -n` clean; tests pass.
- **Observable**: Displayed in `get_auth_status` and Zellij pane status bars.
- **Intervenable**: Operates with standard interactive keyboard shortcuts (`[1]` clean, `[2]` resume, `[4]` login, `[q]` quit).
- **PM-Tracked**: Documented in PR, `PULSE.log`, and `RESUME.json`.
