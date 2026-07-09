BOUNDED TASK — local/Qwen lane, round aqos-v1 (resend, envelope-fit).

Your FIRST action and your LAST action MUST both be a write_file tool call to
the path: .agents/plans/aqos-v1/local.md

Do NOT read more than 2 files. Do NOT explore. Score from the summary below.

Read at most: .agent/PROJECT-AQOS-PRD.md (section 5 workstreams WS1-WS10 only).

Then write_file to .agents/plans/aqos-v1/local.md with EXACTLY this structure:

# local[Qwen] — aqos-v1 ratification

## Scores
WS1: <1-10> — <=10 words
WS2: <1-10> — <=10 words
WS3: <1-10> — <=10 words
WS4: <1-10> — <=10 words
WS5: <1-10> — <=10 words
WS6: <1-10> — <=10 words
WS7: <1-10> — <=10 words
WS8: <1-10> — <=10 words
WS9: <1-10> — <=10 words
WS10: <1-10> — <=10 words

## Top risk
<one sentence>

## Verdict
RATIFY | RATIFY-WITH-AMENDMENTS | REJECT — <one sentence>

RULES:
- The task is DONE only when write_file has actually written local.md. Narrating
  "COMPLETED" without a write_file call is a FAILURE and will be rejected.
- Keep total output under 400 tokens. One write_file call. No commit.
