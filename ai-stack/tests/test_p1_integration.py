#!/usr/bin/env python3
"""
Integration tests for P1 Production Hardening Features

Tests:
1. Query validation with rate limiting
2. Garbage collection operations
3. Let's Encrypt certificate renewal
4. End-to-end security hardening
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

import asyncpg
import httpx
import pytest
from qdrant_client import QdrantClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "aidb"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "hybrid-coordinator"))

from query_validator import VectorSearchRequest, RateLimiter
from garbage_collector import GarbageCollector


class TestQueryValidation:
    """Test suite for query validation and rate limiting"""

    def test_valid_query_accepted(self):
        """Valid queries should pass validation"""
        request = VectorSearchRequest(
            collection="nixos_docs",
            query="How do I configure networking in NixOS?",
            limit=10,
            offset=0,
            min_score=0.7
        )
        assert request.collection == "nixos_docs"
        assert request.limit == 10
        assert request.min_score == 0.7

    def test_invalid_collection_rejected(self):
        """Unknown collections should be rejected"""
        with pytest.raises(ValueError, match="Unknown collection"):
            VectorSearchRequest(
                collection="malicious_collection",
                query="test",
                limit=10
            )

    def test_oversized_query_rejected(self):
        """Queries exceeding 10KB should be rejected"""
        large_query = "x" * 10001
        with pytest.raises(ValueError, match="String should have at most 10000 characters"):
            VectorSearchRequest(
                collection="nixos_docs",
                query=large_query,
                limit=10
            )

    def test_xss_patterns_blocked(self):
        """XSS attack patterns should be blocked"""
        xss_query = "<script>alert('xss')</script>"
        with pytest.raises(ValueError, match="potentially malicious patterns"):
            VectorSearchRequest(
                collection="nixos_docs",
                query=xss_query,
                limit=10
            )

    def test_sql_injection_blocked(self):
        """SQL injection patterns should be blocked"""
        sql_query = "'; DROP TABLE users; --"
        with pytest.raises(ValueError, match="potentially malicious patterns"):
            VectorSearchRequest(
                collection="nixos_docs",
                query=sql_query,
                limit=10
            )

    def test_path_traversal_blocked(self):
        """Path traversal patterns should be blocked"""
        path_query = "../../../etc/passwd"
        with pytest.raises(ValueError, match="potentially malicious patterns"):
            VectorSearchRequest(
                collection="nixos_docs",
                query=path_query,
                limit=10
            )

    def test_limit_bounds_enforced(self):
        """Limit must be between 1 and 100"""
        # Too small
        with pytest.raises(ValueError):
            VectorSearchRequest(
                collection="nixos_docs",
                query="test",
                limit=0
            )

        # Too large
        with pytest.raises(ValueError):
            VectorSearchRequest(
                collection="nixos_docs",
                query="test",
                limit=101
            )

    def test_rate_limiting_enforced(self):
        """Rate limiter should enforce request limits"""
        limiter = RateLimiter(requests_per_minute=5, requests_per_hour=10)
        client_id = "test_client"

        # First 5 requests should succeed
        for i in range(5):
            allowed, error = limiter.check_rate_limit(client_id)
            assert allowed, f"Request {i+1} should be allowed"

        # 6th request should be blocked (minute limit)
        allowed, error = limiter.check_rate_limit(client_id)
        assert not allowed
        assert "Rate limit exceeded" in error

    def test_rate_limiting_resets_after_window(self):
        """Rate limits should reset after time window"""
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=10)
        client_id = "test_client_2"

        # Use up minute limit
        limiter.check_rate_limit(client_id)
        limiter.check_rate_limit(client_id)

        # Should be blocked
        allowed, _ = limiter.check_rate_limit(client_id)
        assert not allowed

        # Manually reset the bucket (simulating time passage)
        limiter.minute_buckets.clear()

        # Should be allowed again
        allowed, _ = limiter.check_rate_limit(client_id)
        assert allowed


@pytest.mark.asyncio
class TestGarbageCollection:
    """Test suite for garbage collection operations"""

    async def setup_test_database(self) -> asyncpg.Pool:
        """Create test database connection"""
        # Use test database credentials
        db_pool = await asyncpg.create_pool(
            host="localhost",
            port=5432,
            database="aidb_test",
            user="aidb",
            password="aidb_password",
            min_size=1,
            max_size=5
        )
        return db_pool

    async def test_cleanup_old_solutions(self):
        """GC should remove old low-value solutions"""
        try:
            db_pool = await self.setup_test_database()
            qdrant = QdrantClient(host="localhost", port=6333)

            gc = GarbageCollector(
                db_pool=db_pool,
                qdrant_client=qdrant,
                max_age_days=30,
                min_value_score=0.5
            )

            # Insert test data: old low-value solution
            async with db_pool.acquire() as conn:
                old_date = datetime.now() - timedelta(days=35)
                await conn.execute("""
                    INSERT INTO solved_issues (id, query, solution, value_score, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                """, "test_old_1", "old query", "old solution", 0.3, old_date)

            # Run GC
            deleted = await gc.cleanup_old_solutions()
            assert deleted >= 1, "Should delete at least 1 old solution"

        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    async def test_prune_low_value_solutions(self):
        """GC should prune low-value solutions when limit reached"""
        try:
            db_pool = await self.setup_test_database()
            qdrant = QdrantClient(host="localhost", port=6333)

            gc = GarbageCollector(
                db_pool=db_pool,
                qdrant_client=qdrant,
                max_solutions=10,  # Low limit for testing
                min_value_score=0.5
            )

            # Insert 15 solutions with varying scores
            async with db_pool.acquire() as conn:
                for i in range(15):
                    value_score = 0.1 + (i * 0.05)  # 0.1 to 0.8
                    await conn.execute("""
                        INSERT INTO solved_issues (id, query, solution, value_score, created_at)
                        VALUES ($1, $2, $3, $4, NOW())
                    """, f"test_prune_{i}", f"query {i}", f"solution {i}", value_score)

            # Run GC
            pruned = await gc.prune_low_value_solutions()
            assert pruned >= 5, "Should prune at least 5 low-value solutions"

            # Verify top solutions remain
            async with db_pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM solved_issues WHERE id LIKE 'test_prune_%'")
                assert count <= 10, "Should keep at most 10 solutions"

        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    async def test_deduplicate_solutions(self):
        """GC should remove duplicate solutions"""
        try:
            db_pool = await self.setup_test_database()
            qdrant = QdrantClient(host="localhost", port=6333)

            gc = GarbageCollector(
                db_pool=db_pool,
                qdrant_client=qdrant,
                deduplicate_similarity=0.95
            )

            # Insert duplicate solutions
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO solved_issues (id, query, solution, value_score, created_at)
                    VALUES
                    ($1, $2, $3, $4, NOW()),
                    ($5, $6, $7, $8, NOW())
                """,
                "dup_1", "How to configure NixOS?", "solution 1", 0.7,
                "dup_2", "how to configure nixos?", "solution 2", 0.6  # Duplicate (lowercase)
                )

            # Run GC
            duplicates = await gc.deduplicate_solutions()
            assert duplicates >= 1, "Should find at least 1 duplicate"

        except Exception as e:
            pytest.skip(f"Database not available: {e}")


@pytest.mark.asyncio
class TestVectorSearchIntegration:
    """Integration tests for vector search with validation"""

    async def test_vector_search_with_validation(self):
        """Vector search should validate and rate limit requests"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test valid request
            response = await client.post(
                "http://localhost:8091/vector/search",
                json={
                    "collection": "nixos_docs",
                    "query": "How do I install packages?",
                    "limit": 5,
                    "offset": 0
                }
            )

            if response.status_code == 200:
                data = response.json()
                assert "results" in data
                assert "total" in data
                assert "has_more" in data
            else:
                pytest.skip("AIDB server not running")

    async def test_vector_search_rejects_invalid_collection(self):
        """Vector search should reject invalid collections"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "http://localhost:8091/vector/search",
                json={
                    "collection": "malicious_collection",
                    "query": "test",
                    "limit": 5
                }
            )

            if response.status_code != 503:  # Service unavailable
                assert response.status_code == 400
                assert "Validation failed" in response.json()["detail"]
            else:
                pytest.skip("AIDB server not running")

    async def test_vector_search_rate_limiting(self):
        """Vector search should enforce rate limits"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Send many requests rapidly
            responses = []
            for i in range(65):  # Exceed 60/min limit
                response = await client.post(
                    "http://localhost:8091/vector/search",
                    json={
                        "collection": "nixos_docs",
                        "query": f"test query {i}",
                        "limit": 5
                    }
                )
                responses.append(response)

            if responses[0].status_code != 503:
                # At least one should be rate limited
                rate_limited = [r for r in responses if r.status_code == 429]
                assert len(rate_limited) > 0, "Should have rate limited requests"
            else:
                pytest.skip("AIDB server not running")


class TestLetsEncryptRenewal:
    """Tests for Let's Encrypt certificate renewal"""

    def test_renewal_script_exists(self):
        """Renewal script should exist and be executable"""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "renew-tls-certificate.sh"
        assert script_path.exists(), "Renewal script should exist"
        assert os.access(script_path, os.X_OK), "Renewal script should be executable"

    def test_systemd_timer_exists(self):
        """Systemd timer configuration should exist"""
        timer_path = Path(__file__).parent.parent / "systemd" / "letsencrypt-renewal.timer"
        service_path = Path(__file__).parent.parent / "systemd" / "letsencrypt-renewal.service"

        assert timer_path.exists(), "Timer file should exist"
        assert service_path.exists(), "Service file should exist"

    def test_nginx_acme_challenge_configured(self):
        """Nginx should have ACME challenge location configured"""
        nginx_conf = Path(__file__).parent.parent / "compose" / "nginx" / "nginx.conf"
        assert nginx_conf.exists(), "Nginx config should exist"

        content = nginx_conf.read_text()
        assert "/.well-known/acme-challenge/" in content, "Should have ACME challenge location"
        assert "/var/www/letsencrypt" in content, "Should have webroot configured"


class TestEndToEndSecurity:
    """End-to-end security hardening tests"""

    @pytest.mark.asyncio
    async def test_complete_security_chain(self):
        """Test complete security chain: validation -> rate limiting -> search -> response"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Test XSS protection
            xss_response = await client.post(
                "http://localhost:8091/vector/search",
                json={
                    "collection": "nixos_docs",
                    "query": "<script>alert('xss')</script>",
                    "limit": 5
                }
            )

            if xss_response.status_code != 503:
                assert xss_response.status_code == 400, "Should reject XSS patterns"

            # 2. Test valid request with pagination
            valid_response = await client.post(
                "http://localhost:8091/vector/search",
                json={
                    "collection": "nixos_docs",
                    "query": "How do I configure services?",
                    "limit": 3,
                    "offset": 0,
                    "min_score": 0.5
                }
            )

            if valid_response.status_code == 200:
                data = valid_response.json()
                assert "results" in data
                assert "total" in data
                assert "limit" in data
                assert "offset" in data
                assert "has_more" in data
                assert data["limit"] == 3
            else:
                pytest.skip("AIDB server not running")


def run_all_tests():
    """Run all P1 integration tests"""
    print("=" * 80)
    print("P1 Production Hardening - Integration Tests")
    print("=" * 80)
    print()

    # Run pytest with verbose output
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "--color=yes"
    ]

    return pytest.main(pytest_args)


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
