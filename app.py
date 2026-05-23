import os
import json
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, abort, render_template, jsonify, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent

from handlers.message_handler import handle_text
from handlers import slip_handler
from services import sheets_service as sheets
from services import auth_service as auth
from services import data_service as data
from services import n8n_service as n8n
from services import line_push
from services import email_service as emailsvc

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "rp-consultant-secret-2026")

# init SQLite DB on startup
auth.init_db()
data.init_data_tables()

configuration = Configuration(
    access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
)
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def on_message(event: MessageEvent):
    user_id = event.source.user_id
    text = event.message.text

    with ApiClient(configuration) as api_client:
        line_api = MessagingApi(api_client)

        # ดึงชื่อผู้ใช้
        try:
            profile = line_api.get_profile(user_id)
            display_name = profile.display_name
        except Exception:
            display_name = "คุณ"

        messages = handle_text(user_id, display_name, text)

        line_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages,
            )
        )


@handler.add(MessageEvent, message=ImageMessageContent)
def on_image(event: MessageEvent):
    """Handle image messages — Slip OCR → auto-save expense."""
    user_id    = event.source.user_id
    message_id = event.message.id

    with ApiClient(configuration) as api_client:
        line_api = MessagingApi(api_client)
        reply_text = slip_handler.process(message_id, user_id)
        line_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


@app.route("/debug", methods=["GET"])
def debug_status():
    """Diagnostic endpoint — check env vars + test Gemini API."""
    import requests as _req, sys

    gemini_key  = os.getenv("GEMINI_API_KEY", "")
    line_token  = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_secret = os.getenv("LINE_CHANNEL_SECRET", "")
    gs_url      = os.getenv("GS_SCRIPT_URL", "")

    result = {
        "python_version": sys.version,
        "env": {
            "GEMINI_API_KEY":            "✅ set" if gemini_key  else "❌ NOT SET",
            "LINE_CHANNEL_ACCESS_TOKEN": "✅ set" if line_token  else "❌ NOT SET",
            "LINE_CHANNEL_SECRET":       "✅ set" if line_secret else "❌ NOT SET",
            "GS_SCRIPT_URL":             "✅ set" if gs_url      else "⚠️ not set (optional)",
        },
    }

    # Gemini key format check only (no API call — avoids wasting quota)
    if gemini_key:
        result["gemini_key_check"] = "✅ key present (39 chars)" if len(gemini_key) > 30 else f"⚠️ key looks short ({len(gemini_key)} chars)"
        result["gemini_model"] = "gemini-2.0-flash"
        result["gemini_note"] = "API not called here to preserve free-tier quota (15 RPM)"
    else:
        result["gemini_key_check"] = "❌ NOT SET"

    # Test LINE token (get bot info)
    if line_token:
        try:
            r = _req.get(
                "https://api.line.me/v2/bot/info",
                headers={"Authorization": f"Bearer {line_token}"},
                timeout=8,
            )
            if r.status_code == 200:
                info = r.json()
                result["line_bot_info"] = f"✅ Bot: {info.get('displayName','?')} | {info.get('basicId','?')}"
            else:
                result["line_bot_info"] = f"❌ HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            result["line_bot_info"] = f"❌ exception: {e}"
    else:
        result["line_bot_info"] = "⏭️ skipped (no token)"

    return jsonify(result)


@app.route("/theme-preview", methods=["GET"])
def theme_preview():
    return send_from_directory(".", "theme-preview.html")


@app.route("/rukphong", methods=["GET"])
def rukphong_profile():
    return send_from_directory("rukphong_site", "index.html")


@app.route("/investment", methods=["GET"])
def investment():
    return send_from_directory(".", "investment.html")


@app.route("/main", methods=["GET"])
def main_page():
    return send_from_directory(".", "main.html")


@app.route("/expense", methods=["GET"])
def expense():
    return send_from_directory(".", "expense.html")


@app.route("/notes", methods=["GET"])
def notes():
    return send_from_directory(".", "notes.html")


@app.route("/tasks", methods=["GET"])
def tasks():
    return send_from_directory(".", "tasks.html")


@app.route("/tracker", methods=["GET"])
def tracker():
    return render_template("tracker.html")


# ── Web UI ─────────────────────────────────────────────────────────────────────

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


@app.route("/help", methods=["GET"])
def help_page():
    return render_template("help.html")


@app.route("/sandbox", methods=["GET"])
def sandbox():
    return render_template("sandbox.html")


@app.route("/smart-import", methods=["GET"])
def smart_import_page():
    return render_template("smart-import.html")


@app.route("/api/expense", methods=["POST"])
def api_add_expense():
    if not SPREADSHEET_ID:
        return jsonify({"ok": False, "error": "Sheets not configured"}), 500
    d = request.json or {}
    try:
        sheets.append_expense_web(
            SPREADSHEET_ID,
            date=d.get("date", ""),
            amount=float(d.get("amount", 0)),
            category=d.get("category", ""),
            payment=d.get("payment", ""),
            note=d.get("note", ""),
            user_name=d.get("recorded_by", "Web"),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/task", methods=["POST"])
def api_add_task():
    if not SPREADSHEET_ID:
        return jsonify({"ok": False, "error": "Sheets not configured"}), 500
    d = request.json or {}
    try:
        sheets.append_work_web(
            SPREADSHEET_ID,
            date=d.get("date", ""),
            task=d.get("task", ""),
            client=d.get("client", ""),
            status=d.get("status", ""),
            priority=d.get("priority", ""),
            due_date=d.get("due_date", ""),
            description=d.get("description", ""),
            note=d.get("note", ""),
            user_name=d.get("recorded_by", "Web"),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/recent", methods=["GET"])
def api_recent():
    if not SPREADSHEET_ID:
        return jsonify({"expenses": [], "tasks": []})
    try:
        expenses = sheets.get_recent_expenses(SPREADSHEET_ID, limit=10)
        tasks    = sheets.get_recent_works(SPREADSHEET_ID, limit=10)
        return jsonify({"expenses": expenses, "tasks": tasks})
    except Exception as e:
        return jsonify({"expenses": [], "tasks": [], "error": str(e)})


# ── Auth API ───────────────────────────────────────────────────────────────────

@app.route("/api/contact", methods=["POST"])
def api_contact():
    d = request.json or {}
    name    = d.get("name", "").strip()
    email   = d.get("email", "").strip()
    company = d.get("company", "").strip()
    subject = d.get("subject", "").strip()
    message = d.get("message", "").strip()
    if not name or not email or not message:
        return jsonify({"ok": False, "error": "กรุณากรอกข้อมูลให้ครบ"}), 400
    # Save to DB
    auth.save_contact(name, email, company, subject, message)
    # Notify admin — LINE push + Email (direct SMTP)
    line_push.notify_contact(name, email, company, subject, message)
    emailsvc.notify_contact(name, email, company, subject, message)
    return jsonify({"ok": True})


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    d = request.json or {}
    result = auth.register(
        email=d.get("email", ""),
        name=d.get("name", ""),
        password=d.get("password", ""),
    )
    # Notify admin — LINE push + Email (direct SMTP)
    if result["ok"]:
        line_push.notify_register(d.get("name", ""), d.get("email", ""))
        emailsvc.notify_register(d.get("name", ""), d.get("email", ""))
    return jsonify(result), (200 if result["ok"] else 400)


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    d = request.json or {}
    result = auth.login(
        email=d.get("email", ""),
        password=d.get("password", ""),
    )
    return jsonify(result), (200 if result["ok"] else 401)


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    token = (request.json or {}).get("token", "")
    auth.logout(token)
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = auth.verify_token(token)
    if not user:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return jsonify({"ok": True, **user})


@app.route("/api/auth/users", methods=["GET"])
def api_users():
    """Admin only — list all users."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = auth.verify_token(token)
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "Admin only"}), 403
    return jsonify({"ok": True, "users": auth.list_users()})


@app.route("/api/contacts", methods=["GET"])
def api_contacts():
    """Admin only — list all contact messages."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = auth.verify_token(token)
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "Admin only"}), 403
    return jsonify({"ok": True, "contacts": auth.list_contacts()})


# ── DATA API — Expenses ────────────────────────────────────────────────────────

@app.route("/api/expenses", methods=["GET"])
def api_get_expenses():
    return jsonify({"ok": True, "data": data.get_expenses()})

@app.route("/api/expenses", methods=["POST"])
def api_save_expense():
    record = request.json or {}
    result = data.save_expense(record)
    if SPREADSHEET_ID:
        try:
            sheets.sync_expense(SPREADSHEET_ID, {**record, "id": result["id"]})
        except Exception:
            pass
    return jsonify({"ok": True, **result})

@app.route("/api/expenses/<eid>", methods=["DELETE"])
def api_delete_expense(eid):
    data.delete_expense(eid)
    if SPREADSHEET_ID:
        try:
            sheets.delete_expense_sheet(SPREADSHEET_ID, eid)
        except Exception:
            pass
    return jsonify({"ok": True})


# ── DATA API — Notes ───────────────────────────────────────────────────────────

@app.route("/api/notes", methods=["GET"])
def api_get_notes():
    return jsonify({"ok": True, "data": data.get_notes()})

@app.route("/api/notes", methods=["POST"])
def api_save_note():
    record = request.json or {}
    result = data.save_note(record)
    if SPREADSHEET_ID:
        try:
            sheets.sync_note(SPREADSHEET_ID, {**record, "id": result["id"]})
        except Exception:
            pass
    return jsonify({"ok": True, **result})

@app.route("/api/notes/<nid>", methods=["DELETE"])
def api_delete_note(nid):
    data.delete_note(nid)
    if SPREADSHEET_ID:
        try:
            sheets.delete_note_sheet(SPREADSHEET_ID, nid)
        except Exception:
            pass
    return jsonify({"ok": True})


# ── DATA API — Tasks ───────────────────────────────────────────────────────────

@app.route("/api/tasks", methods=["GET"])
def api_get_tasks():
    return jsonify({"ok": True, "data": data.get_tasks()})

@app.route("/api/tasks", methods=["POST"])
def api_save_task():
    record = request.json or {}
    result = data.save_task(record)
    if SPREADSHEET_ID:
        try:
            sheets.sync_task(SPREADSHEET_ID, {**record, "id": result["id"]})
        except Exception:
            pass
    return jsonify({"ok": True, **result})

@app.route("/api/tasks/<tid>", methods=["DELETE"])
def api_delete_task(tid):
    data.delete_task(tid)
    if SPREADSHEET_ID:
        try:
            sheets.delete_task_sheet(SPREADSHEET_ID, tid)
        except Exception:
            pass
    return jsonify({"ok": True})


# ── DATA API — Investment ──────────────────────────────────────────────────────

@app.route("/api/portfolios", methods=["GET"])
def api_get_portfolios():
    return jsonify({"ok": True, "data": data.get_portfolios()})

@app.route("/api/portfolios", methods=["POST"])
def api_save_portfolio():
    record = request.json or {}
    result = data.save_portfolio(record)
    return jsonify({"ok": True, **result})

@app.route("/api/portfolios/<pid>", methods=["DELETE"])
def api_delete_portfolio(pid):
    data.delete_portfolio(pid)
    return jsonify({"ok": True})

@app.route("/api/investments", methods=["GET"])
def api_get_investments():
    pid = request.args.get("portfolio", "")
    return jsonify({"ok": True, "data": data.get_investments(pid)})

@app.route("/api/investments", methods=["POST"])
def api_save_investment():
    record = request.json or {}
    result = data.save_investment(record)
    if SPREADSHEET_ID:
        try:
            portfolios = data.get_portfolios()
            pname = next((p["name"] for p in portfolios if p["id"] == record.get("portfolio_id")), "")
            sheets.sync_investment(SPREADSHEET_ID, {**record, "id": result["id"]}, pname)
        except Exception:
            pass
    return jsonify({"ok": True, **result})

@app.route("/api/investments/<iid>", methods=["DELETE"])
def api_delete_investment(iid):
    data.delete_investment(iid)
    if SPREADSHEET_ID:
        try:
            sheets.delete_investment_sheet(SPREADSHEET_ID, iid)
        except Exception:
            pass
    return jsonify({"ok": True})

@app.route("/api/dividends", methods=["GET"])
def api_get_dividends():
    pid = request.args.get("portfolio", "")
    return jsonify({"ok": True, "data": data.get_dividends(pid)})

@app.route("/api/dividends", methods=["POST"])
def api_save_dividend():
    record = request.json or {}
    result = data.save_dividend(record)
    if SPREADSHEET_ID:
        try:
            portfolios = data.get_portfolios()
            pname = next((p["name"] for p in portfolios if p["id"] == record.get("portfolio_id")), "")
            sheets.sync_dividend(SPREADSHEET_ID, {**record, "id": result["id"]}, pname)
        except Exception:
            pass
    return jsonify({"ok": True, **result})

@app.route("/api/dividends/<did>", methods=["DELETE"])
def api_delete_dividend(did):
    data.delete_dividend(did)
    return jsonify({"ok": True})

@app.route("/api/smart-import", methods=["POST"])
def api_smart_import():
    """Call Gemini API to classify text → save tasks/expenses/notes."""
    import json, time, requests as req_lib
    body = request.json or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "No text provided"}), 400

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        # No key — save whole text as a note
        record = {
            "id":       str(int(time.time() * 1000)),
            "date":     __import__("datetime").date.today().isoformat(),
            "title":    text[:60] + ("…" if len(text) > 60 else ""),
            "content":  text,
            "category": "นำเข้า",
        }
        data.save_note(record)
        return jsonify({
            "ok": True, "savedTasks": 0, "savedExpenses": 0, "savedNotes": 1,
            "tasks": [], "expenses": [], "notes": [record],
            "warning": "GEMINI_API_KEY not set — saved as note",
        })

    prompt = (
        "วิเคราะห์ข้อความต่อไปนี้และจัดหมวดหมู่เป็น JSON เท่านั้น ห้ามอธิบายเพิ่มเติม:\n\n"
        f'"{text[:3000]}"\n\n'
        "ตอบในรูปแบบ JSON เท่านั้น:\n"
        '{"tasks":[{"title":"...","priority":"high|medium|low","due":"YYYY-MM-DD หรือ blank"}],'
        '"expenses":[{"amount":0,"category":"อาหาร/เครื่องดื่ม|เดินทาง|ช้อปปิ้ง|สุขภาพ|ที่พัก|ความบันเทิง|การศึกษา|อื่นๆ","notes":"..."}],'
        '"notes":[{"title":"...","content":"...","category":"..."}]}\n\n'
        "กฎ: tasks=action items/สิ่งที่ต้องทำ, expenses=รายจ่ายที่มีตัวเลข, notes=สรุป/บันทึก. "
        "priority: high=ด่วน, low=ไม่เร่งด่วน, medium=ปกติ. ถ้าไม่มีประเภทใดใส่[]"
    )

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
        resp = req_lib.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
        }, timeout=20)

        if resp.status_code != 200:
            raise ValueError(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        import re as _re
        jm = _re.search(r'\{[\s\S]*\}', raw)
        if not jm:
            raise ValueError("No JSON in Gemini response")
        classified = json.loads(jm.group())

    except Exception as e:
        print(f"[SmartImport Gemini] {e}")
        # Fallback: save as note
        record = {
            "id":       str(int(time.time() * 1000)),
            "date":     __import__("datetime").date.today().isoformat(),
            "title":    text[:60] + ("…" if len(text) > 60 else ""),
            "content":  text,
            "category": "นำเข้า",
        }
        data.save_note(record)
        return jsonify({
            "ok": True, "savedTasks": 0, "savedExpenses": 0, "savedNotes": 1,
            "tasks": [], "expenses": [], "notes": [record],
            "warning": f"AI error: {e} — saved as note",
        })

    import re as _re2
    def _safe_float(v):
        try:
            return float(_re2.sub(r'[^\d.]', '', str(v)) or 0)
        except (ValueError, TypeError):
            return 0.0

    today_str = __import__("datetime").date.today().isoformat()
    saved_tasks, saved_expenses, saved_notes = 0, 0, 0
    tasks    = classified.get("tasks", []) if isinstance(classified.get("tasks"), list) else []
    expenses = classified.get("expenses", []) if isinstance(classified.get("expenses"), list) else []
    notes    = classified.get("notes", []) if isinstance(classified.get("notes"), list) else []

    try:
        for t in tasks:
            if not t.get("title"): continue
            data.save_task({
                "id":       str(int(time.time() * 1000)),
                "date":     today_str,
                "title":    t["title"],
                "priority": t.get("priority", "medium"),
                "status":   "todo",
                "due":      t.get("due", ""),
                "notes":    "",
            })
            saved_tasks += 1

        for e in expenses:
            amt = _safe_float(e.get("amount", 0) or 0)
            if amt <= 0: continue
            data.save_expense({
                "id":       str(int(time.time() * 1000)),
                "date":     today_str,
                "amount":   amt,
                "category": e.get("category", "อื่นๆ"),
                "payment":  "",
                "notes":    e.get("notes", ""),
            })
            saved_expenses += 1

        for n in notes:
            if not n.get("content") and not n.get("title"): continue
            data.save_note({
                "id":       str(int(time.time() * 1000)),
                "date":     today_str,
                "title":    n.get("title") or (n.get("content") or "")[:60],
                "content":  n.get("content", ""),
                "category": n.get("category", "นำเข้า"),
            })
            saved_notes += 1

        if not saved_tasks and not saved_expenses and not saved_notes:
            record = {
                "id":       str(int(time.time() * 1000)),
                "date":     today_str,
                "title":    text[:60] + ("…" if len(text) > 60 else ""),
                "content":  text,
                "category": "นำเข้า",
            }
            data.save_note(record)
            saved_notes = 1
            notes = [record]

    except Exception as save_err:
        print(f"[SmartImport Save] {save_err}")
        return jsonify({"ok": False, "error": f"บันทึกข้อมูลล้มเหลว: {save_err}"}), 500

    return jsonify({
        "ok": True,
        "savedTasks":    saved_tasks,
        "savedExpenses": saved_expenses,
        "savedNotes":    saved_notes,
        "tasks":         tasks,
        "expenses":      expenses,
        "notes":         notes,
    })


@app.route("/api/targets/<pid>", methods=["GET"])
def api_get_targets(pid):
    return jsonify({"ok": True, "data": data.get_targets(pid)})

@app.route("/api/targets/<pid>", methods=["PUT"])
def api_save_targets(pid):
    d = request.json or {}
    data.save_targets(pid, d)
    return jsonify({"ok": True})


# ── SYNC API ──────────────────────────────────────────────────────────────────

@app.route("/api/sync/push", methods=["POST"])
def api_sync_push():
    """Push all SQLite data → Google Sheets."""
    if not SPREADSHEET_ID:
        return jsonify({"ok": False, "error": "SPREADSHEET_ID not set"}), 500
    try:
        counts = sheets.push_all(SPREADSHEET_ID, data)
        return jsonify({"ok": True, "pushed": counts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/sync/pull", methods=["POST"])
def api_sync_pull():
    """Pull new rows from Google Sheets → SQLite (skips existing IDs)."""
    if not SPREADSHEET_ID:
        return jsonify({"ok": False, "error": "SPREADSHEET_ID not set"}), 500
    try:
        counts = sheets.pull_all(SPREADSHEET_ID, data)
        return jsonify({"ok": True, "imported": counts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/sync/init", methods=["POST"])
def api_sync_init():
    """Create all sheet tabs with correct headers if they don't exist."""
    if not SPREADSHEET_ID:
        return jsonify({"ok": False, "error": "SPREADSHEET_ID not set"}), 500
    try:
        sheets.init_sheets(SPREADSHEET_ID)
        return jsonify({"ok": True, "message": "Sheets initialized"})
    except Exception as e:
        app.logger.error("sync/init failed: %s", e, exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500


# ── CLAUDE USAGE API ──────────────────────────────────────────────────────────

@app.route("/api/claude-usage", methods=["GET"])
def api_claude_usage():
    import glob
    from collections import defaultdict

    claude_dir = os.path.expanduser("~/.claude/projects")
    by_day = defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0, "messages": 0})

    for jsonl_path in glob.glob(os.path.join(claude_dir, "**", "*.jsonl"), recursive=True):
        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line)
                    if obj.get("type") != "assistant":
                        continue
                    msg = obj.get("message", {})
                    usage = msg.get("usage")
                    if not usage:
                        continue
                    ts = obj.get("timestamp", "")
                    day = ts[:10] if ts else "unknown"
                    by_day[day]["input"]        += usage.get("input_tokens", 0)
                    by_day[day]["output"]       += usage.get("output_tokens", 0)
                    by_day[day]["cache_read"]   += usage.get("cache_read_input_tokens", 0)
                    by_day[day]["cache_create"] += usage.get("cache_creation_input_tokens", 0)
                    by_day[day]["messages"]     += 1
        except Exception:
            pass

    result = [{"date": d, **by_day[d]} for d in sorted(by_day.keys())]
    return jsonify({"ok": True, "data": result})


# ── SANDBOX API ───────────────────────────────────────────────────────────────

import time as _time
import platform as _platform

_SANDBOX_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MEMORY_PATH  = r"\\wsl.localhost\Ubuntu\home\rukphong\.claude\projects\-mnt-c-Users-U939-OneDrive-Desktop-Sandbox\memory"

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".claude",
              "kind-grothendieck-0b547e", "practical-agnesi-e5afd8", ".venv", "venv"}
_SKIP_EXTS = {".pyc", ".pyo", ".db-wal", ".db-shm", ".db-journal"}


def _build_tree(path, depth=0, max_depth=2):
    nodes = []
    try:
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return nodes
    for e in entries:
        if e.name.startswith(".") or e.name in _SKIP_DIRS:
            continue
        if e.is_dir():
            node = {"name": e.name, "is_dir": True, "children": []}
            if depth < max_depth:
                node["children"] = _build_tree(e.path, depth + 1, max_depth)
            nodes.append(node)
        else:
            if any(e.name.endswith(x) for x in _SKIP_EXTS):
                continue
            try:
                mtime = _time.strftime("%m-%d", _time.localtime(e.stat().st_mtime))
            except Exception:
                mtime = ""
            nodes.append({"name": e.name, "is_dir": False, "modified": mtime})
    return nodes


def _load_memories():
    mems = []
    try:
        for fname in sorted(os.listdir(_MEMORY_PATH)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(_MEMORY_PATH, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    mems.append({"file": fname, "content": f.read()})
            except Exception:
                pass
    except Exception:
        pass
    return mems


@app.route("/api/sandbox", methods=["GET"])
def api_sandbox():
    try:
        recent_files = []
        for root, dirs, files in os.walk(_SANDBOX_PATH):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for f in files:
                if any(f.endswith(e) for e in _SKIP_EXTS):
                    continue
                fp = os.path.join(root, f)
                try:
                    st  = os.stat(fp)
                    rel = fp[len(_SANDBOX_PATH) + 1:].replace("\\", "/")
                    recent_files.append({
                        "path":         rel,
                        "modified":     st.st_mtime,
                        "modified_str": _time.strftime("%Y-%m-%d %H:%M", _time.localtime(st.st_mtime)),
                        "size":         st.st_size,
                    })
                except Exception:
                    pass
        recent_files.sort(key=lambda x: x["modified"], reverse=True)
        recent_files = recent_files[:60]

        projects = []
        for item in sorted(os.listdir(_SANDBOX_PATH)):
            item_path = os.path.join(_SANDBOX_PATH, item)
            if not os.path.isdir(item_path) or item.startswith(".") or item in _SKIP_DIRS:
                continue
            file_count, last_mod = 0, 0
            for root, dirs, files in os.walk(item_path):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
                for f in files:
                    if any(f.endswith(e) for e in _SKIP_EXTS):
                        continue
                    try:
                        mtime = os.stat(os.path.join(root, f)).st_mtime
                        file_count += 1
                        if mtime > last_mod:
                            last_mod = mtime
                    except Exception:
                        pass
            projects.append({
                "name":             item,
                "file_count":       file_count,
                "last_modified":    _time.strftime("%Y-%m-%d", _time.localtime(last_mod)) if last_mod else "N/A",
                "last_modified_ts": last_mod,
            })
        projects.sort(key=lambda x: x["last_modified_ts"], reverse=True)

        return jsonify({
            "ok":           True,
            "recent_files": recent_files,
            "projects":     projects,
            "tree":         _build_tree(_SANDBOX_PATH),
            "memories":     _load_memories(),
            "generated_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/sandbox/todos", methods=["GET"])
def api_sandbox_todos_get():
    todos = data.get_todos()
    # map created_at → created for template compatibility
    for t in todos:
        t["created"] = t.pop("created_at", "")[:10]
    return jsonify({"ok": True, "todos": todos})


@app.route("/api/sandbox/todos", methods=["POST"])
def api_sandbox_todos_add():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"ok": False, "error": "empty"}), 400
    result = data.add_todo(text)
    return jsonify({"ok": True, **result})


@app.route("/api/sandbox/todos/<tid>", methods=["PATCH"])
def api_sandbox_todos_toggle(tid):
    data.toggle_todo(tid)
    return jsonify({"ok": True})


@app.route("/api/sandbox/todos/<tid>", methods=["DELETE"])
def api_sandbox_todos_delete(tid):
    data.delete_todo(tid)
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
