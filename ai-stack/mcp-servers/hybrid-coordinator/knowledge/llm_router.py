"""
Intelligent LLM Router - Maximize Local/Free, Minimize Paid
Routes tasks across three tiers: Local > Free > Paid
Target: 80% local, 15% free, 5% paid

Includes Advisor Strategy support for proactive guidance on complex decisions.
"""

import aiohttp
import asyncio
import logging
import sqlite3
import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

# Import advisor detector and config
try:
    from advisor_detector import DecisionPointDetector, DecisionPoint
    from config import Config
    _ADVISOR_AVAILABLE = True
except ImportError:
    logger.warning("advisor_detector or config not available, advisor strategy disabled")
    _ADVISOR_AVAILABLE = False
    DecisionPointDetector = None
    DecisionPoint = None
    Config = None

# Import routing contract (canonical tier/profile/cost registry)
try:
    from routing_contract import (
        CostEstimates as _CostEstimates,
        profile_for_tier as _profile_for_tier,
        profile_for_model_alias as _profile_for_model_alias,
        legacy_tier_to_routing_tier as _legacy_tier_to_routing_tier,
        validate_profile as _validate_profile,
    )
    _CONTRACT_AVAILABLE = True
except ImportError:
    logger.warning("routing_contract not available, using legacy cost estimates")
    _CONTRACT_AVAILABLE = False


class AgentTier(Enum):
    """Agent tier for routing priority"""
    LOCAL = "local"      # llama-cpp (80% of tasks, $0 cost)
    FREE = "free"        # qwen, gemini-free (15% of tasks, $0 cost)
    PAID = "paid"        # claude-sonnet (5% of tasks, high cost)
    CRITICAL = "critical" # claude-opus (1% of tasks, highest cost)


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"       # 80% → Local LLM
    MEDIUM = "medium"       # 15% → Free sub-agent
    HIGH = "high"           # 4% → Paid model
    CRITICAL = "critical"   # 1% → Opus


class LLMRouter:
    """
    Intelligent routing across local, free, and paid LLMs

    Routing Strategy:
    1. Try local llama-cpp first (80% of tasks, $0)
    2. Escalate to free sub-agents if needed (15%, $0)
    3. Use paid models only when necessary (5%, $$)

    Cost Optimization:
    - Current: ~$20/day (all → Claude)
    - Target: ~$1/day (95% local/free)
    - Savings: ~$570/month
    """

    def __init__(self, metrics_db: str = None):
        # Service endpoints
        self.local_llm_endpoint = os.getenv("LLAMA_CPP_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        self.local_embed_endpoint = os.getenv("EMBEDDING_SERVICE_URL", "http://127.0.0.1:8081").rstrip("/")
        self.hybrid_coordinator_endpoint = os.getenv("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003").rstrip("/")

        # Routing metrics
        self.metrics_db = metrics_db or "routing_metrics.db"
        self._init_metrics_db()

        # Advisor strategy support
        self.advisor_enabled = _ADVISOR_AVAILABLE and getattr(Config, "AI_ADVISOR_ENABLED", True) if Config else False
        self.advisor_detector = DecisionPointDetector(
            decision_threshold=getattr(Config, "AI_ADVISOR_DECISION_THRESHOLD", 0.7) if Config else 0.7
        ) if _ADVISOR_AVAILABLE and self.advisor_enabled else None
        self.advisor_uses = {}  # Track advisor uses per task

        # Task classification patterns
        self.local_llm_tasks = {
            "code_review", "log_analysis", "config_validation",
            "test_generation", "documentation", "syntax_check",
            "dependency_analysis", "error_classification",
            "health_summary", "deployment_summary", "parse",
            "extract", "summarize", "format", "validate",
            "check", "list", "count", "find", "search"
        }

        self.sub_agent_tasks = {
            "implementation", "refactoring", "test_scaffolding",
            "boilerplate_generation", "code_completion",
            "syntax_fixes", "simple_debugging", "generate",
            "create", "update", "modify", "fix"
        }

        self.paid_model_tasks = {
            "architecture_decisions", "security_audit_review",
            "complex_reasoning", "ambiguity_resolution",
            "root_cause_analysis", "design", "architect",
            "strategic_planning"
        }

    def _init_metrics_db(self):
        """Initialize routing metrics database"""
        conn = sqlite3.connect(self.metrics_db)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS routing_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                task_type TEXT,
                complexity TEXT,
                tier TEXT,
                model TEXT,
                success BOOLEAN,
                escalated BOOLEAN DEFAULT 0,
                escalated_from TEXT,
                response_time_ms INTEGER,
                cost_estimate REAL
            );

            CREATE TABLE IF NOT EXISTS escalations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                from_tier TEXT,
                to_tier TEXT,
                reason TEXT,
                task_type TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_routing_tier ON routing_decisions(tier);
            CREATE INDEX IF NOT EXISTS idx_routing_timestamp ON routing_decisions(timestamp);

            CREATE TABLE IF NOT EXISTS advisor_consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                task_id TEXT,
                decision_type TEXT,
                executor_tier TEXT,
                executor_model TEXT,
                advisor_model TEXT,
                advisor_tokens INTEGER,
                advisor_cost REAL,
                guidance_applied BOOLEAN DEFAULT 1,
                task_success BOOLEAN,
                time_to_consult_ms INTEGER,
                question TEXT,
                guidance_summary TEXT,
                fallback_rank INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_advisor_task_id ON advisor_consultations(task_id);
            CREATE INDEX IF NOT EXISTS idx_advisor_decision_type ON advisor_consultations(decision_type);
            CREATE INDEX IF NOT EXISTS idx_advisor_timestamp ON advisor_consultations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_advisor_fallback_rank ON advisor_consultations(fallback_rank);
        """)
        conn.commit()
        conn.close()

    def classify_complexity(self, task_description: str) -> TaskComplexity:
        """
        Classify task complexity for routing

        Simple (80%) → Local LLM
        Medium (15%) → Free Sub-Agent
        High (4%) → Paid Model
        Critical (1%) → Opus
        """
        task_lower = task_description.lower()

        # Critical patterns (1% → Opus)
        critical_patterns = [
            "critical security", "production incident",
            "architectural decision", "strategic planning",
            "critical bug", "security breach"
        ]
        if any(p in task_lower for p in critical_patterns):
            return TaskComplexity.CRITICAL

        # High patterns (4% → Paid Model)
        if any(task in task_lower for task in self.paid_model_tasks):
            return TaskComplexity.HIGH

        # Medium patterns (15% → Free Sub-Agent)
        if any(task in task_lower for task in self.sub_agent_tasks):
            return TaskComplexity.MEDIUM

        # Simple (80% → Local LLM)
        return TaskComplexity.SIMPLE

    def route_task(self, task_description: str, context: Dict = None) -> Tuple[AgentTier, str]:
        """
        Route task to optimal agent tier

        Returns: (tier, model_name)
        """
        complexity = self.classify_complexity(task_description)
        context = context or {}

        # Routing decision based on complexity
        if complexity == TaskComplexity.SIMPLE:
            # 80% of tasks → Local LLM
            return (AgentTier.LOCAL, "llama-cpp-local")

        elif complexity == TaskComplexity.MEDIUM:
            # 15% of tasks → Free sub-agent
            # Prefer Qwen for code, Gemini for general
            if any(t in task_description.lower() for t in ["code", "implementation", "debug"]):
                return (AgentTier.FREE, "qwen-coder")
            else:
                return (AgentTier.FREE, "gemini-free")

        elif complexity == TaskComplexity.HIGH:
            # 4% of tasks → Paid model
            return (AgentTier.PAID, "claude-sonnet")

        else:  # CRITICAL
            # 1% of tasks → Opus
            return (AgentTier.CRITICAL, "claude-opus")

    async def execute_with_routing(self, task: Dict) -> Dict:
        """
        Execute task with intelligent routing and auto-escalation

        Args:
            task: {
                "description": str,
                "context": dict,
                "type": str (optional),
                "allow_escalation": bool (default: True)
            }

        Returns:
            {
                "result": str,
                "tier": str,
                "model": str,
                "cost": float,
                "escalated": bool,
                "response_time_ms": int
            }
        """
        start_time = datetime.now()

        # Route to optimal tier
        tier, model = self.route_task(task["description"], task.get("context"))

        logger.info(f"Routing task to {tier.value}/{model}")

        try:
            # Execute with chosen tier
            if tier == AgentTier.LOCAL:
                result = await self._execute_local(task, model)
            elif tier == AgentTier.FREE:
                result = await self._execute_free(task, model)
            else:  # PAID or CRITICAL
                result = await self._execute_paid(task, model)

            # Calculate response time
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            # Record successful routing
            self._record_routing(
                task_type=task.get("type", "unknown"),
                complexity=self.classify_complexity(task["description"]).value,
                tier=tier.value,
                model=model,
                success=True,
                response_time_ms=int(response_time),
                cost_estimate=self._estimate_cost(tier)
            )

            return {
                "result": result,
                "tier": tier.value,
                "model": model,
                "cost": self._estimate_cost(tier),
                "escalated": False,
                "response_time_ms": int(response_time)
            }

        except Exception as e:
            logger.error(f"Execution failed with {tier.value}/{model}: {e}")

            # Auto-escalate if allowed
            if task.get("allow_escalation", True):
                return await self._escalate(task, tier, model, error=str(e))
            else:
                raise

    async def _execute_local(self, task: Dict, model: str) -> str:
        """Execute task with local llama-cpp"""
        prompt = self._build_prompt(task, optimize_for="local")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.local_llm_endpoint}/v1/completions",
                json={
                    "prompt": prompt,
                    "max_tokens": 2048,
                    "temperature": 0.7,
                    "stop": ["</output>", "###", "\n\n\n"]
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Local LLM returned {resp.status}")

                data = await resp.json()
                return data["choices"][0]["text"].strip()

    async def _execute_free(self, task: Dict, model: str) -> str:
        """Execute task with free sub-agent"""
        if _CONTRACT_AVAILABLE:
            profile = _profile_for_model_alias(
                model,
                tier_hint=_legacy_tier_to_routing_tier(AgentTier.FREE.value),
            )
        else:
            profile = "remote-coding" if "coder" in model else "remote-free"
        return await self._execute_via_coordinator(task, model, profile=profile, prefer_local=False)

    async def _execute_paid(self, task: Dict, model: str) -> str:
        """Execute task with paid model (last resort)"""
        if _CONTRACT_AVAILABLE:
            tier = AgentTier.CRITICAL if model == "claude-opus" else AgentTier.PAID
            profile = _profile_for_model_alias(
                model,
                tier_hint=_legacy_tier_to_routing_tier(tier.value),
            )
        else:
            profile = "remote-reasoning" if model == "claude-sonnet" else "remote-gemini"
        return await self._execute_via_coordinator(task, model, profile=profile, prefer_local=False)

    async def _execute_via_coordinator(
        self,
        task: Dict[str, Any],
        model: str,
        *,
        profile: str,
        prefer_local: bool,
    ) -> str:
        """Delegate execution through the hybrid coordinator so router tiers reuse harness failover."""
        if _CONTRACT_AVAILABLE:
            _validate_profile(profile)
        prompt = self._build_prompt(task, optimize_for="remote")
        timeout_s = float(task.get("timeout_s") or task.get("timeout") or 45.0)
        payload: Dict[str, Any] = {
            "task": str(task.get("description") or "").strip(),
            "profile": profile,
            "prefer_local": prefer_local,
            "system_prompt": (
                "You are executing a bounded routed task through the AI harness. "
                "Return a direct, complete answer for the task."
            ),
            "context": dict(task.get("context") or {}),
            "max_tokens": int(task.get("max_tokens") or 768),
            "temperature": float(task.get("temperature") or 0.2),
            "timeout_s": timeout_s,
        }
        payload["context"].setdefault("summary", prompt[:1200])
        if task.get("tools"):
            payload["tools"] = task["tools"]
        if task.get("tool_choice") is not None:
            payload["tool_choice"] = task["tool_choice"]
        if task.get("model"):
            payload["model"] = str(task["model"])

        logger.info("Delegating routed task to coordinator profile=%s model=%s", profile, model)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.hybrid_coordinator_endpoint}/control/ai-coordinator/delegate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout_s + 5.0),
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise Exception(
                        f"Coordinator delegate returned {resp.status}: "
                        f"{str(body)[:240]}"
                    )

        response_text = self._extract_response_text(body)
        if not response_text:
            raise Exception("Coordinator delegate returned no response text")
        return response_text

    def _extract_response_text(self, body: Any) -> str:
        """Extract assistant text from common delegated/coordinator payloads."""
        if isinstance(body, str):
            return body.strip()
        if not isinstance(body, dict):
            return ""

        direct_fields = ("result", "response", "output", "content", "text")
        for field in direct_fields:
            value = body.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()

        if isinstance(body.get("data"), dict):
            nested = self._extract_response_text(body["data"])
            if nested:
                return nested

        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()

        result = body.get("result")
        if isinstance(result, dict):
            nested = self._extract_response_text(result)
            if nested:
                return nested

        return ""

    async def _escalate(self, task: Dict, from_tier: AgentTier,
                       from_model: str, error: str) -> Dict:
        """
        Escalate to higher tier on failure
        Local → Free → Paid
        """
        start_time = datetime.now()

        # Determine escalation target
        if from_tier == AgentTier.LOCAL:
            to_tier, to_model = AgentTier.FREE, "qwen-coder"
            logger.info(f"Escalating from local to free due to: {error}")
        elif from_tier == AgentTier.FREE:
            to_tier, to_model = AgentTier.PAID, "claude-sonnet"
            logger.warning(f"Escalating from free to paid due to: {error}")
        else:
            # Already at paid, can't escalate further
            raise Exception(f"Task failed at paid tier: {error}")

        # Record escalation
        self._record_escalation(
            from_tier=from_tier.value,
            to_tier=to_tier.value,
            reason=error,
            task_type=task.get("type", "unknown")
        )

        # Execute with escalated tier
        try:
            if to_tier == AgentTier.FREE:
                result = await self._execute_free(task, to_model)
            else:
                result = await self._execute_paid(task, to_model)

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            # Record successful escalation
            self._record_routing(
                task_type=task.get("type", "unknown"),
                complexity=self.classify_complexity(task["description"]).value,
                tier=to_tier.value,
                model=to_model,
                success=True,
                escalated=True,
                escalated_from=from_tier.value,
                response_time_ms=int(response_time),
                cost_estimate=self._estimate_cost(to_tier)
            )

            return {
                "result": result,
                "tier": to_tier.value,
                "model": to_model,
                "cost": self._estimate_cost(to_tier),
                "escalated": True,
                "escalated_from": from_tier.value,
                "response_time_ms": int(response_time)
            }

        except Exception as e:
            # Escalation failed, try next tier if possible
            if to_tier == AgentTier.FREE:
                return await self._escalate(task, to_tier, to_model, error=str(e))
            else:
                raise

    def _build_prompt(self, task: Dict, optimize_for: str = "local") -> str:
        """Build prompt optimized for target model"""
        # Include advisor guidance when available (was injected into task dict but never consumed)
        advisor_guidance = task.get("advisor_guidance")
        advisor_note = ""
        if advisor_guidance and isinstance(advisor_guidance, dict):
            action = advisor_guidance.get("action", "proceed")
            reasoning = advisor_guidance.get("reasoning", "")[:300]
            if reasoning:
                advisor_note = f"\n[Advisor guidance — {action}]: {reasoning}\n"

        if optimize_for == "local":
            # Concise prompts work best with local models
            return f"""Task: {task['description']}

Context: {task.get('context', {}).get('summary', 'N/A')}{advisor_note}
Provide a direct, focused response. Be concise and specific.

Response:"""

        else:
            # More detailed prompts for larger models
            advisor_section = ""
            if advisor_guidance and isinstance(advisor_guidance, dict):
                action = advisor_guidance.get("action", "proceed")
                guidance_text = advisor_guidance.get("guidance", "")[:500]
                advisor_section = f'\n<advisor_guidance action="{action}">\n{guidance_text}\n</advisor_guidance>'
            return f"""<task>
{task['description']}
</task>

<context>
{json.dumps(task.get('context', {}), indent=2)}
</context>{advisor_section}

<instructions>
Analyze the task and provide a comprehensive response.
Consider edge cases and provide reasoning.
</instructions>

<response>
"""

    async def execute_with_advisor(self, task: Dict) -> Dict:
        """
        Execute task with optional advisor consultation.

        Flow:
        1. Route to executor tier
        2. Detect decision points before execution
        3. Consult advisor if decision point found
        4. Execute with executor (with advisor guidance if provided)
        5. Return result

        Args:
            task: {
                "description": str,
                "context": dict,
                "type": str (optional),
                "allow_escalation": bool (default: True),
                "allow_advisor": bool (default: True),
                "max_advisor_uses": int (default: 3)
            }

        Returns:
            {
                "result": str,
                "tier": str,
                "model": str,
                "cost": float,
                "escalated": bool,
                "advisor_consulted": bool,
                "advisor_count": int,
                "response_time_ms": int
            }
        """
        start_time = datetime.now()

        # Generate task ID if not provided
        task_id = task.get("task_id", str(uuid.uuid4()))
        task["task_id"] = task_id

        # Route to optimal tier
        tier, model = self.route_task(task["description"], task.get("context"))

        # Check if advisor consultation is enabled and allowed
        allow_advisor = task.get("allow_advisor", True) and self.advisor_enabled
        max_advisor_uses = task.get("max_advisor_uses", getattr(Config, "AI_ADVISOR_MAX_USES_PER_TASK", 3) if Config else 3)

        advisor_consulted = False
        advisor_count = 0

        if allow_advisor and self.advisor_detector:
            # Initialize advisor usage tracking
            self.advisor_uses[task_id] = 0

            # Detect decision points
            decision_point = self.advisor_detector.detect(
                task=task["description"],
                context=task.get("context", {}),
                executor_tier=tier.value,
                task_id=task_id
            )

            if decision_point and self.advisor_uses[task_id] < max_advisor_uses:
                # Consult advisor before execution
                logger.info(f"Consulting advisor for {decision_point.decision_type} decision (confidence={decision_point.confidence:.2f})")

                try:
                    advisor_guidance = await self._consult_advisor(decision_point, tier.value, model)
                    task["advisor_guidance"] = advisor_guidance
                    advisor_consulted = True
                    self.advisor_uses[task_id] += 1
                    advisor_count = self.advisor_uses[task_id]
                except Exception as e:
                    logger.warning(f"Advisor consultation failed: {e}, proceeding without advisor")

        # Execute with executor (potentially with advisor guidance)
        try:
            result = await self.execute_with_routing(task)
            result["advisor_consulted"] = advisor_consulted
            result["advisor_count"] = advisor_count
            return result
        finally:
            # Cleanup advisor tracking
            if task_id in self.advisor_uses:
                del self.advisor_uses[task_id]

    async def _consult_advisor(
        self,
        decision_point: DecisionPoint,
        executor_tier: str,
        executor_model: str
    ) -> Dict:
        """
        Consult advisor for guidance on decision point.

        Uses ranked fallback chain - tries each model in order until one succeeds.

        The advisor provides:
        - Plan/approach recommendation
        - Corrections to executor's approach
        - Stop signal if task is unsafe/inappropriate

        Args:
            decision_point: The detected decision point
            executor_tier: Tier of executor model
            executor_model: Name of executor model

        Returns:
            {
                "decision_type": str,
                "guidance": str,
                "action": str,  # "proceed", "modify", "stop"
                "reasoning": str,
                "model": str,
                "tokens": int,
                "cost": float,
                "fallback_rank": int,  # 0 = primary, 1 = first fallback, etc.
            }
        """
        start_time = datetime.now()

        # Build advisor prompt
        advisor_prompt = self._build_advisor_prompt(decision_point)

        # Get ranked fallback chain for this decision type
        advisor_models = self._get_advisor_model_chain(decision_point.decision_type)
        advisor_endpoint = getattr(Config, "AI_ADVISOR_ENDPOINT", "switchboard") if Config else "switchboard"
        max_tokens = getattr(Config, "AI_ADVISOR_TOKEN_BUDGET", 700) if Config else 700

        # Try each model in the ranked chain until one succeeds
        last_error = None
        for fallback_rank, advisor_model in enumerate(advisor_models):
            try:
                logger.info(
                    f"Attempting advisor consultation with {advisor_model} "
                    f"(rank {fallback_rank}, decision_type={decision_point.decision_type})"
                )

                # Execute advisor call
                if advisor_endpoint == "local" or advisor_endpoint == "switchboard":
                    advisor_response = await self._advisor_via_coordinator(
                        advisor_prompt,
                        advisor_model,
                        max_tokens
                    )
                else:
                    advisor_response = await self._advisor_via_coordinator(
                        advisor_prompt,
                        advisor_model,
                        max_tokens
                    )

                response_time = (datetime.now() - start_time).total_seconds() * 1000

                # Parse advisor response
                guidance = self._parse_advisor_response(advisor_response)
                guidance["model"] = advisor_model
                guidance["fallback_rank"] = fallback_rank

                # Record successful advisor consultation
                self._record_advisor_consultation(
                    task_id=decision_point.task_id,
                    decision_type=decision_point.decision_type,
                    executor_tier=executor_tier,
                    executor_model=executor_model,
                    advisor_model=advisor_model,
                    advisor_tokens=len(advisor_response.split()) * 1.3,
                    time_to_consult_ms=int(response_time),
                    question=decision_point.question,
                    guidance_summary=guidance.get("guidance", "")[:500],
                    fallback_rank=fallback_rank
                )

                logger.info(
                    f"Advisor consultation succeeded with {advisor_model} "
                    f"(rank {fallback_rank}, time={int(response_time)}ms)"
                )

                return guidance

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Advisor {advisor_model} (rank {fallback_rank}) failed: {e}. "
                    f"{'Trying next fallback...' if fallback_rank < len(advisor_models) - 1 else 'No more fallbacks.'}"
                )
                continue

        # All models in the chain failed
        logger.error(
            f"All advisor models failed for {decision_point.decision_type}. "
            f"Tried: {', '.join(advisor_models)}. Last error: {last_error}"
        )
        raise Exception(
            f"All {len(advisor_models)} advisor models failed. Last error: {last_error}"
        )

    async def _advisor_via_coordinator(
        self,
        prompt: str,
        model: str,
        max_tokens: int
    ) -> str:
        """Execute advisor call through hybrid coordinator/switchboard."""
        profile = getattr(Config, "AI_ADVISOR_PROFILE", "remote-reasoning") if Config else "remote-reasoning"

        # Determine if model should override profile routing
        # For specific models like gemini, qwen, gpt, route through appropriate profile
        model_profile_map = {
            "gemini": "remote-gemini",
            "qwen": "remote-coding",
            "gpt": "remote-reasoning",
            "claude-opus": "remote-reasoning",
            "claude-sonnet": "remote-reasoning",
            "deepseek": "remote-reasoning",
        }

        # Check if model name contains a known prefix
        for model_prefix, suggested_profile in model_profile_map.items():
            if model_prefix.lower() in model.lower():
                profile = suggested_profile
                logger.info(f"Routing advisor {model} through profile {profile}")
                break

        payload = {
            "task": prompt,
            "profile": profile,
            "prefer_local": False,
            "model": model,  # Pass explicit model for switchboard routing
            "system_prompt": (
                "You are an expert advisor providing guidance on complex decisions. "
                "Provide concise, actionable recommendations focused on the specific decision point. "
                "Structure your response with: 1) Recommended approach, 2) Key considerations, 3) Action (proceed/modify/stop)."
            ),
            "context": {},
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "timeout_s": 30.0,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.hybrid_coordinator_endpoint}/control/ai-coordinator/delegate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=35.0),
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise Exception(
                        f"Advisor coordinator delegate returned {resp.status}: {str(body)[:240]}"
                    )

        response_text = self._extract_response_text(body)
        if not response_text:
            raise Exception("Advisor coordinator returned no response text")
        return response_text

    def _get_advisor_model_chain(self, decision_type: str) -> List[str]:
        """
        Get ranked fallback chain of advisor models for a decision type.

        Returns a list of 3-4 models to try in order. Strategy:
        1. Decision-type specific ranked chain (e.g., AI_ADVISOR_SECURITY_MODELS)
        2. Legacy single model override (e.g., AI_ADVISOR_SECURITY_MODEL) - prepended if set
        3. Primary advisor model (AI_ADVISOR_MODEL) - added if not in chain
        4. Global fallback chain (AI_ADVISOR_GLOBAL_FALLBACKS)

        Args:
            decision_type: Type of decision (architecture, security, planning, etc.)

        Returns:
            List of model names to try in ranked order (3-4 models)
        """
        if not Config:
            return ["claude-opus-4-5", "claude-sonnet", "gpt-4o", "gemini-2.0-flash-thinking"]

        chain = []

        # Decision-type specific ranked chains
        decision_chain_map = {
            "architecture": "AI_ADVISOR_ARCHITECTURE_MODELS",
            "security": "AI_ADVISOR_SECURITY_MODELS",
            "planning": "AI_ADVISOR_PLANNING_MODELS",
            "tradeoff": "AI_ADVISOR_TRADEOFF_MODELS",
            "ambiguity": "AI_ADVISOR_AMBIGUITY_MODELS",
        }

        # Get decision-specific ranked chain
        chain_key = decision_chain_map.get(decision_type)
        if chain_key:
            decision_chain = getattr(Config, chain_key, [])
            if decision_chain:
                chain.extend(decision_chain)
                logger.debug(f"Using ranked chain for {decision_type}: {decision_chain}")

        # Legacy single model override (prepend if set and not already in chain)
        legacy_model_map = {
            "architecture": "AI_ADVISOR_ARCHITECTURE_MODEL",
            "security": "AI_ADVISOR_SECURITY_MODEL",
            "planning": "AI_ADVISOR_PLANNING_MODEL",
            "tradeoff": "AI_ADVISOR_TRADEOFF_MODEL",
            "ambiguity": "AI_ADVISOR_AMBIGUITY_MODEL",
        }
        legacy_key = legacy_model_map.get(decision_type)
        if legacy_key:
            legacy_model = getattr(Config, legacy_key, "").strip()
            if legacy_model and legacy_model not in chain:
                chain.insert(0, legacy_model)
                logger.debug(f"Prepending legacy override: {legacy_model}")

        # Add primary advisor model if not already in chain
        primary_model = getattr(Config, "AI_ADVISOR_MODEL", "").strip()
        if primary_model and primary_model not in chain:
            chain.append(primary_model)

        # Add global fallbacks (deduped)
        global_fallbacks = getattr(Config, "AI_ADVISOR_GLOBAL_FALLBACKS", [])
        for model in global_fallbacks:
            if model and model not in chain:
                chain.append(model)

        # Ensure we have at least one model
        if not chain:
            logger.warning("No advisor models configured, using default chain")
            chain = ["claude-opus-4-5", "claude-sonnet", "gpt-4o", "gemini-2.0-flash-thinking"]

        logger.info(f"Advisor chain for {decision_type}: {chain[:4]} ({len(chain)} total)")
        return chain

    def _build_advisor_prompt(self, decision_point: DecisionPoint) -> str:
        """Build focused prompt for advisor consultation."""
        return f"""Decision Point Analysis Request

Decision Type: {decision_point.decision_type}
Executor Tier: {decision_point.executor_tier}
Confidence: {decision_point.confidence:.2f}

Question:
{decision_point.question}

Context:
{json.dumps(decision_point.context, indent=2) if decision_point.context else "No additional context"}

Detected Signals: {', '.join(decision_point.detected_signals[:5])}

Please provide:
1. Recommended approach for this decision
2. Key considerations and potential pitfalls
3. Action: proceed (executor can handle), modify (executor needs adjustment), or stop (task should not proceed)

Keep response under 500 words."""

    def _parse_advisor_response(self, response: str) -> Dict:
        """
        Parse advisor response into structured guidance.

        Expected format:
        1. Recommended approach...
        2. Key considerations...
        3. Action: proceed/modify/stop

        Returns:
            {
                "guidance": str,
                "action": str,  # proceed, modify, stop
                "reasoning": str
            }
        """
        response_lower = response.lower()

        # Determine action from response
        action = "proceed"
        if "action: stop" in response_lower or "should not proceed" in response_lower:
            action = "stop"
        elif "action: modify" in response_lower or "needs adjustment" in response_lower or "consider revising" in response_lower:
            action = "modify"

        return {
            "guidance": response,
            "action": action,
            "reasoning": response[:200]  # First 200 chars as summary
        }

    def _record_advisor_consultation(
        self,
        task_id: str,
        decision_type: str,
        executor_tier: str,
        executor_model: str,
        advisor_model: str,
        advisor_tokens: float,
        time_to_consult_ms: int,
        question: str,
        guidance_summary: str,
        task_success: bool = None,
        fallback_rank: int = 0
    ):
        """Record advisor consultation for metrics."""
        # Estimate advisor cost (rough approximation)
        advisor_cost = advisor_tokens * 0.000015  # ~$15 per 1M tokens for Opus

        conn = sqlite3.connect(self.metrics_db)
        conn.execute("""
            INSERT INTO advisor_consultations
            (task_id, decision_type, executor_tier, executor_model, advisor_model,
             advisor_tokens, advisor_cost, time_to_consult_ms, question, guidance_summary,
             task_success, fallback_rank)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id, decision_type, executor_tier, executor_model, advisor_model,
            int(advisor_tokens), advisor_cost, time_to_consult_ms, question, guidance_summary,
            task_success, fallback_rank
        ))
        conn.commit()
        conn.close()

    def _estimate_cost(self, tier: AgentTier) -> float:
        """Estimate cost per task by tier (sourced from routing_contract.CostEstimates)."""
        if _CONTRACT_AVAILABLE:
            routing_tier = _legacy_tier_to_routing_tier(tier.value)
            return _CostEstimates.for_tier(routing_tier)
        # Legacy fallback (stale values — prefer routing_contract env vars instead)
        cost_map = {
            AgentTier.LOCAL: 0.0,
            AgentTier.FREE: 0.0,
            AgentTier.PAID: 0.005,
            AgentTier.CRITICAL: 0.025,
        }
        return cost_map.get(tier, 0.0)

    def _record_routing(self, task_type: str, complexity: str, tier: str,
                       model: str, success: bool, response_time_ms: int = 0,
                       cost_estimate: float = 0.0, escalated: bool = False,
                       escalated_from: str = None):
        """Record routing decision for metrics"""
        conn = sqlite3.connect(self.metrics_db)
        conn.execute("""
            INSERT INTO routing_decisions
            (task_type, complexity, tier, model, success, escalated,
             escalated_from, response_time_ms, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (task_type, complexity, tier, model, success, escalated,
              escalated_from, response_time_ms, cost_estimate))
        conn.commit()
        conn.close()

    def _record_escalation(self, from_tier: str, to_tier: str,
                          reason: str, task_type: str):
        """Record escalation event"""
        conn = sqlite3.connect(self.metrics_db)
        conn.execute("""
            INSERT INTO escalations (from_tier, to_tier, reason, task_type)
            VALUES (?, ?, ?, ?)
        """, (from_tier, to_tier, reason, task_type))
        conn.commit()
        conn.close()

    def get_metrics(self) -> Dict:
        """Get routing metrics and cost savings"""
        conn = sqlite3.connect(self.metrics_db)

        # Tier distribution
        cursor = conn.execute("""
            SELECT tier, COUNT(*) as count,
                   COUNT(*) * 100.0 / (SELECT COUNT(*) FROM routing_decisions) as pct
            FROM routing_decisions
            GROUP BY tier
        """)
        tier_distribution = {row[0]: {"count": row[1], "percentage": row[2]}
                           for row in cursor}

        # Cost savings
        total_tasks = conn.execute(
            "SELECT COUNT(*) FROM routing_decisions"
        ).fetchone()[0]

        actual_cost = conn.execute(
            "SELECT SUM(cost_estimate) FROM routing_decisions"
        ).fetchone()[0] or 0.0

        # If all tasks went to paid model
        potential_cost = total_tasks * 0.02
        savings = potential_cost - actual_cost

        # Escalation rate
        escalations = conn.execute(
            "SELECT COUNT(*) FROM routing_decisions WHERE escalated = 1"
        ).fetchone()[0]

        conn.close()

        return {
            "total_tasks": total_tasks,
            "tier_distribution": tier_distribution,
            "actual_cost_usd": actual_cost,
            "potential_cost_usd": potential_cost,
            "savings_usd": savings,
            "savings_percentage": (savings / potential_cost * 100) if potential_cost > 0 else 0,
            "escalation_count": escalations,
            "escalation_rate": (escalations / total_tasks * 100) if total_tasks > 0 else 0
        }

    def get_advisor_metrics(self) -> Dict:
        """Get advisor strategy metrics."""
        if not self.advisor_enabled:
            return {"advisor_enabled": False}

        conn = sqlite3.connect(self.metrics_db)
        try:
            # Total advisor consultations
            total_consultations = conn.execute(
                "SELECT COUNT(*) FROM advisor_consultations"
            ).fetchone()[0]

            # Decision type distribution
            decision_distribution = {
                row[0]: row[1]
                for row in conn.execute("""
                    SELECT decision_type, COUNT(*) as count
                    FROM advisor_consultations
                    GROUP BY decision_type
                """)
            }

            # Executor tier distribution
            executor_distribution = {
                row[0]: row[1]
                for row in conn.execute("""
                    SELECT executor_tier, COUNT(*) as count
                    FROM advisor_consultations
                    GROUP BY executor_tier
                """)
            }

            # Aggregated scalar metrics
            avg_time = conn.execute(
                "SELECT AVG(time_to_consult_ms) FROM advisor_consultations"
            ).fetchone()[0] or 0

            total_advisor_cost = conn.execute(
                "SELECT SUM(advisor_cost) FROM advisor_consultations"
            ).fetchone()[0] or 0.0

            total_tokens = conn.execute(
                "SELECT SUM(advisor_tokens) FROM advisor_consultations"
            ).fetchone()[0] or 0

            # Success rate (if tracked)
            success_data = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN task_success = 1 THEN 1 ELSE 0 END) as successes
                FROM advisor_consultations
                WHERE task_success IS NOT NULL
            """).fetchone()

            # Fallback usage statistics
            fallback_usage = {
                f"rank_{row[0]}": row[1]
                for row in conn.execute("""
                    SELECT fallback_rank, COUNT(*) as count
                    FROM advisor_consultations
                    GROUP BY fallback_rank
                    ORDER BY fallback_rank
                """)
            }

            # Cross-table: total routing decisions for consultation rate
            total_tasks = conn.execute(
                "SELECT COUNT(*) FROM routing_decisions"
            ).fetchone()[0] if total_consultations > 0 else 0
        finally:
            conn.close()

        success_rate = None
        if success_data and success_data[0] > 0:
            success_rate = (success_data[1] / success_data[0]) * 100

        consultation_rate = (total_consultations / total_tasks * 100) if total_tasks > 0 else 0

        primary_count = fallback_usage.get("rank_0", 0)
        fallback_count = total_consultations - primary_count
        primary_success_rate = (primary_count / total_consultations * 100) if total_consultations > 0 else 0

        return {
            "advisor_enabled": True,
            "total_consultations": total_consultations,
            "consultation_rate_percent": consultation_rate,
            "decision_distribution": decision_distribution,
            "executor_distribution": executor_distribution,
            "avg_consultation_time_ms": int(avg_time),
            "total_advisor_cost_usd": total_advisor_cost,
            "total_advisor_tokens": int(total_tokens),
            "avg_tokens_per_consultation": int(total_tokens / total_consultations) if total_consultations > 0 else 0,
            "task_success_rate_percent": success_rate,
            "fallback_usage": fallback_usage,
            "primary_success_rate_percent": primary_success_rate,
            "fallback_rate_percent": (fallback_count / total_consultations * 100) if total_consultations > 0 else 0
        }


# ============================================================================
# Singleton instance
# ============================================================================

_router = None

def get_router() -> LLMRouter:
    """Get singleton router instance"""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
