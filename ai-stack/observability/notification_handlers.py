"""
Multi-Channel Notification Handlers - Alert delivery to various channels.

Provides notification delivery to email, Slack, Discord, webhooks, and browser.
Handles rate limiting, retry logic, and notification templates.

Part of Phase 1 (Monitoring & Observability) implementation.
"""

import asyncio
import json
import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Any, Dict, Optional, List
import httpx
import yaml

logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """Configuration for notification channels."""
    enabled: bool
    rate_limit_per_hour: int = 10
    retry_attempts: int = 3
    retry_delay_seconds: int = 5


class NotificationHandlers:
    """
    Multi-channel notification delivery system.

    Handles alert routing to email, Slack, Discord, webhooks, and browser.
    Includes rate limiting and retry logic.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize notification handlers.

        Args:
            config_path: Path to notifications YAML config
        """
        self.config: Dict[str, NotificationConfig] = {}
        self.rate_limit_tracking: Dict[str, List[datetime]] = {}

        if config_path and config_path.exists():
            self.load_config(config_path)
        else:
            # Default configuration
            self.config = {
                "email": NotificationConfig(enabled=False, rate_limit_per_hour=10),
                "slack": NotificationConfig(enabled=False, rate_limit_per_hour=20),
                "discord": NotificationConfig(enabled=False, rate_limit_per_hour=20),
                "webhook": NotificationConfig(enabled=True, rate_limit_per_hour=100),
                "browser": NotificationConfig(enabled=True, rate_limit_per_hour=1000),
            }

        # Channel-specific configuration from environment
        self.email_config = {
            "smtp_host": os.getenv("ALERT_SMTP_HOST", "localhost"),
            "smtp_port": int(os.getenv("ALERT_SMTP_PORT", "587")),
            "smtp_user": os.getenv("ALERT_SMTP_USER", ""),
            "smtp_password": os.getenv("ALERT_SMTP_PASSWORD", ""),
            "from_address": os.getenv("ALERT_EMAIL_FROM", "alerts@localhost"),
            "to_addresses": os.getenv("ALERT_EMAIL_TO", "").split(","),
        }

        self.slack_config = {
            "webhook_url": os.getenv("ALERT_SLACK_WEBHOOK_URL", ""),
            "channel": os.getenv("ALERT_SLACK_CHANNEL", "#alerts"),
            "username": os.getenv("ALERT_SLACK_USERNAME", "AI Stack Alerts"),
        }

        self.discord_config = {
            "webhook_url": os.getenv("ALERT_DISCORD_WEBHOOK_URL", ""),
            "username": os.getenv("ALERT_DISCORD_USERNAME", "AI Stack Alerts"),
        }

        self.webhook_config = {
            "urls": os.getenv("ALERT_WEBHOOK_URLS", "").split(","),
            "auth_headers": {},  # Could be loaded from config file
        }

    def load_config(self, config_path: Path) -> None:
        """Load notification configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)

            for channel, settings in config_data.get('channels', {}).items():
                self.config[channel] = NotificationConfig(
                    enabled=settings.get('enabled', False),
                    rate_limit_per_hour=settings.get('rate_limit_per_hour', 10),
                    retry_attempts=settings.get('retry_attempts', 3),
                    retry_delay_seconds=settings.get('retry_delay_seconds', 5),
                )

            logger.info(f"Loaded notification config from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load notification config: {e}")

    def _check_rate_limit(self, channel: str) -> bool:
        """
        Check if notification is within rate limit for channel.

        Args:
            channel: Notification channel name

        Returns:
            True if within limit, False if rate limited
        """
        now = datetime.utcnow()
        config = self.config.get(channel)
        if not config:
            return True

        # Initialize tracking for channel
        if channel not in self.rate_limit_tracking:
            self.rate_limit_tracking[channel] = []

        # Remove notifications older than 1 hour
        cutoff = now - timedelta(hours=1)
        self.rate_limit_tracking[channel] = [
            ts for ts in self.rate_limit_tracking[channel] if ts > cutoff
        ]

        # Check rate limit
        if len(self.rate_limit_tracking[channel]) >= config.rate_limit_per_hour:
            logger.warning(f"Rate limit exceeded for {channel}")
            return False

        # Record this notification
        self.rate_limit_tracking[channel].append(now)
        return True

    async def send_email(self, alert: Any) -> Dict[str, Any]:
        """
        Send alert notification via email.

        Args:
            alert: Alert object

        Returns:
            Result dict with success status
        """
        if not self.config.get("email", NotificationConfig(enabled=False)).enabled:
            return {"success": False, "error": "Email notifications disabled"}

        if not self._check_rate_limit("email"):
            return {"success": False, "error": "Rate limit exceeded"}

        if not self.email_config["smtp_user"] or not self.email_config["to_addresses"][0]:
            return {"success": False, "error": "Email not configured"}

        try:
            # Build email
            msg = MIMEMultipart()
            msg['From'] = self.email_config["from_address"]
            msg['To'] = ", ".join(self.email_config["to_addresses"])
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"

            body = f"""
Alert Details:
--------------
Title: {alert.title}
Severity: {alert.severity.value.upper()}
Source: {alert.source}
Component: {alert.component}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Message:
{alert.message}

Alert ID: {alert.id}
Status: {alert.status.value}

---
AI Stack Monitoring System
            """

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            with smtplib.SMTP(self.email_config["smtp_host"], self.email_config["smtp_port"]) as server:
                server.starttls()
                if self.email_config["smtp_user"]:
                    server.login(self.email_config["smtp_user"], self.email_config["smtp_password"])
                server.send_message(msg)

            logger.info(f"Email notification sent for alert {alert.id}")
            return {"success": True, "channel": "email"}

        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_slack(self, alert: Any) -> Dict[str, Any]:
        """
        Send alert notification to Slack.

        Args:
            alert: Alert object

        Returns:
            Result dict with success status
        """
        if not self.config.get("slack", NotificationConfig(enabled=False)).enabled:
            return {"success": False, "error": "Slack notifications disabled"}

        if not self._check_rate_limit("slack"):
            return {"success": False, "error": "Rate limit exceeded"}

        if not self.slack_config["webhook_url"]:
            return {"success": False, "error": "Slack webhook URL not configured"}

        try:
            # Severity color mapping
            colors = {
                "info": "#36a64f",
                "warning": "#ff9900",
                "critical": "#ff0000",
                "emergency": "#8B0000",
            }

            # Build Slack message
            payload = {
                "channel": self.slack_config["channel"],
                "username": self.slack_config["username"],
                "icon_emoji": ":rotating_light:" if alert.severity.value in ("critical", "emergency") else ":warning:",
                "attachments": [{
                    "color": colors.get(alert.severity.value, "#cccccc"),
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Component", "value": alert.component, "short": True},
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Status", "value": alert.status.value, "short": True},
                    ],
                    "footer": "AI Stack Monitoring",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.slack_config["webhook_url"],
                    json=payload,
                    timeout=10.0
                )

                if response.status_code == 200:
                    logger.info(f"Slack notification sent for alert {alert.id}")
                    return {"success": True, "channel": "slack"}
                else:
                    logger.error(f"Slack notification failed: {response.status_code} {response.text}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_discord(self, alert: Any) -> Dict[str, Any]:
        """
        Send alert notification to Discord.

        Args:
            alert: Alert object

        Returns:
            Result dict with success status
        """
        if not self.config.get("discord", NotificationConfig(enabled=False)).enabled:
            return {"success": False, "error": "Discord notifications disabled"}

        if not self._check_rate_limit("discord"):
            return {"success": False, "error": "Rate limit exceeded"}

        if not self.discord_config["webhook_url"]:
            return {"success": False, "error": "Discord webhook URL not configured"}

        try:
            # Severity color mapping (Discord colors are integers)
            colors = {
                "info": 0x36a64f,      # Green
                "warning": 0xff9900,    # Orange
                "critical": 0xff0000,   # Red
                "emergency": 0x8B0000,  # Dark red
            }

            # Build Discord embed
            payload = {
                "username": self.discord_config["username"],
                "embeds": [{
                    "title": f"🚨 {alert.title}",
                    "description": alert.message,
                    "color": colors.get(alert.severity.value, 0xcccccc),
                    "fields": [
                        {"name": "Severity", "value": alert.severity.value.upper(), "inline": True},
                        {"name": "Component", "value": alert.component, "inline": True},
                        {"name": "Source", "value": alert.source, "inline": True},
                        {"name": "Status", "value": alert.status.value, "inline": True},
                    ],
                    "footer": {"text": "AI Stack Monitoring"},
                    "timestamp": alert.timestamp.isoformat()
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.discord_config["webhook_url"],
                    json=payload,
                    timeout=10.0
                )

                if response.status_code in (200, 204):
                    logger.info(f"Discord notification sent for alert {alert.id}")
                    return {"success": True, "channel": "discord"}
                else:
                    logger.error(f"Discord notification failed: {response.status_code} {response.text}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_webhook(self, alert: Any) -> Dict[str, Any]:
        """
        Send alert notification to generic webhook endpoint.

        Args:
            alert: Alert object

        Returns:
            Result dict with success status
        """
        if not self.config.get("webhook", NotificationConfig(enabled=False)).enabled:
            return {"success": False, "error": "Webhook notifications disabled"}

        if not self._check_rate_limit("webhook"):
            return {"success": False, "error": "Rate limit exceeded"}

        webhook_urls = [url.strip() for url in self.webhook_config["urls"] if url.strip()]
        if not webhook_urls:
            return {"success": False, "error": "No webhook URLs configured"}

        try:
            # Build generic webhook payload
            payload = alert.to_dict()

            results = []
            async with httpx.AsyncClient() as client:
                for url in webhook_urls:
                    try:
                        response = await client.post(
                            url,
                            json=payload,
                            headers=self.webhook_config.get("auth_headers", {}),
                            timeout=10.0
                        )

                        success = response.status_code in (200, 201, 202, 204)
                        results.append({
                            "url": url,
                            "success": success,
                            "status_code": response.status_code
                        })

                        if success:
                            logger.info(f"Webhook notification sent to {url} for alert {alert.id}")
                        else:
                            logger.error(f"Webhook notification failed to {url}: {response.status_code}")

                    except Exception as e:
                        logger.error(f"Webhook notification failed to {url}: {e}")
                        results.append({
                            "url": url,
                            "success": False,
                            "error": str(e)
                        })

            overall_success = any(r["success"] for r in results)
            return {
                "success": overall_success,
                "channel": "webhook",
                "results": results
            }

        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            return {"success": False, "error": str(e)}


# Global notification handlers instance
_notification_handlers = NotificationHandlers()


async def email_notification_handler(alert: Any) -> Dict[str, Any]:
    """Email notification handler for alert engine."""
    return await _notification_handlers.send_email(alert)


async def slack_notification_handler(alert: Any) -> Dict[str, Any]:
    """Slack notification handler for alert engine."""
    return await _notification_handlers.send_slack(alert)


async def discord_notification_handler(alert: Any) -> Dict[str, Any]:
    """Discord notification handler for alert engine."""
    return await _notification_handlers.send_discord(alert)


async def webhook_notification_handler(alert: Any) -> Dict[str, Any]:
    """Webhook notification handler for alert engine."""
    return await _notification_handlers.send_webhook(alert)
