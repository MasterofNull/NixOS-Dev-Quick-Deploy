# NixOS System Dashboard v2.0

**Full-featured system monitor and control board for NixOS host and AI Kubernetes stack**

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 🚀 Features

### Real-Time Monitoring
- **Live Metrics**: CPU, Memory, Disk, Network, GPU usage
- **WebSocket Streaming**: 2-second update interval
- **Historical Charts**: 100-point rolling history with Recharts
- **Health Score**: Calculated from system resource utilization

### Service Management
- **AI Stack Services**: Start/Stop/Restart controls
- **Container Operations**: Manage Kubernetes pods
- **Service Status**: Real-time health monitoring
- **Bulk Actions**: Control multiple services at once

### Modern UI
- **React 19**: Latest React with hooks and concurrent features
- **TypeScript**: Full type safety
- **shadcn/ui**: Beautiful, accessible components
- **Tailwind v4**: Modern styling with CSS layers
- **Dark Theme**: Optimized for long monitoring sessions

### Architecture
```
┌─────────────────────────────────────────────┐
│           Frontend (React + Vite)            │
│  Port 8890 │ WebSocket Client │ REST Client │
└─────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│         Backend (FastAPI + Uvicorn)         │
│  Port 8889 │ WebSocket Server │ REST API    │
└─────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌─────────────┐          ┌─────────────────┐
│   System    │          │  Kubernetes/Systemd │
│  (psutil)   │          │   (subprocess)  │
└─────────────┘          └─────────────────┘
```

## 📦 Tech Stack

### Frontend
- **Framework**: React 19 + Vite 7
- **Language**: TypeScript 5.9
- **UI Library**: shadcn/ui (latest)
- **Styling**: Tailwind CSS v4
- **State**: Zustand
- **API Client**: TanStack Query
- **Charts**: Recharts
- **Icons**: Lucide React
- **Animations**: Framer Motion

### Backend
- **Framework**: FastAPI 0.115+
- **Server**: Uvicorn with WebSocket support
- **Language**: Python 3.13
- **Validation**: Pydantic v2
- **System Metrics**: psutil
- **Async**: asyncio

## 🎯 Quick Start

### 1. Launch Dashboard
```bash
cd dashboard
./start-dashboard.sh
```

This will:
- Install all dependencies automatically
- Start backend API on port 8889
- Start frontend dev server on port 8890
- Open browser to http://localhost:8890

### 2. Access Dashboard
```
Dashboard:  http://localhost:8890
API Docs:   http://localhost:8889/docs
Health:     http://localhost:8889/api/health
```

### 3. Stop Dashboard
Press `Ctrl+C` in the terminal running the start script.

## 🔧 Manual Setup

### Backend Setup
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Start API server
python3 -m api.main
```

### Frontend Setup
```bash
cd frontend

# Install dependencies (using pnpm)
pnpm install

# Start dev server
pnpm run dev

# Build for production
pnpm run build
```

## 📊 API Endpoints

### Metrics
```
GET  /api/metrics/system           - Current system metrics
GET  /api/metrics/history/:metric  - Historical data
GET  /api/metrics/health-score     - System health score
```

### Services
```
GET  /api/services                 - List all services
POST /api/services/:id/start       - Start service
POST /api/services/:id/stop        - Stop service
POST /api/services/:id/restart     - Restart service
```

### Containers
```
GET  /api/containers               - List containers
POST /api/containers/:id/start     - Start container
POST /api/containers/:id/stop      - Stop container
POST /api/containers/:id/restart   - Restart container
GET  /api/containers/:id/logs      - Get logs
```

### WebSocket
```
WS   /ws/metrics                   - Real-time metrics stream
```

## 🎨 UI Components

### Dashboard Sections
1. **System Overview** - 4-card grid with CPU, Memory, Disk, System info
2. **Metrics Chart** - Real-time line chart for CPU and Memory
3. **Service Control** - AI stack service management panel
4. **Container List** - (Coming soon)
5. **Configuration Editor** - (Coming soon)
6. **Log Viewer** - (Coming soon)

### Key Features
- **Responsive Design**: Works on desktop, tablet, mobile
- **Dark Theme**: Easy on the eyes
- **Live Updates**: WebSocket for instant feedback
- **Toast Notifications**: User action feedback
- **Loading States**: Skeletons and spinners
- **Error Handling**: Graceful error messages

## 🔐 Security

### Current Implementation
- CORS configured for localhost only
- No authentication (local development)
- API rate limiting disabled

### Production Recommendations
1. Enable API authentication (JWT tokens)
2. Configure CORS for specific domains
3. Add rate limiting to API endpoints
4. Use HTTPS for WebSocket connections
5. Implement audit logging

## 📈 Performance

### Metrics Collection
- **System Metrics**: Collected every 2 seconds
- **Service Status**: Polled every 10 seconds
- **WebSocket**: Automatic reconnection on disconnect
- **History Buffer**: Last 100 data points (in-memory)

### Optimization
- **Lazy Loading**: Components load on demand
- **Debounced Updates**: Prevents UI thrashing
- **Memoization**: React.memo for expensive renders
- **Virtual Scrolling**: For large container lists (planned)

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version (needs 3.13)
python3 --version

# Check port availability
lsof -i :8889

# Check logs
cd backend
source venv/bin/activate
python3 -m api.main
```

### Frontend won't start
```bash
# Check Node version (needs 20.19+)
node --version

# Clear cache and reinstall
cd frontend
rm -rf node_modules pnpm-lock.yaml
pnpm install

# Check port availability
lsof -i :8890
```

### WebSocket disconnects
- Check backend is running
- Check no firewall blocking port 8889
- Check browser console for errors
- WebSocket auto-reconnects after 5 seconds

### No metrics showing
- Ensure backend has permissions to run systemctl
- Check psutil can access /proc filesystem
- Verify K3s is installed and accessible
- Check API returns data: `curl http://localhost:8889/api/metrics/system`

## 🚧 Roadmap

### Phase 1: Foundation ✅
- [x] FastAPI backend with WebSocket
- [x] React + Vite frontend
- [x] Real-time metrics streaming
- [x] System overview dashboard
- [x] Basic service controls

### Phase 2: Enhanced Monitoring (Week 2)
- [ ] Container resource graphs
- [ ] Network traffic visualization
- [ ] GPU utilization charts
- [ ] Temperature monitoring
- [ ] Historical data export

### Phase 3: Control Features (Week 3)
- [ ] Container log viewer
- [ ] Configuration file editor
- [ ] Quick action toolbar
- [ ] NixOS rebuild trigger
- [ ] Bulk service operations

### Phase 4: Advanced Features (Week 4)
- [ ] Embedded terminal (xterm.js)
- [ ] File browser
- [ ] Model management UI
- [ ] MCP server manager
- [ ] AIDB knowledge browser

### Phase 5: Polish (Week 5)
- [ ] Alert system with notifications
- [ ] Dashboard layouts (drag-and-drop)
- [ ] Export to CSV/JSON/PDF
- [ ] User authentication
- [ ] Multi-theme support

## 🤝 Contributing

### Development Workflow
1. Create feature branch
2. Make changes in `frontend/` or `backend/`
3. Test locally with `./start-dashboard.sh`
4. Run linters: `pnpm lint` (frontend) or `ruff check .` (backend)
5. Submit PR with clear description

### Code Style
- **Frontend**: ESLint + Prettier (auto-configured by Vite)
- **Backend**: Black + Ruff (install: `pip install black ruff`)
- **Commits**: Conventional Commits format

## 📝 License

MIT License - see LICENSE file

## 🙏 Acknowledgments

- Built on NixOS-Dev-Quick-Deploy v6.0.0
- UI components by shadcn/ui
- Charts by Recharts
- Icons by Lucide

---

**Version**: 2.0.0  
**Last Updated**: 2025-01-01  
**Maintainer**: NixOS Dev Quick Deploy Team