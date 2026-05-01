"""User language preference + translations (th / en)."""

import json, os

_LANG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "user_lang.json")


def _load() -> dict:
    try:
        os.makedirs(os.path.dirname(_LANG_FILE), exist_ok=True)
        with open(_LANG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(_LANG_FILE), exist_ok=True)
    with open(_LANG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_user_lang: dict[str, str] = _load()


def get_lang(user_id: str) -> str:
    return _user_lang.get(user_id, "th")


def set_lang(user_id: str, lang: str):
    _user_lang[user_id] = lang
    _save(_user_lang)


def detect_and_set(user_id: str, text: str) -> str:
    """ถ้าข้อความส่วนใหญ่เป็น ASCII ให้ switch เป็น en ชั่วคราว
    แต่ถ้าผู้ใช้ตั้งค่าไว้แล้ว ใช้ค่านั้น"""
    if user_id in _user_lang:
        return _user_lang[user_id]
    thai_chars = sum(1 for c in text if "฀" <= c <= "๿")
    return "en" if thai_chars == 0 and len(text) > 1 else "th"


T: dict[str, dict[str, str]] = {
    # ── Conversation prompts ──────────────────────────────────────────────
    "ask_amount": {
        "th": "💰 กรอกจำนวนเงิน (บาท):\nเช่น  150  หรือ  1,250.50",
        "en": "💰 Enter amount (THB):\ne.g.  150  or  1,250.50",
    },
    "ask_category": {
        "th": "📂 เลือกหมวดหมู่:",
        "en": "📂 Select category:",
    },
    "ask_task": {
        "th": "📋 พิมพ์ชื่องาน / Task ที่ต้องการบันทึก:",
        "en": "📋 Enter task name:",
    },
    "ask_status": {
        "th": "🔖 เลือกสถานะ:",
        "en": "🔖 Select status:",
    },
    "ask_note": {
        "th": "📝 เพิ่มหมายเหตุ (กด ข้าม หรือพิมพ์ได้เลย):",
        "en": "📝 Add note (tap Skip or type):",
    },
    "skip": {
        "th": "ข้าม",
        "en": "Skip",
    },
    # ── Confirmations ─────────────────────────────────────────────────────
    "confirm_expense_header": {
        "th": "✅ บันทึกรายจ่ายสำเร็จ",
        "en": "✅ Expense Saved",
    },
    "confirm_work_header": {
        "th": "✅ บันทึกงานสำเร็จ",
        "en": "✅ Task Saved",
    },
    "label_amount":   {"th": "💰 จำนวน",   "en": "💰 Amount"},
    "label_category": {"th": "📂 หมวดหมู่", "en": "📂 Category"},
    "label_note":     {"th": "📝 หมายเหตุ", "en": "📝 Note"},
    "label_task":     {"th": "📋 งาน",      "en": "📋 Task"},
    "label_status":   {"th": "🔖 สถานะ",    "en": "🔖 Status"},
    "alt_expense":    {"th": "บันทึกรายจ่าย {amount} บาท", "en": "Expense saved {amount} THB"},
    "alt_task":       {"th": "บันทึกงาน: {task}", "en": "Task saved: {task}"},
    # ── Summary ───────────────────────────────────────────────────────────
    "summary_header": {"th": "📊 สรุปรายจ่าย",   "en": "📊 Expense Summary"},
    "summary_today":  {"th": "วันนี้",             "en": "Today"},
    "summary_total":  {"th": "ทั้งหมด ({n} รายการ)", "en": "Total ({n} items)"},
    # ── Lists ─────────────────────────────────────────────────────────────
    "recent_expense_header": {"th": "💰 รายจ่ายล่าสุด", "en": "💰 Recent Expenses"},
    "recent_work_header":    {"th": "📋 งานล่าสุด",      "en": "📋 Recent Tasks"},
    "no_records": {"th": "ยังไม่มีรายการ", "en": "No records yet"},
    # ── System ────────────────────────────────────────────────────────────
    "cancelled": {
        "th": "❌ ยกเลิกแล้ว กลับสู่เมนูหลัก",
        "en": "❌ Cancelled. Back to main menu.",
    },
    "unknown": {
        "th": "ไม่เข้าใจคำสั่ง เลือกจากเมนูด้านล่างได้เลย",
        "en": "Command not recognised. Use the menu below.",
    },
    "greeting": {
        "th": "สวัสดี {name}! 👋\nไม่เข้าใจคำสั่งนี้ เลือกเมนูด้านล่างได้เลย",
        "en": "Hello {name}! 👋\nCommand not recognised. Use the menu below.",
    },
    "menu_prompt": {
        "th": "เลือกเมนูที่ต้องการ 👇",
        "en": "Choose an option 👇",
    },
    "help_text": {
        "th": (
            "📌 เมนูคำสั่ง\n\n"
            "💰 บันทึกรายจ่าย\n  พิมพ์  จ่าย  หรือ  จ่าย 150\n\n"
            "📋 บันทึกงาน\n  พิมพ์  งาน  หรือ  งาน ชื่องาน\n\n"
            "📊 ดูข้อมูล\n  รายจ่ายล่าสุด / งานล่าสุด / สรุปรายจ่าย\n\n"
            "🌐 เปลี่ยนภาษา: พิมพ์  english  หรือ  thai\n"
            "❌ ยกเลิก — ออกจาก flow ปัจจุบัน"
        ),
        "en": (
            "📌 Commands\n\n"
            "💰 Record Expense\n  Type  expense  or  expense 150\n\n"
            "📋 Record Task\n  Type  task  or  task name\n\n"
            "📊 View Data\n  latest expense / latest task / summary\n\n"
            "🌐 Change language: type  thai  or  english\n"
            "❌ cancel — exit current flow"
        ),
    },
    # ── Categories & Statuses (bilingual values) ──────────────────────────
    "categories": {
        "th": ["อาหาร/เครื่องดื่ม", "เดินทาง", "ช้อปปิ้ง", "สุขภาพ",
               "ที่พัก", "ความบันเทิง", "การศึกษา", "อื่นๆ"],
        "en": ["Food/Drinks", "Transport", "Shopping", "Health",
               "Accommodation", "Entertainment", "Education", "Other"],
    },
    "statuses": {
        "th": ["กำลังทำ", "เสร็จแล้ว", "รอดำเนินการ", "ยกเลิก"],
        "en": ["In Progress", "Done", "Pending", "Cancelled"],
    },
}


def t(key: str, lang: str, **kwargs) -> str:
    text = T.get(key, {}).get(lang) or T.get(key, {}).get("th") or key
    return text.format(**kwargs) if kwargs else text


def categories(lang: str) -> list[str]:
    return T["categories"][lang]


def statuses(lang: str) -> list[str]:
    return T["statuses"][lang]
