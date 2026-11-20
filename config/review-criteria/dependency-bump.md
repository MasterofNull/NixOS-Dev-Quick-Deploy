# Dependency-bump review criteria

This PR only changes dependency manifests. Review the upstream change, not just the diff. Web access is expected.

1. Name each package and its old -> new version range.
2. Read the upstream release notes / changelog / breaking-change list for the WHOLE range, not only the last release.
3. List removed or renamed APIs, flags and options, changed defaults, runtime/Python/platform requirement changes, and data or config migrations.
4. Grep the worktree for our usage of the affected package APIs and say whether any usage is affected.
5. Say whether the new floor is installable for our runtime (for example Python version constraints, platform wheels).
6. Return PASS only when nothing relevant breaks. Otherwise return REQUEST_CHANGES and name the adaptation needed.
7. End with an "Upstream changes reviewed" list: package, range, relevant changes or "none relevant".
