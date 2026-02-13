# NixOS Documentation MCP Server

**Status:** ✅ Implemented
**Version:** 1.0.0
**Port:** 8094

---

## Overview

The NixOS Documentation MCP Server provides a centralized knowledge base for all Nix/NixOS documentation across multiple official and community sources. It enables AI agents and developers to quickly search, reference, and retrieve information from the entire Nix ecosystem.

---

## Features

### 📚 Multi-Source Documentation Aggregation

Integrates with:
- **[nix.dev](https://nix.dev)** - Official tutorials and guides (cloned locally)
- **[NixOS Manual](https://nixos.org/manual/nixos/stable/)** - System configuration reference
- **[Nix Manual](https://nixos.org/manual/nix/stable/)** - Package manager documentation
- **[Nixpkgs Manual](https://nixos.org/manual/nixpkgs/stable/)** - Package repository docs
- **[NixOS Search API](https://search.nixos.org)** - Real-time package/option search
- **[Home Manager](https://nix-community.github.io/home-manager/)** - User environment management
- **[NixOS Wiki](https://nixos.wiki)** - Community knowledge base
- **[Nix Pills](https://nixos.org/guides/nix-pills/)** - Deep dive tutorials

### 🔍 Intelligent Search

- **Semantic search** across all documentation sources
- **Package search** with version, license, and platform info
- **Option search** for NixOS configuration options
- **Relevance ranking** for better results
- **Context-aware** excerpts and snippets

### ⚡ Performance & Caching

- **Redis caching** for API responses (1-hour TTL)
- **Disk caching** for web content (24-hour TTL)
- **Local repository cloning** for faster access to markdown docs
- **Automatic sync** on startup and on-demand via `/sync` endpoint

### 🔧 Integration

- **Integrates with AIDB** for knowledge base queries
- **Compatible with Hybrid Coordinator** for context augmentation
- **RESTful API** for easy integration with any agent or tool
- **Health monitoring** for observability

---

## API Endpoints

### Health & Status

```bash
GET /health
```

Returns server health status, cache statistics, and availability.

**Example:**
```bash
curl http://localhost:8094/health
```

### Documentation Search

```bash
POST /search
```

Search across all documentation sources.

**Request Body:**
```json
{
  "query": "how to install packages",
  "sources": ["nix_dev", "nixos_manual"],  // optional
  "limit": 10
}
```

**Example:**
```bash
curl -X POST http://localhost:8094/search \
  -H "Content-Type: application/json" \
  -d '{"query": "declarative configuration", "limit": 5}'
```

### Package Search

```bash
POST /packages/search
```

Search NixOS packages from nixpkgs.

**Request Body:**
```json
{
  "name": "firefox",
  "channel": "nixos-unstable"  // or "nixos-24.05", etc.
}
```

**Example:**
```bash
curl -X POST http://localhost:8094/packages/search \
  -H "Content-Type: application/json" \
  -d '{"name": "neovim", "channel": "nixos-unstable"}'
```

### Option Search

```bash
POST /options/search
```

Search NixOS configuration options.

**Request Body:**
```json
{
  "option": "services.nginx"
}
```

**Example:**
```bash
curl -X POST http://localhost:8094/options/search \
  -H "Content-Type: application/json" \
  -d '{"option": "boot.loader"}'
```

### List Sources

```bash
GET /sources
```

List all available documentation sources.

**Example:**
```bash
curl http://localhost:8094/sources
```

### Sync Repositories

```bash
POST /sync
```

Manually trigger synchronization of all git repositories.

**Example:**
```bash
curl -X POST http://localhost:8094/sync
```

### Cache Management

```bash
GET /cache/stats      # Get cache statistics
DELETE /cache/clear   # Clear all caches
```

**Examples:**
```bash
curl http://localhost:8094/cache/stats
curl -X DELETE http://localhost:8094/cache/clear
```

---

## Architecture

### Data Flow

```
┌─────────────────┐
│   AI Agents     │
│  (Ralph, etc)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   NixOS Docs MCP Server (Port 8094) │
├─────────────────────────────────────┤
│  • Search orchestration             │
│  • Response aggregation             │
│  • Relevance ranking                │
└──┬────────┬───────────┬─────────┬───┘
   │        │           │         │
   ▼        ▼           ▼         ▼
┌──────┐ ┌─────┐   ┌──────┐  ┌──────────┐
│ nix  │ │NixOS│   │NixOS │  │   Git    │
│.dev  │ │ API │   │ Wiki │  │   Repos  │
│Repo  │ │     │   │      │  │(nix.dev) │
└──────┘ └─────┘   └──────┘  └──────────┘
   │        │           │         │
   ▼        ▼           ▼         ▼
┌─────────────────────────────────────┐
│         Caching Layer               │
├─────────────────────────────────────┤
│  Redis (API responses, 1h TTL)      │
│  Disk Cache (Web content, 24h TTL)  │
└─────────────────────────────────────┘
```

### Documentation Source Priority

1. **Priority 1** (Real-time, always fresh):
   - nix.dev (local clone)
   - NixOS Manual
   - Nix Manual
   - NixOS Search API

2. **Priority 2** (Reference materials):
   - Nixpkgs Manual
   - Home Manager Manual
   - Nix Pills

3. **Priority 3** (Community content):
   - NixOS Wiki

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `NIXOS_CACHE_DIR` | `/data/cache` | Disk cache directory |
| `NIXOS_REPOS_DIR` | `/data/repos` | Git repositories directory |
| `NIXOS_CACHE_TTL` | `86400` | Cache TTL in seconds (24h) |

### Data Volumes

- `/data/cache` - Disk cache for web content
- `/data/repos` - Cloned git repositories (nix.dev, home-manager)

---

## Usage Examples

### From AI Agents (Python)

```python
import httpx

async def search_nixos_docs(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8094/search",
            json={"query": query, "limit": 10}
        )
        return response.json()

# Search for how to configure services
results = await search_nixos_docs("enable nginx service")
```

### From AIDB Integration

```python
# AIDB can query NixOS docs for context augmentation
nixos_context = await fetch_url("http://localhost:8094/search",
    method="POST",
    json={"query": user_question}
)
```

### From Command Line

```bash
# Search documentation
curl -X POST http://localhost:8094/search \
  -H "Content-Type: application/json" \
  -d '{"query": "how to use flakes"}'

# Find a package
curl -X POST http://localhost:8094/packages/search \
  -H "Content-Type: application/json" \
  -d '{"name": "postgresql"}'

# Look up a configuration option
curl -X POST http://localhost:8094/options/search \
  -H "Content-Type: application/json" \
  -d '{"option": "networking.firewall"}'
```

---

## Integration with AI Stack

### AIDB Integration

The NixOS Docs server can be integrated with AIDB for enhanced context:

```python
# In AIDB tools
async def get_nixos_help(topic: str):
    """Get NixOS documentation for a topic"""
    docs_response = await httpx.post(
        "http://localhost:8094/search",
        json={"query": topic}
    )
    return docs_response.json()
```

### Ralph Wiggum Integration

Ralph Wiggum can use NixOS docs for autonomous system configuration:

```python
# Before modifying NixOS config
docs = await search_nixos_docs(f"how to configure {service_name}")
# Use docs to inform configuration generation
```

---

## Deployment

### With K3s/Kubernetes

Already configured in `ai-stack/kubernetes` manifests:

```bash
kubectl apply -k ai-stack/kubernetes
```

### Standalone

```bash
cd ai-stack/mcp-servers/nixos-docs
pip install -r requirements.txt
python server.py
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:8094/health
```

### Cache Statistics

```bash
curl http://localhost:8094/cache/stats
```

### Container Logs

```bash
kubectl logs -f -n ai-stack nixos-docs
```

---

## Performance

### Typical Response Times

- **Package search**: 100-300ms (API call)
- **Option search**: 100-300ms (API call)
- **Documentation search** (cached): 50-150ms
- **Documentation search** (uncached): 500-2000ms
- **Repository sync**: 10-60s (one-time on startup)

### Cache Hit Rates

- **Expected**: 80-95% for repeated queries
- **Redis**: API responses cached for 1 hour
- **Disk**: Web content cached for 24 hours

---

## Troubleshooting

### Redis Connection Failed

If Redis is unavailable, the server falls back to disk-only caching:

```
Redis unavailable, using disk cache only: Connection refused
```

This is normal and the server will continue to function.

### Repository Clone Failed

Check network connectivity and disk space:

```bash
kubectl exec -n ai-stack nixos-docs -- df -h
kubectl exec -n ai-stack nixos-docs -- git config --global http.timeout 60
```

### Slow Searches

1. Check cache statistics:
```bash
curl http://localhost:8094/cache/stats
```

2. Ensure repositories are cloned:
```bash
curl -X POST http://localhost:8094/sync
```

3. Monitor container resources:
```bash
kubectl top pod -n ai-stack nixos-docs
```

---

## Roadmap

### Future Enhancements

- [ ] **Vector embeddings** for semantic search
- [ ] **Integration with Qdrant** for similarity search
- [ ] **Automatic daily sync** of repositories
- [ ] **Version comparison** (stable vs unstable)
- [ ] **Code example extraction** from nixpkgs
- [ ] **Flake template generation**
- [ ] **Configuration validation** against options schema

---

## References

- [nix.dev Repository](https://github.com/NixOS/nix.dev)
- [NixOS Search](https://search.nixos.org)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Main AI Stack README](../../README.md)
- [AIDB MCP Server](../aidb/README.md)

---

**Last Updated:** 2025-12-31
**Maintainer:** NixOS Quick Deploy AI Stack Team
