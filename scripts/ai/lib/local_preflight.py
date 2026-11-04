#!/usr/bin/env python3
"""Routing S1: refuse oversize local work before launch.

Standalone on purpose: dispatch.py is whole-file pinned by the L2B contract, so
this resolves the same config via dispatch's own helpers (imported, unmodified)
and builds the request with the same builder, then measures it.

Exit 0 = fits (prints preflight JSON, leaves <output>.preflight.json for the
registry row); exit 3 = refused; exit 4 = preflight itself failed (also a refusal) (JSON on stderr, output
file written, failed/outcome=refused registry row recorded).
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dispatch as D  # noqa: E402
import dispatch_evidence as de  # noqa: E402
from task_config import TaskConfig  # noqa: E402


def _agent_payload(a, cfg, prompt):
    """First aq-agent-loop LLM request: executor system prompt + the full tool
    schema set + task, built by the executor's own functions. Returns
    (payload, output allowance). Later turns carry history and are not covered."""
    import importlib.machinery
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "aq-agent-loop"
    loader = importlib.machinery.SourceFileLoader("aq_agent_loop_pf", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    import agent_executor as ae  # path set up by aq-agent-loop import
    registry = mod.build_registry(tool_manifest=a.tool_manifest)
    ex = ae.LocalAgentExecutor(llama_endpoint=a.llama_url, tool_registry=registry,
                               enable_fallback=False, offline_mode=True,
                               allow_degraded_local_execution=True)
    tools = registry.get_tools_for_model()
    if not ae._LOCAL_ALLOW_COMMIT:
        tools = [t for t in tools if t.get("name") not in ae._AEXEC_COMMIT_TOOLS]
    task_text = D._augment_prompt_with_grounding(prompt)
    proj = mod.select_local_skills(task_text, repo_root=mod._REPO_ROOT)
    context = {"local_skill_projection_status": proj.status,
               "local_skill_names": list(proj.skill_names),
               "local_skill_projection_reason": proj.reason,
               "_local_skill_projection": proj.prompt}
    messages = [
        {"role": "system", "content": ex._get_system_prompt(
            ae.AgentType.AGENT, tools, task_text, proj.prompt)},
        {"role": "user", "content": "Think step by step before calling any tools. "
                                    "State your reasoning (Thought: ...) before each tool call.\n\n" + task_text},
        {"role": "system", "content": f"Context: {json.dumps(context)}"},
    ]
    out_tokens = max(ae.AGENT_TOOL_CALL_MAX_TOKENS, ae.AGENT_TASK_MAX_TOKENS)
    kwargs = {"max_tokens": out_tokens, "role": cfg.role, "stream": True}
    if cfg.task_type:
        kwargs["task_type"] = cfg.task_type
    gbnf = ex._tool_call_grammar(tools)
    if gbnf:
        kwargs["grammar"] = gbnf
    payload = ae.build_llama_payload(messages, **kwargs)
    # The agent system prompt already lists the tools; also count the raw schemas
    # so the estimate stays an upper bound (byte-counted only, never sent to the server).
    payload["_tool_schemas"] = tools
    return payload, out_tokens


def _run() -> int:
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
    p.add_argument("--record-error", action="store_true",
                   help="only record a preflight_error refusal row (used by the shell shim)")
    p.add_argument("--error-code", type=int, default=None)
    a = p.parse_args()
    if a.record_error:
        _record_error(sys.argv, RuntimeError(f"preflight exited {a.error_code}"))
        return de.PREFLIGHT_ERROR_EXIT_CODE

    # Mirrors dispatch.main() delegate resolution; drift only skews the estimate.
    mode = D.classify_mode(a.prompt) if a.mode == "auto" else a.mode
    if a.max_tokens is not None and mode not in ("hybrid", "ralph"):
        # Output budget alone can exceed the context: refuse before the slow
        # classification / assembly / prefetch steps (same contract as below).
        early = de.output_budget_preflight(a.max_tokens, a.llama_url, mode)
        if early is not None:
            return _refuse(a, early, mode, a.role)
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

    if mode in ("hybrid", "ralph"):
        # These services assemble their own prompt; a direct-chat measurement would be a
        # false "accept". Record the labeled limitation and let the launch proceed.
        pf = de.not_measured(mode)
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        de.evidence_path(out).write_text(json.dumps({"task_id": a.task_id, "preflight": pf}))
        print(json.dumps({"refused": False, "preflight": pf}))
        return 0

    # Same prompt augmentation dispatch._run_task applies before the runner (direct/agent).
    if mode in ("direct", "agent"):
        prompt = D._apply_context_assembler(prompt, a.task_id, Path(a.output))
    if mode == "direct":
        ea = D._embedded_assist_prefetch(prompt, os.environ.get("SWITCHBOARD_URL", "http://127.0.0.1:8085"))
        if ea:
            prompt = ea + prompt
    if mode == "agent":
        payload, out_tokens = _agent_payload(a, cfg, prompt)
    else:
        messages = D._prepend_grounding([], cfg)
        messages.append({"role": "user", "content": prompt})
        payload = D.build_llama_payload(messages, max_tokens=cfg.max_tokens, stream=True,
                                        role=cfg.role, task_type=cfg.task_type)
        out_tokens = cfg.max_tokens
    pf = de.preflight(payload, out_tokens, a.llama_url, mode)
    if pf["verdict"] != "refuse":
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        de.evidence_path(out).write_text(json.dumps({"task_id": a.task_id, "preflight": pf}))
        # Launch consumes exactly the prompt that was measured: assemble once.
        de.assembled_path(out).write_text(json.dumps({"task_id": a.task_id, "mode": mode, "prompt": prompt}))
        print(json.dumps({"refused": False, "preflight": pf}))
        return 0

    return _refuse(a, pf, mode, cfg.role)


def _refuse(a, pf, mode, role) -> int:
    refusal = de.refusal_json(a.task_id, pf)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(refusal + "\n")
    D.TaskRegistry(Path(a.delegation_dir)).append(
        task_id=a.task_id, description=a.prompt, output_file=str(out), mode=mode,
        role=role, pid=None,
        extra={"status": "failed", "terminal_reason": pf.get("terminal_reason") or "preflight_refused",
               "outcome": "refused", "preflight": pf, "model_effective": "n/a"})
    print(refusal, file=sys.stderr)
    return de.PREFLIGHT_EXIT_CODE


def main() -> int:
    """Any failure to measure is a refusal: fail closed, never launch unmeasured."""
    try:
        return _run()
    except SystemExit as exc:  # argparse errors
        return exc.code if isinstance(exc.code, int) and exc.code else de.PREFLIGHT_ERROR_EXIT_CODE
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"refused": True, "reason": "preflight_error", "error": repr(exc)[:500],
                          "exit_code": de.PREFLIGHT_ERROR_EXIT_CODE}), file=sys.stderr)
        _record_error(sys.argv, exc)
        return de.PREFLIGHT_ERROR_EXIT_CODE


def _record_error(argv, exc) -> None:
    try:
        p = argparse.ArgumentParser()
        p.add_argument("--task-id")
        p.add_argument("--output")
        p.add_argument("--delegation-dir")
        p.add_argument("--prompt", default="")
        p.add_argument("--mode", default="auto")
        a, _ = p.parse_known_args(argv[1:])
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"refused": True, "task_id": a.task_id,
                                   "reason": "preflight_error", "error": repr(exc)[:500]}) + "\n")
        D.TaskRegistry(Path(a.delegation_dir)).append(
            task_id=a.task_id, description=a.prompt, output_file=str(out), mode=a.mode,
            role="unknown", pid=None,
            extra={"status": "failed", "terminal_reason": "preflight_error",
                   "outcome": "refused", "model_effective": "n/a",
                   "preflight": {"method": "n/a", "measured": None, "limit": None,
                                 "verdict": "error", "error": repr(exc)[:200]}})
    except Exception:  # best effort; the caller still blocks on the nonzero exit
        pass


if __name__ == "__main__":
    sys.exit(main())
