# Repository Guidelines

- Prefer POSIX shell syntax in scripts unless the file already relies on Bash-specific features.
- Keep shellcheck compliance in mind when modifying shell scripts; add inline `shellcheck` directives only when unavoidable.
- Maintain descriptive logging for long-running operations and keep user-facing messages actionable.
- Preserve template placeholders (e.g., `VERSIONPLACEHOLDER`, `HASHPLACEHOLDER`) and comments that explain synchronization requirements.
- Update accompanying helper scripts when modifying template logic so behaviour stays consistent between generated files and runtime tooling.
- When adding documentation files like this one, keep the tone concise and future-oriented.
