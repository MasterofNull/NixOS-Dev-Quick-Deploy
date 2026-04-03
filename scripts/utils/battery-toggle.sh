#!/usr/bin/env bash
# battery-toggle.sh — Runtime battery charge threshold manager
#
# Usage:
#   sudo battery-toggle.sh full          # Charge to 100% (disable thresholds)
#   sudo battery-toggle.sh balanced      # Default: start 20%, stop 80%
#   sudo battery-toggle.sh conservation  # Conservation: start 50%, stop 60%
#   sudo battery-toggle.sh custom 30 90  # Custom: start 30%, stop 90%
#   battery-toggle.sh status             # Show current thresholds
#
# This script writes directly to sysfs and takes effect immediately.
# Changes persist until next reboot or nixos-rebuild (which reapplies config).

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Find battery sysfs paths
BATTERY_PATHS=()
for bat in /sys/class/power_supply/BAT*/; do
  if [[ -d "$bat" ]]; then
    BATTERY_PATHS+=("$bat")
  fi
done

if [[ ${#BATTERY_PATHS[@]} -eq 0 ]]; then
  echo -e "${RED}ERROR: No battery found in /sys/class/power_supply/${NC}"
  exit 1
fi

# Check if sysfs interface exists
START_FILE="${BATTERY_PATHS[0]}charge_control_start_threshold"
STOP_FILE="${BATTERY_PATHS[0]}charge_control_end_threshold"

if [[ ! -f "$START_FILE" ]] || [[ ! -f "$STOP_FILE" ]]; then
  echo -e "${RED}ERROR: Battery charge threshold interface not found.${NC}"
  echo -e "${YELLOW}Your hardware may not support charge control via sysfs.${NC}"
  echo -e "${YELLOW}This is common on non-ThinkPad laptops.${NC}"
  exit 1
fi

show_status() {
  echo -e "${BLUE}=== Battery Charge Threshold Status ===${NC}"
  for bat in "${BATTERY_PATHS[@]}"; do
    bat_name=$(basename "$bat")
    start_file="${bat}charge_control_start_threshold"
    stop_file="${bat}charge_control_end_threshold"
    charge_now_file="${bat}charge_now"
    charge_full_file="${bat}charge_full"
    status_file="${bat}status"

    echo -e "\n${GREEN}Battery: $bat_name${NC}"
    
    if [[ -f "$start_file" ]] && [[ -f "$stop_file" ]]; then
      start_val=$(cat "$start_file" 2>/dev/null || echo "N/A")
      stop_val=$(cat "$stop_file" 2>/dev/null || echo "N/A")
      echo -e "  Start Threshold: ${YELLOW}${start_val}%${NC}"
      echo -e "  Stop Threshold:  ${YELLOW}${stop_val}%${NC}"
    else
      echo -e "  ${RED}Charge control not supported on this battery${NC}"
    fi

    if [[ -f "$status_file" ]]; then
      status=$(cat "$status_file" 2>/dev/null || echo "Unknown")
      echo -e "  Status:          ${YELLOW}${status}${NC}"
    fi

    if [[ -f "$charge_now_file" ]] && [[ -f "$charge_full_file" ]]; then
      charge_now=$(cat "$charge_now_file" 2>/dev/null || echo "0")
      charge_full=$(cat "$charge_full_file" 2>/dev/null || echo "1")
      if [[ "$charge_full" -gt 0 ]]; then
        pct=$((charge_now * 100 / charge_full))
        echo -e "  Current Charge:  ${YELLOW}${pct}%${NC}"
      fi
    fi
  done
  echo ""
}

set_thresholds() {
  local start=$1
  local stop=$2
  local label=$3

  if [[ $start -ge $stop ]]; then
    echo -e "${RED}ERROR: Start threshold ($start%) must be less than stop threshold ($stop%)${NC}"
    exit 1
  fi

  if [[ $start -lt 0 ]] || [[ $stop -gt 100 ]]; then
    echo -e "${RED}ERROR: Thresholds must be between 0 and 100${NC}"
    exit 1
  fi

  echo -e "${BLUE}Setting battery charge thresholds:${NC}"
  echo -e "  Mode:  ${GREEN}${label}${NC}"
  echo -e "  Start: ${YELLOW}${start}%${NC}"
  echo -e "  Stop:  ${YELLOW}${stop}%${NC}"
  echo ""

  for bat in "${BATTERY_PATHS[@]}"; do
    bat_name=$(basename "$bat")
    start_file="${bat}charge_control_start_threshold"
    stop_file="${bat}charge_control_end_threshold"

    if [[ -w "$start_file" ]] && [[ -w "$stop_file" ]]; then
      echo "$start" > "$start_file"
      echo "$stop" > "$stop_file"
      echo -e "${GREEN}✓ $bat_name: Set to start=$start%, stop=$stop%${NC}"
    else
      echo -e "${RED}✗ $bat_name: Cannot write to sysfs (need root?)${NC}"
    fi
  done

  echo ""
  echo -e "${GREEN}Thresholds applied immediately.${NC}"
  echo -e "${YELLOW}Note: Changes persist until reboot or nixos-rebuild.${NC}"
}

usage() {
  echo -e "${BLUE}Usage:${NC} $0 <command> [options]"
  echo ""
  echo -e "${GREEN}Commands:${NC}"
  echo "  full              Charge to 100% (disable thresholds)"
  echo "  balanced          Default mode: start 20%, stop 80%"
  echo "  conservation      Conservation mode: start 50%, stop 60%"
  echo "  custom <s> <e>    Custom thresholds (start%, stop%)"
  echo "  status            Show current battery status and thresholds"
  echo ""
  echo -e "${YELLOW}Examples:${NC}"
  echo "  $0 full              # Allow full charge (before trip)"
  echo "  $0 balanced          # Normal battery health mode"
  echo "  $0 conservation      # Always-plugged-in mode"
  echo "  $0 custom 30 90      # Custom: 30%-90%"
  echo "  $0 status            # Check current settings"
  echo ""
}

# Main command handling
case "${1:-status}" in
  full)
    set_thresholds 0 100 "Full Charge (100%)"
    ;;
  balanced)
    set_thresholds 20 80 "Balanced (20%-80%)"
    ;;
  conservation)
    set_thresholds 50 60 "Conservation (50%-60%)"
    ;;
  custom)
    if [[ $# -ne 3 ]]; then
      echo -e "${RED}ERROR: Custom mode requires start and stop thresholds${NC}"
      echo -e "${YELLOW}Usage: $0 custom <start%> <stop%>${NC}"
      exit 1
    fi
    set_thresholds "$2" "$3" "Custom ($2%-$3%)"
    ;;
  status)
    show_status
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    echo -e "${RED}ERROR: Unknown command '$1'${NC}"
    echo ""
    usage
    exit 1
    ;;
esac
