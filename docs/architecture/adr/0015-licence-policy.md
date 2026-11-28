# ADR 0015: Licence policy: invocation versus linking or vendoring

Status: Accepted (owner 2026-11-27, defaults answer)
Source: C5, D12. Implementation slice: S1d.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

The project is AGPL-3.0-or-later with a `COMMERCIAL-LICENSE`. EUPL-1.2, MPL-2.0 and other copyleft code interacts with that differently depending on how it is used.

## Decision

Invoking an unmodified binary is allowed for any licence that permits use. Linking, vendoring or modifying needs a licence the owner can pass through both `LICENSE` and `COMMERCIAL-LICENSE`: MIT, BSD and Apache-2.0 are acceptable; EUPL, MPL, GPL and AGPL-only code is blocked without an owner-signed waiver. Record per dependency whether it is invoked, linked, vendored, modified or redistributed; an SPDX label alone is insufficient. `check-licence-closure` fails an unresolved `meta.license`.

## C1-C5 check

C5 is the subject of this ADR. C1-C4 n/a.

## Licence

The EUPL-1.2 and AGPL-3.0 compatibility reading is from licence text and is UNVERIFIED at source; the owner confirmed the invocation rule under D12.

## Reversal trigger

A dependency that must be linked or vendored under a blocked licence.
