# Antigravity Advisory: Approval Control Plane PRD (R2) Review

**Author:** Antigravity (Advisory Lane)  
**Date:** 2026-08-16  
**Subject:** Approval Control Plane (ACP) PRD R2 Security & Usability Audit  
**Target File:** `.agents/plans/herdr-agent-operations/ANTIGRAVITY-ACP-PRD-ADVISORY-20260815.md`  

---

## 1. Summary Verdict

**One-Line Recommendation:** Yes, the R2 PRD is the RIGHT shape to build. All R1 advisory feedback points have been successfully folded into the PRD, making the security model exceptionally robust and user-friendly.

---

## 2. Analysis of R2 Modifications & New Advisories

We have reviewed the newly added Section 8 of the PRD, which incorporates the R1 findings. The following implementation advisories are provided for the developers:

### A. The Nix-Level Recovery Bootstrap Security (Slice P1b)
* **Design in R2:** Folds in a declarative Nix-level recovery bootstrap to handle the loss of all authenticators without single-point lockout.
* **Advisory:** To prevent a compromised agent from writing `services.approval-control-plane.recoveryBootstrap = true;` and triggering a NixOS rebuild to bypass authorization, the recovery bootstrap flag must **only** authorize the registration of a new authenticator device. It must *never* auto-approve or sign active queued tasks. The signing service must remain locked for task signing until the new authenticators are successfully registered and verified.

### B. Headless CLI USB Permissions (Slice P4)
* **Design in R2:** Folds in a CLI client (`fido2-assert`-based) for headless VT / rescue consoles.
* **Advisory:** WebAuthn assertions on the command line require direct read/write access to `/dev/hidraw*` nodes. The declarative `udev` rules shipped in Slice P1 must grant access to `/dev/hidraw*` to the console user (or a dedicated unprivileged group like `plugdev`), ensuring `fido2-assert` does not have to be run as `root` (preventing privilege escalation).

### C. Challenge Nonce Single-Use Ledger (Slice P1)
* **Design in R2:** Implements request-bound challenges burned on use using a durable single-use ledger pattern.
* **Advisory:** Ensure that the state of the challenge ledger is stored under the stable lock and written atomically (fsynced) to prevent race conditions where a concurrent writer tries to replay a challenge before the burn is written to disk.

### D. Multi-Owner Schema Readiness
* **Design in R2:** Single-owner target (`hyperd`).
* **Advisory:** The schema for `aq.approval-request.v1` should represent signatures as a list rather than a single field. This future-proofs the schema for M-of-N multi-owner consensus without requiring a breaking change to the payload layout later.
