# Knowledge-source sync transient retry & per-source isolation evidence

Date: 2026-11-10

Incident `rsi-4263f9daeb19f4adc7219106`: `ai-sync-knowledge-sources.service`
aborted its weekly run when `urllib.request.urlopen` raised `URLError`
(`[Errno -2] Name or service not known`) on a single source right after boot,
leaving all remaining sources unsynced and the unit failed for the week.

Changes (`codex-20261110-092004-s6c2tr`):

1. Added `fetch_url(url)` in `scripts/data/sync-knowledge-sources` with bounded
   exponential-backoff retries (`KNOWLEDGE_FETCH_MAX_RETRIES`, default `3`,
   backoff capped at `10s`) on `URLError`, `TimeoutError`, and HTTP `429`/`5xx`,
   while keeping non-retriable HTTP status codes (`404`, etc.) fail-fast `WARN -> None`.
2. Isolated per-source fetch exceptions so a failing source increments
   `fetch_failed` and logs `WARN` while remaining enabled sources continue.
3. Preserved fail-closed semantics: exits `1` if any AIDB import fails or if
   every attempted enabled source fails (`attempted > 0 and fetched == 0`), and
   prints `synced=N skipped=N fetch_failed=N`.
4. Added offline regression test `scripts/testing/test-sync-knowledge-sources-retry.py`
   and registered it in `config/ci-checks.json` (`tests-misc-s-t`).

Validation:

- `bash -n scripts/data/sync-knowledge-sources` — pass.
- `python3 scripts/testing/test-sync-knowledge-sources-retry.py` — 8 tests pass.
- `scripts/data/sync-knowledge-sources --dry-run` — exits 0 (`synced=0 skipped=6 fetch_failed=0`).
- `python3 scripts/testing/test-ci-checks-manifest.py` — pass (8 checks).

Activation attestation (2026-11-10): integrated into `scripts/data/sync-knowledge-sources`
(ExecStart of `ai-sync-knowledge-sources.service`); CI enabled via `tests-misc-s-t`;
live systemd re-run (`sudo systemctl start ai-sync-knowledge-sources.service`)
deferred to owner post-merge activation.
