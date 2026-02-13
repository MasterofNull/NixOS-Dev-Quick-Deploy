# Dashboard Visual Guide - Service Controls

**Quick visual reference for the new service control features**

---

## 🎯 New Features Location

Open http://localhost:8888/dashboard.html and scroll to find:

```
┌─────────────────────────────────────────────────────────────┐
│                    NixOS SYSTEM COMMAND CENTER               │
├─────────────────────────────────────────────────────────────┤
│  Health Score: 95                Last Update: 20:34:56      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [System Metrics]                                            │
│  CPU, Memory, GPU, Disk, Network...                         │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [LLM Stack Status]                                          │
│  llama.cpp, Qdrant, PostgreSQL...                           │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Container Status]                                          │
│  10 containers listed...                                     │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ▼ AI Stack Services                         11 Services    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 🟢 Llama Cpp              RUNNING  ▶Start ■Stop ↻Restart│
│  │    container                                          │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ 🟢 Qdrant                 RUNNING  ▶Start ■Stop ↻Restart│
│  │    container                                          │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ 🟢 Redis                  RUNNING  ▶Start ■Stop ↻Restart│
│  │    container                                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                     ← NEW SECTION ←                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Service Item Breakdown

Each service shows:

```
┌─────────────────────────────────────────────────────────────┐
│ 🟢 Llama Cpp                RUNNING   ▶Start  ■Stop  ↻Restart│
│    container                                                 │
└─────────────────────────────────────────────────────────────┘
  │   │              │           │         │      │      │
  │   │              │           │         │      │      └─ Restart button
  │   │              │           │         │      └──────── Stop button
  │   │              │           │         └───────────── Start button
  │   │              │           └──────────────────────── Status badge
  │   │              └──────────────────────────────────── Service name
  │   └─────────────────────────────────────────────────── Service type
  └─────────────────────────────────────────────────────────── Status dot
```

### Status Indicators

**Status Dot**:
- 🟢 Green = Service is running
- ⚪ Gray = Service is stopped
- Glows when running

**Status Badge**:
- `RUNNING` - Green text, green border
- `STOPPED` - Gray text, gray border

**Buttons**:
- ▶ Start - Disabled when service is running
- ■ Stop - Disabled when service is stopped
- ↻ Restart - Always enabled

---

## 🎮 How to Use

### Starting a Stopped Service

```
1. Find the service with gray dot and STOPPED badge:
   ⚪ MindsDB                STOPPED   ▶Start  ■Stop  ↻Restart
                                         ↑
                                      Click here

2. Click "▶ Start" button

3. Wait ~1 second, status updates:
   🟢 MindsDB                RUNNING   ▶Start  ■Stop  ↻Restart
                                       (disabled)
```

### Stopping a Running Service

```
1. Find the service with green dot and RUNNING badge:
   🟢 Redis                  RUNNING   ▶Start  ■Stop  ↻Restart
                                                  ↑
                                               Click here

2. Click "■ Stop" button

3. Wait ~1 second, status updates:
   ⚪ Redis                  STOPPED   ▶Start  ■Stop  ↻Restart
                                               (disabled)
```

### Restarting a Service

```
1. Find any service and click "↻ Restart":
   🟢 Qdrant                 RUNNING   ▶Start  ■Stop  ↻Restart
                                                         ↑
                                                     Click here

2. Service stops, then starts again

3. Status updates show the process
```

---

## ⚡ Real-Time Updates

The services list automatically refreshes every **10 seconds**.

**Manual refresh**: Reload the page or click browser refresh

**What gets updated**:
- Service status (running/stopped)
- Button enabled/disabled state
- Status dot color
- Status badge

---

## 🚨 Error Handling

### Backend Not Running

If the FastAPI backend (port 8889) is not running, you'll see:

```
┌─────────────────────────────────────────────────────────────┐
│  ▼ AI Stack Services                         -- Services    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │              ⚠️ FastAPI backend not running           │  │
│  │                                                       │  │
│  │     Start backend:                                    │  │
│  │     cd dashboard/backend && uvicorn api.main:app      │  │
│  │                             --port 8889               │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Fix**: Start the backend
```bash
cd dashboard/backend
source venv/bin/activate
uvicorn api.main:app --port 8889
```

Then refresh the page.

### Action Failed

If a start/stop/restart action fails, you'll see an alert:

```
┌────────────────────────────────────┐
│  ⚠️ Alert                           │
├────────────────────────────────────┤
│  Failed to start service:          │
│  Service not found                 │
│                                    │
│              [OK]                  │
└────────────────────────────────────┘
```

**Common causes**:
- Service doesn't exist
- Permission denied
- Backend error

**Check logs**:
```bash
tail -f ${TMPDIR:-/tmp}/dashboard-backend.log
```

---

## 🎨 Visual Design

### Color Scheme (Cyberpunk Theme)

**Status Indicators**:
- Running: #00ff88 (bright green)
- Stopped: #4a5568 (gray)
- Warning: #ffbe0b (yellow)
- Error: #ff006e (magenta)

**Buttons**:
- Default: Dark background, cyan border
- Hover: Lighter background, glowing border
- Disabled: Faded, no interaction

**Typography**:
- Service names: JetBrains Mono, 600 weight
- Service types: JetBrains Mono, 0.75rem, gray
- Buttons: JetBrains Mono, 0.875rem

### Animations

**Hover Effects**:
```
Service item:
  - Border glows cyan (#00d9ff)
  - Subtle shadow appears

Buttons:
  - Background lightens
  - Slight lift (translateY -1px)
  - Border glows matching button type
```

**Status Dot**:
```
Running:
  - Glows with box-shadow
  - Pulsing animation (optional in future)
```

---

## 📱 Services Monitored

The dashboard tracks these services:

```
1.  🟢 Llama Cpp           - LLM inference server
2.  🟢 Qdrant              - Vector database
3.  🟢 Redis               - Cache server
4.  🟢 Postgres            - SQL database
5.  🟢 AIDB                - MCP server (context API)
6.  🟢 Hybrid Coordinator  - Learning coordinator
7.  🟢 NixOS Docs          - Documentation MCP
8.  🟢 Ralph Wiggum        - MCP server
9.  🟢 Health Monitor      - Self-healing service
10. 🟢 Open WebUI          - Web interface
11. 🟢 MindsDB             - ML platform
```

**Service Types**:
- `container` - K3s pod
- `systemd` - Systemd user service

---

## 🔧 Advanced Features

### Browser Console

Open developer tools (F12) to see:

**Successful action**:
```javascript
Service restart result: {
  message: "Service restarted successfully",
  service: "llama-cpp",
  status: "running"
}
```

**Network requests**:
```
POST /api/services/llama-cpp/restart  200 OK  1.2s
GET  /api/services                    200 OK  45ms
```

### API Calls

Behind the scenes, the dashboard calls:

**Load services**:
```javascript
GET http://localhost:8889/api/services
→ Returns array of service objects
```

**Start service**:
```javascript
POST http://localhost:8889/api/services/llama-cpp/start
→ Returns success/error message
```

**Stop service**:
```javascript
POST http://localhost:8889/api/services/qdrant/stop
→ Returns success/error message
```

**Restart service**:
```javascript
POST http://localhost:8889/api/services/redis/restart
→ Returns success/error message
```

---

## 🎯 Quick Reference Card

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Refresh page | F5 or Ctrl+R |
| Open console | F12 |
| Scroll to services | Page Down (multiple times) |

### Mouse Actions

| Action | How |
|--------|-----|
| Start service | Click "▶ Start" button |
| Stop service | Click "■ Stop" button |
| Restart service | Click "↻ Restart" button |
| Collapse section | Click "▼" arrow in header |

### Status Legend

| Icon | Meaning |
|------|---------|
| 🟢 | Service is running |
| ⚪ | Service is stopped |
| ⚠️ | Backend not available |

---

## 📸 Expected Appearance

### Running Services
```
┌──────────────────────────────────────────────────────────┐
│ 🟢 Llama Cpp              RUNNING  [Start] [Stop] [Restart]│
│    container                         ↑       ↑       ↑     │
│                                   disabled active  active  │
└──────────────────────────────────────────────────────────┘
```

### Stopped Services
```
┌──────────────────────────────────────────────────────────┐
│ ⚪ MindsDB                STOPPED  [Start] [Stop] [Restart]│
│    container                         ↑       ↑       ↑     │
│                                   active disabled active  │
└──────────────────────────────────────────────────────────┘
```

### All Services Healthy
```
┌──────────────────────────────────────────────────────────┐
│  ▼ AI Stack Services                     11 Services     │
│                                                           │
│  🟢 Llama Cpp              RUNNING  [Start] [Stop] [Restart]│
│  🟢 Qdrant                 RUNNING  [Start] [Stop] [Restart]│
│  🟢 Redis                  RUNNING  [Start] [Stop] [Restart]│
│  🟢 Postgres               RUNNING  [Start] [Stop] [Restart]│
│  🟢 AIDB                   RUNNING  [Start] [Stop] [Restart]│
│  🟢 Hybrid Coordinator     RUNNING  [Start] [Stop] [Restart]│
│  🟢 NixOS Docs             RUNNING  [Start] [Stop] [Restart]│
│  🟢 Ralph Wiggum           RUNNING  [Start] [Stop] [Restart]│
│  🟢 Health Monitor         RUNNING  [Start] [Stop] [Restart]│
│  🟢 Open WebUI             RUNNING  [Start] [Stop] [Restart]│
│  🟢 MindsDB                RUNNING  [Start] [Stop] [Restart]│
└──────────────────────────────────────────────────────────┘
```

---

## 💡 Pro Tips

### Tip 1: Collapse Sections
Click the "▼" arrow to collapse sections you don't need:
```
▼ AI Stack Services  →  ▶ AI Stack Services (collapsed)
```

### Tip 2: Watch the Updates
After clicking an action, watch for:
1. Button becomes briefly disabled
2. Status dot may change color (~1s)
3. Status badge text updates (~1s)
4. Buttons re-enable based on new status (~1s)

### Tip 3: Use Console for Debugging
If something doesn't work:
1. Press F12 to open console
2. Look for red error messages
3. Check network tab for failed requests
4. Share errors for troubleshooting

### Tip 4: Multiple Actions
You can queue multiple actions:
- Click restart on service A
- Immediately click restart on service B
- Both will execute (may take a few seconds)

### Tip 5: Backend Status
Check if backend is running:
```bash
curl http://localhost:8889/api/health
```

Should return:
```json
{
  "status": "healthy",
  "websocket_connections": 1,
  "metrics_collector": "running"
}
```

---

## 🎓 Tutorial: First Time Usage

### Step 1: Access Dashboard
1. Open browser
2. Navigate to: http://localhost:8888/dashboard.html
3. Wait for page to load (<1 second)

### Step 2: Find Service Controls
1. Scroll down past system metrics
2. Pass the "LLM Stack Status" section
3. Pass the "Container Status" section
4. Find "AI Stack Services" section

### Step 3: Verify Services Loaded
Look for:
- Section header: "AI Stack Services"
- Badge: "11 Services" (or similar count)
- List of services with green/gray dots

If you see "⚠️ FastAPI backend not running":
```bash
cd dashboard/backend
source venv/bin/activate
uvicorn api.main:app --port 8889
```

### Step 4: Test a Restart
1. Find any running service (green dot)
2. Click "↻ Restart" button
3. Wait ~2 seconds
4. Verify service is still running

### Step 5: Explore Features
- Try collapsing/expanding sections
- Check browser console (F12)
- Watch auto-refresh happen (every 10s)
- Test different actions

---

## 📊 Comparison: Before vs After

### Before (No Service Controls)
```
Container Status
├─ local-ai-llama-cpp     [View only]
├─ local-ai-qdrant        [View only]
└─ local-ai-redis         [View only]

No control buttons ❌
Need terminal to manage ❌
No status indicators ❌
```

### After (With Service Controls)
```
AI Stack Services
├─ 🟢 Llama Cpp    RUNNING  [Start][Stop][Restart] ✅
├─ 🟢 Qdrant       RUNNING  [Start][Stop][Restart] ✅
└─ 🟢 Redis        RUNNING  [Start][Stop][Restart] ✅

Full control in UI ✅
No terminal needed ✅
Visual status ✅
Auto-refresh ✅
```

---

## 🎉 You're Ready!

The enhanced dashboard gives you:
- ✅ Visual service status
- ✅ One-click service control
- ✅ Real-time updates
- ✅ Beautiful UI
- ✅ No terminal needed

**Enjoy your unified dashboard!** 🚀

---

**Guide Created**: January 2, 2026
**Dashboard Version**: 2.0 (Unified)
**Features**: Service Control + Full Monitoring
