# Write-region sandbox fixture evidence

2026-11-24 · `TIER0-WRITE-REGION-SANDBOX-FIXTURE`

## Root cause and fix

`wr-sandbox-outside-target-20261115` was recorded in
`pr-864-tier0-sandbox-fixture-occurrence`. The fixture tried to allocate an
outside target under `/var/tmp` or `~/.cache`. When those writes failed in the
restricted runner, it fell back to `/tmp`, which the production allowlist
permits. The handler therefore treated the supposed outside targets as allowed.

The fixture now creates `workspace` and `outside` as siblings under one resolved
`TemporaryDirectory`. It patches `file_operations.ALLOWED_BASE_PATHS` to allow
only the workspace for the duration of the test. A write inside the workspace
must succeed and update the file. Literal traversal, a symlink to the outside
sibling, and a direct absolute path must each return a path-validation error
and leave their target content intact. The patch restores the allowlist before
subsequent tests run.

## Local verification

The clean baseline was `HEAD` at `a47be3197`.

| Command | Clean HEAD | Changed tree |
| --- | --- | --- |
| `ruff check scripts/testing/test-write-region.py` on HEAD and `ruff check --no-cache scripts/testing/test-write-region.py` after the edit | Exit 0 | Exit 0, zero new diagnostics |
| `basedpyright scripts/testing/test-write-region.py` | Exit 1, four errors | Exit 1, the same four errors and zero new diagnostics |
| `python3 -m py_compile scripts/testing/test-write-region.py` | | Exit 0 |
| `PYTHONDONTWRITEBYTECODE=1 python3 scripts/testing/test-write-region.py` | | Exit 0, 62/62 checks passed |
| Full suite with `TMPDIR` set to a fresh directory under `/tmp` | | Exit 0, 62/62 checks passed |

The four existing type errors concern the optional import spec, its loader
and `exec_module`, and the optional `ToolCall`.

Compilation used a temporary bytecode cache outside the worktree:

```bash
python3 - <<'PY'
import os
import subprocess
import tempfile

with tempfile.TemporaryDirectory() as cache:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": cache}
    subprocess.run(["python3", "-m", "py_compile", "scripts/testing/test-write-region.py"], env=env, check=True)
PY
```

The restricted-`TMPDIR` run used:

```bash
python3 - <<'PY'
import os
import subprocess
import tempfile

with tempfile.TemporaryDirectory(prefix="wr-restricted-tmp-", dir="/tmp") as tmpdir:
    env = {**os.environ, "TMPDIR": tmpdir, "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(["python3", "scripts/testing/test-write-region.py"], env=env, check=True)
PY
```

## Rule 15 activation and rollback

- **Integrated and turned on.** The existing script entry point runs the fixture
  on every invocation.
- **Validated end to end locally.** Both runs exercised the real handler and
  verified the resulting file contents. Full verification in the Tier 0
  sandbox is deferred to the orchestrator's integration gate as of 2026-11-24.
- **Observable and intervenable.** The script reports each assertion and exits
  nonzero on failure. The fixture can be rerun with either command above.
- **PM tracking.** The evidence is keyed to `TIER0-WRITE-REGION-SANDBOX-FIXTURE`.
  Live tracker verification is deferred to integration as of 2026-11-24.

Rollback is a revert of the fixture change and this evidence file. A revert
restores the original host-directory fallback and can reintroduce the Tier 0
failure. The change carries no service state or data migration.
