#!/usr/bin/env python3
"""
Query Validation Module for AIDB
Implements security controls for vector search and API requests:
- Size limits (prevent resource exhaustion)
- Collection whitelisting (prevent enumeration)
- Content validation (injection protection)
- Rate limiting (DoS prevention)
- Pagination support
"""

from typing import List, Optional, Set
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timedelta
import re


# Whitelist of allowed collections
ALLOWED_COLLECTIONS: Set[str] = {
    'nixos_docs',
    'solved_issues',
    'skill_embeddings',
    'telemetry_patterns',
    'system_registry',
    'tool_schemas'
}

# Security patterns to reject
DANGEROUS_PATTERNS = [
    r'<script',           # XSS
    r'javascript:',       # XSS
    r'DROP\s+TABLE',      # SQL injection
    r'DELETE\s+FROM',     # SQL injection
    r'\.\./\.\.',         # Path traversal
    r'\.\./',             # Path traversal
    r'<iframe',           # XSS
    r'eval\(',            # Code injection
    r'exec\(',            # Code injection
]


class VectorSearchRequest(BaseModel):
    """
    Validated request for vector search operations.

    All fields are validated to prevent:
    - Resource exhaustion (size limits)
    - Collection enumeration (whitelist)
    - Injection attacks (pattern matching)
    - DoS attacks (rate limiting at endpoint level)
    """

    collection: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Collection name to search (must be whitelisted)"
    )

    query: str = Field(
        ...,
        min_length=1,
        max_length=10_000,  # 10KB max query size
        description="Search query text"
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results (1-100)"
    )

    offset: int = Field(
        default=0,
        ge=0,
        le=10_000,
        description="Pagination offset (max 10,000)"
    )

    min_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0.0-1.0)"
    )

    @field_validator('collection')
    @classmethod
    def validate_collection(cls, v):
        """Validate collection name against whitelist"""
        if v not in ALLOWED_COLLECTIONS:
            raise ValueError(
                f"Unknown collection: '{v}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_COLLECTIONS))}"
            )
        return v

    @field_validator('query')
    @classmethod
    def validate_query_content(cls, v):
        """Validate query for malicious patterns"""
        v_lower = v.lower()

        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, v_lower, re.IGNORECASE):
                raise ValueError(
                    f"Query contains potentially malicious content. "
                    f"Pattern detected: {pattern}"
                )

        # Check for excessive special characters (possible injection attempt)
        special_char_ratio = sum(1 for c in v if not c.isalnum() and not c.isspace()) / len(v)
        if special_char_ratio > 0.3:
            raise ValueError(
                "Query contains excessive special characters (>30%). "
                "This may indicate an injection attempt."
            )

        return v

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v):
        """Additional validation for result limit"""
        # Warn if requesting many results (performance consideration)
        if v > 50:
            # This doesn't fail, just logged at API level
            pass
        return v


class PaginatedResponse(BaseModel):
    """
    Standardized paginated response structure.

    Provides:
    - Results array
    - Total count (for pagination UI)
    - Offset/limit (for next page calculation)
    - has_more flag (convenience)
    """

    results: List[dict] = Field(
        default_factory=list,
        description="Search results"
    )

    total: int = Field(
        ...,
        ge=0,
        description="Total number of matching results"
    )

    offset: int = Field(
        ...,
        ge=0,
        description="Current offset"
    )

    limit: int = Field(
        ...,
        ge=1,
        description="Results per page"
    )

    has_more: bool = Field(
        ...,
        description="Whether more results are available"
    )

    query_time_ms: Optional[float] = Field(
        None,
        description="Query execution time in milliseconds"
    )


class RateLimiter:
    """
    In-memory rate limiter for API endpoints.

    Implements token bucket algorithm with per-client tracking.
    For production, consider using Redis for distributed rate limiting.
    """

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_buckets = {}  # client_id -> (count, reset_time)
        self.hour_buckets = {}    # client_id -> (count, reset_time)

    def check_rate_limit(self, client_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if client is within rate limits.

        Returns:
            (allowed, error_message)
        """
        now = datetime.now()

        # Check minute limit
        if client_id in self.minute_buckets:
            count, reset_time = self.minute_buckets[client_id]
            if now < reset_time:
                if count >= self.requests_per_minute:
                    retry_after = int((reset_time - now).total_seconds())
                    return False, f"Rate limit exceeded: {self.requests_per_minute} requests/minute. Retry after {retry_after}s"
                self.minute_buckets[client_id] = (count + 1, reset_time)
            else:
                # Reset window
                self.minute_buckets[client_id] = (1, now + timedelta(minutes=1))
        else:
            self.minute_buckets[client_id] = (1, now + timedelta(minutes=1))

        # Check hour limit
        if client_id in self.hour_buckets:
            count, reset_time = self.hour_buckets[client_id]
            if now < reset_time:
                if count >= self.requests_per_hour:
                    retry_after = int((reset_time - now).total_seconds())
                    return False, f"Rate limit exceeded: {self.requests_per_hour} requests/hour. Retry after {retry_after}s"
                self.hour_buckets[client_id] = (count + 1, reset_time)
            else:
                # Reset window
                self.hour_buckets[client_id] = (1, now + timedelta(hours=1))
        else:
            self.hour_buckets[client_id] = (1, now + timedelta(hours=1))

        return True, None

    def cleanup_old_buckets(self):
        """Remove expired buckets to prevent memory leak"""
        now = datetime.now()

        # Cleanup minute buckets
        expired_minute = [
            client_id for client_id, (_, reset_time) in self.minute_buckets.items()
            if now > reset_time + timedelta(minutes=5)
        ]
        for client_id in expired_minute:
            del self.minute_buckets[client_id]

        # Cleanup hour buckets
        expired_hour = [
            client_id for client_id, (_, reset_time) in self.hour_buckets.items()
            if now > reset_time + timedelta(hours=2)
        ]
        for client_id in expired_hour:
            del self.hour_buckets[client_id]


# Global rate limiter instance
# In production, use Redis-backed rate limiter for distributed systems
rate_limiter = RateLimiter(requests_per_minute=60, requests_per_hour=1000)


def validate_collection_name(collection: str) -> bool:
    """
    Quick validation for collection name.

    Args:
        collection: Collection name to validate

    Returns:
        True if valid, False otherwise
    """
    return collection in ALLOWED_COLLECTIONS


def get_allowed_collections() -> List[str]:
    """
    Get list of allowed collections.

    Returns:
        Sorted list of allowed collection names
    """
    return sorted(ALLOWED_COLLECTIONS)


def sanitize_query(query: str, max_length: int = 10_000) -> str:
    """
    Sanitize query string for safe processing.

    Args:
        query: Raw query string
        max_length: Maximum allowed length

    Returns:
        Sanitized query string

    Raises:
        ValueError: If query is invalid or dangerous
    """
    # Trim to max length
    if len(query) > max_length:
        raise ValueError(f"Query exceeds maximum length of {max_length} characters")

    # Strip whitespace
    query = query.strip()

    # Check for empty query
    if not query:
        raise ValueError("Query cannot be empty")

    # Additional sanitization can be added here
    # (e.g., normalize unicode, remove control characters)

    return query


def estimate_query_cost(query: str, limit: int) -> float:
    """
    Estimate computational cost of query.

    Used for:
    - Monitoring expensive queries
    - Potential cost-based rate limiting
    - Resource allocation decisions

    Args:
        query: Query string
        limit: Number of results requested

    Returns:
        Estimated cost (arbitrary units, higher = more expensive)
    """
    # Base cost from query length (embedding generation)
    base_cost = len(query) / 1000.0  # ~1 unit per 1000 chars

    # Cost from result limit (similarity search)
    search_cost = limit / 10.0  # ~1 unit per 10 results

    # Total cost
    total_cost = base_cost + search_cost

    return total_cost


# Example usage and testing
if __name__ == "__main__":
    print("Query Validator Module")
    print("=" * 60)

    # Test 1: Valid query
    print("\nTest 1: Valid query")
    try:
        req = VectorSearchRequest(
            collection="nixos_docs",
            query="How do I install vim?",
            limit=10,
            offset=0
        )
        print(f"✅ Valid: {req.collection}, query length: {len(req.query)}")
    except ValueError as e:
        print(f"❌ Invalid: {e}")

    # Test 2: Invalid collection
    print("\nTest 2: Invalid collection")
    try:
        req = VectorSearchRequest(
            collection="evil_collection",
            query="test",
            limit=10
        )
        print(f"✅ Valid: {req.collection}")
    except ValueError as e:
        print(f"❌ Invalid: {e}")

    # Test 3: Malicious query (XSS)
    print("\nTest 3: Malicious query (XSS)")
    try:
        req = VectorSearchRequest(
            collection="nixos_docs",
            query="<script>alert('xss')</script>",
            limit=10
        )
        print(f"✅ Valid: {req.query}")
    except ValueError as e:
        print(f"❌ Invalid: {e}")

    # Test 4: Query too large
    print("\nTest 4: Query too large")
    try:
        req = VectorSearchRequest(
            collection="nixos_docs",
            query="x" * 11_000,  # 11KB
            limit=10
        )
        print(f"✅ Valid: length {len(req.query)}")
    except ValueError as e:
        print(f"❌ Invalid: {e}")

    # Test 5: Rate limiting
    print("\nTest 5: Rate limiting")
    limiter = RateLimiter(requests_per_minute=5, requests_per_hour=10)
    client_id = "test_client"

    for i in range(7):
        allowed, error = limiter.check_rate_limit(client_id)
        if allowed:
            print(f"  Request {i+1}: ✅ Allowed")
        else:
            print(f"  Request {i+1}: ❌ Blocked - {error}")

    print("\n" + "=" * 60)
    print("Query validation module loaded successfully")
