"""
Curated workflow layer on top of the bounded web research fetch primitive.

This keeps the capability generic:
- manifest-driven workflow/source packs
- explicit workflow selection
- bounded expansion into approved explicit URLs only
- deterministic organization of fetched evidence
- safe classification of bot-gated or otherwise unusable pages
"""

from __future__ import annotations

import json
import os
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx

from browser_research import fetch_browser_research
from web_research import fetch_web_research, load_web_research_policy


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "config" / "curated-web-research-sources.json"
BOT_GATE_MARKERS = (
    "just a moment",
    "attention required",
    "enable javascript and cookies",
    "verify you are human",
    "cf-mitigated",
)


@dataclass(frozen=True)
class CuratedResearchWorkflow:
    slug: str
    description: str
    max_urls: int
    default_max_text_chars: int
    inputs: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]


def _manifest_path() -> Path:
    raw = os.getenv("AI_CURATED_RESEARCH_WORKFLOWS_FILE", "").strip()
    return Path(raw) if raw else DEFAULT_MANIFEST_PATH


def _safe_json_load(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("curated research manifest must be a JSON object")
    return data


def load_curated_research_manifest() -> Dict[str, Any]:
    path = _manifest_path()
    if not path.is_file():
        raise FileNotFoundError(f"curated research manifest missing: {path}")
    data = _safe_json_load(path)
    workflows = data.get("workflows")
    if not isinstance(workflows, list):
        raise ValueError("curated research manifest missing workflows list")
    return data


def list_curated_research_workflows() -> List[Dict[str, Any]]:
    manifest = load_curated_research_manifest()
    workflows: List[Dict[str, Any]] = []
    for item in manifest.get("workflows", []):
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        workflows.append(
            {
                "slug": slug,
                "description": str(item.get("description") or "").strip(),
                "source_count": len(item.get("sources") or []),
                "inputs": item.get("inputs") if isinstance(item.get("inputs"), list) else [],
            }
        )
    workflows.sort(key=lambda item: item["slug"])
    return workflows


def get_curated_research_workflow(slug: str) -> CuratedResearchWorkflow:
    target = str(slug or "").strip().lower()
    if not target:
        raise ValueError("workflow slug required")
    manifest = load_curated_research_manifest()
    for item in manifest.get("workflows", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("slug") or "").strip().lower() != target:
            continue
        return CuratedResearchWorkflow(
            slug=target,
            description=str(item.get("description") or "").strip(),
            max_urls=max(int(item.get("max_urls") or 1), 1),
            default_max_text_chars=max(int(item.get("default_max_text_chars") or 600), 128),
            inputs=item.get("inputs") if isinstance(item.get("inputs"), list) else [],
            sources=item.get("sources") if isinstance(item.get("sources"), list) else [],
        )
    raise KeyError(f"unknown curated research workflow: {slug}")


def _template_fields(template: str) -> List[str]:
    names: List[str] = []
    for _, field_name, _, _ in string.Formatter().parse(template):
        if field_name:
            names.append(field_name)
    return names


def _expand_template(template: str, inputs: Dict[str, Any]) -> str:
    fields = _template_fields(template)
    missing = [name for name in fields if not str(inputs.get(name, "")).strip()]
    if missing:
        raise ValueError(f"missing required workflow inputs: {', '.join(sorted(set(missing)))}")
    safe_inputs = {key: str(value).strip() for key, value in inputs.items()}
    return template.format(**safe_inputs)


def _normalize_input_map(inputs: Optional[Dict[str, Any]]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key, value in (inputs or {}).items():
        name = str(key or "").strip()
        if not name:
            continue
        text = str(value or "").strip()
        if text:
            normalized[name] = text
    return normalized


def _required_inputs(workflow: CuratedResearchWorkflow) -> List[str]:
    required: List[str] = []
    for item in workflow.inputs:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name and bool(item.get("required")):
            required.append(name)
    return required


def _compile_sources(workflow: CuratedResearchWorkflow, inputs: Dict[str, str]) -> List[Dict[str, Any]]:
    compiled: List[Dict[str, Any]] = []
    for item in workflow.sources:
        if not isinstance(item, dict):
            continue
        source_name = str(item.get("name") or "").strip()
        if not source_name:
            continue
        template = str(item.get("url_template") or item.get("url") or "").strip()
        if not template:
            continue
        url = _expand_template(template, inputs) if "{" in template else template
        selectors = item.get("selectors") if isinstance(item.get("selectors"), list) else []
        compiled.append(
            {
                "name": source_name,
                "url": url,
                "selectors": [str(selector).strip() for selector in selectors if str(selector or "").strip()],
                "purpose": str(item.get("purpose") or "").strip(),
                "fetch_mode": str(item.get("fetch_mode") or "http").strip().lower() or "http",
                "fallback_fetch_mode": str(item.get("fallback_fetch_mode") or "").strip().lower(),
            }
        )
    return compiled


def _classify_result(page: Optional[Dict[str, Any]], skipped_reason: str) -> Dict[str, Any]:
    if page:
        title = str(page.get("title") or "").strip().lower()
        excerpt = str(page.get("text_excerpt") or "").strip().lower()
        combined = f"{title}\n{excerpt}"
        if any(marker in combined for marker in BOT_GATE_MARKERS):
            return {
                "status": "needs_fallback",
                "issue_class": "bot_gate_detected",
                "fallback_hint": "Switch to the allowed browser-assisted fetch lane, an official export/API, or a manually supplied page artifact.",
            }
        if not excerpt:
            return {
                "status": "needs_review",
                "issue_class": "empty_extract",
                "fallback_hint": "Adjust selectors or switch to a more stable approved source.",
            }
        return {"status": "ok", "issue_class": "", "fallback_hint": ""}

    if skipped_reason.startswith("blocked_by_robots"):
        return {
            "status": "needs_fallback",
            "issue_class": "robots_blocked",
            "fallback_hint": "Do not retry automatically; use an allowed alternate source or user-provided artifact.",
        }
    if "ConnectError" in skipped_reason:
        return {
            "status": "needs_fallback",
            "issue_class": "transport_blocked",
            "fallback_hint": "Try an approved alternate source or browser-assisted capture path.",
        }
    return {
        "status": "needs_review",
        "issue_class": skipped_reason or "missing_result",
        "fallback_hint": "Inspect the source and decide whether selector tuning or source substitution is needed.",
    }


async def run_curated_research_workflow(
    *,
    workflow_slug: str,
    inputs: Optional[Dict[str, Any]] = None,
    max_text_chars: Optional[int] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
    browser_runner: Optional[Callable[..., Awaitable[tuple[int, str, str]]]] = None,
) -> Dict[str, Any]:
    workflow = get_curated_research_workflow(workflow_slug)
    normalized_inputs = _normalize_input_map(inputs)
    required = _required_inputs(workflow)
    missing_required = [name for name in required if name not in normalized_inputs]
    if missing_required:
        raise ValueError(f"missing required workflow inputs: {', '.join(sorted(missing_required))}")

    compiled_sources = _compile_sources(workflow, normalized_inputs)
    if not compiled_sources:
        raise ValueError(f"workflow {workflow.slug} has no usable sources")

    policy = load_web_research_policy()
    source_limit = min(workflow.max_urls, policy.max_urls, len(compiled_sources))
    selected_sources = compiled_sources[:source_limit]
    effective_max_text_chars = min(max_text_chars or workflow.default_max_text_chars, policy.max_text_chars)
    aggregate_fetch = {
        "status": "ok",
        "request": {"max_text_chars": effective_max_text_chars},
        "metrics": {
            "submitted_urls": 0,
            "accepted_urls": 0,
            "page_requests": 0,
            "browser_requests": 0,
            "robots_requests": 0,
            "delays_applied": 0,
            "delay_seconds_total": 0.0,
        },
        "results": [],
        "skipped": [],
    }
    organized_results: List[Dict[str, Any]] = []
    for source in selected_sources:
        fetch_mode = source.get("fetch_mode") or "http"
        per_source_result: Dict[str, Any]
        if fetch_mode == "browser":
            per_source_result = await fetch_browser_research(
                urls=[source["url"]],
                selectors=source.get("selectors", []),
                max_text_chars=effective_max_text_chars,
                transport=transport,
                sleep_fn=sleep_fn,
                browser_runner=browser_runner,
            )
        else:
            per_source_result = await fetch_web_research(
                urls=[source["url"]],
                selectors=source.get("selectors", []),
                max_text_chars=effective_max_text_chars,
                transport=transport,
                sleep_fn=sleep_fn,
            )

        for key, value in (per_source_result.get("metrics") or {}).items():
            if isinstance(value, (int, float)):
                aggregate_fetch["metrics"][key] = aggregate_fetch["metrics"].get(key, 0) + value
        aggregate_fetch["metrics"]["submitted_urls"] += 0
        aggregate_fetch["results"].extend(per_source_result.get("results", []) or [])
        aggregate_fetch["skipped"].extend(per_source_result.get("skipped", []) or [])

        page = next(
            (
                item
                for item in (per_source_result.get("results") or [])
                if isinstance(item, dict) and str(item.get("requested_url") or "") == source["url"]
            ),
            None,
        )
        skipped_reason = next(
            (
                str(item.get("reason") or "")
                for item in (per_source_result.get("skipped") or [])
                if isinstance(item, dict) and str(item.get("url") or "") == source["url"]
            ),
            "",
        )
        classification = _classify_result(page, skipped_reason)
        fallback_used = False
        fallback_mode = source.get("fallback_fetch_mode") or ""
        if (
            fallback_mode == "browser"
            and classification["status"] in {"needs_review", "needs_fallback"}
            and classification["issue_class"] in {"empty_extract", "transport_blocked", "missing_result", "bot_gate_detected"}
        ):
            browser_result = await fetch_browser_research(
                urls=[source["url"]],
                selectors=source.get("selectors", []),
                max_text_chars=effective_max_text_chars,
                transport=transport,
                sleep_fn=sleep_fn,
                browser_runner=browser_runner,
            )
            for key, value in (browser_result.get("metrics") or {}).items():
                if isinstance(value, (int, float)):
                    aggregate_fetch["metrics"][key] = aggregate_fetch["metrics"].get(key, 0) + value
            aggregate_fetch["results"].extend(browser_result.get("results", []) or [])
            aggregate_fetch["skipped"].extend(browser_result.get("skipped", []) or [])
            browser_page = next(
                (
                    item
                    for item in (browser_result.get("results") or [])
                    if isinstance(item, dict) and str(item.get("requested_url") or "") == source["url"]
                ),
                None,
            )
            browser_skipped_reason = next(
                (
                    str(item.get("reason") or "")
                    for item in (browser_result.get("skipped") or [])
                    if isinstance(item, dict) and str(item.get("url") or "") == source["url"]
                ),
                "",
            )
            browser_classification = _classify_result(browser_page, browser_skipped_reason)
            if browser_page is not None or browser_skipped_reason:
                page = browser_page
                skipped_reason = browser_skipped_reason
                classification = browser_classification
                fallback_used = True
        organized_results.append(
            {
                "source_name": source["name"],
                "purpose": source["purpose"],
                "requested_url": source["url"],
                "selectors": source["selectors"],
                "fetch_mode": fetch_mode,
                "fallback_fetch_mode": fallback_mode,
                "fallback_used": fallback_used,
                "result": page,
                "status": classification["status"],
                "issue_class": classification["issue_class"],
                "fallback_hint": classification["fallback_hint"],
            }
        )

    return {
        "status": "ok",
        "workflow": {
            "slug": workflow.slug,
            "description": workflow.description,
            "manifest_path": str(_manifest_path()),
            "inputs": normalized_inputs,
            "required_inputs": required,
        },
        "selected_sources": selected_sources,
        "result_count": len(aggregate_fetch.get("results", []) or []),
        "results": organized_results,
        "fetch": aggregate_fetch,
    }
