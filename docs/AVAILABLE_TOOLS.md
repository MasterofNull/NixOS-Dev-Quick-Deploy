# Available Tools & Resources

**Purpose:** Complete inventory of tools, MCP servers, and resources available to AI agents
**Benefit:** Reduces token usage by providing context upfront, eliminates repeated searches

---

## 🛠️ Standard CLI Tools

### Core Unix/Linux Tools

```bash
# File Operations
ls, cd, pwd, mkdir, rm, mv, cp, chmod, chown
find, fd          # File search
tree              # Directory visualization

# Text Processing
grep, rg          # Pattern search (ripgrep faster)
sed, awk          # Stream editing
cat, head, tail   # File reading
less, more        # File viewing

# System Information
ps, top, htop     # Process monitoring
df, du            # Disk usage
free              # Memory usage
uname             # System info

# Network
curl, wget        # HTTP requests
nc, netcat        # Network connections
ping, traceroute  # Network diagnostics
ss, netstat       # Socket statistics

# Development
git               # Version control
make              # Build automation
docker, podman    # Containers
jq                # JSON processing
yq                # YAML processing
```

### Language-Specific Tools

#### Python
```bash
python3, python      # Python interpreter
pip, pip3            # Package manager
pytest               # Testing framework
black                # Code formatter
ruff                 # Fast linter
flake8, pylint       # Linters
mypy                 # Type checker
poetry, pipenv       # Dependency management
```

#### JavaScript/Node
```bash
node, npm, npx       # Node.js runtime
yarn, pnpm           # Alternative package managers
jest                 # Testing framework
eslint               # Linter
prettier             # Code formatter
tsc                  # TypeScript compiler
webpack, vite        # Bundlers
```

#### Go
```bash
go                   # Go compiler
gofmt                # Code formatter
golint               # Linter
go test              # Testing
```

#### Rust
```bash
cargo                # Build system
rustc                # Compiler
rustfmt              # Formatter
clippy               # Linter
```

---

## 🔌 MCP Servers

> **What are MCP Servers?** Model Context Protocol servers provide specialized capabilities to AI agents through a standardized interface.

### Common MCP Server Capabilities

| Server Type | Provides | Use Cases |
|------------|----------|-----------|
| **File System** | Read/write files | Code editing, log analysis |
| **Database** | Query databases | Data analysis, migrations |
| **Git** | Repository operations | Version control, history |
| **Web** | HTTP requests | API testing, web scraping |
| **Search** | Code/text search | Finding patterns, documentation |
| **Shell** | Command execution | Build, test, deployment |
| **Docker** | Container management | Service orchestration |
| **Kubernetes** | Cluster operations | Cloud deployments |

### Project-Specific MCP Servers

> **Customize this section** for your project. Example:

```yaml
# .mcp/config.yaml (example)
servers:
  - name: aidb-mcp
    port: 8091
    capabilities:
      - file_operations
      - database_queries
      - rag_queries
      - inference_api

  - name: filesystem
    capabilities:
      - read_file
      - write_file
      - list_directory
      - search_files

  - name: database
    capabilities:
      - sql_query
      - schema_introspection
      - migrations
```

**Usage Examples:**

```python
# Query via MCP
response = mcp_client.query(
    "SELECT * FROM users WHERE status='active'"
)

# RAG query
context = mcp_client.rag_query(
    "How do I implement authentication?"
)

# File operations
content = mcp_client.read_file("src/main.py")
```

---

## 📊 Monitoring & Observability Tools

### Metrics & Dashboards

```bash
# Prometheus - Metrics collection
http://localhost:9090           # Query UI
http://localhost:9090/targets   # Scrape targets
http://localhost:9090/graph     # Graph editor

# Grafana - Visualization
http://localhost:3000           # Dashboard UI
# Default credentials: admin/admin

# Common metrics queries:
rate(http_requests_total[5m])   # Request rate
histogram_quantile(0.95, ...)   # 95th percentile
up{job="service-name"}          # Service health
```

### Logging

```bash
# Container logs
docker logs <container>
podman logs <container>

# System logs
journalctl -u <service>
tail -f /var/log/<logfile>

# Application logs
tail -f logs/app.log
grep ERROR logs/app.log
```

### Tracing

```bash
# Jaeger (if configured)
http://localhost:16686

# OpenTelemetry collector
http://localhost:55679
```

---

## 🗄️ Database Tools

### PostgreSQL

```bash
# psql - PostgreSQL client
psql -U username -d database

# Common commands:
\l                  # List databases
\c dbname           # Connect to database
\dt                 # List tables
\d tablename        # Describe table
\q                  # Quit

# Query examples:
SELECT * FROM table LIMIT 10;
EXPLAIN ANALYZE SELECT ...;
```

### Redis

```bash
# redis-cli - Redis client
redis-cli

# Common commands:
KEYS *              # List all keys
GET key             # Get value
SET key value       # Set value
DEL key             # Delete key
INFO                # Server info
MONITOR             # Watch commands
```

### SQLite

```bash
# sqlite3 - SQLite client
sqlite3 database.db

# Common commands:
.tables             # List tables
.schema tablename   # Show schema
.dump               # Export database
```

---

## 🔐 Security & Secrets Management

### Environment Variables

```bash
# Reading secrets
echo $DATABASE_URL
printenv | grep SECRET

# Setting secrets (temporary)
export API_KEY="secret"

# Loading from .env file
source .env
```

### Secrets Files

```bash
# Common locations:
.env                    # Environment variables
.secrets/               # Secret files (gitignored)
~/.ssh/                 # SSH keys
~/.aws/credentials      # AWS credentials
~/.docker/config.json   # Docker credentials
```

### Vault Tools (if configured)

```bash
# HashiCorp Vault
vault login
vault kv get secret/path

# SOPS (encrypted files)
sops -d secrets.enc.yaml
```

---

## 🧪 Testing Tools

### Unit Testing

```bash
# Python
pytest tests/
pytest tests/test_module.py::test_function
pytest -v --cov=src tests/

# JavaScript
npm test
jest tests/
npm run test:coverage

# Go
go test ./...
go test -v -race ./...

# Rust
cargo test
cargo test --verbose
```

### Integration Testing

```bash
# API testing
curl -X POST http://localhost:8000/api/endpoint
httpie POST localhost:8000/api/endpoint

# Load testing
ab -n 1000 -c 10 http://localhost:8000/
hey -n 1000 -c 50 http://localhost:8000/
```

### E2E Testing

```bash
# Playwright
npx playwright test

# Selenium
pytest tests/e2e/

# Cypress
npx cypress run
```

---

## 📦 Package Managers

### System Package Managers

```bash
# Debian/Ubuntu
apt update && apt install <package>
apt search <package>

# RedHat/CentOS
yum install <package>
dnf install <package>

# Arch
pacman -S <package>

# macOS
brew install <package>

# NixOS
nix-env -iA nixpkgs.<package>
```

### Language Package Managers

```bash
# Python
pip install <package>
pip install -r requirements.txt
poetry install

# JavaScript
npm install <package>
yarn add <package>
pnpm add <package>

# Go
go get <package>
go mod download

# Rust
cargo install <package>
```

---

## 🚀 Deployment Tools

### Container Management

```bash
# Docker
docker build -t image:tag .
docker run -d -p 8000:8000 image:tag
docker-compose up -d
docker ps
docker logs <container>

# Podman (Docker alternative)
podman build -t image:tag .
podman run -d -p 8000:8000 image:tag
podman-compose up -d
```

### Orchestration

```bash
# Kubernetes
kubectl get pods
kubectl logs pod-name
kubectl apply -f deployment.yaml
kubectl scale deployment app --replicas=3

# Docker Swarm
docker stack deploy -c stack.yaml appname
docker service ls
```

### CI/CD

```bash
# GitHub Actions
# .github/workflows/*.yml

# GitLab CI
# .gitlab-ci.yml

# Jenkins
# Jenkinsfile
```

---

## 🔍 Code Search & Analysis

### Searching Code

```bash
# grep (standard)
grep -r "pattern" .
grep -rn "function_name" src/

# ripgrep (faster)
rg "pattern"
rg -t python "class.*Model"
rg -l "TODO"              # Files with TODOs

# ag (silver searcher)
ag "pattern"
ag -G "*.py" "import"
```

### Code Analysis

```bash
# Line counting
cloc .                    # Count lines of code
wc -l **/*.py            # Line count by extension

# Complexity
radon cc src/ -a         # Cyclomatic complexity (Python)
eslint --ext .js .       # JavaScript linting

# Security scanning
bandit -r src/           # Python security
npm audit                # JavaScript dependencies
safety check             # Python dependencies
```

---

## 📝 Documentation Tools

### Generating Documentation

```bash
# Python
pdoc src/                # API docs
sphinx-build docs/ output/

# JavaScript
jsdoc src/
typedoc src/

# Go
godoc -http=:6060

# Rust
cargo doc --open
```

### Markdown Tools

```bash
# Preview
grip README.md           # GitHub-flavored
mdcat README.md          # Terminal rendering

# Linting
markdownlint *.md
markdown-link-check README.md

# Converting
pandoc README.md -o README.pdf
```

---

## 🎨 Formatting & Linting

### Code Formatters

```bash
# Python
black .
autopep8 --in-place --recursive .
isort .

# JavaScript
prettier --write "**/*.{js,jsx,ts,tsx,json,md}"
eslint --fix .

# Go
gofmt -w .
goimports -w .

# Rust
cargo fmt
```

### Linters

```bash
# Python
ruff check .
flake8 .
pylint src/
mypy src/

# JavaScript
eslint .
tsc --noEmit         # TypeScript type check

# Go
golangci-lint run

# Rust
cargo clippy
```

---

## 🔧 Build Tools

### Make

```bash
# Common targets
make help            # Show available commands
make build           # Build project
make test            # Run tests
make clean           # Clean build artifacts
make install         # Install dependencies
make deploy          # Deploy project
```

### Task Runners

```bash
# npm scripts
npm run build
npm run dev
npm run lint
npm run format

# Just (modern make alternative)
just build
just test
just deploy
```

---

## 🌐 API & HTTP Tools

### Making Requests

```bash
# curl
curl -X GET http://api.example.com/endpoint
curl -X POST -H "Content-Type: application/json" \
  -d '{"key":"value"}' http://api.example.com/

# httpie (user-friendly)
http GET http://api.example.com/endpoint
http POST http://api.example.com/ key=value

# wget (downloading)
wget http://example.com/file.tar.gz
```

### API Testing

```bash
# Postman CLI
newman run collection.json

# REST Client
http :8000/api/users
http POST :8000/api/users name="John"

# GraphQL
curl -X POST -H "Content-Type: application/json" \
  -d '{"query": "{ users { id name } }"}' \
  http://localhost:4000/graphql
```

---

## 📊 Performance Profiling

### CPU Profiling

```bash
# Python
python -m cProfile script.py
py-spy record -o profile.svg -- python script.py

# Node.js
node --prof script.js
clinic doctor -- node script.js

# Go
go test -cpuprofile=cpu.prof
go tool pprof cpu.prof
```

### Memory Profiling

```bash
# Python
memory_profiler script.py
mprof run script.py && mprof plot

# Node.js
node --inspect script.js
clinic heapprofiler -- node script.js

# valgrind (C/C++)
valgrind --leak-check=full ./program
```

---

## 🎯 Project-Specific Tools

> **Customize this section** for your project.

### Custom Scripts

```bash
# Example: scripts/
./scripts/setup.sh           # Initial setup
./scripts/test.sh            # Run all tests
./scripts/deploy.sh          # Deploy to production
./scripts/backup.sh          # Backup data
./scripts/migrate.sh         # Run migrations
```

### Custom Commands

```bash
# Example: Makefile targets
make bootstrap               # Set up development environment
make docker-up              # Start all containers
make seed-db                # Seed database with test data
make generate-docs          # Generate documentation
```

---

## 📚 Quick Reference

### Most Commonly Used:

```bash
# Development
git status, git diff, git log
grep -r "pattern" .
pytest tests/
docker-compose up

# Debugging
tail -f logs/app.log
docker logs container-name
curl http://localhost:8000/health
psql -U user -d database

# Deployment
make deploy
docker build && docker push
kubectl apply -f deployment.yaml
```

### Emergency Commands:

```bash
# Kill processes
pkill -f process-name
kill -9 $(pgrep process)

# Free space
docker system prune -a
rm -rf node_modules/ __pycache__/

# Restart services
docker-compose restart
systemctl restart service-name

# Check connectivity
ping google.com
curl -I http://service:8000/health
```

---

## 🔄 Updating This Document

When new tools are added to the project:
1. Update the relevant section
2. Add usage examples
3. Document any MCP server changes
4. Update project-specific sections
5. Test all commands work

---

**Last Updated:** 2025-12-03
**Maintainer:** [Your Team]
