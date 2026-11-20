---
subject: llama-cpp.n-gpu-layers
claim: GPU layers ceiling is 12 because the Renoir APU has 4 GB shared VRAM; never suggest n_gpu_layers above 12.
evidence: CLAUDE.md:64
instance: Simurg@claude/sonnet-5.5#p3build
---
