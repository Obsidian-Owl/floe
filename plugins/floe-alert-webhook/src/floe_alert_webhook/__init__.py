"""Floe Webhook alert channel plugin.

This plugin sends contract violation alerts to webhooks.

Entry point: floe.alert_channels.webhook
"""

from __future__ import annotations

from floe_alert_webhook.plugin import WebhookAlertPlugin

__all__ = ["WebhookAlertPlugin"]
