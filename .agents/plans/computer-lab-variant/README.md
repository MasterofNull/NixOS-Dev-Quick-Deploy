# Computer-lab flake variant — seed notes (2026-10-01)

Status: SEED (owner direction 2026-10-01: "a flake geared towards computer lab deployment with
dynamically created users (and also admin)"). Not yet a PRD; captures the per-variant switch points
so the variant is a configuration choice, not a fork.

## Owner constraint
Security choices made for the hyperd agent-dev workstation (newest kernel, update cadence, userns
policy) are per-variant defaults, never system requirements. Everything below is an option.

## Switch points that already exist
| Option | Workstation (hyperd-ai-dev) | Lab variant (to decide) |
|---|---|---|
| `mySystem.kernel.track` | `latest-stable` (security protocol; host mkForce) | latest-stable vs lts — fleet stability vs exposure |
| `mySystem.security.unprivilegedUserNamespaces` | `allow` (agent bubblewrap cells, Electron, Nix sandbox) | likely `restrict` for untrusted users; eval asserts surface the costs (Nix sandbox off, no execution cells) |
| `mySystem.security.kernelHardening.enable` | `true` (kptr_restrict=2, dmesg_restrict=1) | `true` |
| `mySystem.autoUpdate.enable` (+ tiers in `config/update-tiers.json`) | off until drill; frontier tiers for agent tools | on, likely core-only tiers; reboot SLA + lab schedule |
| Reboot policy (`aq-auto-update` REBOOT_SLA_HOURS) | 24h, owner-scheduled reboot | scheduled reboots outside lab hours |

## Open for the PRD
- Dynamic user lifecycle (create/expire per session or roster), admin role separation, home/data reset.
- Whether the AI stack runs on lab machines at all (memory budget: llama.cpp ~24 GB on this class of host).
- Update-tier config per variant (the tier file is currently single; a variant may need its own).
