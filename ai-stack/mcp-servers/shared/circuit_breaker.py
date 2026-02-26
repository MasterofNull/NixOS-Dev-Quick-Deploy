#!/usr/bin/env python3
"""
Shared Circuit Breaker Implementation for AI Stack Services

This module implements a comprehensive circuit breaker pattern for service-to-service 
communication within the AI stack to prevent cascading failures.
"""

import asyncio
import os
import time
import functools
from enum import Enum
from typing import Any, Callable, Optional, Dict, Type
import logging
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    timeout: float = 60.0  # seconds
    reset_timeout: float = 30.0  # seconds
    failure_predicate: Optional[Callable[[Exception], bool]] = None
    success_threshold: int = 2  # Number of successes to close circuit in HALF_OPEN state


class CircuitBreaker:
    """
    Circuit Breaker Pattern Implementation

    Prevents cascading failures by temporarily blocking requests to failing services.
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
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
                    await self._on_success()
                    logger.info("Circuit breaker reset successful, back to CLOSED state")

                return result

            except Exception as e:
                if self._is_failure(e):
                    await self._on_failure()
                    raise
                else:
                    # Not a "failure" for circuit breaker purposes
                    if self.state == CircuitState.HALF_OPEN:
                        await self._on_success()
                    raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.config.reset_timeout

    def _is_failure(self, exception: Exception) -> bool:
        """Determine if an exception should be counted as a failure."""
        if self.config.failure_predicate:
            return self.config.failure_predicate(exception)
        # Default: treat all exceptions as failures
        return True

    async def _on_failure(self):
        """Handle a failure in the protected service."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failure in half-open state means service is still down
            await self._trip()
        elif self.failure_count >= self.config.failure_threshold:
            # Crossed threshold, trip the circuit
            await self._trip()

    async def _on_success(self):
        """Handle a success in the protected service."""
        self.success_count += 1
        if self.state == CircuitState.HALF_OPEN:
            # If we have enough successes in HALF_OPEN, close the circuit
            if self.success_count >= self.config.success_threshold:
                await self._close()
            else:
                # Stay in HALF_OPEN until we reach success threshold
                pass
        else:
            # In CLOSED state, just reset counters
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None

    async def _trip(self):
        """Trip the circuit breaker to OPEN state."""
        self.state = CircuitState.OPEN
        self.failure_count = 0
        self.success_count = 0
        logger.warning(f"Circuit breaker TRIPPED after {self.config.failure_threshold} failures")

    async def _close(self):
        """Close the circuit breaker from HALF_OPEN state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

    def get_state_info(self) -> Dict[str, Any]:
        """Get current state information for monitoring."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "should_reset": self._should_attempt_reset()
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and requests are blocked."""
    pass


class CircuitBreakerError(Exception):
    """Compatibility error for callers expecting a service/timeout payload."""

    def __init__(self, service: str, retry_after: Optional[float] = None):
        self.service = service
        self.retry_after = retry_after
        message = f"Circuit breaker open for {service}"
        if retry_after is not None:
            message = f"{message} (retry_after={retry_after})"
        super().__init__(message)


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers by service name.
    """
    
    def __init__(self, default_config: Optional[Dict] = None):
        self.default_config = default_config or {}
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._config_overrides: Dict[str, Dict] = {}
        
    def set_override_config(self, service_name: str, config: Dict):
        """Set specific configuration for a service."""
        self._config_overrides[service_name] = config
        
    def get(self, service_name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        if service_name not in self._breakers:
            # Merge default config with service-specific overrides
            config_dict = self.default_config.copy()
            config_dict.update(self._config_overrides.get(service_name, {}))
            
            config = CircuitBreakerConfig(**config_dict)
            self._breakers[service_name] = CircuitBreaker(config)
            
        return self._breakers[service_name]
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state information for all registered circuit breakers."""
        return {
            name: breaker.get_state_info()
            for name, breaker in self._breakers.items()
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Backward-compatible alias for state snapshots."""
        return self.get_all_states()


# Decorator for easy application
def circuit_breaker(service_name: str, **cb_kwargs):
    """Decorator to apply circuit breaker to async functions."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get or create circuit breaker for this service
            registry = getattr(wrapper, '_circuit_breaker_registry', CircuitBreakerRegistry())
            circuit_breaker_instance = registry.get(service_name)
            
            # Store registry for reuse
            wrapper._circuit_breaker_registry = registry
            
            return await circuit_breaker_instance.call(func, *args, **kwargs)
        return wrapper
    return decorator


# Example usage for various AI stack services
class AIDBCircuitBreakerClient:
    """Client for AIDB with circuit breaker protection."""

    def __init__(self, base_url: str, circuit_breaker_registry: CircuitBreakerRegistry):
        self.base_url = base_url
        self.circuit_breaker_registry = circuit_breaker_registry

    async def call_query_endpoint(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call AIDB query endpoint with circuit breaker protection."""
        import aiohttp

        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/query",
                    json={"query": query, "context": context or {}},
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    result = await response.json()

                    # Log performance metrics
                    duration = time.time() - start_time
                    logger.info(f"AIDB query completed in {duration:.2f}s")

                    return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"AIDB query failed after {duration:.2f}s: {e}")
            raise


class HybridCoordinatorCircuitBreakerClient:
    """Client for Hybrid Coordinator with circuit breaker protection."""

    def __init__(self, base_url: str, circuit_breaker_registry: CircuitBreakerRegistry):
        self.base_url = base_url
        self.circuit_breaker_registry = circuit_breaker_registry

    async def call_skill_endpoint(self, skill: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call Hybrid Coordinator skill endpoint with circuit breaker protection."""
        import aiohttp

        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/skills/{skill}",
                    json=params,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    result = await response.json()

                    # Log performance metrics
                    duration = time.time() - start_time
                    logger.info(f"Hybrid skill {skill} completed in {duration:.2f}s")

                    return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Hybrid skill {skill} failed after {duration:.2f}s: {e}")
            raise


class RalphWiggumCircuitBreakerClient:
    """Client for Ralph Wiggum with circuit breaker protection."""

    def __init__(self, base_url: str, circuit_breaker_registry: CircuitBreakerRegistry):
        self.base_url = base_url
        self.circuit_breaker_registry = circuit_breaker_registry

    async def call_task_endpoint(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Call Ralph Wiggum task endpoint with circuit breaker protection."""
        import aiohttp

        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/tasks",
                    json={"task": task, "context": context},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()

                    # Log performance metrics
                    duration = time.time() - start_time
                    logger.info(f"Ralph task completed in {duration:.2f}s")

                    return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Ralph task failed after {duration:.2f}s: {e}")
            raise


# Example usage
async def example_usage():
    """Example of how to use the circuit breaker registry."""
    # Create a registry with default configuration
    registry = CircuitBreakerRegistry({
        'failure_threshold': 3,
        'timeout': 60.0,
        'reset_timeout': 30.0
    })
    
    # Override specific service configuration
    registry.set_override_config('qdrant', {
        'failure_threshold': 5,
        'reset_timeout': 60.0
    })
    
    # Create clients with circuit breaker protection
    aidb_client = AIDBCircuitBreakerClient(os.getenv("AIDB_URL", ""), registry)
    hybrid_client = HybridCoordinatorCircuitBreakerClient(os.getenv("HYBRID_COORDINATOR_URL", ""), registry)
    ralph_client = RalphWiggumCircuitBreakerClient(os.getenv("RALPH_URL", ""), registry)

    try:
        # These calls will be protected by circuit breakers
        result = await aidb_client.call_query_endpoint("test query")
        print(f"AIDB Success: {result}")
        
        result = await hybrid_client.call_skill_endpoint("route_search", {"query": "test"})
        print(f"Hybrid Success: {result}")
        
        result = await ralph_client.call_task_endpoint("optimize_loop", {"iterations": 5})
        print(f"Ralph Success: {result}")
        
        # Print circuit breaker states
        print("Circuit breaker states:", registry.get_all_states())
        
    except CircuitBreakerOpenError:
        print("Service is temporarily unavailable (circuit breaker open)")
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
