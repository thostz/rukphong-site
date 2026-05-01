"""
Sync tasks from source sheet (Tasks tab) to the bot's work sheet.
Run: .venv/Scripts/python sync_tasks.py
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")

SOURCE_ID  = "1mlOJfn4I66ZuMPad1VkYBmMlKU62rtzakpuhHurUcJc"
SOURCE_TAB = "Tasks"

DEST_ID  = os.getenv("SPREADSHEET_ID", "")
DEST_TAB = "งาน"

WORK_HEADERS = ["วันที่", "งาน/Task", "สถานะ", "หมายเหตุ", "บันทึกโดย"]

STATUS_MAP = {
    "inprogress":  "กำลังทำ",
    "in progress": "กำลังทำ",
    "done":        "เสร็จแล้ว",
    "pending":     "รอดำเนินการ",
    "cancelled":   "ยกเลิก",
    "canceled":    "ยกเลิก",
}


def _fmt_date(raw: str) -> str:
    if not raw:
        return datetime.now().strftime("%Y-%m-%d")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw.strip()


def _get_service():
    creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def main():
    if not DEST_ID:
        sys.exit("ERROR: SPREADSHEET_ID not set in .env")

    service = _get_service()
    sheets  = service.spreadsheets()

    # ── Read source header + data ────────────────────────────────────────────
    result = sheets.values().get(
        spreadsheetId=SOURCE_ID, range=f"{SOURCE_TAB}!A1:Z"
    ).execute()
    all_rows = result.get("values", [])
    if not all_rows:
        sys.exit("No data found in source sheet")

    headers = [h.strip().lower() for h in all_rows[0]]
    print(f"Source columns: {headers}")

    def col(row, name):
        try:
            idx = headers.index(name)
            return row[idx].strip() if idx < len(row) else ""
        except ValueError:
            return ""

    new_rows = []
    for raw in all_rows[1:]:
        task_id = col(raw, "id")
        if not task_id:
            continue

        title      = col(raw, "title")
        client     = col(raw, "client")
        desc       = col(raw, "description")
        notes      = col(raw, "notes")
        owner      = col(raw, "owner")
        status_raw = col(raw, "status").lower()
        start_date = _fmt_date(col(raw, "startdate") or col(raw, "startDate") or col(raw, "start_date"))

        task_label = f"{title} [{client}]" if client else title
        status = STATUS_MAP.get(status_raw, "กำลังทำ")
        note_parts = [p for p in [desc, notes] if p]
        note = " | ".join(note_parts)

        new_rows.append([start_date, task_label, status, note, owner])

    print(f"Valid tasks to import: {len(new_rows)}")
    if not new_rows:
        print("Nothing to write.")
        return

    # ── Ensure "งาน" sheet exists with headers ───────────────────────────────
    meta = sheets.get(spreadsheetId=DEST_ID).execute()
    existing_tabs = [s["properties"]["title"] for s in meta["sheets"]]

    if DEST_TAB not in existing_tabs:
        sheets.batchUpdate(spreadsheetId=DEST_ID, body={
            "requests": [{"addSheet": {"properties": {"title": DEST_TAB}}}]
        }).execute()
        sheets.values().update(
            spreadsheetId=DEST_ID, range=f"{DEST_TAB}!A1",
            valueInputOption="RAW", body={"values": [WORK_HEADERS]}
        ).execute()
        print(f"Created sheet '{DEST_TAB}' with headers")
    else:
        # Make sure row 1 has headers (safe to overwrite)
        sheets.values().update(
            spreadsheetId=DEST_ID, range=f"{DEST_TAB}!A1",
            valueInputOption="RAW", body={"values": [WORK_HEADERS]}
        ).execute()

    # ── Append rows ──────────────────────────────────────────────────────────
    sheets.values().append(
        spreadsheetId=DEST_ID,
        range=f"{DEST_TAB}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": new_rows},
    ).execute()

    print(f"[OK] Imported {len(new_rows)} tasks into '{DEST_TAB}' sheet")


if __name__ == "__main__":
    main()
