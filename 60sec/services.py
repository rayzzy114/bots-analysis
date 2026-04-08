import asyncio
import logging
from abc import ABC, abstractmethod

import aiosqlite
import httpx


# Models/Storage
class Storage(ABC):
    @abstractmethod
    async def get_payment_details(self, payment_method: str): ...
    @abstractmethod
    async def set_payment_details(self, payment_method: str, card_number: str, recipient_name: str, bank_name: str): ...

class SQLiteStorage(Storage):
    def __init__(self, db_path="bot.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payment_details (
                    payment_method TEXT PRIMARY KEY,
                    card_number TEXT,
                    recipient_name TEXT,
                    bank_name TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def get_payment_details(self, payment_method: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT card_number, recipient_name, bank_name FROM payment_details WHERE payment_method = ?", (payment_method,))
            row = await cursor.fetchone()
            if row:
                return {'card_number': row[0], 'recipient_name': row[1], 'bank_name': row[2]}
            return None

    async def set_payment_details(self, payment_method, card_number, recipient_name, bank_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO payment_details VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                             (payment_method, card_number, recipient_name, bank_name))
            await db.commit()

# Currency Logic
class ParsedAmount:
    def __init__(self, amount: float, currency: str):
        self.amount = amount
        self.currency = currency

class CurrencyParser:
    @staticmethod
    def parse(text: str, currency: str = "BTC") -> ParsedAmount | None:
        try:
            val = float(text.replace(',', '.').replace(' ', ''))
            return ParsedAmount(val, currency)
        except (ValueError, TypeError, AttributeError):
            return None

class RateService:
    def __init__(self):
        self.rates = {}
        self.lock = asyncio.Lock()

    async def update_rates(self):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,litecoin,monero,tether&vs_currencies=rub")
                data = resp.json()
                async with self.lock:
                    self.rates = {
                        "BTC": float(data["bitcoin"]["rub"]),
                        "LTC": float(data["litecoin"]["rub"]),
                        "XMR": float(data["monero"]["rub"]),
                        "USDT": float(data["tether"]["rub"]),
                    }
        except Exception as e:
            logging.error(f"Rate update error: {e}")

    async def run_loop(self):
        while True:
            await self.update_rates()
            await asyncio.sleep(600)
