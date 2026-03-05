# Naming & Label Conventions

Status: Active  
Owner: AI Stack Maintainers  
Last Updated: 2026-03-05

## Script Naming
- Prefer kebab-case for new script files.
- Keep wrapper shims when renaming legacy paths to avoid runtime breakage.
- Use subject-matter folders under `scripts/` (`ai/`, `deploy/`, `governance/`, `testing/`, etc.).

## Script Header Standard
- First line: shebang (`#!/usr/bin/env bash` or `#!/usr/bin/env python3`).
- Within first 8 lines include a purpose comment.
- Keep usage hints concise and accurate.

## Documentation Label Standard
- Active docs (especially `docs/operations/` and `docs/development/`) should include:
  - `Status:`
  - `Owner:`
  - `Last Updated:`
- Keep a single H1 heading per document.
- Use title-case headings for primary sections.

## Change Safety
- Do not rename files that are runtime-wired without updating all references.
- Keep naming-label reports out of tracked docs during routine checks:
  - default output: `.reports/naming-label-consistency-report.md`
  - publish to tracked docs only when intentionally updating governance docs:
    - `scripts/governance/check-naming-label-consistency.sh --publish-doc`
- Validate after naming/label changes:
  - `scripts/governance/check-doc-links.sh --active`
  - `scripts/governance/repo-structure-lint.sh --all`
  - `scripts/governance/quick-deploy-lint.sh --mode fast`
