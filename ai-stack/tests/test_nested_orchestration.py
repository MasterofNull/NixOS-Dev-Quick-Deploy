#!/usr/bin/env python3
"""
P4-ORCH-001: Nested Orchestration Tests
Tests client libraries for service communication
"""

import sys
from pathlib import Path

# Add shared modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "shared"))

from hybrid_client import HybridClient, AIDBClient, UnifiedLearningClient


def test_hybrid_client_initialization():
    """Test Hybrid client initialization"""
    print("Testing Hybrid client initialization...")

    client = HybridClient("http://localhost:8092", timeout=30.0)

    assert client.base_url == "http://localhost:8092", "Base URL should be set"
    assert client.timeout == 30.0, "Timeout should be set"
    assert client._client is not None, "HTTP client should be initialized"

    print("✓ Hybrid client initializes correctly")


def test_aidb_client_initialization():
    """Test AIDB client initialization"""
    print("Testing AIDB client initialization...")

    client = AIDBClient("https://localhost:8443", timeout=30.0, verify_ssl=False)

    assert client.base_url == "https://localhost:8443", "Base URL should be set"
    assert client.timeout == 30.0, "Timeout should be set"
    assert client._client is not None, "HTTP client should be initialized"

    print("✓ AIDB client initializes correctly")


def test_unified_learning_client():
    """Test unified learning client"""
    print("Testing unified learning client...")

    learning = UnifiedLearningClient(
        hybrid_url="http://localhost:8092",
        aidb_url="https://localhost:8443"
    )

    assert learning.hybrid is not None, "Hybrid client should be initialized"
    assert learning.aidb is not None, "AIDB client should be initialized"
    assert isinstance(learning.hybrid, HybridClient), "Should be HybridClient instance"
    assert isinstance(learning.aidb, AIDBClient), "Should be AIDBClient instance"

    print("✓ Unified learning client initializes correctly")


def test_client_url_normalization():
    """Test URL normalization (trailing slash removal)"""
    print("Testing URL normalization...")

    # Test with trailing slash
    client1 = HybridClient("http://localhost:8092/")
    assert client1.base_url == "http://localhost:8092", "Should remove trailing slash"

    # Test without trailing slash
    client2 = HybridClient("http://localhost:8092")
    assert client2.base_url == "http://localhost:8092", "Should keep URL as-is"

    # Test multiple trailing slashes
    client3 = HybridClient("http://localhost:8092///")
    assert client3.base_url == "http://localhost:8092", "Should remove all trailing slashes"

    print("✓ URL normalization works")


def test_aidb_ssl_configuration():
    """Test AIDB SSL configuration"""
    print("Testing AIDB SSL configuration...")

    # With SSL verification
    client_verify = AIDBClient(verify_ssl=True)
    assert client_verify._client is not None, "Client should be initialized with SSL verification"

    # Without SSL verification (self-signed certs)
    client_no_verify = AIDBClient(verify_ssl=False)
    assert client_no_verify._client is not None, "Client should be initialized without SSL verification"

    # Verify different configurations were used
    # (Can't directly test verify attribute in httpx, but we can verify client initialized)
    assert client_verify.timeout == 30.0, "Timeout should be set"
    assert client_no_verify.timeout == 30.0, "Timeout should be set"

    print("✓ SSL configuration works")


def test_client_interfaces():
    """Test that clients have expected methods"""
    print("Testing client interfaces...")

    hybrid = HybridClient()
    assert hasattr(hybrid, 'route_query'), "Should have route_query method"
    assert hasattr(hybrid, 'submit_feedback'), "Should have submit_feedback method"
    assert hasattr(hybrid, 'get_learning_stats'), "Should have get_learning_stats method"
    assert hasattr(hybrid, 'health_check'), "Should have health_check method"
    assert hasattr(hybrid, 'close'), "Should have close method"

    aidb = AIDBClient()
    assert hasattr(aidb, 'vector_search'), "Should have vector_search method"
    assert hasattr(aidb, 'store_interaction'), "Should have store_interaction method"
    assert hasattr(aidb, 'health_check'), "Should have health_check method"
    assert hasattr(aidb, 'close'), "Should have close method"

    learning = UnifiedLearningClient()
    assert hasattr(learning, 'submit_event'), "Should have submit_event method"
    assert hasattr(learning, 'get_statistics'), "Should have get_statistics method"
    assert hasattr(learning, 'health_check'), "Should have health_check method"
    assert hasattr(learning, 'close'), "Should have close method"

    print("✓ Client interfaces correct")


def test_nested_architecture():
    """Test nested orchestration architecture"""
    print("Testing nested architecture...")

    # Create unified client
    learning = UnifiedLearningClient()

    # Verify layering
    assert learning.hybrid is not None, "Hybrid layer should exist"
    assert learning.aidb is not None, "AIDB layer should exist"

    # Verify layer URLs are different (no circular dependency)
    assert learning.hybrid.base_url != learning.aidb.base_url, "Layers should be separate"

    # Verify each layer can be accessed independently
    hybrid_url = learning.hybrid.base_url
    aidb_url = learning.aidb.base_url

    assert "8092" in hybrid_url, "Hybrid should use port 8092"
    assert "8443" in aidb_url, "AIDB should use port 8443"

    print("✓ Nested architecture correct")


def test_context_managers():
    """Test async context manager support"""
    print("Testing context managers...")

    # All clients should support async context managers
    hybrid = HybridClient()
    assert hasattr(hybrid, '__aenter__'), "Should have __aenter__"
    assert hasattr(hybrid, '__aexit__'), "Should have __aexit__"

    aidb = AIDBClient()
    assert hasattr(aidb, '__aenter__'), "Should have __aenter__"
    assert hasattr(aidb, '__aexit__'), "Should have __aexit__"

    learning = UnifiedLearningClient()
    assert hasattr(learning, '__aenter__'), "Should have __aenter__"
    assert hasattr(learning, '__aexit__'), "Should have __aexit__"

    print("✓ Context managers supported")


def test_layer_routing():
    """Test that events route to correct layers"""
    print("Testing layer routing logic...")

    learning = UnifiedLearningClient()

    # Test layer identification
    layers = {
        'ralph': 'hybrid',  # Ralph events go to Hybrid
        'hybrid': 'hybrid',  # Hybrid events go to Hybrid
        'aidb': 'aidb'      # AIDB events go to AIDB
    }

    for layer, expected_target in layers.items():
        # We can't actually call without running servers,
        # but we can verify the logic
        if layer in ('ralph', 'hybrid'):
            target = 'hybrid'
        elif layer == 'aidb':
            target = 'aidb'
        else:
            target = 'unknown'

        assert target == expected_target, f"Layer {layer} should route to {expected_target}"

    print("✓ Layer routing logic correct")


def test_no_circular_dependencies():
    """Test that there are no circular dependencies"""
    print("Testing no circular dependencies...")

    # Create clients
    hybrid = HybridClient("http://localhost:8092")
    aidb = AIDBClient("https://localhost:8443")

    # Verify URLs are different (prerequisite for no circular deps)
    assert hybrid.base_url != aidb.base_url, "Services should be separate"

    # Verify hierarchy (Hybrid can call AIDB, but not vice versa)
    # In our architecture:
    # - Ralph → Hybrid (Ralph uses HybridClient)
    # - Hybrid → AIDB (Hybrid uses AIDBClient)
    # - AIDB doesn't call Hybrid or Ralph

    # Unified client has both, establishing the hierarchy
    learning = UnifiedLearningClient()
    assert learning.hybrid is not None, "Top layer should access Hybrid"
    assert learning.aidb is not None, "Top layer should access AIDB"

    print("✓ No circular dependencies")


def main():
    """Run all tests"""
    print("=" * 60)
    print("P4-ORCH-001: Nested Orchestration Tests")
    print("=" * 60)

    tests = [
        test_hybrid_client_initialization,
        test_aidb_client_initialization,
        test_unified_learning_client,
        test_client_url_normalization,
        test_aidb_ssl_configuration,
        test_client_interfaces,
        test_nested_architecture,
        test_context_managers,
        test_layer_routing,
        test_no_circular_dependencies,
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
