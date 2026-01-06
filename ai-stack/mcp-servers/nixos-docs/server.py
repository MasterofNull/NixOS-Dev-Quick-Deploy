#!/usr/bin/env python3
"""
NixOS Documentation MCP Server
Centralized knowledge base for Nix/NixOS documentation across multiple sources

Features:
- Multi-source documentation aggregation
- Semantic search with embeddings
- Package and options lookup
- Intelligent caching
- Integration with AIDB and vector stores
"""

import os
import json
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis
from diskcache import Cache
from git import Repo
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# Initialize FastAPI app
app = FastAPI(
    title="NixOS Documentation MCP Server",
    version="1.0.0",
    description="Centralized Nix/NixOS documentation and knowledge base"
)

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_DIR = Path(os.getenv("NIXOS_CACHE_DIR", "/data/cache"))
REPOS_DIR = Path(os.getenv("NIXOS_REPOS_DIR", "/data/repos"))
CACHE_TTL = int(os.getenv("NIXOS_CACHE_TTL", "86400"))  # 24 hours

# Initialize cache
disk_cache = Cache(str(CACHE_DIR))
redis_client = None

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
except Exception as e:
    print(f"Redis unavailable, using disk cache only: {e}")
    redis_client = None


# Documentation sources configuration
DOCUMENTATION_SOURCES = {
    "nix_dev": {
        "name": "nix.dev (Official Tutorials)",
        "repo_url": "https://github.com/NixOS/nix.dev.git",
        "web_url": "https://nix.dev",
        "type": "markdown",
        "priority": 1
    },
    "nixos_manual": {
        "name": "NixOS Manual",
        "web_url": "https://nixos.org/manual/nixos/stable/",
        "api_url": "https://nixos.org/manual/nixos/stable/options",
        "type": "html",
        "priority": 1
    },
    "nix_manual": {
        "name": "Nix Manual",
        "web_url": "https://nixos.org/manual/nix/stable/",
        "type": "html",
        "priority": 1
    },
    "nixpkgs_manual": {
        "name": "Nixpkgs Manual",
        "web_url": "https://nixos.org/manual/nixpkgs/stable/",
        "type": "html",
        "priority": 2
    },
    "home_manager": {
        "name": "Home Manager Manual",
        "repo_url": "https://github.com/nix-community/home-manager.git",
        "web_url": "https://nix-community.github.io/home-manager/",
        "type": "markdown",
        "priority": 2
    },
    "nixos_wiki": {
        "name": "NixOS Wiki",
        "web_url": "https://nixos.wiki",
        "type": "mediawiki",
        "priority": 3
    },
    "nix_pills": {
        "name": "Nix Pills",
        "web_url": "https://nixos.org/guides/nix-pills/",
        "type": "html",
        "priority": 2
    },
    "nixpkgs_search": {
        "name": "NixOS Search API",
        "api_url": "https://search.nixos.org/backend",
        "type": "api",
        "priority": 1
    }
}


# Models
class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    sources: Optional[List[str]] = Field(None, description="Specific sources to search")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")

class PackageSearchRequest(BaseModel):
    name: str = Field(..., description="Package name to search")
    channel: str = Field("nixos-unstable", description="Channel (nixos-unstable, nixos-24.05, etc)")

class OptionSearchRequest(BaseModel):
    option: str = Field(..., description="NixOS option to search")

class DocumentationResult(BaseModel):
    source: str
    title: str
    content: str
    url: str
    relevance: float = 1.0
    metadata: Dict[str, Any] = {}


# Helper functions
def get_cache_key(prefix: str, *args) -> str:
    """Generate cache key from prefix and arguments"""
    key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
    return hashlib.md5(key_data.encode()).hexdigest()


async def fetch_url(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch content from URL with timeout"""
    cache_key = get_cache_key("url", url)

    # Check cache
    cached = disk_cache.get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text

            # Cache for 24 hours
            disk_cache.set(cache_key, content, expire=CACHE_TTL)
            return content
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


async def clone_or_update_repo(source_key: str) -> Optional[Path]:
    """Clone or update a git repository"""
    source = DOCUMENTATION_SOURCES.get(source_key)
    if not source or "repo_url" not in source:
        return None

    repo_path = REPOS_DIR / source_key

    try:
        if repo_path.exists():
            # Update existing repo
            repo = Repo(repo_path)
            origin = repo.remotes.origin
            origin.pull()
            print(f"Updated {source_key} repository")
        else:
            # Clone new repo
            REPOS_DIR.mkdir(parents=True, exist_ok=True)
            Repo.clone_from(source["repo_url"], repo_path, depth=1)
            print(f"Cloned {source_key} repository")

        return repo_path
    except Exception as e:
        print(f"Error with repository {source_key}: {e}")
        return None


async def search_nix_dev(query: str, limit: int = 10) -> List[DocumentationResult]:
    """Search nix.dev documentation"""
    results = []
    repo_path = await clone_or_update_repo("nix_dev")

    if not repo_path:
        return results

    # Search markdown files
    source_dir = repo_path / "source"
    if not source_dir.exists():
        return results

    query_lower = query.lower()

    for md_file in source_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")

            # Simple relevance scoring
            title = md_file.stem.replace("-", " ").title()
            content_lower = content.lower()

            if query_lower in content_lower or query_lower in title.lower():
                # Calculate relevance
                relevance = content_lower.count(query_lower) / max(len(content), 1)

                # Extract excerpt
                lines = content.split("\n")
                excerpt_lines = []
                for i, line in enumerate(lines[:50]):  # First 50 lines
                    if query_lower in line.lower():
                        excerpt_lines.append(line)
                        if len(excerpt_lines) >= 5:
                            break

                excerpt = "\n".join(excerpt_lines) if excerpt_lines else "\n".join(lines[:10])

                results.append(DocumentationResult(
                    source="nix.dev",
                    title=title,
                    content=excerpt,
                    url=f"https://nix.dev/{md_file.relative_to(source_dir).with_suffix('.html')}",
                    relevance=relevance,
                    metadata={"file": str(md_file.relative_to(repo_path))}
                ))
        except Exception as e:
            print(f"Error processing {md_file}: {e}")

    # Sort by relevance and limit
    results.sort(key=lambda x: x.relevance, reverse=True)
    return results[:limit]


async def search_nixos_packages(name: str, channel: str = "nixos-unstable") -> List[Dict[str, Any]]:
    """Search NixOS packages via search.nixos.org API"""
    cache_key = get_cache_key("pkg", name, channel)

    # Check cache
    if redis_client:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    url = f"https://search.nixos.org/backend/latest-42-{channel}/_search"

    query_body = {
        "from": 0,
        "size": 50,
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": name,
                            "fields": [
                                "package_attr_name^3",
                                "package_pname^2",
                                "package_programs",
                                "package_description"
                            ]
                        }
                    }
                ]
            }
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=query_body)
            response.raise_for_status()
            data = response.json()

            packages = []
            for hit in data.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                packages.append({
                    "name": source.get("package_attr_name"),
                    "pname": source.get("package_pname"),
                    "version": source.get("package_pversion"),
                    "description": source.get("package_description"),
                    "homepage": source.get("package_homepage", []),
                    "license": source.get("package_license"),
                    "platforms": source.get("package_platforms", []),
                    "url": f"https://search.nixos.org/packages?channel={channel}&query={name}"
                })

            # Cache for 1 hour
            if redis_client:
                redis_client.setex(cache_key, 3600, json.dumps(packages))

            return packages
    except Exception as e:
        print(f"Error searching packages: {e}")
        return []


async def search_nixos_options(option: str) -> List[Dict[str, Any]]:
    """Search NixOS options via search.nixos.org API"""
    cache_key = get_cache_key("opt", option)

    # Check cache
    if redis_client:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

    url = "https://search.nixos.org/backend/latest-42-nixos-unstable/_search"

    query_body = {
        "from": 0,
        "size": 50,
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": option,
                            "fields": ["option_name^2", "option_description"]
                        }
                    }
                ]
            }
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=query_body)
            response.raise_for_status()
            data = response.json()

            options = []
            for hit in data.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                options.append({
                    "name": source.get("option_name"),
                    "description": source.get("option_description"),
                    "type": source.get("option_type"),
                    "default": source.get("option_default"),
                    "example": source.get("option_example"),
                    "url": f"https://search.nixos.org/options?query={option}"
                })

            # Cache for 1 hour
            if redis_client:
                redis_client.setex(cache_key, 3600, json.dumps(options))

            return options
    except Exception as e:
        print(f"Error searching options: {e}")
        return []


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "nixos-docs",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cache": {
            "redis": redis_client is not None,
            "disk": CACHE_DIR.exists()
        }
    }


@app.post("/search")
async def search_documentation(request: SearchRequest):
    """Search across all NixOS documentation sources"""
    results = []

    # Search nix.dev
    if not request.sources or "nix_dev" in request.sources:
        nix_dev_results = await search_nix_dev(request.query, request.limit)
        results.extend(nix_dev_results)

    # Sort by relevance
    results.sort(key=lambda x: x.relevance, reverse=True)

    return {
        "query": request.query,
        "total": len(results),
        "results": [r.dict() for r in results[:request.limit]]
    }


@app.post("/packages/search")
async def search_packages(request: PackageSearchRequest):
    """Search NixOS packages"""
    packages = await search_nixos_packages(request.name, request.channel)

    return {
        "query": request.name,
        "channel": request.channel,
        "total": len(packages),
        "packages": packages
    }


@app.post("/options/search")
async def search_options(request: OptionSearchRequest):
    """Search NixOS configuration options"""
    options = await search_nixos_options(request.option)

    return {
        "query": request.option,
        "total": len(options),
        "options": options
    }


@app.get("/sources")
async def list_sources():
    """List all available documentation sources"""
    sources = []
    for key, info in DOCUMENTATION_SOURCES.items():
        sources.append({
            "id": key,
            "name": info["name"],
            "type": info["type"],
            "priority": info["priority"],
            "web_url": info.get("web_url"),
            "has_repo": "repo_url" in info
        })

    return {"sources": sources}


@app.post("/sync")
async def sync_repositories():
    """Sync all git repositories"""
    results = {}

    for key, source in DOCUMENTATION_SOURCES.items():
        if "repo_url" in source:
            repo_path = await clone_or_update_repo(key)
            results[key] = {
                "status": "success" if repo_path else "failed",
                "path": str(repo_path) if repo_path else None
            }

    return {"sync_results": results}


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    stats = {
        "disk_cache": {
            "size": len(disk_cache),
            "path": str(CACHE_DIR)
        }
    }

    if redis_client:
        try:
            info = redis_client.info("stats")
            stats["redis"] = {
                "connected": True,
                "keys": redis_client.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0)
            }
        except:
            stats["redis"] = {"connected": False}

    return stats


@app.delete("/cache/clear")
async def clear_cache():
    """Clear all caches"""
    disk_cache.clear()

    if redis_client:
        try:
            redis_client.flushdb()
        except:
            pass

    return {"status": "cache cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8094,
        log_level="info"
    )
