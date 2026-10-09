# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-010

## Objective
- Owner: trial the Q4 model. Q5_K_S MTP (23.8 GiB) could not stay resident beside the desktop: swap drift to 0.76 tok/s, and a Vulkan DeviceLost at 21:24 on 2026-10-08. Switch to Q4_K_XL MTP (21.3 GiB): same family, same MTP heads and the same `--spec-type draft-mtp --spec-draft-n-max 2` args. The non-MTP Q4_K_M already on disk would break the draft-mtp args, so it was not used.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- The orchestrator made the edits directly (2-line catalog/facts change plus a sha pin).

## Commands Executed
```bash
aria2c parallel fetch -> ~/Downloads/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf (22853663008 bytes)
sha256sum == HF x-linked-etag 55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1
aq-model-switch --dry-run qwen3.6-35b-mtp   # would switch
nix eval llama-cpp ExecStart: --model active.gguf ... --spec-type draft-mtp --spec-draft-n-max 2
```

## Validation Evidence
- Catalog entry added (config/model-catalog.yaml); facts.nix activeModel is qwen3.6-35b-mtp; the sha256 is pinned in the Nix model catalog, so the fetch service accepts the installed file without re-downloading.

## Rollback Plan
- `sudo aq-model-switch qwen3.6-35b-mtp-q5` (no rebuild) and revert facts.nix.

## Residual Risk
- Quality versus Q5 is unmeasured until the post-switch eval (throughput, residency and a direct-mode quality check). This is an MVP trial, not done.

## Hint Feedback
- None.
