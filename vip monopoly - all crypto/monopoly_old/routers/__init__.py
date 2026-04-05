from aiogram import Router
from handlers import back, start, buy, partner, promo, my_orders, rules, work, admin

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