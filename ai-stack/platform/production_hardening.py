#!/usr/bin/env python3
"""
Production Hardening

Rate limiting, cost budgets, circuit breakers, security isolation,
and audit logging for production deployments.

Part of Phase 5: Platform Maturity & Ecosystem
"""

import asyncio
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4
import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("production_hardening")


class CircuitState(Enum):
    """Circuit breaker state"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class AuditEventType(Enum):
    """Audit event types"""
    AGENT_REGISTRATION = "agent_registration"
    TASK_SUBMISSION = "task_submission"
    MEMORY_STORE = "memory_store"
    MEMORY_RECALL = "memory_recall"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    CIRCUIT_OPENED = "circuit_opened"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostBudget:
    """Cost budget configuration"""
    budget_id: str
    agent_id: str
    daily_budget_usd: float
    monthly_budget_usd: float
    cost_per_token: float = 0.000015  # Default for mid-tier models
    alert_threshold_pct: float = 0.8  # Alert at 80%

    current_daily_spend: float = 0.0
    current_monthly_spend: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CircuitBreaker:
    """Circuit breaker for failure isolation"""
    service_name: str
    state: CircuitState = CircuitState.CLOSED
    failure_threshold: int = 5
    success_threshold: int = 2  # For half-open -> closed
    timeout_seconds: int = 60

    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    opened_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['state'] = self.state.value
        d['last_failure_time'] = self.last_failure_time.isoformat() if self.last_failure_time else None
        d['opened_at'] = self.opened_at.isoformat() if self.opened_at else None
        return d


@dataclass
class AuditEvent:
    """Audit log event"""
    event_id: str
    event_type: AuditEventType
    agent_id: str
    details: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['event_type'] = self.event_type.value
        d['timestamp'] = self.timestamp.isoformat()
        return d


class RateLimiter:
    """
    Token bucket rate limiter with multiple time windows.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config

        # Token buckets per time window
        self.minute_tokens: Dict[str, deque] = defaultdict(lambda: deque(maxlen=config.requests_per_minute))
        self.hour_tokens: Dict[str, deque] = defaultdict(lambda: deque(maxlen=config.requests_per_hour))
        self.day_tokens: Dict[str, deque] = defaultdict(lambda: deque(maxlen=config.requests_per_day))

        logger.info(f"RateLimiter initialized: {config.requests_per_minute} req/min")

    def check_limit(self, agent_id: str) -> bool:
        """Check if request is within rate limits"""
        now = datetime.now()

        # Clean old tokens
        self._cleanup_tokens(agent_id, now)

        # Check limits
        if len(self.minute_tokens[agent_id]) >= self.config.requests_per_minute:
            logger.warning(f"Rate limit exceeded (minute): {agent_id}")
            return False

        if len(self.hour_tokens[agent_id]) >= self.config.requests_per_hour:
            logger.warning(f"Rate limit exceeded (hour): {agent_id}")
            return False

        if len(self.day_tokens[agent_id]) >= self.config.requests_per_day:
            logger.warning(f"Rate limit exceeded (day): {agent_id}")
            return False

        # Add token
        self.minute_tokens[agent_id].append(now)
        self.hour_tokens[agent_id].append(now)
        self.day_tokens[agent_id].append(now)

        return True

    def _cleanup_tokens(self, agent_id: str, now: datetime):
        """Remove expired tokens"""
        # Minute window
        while self.minute_tokens[agent_id] and (now - self.minute_tokens[agent_id][0]) > timedelta(minutes=1):
            self.minute_tokens[agent_id].popleft()

        # Hour window
        while self.hour_tokens[agent_id] and (now - self.hour_tokens[agent_id][0]) > timedelta(hours=1):
            self.hour_tokens[agent_id].popleft()

        # Day window
        while self.day_tokens[agent_id] and (now - self.day_tokens[agent_id][0]) > timedelta(days=1):
            self.day_tokens[agent_id].popleft()

    def get_remaining_quota(self, agent_id: str) -> Dict[str, int]:
        """Get remaining request quota"""
        self._cleanup_tokens(agent_id, datetime.now())

        return {
            "minute": self.config.requests_per_minute - len(self.minute_tokens[agent_id]),
            "hour": self.config.requests_per_hour - len(self.hour_tokens[agent_id]),
            "day": self.config.requests_per_day - len(self.day_tokens[agent_id])
        }


class BudgetManager:
    """
    Manages cost budgets with alerts and enforcement.
    """

    def __init__(
        self,
        pg_host: str = "127.0.0.1",
        pg_port: int = 5432,
        pg_user: str = "postgres",
        pg_database: str = "ai_context",
        pg_password: str = ""
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password

        self.conn: Optional[asyncpg.Connection] = None
        self.budgets: Dict[str, CostBudget] = {}

        logger.info("BudgetManager initialized")

    async def connect(self):
        """Connect to PostgreSQL"""
        self.conn = await asyncpg.connect(
            host=self.pg_host,
            port=self.pg_port,
            user=self.pg_user,
            database=self.pg_database,
            password=self.pg_password
        )
        logger.info("Connected to PostgreSQL")

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()

    async def set_budget(self, budget: CostBudget):
        """Set or update cost budget"""
        await self.conn.execute("""
            INSERT INTO cost_budgets (
                budget_id, agent_id, daily_budget_usd, monthly_budget_usd,
                cost_per_token, alert_threshold_pct
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (agent_id) DO UPDATE SET
                daily_budget_usd = EXCLUDED.daily_budget_usd,
                monthly_budget_usd = EXCLUDED.monthly_budget_usd,
                cost_per_token = EXCLUDED.cost_per_token,
                alert_threshold_pct = EXCLUDED.alert_threshold_pct,
                updated_at = NOW()
        """,
            budget.budget_id,
            budget.agent_id,
            budget.daily_budget_usd,
            budget.monthly_budget_usd,
            budget.cost_per_token,
            budget.alert_threshold_pct
        )

        self.budgets[budget.agent_id] = budget
        logger.info(f"Budget set for {budget.agent_id}: ${budget.daily_budget_usd}/day")

    async def check_budget(self, agent_id: str, estimated_cost: float) -> bool:
        """Check if operation is within budget"""
        budget = self.budgets.get(agent_id)
        if not budget:
            # No budget set, allow operation
            return True

        # Get current spend
        daily_spend = await self._get_daily_spend(agent_id)
        monthly_spend = await self._get_monthly_spend(agent_id)

        # Check limits
        if daily_spend + estimated_cost > budget.daily_budget_usd:
            logger.warning(f"Daily budget exceeded for {agent_id}: ${daily_spend:.2f} + ${estimated_cost:.2f} > ${budget.daily_budget_usd}")
            return False

        if monthly_spend + estimated_cost > budget.monthly_budget_usd:
            logger.warning(f"Monthly budget exceeded for {agent_id}: ${monthly_spend:.2f} + ${estimated_cost:.2f} > ${budget.monthly_budget_usd}")
            return False

        # Check alert threshold
        daily_pct = (daily_spend + estimated_cost) / budget.daily_budget_usd
        if daily_pct >= budget.alert_threshold_pct:
            logger.warning(f"Budget alert for {agent_id}: {daily_pct:.1%} of daily budget used")

        return True

    async def record_cost(self, agent_id: str, cost: float, tokens_used: int):
        """Record actual cost incurred"""
        await self.conn.execute("""
            INSERT INTO cost_tracking (
                tracking_id, agent_id, cost_usd, tokens_used
            ) VALUES ($1, $2, $3, $4)
        """, str(uuid4()), agent_id, cost, tokens_used)

        logger.info(f"Cost recorded for {agent_id}: ${cost:.4f} ({tokens_used} tokens)")

    async def _get_daily_spend(self, agent_id: str) -> float:
        """Get current daily spend"""
        spend = await self.conn.fetchval("""
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM cost_tracking
            WHERE agent_id = $1
              AND created_at >= CURRENT_DATE
        """, agent_id)
        return float(spend)

    async def _get_monthly_spend(self, agent_id: str) -> float:
        """Get current monthly spend"""
        spend = await self.conn.fetchval("""
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM cost_tracking
            WHERE agent_id = $1
              AND created_at >= date_trunc('month', CURRENT_DATE)
        """, agent_id)
        return float(spend)

    async def get_budget_summary(self, agent_id: str) -> Dict[str, Any]:
        """Get budget summary"""
        budget = self.budgets.get(agent_id)
        if not budget:
            return {"error": "No budget set"}

        daily_spend = await self._get_daily_spend(agent_id)
        monthly_spend = await self._get_monthly_spend(agent_id)

        return {
            "agent_id": agent_id,
            "daily_budget": budget.daily_budget_usd,
            "daily_spend": daily_spend,
            "daily_remaining": budget.daily_budget_usd - daily_spend,
            "daily_pct_used": (daily_spend / budget.daily_budget_usd) * 100,
            "monthly_budget": budget.monthly_budget_usd,
            "monthly_spend": monthly_spend,
            "monthly_remaining": budget.monthly_budget_usd - monthly_spend,
            "monthly_pct_used": (monthly_spend / budget.monthly_budget_usd) * 100
        }


class CircuitBreakerManager:
    """
    Manages circuit breakers for failure isolation.
    """

    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        logger.info("CircuitBreakerManager initialized")

    def register_service(
        self,
        service_name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60
    ):
        """Register service with circuit breaker"""
        self.breakers[service_name] = CircuitBreaker(
            service_name=service_name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_seconds=timeout_seconds
        )
        logger.info(f"Circuit breaker registered: {service_name}")

    def can_execute(self, service_name: str) -> bool:
        """Check if circuit allows execution"""
        breaker = self.breakers.get(service_name)
        if not breaker:
            return True

        now = datetime.now()

        if breaker.state == CircuitState.CLOSED:
            return True

        if breaker.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if breaker.opened_at and (now - breaker.opened_at).total_seconds() >= breaker.timeout_seconds:
                # Move to half-open
                breaker.state = CircuitState.HALF_OPEN
                breaker.success_count = 0
                logger.info(f"Circuit breaker half-open: {service_name}")
                return True
            return False

        if breaker.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self, service_name: str):
        """Record successful execution"""
        breaker = self.breakers.get(service_name)
        if not breaker:
            return

        breaker.failure_count = 0

        if breaker.state == CircuitState.HALF_OPEN:
            breaker.success_count += 1
            if breaker.success_count >= breaker.success_threshold:
                breaker.state = CircuitState.CLOSED
                breaker.opened_at = None
                logger.info(f"Circuit breaker closed: {service_name}")

    def record_failure(self, service_name: str):
        """Record failed execution"""
        breaker = self.breakers.get(service_name)
        if not breaker:
            return

        breaker.failure_count += 1
        breaker.last_failure_time = datetime.now()

        if breaker.state == CircuitState.HALF_OPEN:
            # Failed during recovery, reopen
            breaker.state = CircuitState.OPEN
            breaker.opened_at = datetime.now()
            logger.warning(f"Circuit breaker reopened: {service_name}")

        elif breaker.state == CircuitState.CLOSED:
            if breaker.failure_count >= breaker.failure_threshold:
                breaker.state = CircuitState.OPEN
                breaker.opened_at = datetime.now()
                logger.warning(f"Circuit breaker opened: {service_name} ({breaker.failure_count} failures)")

    def get_status(self, service_name: str) -> Dict[str, Any]:
        """Get circuit breaker status"""
        breaker = self.breakers.get(service_name)
        if not breaker:
            return {"error": "Service not registered"}

        return breaker.to_dict()


class AuditLogger:
    """
    Compliance audit logging with PostgreSQL persistence.
    """

    def __init__(
        self,
        pg_host: str = "127.0.0.1",
        pg_port: int = 5432,
        pg_user: str = "postgres",
        pg_database: str = "ai_context",
        pg_password: str = ""
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password

        self.conn: Optional[asyncpg.Connection] = None

        logger.info("AuditLogger initialized")

    async def connect(self):
        """Connect to PostgreSQL"""
        self.conn = await asyncpg.connect(
            host=self.pg_host,
            port=self.pg_port,
            user=self.pg_user,
            database=self.pg_database,
            password=self.pg_password
        )
        logger.info("Connected to PostgreSQL")

    async def close(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()

    async def log_event(self, event: AuditEvent):
        """Log audit event"""
        await self.conn.execute("""
            INSERT INTO audit_events (
                event_id, event_type, agent_id, details, metadata
            ) VALUES ($1, $2, $3, $4, $5)
        """,
            event.event_id,
            event.event_type.value,
            event.agent_id,
            json.dumps(event.details),
            json.dumps(event.metadata)
        )

        logger.info(f"Audit event logged: {event.event_type.value} by {event.agent_id}")

    async def query_events(
        self,
        agent_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Query audit events"""
        conditions = []
        params = []
        param_idx = 1

        if agent_id:
            conditions.append(f"agent_id = ${param_idx}")
            params.append(agent_id)
            param_idx += 1

        if event_type:
            conditions.append(f"event_type = ${param_idx}")
            params.append(event_type.value)
            param_idx += 1

        if start_time:
            conditions.append(f"created_at >= ${param_idx}")
            params.append(start_time)
            param_idx += 1

        if end_time:
            conditions.append(f"created_at <= ${param_idx}")
            params.append(end_time)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        rows = await self.conn.fetch(f"""
            SELECT * FROM audit_events
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx}
        """, *params, limit)

        events = []
        for row in rows:
            events.append(AuditEvent(
                event_id=row['event_id'],
                event_type=AuditEventType(row['event_type']),
                agent_id=row['agent_id'],
                details=json.loads(row['details']),
                timestamp=row['created_at'],
                metadata=json.loads(row['metadata'] or '{}')
            ))

        logger.info(f"Queried {len(events)} audit events")
        return events


async def main():
    """Example usage"""
    # Rate limiter
    rate_limiter = RateLimiter(RateLimitConfig(requests_per_minute=10))

    for i in range(15):
        allowed = rate_limiter.check_limit("test_agent")
        print(f"Request {i+1}: {'ALLOWED' if allowed else 'BLOCKED'}")

    quota = rate_limiter.get_remaining_quota("test_agent")
    print(f"\nRemaining quota: {quota}")

    # Budget manager
    budget_mgr = BudgetManager()
    await budget_mgr.connect()

    budget = CostBudget(
        budget_id=str(uuid4()),
        agent_id="test_agent",
        daily_budget_usd=10.0,
        monthly_budget_usd=200.0
    )
    await budget_mgr.set_budget(budget)

    allowed = await budget_mgr.check_budget("test_agent", 0.05)
    print(f"\nBudget check: {'ALLOWED' if allowed else 'BLOCKED'}")

    await budget_mgr.record_cost("test_agent", 0.05, 3333)

    summary = await budget_mgr.get_budget_summary("test_agent")
    print(f"Budget summary: {json.dumps(summary, indent=2)}")

    await budget_mgr.close()

    # Circuit breaker
    circuit_mgr = CircuitBreakerManager()
    circuit_mgr.register_service("external_api")

    for i in range(7):
        if circuit_mgr.can_execute("external_api"):
            # Simulate failure
            circuit_mgr.record_failure("external_api")
            print(f"Attempt {i+1}: FAILED")
        else:
            print(f"Attempt {i+1}: CIRCUIT OPEN (rejected)")

    status = circuit_mgr.get_status("external_api")
    print(f"\nCircuit status: {json.dumps(status, indent=2, default=str)}")

    # Audit logger
    audit_logger = AuditLogger()
    await audit_logger.connect()

    event = AuditEvent(
        event_id=str(uuid4()),
        event_type=AuditEventType.TASK_SUBMISSION,
        agent_id="test_agent",
        details={"task_id": "task_123", "query": "Test query"},
        metadata={"ip_address": "127.0.0.1"}
    )
    await audit_logger.log_event(event)

    events = await audit_logger.query_events(agent_id="test_agent", limit=5)
    print(f"\nAudit events: {len(events)} logged")

    await audit_logger.close()


if __name__ == "__main__":
    asyncio.run(main())
