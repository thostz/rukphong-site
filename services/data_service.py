"""SQLite CRUD for Expense, Notes, Tasks, Investment (portfolios/investments/dividends/targets)."""

import os
import sqlite3
import json
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")


def _connect():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    con = sqlite3.connect(_DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_data_tables():
    con = _connect()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          TEXT PRIMARY KEY,
            description TEXT,
            category    TEXT,
            currency    TEXT DEFAULT 'THB',
            amount      REAL,
            date        TEXT,
            notes       TEXT,
            created_at  TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes_tb (
            id         TEXT PRIMARY KEY,
            title      TEXT,
            content    TEXT,
            category   TEXT,
            date       TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id         TEXT PRIMARY KEY,
            title      TEXT,
            priority   TEXT,
            status     TEXT,
            due        TEXT,
            notes      TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS investments (
            id            TEXT PRIMARY KEY,
            portfolio_id  TEXT,
            type          TEXT,
            symbol        TEXT,
            name          TEXT,
            qty           REAL DEFAULT 0,
            cost_price    REAL DEFAULT 0,
            current_price REAL DEFAULT 0,
            note          TEXT,
            created_at    TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dividends (
            id           TEXT PRIMARY KEY,
            portfolio_id TEXT,
            date         TEXT,
            amount       REAL DEFAULT 0,
            note         TEXT,
            symbol       TEXT,
            type         TEXT,
            created_at   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inv_targets (
            portfolio_id TEXT PRIMARY KEY,
            data         TEXT,
            updated_at   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sandbox_todos (
            id         TEXT PRIMARY KEY,
            text       TEXT NOT NULL,
            done       INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    con.commit()
    cur.close()
    con.close()


# ── EXPENSES ──────────────────────────────────────────────────────────────────

def get_expenses() -> list:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM expenses ORDER BY date DESC, created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); con.close()
    return rows

def save_expense(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT id FROM expenses WHERE id=?", (rid,))
    if cur.fetchone():
        cur.execute("""UPDATE expenses SET description=?,category=?,currency=?,amount=?,date=?,notes=?
                       WHERE id=?""",
                    (record.get("description",""), record.get("category",""),
                     record.get("currency","THB"), float(record.get("amount",0)),
                     record.get("date",""), record.get("notes",""), rid))
    else:
        cur.execute("""INSERT INTO expenses (id,description,category,currency,amount,date,notes,created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (rid, record.get("description",""), record.get("category",""),
                     record.get("currency","THB"), float(record.get("amount",0)),
                     record.get("date",""), record.get("notes",""), now))
    con.commit()
    cur.close(); con.close()
    return {"id": rid}

def delete_expense(eid: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM expenses WHERE id=?", (eid,))
    con.commit()
    cur.close(); con.close()


# ── NOTES ─────────────────────────────────────────────────────────────────────

def get_notes() -> list:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM notes_tb ORDER BY date DESC, created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); con.close()
    return rows

def save_note(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT id FROM notes_tb WHERE id=?", (rid,))
    if cur.fetchone():
        cur.execute("UPDATE notes_tb SET title=?,content=?,category=?,date=? WHERE id=?",
                    (record.get("title",""), record.get("content",""),
                     record.get("category",""), record.get("date",""), rid))
    else:
        cur.execute("""INSERT INTO notes_tb (id,title,content,category,date,created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (rid, record.get("title",""), record.get("content",""),
                     record.get("category",""), record.get("date",""), now))
    con.commit()
    cur.close(); con.close()
    return {"id": rid}

def delete_note(nid: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM notes_tb WHERE id=?", (nid,))
    con.commit()
    cur.close(); con.close()


# ── TASKS ─────────────────────────────────────────────────────────────────────

def get_tasks() -> list:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM tasks ORDER BY due ASC, created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); con.close()
    return rows

def save_task(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT id FROM tasks WHERE id=?", (rid,))
    if cur.fetchone():
        cur.execute("""UPDATE tasks SET title=?,priority=?,status=?,due=?,notes=?,updated_at=?
                       WHERE id=?""",
                    (record.get("title",""), record.get("priority",""),
                     record.get("status",""), record.get("due",""),
                     record.get("notes",""), now, rid))
    else:
        cur.execute("""INSERT INTO tasks (id,title,priority,status,due,notes,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (rid, record.get("title",""), record.get("priority",""),
                     record.get("status",""), record.get("due",""),
                     record.get("notes",""), now, now))
    con.commit()
    cur.close(); con.close()
    return {"id": rid}

def delete_task(tid: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM tasks WHERE id=?", (tid,))
    con.commit()
    cur.close(); con.close()


# ── PORTFOLIOS ────────────────────────────────────────────────────────────────

def get_portfolios() -> list:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM portfolios ORDER BY created_at ASC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); con.close()
    return rows

def save_portfolio(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT id FROM portfolios WHERE id=?", (rid,))
    if cur.fetchone():
        cur.execute("UPDATE portfolios SET name=? WHERE id=?", (record.get("name",""), rid))
    else:
        cur.execute("INSERT INTO portfolios (id,name,created_at) VALUES (?,?,?)",
                    (rid, record.get("name",""), now))
    con.commit()
    cur.close(); con.close()
    return {"id": rid}

def delete_portfolio(pid: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM investments WHERE portfolio_id=?", (pid,))
    cur.execute("DELETE FROM dividends WHERE portfolio_id=?", (pid,))
    cur.execute("DELETE FROM inv_targets WHERE portfolio_id=?", (pid,))
    cur.execute("DELETE FROM portfolios WHERE id=?", (pid,))
    con.commit()
    cur.close(); con.close()


# ── INVESTMENTS ───────────────────────────────────────────────────────────────

def get_investments(portfolio_id: str) -> list:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM investments WHERE portfolio_id=? ORDER BY created_at ASC",
                (portfolio_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); con.close()
    return rows

def save_investment(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT id FROM investments WHERE id=?", (rid,))
    if cur.fetchone():
        cur.execute("""UPDATE investments SET type=?,symbol=?,name=?,qty=?,cost_price=?,
                       current_price=?,note=? WHERE id=?""",
                    (record.get("type",""), record.get("symbol",""), record.get("name",""),
                     float(record.get("qty",0)), float(record.get("cost",0)),
                     float(record.get("price",0)), record.get("note",""), rid))
    else:
        cur.execute("""INSERT INTO investments (id,portfolio_id,type,symbol,name,qty,cost_price,current_price,note,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (rid, record.get("portfolio_id",""), record.get("type",""),
                     record.get("symbol",""), record.get("name",""),
                     float(record.get("qty",0)), float(record.get("cost",0)),
                     float(record.get("price",0)), record.get("note",""), now))
    con.commit()
    cur.close(); con.close()
    return {"id": rid}

def delete_investment(iid: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM investments WHERE id=?", (iid,))
    con.commit()
    cur.close(); con.close()


# ── DIVIDENDS ─────────────────────────────────────────────────────────────────

def get_dividends(portfolio_id: str) -> list:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM dividends WHERE portfolio_id=? ORDER BY date DESC",
                (portfolio_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); con.close()
    return rows

def save_dividend(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT id FROM dividends WHERE id=?", (rid,))
    if cur.fetchone():
        cur.execute("UPDATE dividends SET date=?,amount=?,note=?,symbol=?,type=? WHERE id=?",
                    (record.get("date",""), float(record.get("amount",0)),
                     record.get("note",""), record.get("symbol",""),
                     record.get("type",""), rid))
    else:
        cur.execute("""INSERT INTO dividends (id,portfolio_id,date,amount,note,symbol,type,created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (rid, record.get("portfolio_id",""), record.get("date",""),
                     float(record.get("amount",0)), record.get("note",""),
                     record.get("symbol",""), record.get("type",""), now))
    con.commit()
    cur.close(); con.close()
    return {"id": rid}

def delete_dividend(did: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM dividends WHERE id=?", (did,))
    con.commit()
    cur.close(); con.close()


# ── TARGETS ───────────────────────────────────────────────────────────────────

def get_targets(portfolio_id: str) -> dict:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT data FROM inv_targets WHERE portfolio_id=?", (portfolio_id,))
    row = cur.fetchone()
    cur.close(); con.close()
    return json.loads(row["data"]) if row else {}

def save_targets(portfolio_id: str, data: dict):
    now = datetime.now().isoformat()
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT portfolio_id FROM inv_targets WHERE portfolio_id=?", (portfolio_id,))
    if cur.fetchone():
        cur.execute("UPDATE inv_targets SET data=?,updated_at=? WHERE portfolio_id=?",
                    (json.dumps(data), now, portfolio_id))
    else:
        cur.execute("INSERT INTO inv_targets (portfolio_id,data,updated_at) VALUES (?,?,?)",
                    (portfolio_id, json.dumps(data), now))
    con.commit()
    cur.close(); con.close()


# ── SANDBOX TODOS ─────────────────────────────────────────────────────────────

def get_todos() -> list:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM sandbox_todos ORDER BY created_at ASC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); con.close()
    for r in rows:
        r["done"] = bool(r["done"])
    return rows

def add_todo(text: str) -> dict:
    now = datetime.now().isoformat()
    tid = str(int(datetime.now().timestamp() * 1000))
    con = _connect()
    cur = con.cursor()
    cur.execute("INSERT INTO sandbox_todos (id,text,done,created_at) VALUES (?,?,0,?)",
                (tid, text, now))
    con.commit()
    cur.close(); con.close()
    return {"id": tid}

def toggle_todo(tid: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("UPDATE sandbox_todos SET done = 1 - done WHERE id=?", (tid,))
    con.commit()
    cur.close(); con.close()

def delete_todo(tid: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM sandbox_todos WHERE id=?", (tid,))
    con.commit()
    cur.close(); con.close()
