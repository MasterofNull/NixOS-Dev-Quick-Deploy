# Secure Container Management Architecture

Owner: AI Stack Maintainers
Last Updated: 2026-03-05

## Fixing P0 Security Issues While Keeping Functionality

**Date:** January 23, 2026
**Status:** 🔄 DESIGN PHASE

---

## Problem Statement

Three core services currently have critical security vulnerabilities:

1. **health-monitor** - Uses `privileged: true` (complete host access)
2. **ralph-wiggum** - Mounts Podman socket (can control all containers)
3. **container-engine** - Mounts Podman socket (API exposure risk)

**Can't just disable:** These are core services for the agentic stack!
**Need to:** Keep functionality, remove security risks

---

## Current Architecture (INSECURE)

```
┌─────────────────────────────────────────────────────────┐
│ Container (privileged: true)                             │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ health-monitor                                       │ │
│ │ - Full root access to host                          │ │
│ │ - Can break out of container                        │ │
│ │ - Can access all host files                         │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Container (socket mount)                                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ralph-wiggum / container-engine                      │ │
│ │ - Volume: /var/run/podman/podman.sock              │ │
│ │ - Can create privileged containers                  │ │
│ │ - Can mount any host path                           │ │
│ │ - Can access other containers' data                 │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Attack Scenario:**
1. Attacker compromises any of these containers
2. Uses socket/privilege to create new privileged container
3. Mounts host `/` into container
4. Full root access to host system
5. Game over

---

## Secure Architecture (PROPOSED)

### Option A: Podman REST API (Recommended)

```
┌──────────────────────────────────────────────────────────┐
│ HOST                                                      │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Podman REST API (systemd socket activation)        │  │
│  │ - Listening on http://host.containers.internal:2375│  │
│  │ - No root required (rootless Podman)               │  │
│  │ - Rate limited                                      │  │
│  │ - Audit logged                                      │  │
│  └────────────────────────────────────────────────────┘  │
│                            ↓ HTTP API                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Container (NO privileges)                           │  │
│  │ ┌────────────────────────────────────────────────┐ │  │
│  │ │ health-monitor / ralph-wiggum / container-engine│ │  │
│  │ │ - Calls Podman API via HTTP                     │ │  │
│  │ │ - Limited to allowed operations                 │ │  │
│  │ │ - No direct host access                         │ │  │
│  │ └────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ No privileged containers
- ✅ No socket mounts
- ✅ Network isolation
- ✅ Can be rate-limited
- ✅ Full audit trail
- ✅ Works with rootless Podman

**Drawbacks:**
- Requires Podman API setup on host
- Slightly more latency (HTTP vs socket)

---

### Option B: Restricted Socket Proxy (Compromise)

```
┌──────────────────────────────────────────────────────────┐
│ HOST                                                      │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Socket Proxy (separate container)                  │  │
│  │ - Mounts Podman socket (ONLY this container)       │  │
│  │ - Exposes filtered API                             │  │
│  │ - Allowed operations:                              │  │
│  │   • Container list                                 │  │
│  │   • Container inspect                              │  │
│  │   • Container restart (specific containers only)   │  │
│  │ - Blocked operations:                              │  │
│  │   • Create privileged containers                   │  │
│  │   • Mount host paths                               │  │
│  │   • Network host mode                              │  │
│  └────────────────────────────────────────────────────┘  │
│                            ↓ Filtered API                 │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Container (NO privileges, NO socket)                │  │
│  │ ┌────────────────────────────────────────────────┐ │  │
│  │ │ health-monitor / ralph-wiggum / container-engine│ │  │
│  │ │ - Calls proxy API                               │ │  │
│  │ │ - Limited to safe operations                    │ │  │
│  │ └────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ Most containers have no privileges
- ✅ One proxy container controls access
- ✅ Can implement custom security policies
- ✅ No host configuration needed

**Drawbacks:**
- ⚠️ Proxy container still has socket access
- ⚠️ If proxy is compromised, still risky
- Requires custom proxy implementation

---

### Option C: Kubernetes-style Sidecar (Advanced)

```
┌──────────────────────────────────────────────────────────┐
│ POD (Shared network namespace)                           │
│                                                            │
│  ┌────────────────┐        ┌──────────────────────────┐  │
│  │ Sidecar        │ socket │ Application Container     │  │
│  │ (privileged)   │←──────→│ (NO privileges)           │  │
│  │ - Has socket   │  IPC   │ - Calls sidecar via IPC   │  │
│  │ - Minimal code │        │ - Main logic here         │  │
│  └────────────────┘        └──────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ Privilege isolated to tiny sidecar
- ✅ Application logic has no privileges
- ✅ Follows principle of least privilege

**Drawbacks:**
- Requires Podman pod architecture
- More complex deployment

---

## Recommended Solution: Option A (Podman REST API)

### Implementation Steps

#### Step 1: Enable Podman REST API on Host

```bash
# Enable Podman API socket (rootless)
systemctl --user enable --now podman.socket

# Verify it's running
curl -s http://localhost:2375/version

# Output should show Podman version info
```

**Configuration file:** `/etc/systemd/system/podman-api.socket`
```ini
[Unit]
Description=Podman API Socket
Documentation=man:podman-system-service(1)

[Socket]
ListenStream=127.0.0.1:2375
SocketMode=0660
SocketUser=podman-api
SocketGroup=podman-api

[Install]
WantedBy=sockets.target
```

#### Step 2: Create Podman API Service

```bash
# Service file: /etc/systemd/system/podman-api.service
[Unit]
Description=Podman API Service
Requires=podman-api.socket
After=podman-api.socket
Documentation=man:podman-system-service(1)
StartLimitIntervalSec=0

[Service]
Type=exec
KillMode=process
Environment=LOGGING="--log-level=info"
ExecStart=/usr/bin/podman system service --time=0

[Install]
WantedBy=default.target
```

#### Step 3: Configure Network Access

Expose the Podman API on a node-local endpoint and allow pods to reach it:
- Bind the service to a node IP (or localhost + hostNetwork proxy) and allowlist it in firewall rules.
- Set `PODMAN_API_URL` on each Deployment to `http://<node-ip>:2375`.
- Add NetworkPolicy egress rules to only permit Podman API traffic from approved namespaces.

#### Step 4: Update Services to Use API

**health-monitor** changes (Deployment env):
- Set `PODMAN_API_URL` to the node-local endpoint.
- Set `ALLOWED_OPERATIONS=inspect,restart`.
- Remove `privileged: true`.
- Remove any hostPath socket mounts.

**ralph-wiggum** changes (Deployment env):
- Set `PODMAN_API_URL` to the node-local endpoint.
- Set `ALLOWED_OPERATIONS=list,inspect,create,start,stop`.
- Remove any hostPath socket mounts.

**container-engine** changes (Deployment env):
- Set `PODMAN_API_URL` to the node-local endpoint.
- Remove any hostPath socket mounts.

#### Step 5: Update Python Code

**Old code (INSECURE):**
```python
import docker
client = docker.DockerClient(base_url='unix://var/run/docker.sock')
container = client.containers.get('my-container')
container.restart()
```

**New code (SECURE):**
```python
import httpx

PODMAN_API_URL = os.getenv("PODMAN_API_URL", "http://host.containers.internal:2375")

async def restart_container(container_name: str):
    async with httpx.AsyncClient() as client:
        # List containers to get ID
        response = await client.get(
            f"{PODMAN_API_URL}/v1.0.0/libpod/containers/json",
            params={"filters": json.dumps({"name": [container_name]})}
        )
        containers = response.json()
        if not containers:
            raise ValueError(f"Container {container_name} not found")

        container_id = containers[0]["Id"]

        # Restart container
        response = await client.post(
            f"{PODMAN_API_URL}/v1.0.0/libpod/containers/{container_id}/restart"
        )
        return response.status_code == 204
```

---

## Security Improvements

### Before (INSECURE)
| Service | Risk Level | Attack Surface |
|---------|------------|----------------|
| health-monitor | 🔴 CRITICAL | Full root access |
| ralph-wiggum | 🔴 CRITICAL | All containers |
| container-engine | 🔴 CRITICAL | All containers |

### After (SECURE)
| Service | Risk Level | Attack Surface |
|---------|------------|----------------|
| health-monitor | 🟢 LOW | API calls only, rate limited |
| ralph-wiggum | 🟢 LOW | API calls only, audit logged |
| container-engine | 🟢 LOW | API calls only, network isolated |

**Risk Reduction:** 90%+

---

## Additional Security Measures

### 1. Rate Limiting (nginx proxy in front of API)

Deploy a `podman-api-proxy` Kubernetes Deployment + ClusterIP Service:
- Nginx config stored in a ConfigMap.
- Service exposed only to the ai-stack namespace.
- Rate limits enforced before reaching the host API.

**nginx-rate-limit.conf:**
```nginx
http {
    limit_req_zone $binary_remote_addr zone=podman_api:10m rate=10r/s;

    server {
        listen 80;

        location / {
            limit_req zone=podman_api burst=20;
            proxy_pass http://host.containers.internal:2375;
        }
    }
}
```

### 2. Operation Allowlist

Create wrapper that only allows safe operations:

```python
ALLOWED_OPERATIONS = {
    "health-monitor": ["list", "inspect", "restart"],
    "ralph-wiggum": ["list", "inspect", "create", "start", "stop"],
    "container-engine": ["list", "inspect", "logs"]
}

def check_operation(service: str, operation: str):
    if operation not in ALLOWED_OPERATIONS.get(service, []):
        raise PermissionError(f"{service} not allowed to {operation}")
```

### 3. Audit Logging

Log all container operations:

```python
async def audit_log(service: str, operation: str, container: str):
    await postgres.execute("""
        INSERT INTO container_audit_log
        (timestamp, service, operation, container, success)
        VALUES ($1, $2, $3, $4, $5)
    """, datetime.now(), service, operation, container, True)
```

---

## Implementation Checklist

### Phase 1: Setup Podman API (Day 2)
- [ ] Enable Podman API socket on host
- [ ] Test API accessibility from containers
- [ ] Configure rate limiting (nginx proxy)
- [ ] Set up audit logging table

### Phase 2: Update Services (Day 2-3)
- [ ] Modify health-monitor code to use HTTP API
- [ ] Modify ralph-wiggum code to use HTTP API
- [ ] Modify container-engine code to use HTTP API
- [ ] Add operation allowlist checks
- [ ] Add audit logging calls

### Phase 3: Update Kubernetes Manifests (Day 3)
- [ ] Remove `privileged: true` from health-monitor
- [ ] Remove hostPath socket mounts from ralph-wiggum
- [ ] Remove hostPath socket mounts from container-engine
- [ ] Add env vars for `PODMAN_API_URL` + `ALLOWED_OPERATIONS`
- [ ] Add NetworkPolicy egress allowlist for the Podman API endpoint

### Phase 4: Testing (Day 3)
- [ ] Test health-monitor can restart containers
- [ ] Test ralph-wiggum can orchestrate agents
- [ ] Test container-engine API works
- [ ] Verify no privileged containers running
- [ ] Verify no socket mounts exist
- [ ] Test that unauthorized operations are blocked

### Phase 5: Security Validation (Day 3)
- [ ] Run security scan (Trivy)
- [ ] Verify no privileged containers
- [ ] Verify no socket mounts
- [ ] Test that container breakout attempts fail
- [ ] Review audit logs

---

## Rollback Plan

If API approach doesn't work:

### Fallback: Minimal Privilege Socket Proxy

1. Deploy a socket-proxy Deployment that mounts the Podman socket read-only.
2. Lock it down with a dedicated ServiceAccount + NetworkPolicy.
3. Point services to the proxy URL instead of direct socket access.

---

## Success Criteria

✅ **Security:**
- Zero privileged containers
- Zero socket mounts (except optional proxy)
- All operations audit logged
- Rate limiting in place

✅ **Functionality:**
- health-monitor can restart failed services
- ralph-wiggum can orchestrate agents
- container-engine API works
- No performance degradation

✅ **Monitoring:**
- Audit log accessible via dashboard
- Failed operation attempts logged
- Performance metrics tracked

---

## Timeline

- **Day 2 AM:** Setup Podman API on host
- **Day 2 PM:** Update service code
- **Day 3 AM:** Update Kubernetes manifests
- **Day 3 PM:** Testing and validation

**Total Time:** 2 days

---

**Status:** 🔄 READY TO IMPLEMENT
**Risk Level:** 🟢 LOW (Easy rollback if needed)
**Priority:** 🔴 P0 (Security critical)
