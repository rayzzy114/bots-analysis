import asyncio

import logging

import sys

from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher

from sqlalchemy import select

from sqlalchemy.orm import selectinload

from core.config import Config

from core.database import init_db, async_session

from core.models import Order, OrderStatus

from bot.middlewares import DbSessionMiddleware


async def auto_cancel_orders(bot: Bot):

    """Background task to cancel orders older than 10 minutes."""

    while True:

        try:

            async with async_session() as session:


                timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)

                query = select(Order).options(selectinload(Order.user)).where(

                    Order.status == OrderStatus.PENDING,

                    Order.created_at <= timeout_threshold

                )

                result = await session.execute(query)

                orders_to_cancel = result.scalars().all()


                for order in orders_to_cancel:


                    order.status = OrderStatus.CANCELLED



                    if order.type.value == "sell":

                        action_type = "продажу"

                        verb = "продать"

                    elif order.type.value == "mix":

                        action_type = "чистку"

                        verb = "почистить"

                    else:

                        action_type = "покупку"

                        verb = "купить"


                    amount_str = f"{order.amount_in:.2f}" if order.currency_in == "RUB" else f"{order.amount_in}"


                    text = f"""⏱ <b>Заявка отменена</b>

Заявка <code>LXY-{order.id}</code> на {action_type} {amount_str} {order.currency_in} была автоматически отменена, так как время ожидания истекло.

Если вы хотите {verb} криптовалюту, создайте новую заявку."""


                    try:

                        await bot.send_message(order.user.telegram_id, text, parse_mode="HTML")

                    except Exception as e:

                        logging.warning(f"Failed to notify user {order.user.telegram_id}: {e}")


                await session.commit()

        except Exception as e:

            logging.error(f"Error in auto_cancel_orders: {e}")


        await asyncio.sleep(60)                     


async def main():

    logging.basicConfig(

        level=logging.INFO,

        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",

    )


    try:

        Config.validate()

    except ValueError as e:

        logging.error(e)

        sys.exit(1)


    await init_db()


    bot = Bot(token=Config.BOT_TOKEN)

    dp = Dispatcher()

    dp.update.outer_middleware(DbSessionMiddleware(async_session))



    from bot.handlers import start, mixer, exchange, info, settings, admin, profile

    dp.include_router(admin.router)

    dp.include_router(start.router)

    dp.include_router(mixer.router)

    dp.include_router(exchange.router)

    dp.include_router(info.router)

    dp.include_router(settings.router)

    dp.include_router(profile.router)



    asyncio.create_task(auto_cancel_orders(bot))



    from bot.tasks import setup_scheduler

    setup_scheduler(bot)


    logging.info("Starting bot...")

    await dp.start_polling(bot)


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):

        print("Bot stopped")

    except Exception as e:

        print(f"Error: {e}")

