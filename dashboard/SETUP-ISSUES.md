# Dashboard Setup Issues & Fixes

**Date:** December 31, 2025
**Status:** Backend ✅ Working | Frontend ⚠️ Needs Component Installation

---

## Issues Found & Fixed

### 1. ✅ Backend Start Command (FIXED)

**Problem:** Start script used `python3 -m api.main` instead of `uvicorn`

**Error:**
```
ERROR: Error loading ASGI app. Could not import module "main".
```

**Fix Applied:**
Changed [start-dashboard.sh](start-dashboard.sh:56) from:
```bash
python3 -m api.main &
```

To:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8889 --reload &
```

**Status:** ✅ Backend now starts correctly

---

### 2. ⚠️ Missing shadcn/ui Components (NEEDS FIX)

**Problem:** Frontend code references shadcn/ui components that were never installed

**Missing Components:**
- `@/components/ui/card`
- `@/components/ui/button`
- `@/components/ui/badge`
- `@/components/ui/progress`
- `@/components/ui/chart`
- `@/components/ui/dropdown-menu`

**Error:**
```
Failed to resolve import "@/components/ui/card" from "src/components/MetricsChart.tsx"
Cannot apply unknown utility class `border-border`
```

**Root Cause:**
- Dashboard was designed to use shadcn/ui
- Components referenced in code but never installed
- Tailwind CSS v4 config incomplete

**Solutions:**

#### Option A: Install shadcn/ui Components (Recommended)

```bash
cd dashboard/frontend

# Install Radix UI dependencies
pnpm add @radix-ui/react-slot @radix-ui/react-dropdown-menu \
  @radix-ui/react-progress @radix-ui/react-separator \
  class-variance-authority

# Create components directory
mkdir -p src/components/ui

# Install individual components using shadcn CLI
# (Requires components.json config first)
```

#### Option B: Simplify to Use Basic Components

Replace shadcn components with simple divs and basic styling.

**Required Changes:**
- Replace `<Card>` with styled `<div>`
- Replace `<Button>` with styled `<button>`
- Replace `<Badge>` with styled `<span>`
- Replace `<Progress>` with HTML5 `<progress>` or custom div
- Fix Tailwind CSS v4 config for `border-border` class

---

## Current Status

### ✅ Backend Working

**Port:** 8889
**Status:** Running successfully

**Verified Endpoints:**
```bash
# System metrics with container stats
curl http://localhost:8889/api/metrics/system

# List all 11 services (including nixos-docs, ralph-wiggum)
curl http://localhost:8889/api/services

# List containers
curl http://localhost:8889/api/containers

# Health score
curl http://localhost:8889/api/metrics/health-score
```

**Features Confirmed:**
- ✅ Container stats collection working
- ✅ All 11 services monitored (llama-cpp, qdrant, redis, postgres, aidb, hybrid-coordinator, **nixos-docs**, **ralph-wiggum**, health-monitor, open-webui, mindsdb)
- ✅ WebSocket support enabled
- ✅ Metrics collection with psutil
- ✅ Service management (start/stop/restart)

---

### ⚠️ Frontend Issues

**Port:** 8890
**Status:** Not starting due to missing dependencies

**Issues:**
1. Missing shadcn/ui components
2. Tailwind CSS v4 class `border-border` undefined
3. Import resolution failures

**Impact:**
- Cannot load dashboard UI
- Components fail to compile
- Vite dev server errors

---

## Recommended Fix Steps

### Immediate (To Get Dashboard Running)

**Step 1: Create Tailwind Config**

Create `dashboard/frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      borderColor: {
        DEFAULT: 'hsl(var(--border))',
        border: 'hsl(var(--border))',
      },
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
      },
    },
  },
  plugins: [],
}
```

**Step 2: Install Missing Radix UI Packages**

```bash
cd dashboard/frontend
pnpm add @radix-ui/react-slot @radix-ui/react-dropdown-menu \
  @radix-ui/react-progress @radix-ui/react-separator \
  class-variance-authority
```

**Step 3: Create Basic UI Components**

Manually create the missing components in `src/components/ui/`:
- `card.tsx`
- `button.tsx`
- `badge.tsx`
- `progress.tsx`
- `chart.tsx` (for Recharts wrapper)
- `dropdown-menu.tsx`

(Or use shadcn CLI after creating `components.json`)

---

## Alternative: Use CLI Monitor Instead

Since the **CLI monitor ([scripts/ai-stack-monitor.sh](../scripts/ai-stack-monitor.sh)) is fully working**, you can use that for monitoring:

```bash
# Start CLI monitor (works immediately)
./scripts/ai-stack-monitor.sh
```

**CLI Monitor Features:**
- ✅ Real-time container status
- ✅ CPU and Memory stats
- ✅ All 9 core services monitored
- ✅ Includes nixos-docs and ralph-wiggum
- ✅ 5-second refresh
- ✅ No dependencies needed

---

## Testing Backend

### Test Services API
```bash
curl http://localhost:8889/api/services | jq '.'
```

**Expected Output:**
```json
[
  {"id": "llama-cpp", "name": "Llama Cpp", "status": "stopped", "type": "container"},
  {"id": "qdrant", "name": "Qdrant", "status": "stopped", "type": "container"},
  {"id": "redis", "name": "Redis", "status": "stopped", "type": "container"},
  {"id": "postgres", "name": "Postgres", "status": "stopped", "type": "container"},
  {"id": "aidb", "name": "Aidb", "status": "stopped", "type": "container"},
  {"id": "hybrid-coordinator", "name": "Hybrid Coordinator", "status": "stopped", "type": "container"},
  {"id": "nixos-docs", "name": "Nixos Docs", "status": "stopped", "type": "container"},
  {"id": "ralph-wiggum", "name": "Ralph Wiggum", "status": "stopped", "type": "container"},
  {"id": "health-monitor", "name": "Health Monitor", "status": "stopped", "type": "container"},
  {"id": "open-webui", "name": "Open Webui", "status": "stopped", "type": "container"},
  {"id": "mindsdb", "name": "Mindsdb", "status": "stopped", "type": "container"}
]
```

### Test Container Stats
```bash
curl http://localhost:8889/api/metrics/system | jq '.containers'
```

**Expected:** Container count, running list, and per-container stats

---

## Summary

### ✅ What's Working
- Backend API fully functional
- All 11 services monitored
- Container stats collection
- nixos-docs and ralph-wiggum integrated
- Service management endpoints
- WebSocket support
- CLI monitor fully functional

### ⚠️ What Needs Work
- Frontend UI components (shadcn/ui installation)
- Tailwind CSS v4 configuration
- Component imports

### 📝 Files Modified
1. [start-dashboard.sh](start-dashboard.sh) - Fixed backend start command
2. [backend/api/services/service_manager.py](backend/api/services/service_manager.py) - Added 5 new services
3. [backend/api/services/metrics_collector.py](backend/api/services/metrics_collector.py) - Added container stats

---

## Next Steps

**For Users:**
1. Use CLI monitor ([scripts/ai-stack-monitor.sh](../scripts/ai-stack-monitor.sh)) for immediate monitoring
2. Backend API is available at http://localhost:8889/docs for API exploration
3. Frontend requires component installation to work

**For Developers:**
1. Install shadcn/ui components or create basic replacements
2. Configure Tailwind CSS v4 properly
3. Test frontend compilation
4. Complete the dashboard v2 setup

---

**Status:** Backend ✅ | Frontend ⚠️ Needs Component Installation
**Recommendation:** Use CLI monitor for now, fix frontend components later
**Backend API:** http://localhost:8889 (working)
**Frontend:** http://localhost:8890 (needs fixing)
