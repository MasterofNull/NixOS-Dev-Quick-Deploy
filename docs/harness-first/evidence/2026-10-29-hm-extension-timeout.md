# Home Manager extension installs time out instead of hanging — 2026-10-29

## Objective

Stop `home-manager switch` from hanging when a VSCodium extension download stalls (P1.10 F1, `.agents/plans/system-integrity-recovery/SECURITY-UPDATE-LANE.md`).

## Workflow/Session IDs

- Claude session 50391bdd; implementer Codex `codex-20261029-131142-c3vefd`.
- Incident: on 2026-10-29 the owner's `home-manager switch` hung for 15+ minutes. `codium --install-extension qwenlm.qwen-code-vscode-ide-companion --force` held an established TLS connection to the extension CDN with no progress. The owner killed the process to continue.

## Delegation Decision

Bounded single-file Nix edit routed to Codex (Rule 17; owner authorized Codex budget use). Claude orchestrator reviewed the diff. Local Qwen gives the independent review.

## Commands Executed

```
nix-instantiate --parse nix/home/base.nix
nix eval .#homeConfigurations.hyperd.activationPackage.drvPath
nix build --no-link --print-out-paths .#homeConfigurations.hyperd.activationPackage
bash -n <generated activate script>
```

## Validation Evidence

- Parse: PASS. The activation package evaluates and builds (`/nix/store/5zkzz09w0ccj86zic6464mr4sa1wncnl-home-manager-generation`). `bash -n` on the generated `activate` passes.
- The generated `activate` contains `timeout 120` on the Continue VSIX install and on the per-extension loop (lines 734 and 744).
- Not yet exercised: a real stalled download. That is validated on the owner's next `home-manager switch` (delivery-workflow step 6).

## Rollback Plan

Revert the commit. Installs then run without a time limit again, as before.

## Residual Risk

- A slow but working connection that needs more than 120 s per extension skips that extension; the activation prints the command to install it later.
- The Continue VSIX install is a local file, so a timeout there indicates a VSCodium problem rather than the network.

## Hint Feedback

Activation scripts that reach the network had no time limits anywhere in `nix/home/base.nix`. A tier0 lint for network calls in activation without `timeout` would catch the next one.
