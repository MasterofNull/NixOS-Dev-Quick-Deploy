# aq-wiki body-hash cache keying — independent review

Author: Codex (tracked scripts/ai/aq-wiki, re-targeted from the gitignored ua-batch-processor.py).
Reviewer: Claude Opus 4.8 (orchestrator, NON-AUTHOR). Rule 18: local-direct reviewer flaky x2, sonnet uncertain -> next eligible non-author flagship reviewed; cross-lane confirmatory queued.
Verified: py_compile PASS; test-aqwiki-bodyhash-cache.py 3/3 (same body->skip; changed->regen+rehash; missing hash->regen); _body_sha256 gate = git-changed AND (missing hash OR mismatch); backward-compatible; additive body_sha256 map only; `aq-wiki --status` intact (no schema break); stdlib hashlib only; on the TRACKED file.
Verdict: PASS. Cross-lane confirmatory queued (advisory).
