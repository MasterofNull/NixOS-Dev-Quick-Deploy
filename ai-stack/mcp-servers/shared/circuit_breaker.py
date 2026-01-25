#!/usr/bin/env python3
"""
P2-REL-002: Circuit Breaker Pattern
Prevents cascade failures when external dependencies fail

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests blocked
- HALF_OPEN: Testing if service recovered

Behavior:
- After N failures (default 5), circuit opens
- After timeout (default 30s), enters HALF_OPEN to test
- If test succeeds, closes circuit
- If test fails, reopens circuit
"""

import time
from enum import Enum
from typing import Callable, Any, Optional
from datetime import datetime, timezone
import threading


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit is open"""
    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker OPEN for {service_name}. "
            f"Retry after {retry_after:.1f} seconds"
        )


class CircuitBreaker:
    """
    Circuit breaker for external dependencies

    Usage:
        breaker = CircuitBreaker(
            name="postgresql",
            failure_threshold=5,
            timeout=30.0
        )

        try:
            result = breaker.call(lambda: expensive_operation())
        except CircuitBreakerError as e:
            # Circuit is open, service unavailable
            log.error("service_unavailable", service=e.service_name)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: float = 30.0,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker

        Args:
            name: Service name (for logging)
            failure_threshold: Failures before opening circuit
            timeout: Seconds before trying again
            success_threshold: Successes needed to close from HALF_OPEN
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.timeout:
                        self._state = CircuitState.HALF_OPEN
                        self._success_count = 0

            return self._state

    @property
    def is_available(self) -> bool:
        """Check if requests can pass through"""
        return self.state != CircuitState.OPEN

    @property
    def stats(self) -> dict:
        """Get circuit breaker statistics"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": (
                    datetime.fromtimestamp(self._last_failure_time, tz=timezone.utc).isoformat()
                    if self._last_failure_time else None
                )
            }

    def call(self, func: Callable[[], Any]) -> Any:
        """
        Execute function through circuit breaker

        Args:
            func: Function to execute

        Returns:
            Result of function call

        Raises:
            CircuitBreakerError: If circuit is OPEN
            Exception: Original exception from func
        """
        current_state = self.state

        # Block requests if circuit is OPEN
        if current_state == CircuitState.OPEN:
            retry_after = self.timeout - (time.time() - (self._last_failure_time or 0))
            raise CircuitBreakerError(self.name, max(0, retry_after))

        # Try to execute the function
        try:
            result = func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1

                # Close circuit if enough successes
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Test failed, reopen circuit
                self._state = CircuitState.OPEN
                self._success_count = 0

            elif self._state == CircuitState.CLOSED:
                # Open circuit if threshold exceeded
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN

    def reset(self):
        """Manually reset circuit to CLOSED (for testing/admin)"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers

    Usage:
        registry = CircuitBreakerRegistry()

        # Get or create breaker
        postgres_breaker = registry.get("postgresql")

        # Use breaker
        result = postgres_breaker.call(lambda: db.query(...))

        # Check all breaker states
        for stats in registry.get_all_stats():
            print(f"{stats['name']}: {stats['state']}")
    """

    def __init__(self, default_config: Optional[dict] = None):
        """
        Initialize registry

        Args:
            default_config: Default config for new breakers
                {
                    'failure_threshold': 5,
                    'timeout': 30.0,
                    'success_threshold': 2
                }
        """
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self._default_config = default_config or {
            'failure_threshold': 5,
            'timeout': 30.0,
            'success_threshold': 2
        }

    def get(self, name: str) -> CircuitBreaker:
        """Get or create circuit breaker by name"""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    **self._default_config
                )
            return self._breakers[name]

    def get_all_stats(self) -> list[dict]:
        """Get stats for all circuit breakers"""
        with self._lock:
            return [breaker.stats for breaker in self._breakers.values()]

    def reset_all(self):
        """Reset all circuit breakers (for testing)"""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
