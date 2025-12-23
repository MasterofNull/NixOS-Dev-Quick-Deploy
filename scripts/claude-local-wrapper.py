#!/usr/bin/env python3
"""
Claude Code Local AI Wrapper
Forces all AI queries through local hybrid coordinator
"""

import json
import os
import sys
import requests
from typing import Dict, Any

HYBRID_COORDINATOR = os.getenv("HYBRID_COORDINATOR_URL", "http://localhost:8092")
AIDB_MCP = os.getenv("AIDB_MCP_URL", "http://localhost:8091")

class LocalAIWrapper:
    """
    Wrapper that intercepts Claude API calls and routes through local stack
    """

    def __init__(self):
        self.hybrid_url = HYBRID_COORDINATOR
        self.aidb_url = AIDB_MCP
        self.session = requests.Session()
        self.telemetry_path = os.path.expanduser("~/.local/share/nixos-ai-stack/telemetry")
        os.makedirs(self.telemetry_path, exist_ok=True)

    def query(self, prompt: str, context: str = "", force_local: bool = None) -> Dict[str, Any]:
        """
        Route query through hybrid coordinator

        Args:
            prompt: The query/prompt
            context: Additional context
            force_local: True=local LLM, False=remote API, None=auto-route
        """

        # Get RAG context if available
        rag_context = self._get_rag_context(prompt)

        # Combine contexts
        full_context = f"{context}\n\n{rag_context}" if context else rag_context

        # Route through hybrid coordinator
        payload = {
            "query": prompt,
            "context": full_context,
            "force_local": force_local,
            "metadata": {
                "source": "claude_wrapper",
                "wrapper_version": "1.0.0"
            }
        }

        try:
            response = self.session.post(
                f"{self.hybrid_url}/query",
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                self._log_usage(prompt, result)
                return result
            else:
                # Fallback to direct local LLM
                return self._fallback_local(prompt, full_context)

        except Exception as e:
            print(f"Hybrid coordinator error: {e}", file=sys.stderr)
            return self._fallback_local(prompt, full_context)

    def _get_rag_context(self, query: str) -> str:
        """Retrieve relevant context from knowledge base"""
        try:
            response = self.session.get(
                f"{self.aidb_url}/documents",
                params={"search": query, "limit": 5},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                docs = data.get("documents", [])
                if docs:
                    context_parts = [doc.get("content", "") for doc in docs]
                    return "\n\n".join(context_parts[:3])  # Top 3 docs

            return ""

        except Exception:
            return ""

    def _fallback_local(self, prompt: str, context: str) -> Dict[str, Any]:
        """Fallback to direct llama.cpp query"""
        try:
            llama_url = "http://localhost:8080/v1/chat/completions"

            messages = []
            if context:
                messages.append({"role": "system", "content": context})
            messages.append({"role": "user", "content": prompt})

            response = self.session.post(
                llama_url,
                json={
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "response": result["choices"][0]["message"]["content"],
                    "source": "local_llm_fallback",
                    "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                }

        except Exception as e:
            return {
                "error": f"All routing failed: {e}",
                "response": "ERROR: Local AI stack unavailable"
            }

    def _log_usage(self, query: str, response: Dict):
        """Log usage for metrics"""
        log_entry = {
            "timestamp": os.popen("date -Iseconds").read().strip(),
            "query_preview": query[:100],
            "decision": response.get("source", "unknown"),
            "tokens_used": response.get("tokens_used", 0),
            "tokens_saved": response.get("tokens_saved", 0)
        }

        log_file = os.path.join(self.telemetry_path, "wrapper-usage.jsonl")
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")


def main():
    """CLI interface for wrapper"""
    if len(sys.argv) < 2:
        print("Usage: claude-local-wrapper.py <query>")
        print("   Or: claude-local-wrapper.py --force-local <query>")
        sys.exit(1)

    force_local = None
    query_start = 1

    if sys.argv[1] == "--force-local":
        force_local = True
        query_start = 2
    elif sys.argv[1] == "--force-remote":
        force_local = False
        query_start = 2

    query = " ".join(sys.argv[query_start:])

    wrapper = LocalAIWrapper()
    result = wrapper.query(query, force_local=force_local)

    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(result.get("response", "No response"))

    # Print metadata to stderr
    print(f"\n[Source: {result.get('source', 'unknown')}]", file=sys.stderr)
    print(f"[Tokens: {result.get('tokens_used', 0)}]", file=sys.stderr)
    if result.get("tokens_saved"):
        print(f"[Saved: {result['tokens_saved']} tokens]", file=sys.stderr)


if __name__ == "__main__":
    main()
