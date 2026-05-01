"""Push LINE messages to admin using Messaging API (replaces LINE Notify)."""

import os
import requests

_TOKEN    = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
_ADMIN_ID = os.getenv("ADMIN_LINE_USER_ID", "")

_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def _push(text: str) -> bool:
    if not _TOKEN or not _ADMIN_ID:
        print("[LINE Push] ADMIN_LINE_USER_ID or TOKEN not set — skipping")
        return False
    try:
        res = requests.post(
            _PUSH_URL,
            headers={"Authorization": f"Bearer {_TOKEN}"},
            json={"to": _ADMIN_ID, "messages": [{"type": "text", "text": text}]},
            timeout=10,
        )
        print(f"[LINE Push] {res.status_code}")
        return res.ok
    except Exception as e:
        print(f"[LINE Push] error: {e}")
        return False


def notify_contact(name: str, email: str, company: str,
                   subject: str, message: str):
    text = (
        f"📩 Contact Form\n\n"
        f"จาก: {name}\n"
        f"Email: {email}\n"
        f"บริษัท: {company or '-'}\n"
        f"เรื่อง: {subject or '-'}\n\n"
        f"{message}"
    )
    _push(text)


def notify_register(name: str, email: str):
    text = (
        f"👤 ผู้ใช้ใหม่ลงทะเบียน\n\n"
        f"ชื่อ: {name}\n"
        f"Email: {email}"
    )
    _push(text)
