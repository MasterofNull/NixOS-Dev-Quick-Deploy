# Troubleshooting Runbooks

**Status:** Active (Phase 58+ Update)
**Owner:** AI Stack Maintainers
**Last Updated:** 2026-05-20
**Version:** 2.0.0

## Table of Contents

1. [Core Service Failures](#core-service-failures)
2. [Data Store Issues (Qdrant/Postgres)](#data-store-issues)
3. [Inference Performance](#inference-performance)
4. [Deployment Failures](#deployment-failures)
5. [Network & Firewall](#network-firewall)

---

## Core Service Failures

### Hybrid Coordinator (8003) Not Responding

**Symptom**: `aq-qa` Layer 2 fails. Requests to `http://localhost:8003/health` time out or return 500.

**Diagnosis**:
```bash
# Check service status
sudo systemctl status ai-hybrid-coordinator

# Check logs for crashes or API key errors
sudo journalctl -u ai-hybrid-coordinator -n 100 --no-pager

# Verify port binding
sudo ss -tuln | grep 8003
```

**Resolution**:
- **API Key Mismatch**: Ensure `/run/secrets/hybrid_coordinator_api_key` exists and is readable by the service.
- **Service Restart**: `sudo systemctl restart ai-hybrid-coordinator`
- **Port Conflict**: If port 8003 is taken, check `nix/modules/core/options.nix` and ensure no other process is bound.

---

## Data Store Issues

### Qdrant (6333) Connection Errors

**Symptom**: `aq-qa 1` fails. Logs show `Connection refused` for vector search.

**Diagnosis**:
```bash
# Check if Qdrant is running
sudo systemctl status qdrant

# Check disk space (Qdrant fails if disk is full)
df -h /var/lib/qdrant

# Verify collections
curl -s http://localhost:6333/collections | jq
```

**Resolution**:
- **Full Disk**: Clean up `/var/lib/qdrant/snapshots/` or expand the volume.
- **Index Corruption**: If a specific collection is corrupted, you may need to delete and re-index via `aq-memory reindex`.

### PostgreSQL (5432) Issues

**Symptom**: AIDB or Dashboard fails to load data. Logs show `Connection pool exhausted` or `Peer authentication failed`.

**Diagnosis**:
```bash
# Check Postgres status
sudo systemctl status postgresql

# Check active connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"
```

**Resolution**:
- **Too Many Connections**: Restart dependent services (`ai-aidb`, `dashboard-api`) to clear leaked connections.
- **Auth Failure**: Verify `services.postgresql.authentication` in your NixOS config allows `ident` or `trust` for local sockets.

---

## Inference Performance

### Slow Chat/Embedding Responses

**Symptom**: Inference takes > 3 minutes or fails with timeouts.

**Diagnosis**:
```bash
# Check VRAM usage
aq-llama-debug --check-vram

# Verify GPU layers
journalctl -u llama-cpp -n 100 | grep "llm_load_tensors"
```

**Resolution**:
- **CPU Fallback**: If `nvidia-smi` shows 0MB usage, the model didn't offload to GPU. Check `acceleration` setting in `mySystem.aiStack`.
- **Inference Hang**: Restart the inference engines:
  `sudo systemctl restart llama-cpp llama-cpp-embed`

---

## Deployment Failures

### `nixos-rebuild switch` Fails

**Symptom**: `./deploy` or `sudo nixos-rebuild switch` returns errors during build or activation.

**Diagnosis**:
```bash
# Check for Nix syntax errors
nix flake check

# View detailed build logs
sudo journalctl -u nix-daemon -n 100
```

**Resolution**:
- **Collision**: If files in `/etc` or `/var/lib` conflict, Nix will fail activation. Move the offending file and retry.
- **OOM during build**: Ensure you have at least 8GB of swap/RAM for large model evaluations.

---

## Network & Firewall

### Cannot Reach Dashboard (8888)

**Symptom**: Browser shows "Connection Refused" for the dashboard.

**Diagnosis**:
```bash
# Check if dashboard is bound to 127.0.0.1 or 0.0.0.0
sudo ss -tuln | grep 8888

# Check NixOS firewall status
sudo nft list ruleset | grep 8888
```

**Resolution**:
- **Bind Address**: If you need LAN access, set `mySystem.monitoring.commandCenter.bindAddress = "0.0.0.0";`.
- **Firewall**: Ensure `networking.firewall.allowedTCPPorts` includes 8888 and 8889.

---

**Next Steps**:
- Refer to [Operator Runbook](OPERATOR-RUNBOOK.md) for routine tasks.
- Refer to [System Overview](../agent-guides/00-SYSTEM-OVERVIEW.md) for architecture.
