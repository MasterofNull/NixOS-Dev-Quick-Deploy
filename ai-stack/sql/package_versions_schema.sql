-- Package Versions Tracking Schema
-- Stores version information for all packages used in the AI stack
-- Updated: 2026-01-11

CREATE TABLE IF NOT EXISTS package_versions (
    id SERIAL PRIMARY KEY,
    package_name VARCHAR(255) NOT NULL,
    package_type VARCHAR(50) NOT NULL,  -- 'python', 'container', 'binary'
    current_version VARCHAR(100),
    latest_version VARCHAR(100),
    git_repo_url TEXT,
    container_name VARCHAR(255),  -- Which container uses this package
    check_date TIMESTAMP DEFAULT NOW(),
    update_available BOOLEAN GENERATED ALWAYS AS (current_version != latest_version) STORED,
    UNIQUE(package_name, container_name)
);

CREATE TABLE IF NOT EXISTS package_changelogs (
    id SERIAL PRIMARY KEY,
    package_name VARCHAR(255) NOT NULL,
    version VARCHAR(100) NOT NULL,
    release_date DATE,
    changelog_text TEXT,
    breaking_changes BOOLEAN DEFAULT FALSE,
    security_fixes BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(package_name, version)
);

CREATE TABLE IF NOT EXISTS package_dependencies (
    id SERIAL PRIMARY KEY,
    parent_package VARCHAR(255) NOT NULL,
    dependency_package VARCHAR(255) NOT NULL,
    version_constraint VARCHAR(100),
    required BOOLEAN DEFAULT TRUE,
    UNIQUE(parent_package, dependency_package)
);

-- Create indexes for fast queries
CREATE INDEX idx_pkg_name ON package_versions(package_name);
CREATE INDEX idx_container ON package_versions(container_name);
CREATE INDEX idx_update_available ON package_versions(update_available);
CREATE INDEX idx_changelog_pkg ON package_changelogs(package_name);

-- Insert initial package data
INSERT INTO package_versions (package_name, package_type, current_version, latest_version, git_repo_url, container_name) VALUES
-- Aider-Wrapper packages
('aider-chat', 'python', 'not_installed', '0.16.0', 'https://github.com/paul-gauthier/aider', 'aider-wrapper'),
('fastapi', 'python', '0.115.6', '0.128.0', 'https://github.com/tiangolo/fastapi', 'aider-wrapper'),
('uvicorn', 'python', '0.34.0', '0.40.0', 'https://github.com/encode/uvicorn', 'aider-wrapper'),
('pydantic', 'python', '2.10.5', '2.12.5', 'https://github.com/pydantic/pydantic', 'aider-wrapper'),
('aiohttp', 'python', '3.13.3', '3.13.3', 'https://github.com/aio-libs/aiohttp', 'aider-wrapper'),
('structlog', 'python', 'unknown', '25.5.0', 'https://github.com/hynek/structlog', 'aider-wrapper'),

-- AIDB packages
('fastapi', 'python', '0.122.0', '0.128.0', 'https://github.com/tiangolo/fastapi', 'aidb'),
('aiohttp', 'python', '3.13.3', '3.13.3', 'https://github.com/aio-libs/aiohttp', 'aidb'),

-- Hybrid-Coordinator packages
('asyncpg', 'python', 'not_installed', '0.31.0', 'https://github.com/MagicStack/asyncpg', 'hybrid-coordinator'),
('qdrant-client', 'python', 'unknown', '1.16.2', 'https://github.com/qdrant/qdrant-client', 'hybrid-coordinator'),

-- Container images
('qdrant', 'container', 'v1.7.4', 'v1.16.0', 'https://github.com/qdrant/qdrant', 'qdrant'),
('llama.cpp', 'container', 'unknown', 'b4570', 'https://github.com/ggerganov/llama.cpp', 'llama-cpp'),
('postgres', 'container', '15', '17.2', 'https://github.com/postgres/postgres', 'postgres'),
('redis', 'container', '7', '8.0.1', 'https://github.com/redis/redis', 'redis'),
('prometheus', 'container', 'v2.45.0', 'v3.2.1', 'https://github.com/prometheus/prometheus', 'prometheus'),
('grafana', 'container', '10.2.0', '11.5.0', 'https://github.com/grafana/grafana', 'grafana')
ON CONFLICT (package_name, container_name) DO UPDATE SET
    current_version = EXCLUDED.current_version,
    latest_version = EXCLUDED.latest_version,
    check_date = NOW();

-- Insert changelog data for Aider (most important update)
INSERT INTO package_changelogs (package_name, version, release_date, changelog_text, breaking_changes, security_fixes) VALUES
('aider-chat', '0.16.0', '2025-01-15', 'Major updates: Improved code editing accuracy, better git integration, support for more LLM providers, enhanced context management, bug fixes', FALSE, FALSE),
('fastapi', '0.128.0', '2025-12-20', 'Performance improvements, better async handling, updated dependencies, new features for WebSocket support', FALSE, TRUE),
('asyncpg', '0.31.0', '2025-11-10', 'Performance optimizations for connection pooling, better error handling, support for PostgreSQL 17', FALSE, FALSE),
('qdrant', 'v1.16.0', '2026-01-05', 'Major performance improvements, new vector search algorithms, better memory management, enhanced API', FALSE, FALSE)
ON CONFLICT (package_name, version) DO NOTHING;

-- Create view for packages needing updates
CREATE OR REPLACE VIEW packages_needing_updates AS
SELECT
    package_name,
    package_type,
    container_name,
    current_version,
    latest_version,
    git_repo_url,
    CASE
        WHEN current_version = 'not_installed' THEN 'install'
        WHEN current_version = 'unknown' THEN 'check'
        WHEN current_version != latest_version THEN 'update'
        ELSE 'current'
    END as action_needed
FROM package_versions
WHERE update_available = TRUE OR current_version IN ('not_installed', 'unknown')
ORDER BY
    CASE package_name
        WHEN 'aider-chat' THEN 1  -- Highest priority
        WHEN 'fastapi' THEN 2
        WHEN 'asyncpg' THEN 3
        ELSE 4
    END,
    package_name;

-- Function to get update summary
CREATE OR REPLACE FUNCTION get_update_summary()
RETURNS TABLE (
    total_packages BIGINT,
    needs_install BIGINT,
    needs_update BIGINT,
    up_to_date BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_packages,
        COUNT(*) FILTER (WHERE current_version = 'not_installed')::BIGINT as needs_install,
        COUNT(*) FILTER (WHERE update_available = TRUE AND current_version != 'not_installed')::BIGINT as needs_update,
        COUNT(*) FILTER (WHERE update_available = FALSE AND current_version NOT IN ('not_installed', 'unknown'))::BIGINT as up_to_date
    FROM package_versions;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE package_versions IS 'Tracks all package versions across the AI stack for automated updates';
COMMENT ON TABLE package_changelogs IS 'Stores release notes and changelog information for LLM context';
COMMENT ON VIEW packages_needing_updates IS 'Shows which packages need installation or updates';
