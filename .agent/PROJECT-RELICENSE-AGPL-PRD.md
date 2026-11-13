# PRD: Relicense to AGPL-3.0-or-later with a commercial option

Status: owner-directed 2026-11-12. The owner holds the copyright and directed the change.
Owner request: ensure reciprocity and attribution from people and companies who build on this
system; welcome personal and research use that gives back to the public domain; do NOT ship any
covert tracking/"call-home" mechanism.

## Decision

- The project's own code moves from MIT to **GNU AGPL-3.0-or-later**.
- A separate **commercial license** is offered for commercial/hosted use that will not meet the
  AGPL's source-disclosure terms (COMMERCIAL-LICENSE).
- No telemetry, beacon, or usage-reporting code is added, now or later. Enforcement is by the
  license, observed openly. (A covert reporting mechanism was considered and rejected: it would be
  spyware/backdoor behaviour, would exfiltrate data from third-party machines, and is unenforceable;
  the MIT grant also made prior use permitted, so there was nothing to detect.)

## Why AGPL (not a tracker)

- AGPL §13 is the enforceable, open form of the owner's intent: run a modified version as a service
  and you must offer users your source. That pressures commercial "take and don't give back" use by
  obligation, not guilt.
- Personal use, study and research stay unburdened; sharing improvements upstream or in papers is the
  reciprocity hoped for; CITATION.cff is the courtesy asked in return.
- Dual-licensing turns "profits off the author's time" into either give-back or pay — a standard model.

## Scope of this change

Relicensed (first-party):
- LICENSE -> full AGPL-3.0 text (GNU canonical, sha256 0d96a4ff…abcb0).
- NOTICE (copyright, AGPL summary, reciprocity, prior-MIT note, third-party exclusions).
- COMMERCIAL-LICENSE, CITATION.cff.
- README license/citation/support section and badge.
- nix/pkgs/agentic-tools.nix meta.license mit -> agpl3Plus (packages our own scripts/agent-tools).

NOT changed (correctly):
- ai-stack/agents/skills/*/LICENSE.txt — Anthropic's materials, "all rights reserved"; excluded in NOTICE.
- nix/pkgs/*.nix meta.license on packaged third-party tools (models-dev, opencode, maigret, mosaic,
  rtk, pi-agent): these declare the UPSTREAM license and must stay accurate.
- assets/vendor/**, node_modules, lockfiles, dependency SPDX tags: upstream licenses retained.
- config/*.json and tasks_inbox notes referring to dependencies' MIT status: factual, left as-is.

## Legal notes

- The owner is effectively the sole copyright holder: `git shortlog -sne` shows all commits under the
  owner's identities (MasterofNull and the local NixOS User alias). No third-party contributor
  copyright blocks the relicense.
- MIT is irrevocable for already-distributed copies: commits up to the one before the relicense remain
  MIT-available. Historical text preserved at LICENSE-MIT-historical.
- AGPL is compatible with the MIT/Apache/permissive dependencies bundled here (their notices are kept).

## Follow-ups (separate slices)

- First-party `meta.license` sweep: add `agpl3Plus` to our own flake packages that omit a license
  (e.g. harness-contracts), while leaving third-party package declarations untouched. Needs a careful
  first-party vs third-party audit, so it is not bundled here.
- Add per-file SPDX headers (`SPDX-License-Identifier: AGPL-3.0-or-later`) to first-party source as a
  later mechanical slice.
- GitHub "commercial-license request" issue template.
- Trademark/name check before any public branding of the persona name (tracked with the persona PRD).

## Acceptance

- GitHub detects the repo license as AGPL-3.0 (driven by LICENSE).
- LICENSE is the verbatim canonical AGPL-3.0 text; NOTICE, COMMERCIAL-LICENSE, CITATION.cff present.
- README states the license, reciprocity, commercial option, and the no-telemetry commitment.
- Third-party licenses are untouched and explicitly excluded in NOTICE.
- tier0 and manifest gates pass; independent review via aq-land.
