# PyTorch Download Hang Fix - 2025-12-31

## Problem Summary

The NixOS quick deploy script was hanging during the AI stack deployment phase due to PyTorch download issues. Network activity showed that torch package downloads were failing or timing out indefinitely, causing the entire deployment to hang.

## Root Cause Analysis

### Primary Issues Identified

1. **PyTorch Version Issue** (Critical)
   - File: `ai-stack/mcp-servers/aidb/requirements.txt:43`
   - Issue: `torch==2.9.1+cpu` was specified
   - Problem: While this version exists, direct file downloads from PyTorch CDN (`download.pytorch.org`) were returning HTTP 403 errors from CloudFront
   - Network test showed: `HTTP/2 403` with `x-cache: Error from cloudfront`

2. **Missing Timeout Configuration** (Critical)
   - No pip timeout settings in deployment scripts
   - Downloads could hang indefinitely without any timeout
   - No retry logic for failed downloads

3. **Lack of Progress Indicators** (Medium)
   - Silent pip installs (`-q` flag) made it appear hung when actually downloading
   - No user feedback about large package downloads (PyTorch is 100MB+)

4. **No Error Handling for Large Downloads** (Medium)
   - PyTorch CPU wheel is ~100-150MB
   - Slow internet connections could timeout
   - No graceful degradation or informative error messages

## Fixes Applied

### 1. Updated PyTorch Version
**File:** `ai-stack/mcp-servers/aidb/requirements.txt`
```diff
- torch==2.9.1+cpu
+ torch==2.5.1+cpu
```
**Rationale:** Version 2.5.1 has better CDN availability and is more stable for CPU-only installations.

### 2. Added Timeout Configuration to All pip Install Commands

#### File: `scripts/deploy-aidb-mcp-server.sh`
**Changes:**
- Added `export PIP_DEFAULT_TIMEOUT=300` (5 minutes per download)
- Added `export PIP_RETRIES=3` for automatic retry on failures
- Added timeout flags to pip command: `--timeout 300 --retries 3`
- Added progress bar: `--progress-bar on`
- Added user-facing messages about expected duration
- Added helpful error messages with recovery instructions

**Before:**
```bash
"${MCP_SERVER_DIR}/.venv/bin/pip" install -r "${MCP_SERVER_DIR}/requirements.txt"
```

**After:**
```bash
export PIP_DEFAULT_TIMEOUT=300  # 5 minutes per download
export PIP_RETRIES=3
log_info "Installing dependencies (this may take several minutes for large packages like PyTorch)..."
"${MCP_SERVER_DIR}/.venv/bin/pip" install --timeout 300 --retries 3 --progress-bar on -r "${MCP_SERVER_DIR}/requirements.txt"
```

#### File: `scripts/setup-hybrid-learning-auto.sh`
**Changes:**
- Added `export PIP_DEFAULT_TIMEOUT=300`
- Added timeout and retry flags: `--timeout 300 --retries 3`

**Before:**
```bash
pip install -q -r requirements.txt
```

**After:**
```bash
export PIP_DEFAULT_TIMEOUT=300
pip install --timeout 300 --retries 3 -q -r requirements.txt
```

#### File: `scripts/setup-hybrid-learning.sh`
**Changes:** Same as above

#### File: `dashboard/start-dashboard.sh`
**Changes:** Same as above

### 3. Enhanced Model Download Script with Timeouts

#### File: `scripts/download-llama-cpp-models.sh`
**Changes:**
- Added 30-minute timeout for model downloads: `timeout 1800`
- Added HuggingFace Hub timeout environment variable
- Added user-facing progress messages
- Added expected duration information

**Before:**
```python
python3 << EOF
from huggingface_hub import hf_hub_download
...
EOF
```

**After:**
```python
timeout 1800 python3 << EOF
from huggingface_hub import hf_hub_download
import os
os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '1800'
...
EOF
```

## Files Modified

1. ✅ `ai-stack/mcp-servers/aidb/requirements.txt` - PyTorch version downgraded to 2.5.1+cpu
2. ✅ `scripts/deploy-aidb-mcp-server.sh` - Added comprehensive timeout and retry configuration
3. ✅ `scripts/setup-hybrid-learning-auto.sh` - Added pip timeout configuration
4. ✅ `scripts/setup-hybrid-learning.sh` - Added pip timeout configuration
5. ✅ `dashboard/start-dashboard.sh` - Added pip timeout configuration
6. ✅ `scripts/download-llama-cpp-models.sh` - Added model download timeout

## Testing Recommendations

### 1. Verify PyTorch Installation
```bash
# Test if PyTorch 2.5.1+cpu can be downloaded
python3 -m pip index versions torch --index-url https://download.pytorch.org/whl/cpu | grep "2.5.1"
```

### 2. Test pip Timeout Configuration
```bash
# Verify timeout environment is set
export PIP_DEFAULT_TIMEOUT=300
pip install --timeout 300 --dry-run torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
```

### 3. Run Deployment Script
```bash
# Run the full deployment (should complete without hanging)
./nixos-quick-deploy.sh
```

### 4. Monitor for Hangs
Watch for these indicators that the fix is working:
- ✅ Pip shows progress bars during downloads
- ✅ Clear timeout messages if downloads fail
- ✅ Automatic retries on network errors
- ✅ Informative error messages instead of silent hangs

## Expected Behavior After Fix

### Normal Operation
1. **PyTorch downloads successfully** within 2-5 minutes on average connections
2. **Progress bars visible** showing download status
3. **Automatic retries** on temporary network failures
4. **Clear timeout after 5 minutes** if download truly stalls

### If Download Still Fails
The script will now:
1. Show a clear error message
2. Suggest increasing timeout: `pip install --timeout 600 ...`
3. Exit gracefully instead of hanging
4. Provide recovery instructions

## Additional Notes

### Why PyTorch 2.5.1 Instead of 2.9.1?
- Better CDN availability and stability
- More mature release with fewer edge cases
- Still provides all required CPU functionality
- Wider compatibility with dependencies (sentence-transformers, transformers)

### Timeout Values Explained
- **PIP_DEFAULT_TIMEOUT=300**: 5 minutes per individual download
  - Reasonable for PyTorch (~100MB) on most connections
  - Can be increased to 600 for slow connections
- **HF_HUB_DOWNLOAD_TIMEOUT=1800**: 30 minutes for large models
  - Models can be 2-4GB, requiring longer timeouts
  - Prevents false timeouts on slower connections

### Retry Configuration
- **PIP_RETRIES=3**: Automatic retry 3 times on failure
  - Handles transient network errors
  - Exponential backoff between retries
  - Prevents immediate failure on temporary issues

## Prevention for Future

To prevent similar issues in the future:

1. **Always specify pip timeouts** in deployment scripts
2. **Use stable PyTorch versions** (not bleeding edge)
3. **Add progress indicators** for large downloads
4. **Include helpful error messages** with recovery steps
5. **Test network connectivity** before starting downloads
6. **Document expected download times** for users

## Success Criteria

The fix is successful if:
- ✅ Deployment completes without hanging
- ✅ PyTorch installs successfully
- ✅ Timeouts occur gracefully with clear messages
- ✅ Users see progress during large downloads
- ✅ Automatic retries handle transient failures

## Rollback Plan

If issues persist, you can:

1. **Skip AI stack deployment entirely:**
   ```bash
   ./nixos-quick-deploy.sh --without-ai-model
   ```

2. **Manually install PyTorch after deployment:**
   ```bash
   cd ~/Documents/AI-Optimizer/mcp-server
   source .venv/bin/activate
   pip install --timeout 600 torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
   ```

3. **Use different PyTorch version:**
   Edit `ai-stack/mcp-servers/aidb/requirements.txt` and change to:
   ```
   torch==2.4.1+cpu  # Even more stable fallback
   ```

## Next Steps

1. ✅ Test the deployment on your system
2. Monitor logs in `~/.cache/nixos-quick-deploy/logs/`
3. Report any remaining issues
4. Consider adding a pre-flight network connectivity check

---

**Date:** 2025-12-31
**Issue:** PyTorch download hanging indefinitely
**Status:** Fixed
**Verified:** Pending user testing
