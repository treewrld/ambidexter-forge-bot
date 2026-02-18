import sqlite3
from pathlib import Path
from typing import Optional, List

DB_PATH = Path("database.sqlite3")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            username TEXT,
            name TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            type TEXT,
            service_code TEXT,
            title TEXT,
            description TEXT,
            budget TEXT,
            deadline TEXT,
            contact_method TEXT,
            contact_value TEXT,
            status TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
        """
    )

    # ====== ЧЁРНЫЙ СПИСОК ======
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS banned_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
        """
    )

    # ====== ПОПЫТКИ КАПЧИ ======
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS captcha_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            attempts INTEGER DEFAULT 0,
            last_attempt_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ====== ЗАЯВКИ НА РАЗБАН ======
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS unban_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


def get_or_create_client(tg_id: int, username: Optional[str], name: Optional[str]) -> int:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM clients WHERE tg_id = ?", (tg_id,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row["id"]

    cur.execute(
        "INSERT INTO clients (tg_id, username, name) VALUES (?, ?, ?)",
        (tg_id, username, name),
    )
    conn.commit()
    client_id = cur.lastrowid
    conn.close()
    return client_id


def add_order(
    client_id: int,
    type_: str,
    service_code: Optional[str],
    title: Optional[str],
    description: str,
    budget: Optional[str],
    deadline: Optional[str],
    contact_method: str,
    contact_value: str,
) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO orders (
            client_id, type, service_code, title, description,
            budget, deadline, contact_method, contact_value, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """,
        (
            client_id,
            type_,
            service_code,
            title,
            description,
            budget,
            deadline,
            contact_method,
            contact_value,
        ),
    )
    conn.commit()
    order_id = cur.lastrowid
    conn.close()
    return order_id


def get_orders_page(page: int, per_page: int = 3):
    offset = (page - 1) * per_page
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS cnt FROM orders")
    total = cur.fetchone()["cnt"]

    cur.execute(
        """
        SELECT o.*, c.name AS client_name
        FROM orders o
        LEFT JOIN clients c ON c.id = o.client_id
        ORDER BY o.id DESC
        LIMIT ? OFFSET ?
        """,
        (per_page, offset),
    )
    rows = cur.fetchall()
    conn.close()
    return rows, total


def get_order_by_id(order_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.*, c.name AS client_name, c.tg_id AS client_tg_id
        FROM orders o
        LEFT JOIN clients c ON c.id = o.client_id
        WHERE o.id = ?
        """,
        (order_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def update_order_status(order_id: int, status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


# ====== ЧЁРНЫЙ СПИСОК / БАН ======

def is_user_banned(tg_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT active FROM banned_users WHERE tg_id = ?",
        (tg_id,),
    )
    row = cur.fetchone()
    conn.close()
    return bool(row and row["active"] == 1)


def get_ban_reason(tg_id: int) -> Optional[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT reason FROM banned_users WHERE tg_id = ? AND active = 1",
        (tg_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row["reason"] if row else None


def ban_user(tg_id: int, reason: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO banned_users (tg_id, reason, active)
        VALUES (?, ?, 1)
        ON CONFLICT(tg_id) DO UPDATE SET reason = excluded.reason, active = 1
        """,
        (tg_id, reason),
    )
    conn.commit()
    conn.close()


def unban_user(tg_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE banned_users SET active = 0 WHERE tg_id = ?",
        (tg_id,),
    )
    conn.commit()
    conn.close()


def get_banned_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM banned_users WHERE active = 1 ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ====== ПОПЫТКИ КАПЧИ ======

def get_captcha_attempts(tg_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT attempts FROM captcha_attempts WHERE tg_id = ?",
        (tg_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row["attempts"] if row else 0


def increment_captcha_attempts(tg_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO captcha_attempts (tg_id, attempts)
        VALUES (?, 1)
        ON CONFLICT(tg_id) DO UPDATE SET attempts = attempts + 1
        """,
        (tg_id,),
    )
    conn.commit()
    cur.execute(
        "SELECT attempts FROM captcha_attempts WHERE tg_id = ?",
        (tg_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row["attempts"] if row else 0


def reset_captcha_attempts(tg_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM captcha_attempts WHERE tg_id = ?",
        (tg_id,),
    )
    conn.commit()
    conn.close()


# ====== ЗАЯВКИ НА РАЗБАН ======

def add_unban_request(tg_id: int, reason: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO unban_requests (tg_id, reason, status)
        VALUES (?, ?, 'pending')
        """,
        (tg_id, reason),
    )
    conn.commit()
    conn.close()


def get_unban_requests(status: str = "pending"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM unban_requests WHERE status = ? ORDER BY created_at DESC",
        (status,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def update_unban_request_status(request_id: int, status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE unban_requests SET status = ? WHERE id = ?",
        (status, request_id),
    )
    conn.commit()
    conn.close()
