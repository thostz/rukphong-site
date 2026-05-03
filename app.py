import os
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
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from handlers.message_handler import handle_text
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


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


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
            sheets.append_expense_web(SPREADSHEET_ID,
                date=record.get("date",""), amount=float(record.get("amount",0)),
                category=record.get("category",""), payment=record.get("currency",""),
                note=record.get("notes",""), user_name="Web")
        except Exception:
            pass
    return jsonify({"ok": True, **result})

@app.route("/api/expenses/<eid>", methods=["DELETE"])
def api_delete_expense(eid):
    data.delete_expense(eid)
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
            sheets.append_work_web(SPREADSHEET_ID,
                date=record.get("due",""), task=record.get("title",""),
                client="", status=record.get("status",""),
                priority=record.get("priority",""), due_date=record.get("due",""),
                description="", note=record.get("notes",""), user_name="Web")
        except Exception:
            pass
    return jsonify({"ok": True, **result})

@app.route("/api/tasks/<tid>", methods=["DELETE"])
def api_delete_task(tid):
    data.delete_task(tid)
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

@app.route("/api/targets/<pid>", methods=["GET"])
def api_get_targets(pid):
    return jsonify({"ok": True, "data": data.get_targets(pid)})

@app.route("/api/targets/<pid>", methods=["PUT"])
def api_save_targets(pid):
    d = request.json or {}
    data.save_targets(pid, d)
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
