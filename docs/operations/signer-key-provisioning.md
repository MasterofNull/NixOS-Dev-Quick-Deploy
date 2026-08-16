---
doc_type: reference
title: Signer-key provisioning (aq-provision-signer-key)
source: scripts/ai/aq-provision-signer-key
tags: [sops, secrets, ed25519, signer-key, provisioning, rotation, foundation-c]
---

# Signer-key provisioning

Status: active
Owner: AI Stack Maintainers
Last Updated: 2026-08-15

## Why
Each Foundation-C confined service (ALA lease-signing-authority, C2-SCI scheduler-context issuer, and the
coming TEG / C6 owner key) needs its own Ed25519 signing keypair: the private in SOPS → `/run/secrets`, the
public in a verifier allowlist JSON. This had been fully manual — a hand-run keygen that prints the private
on screen, a TTY `sops` editor (which fails with no TTY under a non-interactive shell), and a hand-edited
allowlist. That chain produced repeated failures: TTY errors, the wrong value saved, restart-vs-rebuild
confusion, the key ending up in scrollback, and — the big one — editing the **wrong SOPS file**.

`aq-provision-signer-key` closes it in one **owner-run** command.

## The wrong-file footgun (important)
The active SOPS file is `mySystem.secrets.sopsFile`, which `nix/hosts/hyperd/deploy-options.local.nix`
(gitignored) typically `mkForce`-redirects OUT of the repo, e.g.
`/home/hyperd/.local/share/nixos-quick-deploy/secrets/hyperd/secrets.sops.yaml`. Editing the repo path
`nix/hosts/hyperd/secrets.sops.yaml` does NOT reach the rebuild. The tool resolves the real file
automatically (deploy-options mkForce → `nix eval` of the config → repo fallback), so you can't target the
wrong one.

## Usage
```bash
aq-provision-signer-key --service c2-scheduler-context-issuer      # provision / re-key (replace)
aq-provision-signer-key --service lease-signing-authority --rotate # rotate: new active key, deprecate old
aq-provision-signer-key --secret-name X --allowlist Y.json --key-id Z   # explicit, no preset
aq-provision-signer-key --service ... --dry-run                    # show the plan, write nothing
aq-provision-signer-key --self-test                               # logic check (no sops, no real key)
```
Then: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` (re-decrypts `/run/secrets` — a service restart
does NOT), then re-validate the live mint round-trip.

## Security model
- Owner-run. The private key is generated in the owner's own process, goes straight into SOPS via sops's
  EDITOR hook (a 0600 tmpfs temp, shredded after) — never printed, never in argv/shell-history, never a
  tracked file. No agent holds signing material (verify != forge).
- Prints only the public key + key_id. Verifies the SOPS write landed (64-hex) BEFORE touching the
  allowlist, and aborts (leaving SOPS/allowlist consistent) if not.
- Rotation is first-class: `--rotate` appends a new active key and marks prior actives `retired` (the gate
  re-reads the allowlist per call, so a retired key stops verifying without a restart).

## Epoch bump / revoke — the one-shot (`aq-epoch-bump bump`)
The fleet kill-switch (advance the revocation epoch → revoke held leases) used to be a manual
build→copy-bytes→sign-offline→paste→submit dance. `aq-epoch-bump bump` collapses it to one owner command:
build → sign → submit over the running authority's UDS.
```bash
# one-time: passphrase-protect the offline owner key so an autonomous agent can never fire it
age -p -o ~/.config/aq/c6-owner.key.age <owner-private-hex-file>
# then, per revoke/rotation (owner-run; prompts for the passphrase):
aq-epoch-bump bump --actor-key-id owner-2026-08 --reason-code operator-revoke --expected-epoch <N> \
  --key-file ~/.config/aq/c6-owner.key.age
```
**Human-in-the-loop preserved:** the age passphrase is the factor an autonomous agent cannot forge — it is
prompted interactively, so a non-interactive agent (no TTY, no passphrase) cannot decrypt the key and cannot
fire the kill-switch. A plaintext `--key-file` is accepted only with a warning (it is agent-readable — do not
use it for the kill-switch key). The private key is read into memory, used, and never printed/logged/written.

## Where this is heading (repeatable operator workflows, not a drawer of one-shots)
`aq-provision-signer-key` and `aq-epoch-bump bump` are the ATOMS of a common shape: owner-authorized,
human-factor-gated, multi-step (build → authorize → apply → validate). The next layer is a NAMED, repeatable,
idempotent operator-workflow/runbook layer (activate-signer-service, rotate-key, epoch-revoke, emit-grant,
activate-foundation-c-slice) with ONE unified human-factor auth gating owner steps — the ACTION side of the
HERDR / operator-context work (integration contract #4: human-controls → audited AQ action paths). Tracked
self-improvement direction; the one-shots feed it.

## Presets
`config/aqos/*-signer-keys.json` + the SOPS secret name per service, in the `PRESETS` map. Add a service by
extending that map (secret name, allowlist path, key_id prefix).
