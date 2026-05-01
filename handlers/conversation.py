"""State machine for multi-step LINE conversations."""

from handlers.lang import categories as lang_categories, statuses as lang_statuses

# Return markers — interpreted by message_handler
SHOW_CATEGORY_QR = "__SHOW_CATEGORY_QR__"
SHOW_STATUS_QR = "__SHOW_STATUS_QR__"
SHOW_NOTE_QR = "__SHOW_NOTE_QR__"
EXPENSE_DONE = "__EXPENSE_DONE__"
WORK_DONE = "__WORK_DONE__"

_sessions: dict[str, dict] = {}


def get_session(user_id: str) -> dict:
    return _sessions.get(user_id, {})


def set_session(user_id: str, data: dict):
    _sessions[user_id] = data


def clear_session(user_id: str):
    _sessions.pop(user_id, None)


# ── Expense flow ──────────────────────────────────────────────────────────────

def start_expense(user_id: str, amount: float | None = None) -> str:
    if amount is not None:
        set_session(user_id, {"flow": "expense", "step": "category", "amount": amount})
        return SHOW_CATEGORY_QR
    set_session(user_id, {"flow": "expense", "step": "amount"})
    return "__ASK_AMOUNT__"


# ── Work flow ─────────────────────────────────────────────────────────────────

def start_work(user_id: str, task: str | None = None) -> str:
    if task:
        set_session(user_id, {"flow": "work", "step": "status", "task": task})
        return SHOW_STATUS_QR
    set_session(user_id, {"flow": "work", "step": "task"})
    return "__ASK_TASK__"


# ── Step router ───────────────────────────────────────────────────────────────

def handle_step(user_id: str, text: str) -> tuple[str, dict | None]:
    session = get_session(user_id)
    flow = session.get("flow")
    step = session.get("step")

    if flow == "expense":
        return _expense_step(user_id, session, step, text)
    if flow == "work":
        return _work_step(user_id, session, step, text)
    return "", None


def _match_category(text: str) -> str | None:
    all_cats = lang_categories("th") + lang_categories("en")
    return text if text in all_cats else None


def _match_status(text: str) -> str | None:
    all_statuses = lang_statuses("th") + lang_statuses("en")
    return text if text in all_statuses else None


def _expense_step(user_id, session, step, text) -> tuple[str, dict | None]:
    if step == "amount":
        try:
            amount = float(text.replace(",", ""))
        except ValueError:
            return "❌ กรุณาพิมพ์จำนวนเงินเป็นตัวเลข เช่น  150", None
        session.update({"step": "category", "amount": amount})
        set_session(user_id, session)
        return SHOW_CATEGORY_QR, None

    if step == "category":
        matched = _match_category(text)
        if not matched:
            return SHOW_CATEGORY_QR, None
        session.update({"step": "note", "category": matched})
        set_session(user_id, session)
        return SHOW_NOTE_QR, None

    if step == "note":
        note = "" if text.strip() == "-" else text.strip()
        data = {
            "type": "expense",
            "amount": session["amount"],
            "category": session["category"],
            "note": note,
        }
        clear_session(user_id)
        return EXPENSE_DONE, data

    return "", None


def _work_step(user_id, session, step, text) -> tuple[str, dict | None]:
    if step == "task":
        session.update({"step": "status", "task": text.strip()})
        set_session(user_id, session)
        return SHOW_STATUS_QR, None

    if step == "status":
        matched = _match_status(text)
        if not matched:
            return SHOW_STATUS_QR, None
        session.update({"step": "note", "status": matched})
        set_session(user_id, session)
        return SHOW_NOTE_QR, None

    if step == "note":
        note = "" if text.strip() == "-" else text.strip()
        data = {
            "type": "work",
            "task": session["task"],
            "status": session["status"],
            "note": note,
        }
        clear_session(user_id)
        return WORK_DONE, data

    return "", None
