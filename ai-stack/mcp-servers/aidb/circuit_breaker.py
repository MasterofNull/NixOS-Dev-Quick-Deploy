#!/usr/bin/env python3
"""
Circuit Breaker Implementation for AIDB → Hybrid Coordinator calls

This module implements a circuit breaker pattern for service-to-service communication
between AIDB and Hybrid Coordinator to prevent cascading failures.
"""

import asyncio
import os
import time
import functools
from enum import Enum
from typing import Any, Callable, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit Breaker Pattern Implementation
    
    Prevents cascading failures by temporarily blocking requests to failing services.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,  # seconds
        reset_timeout: float = 30.0,  # seconds
        failure_predicate: Optional[Callable[[Exception], bool]] = None
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.reset_timeout = reset_timeout
        self.failure_predicate = failure_predicate or (lambda ex: True)
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
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
                    self._on_success()
                    logger.info("Circuit breaker reset successful, back to CLOSED state")
                
                return result
                
            except Exception as e:
                if self.failure_predicate(e):
                    await self._on_failure()
                    raise
                else:
                    # Not a "failure" for circuit breaker purposes
                    if self.state == CircuitState.HALF_OPEN:
                        self._on_success()
                    raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.reset_timeout
    
    async def _on_failure(self):
        """Handle a failure in the protected service."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
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


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and requests are blocked."""
    pass


# Decorator for easy application
def circuit_breaker(**cb_kwargs):
    """Decorator to apply circuit breaker to async functions."""
    circuit_breaker_instance = CircuitBreaker(**cb_kwargs)
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await circuit_breaker_instance.call(func, *args, **kwargs)
        return wrapper
    return decorator


# Example usage for AIDB → Hybrid Coordinator calls
class AIDBHybridClient:
    """Client for AIDB to communicate with Hybrid Coordinator with circuit breaker protection."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        # Circuit breaker with 5 failures in a row, 60s timeout, 30s reset
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60.0,
            reset_timeout=30.0,
            failure_predicate=lambda ex: isinstance(ex, (ConnectionError, TimeoutError, OSError))
        )
    
    @circuit_breaker()
    async def query_hybrid_coordinator(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Query the hybrid coordinator with circuit breaker protection."""
        import aiohttp
        
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/query",
                    json={"query": query, "context": context or {}},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()
                    
                    # Log performance metrics
                    duration = time.time() - start_time
                    logger.info(f"Hybrid coordinator query completed in {duration:.2f}s")
                    
                    return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Hybrid coordinator query failed after {duration:.2f}s: {e}")
            raise


# Example usage
async def example_usage():
    """Example of how to use the circuit breaker."""
    client = AIDBHybridClient(os.getenv("HYBRID_COORDINATOR_URL", ""))
    
    try:
        result = await client.query_hybrid_coordinator("test query")
        print(f"Success: {result}")
    except CircuitBreakerOpenError:
        print("Service is temporarily unavailable (circuit breaker open)")
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
