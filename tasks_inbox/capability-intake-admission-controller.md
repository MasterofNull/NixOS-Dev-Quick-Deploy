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
