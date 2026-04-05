from aiogram import Router
from handlers import (
    admin,
    back,
    start,
    wallet,
    deposit,
    rates,
    how_to_exchange,
    about,
    review,
    profile,
    invite,
    withdraw,
    exchange,
    buy,
    sell,
    exchange_wallet,
    calculator
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