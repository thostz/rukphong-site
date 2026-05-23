"""Google Sheets ↔ SQLite sync service.

Sheet layout (all tabs have ID as column A — matches SQLite primary key):

  รายจ่าย  : ID | วันที่ | จำนวนเงิน | สกุลเงิน | หมวดหมู่ | หมายเหตุ | created_at
  งาน      : ID | หัวข้อ | Priority | Status | วันครบกำหนด | หมายเหตุ | created_at | updated_at
  บันทึก   : ID | วันที่ | หัวข้อ | เนื้อหา | หมวดหมู่
  การลงทุน : ID | Portfolio | ประเภท | Symbol | ชื่อ | จำนวน | ราคาทุน | ราคาตลาด | หมายเหตุ | วันที่
  เงินปันผล: ID | Portfolio | วันที่ | จำนวนเงิน | Symbol | ประเภท | หมายเหตุ
"""

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

EXPENSE_HEADERS    = ["ID", "วันที่", "จำนวนเงิน", "สกุลเงิน", "หมวดหมู่", "หมายเหตุ", "created_at"]
WORK_HEADERS       = ["ID", "หัวข้อ", "Priority", "Status", "วันครบกำหนด", "หมายเหตุ", "created_at", "updated_at"]
NOTES_HEADERS      = ["ID", "วันที่", "หัวข้อ", "เนื้อหา", "หมวดหมู่"]
INVESTMENT_HEADERS = ["ID", "Portfolio", "ประเภท", "Symbol", "ชื่อ", "จำนวน", "ราคาทุน", "ราคาตลาด", "หมายเหตุ", "วันที่"]
DIVIDEND_HEADERS   = ["ID", "Portfolio", "วันที่", "จำนวนเงิน", "Symbol", "ประเภท", "หมายเหตุ"]


def _get_service():
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64", "")
    if creds_b64:
        info = json.loads(base64.b64decode(creds_b64).decode())
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
    return build("sheets", "v4", credentials=creds)


def _ensure_sheet(service, spreadsheet_id: str, sheet_name: str, headers: list):
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["title"] for s in meta["sheets"]]
    if sheet_name not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


def _get_id_index(service, spreadsheet_id: str, sheet_name: str) -> dict:
    """Return {id_str: row_number} for column A (1-based, skipping header row 1)."""
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A:A"
    ).execute()
    rows = result.get("values", [])
    return {rows[i][0]: i + 1 for i in range(1, len(rows)) if rows[i]}


def _get_sheet_id(service, spreadsheet_id: str, sheet_name: str) -> int:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return next(s["properties"]["sheetId"] for s in meta["sheets"]
                if s["properties"]["title"] == sheet_name)


def _upsert_row(service, spreadsheet_id: str, sheet_name: str, headers: list, rid: str, row: list):
    """Insert or update a row identified by rid in column A."""
    _ensure_sheet(service, spreadsheet_id, sheet_name, headers)
    idx = _get_id_index(service, spreadsheet_id, sheet_name)
    if rid in idx:
        row_num = idx[rid]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
    else:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()


def _delete_row(service, spreadsheet_id: str, sheet_name: str, rid: str):
    """Delete a row by ID in column A."""
    idx = _get_id_index(service, spreadsheet_id, sheet_name)
    if rid not in idx:
        return
    row_num = idx[rid]
    sheet_id = _get_sheet_id(service, spreadsheet_id, sheet_name)
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": [{
        "deleteDimension": {"range": {
            "sheetId": sheet_id, "dimension": "ROWS",
            "startIndex": row_num - 1, "endIndex": row_num
        }}
    }]}).execute()


def init_sheets(spreadsheet_id: str):
    service = _get_service()
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"] for s in meta["sheets"]}
    for name, headers in [
        (EXPENSE_SHEET,    EXPENSE_HEADERS),
        (WORK_SHEET,       WORK_HEADERS),
        (NOTES_SHEET,      NOTES_HEADERS),
        (INVESTMENT_SHEET, INVESTMENT_HEADERS),
        (DIVIDEND_SHEET,   DIVIDEND_HEADERS),
    ]:
        if name not in existing:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": name}}}]}
            ).execute()
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{name}!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()


# ── PUSH: SQLite → Sheets ──────────────────────────────────────────────────────

def sync_expense(spreadsheet_id: str, record: dict):
    service = _get_service()
    rid = str(record.get("id", ""))
    row = [rid, record.get("date", ""), record.get("amount", 0),
           record.get("currency", "THB"), record.get("category", ""),
           record.get("notes", ""), record.get("created_at", "")]
    _upsert_row(service, spreadsheet_id, EXPENSE_SHEET, EXPENSE_HEADERS, rid, row)

def delete_expense_sheet(spreadsheet_id: str, rid: str):
    service = _get_service()
    _delete_row(service, spreadsheet_id, EXPENSE_SHEET, rid)


def sync_task(spreadsheet_id: str, record: dict):
    service = _get_service()
    rid = str(record.get("id", ""))
    row = [rid, record.get("title", ""), record.get("priority", ""),
           record.get("status", ""), record.get("due", ""),
           record.get("notes", ""), record.get("created_at", ""), record.get("updated_at", "")]
    _upsert_row(service, spreadsheet_id, WORK_SHEET, WORK_HEADERS, rid, row)

def delete_task_sheet(spreadsheet_id: str, rid: str):
    service = _get_service()
    _delete_row(service, spreadsheet_id, WORK_SHEET, rid)


def sync_note(spreadsheet_id: str, record: dict):
    service = _get_service()
    rid = str(record.get("id", ""))
    row = [rid, record.get("date", ""), record.get("title", ""),
           record.get("content", ""), record.get("category", "")]
    _upsert_row(service, spreadsheet_id, NOTES_SHEET, NOTES_HEADERS, rid, row)

def delete_note_sheet(spreadsheet_id: str, rid: str):
    service = _get_service()
    _delete_row(service, spreadsheet_id, NOTES_SHEET, rid)


def sync_investment(spreadsheet_id: str, record: dict, portfolio_name: str = ""):
    service = _get_service()
    rid = str(record.get("id", ""))
    row = [rid, portfolio_name, record.get("type", ""), record.get("symbol", ""),
           record.get("name", ""), record.get("qty", 0), record.get("cost", 0),
           record.get("price", 0), record.get("note", ""),
           datetime.now().strftime("%Y-%m-%d")]
    _upsert_row(service, spreadsheet_id, INVESTMENT_SHEET, INVESTMENT_HEADERS, rid, row)

def delete_investment_sheet(spreadsheet_id: str, rid: str):
    service = _get_service()
    _delete_row(service, spreadsheet_id, INVESTMENT_SHEET, rid)


def sync_dividend(spreadsheet_id: str, record: dict, portfolio_name: str = ""):
    service = _get_service()
    rid = str(record.get("id", ""))
    row = [rid, portfolio_name, record.get("date", ""), record.get("amount", 0),
           record.get("symbol", ""), record.get("type", ""), record.get("note", "")]
    _upsert_row(service, spreadsheet_id, DIVIDEND_SHEET, DIVIDEND_HEADERS, rid, row)

def delete_dividend_sheet(spreadsheet_id: str, rid: str):
    service = _get_service()
    _delete_row(service, spreadsheet_id, DIVIDEND_SHEET, rid)


def push_all(spreadsheet_id: str, data_svc) -> dict:
    """Full push: dump all SQLite records to Sheets."""
    counts = {}
    for rec in data_svc.get_expenses():
        sync_expense(spreadsheet_id, rec)
    counts["expenses"] = len(data_svc.get_expenses())

    for rec in data_svc.get_notes():
        sync_note(spreadsheet_id, rec)
    counts["notes"] = len(data_svc.get_notes())

    for rec in data_svc.get_tasks():
        sync_task(spreadsheet_id, rec)
    counts["tasks"] = len(data_svc.get_tasks())

    for portfolio in data_svc.get_portfolios():
        pid = portfolio["id"]
        pname = portfolio["name"]
        for rec in data_svc.get_investments(pid):
            sync_investment(spreadsheet_id, rec, pname)
        for rec in data_svc.get_dividends(pid):
            sync_dividend(spreadsheet_id, rec, pname)
    counts["portfolios"] = len(data_svc.get_portfolios())

    return counts


# ── PULL: Sheets → SQLite ──────────────────────────────────────────────────────

def _read_sheet(service, spreadsheet_id: str, sheet_name: str, headers: list) -> list[dict]:
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A2:{chr(64 + len(headers))}"
        ).execute()
    except Exception:
        return []
    rows = result.get("values", [])
    keys = headers
    out = []
    for r in rows:
        if not r or not r[0]:
            continue
        padded = r + [""] * (len(keys) - len(r))
        out.append(dict(zip(keys, padded)))
    return out


def pull_all(spreadsheet_id: str, data_svc) -> dict:
    """Pull all Sheets data → upsert into SQLite. SQLite wins on conflict (skip if ID exists)."""
    service = _get_service()
    counts = {}

    # Expenses
    rows = _read_sheet(service, spreadsheet_id, EXPENSE_SHEET, EXPENSE_HEADERS)
    existing_ids = {r["id"] for r in data_svc.get_expenses()}
    new = 0
    for r in rows:
        rid = r.get("ID", "")
        if not rid or rid in existing_ids:
            continue
        data_svc.save_expense({
            "id": rid, "date": r.get("วันที่", ""),
            "amount": r.get("จำนวนเงิน", 0), "currency": r.get("สกุลเงิน", "THB"),
            "category": r.get("หมวดหมู่", ""), "notes": r.get("หมายเหตุ", ""),
        })
        new += 1
    counts["expenses"] = new

    # Tasks
    rows = _read_sheet(service, spreadsheet_id, WORK_SHEET, WORK_HEADERS)
    existing_ids = {r["id"] for r in data_svc.get_tasks()}
    new = 0
    for r in rows:
        rid = r.get("ID", "")
        if not rid or rid in existing_ids:
            continue
        data_svc.save_task({
            "id": rid, "title": r.get("หัวข้อ", ""),
            "priority": r.get("Priority", "medium"), "status": r.get("Status", "todo"),
            "due": r.get("วันครบกำหนด", ""), "notes": r.get("หมายเหตุ", ""),
        })
        new += 1
    counts["tasks"] = new

    # Notes
    rows = _read_sheet(service, spreadsheet_id, NOTES_SHEET, NOTES_HEADERS)
    existing_ids = {r["id"] for r in data_svc.get_notes()}
    new = 0
    for r in rows:
        rid = r.get("ID", "")
        if not rid or rid in existing_ids:
            continue
        data_svc.save_note({
            "id": rid, "date": r.get("วันที่", ""),
            "title": r.get("หัวข้อ", ""), "content": r.get("เนื้อหา", ""),
            "category": r.get("หมวดหมู่", ""),
        })
        new += 1
    counts["notes"] = new

    return counts


# ── LEGACY helpers (kept for backward compat) ─────────────────────────────────

def append_expense_web(spreadsheet_id, date, amount, category, payment, note, user_name):
    sync_expense(spreadsheet_id, {
        "id": str(int(datetime.now().timestamp() * 1000)),
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "amount": amount, "currency": payment or "THB",
        "category": category, "notes": note,
    })

def append_expense(spreadsheet_id, amount, category, note, user_name):
    append_expense_web(spreadsheet_id, "", amount, category, "", note, user_name)

def append_work_web(spreadsheet_id, date, task, client, status, priority, due_date, description, note, user_name):
    sync_task(spreadsheet_id, {
        "id": str(int(datetime.now().timestamp() * 1000)),
        "title": task, "priority": priority or "medium",
        "status": status or "todo", "due": due_date or date,
        "notes": note,
    })

def append_work(spreadsheet_id, task, status, note, user_name):
    append_work_web(spreadsheet_id, "", task, "", status, "medium", "", "", note, user_name)

def get_recent_expenses(spreadsheet_id: str, limit: int = 5) -> list:
    service = _get_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{EXPENSE_SHEET}!A2:G"
        ).execute()
        rows = result.get("values", [])[-limit:]
        return [{"date": r[1] if len(r) > 1 else "", "amount": r[2] if len(r) > 2 else "",
                 "category": r[4] if len(r) > 4 else "", "note": r[5] if len(r) > 5 else ""}
                for r in reversed(rows)]
    except Exception:
        return []

def get_recent_works(spreadsheet_id: str, limit: int = 5) -> list:
    service = _get_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{WORK_SHEET}!A2:H"
        ).execute()
        rows = result.get("values", [])[-limit:]
        return [{"date": r[6] if len(r) > 6 else "", "task": r[1] if len(r) > 1 else "",
                 "status": r[3] if len(r) > 3 else "", "note": r[5] if len(r) > 5 else ""}
                for r in reversed(rows)]
    except Exception:
        return []

def get_expense_summary(spreadsheet_id: str) -> dict:
    service = _get_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{EXPENSE_SHEET}!A2:G"
        ).execute()
        rows = result.get("values", [])
    except Exception:
        return {"total": 0, "today_total": 0, "by_category": {}, "count": 0}
    today = datetime.now().strftime("%Y-%m-%d")
    total, today_total = 0.0, 0.0
    by_category: dict = {}
    for r in rows:
        try:
            amount   = float(r[2]) if len(r) > 2 else 0
            category = r[4] if len(r) > 4 else "อื่นๆ"
            date     = (r[1] if len(r) > 1 else "")[:10]
            total   += amount
            by_category[category] = by_category.get(category, 0) + amount
            if date == today:
                today_total += amount
        except (ValueError, IndexError):
            continue
    return {"total": total, "today_total": today_total,
            "by_category": by_category, "count": len(rows)}

def get_all_notes(spreadsheet_id: str) -> list:
    service = _get_service()
    _ensure_sheet(service, spreadsheet_id, NOTES_SHEET, NOTES_HEADERS)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{NOTES_SHEET}!A2:E"
    ).execute()
    rows = result.get("values", [])
    return [{"id": r[0] if len(r) > 0 else "", "date": r[1] if len(r) > 1 else "",
             "title": r[2] if len(r) > 2 else "", "content": r[3] if len(r) > 3 else "",
             "category": r[4] if len(r) > 4 else ""} for r in rows if r]
