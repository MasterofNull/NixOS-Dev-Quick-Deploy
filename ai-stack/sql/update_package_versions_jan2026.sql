-- Package Version Updates - January 2026
-- Based on web research of actual current versions
-- Updated: 2026-01-10

-- Update package versions to actual January 2026 releases
UPDATE package_versions SET
    current_version = 'not_installed',
    latest_version = '0.86.1',
    check_date = NOW()
WHERE package_name = 'aider-chat' AND container_name = 'aider-wrapper';

UPDATE package_versions SET
    current_version = '0.115.6',
    latest_version = '0.128.0',
    check_date = NOW()
WHERE package_name = 'fastapi' AND container_name = 'aider-wrapper';

UPDATE package_versions SET
    current_version = '0.122.0',
    latest_version = '0.128.0',
    check_date = NOW()
WHERE package_name = 'fastapi' AND container_name = 'aidb';

UPDATE package_versions SET
    current_version = 'v1.7.4',
    latest_version = 'v1.16.0',
    check_date = NOW()
WHERE package_name = 'qdrant';

UPDATE package_versions SET
    current_version = 'b7626',
    latest_version = 'b7691',
    check_date = NOW()
WHERE package_name = 'llama.cpp';

UPDATE package_versions SET
    current_version = '15',
    latest_version = '18.1',
    check_date = NOW()
WHERE package_name = 'postgres';

UPDATE package_versions SET
    current_version = '7',
    latest_version = '8.4',
    check_date = NOW()
WHERE package_name = 'redis';

UPDATE package_versions SET
    current_version = 'v2.45.0',
    latest_version = 'v3.9.1',
    check_date = NOW()
WHERE package_name = 'prometheus';

UPDATE package_versions SET
    current_version = '10.2.0',
    latest_version = '12.3.0',
    check_date = NOW()
WHERE package_name = 'grafana';

-- Add new changelog entries for major updates
INSERT INTO package_changelogs (package_name, version, release_date, changelog_text, breaking_changes, security_fixes) VALUES
('aider-chat', '0.86.1', '2026-01-07', 'Major improvements: Support for Claude Sonnet 4 and Opus 4, GPT 4.1/mini/nano support, improved codebase mapping, 70-80% of code written by aider itself. Works best with Claude 3.7 Sonnet, DeepSeek R1, OpenAI o1/o3-mini. Python 3.8-3.13 support.', FALSE, FALSE),
('qdrant', 'v1.16.0', '2026-01-01', 'Tiered multitenancy with tenant promotion, inline storage for disk-efficient vector search, ACORN algorithm for improved filtered search, conditional update API for embedding model migration, improved full-text search with text_any condition and ASCII folding', FALSE, FALSE),
('postgres', '18.1', '2025-11-13', 'Latest major release with security fixes and bug improvements. PostgreSQL 13 is now EOL. Active support for versions 18, 17, 16, 15, 14.', FALSE, TRUE),
('llama.cpp', 'b7691', '2026-01-10', 'Latest build with MobileNetV5 helpers improvements, removal of unused functions, updates to conversion scripts with explicit tensor mapping. Includes platform-specific binaries for Windows CUDA 12.4/13.1, macOS ARM64/x64, Ubuntu Vulkan', FALSE, FALSE),
('redis', '8.4', '2026-01-01', 'Latest GA release for Redis Open Source', FALSE, FALSE),
('prometheus', '3.9.1', '2026-01-07', 'Bugfix release: agent crash fix, scraping relabel keep/drop fixes. Major v3.0 features: New Mantine UI interface, Native Histograms as stable feature, PromLens-style tree view, better metrics explorer', FALSE, TRUE),
('grafana', '12.3.0', '2026-01-01', 'Reimagined log exploration, enhanced data connectivity, monthly release schedule', FALSE, FALSE)
ON CONFLICT (package_name, version) DO UPDATE SET
    changelog_text = EXCLUDED.changelog_text,
    release_date = EXCLUDED.release_date,
    breaking_changes = EXCLUDED.breaking_changes,
    security_fixes = EXCLUDED.security_fixes;

-- Query to see all updates needed
SELECT
    package_name,
    container_name,
    current_version,
    latest_version,
    git_repo_url
FROM packages_needing_updates
ORDER BY
    CASE
        WHEN package_name = 'aider-chat' THEN 1
        WHEN package_name = 'prometheus' THEN 2
        WHEN package_name = 'grafana' THEN 3
        WHEN package_name = 'qdrant' THEN 4
        WHEN package_name = 'postgres' THEN 5
        ELSE 6
    END;
