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
# entry inside ~/.npm-global/lib/node_modules/<package>. The manifest is parsed by
# lib/tools.sh (install_claude_code()/install_vscodium_extensions()) so keep the
# delimiter structure intact when adding new packages.
#
# NOTE: Primary AI CLIs now use native installers (lib/tools.sh):
#   - Claude Code: install_claude_code_native()
#   - Gemini CLI: install_gemini_cli_native()
#   - Qwen Code:  install_qwen_code_native()
#   - Codex CLI:  install_codex_cli_native()
#
# NPM packages below are FALLBACK only - used when native installer fails or
# for systems that cannot run native installers.

NPM_AI_PACKAGE_MANIFEST=(
  # Fallback packages - only installed if native installer fails
  "@openai/codex|0.28.0|GPT CodeX CLI (fallback)|codex|gpt-codex-wrapper|OpenAI.gpt-codex|GPT_CODEX_DEBUG"
  "openai|6.16.0|OpenAI CLI (fallback)|openai|openai-wrapper|OpenAI.chatgpt|OPENAI_DEBUG"
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
  ["OpenAI.chatgpt"]="https://marketplace.visualstudio.com/items?itemName=OpenAI.chatgpt"
  ["Google.geminicodeassist"]="https://marketplace.visualstudio.com/items?itemName=Google.geminicodeassist"
)

