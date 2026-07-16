# Codex Design Review — C0.6 Revision 1

**Reviewer principal:** `codex-subagent-c05a-acceptance-matrix`
**Role:** independent read-only architecture, security, SRE, and local-inference reviewer
**Subject hash:** `f79155808caeeda54f8388486395ddd79d2267a2b5cafc0cdc63b83d56d1a979`

The root-cause evidence was strong, but implementation was blocked on eight contract defects:

1. A monotonic timestamp cannot be durably replayed across process/host restart.
2. Queue/provider phases could consume the cleanup reserve.
3. External cancellation convergence could not be guaranteed within the inventory.
4. Caller, policy, tier, and research-to-review timeout precedence was ambiguous.
5. New failures risked a parallel lifecycle taxonomy instead of C0 reason mapping.
6. Partial-output permissions, bounds, redaction, and acceptance state were not binding.
7. The ten-file slice could not satisfy dashboard/service coverage by itself.
8. Boundary, cancellation, partial-output, mapping, and late-success vectors were incomplete.

VERDICT: REQUEST_REVISION — resolve deadline durability/reserve semantics, cancellation authority, timeout precedence, canonical reasons, privacy, and visibility delivery.
