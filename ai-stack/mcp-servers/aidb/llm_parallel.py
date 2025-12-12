from __future__ import annotations

import asyncio
from typing import Any, Dict

import httpx


async def _generate(
    client: httpx.AsyncClient,
    *,
    model: str,
    prompt: str,
    max_tokens: int,
) -> Dict[str, Any]:
    response = await client.post(
        "/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False,
        },
    )
    response.raise_for_status()
    payload = response.json()
    message = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return {
        "model": model,
        "response": message,
        "raw": payload,
    }


async def run_parallel_inference(
    client: httpx.AsyncClient,
    *,
    prompt: str,
    simple_model: str,
    complex_model: str,
    max_tokens: int = 256,
) -> Dict[str, Any]:
    """Execute two model generations concurrently and return both results."""

    simple_task = asyncio.create_task(
        _generate(client, model=simple_model, prompt=prompt, max_tokens=max_tokens)
    )
    complex_task = asyncio.create_task(
        _generate(client, model=complex_model, prompt=prompt, max_tokens=max_tokens)
    )
    simple_result, complex_result = await asyncio.gather(simple_task, complex_task)
    return {"simple": simple_result, "complex": complex_result}
