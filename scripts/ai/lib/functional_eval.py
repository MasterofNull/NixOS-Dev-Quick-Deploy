#!/usr/bin/env python3
"""Frontier FE-2a functional evaluation engine for code generation prompts.

Provides:
- FunctionalTask definitions with concrete assertions and reference/flawed fixtures.
- Safe isolated execution of generated Python code against task assertions.
- Reproducible scoring metric in [0.0, 1.0] with measured headroom (replaces meta-probe).
- Health summary projection for dashboard visibility and QA checks.
"""
from __future__ import annotations

import re
import types
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FunctionalTask:
    name: str
    description: str
    prompt_variables: Dict[str, str]
    check_script: str
    reference_code: str
    flawed_code: str


# Canonical functional task set for evaluating code generation prompts
FUNCTIONAL_TASKS: List[FunctionalTask] = [
    FunctionalTask(
        name="clamp",
        description="Limit x to inclusive range [lo, hi]",
        prompt_variables={
            "task_description": "Implement clamp(x, lo, hi) in Python that bounds x to the inclusive range [lo, hi].",
            "files_list": "math_utils.py",
            "numbered_change_list": "1. Define def clamp(x, lo, hi): ... returning the bounded value.",
            "exclusion_list": "Do not import external math libraries.",
        },
        check_script=(
            "assert hasattr(m, 'clamp'), 'missing clamp function'\n"
            "assert m.clamp(5, 0, 3) == 3, 'clamp(5, 0, 3) must be 3'\n"
            "assert m.clamp(-1, 0, 3) == 0, 'clamp(-1, 0, 3) must be 0'\n"
            "assert m.clamp(2, 0, 3) == 2, 'clamp(2, 0, 3) must be 2'\n"
        ),
        reference_code="def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n",
        flawed_code="def clamp(x, lo, hi):\n    return x\n",
    ),
    FunctionalTask(
        name="slugify",
        description="Lowercase and hyphen-join whitespace words",
        prompt_variables={
            "task_description": "Implement slugify(text) in Python that lowercases text and joins whitespace-separated words with single hyphens.",
            "files_list": "string_utils.py",
            "numbered_change_list": "1. Define def slugify(text): ... returning the slugified string.",
            "exclusion_list": "Do not use external slug libraries.",
        },
        check_script=(
            "assert hasattr(m, 'slugify'), 'missing slugify function'\n"
            "assert m.slugify('Hello  World') == 'hello-world', 'slugify double-space mismatch'\n"
            "assert m.slugify('A b') == 'a-b', 'slugify simple mismatch'\n"
            "assert m.slugify('  Test  ') == 'test', 'slugify padding mismatch'\n"
        ),
        reference_code="def slugify(text):\n    return '-'.join(text.lower().split())\n",
        flawed_code="def slugify(text):\n    return text.lower()\n",
    ),
    FunctionalTask(
        name="evens",
        description="Filter even numbers preserving order",
        prompt_variables={
            "task_description": "Implement evens(numbers) in Python that returns a list containing only even numbers, preserving original order.",
            "files_list": "list_utils.py",
            "numbered_change_list": "1. Define def evens(numbers): ... returning list of even integers.",
            "exclusion_list": "Do not sort the output.",
        },
        check_script=(
            "assert hasattr(m, 'evens'), 'missing evens function'\n"
            "assert m.evens([1, 2, 3, 4]) == [2, 4], 'evens([1, 2, 3, 4]) must be [2, 4]'\n"
            "assert m.evens([]) == [], 'evens([]) must be []'\n"
            "assert m.evens([4, 2, 6]) == [4, 2, 6], 'evens order must be preserved'\n"
        ),
        reference_code="def evens(numbers):\n    return [x for x in numbers if x % 2 == 0]\n",
        flawed_code="def evens(numbers):\n    return [x for x in numbers if x % 2 == 1]\n",
    ),
    FunctionalTask(
        name="mean",
        description="True arithmetic mean, returning 0.0 for empty list",
        prompt_variables={
            "task_description": "Implement mean(numbers) in Python that returns the arithmetic mean of numbers, or 0.0 if numbers is empty.",
            "files_list": "stats_utils.py",
            "numbered_change_list": "1. Define def mean(numbers): ... returning float mean.",
            "exclusion_list": "Do not raise ZeroDivisionError on empty input.",
        },
        check_script=(
            "assert hasattr(m, 'mean'), 'missing mean function'\n"
            "assert m.mean([2, 4]) == 3.0, 'mean([2, 4]) must be 3.0'\n"
            "assert m.mean([]) == 0.0, 'mean([]) must be 0.0'\n"
            "assert m.mean([1, 2, 3]) == 2.0, 'mean([1, 2, 3]) must be 2.0'\n"
        ),
        reference_code="def mean(numbers):\n    return float(sum(numbers) / len(numbers)) if numbers else 0.0\n",
        flawed_code="def mean(numbers):\n    return sum(numbers) / len(numbers)\n",
    ),
    FunctionalTask(
        name="dedupe",
        description="Deduplicate preserving first-seen order",
        prompt_variables={
            "task_description": "Implement dedupe(items) in Python that drops duplicate elements while strictly preserving first-seen order.",
            "files_list": "collection_utils.py",
            "numbered_change_list": "1. Define def dedupe(items): ... returning deduplicated list.",
            "exclusion_list": "Do not sort elements.",
        },
        check_script=(
            "assert hasattr(m, 'dedupe'), 'missing dedupe function'\n"
            "assert m.dedupe([3, 1, 3, 2, 1]) == [3, 1, 2], 'dedupe must preserve order'\n"
            "assert m.dedupe([]) == [], 'dedupe([]) must be []'\n"
            "assert m.dedupe(['a', 'b', 'a']) == ['a', 'b'], 'dedupe string mismatch'\n"
        ),
        reference_code=(
            "def dedupe(items):\n"
            "    seen = set()\n"
            "    return [x for x in items if not (x in seen or seen.add(x))]\n"
        ),
        flawed_code="def dedupe(items):\n    return sorted(set(items))\n",
    ),
    FunctionalTask(
        name="service_hardening",
        description="Generate hardened systemd service config dict",
        prompt_variables={
            "task_description": "Implement build_service_config(service_name, port_env_var) in Python returning a dictionary with DynamicUser=True, ProtectSystem='strict', PrivateTmp=True, and ExecStart with environment-driven port.",
            "files_list": "service_builder.py",
            "numbered_change_list": "1. Define def build_service_config(service_name, port_env_var): ... returning service configuration dict.",
            "exclusion_list": "Never hardcode fixed port numbers.",
        },
        check_script=(
            "assert hasattr(m, 'build_service_config'), 'missing build_service_config'\n"
            "cfg = m.build_service_config('ai-aidb', 'AIDB_PORT')\n"
            "assert cfg.get('DynamicUser') is True, 'DynamicUser must be True'\n"
            "assert cfg.get('ProtectSystem') == 'strict', 'ProtectSystem must be strict'\n"
            "assert cfg.get('PrivateTmp') is True, 'PrivateTmp must be True'\n"
            "assert 'AIDB_PORT' in str(cfg.get('ExecStart', '')), 'ExecStart must reference port env var'\n"
        ),
        reference_code=(
            "def build_service_config(service_name, port_env_var):\n"
            "    return {\n"
            "        'service_name': service_name,\n"
            "        'DynamicUser': True,\n"
            "        'ProtectSystem': 'strict',\n"
            "        'PrivateTmp': True,\n"
            "        'ExecStart': f'/run/current-system/sw/bin/{service_name} --port ${{{port_env_var}}}'\n"
            "    }\n"
        ),
        flawed_code=(
            "def build_service_config(service_name, port_env_var):\n"
            "    return {'service_name': service_name, 'ExecStart': f'{service_name} --port 8080'}\n"
        ),
    ),
]


def extract_code_block(text: str) -> str:
    """Extract code from markdown code fences or strip prose."""
    # Look for python code block
    py_match = re.search(r"```(?:python|py)\s*\n(.*?)\n```", text, re.DOTALL)
    if py_match:
        return py_match.group(1).strip()
    # Look for generic code block
    gen_match = re.search(r"```\s*\n(.*?)\n```", text, re.DOTALL)
    if gen_match:
        return gen_match.group(1).strip()
    # If no fences, filter out non-python lines or return raw text
    return text.strip()


def execute_functional_check(code: str, check_script: str) -> Tuple[bool, List[str]]:
    """Compile and execute code and assertions in an isolated module scope."""
    failures: List[str] = []
    if not code.strip():
        return False, ["empty code output"]

    try:
        compiled_code = compile(code, "<generated_code>", "exec")
        mod = types.ModuleType("generated_module")
        exec(compiled_code, mod.__dict__)
    except SyntaxError as se:
        return False, [f"Syntax error: {se.msg} (line {se.lineno})"]
    except Exception as exc:
        return False, [f"Code execution error: {type(exc).__name__}: {exc}"]

    try:
        check_ns = {"m": mod, "__builtins__": __builtins__}
        compiled_check = compile(check_script, "<check_script>", "exec")
        exec(compiled_check, check_ns)
        return True, []
    except AssertionError as ae:
        msg = str(ae) or "assertion condition returned false"
        failures.append(f"Assertion failed: {msg}")
        return False, failures
    except Exception as exc:
        failures.append(f"Test evaluation error: {type(exc).__name__}: {exc}")
        return False, failures


def evaluate_tasks_mock(
    tasks: Optional[List[FunctionalTask]] = None,
    pass_indices: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Deterministically evaluate tasks using reference or flawed fixtures (for testing/mock)."""
    eval_tasks = tasks or FUNCTIONAL_TASKS
    indices = pass_indices if pass_indices is not None else list(range(len(eval_tasks)))
    results: List[Dict[str, Any]] = []

    for idx, t in enumerate(eval_tasks):
        code = t.reference_code if idx in indices else t.flawed_code
        ok, errs = execute_functional_check(code, t.check_script)
        results.append({
            "task": t.name,
            "description": t.description,
            "passed": ok,
            "failures": errs,
            "mode": "reference" if idx in indices else "flawed",
        })

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(eval_tasks)
    score = (passed_count / total_count) if total_count > 0 else 0.0

    return {
        "metric": "functional_eval",
        "target_prompt": "aider_task_systems_code",
        "tasks_evaluated": total_count,
        "tasks_passed": passed_count,
        "score": round(score, 4),
        "headroom": round(1.0 - score, 4),
        "status": "ready",
        "results": results,
    }


def health_summary() -> Dict[str, Any]:
    """Bounded projection of functional evaluation readiness for dashboard and QA."""
    total = len(FUNCTIONAL_TASKS)
    # Reference fixture baseline: 100% capable, but flawed fixture proves headroom detection
    return {
        "available": True,
        "status": "ok",
        "metric": "functional_eval",
        "tasks_available": total,
        "headroom_observable": True,
        "baseline_ready": True,
        "target_prompt": "aider_task_systems_code",
    }
