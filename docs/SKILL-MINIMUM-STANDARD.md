# Skill Minimum Standard

Last Updated: 2026-02-16
Owner: Phase 27 skill governance

## Minimum Viable Skill (MVS)

A skill can be valid with one file:
- `SKILL.md`

Required in `SKILL.md` frontmatter:
- `name`
- `description`

Recommended:
- `license`
- maintenance/version stanza in the body

## Progressive Disclosure is Optional

Use extra folders only when needed:
- `scripts/`
- `references/`
- `assets/`

Do not split content by default. Start with single-file SKILL-first and add files only when complexity requires it.

## Reference Depth Constraint

Relative references from `SKILL.md` must be one hop max:
- allowed: `./reference.md`
- allowed: `./references/topic.md`
- blocked: `./references/deeper/topic.md`

Rationale: reduce brittle link graphs and file-not-found errors.

## Enforcement

CI/governance lint scripts:
- `scripts/lint-skill-template.sh`
- `scripts/validate-skill-references.sh`
- `scripts/check-skill-source-of-truth.sh`
