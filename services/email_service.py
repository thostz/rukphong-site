"""Send email notifications via Gmail SMTP — no N8N required."""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", GMAIL_USER)


def _send(subject: str, html: str, reply_to: str = ""):
    if not GMAIL_USER or not GMAIL_PASS:
        print("[Email] GMAIL_USER or GMAIL_APP_PASSWORD not set — skipping")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"RP Consultant <{GMAIL_USER}>"
        msg["To"]      = ADMIN_EMAIL
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.sendmail(GMAIL_USER, ADMIN_EMAIL, msg.as_string())
        print("[Email] sent OK")
        return True
    except Exception as e:
        print(f"[Email] error: {e}")
        return False


def notify_contact(name: str, email: str, company: str,
                   subject: str, message: str):
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:20px;border-radius:12px 12px 0 0">
        <h2 style="color:#fff;margin:0">📩 Contact Message</h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px">
        <table style="width:100%;border-collapse:collapse">
          <tr><td style="padding:8px 12px;background:#f9fafb;font-weight:600;width:30%">ชื่อ</td>
              <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9">{name}</td></tr>
          <tr><td style="padding:8px 12px;background:#f9fafb;font-weight:600">Email</td>
              <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9">{email}</td></tr>
          <tr><td style="padding:8px 12px;background:#f9fafb;font-weight:600">บริษัท</td>
              <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9">{company or '-'}</td></tr>
          <tr><td style="padding:8px 12px;background:#f9fafb;font-weight:600">เรื่อง</td>
              <td style="padding:8px 12px">{subject or '-'}</td></tr>
        </table>
        <div style="margin-top:20px;background:#f9fafb;padding:16px;border-radius:8px;
                    border-left:4px solid #6366f1;white-space:pre-wrap">{message}</div>
      </div>
    </div>"""
    _send(
        subject=f"[Contact] {subject or 'New message'} from {name}",
        html=html,
        reply_to=email,
    )


def notify_register(name: str, email: str):
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:auto">
      <div style="background:linear-gradient(135deg,#3b82f6,#6366f1);padding:20px;border-radius:12px 12px 0 0">
        <h2 style="color:#fff;margin:0">👤 New Registration</h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px">
        <table style="width:100%;border-collapse:collapse">
          <tr><td style="padding:8px 12px;background:#f9fafb;font-weight:600;width:30%">ชื่อ</td>
              <td style="padding:8px 12px;border-bottom:1px solid #f1f5f9">{name}</td></tr>
          <tr><td style="padding:8px 12px;background:#f9fafb;font-weight:600">Email</td>
              <td style="padding:8px 12px">{email}</td></tr>
        </table>
      </div>
    </div>"""
    _send(subject=f"[Register] New user: {name}", html=html)
