# Discovery Pipeline Code Review
**Date**: 2025-12-22
**Reviewer**: Claude (Local LLM)
**Scope**: Discovery crawler, dashboard integration, keyword signals extraction

---

## Executive Summary

✅ **Overall Assessment**: System is well-architected with good separation of concerns
⚠️ **Critical Issues**: 1 (GitHub rate limiting without token)
⚠️ **Medium Issues**: 4 (error handling, data flow, UI bugs)
💡 **Improvements**: 6 proposed enhancements

---

## 1. Bugs and Logical Issues

### 🔴 CRITICAL: GitHub Rate Limiting (scripts/discover-improvements.sh:62-67)

**Issue**: GitHub API calls fail with 403 rate limit errors when no auth token is provided.

**Location**: Lines 62-67
```python
def fetch_json(url: str) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
```

**Evidence**: Discovery report shows all GitHub sources failed:
```
- https://github.com/qdrant/qdrant/releases (error: HTTP Error 403: rate limit exceeded)
```

**Impact**:
- No high-value candidates detected
- All GitHub sources show as "error" signals
- Dashboard displays only low-trust signals

**Fix**:
1. Document requirement for `GITHUB_TOKEN` in discovery script header
2. Add early warning if token missing when GitHub sources are configured
3. Consider adding GitHub token check to health monitoring

**Recommendation**:
```python
# At top of main():
github_sources = [s for s in sources if s.get("type") == "github_release"]
if github_sources and not (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")):
    print("WARNING: GitHub token not set. GitHub API calls will fail due to rate limits.", file=sys.stderr)
    print("Set GITHUB_TOKEN or GH_TOKEN environment variable for authenticated requests.", file=sys.stderr)
```

---

### ⚠️ MEDIUM: Duplicate Reddit Source (config/improvement-sources.json:44-54)

**Issue**: Reddit r/LocalLLaMA appears twice with different weights (0.15 vs 0.08) and cadences.

**Location**: Lines 44-47 and 50-53
```json
{
  "url": "https://www.reddit.com/r/LocalLLaMA/",
  "type": "social",
  "weight": 0.15,
  "cadence_hours": 72
},
...
{
  "url": "https://www.reddit.com/r/localllama/",  // lowercase
  "type": "social",
  "weight": 0.08,
  "cadence_hours": 168
}
```

**Impact**:
- Same content fetched with two different priorities
- Wastes API calls and processing time
- Confusing metrics (double-counting)

**Fix**: Remove duplicate entry, standardize on canonical URL

**Recommendation**:
```json
// Keep only one (probably the 72h cadence one):
{
  "url": "https://www.reddit.com/r/LocalLLaMA/",
  "type": "social",
  "weight": 0.15,
  "cadence_hours": 72
}
```

---

### ⚠️ MEDIUM: Missing Timezone Awareness (scripts/discover-improvements.sh:173-189)

**Issue**: `is_due()` compares naive datetime with timezone-aware datetime.

**Location**: Lines 173-189
```python
def is_due(source: dict, state: dict, now: dt.datetime) -> bool:
    ...
    try:
        last_dt = dt.datetime.fromisoformat(last_checked)  # May be TZ-aware
    except ValueError:
        return True
    delta = now - last_dt  # TypeError if TZ mismatch
    return delta.total_seconds() >= float(cadence_hours) * 3600
```

**Evidence**: State file shows timestamps with `+00:00` suffix (TZ-aware)
```json
"https://github.com/qdrant/qdrant/releases": "2025-12-22T23:19:43.358727+00:00"
```

But `now` is passed as `dt.datetime.now(dt.timezone.utc)` (line 230), which is TZ-aware.

**Impact**:
- Currently works because both are TZ-aware
- Fragile: would break if state file had naive timestamps
- Could cause unexpected behavior if state corrupted

**Fix**: Ensure both datetimes are TZ-aware before comparison

**Recommendation**:
```python
try:
    last_dt = dt.datetime.fromisoformat(last_checked)
    # Ensure timezone-aware
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=dt.timezone.utc)
except ValueError:
    return True
```

---

### ⚠️ MEDIUM: Report Parsing Assumes Exact Format (generate-dashboard-data.sh:1306-1367)

**Issue**: Python parser hardcodes expected section headers and field names.

**Location**: Lines 1306-1367 (embedded Python in bash script)
```python
if line.startswith("## "):
    if "Candidate Summary" in line:
        section = "candidates"
    elif "Signals" in line:
        section = "signals"
```

**Impact**:
- Breaks if discovery script changes header wording
- Fragile coupling between two scripts
- Silent failures (empty lists instead of errors)

**Example Failure Scenario**:
- Discovery script changes "Candidate Summary (Scored)" to "High-Value Candidates"
- Parser sets `section = None`
- All candidates silently dropped from dashboard

**Fix**: Use more flexible matching or shared constants

**Recommendation**:
```python
# More flexible matching
if line.startswith("## "):
    line_lower = line.lower()
    if "candidate" in line_lower:
        section = "candidates"
    elif "signal" in line_lower and "low" in line_lower:
        section = "signals"
    elif "sources" in line_lower:
        section = "sources"
```

Or extract parser to shared module:
```bash
# discovery_parser.py (new file)
# scripts/discover-improvements.sh imports it
# scripts/generate-dashboard-data.sh calls it
```

---

### ⚠️ MINOR: Dashboard Discovery Badge Shows Wrong Count (dashboard.html:2329)

**Issue**: Badge shows `candidate_count` as "High-Value", but signals are also important.

**Location**: Line 2329
```javascript
badge.textContent = `${candidateCount} High-Value`;
```

**Impact**:
- Badge reads "0 High-Value" when there are 11 low-trust signals
- User thinks discovery found nothing
- Misleading at-a-glance status

**Fix**: Show total signal count or both

**Recommendation**:
```javascript
if (candidateCount > 0) {
    badge.textContent = `${candidateCount} High-Value`;
} else if (signalCount > 0) {
    badge.textContent = `${signalCount} Signals`;
} else {
    badge.textContent = 'No Signals';
}
```

Or show both:
```javascript
badge.textContent = `${candidateCount} HV / ${signalCount} LT`;
```

---

## 2. Missing Tests and Validation

### Missing Test: Cadence Enforcement

**What's Missing**: No automated test verifying sources are skipped when not due.

**Why Important**: Core feature to reduce noise and API usage.

**Recommendation**: Add unit test
```python
def test_cadence_enforcement():
    """Verify sources with cadence_hours are skipped when not due."""
    state = {
        "https://example.com": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    }
    source = {"url": "https://example.com", "cadence_hours": 24}
    now = datetime.now(timezone.utc)

    # Should not be due (only 1 hour passed, needs 24)
    assert not is_due(source, state, now)

    # Should be due after 24 hours
    now_later = now + timedelta(hours=25)
    assert is_due(source, state, now_later)
```

---

### Missing Test: Duplicate URL Detection

**What's Missing**: No check for duplicate source URLs in config.

**Why Important**: Currently has duplicate (r/LocalLLaMA twice).

**Recommendation**: Add validation script
```bash
# scripts/validate-discovery-config.sh
#!/usr/bin/env bash
set -euo pipefail

config="config/improvement-sources.json"
urls=$(jq -r '.[].url' "$config")
duplicates=$(echo "$urls" | sort | uniq -d)

if [[ -n "$duplicates" ]]; then
    echo "ERROR: Duplicate URLs found in $config:"
    echo "$duplicates"
    exit 1
fi
echo "✓ No duplicate URLs"
```

---

### Missing Test: Report → JSON Parsing

**What's Missing**: No test ensuring parser correctly extracts candidates/signals.

**Why Important**: Parser is fragile (string matching).

**Recommendation**: Add integration test
```python
def test_report_to_json_parsing():
    """Verify discovery report is correctly parsed to keyword-signals.json."""
    report_content = """
# Improvement Discovery Report
**Date:** 2025-12-22

## Candidate Summary (Scored)

### https://github.com/foo/bar
- **Score:** 42.5
- **Repo:** foo/bar
- **Latest release:** v1.2.3

## Signals (Low-Trust)

- https://reddit.com/r/foo (social signal; requires corroboration)
    """

    # Write test report
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(report_content)
        report_path = f.name

    # Run parser
    output_path = report_path.replace('.md', '.json')
    subprocess.run(['python3', 'scripts/parse-discovery-report.py', report_path, output_path])

    # Verify output
    with open(output_path) as f:
        data = json.load(f)

    assert len(data['candidates']) == 1
    assert data['candidates'][0]['score'] == 42.5
    assert len(data['signals']) == 1
    assert 'social' in data['signals'][0]['note']
```

---

### Missing Validation: GitHub Token at Runtime

**What's Missing**: No early check if GitHub token is available.

**Why Important**: All GitHub sources fail silently with rate limit errors.

**Recommendation**: Add preflight check
```python
# In main(), before processing sources:
github_sources = [s for s in sources if s.get("type") == "github_release"]
has_token = bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))

if github_sources and not has_token:
    print("⚠️  WARNING: No GitHub token found", file=sys.stderr)
    print(f"   {len(github_sources)} GitHub sources will likely fail due to rate limits", file=sys.stderr)
    print("   Set GITHUB_TOKEN or GH_TOKEN environment variable", file=sys.stderr)
    # Optional: prompt to continue or exit
```

---

### Missing Validation: State File Corruption

**What's Missing**: No validation when loading state file.

**Why Important**: Corrupt state could cause all sources to reprocess.

**Recommendation**: Add schema validation
```python
def load_state() -> dict:
    if STATE_FILE.is_file():
        try:
            data = json.loads(STATE_FILE.read_text())
            if isinstance(data, dict):
                # Validate all values are ISO timestamps
                for url, timestamp in data.items():
                    try:
                        dt.datetime.fromisoformat(timestamp)
                    except (ValueError, AttributeError):
                        print(f"⚠️  Invalid timestamp for {url}: {timestamp}", file=sys.stderr)
                        del data[url]  # Remove invalid entry
                return data
        except json.JSONDecodeError as e:
            print(f"⚠️  Corrupt state file: {e}", file=sys.stderr)
            return {}
    return {}
```

---

## 3. Reliability Improvements

### Improvement 1: Exponential Backoff for Rate Limits

**Current Issue**: Rate limit errors are permanent failures.

**Recommendation**: Implement retry with backoff
```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as e:
                    if e.code == 403 and 'rate limit' in str(e).lower():
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            print(f"Rate limited, retry in {delay}s...", file=sys.stderr)
                            time.sleep(delay)
                        else:
                            raise
                    else:
                        raise
        return wrapper
    return decorator

@retry_with_backoff(max_retries=2, base_delay=2.0)
def fetch_json(url: str) -> dict:
    ...
```

---

### Improvement 2: Graceful Degradation for Missing Data

**Current Issue**: Dashboard shows empty lists if keyword-signals.json missing.

**Current Behavior**: File created with `"status": "missing"` but UI shows generic empty state.

**Recommendation**: Show helpful message
```javascript
function updateDiscoverySignals(data) {
    ...
    if (data.status === 'missing') {
        const hint = document.createElement('div');
        hint.className = 'data-item';
        hint.style.color = 'var(--text-muted)';
        hint.innerHTML = 'No discovery report found. Run:<br><code>scripts/discover-improvements.sh</code>';
        candidatesEl.appendChild(hint);
        return;
    }
    ...
}
```

---

### Improvement 3: Cache GitHub API Responses

**Current Issue**: Every run makes fresh GitHub API calls.

**Recommendation**: Add HTTP caching layer
```python
import hashlib
from pathlib import Path

CACHE_DIR = REPO_ROOT / ".cache" / "discovery"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def fetch_json_cached(url: str, ttl_hours: int = 1) -> dict:
    cache_key = hashlib.sha256(url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.json"

    if cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_hours < ttl_hours:
            return json.loads(cache_file.read_text())

    data = fetch_json(url)
    cache_file.write_text(json.dumps(data))
    return data
```

---

### Improvement 4: Parallel Source Processing

**Current Issue**: Sources processed sequentially (slow for 30+ sources).

**Recommendation**: Use concurrent.futures
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_source(source):
    """Process a single source and return results."""
    # Move per-source logic here
    ...
    return {"candidates": [...], "signals": [...]}

# In main():
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(process_source, src): src for src in sources}
    for future in as_completed(futures):
        result = future.result()
        candidates.extend(result["candidates"])
        signals.extend(result["signals"])
```

---

### Improvement 5: Structured Logging

**Current Issue**: Print statements mixed with data output.

**Recommendation**: Use Python logging module
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(REPO_ROOT / 'logs' / 'discovery.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Usage:
logger.info(f"Processing {len(sources)} sources")
logger.warning(f"Rate limit hit for {url}")
logger.error(f"Failed to parse: {e}")
```

---

### Improvement 6: Dashboard Auto-Refresh on New Report

**Current Issue**: Dashboard shows stale data until manual refresh.

**Recommendation**: Watch for file changes
```javascript
let lastReportPath = '';

async function checkForNewReport() {
    const signals = await fetchJSON('keyword-signals.json');
    if (signals.report_path !== lastReportPath) {
        lastReportPath = signals.report_path;
        loadData(); // Reload all data
        showNotification('New discovery report available!');
    }
}

// Check every 30 seconds
setInterval(checkForNewReport, 30000);
```

---

## 4. Noise Reduction Suggestions

### Current Noise Sources

Based on `improvement-sources.json` analysis:

**Low-Value Social Sources** (candidates for removal):
- `r/ChatGPT` (weight: 0.07) - Too generic, low signal
- `r/codex` (weight: 0.06, cadence: 336h) - Rarely updated
- `r/opensource` (weight: 0.06, cadence: 336h) - Too broad

**Discord Servers** (weight: 0.03 each, cadence: 720h):
- Cannot be crawled programmatically (authentication required)
- Always show as "review manually" with no useful data
- **Recommendation**: Remove all Discord URLs or set `type: "manual_only"`

**Overly Broad Research Sources**:
- `paperswithcode.com` (weight: 0.2) - Too many papers, low NixOS relevance
- **Recommendation**: Replace with curated arXiv searches for specific topics

---

### Recommended Source Weights Adjustment

```json
// Current problems:
{
  "url": "https://www.reddit.com/r/LocalLLaMA/",
  "weight": 0.15,  // Too high for social source
  "cadence_hours": 72  // Too frequent (every 3 days)
}

// Recommended:
{
  "url": "https://www.reddit.com/r/LocalLLaMA/",
  "weight": 0.08,  // Lower weight (social sources unreliable)
  "cadence_hours": 168  // Weekly check is enough
}
```

**Rationale**:
- Social sources need manual verification (per doc: "requires corroboration")
- High weight (0.15) elevates unverified signals
- Frequent checks (72h) waste API calls

---

### Add Source Quality Metrics

**Recommendation**: Track historical accuracy of each source
```json
// Add to state file:
{
  "source_metrics": {
    "https://github.com/qdrant/qdrant/releases": {
      "total_checks": 42,
      "valid_releases": 38,
      "false_positives": 2,
      "accuracy": 0.90
    }
  }
}
```

Then adjust weights dynamically:
```python
def adjust_weight(source, metrics):
    base_weight = source.get("weight", 0.3)
    accuracy = metrics.get("accuracy", 1.0)
    return base_weight * accuracy
```

---

## 5. Better Structure for Keyword Extraction

### Current Approach

Dashboard parses Markdown report using string matching:
- Fragile (breaks if format changes)
- No semantic understanding
- Misses context (e.g., "error: rate limit" treated as signal)

### Recommended Approach: Structured JSON Output

**Change 1**: Discovery script outputs JSON directly
```python
# In main(), replace Markdown generation with:
output_json = out_path.with_suffix('.json')
json_data = {
    "metadata": {
        "timestamp": timestamp,
        "sources_checked": len(sources),
        "rate_limit_hit": rate_limit_hit
    },
    "candidates": [
        {
            "url": "https://github.com/foo/bar",
            "repo": "foo/bar",
            "score": 42.5,
            "release": {"name": "v1.2.3", "url": "..."},
            "stars": 1234
        }
    ],
    "signals": [
        {
            "url": "https://reddit.com/r/foo",
            "type": "social",
            "note": "requires corroboration",
            "confidence": 0.3
        }
    ]
}
output_json.write_text(json.dumps(json_data, indent=2))

# Also generate Markdown for human readability
generate_markdown_report(json_data, out_path)
```

**Change 2**: Dashboard reads JSON directly
```javascript
// No parsing needed!
const report = await fetchJSON('discovery-report-2025-12-22.json');
updateDiscoverySignals(report);
```

**Benefits**:
- Eliminates fragile parsing
- Easier to extend (add new fields without breaking parser)
- JSON is canonical format (Markdown is view)

---

### Alternative: Use YAML for Human-Friendly Config

**Current**: JSON is not ideal for manual editing
**Recommendation**: Use YAML for source config

```yaml
# config/improvement-sources.yaml
sources:
  - url: https://github.com/qdrant/qdrant/releases
    type: github_release
    weight: 0.7
    cadence_hours: 168
    tags: [vector-db, core-dependency]

  - url: https://www.reddit.com/r/LocalLLaMA/
    type: social
    weight: 0.08
    cadence_hours: 168
    tags: [community, low-trust]
    note: "Manual verification required"
```

Then convert to JSON at runtime:
```python
import yaml

if SOURCES_YAML.exists():
    sources = yaml.safe_load(SOURCES_YAML.read_text())['sources']
elif SOURCES_JSON.exists():
    sources = json.loads(SOURCES_JSON.read_text())
```

---

## 6. Summary Checklist

### Critical (Must Fix)
- [ ] Add GitHub token check and warning (scripts/discover-improvements.sh)
- [ ] Document `GITHUB_TOKEN` requirement in README
- [ ] Remove duplicate Reddit r/LocalLLaMA entry

### High Priority (Should Fix)
- [ ] Fix timezone handling in `is_due()` (add TZ awareness check)
- [ ] Make report parser more flexible (use contains vs exact match)
- [ ] Add validation script for duplicate URLs
- [ ] Remove uncrawlable Discord sources

### Medium Priority (Nice to Have)
- [ ] Add retry logic with exponential backoff
- [ ] Implement HTTP response caching
- [ ] Add structured logging
- [ ] Show helpful message when no report found

### Low Priority (Future Enhancement)
- [ ] Parallel source processing
- [ ] Auto-refresh dashboard on new report
- [ ] Track source quality metrics
- [ ] Switch to structured JSON output
- [ ] Consider YAML for source config

---

## 7. Code Quality Assessment

### What's Good ✅

1. **Separation of Concerns**: Discovery script, parser, and dashboard are properly decoupled
2. **Cadence System**: Smart feature to reduce noise and API usage
3. **Weighted Sources**: Flexible priority system
4. **State Persistence**: Crawler state properly saved/loaded
5. **Graceful Degradation**: Handles missing files without crashing
6. **Type Hints**: Good use of Python type annotations
7. **Documentation**: Source types and weights are documented

### What Needs Work ⚠️

1. **Error Handling**: Many bare `except Exception` blocks (lines 204, 222, 282, 357)
2. **String Parsing**: Fragile Markdown parsing (should use structured format)
3. **Hardcoded Paths**: `REPO_ROOT` assumes script location
4. **No Input Validation**: Source config not validated
5. **Silent Failures**: Errors logged but not surfaced to user
6. **Mixed Concerns**: Bash script contains embedded Python code

---

## 8. Performance Metrics

**Current Performance** (estimated):
- Sources: 30
- Sequential processing: ~60 seconds
- API calls: 7 GitHub + 4 HTTP scrapes = ~11 requests
- Disk I/O: 2 reads + 2 writes

**With Proposed Improvements**:
- Parallel processing: ~15 seconds (4x faster)
- HTTP caching: 90% fewer API calls on subsequent runs
- Structured JSON: No Markdown parsing overhead

---

## 9. Security Considerations

### Potential Risks

1. **Arbitrary URL Fetching**: Config file could contain malicious URLs
   - **Mitigation**: Validate URL schemes (allow only http/https)

2. **Command Injection**: None found (good!)
   - URLs are used in HTTP requests (no shell execution)

3. **Disk Space**: State file could grow unbounded
   - **Mitigation**: Add max age for state entries (e.g., purge after 1 year)

4. **Secrets Exposure**: GitHub token in environment
   - **Current**: Safe (uses env vars, not hardcoded)
   - **Recommendation**: Document token scopes needed (public_repo only)

---

## 10. Recommended Action Plan

**Week 1** (Critical):
1. Set `GITHUB_TOKEN` environment variable
2. Remove duplicate r/LocalLLaMA source
3. Add GitHub token check with warning
4. Test discovery script produces candidates

**Week 2** (High Priority):
1. Fix timezone handling in `is_due()`
2. Make report parser more flexible
3. Add validation script for source config
4. Remove Discord sources (uncrawlable)

**Week 3** (Nice to Have):
1. Add HTTP response caching
2. Implement retry logic for rate limits
3. Add structured logging

**Week 4** (Future):
1. Switch to structured JSON output
2. Add parallel source processing
3. Track source quality metrics

---

**End of Review**
