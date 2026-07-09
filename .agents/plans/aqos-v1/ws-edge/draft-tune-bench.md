# Bench prep — specDraftNMax 2 → 3 (speculative decoding tune, god-tier prompt 6)

**Date**: 2026-07-09 · **Status**: ready to run when the local slot is free
**Free + reversible**: one nix option, no model change, no rebudget. Helps only
if MTP draft-acceptance > ~60%; a clean-slot A/B tells us.

## Hypothesis
The running server uses `--spec-draft-n-max 2`. `nix/modules/core/options.nix`
notes higher values improve throughput when acceptance rate > 60%. Raising to 3
drafts more tokens per step; if the 35B accepts them, tok/s rises; if not, it
wastes draft compute and tok/s falls. Measured, not assumed.

## The one-line change (apply only for the B run)
`nix/hosts/hyperd/facts.nix`:
```nix
llamaCpp.specDraftNMax = 3;   # was 2
```
Then `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` and let the model reload.

## Method (A/B, clean slot — the eval-contention guard now protects this)
Run each arm 3× and take the median. Do NOT run under other local load (the
prompt-5 slot-contention guard applies to evals; for a manual bench, confirm
`curl -s localhost:8080/slots | jq '.[0].is_processing'` is false first).

```bash
# Arm A (current, draft-n-max=2) — capture baseline BEFORE changing nix:
python3 scripts/testing/bench-local-agent.py --runs 3 --json > /tmp/bench-draft2.json
# read median predicted_tokens_seconds
curl -s localhost:8080/metrics | grep predicted_tokens_seconds

# ... apply the nix change + rebuild ...

# Arm B (draft-n-max=3):
python3 scripts/testing/bench-local-agent.py --runs 3 --json > /tmp/bench-draft3.json
curl -s localhost:8080/metrics | grep predicted_tokens_seconds
```

## Decision rule (publish the delta)
- B median tok/s ≥ A × 1.05  → keep specDraftNMax=3 (commit the nix change + note the %).
- B within ±5% of A          → revert to 2 (no benefit, less draft waste).
- B < A × 0.95               → revert to 2 (acceptance too low at n=3).

Record the result in `.agent/ACTIVATION-AUDIT.md` and update
`LOCAL_TOK_PER_SEC` in `shared/llm_config.py` if the anchor moved.

## Note
This is orthogonal to the SMALL_RESIDENT rebudget — run it independently. The
current measured anchor is ~2.96–3.45 tok/s WITH draft-n-max=2 already active
(MTP self-speculative), so this bench measures the marginal gain of n=2→3 only.
