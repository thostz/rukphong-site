"""User authentication via PostgreSQL — login, register, session."""

import os
import hashlib
import secrets
from datetime import datetime

import psycopg2
import psycopg2.extras


def _connect():
    url = os.environ["DATABASE_URL"]
    # Render uses postgres:// but psycopg2 needs postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    con = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    return con


def init_db():
    """Create tables + seed admin user on first run."""
    con = _connect()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           SERIAL PRIMARY KEY,
            email        TEXT    UNIQUE NOT NULL,
            name         TEXT    NOT NULL,
            password_hash TEXT   NOT NULL,
            role         TEXT    NOT NULL DEFAULT 'user',
            created_at   TEXT    NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            created_at TEXT    NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id         SERIAL PRIMARY KEY,
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
    cur.execute("SELECT id FROM users WHERE email=%s", ("admin@rukphong.com",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (email,name,password_hash,role,created_at) VALUES (%s,%s,%s,%s,%s)",
            ("admin@rukphong.com", "Rukphong",
             _hash("admin123"), "admin",
             datetime.now().isoformat())
        )
        con.commit()

    cur.close()
    con.close()


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register(email: str, name: str, password: str) -> dict:
    email = email.strip().lower()
    if not email or not name or not password:
        return {"ok": False, "error": "กรุณากรอกข้อมูลให้ครบ"}
    if len(password) < 6:
        return {"ok": False, "error": "Password ต้องมีอย่างน้อย 6 ตัวอักษร"}
    try:
        con = _connect()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO users (email,name,password_hash,role,created_at) VALUES (%s,%s,%s,%s,%s)",
            (email, name.strip(), _hash(password), "user",
             datetime.now().isoformat())
        )
        con.commit()
        cur.close()
        con.close()
        return {"ok": True}
    except psycopg2.errors.UniqueViolation:
        return {"ok": False, "error": "Email นี้มีผู้ใช้แล้ว"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    con = _connect()
    cur = con.cursor()
    cur.execute(
        "SELECT id,name,role FROM users WHERE email=%s AND password_hash=%s",
        (email, _hash(password))
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        con.close()
        return {"ok": False, "error": "Email หรือ Password ไม่ถูกต้อง"}

    token = secrets.token_hex(32)
    cur.execute(
        "INSERT INTO sessions (token,user_id,created_at) VALUES (%s,%s,%s)",
        (token, row["id"], datetime.now().isoformat())
    )
    con.commit()
    cur.close()
    con.close()
    return {"ok": True, "token": token, "name": row["name"], "role": row["role"]}


def verify_token(token: str) -> dict | None:
    if not token:
        return None
    con = _connect()
    cur = con.cursor()
    cur.execute("""
        SELECT u.id, u.name, u.email, u.role
        FROM sessions s JOIN users u ON s.user_id=u.id
        WHERE s.token=%s
    """, (token,))
    row = cur.fetchone()
    cur.close()
    con.close()
    return dict(row) if row else None


def logout(token: str):
    con = _connect()
    cur = con.cursor()
    cur.execute("DELETE FROM sessions WHERE token=%s", (token,))
    con.commit()
    cur.close()
    con.close()


def save_contact(name: str, email: str, company: str,
                 subject: str, message: str) -> dict:
    try:
        con = _connect()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO contacts (name,email,company,subject,message,created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            (name, email, company, subject, message, datetime.now().isoformat())
        )
        con.commit()
        cur.close()
        con.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_contacts() -> list[dict]:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT * FROM contacts ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    con.close()
    return rows


def list_users() -> list[dict]:
    con = _connect()
    cur = con.cursor()
    cur.execute("SELECT id,email,name,role,created_at FROM users ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    con.close()
    return rows
