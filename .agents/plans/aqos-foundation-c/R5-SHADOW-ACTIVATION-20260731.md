# Foundation C — R5 SHADOW Activation (owner-authorized 2026-07-31)

Turns on the C3b confinement spine in **SHADOW**: real tool-calling is UNCHANGED; the switchboard
adapter additionally exercises mint→sign→UDS→bwrap-cell→validator on real admitted effects in
parallel (dogfood/validation), deny-closed on any failure, never touching the real result. This is
NOT authoritative cutover (cells replacing in-process execution) — that is a separate later slice.

## The three declarative changes (committed; live on `nixos-rebuild switch`)
1. `nix/modules/profiles/ai-dev.nix` — `mySystem.aiStack.executionCellRunner.enable = true` +
   `flagOn = true`. Starts the dedicated, unprivileged, socket-activated bwrap runner and flags it
   on (CAPABILITY_EXECUTION_CELLS=1 in the runner). The module auto-joins the switchboard user
   (primaryUser) to the `aq-execution-cell-clients` socket group.
2. `nix/modules/services/execution-cell-runner.nix` — wires
   `AQ_EXECUTION_CELL_RUNNER_PUBLIC_KEY_HEX` from the tracked `config/grant-signing-public-key`
   (the runner runs from the Nix store, so the relative-file fallback can't resolve; this env is
   authoritative). Public key `6082fc49…` matches the SOPS private key the adapter signs with.
3. `nix/modules/services/switchboard.nix` — `CAPABILITY_CELL_ADAPTER=1` (the shadow attach). The
   rebuild also lands the SOPS grant private key at `/run/secrets/aq-grant-signing-key`.
Switchboard hardening (RestrictNamespaces/NoNewPrivileges/empty caps) UNCHANGED (verified). All
three `.nix` parse clean.

## Rebuild
```
sudo nixos-rebuild switch --flake .#hyperd-ai-dev
```

## Post-rebuild validation (I run these — no sudo needed)
1. **Runner up:** `systemctl status aq-execution-cell-runner.socket` (listening); the service is
   socket-activated (starts on first connection).
2. **Keys:** `/run/secrets/aq-grant-signing-key` present (root:ai-stack 0440); the adapter loads it
   (is_dev-equivalent = false → mints real signed grants); the runner's public key matches (grants verify).
3. **Real tool-calling UNCHANGED:** a normal local-agent tool call still runs + returns exactly as
   before (the shadow adapter never alters the result).
4. **Shadow spine exercised:** on a real cell-required effect, the adapter mints+signs a grant,
   the runner accepts (SO_PEERCRED + signature), constructs a bwrap cell, validates, and returns a
   typed GREEN/RED receipt — visible in the runner logs / receipt projection. A signature/key/confinement
   failure → deny-closed shadow (logged), real execution unaffected.
5. **No regression:** C2 enforcement still admits first-party tools + denies unknown; C5 spans still
   emit; switchboard healthy; no 401/empty-response anomalies.

## Rollback (instant-ish)
Set `executionCellRunner.enable=false` + `flagOn=false` (ai-dev.nix) and `CAPABILITY_CELL_ADAPTER=0`
(switchboard.nix) + rebuild. Emergency non-rebuild: `CAPABILITY_CELL_ADAPTER=0` in the switchboard
`overrides.env` + restart the service (stops the shadow submit immediately; runner idles).

## What this does NOT do
- Does NOT make cells authoritative for real effects (in-process execution stays the source of truth).
- Does NOT enable network egress (C4), the scheduler gate (C6), or the delegate broker (C3a-2).
- Codex verifies the R5 build + this shadow activation on its Aug-4 return.
