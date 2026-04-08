from aiogram import Router

from handlers import admin, back, buy, my_orders, partner, promo, rules, start, work


def get_routers() -> list[Router]:
    return [
        admin.router,
        back.router,
        start.router,
        partner.router,
        promo.router,
        my_orders.router,
        rules.router,
        work.router,
        buy.router
    ]
