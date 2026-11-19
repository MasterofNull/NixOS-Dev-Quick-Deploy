# MCP probe natural-exit race

QA run 43815332520 failed with `crash: stderr/exit not captured: 'boom: cannot start' None` on main 4cbcdf63d. Stdout EOF can precede process termination; a single poll loses the natural exit code.

The producer now waits at most 500 ms, capped by the remaining handshake deadline, in the two EOF states before cleanup. A child that remains alive keeps `exit=None`; cleanup signals are never reported as its natural exit. No dependency or protocol change.

Regression evidence: `SWEEP_LANES_SCRIPT` pointed at the original producer produced exactly two failures (initialize and tools/list delayed exits returned None, expected 7). The repaired `python3 scripts/testing/test-sweep-lanes.py` passed all fixture, fake-server, timeout and descendant-cleanup checks. The additional stdout-closed/live-child case stays bounded and verifies the child is gone afterward. `git diff --check` passed.

Independent native Codex review: PASS, no correctness blocker. The overall handshake includes existing stderr and process-cleanup time beyond its protocol deadline; this is not a strict total-runtime guarantee. Gemini diagnostic dispatch died during session interruption and relaunch was permanently rejected by the shell allowlist; no Gemini approval is claimed. Shared catch-up handoff preserves Gemini's four existing slice assignments.

Activation attestation: existing QA caller exercises this producer; observable fields and cleanup remain intact. Main integration and CI are pending landing. No system switch, restart, rollback or owner release acceptance performed. Older Nix runner communication loss remains unconfirmed; unavailable logs do not establish an OOM cause.

Staged validation caught a 202-line memory index exceeding the 200-line contract. The new repair pointer now shares the existing index entry; the index is 200 lines. The failed gate reported 69 passed and one focused-check failure. A fresh staged gate is required before commit. MemoryBroker accepted a queued fact (ad00f79f-c8bf-4ff9-b7aa-6545a319a31f); durable persistence is unconfirmed.
