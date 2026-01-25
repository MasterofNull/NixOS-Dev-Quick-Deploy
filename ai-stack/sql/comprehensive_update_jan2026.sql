-- Comprehensive Package Update - January 2026
-- All versions verified from official sources
-- Includes missing containers and MCP servers

-- Add missing containers to package_versions
INSERT INTO package_versions (package_name, package_type, current_version, latest_version, git_repo_url, container_name) VALUES
('jaeger', 'container', 'v1.x', 'v2.0', 'https://github.com/jaegertracing/jaeger', 'jaeger'),
('mindsdb', 'container', 'unknown', '25.13.1', 'https://github.com/mindsdb/mindsdb', 'mindsdb'),
('container-engine', 'service', 'unknown', '1.0.0', 'custom', 'container-engine'),
('dashboard-api', 'service', 'unknown', '1.0.0', 'custom', 'dashboard-api'),
('embeddings-service', 'service', 'unknown', '1.0.0', 'custom', 'embeddings-service'),
('ralph-wiggum', 'service', '1.0.0', 'compare', 'https://github.com/mikeyobrien/ralph-orchestrator', 'ralph-wiggum'),
('hybrid-coordinator', 'service', '1.0.0', '1.0.0', 'custom', 'hybrid-coordinator'),
('health-monitor', 'service', '1.0.0', '1.0.0', 'custom', 'health-monitor'),
('qdrant-populator', 'service', '1.0.0', '1.0.0', 'custom', 'qdrant-populator')
ON CONFLICT (package_name, container_name) DO NOTHING;

-- Update with correct January 2026 versions
UPDATE package_versions SET latest_version = 'v2.0', check_date = NOW() WHERE package_name = 'jaeger';
UPDATE package_versions SET latest_version = '0.31.0', check_date = NOW() WHERE package_name = 'asyncpg';
UPDATE package_versions SET latest_version = '25.13.1', check_date = NOW() WHERE package_name = 'mindsdb';

-- Add MindsDB changelog entry
INSERT INTO package_changelogs (package_name, version, release_date, changelog_text, breaking_changes, security_fixes) VALUES
('mindsdb', '25.13.1', '2026-01-08', 'Latest release with security improvements, performance enhancements, and documentation updates. Supports Python 3.10-3.13. Features include API endpoint for validating connection parameters, faster file usage for large datasets, fixed reranking issues, tightened security by hiding Ollama API keys, and automatic ChromaDB storage clearing on Knowledge Base deletion.', FALSE, TRUE)
ON CONFLICT (package_name, version) DO UPDATE SET
    changelog_text = EXCLUDED.changelog_text,
    release_date = EXCLUDED.release_date,
    security_fixes = EXCLUDED.security_fixes;

-- Create view for critical updates
CREATE OR REPLACE VIEW critical_updates_needed AS
SELECT
    package_name,
    container_name,
    current_version,
    latest_version,
    CASE
        WHEN package_name = 'jaeger' THEN 'V1 DEPRECATED Jan 2026'
        WHEN package_name = 'aider-chat' THEN 'Core functionality broken without this'
        WHEN package_name = 'prometheus' THEN 'Security fixes in v3.9.1'
        WHEN package_name = 'asyncpg' THEN 'Required for P3-PERF-002'
        ELSE 'Stability and features'
    END as urgency_reason
FROM packages_needing_updates
WHERE package_name IN ('jaeger', 'aider-chat', 'prometheus', 'asyncpg', 'postgres', 'qdrant')
ORDER BY
    CASE package_name
        WHEN 'jaeger' THEN 1
        WHEN 'aider-chat' THEN 2
        WHEN 'prometheus' THEN 3
        WHEN 'asyncpg' THEN 4
        ELSE 5
    END;

-- Add edge case tracking table
CREATE TABLE IF NOT EXISTS upgrade_edge_cases (
    id SERIAL PRIMARY KEY,
    package_name VARCHAR(255) NOT NULL,
    from_version VARCHAR(100),
    to_version VARCHAR(100),
    edge_case_description TEXT NOT NULL,
    migration_required BOOLEAN DEFAULT FALSE,
    breaking_changes BOOLEAN DEFAULT FALSE,
    data_backup_required BOOLEAN DEFAULT FALSE,
    estimated_downtime_minutes INTEGER,
    mitigation_steps TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Populate known edge cases
INSERT INTO upgrade_edge_cases (package_name, from_version, to_version, edge_case_description, migration_required, breaking_changes, data_backup_required, estimated_downtime_minutes, mitigation_steps) VALUES
('jaeger', 'v1.x', 'v2.0', 'Complete architecture change - now based on OpenTelemetry Collector. Single binary replaces multiple binaries (agent, collector, ingester, query). Configuration format completely different.', TRUE, TRUE, TRUE, 30, 'Export existing traces, rewrite configuration for v2, test in staging first, document rollback procedure'),
('postgres', '15', '18.1', 'PostgreSQL 13 is EOL. Schema changes possible. Performance characteristics different. New features may break old queries.', TRUE, FALSE, TRUE, 60, 'pg_dump before upgrade, test queries after upgrade, check for deprecated features, run ANALYZE after migration'),
('prometheus', 'v2.45.0', 'v3.9.1', 'First major update in 7 years. New UI (Mantine). Native Histograms require explicit config. API changes may break dashboards.', TRUE, TRUE, FALSE, 15, 'Update Grafana dashboards, enable native_histograms in scrape config, test all queries'),
('qdrant', 'v1.7.4', 'v1.16.0', 'New inline storage mode. ACORN algorithm. Conditional update API. May need to rebuild indexes to use new features.', FALSE, FALSE, TRUE, 20, 'Backup vector data, test new features in dev, gradual rollout of inline storage'),
('aider-chat', 'none', '0.86.1', 'Complex dependency tree. Requires specific Python version (3.8-3.13). May conflict with existing packages. Git must be configured in container.', FALSE, FALSE, FALSE, 5, 'Use clean environment, let aider manage dependencies, configure git user/email'),
('ralph-wiggum', '1.0.0', 'v2.35', 'Multi-agent architecture vs single agent. 14 agents vs 1. 85-90% token reduction possible. 559 tests in new version vs unknown in current.', TRUE, TRUE, FALSE, 45, 'Compare current implementation with mikeyobrien/ralph-orchestrator and alfredolopez80/multi-agent-ralph-loop patterns'),
('redis', '7', '8.4', 'New GA release. Persistence configuration may need review. RDB/AOF format changes possible.', FALSE, FALSE, TRUE, 10, 'Backup RDB/AOF files, test persistence after upgrade, verify replication')
ON CONFLICT DO NOTHING;

-- Create dependency conflict tracking
CREATE TABLE IF NOT EXISTS dependency_conflicts (
    id SERIAL PRIMARY KEY,
    package_a VARCHAR(255) NOT NULL,
    package_a_version VARCHAR(100),
    package_b VARCHAR(255) NOT NULL,
    package_b_version VARCHAR(100),
    conflict_type VARCHAR(50), -- 'version', 'api', 'resource'
    description TEXT,
    resolution TEXT,
    identified_date TIMESTAMP DEFAULT NOW()
);

-- Known conflicts from build attempts
INSERT INTO dependency_conflicts (package_a, package_a_version, package_b, package_b_version, conflict_type, description, resolution) VALUES
('aider-chat', '0.86.1', 'aiohttp', '>3.12', 'version', 'Aider 0.86.1 uses aiohttp 3.12.15. Other services may expect 3.13.x', 'Let each container manage its own aiohttp version'),
('fastapi', '0.128.0', 'starlette', '>=0.40.0,<0.51.0', 'version', 'FastAPI 0.128.0 requires specific Starlette range', 'Install fastapi without pinning starlette'),
('prometheus', 'v3.x', 'grafana-dashboards', 'old', 'api', 'Prometheus v3 API changes may break Grafana dashboards', 'Update Grafana to v12.3, regenerate dashboards')
ON CONFLICT DO NOTHING;

-- Summary query
SELECT
    'Total Packages' as metric,
    COUNT(*)::text as value
FROM package_versions
UNION ALL
SELECT
    'Needs Update',
    COUNT(*)::text
FROM packages_needing_updates
UNION ALL
SELECT
    'Critical Updates',
    COUNT(*)::text
FROM critical_updates_needed
UNION ALL
SELECT
    'Edge Cases',
    COUNT(*)::text
FROM upgrade_edge_cases
UNION ALL
SELECT
    'Known Conflicts',
    COUNT(*)::text
FROM dependency_conflicts;

COMMENT ON VIEW critical_updates_needed IS 'Packages requiring immediate attention with urgency reasons';
COMMENT ON TABLE upgrade_edge_cases IS 'Migration issues and downtime estimates for major upgrades';
COMMENT ON TABLE dependency_conflicts IS 'Known version conflicts between packages';
