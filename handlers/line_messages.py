"""Rich LINE message builders — QuickReply & Flex, bilingual."""

from linebot.v3.messaging import (
    TextMessage, FlexMessage, QuickReply, QuickReplyItem, MessageAction,
    FlexBubble, FlexBox, FlexText, FlexSeparator,
)
from handlers.lang import t, categories, statuses


def _qr(label: str, text: str) -> QuickReplyItem:
    return QuickReplyItem(action=MessageAction(label=label[:20], text=text))


# ── Main menu ─────────────────────────────────────────────────────────────────

def main_menu(text: str, lang: str = "th") -> TextMessage:
    if lang == "en":
        items = [
            _qr("💰 Record Expense", "expense"),
            _qr("📋 Record Task",    "task"),
            _qr("💰 Latest Expense", "latest expense"),
            _qr("📋 Latest Task",    "latest task"),
            _qr("📊 Summary",        "summary"),
        ]
    else:
        items = [
            _qr("💰 บันทึกรายจ่าย", "จ่าย"),
            _qr("📋 บันทึกงาน",     "งาน"),
            _qr("💰 รายจ่ายล่าสุด", "รายจ่ายล่าสุด"),
            _qr("📋 งานล่าสุด",     "งานล่าสุด"),
            _qr("📊 สรุปรายจ่าย",   "สรุปรายจ่าย"),
        ]
    return TextMessage(text=text, quick_reply=QuickReply(items=items))


# ── Conversation steps ────────────────────────────────────────────────────────

def ask_amount(lang: str = "th") -> TextMessage:
    return TextMessage(text=t("ask_amount", lang))


def ask_category(lang: str = "th") -> TextMessage:
    items = [_qr(c, c) for c in categories(lang)]
    return TextMessage(text=t("ask_category", lang), quick_reply=QuickReply(items=items))


def ask_task(lang: str = "th") -> TextMessage:
    return TextMessage(text=t("ask_task", lang))


def ask_status(lang: str = "th") -> TextMessage:
    items = [_qr(s, s) for s in statuses(lang)]
    return TextMessage(text=t("ask_status", lang), quick_reply=QuickReply(items=items))


def ask_note(lang: str = "th") -> TextMessage:
    return TextMessage(
        text=t("ask_note", lang),
        quick_reply=QuickReply(items=[_qr(t("skip", lang), "-")]),
    )


# ── Confirmation Flex cards ───────────────────────────────────────────────────

def confirm_expense(amount: float, category: str, note: str, lang: str = "th") -> FlexMessage:
    bubble = FlexBubble(
        header=FlexBox(
            layout="vertical", background_color="#27ACB2",
            contents=[FlexText(text=t("confirm_expense_header", lang),
                               weight="bold", color="#ffffff", size="md")],
        ),
        body=FlexBox(layout="vertical", contents=[
            FlexBox(layout="horizontal", contents=[
                FlexText(text=t("label_amount", lang),   size="sm", color="#555555", flex=2),
                FlexText(text=f"{amount:,.2f} {'THB' if lang=='en' else 'บาท'}",
                         size="sm", color="#27ACB2", align="end", flex=3, weight="bold"),
            ]),
            FlexSeparator(margin="sm"),
            FlexBox(layout="horizontal", margin="sm", contents=[
                FlexText(text=t("label_category", lang), size="sm", color="#555555", flex=2),
                FlexText(text=category, size="sm", color="#111111", align="end", flex=3),
            ]),
            FlexBox(layout="horizontal", margin="sm", contents=[
                FlexText(text=t("label_note", lang), size="sm", color="#555555", flex=2),
                FlexText(text=note or "-", size="sm", color="#111111", align="end", flex=3, wrap=True),
            ]),
        ]),
    )
    unit = "THB" if lang == "en" else "บาท"
    return FlexMessage(alt_text=f"{t('confirm_expense_header', lang)} {amount:,.2f} {unit}",
                       contents=bubble)


def confirm_work(task: str, status: str, note: str, lang: str = "th") -> FlexMessage:
    bubble = FlexBubble(
        header=FlexBox(
            layout="vertical", background_color="#5B8AF0",
            contents=[FlexText(text=t("confirm_work_header", lang),
                               weight="bold", color="#ffffff", size="md")],
        ),
        body=FlexBox(layout="vertical", contents=[
            FlexBox(layout="horizontal", contents=[
                FlexText(text=t("label_task", lang),   size="sm", color="#555555", flex=2),
                FlexText(text=task, size="sm", color="#111111", align="end", flex=3, wrap=True),
            ]),
            FlexSeparator(margin="sm"),
            FlexBox(layout="horizontal", margin="sm", contents=[
                FlexText(text=t("label_status", lang), size="sm", color="#555555", flex=2),
                FlexText(text=status, size="sm", color="#5B8AF0", align="end", flex=3, weight="bold"),
            ]),
            FlexBox(layout="horizontal", margin="sm", contents=[
                FlexText(text=t("label_note", lang), size="sm", color="#555555", flex=2),
                FlexText(text=note or "-", size="sm", color="#111111", align="end", flex=3, wrap=True),
            ]),
        ]),
    )
    return FlexMessage(alt_text=t("alt_task", lang, task=task), contents=bubble)


# ── Summary / list Flex cards ─────────────────────────────────────────────────

def expense_summary(summary: dict, lang: str = "th") -> FlexMessage:
    rows = []
    for cat, total in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
        rows.append(FlexBox(layout="horizontal", margin="sm", contents=[
            FlexText(text=cat, size="xs", color="#555555", flex=3),
            FlexText(text=f"{total:,.0f}", size="xs", align="end", flex=2, weight="bold"),
        ]))
    unit = "THB" if lang == "en" else "บาท"
    bubble = FlexBubble(
        header=FlexBox(layout="vertical", background_color="#FF6B6B",
                       contents=[FlexText(text=t("summary_header", lang),
                                          weight="bold", color="#ffffff")]),
        body=FlexBox(layout="vertical", contents=[
            FlexBox(layout="horizontal", contents=[
                FlexText(text=t("summary_today", lang), size="sm", color="#555555"),
                FlexText(text=f"{summary['today_total']:,.2f} {unit}",
                         size="sm", align="end", weight="bold", color="#FF6B6B"),
            ]),
            FlexBox(layout="horizontal", margin="sm", contents=[
                FlexText(text=t("summary_total", lang, n=summary["count"]),
                         size="sm", color="#555555"),
                FlexText(text=f"{summary['total']:,.2f} {unit}",
                         size="sm", align="end", weight="bold"),
            ]),
            FlexSeparator(margin="md"),
            *rows,
        ]),
    )
    return FlexMessage(alt_text=t("summary_header", lang), contents=bubble)


def recent_expenses(rows: list[dict], lang: str = "th") -> FlexMessage:
    unit = "THB" if lang == "en" else "฿"
    items = []
    for r in rows:
        try:
            amount = float(r.get("amount", 0))
        except (ValueError, TypeError):
            amount = 0
        note_row = [FlexText(text=r["note"], size="xxs", color="#888888")] if r.get("note") else []
        items += [
            FlexBox(layout="horizontal", margin="sm", contents=[
                FlexBox(layout="vertical", flex=4, contents=[
                    FlexText(text=r.get("category", "-"), size="sm", weight="bold"),
                    FlexText(text=r.get("date", ""),      size="xxs", color="#aaaaaa"),
                    *note_row,
                ]),
                FlexText(text=f"{amount:,.0f} {unit}", size="sm", align="end",
                         flex=2, weight="bold", color="#FF6B6B"),
            ]),
            FlexSeparator(margin="sm"),
        ]
    body = items or [FlexText(text=t("no_records", lang), color="#aaaaaa", align="center")]
    bubble = FlexBubble(
        header=FlexBox(layout="vertical", background_color="#FF6B6B",
                       contents=[FlexText(text=t("recent_expense_header", lang),
                                          weight="bold", color="#ffffff")]),
        body=FlexBox(layout="vertical", contents=body),
    )
    return FlexMessage(alt_text=t("recent_expense_header", lang), contents=bubble)


def recent_works(rows: list[dict], lang: str = "th") -> FlexMessage:
    STATUS_COLORS = {
        "เสร็จแล้ว": "#27ACB2", "Done": "#27ACB2",
        "กำลังทำ": "#F0A500",   "In Progress": "#F0A500",
        "รอดำเนินการ": "#888888", "Pending": "#888888",
        "ยกเลิก": "#FF6B6B",    "Cancelled": "#FF6B6B",
    }
    items = []
    for r in rows:
        color = STATUS_COLORS.get(r.get("status", ""), "#888888")
        items += [
            FlexBox(layout="horizontal", margin="sm", contents=[
                FlexBox(layout="vertical", flex=4, contents=[
                    FlexText(text=r.get("task", "-"), size="sm", weight="bold", wrap=True),
                    FlexText(text=r.get("date", ""), size="xxs", color="#aaaaaa"),
                ]),
                FlexText(text=r.get("status", "-"), size="xs", align="end",
                         flex=2, weight="bold", color=color),
            ]),
            FlexSeparator(margin="sm"),
        ]
    body = items or [FlexText(text=t("no_records", lang), color="#aaaaaa", align="center")]
    bubble = FlexBubble(
        header=FlexBox(layout="vertical", background_color="#5B8AF0",
                       contents=[FlexText(text=t("recent_work_header", lang),
                                          weight="bold", color="#ffffff")]),
        body=FlexBox(layout="vertical", contents=body),
    )
    return FlexMessage(alt_text=t("recent_work_header", lang), contents=bubble)
