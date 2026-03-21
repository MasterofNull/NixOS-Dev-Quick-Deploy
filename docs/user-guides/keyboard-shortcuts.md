# Keyboard Shortcuts Reference

A comprehensive guide to keyboard shortcuts in the NixOS AI Stack Dashboard and CLI tools.

## Dashboard Shortcuts

Access these shortcuts anywhere in the web dashboard. Press `?` to show the help modal.

### Navigation

| Shortcut | Action | Context |
|----------|--------|---------|
| `r` | Refresh current view | All pages |
| `s` | Focus search box | All pages |
| `?` | Show keyboard shortcuts | All pages |
| `Esc` | Close modals / clear search | Modals and search |
| `Tab` | Navigate between sections | Navigation |
| `Shift+Tab` | Navigate backwards | Navigation |

### Common Actions

| Shortcut | Action | Context |
|----------|--------|---------|
| `Enter` | Confirm action | Dialogs and forms |
| `Escape` | Cancel action | Dialogs and forms |
| `Ctrl+S` | Save configuration | Configuration panel |
| `Ctrl+C` | Copy to clipboard | Copyable fields |

### View Specific Shortcuts

#### System Metrics View
| Shortcut | Action |
|----------|--------|
| `m` | Jump to Memory section |
| `c` | Jump to CPU section |
| `d` | Jump to Disk section |
| `n` | Jump to Network section |

#### AI Stack Status
| Shortcut | Action |
|----------|--------|
| `a` | Toggle AI stack details |
| `l` | Jump to service logs |
| `h` | Show health status |

#### Deployment Operations
| Shortcut | Action |
|----------|--------|
| `p` | Jump to deployments |
| `n` | New deployment form |
| `d` | Delete selected deployment |
| `l` | View deployment logs |

#### Reports & Analytics
| Shortcut | Action |
|----------|--------|
| `g` | Generate new report |
| `e` | Export current view |
| `f` | Filter results |
| `t` | Show trends |

## CLI Tool Shortcuts

### Tab Completion

Use `Tab` for auto-completion in terminal commands:

```bash
# Command name completion
aq-<Tab>              # Shows: aq-report, aq-qa, aq-orchestrator, etc.

# Option completion
aq-report --<Tab>     # Shows: --since, --format, --aidb-import, --help

# Value completion
aq-report --since=<Tab>  # Shows: 1d, 7d, 30d, 1w, 1m, 3m

# Service name completion
systemctl status <Tab>   # Shows available services
```

### Navigation Shortcuts

These work in the terminal when running interactive commands:

| Shortcut | Action |
|----------|--------|
| `Ctrl+A` | Jump to start of line |
| `Ctrl+E` | Jump to end of line |
| `Ctrl+W` | Delete word backwards |
| `Ctrl+U` | Clear entire line |
| `Ctrl+K` | Delete to end of line |
| `Ctrl+R` | Search command history |
| `Alt+.` | Insert last argument from previous command |
| `Ctrl+Y` | Paste deleted text |

### Command History

| Shortcut | Action |
|----------|--------|
| `↑` / `↓` | Navigate command history |
| `Ctrl+R` | Reverse search in history |
| `Ctrl+S` | Forward search in history |
| `Ctrl+P` | Previous command |
| `Ctrl+N` | Next command |

## Common Workflow Shortcuts

### Quick Status Check

```bash
# Jump to logs quickly
journalctl -u ai-hybrid-coordinator -f  # Then press 'Ctrl+C' to exit

# Quick health check with history
systemctl status ai-hybrid-coordinator && history 1

# Use 'Up' arrow to run similar commands
```

### Deployment Operations

```bash
# Run deployment with history search
Ctrl+R deploy              # Search for previous deploy commands

# Then use Alt+. to populate arguments from last deployment
# Or manually edit with Ctrl+A / Ctrl+E
```

## Custom Shortcuts (Advanced)

You can create custom shortcuts in your shell configuration:

### Bash Aliases

Add to `~/.bashrc`:

```bash
# Quick commands
alias ai-status='systemctl status ai-hybrid-coordinator'
alias ai-logs='journalctl -u ai-hybrid-coordinator -n 50 -f'
alias ai-restart='sudo systemctl restart ai-hybrid-coordinator'
alias ai-health='curl -s http://localhost:3000/api/health | jq .'

# Workflow commands
alias aq-list='aq-orchestrator workflow list'
alias aq-status='aq-orchestrator workflow status'

# Dashboard
alias db-open='xdg-open http://localhost:3000'
alias db-health='curl -I http://localhost:3000'
```

### Shell Functions

```bash
# Add to ~/.bashrc for complex operations
deploy-workflow() {
    local workflow=$1
    local params=${2:-"{}"}
    echo "Deploying workflow: $workflow"
    aq-orchestrator workflow run "$workflow" --params "$params"
}

quick-report() {
    echo "Generating report since $1..."
    aq-report --since="${1:-7d}" --format=text | less
}

watch-logs() {
    local service=${1:-ai-hybrid-coordinator}
    journalctl -u "$service" -n 100 -f
}
```

### Zsh Configuration

If using Zsh, add to `~/.zshrc`:

```zsh
# Key bindings
bindkey '^R' history-incremental-search-backward
bindkey '^S' history-incremental-search-forward

# Aliases same as above
alias ai-status='systemctl status ai-hybrid-coordinator'
alias ai-logs='journalctl -u ai-hybrid-coordinator -n 50 -f'
```

## Desktop Shortcuts

### System Tray / Application Menu

You can create desktop shortcuts for quick access:

```bash
# Create desktop launcher for dashboard
cat > ~/.local/share/applications/nixos-ai-stack.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=NixOS AI Stack Dashboard
Comment=AI Stack Management Dashboard
Exec=xdg-open http://localhost:3000
Icon=network-server
Categories=Utility;

[Desktop Action CheckHealth]
Name=Check Health
Exec=notify-send "AI Stack Health" "$(curl -s http://localhost:3000/api/health | jq -r '.status')"

[Desktop Action ViewLogs]
Name=View Logs
Exec=gnome-terminal -- journalctl -u ai-hybrid-coordinator -f
EOF
```

## IDE Integration

### VS Code

Add to `.vscode/keybindings.json`:

```json
[
    {
        "key": "ctrl+alt+a",
        "command": "terminal.sendSequence",
        "args": { "text": "aq-report --since=7d --format=text\u000d" }
    },
    {
        "key": "ctrl+alt+d",
        "command": "terminal.sendSequence",
        "args": { "text": "systemctl status ai-hybrid-coordinator\u000d" }
    }
]
```

### Vim/Neovim

Add to `~/.config/nvim/init.vim`:

```vim
" Quick dashboard health check
nnoremap <leader>aha :!curl -s http://localhost:3000/api/health \| jq .<CR>

" View logs
nnoremap <leader>alog :terminal journalctl -u ai-hybrid-coordinator -f<CR>

" Generate report
nnoremap <leader>areport :terminal aq-report --since=7d --format=text<CR>
```

## Tips & Tricks

1. **History Search**: Use `Ctrl+R` frequently to find previous commands
2. **Aliases**: Create aliases for your most-used commands
3. **Functions**: Use shell functions for complex multi-step operations
4. **Completion**: Learn to use Tab completion - it saves typing
5. **Last Argument**: Use `Alt+.` to reuse the last argument from previous command
6. **Copy-Paste**: In dashboard, copyable fields have a dotted underline

## Customization

### Dashboard Keyboard Shortcuts

Edit dashboard behavior by modifying JavaScript in browser console:

```javascript
// Add custom shortcut (in browser console)
KeyboardShortcutsManager.shortcuts['x'] = {
    description: 'Export current data',
    action: () => { window.location.href = '/api/export/current'; }
};
```

### Terminal Themes

Use key shortcuts more effectively with a good terminal theme:

```bash
# Export a report with colors
aq-report --since=7d --format=text | less -R

# Use --debug for more detailed output
aq-report --since=7d --format=text --debug 2>&1 | less -R
```

## Accessibility

If you prefer keyboard-only navigation:

1. Press `Tab` to focus interactive elements
2. Press `Enter` or `Space` to activate buttons
3. Use `Shift+Tab` to navigate backwards
4. Screen readers will announce elements properly

## Troubleshooting Shortcuts

### Shortcuts Not Working?

1. **Ensure focus**: Click in the dashboard first
2. **Avoid input fields**: Shortcuts don't work when typing in input boxes
3. **Browser extensions**: Some extensions override shortcuts
4. **Terminal settings**: Check terminal key binding settings

### Clearing History

```bash
# Clear command history
history -c

# Save empty history to file
cat /dev/null > ~/.bash_history

# Or selectively remove entries
history -d <line_number>
```

## Quick Reference Card

Print this for quick reference:

```
┌─────────────────────────────────────────────────────────┐
│       NixOS AI Stack - Quick Keyboard Reference         │
├─────────────────────────────────────────────────────────┤
│ Dashboard:     r=Refresh  s=Search  ?=Help Esc=Close    │
│ Terminal:      Tab=Complete Ctrl+R=History Up/Down=Nav  │
│ Common:        Ctrl+A=StartLine Ctrl+E=EndLine          │
│ Workflow:      Ctrl+R deploy (search) Alt+.=LastArg     │
│ Aliases:       ai-logs  ai-health  ai-status            │
└─────────────────────────────────────────────────────────┘
```

---

**Pro Tip**: Combine shortcuts with aliases for maximum productivity. For example:
```bash
# Create alias
alias ai-report='aq-report --since=7d --format=text'

# Then use Ctrl+R to search and run
# Then use Alt+. to get the last argument in a new command
```
