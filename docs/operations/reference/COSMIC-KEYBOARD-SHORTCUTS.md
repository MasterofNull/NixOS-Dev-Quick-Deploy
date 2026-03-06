# COSMIC Desktop Keyboard Shortcuts

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05

Reference guide for COSMIC Desktop Environment keyboard shortcuts on NixOS.

## Essential System Shortcuts

| Shortcut | Action |
|----------|--------|
| `Super` | Open application launcher |
| `Super + A` | Open application library |
| `Super + T` | Open terminal |
| `Super + E` | Open file manager |
| `Super + L` | Lock screen |
| `Super + D` | Show desktop (minimize all) |

## Window Management

| Shortcut | Action |
|----------|--------|
| `Super + Q` | Close window |
| `Super + M` | Maximize/restore window |
| `Super + H` | Minimize window |
| `Super + F` | Toggle fullscreen |
| `Super + Left` | Tile window left |
| `Super + Right` | Tile window right |
| `Super + Up` | Maximize window |
| `Super + Down` | Restore/minimize window |

## Workspace Navigation

| Shortcut | Action |
|----------|--------|
| `Super + 1-9` | Switch to workspace 1-9 |
| `Super + Shift + 1-9` | Move window to workspace 1-9 |
| `Super + Page_Up` | Previous workspace |
| `Super + Page_Down` | Next workspace |
| `Super + Tab` | Application switcher |
| `Alt + Tab` | Window switcher (same app) |

## Screenshot & Recording

| Shortcut | Action |
|----------|--------|
| `Print` | Screenshot (full screen) |
| `Shift + Print` | Screenshot (selection) |
| `Alt + Print` | Screenshot (current window) |
| `Super + Shift + R` | Screen recording toggle |

## System Controls

| Shortcut | Action |
|----------|--------|
| `Super + Escape` | Power menu |
| `Super + ,` | Open settings |
| `Super + N` | Open notifications panel |
| `Super + Space` | Toggle keyboard layout |

## AI Stack Integration (Custom)

| Shortcut | Action |
|----------|--------|
| `Super + Shift + T` | Open terminal with AI hints |
| `Super + Shift + A` | Quick AI query (if configured) |

## Customization

COSMIC stores keyboard shortcuts in:
```
~/.config/cosmic/com.system76.CosmicComp/v1/key_bindings.ron
```

To modify shortcuts:
1. Open **Settings** > **Keyboard** > **Shortcuts**
2. Or edit the RON file directly (requires logout/login to apply)

## Multi-Monitor Notes

- `Super + Shift + Left/Right` - Move window between monitors
- COSMIC auto-arranges workspaces per monitor
- cosmic-greeter respects multi-monitor layouts after first login

## Troubleshooting

**Shortcuts not working after resume:**
- COSMIC compositor may need reset: `systemctl --user restart cosmic-comp`

**Custom shortcuts not persisting:**
- Ensure `~/.config/cosmic/` is writable
- Check cosmic-session logs: `journalctl --user -u cosmic-session`

---

*Last updated: 2026-03-05*
*Applies to: COSMIC DE on NixOS 25.11*
