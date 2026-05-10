from __future__ import annotations
"""
Slip OCR handler for Render/Flask LINE webhook.

Flow:
  1. Download image from LINE Content API
  2. If GEMINI_API_KEY is set → use Gemini Vision (gemini-1.5-flash) to read slip
     Otherwise → reply with manual entry prompt
  3. Parse amount + category from Gemini response
  4. Save to PostgreSQL via data_service
  5. Also fire-and-forget POST to Apps Script sheet
  6. Return reply string for LINE

Requires env vars:
  LINE_CHANNEL_ACCESS_TOKEN  (already set)
  GEMINI_API_KEY             (optional — get free key at aistudio.google.com)
"""

import os
import json
import time
import base64
import threading
import requests
import datetime

from services import data_service as data_svc

LINE_TOKEN   = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
GS_SCRIPT_URL = os.getenv("GS_SCRIPT_URL", "")


# ── Main entry ────────────────────────────────────────────────────────────────

def process(message_id: str, user_id: str) -> str:
    """Download image → OCR → save expense → return reply."""
    if not GEMINI_KEY:
        return (
            "📸 ได้รับรูปแล้ว!\n\n"
            "หากเป็น Slip ให้พิมพ์คำสั่งด้วยตนเอง:\n"
            "จ่าย [จำนวน] [หมวด]\n\n"
            "ตัวอย่าง:\nจ่าย 350 อาหาร\nจ่าย 120 เดินทาง\n\n"
            "(ตั้งค่า GEMINI_API_KEY เพื่อเปิดใช้งาน Slip OCR อัตโนมัติ)"
        )

    try:
        img_b64, mime = _download_image(message_id)
        if not img_b64:
            return "❌ ไม่สามารถดาวน์โหลดรูปได้ กรุณาลองใหม่"

        result = _gemini_ocr(img_b64, mime)
        if not result:
            return (
                "❌ อ่านข้อมูลจากรูปไม่ได้\n\n"
                "กรุณาพิมพ์:\nจ่าย [จำนวน] [หมวด]\n\n"
                "เช่น: จ่าย 350 อาหาร"
            )

        amount   = result.get("amount", 0)
        category = result.get("category", "อื่นๆ")
        merchant = result.get("merchant", "")
        notes    = f"Slip: {merchant}" if merchant else "จาก Slip"

        if not amount or float(amount) <= 0:
            raw_text = result.get("raw_text", "")
            return (
                f"📄 อ่านข้อความได้แต่ไม่พบจำนวนเงิน\n\n"
                + (f'"{raw_text[:120]}"\n\n' if raw_text else "")
                + "กรุณาพิมพ์:\nจ่าย [จำนวน] [หมวด]"
            )

        # Save to DB
        record = {
            "id":       str(int(time.time() * 1000)),
            "date":     datetime.date.today().isoformat(),
            "amount":   float(amount),
            "category": category,
            "payment":  "",
            "notes":    notes,
        }
        data_svc.save_expense(record)

        # Sync to Apps Script sheet (fire-and-forget)
        if GS_SCRIPT_URL:
            threading.Thread(
                target=_post_gs,
                args=("saveExpense", record),
                daemon=True,
            ).start()

        fmt = f"{float(amount):,.2f}"
        reply = (
            f"✅ บันทึกจาก Slip อัตโนมัติ\n"
            f"💰 ฿{fmt}\n"
            f"📂 {category}"
        )
        if merchant:
            reply += f"\n🏪 {merchant}"
        reply += "\n\nถ้าหมวดไม่ถูก พิมพ์:\nจ่าย [จำนวน] [หมวด]"
        return reply

    except Exception as e:
        print(f"[SlipHandler] {e}")
        return f"❌ เกิดข้อผิดพลาด: {e}"


# ── Internals ─────────────────────────────────────────────────────────────────

def _download_image(message_id: str):
    """Download image from LINE Content API. Returns (base64_str, mime_type)."""
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {LINE_TOKEN}"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[SlipHandler] LINE image download failed: {resp.status_code}")
            return None, None
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        b64  = base64.b64encode(resp.content).decode("utf-8")
        return b64, mime
    except Exception as e:
        print(f"[SlipHandler] download error: {e}")
        return None, None


def _gemini_ocr(img_b64: str, mime: str) -> dict | None:
    """
    Send image to Gemini Vision for slip OCR.
    Returns dict with keys: amount, category, merchant, raw_text
    """
    prompt = (
        "อ่านข้อมูลจากสลิปหรือใบเสร็จในรูปนี้ แล้วตอบเป็น JSON เท่านั้น:\n\n"
        "{\n"
        '  "amount": <number ยอดเงินทั้งหมด หรือ 0 ถ้าไม่พบ>,\n'
        '  "category": "<หมวดหมู่ เช่น อาหาร/เครื่องดื่ม|เดินทาง|ช้อปปิ้ง|สุขภาพ|ที่พัก|ความบันเทิง|การศึกษา|อื่นๆ>",\n'
        '  "merchant": "<ชื่อร้านหรือ merchant ถ้ามี>",\n'
        '  "raw_text": "<ข้อความสำคัญจากสลิป ไม่เกิน 100 ตัวอักษร>"\n'
        "}\n\n"
        "ถ้าไม่ใช่สลิปหรือใบเสร็จ ให้ใส่ amount: 0"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    )
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": img_b64}},
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
    }

    try:
        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code != 200:
            print(f"[SlipHandler] Gemini Vision error {resp.status_code}: {resp.text[:200]}")
            return None

        raw  = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        import re
        jm = re.search(r'\{[\s\S]*\}', raw)
        if not jm:
            print(f"[SlipHandler] No JSON in Gemini response: {raw[:200]}")
            return None
        return json.loads(jm.group())

    except Exception as e:
        print(f"[SlipHandler] Gemini OCR error: {e}")
        return None


def _post_gs(action: str, record: dict):
    """Fire-and-forget POST to Apps Script."""
    try:
        requests.post(
            GS_SCRIPT_URL,
            data=json.dumps({"action": action, "record": record}),
            timeout=10,
        )
    except Exception as e:
        print(f"[SlipHandler GS.{action}] {e}")
