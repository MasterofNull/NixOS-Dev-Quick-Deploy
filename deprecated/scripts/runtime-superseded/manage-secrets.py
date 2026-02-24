#!/usr/bin/env python3
"""
AI Stack Secrets Manager - Interactive TUI for managing Kubernetes secrets
Supports: password generation, rotation, backup, restore, and validation

Usage:
    python manage-secrets.py              # Interactive TUI mode
    python manage-secrets.py init         # Initialize all secrets
    python manage-secrets.py rotate all   # Rotate all passwords
    python manage-secrets.py backup       # Backup secrets
    python manage-secrets.py status       # Show secret status
"""

import os
import sys
import secrets
import string
import shutil
import subprocess
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Check for rich library
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.markdown import Markdown
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("Warning: 'rich' library not found. Install with: pip install rich")
    print("Falling back to basic CLI mode\n")

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
SECRETS_DIR = PROJECT_ROOT / "ai-stack" / "kubernetes" / "secrets" / "generated"
BACKUP_DIR = PROJECT_ROOT / "backups" / "secrets"
CONFIG_FILE = PROJECT_ROOT / "ai-stack" / "kubernetes" / "secrets" / ".secrets-config.json"

# Secret definitions
SECRET_DEFS = {
    # Passwords (32 bytes, 256-bit entropy)
    "postgres_password": {
        "type": "password",
        "length": 32,
        "description": "PostgreSQL database password",
        "services": ["postgres", "aidb", "hybrid-coordinator", "health-monitor", "ralph-wiggum"]
    },
    "redis_password": {
        "type": "password",
        "length": 32,
        "description": "Redis cache password",
        "services": ["redis", "aidb", "nixos-docs", "autogpt", "ralph-wiggum"]
    },
    "grafana_admin_password": {
        "type": "password",
        "length": 32,
        "description": "Grafana admin UI password",
        "services": ["grafana"]
    },

    # API Keys (64 bytes, 512-bit entropy)
    "stack_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "Main stack API key",
        "services": ["global"]
    },
    "aidb_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "AIDB service API key",
        "services": ["aidb"]
    },
    "aider_wrapper_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "Aider wrapper API key",
        "services": ["aider-wrapper"]
    },
    "container_engine_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "Container engine API key",
        "services": ["container-engine"]
    },
    "dashboard_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "Dashboard API key",
        "services": ["dashboard"]
    },
    "embeddings_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "Embeddings service API key",
        "services": ["embeddings"]
    },
    "hybrid_coordinator_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "Hybrid coordinator API key",
        "services": ["hybrid-coordinator"]
    },
    "nixos_docs_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "NixOS docs service API key",
        "services": ["nixos-docs"]
    },
    "ralph_wiggum_api_key": {
        "type": "api_key",
        "length": 64,
        "description": "Ralph Wiggum orchestrator API key",
        "services": ["ralph-wiggum"]
    },
}


class SecretsManager:
    """Manages Docker/Podman secrets for the AI stack"""

    def __init__(self):
        self.secrets_dir = SECRETS_DIR
        self.backup_dir = BACKUP_DIR
        self.config_file = CONFIG_FILE
        self.console = Console() if HAS_RICH else None

        # Ensure directories exist
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, message: str, style: str = ""):
        """Print message with or without rich"""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)

    def _generate_password(self, length: int = 32) -> str:
        """Generate cryptographically secure password"""
        # Use alphanumeric + safe special chars (database compatible)
        # Avoid: / + = (can cause issues in connection strings)
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password

    def _generate_api_key(self, length: int = 64) -> str:
        """Generate cryptographically secure API key"""
        # Use URL-safe base64-like characters
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(length))
        return api_key

    def _write_secret(self, name: str, value: str) -> bool:
        """Write secret to file with correct permissions"""
        try:
            secret_file = self.secrets_dir / name

            # Write secret
            secret_file.write_text(value)

            # Set permissions to 644 (readable by containers)
            secret_file.chmod(0o644)

            return True
        except Exception as e:
            self._print(f"Error writing secret {name}: {e}", "red")
            return False

    def _read_secret(self, name: str) -> Optional[str]:
        """Read secret from file"""
        try:
            secret_file = self.secrets_dir / name
            if secret_file.exists():
                return secret_file.read_text().strip()
            return None
        except Exception as e:
            self._print(f"Error reading secret {name}: {e}", "red")
            return None

    def _get_secret_hash(self, name: str) -> Optional[str]:
        """Get hash of secret value (for tracking changes without exposing value)"""
        value = self._read_secret(name)
        if value:
            return hashlib.sha256(value.encode()).hexdigest()[:16]
        return None

    def _load_config(self) -> Dict:
        """Load secrets configuration"""
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load secrets config %s: %s", self.config_file, e)
        return {}

    def _save_config(self, config: Dict):
        """Save secrets configuration"""
        self.config_file.write_text(json.dumps(config, indent=2))

    def init_secrets(self, force: bool = False):
        """Initialize all secrets"""
        self._print("\n[bold cyan]Initializing AI Stack Secrets[/bold cyan]")
        self._print("=" * 60)

        config = self._load_config()
        created = 0
        skipped = 0

        if self.console:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            )

        for secret_name, secret_def in SECRET_DEFS.items():
            secret_file = self.secrets_dir / secret_name

            if secret_file.exists() and not force:
                self._print(f"⏭️  Skipping {secret_name} (already exists)", "yellow")
                skipped += 1
                continue

            # Generate secret based on type
            if secret_def["type"] == "password":
                value = self._generate_password(secret_def["length"])
            elif secret_def["type"] == "api_key":
                value = self._generate_api_key(secret_def["length"])
            else:
                self._print(f"Unknown secret type for {secret_name}", "red")
                continue

            # Write secret
            if self._write_secret(secret_name, value):
                created += 1

                # Update config
                config[secret_name] = {
                    "created": datetime.now().isoformat(),
                    "hash": self._get_secret_hash(secret_name),
                    "type": secret_def["type"],
                    "rotated": None
                }

                self._print(f"✅ Created {secret_name} ({secret_def['length']} bytes)", "green")
            else:
                self._print(f"❌ Failed to create {secret_name}", "red")

        self._save_config(config)

        self._print("\n" + "=" * 60)
        self._print(f"[bold green]Created: {created}[/bold green] | [yellow]Skipped: {skipped}[/yellow]")

        if created > 0:
            self._print("\n[bold yellow]⚠️  Important:[/bold yellow]")
            self._print("1. Passwords have been generated with 644 permissions")
            self._print("2. Restart services to apply new passwords")
            self._print("3. For existing databases, you may need to update passwords manually")

    def rotate_secret(self, secret_name: str):
        """Rotate a single secret"""
        if secret_name not in SECRET_DEFS:
            self._print(f"Unknown secret: {secret_name}", "red")
            return

        secret_def = SECRET_DEFS[secret_name]
        self._print(f"\n[bold yellow]Rotating secret: {secret_name}[/bold yellow]")
        self._print(f"Description: {secret_def['description']}")
        self._print(f"Affected services: {', '.join(secret_def['services'])}")

        if self.console:
            confirm = Confirm.ask("\n⚠️  This will generate a NEW secret. Continue?", default=False)
        else:
            confirm = input("\n⚠️  This will generate a NEW secret. Continue? (y/N): ").lower() == 'y'

        if not confirm:
            self._print("Cancelled", "yellow")
            return

        # Generate new secret
        if secret_def["type"] == "password":
            value = self._generate_password(secret_def["length"])
        else:
            value = self._generate_api_key(secret_def["length"])

        # Write secret
        if self._write_secret(secret_name, value):
            # Update config
            config = self._load_config()
            if secret_name not in config:
                config[secret_name] = {"created": datetime.now().isoformat()}

            config[secret_name]["rotated"] = datetime.now().isoformat()
            config[secret_name]["hash"] = self._get_secret_hash(secret_name)
            self._save_config(config)

            self._print(f"\n✅ Successfully rotated {secret_name}", "green")
            self._print("\n[bold yellow]Next steps:[/bold yellow]")
            self._print(f"1. Restart affected services: {', '.join(secret_def['services'])}")
            if secret_def["type"] == "password":
                self._print("2. For existing databases, update password manually:")
                if "postgres" in secret_def["services"]:
                    self._print(f"   PGPASSWORD=$(cat {self.secrets_dir / secret_name})")
                    self._print("   kubectl exec -n ai-stack deploy/postgres -- psql -U mcp -d mcp \\")
                    self._print("     -c \"ALTER USER mcp WITH PASSWORD '$(cat secrets/postgres_password)';\"")
        else:
            self._print(f"❌ Failed to rotate {secret_name}", "red")

    def rotate_all_secrets(self):
        """Rotate all secrets"""
        self._print("\n[bold red]⚠️  ROTATE ALL SECRETS[/bold red]")
        self._print("This will regenerate ALL passwords and API keys.")
        self._print("All services will need to be restarted.")

        if self.console:
            confirm = Confirm.ask("\nAre you SURE you want to continue?", default=False)
        else:
            confirm = input("\nAre you SURE you want to continue? (y/N): ").lower() == 'y'

        if not confirm:
            self._print("Cancelled", "yellow")
            return

        for secret_name in SECRET_DEFS.keys():
            self._print(f"\n→ Rotating {secret_name}...")
            self.rotate_secret(secret_name)

    def backup_secrets(self) -> Optional[str]:
        """Backup all secrets to timestamped directory"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"secrets_{timestamp}"

        try:
            backup_path.mkdir(parents=True, exist_ok=True)

            backed_up = 0
            for secret_name in SECRET_DEFS.keys():
                secret_file = self.secrets_dir / secret_name
                if secret_file.exists():
                    shutil.copy2(secret_file, backup_path / secret_name)
                    backed_up += 1

            # Backup config
            if self.config_file.exists():
                shutil.copy2(self.config_file, backup_path / ".secrets-config.json")

            self._print(f"\n✅ Backed up {backed_up} secrets to:", "green")
            self._print(f"   {backup_path}", "cyan")

            return str(backup_path)
        except Exception as e:
            self._print(f"❌ Backup failed: {e}", "red")
            return None

    def restore_secrets(self, backup_path: str):
        """Restore secrets from backup"""
        backup_dir = Path(backup_path)

        if not backup_dir.exists():
            self._print(f"Backup directory not found: {backup_path}", "red")
            return

        self._print(f"\n[bold yellow]Restoring secrets from:[/bold yellow]")
        self._print(f"   {backup_path}")

        if self.console:
            confirm = Confirm.ask("\n⚠️  This will OVERWRITE current secrets. Continue?", default=False)
        else:
            confirm = input("\n⚠️  This will OVERWRITE current secrets. Continue? (y/N): ").lower() == 'y'

        if not confirm:
            self._print("Cancelled", "yellow")
            return

        try:
            restored = 0
            for secret_file in backup_dir.glob("*"):
                if secret_file.name.startswith("."):
                    continue

                dest_file = self.secrets_dir / secret_file.name
                shutil.copy2(secret_file, dest_file)
                dest_file.chmod(0o644)
                restored += 1

            # Restore config
            backup_config = backup_dir / ".secrets-config.json"
            if backup_config.exists():
                shutil.copy2(backup_config, self.config_file)

            self._print(f"\n✅ Restored {restored} secrets", "green")
        except Exception as e:
            self._print(f"❌ Restore failed: {e}", "red")

    def list_backups(self):
        """List available backups"""
        if not self.backup_dir.exists():
            self._print("No backups found", "yellow")
            return []

        backups = sorted([d for d in self.backup_dir.iterdir() if d.is_dir()], reverse=True)

        if not backups:
            self._print("No backups found", "yellow")
            return []

        if self.console:
            table = Table(title="Available Backups", box=box.ROUNDED)
            table.add_column("#", style="cyan")
            table.add_column("Date", style="green")
            table.add_column("Path", style="blue")
            table.add_column("Files", style="magenta")

            for i, backup in enumerate(backups, 1):
                files = len(list(backup.glob("*")))
                date = backup.name.replace("secrets_", "").replace("_", " ")
                table.add_row(str(i), date, str(backup.name), str(files))

            self.console.print(table)
        else:
            self._print("\nAvailable Backups:")
            for i, backup in enumerate(backups, 1):
                files = len(list(backup.glob("*")))
                self._print(f"  {i}. {backup.name} ({files} files)")

        return backups

    def status(self):
        """Show status of all secrets"""
        config = self._load_config()

        if self.console:
            table = Table(title="AI Stack Secrets Status", box=box.ROUNDED)
            table.add_column("Secret", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Size", style="blue")
            table.add_column("Services", style="yellow")
            table.add_column("Last Rotated", style="dim")

            for secret_name, secret_def in SECRET_DEFS.items():
                secret_file = self.secrets_dir / secret_name

                if secret_file.exists():
                    size = secret_file.stat().st_size
                    status = "✅ OK"
                    style = "green"
                else:
                    size = 0
                    status = "❌ MISSING"
                    style = "red"

                rotated = config.get(secret_name, {}).get("rotated", "Never")
                if rotated != "Never":
                    rotated = rotated.split("T")[0]

                services = ", ".join(secret_def["services"][:2])
                if len(secret_def["services"]) > 2:
                    services += f" +{len(secret_def['services']) - 2}"

                table.add_row(
                    secret_name,
                    secret_def["type"],
                    status,
                    f"{size}B",
                    services,
                    rotated
                )

            self.console.print(table)
        else:
            self._print("\nAI Stack Secrets Status:")
            self._print("=" * 80)
            for secret_name, secret_def in SECRET_DEFS.items():
                secret_file = self.secrets_dir / secret_name
                status = "✅ OK" if secret_file.exists() else "❌ MISSING"
                size = secret_file.stat().st_size if secret_file.exists() else 0
                self._print(f"  {secret_name:30} {status:10} {size:4}B {secret_def['type']}")

    def validate(self):
        """Validate all secrets"""
        self._print("\n[bold cyan]Validating Secrets[/bold cyan]")
        self._print("=" * 60)

        issues = []
        warnings = []

        for secret_name, secret_def in SECRET_DEFS.items():
            secret_file = self.secrets_dir / secret_name

            # Check existence
            if not secret_file.exists():
                issues.append(f"❌ {secret_name}: File does not exist")
                continue

            # Check size
            size = secret_file.stat().st_size
            expected_size = secret_def["length"]
            if size != expected_size:
                warnings.append(f"⚠️  {secret_name}: Size is {size}B, expected {expected_size}B")

            # Check permissions
            perms = oct(secret_file.stat().st_mode)[-3:]
            if perms != "644":
                warnings.append(f"⚠️  {secret_name}: Permissions are {perms}, should be 644")

            # Check content
            value = self._read_secret(secret_name)
            if not value:
                issues.append(f"❌ {secret_name}: Empty or unreadable")
            elif len(value) != expected_size:
                warnings.append(f"⚠️  {secret_name}: Content length is {len(value)}, expected {expected_size}")

        if issues:
            self._print("\n[bold red]Issues Found:[/bold red]")
            for issue in issues:
                self._print(f"  {issue}")

        if warnings:
            self._print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in warnings:
                self._print(f"  {warning}")

        if not issues and not warnings:
            self._print("\n[bold green]✅ All secrets are valid![/bold green]")

        return len(issues) == 0

    def interactive_menu(self):
        """Show interactive menu"""
        while True:
            if self.console:
                self.console.clear()
                self.console.print(Panel.fit(
                    "[bold cyan]AI Stack Secrets Manager[/bold cyan]\n"
                    "[dim]Manage passwords and API keys for your AI stack[/dim]",
                    border_style="cyan"
                ))

                menu = Table(show_header=False, box=None, padding=(0, 2))
                menu.add_row("[cyan]1.[/cyan]", "Initialize all secrets")
                menu.add_row("[cyan]2.[/cyan]", "Rotate a secret")
                menu.add_row("[cyan]3.[/cyan]", "Rotate all secrets")
                menu.add_row("[cyan]4.[/cyan]", "Backup secrets")
                menu.add_row("[cyan]5.[/cyan]", "Restore from backup")
                menu.add_row("[cyan]6.[/cyan]", "Show status")
                menu.add_row("[cyan]7.[/cyan]", "Validate secrets")
                menu.add_row("[cyan]8.[/cyan]", "Exit")

                self.console.print(menu)

                choice = Prompt.ask("\nSelect an option", choices=["1", "2", "3", "4", "5", "6", "7", "8"])
            else:
                print("\n" + "=" * 60)
                print("AI Stack Secrets Manager")
                print("=" * 60)
                print("1. Initialize all secrets")
                print("2. Rotate a secret")
                print("3. Rotate all secrets")
                print("4. Backup secrets")
                print("5. Restore from backup")
                print("6. Show status")
                print("7. Validate secrets")
                print("8. Exit")
                choice = input("\nSelect an option (1-8): ")

            if choice == "1":
                self.init_secrets()
                input("\nPress Enter to continue...")
            elif choice == "2":
                self.status()
                if self.console:
                    secret = Prompt.ask("\nEnter secret name to rotate")
                else:
                    secret = input("\nEnter secret name to rotate: ")
                self.rotate_secret(secret)
                input("\nPress Enter to continue...")
            elif choice == "3":
                self.rotate_all_secrets()
                input("\nPress Enter to continue...")
            elif choice == "4":
                self.backup_secrets()
                input("\nPress Enter to continue...")
            elif choice == "5":
                backups = self.list_backups()
                if backups:
                    if self.console:
                        choice = Prompt.ask("\nSelect backup number to restore (or 'cancel')")
                    else:
                        choice = input("\nSelect backup number to restore (or 'cancel'): ")

                    if choice.lower() != 'cancel':
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(backups):
                                self.restore_secrets(str(backups[idx]))
                        except ValueError:
                            self._print("Invalid selection", "red")
                input("\nPress Enter to continue...")
            elif choice == "6":
                self.status()
                input("\nPress Enter to continue...")
            elif choice == "7":
                self.validate()
                input("\nPress Enter to continue...")
            elif choice == "8":
                self._print("\nGoodbye! 👋", "cyan")
                break


def main():
    """Main entry point"""
    manager = SecretsManager()

    if len(sys.argv) == 1:
        # Interactive mode
        manager.interactive_menu()
    else:
        # CLI mode
        command = sys.argv[1].lower()

        if command == "init":
            force = "--force" in sys.argv
            manager.init_secrets(force=force)
        elif command == "rotate":
            if len(sys.argv) < 3:
                print("Usage: manage-secrets.py rotate <secret_name|all>")
                sys.exit(1)

            secret = sys.argv[2].lower()
            if secret == "all":
                manager.rotate_all_secrets()
            else:
                manager.rotate_secret(secret)
        elif command == "backup":
            manager.backup_secrets()
        elif command == "restore":
            if len(sys.argv) < 3:
                backups = manager.list_backups()
                if backups:
                    print(f"\nUsage: manage-secrets.py restore <backup_path>")
                sys.exit(1)
            manager.restore_secrets(sys.argv[2])
        elif command == "status":
            manager.status()
        elif command == "validate":
            valid = manager.validate()
            sys.exit(0 if valid else 1)
        elif command == "list-backups":
            manager.list_backups()
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  init [--force]      - Initialize all secrets")
            print("  rotate <name|all>   - Rotate secret(s)")
            print("  backup              - Backup all secrets")
            print("  restore <path>      - Restore from backup")
            print("  status              - Show secret status")
            print("  validate            - Validate all secrets")
            print("  list-backups        - List available backups")
            sys.exit(1)


if __name__ == "__main__":
    main()
