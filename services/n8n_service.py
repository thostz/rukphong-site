"""Trigger N8N webhook for notifications (LINE + Email)."""

import os
import requests

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")


def _trigger(payload: dict) -> bool:
    if not N8N_WEBHOOK_URL:
        print("[N8N] N8N_WEBHOOK_URL not set — skipping notification")
        return False
    try:
        res = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
        print(f"[N8N] triggered → {res.status_code}")
        return res.ok
    except Exception as e:
        print(f"[N8N] error: {e}")
        return False


def notify_contact(name: str, email: str, company: str,
                   subject: str, message: str):
    """Fired when someone submits the contact form."""
    _trigger({
        "type": "contact",
        "name": name,
        "email": email,
        "company": company,
        "subject": subject,
        "message": message,
    })


def notify_register(name: str, email: str):
    """Fired when a new user registers."""
    _trigger({
        "type": "register",
        "name": name,
        "email": email,
    })
