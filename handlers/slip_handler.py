from __future__ import annotations
"""
Slip OCR handler for Render/Flask LINE webhook.

Flow:
  1. Download image from LINE Content API
  2. If GEMINI_API_KEY is set → use Gemini Vision (gemini-2.0-flash) to read slip
     Otherwise → reply with manual entry prompt
  3. Parse amount + category + date from Gemini response
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
import re

from services import data_service as data_svc

GS_SCRIPT_URL = os.getenv("GS_SCRIPT_URL", "")


# ── Main entry ────────────────────────────────────────────────────────────────

def process(message_id: str, user_id: str) -> str:
    """Download image → OCR → save expense → return reply."""
    # Read env vars at request time (not at import time) so Render picks them up
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

    print(f"[SlipHandler] process() — gemini_key={'SET' if gemini_key else 'MISSING'}, line_token={'SET' if line_token else 'MISSING'}, msg_id={message_id}")

    if not gemini_key:
        return (
            "⚠️ [DEBUG] GEMINI_API_KEY ยังไม่ได้ตั้งค่าบน Render\n\n"
            "วิธีแก้: Render Dashboard → Environment → เพิ่ม GEMINI_API_KEY\n\n"
            "หรือพิมพ์:\nจ่าย [จำนวน] [หมวด]\nเช่น: จ่าย 350 อาหาร"
        )

    try:
        img_b64, mime = _download_image(message_id, line_token)
        if not img_b64:
            return (
                "⚠️ [DEBUG] ดาวน์โหลดรูปจาก LINE ไม่ได้\n"
                f"token={'SET' if line_token else 'MISSING'}\n"
                "ตรวจสอบ LINE_CHANNEL_ACCESS_TOKEN บน Render"
            )

        result = _gemini_ocr(img_b64, mime, gemini_key)
        if not result:
            return (
                "⚠️ [DEBUG] Gemini อ่านรูปไม่ได้\n"
                f"mime={mime} | img_size={len(img_b64)} chars\n"
                "ตรวจสอบ log บน Render ว่ามี Gemini error อะไร"
            )

        amount   = result.get("amount", 0)
        category = result.get("category", "อื่นๆ")
        merchant = result.get("merchant", "")
        slip_date = result.get("date", "")  # date extracted from slip
        notes    = f"Slip: {merchant}" if merchant else "จาก Slip"

        if not amount or float(amount) <= 0:
            raw_text = result.get("raw_text", "")
            return (
                "📄 อ่านข้อความได้แต่ไม่พบจำนวนเงิน\n\n"
                + (f'"{raw_text[:120]}"\n\n' if raw_text else "")
                + "กรุณาพิมพ์:\nจ่าย [จำนวน] [หมวด]"
            )

        # Use slip date if valid, otherwise today
        today = datetime.date.today().isoformat()
        record_date = _parse_date(slip_date) or today

        # Save to DB
        record = {
            "id":       str(int(time.time() * 1000)),
            "date":     record_date,
            "amount":   float(amount),
            "category": category,
            "payment":  "",
            "notes":    notes,
        }
        data_svc.save_expense(record)

        # Sync to Apps Script sheet (fire-and-forget)
        gs_url = os.getenv("GS_SCRIPT_URL", "")
        if gs_url:
            threading.Thread(
                target=_post_gs,
                args=(gs_url, "saveExpense", record),
                daemon=True,
            ).start()

        fmt = f"{float(amount):,.2f}"
        reply = (
            f"✅ บันทึกจาก Slip อัตโนมัติ\n"
            f"📅 {record_date}\n"
            f"💰 ฿{fmt}\n"
            f"📂 {category}"
        )
        if merchant:
            reply += f"\n🏪 {merchant}"
        reply += "\n\nถ้าหมวดไม่ถูก พิมพ์:\nจ่าย [จำนวน] [หมวด]"
        return reply

    except Exception as e:
        print(f"[SlipHandler] EXCEPTION: {e}")
        return f"⚠️ [DEBUG] Exception: {e}"


# ── Internals ─────────────────────────────────────────────────────────────────

def _download_image(message_id: str, line_token: str):
    """Download image from LINE Content API. Returns (base64_str, mime_type)."""
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {line_token}"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[SlipHandler] LINE image download failed: {resp.status_code} — token set: {bool(line_token)}")
            return None, None
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        b64  = base64.b64encode(resp.content).decode("utf-8")
        return b64, mime
    except Exception as e:
        print(f"[SlipHandler] download error: {e}")
        return None, None


def _gemini_ocr(img_b64: str, mime: str, gemini_key: str) -> dict | None:
    """
    Send image to Gemini Vision for slip OCR.
    Returns dict with keys: amount, category, merchant, date, raw_text
    """
    prompt = (
        "อ่านข้อมูลจากสลิปหรือใบเสร็จในรูปนี้ แล้วตอบเป็น JSON เท่านั้น ห้ามอธิบายเพิ่มเติม:\n\n"
        "{\n"
        '  "amount": <number ยอดเงินทั้งหมด หรือ 0 ถ้าไม่พบ>,\n'
        '  "category": "<อาหาร/เครื่องดื่ม|เดินทาง|ช้อปปิ้ง|สุขภาพ|ที่พัก|ความบันเทิง|การศึกษา|อื่นๆ>",\n'
        '  "merchant": "<ชื่อร้านหรือผู้รับโอนเงิน ถ้ามี ไม่เช่นนั้น blank>",\n'
        '  "date": "<วันที่ในสลิป รูปแบบ YYYY-MM-DD ถ้าไม่พบให้ blank>",\n'
        '  "raw_text": "<ข้อความสำคัญจากสลิป ไม่เกิน 100 ตัวอักษร>"\n'
        "}\n\n"
        "ถ้าไม่ใช่สลิปหรือใบเสร็จ ให้ใส่ amount: 0"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.0-flash:generateContent?key={gemini_key}"
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
            print(f"[SlipHandler] Gemini Vision error {resp.status_code}: {resp.text[:300]}")
            return None

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        jm = re.search(r'\{[\s\S]*\}', raw)
        if not jm:
            print(f"[SlipHandler] No JSON in Gemini response: {raw[:200]}")
            return None
        return json.loads(jm.group())

    except Exception as e:
        print(f"[SlipHandler] Gemini OCR error: {e}")
        return None


def _parse_date(date_str: str) -> str | None:
    """Try to parse date string → YYYY-MM-DD. Returns None if invalid."""
    if not date_str:
        return None
    # Already ISO format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        try:
            datetime.date.fromisoformat(date_str)
            return date_str
        except ValueError:
            return None
    # Try common Thai/Asian formats: DD/MM/YYYY, DD-MM-YYYY
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _post_gs(gs_url: str, action: str, record: dict):
    """Fire-and-forget POST to Apps Script."""
    try:
        requests.post(
            gs_url,
            data=json.dumps({"action": action, "record": record}),
            timeout=10,
        )
    except Exception as e:
        print(f"[SlipHandler GS.{action}] {e}")
