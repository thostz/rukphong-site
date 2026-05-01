"""User authentication via SQLite — login, register, session."""

import sqlite3
import os
import hashlib
import secrets
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "users.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    """Create tables + seed admin user on first run."""
    with _connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email        TEXT    UNIQUE NOT NULL,
                name         TEXT    NOT NULL,
                password_hash TEXT   NOT NULL,
                role         TEXT    NOT NULL DEFAULT 'user',
                created_at   TEXT    NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                created_at TEXT    NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL,
                company    TEXT,
                subject    TEXT,
                message    TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        con.commit()

        # Seed admin if not exists
        row = con.execute("SELECT id FROM users WHERE email=?",
                          ("admin@rukphong.com",)).fetchone()
        if not row:
            con.execute(
                "INSERT INTO users (email,name,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                ("admin@rukphong.com", "Rukphong",
                 _hash("admin123"), "admin",
                 datetime.now().isoformat())
            )
            con.commit()


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register(email: str, name: str, password: str) -> dict:
    email = email.strip().lower()
    if not email or not name or not password:
        return {"ok": False, "error": "กรุณากรอกข้อมูลให้ครบ"}
    if len(password) < 6:
        return {"ok": False, "error": "Password ต้องมีอย่างน้อย 6 ตัวอักษร"}
    try:
        with _connect() as con:
            con.execute(
                "INSERT INTO users (email,name,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                (email, name.strip(), _hash(password), "user",
                 datetime.now().isoformat())
            )
            con.commit()
        return {"ok": True}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "Email นี้มีผู้ใช้แล้ว"}


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    with _connect() as con:
        row = con.execute(
            "SELECT id,name,role FROM users WHERE email=? AND password_hash=?",
            (email, _hash(password))
        ).fetchone()
        if not row:
            return {"ok": False, "error": "Email หรือ Password ไม่ถูกต้อง"}

        token = secrets.token_hex(32)
        con.execute(
            "INSERT INTO sessions (token,user_id,created_at) VALUES (?,?,?)",
            (token, row["id"], datetime.now().isoformat())
        )
        con.commit()
        return {"ok": True, "token": token,
                "name": row["name"], "role": row["role"]}


def verify_token(token: str) -> dict | None:
    if not token:
        return None
    with _connect() as con:
        row = con.execute("""
            SELECT u.id, u.name, u.email, u.role
            FROM sessions s JOIN users u ON s.user_id=u.id
            WHERE s.token=?
        """, (token,)).fetchone()
        return dict(row) if row else None


def logout(token: str):
    with _connect() as con:
        con.execute("DELETE FROM sessions WHERE token=?", (token,))
        con.commit()


def save_contact(name: str, email: str, company: str,
                 subject: str, message: str) -> dict:
    try:
        with _connect() as con:
            con.execute(
                "INSERT INTO contacts (name,email,company,subject,message,created_at) VALUES (?,?,?,?,?,?)",
                (name, email, company, subject, message, datetime.now().isoformat())
            )
            con.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_contacts() -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            "SELECT * FROM contacts ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def list_users() -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            "SELECT id,email,name,role,created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
