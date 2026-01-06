#!/usr/bin/env bash
# Download Cache Library with Integrity Checking
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Reusable download caching with SHA256 verification

DOWNLOAD_CACHE="${DOWNLOAD_CACHE:-${HOME}/.cache/nixos-quick-deploy/downloads}"
mkdir -p "$DOWNLOAD_CACHE"

# Download file with caching and integrity check
# Usage: cached_download URL DEST_FILE [EXPECTED_SHA256]
# Returns: 0 on success, 1 on failure
cached_download() {
    local url="$1"
    local dest="$2"
    local expected_sha256="${3:-}"

    if [ -z "$url" ] || [ -z "$dest" ]; then
        echo "✗ Usage: cached_download URL DEST_FILE [EXPECTED_SHA256]" >&2
        return 1
    fi

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
                    echo "✓ Using cached file (integrity verified): ${cache_file##*/}"
                    cp "$cache_file" "$dest"
                    return 0
                else
                    echo "⚠ Cached file corrupted (checksum mismatch), re-downloading..."
                    rm -f "$cache_file" "$cache_meta"
                fi
            else
                echo "✓ Using cached file: ${cache_file##*/}"
                cp "$cache_file" "$dest"
                return 0
            fi
        else
            echo "⚠ Cache metadata mismatch, re-downloading..."
            rm -f "$cache_file" "$cache_meta"
        fi
    fi

    # Download file
    echo "⬇ Downloading: $(basename "$url")"
    echo "  From: $url"

    # Create temporary file
    local temp_file="${cache_file}.tmp"

    if curl -fsSL --retry 5 --retry-delay 3 --connect-timeout 30 "$url" -o "$temp_file"; then
        # Verify integrity if checksum provided
        if [ -n "$expected_sha256" ]; then
            local actual_sha256=$(sha256sum "$temp_file" | awk '{print $1}')
            if [ "$actual_sha256" != "$expected_sha256" ]; then
                echo "✗ Download failed: checksum mismatch" >&2
                echo "  Expected: $expected_sha256" >&2
                echo "  Got:      $actual_sha256" >&2
                rm -f "$temp_file"
                return 1
            fi
            echo "✓ Download complete (integrity verified)"
        else
            echo "✓ Download complete (no integrity check)"
        fi

        # Move to cache and save metadata
        mv "$temp_file" "$cache_file"
        echo "$url" > "$cache_meta"

        # Copy to destination
        cp "$cache_file" "$dest"
        return 0
    else
        echo "✗ Download failed: $url" >&2
        rm -f "$temp_file"
        return 1
    fi
}

# Download and extract tarball with caching
# Usage: cached_download_extract URL DEST_DIR [EXPECTED_SHA256] [TAR_FLAGS]
cached_download_extract() {
    local url="$1"
    local dest_dir="$2"
    local expected_sha256="${3:-}"
    local tar_flags="${4:--xzf}"

    local temp_file="/tmp/download-$$.tar.gz"

    if cached_download "$url" "$temp_file" "$expected_sha256"; then
        mkdir -p "$dest_dir"
        if tar "$tar_flags" "$temp_file" -C "$dest_dir"; then
            echo "✓ Extracted to: $dest_dir"
            rm -f "$temp_file"
            return 0
        else
            echo "✗ Extraction failed" >&2
            rm -f "$temp_file"
            return 1
        fi
    else
        return 1
    fi
}

# Clear old cache entries (older than N days)
# Usage: cleanup_download_cache [DAYS] (default: 30)
cleanup_download_cache() {
    local days="${1:-30}"

    if [ ! -d "$DOWNLOAD_CACHE" ]; then
        echo "✓ Cache directory doesn't exist, nothing to clean"
        return 0
    fi

    echo "🧹 Cleaning download cache (files older than ${days} days)..."

    local count_before=$(find "$DOWNLOAD_CACHE" -type f | wc -l)
    find "$DOWNLOAD_CACHE" -type f -mtime +"$days" -delete
    local count_after=$(find "$DOWNLOAD_CACHE" -type f | wc -l)
    local removed=$((count_before - count_after))

    echo "✓ Removed $removed old cache entries"
    echo "  Cache location: $DOWNLOAD_CACHE"
    echo "  Remaining files: $count_after"
    echo "  Total size: $(du -sh "$DOWNLOAD_CACHE" 2>/dev/null | awk '{print $1}' || echo '0')"
}

# Show cache statistics
show_cache_stats() {
    if [ ! -d "$DOWNLOAD_CACHE" ]; then
        echo "Cache directory doesn't exist: $DOWNLOAD_CACHE"
        return 0
    fi

    local file_count=$(find "$DOWNLOAD_CACHE" -type f -name "*" ! -name "*.meta" | wc -l)
    local total_size=$(du -sh "$DOWNLOAD_CACHE" 2>/dev/null | awk '{print $1}' || echo '0')

    echo "Download Cache Statistics:"
    echo "  Location: $DOWNLOAD_CACHE"
    echo "  Files: $file_count"
    echo "  Total size: $total_size"

    if [ "$file_count" -gt 0 ]; then
        echo ""
        echo "Oldest files:"
        find "$DOWNLOAD_CACHE" -type f ! -name "*.meta" -printf '%T+ %s %p\n' | sort | head -5 | while read -r line; do
            local date=$(echo "$line" | awk '{print $1}')
            local size=$(echo "$line" | awk '{print $2}')
            local file=$(echo "$line" | awk '{print $3}')
            local size_mb=$((size / 1024 / 1024))
            echo "  $(basename "$file"): ${size_mb}MB (${date%%T*})"
        done
    fi
}

# Verify cached file integrity
# Usage: verify_cache_file CACHE_HASH EXPECTED_SHA256
verify_cache_file() {
    local cache_hash="$1"
    local expected_sha256="$2"
    local cache_file="${DOWNLOAD_CACHE}/${cache_hash}"

    if [ ! -f "$cache_file" ]; then
        echo "✗ Cache file not found: $cache_hash"
        return 1
    fi

    local actual_sha256=$(sha256sum "$cache_file" | awk '{print $1}')
    if [ "$actual_sha256" = "$expected_sha256" ]; then
        echo "✓ Cache file valid: $cache_hash"
        return 0
    else
        echo "✗ Cache file corrupted: $cache_hash"
        echo "  Expected: $expected_sha256"
        echo "  Got:      $actual_sha256"
        return 1
    fi
}
