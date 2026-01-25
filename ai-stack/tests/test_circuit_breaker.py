#!/usr/bin/env python3
"""
P2-REL-002: Circuit Breaker Tests
Tests circuit breaker pattern for preventing cascade failures
"""

import sys
import time
from pathlib import Path

# Add shared modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "shared"))

from circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerError, CircuitBreakerRegistry


def test_circuit_breaker_closed_state():
    """Test normal operation in CLOSED state"""
    print("Testing CLOSED state (normal operation)...")

    breaker = CircuitBreaker(name="test-service", failure_threshold=3, timeout=2.0)

    assert breaker.state == CircuitState.CLOSED, "Should start in CLOSED state"

    # Successful calls should work
    call_count = 0

    def successful_operation():
        nonlocal call_count
        call_count += 1
        return "success"

    for i in range(5):
        result = breaker.call(successful_operation)
        assert result == "success", f"Call {i+1} should succeed"

    assert call_count == 5, "Should have called function 5 times"
    assert breaker.state == CircuitState.CLOSED, "Should remain CLOSED"

    print("✓ CLOSED state works")


def test_circuit_breaker_opens_on_failures():
    """Test circuit opens after threshold failures"""
    print("Testing circuit opens after failures...")

    breaker = CircuitBreaker(name="failing-service", failure_threshold=3, timeout=2.0)

    failure_count = 0

    def failing_operation():
        nonlocal failure_count
        failure_count += 1
        raise ConnectionError("Service unavailable")

    # Cause 3 failures to open circuit
    for i in range(3):
        try:
            breaker.call(failing_operation)
            assert False, f"Call {i+1} should have raised"
        except ConnectionError:
            pass  # Expected

    assert failure_count == 3, "Should have attempted 3 times"
    assert breaker.state == CircuitState.OPEN, "Circuit should be OPEN"

    # Now circuit should fail fast without calling function
    try:
        breaker.call(failing_operation)
        assert False, "Should have raised CircuitBreakerError"
    except CircuitBreakerError as e:
        assert "failing-service" in str(e), "Error should mention service name"
        assert failure_count == 3, "Should NOT have called function (fail fast)"

    print("✓ Circuit opens after threshold failures")


def test_circuit_breaker_half_open_recovery():
    """Test circuit transitions to HALF_OPEN and recovers"""
    print("Testing HALF_OPEN recovery...")

    breaker = CircuitBreaker(name="recovering-service", failure_threshold=2, timeout=1.0, success_threshold=2)

    # Open the circuit
    def failing_operation():
        raise ConnectionError("Service down")

    for _ in range(2):
        try:
            breaker.call(failing_operation)
        except ConnectionError:
            pass

    assert breaker.state == CircuitState.OPEN, "Circuit should be OPEN"

    # Wait for timeout
    print("  Waiting for timeout (1s)...")
    time.sleep(1.1)

    # Circuit should now be HALF_OPEN
    assert breaker.state == CircuitState.HALF_OPEN, "Circuit should be HALF_OPEN"

    # Successful call should close circuit (need success_threshold successes)
    success_count = 0

    def successful_operation():
        nonlocal success_count
        success_count += 1
        return "recovered"

    # First success
    result = breaker.call(successful_operation)
    assert result == "recovered", "Call should succeed"
    assert breaker.state == CircuitState.HALF_OPEN, "Should still be HALF_OPEN (need 2 successes)"

    # Second success should close circuit
    result = breaker.call(successful_operation)
    assert result == "recovered", "Call should succeed"
    assert breaker.state == CircuitState.CLOSED, "Circuit should be CLOSED"
    assert success_count == 2, "Should have called twice"

    print("✓ HALF_OPEN recovery works")


def test_circuit_breaker_reopens_on_half_open_failure():
    """Test circuit reopens if test fails in HALF_OPEN"""
    print("Testing circuit reopens on HALF_OPEN failure...")

    breaker = CircuitBreaker(name="flaky-service", failure_threshold=2, timeout=0.5)

    # Open circuit
    def failing_operation():
        raise TimeoutError("Service timeout")

    for _ in range(2):
        try:
            breaker.call(failing_operation)
        except TimeoutError:
            pass

    assert breaker.state == CircuitState.OPEN, "Circuit should be OPEN"

    # Wait for timeout to enter HALF_OPEN
    time.sleep(0.6)
    assert breaker.state == CircuitState.HALF_OPEN, "Circuit should be HALF_OPEN"

    # Failure in HALF_OPEN should reopen circuit
    try:
        breaker.call(failing_operation)
    except TimeoutError:
        pass

    assert breaker.state == CircuitState.OPEN, "Circuit should reopen on HALF_OPEN failure"

    print("✓ Circuit reopens on HALF_OPEN failure")


def test_circuit_breaker_reset():
    """Test manual circuit reset"""
    print("Testing manual reset...")

    breaker = CircuitBreaker(name="resetable-service", failure_threshold=2, timeout=10.0)

    # Open circuit
    def failing():
        raise ValueError("Error")

    for _ in range(2):
        try:
            breaker.call(failing)
        except ValueError:
            pass

    assert breaker.state == CircuitState.OPEN, "Circuit should be OPEN"

    # Reset circuit
    breaker.reset()
    assert breaker.state == CircuitState.CLOSED, "Circuit should be CLOSED after reset"

    # Should work again
    result = breaker.call(lambda: "working")
    assert result == "working", "Should work after reset"

    print("✓ Manual reset works")


def test_circuit_breaker_registry():
    """Test circuit breaker registry"""
    print("Testing circuit breaker registry...")

    registry = CircuitBreakerRegistry(default_config={
        'failure_threshold': 3,
        'timeout': 1.0,
        'success_threshold': 1
    })

    # Get breakers
    postgres_breaker = registry.get("postgresql")
    redis_breaker = registry.get("redis")
    qdrant_breaker = registry.get("qdrant")

    assert postgres_breaker.name == "postgresql", "Should have correct name"
    assert redis_breaker.name == "redis", "Should have correct name"

    # Getting same breaker should return same instance
    postgres_breaker2 = registry.get("postgresql")
    assert postgres_breaker is postgres_breaker2, "Should return same instance"

    # Get all stats
    stats = registry.get_all_stats()
    assert len(stats) == 3, "Should have 3 breakers"

    service_names = {s['name'] for s in stats}
    assert service_names == {"postgresql", "redis", "qdrant"}, "Should have all services"

    print("✓ Circuit breaker registry works")


def test_circuit_breaker_stats():
    """Test circuit breaker statistics"""
    print("Testing circuit breaker statistics...")

    breaker = CircuitBreaker(name="monitored-service", failure_threshold=2, timeout=1.0)

    # Initial stats
    stats = breaker.stats
    assert stats['name'] == "monitored-service", "Should have correct name"
    assert stats['state'] == CircuitState.CLOSED.value, "Should be CLOSED"
    assert stats['failure_count'] == 0, "Should have no failures"

    # Cause failures
    def failing():
        raise RuntimeError("Fail")

    for _ in range(2):
        try:
            breaker.call(failing)
        except RuntimeError:
            pass

    # Check stats after failures
    stats = breaker.stats
    assert stats['state'] == CircuitState.OPEN.value, "Should be OPEN"
    assert stats['failure_count'] == 2, "Should have 2 failures"
    assert stats['last_failure'] is not None, "Should have last failure time"

    print("✓ Circuit breaker statistics work")


def main():
    """Run all tests"""
    print("=" * 60)
    print("P2-REL-002: Circuit Breaker Tests")
    print("=" * 60)

    tests = [
        test_circuit_breaker_closed_state,
        test_circuit_breaker_opens_on_failures,
        test_circuit_breaker_half_open_recovery,
        test_circuit_breaker_reopens_on_half_open_failure,
        test_circuit_breaker_reset,
        test_circuit_breaker_registry,
        test_circuit_breaker_stats,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1

    print()
    print("=" * 60)
    if failed == 0:
        print(f"✓ ALL TESTS PASSED ({passed}/{len(tests)})")
        print("=" * 60)
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed} passed, {failed} failed)")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
