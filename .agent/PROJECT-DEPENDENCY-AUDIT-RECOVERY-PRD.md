# Dependency audit recovery

## Root cause

The hosted security audit selects Python 3.11. AIDB now requires NumPy >=2.5.5, which requires Python >=3.12. The audit could scan the other two in-scope manifests and fail resolving AIDB before an advisory report was produced. The repository declares Python 3.13 in .python-version. The existing audit summary reported a count without identifying the affected file.

## Proposed change

Use actions/setup-python's python-version-file input for the security job. Identify failed manifest paths and whether the scanner returned an unexpected exit code or its report was rejected. Publish bounded diagnostics and retain the existing nonzero exit in CI. Advisory policy and manifest discovery are outside this recovery.

## Acceptance and review

Run the audit gate regression tests, then run the actual scanner under Python 3.13 on all three in-scope requirements files. On a draft pull request, inspect the hosted security job and artifact for coverage of three manifests and report any remaining findings independently of coverage. Record planning and code review separately, with the subject commit. Landing requires the repository's review process and owner authorization.

## Rollback

Revert this slice if it causes a workflow regression. A revert would restore the Python mismatch and its partial coverage until corrected.
