# Capability Intake Review: mcp-admission-controller

Reference skills: `capability-intake`, `mcp-server`, `security-scanner`

## Audit Verdict: REQUEST_REVISION

### Evidence:
1. `aq-capability-intake` currently performs basic static parsing of metadata in [agent-capability-intake-candidates.json](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/agent-capability-intake-candidates.json) and blocked tool name lists.
2. It does NOT evaluate actual tool parameter schemas for parameter injection vulnerabilities (e.g. checking if parameters accept shell commands or file paths without strict regex/enum checks).
3. Blocked tool names check is exact match only, meaning variants like `execute_shell_run` could slip through.
4. Package installers (`npx`, `npm`, `pip`, etc.) are flagged, but setup scripts within third-party packages are not analyzed.

### Proposed Test Cases:
1. Test a candidate claiming to be read-only but specifying a parameter in its schema named `command_override` with type `string`.
2. Test an installation step containing a package name with typo-squatted naming (e.g., `playwrigt-mcp`).

### Follow-up Patch Scope:
1. **[MODIFY]** [aq-capability-intake](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/aq-capability-intake): Add a JSON Schema validator to scan tool parameter definitions and reject tools with parameters containing names like `exec`, `cmd`, `shell`, `args` unless they are bound to a strict enum.
2. **[MODIFY]** [tool_security_auditor.py](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/shared/tool_security_auditor.py): Implement fuzzy-match checking (using soundex or Levenshtein distance) against blocked tool name lists.

## Resolution (2026-07-23) — RESOLVED

An Antigravity-authored candidate diff attempted this patch but was independently reviewed
(`.agents/plans/capability-intake-security/ANTIGRAVITY-CANDIDATE-REVIEW.md`, VERDICT: REVISE) and found
defective: the schema validator's keyword set omitted `command` (`"cmd"` is not a substring of `"command"`,
so both the bare keyword and the finding's own literal test case, `command_override`, sailed through), and
recursion never descended into `items`/`additionalProperties`/`patternProperties`/`$defs`/`definitions`, so
any nested-object or array-of-objects schema hid a command param trivially. This revision fixes both gaps in
`scripts/ai/aq-capability-intake:_validate_schema`:

- Restricted-keyword set is now `{exec, cmd, command, shell, entrypoint, run}` (owner-decided, matched by
  substring containment so `command_override` is caught), with `args` handled separately as a needs-review
  signal rather than a hard block (owner decision — `args` is commonly legitimate, e.g. `search_args`,
  `extra_args`; a hard block on it would false-block real tools).
- Recursion now covers `properties`, `items` (array/tuple form), `additionalProperties`, `patternProperties`,
  `$defs`/`definitions`, and `allOf`/`anyOf`/`oneOf`.
- A flagged param is admitted only if bound to a strict `enum`, a regex `pattern`, or a bounded `maxLength`
  (owner decision — enum-only was rejected as too brittle for legitimate free-form tools).
- Fuzzy blocked-tool-name matching (item 2, in `tool_security_auditor.py`) was already sound in the candidate
  and is unchanged.

Regression-tested in `scripts/testing/test-capability-intake.py`: the finding's own `command_override` case,
a bare `command` case, a nested array-of-objects case, and a nested map (`additionalProperties`) case all now
`blocked`; enum/pattern/maxLength-admitted params and an `args`-only param (`needs-review`, not blocked) are
covered by new dedicated test cases. Verified genuinely load-bearing: reverting the keyword-set fix or the
nested-schema recursion each independently reproduces the original bypass and fails the corresponding new
test with `AssertionError`.
