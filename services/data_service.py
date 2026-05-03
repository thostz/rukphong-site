"""SQLite CRUD for Expense, Notes, Tasks, Investment (portfolios/investments/dividends/targets)."""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "users.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_data_tables():
    with _connect() as con:
        con.execute("""
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
        con.execute("""
            CREATE TABLE IF NOT EXISTS notes_tb (
                id         TEXT PRIMARY KEY,
                title      TEXT,
                content    TEXT,
                category   TEXT,
                date       TEXT,
                created_at TEXT
            )
        """)
        con.execute("""
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
        con.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                created_at TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS investments (
                id           TEXT PRIMARY KEY,
                portfolio_id TEXT,
                type         TEXT,
                symbol       TEXT,
                name         TEXT,
                qty          REAL DEFAULT 0,
                cost_price   REAL DEFAULT 0,
                current_price REAL DEFAULT 0,
                note         TEXT,
                created_at   TEXT,
                FOREIGN KEY(portfolio_id) REFERENCES portfolios(id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS dividends (
                id           TEXT PRIMARY KEY,
                portfolio_id TEXT,
                date         TEXT,
                amount       REAL DEFAULT 0,
                note         TEXT,
                symbol       TEXT,
                type         TEXT,
                created_at   TEXT,
                FOREIGN KEY(portfolio_id) REFERENCES portfolios(id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS inv_targets (
                portfolio_id TEXT PRIMARY KEY,
                data         TEXT,
                updated_at   TEXT,
                FOREIGN KEY(portfolio_id) REFERENCES portfolios(id)
            )
        """)
        con.commit()


# ── EXPENSES ──────────────────────────────────────────────────────────────────

def get_expenses() -> list:
    with _connect() as con:
        rows = con.execute("SELECT * FROM expenses ORDER BY date DESC, created_at DESC").fetchall()
        return [dict(r) for r in rows]

def save_expense(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    with _connect() as con:
        existing = con.execute("SELECT id FROM expenses WHERE id=?", (rid,)).fetchone()
        if existing:
            con.execute("""UPDATE expenses SET description=?,category=?,currency=?,amount=?,date=?,notes=?
                           WHERE id=?""",
                        (record.get("description",""), record.get("category",""),
                         record.get("currency","THB"), float(record.get("amount",0)),
                         record.get("date",""), record.get("notes",""), rid))
        else:
            con.execute("""INSERT INTO expenses (id,description,category,currency,amount,date,notes,created_at)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (rid, record.get("description",""), record.get("category",""),
                         record.get("currency","THB"), float(record.get("amount",0)),
                         record.get("date",""), record.get("notes",""), now))
        con.commit()
    return {"id": rid}

def delete_expense(eid: str):
    with _connect() as con:
        con.execute("DELETE FROM expenses WHERE id=?", (eid,))
        con.commit()


# ── NOTES ─────────────────────────────────────────────────────────────────────

def get_notes() -> list:
    with _connect() as con:
        rows = con.execute("SELECT * FROM notes_tb ORDER BY date DESC, created_at DESC").fetchall()
        return [dict(r) for r in rows]

def save_note(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    with _connect() as con:
        existing = con.execute("SELECT id FROM notes_tb WHERE id=?", (rid,)).fetchone()
        if existing:
            con.execute("UPDATE notes_tb SET title=?,content=?,category=?,date=? WHERE id=?",
                        (record.get("title",""), record.get("content",""),
                         record.get("category",""), record.get("date",""), rid))
        else:
            con.execute("""INSERT INTO notes_tb (id,title,content,category,date,created_at)
                           VALUES (?,?,?,?,?,?)""",
                        (rid, record.get("title",""), record.get("content",""),
                         record.get("category",""), record.get("date",""), now))
        con.commit()
    return {"id": rid}

def delete_note(nid: str):
    with _connect() as con:
        con.execute("DELETE FROM notes_tb WHERE id=?", (nid,))
        con.commit()


# ── TASKS ─────────────────────────────────────────────────────────────────────

def get_tasks() -> list:
    with _connect() as con:
        rows = con.execute("SELECT * FROM tasks ORDER BY due ASC, created_at DESC").fetchall()
        return [dict(r) for r in rows]

def save_task(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    with _connect() as con:
        existing = con.execute("SELECT id FROM tasks WHERE id=?", (rid,)).fetchone()
        if existing:
            con.execute("""UPDATE tasks SET title=?,priority=?,status=?,due=?,notes=?,updated_at=?
                           WHERE id=?""",
                        (record.get("title",""), record.get("priority",""),
                         record.get("status",""), record.get("due",""),
                         record.get("notes",""), now, rid))
        else:
            con.execute("""INSERT INTO tasks (id,title,priority,status,due,notes,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (rid, record.get("title",""), record.get("priority",""),
                         record.get("status",""), record.get("due",""),
                         record.get("notes",""), now, now))
        con.commit()
    return {"id": rid}

def delete_task(tid: str):
    with _connect() as con:
        con.execute("DELETE FROM tasks WHERE id=?", (tid,))
        con.commit()


# ── PORTFOLIOS ────────────────────────────────────────────────────────────────

def get_portfolios() -> list:
    with _connect() as con:
        rows = con.execute("SELECT * FROM portfolios ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]

def save_portfolio(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    with _connect() as con:
        existing = con.execute("SELECT id FROM portfolios WHERE id=?", (rid,)).fetchone()
        if existing:
            con.execute("UPDATE portfolios SET name=? WHERE id=?", (record.get("name",""), rid))
        else:
            con.execute("INSERT INTO portfolios (id,name,created_at) VALUES (?,?,?)",
                        (rid, record.get("name",""), now))
        con.commit()
    return {"id": rid}

def delete_portfolio(pid: str):
    with _connect() as con:
        con.execute("DELETE FROM investments WHERE portfolio_id=?", (pid,))
        con.execute("DELETE FROM dividends WHERE portfolio_id=?", (pid,))
        con.execute("DELETE FROM inv_targets WHERE portfolio_id=?", (pid,))
        con.execute("DELETE FROM portfolios WHERE id=?", (pid,))
        con.commit()


# ── INVESTMENTS ───────────────────────────────────────────────────────────────

def get_investments(portfolio_id: str) -> list:
    with _connect() as con:
        rows = con.execute("SELECT * FROM investments WHERE portfolio_id=? ORDER BY created_at ASC",
                           (portfolio_id,)).fetchall()
        return [dict(r) for r in rows]

def save_investment(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    with _connect() as con:
        existing = con.execute("SELECT id FROM investments WHERE id=?", (rid,)).fetchone()
        if existing:
            con.execute("""UPDATE investments SET type=?,symbol=?,name=?,qty=?,cost_price=?,
                           current_price=?,note=? WHERE id=?""",
                        (record.get("type",""), record.get("symbol",""), record.get("name",""),
                         float(record.get("qty",0)), float(record.get("cost",0)),
                         float(record.get("price",0)), record.get("note",""), rid))
        else:
            con.execute("""INSERT INTO investments (id,portfolio_id,type,symbol,name,qty,cost_price,current_price,note,created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (rid, record.get("portfolio_id",""), record.get("type",""),
                         record.get("symbol",""), record.get("name",""),
                         float(record.get("qty",0)), float(record.get("cost",0)),
                         float(record.get("price",0)), record.get("note",""), now))
        con.commit()
    return {"id": rid}

def delete_investment(iid: str):
    with _connect() as con:
        con.execute("DELETE FROM investments WHERE id=?", (iid,))
        con.commit()


# ── DIVIDENDS ─────────────────────────────────────────────────────────────────

def get_dividends(portfolio_id: str) -> list:
    with _connect() as con:
        rows = con.execute("SELECT * FROM dividends WHERE portfolio_id=? ORDER BY date DESC",
                           (portfolio_id,)).fetchall()
        return [dict(r) for r in rows]

def save_dividend(record: dict) -> dict:
    now = datetime.now().isoformat()
    rid = record.get("id") or str(int(datetime.now().timestamp() * 1000))
    with _connect() as con:
        existing = con.execute("SELECT id FROM dividends WHERE id=?", (rid,)).fetchone()
        if existing:
            con.execute("UPDATE dividends SET date=?,amount=?,note=?,symbol=?,type=? WHERE id=?",
                        (record.get("date",""), float(record.get("amount",0)),
                         record.get("note",""), record.get("symbol",""),
                         record.get("type",""), rid))
        else:
            con.execute("""INSERT INTO dividends (id,portfolio_id,date,amount,note,symbol,type,created_at)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (rid, record.get("portfolio_id",""), record.get("date",""),
                         float(record.get("amount",0)), record.get("note",""),
                         record.get("symbol",""), record.get("type",""), now))
        con.commit()
    return {"id": rid}

def delete_dividend(did: str):
    with _connect() as con:
        con.execute("DELETE FROM dividends WHERE id=?", (did,))
        con.commit()


# ── TARGETS ───────────────────────────────────────────────────────────────────

def get_targets(portfolio_id: str) -> dict:
    with _connect() as con:
        row = con.execute("SELECT data FROM inv_targets WHERE portfolio_id=?",
                          (portfolio_id,)).fetchone()
        return json.loads(row["data"]) if row else {}

def save_targets(portfolio_id: str, data: dict):
    now = datetime.now().isoformat()
    with _connect() as con:
        existing = con.execute("SELECT portfolio_id FROM inv_targets WHERE portfolio_id=?",
                               (portfolio_id,)).fetchone()
        if existing:
            con.execute("UPDATE inv_targets SET data=?,updated_at=? WHERE portfolio_id=?",
                        (json.dumps(data), now, portfolio_id))
        else:
            con.execute("INSERT INTO inv_targets (portfolio_id,data,updated_at) VALUES (?,?,?)",
                        (portfolio_id, json.dumps(data), now))
        con.commit()
