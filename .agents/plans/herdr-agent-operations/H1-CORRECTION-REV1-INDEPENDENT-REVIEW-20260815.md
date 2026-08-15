---
doc_type: design-review
id: herdr-h1-correction-rev1-independent-review-20260815
title: HERDR H1 correction revision 1 independent review
status: complete
parent_prd: herdr-h1-correction
reviewer: "Codex (independent reviewer; did not author the correction subjects)"
verdict: "REQUEST_REVISION"
date: 2026-08-15
---

# HERDR H1 correction revision 1 independent review

This immutable receipt records the independent review of the six exact H1 correction subjects below. It does not accept H1, authorize runtime behavior, or apply to subsequently revised bytes.

## Reviewed subjects

| Subject | SHA-256 |
|---|---|
| `.agent/PROJECT-HERDR-H1-CORRECTION-PRD.md` | `78f4df5180309b2f7bf9f9a7bfde09272ceaab62766b174c980baa81ce2f3918` |
| `.agents/plans/herdr-agent-operations/H1-CORRECTION-DESIGN-20260815.md` | `cd37147083bb573d3c46541af0e08c528a471b5c1966c25b44bea4aea4c37431` |
| `.agents/plans/herdr-agent-operations/evidence/H1-SBOM.spdx.json` | `fba41f3915bac79154784d46efcebeeae5f4852c7cb5df6aed3445895ebc1b94` |
| `.agents/plans/herdr-agent-operations/H1-SUPPLY-CHAIN-REPORT.md` | `47643c3bd9da628b3679f82d0ede41fb5f13e267468d2ee72a1c75586e8b3663` |
| `.agents/plans/herdr-agent-operations/tracker.json` | `74ce08c1001af970e8450b6a55393531a9b154fd9c9bc60c8b1c163919f3f7d5` |
| `scripts/testing/test-herdr-h1-contract.py` | `a0471200f2238e2b95b5c9bc3ebf5c73529fc4ea75e550ed81ff586830f0f42a` |

Frozen predecessor: `ea96bcbfc05fca32d164137fd2cef261f5c68acc`.

## Verdict

`REQUEST_REVISION`.

The sole blocking finding was that the SPDX SBOM did not satisfy the correction PRD's deterministic-normalization requirement. It retained a generation-time timestamp, an unnormalized root package name/SPDXID containing the physical Nix-store scan path, and unsorted package, file, and relationship arrays. The correction also lacked a documented reproducible Syft generation and normalization pipeline. The SBOM, its recorded hash, and dependent report evidence therefore required revision and a fresh hash-bound review.

All other reviewed correction requirements passed: all six subject hashes matched; the five behavior/runbook files remained byte-identical to the frozen predecessor; the hermetic and real Home Manager/Nix evaluation evidence was consistent with the test assertions; the fresh no-link build and `herdr 0.7.5` receipts were truthful; SPDX structure, counts, unique identifiers, and relationship integrity checked out; and no runtime authority, activation, service, socket, secret, or sensitive host-path leakage was introduced. Tier-0 had not run and was not credited; it remained a separate pre-commit gate.

The reviewer made no modifications during the review and ran no tests, builds, Nix evaluation, Syft generation, Tier-0, staging, commit, or HERDR runtime action.

VERDICT: REQUEST_REVISION — deterministically normalize the SPDX SBOM, document its reproducible generation pipeline, refresh dependent hashes/evidence, and obtain a fresh independent review
