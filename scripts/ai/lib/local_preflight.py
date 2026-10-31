#!/usr/bin/env python3
"""Routing S1: refuse oversize local work before launch.

Standalone on purpose: dispatch.py is whole-file pinned by the L2B contract, so
this resolves the same config via dispatch's own helpers (imported, unmodified)
and builds the request with the same builder, then measures it.

Exit 0 = fits (prints preflight JSON); exit 3 = refused (JSON on stderr, output
file written, failed/outcome=refused registry row recorded).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dispatch as D  # noqa: E402
import dispatch_evidence as de  # noqa: E402
from task_config import TaskConfig  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task-id", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--mode", default="auto")
    p.add_argument("--task-type", default=None)
    p.add_argument("--role", default="auto")
    p.add_argument("--prompt", required=True)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--max-tokens", type=int, default=None)
    p.add_argument("--tool-manifest", default="full")
    p.add_argument("--delegation-dir", required=True)
    p.add_argument("--llama-url", default="http://127.0.0.1:8080")
    a = p.parse_args()

    # Mirrors dispatch.main() delegate resolution; drift only skews the estimate.
    mode = D.classify_mode(a.prompt) if a.mode == "auto" else a.mode
    tokens = a.max_tokens if a.max_tokens is not None else D.classify_tokens(a.prompt, mode)
    task_type = (D.classify_task_type(a.prompt, mode)
                 if (not a.task_type or a.task_type == "auto") else a.task_type)
    hint = None
    if tokens is None:
        try:
            from llm_config import get_task_profile
            prof = get_task_profile(task_type)
            hint = prof.max_tokens_hint if prof else None
        except Exception:
            pass
    role, prompt = a.role, a.prompt
    aa = D._auto_assign
    if aa is not None and aa.enabled():
        role = aa.resolve_role(a.role, a.prompt)
        block = aa.skill_hint_block(a.prompt, D._REPO_ROOT)
        if block and block not in prompt:
            prompt = f"{prompt}\n\n{block}"
    elif a.role == "auto":
        role = "implementer"
    cfg = TaskConfig.from_args(
        mode=mode, role=role, timeout_secs=a.timeout, max_tokens=tokens,
        llama_url=a.llama_url, hybrid_url="", ralph_url="", task_type=task_type,
        max_tokens_hint=hint, tool_manifest=a.tool_manifest)

    messages = D._prepend_grounding([], cfg)
    messages.append({"role": "user", "content": prompt})
    payload = D.build_llama_payload(messages, max_tokens=cfg.max_tokens, stream=True,
                                    role=cfg.role, task_type=cfg.task_type)
    pf = de.preflight(payload.get("messages", []), cfg.max_tokens, a.llama_url, mode)
    if pf["verdict"] != "refuse":
        print(json.dumps({"refused": False, "preflight": pf}))
        return 0

    refusal = de.refusal_json(a.task_id, pf)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(refusal + "\n")
    D.TaskRegistry(Path(a.delegation_dir)).append(
        task_id=a.task_id, description=a.prompt, output_file=str(out), mode=mode,
        role=cfg.role, pid=None,
        extra={"status": "failed", "terminal_reason": "preflight_refused",
               "outcome": "refused", "preflight": pf, "model_effective": "n/a"})
    print(refusal, file=sys.stderr)
    return de.PREFLIGHT_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
