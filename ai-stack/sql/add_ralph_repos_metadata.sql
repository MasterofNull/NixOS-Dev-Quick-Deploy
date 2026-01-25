-- Add Ralph Wiggum GitHub Repository Metadata
-- January 2026 - Comprehensive Ralph implementations

-- Create table for tracking Ralph/AI agent repositories
CREATE TABLE IF NOT EXISTS ralph_implementations (
    id SERIAL PRIMARY KEY,
    repo_name VARCHAR(255) NOT NULL UNIQUE,
    repo_url TEXT NOT NULL,
    maintainer VARCHAR(255),
    description TEXT,
    stars INTEGER,
    version VARCHAR(100),
    key_features JSONB,
    status VARCHAR(50), -- 'production', 'experimental', 'reference'
    recommended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert Ralph implementations
INSERT INTO ralph_implementations (repo_name, repo_url, maintainer, description, stars, version, key_features, status, recommended) VALUES
(
    'frankbria/ralph-claude-code',
    'https://github.com/frankbria/ralph-claude-code',
    'frankbria',
    'Autonomous AI development loop for Claude Code with intelligent exit detection, rate limiting, and circuit breaker. Most actively developed Ralph implementation with comprehensive testing.',
    653,
    'v0.9.8',
    '{"features": ["Intelligent exit detection", "Rate limiting (100 calls/hour, configurable)", "Circuit breaker with advanced error detection", "Response Analyzer with AI-powered semantic understanding", "Dashboard monitoring", "CI/CD Integration with GitHub Actions", "276 tests with 100% pass rate"]}'::jsonb,
    'production',
    TRUE
),
(
    'snarktank/ralph',
    'https://github.com/snarktank/ralph',
    'Ryan Carson (snarktank)',
    'Autonomous AI agent loop that runs Amp repeatedly until all PRD items are complete. Memory persists via git history, progress.txt, and prd.json.',
    NULL,
    'latest',
    '{"features": ["Automatic handoff when context fills up", "Updates AGENTS.md files with learnings after each iteration", "Memory persists via git history", "Exits when all stories have passes: true", "Works with Amp agent"]}'::jsonb,
    'production',
    TRUE
),
(
    'vercel-labs/ralph-loop-agent',
    'https://github.com/vercel-labs/ralph-loop-agent',
    'Vercel Labs (official)',
    'Continuous Autonomy for the AI SDK. Development methodology built around continuous AI agent loops for Vercel AI SDK.',
    NULL,
    'latest',
    '{"features": ["Continuous AI agent loops", "AI SDK integration", "Vercel ecosystem optimized", "Official Vercel implementation"]}'::jsonb,
    'production',
    TRUE
),
(
    'mikeyobrien/ralph-orchestrator',
    'https://github.com/mikeyobrien/ralph-orchestrator',
    'mikeyobrien',
    'An improved implementation of the Ralph Wiggum technique for autonomous AI agent orchestration. Production-ready with comprehensive documentation.',
    NULL,
    'latest',
    '{"features": ["Production-ready implementation", "Comprehensive documentation at mikeyobrien.github.io/ralph-orchestrator", "Improved orchestration patterns", "Multi-agent support"]}'::jsonb,
    'production',
    TRUE
),
(
    'UtpalJayNadiger/ralphwiggumexperiment',
    'https://github.com/UtpalJayNadiger/ralphwiggumexperiment',
    'UtpalJayNadiger',
    'The Ralph Wiggum Experiment: Can AI meaningfully self-improve through iterative loops? Experimental research repository.',
    NULL,
    'experimental',
    '{"features": ["AI self-improvement research", "Iterative loop experiments", "Research-focused"]}'::jsonb,
    'experimental',
    FALSE
)
ON CONFLICT (repo_name) DO UPDATE SET
    description = EXCLUDED.description,
    stars = EXCLUDED.stars,
    version = EXCLUDED.version,
    key_features = EXCLUDED.key_features,
    status = EXCLUDED.status,
    recommended = EXCLUDED.recommended,
    updated_at = NOW();

-- Update existing ralph-wiggum package to reference multiple implementations
UPDATE package_versions
SET git_repo_url = 'https://github.com/mikeyobrien/ralph-orchestrator'
WHERE package_name = 'ralph-wiggum' AND container_name = 'ralph-wiggum';

-- Add note about Ralph technique to package_changelogs
INSERT INTO package_changelogs (package_name, version, release_date, changelog_text, breaking_changes, security_fixes) VALUES
(
    'ralph-wiggum',
    '2026.01',
    '2026-01-10',
    'Ralph Wiggum Loop technique has become the biggest name in AI development in January 2026. Named after Geoffrey Huntley''s technique, the core principle is "naive persistence beats sophisticated complexity". Multiple production implementations available: frankbria/ralph-claude-code (653 stars, v0.9.8, most active), snarktank/ralph (Amp integration), vercel-labs/ralph-loop-agent (AI SDK), mikeyobrien/ralph-orchestrator (production-ready). Real-world success: 14-hour autonomous sessions upgrading React v16→v19 without human input. Featured in DEV Community, VentureBeat, Medium, listed on AwesomeClaude.',
    FALSE,
    FALSE
)
ON CONFLICT (package_name, version) DO UPDATE SET
    changelog_text = EXCLUDED.changelog_text,
    release_date = EXCLUDED.release_date;

-- Create view for recommended Ralph implementations
CREATE OR REPLACE VIEW recommended_ralph_implementations AS
SELECT
    repo_name,
    repo_url,
    maintainer,
    description,
    stars,
    version,
    key_features,
    status
FROM ralph_implementations
WHERE recommended = TRUE
ORDER BY
    CASE status
        WHEN 'production' THEN 1
        WHEN 'experimental' THEN 2
        ELSE 3
    END,
    stars DESC NULLS LAST;

-- Summary query
SELECT
    'Total Ralph Implementations' as metric,
    COUNT(*)::text as value
FROM ralph_implementations
UNION ALL
SELECT
    'Production Ready',
    COUNT(*)::text
FROM ralph_implementations
WHERE status = 'production'
UNION ALL
SELECT
    'Recommended',
    COUNT(*)::text
FROM ralph_implementations
WHERE recommended = TRUE;

COMMENT ON TABLE ralph_implementations IS 'Tracks Ralph Wiggum autonomous agent implementations and GitHub repositories';
COMMENT ON VIEW recommended_ralph_implementations IS 'Production-ready and recommended Ralph implementations for reference';
