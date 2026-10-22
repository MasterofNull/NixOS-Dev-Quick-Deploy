---
name: rea-reverse-engineering
description: Reverse engineering and binary/application deep analysis workflow based on REA (Reverse Engineer Anything).
---

# REA: Reverse Engineer Anything Skill

## Purpose

Use this skill when reverse engineering, decompiling, or inspecting native binaries, Electron/JavaScript applications, .NET assemblies, or runtime software behavior for the software dev factory.

REA connects the agentic software dev factory to deep local reverse engineering capabilities across three layers:
1. **JavaScript & Electron Applications**: Extracts modules, imports, Electron preload/IPC boundaries, and state without running untrusted code.
2. **.NET Assemblies**: Decompiles CIL bytecode, recovers types, methods, and structure.
3. **Native Binaries (x86/x64/ARM/DOS)**: Deep disassembly, decompilation, and pseudocode recovery via local analysis engines (Ghidra, Hopper, IDA).

## Tools & Tool Allowlist

The capability intake registry declares the following approved tools for REA:
- `analyze_javascript_application`: Recovers modules, imports, and IPC channels from JS/ASAR packages.
- `analyze_dotnet_assembly`: Decompiles and extracts classes/methods from .NET PE binaries.
- `analyze_native_binary`: Disassembles and decompiles native machine code into pseudocode.
- `rea_session_evidence`: Emits structured reverse engineering findings and reconstruction proofs.

## Hard Rules & Sandboxing

1. **Local-Only Analysis**:
   - All reverse engineering operations MUST execute locally. Never upload target binaries, keys, or disassembled assets to external cloud APIs or unapproved endpoints.
2. **Quarantine Scratchpad Isolation**:
   - Targets under examination must be placed in a dedicated scratchpad directory:
     `<appDataDir>/brain/<conversation-id>/scratch/rea-targets/` or isolated `/tmp/rea-quarantine/`.
   - Never decompile or mutate live host binaries in place.
3. **Secret & Credential Masking**:
   - Ambient environment credentials (`SOPS_*`, SSH agent sockets, `/run/secrets/*`) are strictly scrubbed from decompilation sub-processes.
4. **License & Ethical Use**:
   - REA analysis is strictly for lawful interoperability, defect remediation, security analysis, and software development factory reconstruction of approved targets.

## Usage & Commands

Audit candidate status:
```bash
scripts/ai/aq-capability-intake audit rea-reverse-engineering --json
```

Inspect an Electron / JavaScript target:
```bash
scripts/ai/mcp-rea-sandboxed analyze-javascript-application /path/to/extracted-app --json
```

## References

- Capability Registry: `config/agent-capability-intake-candidates.json`
- Intake Audit CLI: `scripts/ai/aq-capability-intake`
- Upstream: `https://github.com/morluto/rea`
