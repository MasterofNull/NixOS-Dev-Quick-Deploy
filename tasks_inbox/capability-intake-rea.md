# Capability Intake Review: rea-reverse-engineering

Reference skills: `capability-intake`, `rea-reverse-engineering`, `security-scanner`

## Audit Verdict: ACCEPTED_WITH_MITIGATIONS

### Summary:
REA (Reverse Engineer Anything) provides local reverse engineering and decompilation across JavaScript/Electron applications, .NET assemblies, and native binaries for the software dev factory.

### Mitigations Required:
1. **Pinned Version / No Floating Spec**: Pinned to version `0.1.0`. `npx -y @latest` is dropped from instructions and disallowed by policy.
2. **Local Hermetic Execution**: All reverse engineering analysis executes locally in isolated quarantine workspaces (`/tmp/rea-quarantine/` or agent scratch directories).
3. **Network Isolation**: Process execution is denied external network egress (`bwrap --unshare-all`).
4. **Credential Scrubbing**: Process environment scrubs ambient credentials (`SOPS_*`, `SSH_AUTH_SOCK`, `/run/secrets/*`).
5. **Tool Allowlist**: Only approved allowlisted tools (`analyze_javascript_application`, `analyze_dotnet_assembly`, `analyze_native_binary`, `rea_session_evidence`) may be exposed to agent runtimes.
6. **License Verification**: Upstream project is verified MIT licensed.

### Status:
Candidate intake admission closed out with mitigations. Sandboxed execution launcher (W1-S2) is scheduled to enforce runtime bwrap isolation.
