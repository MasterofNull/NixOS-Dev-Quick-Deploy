# Skill Backup Policy

Last Updated: 2026-02-16
Owner: Phase 27 governance track

## Policy

Use Git history/tags for skill backup and restore.

Do not create filesystem backup trees such as:
- `.claude/skills.backup-*`
- `skills-backup-*`
- duplicate `SKILL.md` trees outside approved roots

## Approved Skill Roots

- `.agent/skills/` (canonical)
- `ai-stack/agents/skills/` (intentional mirror)
- `archive/` (historical/testing fixtures only)

## Backup/Restore Procedure

1. Create a commit before major skill edits.
2. Create annotated tags for release checkpoints.
3. Restore from Git when needed:
   - `git show <tag>:<path>`
   - `git checkout <tag> -- <path>` (explicit, scoped restore)

## CI Enforcement

- `scripts/check-skill-source-of-truth.sh`
- `scripts/validate-skill-references.sh`
- `scripts/lint-skill-external-deps.sh`
