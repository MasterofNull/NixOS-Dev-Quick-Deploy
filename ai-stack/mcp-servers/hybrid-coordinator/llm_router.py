"""
Intelligent LLM Router - Maximize Local/Free, Minimize Paid
Routes tasks across three tiers: Local > Free > Paid
Target: 80% local, 15% free, 5% paid
"""

import aiohttp
import asyncio
import logging
import sqlite3
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


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
        self.local_llm_endpoint = "http://localhost:8080"
        self.local_embed_endpoint = "http://localhost:8081"
        self.hybrid_coordinator_endpoint = "http://localhost:8003"

        # Routing metrics
        self.metrics_db = metrics_db or "routing_metrics.db"
        self._init_metrics_db()

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
        # Placeholder - integrate with actual free model APIs
        # For now, fallback to local
        logger.info(f"Free agent {model} not yet implemented, using local")
        return await self._execute_local(task, "llama-cpp-local")

    async def _execute_paid(self, task: Dict, model: str) -> str:
        """Execute task with paid model (last resort)"""
        # Placeholder - this would integrate with Claude API
        raise NotImplementedError(
            f"Paid model {model} execution should be rare. "
            f"Consider if this task can be handled locally."
        )

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

        if optimize_for == "local":
            # Concise prompts work best with local models
            return f"""Task: {task['description']}

Context: {task.get('context', {}).get('summary', 'N/A')}

Provide a direct, focused response. Be concise and specific.

Response:"""

        else:
            # More detailed prompts for larger models
            return f"""<task>
{task['description']}
</task>

<context>
{json.dumps(task.get('context', {}), indent=2)}
</context>

<instructions>
Analyze the task and provide a comprehensive response.
Consider edge cases and provide reasoning.
</instructions>

<response>
"""

    def _estimate_cost(self, tier: AgentTier) -> float:
        """Estimate cost per task by tier"""
        cost_map = {
            AgentTier.LOCAL: 0.0,      # Infrastructure already paid
            AgentTier.FREE: 0.0,       # Free tier APIs
            AgentTier.PAID: 0.02,      # ~$0.02 per task
            AgentTier.CRITICAL: 0.05   # ~$0.05 per task
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
