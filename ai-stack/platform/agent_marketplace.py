#!/usr/bin/env python3
"""
Agent Marketplace

Registry of available agents with capability tracking, performance
benchmarks, and cost/quality tradeoff analysis.

Part of Phase 5: Platform Maturity & Ecosystem
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4
import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_marketplace")


class AgentTier(Enum):
    """Agent pricing tier"""
    FREE = "free"
    COMMUNITY = "community"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class AgentStatus(Enum):
    """Agent availability status"""
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"
    BETA = "beta"


@dataclass
class AgentCapability:
    """Individual agent capability"""
    capability_id: str
    name: str
    description: str
    proficiency_score: float  # 0-1
    examples: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceBenchmark:
    """Performance metrics for an agent"""
    benchmark_id: str
    agent_id: str
    task_domain: str
    success_rate: float  # 0-1
    avg_quality_score: float  # 0-1
    avg_latency_ms: int
    avg_tokens_used: int
    avg_cost_usd: float
    sample_size: int
    measured_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['measured_at'] = self.measured_at.isoformat()
        return d


@dataclass
class CostQualityProfile:
    """Cost vs quality tradeoff profile"""
    profile_id: str
    agent_id: str
    task_domain: str
    cost_per_task_usd: float
    quality_score: float  # 0-1
    speed_score: float  # 0-1, higher is faster
    reliability_score: float  # 0-1
    value_score: float  # Computed: quality / cost
    recommended_for: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentListing:
    """Agent marketplace listing"""
    agent_id: str
    name: str
    provider: str
    tier: AgentTier
    status: AgentStatus
    description: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    supported_domains: List[str] = field(default_factory=list)
    pricing: Dict[str, Any] = field(default_factory=dict)
    performance_benchmarks: List[PerformanceBenchmark] = field(default_factory=list)
    cost_quality_profiles: List[CostQualityProfile] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['tier'] = self.tier.value
        d['status'] = self.status.value
        d['capabilities'] = [c.to_dict() for c in self.capabilities]
        d['performance_benchmarks'] = [b.to_dict() for b in self.performance_benchmarks]
        d['cost_quality_profiles'] = [p.to_dict() for p in self.cost_quality_profiles]
        d['created_at'] = self.created_at.isoformat()
        d['updated_at'] = self.updated_at.isoformat()
        return d


class AgentMarketplace:
    """
    Marketplace for discovering and managing agent integrations.
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
        self.agent_cache: Dict[str, AgentListing] = {}
        self.cache_ttl: int = 300  # 5 minutes

        logger.info("AgentMarketplace initialized")

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
            logger.info("Database connection closed")

    async def register_agent(self, listing: AgentListing) -> str:
        """Register new agent in marketplace"""
        await self.conn.execute("""
            INSERT INTO agent_marketplace (
                agent_id, name, provider, tier, status, description,
                capabilities, supported_domains, pricing, tags, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (agent_id) DO UPDATE SET
                name = EXCLUDED.name,
                provider = EXCLUDED.provider,
                tier = EXCLUDED.tier,
                status = EXCLUDED.status,
                description = EXCLUDED.description,
                capabilities = EXCLUDED.capabilities,
                supported_domains = EXCLUDED.supported_domains,
                pricing = EXCLUDED.pricing,
                tags = EXCLUDED.tags,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """,
            listing.agent_id,
            listing.name,
            listing.provider,
            listing.tier.value,
            listing.status.value,
            listing.description,
            json.dumps([c.to_dict() for c in listing.capabilities]),
            listing.supported_domains,
            json.dumps(listing.pricing),
            listing.tags,
            json.dumps(listing.metadata)
        )

        # Invalidate cache
        if listing.agent_id in self.agent_cache:
            del self.agent_cache[listing.agent_id]

        logger.info(f"Agent registered: {listing.agent_id} ({listing.name})")
        return listing.agent_id

    async def record_benchmark(self, benchmark: PerformanceBenchmark):
        """Record performance benchmark"""
        await self.conn.execute("""
            INSERT INTO agent_performance_benchmarks (
                benchmark_id, agent_id, task_domain, success_rate,
                avg_quality_score, avg_latency_ms, avg_tokens_used,
                avg_cost_usd, sample_size
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
            benchmark.benchmark_id,
            benchmark.agent_id,
            benchmark.task_domain,
            benchmark.success_rate,
            benchmark.avg_quality_score,
            benchmark.avg_latency_ms,
            benchmark.avg_tokens_used,
            benchmark.avg_cost_usd,
            benchmark.sample_size
        )

        logger.info(
            f"Benchmark recorded: {benchmark.agent_id} in {benchmark.task_domain} "
            f"(success={benchmark.success_rate:.2%})"
        )

    async def update_cost_quality_profile(self, profile: CostQualityProfile):
        """Update cost/quality tradeoff profile"""
        await self.conn.execute("""
            INSERT INTO agent_cost_quality_profiles (
                profile_id, agent_id, task_domain, cost_per_task_usd,
                quality_score, speed_score, reliability_score, value_score,
                recommended_for
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (agent_id, task_domain) DO UPDATE SET
                cost_per_task_usd = EXCLUDED.cost_per_task_usd,
                quality_score = EXCLUDED.quality_score,
                speed_score = EXCLUDED.speed_score,
                reliability_score = EXCLUDED.reliability_score,
                value_score = EXCLUDED.value_score,
                recommended_for = EXCLUDED.recommended_for,
                updated_at = NOW()
        """,
            profile.profile_id,
            profile.agent_id,
            profile.task_domain,
            profile.cost_per_task_usd,
            profile.quality_score,
            profile.speed_score,
            profile.reliability_score,
            profile.value_score,
            profile.recommended_for
        )

        logger.info(
            f"Cost/quality profile updated: {profile.agent_id} in {profile.task_domain} "
            f"(value={profile.value_score:.2f})"
        )

    async def search_agents(
        self,
        query: Optional[str] = None,
        domains: Optional[List[str]] = None,
        tier: Optional[AgentTier] = None,
        status: Optional[AgentStatus] = None,
        min_quality_score: float = 0.0,
        max_cost_usd: Optional[float] = None,
        limit: int = 20
    ) -> List[AgentListing]:
        """Search marketplace for agents"""
        conditions = ["status = 'active'"]
        params = []
        param_idx = 1

        if query:
            conditions.append(f"(name ILIKE ${param_idx} OR description ILIKE ${param_idx})")
            params.append(f"%{query}%")
            param_idx += 1

        if tier:
            conditions.append(f"tier = ${param_idx}")
            params.append(tier.value)
            param_idx += 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        rows = await self.conn.fetch(f"""
            SELECT * FROM agent_marketplace
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT ${param_idx}
        """, *params, limit)

        agents = []
        for row in rows:
            # Load capabilities
            capabilities = []
            for cap_data in json.loads(row['capabilities'] or '[]'):
                capabilities.append(AgentCapability(**cap_data))

            # Load benchmarks
            benchmarks = await self._get_benchmarks(row['agent_id'])

            # Load cost/quality profiles
            profiles = await self._get_cost_quality_profiles(row['agent_id'])

            # Filter by quality and cost if specified
            if min_quality_score > 0.0 or max_cost_usd is not None:
                if not profiles:
                    continue

                meets_criteria = False
                for profile in profiles:
                    if profile.quality_score >= min_quality_score:
                        if max_cost_usd is None or profile.cost_per_task_usd <= max_cost_usd:
                            meets_criteria = True
                            break

                if not meets_criteria:
                    continue

            agent = AgentListing(
                agent_id=row['agent_id'],
                name=row['name'],
                provider=row['provider'],
                tier=AgentTier(row['tier']),
                status=AgentStatus(row['status']),
                description=row['description'],
                capabilities=capabilities,
                supported_domains=row['supported_domains'] or [],
                pricing=json.loads(row['pricing'] or '{}'),
                performance_benchmarks=benchmarks,
                cost_quality_profiles=profiles,
                tags=row['tags'] or [],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                metadata=json.loads(row['metadata'] or '{}')
            )

            agents.append(agent)

        logger.info(f"Found {len(agents)} agents matching search criteria")
        return agents

    async def get_agent(self, agent_id: str) -> Optional[AgentListing]:
        """Get agent by ID"""
        # Check cache
        if agent_id in self.agent_cache:
            cached = self.agent_cache[agent_id]
            if (datetime.now() - cached.updated_at).total_seconds() < self.cache_ttl:
                return cached

        row = await self.conn.fetchrow("""
            SELECT * FROM agent_marketplace WHERE agent_id = $1
        """, agent_id)

        if not row:
            return None

        # Load capabilities
        capabilities = []
        for cap_data in json.loads(row['capabilities'] or '[]'):
            capabilities.append(AgentCapability(**cap_data))

        # Load benchmarks
        benchmarks = await self._get_benchmarks(agent_id)

        # Load cost/quality profiles
        profiles = await self._get_cost_quality_profiles(agent_id)

        agent = AgentListing(
            agent_id=row['agent_id'],
            name=row['name'],
            provider=row['provider'],
            tier=AgentTier(row['tier']),
            status=AgentStatus(row['status']),
            description=row['description'],
            capabilities=capabilities,
            supported_domains=row['supported_domains'] or [],
            pricing=json.loads(row['pricing'] or '{}'),
            performance_benchmarks=benchmarks,
            cost_quality_profiles=profiles,
            tags=row['tags'] or [],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            metadata=json.loads(row['metadata'] or '{}')
        )

        # Update cache
        self.agent_cache[agent_id] = agent

        return agent

    async def recommend_agent_for_task(
        self,
        task_domain: str,
        priority: str = "balanced"  # quality, cost, speed, balanced
    ) -> Optional[Tuple[AgentListing, float]]:
        """Recommend best agent for a task domain"""
        # Get all agents with profiles for this domain
        rows = await self.conn.fetch("""
            SELECT
                m.agent_id,
                m.name,
                p.cost_per_task_usd,
                p.quality_score,
                p.speed_score,
                p.reliability_score,
                p.value_score
            FROM agent_marketplace m
            JOIN agent_cost_quality_profiles p ON m.agent_id = p.agent_id
            WHERE m.status = 'active'
              AND p.task_domain = $1
            ORDER BY
                CASE
                    WHEN $2 = 'quality' THEN p.quality_score
                    WHEN $2 = 'cost' THEN 1.0 - (p.cost_per_task_usd / NULLIF((SELECT MAX(cost_per_task_usd) FROM agent_cost_quality_profiles WHERE task_domain = $1), 0))
                    WHEN $2 = 'speed' THEN p.speed_score
                    ELSE p.value_score
                END DESC
            LIMIT 1
        """, task_domain, priority)

        if not rows:
            logger.warning(f"No agents found for task domain: {task_domain}")
            return None

        row = rows[0]
        agent = await self.get_agent(row['agent_id'])

        if not agent:
            return None

        # Calculate recommendation score based on priority
        if priority == "quality":
            score = row['quality_score']
        elif priority == "cost":
            max_cost = await self.conn.fetchval(
                "SELECT MAX(cost_per_task_usd) FROM agent_cost_quality_profiles WHERE task_domain = $1",
                task_domain
            )
            score = 1.0 - (row['cost_per_task_usd'] / max_cost) if max_cost > 0 else 0.0
        elif priority == "speed":
            score = row['speed_score']
        else:  # balanced
            score = row['value_score']

        logger.info(
            f"Recommended agent for {task_domain} (priority={priority}): "
            f"{agent.name} (score={score:.2f})"
        )

        return (agent, score)

    async def get_marketplace_stats(self) -> Dict[str, Any]:
        """Get marketplace statistics"""
        stats = {}

        # Agent counts by tier
        tier_counts = await self.conn.fetch("""
            SELECT tier, COUNT(*) as count
            FROM agent_marketplace
            GROUP BY tier
        """)
        stats['agents_by_tier'] = {row['tier']: row['count'] for row in tier_counts}

        # Agent counts by status
        status_counts = await self.conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM agent_marketplace
            GROUP BY status
        """)
        stats['agents_by_status'] = {row['status']: row['count'] for row in status_counts}

        # Top domains
        domain_counts = defaultdict(int)
        rows = await self.conn.fetch("SELECT supported_domains FROM agent_marketplace")
        for row in rows:
            for domain in row['supported_domains'] or []:
                domain_counts[domain] += 1
        stats['top_domains'] = dict(sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10])

        # Performance averages by domain
        domain_perf = await self.conn.fetch("""
            SELECT
                task_domain,
                AVG(success_rate) as avg_success_rate,
                AVG(avg_quality_score) as avg_quality,
                AVG(avg_latency_ms) as avg_latency,
                AVG(avg_cost_usd) as avg_cost
            FROM agent_performance_benchmarks
            GROUP BY task_domain
            ORDER BY task_domain
        """)
        stats['domain_performance'] = {
            row['task_domain']: {
                'success_rate': float(row['avg_success_rate']),
                'quality': float(row['avg_quality']),
                'latency_ms': int(row['avg_latency']),
                'cost_usd': float(row['avg_cost'])
            }
            for row in domain_perf
        }

        logger.info(f"Marketplace stats: {len(stats)} metrics")
        return stats

    async def _get_benchmarks(self, agent_id: str) -> List[PerformanceBenchmark]:
        """Get performance benchmarks for agent"""
        rows = await self.conn.fetch("""
            SELECT * FROM agent_performance_benchmarks
            WHERE agent_id = $1
            ORDER BY measured_at DESC
            LIMIT 10
        """, agent_id)

        benchmarks = []
        for row in rows:
            benchmarks.append(PerformanceBenchmark(
                benchmark_id=row['benchmark_id'],
                agent_id=row['agent_id'],
                task_domain=row['task_domain'],
                success_rate=float(row['success_rate']),
                avg_quality_score=float(row['avg_quality_score']),
                avg_latency_ms=row['avg_latency_ms'],
                avg_tokens_used=row['avg_tokens_used'],
                avg_cost_usd=float(row['avg_cost_usd']),
                sample_size=row['sample_size'],
                measured_at=row['measured_at']
            ))

        return benchmarks

    async def _get_cost_quality_profiles(self, agent_id: str) -> List[CostQualityProfile]:
        """Get cost/quality profiles for agent"""
        rows = await self.conn.fetch("""
            SELECT * FROM agent_cost_quality_profiles
            WHERE agent_id = $1
            ORDER BY updated_at DESC
        """, agent_id)

        profiles = []
        for row in rows:
            profiles.append(CostQualityProfile(
                profile_id=row['profile_id'],
                agent_id=row['agent_id'],
                task_domain=row['task_domain'],
                cost_per_task_usd=float(row['cost_per_task_usd']),
                quality_score=float(row['quality_score']),
                speed_score=float(row['speed_score']),
                reliability_score=float(row['reliability_score']),
                value_score=float(row['value_score']),
                recommended_for=row['recommended_for'] or []
            ))

        return profiles


async def main():
    """Example usage"""
    marketplace = AgentMarketplace()

    try:
        await marketplace.connect()

        # Register sample agents
        claude_agent = AgentListing(
            agent_id="claude-opus-4",
            name="Claude Opus 4",
            provider="Anthropic",
            tier=AgentTier.PROFESSIONAL,
            status=AgentStatus.ACTIVE,
            description="Advanced reasoning and coding assistant",
            capabilities=[
                AgentCapability(
                    capability_id="cap_reasoning",
                    name="Advanced Reasoning",
                    description="Complex problem solving and analysis",
                    proficiency_score=0.95,
                    examples=["Architecture design", "Algorithm optimization"]
                ),
                AgentCapability(
                    capability_id="cap_coding",
                    name="Code Generation",
                    description="High-quality code implementation",
                    proficiency_score=0.90,
                    examples=["Python", "JavaScript", "Rust"]
                )
            ],
            supported_domains=["architecture", "coding", "analysis", "testing"],
            pricing={"per_million_tokens": 15.00},
            tags=["reasoning", "coding", "premium"]
        )

        await marketplace.register_agent(claude_agent)

        # Record benchmark
        benchmark = PerformanceBenchmark(
            benchmark_id=str(uuid4()),
            agent_id="claude-opus-4",
            task_domain="architecture",
            success_rate=0.92,
            avg_quality_score=0.88,
            avg_latency_ms=3500,
            avg_tokens_used=2500,
            avg_cost_usd=0.0375,
            sample_size=150
        )
        await marketplace.record_benchmark(benchmark)

        # Update cost/quality profile
        profile = CostQualityProfile(
            profile_id=str(uuid4()),
            agent_id="claude-opus-4",
            task_domain="architecture",
            cost_per_task_usd=0.0375,
            quality_score=0.88,
            speed_score=0.75,
            reliability_score=0.92,
            value_score=0.88 / 0.0375,  # 23.47
            recommended_for=["complex_architecture", "high_stakes_design"]
        )
        await marketplace.update_cost_quality_profile(profile)

        # Search agents
        agents = await marketplace.search_agents(
            query="reasoning",
            min_quality_score=0.8,
            limit=5
        )
        print(f"\nFound {len(agents)} agents:")
        for agent in agents:
            print(f"  - {agent.name} ({agent.tier.value})")

        # Get recommendation
        recommendation = await marketplace.recommend_agent_for_task(
            task_domain="architecture",
            priority="quality"
        )
        if recommendation:
            agent, score = recommendation
            print(f"\nRecommended: {agent.name} (score={score:.2f})")

        # Get stats
        stats = await marketplace.get_marketplace_stats()
        print(f"\nMarketplace stats:")
        print(json.dumps(stats, indent=2, default=str))

    finally:
        await marketplace.close()


if __name__ == "__main__":
    asyncio.run(main())
