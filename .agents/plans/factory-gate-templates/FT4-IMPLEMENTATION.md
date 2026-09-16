# FT-4 implementation boundary

`aqd workflows retrofit` is now preview-only unless passed an exact current
`--confirm-retrofit <preview-digest>`. The installer hashes the pristine bundle,
Git config, executable original hooks, preserved target files, planned rendered
gate bytes/check configuration, writes, and hook routing. Records are canonical
typed length-framed JSON records containing path, type, mode, and content digest;
they do not concatenate raw file contents. A changed target, bundle, or scanner
tool availability invalidates confirmation before any write.

The focused proof holds CLI parameters constant while changing a controlled
scanner from unavailable to available, and re-partitions the same binary byte
stream across two existing files. Both cases stale the preview before writes.

FT-4 supports ordinary local `.git` metadata with the default hooks path only.
Git redirects, shared metadata, symlinked config/hooks, configured external hook
paths, unsafe ancestors, and existing factory destinations are refused. Existing
project instructions, CI, tracker, and manifest destinations are retained rather
than overwritten. The original local Git config is copied byte/mode-preserving
to the previewed `.factory/gate-backups/<digest>/.git-config` before hook routing.

The retrofit installs factory hook bodies outside `.githooks`, then creates
wrappers. Every executable original hook is routed with its original arguments,
stdin, cwd, and failure result; original `pre-commit` and `commit-msg` run before
their factory counterparts. This is cooperative hook composition, not a claim of
same-user tamper resistance. No target build, test, lint, hook, or dependency
command runs during preview or install; disposable fixtures provide execution
evidence.

R1 hardening refuses existing enforcement components (including a project
`scripts/governance/gate-runner`) rather than preserving a possible bypass.
Archive destinations and every ancestor are checked before copying Git config;
symlinked archive paths are refused. Router scripts use the installed absolute
target root rather than `git rev-parse`, so an original hook still receives its
Git-provided cwd, arguments, stdin, and exit status when invoked from `.git`.
