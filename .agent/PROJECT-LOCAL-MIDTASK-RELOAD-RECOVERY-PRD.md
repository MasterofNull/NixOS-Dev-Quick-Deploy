# Local mid-task model-reload recovery

## Objective

Prevent a local agent task from failing solely because llama.cpp is reloading
between a transport retry and its replacement request.

## Evidence

`local-20260828-102647-4e39k2` received a switchboard 502 when the prior
llama process was killed, then received `503 Loading model` while the new
model loaded.  The model was ready about 62 seconds later, but the executor
treated the 503 as terminal.

## Bounded change

- Preserve the existing ordinary reduced-token retry after a transport error.
- Only an executor error explicitly identifying local `503` and `Loading
  model` may start a readiness poll.
- Poll the canonical direct `LLAMA_URL` `/health` surface (not switchboard's
  aggregate health) for at most the smaller of 120 seconds and the enclosing
  task's remaining hard wall budget, then replay the already-reduced request
  once without changing messages, routing, authority, or token budget.
- Each health probe is capped by the remaining wait budget. If a direct
  `LLAMA_URL` is unavailable while routed through switchboard, fail closed.
- Propagate all other 503s and a readiness timeout unchanged.

## Acceptance criteria

- A fake 502, then loading 503, then not-ready/ready health sequence succeeds
  on the one replay.
- A 503 with another body remains terminal and does not poll.
- A smaller remaining hard wall budget caps the wait and each probe timeout.
- A probe that consumes the remaining wait budget returns without a stale sleep.
- Switchboard routing selects direct `LLAMA_URL`; a switchboard-only 200 cannot
  mark the model ready.
- Focused hermetic test and Python compilation pass.

## Explicit exclusions

No service restart, deployment, routing change, retry loop, environment
variable, or remote-fallback change is part of this slice.
