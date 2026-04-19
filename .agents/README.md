# `.agents/` Directory Structure

This directory follows the **strands-agents SOP (Standard Operating Procedure)** pattern for organizing workflow artifacts and agent outputs, while preserving existing project-specific directories.

## Directory Layout

```
.agents/
├── summary/      # [NEW] Documentation and summaries (always commit)
├── planning/     # [NEW] Design decisions and plans (often commit)
├── tasks/        # [NEW] Task breakdowns and checklists (optionally commit)
├── scratchpad/   # [NEW] Working files and temporary artifacts (never commit - .gitignore)
│
├── plans/        # [EXISTING] Implementation plans and roadmaps
├── reports/      # [EXISTING] Session and phase completion reports
├── designs/      # [EXISTING] Architecture and design documents
├── audits/       # [EXISTING] System and code audits
├── research/     # [EXISTING] Research notes and investigations
└── issues/       # [EXISTING] Tracked issues and problems
```

## Strands SOP Pattern (New Directories)

## Usage Guidelines

### `summary/`
- **Purpose**: Final documentation, executive summaries, and completed workflow reports
- **Git Policy**: Always commit these files
- **Examples**:
  - Workflow completion reports
  - Analysis summaries
  - Decision records
  - Post-mortem documentation

### `planning/`
- **Purpose**: Design decisions, architectural plans, and implementation strategies
- **Git Policy**: Often commit (team-reviewable planning artifacts)
- **Examples**:
  - Technical design documents
  - Implementation roadmaps
  - Architecture decision records (ADRs)
  - Phased execution plans

### `tasks/`
- **Purpose**: Task breakdowns, checklists, and work-in-progress tracking
- **Git Policy**: Optionally commit (depends on team workflow)
- **Examples**:
  - Sprint task lists
  - Implementation checklists
  - Bug tracking artifacts
  - Test coverage plans

### `scratchpad/`
- **Purpose**: Temporary working files, experiments, and transient artifacts
- **Git Policy**: Never commit (excluded in .gitignore)
- **Examples**:
  - Draft notes
  - Experimental code snippets
  - Temporary analysis files
  - Debug traces

## Integration with AI Harness

This structure integrates with:
- **MCP Client**: Helper functions in `ai-stack/local-orchestrator/mcp_client.py`
- **SOP Engine**: Workflow execution writes artifacts to appropriate directories
- **Hybrid Coordinator**: Workflow planning and execution APIs

## Strands-Agents Pattern

This directory structure is inspired by the [strands-agents/agent-sop](https://github.com/strands-agents/agent-sop) pattern, which organizes agent workflow artifacts in a standardized, version-control-friendly manner.

Key principles:
1. **Clear separation** between permanent and temporary artifacts
2. **Git-friendly** organization that preserves important decisions
3. **Consistent structure** across different workflows and agents
4. **Self-documenting** hierarchy that explains artifact lifecycle

## Existing Project Directories (Preserved)

### `plans/`
- **Purpose**: Implementation plans, roadmaps, and phase execution documents
- **Legacy**: Contains historical project plans and phase completions
- **Mapping**: Similar to `planning/` but more project-specific

### `reports/`
- **Purpose**: Session completion reports, validation reports, and summaries
- **Legacy**: Historical session summaries and phase validations
- **Mapping**: Similar to `summary/` but for completion reports

### `designs/`
- **Purpose**: Architectural designs and system integration documents
- **Legacy**: Contains system architecture and integration designs
- **Mapping**: Architectural subset of `planning/`

### `audits/`
- **Purpose**: System audits, code reviews, and assessment reports
- **Legacy**: Contains deployment and feature audits
- **Mapping**: Quality assurance artifacts (can go in `summary/` or separate)

### `research/`
- **Purpose**: Research notes, investigations, and exploratory work
- **Legacy**: Technical research and exploration artifacts
- **Mapping**: Can use `scratchpad/` for WIP research, `summary/` for conclusions

### `issues/`
- **Purpose**: Issue tracking, problem documentation, and resolutions
- **Legacy**: Contains tracked issues and their resolutions
- **Mapping**: Similar to `tasks/` but for issue tracking

## Migration Strategy

**For new workflows**: Use the strands SOP pattern (`summary/`, `planning/`, `tasks/`, `scratchpad/`)
**For existing workflows**: Continue using existing directories as needed
**Hybrid approach**: Workflows can use both structures as appropriate

The strands pattern directories are optimized for SOP-based workflows, while existing directories preserve project history and domain-specific organization.

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Agent behavior and workflow guidance
- [docs/agent-guides/40-HYBRID-WORKFLOW.md](../docs/agent-guides/40-HYBRID-WORKFLOW.md) - Hybrid workflow model
- [.agent/workflows/](../.agent/workflows/) - Existing workflow evidence (alternate location)
