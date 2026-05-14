#!/usr/bin/env bash
# install.sh — Universal installer for Agentic CLI Tools.
#
# Copies the toolset to ~/.local/bin and ensures executability for
# non-Nix environments.
set -e

INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

TOOLS=("agrep" "als" "acat" "asum")

echo "Installing Agentic CLI Tools to $INSTALL_DIR..."

for tool in "${TOOLS[@]}"; do
  cp "./scripts/agent-tools/$tool" "$INSTALL_DIR/$tool"
  chmod +x "$INSTALL_DIR/$tool"
  echo "  - Installed $tool"
done

echo "✅ Installation complete. Ensure $INSTALL_DIR is in your PATH."
