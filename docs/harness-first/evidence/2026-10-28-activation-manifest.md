# Activation manifest (P5.2) — 2026-10-28

## Problem

Features were merged as done while nothing ran them: `aq-oncalld` (#506/#573, enable option set nowhere), the operator guidance spool (#504/#510, writer invoked by no production path), the durable runtime (#505/#509, only a dashboard health reader). Rules 15/23 ("enabled != done", "no decorative code") were prose only.

## Design

- `config/activation-manifest.json`: `{schema_version:1, features:[{feature, entrypoint, live_caller, enable, health_signal, deferral}]}`.
- `scripts/governance/check-activation-manifest.py` (stdlib only), output prefixed `[activation-manifest]`, exit 0/1.
  - Per entry: entrypoint exists; live_caller exists and contains the entrypoint basename or stem; health_signal `<path>:<symbol>` file exists and contains the symbol; non-null `enable` is set to true somewhere under `nix/` (excluding `nix/modules/core/options.nix` and any file containing `options.<parent path>`).
  - A valid deferral (`YYYY-MM-DD` date, non-empty reason) excuses only the live_caller-reference and enable checks. Missing files and missing health symbols always fail. Deferral older than 90 days is a WARN only (Rule 19 corollary).
  - New-entrypoint detection (added files vs `merge-base HEAD origin/main`, `--base <ref>`, or `--staged` for the index): `scripts/ai/aq-*` (direct child, no extension or `.py`), `nix/modules/services/*.nix` (not `default.nix`), and any `systemd[.user].services.<name>` on added lines of nix files. A file must equal some entry's `entrypoint` or `live_caller`; a unit name must appear anywhere in the manifest entries.
- `scripts/governance/tier0.d/check-activation-manifest.sh` runs the checker with `--staged`.
- Test `scripts/testing/test-activation-manifest.py` (registered as `activation-manifest-tests` in `config/ci-checks.json`).

## Matching limits

- Enable detection is textual: `<full.path> = true`, or `<parent-last-segment> = { ... enable = true` with no `}` between; `lib.mkDefault`/`mkForce` around `true` accepted. Values set via let-bindings, `inherit`, `mkMerge`, `mkIf`-wrapped computed conditions, or nested braces before `enable` are not seen (false FAIL; use a deferral or restructure).
- A different attrset with the same last segment name could satisfy the block match (false PASS).
- live_caller reference is a substring check; it proves a mention, not a call.
- systemd units with interpolated names (`services.${x}`) are not detected; moved lines count as added.
- Only NEW entrypoints are forced into the manifest; existing ones are not backfilled.
- Base mode includes untracked files and the working tree; `--staged` sees only the index.

## Seeded entries (all deferred, backlog "2026-10-28 P3 retro-review")

| Feature | Finding |
|---|---|
| aq-oncalld | `services.aiOncalld.enable` declared at `nix/modules/services/oncalld.nix:11`, set true nowhere in `nix/`; dashboard loads `oncalld_engine.py` on demand only. |
| operator guidance spool | Writer `scripts/ai/aq-human-intervention:44-52` appends to `.agents/delegation/control/<id>.jsonl`; the queue is drained only by local agents (`ai-stack/local-agents/agent_executor.py:2752`); nothing outside tests invokes the CLI. |
| durable runtime | `scripts/ai/lib/durable_runtime.py` imported only by the dashboard health summary (`aistack.py:7493-7506`), by `aq-durable` and tests; no production agent loop records intents. |

## Commands and output

```
$ python3 scripts/governance/check-activation-manifest.py --base origin/main
[activation-manifest] deferred: aq-oncalld autonomous on-call incident daemon (2026-10-28)
[activation-manifest] deferred: operator guidance spool (aq-human-intervention control queue) (2026-10-28)
[activation-manifest] deferred: durable runtime (idempotent effect ledger, aq-durable) (2026-10-28)
[activation-manifest] 3 entries, 0 fail, 0 warn

$ python3 scripts/testing/test-activation-manifest.py
Ran 11 tests in ~1s
OK
```
