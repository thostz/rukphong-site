"""Route incoming LINE text messages → list[Message]."""

import os
import re
from linebot.v3.messaging import TextMessage

from handlers.conversation import (
    EXPENSE_DONE, WORK_DONE,
    SHOW_CATEGORY_QR, SHOW_STATUS_QR, SHOW_NOTE_QR,
    clear_session, get_session, handle_step, start_expense, start_work,
)
from handlers.lang import detect_and_set, get_lang, set_lang, t
import handlers.line_messages as lm
from services import sheets_service as sheets

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")

# ── คำสั่ง "ล่าสุด / latest" ต้องเช็คก่อน startswith ─────────────────────────
RECENT_EXPENSE_CMDS = {"รายจ่ายล่าสุด", "latest expense", "recent expense"}
RECENT_WORK_CMDS    = {"งานล่าสุด", "latest task", "recent task", "latest work"}
SUMMARY_CMDS        = {"สรุปรายจ่าย", "summary", "สรุป"}
CANCEL_CMDS         = {"ยกเลิก", "cancel", "ออก", "exit"}
HELP_CMDS           = {"help", "ช่วยเหลือ", "เมนู", "menu", "?", "/?"}
MYID_CMDS           = {"myid", "my id", "userid", "user id"}
EXPENSE_PREFIXES    = ("จ่าย", "expense", "ค่าใช้จ่าย")
WORK_PREFIXES       = ("งาน", "task", "work")


def _is_menu_command(lower: str) -> bool:
    return (
        lower in CANCEL_CMDS | HELP_CMDS | RECENT_EXPENSE_CMDS |
        RECENT_WORK_CMDS | SUMMARY_CMDS | {"english", "thai", "ภาษาอังกฤษ", "ภาษาไทย"}
        or any(lower.startswith(p + " ") or lower == p for p in EXPENSE_PREFIXES)
        or any(lower.startswith(p + " ") or lower == p for p in WORK_PREFIXES)
    )


def handle_text(user_id: str, display_name: str, text: str) -> list:
    text  = text.strip()
    lower = text.lower()

    # ── ตรวจภาษาจากข้อความ (ถ้าผู้ใช้ยังไม่ได้ตั้งค่า) ──────────────────────
    lang = detect_and_set(user_id, text)

    # ── สลับภาษา ──────────────────────────────────────────────────────────────
    if lower in ("english", "ภาษาอังกฤษ"):
        set_lang(user_id, "en")
        return [lm.main_menu("🌐 Switched to English 🇬🇧", lang="en")]
    if lower in ("thai", "ภาษาไทย"):
        set_lang(user_id, "th")
        return [lm.main_menu("🌐 เปลี่ยนเป็นภาษาไทย 🇹🇭", lang="th")]

    lang = get_lang(user_id)

    # ── ยกเลิก ────────────────────────────────────────────────────────────────
    if lower in CANCEL_CMDS:
        clear_session(user_id)
        return [lm.main_menu(t("cancelled", lang), lang)]

    # ── อยู่ใน conversation flow ───────────────────────────────────────────────
    if get_session(user_id):
        if _is_menu_command(lower):
            clear_session(user_id)      # กด Rich Menu ใหม่ → ล้าง flow เก่า
        else:
            return _process_step(user_id, display_name, text, lang)

    # ── ดู User ID ────────────────────────────────────────────────────────────
    if lower in MYID_CMDS:
        return [TextMessage(text=f"LINE User ID ของคุณ:\n{user_id}")]

    # ── ช่วยเหลือ ──────────────────────────────────────────────────────────────
    if lower in HELP_CMDS:
        return [lm.main_menu(t("help_text", lang), lang)]

    # ── "ล่าสุด" ต้องเช็คก่อน prefix งาน/จ่าย ──────────────────────────────
    if lower in RECENT_EXPENSE_CMDS:
        return [_recent_expenses(lang)]

    if lower in RECENT_WORK_CMDS:
        return [_recent_works(lang)]

    if lower in SUMMARY_CMDS:
        return [_expense_summary(lang)]

    # ── เริ่มบันทึกรายจ่าย ────────────────────────────────────────────────────
    if any(lower.startswith(p) for p in EXPENSE_PREFIXES):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            try:
                amount = float(parts[1].replace(",", ""))
                return _marker_msgs(start_expense(user_id, amount), None, display_name, lang)
            except ValueError:
                pass
        return _marker_msgs(start_expense(user_id), None, display_name, lang)

    # ── เริ่มบันทึกงาน ────────────────────────────────────────────────────────
    if any(lower.startswith(p) for p in WORK_PREFIXES):
        parts = text.split(maxsplit=1)
        task = parts[1].strip() if len(parts) > 1 else None
        return _marker_msgs(start_work(user_id, task), None, display_name, lang)

    # ── ตัวเลขเปล่า → รายจ่าย ─────────────────────────────────────────────────
    if re.fullmatch(r"[\d,]+(\.\d{1,2})?", text):
        try:
            amount = float(text.replace(",", ""))
            return _marker_msgs(start_expense(user_id, amount), None, display_name, lang)
        except ValueError:
            pass

    return [lm.main_menu(t("greeting", lang, name=display_name), lang)]


# ── Internals ──────────────────────────────────────────────────────────────────

def _process_step(user_id, display_name, text, lang) -> list:
    marker, data = handle_step(user_id, text)
    return _marker_msgs(marker, data, display_name, lang)


def _marker_msgs(marker: str, data: dict | None, display_name: str, lang: str) -> list:
    if marker == "__ASK_AMOUNT__":   return [lm.ask_amount(lang)]
    if marker == "__ASK_TASK__":     return [lm.ask_task(lang)]
    if marker == SHOW_CATEGORY_QR:   return [lm.ask_category(lang)]
    if marker == SHOW_STATUS_QR:     return [lm.ask_status(lang)]
    if marker == SHOW_NOTE_QR:       return [lm.ask_note(lang)]
    if marker == EXPENSE_DONE and data:
        _save(data, display_name)
        return [lm.confirm_expense(data["amount"], data["category"], data["note"], lang)]
    if marker == WORK_DONE and data:
        _save(data, display_name)
        return [lm.confirm_work(data["task"], data["status"], data["note"], lang)]
    if marker:
        return [TextMessage(text=marker)]
    return [lm.main_menu(t("unknown", lang), lang)]


def _save(data: dict, display_name: str):
    if not SPREADSHEET_ID:
        return
    try:
        if data["type"] == "expense":
            sheets.append_expense(SPREADSHEET_ID, data["amount"],
                                  data["category"], data["note"], display_name)
        elif data["type"] == "work":
            sheets.append_work(SPREADSHEET_ID, data["task"],
                               data["status"], data["note"], display_name)
    except Exception as e:
        print(f"[Sheets Error] {e}")


def _recent_expenses(lang: str) -> object:
    if not SPREADSHEET_ID:
        return TextMessage(text="⚠️ Google Sheets not configured")
    try:
        return lm.recent_expenses(sheets.get_recent_expenses(SPREADSHEET_ID), lang)
    except Exception as e:
        return TextMessage(text=f"❌ Error: {e}")


def _recent_works(lang: str) -> object:
    if not SPREADSHEET_ID:
        return TextMessage(text="⚠️ Google Sheets not configured")
    try:
        return lm.recent_works(sheets.get_recent_works(SPREADSHEET_ID), lang)
    except Exception as e:
        return TextMessage(text=f"❌ Error: {e}")


def _expense_summary(lang: str) -> object:
    if not SPREADSHEET_ID:
        return TextMessage(text="⚠️ Google Sheets not configured")
    try:
        return lm.expense_summary(sheets.get_expense_summary(SPREADSHEET_ID), lang)
    except Exception as e:
        return TextMessage(text=f"❌ Error: {e}")
