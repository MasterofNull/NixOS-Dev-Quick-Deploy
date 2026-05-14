# Agentic CLI Tools (Universal Edition)

A suite of token-optimized, context-aware CLI tools designed for AI agents and human users operating in large codebases. Designed to be portable across any Linux, macOS, or CLI environment.

## Features
- **Project Agnostic**: No hardcoded paths. Works in any directory structure.
- **Hierarchical Config**: Respects global (`~/.config/agentic-tools/config.json`) and local (`.agentic-tools.json`) ignore patterns.
- **Token Maxxing**: Hard limits on output, automatic truncation, and structural summarization to preserve LLM context.
- **Environment Aware**: Automatically detects TTY for colors and formatting.

## Tools

### `agrep` (Agentic Grep)
Token-efficient search that avoids noise and limits output.
- **Optimizations**: Filters common noise (`.git`, `node_modules`, `target`, etc.) by default.
- **Usage**: `agrep <pattern> [path]`

### `als` (Agentic List)
Compact directory listing that focuses on relevant files.
- **Optimizations**: Filters noise and limits depth (default: 1) to prevent context blowout.
- **Usage**: `als [path] [-d depth] [-l]`

### `acat` (Agent Cat)
Safe file reading with line numbers and automatic truncation.
- **Optimizations**: Limits output to 500 lines by default. Supports `--start`/`--end`.
- **Usage**: `acat <file> [--head N] [--tail N]`

### `asum` (Agent Summarize)
Structural overview of file architecture.
- **Supported**: Python, JavaScript/TypeScript, Go, Markdown, Nix.
- **Usage**: `asum <file>`

### `adiff` (Agentic Diff)
Token-optimized git diff viewer.
- **Optimizations**: Summarizes large changes, colorizes output for humans, strips noise for agents.
- **Usage**: `adiff [--staged]`

### `alog` (Agentic Log)
Token-efficient log summarizer.
- **Optimizations**: Extracts errors and warnings, collapses repetitive info noise.
- **Usage**: `journalctl -u ai-aidb | alog`

### `atest` (Agentic Test)
Surgical test failure reporter.
- **Optimizations**: Suppresses passing noise, extracts failure stack traces only.
- **Usage**: `atest pytest tests/`

### `aenv` (Agentic Env)
Secure and filtered environment viewer.
- **Optimizations**: Filters system noise, masks sensitive keys (secrets, tokens).
- **Usage**: `aenv AI_`

### `aproc` (Agentic Process)
Capped and filtered process monitor.
- **Optimizations**: Shows only high-resource or project-relevant processes (llama, python, etc.).
- **Usage**: `aproc`

### `ahist` (Agentic History)
Compact git history viewer.
- **Optimizations**: One-line semantic summary, strips colors for agents.
- **Usage**: `ahist -n 10`

## Configuration
You can customize ignore patterns by creating a `.agentic-tools.json` file in your project root:
```json
{
  "ignores": ["dist", "build", "custom-noise"]
}
```
