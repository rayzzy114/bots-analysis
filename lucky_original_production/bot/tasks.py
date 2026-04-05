import asyncio

import logging

import os

from aiogram import Bot

from aiogram.types import FSInputFile

from sqlalchemy import select

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apscheduler.triggers.cron import CronTrigger


from core.database import async_session

from core.models import User



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

        broadcast_black_friday,

        trigger=CronTrigger(day_of_week='fri', hour=12, minute=0, timezone='Europe/Moscow'),

        kwargs={'bot': bot}

    )


    scheduler.start()

    return scheduler

