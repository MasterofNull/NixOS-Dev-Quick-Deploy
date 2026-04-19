---
name: Codebase Analysis SOP
description: Standard procedure for analyzing codebases systematically
version: 1.0.0
parameters:
  target_directory: "."
  depth: "full"
---

# Codebase Analysis SOP

This SOP defines the standard procedure for performing comprehensive codebase analysis.

## Prerequisites

1. MUST have read access to target codebase
2. SHOULD have git repository initialized
3. MAY use automated analysis tools

## Discovery Phase

1. MUST identify project structure and technology stack
   - Examine directory layout
   - Identify primary languages and frameworks
   - Locate configuration files

2. MUST analyze dependency management
   - Check package.json, requirements.txt, Cargo.toml, etc.
   - Identify direct and transitive dependencies
   - Flag outdated or vulnerable dependencies

3. SHOULD review build and deployment configuration
   - Examine build scripts and CI/CD pipelines
   - Check deployment manifests
   - Identify environment-specific configurations

## Code Quality Assessment

1. MUST evaluate code organization
   - Assess module structure and separation of concerns
   - Check for consistent naming conventions
   - Identify architectural patterns

2. SHOULD perform static analysis
   - Run linters and formatters
   - Check for common anti-patterns
   - Measure code complexity metrics

3. MAY conduct security scanning
   - Run SAST tools if available
   - Check for hardcoded secrets
   - Verify secure coding practices

## Documentation Review

1. SHOULD assess documentation completeness
   - Check for README and contributing guidelines
   - Verify API documentation exists
   - Review inline code comments

2. MAY evaluate documentation quality
   - Check for outdated information
   - Verify examples are functional
   - Assess clarity and comprehensiveness

## Testing Infrastructure

1. MUST identify test coverage
   - Locate test files and frameworks
   - Measure coverage percentage
   - Identify untested critical paths

2. SHOULD evaluate test quality
   - Check for unit, integration, and e2e tests
   - Assess test maintainability
   - Verify tests are passing

## Output Requirements

1. MUST generate analysis report
   - Summarize findings in `.agents/summary/codebase-analysis.md`
   - Include metrics and statistics
   - Provide actionable recommendations

2. SHOULD create issue tracker entries
   - File issues for critical findings
   - Tag with appropriate labels
   - Assign priority levels

3. MAY produce visualization artifacts
   - Generate dependency graphs
   - Create architecture diagrams
   - Export metrics dashboards
