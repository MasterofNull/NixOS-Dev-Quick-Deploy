#!/usr/bin/env python3
"""
Retry with Exponential Backoff Implementation for AI Stack Services

Implements robust retry mechanisms with exponential backoff for all external service calls.
"""

import asyncio
import os
import time
import random
from typing import Any, Callable, Optional, Type, Union, List
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,  # seconds
        max_delay: float = 60.0,  # seconds
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retry_exceptions: Optional[List[Type[Exception]]] = None,
        exclude_exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retry_exceptions = retry_exceptions or [Exception]
        self.exclude_exceptions = exclude_exceptions or []


async def retry_with_backoff(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs
) -> Any:
    """
    Execute a function with retry and exponential backoff
    
    Args:
        func: The function to execute
        config: Retry configuration
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        Result of the function call
    
    Raises:
        The last exception raised by the function if all retries fail
    """
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            last_exception = e
            
            # Check if this exception should be retried
            should_retry = False
            for exc_type in config.retry_exceptions:
                if isinstance(e, exc_type):
                    should_retry = True
                    break
            
            # Check if this exception should be excluded from retry
            for exc_type in config.exclude_exceptions:
                if isinstance(e, exc_type):
                    should_retry = False
                    break
            
            if not should_retry or attempt == config.max_attempts - 1:
                # Don't retry or this is the last attempt
                raise e
            
            # Calculate delay with exponential backoff
            delay = min(
                config.base_delay * (config.backoff_factor ** attempt),
                config.max_delay
            )
            
            # Add jitter if enabled
            if config.jitter:
                delay *= (0.5 + random.random() * 0.5)  # Random factor between 0.5 and 1.5
            
            logger.warning(
                f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
    
    # This shouldn't happen, but just in case
    raise last_exception


def retryable(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Optional[List[Type[Exception]]] = None,
    exclude_exceptions: Optional[List[Type[Exception]]] = None
):
    """
    Decorator to make a function retryable with exponential backoff
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor,
                jitter=jitter,
                retry_exceptions=retry_exceptions,
                exclude_exceptions=exclude_exceptions
            )
            return await retry_with_backoff(func, config, *args, **kwargs)
        return wrapper
    return decorator


class CircuitBreakerRetryHandler:
    """
    Handler that combines circuit breaker and retry logic
    """
    def __init__(self, circuit_breaker_registry):
        self.circuit_breaker_registry = circuit_breaker_registry
    
    async def call_with_circuit_and_retry(
        self,
        service_name: str,
        func: Callable,
        retry_config: RetryConfig,
        *args,
        **kwargs
    ) -> Any:
        """
        Call a function with both circuit breaker and retry protection
        """
        # Get the circuit breaker for this service
        circuit_breaker = self.circuit_breaker_registry.get(service_name)
        
        # Wrap the function with circuit breaker protection
        async def protected_func(*f_args, **f_kwargs):
            return await circuit_breaker.call(func, *f_args, **f_kwargs)
        
        # Execute with retry logic
        return await retry_with_backoff(protected_func, retry_config, *args, **kwargs)


# Specific retry configurations for different services
class RetryPresets:
    """Common retry configurations for different service types"""
    
    # For database operations
    DATABASE = RetryConfig(
        max_attempts=5,
        base_delay=0.5,
        max_delay=30.0,
        retry_exceptions=[Exception],  # Customize based on your DB driver
        exclude_exceptions=[]
    )
    
    # For external API calls
    EXTERNAL_API = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=60.0,
        retry_exceptions=[ConnectionError, TimeoutError, OSError],
        exclude_exceptions=[]
    )
    
    # For internal service calls
    INTERNAL_SERVICE = RetryConfig(
        max_attempts=3,
        base_delay=0.5,
        max_delay=10.0,
        retry_exceptions=[ConnectionError, TimeoutError, OSError],
        exclude_exceptions=[]
    )
    
    # For Qdrant operations
    QDRANT = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        retry_exceptions=[ConnectionError, TimeoutError, OSError],
        exclude_exceptions=[]
    )


# Example usage classes for different services
class AIDBRetryClient:
    """Client for AIDB with retry and circuit breaker protection"""
    
    def __init__(self, circuit_breaker_registry):
        self.circuit_breaker_registry = circuit_breaker_registry
        self.retry_handler = CircuitBreakerRetryHandler(circuit_breaker_registry)
        self.aidb_url = (os.getenv("AIDB_URL") or "").rstrip("/")
        if not self.aidb_url:
            raise ValueError("AIDB_URL must be set for AIDBRetryClient")
    
    @retryable(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def query_with_retry(self, query: str, context: dict = None):
        """Query AIDB with retry protection"""
        import aiohttp
        
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.aidb_url}/query",
                    json={"query": query, "context": context or {}},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()
                    
                    duration = time.time() - start_time
                    logger.info(f"AIDB query completed in {duration:.2f}s")
                    
                    return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"AIDB query failed after {duration:.2f}s: {e}")
            raise
    
    async def query_with_circuit_and_retry(self, query: str, context: dict = None):
        """Query AIDB with both circuit breaker and retry protection"""
        async def query_func(q, ctx):
            return await self.query_with_retry(q, ctx)
        
        return await self.retry_handler.call_with_circuit_and_retry(
            "aidb",
            query_func,
            RetryPresets.INTERNAL_SERVICE,
            query,
            context
        )


class HybridCoordinatorRetryClient:
    """Client for Hybrid Coordinator with retry and circuit breaker protection"""
    
    def __init__(self, circuit_breaker_registry):
        self.circuit_breaker_registry = circuit_breaker_registry
        self.retry_handler = CircuitBreakerRetryHandler(circuit_breaker_registry)
        self.hybrid_url = (os.getenv("HYBRID_COORDINATOR_URL") or "").rstrip("/")
        if not self.hybrid_url:
            raise ValueError("HYBRID_COORDINATOR_URL must be set for HybridCoordinatorRetryClient")
    
    @retryable(max_attempts=3, base_delay=1.0, max_delay=15.0)
    async def call_skill_with_retry(self, skill: str, params: dict):
        """Call a skill with retry protection"""
        import aiohttp
        
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.hybrid_url}/skills/{skill}",
                    json=params,
                    timeout=aiohttp.ClientTimeout(total=45)
                ) as response:
                    result = await response.json()
                    
                    duration = time.time() - start_time
                    logger.info(f"Hybrid skill {skill} completed in {duration:.2f}s")
                    
                    return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Hybrid skill {skill} failed after {duration:.2f}s: {e}")
            raise
    
    async def call_skill_with_circuit_and_retry(self, skill: str, params: dict):
        """Call a skill with both circuit breaker and retry protection"""
        async def skill_func(s, p):
            return await self.call_skill_with_retry(s, p)
        
        return await self.retry_handler.call_with_circuit_and_retry(
            "hybrid-coordinator",
            skill_func,
            RetryPresets.INTERNAL_SERVICE,
            skill,
            params
        )


class RalphWiggumRetryClient:
    """Client for Ralph Wiggum with retry and circuit breaker protection"""
    
    def __init__(self, circuit_breaker_registry):
        self.circuit_breaker_registry = circuit_breaker_registry
        self.retry_handler = CircuitBreakerRetryHandler(circuit_breaker_registry)
    
    @retryable(max_attempts=3, base_delay=2.0, max_delay=30.0)
    async def submit_task_with_retry(self, task: str, context: dict):
        """Submit a task with retry protection"""
        import aiohttp
        
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                ralph_url = os.getenv("RALPH_WIGGUM_URL", "http://localhost:8004")
                async with session.post(
                    f"{ralph_url}/tasks",
                    json={"task": task, "context": context},
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    result = await response.json()
                    
                    duration = time.time() - start_time
                    logger.info(f"Ralph task submitted in {duration:.2f}s")
                    
                    return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Ralph task submission failed after {duration:.2f}s: {e}")
            raise
    
    async def submit_task_with_circuit_and_retry(self, task: str, context: dict):
        """Submit a task with both circuit breaker and retry protection"""
        async def task_func(t, ctx):
            return await self.submit_task_with_retry(t, ctx)
        
        return await self.retry_handler.call_with_circuit_and_retry(
            "ralph-wiggum",
            task_func,
            RetryPresets.INTERNAL_SERVICE,
            task,
            context
        )


# Example usage
async def example_usage():
    """Example of how to use the retry and circuit breaker system"""
    # This would normally come from your DI container or be instantiated elsewhere
    from .circuit_breaker import CircuitBreakerRegistry
    
    registry = CircuitBreakerRegistry({
        'failure_threshold': 3,
        'timeout': 60.0,
        'reset_timeout': 30.0
    })
    
    # Create clients with retry and circuit breaker protection
    aidb_client = AIDBRetryClient(registry)
    hybrid_client = HybridCoordinatorRetryClient(registry)
    ralph_client = RalphWiggumRetryClient(registry)
    
    try:
        # These calls will have both retry and circuit breaker protection
        result = await aidb_client.query_with_circuit_and_retry("test query")
        print(f"AIDB Success: {result}")
        
        result = await hybrid_client.call_skill_with_circuit_and_retry("route_search", {"query": "test"})
        print(f"Hybrid Success: {result}")
        
        result = await ralph_client.submit_task_with_circuit_and_retry("optimize_loop", {"iterations": 5})
        print(f"Ralph Success: {result}")
        
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage())
