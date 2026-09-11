# End-to-end: install -> reboot -> first-boot finalize -> properly-configured NixOS

**Goal (owner-chosen 2026-09-09):** the full chain on real hardware — partition + install the config onto a
real disk, reboot, finalize the non-declarative residue at first boot, and end with a **properly-configured
NixOS** (secure services ON). Naming is irrelevant; the running configured system is the deliverable.

**Reproduction target (owner-required 2026-09-09): the install + verification must FULLY REPRODUCE the
NixOS AI agentic software factory WITH the local AI dev env** — not just the AI-off golden base. That means
the local LLM serving path (llama.cpp), AIDB, hybrid-coordinator, switchboard, and the agent tooling all
come up and wire correctly. Two-tier verification because of hardware reality (host = 27GB RAM, real model
~24GB, often already resident, so the real big model cannot load inside a VM alongside it):
- **In the VM (s3):** the FULL ai-dev/agentic-factory config builds + boots + every service reaches healthy
  startup, using a SMALL swappable test model (the model file is config) — proves the whole factory
  reproduces declaratively and its serving path works. NOT a big-model benchmark.
- **On real hardware (s4):** the full-size model runs at speed — the one thing the VM cannot show.
The install/verify TARGET host is therefore the full AI-on factory config, not the golden AI-off base.

**Safety contract (non-negotiable):** the ENTIRE chain is proven in a disposable VM first. The only
irreversible act — erasing a real disk — is the LAST slice, run from the OWNER's terminal (Claude has no
sudo and never erases a real disk). We do not bet a real machine on unproven code. Rollback (p3-rollback)
+ VM-boot proof (VM dogfood) are DONE, so this is now unlockable.

**Encryption contract (owner 2026-09-09: "all secrets encrypted" + "disk encryption is the user's choice
at install, per OS best practice"):** two layers, one always-on, one user-chosen:
1. **ALWAYS ON — service passwords/secrets** (postgres_password, AIDB/coordinator/embeddings/bouncer API
   auth) are **SOPS/age-encrypted** in the repo and RANDOMLY GENERATED (never human-typed, never
   login-derived); decrypted only at runtime into `/run/secrets` (tmpfs, never persisted). One age key
   unlocks all. This is not a toggle — it satisfies "all secrets encrypted" unconditionally.
2. **USER CHOICE at install — full-disk LUKS encryption** (recommended ON), exactly as mainstream OS
   installers offer it. It is what encrypts the **age key** and **/etc/shadow hashes** at rest (those
   cannot be SOPS-encrypted — the age key is what decrypts; chicken-and-egg). Informed-choice warning the
   wizard MUST show: declining it leaves the age key + password hashes on a plaintext disk, readable if the
   machine is physically stolen (SOPS still encrypts the secrets; the key protecting them is exposed).
The single secret-unlocking "keyring" is the age key (protected at rest by LUKS when chosen); the login
password is for login only, never the master for service secrets (services start at boot, pre-login).
Boot-unlock sub-decision when encryption is chosen: manual LUKS passphrase vs TPM2 auto-unlock (unattended
headless boot, hardware-bound) + recovery passphrase — recommend TPM2 auto-unlock for an AI workstation.

## Where each config value is set (owner Q 2026-09-09: "are hostname/user/password set at install?")
Two install paths exist. Standard graphical NixOS (Calamares) collects hostname+user+password in the
wizard. Our minimal/declarative path does NOT — so WE decide, and the clean split is:
- **Set at INSTALL time by our setup wizard (s1), like the standard wizard:**
  - **Hostname** — not a secret; declared (`networking.hostName`).
  - **Username** — not a secret; declared (`users.users.<primaryUser>`).
  - **User password** — collected at install, HASHED, written to a password-file on the target (outside
    the world-readable Nix store; `core/base.nix` requires a password directive for a non-mutable user).
    `nixos-install` also prompts for the root password. => password is NOT first-boot residue.
  - **Hardware facts** (`hardware-configuration.nix`) — generated at install (`nixos-generate-config`).
- **Genuinely NON-declarable => finalized at FIRST BOOT (s2), because they cannot exist at install time:**
  - **SOPS decryption key** (`/var/lib/sops-nix/key.txt`) — the linchpin. Not in the repo (store is
    world-readable). Until placed, sops-nix decrypts nothing and the golden profile's secure services
    (firewall bouncer, switchboard signer, AIDB/coordinator API auth) stay DORMANT. Placing it flips them ON.
  - **Agent OAuth logins + hardware-key/biometric enrollment** — per-user, interactive, out-of-band
    (NO-API-keys/OAuth-only + beginner control surface).

## Full payload inventory (owner Q 2026-09-09: "are we implementing sandboxing, DBs, tooling, all payloads?")
Two categories — the reproduction is only "full" if BOTH are handled:
- **Reproduces automatically (declarative; s1c verifies each is UP):** AI sandboxing (systemd hardening,
  AppArmor, capability-lease = lease-signing-authority + revocation-epoch-authority, crowdsec,
  localhost-isolation); databases AS SERVICES (PostgreSQL, Redis, Qdrant + data dirs + port registry);
  all tooling (aq-* CLIs, MCP servers, switchboard, dashboard); agent config payloads tracked in the repo
  (prompts, skills, wiki, knowledge-graph, agent .md).
- **NOT automatic — explicit provisioning slice required:**
  1. **Model files (GGUF)** — not in repo/store; live at `/var/lib/llama-cpp/models/`. Provision via the
     declared `llamaCpp.huggingFaceRepo`/`File`+sha256 auto-download (needs network + disk) OR placement.
     VM uses a SMALL model; real 24GB model provisioned on metal (s4).
  2. **Accumulated DATA** — Qdrant RAG vectors, Postgres/AIDB rows, agent-memory collections, learned/
     trained adapters. A fresh install = EMPTY-but-wired stores. This is STATE, not config.
- **Fresh-vs-clone decision (owner, recommend FRESH):** CORE = fresh fully-capable factory (all services +
  sandbox + model + empty stores that RE-SEED knowledge from tracked repo sources). OPTIONAL SEPARATE STEP =
  clone this machine's live DB data / adapters / memory (backup->restore of the data partitions). Build
  fresh-capability first; state-cloning is a separable migration slice.

## Reuse (already in-repo — compose, do not rebuild; Rule 20b)
- **disko**: flake input present; `mySystem.disk.layout` option + assertions already wired (flake.nix).
- **Hardware facts**: `scripts/governance/discover-system-facts.sh` (`nixos-generate-config --show-hardware-config`).
- **Age-key generation**: `scripts/governance/manage-secrets.py`, `scripts/security/fix-secrets-encryption.sh` (`age-keygen`).
- **VM harness pattern**: `scripts/testing/aqos-vm-dogfood.sh` + `nix/hosts/aqos-vm/` (systemd oneshot marker, show-once).
- **Recovery media**: `scripts/testing/recovery-iso-disk-fix.sh`. **Config generation brain**: P0-P2 resolver/approval.

## Slices (VM-first; route cheapest-eligible; real hardware last + owner-gated)
### s1 — setup wizard: collect identity + disko layout + install into a VM disk (FIRST)
Collect **hostname + username + user password** at install time (like the standard wizard): declare
hostname+username, hash the password into a password-file on the target (never plaintext in the store).
Follow mainstream-installer UX: offer standard install choices with sane defaults, including **full-disk
LUKS encryption as a yes/no user choice (recommended ON)** with the informed-choice warning. Provide TWO
disko layouts — encrypted and plain — selectable via `mySystem.disk.layout` from that choice; wire
hardware-facts (`nixos-generate-config`). When encryption is chosen, resolve boot-unlock (TPM2 auto-unlock
+ recovery passphrase recommended, vs manual passphrase). Harness partitions a **virtual** disk (test BOTH
the encrypted and plain layouts), installs the golden config, and boots the result (extend aqos-vm-dogfood).
Proves the install step incl. LUKS unlock when selected. No real disk, no sudo.

### s2 — first-boot finalization service (declarative, show-once) — SOPS key + OAuth only
A declarative systemd first-boot oneshot (modeled on the aqos-vm marker): (a) provision the SOPS age key —
prefer an owner-provided key, generate-if-absent fallback, reusing manage-secrets/fix-secrets-encryption —
which flips the secure services ON; (b) walk agent OAuth logins + hardware-key/biometric enrollment in
plain language (NO-API-keys/OAuth-only + Approval Control Plane). Password/hostname/user are NOT here (s1).
Validate in VM: after finalize, sops-nix decrypts and bouncer/signer/API-auth are active.

### s1c — full-factory VM target (REQUIRED: reproduces the AI dev env, not just golden base)
A VM host that installs the FULL ai-dev/agentic-factory config (aiStack role ON) with a SMALL swappable
test model (not the 24GB model — host RAM can't hold both). Boot it and verify the factory reproduces:
llama.cpp health, AIDB, hybrid-coordinator, switchboard, agent tooling all reach healthy startup (reuse the
health-spider / service health endpoints, ports from env). This is the "fully reproduce the factory"
verification. Depends on s1a (disk/install mechanics).

### s1d — payload provisioning (model + RAG re-seed; the non-automatic payloads)
Declarative model provisioning (`llamaCpp.huggingFaceRepo`/`File`+sha256 auto-download, SMALL model in VM /
real model on metal) + a RAG/knowledge RE-SEED path that re-ingests the tracked repo sources (wiki, docs,
knowledge-graph) into empty Qdrant/AIDB on a fresh factory. Fresh-capability, not state-clone. Verified in
s1c (ingest->search roundtrip with the small model). State-cloning (live DB/adapters/memory migration) is a
SEPARATE optional slice, not part of fresh reproduction.

### s3 — end-to-end VM dogfood (the "both end-to-end" proof)
Chain s1a+s1b+s1c+s2: install the FULL factory into a fresh VM disk -> reboot -> first-boot finalize (age
key) -> assert (a) secure services ON, (b) the full AI dev env reproduced + healthy (small model). One
disposable command, no sudo. End-to-end proof MINUS the big-model benchmark (that is s4). Gate for s4.

### s4 — real-hardware activation (owner-run; ONLY irreversible step)
Documented + guarded procedure applying the same layout+install+finalize to the real machine, from the
owner's terminal. Recovery media as fallback. Gated HARD behind s3 passing.

## Sequencing
s1 -> s2 -> s3 (all disposable-VM) -> s4 (owner terminal, real hardware). Each slice: independent
non-author review -> tier0 gate -> trunk envelope -> merge. ACTIVATION-AUDIT per slice; PM tracker updated.
