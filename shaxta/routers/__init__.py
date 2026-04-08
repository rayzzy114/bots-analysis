from aiogram import Router

from handlers import (
    about,
    admin,
    back,
    buy,
    calculator,
    deposit,
    exchange,
    exchange_wallet,
    how_to_exchange,
    invite,
    profile,
    rates,
    review,
    sell,
    start,
    wallet,
    withdraw,
)


def get_routers() -> list[Router]:
    return [
        admin.router,
        back.router,
        start.router,
        wallet.router,
        deposit.router,
        rates.router,
        how_to_exchange.router,
        about.router,
        review.router,
        profile.router,
        invite.router,
        calculator.router,
        withdraw.router,
        exchange.router,
        buy.router,
        sell.router,
        exchange_wallet.router
    ]
