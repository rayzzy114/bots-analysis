import json
import random

import aiohttp
import aiosqlite

from config import bank, requisites

DB_PATH = "users.db"

DEFAULT_PAYMENT_METHODS = [
    {"name": "💳 СБП", "requisites": "", "bank": ""},
    {"name": "Газпромбанк ➡️ Газпромбанк", "requisites": "", "bank": ""},
    {"name": "ВТБ ➡️ ВТБ", "requisites": "", "bank": ""},
    {"name": "Сбер ➡️ Сбер", "requisites": "", "bank": ""},
    {"name": "Тинькофф ➡️ Тинькофф", "requisites": "", "bank": ""},
    {"name": "Трансгран перевод", "requisites": "", "bank": ""}
]

DEFAULT_COMMISSION = 30


async def get_cbr_usd_rate() -> float:
    """Fetch USD/RUB rate from Central Bank of Russia."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    import json
                    data = json.loads(await response.text())
                    return float(data["Valute"]["USD"]["Value"])
    except Exception as e:
        print(f"❌ CBR ошибка: {e}")
    return 90.0


async def get_ltc_rates() -> tuple:
    """Get LTC rates: try Binance first, then CoinGecko, then .env fallback."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "https://api.binance.com/api/v3/ticker/price?symbol=LTCUSDT",
                    timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    usd = float(data.get("price", 0))
                    if usd > 0:
                        rub = await get_cbr_usd_rate() * usd
                        print(f"✅ Binance LTC: ${usd}, ₽{rub:.0f}")
                        return (usd, rub)
    except Exception as e:
        print(f"Binance LTC ошибка: {e}")

    # Fallback to CoinGecko
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd,rub"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    ltc = data.get("litecoin", {})
                    usd = float(ltc.get("usd", 0))
                    rub = float(ltc.get("rub", 0))
                    if usd > 0 and rub > 0:
                        print(f"✅ CoinGecko LTC: ${usd}, ₽{rub:.0f}")
                        return (usd, rub)
    except Exception as e:
        print(f"❌ CoinGecko LTC ошибка: {e}")

    from config import LTC_RATE_RUB, LTC_RATE_USD
    return (LTC_RATE_USD, LTC_RATE_RUB)


async def get_btc_rates() -> tuple:
    """Get BTC rates: try Binance first, then CoinGecko, then .env fallback."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                    timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    usd = float(data.get("price", 0))
                    if usd > 0:
                        rub = await get_cbr_usd_rate() * usd
                        print(f"✅ Binance BTC: ${usd}, ₽{rub:.0f}")
                        return (usd, rub)
    except Exception as e:
        print(f"Binance BTC ошибка: {e}")

    # Fallback to CoinGecko
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,rub"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    btc = data.get("bitcoin", {})
                    usd = float(btc.get("usd", 0))
                    rub = float(btc.get("rub", 0))
                    if usd > 0 and rub > 0:
                        print(f"✅ CoinGecko BTC: ${usd}, ₽{rub:.0f}")
                        return (usd, rub)
    except Exception as e:
        print(f"❌ CoinGecko BTC ошибка: {e}")

    from config import BTC_RATE_RUB, BTC_RATE_USD
    return (BTC_RATE_USD, BTC_RATE_RUB)


async def init_settings_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                requisites TEXT,
                bank TEXT,
                payment_methods TEXT DEFAULT '[]',
                commission INTEGER DEFAULT 30,
                requisites_mode INTEGER DEFAULT 0
            )
        """)

        cursor = await db.execute("SELECT id FROM settings WHERE id = 1")
        if not await cursor.fetchone():
            await db.execute(
                """INSERT INTO settings (id, requisites, bank, payment_methods, commission, requisites_mode) 
                   VALUES (1, ?, ?, ?, ?, 0)""",
                (requisites or "", bank or "", json.dumps(DEFAULT_PAYMENT_METHODS, ensure_ascii=False),
                 DEFAULT_COMMISSION)
            )
            await db.commit()
            return

        cursor = await db.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "payment_methods" not in columns:
            await db.execute("ALTER TABLE settings ADD COLUMN payment_methods TEXT DEFAULT '[]'")
        if "commission" not in columns:
            await db.execute(f"ALTER TABLE settings ADD COLUMN commission INTEGER DEFAULT {DEFAULT_COMMISSION}")
        if "requisites_mode" not in columns:
            await db.execute("ALTER TABLE settings ADD COLUMN requisites_mode INTEGER DEFAULT 0")

        cursor = await db.execute("SELECT payment_methods FROM settings WHERE id = 1")
        result = await cursor.fetchone()

        need_update = False
        methods = []

        if result and result[0]:
            try:
                methods = json.loads(result[0])
                if methods and isinstance(methods[0], str):
                    methods = [{"name": m, "requisites": "", "bank": ""} for m in methods]
                    need_update = True
                elif methods and "bank" not in methods[0]:
                    for m in methods:
                        m["bank"] = ""
                    need_update = True
            except Exception:
                methods = []
                need_update = True
        else:
            need_update = True

        if not methods:
            methods = DEFAULT_PAYMENT_METHODS.copy()
            need_update = True

        if need_update:
            await db.execute(
                "UPDATE settings SET payment_methods = ? WHERE id = 1",
                (json.dumps(methods, ensure_ascii=False),)
            )

        await db.commit()


async def get_commission() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT commission FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        return result[0] if result and result[0] is not None else DEFAULT_COMMISSION


async def set_commission(commission: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE settings SET commission = ? WHERE id = 1", (commission,))
        await db.commit()


async def get_requisites() -> str:
    default_requisites = requisites or ""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT requisites FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        return result[0] if result and result[0] else default_requisites


async def get_bank() -> str:
    default_bank = bank or ""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT bank FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        return result[0] if result and result[0] else default_bank


async def update_requisites(new_requisites: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE settings SET requisites = ? WHERE id = 1", (new_requisites,))
        await db.commit()


async def update_bank(new_bank: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE settings SET bank = ? WHERE id = 1", (new_bank,))
        await db.commit()


async def get_requisites_mode() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT requisites_mode FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        return result[0] if result and result[0] is not None else 0


async def set_requisites_mode(mode: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE settings SET requisites_mode = ? WHERE id = 1", (mode,))
        await db.commit()


async def get_payment_methods() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        cursor = await db.execute("SELECT payment_methods FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        if result and result[0]:
            try:
                methods = json.loads(result[0])
                if isinstance(methods, list):
                    if len(methods) > 0 and isinstance(methods[0], str):
                        return [{"name": m, "requisites": "", "bank": ""} for m in methods]
                    return methods
            except Exception as e:
                print(f'Exception caught: {e}')
        return DEFAULT_PAYMENT_METHODS.copy()


async def add_payment_method(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        cursor = await db.execute("SELECT payment_methods FROM settings WHERE id = 1")
        result = await cursor.fetchone()

        methods = []
        if result and result[0]:
            try:
                loaded = json.loads(result[0])
                if isinstance(loaded, list):
                    methods = loaded
            except Exception as e:
                print(f'Exception caught: {e}')

        methods.append({"name": name, "requisites": "", "bank": ""})

        await db.execute(
            "UPDATE settings SET payment_methods = ? WHERE id = 1",
            (json.dumps(methods, ensure_ascii=False),)
        )
        await db.commit()


async def remove_payment_method(index: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        cursor = await db.execute("SELECT payment_methods FROM settings WHERE id = 1")
        result = await cursor.fetchone()

        if not result or not result[0]:
            return

        try:
            methods = json.loads(result[0])
        except Exception:
            return

        if not isinstance(methods, list) or index < 0 or index >= len(methods):
            return

        methods.pop(index)

        await db.execute(
            "UPDATE settings SET payment_methods = ? WHERE id = 1",
            (json.dumps(methods, ensure_ascii=False),)
        )
        await db.commit()


async def update_method_requisites(index: int, new_requisites: str, new_bank: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        cursor = await db.execute("SELECT payment_methods FROM settings WHERE id = 1")
        result = await cursor.fetchone()

        if not result or not result[0]:
            return

        try:
            methods = json.loads(result[0])
        except Exception:
            return

        if not isinstance(methods, list) or index < 0 or index >= len(methods):
            return

        methods[index]["requisites"] = new_requisites
        methods[index]["bank"] = new_bank

        await db.execute(
            "UPDATE settings SET payment_methods = ? WHERE id = 1",
            (json.dumps(methods, ensure_ascii=False),)
        )
        await db.commit()


async def get_method_requisites(index: int) -> tuple:
    methods = await get_payment_methods()
    if 0 <= index < len(methods):
        req = methods[index].get("requisites", "")
        bank_name = methods[index].get("bank", "")
        if req:
            return (req, bank_name)

    available = [(m.get("requisites", ""), m.get("bank", "")) for m in methods if m.get("requisites", "")]
    if available:
        return random.choice(available)

    default_req = await get_requisites()
    default_bank = await get_bank()
    return (default_req, default_bank)
