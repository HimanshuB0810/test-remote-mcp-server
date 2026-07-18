from fastmcp import FastMCP
import os
import sqlite3
import traceback

DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("ExpenseTracker")


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
        """)
        c.commit()


init_db()


@mcp.tool
def add_expense(date, amount, category, subcategory="", note=""):
    """
    Add a new expense entry to the database.
    """
    try:
        with sqlite3.connect(DB_PATH) as c:
            cur = c.execute(
                """
                INSERT INTO expenses(date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note),
            )

            c.commit()

            return {
                "status": "ok",
                "id": cur.lastrowid
            }

    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@mcp.tool
def list_expenses(start_date, end_date):
    """
    List all expense entries within an inclusive date range.
    """
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT
                id,
                date,
                amount,
                category,
                subcategory,
                note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date),
        )

        cols = [d[0] for d in cur.description]

        return [
            dict(zip(cols, row))
            for row in cur.fetchall()
        ]


@mcp.tool
def summarize_expenses(start_date, end_date):
    """
    Summarize expenses within an inclusive date range.
    Returns total spending, transaction count,
    and category-wise totals.
    """
    with sqlite3.connect(DB_PATH) as c:

        cur = c.execute(
            """
            SELECT
                COUNT(*) AS total_transactions,
                COALESCE(SUM(amount), 0) AS total_spent
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        )

        total_transactions, total_spent = cur.fetchone()

        cur = c.execute(
            """
            SELECT
                category,
                COUNT(*) AS transactions,
                SUM(amount) AS total
            FROM expenses
            WHERE date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (start_date, end_date),
        )

        categories = [
            {
                "category": row[0],
                "transactions": row[1],
                "total": row[2],
            }
            for row in cur.fetchall()
        ]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_transactions": total_transactions,
        "total_spent": total_spent,
        "category_summary": categories,
    }


@mcp.tool
def debug_db():
    """
    Debug database permissions and location.
    """
    return {
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
        "db_readable": os.access(DB_PATH, os.R_OK),
        "db_writable": os.access(DB_PATH, os.W_OK),
        "directory": os.path.dirname(DB_PATH),
        "directory_exists": os.path.exists(os.path.dirname(DB_PATH)),
        "directory_writable": os.access(os.path.dirname(DB_PATH), os.W_OK),
    }


@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
    )