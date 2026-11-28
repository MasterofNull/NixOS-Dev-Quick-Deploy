# ADR 0006: LiteLLM: keep the custom switchboard

Status: Accepted (owner 2026-11-27, defaults answer)
Source: rev 4 D4. Implementation slice: none.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

LiteLLM could replace the switchboard as an OpenAI-compatible proxy. The nixpkgs pin 1.86.0 is inside GHSA-3cv6-jpf6-8222 (< 1.94.0) and PyPI 1.107.0 is GHSA-92x9-889m-jgmw. It adds a key store and Postgres.

## Decision

KEEP-CUSTOM (switchboard). Reference the API shape only. Never vendor its `enterprise/` directory.

## C1-C5 check

C1 PASS (llama.cpp path untested). C2 PASS for the proxy (prebuilt admin UI UNVERIFIED). C3 PASS as a pin, but the pin is a security gate failure. C4 adds a key store and Postgres. C5 never vendor `enterprise/`.

## Licence

MIT, with a separate licence for `enterprise/`.

## Reversal trigger

A switchboard maintenance cost that exceeds the adoption cost, with a pin outside the advisory ranges.
