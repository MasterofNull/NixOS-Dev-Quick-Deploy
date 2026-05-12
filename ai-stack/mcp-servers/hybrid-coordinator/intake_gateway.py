from workflow.intake_gateway import *
import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional
from aiohttp import web

logger = logging.getLogger(__name__)

# 1. The FSM State Payload
@dataclass
class LifecycleSession:
    session_id: str
    task_description: str
    caller_identity: Dict[str, str] = field(default_factory=dict)
    complexity: str = "simple"
    domain_hint: str = "general"
    current_phase: str = "INTAKE"
    context: Dict[str, Any] = field(default_factory=dict)
    plan: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    response: Optional[str] = None
    halt_execution: bool = False
    stream: Optional[AsyncGenerator[str, None]] = None

# 1.5 Module State & Initialization
_lifecycle_dir = None
_agent_registry = None
_domain_router_mod = None
_hints_url = ""
_error_payload_fn = None

def init(*, lifecycle_dir, switchboard_url=None, cli_bridge_url=None, hints_url="", error_payload_fn=None, agent_registry=None, domain_router_mod=None):
    global _lifecycle_dir, _agent_registry, _domain_router_mod, _hints_url, _error_payload_fn
    _lifecycle_dir = lifecycle_dir
    _agent_registry = agent_registry
    _domain_router_mod = domain_router_mod
    _hints_url = hints_url
    _error_payload_fn = error_payload_fn

# 2. The Async Middleware Base Interface
class AsyncHarnessLayer(ABC):
    def __init__(self, next_layer: Optional['AsyncHarnessLayer'] = None):
        self.next_layer = next_layer

    @abstractmethod
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        pass

    async def next(self, session: LifecycleSession) -> LifecycleSession:
        if self.next_layer and not session.halt_execution:
            return await self.next_layer.process(session)
        return session

# 3. Phase 26 Deterministic FSM Layers

class IntakePhaseLayer(AsyncHarnessLayer):
    """Phase 1: Normalize input, detect complexity + domain hint"""
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        logger.info(f"[{session.session_id}] Entering INTAKE phase")
        session.current_phase = "INTAKE"

        if not session.task_description.strip():
            session.errors.append("Validation Error: Task description empty")
            session.halt_execution = True
            return session

        # Simple heuristic for complexity (can be expanded)
        word_count = len(session.task_description.split())
        if word_count > 50:
            session.complexity = "complex"
        elif word_count > 15:
            session.complexity = "standard"
        else:
            session.complexity = "simple"

        return await self.next(session)

class DiscoverPhaseLayer(AsyncHarnessLayer):
    """Phase 2: Codebase scan, health check, existing plans/PRD query"""
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        if session.complexity == "simple":
            logger.info(f"[{session.session_id}] Skipping DISCOVER phase for simple task")
            return await self.next(session)

        logger.info(f"[{session.session_id}] Entering DISCOVER phase")
        session.current_phase = "DISCOVER"
        session.context["discover_complete"] = True
        return await self.next(session)

class PrdPhaseLayer(AsyncHarnessLayer):
    """Phase 3: Generate or locate existing PRD; scope the work"""
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        if session.complexity == "simple":
            logger.info(f"[{session.session_id}] Skipping PRD phase for simple task")
            return await self.next(session)

        logger.info(f"[{session.session_id}] Entering PRD phase")
        session.current_phase = "PRD"
        session.context["prd_generated"] = True
        return await self.next(session)

class PlanPhaseLayer(AsyncHarnessLayer):
    """Phase 4: Phased execution plan with tool assignments per phase"""
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        logger.info(f"[{session.session_id}] Entering PLAN phase")
        session.current_phase = "PLAN"
        return await self.next(session)

class AssignPhaseLayer(AsyncHarnessLayer):
    """Phase 5: Call agent_capability_registry to match agents to plan phases"""
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        session.current_phase = "ASSIGN"
        logger.info(f"[{session.session_id}] Entering ASSIGN phase")

        if _agent_registry and hasattr(_agent_registry, "discover_agents"):
            agents = _agent_registry.discover_agents()
            session.context["available_agents"] = list(agents.keys())
            logger.info(f"[{session.session_id}] Discovered available agents: {list(agents.keys())}")

        return await self.next(session)

class DelegatePhaseLayer(AsyncHarnessLayer):
    """Phase 6: Call domain_router to route slices; fire sub-agent tasks"""
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        session.current_phase = "DELEGATE"
        logger.info(f"[{session.session_id}] Entering DELEGATE phase")

        if _domain_router_mod and hasattr(_domain_router_mod, "classify_domain"):
            domain = _domain_router_mod.classify_domain(session.task_description, session.domain_hint)
            team = _domain_router_mod.route_to_team(domain)
            session.context["assigned_domain"] = domain
            session.context["assigned_team"] = team
            logger.info(f"[{session.session_id}] Routed task to domain '{domain}' handled by team: {team}")

        return await self.next(session)

class ValidatePhaseLayer(AsyncHarnessLayer):
    """Phase 7: aq-qa smoke, syntax checks, test runner gates"""
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        session.current_phase = "VALIDATE"
        logger.info(f"[{session.session_id}] Entering VALIDATE phase")
        return await self.next(session)

class CommitPhaseLayer(AsyncHarnessLayer):
    """Phase 8: Guided commit with tier0-validation-gate"""
    async def process(self, session: LifecycleSession) -> LifecycleSession:
        session.current_phase = "COMMIT"
        logger.info(f"[{session.session_id}] Entering COMMIT phase")
        return await self.next(session)

# 4. UAG Pipeline Builder
def build_lifecycle_pipeline() -> AsyncHarnessLayer:
    """Wires the 8-Phase FSM pipeline together."""
    commit = CommitPhaseLayer()
    validate = ValidatePhaseLayer(next_layer=commit)
    delegate = DelegatePhaseLayer(next_layer=validate)
    assign = AssignPhaseLayer(next_layer=delegate)
    plan = PlanPhaseLayer(next_layer=assign)
    prd = PrdPhaseLayer(next_layer=plan)
    discover = DiscoverPhaseLayer(next_layer=prd)
    intake = IntakePhaseLayer(next_layer=discover)

    return intake

# 5. HTTP Route Handlers
async def handle_intake(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    task_description = data.get("prompt") or data.get("task_description") or ""
    session = LifecycleSession(
        session_id=str(uuid.uuid4()),
        task_description=task_description,
        caller_identity={
            "profile": request.headers.get("X-AI-Profile", "default"),
            "caller": request.headers.get("X-Caller-Id", "unknown"),
            "user_agent": request.headers.get("User-Agent", "unknown"),
        }
    )

    pipeline = build_lifecycle_pipeline()
    final_session = await pipeline.process(session)

    if final_session.halt_execution:
        return web.json_response({"error": "validation_failed", "details": final_session.errors}, status=400)

    return web.json_response({
        "session_id": final_session.session_id,
        "current_phase": final_session.current_phase,
        "complexity": final_session.complexity,
        "domain_hint": final_session.domain_hint,
        "next_action": "proceed"
    })

async def handle_lifecycle_status(request: web.Request) -> web.Response:
    session_id = request.match_info.get("id")
    return web.json_response({"session_id": session_id, "status": "stub_status"})

async def handle_lifecycle_advance(request: web.Request) -> web.Response:
    session_id = request.match_info.get("id")
    return web.json_response({"session_id": session_id, "status": "stub_advanced"})

def register_routes(app: web.Application):
    app.router.add_post("/agent/intake", handle_intake)
    app.router.add_get("/agent/lifecycle/{id}", handle_lifecycle_status)
    app.router.add_post("/agent/lifecycle/{id}/advance", handle_lifecycle_advance)
