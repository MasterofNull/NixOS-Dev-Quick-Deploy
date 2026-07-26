# Foundation C — C2 Amendment: first-party/built-in tool lease source

**Supersedes the C2 freeze** (`C2-FREEZE-AND-ACTIVATION.md`, subject `313b723b`). The frozen
C2 design had a BLOCKING gap found post-freeze (evidence-confirmed, not reasoned): its
tool→lease admission admits a tool only if an **external candidate** lease (C1 issuance,
per registry candidate) lists it — but the harness's **built-in bundle tools**
(`run_command`, `file_edit`, `write_file`, `memory`, … from `_TOOL_BUNDLES`) are NOT registry
candidates, so under flag-ON enforcement they'd have no lease and be **denied**, breaking the
harness's own tool-calling. Shadow evidence: `aq-capability-shadow` over all 11 candidates →
11 would-issue, 0 built-in tools present in any lease. This amendment closes it; C2 must be
re-reviewed (rev3) + re-frozen before any owner activation.

## Fix — first-party tools are a lease SOURCE, not an exemption
Built-in tools are **first-party** (shipped + trusted by the harness), categorically different
from untrusted external capabilities — but they are still governed by a real CapabilityLease
(signed, `verify`-checked, epoch-checked, strippable). They are NOT a bypass.

### New file (C2 ceiling 4 → 5)
- **NEW `config/first-party-tools.json`** — declares the first-party/built-in tools the
  harness ships (sourced from `_TOOL_BUNDLES` in `switchboard.py`), each with:
  `{tool, actions:[tool], resources:[...], constraints:{...}, trust_tier, zero_trust_behavior,
  write_capable:bool, network_capable:bool}`. This is the authoritative first-party set;
  anything NOT in it and NOT admitted by a candidate lease is denied.

### Gate change (`capability_lease_gate.py`, within the existing ceiling)
A tool is admitted for execution iff **EITHER**:
1. a valid **candidate** lease admits it (external capabilities — unchanged), **OR**
2. it is in `config/first-party-tools.json` AND a **first-party lease** (issued by the trust
   root from that manifest) admits it: signature-valid, non-expired, not epoch-stale.

Both are real leases through the same `verify` path. The first-party lease is issued from the
manifest by the signer ONLY by a deliberate operator step — at startup, or an explicit
re-issue AFTER the operator clears an epoch bump — **never automatically on an epoch bump**
(auto-reissue would mint a current-epoch lease that immediately re-admits `run_command`,
defeating revocation — forbidden; see the non-self-healing invariant below).

### Load-bearing invariants preserved (the amendment does NOT reopen any B1/B2 fail-open)
- **`zero_trust_behavior: strip` STILL applies to first-party tools.** Under a stripped
  request, write/network/delegate/unsandboxed-exec-capable first-party tools (incl.
  `run_command`, `write_file`) are DROPPED — first-party ≠ strip-exempt. Only safe first-party
  tools survive a strip. (This keeps the S3 task-monotonic strip meaningful.)
- **`revocation_epoch` STILL applies, and revocation is NOT self-healing** (codex rev2): a
  first-party lease goes stale on an epoch bump like any lease. **First-party leases are NOT
  auto-reissued per-request** — reissuance is a deliberate act (startup, or an explicit
  re-issue after the operator clears the bump). So bumping the epoch actually REVOKES
  `run_command` fleet-wide until deliberate re-issue; automatic per-request reissuance would
  defeat revocation and is forbidden.
- **DEV-key degrade (B2) STILL applies** — if the signer is on the DEV key (no production
  secret), enforcement degrades to the safe-read allowlist; a first-party lease created under
  the DEV key is NOT verified/admitted (it hits the same S4 degrade, proven by an explicit test).
- **Deny-closed default** — a tool in NEITHER a candidate lease NOR the first-party manifest
  (with a valid first-party lease) is DROPPED. No fail-open.

## rev2 — codex REQUEST_REVISION folded (2026-07-25, C2-AMENDMENT-REVIEW-CODEX.md)
Codex (deepest F3 contributor) confirmed the core sound (5-file ceiling, lease-source-not-
exemption, deny-closed, PREPARED_ONLY+re-freeze+owner-activation, flag-default-OFF) but
REQUEST_REVISION on four amendment-specific edges — all folded:
- **(codex-1) Epoch reissuance must not undo revocation.** First-party leases are re-issued
  only deliberately, never automatically per-request → an epoch bump genuinely revokes. (Folded
  into the revocation_epoch invariant above.)
- **(codex-2) Bidirectional manifest↔bundle equality.** The completeness check is EXACT set
  equality between `config/first-party-tools.json` and the live `_TOOL_BUNDLES` set: a bundle
  tool missing from the manifest (silent deny) AND a manifest tool absent from the bundles
  (privilege EXPANSION — a non-existent/extra first-party grant) both FAIL the check, fail-closed.
- **(codex-3) Per-tool risk metadata is cryptographically BOUND, not read from the mutable
  manifest at check time.** Each first-party lease embeds its tool's risk classification
  (`write_capable`, `network_capable`, `trust_tier`, `zero_trust` category, constraints) inside
  the SIGNED canonical payload; the gate reads the classification from the VERIFIED lease, never
  from the on-disk manifest at admission. Schema-validate; fail closed on any manifest/lease
  mismatch. Tampering tests for EVERY privileged category (network, write, exec, secret,
  delegate), not only `run_command`/`write_file`.
- **(codex-4) First-party DEV-key regression test.** A cryptographically valid first-party lease
  created with the DEV key → enforcement enters the safe-read degrade, admitting nothing under
  the DEV key.

## Acceptance additions (incl. codex rev2 tests)
- Flag-ON, normal request: `run_command` (built-in) IS admitted via its first-party lease
  (NOT denied) — the regression the gap would have caused.
- Flag-ON, `zero_trust: strip` request: `run_command`/`write_file` first-party tools are
  DROPPED (strip still bites); a safe-read first-party tool survives.
- **Revocation (codex-1):** epoch bump → first-party leases stale → tools DROPPED, and they are
  NOT auto-reissued on the next request (a re-issue requires the deliberate step).
- Deny-closed: a tool absent from both the candidate leases and the first-party manifest → DROPPED.
- **Bidirectional equality (codex-2):** a bundle tool missing from the manifest FAILS closed;
  a manifest tool NOT in `_TOOL_BUNDLES` FAILS closed (no privilege expansion).
- **Bound-metadata tampering (codex-3):** mutating a tool's risk fields in the on-disk manifest
  does NOT change admission (the gate uses the SIGNED lease's classification); a lease whose
  bound metadata ≠ manifest FAILS closed. A tampering test per privileged category
  (network / write / exec / secret / delegate), not only run_command/write_file.
- **First-party DEV-key (codex-4):** a valid first-party lease created under the DEV key →
  safe-read degrade, admits nothing under the DEV key.

## Review outcome — CLEARED for C2 rev3
- codex (C2-AMENDMENT-REVIEW-CODEX.md): REQUEST_REVISION, 4 findings — folded (rev2).
- Opus confirmatory re-review (C2-AMENDMENT-REREVIEW-OPUS.md): REVISE — codex-2/3/4 confirmed
  genuinely closed; codex-1 had a residual contradiction (line 32 "re-issued on epoch bump"
  vs the non-self-healing invariant). **Fixed** (line 32 now: deliberate re-issue only, never
  auto on epoch bump) — the reviewer named this exact one-line fix and stated the amendment is
  then "safe to fold into C2 rev3 and re-freeze." Two NICE-TO-HAVEs deferred to C2
  implementation: define `lease_tools`/duplicate/`actions==[tool]` handling; name the signed-
  constraints field carrying the risk metadata.

**Status: CLEARED to fold into C2 rev3 + re-freeze.** The frozen C2 subject becomes the pair
{C2-DESIGN-AND-AUTHORIZATION.md, this amendment}, ceiling 4→5 (+ config/first-party-tools.json).
Still owner-gated, flag-default-OFF; prior freeze `313b723b` superseded (see C2-FREEZE rev2).
