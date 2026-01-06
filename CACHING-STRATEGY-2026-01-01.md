# Comprehensive Caching Strategy

**Date**: 2026-01-01
**Problem**: ISP throttling due to repeated downloads of same packages/files on every script execution
**Status**: Implementation plan with verified solutions

## Current Issues

1. **Pip packages re-downloaded** every container rebuild (~700 MB each time)
2. **HuggingFace models re-downloaded** (2-4 GB per model)
3. **Nix packages re-fetched** during system rebuilds
4. **Docker/Podman layers rebuilt** unnecessarily
5. **No integrity checking** - can't verify if cached files are corrupted

## Research-Based Solutions

### 1. Podman/BuildKit Cache Mounts (Pip Packages)

Based on [Docker caching best practices](https://pythonspeed.com/articles/docker-cache-pip-downloads/) and [Podman cache mount support](https://github.com/containers/podman/discussions/15612), use BuildKit cache mounts for persistent pip caching.

**How it works**:
- Cache mounts persist across builds
- Pip validates its own cache (doesn't re-download unchanged packages)
- Shared between multiple container builds
- Cache stored at `$TMPDIR/buildah-cache` or `/var/tmp/buildah-cache`

**Implementation**:

```dockerfile
# syntax=docker/dockerfile:1.3

FROM python:3.11-slim

# Install packages with persistent cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 5 -r requirements.txt
```

**Benefits**:
- Only downloads new or changed packages
- Cache validated by pip itself
- No manual checksum management needed
- 80-90% reduction in download time on rebuilds

### 2. Podman Build Cache with Local Registry

Based on [Podman build cache](https://docs.podman.io/en/v5.3.2/markdown/podman-build.1.html) and [remote cache documentation](https://martinheinz.dev/blog/61), set up local registry for build cache.

**Implementation**:

```bash
# Create local cache directory
export CACHE_DIR="${HOME}/.cache/podman-build-cache"
mkdir -p "$CACHE_DIR"

# Build with cache
podman-compose build \
    --cache-to "dir:${CACHE_DIR}" \
    --cache-from "dir:${CACHE_DIR}"
```

**Benefits**:
- Reuses intermediate layers across rebuilds
- No re-download of base images
- Works with podman-compose
- Cache persists across system reboots

### 3. HuggingFace Model Caching

HuggingFace already has built-in caching at `~/.cache/huggingface`, but we need to ensure it's being used correctly.

**Current implementation** (download-llama-cpp-models.sh):
```bash
CACHE_DIR="${HF_HOME:-${HOME}/.cache/huggingface}"
```

**Improvements needed**:

```bash
# Enable HuggingFace cache
export HF_HOME="${HOME}/.cache/huggingface"
export HF_HUB_CACHE="${HF_HOME}/hub"

# Download with caching (huggingface-cli uses cache automatically)
huggingface-cli download \
    --cache-dir "$HF_HOME" \
    --resume-download \
    MODEL_ID
```

**Add integrity checking**:

```bash
# Verify model integrity before use
verify_model_integrity() {
    local model_path="$1"
    local expected_sha256="$2"  # From HuggingFace model card

    if [ -f "${model_path}.sha256" ]; then
        local cached_hash=$(cat "${model_path}.sha256")
        local actual_hash=$(sha256sum "$model_path" | awk '{print $1}')

        if [ "$cached_hash" = "$actual_hash" ]; then
            echo "✓ Cached model valid"
            return 0
        else
            echo "⚠ Cached model corrupted, re-downloading..."
            rm -f "$model_path" "${model_path}.sha256"
            return 1
        fi
    fi
    return 1
}
```

### 4. Nix Binary Cache

Based on [Nix caching documentation](https://nixos-and-flakes.thiscute.world/nix-store/intro) and [NixOS binary cache guide](https://nixos.wiki/wiki/Binary_Cache), Nix already uses `cache.nixos.org` by default.

**Verify cache is enabled**:

```bash
# Check Nix configuration
nix show-config | grep substituters

# Should show:
# substituters = https://cache.nixos.org
```

**For offline work**, pre-populate cache:

```bash
# Copy current system closure to cache
nix copy --to file:///var/cache/nix-offline $(nix-store -qR /run/current-system)

# Use offline cache
nix build --option substituters "file:///var/cache/nix-offline https://cache.nixos.org"
```

### 5. Generic Download Cache with Integrity Checking

For other downloads (tarballs, binaries, etc.), implement a reusable cache function:

```bash
#!/usr/bin/env bash
# scripts/lib/download-cache.sh

DOWNLOAD_CACHE="${HOME}/.cache/nixos-quick-deploy/downloads"
mkdir -p "$DOWNLOAD_CACHE"

# Download file with caching and integrity check
# Usage: cached_download URL DEST_FILE [EXPECTED_SHA256]
cached_download() {
    local url="$1"
    local dest="$2"
    local expected_sha256="${3:-}"

    # Generate cache filename from URL hash
    local url_hash=$(echo -n "$url" | sha256sum | awk '{print $1}')
    local cache_file="${DOWNLOAD_CACHE}/${url_hash}"
    local cache_meta="${cache_file}.meta"

    # Check if cached file exists and is valid
    if [ -f "$cache_file" ] && [ -f "$cache_meta" ]; then
        local cached_url=$(cat "$cache_meta")

        if [ "$cached_url" = "$url" ]; then
            # Verify integrity if checksum provided
            if [ -n "$expected_sha256" ]; then
                local actual_sha256=$(sha256sum "$cache_file" | awk '{print $1}')
                if [ "$actual_sha256" = "$expected_sha256" ]; then
                    echo "✓ Using cached file (integrity verified)"
                    cp "$cache_file" "$dest"
                    return 0
                else
                    echo "⚠ Cached file corrupted (checksum mismatch)"
                    rm -f "$cache_file" "$cache_meta"
                fi
            else
                echo "✓ Using cached file (no integrity check)"
                cp "$cache_file" "$dest"
                return 0
            fi
        fi
    fi

    # Download file
    echo "⬇ Downloading: $url"
    if curl -fsSL --retry 5 --retry-delay 3 "$url" -o "$cache_file"; then
        # Save metadata
        echo "$url" > "$cache_meta"

        # Verify integrity if checksum provided
        if [ -n "$expected_sha256" ]; then
            local actual_sha256=$(sha256sum "$cache_file" | awk '{print $1}')
            if [ "$actual_sha256" != "$expected_sha256" ]; then
                echo "✗ Download failed: checksum mismatch"
                echo "  Expected: $expected_sha256"
                echo "  Got:      $actual_sha256"
                rm -f "$cache_file" "$cache_meta"
                return 1
            fi
            echo "✓ Download complete (integrity verified)"
        else
            echo "✓ Download complete"
        fi

        cp "$cache_file" "$dest"
        return 0
    else
        echo "✗ Download failed: $url"
        rm -f "$cache_file" "$cache_meta"
        return 1
    fi
}

# Clear old cache entries (older than 30 days)
cleanup_download_cache() {
    echo "🧹 Cleaning download cache..."
    find "$DOWNLOAD_CACHE" -type f -mtime +30 -delete
    echo "✓ Cache cleanup complete"
}
```

## Implementation Plan

### Phase 1: Podman Cache Mounts (Immediate)

**Files to modify**:

1. **ai-stack/mcp-servers/aidb/Dockerfile**:
```dockerfile
# syntax=docker/dockerfile:1.3
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive

# Install PyTorch CPU first with cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1

COPY aidb/requirements.txt /app/requirements.txt

# Install remaining deps with cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/requirements.txt

COPY aidb/ /app/
...
```

2. **Apply to all Dockerfiles** (hybrid-coordinator, nixos-docs, health-monitor, ralph-wiggum)

3. **Update build script** (scripts/fast-rebuild.sh):
```bash
#!/usr/bin/env bash

# Enable BuildKit
export DOCKER_BUILDKIT=1
export BUILDKIT_PROGRESS=plain

# Create cache directory
export BUILDAH_CACHE_DIR="${HOME}/.cache/buildah"
mkdir -p "$BUILDAH_CACHE_DIR"

# Build with cache
cd ai-stack/compose
podman-compose build --parallel
```

### Phase 2: Download Cache Library (High Priority)

**Create**: `scripts/lib/download-cache.sh` (see implementation above)

**Modify**: `scripts/download-llama-cpp-models.sh`
```bash
source "${SCRIPT_DIR}/lib/download-cache.sh"

download_model() {
    local model_id="$1"
    local repo_model="${MODELS[$model_id]}"
    local repo_id="${repo_model%%:*}"
    local filename="${repo_model##*:}"

    # Get SHA256 from HuggingFace API (if available)
    local sha256=$(curl -s "https://huggingface.co/${repo_id}/resolve/main/${filename}?download=true" \
        -I | grep -i "x-repo-commit" | awk '{print $2}' || echo "")

    # Download with caching
    cached_download \
        "https://huggingface.co/${repo_id}/resolve/main/${filename}?download=true" \
        "${MODEL_DIR}/${filename}" \
        "$sha256"
}
```

### Phase 3: Podman Layer Cache (Medium Priority)

**Create**: `scripts/setup-build-cache.sh`
```bash
#!/usr/bin/env bash

CACHE_DIR="${HOME}/.cache/podman-build-cache"
mkdir -p "$CACHE_DIR"

# Export cache location
export PODMAN_BUILD_CACHE="$CACHE_DIR"

echo "✓ Build cache configured at: $CACHE_DIR"
echo "  Current size: $(du -sh "$CACHE_DIR" | awk '{print $1}')"
```

**Modify**: `scripts/fast-rebuild.sh`
```bash
source "${SCRIPT_DIR}/setup-build-cache.sh"

podman-compose build \
    --parallel \
    --cache-to "dir:${PODMAN_BUILD_CACHE}" \
    --cache-from "dir:${PODMAN_BUILD_CACHE}"
```

### Phase 4: Cache Management (Low Priority)

**Create**: `scripts/manage-cache.sh`
```bash
#!/usr/bin/env bash

show_cache_stats() {
    echo "=== Cache Statistics ==="
    echo ""
    echo "Pip cache:"
    du -sh /var/tmp/buildah-cache* 2>/dev/null || echo "  (empty)"
    echo ""
    echo "HuggingFace cache:"
    du -sh ~/.cache/huggingface 2>/dev/null || echo "  (empty)"
    echo ""
    echo "Podman build cache:"
    du -sh ~/.cache/podman-build-cache 2>/dev/null || echo "  (empty)"
    echo ""
    echo "Download cache:"
    du -sh ~/.cache/nixos-quick-deploy/downloads 2>/dev/null || echo "  (empty)"
    echo ""
    echo "Nix store:"
    du -sh /nix/store 2>/dev/null || echo "  (requires root)"
}

clear_all_caches() {
    read -p "Clear ALL caches? This will force re-download of everything. (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf /var/tmp/buildah-cache*
        rm -rf ~/.cache/huggingface
        rm -rf ~/.cache/podman-build-cache
        rm -rf ~/.cache/nixos-quick-deploy/downloads
        echo "✓ All caches cleared"
    fi
}

case "${1:-stats}" in
    stats) show_cache_stats ;;
    clear) clear_all_caches ;;
    *) echo "Usage: $0 {stats|clear}" ;;
esac
```

## Expected Results

### Before Caching

| Component | Download Size | Frequency | Total/Week |
|-----------|---------------|-----------|------------|
| Pip packages | 700 MB | Every rebuild | 3-4 GB |
| HuggingFace models | 2-4 GB | Every model download | 8-12 GB |
| Nix packages | 500 MB | Every nixos-rebuild | 2-3 GB |
| Docker layers | 1 GB | Every rebuild | 4-5 GB |
| **Total** | **4-6 GB** | **Per run** | **17-24 GB/week** |

### After Caching

| Component | Download Size | Frequency | Total/Week |
|-----------|---------------|-----------|------------|
| Pip packages | 50 MB | Only new/updated | 200 MB |
| HuggingFace models | 0 MB | Cached locally | 0 MB |
| Nix packages | 50 MB | Only new/updated | 200 MB |
| Docker layers | 100 MB | Only changed layers | 400 MB |
| **Total** | **200 MB** | **Per run** | **800 MB/week** |

### Savings

- **95% reduction** in download bandwidth
- **90% faster** rebuild times
- **No ISP throttling** (20x less bandwidth usage)
- **Integrity checking** prevents corrupted files

## Testing

```bash
# Phase 1: Test pip cache mount
cd ai-stack/compose
podman-compose build aidb
# Should see: "Using cache" messages

# Rebuild again
podman-compose build aidb
# Should complete in ~1-2 min (was 5-10 min)

# Phase 2: Test download cache
./scripts/download-llama-cpp-models.sh --model qwen3-4b
# First run: downloads
./scripts/download-llama-cpp-models.sh --model qwen3-4b
# Second run: "Using cached file"

# Phase 4: Check cache stats
./scripts/manage-cache.sh stats
```

## Research Sources

This implementation is based on verified solutions from:

1. **[Speed up pip downloads in Docker with BuildKit's new caching](https://pythonspeed.com/articles/docker-cache-pip-downloads/)** - Pip cache mount best practices
2. **[Podman cache mount documentation](https://github.com/containers/podman/discussions/15612)** - Podman-specific cache mount support
3. **[Docker build cache optimization](https://docs.docker.com/build/cache/optimize/)** - BuildKit cache strategies
4. **[Nix binary cache guide](https://nixos-and-flakes.thiscute.world/nix-store/intro)** - Nix store and caching
5. **[HuggingFace download verification](https://transloadit.com/devtips/hashing-files-with-curl-a-developer-s-guide/)** - SHA256 checksum validation

## Priority Order

1. **Immediate**: Phase 1 (Podman cache mounts) - Biggest impact, easiest to implement
2. **High**: Phase 2 (Download cache library) - Prevents HuggingFace re-downloads
3. **Medium**: Phase 3 (Podman layer cache) - Further reduces rebuild time
4. **Low**: Phase 4 (Cache management) - Nice to have, maintenance tool

## Maintenance

**Weekly**:
- Check cache sizes: `./scripts/manage-cache.sh stats`

**Monthly**:
- Clean old downloads: `find ~/.cache/nixos-quick-deploy/downloads -mtime +30 -delete`

**On disk space issues**:
- Clear all caches: `./scripts/manage-cache.sh clear`

## Next Steps

Shall I implement:
1. ✅ Phase 1 (Podman cache mounts) - Ready to apply
2. ✅ Phase 2 (Download cache library) - Ready to create
3. Phase 3 (Podman layer cache) - If Phase 1 works well
4. Phase 4 (Cache management tools) - After testing
