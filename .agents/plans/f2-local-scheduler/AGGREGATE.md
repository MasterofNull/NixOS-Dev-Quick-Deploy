# F2 (Local Scheduler) — Aggregate (interim; ROUND OPEN for antigravity)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ · **codex** ✅ (112L) · **local[Qwen]** ✅ (salvaged — see note) · **antigravity** ⏳ inbox.

## Interim reading (3/4 landed)
Strong convergence on the design direction (matches claude's seed): **resident small model(s)
(4B/phi-4-mini + 8B) + 35B session-mode**, a **measured slot scheduler** (queue classes + MLFQ),
**VRAM-aware** swap management on the 4GB APU, **GBNF + grammar cache**, and declarative Nix wiring.
Local[Qwen] independently reached the same model-tier + VRAM-aware-scheduling design — convergence
confirmed even through a messy emission.

## local[Qwen] note (a live F2/reliability data point)
Its dispatch (`9ydtl2`) completed (1003s) but emitted its `write_file` as TEXT (0 tool calls) and
mislabeled itself "codex" in-body — the known local-model-review-lane-reliability quirks. Design
salvaged to `local.md`. This is itself evidence FOR F2 (fast-lane routing + GBNF would make local's
structured tool-emission reliable) and for the F1 typed-sidecar + collect-time extraction (so a
text-only local answer still yields a usable contribution).

## Status
3/4 landed, converging. Round OPEN for antigravity (inbox not yet processed by the IDE). Full
synthesis + top-3 merge when antigravity lands. The claude seed's headline move — a **resident
fast-lane server `:8082`** to end the single-slot serialization — is being demonstrated live right
now: 4 local dispatches are serialized behind the one 35B slot.
