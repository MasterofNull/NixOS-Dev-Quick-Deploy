#!/usr/bin/env python3
"""
Shared Local Model Client for aq-* tools.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

_SHARED = Path(__file__).resolve().parents[3] / "ai-stack" / "mcp-servers" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
from llm_config import build_llama_payload, AGENT_TASK_MAX_TOKENS


class LocalModelClient:
    def __init__(
        self,
        llama_url: str = os.getenv("LLAMA_URL", "http://127.0.0.1:8080"),
        timeout: float = float(os.getenv("AI_LOCAL_FRONTDOOR_MAX_TIME", "600")),
    ):
        self.llama_url = llama_url.rstrip("/")
        self.timeout = timeout

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = AGENT_TASK_MAX_TOKENS,
        stream: bool = False,
    ) -> Any:
        """Execute chat completion against the local model."""
        url = f"{self.llama_url}/v1/chat/completions"
        model_id = os.getenv("AI_LOCAL_MODEL_ID", "local-model")
        payload = build_llama_payload(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
            model=model_id,
        )
        
        if stream:
            return self._stream_request(url, payload)
        
        return self._post(url, payload)

    def _post(self, url: str, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"error": str(e)}

    def _stream_request(self, url: str, payload: dict):
        """Generator for streaming responses."""
        # Simple implementation using urllib for stream
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                for line in r:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        content = line[6:]
                        if content == "[DONE]":
                            break
                        yield json.loads(content)
        except Exception as e:
            yield {"error": str(e)}
