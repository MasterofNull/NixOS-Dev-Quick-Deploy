"""
Constraint-Engineered Development (CED) Parallel Inference Framework

Implements multi-model concurrent execution for improved code quality through
diverse LLM perspectives. Based on the CED methodology from rootcx.com.

Architecture:
- 3 specialized models running in parallel
- Task routing based on model strengths
- Consensus-based result synthesis
- Async/await for efficient concurrency
"""

import asyncio
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import httpx
import logging

logger = logging.getLogger(__name__)


class ModelRole(Enum):
    """Model specializations for task routing"""
    GENERAL_REASONING = "general_reasoning"
    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"


@dataclass
class ModelEndpoint:
    """Configuration for a model endpoint"""
    name: str
    role: ModelRole
    base_url: str
    use_case: str


class ParallelInferenceEngine:
    """
    Manages concurrent execution across multiple specialized LLM models.

    Uses Constraint-Engineered Development approach to leverage:
    1. Qwen3-4B-Instruct: General-purpose reasoning and task coordination
    2. Qwen2.5-Coder: Specialized code generation and refactoring
    3. Deepseek-Coder: Deep code understanding and bug detection
    """

    def __init__(self):
        """Initialize the parallel inference engine with model endpoints"""
        self.enabled = os.getenv("CONSTRAINT_ENGINEERED_DEVELOPMENT", "false").lower() == "true"

        # Configure model endpoints from environment
        self.models = {
            ModelRole.GENERAL_REASONING: ModelEndpoint(
                name="Qwen3-4B-Instruct",
                role=ModelRole.GENERAL_REASONING,
                base_url=os.getenv("LEMONADE_BASE_URL", "http://lemonade:8000/api/v1"),
                use_case="General-purpose task coordination and high-level reasoning"
            ),
            ModelRole.CODE_GENERATION: ModelEndpoint(
                name="Qwen2.5-Coder",
                role=ModelRole.CODE_GENERATION,
                base_url=os.getenv("LEMONADE_CODER_URL", "http://lemonade-coder:8001/api/v1"),
                use_case="Specialized code generation and refactoring"
            ),
            ModelRole.CODE_ANALYSIS: ModelEndpoint(
                name="Deepseek-Coder",
                role=ModelRole.CODE_ANALYSIS,
                base_url=os.getenv("LEMONADE_DEEPSEEK_URL", "http://lemonade-deepseek:8002/api/v1"),
                use_case="Deep code understanding and bug detection"
            )
        }

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(timeout=60.0, limits=httpx.Limits(max_connections=10))

        logger.info(f"Parallel inference engine initialized (enabled={self.enabled})")
        if self.enabled:
            for role, endpoint in self.models.items():
                logger.info(f"  {role.value}: {endpoint.name} @ {endpoint.base_url}")

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def _call_model(
        self,
        endpoint: ModelEndpoint,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> Tuple[ModelRole, Optional[str], Optional[str]]:
        """
        Call a single model endpoint asynchronously.

        Returns:
            Tuple of (role, response_content, error_message)
        """
        try:
            # Convert base_url to chat completion endpoint
            # Format: http://host:port/api/v1 -> http://host:port/v1/chat/completions
            url = endpoint.base_url.replace("/api/v1", "/v1/chat/completions")

            payload = {
                "model": endpoint.name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            logger.debug(f"Calling {endpoint.name} at {url}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            logger.debug(f"{endpoint.name} responded with {len(content)} chars")
            return (endpoint.role, content, None)

        except Exception as e:
            error_msg = f"{endpoint.name} error: {str(e)}"
            logger.error(error_msg)
            return (endpoint.role, None, error_msg)

    async def parallel_execute(
        self,
        task_description: str,
        context: Optional[str] = None,
        target_roles: Optional[List[ModelRole]] = None,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Execute a task across multiple models in parallel.

        Args:
            task_description: The task prompt for the models
            context: Optional context to include in the prompt
            target_roles: Which models to use (default: all)
            max_tokens: Maximum tokens per response
            temperature: Sampling temperature

        Returns:
            Dictionary containing:
            - responses: Dict mapping role -> response content
            - errors: Dict mapping role -> error messages
            - consensus: Optional synthesized consensus response
            - metadata: Execution metadata (timing, etc.)
        """
        if not self.enabled:
            # Fallback to single model if CED not enabled
            general_model = self.models[ModelRole.GENERAL_REASONING]
            messages = [{"role": "user", "content": task_description}]
            if context:
                messages.insert(0, {"role": "system", "content": context})

            role, content, error = await self._call_model(general_model, messages, max_tokens, temperature)
            return {
                "responses": {ModelRole.GENERAL_REASONING.value: content} if content else {},
                "errors": {ModelRole.GENERAL_REASONING.value: error} if error else {},
                "consensus": content,
                "metadata": {"ced_enabled": False, "model_count": 1}
            }

        # Determine which models to use
        target_models = target_roles or list(self.models.keys())

        # Build message structure
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": task_description})

        # Execute in parallel
        start_time = asyncio.get_event_loop().time()
        tasks = [
            self._call_model(self.models[role], messages, max_tokens, temperature)
            for role in target_models
        ]
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        # Process results
        responses = {}
        errors = {}
        for role, content, error in results:
            if content:
                responses[role.value] = content
            if error:
                errors[role.value] = error

        # Synthesize consensus (simple majority for now)
        consensus = self._synthesize_consensus(responses)

        return {
            "responses": responses,
            "errors": errors,
            "consensus": consensus,
            "metadata": {
                "ced_enabled": True,
                "model_count": len(target_models),
                "execution_time": end_time - start_time,
                "success_count": len(responses),
                "error_count": len(errors)
            }
        }

    def _synthesize_consensus(self, responses: Dict[str, str]) -> Optional[str]:
        """
        Synthesize a consensus response from multiple model outputs.

        Current implementation: Return the longest response (most comprehensive)
        Future: Implement proper consensus algorithm with voting/merging
        """
        if not responses:
            return None

        # Simple heuristic: longest response is usually most comprehensive
        return max(responses.values(), key=len)

    async def route_task(
        self,
        task: str,
        task_type: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route a task to the most appropriate model(s) based on task type.

        Task types:
        - "code_generation": Route to CODE_GENERATION model
        - "code_analysis": Route to CODE_ANALYSIS model
        - "code_review": Route to both CODE_GENERATION and CODE_ANALYSIS
        - "general": Route to GENERAL_REASONING model
        - "comprehensive": Route to all models
        """
        routing_map = {
            "code_generation": [ModelRole.CODE_GENERATION],
            "code_analysis": [ModelRole.CODE_ANALYSIS],
            "code_review": [ModelRole.CODE_GENERATION, ModelRole.CODE_ANALYSIS],
            "general": [ModelRole.GENERAL_REASONING],
            "comprehensive": list(self.models.keys())
        }

        target_roles = routing_map.get(task_type, [ModelRole.GENERAL_REASONING])

        logger.info(f"Routing task (type={task_type}) to {len(target_roles)} models")
        return await self.parallel_execute(
            task_description=task,
            context=context,
            target_roles=target_roles
        )


# Global singleton instance
_engine: Optional[ParallelInferenceEngine] = None


def get_engine() -> ParallelInferenceEngine:
    """Get the global parallel inference engine instance"""
    global _engine
    if _engine is None:
        _engine = ParallelInferenceEngine()
    return _engine


async def shutdown_engine():
    """Shutdown the global engine and close connections"""
    global _engine
    if _engine is not None:
        await _engine.close()
        _engine = None
