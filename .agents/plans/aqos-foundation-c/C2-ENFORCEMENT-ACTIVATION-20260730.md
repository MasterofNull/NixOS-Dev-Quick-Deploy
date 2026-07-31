# Foundation C — C2 Tool-Lease Enforcement: LIVE ACTIVATION (owner-authorized 2026-07-30)

Owner directive: "start activating the system... permanent C2 (Nix + rebuild)", leaving room for
codex to review/adjust on its Aug-4 return.

## What is activated
`CAPABILITY_LEASE_ENFORCEMENT=1` added to the `ai-switchboard` service Environment
(`nix/modules/services/switchboard.nix`). On the next `nixos-rebuild switch`, C2 tool-lease
enforcement is LIVE: every tool call is admitted only via a verified capability lease; the harness's
own built-ins are admitted through first-party leases (`config/first-party-tools.json`).

## Why C2 is the safe first activation
- Only enforcement slice with codex DEPTH review: codex-20260729-043758 (REVISE, 2 HIGH) →
  -163121 (PASS after fold). Both HIGH fail-open classes closed (zero-trust monotonicity;
  manifest↔signed-metadata tripwire).
- Pre-flight 83/83 flag-ON suite green (admits first-party tools incl. run_command/file_edit;
  denies unauthorized; deny-closed; DEV-key/unresolvable-epoch degrade to safe-read).
- Switchboard hardening UNCHANGED (RestrictNamespaces/NoNewPrivileges/empty-caps intact — only an
  Environment entry added).

## Activation Gate (Rule 15) — C2 now crosses "turned ON" (was deferred)
integrated ✔ (live executor chokepoint) · turned-ON → ON after rebuild · functionally-validated →
post-rebuild live check (below) · observable → decision audit lines (C5 spans pending) · intervenable
→ flag=0 + rebuild reverts instantly-ish; epoch bump (C6, pending) is the finer lever.

## Post-rebuild validation (run after `nixos-rebuild switch`)
1. switchboard healthy: `curl -s localhost:8085/health`.
2. a real tool-calling request still works (first-party lease admits run_command/read_file).
3. an unauthorized/unclassified tool is denied (deny-closed) — spot check via the gate decision log.
4. no 401/empty-response regression; watch switchboard logs for lease-denial anomalies.

## Rollback (instant-ish)
Set `CAPABILITY_LEASE_ENFORCEMENT=0` (or remove the line) in switchboard.nix + `nixos-rebuild switch`.
(Or, for an emergency non-rebuild revert, write `CAPABILITY_LEASE_ENFORCEMENT=0` to the switchboard's
mutable overrides.env + restart the service — wiped by next rebuild, so also fix the .nix.)

## Left for codex (Aug-4)
The permanent Nix declaration + this activation are in the AGENT-CATCHUP-QUEUE for codex's
confirmatory audit; codex may propose adjustments (advisory unless a real defect → bounded fix).
Other enforcement slices (R3 runner enable, R5/C4/C6/C3a-2 builds) remain OFF/unbuilt pending codex.

## VALIDATED LIVE 2026-07-30 (post-rebuild, key provisioned)
- /run/secrets/aq-lease-signing-key present (root:ai-stack 0440); resolve_key() is_dev=False (production key).
- LIVE enforce(): run_command / write_file / read_file / store_memory / delegate_to_remote → ADMIT
  (first-party-lease-verified); a_nonexistent_tool + the `file_edit` bundle-name → DENY (deny-closed,
  no-admitting-lease). switchboard active + healthy; CAPABILITY_LEASE_ENFORCEMENT=1.
- The DEV-key degrade (which had denied privileged tools) is resolved by the provisioned key
  (commits: flag 4adcf55b + key b076528c).
- **Activation Gate (Rule 15): C2 now satisfies integrated + turned-ON + functionally-validated-real-world.**
  Remaining DoD legs: observable (C5 spans, built/uncommitted) + finer intervenability (C6 epoch bump, designed).
- Owner-authorized; codex to confirmatory-audit the live activation on Aug-4 return (catch-up queue).
