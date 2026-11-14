# Refresh stale nix/pkgs pins

Date: 2026-11-14

## Objective

The 2026-11-13 audit found hand-pinned packages in nix/pkgs months behind upstream. This refreshes the ones that can be bumped safely. Each package is built individually and smoke-tested.

## Workflow/Session IDs

- Branch `worktree-agent-a10c716adb891f162`. Delivery-friction wave.
- The implementer's run was killed by a power loss mid-refresh; Simurg@claude/opus-5.5#da0ef470 resumed it on 2026-11-14.
- Companion PR #779 adds the pin watch for nix/pkgs.

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default). The independent reviewer lane is chosen by aq-land (codex first; Gemini is unavailable until 2026-11-20).

## Commands Executed

- `nice -n 19 nix build` per package, through the repo overlay, one build at a time.
- `opencode --version` printed `1.19.5`.
- The models-dev store path contains `_api.json` and `_models.json`.

## Results

| Package | Old | New | Notes |
|---|---|---|---|
| opencode | 1.3.0 | 1.19.5 | needs `nodejs` + `patchShebangs` for vite (`/usr/bin/env: bad interpreter`) |
| models-dev | 2026-03-17 | 2026-11-14 (a5458bdc) | data package |
| continue-cli | 1.5.45 | 1.5.47 | |
| maigret | 0.6.1 | 0.6.6 | |
| mosaic | rev=main | 0df2c04 | reproducible pin |

Skipped, both logged in `.agent/memory/issues-backlog.md`:
- pi-agent: never buildable (`lib.fakeHash`).
- herdr: trust-pinned, so it goes through supply-chain review first.

## Activation

- ON: after the next owner rebuild (`aq-deploy-current`).
- Validate live: `opencode --version` reports 1.19.5.
- Intervenable: revert the per-package commit.
