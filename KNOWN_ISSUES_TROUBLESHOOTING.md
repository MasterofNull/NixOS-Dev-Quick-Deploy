# Known Issues & Troubleshooting

## Phase 7 - Documentation Verification

### Known Issues

#### 1. Open WebUI CrashLoopBackOff
- **Status**: ⚠️ Optional service in CrashLoopBackOff state
- **Impact**: Does not affect core AI stack functionality
- **Resolution**: This is an optional service and does not impact core functionality
- **Tracking**: Issue acknowledged in test results

#### 2. Registry Push Flow
- **Status**: Pending documentation for immutable image tagging
- **Workaround**: Current workflow uses `localhost:5000` local registry
- **Commands**:
  ```bash
  # Tag and push images
  skopeo copy docker://source/image docker://localhost:5000/target/image:tag
  
  # Or use buildah for building and pushing
  buildah bud -t localhost:5000/service-name:tag .
  buildah push localhost:5000/service-name:tag
  ```

#### 3. Portainer Initial Setup
- **Status**: Pending validation of login and initial wizard reset
- **Default Access**:
  - URL: http://localhost:9000 or configured port
  - Default user: admin
  - Default password: prompted on first login

### Troubleshooting Commands

#### Service Health Checks
```bash
# Check all services health
curl http://localhost:8091/health  # AIDB
curl http://localhost:8092/health  # Hybrid Coordinator  
curl http://localhost:8098/health  # Ralph Wiggum
curl http://localhost:8081/health  # Embeddings
```

#### Kubernetes Status
```bash
# Check all pods in ai-stack namespace
kubectl get pods -n ai-stack

# Check services
kubectl get svc -n ai-stack

# Check deployments
kubectl get deployments -n ai-stack
```

#### Common Fixes
```bash
# Restart problematic deployments
kubectl rollout restart deployment/DEPLOYMENT_NAME -n ai-stack

# Check logs
kubectl logs -f deployment/DEPLOYMENT_NAME -n ai-stack

# Scale deployment if needed
kubectl scale deployment/DEPLOYMENT_NAME --replicas=1 -n ai-stack
```

### Testing Commands
```bash
# Run the full E2E test suite
python -m pytest tests/test_hospital_e2e.py -v

# Run API contract tests
python -m pytest ai-stack/tests/test_api_contracts.py -v

# Run individual service tests
python -m pytest ai-stack/tests/ -k "service_name"
```