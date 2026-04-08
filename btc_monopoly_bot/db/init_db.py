import aiosqlite

from config import bank, requisites


async def init_db():
    default_requisites = requisites or ""
    default_bank = bank or ""

    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                card TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                requisites TEXT,
                bank TEXT
            )
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM settings")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await db.execute("""
                INSERT INTO settings (id, requisites, bank)
                VALUES (1, ?, ?)
            """, (default_requisites, default_bank))
        await db.commit()
