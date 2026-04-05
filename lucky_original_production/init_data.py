import asyncio

from core.database import async_session, init_db

from core.models import Rate, Setting

from sqlalchemy import select


async def init():

    await init_db()

    async with async_session() as session:


        new_rates = [

            {"currency": "BTC", "buy": 6850000, "sell": 6654749},

            {"currency": "ETH", "buy": 235000, "sell": 228000},

            {"currency": "LTC", "buy": 5300, "sell": 5168},

            {"currency": "TRX", "buy": 23.5, "sell": 22.0},

            {"currency": "USDT", "buy": 78.5, "sell": 76.4},

        ]


        for r_data in new_rates:

            res = await session.execute(select(Rate).where(Rate.currency == r_data["currency"]))

            rate = res.scalar_one_or_none()

            if rate:

                rate.buy_rate, rate.sell_rate = r_data["buy"], r_data["sell"]

            else:

                session.add(Rate(currency=r_data["currency"], buy_rate=r_data["buy"], sell_rate=r_data["sell"]))



        res = await session.execute(select(Setting).where(Setting.key == "support_username"))

        if not res.scalar_one_or_none():

            session.add(Setting(key="support_username", value="@luckyexchangesupport"))


        await session.commit()

        print("Данные инициализированы")


if __name__ == "__main__":

    asyncio.run(init())
