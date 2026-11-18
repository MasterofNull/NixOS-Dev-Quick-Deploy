# Deploy validation, 2026-11-15

NixOS and Home Manager activated cd074797 successfully. Final phase 0 QA failed factory readiness fixture 0.10.50: preview and confirmation subprocesses independently queried the live GitHub owner, making the hash-bound plan nondeterministic. Pinning FACTORY_OWNER_HANDLE=factory-fixture passes all 26 invariants while preserving production preview integrity.

The aq-update reconciliation path could skip failed deploy-wrapper QA once the new revision was running. Reconciliation now runs phase 0 QA, requiring a valid zero-failure summary and zero process exit before completion. Update tests pass 41/41, including failure, malformed summary, process failure and successful retry without rebuilding.

Sudo timestamp_timeout=0 is deliberate policy in nix/modules/core/base.nix. Corrected single-prompt wording without weakening policy. Optional VSCodium extension timeouts remain deferred; activation continued and their cause is not established.
