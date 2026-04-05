import aiosqlite

async def add_user(user_id: int, card: str = ""):
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        exists = await cursor.fetchone()

        if not exists:
            await db.execute("""
                INSERT INTO users (id, balance, card)
                VALUES (?, ?, ?)
            """, (user_id, 0, card))
            await db.commit()

async def update_user_card(user_id: int, card: str):
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            UPDATE users
            SET card = ?
            WHERE id = ?
        """, (card, user_id))
        await db.commit()

async def get_user_card(user_id: int) -> str:
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT card FROM users WHERE id = ?", (user_id,))
        result = await cursor.fetchone()
        return result[0] if result and result[0] else "не указан"
