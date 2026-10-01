#!/usr/bin/env python3
"""classify_tokens size-down signals must not fire on embedded payload text."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai" / "lib"))
from dispatch import classify_tokens  # noqa: E402

CASES = [
    ("short exact-reply ping stays tiny",
     "Reply with exactly READY and nothing else.", 150),
    ("short brief summary stays small",
     "Summarize in two lines what this module does.", 400),
    ("review with signal after long head is not capped",
     "Read-only independent review, reviewer role. " + "Context sentence. " * 30
     + "Reply with VERDICT: PASS or REQUEST_CHANGES.\nDIFF:\n+ping()\n", None),
    ("embedded diff keyword is ignored",
     "Review this change for correctness.\n" + "x = 1\n" * 80 + "# reply with ping\n", None),
]


def main() -> int:
    failed = 0
    for name, prompt, expected in CASES:
        got = classify_tokens(prompt)
        ok = got == expected
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name} (got {got}, want {expected})")
    print(f"\n{len(CASES) - failed}/{len(CASES)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
