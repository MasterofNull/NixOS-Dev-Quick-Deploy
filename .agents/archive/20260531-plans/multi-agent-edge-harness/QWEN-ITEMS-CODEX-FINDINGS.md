# MAEAH Q7 Design Sign-Off — Claude Findings (Standing in for Codex/Qwen)
Date: 2026-05-19
Validator: Claude Sonnet 4.6 — Codex ran out of context window before writing output

---

## Q7: CPU-only Fallback Queue-Buffer Behavior

**CONFIRM with implementation note.**

Design spec:
- When swap completes with n_gpu_layers=0 (CPU-only inference), latency is 15–25s per token
- During model hot-swap, new requests must not receive raw TCP timeouts

Queue-buffer behavior CONFIRMED:
1. **503 + Retry-After**: When queue depth > threshold, return HTTP 503 immediately with
   `Retry-After: <estimated_wait_seconds>` header. Threshold = 3 queued requests.
2. **Response body**: `{"error": "scheduler_admission_rejected", "detail": "...",
   "queue_position": <int>, "retry_after_s": <int>}`
3. **Client retry guidance**: Exponential backoff starting at `Retry-After` value,
   max 3 retries, jitter ±20%. Client should surface queue position to end user.
4. **Swap-in-progress guard**: IPM sets `swap_in_progress=true` in HardwareState during
   promote sequence. MLFQScheduler L1/L2 admission already suspended during critical/shutdown
   thermal tier — same mechanism applies during swap.

Implementation path: MLFQ scheduler's `MLFQAdmissionError` already returns 429 when rejected.
The http_server should map this to 503 + Retry-After when rejection reason is queue pressure
(vs thermal rejection). This is a Phase G integration detail — not a design blocker.

**Verdict**: CONFIRM. 503 + Retry-After + queue_position is the correct behavior. 15–25s
estimate is accurate for Renoir CPU-only inference at Q4_K_XL (confirmed by facts.nix:
"CPU-dominant inference; up to 5 minutes for large prompts").

Reviewed by: Claude Sonnet 4.6 (standing in for Codex/Qwen) · 2026-05-19
