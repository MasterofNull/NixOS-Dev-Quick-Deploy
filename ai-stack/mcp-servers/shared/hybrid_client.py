#!/usr/bin/env python3
"""
P4-ORCH-001: Hybrid Coordinator Client
Enables other services to invoke Hybrid Coordinator
"""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


class HybridClient:
    """
    Client for Hybrid Coordinator MCP Server

    Enables nested orchestration: Other services → Hybrid → AIDB

    Usage:
        client = HybridClient("http://localhost:8092")

        # Route a query
        response = await client.route_query(
            prompt="What is NixOS?",
            prefer_local=True
        )

        # Submit learning feedback
        await client.submit_feedback(
            interaction_id="abc123",
            outcome="success",
            value_score=0.9
        )
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8092",
        timeout: float = 30.0
    ):
        """
        Initialize Hybrid client

        Args:
            base_url: Hybrid coordinator URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def route_query(
        self,
        prompt: str,
        prefer_local: bool = True,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route a query through Hybrid coordinator

        Args:
            prompt: Query text
            prefer_local: Whether to prefer local LLM
            context: Additional context

        Returns:
            {
                'response': str,
                'backend': 'local' | 'remote',
                'model': str,
                'latency_ms': int
            }
        """
        payload = {
            'prompt': prompt,
            'prefer_local': prefer_local,
            'context': context or {}
        }

        response = await self._client.post(
            f"{self.base_url}/query",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def submit_feedback(
        self,
        interaction_id: str,
        outcome: str,
        value_score: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Submit feedback for a query interaction

        Args:
            interaction_id: Unique interaction ID
            outcome: 'success' | 'failure' | 'partial'
            value_score: 0.0 to 1.0
            metadata: Additional metadata

        Returns:
            {'status': 'recorded', 'timestamp': '...'}
        """
        payload = {
            'interaction_id': interaction_id,
            'outcome': outcome,
            'value_score': value_score,
            'metadata': metadata or {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        response = await self._client.post(
            f"{self.base_url}/feedback",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_learning_stats(self) -> Dict[str, Any]:
        """
        Get continuous learning statistics

        Returns:
            {
                'total_patterns_learned': int,
                'patterns_by_type': dict,
                'finetuning_dataset_size': int,
                'backpressure': dict,
                'learning_paused': bool
            }
        """
        response = await self._client.get(
            f"{self.base_url}/learning/stats"
        )
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Hybrid coordinator health

        Returns:
            {
                'status': 'healthy' | 'degraded',
                'version': str,
                'services': dict
            }
        """
        response = await self._client.get(
            f"{self.base_url}/health"
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


class AIDBClient:
    """
    Client for AIDB MCP Server

    Enables nested orchestration: Hybrid → AIDB

    Usage:
        client = AIDBClient("https://localhost:8443")

        # Vector search
        results = await client.vector_search(
            query="NixOS configuration",
            collection="documents",
            limit=5
        )

        # Store interaction
        await client.store_interaction(
            prompt="What is NixOS?",
            response="NixOS is...",
            backend="local"
        )
    """

    def __init__(
        self,
        base_url: str = "https://localhost:8443",
        timeout: float = 30.0,
        verify_ssl: bool = False  # Self-signed cert
    ):
        """
        Initialize AIDB client

        Args:
            base_url: AIDB server URL
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=timeout,
            verify=verify_ssl
        )

    async def vector_search(
        self,
        query: str,
        collection: str = "documents",
        limit: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search

        Args:
            query: Search query
            collection: Collection name
            limit: Max results
            score_threshold: Minimum similarity score

        Returns:
            List of matching documents with scores
        """
        payload = {
            'query': query,
            'collection': collection,
            'limit': limit,
            'score_threshold': score_threshold
        }

        response = await self._client.post(
            f"{self.base_url}/aidb/search",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def store_interaction(
        self,
        prompt: str,
        response: str,
        backend: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Store an interaction for learning

        Args:
            prompt: User prompt
            response: System response
            backend: 'local' | 'remote'
            metadata: Additional metadata

        Returns:
            {'status': 'stored', 'id': '...'}
        """
        payload = {
            'prompt': prompt,
            'response': response,
            'backend': backend,
            'metadata': metadata or {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        response = await self._client.post(
            f"{self.base_url}/aidb/interactions",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> Dict[str, Any]:
        """
        Check AIDB health

        Returns:
            Health status including all probes
        """
        response = await self._client.get(
            f"{self.base_url}/aidb/health"
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


class UnifiedLearningClient:
    """
    P4-ORCH-001: Unified learning client for nested orchestration

    Coordinates learning across all layers:
    - Ralph Wiggum: Task-level learning
    - Hybrid: Query routing and pattern learning
    - AIDB: Knowledge base updates

    Usage:
        learning = UnifiedLearningClient()

        # Submit learning event from any layer
        await learning.submit_event(
            layer="hybrid",
            event_type="routing_decision",
            data={
                'decision': 'local',
                'confidence': 0.95,
                'latency_ms': 150
            }
        )

        # Get unified statistics
        stats = await learning.get_statistics()
    """

    def __init__(
        self,
        hybrid_url: str = "http://localhost:8092",
        aidb_url: str = "https://localhost:8443"
    ):
        """
        Initialize unified learning client

        Args:
            hybrid_url: Hybrid coordinator URL
            aidb_url: AIDB server URL
        """
        self.hybrid = HybridClient(hybrid_url)
        self.aidb = AIDBClient(aidb_url)

    async def submit_event(
        self,
        layer: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Submit learning event from any orchestration layer

        Args:
            layer: 'ralph' | 'hybrid' | 'aidb'
            event_type: Event type
            data: Event data

        Returns:
            {'status': 'recorded', 'layer': '...'}
        """
        event = {
            'layer': layer,
            'event_type': event_type,
            'data': data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Route to appropriate service
        if layer in ('ralph', 'hybrid'):
            # Hybrid handles orchestration-level learning
            return await self.hybrid.submit_feedback(
                interaction_id=f"{layer}-{event_type}-{datetime.now().timestamp()}",
                outcome='success',
                value_score=data.get('value_score', 0.5),
                metadata=event
            )
        elif layer == 'aidb':
            # AIDB handles knowledge-level learning
            return await self.aidb.store_interaction(
                prompt=data.get('prompt', ''),
                response=data.get('response', ''),
                backend=data.get('backend', 'unknown'),
                metadata=event
            )
        else:
            raise ValueError(f"Unknown layer: {layer}")

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get unified learning statistics across all layers

        Returns:
            {
                'hybrid': {...},
                'aidb': {...},
                'total_events': int
            }
        """
        # Gather stats from all layers
        hybrid_stats = await self.hybrid.get_learning_stats()
        aidb_health = await self.aidb.health_check()

        return {
            'hybrid': hybrid_stats,
            'aidb': aidb_health,
            'total_events': hybrid_stats.get('total_patterns_learned', 0),
            'unified': True
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of entire orchestration stack

        Returns:
            Health status for all layers
        """
        hybrid_health = await self.hybrid.health_check()
        aidb_health = await self.aidb.health_check()

        all_healthy = (
            hybrid_health.get('status') == 'healthy' and
            aidb_health.get('status') == 'healthy'
        )

        return {
            'status': 'healthy' if all_healthy else 'degraded',
            'layers': {
                'hybrid': hybrid_health,
                'aidb': aidb_health
            }
        }

    async def close(self):
        """Close all clients"""
        await self.hybrid.close()
        await self.aidb.close()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
