"""Support slack integration.

Any time we want to send a notification to Slack, we use the configured Slack
"Incoming Webhook" which must be configured and then set in the config file
with the variable `SLACK_HOOK`
"""

# pylama:ignore=D213,E501

import requests
from flask import current_app

from .log import app_logger


def notify(msg, *args):
    """Notify slack if possible."""
    log = app_logger()

    hook = current_app.config.get("SLACK_HOOK", "").strip()
    if not hook:
        log.warn("Slack NOT notified: SLACK_HOOK not configured")
        return

    if args:
        msg = msg % args
    if not msg.strip():
        log.warn("Slack NOT notified: no message specified")
        return

    r = requests.post(hook, json={
        "channel": "#general",
        "username": "Movie Night Monkey",
        "icon_emoji": ":monkey:",
        "mrkdwn": True,
        "text": msg
    })

    if r.status_code == requests.codes.ok:
        log.info("Notified slack")
    else:
        log.error("Error notifying slack: [%d %s] %s", r.status_code, r.reason, r.text)
