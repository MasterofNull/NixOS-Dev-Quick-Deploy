#!/usr/bin/env python3
"""
Comprehensive Quality System Health Validator

Validates all quality intelligence features are working:
- RAG reflection loop
- Generator-critic pattern
- Quality cache
- Quality monitoring
- Auto-improvement
- All metrics tracking

Run after deployments to ensure quality system integrity.
"""

import sys
import requests
import json
from pathlib import Path

# Configuration
API_KEY = "Model1"
BASE_URL = "http://localhost:8003"
HEADERS = {"X-API-Key": API_KEY}


def test_status_endpoint():
    """Test /status endpoint is accessible and returns quality stats."""
    print("Testing /status endpoint...")

    try:
        response = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=5)
        response.raise_for_status()
        data = response.json()

        # Check all quality features are present
        required_keys = [
            "rag_reflection_stats",
            "generator_critic_stats",
            "quality_cache_stats",
            "quality_health",
            "quality_monitor",
            "auto_quality_improvement",
        ]

        missing = [key for key in required_keys if key not in data]
        if missing:
            print(f"✗ Missing keys in /status: {missing}")
            return False

        print("✓ All quality features present in /status")
        return True

    except Exception as e:
        print(f"✗ Failed to access /status: {e}")
        return False


def test_rag_reflection_stats():
    """Test RAG reflection stats are structured correctly."""
    print("\nTesting RAG reflection stats...")

    try:
        response = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=5)
        data = response.json()
        stats = data.get("rag_reflection_stats", {})

        required_fields = [
            "total_retrievals",
            "retries_triggered",
            "retry_rate",
            "avg_initial_confidence",
            "avg_final_confidence",
            "active",
        ]

        missing = [f for f in required_fields if f not in stats]
        if missing:
            print(f"✗ Missing reflection fields: {missing}")
            return False

        if stats.get("active") is not True:
            print("✗ Reflection not active")
            return False

        print(f"✓ Reflection stats valid (active={stats['active']})")
        return True

    except Exception as e:
        print(f"✗ Reflection stats error: {e}")
        return False


def test_critic_stats():
    """Test generator-critic stats are structured correctly."""
    print("\nTesting generator-critic stats...")

    try:
        response = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=5)
        data = response.json()
        stats = data.get("generator_critic_stats", {})

        required_fields = [
            "total_evaluations",
            "interventions_triggered",
            "intervention_rate",
            "avg_quality_score",
            "active",
        ]

        missing = [f for f in required_fields if f not in stats]
        if missing:
            print(f"✗ Missing critic fields: {missing}")
            return False

        if stats.get("active") is not True:
            print("✗ Critic not active")
            return False

        print(f"✓ Critic stats valid (active={stats['active']})")
        return True

    except Exception as e:
        print(f"✗ Critic stats error: {e}")
        return False


def test_cache_stats():
    """Test quality cache stats are structured correctly."""
    print("\nTesting quality cache stats...")

    try:
        response = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=5)
        data = response.json()
        stats = data.get("quality_cache_stats", {})

        required_fields = [
            "total_queries",
            "cache_hits",
            "cache_misses",
            "hit_rate",
            "cache_size",
            "cache_max_size",
            "active",
        ]

        missing = [f for f in required_fields if f not in stats]
        if missing:
            print(f"✗ Missing cache fields: {missing}")
            return False

        if stats.get("active") is not True:
            print("✗ Cache not active")
            return False

        if stats.get("cache_max_size") != 1000:
            print(f"✗ Cache max size incorrect: {stats.get('cache_max_size')}")
            return False

        print(f"✓ Cache stats valid (size={stats['cache_size']}/{stats['cache_max_size']})")
        return True

    except Exception as e:
        print(f"✗ Cache stats error: {e}")
        return False


def test_quality_health():
    """Test quality health monitoring."""
    print("\nTesting quality health monitoring...")

    try:
        response = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=5)
        data = response.json()
        health = data.get("quality_health", {})

        required_fields = [
            "health_score",
            "status",
            "active_alerts",
            "alert_count",
        ]

        missing = [f for f in required_fields if f not in health]
        if missing:
            print(f"✗ Missing health fields: {missing}")
            return False

        score = health.get("health_score", 0)
        status = health.get("status", "unknown")

        if not (0 <= score <= 100):
            print(f"✗ Health score out of range: {score}")
            return False

        if status not in ["healthy", "degraded", "critical"]:
            print(f"✗ Invalid health status: {status}")
            return False

        print(f"✓ Health monitoring valid (score={score}, status={status})")
        return True

    except Exception as e:
        print(f"✗ Health monitoring error: {e}")
        return False


def test_quality_monitor():
    """Test quality monitor stats."""
    print("\nTesting quality monitor...")

    try:
        response = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=5)
        data = response.json()
        monitor = data.get("quality_monitor", {})

        required_fields = [
            "check_count",
            "recent_alerts",
            "alert_counts",
            "active",
        ]

        missing = [f for f in required_fields if f not in monitor]
        if missing:
            print(f"✗ Missing monitor fields: {missing}")
            return False

        if monitor.get("active") is not True:
            print("✗ Monitor not active")
            return False

        checks = monitor.get("check_count", 0)
        print(f"✓ Monitor valid (checks={checks}, active={monitor['active']})")
        return True

    except Exception as e:
        print(f"✗ Monitor error: {e}")
        return False


def test_auto_improvement():
    """Test auto quality improvement stats."""
    print("\nTesting auto quality improvement...")

    try:
        response = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=5)
        data = response.json()
        auto_improve = data.get("auto_quality_improvement", {})

        required_fields = [
            "total_responses",
            "improvement_triggered",
            "trigger_rate",
            "success_rate",
            "active",
        ]

        missing = [f for f in required_fields if f not in auto_improve]
        if missing:
            print(f"✗ Missing auto-improvement fields: {missing}")
            return False

        if auto_improve.get("active") is not True:
            print("✗ Auto-improvement not active")
            return False

        print(f"✓ Auto-improvement valid (active={auto_improve['active']})")
        return True

    except Exception as e:
        print(f"✗ Auto-improvement error: {e}")
        return False


def test_service_health():
    """Test service is running and healthy."""
    print("\nTesting service health...")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "healthy":
            print(f"✗ Service not healthy: {data.get('status')}")
            return False

        print(f"✓ Service healthy")
        return True

    except Exception as e:
        print(f"✗ Service health check failed: {e}")
        return False


def run_all_tests():
    """Run all quality system health tests."""
    print("=" * 60)
    print("Quality System Health Validation")
    print("=" * 60)

    tests = [
        ("Service Health", test_service_health),
        ("Status Endpoint", test_status_endpoint),
        ("RAG Reflection", test_rag_reflection_stats),
        ("Generator-Critic", test_critic_stats),
        ("Quality Cache", test_cache_stats),
        ("Quality Health", test_quality_health),
        ("Quality Monitor", test_quality_monitor),
        ("Auto-Improvement", test_auto_improvement),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8s} {name}")

    print("=" * 60)
    print(f"Result: {passed}/{total} tests passed")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
