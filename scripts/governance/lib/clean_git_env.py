#!/usr/bin/env python3
"""Environment scrubbing for test/QA subprocess launches (see clean-git-env.sh)."""
import os

# Keep in sync with scripts/governance/lib/clean-git-env.sh.
CLEAN_GIT_ENV_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_PREFIX",
    "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES",
)


def clean_git_env(env=None):
    """Return a copy of env (default os.environ) without repo-locating GIT_* vars."""
    base = os.environ if env is None else env
    return {k: v for k, v in base.items() if k not in CLEAN_GIT_ENV_VARS}
