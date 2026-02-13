# Registry Push Flow Documentation

## Immutable Image Tagging and Registry Push Flow

This document describes the proper workflow for tagging and pushing immutable images to registries for all services in the AI stack.

### Overview
The system uses a registry-based workflow for container image management, replacing the deprecated local image import method. This ensures consistent, reproducible deployments across environments.

### Service Images and Registry Tags

#### Core AI Services
```bash
# AIDB Service
docker build -t ai-stack-aidb:dev -f ai-stack/mcp-servers/aidb/Dockerfile .
docker tag ai-stack-aidb:dev localhost:5000/ai-stack-aidb:dev
docker push localhost:5000/ai-stack-aidb:dev

# Hybrid Coordinator Service
docker build -t ai-stack-hybrid-coordinator:dev -f ai-stack/mcp-servers/hybrid-coordinator/Dockerfile .
docker tag ai-stack-hybrid-coordinator:dev localhost:5000/ai-stack-hybrid-coordinator:dev
docker push localhost:5000/ai-stack-hybrid-coordinator:dev

# Ralph Wiggum Service
docker build -t ai-stack-ralph-wiggum:dev -f ai-stack/mcp-servers/ralph-wiggum/Dockerfile .
docker tag ai-stack-ralph-wiggum:dev localhost:5000/ai-stack-ralph-wiggum:dev
docker push localhost:5000/ai-stack-ralph-wiggum:dev

# Embeddings Service
docker build -t ai-stack-embeddings:dev -f ai-stack/mcp-servers/embeddings-service/Dockerfile .
docker tag ai-stack-embeddings:dev localhost:5000/ai-stack-embeddings:dev
docker push localhost:5000/ai-stack-embeddings:dev

# NixOS Docs Service
docker build -t ai-stack-nixos-docs:dev -f ai-stack/mcp-servers/nixos-docs/Dockerfile .
docker tag ai-stack-nixos-docs:dev localhost:5000/ai-stack-nixos-docs:dev
docker push localhost:5000/ai-stack-nixos-docs:dev

# Dashboard API
docker build -t ai-stack-dashboard-api:dev -f dashboard/backend/Dockerfile .
docker tag ai-stack-dashboard-api:dev localhost:5000/ai-stack-dashboard-api:dev
docker push localhost:5000/ai-stack-dashboard-api:dev
```

### Using Skopeo for Image Operations

Skopeo provides a more efficient way to copy images without requiring local storage:

```bash
# Copy from source to local registry
skopeo copy docker://source-image:tag docker://localhost:5000/target-image:tag

# Copy between registries
skopeo copy docker://localhost:5000/source-image:tag docker://remote-registry/target-image:tag

# Copy with authentication
skopeo copy --dest-creds username:password docker://source-image:tag docker://registry/target-image:tag
```

### Build and Push Script

Create a script to automate the build and push process:

```bash
#!/bin/bash
# scripts/build-and-push-images.sh

set -e

REGISTRY=${1:-"localhost:5000"}
TAG=${2:-"dev"}

SERVICES=(
  "aidb:ai-stack/mcp-servers/aidb/Dockerfile"
  "hybrid-coordinator:ai-stack/mcp-servers/hybrid-coordinator/Dockerfile" 
  "ralph-wiggum:ai-stack/mcp-servers/ralph-wiggum/Dockerfile"
  "embeddings:ai-stack/mcp-servers/embeddings-service/Dockerfile"
  "nixos-docs:ai-stack/mcp-servers/nixos-docs/Dockerfile"
  "dashboard-api:dashboard/backend/Dockerfile"
)

echo "Building and pushing images to $REGISTRY with tag $TAG..."

for service_config in "${SERVICES[@]}"; do
  service_name=$(echo $service_config | cut -d':' -f1)
  dockerfile_path=$(echo $service_config | cut -d':' -f2-)
  
  echo "Processing $service_name..."
  
  # Build the image
  docker build -t ai-stack-$service_name:$TAG -f $dockerfile_path . 
  
  # Tag for registry
  docker tag ai-stack-$service_name:$TAG $REGISTRY/ai-stack-$service_name:$TAG
  
  # Push to registry
  docker push $REGISTRY/ai-stack-$service_name:$TAG
  
  echo "Successfully pushed $service_name:$TAG to $REGISTRY"
done

echo "All images pushed successfully!"
```

### Kubernetes Deployment Configuration

Update Kubernetes deployments to use the registry images:

```yaml
# Example deployment configuration
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aidb
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aidb
  template:
    spec:
      containers:
      - name: aidb
        image: localhost:5000/ai-stack-aidb:dev  # Updated to use registry
        imagePullPolicy: Always  # Always pull latest from registry
```

### Environment Consistency

Ensure local/remote registry parity:

```bash
# Local development registry
LOCAL_REGISTRY=localhost:5000

# Staging registry
STAGING_REGISTRY=staging.registry.example.com

# Production registry  
PROD_REGISTRY=prod.registry.example.com

# Use environment variable to switch between registries
REGISTRY=${AI_STACK_REGISTRY:-$LOCAL_REGISTRY}

# Build and tag for current environment
docker build -t service-name:tag .
docker tag service-name:tag $REGISTRY/service-name:tag
docker push $REGISTRY/service-name:tag
```

### Verification Commands

```bash
# List images in local registry
curl -X GET http://localhost:5000/v2/_catalog

# Check specific repository tags
curl -X GET http://localhost:5000/v2/ai-stack-aidb/tags/list

# Verify images are available
docker images | grep ai-stack

# Test pulling from registry
docker pull localhost:5000/ai-stack-aidb:dev
```

### Best Practices

1. **Immutable Tags**: Use specific version tags instead of `latest`
2. **Digest Pinning**: For production, pin to specific image digests
3. **Multi-arch Support**: Build for target architectures
4. **Security Scanning**: Scan images before pushing
5. **Cleanup Policy**: Implement registry cleanup for old images

### Troubleshooting

#### Registry Not Accessible
```bash
# Check if registry is running
curl http://localhost:5000/v2/

# Check registry logs
kubectl logs -n default deployment/registry  # if running in K8s
```

#### Push Failures
```bash
# Check credentials
docker login localhost:5000

# Verify image exists locally
docker images | grep image-name
```

This completes the documentation for immutable image tagging and registry push flow for all services.