# Portainer Setup and Validation

## Initial Portainer Login and Wizard Reset

This document provides guidance for setting up and validating Portainer in the NixOS AI Stack deployment.

### Initial Setup

#### Access Portainer
1. **URL**: Navigate to `http://<your-host>:9000` (or the configured Portainer port)
2. **Default Port**: Usually 9000 unless changed in configuration
3. **Connection**: Ensure the port is accessible from your client machine

#### Initial Wizard Flow
1. **Admin User Creation**:
   - Username: `admin` (or preferred admin username)
   - Password: Strong password (minimum 8 characters)
   - Confirm Password: Same as above

2. **Environment Selection**:
   - Choose "Docker" if connecting to Docker environment
   - Choose "Kubernetes" if connecting to Kubernetes cluster
   - For this setup, select "Kubernetes" since we're using K3s

3. **Kubernetes Connection**:
   - Select "Connect to existing cluster"
   - Portainer will use the in-cluster configuration to connect to K3s

### Validation Steps

#### 1. Login Validation
```bash
# Verify Portainer is accessible
curl -I http://localhost:9000

# Check if Portainer is running in K8s
kubectl get pods -n portainer
kubectl get svc -n portainer
```

#### 2. Dashboard Access
1. Log into Portainer with admin credentials
2. Verify the dashboard loads correctly
3. Check that the Kubernetes cluster is detected
4. Verify namespace visibility (ai-stack, default, kube-system, etc.)

#### 3. Resource Management
1. Navigate to "Kubernetes" section
2. Verify you can see:
   - Namespaces (ai-stack, backups, monitoring)
   - Deployments in ai-stack namespace
   - Services and pods
   - ConfigMaps and Secrets

#### 4. Deployment Management
1. Test viewing existing deployments:
   - aidb
   - hybrid-coordinator
   - ralph-wiggum
   - embeddings
   - nixos-docs
2. Verify you can see pod status and logs
3. Test scaling a deployment up/down

### Common Portainer Tasks for AI Stack

#### View AI Stack Resources
1. Go to Kubernetes → Namespaces → Select "ai-stack"
2. View Deployments, Services, Pods, ConfigMaps, Secrets
3. Check resource utilization and status

#### Manage Deployments
1. Navigate to Deployments in ai-stack namespace
2. View deployment status and pod count
3. Scale deployments up/down as needed
4. Restart deployments if necessary

#### Monitor Resources
1. Use the "Resources" view to see cluster utilization
2. Check CPU and memory usage
3. Monitor storage usage

### Troubleshooting

#### Portainer Not Accessible
```bash
# Check if Portainer pod is running
kubectl get pods -n portainer

# Check Portainer service
kubectl get svc -n portainer

# Check Portainer logs
kubectl logs -n portainer deployment/portainer

# Port-forward if needed
kubectl port-forward -n portainer svc/portainer 9000:9000
```

#### Login Issues
1. **Forgot Password**: If you forgot the admin password, you can reset it:
   ```bash
   # Get the Portainer pod name
   POD_NAME=$(kubectl get pods -n portainer -o jsonpath='{.items[0].metadata.name}')
   
   # Execute password reset (if supported by Portainer version)
   kubectl exec -n portainer $POD_NAME -- /portainer --clean
   ```

2. **Connection Issues**: Verify the Kubernetes connection:
   - Check if the Portainer pod has proper service account permissions
   - Verify RBAC configuration

#### Wizard Reset Procedure
If you need to reset the initial setup wizard:

1. **Delete Portainer deployment and recreate**:
   ```bash
   kubectl delete -n portainer deployment/portainer
   kubectl delete -n portainer svc/portainer
   # Then redeploy using your original manifest
   ```

2. **Alternative**: If Portainer supports it, look for reset options in settings

### Security Best Practices

1. **Change Default Credentials**: Always change the default admin password
2. **Enable Authentication**: Ensure authentication is required
3. **RBAC**: Configure proper role-based access control
4. **Network Security**: Restrict access to Portainer interface
5. **Regular Updates**: Keep Portainer updated to latest version

### Integration with AI Stack

#### View AI Stack Status
1. Use Portainer to monitor the health of AI stack services
2. Check pod status and restart if needed
3. Monitor resource usage of AI services
4. View logs for debugging

#### Deployment Operations
1. Scale AI services up/down based on demand
2. Update image tags for deployments
3. Rollback deployments if needed
4. Check deployment history

### Expected Validation Results

After completing the Portainer setup and validation:

- [ ] Successfully logged into Portainer
- [ ] Initial wizard completed
- [ ] Kubernetes cluster detected and connected
- [ ] ai-stack namespace visible
- [ ] All AI stack deployments visible in Portainer
- [ ] Can view pod status and logs
- [ ] Can perform basic management operations

This completes the validation of Portainer login and initial wizard reset flow.