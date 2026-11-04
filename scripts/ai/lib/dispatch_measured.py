#!/usr/bin/env python3
"""Routing S1: launch dispatch.py with the exact prompt preflight measured.

dispatch.py is whole-file pinned by the L2B contract, so it stays unmodified; this
launcher imports it, replaces its two live prompt-assembly steps (context assembler,
embedded-assist prefetch) with the already-measured result, then runs its own main().
`--assembled-file` is consumed here; a missing/mismatched file fails the launch.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dispatch as D  # noqa: E402
import dispatch_evidence as de  # noqa: E402


def _pop(argv: list, flag: str):
    if flag not in argv:
        return None
    i = argv.index(flag)
    value = argv[i + 1] if i + 1 < len(argv) else None
    del argv[i:i + 2]
    return value


def main() -> int:
    argv = sys.argv[1:]
    assembled = _pop(argv, "--assembled-file")
    task_id = argv[argv.index("--task-id") + 1] if "--task-id" in argv else ""
    output = argv[argv.index("--output") + 1] if "--output" in argv else ""
    prompt = de.load_assembled_prompt(assembled, task_id) if assembled else None
    if prompt is None:
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            Path(output).write_text(f"Error: assembled prompt {assembled} missing or not for task {task_id}")
        print(f"assembled prompt unavailable: {assembled}", file=sys.stderr)
        return 1
    D._apply_context_assembler = lambda _p, _t, _o: prompt
    D._embedded_assist_prefetch = lambda *_a, **_k: ""
    sys.argv = [sys.argv[0]] + argv
    return D.main()


if __name__ == "__main__":
    sys.exit(main())
