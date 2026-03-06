# Skill Distribution Manifest

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05

## Overview

This document describes the packaged skills available in the NixOS-Dev-Quick-Deploy AI stack for Claude Code and compatible agents.

## Skill Inventory

### Core Workflow Skills

| Skill | Command | Purpose | Dependencies |
|-------|---------|---------|--------------|
| prime | `/prime` | Load minimal project context | None |
| create-prd | `/create-prd` | Generate/refresh PROJECT-PRD.md | File system access |
| plan-feature | `/plan-feature` | Build implementation plan with context refs | Hybrid Coordinator |
| execute | `/execute` | Execute from plan file | Plan file, Hybrid API |
| commit | `/commit` | Commit isolated slice with evidence | Git |
| explore-harness | `/explore-harness` | Quick harness capability discovery | Hybrid Coordinator |

### Installation

Skills are located in `.claude/commands/` and are automatically loaded by Claude Code.

To install in another project:

```bash
# Copy skill definitions
cp -r .claude/commands/ /path/to/project/.claude/commands/

# Ensure CLAUDE.md references are updated
```

### Skill Definitions

#### /prime

Loads minimal project context for session initialization.

```markdown
# From .claude/commands/prime.md
Load minimal context from CLAUDE.md and essential files.
Focus on project structure and recent changes.
Do not load full documentation unless requested.
```

**Usage:**
```
/prime
```

#### /create-prd

Creates or refreshes the project requirements document.

```markdown
# From .claude/commands/create-prd.md
Analyze codebase structure and generate PROJECT-PRD.md.
Include: objectives, architecture, constraints, acceptance criteria.
Output to .agent/PROJECT-PRD.md
```

**Usage:**
```
/create-prd .agent/PROJECT-PRD.md
```

#### /plan-feature

Builds an implementation plan with context references.

**Usage:**
```
/plan-feature "Add user authentication"
```

#### /execute

Executes implementation from a plan file.

**Usage:**
```
/execute .agents/plans/phase-1.md
```

#### /commit

Commits the current isolated slice with evidence capture.

**Usage:**
```
/commit
```

#### /explore-harness

Quickly explores AI stack harness capabilities.

**Usage:**
```
/explore-harness
```

## AI Stack Skills (Extended)

These skills require the AI stack services to be running.

### ai-stack-qa

QA workflow for health checks and phase verification.

**Dependencies:** Hybrid Coordinator (:8003), AIDB (:8002)

**Usage:**
```
/ai-stack-qa
```

### health-monitoring

Health monitoring and diagnostics skill.

**Dependencies:** All AI stack services

### mcp-server

MCP server integration and tool discovery.

**Dependencies:** MCP bridge, tool registry

## Packaging for Distribution

### Minimal Package

For projects that only need core workflow skills:

```
.claude/
└── commands/
    ├── prime.md
    ├── plan-feature.md
    ├── execute.md
    └── commit.md
```

### Full Package

For projects with AI stack integration:

```
.claude/
├── commands/
│   ├── prime.md
│   ├── create-prd.md
│   ├── plan-feature.md
│   ├── execute.md
│   ├── commit.md
│   └── explore-harness.md
└── settings.json (optional)
```

### Integration Requirements

| Feature | Requirement |
|---------|-------------|
| Basic skills | Claude Code v1.0+ |
| Harness integration | Hybrid Coordinator running |
| RAG-enhanced planning | AIDB + Qdrant collections |
| Hints integration | Hint engine enabled |

## Version Compatibility

| Skill Version | Claude Code | AI Stack |
|---------------|-------------|----------|
| 1.0.0 | 1.0+ | 0.3.0+ |

## Customization

Skills can be customized by editing the markdown files in `.claude/commands/`.

Key customization points:
- Context loading depth
- Plan output format
- Commit message templates
- Evidence capture requirements

---

*See also: [SKILL-MINIMUM-STANDARD.md](../SKILL-MINIMUM-STANDARD.md)*
