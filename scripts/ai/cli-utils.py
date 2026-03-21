#!/usr/bin/env python3
"""
CLI Utilities for Phase 6.2: User Experience Polish

Provides color output, progress tracking, confirmations, and enhanced error messages
for command-line tools in the NixOS AI Stack.
"""

import sys
import time
from typing import Callable, Optional
from datetime import datetime


class ANSIColors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'

    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


class Logger:
    """Enhanced logger with color support"""

    def __init__(self, name: str = "app", use_color: bool = True):
        self.name = name
        self.use_color = use_color and sys.stdout.isatty()

    def _format_timestamp(self) -> str:
        """Format current timestamp"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _colorize(self, text: str, color: str) -> str:
        """Apply color if enabled"""
        if self.use_color:
            return f"{color}{text}{ANSIColors.RESET}"
        return text

    def info(self, message: str):
        """Print informational message in blue"""
        timestamp = self._format_timestamp()
        colored_msg = self._colorize(f"[{timestamp}] ℹ {message}", ANSIColors.CYAN)
        print(colored_msg)

    def success(self, message: str):
        """Print success message in green"""
        timestamp = self._format_timestamp()
        colored_msg = self._colorize(f"[{timestamp}] ✓ {message}", ANSIColors.GREEN)
        print(colored_msg)

    def warning(self, message: str):
        """Print warning message in yellow"""
        timestamp = self._format_timestamp()
        colored_msg = self._colorize(f"[{timestamp}] ⚠ {message}", ANSIColors.YELLOW)
        print(colored_msg, file=sys.stderr)

    def error(self, message: str, code: Optional[str] = None):
        """Print error message in red with optional error code"""
        timestamp = self._format_timestamp()
        code_str = f" [{code}]" if code else ""
        colored_msg = self._colorize(f"[{timestamp}] ✕ {message}{code_str}", ANSIColors.RED)
        print(colored_msg, file=sys.stderr)

    def debug(self, message: str):
        """Print debug message in dim text"""
        if sys.stdout.isatty():
            timestamp = self._format_timestamp()
            colored_msg = self._colorize(f"[{timestamp}] ⟳ {message}", ANSIColors.DIM)
            print(colored_msg, file=sys.stderr)

    def header(self, message: str):
        """Print a formatted header"""
        if self.use_color:
            border = "=" * (len(message) + 4)
            print(f"\n{self._colorize(border, ANSIColors.CYAN)}")
            print(self._colorize(f"  {message}", ANSIColors.BOLD + ANSIColors.CYAN))
            print(f"{self._colorize(border, ANSIColors.CYAN)}\n")
        else:
            print(f"\n{'=' * (len(message) + 4)}\n  {message}\n{'=' * (len(message) + 4)}\n")


class ProgressBar:
    """Simple progress bar for long-running operations"""

    def __init__(self, total: int, label: str = "Progress", use_color: bool = True):
        self.total = total
        self.current = 0
        self.label = label
        self.use_color = use_color and sys.stdout.isatty()
        self.start_time = time.time()

    def update(self, amount: int = 1):
        """Update progress"""
        self.current = min(self.current + amount, self.total)
        self._draw()

    def set(self, value: int):
        """Set progress to specific value"""
        self.current = min(value, self.total)
        self._draw()

    def _draw(self):
        """Draw the progress bar"""
        if self.total == 0:
            return

        percent = self.current / self.total
        filled = int(50 * percent)
        bar = "█" * filled + "░" * (50 - filled)

        elapsed = time.time() - self.start_time
        if self.current > 0 and percent < 1:
            eta = elapsed / percent - elapsed
            eta_str = f" ETA: {int(eta)}s"
        else:
            eta_str = ""

        if self.use_color:
            percent_color = ANSIColors.GREEN if percent >= 0.75 else ANSIColors.YELLOW if percent >= 0.5 else ANSIColors.CYAN
            percent_str = f"{percent_color}{int(percent * 100):3d}%{ANSIColors.RESET}"
        else:
            percent_str = f"{int(percent * 100):3d}%"

        line = f"\r{self.label} {percent_str} │{bar}│{eta_str}"
        sys.stdout.write(line)
        sys.stdout.flush()

        if self.current >= self.total:
            print()  # New line when complete


class Spinner:
    """Simple spinner for indeterminate operations"""

    FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    def __init__(self, label: str = "Loading", use_color: bool = True):
        self.label = label
        self.use_color = use_color and sys.stdout.isatty()
        self.frame = 0
        self.running = False

    def start(self):
        """Start the spinner"""
        if not self.use_color:
            print(f"{self.label}...")
            return

        self.running = True
        self.frame = 0
        self._draw()

    def stop(self, final_message: str = "Done"):
        """Stop the spinner"""
        self.running = False
        if self.use_color:
            sys.stdout.write(f"\r{ANSIColors.GREEN}✓{ANSIColors.RESET} {final_message:<50}\n")
            sys.stdout.flush()

    def update(self):
        """Update spinner frame"""
        if self.running and self.use_color:
            self.frame = (self.frame + 1) % len(self.FRAMES)
            self._draw()

    def _draw(self):
        """Draw spinner frame"""
        frame_char = self.FRAMES[self.frame]
        line = f"\r{frame_char} {self.label:<50}"
        sys.stdout.write(line)
        sys.stdout.flush()


def confirm(prompt: str, default: bool = False) -> bool:
    """Interactive confirmation prompt"""
    default_str = "[Y/n]" if default else "[y/N]"
    while True:
        sys.stdout.write(f"{prompt} {default_str}: ")
        sys.stdout.flush()
        choice = input().lower()

        if choice in ('y', 'yes'):
            return True
        elif choice in ('n', 'no'):
            return False
        elif choice == '':
            return default
        else:
            print("Please enter 'y' or 'n'")


class ContextualError:
    """Contextual error with guidance and error codes"""

    ERRORS = {
        'E001': {
            'title': 'Configuration Error',
            'message': 'Required configuration is missing.',
            'guidance': 'Check your config file and ensure all required fields are present.'
        },
        'E101': {
            'title': 'Connection Failed',
            'message': 'Unable to reach the service.',
            'guidance': 'Verify the service is running and network connectivity is available.'
        },
        'E102': {
            'title': 'Network Timeout',
            'message': 'The request took too long to complete.',
            'guidance': 'Check your network connection and try again.'
        },
        'E201': {
            'title': 'Permission Denied',
            'message': 'You do not have sufficient permissions.',
            'guidance': 'Run with elevated privileges or check file ownership.'
        },
        'E301': {
            'title': 'Resource Not Found',
            'message': 'The requested resource does not exist.',
            'guidance': 'Verify the resource ID and try again.'
        },
        'E401': {
            'title': 'API Error',
            'message': 'An unexpected error occurred.',
            'guidance': 'Check the system logs for more details or contact support.'
        },
    }

    @staticmethod
    def show(error_code: str, details: str = "", logger: Optional[Logger] = None):
        """Display a contextual error message"""
        if logger is None:
            logger = Logger()

        error_info = ContextualError.ERRORS.get(error_code, ContextualError.ERRORS['E401'])

        logger.error(f"{error_info['title']}: {error_info['message']}", code=error_code)
        if details:
            logger.error(f"Details: {details}")
        logger.error(f"Guidance: {error_info['guidance']}")


def format_table(rows: list, headers: list, column_widths: Optional[list] = None) -> str:
    """Format data as a simple table"""
    if not rows:
        return "No data"

    if column_widths is None:
        column_widths = [max(len(str(h)), max(len(str(row[i])) for row in rows))
                         for i, h in enumerate(headers)]

    # Header
    lines = []
    header_line = " | ".join(str(h).ljust(w) for h, w in zip(headers, column_widths))
    lines.append(header_line)
    lines.append("-" * len(header_line))

    # Rows
    for row in rows:
        row_line = " | ".join(str(cell).ljust(w) for cell, w in zip(row, column_widths))
        lines.append(row_line)

    return "\n".join(lines)


def humanize_duration(seconds: float) -> str:
    """Convert seconds to human-readable duration"""
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def humanize_bytes(bytes_value: int) -> str:
    """Convert bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f}{unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f}PB"


# Global logger instance
logger = Logger()
