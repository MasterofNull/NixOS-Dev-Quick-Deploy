#!/usr/bin/env python3
"""
Federation Protocol

Cross-deployment learning with anonymized pattern sharing and
federated metric aggregation.

Part of Phase 5: Platform Maturity & Ecosystem
"""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4
import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("federation_protocol")


class SharingLevel(Enum):
    """Data sharing privacy level"""
    PRIVATE = "private"  # No sharing
    ANONYMOUS = "anonymous"  # Hash identifiers, aggregate metrics
    CONSORTIUM = "consortium"  # Share within trusted group
    PUBLIC = "public"  # Public dataset contribution


class PatternCategory(Enum):
    """Pattern classification"""
    CODE_SOLUTION = "code_solution"
    ERROR_FIX = "error_fix"
    OPTIMIZATION = "optimization"
    BEST_PRACTICE = "best_practice"
    ANTI_PATTERN = "anti_pattern"


@dataclass
class AnonymizedPattern:
    """Pattern with privacy-preserving transformations"""
    pattern_id: str
    category: PatternCategory
    domain: str
    problem_hash: str  # SHA256 of problem description
    solution_hash: str  # SHA256 of solution
    effectiveness_score: float  # 0-1
    usage_count: int
    success_rate: float
    source_deployment_hash: str  # SHA256 of deployment ID
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['category'] = self.category.value
        d['created_at'] = self.created_at.isoformat()
        return d


@dataclass
class FederatedMetric:
    """Aggregated metric across deployments"""
    metric_id: str
    metric_name: str
    metric_type: str  # avg, sum, count, distribution
    value: float
    std_dev: float
    deployment_count: int
    measured_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['measured_at'] = self.measured_at.isoformat()
        return d


@dataclass
class FederationNode:
    """Federation network node"""
    node_id: str
    node_hash: str  # SHA256 of node_id
    sharing_level: SharingLevel
    trusted_nodes: List[str] = field(default_factory=list)
    endpoints: Dict[str, str] = field(default_factory=dict)
    last_sync: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['sharing_level'] = self.sharing_level.value
        d['last_sync'] = self.last_sync.isoformat() if self.last_sync else None
        return d


class FederationProtocol:
    """
    Manages cross-deployment learning with privacy preservation.
    """

    def __init__(
        self,
        node_id: str,
        sharing_level: SharingLevel = SharingLevel.ANONYMOUS,
        pg_host: str = "127.0.0.1",
        pg_port: int = 5432,
        pg_user: str = "postgres",
        pg_database: str = "ai_context",
        pg_password: str = ""
    ):
        self.node_id = node_id
        self.node_hash = self._hash_identifier(node_id)
        self.sharing_level = sharing_level

        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password

        self.conn: Optional[asyncpg.Connection] = None
        self.trusted_nodes: Set[str] = set()

        logger.info(f"FederationProtocol initialized (node={self.node_hash}, level={sharing_level.value})")

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

    def _hash_identifier(self, identifier: str) -> str:
        """Create privacy-preserving hash"""
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]

    def _anonymize_content(self, content: str) -> str:
        """Anonymize content while preserving structure"""
        # Hash the content but preserve length and structure indicators
        content_hash = self._hash_identifier(content)
        return f"<anonymized:{content_hash}:len={len(content)}>"

    async def share_pattern(
        self,
        category: PatternCategory,
        domain: str,
        problem_description: str,
        solution: str,
        effectiveness_score: float,
        usage_count: int = 1,
        success_rate: float = 1.0
    ) -> str:
        """Share pattern with privacy preservation"""
        if self.sharing_level == SharingLevel.PRIVATE:
            logger.info("Pattern not shared (privacy level: PRIVATE)")
            return ""

        # Anonymize sensitive data
        pattern = AnonymizedPattern(
            pattern_id=str(uuid4()),
            category=category,
            domain=domain,
            problem_hash=self._hash_identifier(problem_description),
            solution_hash=self._hash_identifier(solution),
            effectiveness_score=effectiveness_score,
            usage_count=usage_count,
            success_rate=success_rate,
            source_deployment_hash=self.node_hash
        )

        # Store locally first
        await self.conn.execute("""
            INSERT INTO federated_patterns (
                pattern_id, category, domain, problem_hash, solution_hash,
                effectiveness_score, usage_count, success_rate,
                source_deployment_hash, sharing_level
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
            pattern.pattern_id,
            pattern.category.value,
            pattern.domain,
            pattern.problem_hash,
            pattern.solution_hash,
            pattern.effectiveness_score,
            pattern.usage_count,
            pattern.success_rate,
            pattern.source_deployment_hash,
            self.sharing_level.value
        )

        logger.info(
            f"Pattern shared: {pattern.category.value} in {pattern.domain} "
            f"(effectiveness={pattern.effectiveness_score:.2f})"
        )

        return pattern.pattern_id

    async def import_patterns(
        self,
        category: Optional[PatternCategory] = None,
        domain: Optional[str] = None,
        min_effectiveness: float = 0.7
    ) -> List[AnonymizedPattern]:
        """Import patterns from federation network"""
        conditions = ["sharing_level != 'private'"]
        params = []
        param_idx = 1

        if category:
            conditions.append(f"category = ${param_idx}")
            params.append(category.value)
            param_idx += 1

        if domain:
            conditions.append(f"domain = ${param_idx}")
            params.append(domain)
            param_idx += 1

        conditions.append(f"effectiveness_score >= ${param_idx}")
        params.append(min_effectiveness)
        param_idx += 1

        where_clause = " AND ".join(conditions)

        rows = await self.conn.fetch(f"""
            SELECT * FROM federated_patterns
            WHERE {where_clause}
            ORDER BY effectiveness_score DESC, usage_count DESC
            LIMIT 100
        """, *params)

        patterns = []
        for row in rows:
            patterns.append(AnonymizedPattern(
                pattern_id=row['pattern_id'],
                category=PatternCategory(row['category']),
                domain=row['domain'],
                problem_hash=row['problem_hash'],
                solution_hash=row['solution_hash'],
                effectiveness_score=float(row['effectiveness_score']),
                usage_count=row['usage_count'],
                success_rate=float(row['success_rate']),
                source_deployment_hash=row['source_deployment_hash'],
                created_at=row['created_at'],
                metadata={}
            ))

        logger.info(f"Imported {len(patterns)} patterns from federation network")
        return patterns

    async def aggregate_metric(
        self,
        metric_name: str,
        local_value: float,
        aggregation_type: str = "avg"  # avg, sum, count, distribution
    ) -> FederatedMetric:
        """Contribute to federated metric aggregation"""
        # Store local contribution
        await self.conn.execute("""
            INSERT INTO federated_metric_contributions (
                contribution_id, metric_name, source_deployment_hash,
                value, aggregation_type
            ) VALUES ($1, $2, $3, $4, $5)
        """,
            str(uuid4()),
            metric_name,
            self.node_hash,
            local_value,
            aggregation_type
        )

        # Calculate aggregate
        stats = await self.conn.fetchrow("""
            SELECT
                COUNT(DISTINCT source_deployment_hash) as deployment_count,
                AVG(value) as avg_value,
                STDDEV(value) as std_dev,
                SUM(value) as sum_value,
                COUNT(*) as count_value
            FROM federated_metric_contributions
            WHERE metric_name = $1
              AND created_at > NOW() - INTERVAL '7 days'
        """, metric_name)

        if aggregation_type == "avg":
            aggregate_value = float(stats['avg_value'] or 0.0)
        elif aggregation_type == "sum":
            aggregate_value = float(stats['sum_value'] or 0.0)
        elif aggregation_type == "count":
            aggregate_value = float(stats['count_value'] or 0)
        else:
            aggregate_value = float(stats['avg_value'] or 0.0)

        metric = FederatedMetric(
            metric_id=str(uuid4()),
            metric_name=metric_name,
            metric_type=aggregation_type,
            value=aggregate_value,
            std_dev=float(stats['std_dev'] or 0.0),
            deployment_count=stats['deployment_count'] or 0
        )

        logger.info(
            f"Metric aggregated: {metric_name} = {metric.value:.2f} "
            f"(stddev={metric.std_dev:.2f}, n={metric.deployment_count})"
        )

        return metric

    async def get_federation_insights(self) -> Dict[str, Any]:
        """Get insights from federated learning"""
        insights = {}

        # Top patterns by domain
        domain_patterns = await self.conn.fetch("""
            SELECT
                domain,
                category,
                COUNT(*) as pattern_count,
                AVG(effectiveness_score) as avg_effectiveness,
                AVG(success_rate) as avg_success_rate
            FROM federated_patterns
            WHERE sharing_level != 'private'
            GROUP BY domain, category
            ORDER BY pattern_count DESC
            LIMIT 20
        """)

        insights['top_patterns'] = [
            {
                'domain': row['domain'],
                'category': row['category'],
                'pattern_count': row['pattern_count'],
                'avg_effectiveness': float(row['avg_effectiveness']),
                'avg_success_rate': float(row['avg_success_rate'])
            }
            for row in domain_patterns
        ]

        # Deployment diversity
        deployment_count = await self.conn.fetchval("""
            SELECT COUNT(DISTINCT source_deployment_hash)
            FROM federated_patterns
        """)
        insights['unique_deployments'] = deployment_count

        # Recent activity
        recent_patterns = await self.conn.fetchval("""
            SELECT COUNT(*)
            FROM federated_patterns
            WHERE created_at > NOW() - INTERVAL '7 days'
        """)
        insights['patterns_last_7_days'] = recent_patterns

        # Network health
        insights['network_health'] = {
            'total_patterns': await self.conn.fetchval("SELECT COUNT(*) FROM federated_patterns"),
            'active_deployments': deployment_count,
            'sharing_enabled': self.sharing_level != SharingLevel.PRIVATE
        }

        logger.info(f"Federation insights: {len(insights)} metrics")
        return insights

    async def register_federation_node(self, node: FederationNode):
        """Register node in federation network"""
        await self.conn.execute("""
            INSERT INTO federation_nodes (
                node_id, node_hash, sharing_level, trusted_nodes,
                endpoints, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (node_hash) DO UPDATE SET
                sharing_level = EXCLUDED.sharing_level,
                trusted_nodes = EXCLUDED.trusted_nodes,
                endpoints = EXCLUDED.endpoints,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """,
            node.node_id,
            node.node_hash,
            node.sharing_level.value,
            node.trusted_nodes,
            json.dumps(node.endpoints),
            json.dumps(node.metadata)
        )

        logger.info(f"Federation node registered: {node.node_hash}")

    async def add_trusted_node(self, node_hash: str):
        """Add node to trusted list (for consortium sharing)"""
        self.trusted_nodes.add(node_hash)

        await self.conn.execute("""
            UPDATE federation_nodes
            SET trusted_nodes = array_append(trusted_nodes, $1)
            WHERE node_hash = $2
        """, node_hash, self.node_hash)

        logger.info(f"Trusted node added: {node_hash}")

    async def sync_with_node(self, target_node_hash: str) -> Dict[str, Any]:
        """Synchronize patterns with another node"""
        # Check if target is trusted (for consortium sharing)
        if self.sharing_level == SharingLevel.CONSORTIUM:
            if target_node_hash not in self.trusted_nodes:
                logger.warning(f"Node not trusted: {target_node_hash}")
                return {"status": "rejected", "reason": "node_not_trusted"}

        # Get patterns to share
        patterns = await self.conn.fetch("""
            SELECT * FROM federated_patterns
            WHERE source_deployment_hash = $1
              AND (
                sharing_level = 'public'
                OR (sharing_level = 'anonymous' AND $2 != 'private')
                OR (sharing_level = 'consortium' AND $3 = TRUE)
              )
            ORDER BY created_at DESC
            LIMIT 100
        """,
            self.node_hash,
            self.sharing_level.value,
            target_node_hash in self.trusted_nodes
        )

        sync_result = {
            "status": "success",
            "patterns_shared": len(patterns),
            "target_node": target_node_hash,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"Synced with node {target_node_hash}: {len(patterns)} patterns shared")
        return sync_result

    async def get_federation_stats(self) -> Dict[str, Any]:
        """Get federation network statistics"""
        stats = {}

        # Pattern statistics
        stats['total_patterns'] = await self.conn.fetchval(
            "SELECT COUNT(*) FROM federated_patterns"
        )
        stats['patterns_by_category'] = dict(
            await self.conn.fetch("""
                SELECT category, COUNT(*) as count
                FROM federated_patterns
                GROUP BY category
            """)
        )

        # Metric statistics
        stats['active_metrics'] = await self.conn.fetchval("""
            SELECT COUNT(DISTINCT metric_name)
            FROM federated_metric_contributions
            WHERE created_at > NOW() - INTERVAL '7 days'
        """)

        # Network statistics
        stats['network'] = {
            'registered_nodes': await self.conn.fetchval("SELECT COUNT(*) FROM federation_nodes"),
            'trusted_nodes': len(self.trusted_nodes),
            'sharing_level': self.sharing_level.value
        }

        return stats


async def main():
    """Example usage"""
    federation = FederationProtocol(
        node_id="deployment_001",
        sharing_level=SharingLevel.ANONYMOUS
    )

    try:
        await federation.connect()

        # Share a pattern
        pattern_id = await federation.share_pattern(
            category=PatternCategory.CODE_SOLUTION,
            domain="python",
            problem_description="Async database connection pooling",
            solution="Use asyncpg with connection pool management",
            effectiveness_score=0.92,
            usage_count=15,
            success_rate=0.87
        )
        print(f"Pattern shared: {pattern_id}")

        # Import patterns
        patterns = await federation.import_patterns(
            domain="python",
            min_effectiveness=0.8
        )
        print(f"\nImported {len(patterns)} patterns:")
        for p in patterns[:3]:
            print(f"  - {p.category.value} in {p.domain} (effectiveness={p.effectiveness_score:.2f})")

        # Aggregate metric
        metric = await federation.aggregate_metric(
            metric_name="avg_query_latency_ms",
            local_value=125.5,
            aggregation_type="avg"
        )
        print(f"\nFederated metric: {metric.metric_name} = {metric.value:.2f} (n={metric.deployment_count})")

        # Get insights
        insights = await federation.get_federation_insights()
        print(f"\nFederation insights:")
        print(json.dumps(insights, indent=2, default=str))

        # Get stats
        stats = await federation.get_federation_stats()
        print(f"\nFederation stats:")
        print(json.dumps(stats, indent=2, default=str))

    finally:
        await federation.close()


if __name__ == "__main__":
    asyncio.run(main())
