# Dependency-bump review criteria

This PR only changes dependency manifests. Review the upstream change, not just the diff. Web access is expected.

1. Name each package and its old -> new version range.
2. Read the upstream release notes / changelog / breaking-change list for the WHOLE range, not only the last release.
3. List removed or renamed APIs, flags and options, changed defaults, runtime/Python/platform requirement changes, and data or config migrations.
4. Grep the worktree for our usage of the affected package APIs and say whether any usage is affected.
5. Say whether the new floor is installable for our runtime (for example Python version constraints, platform wheels).
6. Return PASS only when nothing relevant breaks. Otherwise return REQUEST_CHANGES and name the adaptation needed.
7. End with a substantive `## Upstream changes reviewed` section. For each affected package, provide a separate evidence block with these exact fields and concrete values: `Package and range: <package> <old> -> <new>`; `Release notes: <one or more https:// upstream links>`; `Authority: Nix` or `Authority: manifest`; and `Input path: <concrete repository input path>`. A fast-lane PASS supports exactly one package only when the actual `origin/main...HEAD` unified diff has one replacement of a numeric dotted version using the same `==` or `>=` operator; its package and old/new values must match that replacement. Use the regular review path for multiple packages, lockfile-only changes, or ambiguous manifest changes.
8. Add `Closure: changed` or `Closure: unchanged` and `Closure evidence: <actual comparison command with both operands>; <result>`. For an unchanged closure, name the comparison and its affirmative result, such as `git diff --no-index /tmp/closure-before /tmp/closure-after; exit 0 (no differences)`. For a changed closure, name a positive difference result, such as `nix store diff-closures /nix/store/old /nix/store/new; differences found`. Use `no differences` or `exit 0 (no differences)` for unchanged, and `differences found` or `exit 0, differences found` for changed.
9. For `Closure: changed`, also add `Deployed runtime: <concrete deployed service or command>` and `Runtime result: <passed, success, ok, healthy, running, active, or exit 0>`. The fast-lane gate validates this evidence's shape; the trusted reviewer remains responsible for validating the facts.
10. Return REQUEST_CHANGES when this evidence is missing or ambiguous; do not infer it from the manifest diff alone.
