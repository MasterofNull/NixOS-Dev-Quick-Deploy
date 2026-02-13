#!/usr/bin/env python3
"""
P4-ORCH-001: Hybrid Coordinator Client
Enables other services to invoke Hybrid Coordinator
"""

import asyncio
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class CircuitState:
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and requests are blocked."""
    pass


class AIDBClientCircuitBreaker:
    """
    Circuit Breaker Pattern Implementation for AIDB calls

    Prevents cascading failures by temporarily blocking requests to failing services.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,  # seconds
        reset_timeout: float = 30.0,  # seconds
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.reset_timeout = reset_timeout

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """Execute a function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info("AIDB circuit breaker transitioning to HALF_OPEN for reset attempt")
                else:
                    raise CircuitBreakerOpenError("AIDB circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)

                if self.state == CircuitState.HALF_OPEN:
                    # Success in half-open state means service is recovered
                    self._on_success()
                    logger.info("AIDB circuit breaker reset successful, back to CLOSED state")

                return result

            except Exception as e:
                await self._on_failure()
                raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return (datetime.now().timestamp() - self.last_failure_time) >= self.reset_timeout

    async def _on_failure(self):
        """Handle a failure in the protected service."""
        self.failure_count += 1
        self.last_failure_time = datetime.now().timestamp()

        if self.state == CircuitState.HALF_OPEN:
            # Failure in half-open state means service is still down
            self._trip()
        elif self.failure_count >= self.failure_threshold:
            # Crossed threshold, trip the circuit
            self._trip()

    def _on_success(self):
        """Handle a success in the protected service."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def _trip(self):
        """Trip the circuit breaker to OPEN state."""
        self.state = CircuitState.OPEN
        self.failure_count = 0
        logger.warning(f"AIDB circuit breaker TRIPPED after {self.failure_threshold} failures")

    def reset(self):
        """Manually reset the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None


class HybridClientCircuitBreaker:
    """
    Circuit Breaker Pattern Implementation for Hybrid Coordinator calls

    Prevents cascading failures by temporarily blocking requests to failing services.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        timeout: float = 60.0,  # seconds
        reset_timeout: float = 30.0,  # seconds
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.reset_timeout = reset_timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        """Execute a function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN for reset attempt")
                else:
                    raise CircuitBreakerOpenError("Circuit breaker is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                
                if self.state == CircuitState.HALF_OPEN:
                    # Success in half-open state means service is recovered
                    self._on_success()
                    logger.info("Circuit breaker reset successful, back to CLOSED state")
                
                return result
                
            except Exception as e:
                await self._on_failure()
                raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return (datetime.now().timestamp() - self.last_failure_time) >= self.reset_timeout

    async def _on_failure(self):
        """Handle a failure in the protected service."""
        self.failure_count += 1
        self.last_failure_time = datetime.now().timestamp()

        if self.state == CircuitState.HALF_OPEN:
            # Failure in half-open state means service is still down
            self._trip()
        elif self.failure_count >= self.failure_threshold:
            # Crossed threshold, trip the circuit
            self._trip()

    def _on_success(self):
        """Handle a success in the protected service."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def _trip(self):
        """Trip the circuit breaker to OPEN state."""
        self.state = CircuitState.OPEN
        self.failure_count = 0
        logger.warning(f"Circuit breaker TRIPPED after {self.failure_threshold} failures")

    def reset(self):
        """Manually reset the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None


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
        timeout: float = 30.0,
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: float = 60.0,
        circuit_breaker_reset_timeout: float = 30.0
    ):
        """
        Initialize Hybrid client

        Args:
            base_url: Hybrid coordinator URL
            timeout: Request timeout in seconds
            enable_circuit_breaker: Whether to enable circuit breaker protection
            circuit_breaker_threshold: Number of failures before tripping circuit
            circuit_breaker_timeout: Timeout for circuit breaker in seconds
            circuit_breaker_reset_timeout: Time to wait before attempting reset
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
        
        # Initialize circuit breaker if enabled
        self.enable_circuit_breaker = enable_circuit_breaker
        if enable_circuit_breaker:
            self.circuit_breaker = HybridClientCircuitBreaker(
                failure_threshold=circuit_breaker_threshold,
                timeout=circuit_breaker_timeout,
                reset_timeout=circuit_breaker_reset_timeout
            )

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
        async def _make_request():
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
        
        if self.enable_circuit_breaker:
            return await self.circuit_breaker.call(_make_request)
        else:
            return await _make_request()

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
        async def _make_request():
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
        
        if self.enable_circuit_breaker:
            return await self.circuit_breaker.call(_make_request)
        else:
            return await _make_request()

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
        async def _make_request():
            response = await self._client.get(
                f"{self.base_url}/learning/stats"
            )
            response.raise_for_status()
            return response.json()
        
        if self.enable_circuit_breaker:
            return await self.circuit_breaker.call(_make_request)
        else:
            return await _make_request()

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
        async def _make_request():
            response = await self._client.get(
                f"{self.base_url}/health"
            )
            response.raise_for_status()
            return response.json()
        
        if self.enable_circuit_breaker:
            return await self.circuit_breaker.call(_make_request)
        else:
            return await _make_request()

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
        verify_ssl: bool = False,  # Self-signed cert
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        circuit_breaker_reset_timeout: float = 30.0
    ):
        """
        Initialize AIDB client

        Args:
            base_url: AIDB server URL
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            enable_circuit_breaker: Whether to enable circuit breaker protection
            circuit_breaker_threshold: Number of failures before tripping circuit
            circuit_breaker_timeout: Timeout for circuit breaker in seconds
            circuit_breaker_reset_timeout: Time to wait before attempting reset
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=timeout,
            verify=verify_ssl
        )
        
        # Initialize circuit breaker if enabled
        self.enable_circuit_breaker = enable_circuit_breaker
        if enable_circuit_breaker:
            self.circuit_breaker = HybridClientCircuitBreaker(
                failure_threshold=circuit_breaker_threshold,
                timeout=circuit_breaker_timeout,
                reset_timeout=circuit_breaker_reset_timeout
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
        async def _make_request():
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
        
        if self.enable_circuit_breaker:
            return await self.circuit_breaker.call(_make_request)
        else:
            return await _make_request()

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
        async def _make_request():
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
        
        if self.enable_circuit_breaker:
            return await self.circuit_breaker.call(_make_request)
        else:
            return await _make_request()

    async def health_check(self) -> Dict[str, Any]:
        """
        Check AIDB health

        Returns:
            Health status including all probes
        """
        async def _make_request():
            response = await self._client.get(
                f"{self.base_url}/aidb/health"
            )
            response.raise_for_status()
            return response.json()
        
        if self.enable_circuit_breaker:
            return await self.circuit_breaker.call(_make_request)
        else:
            return await _make_request()

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
        aidb_url: str = "https://localhost:8443",
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: float = 60.0,
        circuit_breaker_reset_timeout: float = 30.0
    ):
        """
        Initialize unified learning client

        Args:
            hybrid_url: Hybrid coordinator URL
            aidb_url: AIDB server URL
            enable_circuit_breaker: Whether to enable circuit breaker protection
            circuit_breaker_threshold: Number of failures before tripping circuit
            circuit_breaker_timeout: Timeout for circuit breaker in seconds
            circuit_breaker_reset_timeout: Time to wait before attempting reset
        """
        # Initialize clients with circuit breaker protection
        self.hybrid = HybridClient(
            hybrid_url,
            enable_circuit_breaker=enable_circuit_breaker,
            circuit_breaker_threshold=circuit_breaker_threshold,
            circuit_breaker_timeout=circuit_breaker_timeout,
            circuit_breaker_reset_timeout=circuit_breaker_reset_timeout
        )
        self.aidb = AIDBClient(
            aidb_url,
            enable_circuit_breaker=enable_circuit_breaker,
            circuit_breaker_threshold=circuit_breaker_threshold,
            circuit_breaker_timeout=circuit_breaker_timeout,
            circuit_breaker_reset_timeout=circuit_breaker_reset_timeout
        )

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
            try:
                return await self.hybrid.submit_feedback(
                    interaction_id=f"{layer}-{event_type}-{datetime.now().timestamp()}",
                    outcome='success',
                    value_score=data.get('value_score', 0.5),
                    metadata=event
                )
            except CircuitBreakerOpenError:
                logger.warning(f"Circuit breaker open for hybrid coordinator, event {event_type} not recorded")
                return {'status': 'circuit_breaker_open', 'layer': layer, 'event_type': event_type}
        elif layer == 'aidb':
            # AIDB handles knowledge-level learning
            try:
                return await self.aidb.store_interaction(
                    prompt=data.get('prompt', ''),
                    response=data.get('response', ''),
                    backend=data.get('backend', 'unknown'),
                    metadata=event
                )
            except CircuitBreakerOpenError:
                logger.warning(f"Circuit breaker open for aidb, event {event_type} not recorded")
                return {'status': 'circuit_breaker_open', 'layer': layer, 'event_type': event_type}
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
        # Gather stats from all layers, handling circuit breaker exceptions
        try:
            hybrid_stats = await self.hybrid.get_learning_stats()
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker open for hybrid coordinator, using default stats")
            hybrid_stats = {
                'total_patterns_learned': 0,
                'patterns_by_type': {},
                'finetuning_dataset_size': 0,
                'backpressure': {},
                'learning_paused': True
            }
        
        try:
            aidb_health = await self.aidb.health_check()
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker open for aidb, using default health")
            aidb_health = {
                'status': 'degraded',
                'version': 'unknown',
                'services': {}
            }

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
        # Check health of all services, handling circuit breaker exceptions
        try:
            hybrid_health = await self.hybrid.health_check()
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker open for hybrid coordinator, marking as unhealthy")
            hybrid_health = {
                'status': 'unhealthy',
                'error': 'circuit_breaker_open'
            }
        
        try:
            aidb_health = await self.aidb.health_check()
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker open for aidb, marking as unhealthy")
            aidb_health = {
                'status': 'unhealthy',
                'error': 'circuit_breaker_open'
            }

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
