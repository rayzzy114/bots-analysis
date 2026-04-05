import aiosqlite

from config import DEFAULT_COMMISSION, PAYMENT_BANK, payment_details, OPERATOR


async def get_operator() -> str:
    """
    Returns operator username from database settings.
    Falls back to OPERATOR env var if not set in DB.
    """
    default_operator = OPERATOR or ""
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT operator FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        if result and result[0]:
            return result[0]
        return default_operator


async def update_operator(operator: str) -> None:
    """Updates operator username in database settings."""
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            UPDATE settings
            SET operator = ?
            WHERE id = 1
        """, (operator,))
        await db.commit()


async def get_requisites() -> str:
    default_requisites = payment_details or ""
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT requisites FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        return result[0] if result and result[0] else default_requisites

async def get_bank() -> str:
    default_bank = PAYMENT_BANK or ""
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT bank FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        return result[0] if result and result[0] else default_bank


async def get_commission() -> float:
    default_commission = max(0.0, float(DEFAULT_COMMISSION))
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT commission FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        if not result or result[0] is None:
            return default_commission
        try:
            return max(0.0, float(result[0]))
        except (TypeError, ValueError):
            return default_commission

async def update_requisites(requisites: str):
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            UPDATE settings
            SET requisites = ?
            WHERE id = 1
        """, (requisites,))
        await db.commit()

async def update_bank(bank: str):
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            UPDATE settings
            SET bank = ?
            WHERE id = 1
        """, (bank,))
        await db.commit()


async def update_commission(commission: float):
    normalized = max(0.0, float(commission))
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            UPDATE settings
            SET commission = ?
            WHERE id = 1
        """, (normalized,))
        await db.commit()
