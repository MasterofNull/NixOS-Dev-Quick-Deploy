---
review_kind: "independent exact authorization review"
reviewer_role: "Codex independent reviewer"
subject: "RUNNER-DEPLOYMENT-HARDENING-IMPLEMENTATION-AUTHORIZATION-20260801.md"
subject_sha256: "a89eb74b54abab137e742093ccb4715af101fb6f118b82147e385fd89fedf357"
reviewed_head: "17f899bf838973c755ab7a3e6095ec04a2e74220"
verdict: "REQUEST_REVISION"
implementation_authorization: "NONE"
activation_authorization: "NONE"
---

# Runner-Hardening Implementation Authorization — Independent Review

## Exact binding assessment

The subject hash is
`a89eb74b54abab137e742093ccb4715af101fb6f118b82147e385fd89fedf357`.
Its declared base HEAD matches the current HEAD
`17f899bf838973c755ab7a3e6095ec04a2e74220`.

The current hashes match the authorization/freeze for all four editable paths:
`execution_cell_runner.py` (`34837d…60fb`),
`test-execution-cell-runner.py` (`4f8094…93ef`),
`execution-cell-runner.nix` (`d2f12a…1d12`), and `env-contract.yaml`
(`62450e…440f`). The `switchboard.nix` no-edit anchor also matches
(`10e3bb…343a`). The referenced revised design (`48cae30d…0c63`), freeze
candidate (`430093d…25df`), and Foundation-C acceptance
(`3e79f45e…102f`) match their claimed current bytes.

The scope remains correctly narrow and PREPARED_ONLY: four default-OFF files
only, with no new file, stage, commit, runtime, deployment, traffic, or owner
activation conferred by these bytes.

## Blocking finding

The declared exact reviewed chain includes a “Revision-3 binding review” with
SHA-256
`c802f5f50c140129925ae5067b444d2fb5a6b1db24b8373e3832dab5226b89ca`.
No corresponding review record is present in the reviewed planning corpus, and
the authorization neither gives its path nor records its verdict, reviewer role,
or the exact predecessor subjects it assessed. A digest alone is not reviewable
evidence: this independent reviewer cannot verify that it is an independent PASS
over the design/freeze chain, rather than an unavailable, stale, or non-PASS
artifact. The authorization therefore overclaims an exact reviewed chain.

Correct the authorization by adding the immutable review path, exact subject
hashes, reviewer identity/role, and a verified `PASS` verdict (or remove that
claim and obtain such a review before any owner act). Re-freeze this
authorization after the correction; a new independent review must then bind its
new exact SHA.

## Verdict

**VERDICT: REQUEST_REVISION.** The concrete ceiling and current anchors are
sound, but the unavailable Revision-3 review prevents this grant from becoming
hash-bound authorization. This verdict confers no implementation, activation,
staging, commit, build, provider/network, or deployment authority.
