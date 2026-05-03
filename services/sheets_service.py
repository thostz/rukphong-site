import os
import json
import base64
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = "credentials.json"

EXPENSE_SHEET    = "รายจ่าย"
WORK_SHEET       = "งาน"
NOTES_SHEET      = "บันทึก"
INVESTMENT_SHEET = "การลงทุน"
DIVIDEND_SHEET   = "เงินปันผล"

EXPENSE_HEADERS    = ["วันที่", "จำนวนเงิน (บาท)", "หมวดหมู่", "หมายเหตุ", "บันทึกโดย", "วิธีชำระเงิน"]
WORK_HEADERS       = ["วันที่", "งาน/Task", "สถานะ", "หมายเหตุ", "บันทึกโดย", "Client/Project", "Priority", "วันครบกำหนด", "รายละเอียด"]
NOTES_HEADERS      = ["ID", "วันที่", "หัวข้อ", "เนื้อหา", "หมวดหมู่"]
INVESTMENT_HEADERS = ["ID", "Portfolio", "ประเภท", "Symbol", "ชื่อ", "จำนวน", "ราคาทุน", "ราคาตลาด", "หมายเหตุ", "วันที่"]
DIVIDEND_HEADERS   = ["ID", "Portfolio", "วันที่", "จำนวนเงิน", "Symbol", "ประเภท", "หมายเหตุ"]

EXPENSE_CATEGORIES = {
    "1": "อาหาร/เครื่องดื่ม",
    "2": "เดินทาง",
    "3": "ช้อปปิ้ง",
    "4": "สุขภาพ",
    "5": "ที่พัก",
    "6": "ความบันเทิง",
    "7": "การศึกษา",
    "8": "อื่นๆ",
}

WORK_STATUSES = {
    "1": "กำลังทำ",
    "2": "เสร็จแล้ว",
    "3": "รอดำเนินการ",
    "4": "ยกเลิก",
}


def _get_service():
    # Cloud deployment: credentials stored as base64 env var
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64", "")
    if creds_b64:
        info = json.loads(base64.b64decode(creds_b64).decode())
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
    return build("sheets", "v4", credentials=creds)


def _ensure_sheet_exists(service, spreadsheet_id: str, sheet_name: str, headers: list):
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["title"] for s in meta["sheets"]]

    if sheet_name not in existing:
        body = {
            "requests": [
                {"addSheet": {"properties": {"title": sheet_name}}}
            ]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body=body
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


def init_sheets(spreadsheet_id: str):
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, EXPENSE_SHEET, EXPENSE_HEADERS)
    _ensure_sheet_exists(service, spreadsheet_id, WORK_SHEET, WORK_HEADERS)


def append_expense(
    spreadsheet_id: str,
    amount: float,
    category: str,
    note: str,
    user_name: str,
) -> bool:
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, EXPENSE_SHEET, EXPENSE_HEADERS)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    row = [now, amount, category, note, user_name]
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{EXPENSE_SHEET}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    return True


def append_work(
    spreadsheet_id: str,
    task: str,
    status: str,
    note: str,
    user_name: str,
) -> bool:
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, WORK_SHEET, WORK_HEADERS)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    row = [now, task, status, note, user_name]
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{WORK_SHEET}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    return True


def append_expense_web(
    spreadsheet_id: str,
    date: str,
    amount: float,
    category: str,
    payment: str,
    note: str,
    user_name: str,
) -> bool:
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, EXPENSE_SHEET, EXPENSE_HEADERS)
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    row = [date, amount, category, note, user_name, payment]
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{EXPENSE_SHEET}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    return True


def append_work_web(
    spreadsheet_id: str,
    date: str,
    task: str,
    client: str,
    status: str,
    priority: str,
    due_date: str,
    description: str,
    note: str,
    user_name: str,
) -> bool:
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, WORK_SHEET, WORK_HEADERS)
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    row = [date, task, status, note, user_name, client, priority, due_date, description]
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{WORK_SHEET}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    return True


def get_recent_expenses(spreadsheet_id: str, limit: int = 5) -> list[dict]:
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{EXPENSE_SHEET}!A2:E")
        .execute()
    )
    rows = result.get("values", [])
    recent = rows[-limit:] if len(rows) > limit else rows
    return [
        {
            "date": r[0] if len(r) > 0 else "",
            "amount": r[1] if len(r) > 1 else "",
            "category": r[2] if len(r) > 2 else "",
            "note": r[3] if len(r) > 3 else "",
        }
        for r in reversed(recent)
    ]


def get_recent_works(spreadsheet_id: str, limit: int = 5) -> list[dict]:
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{WORK_SHEET}!A2:E")
        .execute()
    )
    rows = result.get("values", [])
    recent = rows[-limit:] if len(rows) > limit else rows
    return [
        {
            "date": r[0] if len(r) > 0 else "",
            "task": r[1] if len(r) > 1 else "",
            "status": r[2] if len(r) > 2 else "",
            "note": r[3] if len(r) > 3 else "",
        }
        for r in reversed(recent)
    ]


def get_expense_summary(spreadsheet_id: str) -> dict:
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{EXPENSE_SHEET}!A2:E")
        .execute()
    )
    rows = result.get("values", [])
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0.0
    today_total = 0.0
    by_category: dict[str, float] = {}

    for r in rows:
        try:
            amount = float(r[1]) if len(r) > 1 else 0
            category = r[2] if len(r) > 2 else "อื่นๆ"
            date = r[0][:10] if len(r) > 0 else ""
            total += amount
            by_category[category] = by_category.get(category, 0) + amount
            if date == today:
                today_total += amount
        except (ValueError, IndexError):
            continue

    return {
        "total": total,
        "today_total": today_total,
        "by_category": by_category,
        "count": len(rows),
    }


# ── NOTES ─────────────────────────────────────────────────────────────────────

def sync_note(spreadsheet_id: str, record: dict):
    """Upsert a note row identified by its ID in column A."""
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, NOTES_SHEET, NOTES_HEADERS)
    rid = str(record.get("id", ""))
    date = record.get("date", datetime.now().strftime("%Y-%m-%d"))
    row = [rid, date, record.get("title", ""), record.get("content", ""), record.get("category", "")]

    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{NOTES_SHEET}!A:A"
    ).execute()
    ids = [r[0] if r else "" for r in result.get("values", [])]
    if rid in ids:
        row_num = ids.index(rid) + 1
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{NOTES_SHEET}!A{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
    else:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=f"{NOTES_SHEET}!A1",
            valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()


def delete_note_sheet(spreadsheet_id: str, rid: str):
    service = _get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{NOTES_SHEET}!A:A"
    ).execute()
    ids = [r[0] if r else "" for r in result.get("values", [])]
    if rid not in ids:
        return
    row_num = ids.index(rid) + 1
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = next(s["properties"]["sheetId"] for s in meta["sheets"]
                    if s["properties"]["title"] == NOTES_SHEET)
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": [{
        "deleteDimension": {"range": {"sheetId": sheet_id, "dimension": "ROWS",
                                      "startIndex": row_num - 1, "endIndex": row_num}}
    }]}).execute()


def get_all_notes(spreadsheet_id: str) -> list:
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, NOTES_SHEET, NOTES_HEADERS)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{NOTES_SHEET}!A2:E"
    ).execute()
    rows = result.get("values", [])
    return [{"id": r[0] if len(r) > 0 else "", "date": r[1] if len(r) > 1 else "",
             "title": r[2] if len(r) > 2 else "", "content": r[3] if len(r) > 3 else "",
             "category": r[4] if len(r) > 4 else ""} for r in rows if r]


# ── INVESTMENT ────────────────────────────────────────────────────────────────

def sync_investment(spreadsheet_id: str, record: dict, portfolio_name: str = ""):
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, INVESTMENT_SHEET, INVESTMENT_HEADERS)
    rid = str(record.get("id", ""))
    row = [rid, portfolio_name, record.get("type", ""), record.get("symbol", ""),
           record.get("name", ""), record.get("qty", 0), record.get("cost", 0),
           record.get("price", 0), record.get("note", ""),
           datetime.now().strftime("%Y-%m-%d")]

    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{INVESTMENT_SHEET}!A:A"
    ).execute()
    ids = [r[0] if r else "" for r in result.get("values", [])]
    if rid in ids:
        row_num = ids.index(rid) + 1
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{INVESTMENT_SHEET}!A{row_num}",
            valueInputOption="USER_ENTERED", body={"values": [row]},
        ).execute()
    else:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=f"{INVESTMENT_SHEET}!A1",
            valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()


def delete_investment_sheet(spreadsheet_id: str, rid: str):
    service = _get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{INVESTMENT_SHEET}!A:A"
    ).execute()
    ids = [r[0] if r else "" for r in result.get("values", [])]
    if rid not in ids:
        return
    row_num = ids.index(rid) + 1
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = next(s["properties"]["sheetId"] for s in meta["sheets"]
                    if s["properties"]["title"] == INVESTMENT_SHEET)
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": [{
        "deleteDimension": {"range": {"sheetId": sheet_id, "dimension": "ROWS",
                                      "startIndex": row_num - 1, "endIndex": row_num}}
    }]}).execute()


def sync_dividend(spreadsheet_id: str, record: dict, portfolio_name: str = ""):
    service = _get_service()
    _ensure_sheet_exists(service, spreadsheet_id, DIVIDEND_SHEET, DIVIDEND_HEADERS)
    rid = str(record.get("id", ""))
    row = [rid, portfolio_name, record.get("date", ""), record.get("amount", 0),
           record.get("symbol", ""), record.get("type", ""), record.get("note", "")]
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range=f"{DIVIDEND_SHEET}!A1",
        valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
