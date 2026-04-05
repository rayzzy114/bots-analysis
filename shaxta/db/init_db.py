import aiosqlite

from config import DEFAULT_COMMISSION, PAYMENT_BANK, payment_details, OPERATOR


async def init_db():
    default_requisites = payment_details or ""
    default_bank = PAYMENT_BANK or ""
    default_commission = max(0.0, float(DEFAULT_COMMISSION))
    default_commission_sql = f"{default_commission:.6f}"
    default_operator = OPERATOR or ""

    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                card TEXT
            )
        """)
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                requisites TEXT,
                bank TEXT,
                commission REAL DEFAULT {default_commission_sql},
                operator TEXT
            )
        """)

        cursor = await db.execute("PRAGMA table_info(settings)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "commission" not in columns:
            await db.execute("ALTER TABLE settings ADD COLUMN commission REAL")
            await db.execute(
                "UPDATE settings SET commission = ? WHERE id = 1",
                (default_commission,),
            )
        if "operator" not in columns:
            await db.execute("ALTER TABLE settings ADD COLUMN operator TEXT")
            await db.execute(
                "UPDATE settings SET operator = ? WHERE id = 1",
                (default_operator,),
            )

        cursor = await db.execute("SELECT COUNT(*) FROM settings")
        count_row = await cursor.fetchone()
        count = count_row[0] if count_row else 0
        if count == 0:
            await db.execute("""
                INSERT INTO settings (id, requisites, bank, commission, operator)
                VALUES (1, ?, ?, ?, ?)
            """, (default_requisites, default_bank, default_commission, default_operator))
        else:
            await db.execute("""
                UPDATE settings
                SET commission = COALESCE(commission, ?),
                    operator = COALESCE(operator, ?)
                WHERE id = 1
            """, (default_commission, default_operator))

        await db.commit()
