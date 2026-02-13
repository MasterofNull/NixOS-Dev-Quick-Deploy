#!/usr/bin/env bash
# NPM package manifest for AI coding assistants installed by Phase 6.
# Each entry format:
#   package|version|display_name|bin_command|wrapper_name|extension_id|debug_env
# - package: npm identifier used with npm install -g
# - version: pinned npm version (required; avoid "latest")
# - display_name: human friendly name for logging
# - bin_command: primary command exposed by the npm package (used to resolve bin script)
# - wrapper_name: filename (without path) for the smart Node wrapper we create
# - extension_id: optional Open VSX / VSCode Marketplace identifier (codium --install-extension)
# - debug_env: optional environment variable that enables verbose wrapper logging
#
# Wrapper files are created under ~/.npm-global/bin and point at the resolved bin
# entry inside ~/.npm-global/lib/node_modules/<package>. The manifest is parsed
# by lib/tools.sh (install_claude_code()/install_vscodium_extensions()) so keep
# the delimiter structure intact when adding new packages.

NPM_AI_PACKAGE_MANIFEST=(
  # NOTE: Claude Code removed from NPM manifest — now installed via native installer
  # (curl -fsSL https://claude.ai/install.sh | bash). See lib/tools.sh install_claude_code_native().
  "@openai/codex|0.28.0|GPT CodeX CLI|codex|gpt-codex-wrapper||GPT_CODEX_DEBUG"
  "@openai/codex|0.28.0|Codex IDE|codex|codex-wrapper||CODEX_DEBUG"
  "openai|6.16.0|OpenAI CLI|openai|openai-wrapper|openai.chatgpt|OPENAI_DEBUG"
  "@google/gemini-cli|0.3.3|Gemini CLI|gemini|gemini-wrapper||GEMINI_DEBUG"
  "@qwen-code/qwen-code|0.0.11|Qwen Code CLI|qwen|qwen-wrapper||QWEN_DEBUG"
)

declare -gA NPM_AI_PACKAGE_MANUAL_URLS=(
  ["@google/gemini-cli"]="https://github.com/google-gemini/gemini-cli"
  ["@qwen-code/qwen-code"]="https://github.com/QwenLM/qwen-code"
  ["@openai/codex"]="https://help.openai.com/en/articles/11096431-openai-codex-ci-getting-started"
  ["openai"]="https://github.com/openai/openai-node"
)

declare -gA VSCODE_AI_EXTENSION_FALLBACK_URLS=(
  ["OpenAI.gpt-codex"]="https://marketplace.visualstudio.com/items?itemName=OpenAI.gpt-codex"
  ["OpenAI.codex-ide"]="https://marketplace.visualstudio.com/items?itemName=OpenAI.codex-ide"
)
