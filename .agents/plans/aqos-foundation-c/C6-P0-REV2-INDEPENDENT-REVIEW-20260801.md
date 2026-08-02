# C6-P0 Revision 2 — Independent Review

Status: `REQUEST_REVISION — NOT FREEZE ELIGIBLE`  
Reviewer: `Codex orchestrator, independent of subject author`  
Subject SHA-256: `6b9e53d6708f4045a0d98860339afc922530d9467b50eee517526941bf7e5b85`

The revision closes the mechanical inventory findings: existing C2, dispatch,
Nix-import, and switchboard anchors are exact; absent issuer, transport, schema,
manifests, Nix service, fixture, and test paths are explicitly NEW. The domain
separation, raw-caller denial, peer-bound immutable handoff, public owner-key
allowlist, default-OFF boundary, and deferred Service Coverage direction are
sound.

Two trust anchors remain unspecified:

1. The scheduler-context signer has no private-key authority/provisioning path.
   The design requires a new key family and names a future public revision, but
   inventories no SOPS/Nix secret declaration, signer process boundary, read
   permission, rotation/revocation source, or fail-closed key-unavailable path.
   A Python module cannot be the sole issuer while its signing key source and
   execution principal remain outside the ceiling.
2. The transport peer policy is deferred to values in the future manifest. The
   design must freeze the canonical service/user identity and the Nix ownership
   source that resolves it; hard-coded numeric UID/GID is not portable, while a
   caller-writable manifest is not authority. It must also state which existing
   process hosts the issuer and UDS endpoint while the future epoch-authority
   service remains disabled.

Either narrow C6-P0 to pure schemas/manifests with no claim that it closes the
issuer/transport prerequisite, or add the complete secret/principal/service
authority inventory and default-OFF integration tests. Any new service or
enabled runtime path must also satisfy Service Coverage in the same slice.

`VERDICT: REQUEST_REVISION` — exact file hashes are now pinned, but signer and
peer/service authority are still placeholders. No implementation authorization,
activation, staging, commit, runtime, provider/network, or deployment action is
permitted.
