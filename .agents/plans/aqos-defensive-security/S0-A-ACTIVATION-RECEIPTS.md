# Track S — S0-A Activation Receipts (self-contained ledger)

Recorded per the Claude confirmatory review's advisory-A (bind the independent PASSes to the
exact AM1 post-change hashes so activation is self-contained).

## Independent PASS receipts
- **codex** — independent review PASS (primary gate; 2 blocking revisions required + then
  resolved: deterministic duplicate-ID rejection in `_load_registry`; bounded `propertyNames`
  on `tool_schemas` keys + nested `toolSchema.properties`).
- **Claude (Opus, fable-5 lane)** — confirmatory catch-up review CONFIRM-PASS 2026-07-29
  (`S0-A-CLAUDE-CONFIRMATORY-REVIEW.md`): all 9 axes verified against source; fail-closed
  (invalid/duplicate registry → ValueError→exit 2, empty stdout); registry `+81/-0`, 11
  baseline records incl. `t3mp3st` byte-unchanged; new records derive `review-recommended`.

## Frozen AM1 post-change hashes (subject of both PASSes)
- schema `d080957b…`
- CLI `cdf59fc5…`
- test `cd4aaebf…`
- registry input `ab5d56ac…` (matches AM1 frozen input)

## Advisory (non-gating)
- The antigravity advisory review (`antigravity-track-s-review.md`) is UNTRUSTED and factually
  loose — it claims "sandboxed containers" + "SHA-256 append-only logs" that do NOT exist at
  S0-A (actual dispositions are more conservative). Its 10/10 does NOT count as substantive
  verification. Consistent with the standing antigravity-untrusted-advisory finding.
