# AIDB catalog rebuild fetch resilience — 2026-10-16

## Root cause and scope

At 07:30:23 PDT (journal display time) on 2026-10-16, boot catalog synchronization encountered a DNS failure from the Python skills lister (`urllib.error.URLError` with `gaierror`).  The MCP fetch path converted any `curl` failure into `exit 0`, which hid the failure and skipped the remaining validation.  The skills path had neither a bounded execution timeout nor retries.

This slice changes only `scripts/data/sync-aidb-library-catalog.sh` and its focused regression test.  It makes no Nix, systemd, runtime, port, URL, or credential changes.  The unrelated Codex factory recovery worktree at `/tmp/factory-rollout-codex-recovery` was preserved.

## Change

Both upstream producers now use one Bash helper with at most three attempts.  MCP requests use `curl -fsS --connect-timeout 5 --max-time 30`; the skills lister uses native `timeout --foreground 30s`.  A fetched response is promoted from an attempt file only after success, so a failed fetch cannot be transformed or imported.  Exhausting attempts returns nonzero and states that import is refused.

The one-second delay between attempts is deliberately bounded: it adds at most two seconds while the three fetch limits already cap a worst case at about 92 seconds.  It gives a transient resolver failure another lookup opportunity without turning this producer repair into a service-ordering workaround.  It does not claim to solve boot ordering; the owner service rerun remains required after integration.

## Evidence

Focused validation in the isolated worktree passed:

```text
bash -n scripts/data/sync-aidb-library-catalog.sh
python3 scripts/testing/test-aidb-library-catalog-sync-fetch.py
python3 scripts/testing/test-boot-stability-regressions.py
python3 -m py_compile scripts/testing/test-aidb-library-catalog-sync-fetch.py
git diff --check
```

The regression test proves transient MCP and skills failures retry successfully, permanent failures return nonzero after three attempts, and failed fetches send no import request.  It asserts the exact bounded `curl` and `timeout --foreground 30s` invocations, plus simulated lister timeout exit 124 with three attempts and a subprocess deadline.

Live evidence on 2026-10-16: DNS resolves; `systemctl --failed` and `systemctl --user --failed` each report zero failed units.  A real full run of the patched worktree catalog-sync script against the upstream and AIDB passed with exit 0, `imported=0` for both catalogs, and `--validate-only` passed with 247 MCP entries and 46 skills.

A read-only database query confirmed AIDB is 502 MB with stored collation version 2.40 and actual OS collation version 2.42.  This is deferred as medium-severity database maintenance requiring reindexing before a refresh; this slice neither repairs it nor masks it with a refresh.  `ai-eval-startup` is a user service and completed successfully with exit 0; the earlier system-scope lookup was not applicable.

## Activation deferral

Activation is **deferred**.  The producer change is unmerged and no runtime configuration was changed.  Before activation can be attested, the PR must integrate and the owner must rerun the relevant service or script, then verify the live producer behavior.  The passing direct worktree-script run validates this diff; installed-service activation remains unverified until integration and an owner-run service verification.

MemoryBroker persistence initially returned `{error: timed out}`.  A retry returned `QUEUED` with id `d2d0cf63-d808-4a58-8959-46d677d5eda9`; that queued acknowledgment does not confirm persistence.  No stored seed is claimed; the limitation is recorded in the issue backlog and memory index.


## Post-validation governance

The full tier0 pre-commit run reported 58 passed and two failing gates; no commit ran.  The focused CI memory-governance failure was caused by this slice's one new memory-index entry taking `ai-stack/agent-memory/MEMORY.md` from its 200-line base to 201 lines.  Its AIDB evidence pointer was merged into the adjacent maintenance entry without removing content, restoring the file to 200 lines.  `python3 scripts/testing/test-agent-memory-surface-registry.py` then passed.

The remaining failures are aq-qa phase-0 checks `0.10.8` (memory) and `0.10.2` (token usage), pending reviewer diagnosis.  They are recorded as unresolved blockers and are not attributed to the catalog-fetch repair.
