# Code Examples & Patterns

**Purpose:** Common code patterns and examples for quick reference
**Benefit:** Copy-paste templates that follow best practices

---

## Python Examples

### Good Function Example

```python
def calculate_total(items: list[dict]) -> float:
    """Calculate total price from items."""
    return sum(item.get("price", 0) for item in items)
```

**Why it's good:**
- Type hints for clarity
- One clear purpose
- Handles missing keys
- Concise docstring

### Good Class Example

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    """User account model."""
    id: int
    username: str
    email: str
    is_active: bool = True
    created_at: Optional[datetime] = None

    def validate_email(self) -> bool:
        """Check if email format is valid."""
        return "@" in self.email and "." in self.email.split("@")[1]
```

**Why it's good:**
- Uses dataclass for simplicity
- Type hints throughout
- Clear field defaults
- Focused methods

### API Endpoint Example

```python
from fastapi import APIRouter, HTTPException, Depends
from typing import List

router = APIRouter(prefix="/api/users")

@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db = Depends(get_db)
) -> List[UserResponse]:
    """List all users with pagination."""
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    user: UserCreate,
    db = Depends(get_db)
) -> UserResponse:
    """Create a new user."""
    db_user = User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
```

### Database Query Example

```python
from sqlalchemy import select
from typing import Optional

def get_user_by_email(db, email: str) -> Optional[User]:
    """Find user by email address."""
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()

def get_active_users(db, limit: int = 100) -> list[User]:
    """Get active users with limit."""
    stmt = (
        select(User)
        .where(User.is_active == True)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()
```

---

## JavaScript/TypeScript Examples

### Good Function Example

```typescript
interface Item {
  name: string;
  price: number;
  quantity: number;
}

function calculateTotal(items: Item[]): number {
  return items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
}
```

### React Component Example

```typescript
import React, { useState, useEffect } from 'react';

interface UserListProps {
  onUserSelect: (userId: number) => void;
}

export const UserList: React.FC<UserListProps> = ({ onUserSelect }) => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUsers()
      .then(setUsers)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <ul>
      {users.map(user => (
        <li key={user.id} onClick={() => onUserSelect(user.id)}>
          {user.name}
        </li>
      ))}
    </ul>
  );
};
```

### API Client Example

```typescript
class APIClient {
  private baseURL: string;
  private token?: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  setAuthToken(token: string): void {
    this.token = token;
  }

  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    return headers;
  }
}
```

---

## Testing Examples

### Python Unit Test

```python
import pytest
from myapp import calculate_total

def test_calculate_total_empty_list():
    assert calculate_total([]) == 0

def test_calculate_total_single_item():
    items = [{"price": 10.50}]
    assert calculate_total(items) == 10.50

def test_calculate_total_multiple_items():
    items = [
        {"price": 10.00},
        {"price": 20.00},
        {"price": 15.50}
    ]
    assert calculate_total(items) == 45.50

def test_calculate_total_missing_price():
    items = [{"name": "Item"}, {"price": 10}]
    assert calculate_total(items) == 10
```

### Python Integration Test

```python
import pytest
from fastapi.testclient import TestClient
from myapp import app

client = TestClient(app)

@pytest.fixture
def test_user():
    """Create test user."""
    response = client.post("/api/users/", json={
        "username": "testuser",
        "email": "test@example.com"
    })
    return response.json()

def test_get_users(test_user):
    response = client.get("/api/users/")
    assert response.status_code == 200
    assert len(response.json()) >= 1

def test_get_user_by_id(test_user):
    user_id = test_user["id"]
    response = client.get(f"/api/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["id"] == user_id
```

### JavaScript Unit Test

```typescript
import { describe, it, expect } from 'vitest';
import { calculateTotal } from './utils';

describe('calculateTotal', () => {
  it('returns 0 for empty array', () => {
    expect(calculateTotal([])).toBe(0);
  });

  it('calculates total for single item', () => {
    const items = [{ name: 'Item', price: 10, quantity: 2 }];
    expect(calculateTotal(items)).toBe(20);
  });

  it('calculates total for multiple items', () => {
    const items = [
      { name: 'Item 1', price: 10, quantity: 2 },
      { name: 'Item 2', price: 5, quantity: 3 },
    ];
    expect(calculateTotal(items)).toBe(35);
  });
});
```

---

## Database Migration Examples

### SQLAlchemy Migration (Alembic)

```python
"""Add email column to users

Revision ID: 001
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('users',
        sa.Column('email', sa.String(255), nullable=False)
    )
    op.create_index('ix_users_email', 'users', ['email'])

def downgrade():
    op.drop_index('ix_users_email', 'users')
    op.drop_column('users', 'email')
```

### Raw SQL Migration

```sql
-- Migration: 001_add_users_table.sql
-- Description: Create users table

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);

-- Rollback
-- DROP TABLE IF EXISTS users CASCADE;
```

---

## Configuration Examples

### Environment Configuration

```python
# config.py
import os
from dataclasses import dataclass

@dataclass
class Config:
    """Application configuration."""
    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "appdb")
    DB_USER: str = os.getenv("DB_USER", "app_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_DEBUG: bool = os.getenv("API_DEBUG", "false").lower() == "true"

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION: int = 3600

    @property
    def database_url(self) -> str:
        """Build database URL."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

config = Config()
```

### YAML Configuration

```yaml
# config.yaml
application:
  name: MyApp
  version: 1.0.0
  debug: false

database:
  host: localhost
  port: 5432
  name: appdb
  user: app_user
  pool_size: 10
  max_overflow: 20

api:
  host: 0.0.0.0
  port: 8000
  cors:
    enabled: true
    origins:
      - http://localhost:3000
      - https://app.example.com

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: logs/app.log
```

---

## Docker Examples

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=appdb
      - DB_USER=app_user
      - DB_PASSWORD=${DB_PASSWORD}
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=appdb
      - POSTGRES_USER=app_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app_user -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

---

## Monitoring Examples

### Prometheus Metrics

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Counters
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Histograms
http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Gauges
active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)

# Usage in middleware
def track_request(method, endpoint):
    start_time = time.time()

    try:
        # Process request
        result = process_request()
        status = 200
        return result
    except Exception as e:
        status = 500
        raise
    finally:
        duration = time.time() - start_time
        http_requests_total.labels(method, endpoint, status).inc()
        http_request_duration.labels(method, endpoint).observe(duration)
```

### Health Check Endpoint

```python
from fastapi import FastAPI, status
from typing import Dict

app = FastAPI()

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Status indicating system health
    """
    # Check database connection
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # Check Redis connection
    try:
        redis.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    overall_status = "healthy" if all([
        db_status == "healthy",
        redis_status == "healthy"
    ]) else "unhealthy"

    return {
        "status": overall_status,
        "database": db_status,
        "redis": redis_status,
        "version": "1.0.0"
    }
```

---

## Error Handling Examples

### Python Exception Handling

```python
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

class ResourceNotFoundError(Exception):
    """Raised when resource is not found."""
    pass

class ValidationError(Exception):
    """Raised when validation fails."""
    pass

def get_user(user_id: int) -> User:
    """Get user by ID with proper error handling."""
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ResourceNotFoundError(f"User {user_id} not found")

        return user

    except ResourceNotFoundError:
        logger.warning(f"User {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
```

---

## Logging Examples

### Structured Logging

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())

logger = logging.getLogger("myapp")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage
logger.info("User logged in", extra={"user_id": 123})
logger.error("Database connection failed", extra={"host": "db.example.com"})
```

---

**Last Updated:** 2025-12-03
**Maintainer:** [Your Team]
