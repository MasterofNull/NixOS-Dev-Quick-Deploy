# .agents

Progressive-disclosure planning layer for this repository.

## Purpose
- Store phase and slice plans under `.agents/plans/`.
- Keep plans small, explicit, and evidence-driven.
- Keep this layer focused on planning artifacts only.

## Structure Contract
- Place all implementation plan files in `.agents/plans/`.
- Do not store command specs here (`.claude/commands/` owns those).
- Do not store PRD/global rules here (`.agent/` owns those).
- Prefer one logical slice per plan file.

## Layout
```text
.agents/
└── plans/
    ├── README.md
    ├── phase-template.md
    └── phase-XX-*.md
```

## Validation
```bash
scripts/governance/repo-structure-lint.sh --staged
```
