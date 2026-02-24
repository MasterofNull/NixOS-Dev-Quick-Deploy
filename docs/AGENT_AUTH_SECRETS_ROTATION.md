# Agent Authentication and Secrets Rotation

## Secure Authentication and Secrets Management for AI Stack Agents

This document outlines the authentication mechanisms and secrets rotation procedures for agents accessing the NixOS AI Stack.

### Authentication Methods

#### 1. API Key Authentication
All MCP services support API key authentication via the `X-API-Key` header:

```
curl -H "X-API-Key: YOUR_API_KEY" http://aidb:8091/health
```

**API Key Format**:
- Length: 32+ characters
- Character set: Alphanumeric + special characters
- Generation: Cryptographically secure random generation
- Storage: Kubernetes secrets or Docker secrets

#### 2. Service Account Authentication
For services running in Kubernetes, use service account tokens:

```bash
# Access token from pod
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
curl -H "Authorization: Bearer $TOKEN" https://kubernetes.default.svc/apis/
```

### Secrets Storage and Management

#### Kubernetes Secrets
API keys and sensitive credentials are stored in Kubernetes secrets:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aidb-api-key
  namespace: ai-stack
type: Opaque
data:
  api-key: <base64-encoded-api-key>
```

#### Secret Mounting
Services mount secrets as files or environment variables:

```yaml
env:
- name: AIDB_API_KEY_FILE
  value: /run/secrets/aidb-api-key
volumeMounts:
- name: aidb-api-key
  mountPath: /run/secrets/aidb-api-key
  subPath: api-key
```

### Secrets Rotation Procedures

#### 1. Automated Rotation
Implement automated secrets rotation with the following schedule:

- **API Keys**: Rotate every 90 days
- **Service Account Tokens**: Rotate every 1 year (Kubernetes default)
- **Database Passwords**: Rotate every 180 days
- **Encryption Keys**: Rotate every 365 days

#### 2. Manual Rotation Process

##### Step 1: Generate New Secret
```bash
# Generate new API key
NEW_API_KEY=$(openssl rand -hex 32)

# Or using Python
NEW_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

##### Step 2: Create New Kubernetes Secret
```bash
kubectl create secret generic new-aidb-api-key \
  --from-literal=api-key="$NEW_API_KEY" \
  -n ai-stack
```

##### Step 3: Update Deployments
```bash
# Patch deployment to use new secret
kubectl patch deployment aidb \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/envFrom/0/secretRef/name", "value": "new-aidb-api-key"}]' \
  -n ai-stack
```

##### Step 4: Verify New Secret Works
```bash
# Test with new API key
curl -H "X-API-Key: $NEW_API_KEY" http://aidb.ai-stack.svc.cluster.local:8091/health
```

##### Step 5: Clean Up Old Secret
```bash
# After verification, delete old secret
kubectl delete secret old-aidb-api-key -n ai-stack
```

### Agent-Specific Authentication

#### 1. External Agents
For external agents connecting to the AI stack:

```bash
# Environment variables
export AIDB_API_KEY="your-api-key"
export HYBRID_COORDINATOR_API_KEY="your-api-key"
export RALPH_WIGGUM_API_KEY="your-api-key"

# Usage in requests
curl -H "X-API-Key: $AIDB_API_KEY" http://your-domain:8091/documents?search=test
```

#### 2. Internal Agents
For agents running inside the Kubernetes cluster:

```python
import os
import requests

# Read API key from mounted secret file
def get_api_key():
    api_key_file = os.getenv("AIDB_API_KEY_FILE", "/run/secrets/aidb-api-key")
    try:
        with open(api_key_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

# Use in requests
api_key = get_api_key()
if api_key:
    headers = {"X-API-Key": api_key}
    response = requests.get("http://aidb:8091/health", headers=headers)
```

### Secrets Rotation Automation Script

Create a script to automate the rotation process:

```bash
#!/bin/bash
# scripts/rotate-agent-secrets.sh

set -e

NAMESPACE=${1:-"ai-stack"}
SECRET_NAME=${2:-"aidb-api-key"}
NEW_SECRET_NAME="${SECRET_NAME}-new-$(date +%Y%m%d-%H%M%S)"

echo "Rotating secret: $SECRET_NAME in namespace: $NAMESPACE"

# Generate new API key
NEW_API_KEY=$(openssl rand -hex 32)
echo "Generated new API key"

# Create new secret
kubectl create secret generic "$NEW_SECRET_NAME" \
  --from-literal="api-key=$NEW_API_KEY" \
  -n "$NAMESPACE"

echo "Created new secret: $NEW_SECRET_NAME"

# Update deployments to use new secret
# This assumes the deployment uses the secret in envFrom
kubectl patch deployment aidb \
  --type='json' \
  -p="[{'op': 'replace', 'path': '/spec/template/spec/containers/0/envFrom/0/secretRef/name', 'value': '$NEW_SECRET_NAME'}]" \
  -n "$NAMESPACE"

echo "Updated deployment to use new secret"

# Wait for rollout
kubectl rollout status deployment/aidb -n "$NAMESPACE"

# Verify new secret works
sleep 10
if curl -f -H "X-API-Key: $NEW_API_KEY" "http://aidb.$NAMESPACE.svc.cluster.local:8091/health" > /dev/null; then
    echo "Verification successful with new API key"
    
    # Delete old secret
    OLD_SECRET_NAME=$(kubectl get deployment aidb -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].envFrom[0].secretRef.name}')
    if [ ! -z "$OLD_SECRET_NAME" ] && [ "$OLD_SECRET_NAME" != "$NEW_SECRET_NAME" ]; then
        kubectl delete secret "$OLD_SECRET_NAME" -n "$NAMESPACE"
        echo "Deleted old secret: $OLD_SECRET_NAME"
    fi
else
    echo "Verification failed, rolling back..."
    kubectl patch deployment aidb \
      --type='json' \
      -p="[{'op': 'replace', 'path': '/spec/template/spec/containers/0/envFrom/0/secretRef/name', 'value': '$OLD_SECRET_NAME'}]" \
      -n "$NAMESPACE"
    kubectl delete secret "$NEW_SECRET_NAME" -n "$NAMESPACE"
    exit 1
fi

echo "Secret rotation completed successfully"
```

### Security Best Practices

#### 1. Least Privilege Access
- Grant agents minimum required permissions
- Use specific API keys per service/function
- Implement role-based access control

#### 2. Audit Logging
- Log all authentication attempts
- Monitor for suspicious access patterns
- Track API key usage

#### 3. Key Compromise Response
- Immediate revocation procedure
- Incident response plan
- Notification system

### Monitoring and Alerts

#### Secrets Expiration Monitoring
```bash
# Check secrets age
kubectl get secrets -n ai-stack -o custom-columns='NAME:.metadata.name,CREATED:.metadata.creationTimestamp'

# Alert when secrets are approaching rotation date
# (Implement in Prometheus/Grafana)
```

#### Authentication Failure Monitoring
- Track failed authentication attempts
- Alert on unusual patterns
- Monitor for brute force attempts

### Agent Integration Guidelines

#### 1. Secure Secret Handling
```python
import os
import stat
from pathlib import Path

def validate_secret_permissions(secret_path):
    """Ensure secret file has secure permissions"""
    path = Path(secret_path)
    if path.exists():
        file_stat = path.stat()
        # Check that file is only readable by owner
        if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
            raise Exception("Secret file has insecure permissions")
```

#### 2. Graceful Degradation
```python
def get_api_key_with_fallback():
    """Get API key with fallback mechanisms"""
    # Try environment variable first
    api_key = os.getenv("AIDB_API_KEY")
    if api_key:
        return api_key
    
    # Try secret file
    secret_file = os.getenv("AIDB_API_KEY_FILE")
    if secret_file:
        try:
            with open(secret_file, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            pass
    
    # No authentication available
    return None
```

### Rotation Schedule

| Secret Type | Rotation Interval | Automation | Owner |
|-------------|-----------------|------------|-------|
| API Keys | Every 90 days | Yes | Platform Team |
| Database Passwords | Every 180 days | Yes | Platform Team |
| Service Account Tokens | Every 1 year | Automatic | Kubernetes |
| Encryption Keys | Every 365 days | Manual | Security Team |

This provides a comprehensive approach to agent authentication and secrets rotation.