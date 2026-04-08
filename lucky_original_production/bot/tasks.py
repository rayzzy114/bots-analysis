import asyncio
import logging
import os

import httpx
from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.database import async_session
from core.models import Rate, User
from sqlalchemy import select


async def update_rates():
    logging.info("Updating rates from Coingecko...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,litecoin,monero&vs_currencies=usd")
            data = resp.json()

            async with async_session() as session:
                for coin in ['bitcoin', 'litecoin', 'monero']:
                    price = data.get(coin, {}).get('usd', 0.0)
                    currency = coin.upper()

                    result = await session.execute(select(Rate).where(Rate.currency == currency))
                    rate_obj = result.scalar_one_or_none()

                    if rate_obj:
                        rate_obj.buy_rate = price * 1.05
                        rate_obj.sell_rate = price * 0.95
                    else:
                        session.add(Rate(currency=currency, buy_rate=price * 1.05, sell_rate=price * 0.95))
                await session.commit()
    except Exception as e:
        logging.error(f"Failed to update rates: {e}")



CAPTION = (

    "Черная пятница! 🍀\n\n"

    "Каждую последнюю пятницу месяца мы раздаем промо-коды на скидку 10%!\n\n"

    "Активируй промо-код в боте прямо сейчас:\n"

    "➡️ BLACKFRIDAY3001\n\n"

    "❗️ Количество использований ограничено ❗️"

)


async def broadcast_black_friday(bot: Bot):

    """Sends Black Friday message to all users."""

    logging.info("Starting Black Friday broadcast...")


    file_path = os.path.join("assets", "black_friday.jpg")

    if not os.path.exists(file_path):

        logging.error(f"File not found: {file_path}")

        return


    photo = FSInputFile(file_path)


    file_id = None


    async with async_session() as session:

        result = await session.execute(select(User.telegram_id))

        user_ids = result.scalars().all()


    count = 0

    for user_id in user_ids:

        try:



            media_to_send = file_id if file_id else photo


            message = await bot.send_photo(

                chat_id=user_id,

                photo=media_to_send,

                caption=CAPTION

            )



            if file_id is None and message.photo:


                file_id = message.photo[-1].file_id


            count += 1


            await asyncio.sleep(0.05)


        except Exception as e:



            logging.warning(f"Failed to send to {user_id}: {e}")


    logging.info(f"Broadcast finished. Sent to {count} users.")


def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        update_rates,
        trigger='interval',
        minutes=30
    )

    scheduler.add_job(
        broadcast_black_friday,
        trigger=CronTrigger(day_of_week='fri', hour=12, minute=0, timezone='Europe/Moscow'),
        kwargs={'bot': bot}
    )

    scheduler.start()
    return scheduler


