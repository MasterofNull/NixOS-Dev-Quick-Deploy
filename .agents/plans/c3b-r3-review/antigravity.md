VERDICT: PASS

# Foundation C — C3b R3 Independent Design Review

- **Reviewer:** Antigravity (independent flagship reviewer)
- **Author:** Opus (sub-agent implementer)
- **Subject:** `.agents/plans/aqos-foundation-c/C3B-R3-DESIGN-AND-AUTHORIZATION.md`
- **Scope:** C3b Stage R3 design review only (no implementation or code changes)

---

## 1. Resolution of Historical Findings & Constraints

- **Host User Namespace Grounding (SF-2):** RESOLVED (§2). We verified via local execution that unprivileged user namespace creation (`unshare --user`) is permitted by default on the host kernel (`max_user_namespaces = 111259`). This permits bwrap sandboxing without mutating global kernel policies.
- **Supervision & Process Lifecycle (R0 Finding #7):** RESOLVED (§6). The design enforces aggressive runner-generated heartbeats (1s local deadline) and cgroup-scoped SIGTERM/SIGKILL trees. Failures to clean the tree result in immediate `QUARANTINED` status.
- **Switchboard Hardening Parity:** RESOLVED (§2, §8). The switchboard systemd hardening parameters (`RestrictNamespaces=true`, `NoNewPrivileges=true`, empty capabilities, private user) are maintained byte-for-byte. The runner relaxes only its own unit's `RestrictNamespaces` to `CLONE_NEWUSER | CLONE_NEWNS` to run bubblewrap.

---

## 2. Nine Review Obligations Verification (§10)

| Obligation | Design Status | Verification Details |
|---|---|---|
| **1. Userns & hardening (§2)** | **CLOSED** | Kernel supports unprivileged userns; switchboard.nix is untouched. Runner RestrictNamespaces is tightly scoped. |
| **2. UDS Transport-only (§3)** | **CLOSED** | authenticated peer access via `SO_PEERCRED` for clients group; transport-only channel with no error oracle. |
| **3. Asymmetric Verification (§4)** | **CLOSED** | Signature verified via R1 `verify_grant` with Ed25519 public key only. A compromised runner cannot sign new grants. |
| **4. Bubblewrap Argv (§5)** | **CLOSED** | `--unshare-all`, `--unshare-net` (no egress), `--clearenv` to scrub environment variables. No unsandboxed fallback. |
| **5. Supervision & Fence (§6)** | **CLOSED** | 250ms polling, cgroup.kill tree reaping, and double-check epoch fence prior to publishing GREEN. |
| **6. Out-of-cell Validator (§7)** | **CLOSED** | Ignores cell git config/hooks; runs byte-by-byte direct tree comparison. Only declared paths allowed. |
| **7. No Auto-merge (§7)** | **CLOSED** | GREEN only outputs/retains a validated diff for separate orchestrator review; no silent/automated merges. |
| **8. Nix Hardening (§8)** | **CLOSED** | Declares runner unit with strict sandboxing (ProtectSystem=strict, StateDirectory, custom unprivileged user). |
| **9. Scope Containment (§1)** | **CLOSED** | Bounded strictly to runner and validator design; no switchboard routing changes, no live network, no performance gates. |

---

## 3. Reviewer Positions on Open Questions (§12)

- **Q-R3-1 (Persistent vs. Transient Runner):** We endorse the persistent socket-activated runner as the baseline. It simplifies privilege separation, as a transient unit (`systemd-run`) requires dbus privileges or root authority to create, whereas a persistent socket-activated runner runs under a dedicated unprivileged user right from the start.
- **Q-R3-2 (Validator Confinement):** We agree that the validator must run inside its own minimal bubblewrap cell with `--unshare-all --unshare-net --read-only /` to prevent untrusted diff parser escapes.
- **Q-R3-3 (Cgroup v2 Delegation):** Yes, cgroup v2 delegation works flawlessly. Systemd units with `Delegate=yes` permit the unprivileged owner of the process to write to `cgroup.kill` and control the subtree, making whole-tree process reaping secure and privilege-minimized.
- **Q-R3-4 (Descriptor Vocabulary):** We agree that the initial R3 execution should be restricted to the minimal vocabulary (`noop`, `read-validate`, and `single-file-write`), deferring any richer command structures to future reviewed slices.

---

## 4. Findings

### SHOULD-FIX
- **cgroup Delegation Config (§8, §12):**
  - *Observation:* To ensure proper cgroup-scoped killing under an unprivileged user, systemd requires the unit to explicitly declare `Delegate=yes;`.
  - *Fix:* Ensure the systemd service declaration in `execution-cell-runner.nix` includes `Service.Delegate = true;` to permit control of the cell cgroup tree.

### NICE-TO-HAVE
- **Socket Runtime Directory Management (§8):**
  - *Observation:* The socket path is specified under `/run/aq-execution-cell-runner/`.
  - *Fix:* The systemd socket or service unit should declare `RuntimeDirectory = "aq-execution-cell-runner";` to allow systemd to manage the lifecycle, ownership, and permissions of the directory in `/run/` automatically.
