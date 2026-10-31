# PR672 package count baseline refresh

## Scope

Regenerated the tracked package-count baseline after the Herdr package was enabled for the `hyperd` Home Manager configuration. No lockfile or runtime state was changed.

## Evidence

- Ran `scripts/testing/check-package-count-drift.sh --write-baseline` successfully.
- Ran `scripts/testing/check-package-count-drift.sh` afterward; it passed with `Package count baseline check passed.`
- The regenerated values reflect `hyperd` and `hyperd-hyperd` Home Manager counts changing from 67 to 68, and combined `hyperd-ai-dev`, `hyperd-gaming`, and `hyperd-minimal` counts changing from 453/341/241 to 454/342/242.
- The generated summary updates Home Manager max/average to 68/66.80 and combined max/average to 454/350.83.

## Limits

This records package count evaluation only. No live activation or tier0 validation was run in this bounded slice.
