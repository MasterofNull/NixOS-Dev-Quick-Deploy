-- ============================================================================
-- NixOS AI Stack - PostgreSQL Schema Initialization
-- Version: 1.0.0
-- Purpose: Centralized knowledge base for all system data
-- ============================================================================
-- This schema is automatically run when the database is first created
-- It creates tables for: documentation, system state, deployment history,
-- code analysis, telemetry, learning patterns, and more.
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";  -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For full-text search

-- ============================================================================
-- 1. DOCUMENTATION & KNOWLEDGE BASE
-- ============================================================================

-- All markdown documentation files
CREATE TABLE documentation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type VARCHAR(50) DEFAULT 'markdown',
    category VARCHAR(100),
    tags TEXT[],
    metadata JSONB DEFAULT '{}',
    checksum VARCHAR(64),  -- SHA256 of content
    embedding vector(384),  -- Sentence transformer embedding
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    indexed_at TIMESTAMP DEFAULT NOW(),
    relevance_score FLOAT DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP
);

CREATE INDEX idx_documentation_path ON documentation(file_path);
CREATE INDEX idx_documentation_category ON documentation(category);
CREATE INDEX idx_documentation_tags ON documentation USING GIN(tags);
CREATE INDEX idx_documentation_embedding ON documentation USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_documentation_content_fts ON documentation USING GIN(to_tsvector('english', content));
CREATE INDEX idx_documentation_updated ON documentation(updated_at DESC);

-- ============================================================================
-- 2. SYSTEM STATE & CONFIGURATION
-- ============================================================================

-- System deployments and their state
CREATE TABLE deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_type VARCHAR(50) NOT NULL, -- 'initial', 'update', 'rollback'
    phase INTEGER,
    phase_name VARCHAR(100),
    status VARCHAR(50) NOT NULL, -- 'running', 'completed', 'failed', 'rolled_back'
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    log_file TEXT,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    packages_installed TEXT[],
    services_configured TEXT[],
    git_commit VARCHAR(40),
    nixos_generation INTEGER
);

CREATE INDEX idx_deployments_status ON deployments(status);
CREATE INDEX idx_deployments_started ON deployments(started_at DESC);
CREATE INDEX idx_deployments_type ON deployments(deployment_type);

-- Deployment reports and session logs (instead of cluttering repo with markdown files)
CREATE TABLE deployment_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    report_type VARCHAR(50) NOT NULL, -- 'deployment', 'fix', 'upgrade', 'error', 'debug', 'summary', 'session'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Relationships
    deployment_id UUID REFERENCES deployments(id) ON DELETE SET NULL,

    -- Search and categorization
    tags TEXT[],
    category VARCHAR(100),

    -- Relevance and archival
    is_archived BOOLEAN DEFAULT FALSE,
    archived_at TIMESTAMP,
    relevance_score FLOAT DEFAULT 1.0,

    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
    ) STORED
);

CREATE INDEX idx_reports_type ON deployment_reports(report_type);
CREATE INDEX idx_reports_created ON deployment_reports(created_at DESC);
CREATE INDEX idx_reports_deployment ON deployment_reports(deployment_id);
CREATE INDEX idx_reports_search ON deployment_reports USING GIN(search_vector);
CREATE INDEX idx_reports_metadata ON deployment_reports USING GIN(metadata);
CREATE INDEX idx_reports_tags ON deployment_reports USING GIN(tags);
CREATE INDEX idx_reports_archived ON deployment_reports(is_archived, created_at DESC);

-- Auto-update updated_at timestamp for reports
CREATE OR REPLACE FUNCTION update_report_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_report_updated_at
BEFORE UPDATE ON deployment_reports
FOR EACH ROW
EXECUTE FUNCTION update_report_updated_at();

-- System configuration snapshots
CREATE TABLE system_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_type VARCHAR(50) NOT NULL, -- 'pre-deploy', 'post-deploy', 'manual'
    nixos_version VARCHAR(50),
    kernel_version VARCHAR(100),
    packages JSONB,  -- All installed packages
    services JSONB,  -- Running services
    containers JSONB,  -- Container status
    hardware JSONB,  -- Hardware info
    disk_usage JSONB,  -- Disk space per mount
    memory_usage BIGINT,  -- MB
    cpu_info JSONB,
    gpu_info JSONB,
    network_info JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    deployment_id UUID REFERENCES deployments(id)
);

CREATE INDEX idx_snapshots_created ON system_snapshots(created_at DESC);
CREATE INDEX idx_snapshots_deployment ON system_snapshots(deployment_id);

-- ============================================================================
-- 3. CODE REPOSITORY & FILE TRACKING
-- ============================================================================

-- Git repositories
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    path TEXT NOT NULL UNIQUE,
    remote_url TEXT,
    current_branch VARCHAR(200),
    latest_commit VARCHAR(40),
    commit_count INTEGER,
    file_count INTEGER,
    line_count INTEGER,
    primary_language VARCHAR(50),
    languages JSONB,  -- {language: line_count}
    last_commit_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_repos_path ON repositories(path);
CREATE INDEX idx_repos_name ON repositories(name);
CREATE INDEX idx_repos_active ON repositories(is_active);

-- Source code files
CREATE TABLE source_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    file_type VARCHAR(50),
    language VARCHAR(50),
    size_bytes BIGINT,
    line_count INTEGER,
    code_lines INTEGER,  -- Excluding comments/blank
    comment_lines INTEGER,
    blank_lines INTEGER,
    complexity_score FLOAT,  -- Cyclomatic complexity
    content_hash VARCHAR(64),  -- SHA256
    last_modified TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    indexed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(repository_id, relative_path)
);

CREATE INDEX idx_source_files_repo ON source_files(repository_id);
CREATE INDEX idx_source_files_path ON source_files(relative_path);
CREATE INDEX idx_source_files_type ON source_files(file_type);
CREATE INDEX idx_source_files_language ON source_files(language);
CREATE INDEX idx_source_files_modified ON source_files(last_modified DESC);

-- Code functions/classes (for searchability)
CREATE TABLE code_symbols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID REFERENCES source_files(id) ON DELETE CASCADE,
    symbol_type VARCHAR(50), -- 'function', 'class', 'method', 'variable'
    name TEXT NOT NULL,
    qualified_name TEXT,  -- Full namespace path
    line_number INTEGER,
    end_line INTEGER,
    signature TEXT,
    docstring TEXT,
    complexity INTEGER,
    parameters JSONB,
    return_type VARCHAR(200),
    decorators TEXT[],
    is_public BOOLEAN DEFAULT TRUE,
    embedding vector(384),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_code_symbols_file ON code_symbols(file_id);
CREATE INDEX idx_code_symbols_type ON code_symbols(symbol_type);
CREATE INDEX idx_code_symbols_name ON code_symbols(name);
CREATE INDEX idx_code_symbols_embedding ON code_symbols USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- 4. DEPLOYMENT TELEMETRY & EVENTS
-- ============================================================================

-- Deployment events and telemetry
CREATE TABLE telemetry_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50), -- 'deployment', 'error', 'performance', 'usage'
    severity VARCHAR(20), -- 'info', 'warning', 'error', 'critical'
    source VARCHAR(100),  -- Which component generated this
    message TEXT,
    metadata JSONB DEFAULT '{}',
    duration_ms INTEGER,
    error_details JSONB,
    stack_trace TEXT,
    user_id VARCHAR(100),
    session_id UUID,
    deployment_id UUID REFERENCES deployments(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_telemetry_type ON telemetry_events(event_type);
CREATE INDEX idx_telemetry_category ON telemetry_events(event_category);
CREATE INDEX idx_telemetry_severity ON telemetry_events(severity);
CREATE INDEX idx_telemetry_created ON telemetry_events(created_at DESC);
CREATE INDEX idx_telemetry_deployment ON telemetry_events(deployment_id);

-- ============================================================================
-- 5. AI/ML TOOL REGISTRY & USAGE
-- ============================================================================

-- MCP tools and AI agents
CREATE TABLE tools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_id VARCHAR(200) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    tool_type VARCHAR(50), -- 'mcp_server', 'npm_package', 'vscode_extension', 'cli'
    version VARCHAR(50),
    description TEXT,
    capabilities JSONB,  -- What the tool can do
    parameters JSONB,  -- Tool parameters schema
    server_url TEXT,
    port INTEGER,
    status VARCHAR(50), -- 'active', 'inactive', 'error', 'disabled'
    install_path TEXT,
    config JSONB,
    dependencies TEXT[],
    last_health_check TIMESTAMP,
    health_status VARCHAR(50),
    usage_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    avg_execution_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tools_id ON tools(tool_id);
CREATE INDEX idx_tools_type ON tools(tool_type);
CREATE INDEX idx_tools_status ON tools(status);
CREATE INDEX idx_tools_health ON tools(last_health_check DESC);

-- Tool execution history
CREATE TABLE tool_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_id UUID REFERENCES tools(id),
    execution_type VARCHAR(50), -- 'manual', 'automated', 'agent'
    input_params JSONB,
    output_data JSONB,
    status VARCHAR(50), -- 'success', 'error', 'timeout'
    duration_ms INTEGER,
    error_message TEXT,
    session_id UUID,
    user_id VARCHAR(100),
    context JSONB,  -- Surrounding context
    executed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tool_exec_tool ON tool_executions(tool_id);
CREATE INDEX idx_tool_exec_executed ON tool_executions(executed_at DESC);
CREATE INDEX idx_tool_exec_status ON tool_executions(status);

-- ============================================================================
-- 6. LEARNING PATTERNS & AI INSIGHTS
-- ============================================================================

-- Extracted patterns from usage
CREATE TABLE learning_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pattern_type VARCHAR(100), -- 'code_pattern', 'error_solution', 'best_practice', 'workflow'
    title TEXT NOT NULL,
    description TEXT,
    pattern_data JSONB,  -- The actual pattern
    context JSONB,  -- When this pattern applies
    confidence_score FLOAT,
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT,
    source_interactions UUID[],  -- References to interactions that generated this
    tags TEXT[],
    embedding vector(384),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP
);

CREATE INDEX idx_patterns_type ON learning_patterns(pattern_type);
CREATE INDEX idx_patterns_confidence ON learning_patterns(confidence_score DESC);
CREATE INDEX idx_patterns_usage ON learning_patterns(usage_count DESC);
CREATE INDEX idx_patterns_embedding ON learning_patterns USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_patterns_tags ON learning_patterns USING GIN(tags);

-- ============================================================================
-- 7. ERROR TRACKING & SOLUTIONS
-- ============================================================================

-- Known errors and their solutions
CREATE TABLE errors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    error_type VARCHAR(100),
    error_code VARCHAR(50),
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    context JSONB,  -- Where/when it occurred
    severity VARCHAR(20),
    occurrence_count INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolution_pattern_id UUID REFERENCES learning_patterns(id),
    embedding vector(384)
);

CREATE INDEX idx_errors_type ON errors(error_type);
CREATE INDEX idx_errors_resolved ON errors(resolved);
CREATE INDEX idx_errors_last_seen ON errors(last_seen DESC);
CREATE INDEX idx_errors_embedding ON errors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================================
-- 8. PACKAGE & DEPENDENCY TRACKING
-- ============================================================================

-- All system packages
CREATE TABLE packages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_manager VARCHAR(50), -- 'nix', 'npm', 'pip', 'cargo', 'flatpak'
    package_name VARCHAR(200) NOT NULL,
    version VARCHAR(100),
    installed_version VARCHAR(100),
    available_version VARCHAR(100),
    description TEXT,
    homepage TEXT,
    license VARCHAR(100),
    size_bytes BIGINT,
    install_path TEXT,
    dependencies TEXT[],
    dependents TEXT[],  -- Reverse dependencies
    is_direct BOOLEAN DEFAULT TRUE,  -- Direct vs transitive
    install_date TIMESTAMP,
    update_available BOOLEAN DEFAULT FALSE,
    last_checked TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(package_manager, package_name)
);

CREATE INDEX idx_packages_manager ON packages(package_manager);
CREATE INDEX idx_packages_name ON packages(package_name);
CREATE INDEX idx_packages_update ON packages(update_available);

-- ============================================================================
-- 9. CONTAINER & SERVICE TRACKING
-- ============================================================================

-- Container instances
CREATE TABLE containers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    container_id VARCHAR(64) UNIQUE,
    name VARCHAR(200) NOT NULL,
    image VARCHAR(300),
    status VARCHAR(50), -- 'running', 'exited', 'created', 'restarting'
    ports JSONB,  -- Port mappings
    volumes JSONB,  -- Volume mounts
    environment JSONB,  -- Environment variables
    labels JSONB,
    networks TEXT[],
    resource_limits JSONB,
    health_status VARCHAR(50),
    restart_count INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    stopped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_containers_name ON containers(name);
CREATE INDEX idx_containers_status ON containers(status);
CREATE INDEX idx_containers_health ON containers(health_status);

-- ============================================================================
-- 10. CONFIGURATION & SETTINGS
-- ============================================================================

-- System-wide key-value configuration
CREATE TABLE configuration (
    key VARCHAR(200) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    category VARCHAR(100),
    is_sensitive BOOLEAN DEFAULT FALSE,
    default_value JSONB,
    validation_schema JSONB,
    updated_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_config_category ON configuration(category);

-- ============================================================================
-- 11. SEARCH & RETRIEVAL VIEWS
-- ============================================================================

-- Combined search view for all searchable content
CREATE VIEW searchable_content AS
SELECT
    'documentation' as source_type,
    id,
    title as name,
    content,
    embedding,
    tags,
    updated_at
FROM documentation
UNION ALL
SELECT
    'code_symbol' as source_type,
    id,
    name,
    COALESCE(docstring, signature) as content,
    embedding,
    ARRAY[]::TEXT[] as tags,
    updated_at
FROM code_symbols
WHERE embedding IS NOT NULL
UNION ALL
SELECT
    'learning_pattern' as source_type,
    id,
    title as name,
    description as content,
    embedding,
    tags,
    updated_at
FROM learning_patterns
WHERE embedding IS NOT NULL;

-- Recent activity view
CREATE VIEW recent_activity AS
SELECT
    'deployment' as activity_type,
    id,
    phase_name as description,
    status,
    started_at as timestamp
FROM deployments
UNION ALL
SELECT
    'tool_execution' as activity_type,
    id,
    (SELECT name FROM tools WHERE tools.id = tool_executions.tool_id) as description,
    status,
    executed_at as timestamp
FROM tool_executions
ORDER BY timestamp DESC
LIMIT 100;

-- System health summary view
CREATE VIEW system_health AS
SELECT
    (SELECT COUNT(*) FROM containers WHERE status = 'running') as running_containers,
    (SELECT COUNT(*) FROM containers WHERE health_status = 'unhealthy') as unhealthy_containers,
    (SELECT COUNT(*) FROM tools WHERE status = 'active') as active_tools,
    (SELECT COUNT(*) FROM tools WHERE health_status = 'error') as errored_tools,
    (SELECT COUNT(*) FROM errors WHERE NOT resolved AND last_seen > NOW() - INTERVAL '24 hours') as recent_errors,
    (SELECT COUNT(*) FROM deployments WHERE status = 'running') as active_deployments,
    (SELECT MAX(created_at) FROM system_snapshots) as last_snapshot;

-- ============================================================================
-- 12. AUTOMATIC TRIGGERS
-- ============================================================================

-- Update timestamps automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_documentation_updated_at BEFORE UPDATE ON documentation
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tools_updated_at BEFORE UPDATE ON tools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patterns_updated_at BEFORE UPDATE ON learning_patterns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Increment access count on documentation reads
CREATE OR REPLACE FUNCTION increment_doc_access()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE documentation
    SET access_count = access_count + 1,
        last_accessed = NOW()
    WHERE id = NEW.id;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ============================================================================
-- 13. INITIAL DATA
-- ============================================================================

-- Insert default configuration
INSERT INTO configuration (key, value, description, category) VALUES
('system.version', '"1.0.0"', 'NixOS AI Stack version', 'system'),
('ai.default_model', '"qwen2.5-coder-7b"', 'Default LLM model', 'ai'),
('deployment.auto_backup', 'true', 'Enable automatic backups before deployment', 'deployment'),
('telemetry.enabled', 'true', 'Enable telemetry collection', 'telemetry'),
('learning.enabled', 'true', 'Enable pattern learning', 'learning'),
('search.max_results', '50', 'Maximum search results to return', 'search');

-- Grant permissions (for AIDB and other services)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mcp;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mcp;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO mcp;

-- ============================================================================
-- Schema initialization complete
-- ============================================================================
