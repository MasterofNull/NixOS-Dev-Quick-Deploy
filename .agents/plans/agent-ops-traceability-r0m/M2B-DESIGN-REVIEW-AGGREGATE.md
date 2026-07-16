# M2B Design Review Aggregate

Packet reviewed: `M2B-DESIGN-PACKET.md` SHA-256
`cce83b39c147423756c0d3187b2ad2f5db353645e73660625b27d448f01d11ce`
Date: 2026-07-16
Aggregate verdict: **REQUEST_REVISION**

Post-review disposition: **SUPERSEDED BY STRONGER RUNTIME EVIDENCE**

| Lane | Verdict | Disposition |
|---|---|---|
| Codex flagship | REQUEST_REVISION | Binding topology and activation defects accepted. |
| Antigravity flagship | PASS | Invariant validation retained; authorization recommendation superseded by unresolved concrete defects. |
| Fable flagship | unavailable | Two correctly routed `claude-fable-5` attempts exited with zero-byte evidence and were reconciled stale. |

Antigravity validated CAS, receipt contents, durable replacement, monitoring, and stop conditions. It
did not address how a non-serializable process-local receipt crosses the separate Bash/CLI process
boundary, and it treated a Git commit as an atomic cutover even though worktree wrappers are directly
executable while being edited. Reviewer-gate policy does not permit one PASS to erase specific
unresolved architecture defects.

Revision 4 therefore preserves Antigravity's accepted invariants while adding:

1. one Python launch supervisor that owns the receipt and barrier lifecycle in-process;
2. a closed activation manifest installed in `legacy` mode;
3. a separately authorized, exclusive-lock, zero-active-work, single-file switch to `enforced`;
4. separate M2B1 dormant-foundation and M2B2 live-activation acceptance.

No implementation authorization may be prepared from the superseded packet hash. Revision 4 requires
changed-scope flagship review.

An interactive Claude diagnostic confirmed the direct CLI/model/auth path works for a trivial prompt;
the compact serialized re-review still failed identically, so its absence is treated as headless-lane
reliability evidence rather than an abstention or negative design verdict.

Antigravity subsequently passed Revision 4's in-process supervisor and activation-lock design. After
that review, a live probe established that the managed caller sandbox uses parent-death/process-tree
cleanup and denies access to the user-systemd bus. Therefore an in-process child—even a correct
receipt-bound supervisor—cannot provide background durability. The PASS remains useful evidence for
receipt, locking, and activation invariants, but its M2B1 authorization recommendation is superseded.
The host-side socket-activated broker program now owns the execution-boundary requirement.

VERDICT: REQUEST_REVISION — re-review Revision 4 broker and activation-boundary changes before authorization
