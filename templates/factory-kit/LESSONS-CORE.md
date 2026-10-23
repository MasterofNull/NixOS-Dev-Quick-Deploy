# Core Lessons for Autonomous Software Factory

Canonical operational lessons compiled from production development across multi-agent harnesses:

## 1. Relative Hooks Path
`core.hooksPath` must always be configured with repository-relative paths (`.githooks`, avoiding absolute paths). Absolute paths break worktree isolation, fail across distinct machines, and leak host paths into committed git configs.

## 2. CI/Local Parity
Checks executed in local pre-push and PR CI must use the exact same manifest runner (`run-ci-checks.sh` backed by `config/ci-checks.json`). Testing drift causes merge failures and false confidence.

## 3. Ephemeral /tmp and Deployment State
Never rely on volatile `/tmp` storage across daemon lifecycles or reboots. Runtime state must reside under tracked project paths or persistent directories declared declaratively.

## 4. Stale Deploy Sources & Divergence
Never deploy or test uncommitted changes in production paths without a clean commit anchor. Every operational cycle must bind to explicit commit SHAs and verified tree digests.
