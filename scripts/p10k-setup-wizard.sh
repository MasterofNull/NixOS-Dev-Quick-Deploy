#!/usr/bin/env bash
# Powerlevel10k Interactive Setup Wizard for NixOS
# Enhanced with better colors, contrast, and customization
# Works with home-manager by generating a writable config overlay

set -euo pipefail

# Directories
CONFIG_DIR="$HOME/.config/p10k"
THEME_FILE="$CONFIG_DIR/theme.sh"
MARKER_FILE="$CONFIG_DIR/.configured"

# Ensure directory exists
mkdir -p "$CONFIG_DIR"

# Colors with better contrast for dark terminals
RED='\033[1;31m'        # Bright red
GREEN='\033[1;32m'      # Bright green
YELLOW='\033[1;33m'     # Bright yellow
BLUE='\033[1;34m'       # Bright blue
MAGENTA='\033[1;35m'    # Bright magenta
CYAN='\033[1;36m'       # Bright cyan
WHITE='\033[1;37m'      # Bright white
BOLD='\033[1m'
NC='\033[0m'            # No color

clear

cat << 'EOF'
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ██████╗  ██╗ ██████╗ ██╗  ██╗                         ║
║   ██╔══██╗███║██╔═████╗██║ ██╔╝                         ║
║   ██████╔╝╚██║██║██╔██║█████╔╝                          ║
║   ██╔═══╝  ██║████╔╝██║██╔═██╗                          ║
║   ██║      ██║╚██████╔╝██║  ██╗                         ║
║   ╚═╝      ╚═╝ ╚═════╝ ╚═╝  ╚═╝                         ║
║                                                          ║
║   Powerlevel10k Configuration Wizard                    ║
║   for NixOS - Enhanced Edition                          ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

EOF

echo -e "${CYAN}${BOLD}This wizard will help you configure your zsh prompt.${NC}\n"

# Check if already configured
if [[ -f "$MARKER_FILE" ]]; then
    echo -e "${YELLOW}You've already configured p10k.${NC}"
    echo -e "${CYAN}To reconfigure, run: ${WHITE}rm $MARKER_FILE && exec zsh${NC}\n"
    exit 0
fi

# Step 1: Font check with better examples
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}${BOLD}Step 1: Font Check${NC}"
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"
echo -e "${WHITE}${BOLD}This is how icons should appear:${NC}"
echo -e ""
echo -e "  ${CYAN}Test Icons:${NC}  ${WHITE}${BOLD}󰊕     ${NC}"
echo -e "  ${CYAN}Git Branch:${NC}  ${GREEN}  main${NC}"
echo -e "  ${CYAN}NixOS:${NC}      ${BLUE}❄️  NixOS${NC}"
echo -e "  ${CYAN}Directory:${NC}  ${YELLOW}  ~/projects${NC}"
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Can you see all icons clearly? [y/n]: ${NC}")" -n 1 font_ok
echo ""

if [[ "$font_ok" != "y" && "$font_ok" != "Y" ]]; then
    echo -e "\n${RED}${BOLD}Please install a Nerd Font and configure your terminal:${NC}"
    echo -e "  ${CYAN}•${NC} ${WHITE}MesloLGS NF${NC} (Recommended - included in home-manager config)"
    echo -e "  ${CYAN}•${NC} ${WHITE}FiraCode Nerd Font${NC}"
    echo -e "  ${CYAN}•${NC} ${WHITE}JetBrainsMono Nerd Font${NC}"
    echo ""
    echo -e "${YELLOW}${BOLD}Configure your terminal:${NC}"
    echo -e "  ${CYAN}Alacritty:${NC} Edit ~/.config/alacritty/alacritty.toml"
    echo -e "             font.normal.family = \"MesloLGS NF\""
    echo -e "  ${CYAN}GNOME Terminal:${NC} Right-click → Preferences → Profile → Text"
    echo -e "  ${CYAN}VSCode:${NC} Settings → terminal.integrated.fontFamily"
    echo -e "            \"MesloLGS NF\""
    echo ""
    echo -e "${CYAN}Restart your terminal after changing fonts and run: ${WHITE}${BOLD}exec zsh${NC}\n"
    exit 1
fi

# Step 2: Prompt style with visual examples
clear
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}${BOLD}Step 2: Prompt Style${NC}"
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"
echo -e "${CYAN}${BOLD}1) Lean${NC}    - ${WHITE}Minimal, single-line, fast${NC}"
echo -e "   ${GREEN}~/projects/my-app${NC} ${BLUE}  main${NC} ${RED}✗${NC} ${WHITE}❯${NC}"
echo ""
echo -e "${CYAN}${BOLD}2) Classic${NC} - ${WHITE}Two lines, informative${NC}"
echo -e "   ${BLUE}╭─${NC} ${GREEN}~/projects/my-app${NC} ${BLUE}  main${NC} ${RED}✗${NC}"
echo -e "   ${BLUE}╰─${NC}${WHITE}❯${NC}"
echo ""
echo -e "${CYAN}${BOLD}3) Rainbow${NC} - ${WHITE}Colorful, fun, segments with backgrounds${NC}"
echo -e "   ${WHITE}${BOLD}${NC} ${GREEN}~/projects${NC} ${BLUE}  main${NC} ${YELLOW} ✗${NC} ${WHITE}❯${NC}"
echo ""
echo -e "${CYAN}${BOLD}4) Pure${NC}    - ${WHITE}Minimalist, no separators${NC}"
echo -e "   ${CYAN}~${NC}${WHITE}/${NC}${CYAN}projects${NC}${WHITE}/${NC}${CYAN}my-app${NC} ${BLUE} main${NC} ${WHITE}❯${NC}"
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Your choice [1-4]: ${NC}")" -n 1 style_choice
echo -e "\n"

case "$style_choice" in
    1) PROMPT_STYLE="lean" ;;
    2) PROMPT_STYLE="classic" ;;
    3) PROMPT_STYLE="rainbow" ;;
    4) PROMPT_STYLE="pure" ;;
    *) PROMPT_STYLE="lean" ;;
esac

# Step 3: Enhanced color scheme with better descriptions
clear
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}${BOLD}Step 3: Color Scheme & Contrast${NC}"
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"
echo -e "${YELLOW}${BOLD}Choose colors that match your terminal background:${NC}"
echo ""
echo -e "${CYAN}${BOLD}1) High Contrast Dark${NC}  - ${WHITE}${BOLD}Bright, vibrant colors (RECOMMENDED)${NC}"
echo -e "   ${GREEN}${BOLD}Best for:${NC} Dark terminals, high readability"
echo -e "   ${BLUE}Example:${NC} ${WHITE}${BOLD}~/projects${NC} ${GREEN}${BOLD}  main${NC} ${YELLOW}${BOLD}✗${NC}"
echo ""
echo -e "${CYAN}${BOLD}2) Light${NC}              - ${WHITE}Dark colors (for light terminals)${NC}"
echo -e "   ${GREEN}${BOLD}Best for:${NC} White/light backgrounds"
echo ""
echo -e "${CYAN}${BOLD}3) Solarized Dark${NC}     - ${WHITE}Warm, balanced${NC}"
echo -e "   ${GREEN}${BOLD}Best for:${NC} Solarized Dark theme"
echo ""
echo -e "${CYAN}${BOLD}4) Gruvbox${NC}            - ${WHITE}Retro, warm colors${NC}"
echo -e "   ${GREEN}${BOLD}Best for:${NC} Gruvbox theme lovers"
echo ""
echo -e "${CYAN}${BOLD}5) Nord${NC}               - ${WHITE}Cool, bluish theme${NC}"
echo -e "   ${GREEN}${BOLD}Best for:${NC} Nord theme users"
echo ""
echo -e "${CYAN}${BOLD}6) Dracula${NC}            - ${WHITE}Purple-ish, vibrant${NC}"
echo -e "   ${GREEN}${BOLD}Best for:${NC} Dracula theme fans"
echo ""
echo -e "${CYAN}${BOLD}7) Custom High Contrast${NC} - ${WHITE}${BOLD}Maximum readability${NC}"
echo -e "   ${GREEN}${BOLD}Best for:${NC} Accessibility, visual impairment"
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Your choice [1-7]: ${NC}")" -n 1 color_choice
echo -e "\n"

case "$color_choice" in
    1) COLOR_SCHEME="high-contrast-dark" ;;
    2) COLOR_SCHEME="light" ;;
    3) COLOR_SCHEME="solarized" ;;
    4) COLOR_SCHEME="gruvbox" ;;
    5) COLOR_SCHEME="nord" ;;
    6) COLOR_SCHEME="dracula" ;;
    7) COLOR_SCHEME="custom-high-contrast" ;;
    *) COLOR_SCHEME="high-contrast-dark" ;;
esac

# Step 4: Background/Foreground customization
clear
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}${BOLD}Step 4: Terminal Background${NC}"
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"
echo -e "${YELLOW}${BOLD}What is your terminal background color?${NC}"
echo ""
echo -e "${CYAN}${BOLD}1) Dark/Black${NC}     - ${WHITE}Most common${NC}"
echo -e "${CYAN}${BOLD}2) Very Dark Grey${NC} - ${WHITE}Softer than black${NC}"
echo -e "${CYAN}${BOLD}3) Light/White${NC}    - ${WHITE}Light background${NC}"
echo -e "${CYAN}${BOLD}4) Custom${NC}         - ${WHITE}Will use bright colors${NC}"
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Your choice [1-4]: ${NC}")" -n 1 bg_choice
echo -e "\n"

case "$bg_choice" in
    1) BACKGROUND_TYPE="dark" ;;
    2) BACKGROUND_TYPE="grey" ;;
    3) BACKGROUND_TYPE="light" ;;
    4) BACKGROUND_TYPE="custom" ;;
    *) BACKGROUND_TYPE="dark" ;;
esac

# Step 5: Prompt elements
clear
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}${BOLD}Step 5: Customize Elements${NC}"
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"

read -p "$(echo -e "${YELLOW}${BOLD}Show time in prompt? [y/n]: ${NC}")" -n 1 show_time
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Show NixOS snowflake icon ❄️ ? [Y/n]: ${NC}")" -n 1 show_os
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Show current directory full path? [Y/n]: ${NC}")" -n 1 show_full_path
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Always show user@hostname? [y/n]: ${NC}")" -n 1 show_context
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Show Python virtualenv indicator? [Y/n]: ${NC}")" -n 1 show_venv
echo ""
read -p "$(echo -e "${YELLOW}${BOLD}Enable transient prompt (clean history)? [Y/n]: ${NC}")" -n 1 transient
echo -e "\n"

# Convert to yes/no (default yes for most)
[[ "$show_time" == "y" || "$show_time" == "Y" ]] && SHOW_TIME="true" || SHOW_TIME="false"
[[ "$show_os" != "n" && "$show_os" != "N" ]] && SHOW_OS="true" || SHOW_OS="false"
[[ "$show_full_path" != "n" && "$show_full_path" != "N" ]] && SHOW_FULL_PATH="true" || SHOW_FULL_PATH="false"
[[ "$show_context" == "y" || "$show_context" == "Y" ]] && SHOW_CONTEXT="true" || SHOW_CONTEXT="false"
[[ "$show_venv" != "n" && "$show_venv" != "N" ]] && SHOW_VENV="true" || SHOW_VENV="false"
[[ "$transient" != "n" && "$transient" != "N" ]] && TRANSIENT="true" || TRANSIENT="false"

# Step 6: Summary
clear
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}${BOLD}Configuration Summary${NC}"
echo -e "${MAGENTA}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"
echo -e "${CYAN}${BOLD}Style:${NC}           ${WHITE}$PROMPT_STYLE${NC}"
echo -e "${CYAN}${BOLD}Colors:${NC}          ${WHITE}$COLOR_SCHEME${NC}"
echo -e "${CYAN}${BOLD}Background:${NC}      ${WHITE}$BACKGROUND_TYPE${NC}"
echo -e "${CYAN}${BOLD}Show Time:${NC}       ${WHITE}$SHOW_TIME${NC}"
echo -e "${CYAN}${BOLD}NixOS Icon:${NC}      ${WHITE}$SHOW_OS${NC}"
echo -e "${CYAN}${BOLD}Full Path:${NC}       ${WHITE}$SHOW_FULL_PATH${NC}"
echo -e "${CYAN}${BOLD}Context:${NC}         ${WHITE}$SHOW_CONTEXT${NC}"
echo -e "${CYAN}${BOLD}Python Venv:${NC}     ${WHITE}$SHOW_VENV${NC}"
echo -e "${CYAN}${BOLD}Transient:${NC}       ${WHITE}$TRANSIENT${NC}"
echo ""

read -p "$(echo -e "${GREEN}${BOLD}Apply this configuration? [Y/n]: ${NC}")" -n 1 confirm
echo -e "\n"

if [[ "$confirm" == "n" || "$confirm" == "N" ]]; then
    echo -e "${RED}${BOLD}Configuration cancelled.${NC}"
    echo -e "${CYAN}Run '${WHITE}${BOLD}exec zsh${CYAN}' to try again.${NC}\n"
    exit 0
fi

# Save configuration
cat > "$THEME_FILE" << EOFTHEME
# P10k Theme Configuration - Enhanced Edition
# Generated: $(date)
# To reconfigure: rm $MARKER_FILE && exec zsh

export P10K_STYLE="$PROMPT_STYLE"
export P10K_COLORS="$COLOR_SCHEME"
export P10K_BACKGROUND="$BACKGROUND_TYPE"
export P10K_SHOW_TIME=$SHOW_TIME
export P10K_SHOW_OS=$SHOW_OS
export P10K_SHOW_FULL_PATH=$SHOW_FULL_PATH
export P10K_SHOW_CONTEXT=$SHOW_CONTEXT
export P10K_SHOW_VENV=$SHOW_VENV
export P10K_TRANSIENT=$TRANSIENT
EOFTHEME

touch "$MARKER_FILE"

echo -e "${GREEN}${BOLD}✓ Configuration saved!${NC}\n"
echo -e "${CYAN}Your theme has been configured with enhanced contrast and readability.${NC}"
echo -e "${CYAN}Restart zsh to see changes: ${WHITE}${BOLD}exec zsh${NC}\n"

exit 0
