# ADR 0004: LangGraph deferred

Status: Accepted (owner 2026-11-27, defaults answer)
Source: rev 4 D3. Implementation slice: none.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

LangGraph core could provide durable replay and interrupt for the coordinator run store. No gap in the existing coordinator has been demonstrated.

## Decision

DEFER. Revisit only if live replay or interrupt tests of the coordinator run store show a gap. Core only, never `langgraph-api` (CVE-2026-55235 and -55236), and one authoritative store.

## C1-C5 check

C1 PASS (hosted SDK path not required). C2 PASS (Python). C3 PASS (nixpkgs 1.1.10). C4 adds the langchain-core tree. C5 PASS.

## Licence

MIT (core).

## Reversal trigger

A demonstrated replay or interrupt gap in a live coordinator run-store test.
