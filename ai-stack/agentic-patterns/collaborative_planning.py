#!/usr/bin/env python3
"""
Collaborative Planning

Enables multiple agents to contribute to planning, with LLM synthesis
into coherent strategy and phase assignments to best-suited agents.

Part of Phase 4: Advanced Multi-Agent Collaboration
"""

import asyncio
import aiohttp
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("collaborative_planning")

LLAMA_CHAT_URL = os.getenv("LLAMA_CHAT_URL", "http://127.0.0.1:8080")


class PlanPhaseType(Enum):
    """Types of plan phases"""
    RESEARCH = "research"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    REVIEW = "review"
    DEPLOYMENT = "deployment"


@dataclass
class PlanContribution:
    """Individual agent contribution to plan"""
    contribution_id: str
    agent_id: str
    agent_capability_score: float
    phase_type: PlanPhaseType
    description: str
    approach: str
    estimated_effort: str
    dependencies: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    confidence: float = 0.8
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['phase_type'] = self.phase_type.value
        d['created_at'] = self.created_at.isoformat()
        return d


@dataclass
class SynthesizedPlanPhase:
    """Synthesized plan phase from multiple contributions"""
    phase_id: str
    phase_type: PlanPhaseType
    title: str
    description: str
    approach: str
    assigned_agent: str
    assignment_reason: str
    dependencies: List[str] = field(default_factory=list)
    estimated_effort: str = "medium"
    risks: List[str] = field(default_factory=list)
    source_contributions: List[str] = field(default_factory=list)  # contribution_ids
    confidence: float = 0.8

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['phase_type'] = self.phase_type.value
        return d


@dataclass
class CollaborativePlan:
    """Complete collaborative plan"""
    plan_id: str
    objective: str
    contributions: List[PlanContribution] = field(default_factory=list)
    synthesized_phases: List[SynthesizedPlanPhase] = field(default_factory=list)
    overall_strategy: str = ""
    estimated_timeline: str = ""
    critical_risks: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    synthesized_at: Optional[datetime] = None
    status: str = "collecting_contributions"  # collecting_contributions, synthesized, approved, in_execution


class CollaborativePlanner:
    """
    Orchestrates collaborative planning across multiple agents.
    """

    def __init__(self, llama_url: str = LLAMA_CHAT_URL):
        self.llama_url = llama_url
        self.http_client = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120))
        self.active_plans: Dict[str, CollaborativePlan] = {}

        logger.info("CollaborativePlanner initialized")

    async def close(self):
        """Close HTTP client"""
        await self.http_client.close()

    async def call_local_llm(
        self, prompt: str, max_tokens: int = 2000, temperature: float = 0.3
    ) -> str:
        """Call local LLM for synthesis."""
        try:
            async with self.http_client.post(
                f"{self.llama_url}/v1/chat/completions",
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a planning synthesis expert. "
                                     "Analyze multiple plan contributions and create coherent, "
                                     "actionable execution plans."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error(f"LLM call failed: {exc}")
            return ""

    def create_plan(self, objective: str) -> str:
        """Create new collaborative plan"""
        plan_id = str(uuid4())
        plan = CollaborativePlan(
            plan_id=plan_id,
            objective=objective
        )
        self.active_plans[plan_id] = plan

        logger.info(f"Created plan: {plan_id} for objective: {objective}")
        return plan_id

    def add_contribution(
        self,
        plan_id: str,
        agent_id: str,
        agent_capability_score: float,
        phase_type: PlanPhaseType,
        description: str,
        approach: str,
        estimated_effort: str = "medium",
        dependencies: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
        confidence: float = 0.8
    ) -> str:
        """Add agent contribution to plan"""
        plan = self.active_plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        contribution = PlanContribution(
            contribution_id=str(uuid4()),
            agent_id=agent_id,
            agent_capability_score=agent_capability_score,
            phase_type=phase_type,
            description=description,
            approach=approach,
            estimated_effort=estimated_effort,
            dependencies=dependencies or [],
            risks=risks or [],
            confidence=confidence
        )

        plan.contributions.append(contribution)

        logger.info(
            f"Added contribution from {agent_id} to plan {plan_id} "
            f"(phase={phase_type.value}, confidence={confidence})"
        )

        return contribution.contribution_id

    async def synthesize_plan(
        self,
        plan_id: str,
        agent_capabilities: Dict[str, float]
    ) -> CollaborativePlan:
        """
        Synthesize contributions into coherent plan using LLM.

        Args:
            plan_id: Plan to synthesize
            agent_capabilities: Agent capability scores by domain

        Returns:
            Updated plan with synthesized phases
        """
        plan = self.active_plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        if not plan.contributions:
            logger.warning(f"No contributions to synthesize for plan {plan_id}")
            return plan

        # Group contributions by phase type
        contributions_by_phase = defaultdict(list)
        for contrib in plan.contributions:
            contributions_by_phase[contrib.phase_type].append(contrib)

        # Build synthesis prompt
        prompt = self._build_synthesis_prompt(plan, contributions_by_phase, agent_capabilities)

        # Call LLM for synthesis
        llm_response = await self.call_local_llm(prompt, max_tokens=2500)

        # Parse LLM response
        synthesis_result = self._parse_synthesis_response(llm_response)

        if not synthesis_result:
            logger.error("Failed to parse synthesis response")
            return plan

        # Create synthesized phases
        plan.synthesized_phases = []

        for phase_data in synthesis_result.get("phases", []):
            phase = SynthesizedPlanPhase(
                phase_id=str(uuid4()),
                phase_type=PlanPhaseType(phase_data["phase_type"]),
                title=phase_data["title"],
                description=phase_data["description"],
                approach=phase_data["approach"],
                assigned_agent=phase_data["assigned_agent"],
                assignment_reason=phase_data["assignment_reason"],
                dependencies=phase_data.get("dependencies", []),
                estimated_effort=phase_data.get("estimated_effort", "medium"),
                risks=phase_data.get("risks", []),
                source_contributions=phase_data.get("source_contributions", []),
                confidence=float(phase_data.get("confidence", 0.8))
            )
            plan.synthesized_phases.append(phase)

        # Set overall strategy
        plan.overall_strategy = synthesis_result.get("overall_strategy", "")
        plan.estimated_timeline = synthesis_result.get("estimated_timeline", "")
        plan.critical_risks = synthesis_result.get("critical_risks", [])
        plan.synthesized_at = datetime.now()
        plan.status = "synthesized"

        logger.info(
            f"Synthesized plan {plan_id}: {len(plan.synthesized_phases)} phases, "
            f"{len(plan.contributions)} contributions"
        )

        return plan

    def _build_synthesis_prompt(
        self,
        plan: CollaborativePlan,
        contributions_by_phase: Dict[PlanPhaseType, List[PlanContribution]],
        agent_capabilities: Dict[str, float]
    ) -> str:
        """Build prompt for LLM synthesis"""

        # Format contributions
        contributions_text = []
        for phase_type, contribs in contributions_by_phase.items():
            contributions_text.append(f"\n{phase_type.value.upper()} Phase Contributions:")
            for i, contrib in enumerate(contribs, 1):
                contributions_text.append(
                    f"  {i}. Agent: {contrib.agent_id} (capability={contrib.agent_capability_score:.2f}, "
                    f"confidence={contrib.confidence:.2f})\n"
                    f"     Description: {contrib.description}\n"
                    f"     Approach: {contrib.approach}\n"
                    f"     Effort: {contrib.estimated_effort}\n"
                    f"     Risks: {', '.join(contrib.risks) if contrib.risks else 'None'}"
                )

        contributions_summary = "\n".join(contributions_text)

        # Format agent capabilities
        agent_caps_text = "\n".join(
            f"  - {agent_id}: {score:.2f}"
            for agent_id, score in sorted(agent_capabilities.items(), key=lambda x: x[1], reverse=True)
        )

        prompt = f"""Synthesize multiple agent plan contributions into a coherent execution plan.

**Objective:** {plan.objective}

**Agent Contributions:**
{contributions_summary}

**Agent Capabilities:**
{agent_caps_text}

**Instructions:**
1. Analyze all contributions and identify the best approach for each phase
2. Assign each phase to the most capable agent
3. Create a coherent overall strategy
4. Identify dependencies between phases
5. Estimate realistic timeline
6. Highlight critical risks

Respond in JSON format:
{{
  "overall_strategy": "brief description of overall approach",
  "estimated_timeline": "realistic timeline estimate",
  "critical_risks": ["risk 1", "risk 2"],
  "phases": [
    {{
      "phase_type": "research|design|implementation|testing|review|deployment",
      "title": "phase title",
      "description": "what this phase accomplishes",
      "approach": "how this phase will be executed",
      "assigned_agent": "agent_id",
      "assignment_reason": "why this agent is best suited",
      "dependencies": ["phase_id or description"],
      "estimated_effort": "low|medium|high",
      "risks": ["risk 1", "risk 2"],
      "confidence": 0.0-1.0
    }}
  ]
}}

JSON:"""

        return prompt

    def _parse_synthesis_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM synthesis response"""
        if not response:
            return None

        try:
            # Try direct parse
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting from code blocks
        if "```json" in response:
            try:
                json_str = response.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        # Try finding JSON object
        if "{" in response and "}" in response:
            try:
                start = response.index("{")
                end = response.rindex("}") + 1
                json_str = response[start:end]
                return json.loads(json_str)
            except (ValueError, json.JSONDecodeError):
                pass

        logger.warning("Could not parse synthesis response")
        return None

    def get_execution_order(self, plan_id: str) -> List[SynthesizedPlanPhase]:
        """Get phases in execution order based on dependencies"""
        plan = self.active_plans.get(plan_id)
        if not plan or not plan.synthesized_phases:
            return []

        # Simple topological sort by phase type order
        phase_order = [
            PlanPhaseType.RESEARCH,
            PlanPhaseType.DESIGN,
            PlanPhaseType.IMPLEMENTATION,
            PlanPhaseType.TESTING,
            PlanPhaseType.REVIEW,
            PlanPhaseType.DEPLOYMENT
        ]

        sorted_phases = sorted(
            plan.synthesized_phases,
            key=lambda p: phase_order.index(p.phase_type)
        )

        return sorted_phases

    def get_plan_summary(self, plan_id: str) -> Dict[str, Any]:
        """Get plan summary"""
        plan = self.active_plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}

        return {
            "plan_id": plan_id,
            "objective": plan.objective,
            "status": plan.status,
            "contributions_count": len(plan.contributions),
            "unique_contributors": len(set(c.agent_id for c in plan.contributions)),
            "phases_count": len(plan.synthesized_phases),
            "overall_strategy": plan.overall_strategy,
            "estimated_timeline": plan.estimated_timeline,
            "critical_risks_count": len(plan.critical_risks),
            "created_at": plan.created_at.isoformat(),
            "synthesized_at": plan.synthesized_at.isoformat() if plan.synthesized_at else None
        }


async def main():
    """Example usage"""
    planner = CollaborativePlanner()

    try:
        # Create plan
        plan_id = planner.create_plan("Implement user authentication system")

        # Add contributions from different agents
        planner.add_contribution(
            plan_id=plan_id,
            agent_id="security_expert",
            agent_capability_score=0.95,
            phase_type=PlanPhaseType.DESIGN,
            description="Design secure authentication flow",
            approach="Use OAuth 2.0 with JWT tokens, implement rate limiting",
            estimated_effort="medium",
            risks=["Token expiration edge cases", "Session hijacking"],
            confidence=0.9
        )

        planner.add_contribution(
            plan_id=plan_id,
            agent_id="backend_developer",
            agent_capability_score=0.85,
            phase_type=PlanPhaseType.IMPLEMENTATION,
            description="Implement auth backend",
            approach="Create auth service with FastAPI, integrate with PostgreSQL",
            estimated_effort="high",
            dependencies=["Design phase completion"],
            risks=["Database migration complexity"],
            confidence=0.8
        )

        planner.add_contribution(
            plan_id=plan_id,
            agent_id="qa_engineer",
            agent_capability_score=0.90,
            phase_type=PlanPhaseType.TESTING,
            description="Test authentication system",
            approach="Unit tests, integration tests, security penetration testing",
            estimated_effort="medium",
            dependencies=["Implementation completion"],
            risks=["Hard to test edge cases"],
            confidence=0.85
        )

        # Synthesize plan
        agent_capabilities = {
            "security_expert": 0.95,
            "backend_developer": 0.85,
            "qa_engineer": 0.90
        }

        print("\nSynthesizing plan...")
        synthesized_plan = await planner.synthesize_plan(plan_id, agent_capabilities)

        # Get execution order
        execution_order = planner.get_execution_order(plan_id)

        print(f"\nExecution Plan ({len(execution_order)} phases):")
        for i, phase in enumerate(execution_order, 1):
            print(f"\n{i}. {phase.title} ({phase.phase_type.value})")
            print(f"   Assigned to: {phase.assigned_agent}")
            print(f"   Reason: {phase.assignment_reason}")
            print(f"   Effort: {phase.estimated_effort}")
            print(f"   Confidence: {phase.confidence:.2f}")

        # Get summary
        summary = planner.get_plan_summary(plan_id)
        print(f"\nPlan Summary:")
        print(json.dumps(summary, indent=2))

    finally:
        await planner.close()


if __name__ == "__main__":
    asyncio.run(main())
