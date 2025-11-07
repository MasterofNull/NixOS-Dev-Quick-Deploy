#!/usr/bin/env bash
# NPM package manifest for AI coding assistants installed by Phase 6.
# Each entry format:
#   package|display_name|bin_command|wrapper_name|extension_id|debug_env
# - package: npm identifier used with npm install -g
# - display_name: human friendly name for logging
# - bin_command: primary command exposed by the npm package (used to resolve bin script)
# - wrapper_name: filename (without path) for the smart Node wrapper we create
# - extension_id: optional Open VSX / VSCode Marketplace identifier (codium --install-extension)
# - debug_env: optional environment variable that enables verbose wrapper logging
#
# Wrapper files are created under ~/.npm-global/bin and point at the resolved bin
# entry inside ~/.npm-global/lib/node_modules/<package>.

NPM_AI_PACKAGE_MANIFEST=(
  "@anthropic-ai/claude-code|Claude Code|claude|claude-wrapper|Anthropic.claude-code|CLAUDE_DEBUG"
  "@openai/codex|GPT CodeX CLI|codex|gpt-codex-wrapper|OpenAI.gpt-codex|GPT_CODEX_DEBUG"
  "@openai/codex|Codex IDE|codex|codex-wrapper|OpenAI.codex-ide|CODEX_DEBUG"
  "openai|OpenAI CLI|openai|openai-wrapper|openai.chatgpt|OPENAI_DEBUG"
  "@gooseai/cli|Goose CLI|gooseai|gooseai-wrapper|GooseAI.gooseai-vscode|GOOSEAI_DEBUG"
)

declare -gA NPM_AI_PACKAGE_MANUAL_URLS=(
  ["@gooseai/cli"]="https://block.github.io/goose/docs/getting-started/installation/"
)

declare -gA VSCODE_AI_EXTENSION_FALLBACK_URLS=(
  ["OpenAI.gpt-codex"]="https://marketplace.visualstudio.com/items?itemName=OpenAI.gpt-codex"
  ["OpenAI.codex-ide"]="https://marketplace.visualstudio.com/items?itemName=OpenAI.codex-ide"
  ["GooseAI.gooseai-vscode"]="https://marketplace.visualstudio.com/items?itemName=GooseAI.gooseai-vscode"
)
