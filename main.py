from fastmcp import FastMCP
import os
import asyncio
import traceback
import aiosqlite

# Use a writable directory at runtime instead of the app's install directory,
# which is often read-only in containerized/serverless deployments.
# You can override this via an environment variable if your platform
# provides a specific writable/persistent volume path.
DB_DIR = os.environ.get("DATA_DIR", "/tmp")
DB_PATH = os.path.join(DB_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("ExpenseTracker")


async def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
        """)
        await db.commit()


@mcp.tool
async def add_expense(date, amount, category, subcategory="", note=""):
    """
    Add a new expense entry to the database.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                """
                INSERT INTO expenses(date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note),
            )

            await db.commit()

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
async def list_expenses(start_date, end_date):
    """
    List all expense entries within an inclusive date range.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
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

        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]

        return [
            dict(zip(cols, row))
            for row in rows
        ]


@mcp.tool
async def summarize_expenses(start_date, end_date):
    """
    Summarize expenses within an inclusive date range.
    Returns total spending, transaction count,
    and category-wise totals.
    """
    async with aiosqlite.connect(DB_PATH) as db:

        cur = await db.execute(
            """
            SELECT
                COUNT(*) AS total_transactions,
                COALESCE(SUM(amount), 0) AS total_spent
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """,
            (start_date, end_date),
        )

        total_transactions, total_spent = await cur.fetchone()

        cur = await db.execute(
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

        rows = await cur.fetchall()

        categories = [
            {
                "category": row[0],
                "transactions": row[1],
                "total": row[2],
            }
            for row in rows
        ]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_transactions": total_transactions,
        "total_spent": total_spent,
        "category_summary": categories,
    }


@mcp.tool
async def debug_db():
    """
    Debug database permissions and location.
    """
    return {
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
        "db_readable": os.access(DB_PATH, os.R_OK) if os.path.exists(DB_PATH) else None,
        "db_writable": os.access(DB_PATH, os.W_OK) if os.path.exists(DB_PATH) else None,
        "directory": DB_DIR,
        "directory_exists": os.path.exists(DB_DIR),
        "directory_writable": os.access(DB_DIR, os.W_OK),
    }


@mcp.resource("expense://categories", mime_type="application/json")
async def categories():
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    asyncio.run(init_db())

    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
    )