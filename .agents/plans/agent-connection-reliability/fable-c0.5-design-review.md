# Fable Flagship Design Review — C0.5A

Reviewer: `claude-fable-5`
Dispatch: `claude-20260716-141123-n2apuq`
Role: independent flagship architecture/security/SRE/contract reviewer
Subject: `.agents/plans/agent-connection-reliability/C0.5-DESIGN-PACKET.md`

The existing round models may remain untouched. The new pure module can derive receipt/feedback
evidence from immutable RoundManifest, Contribution, dispatch, assignment, policy, and evidence
inputs. It owns no persistence or lifecycle transitions. The three schemas are generated/frozen
projections from one Pydantic/semantic SSOT with deterministic byte-equality gating.

Confirmed sufficient: exact bounded inventory, total contribution/reviewer verdict mapping,
policy-driven quorum, trusted independence lineage, material-rewriter recusal and revision rules,
critical advisory dissent disposition, immutable/independently verified promotion evidence, local
modality semantics, schema bounds, C0 linkage, and deterministic golden vectors.

Non-blocking implementation precision requirements:

1. Pin a total mapping for every existing lane state, including nonterminal and `amended`, and add
   still-running-required-lane and amended-lane vectors.
2. Pin the receipt terminal-decision precedence lattice in policy and fixtures.
3. State exactly which documents compose the pre-implementation policy subject hash.
4. Use `incomplete` before critical dissent disposition and policy-derived `revision_required` or
   another terminal after disposition.

Implementation remains separately authorized; this review grants no live authority.

VERDICT: PASS — C0.5A is a bounded, pure, injection-only adjudication/feedback projection with a single Pydantic SSOT, total verdict mapping, fail-closed quorum/independence/poisoning defenses, and pinned deterministic vectors; the four residual ambiguities are non-blocking precision items resolvable within the stated inventory.
