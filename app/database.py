import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("orders.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone       TEXT NOT NULL,
                address     TEXT NOT NULL,
                items       TEXT NOT NULL,
                notes       TEXT DEFAULT '',
                total_price REAL DEFAULT 0,
                status      TEXT DEFAULT 'pending',
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()


def place_order(customer_name: str, phone: str, address: str, items: list, notes: str = "") -> int:
    total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO orders (customer_name, phone, address, items, notes, total_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_name, phone, address, json.dumps(items, ensure_ascii=False), notes, round(total, 2)),
        )
        conn.commit()
        return cursor.lastrowid


def get_orders() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def update_order_status(order_id: int, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()


def get_stats() -> dict:
    with get_conn() as conn:
        today = datetime.now().strftime("%Y-%m-%d")

        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        today_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        total_revenue = conn.execute(
            "SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status != 'cancelled'"
        ).fetchone()[0]
        pending_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'pending'"
        ).fetchone()[0]

        daily_rows = conn.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM orders
            WHERE DATE(created_at) >= DATE('now', '-6 days')
            GROUP BY day
            ORDER BY day
        """).fetchall()

        all_items_rows = conn.execute(
            "SELECT items FROM orders WHERE status != 'cancelled'"
        ).fetchall()
        product_counts: dict[str, int] = {}
        for row in all_items_rows:
            for item in json.loads(row[0]):
                name = item.get("name_ar") or item.get("name_en", "غير معروف")
                qty = item.get("quantity", 1)
                product_counts[name] = product_counts.get(name, 0) + qty

        top_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_orders": total_orders,
            "today_orders": today_orders,
            "total_revenue": round(total_revenue, 2),
            "pending_orders": pending_orders,
            "daily_orders": [{"day": r["day"], "count": r["count"]} for r in daily_rows],
            "top_products": [{"name": p[0], "count": p[1]} for p in top_products],
        }
